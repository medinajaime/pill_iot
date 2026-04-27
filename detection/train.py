"""
train.py — Fine-tune MobileNetV2 on ePillID (PyTorch) and export to ONNX.

Requires PyTorch with CUDA 12.8 for RTX 5080 (Blackwell):
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
    pip install onnx onnxruntime tqdm pandas scikit-learn

Then run:
    python train.py --epillid_dir ePillID_data
    python train.py --epillid_dir ePillID_data --epochs 30

ePillID dataset layout expected
---------------------------------
    ePillID_data/
        all_labels.csv                      ← label index for all images
        classification_data/
            fcn_mix_weight/dc_224/          ← consumer photos (main training set)
            fcn_mix_weight/dr_224/          ← reference photos
            segmented_nih_pills_224/        ← segmented images

Output
------
    models/pill_embedding.onnx   — copy this to the Pi

Two-phase training with ArcFace loss
-------------------------------------
    Phase 1: frozen backbone, train ArcFace head only          (~5 epochs)
    Phase 2: unfreeze last 2 MobileNetV2 feature blocks, fine-tune  (~N epochs)

    ArcFace adds an angular margin to the classification loss which forces
    embeddings of different pill classes to be angularly separated on the
    unit hypersphere. This directly improves cosine-similarity matching.
"""

import argparse
import time
from pathlib import Path
from PIL import Image

import numpy as np

# ── torch ─────────────────────────────────────────────────────────────────────

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, random_split
    from torchvision import datasets, transforms, models
except ImportError:
    raise SystemExit(
        "PyTorch is required.\n"
        "Install for RTX 5080 (CUDA 12.8):\n"
        "  pip install torch torchvision "
        "--index-url https://download.pytorch.org/whl/cu128"
    )

try:
    import onnx
except ImportError:
    raise SystemExit("Install onnx:  pip install onnx")

try:
    import pandas as pd
except ImportError:
    raise SystemExit("Install pandas:  pip install pandas")

try:
    from sklearn.model_selection import train_test_split
except ImportError:
    raise SystemExit("Install scikit-learn:  pip install scikit-learn")

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

# ── paths & constants ─────────────────────────────────────────────────────────

MODEL_DIR  = Path(__file__).parent / "models"
ONNX_PATH  = MODEL_DIR / "pill_embedding.onnx"

IMG_SIZE    = 224
EMBED_DIM   = 1280     # MobileNetV2 final conv output channels
NORM_MEAN   = [0.485, 0.456, 0.406]   # ImageNet stats (torchvision convention)
NORM_STD    = [0.229, 0.224, 0.225]


# ── ArcFace loss ──────────────────────────────────────────────────────────────

class ArcFaceLoss(nn.Module):
    """
    Additive Angular Margin Loss (ArcFace, Deng et al. 2019).

    Adds a fixed angular margin `m` to the angle between the embedding and
    the target class weight vector. This forces inter-class angular separation
    directly in the embedding space, making cosine-similarity matching reliable.

    s=64 and m=0.5 are standard values from the original paper.
    """

    def __init__(self, embed_dim: int, num_classes: int, s: float = 64.0, m: float = 0.5):
        super().__init__()
        self.s = s
        self.m = m
        self.W = nn.Parameter(torch.empty(embed_dim, num_classes))
        nn.init.xavier_uniform_(self.W)

    def forward(self, embeddings: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        # Both embeddings and W columns are L2-normalised → dot = cosine
        W_norm  = F.normalize(self.W, p=2, dim=0)
        cosine  = torch.clamp(embeddings @ W_norm, -1.0 + 1e-7, 1.0 - 1e-7)  # [B, C]
        theta   = torch.acos(cosine)

        # Add margin only to the target class
        one_hot = torch.zeros_like(cosine).scatter_(1, labels.unsqueeze(1), 1.0)
        output  = torch.cos(theta + self.m * one_hot)

        return F.cross_entropy(output * self.s, labels)


# ── model ─────────────────────────────────────────────────────────────────────

class PillEmbedder(nn.Module):
    """
    MobileNetV2 backbone → 1280-dim L2-normalised embedding.
    ArcFaceLoss is used during training; at export only embed() is kept.
    """

    def __init__(self, num_classes: int):
        super().__init__()
        base = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
        self.backbone = base.features           # [B, 1280, 7, 7]
        self.pool     = nn.AdaptiveAvgPool2d(1) # [B, 1280, 1, 1]
        self.arcface  = ArcFaceLoss(EMBED_DIM, num_classes)

    def embed(self, x: torch.Tensor) -> torch.Tensor:
        """L2-normalised [B, 1280] embedding — used at export and inference."""
        feat = self.pool(self.backbone(x)).flatten(1)
        return F.normalize(feat, p=2, dim=1)

    def forward(self, x: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        """Return ArcFace loss scalar for training."""
        return self.arcface(self.embed(x), labels)

    def freeze_backbone(self):
        for p in self.backbone.parameters():
            p.requires_grad = False

    def unfreeze_top_blocks(self, n_blocks: int = 2):
        total = len(self.backbone)   # 19 blocks in MobileNetV2
        for i, layer in enumerate(self.backbone):
            for p in layer.parameters():
                p.requires_grad = i >= (total - n_blocks)


# ── data ──────────────────────────────────────────────────────────────────────

class EpillIDDataset(torch.utils.data.Dataset):
    """
    Loads ePillID images using all_labels.csv.

    The CSV maps each image filename to a pill-type label string.
    We encode labels as integers and return (image_tensor, label_int).

    img_source controls which image set to use:
        'consumer'   — fcn_mix_weight/dc_224/  (varied conditions, best for training)
        'reference'  — fcn_mix_weight/dr_224/  (studio quality)
        'segmented'  — segmented_nih_pills_224/ (already cropped)
        'all'        — all three combined
    """

    def __init__(
        self,
        epillid_dir: Path,
        indices: list,
        df: "pd.DataFrame",
        label2idx: dict,
        transform,
        img_source: str = "consumer",
    ):
        self.root      = Path(epillid_dir) / "classification_data"
        self.df        = df.iloc[indices].reset_index(drop=True)
        self.label2idx = label2idx
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row       = self.df.iloc[idx]
        img_path  = self.root / row["image_path"]
        label_idx = self.label2idx[row["label"]]
        img = Image.open(img_path).convert("RGB")
        return self.transform(img), label_idx


def build_loaders(
    epillid_dir: Path,
    batch_size:  int,
    val_frac:    float = 0.25,
    seed:        int   = 42,
    img_source:  str   = "consumer",
) -> tuple:
    """
    Returns (train_loader, val_loader, num_classes).

    Stratified split: each pill type appears in both train and val
    (where possible — types with only 1 image go to train only).
    """
    csv_path = Path(epillid_dir) / "all_labels.csv"
    df       = pd.read_csv(csv_path)

    # Filter by image source
    if img_source == "consumer":
        df = df[df["image_path"].str.startswith("fcn_mix_weight/dc_224")]
    elif img_source == "reference":
        df = df[df["image_path"].str.startswith("fcn_mix_weight/dr_224")]
    elif img_source == "segmented":
        df = df[df["image_path"].str.startswith("segmented_nih_pills_224")]
    # 'all' keeps everything

    df = df.reset_index(drop=True)

    # Encode string labels to integers
    unique_labels = sorted(df["label"].unique())
    label2idx     = {lbl: i for i, lbl in enumerate(unique_labels)}
    num_classes   = len(unique_labels)

    # Stratified split — types with only 1 sample can't be stratified,
    # put them in training only
    counts    = df["label"].value_counts()
    singleton = counts[counts == 1].index
    multi_df  = df[~df["label"].isin(singleton)]
    solo_df   = df[ df["label"].isin(singleton)]

    train_idx, val_idx = train_test_split(
        multi_df.index.tolist(),
        test_size        = val_frac,
        stratify         = multi_df["label"].values,
        random_state     = seed,
    )
    train_idx = train_idx + solo_df.index.tolist()

    train_tf = transforms.Compose([
        transforms.RandomResizedCrop(IMG_SIZE, scale=(0.75, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(),
        transforms.RandomRotation(30),
        transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.25, hue=0.05),
        transforms.ToTensor(),
        transforms.Normalize(NORM_MEAN, NORM_STD),
    ])
    val_tf = transforms.Compose([
        transforms.Resize(int(IMG_SIZE * 1.14)),
        transforms.CenterCrop(IMG_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(NORM_MEAN, NORM_STD),
    ])

    train_ds = EpillIDDataset(epillid_dir, train_idx, df, label2idx, train_tf)
    val_ds   = EpillIDDataset(epillid_dir, val_idx,   df, label2idx, val_tf)

    print(f"  Train: {len(train_ds)} images  |  Val: {len(val_ds)} images  |  Classes: {num_classes}")

    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True,
        num_workers=4, pin_memory=True, persistent_workers=True,
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False,
        num_workers=4, pin_memory=True, persistent_workers=True,
    )
    return train_loader, val_loader, num_classes


# ── training loop ─────────────────────────────────────────────────────────────

def run_epoch(
    model:     PillEmbedder,
    loader:    DataLoader,
    optimiser: torch.optim.Optimizer,
    device:    torch.device,
    train:     bool,
) -> float:
    """Returns mean loss for the epoch. ArcFace loss doesn't give accuracy."""
    model.train(train)
    total_loss = total = 0

    it = tqdm(loader, leave=False) if tqdm else loader
    with torch.set_grad_enabled(train):
        for imgs, labels in it:
            imgs, labels = imgs.to(device), labels.to(device)
            loss = model(imgs, labels)   # ArcFace returns loss scalar directly

            if train:
                optimiser.zero_grad()
                loss.backward()
                optimiser.step()

            total_loss += loss.item() * len(imgs)
            total      += len(imgs)

    return total_loss / total


def train(
    epillid_dir: Path,
    epochs:      int   = 30,
    batch_size:  int   = 64,
    lr_phase1:   float = 1e-3,
    lr_phase2:   float = 1e-5,
    img_source:  str   = "consumer",
) -> PillEmbedder:

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDevice: {device}")
    if device.type == "cuda":
        print(f"GPU:    {torch.cuda.get_device_name(0)}")

    train_loader, val_loader, num_classes = build_loaders(
        epillid_dir, batch_size, img_source=img_source
    )
    print(f"Classes: {num_classes}\n")

    model = PillEmbedder(num_classes).to(device)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    best_val_loss    = float("inf")
    patience_counter = 0
    patience         = 7
    ckpt_path        = MODEL_DIR / "best.pt"

    # ── Phase 1: warm up ArcFace head, backbone frozen ────────────────────────
    model.freeze_backbone()
    phase1_epochs = max(1, epochs // 6)
    opt1   = torch.optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()), lr=lr_phase1
    )
    sched1 = torch.optim.lr_scheduler.CosineAnnealingLR(opt1, phase1_epochs)

    print(f"── Phase 1 (frozen backbone, {phase1_epochs} epochs) ──")
    for ep in range(1, phase1_epochs + 1):
        t0      = time.time()
        tr_loss = run_epoch(model, train_loader, opt1, device, train=True)
        va_loss = run_epoch(model, val_loader,   opt1, device, train=False)
        sched1.step()
        print(f"  ep {ep:3d}  loss {tr_loss:.4f}/{va_loss:.4f}  ({time.time()-t0:.0f}s)")
        if va_loss < best_val_loss:
            best_val_loss = va_loss
            torch.save(model.state_dict(), ckpt_path)

    # ── Phase 2: fine-tune top backbone blocks ────────────────────────────────
    model.unfreeze_top_blocks(n_blocks=2)
    opt2   = torch.optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()), lr=lr_phase2
    )
    sched2 = torch.optim.lr_scheduler.CosineAnnealingLR(opt2, epochs)

    print(f"\n── Phase 2 (fine-tune top 2 blocks, up to {epochs} epochs) ──")
    for ep in range(1, epochs + 1):
        t0      = time.time()
        tr_loss = run_epoch(model, train_loader, opt2, device, train=True)
        va_loss = run_epoch(model, val_loader,   opt2, device, train=False)
        sched2.step()
        marker = ""
        if va_loss < best_val_loss:
            best_val_loss = va_loss
            torch.save(model.state_dict(), ckpt_path)
            patience_counter = 0
            marker = " ✓"
        else:
            patience_counter += 1
        print(f"  ep {ep:3d}  loss {tr_loss:.4f}/{va_loss:.4f}  ({time.time()-t0:.0f}s){marker}")
        if patience_counter >= patience:
            print(f"  Early stop ({patience} epochs without improvement)")
            break

    print(f"\nBest val loss: {best_val_loss:.4f}")
    model.load_state_dict(torch.load(ckpt_path, map_location=device))
    return model


# ── ONNX export ───────────────────────────────────────────────────────────────

def export_onnx(model: PillEmbedder, epillid_dir: Path = None):
    """
    Export the embed() path (no classifier head) to ONNX.
    Input:  [1, 3, 224, 224] float32  (ImageNet-normalised)
    Output: [1, 1280] float32  (L2-normalised embedding)
    """
    model.eval()

    # Wrapper that only runs the embed() path
    class EmbedOnly(nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m
        def forward(self, x):
            return self.m.embed(x)

    wrapper   = EmbedOnly(model).cpu()
    dummy_inp = torch.zeros(1, 3, IMG_SIZE, IMG_SIZE)

    torch.onnx.export(
        wrapper,
        dummy_inp,
        str(ONNX_PATH),
        input_names    = ["image"],
        output_names   = ["embedding"],
        dynamic_axes   = {"image": {0: "batch"}, "embedding": {0: "batch"}},
        opset_version  = 17,
        do_constant_folding = True,
    )

    # Verify the exported model
    onnx.checker.check_model(str(ONNX_PATH))
    size_kb = ONNX_PATH.stat().st_size / 1024
    print(f"\nExported → {ONNX_PATH}  ({size_kb:.0f} KB)")
    print("Copy models/pill_embedding.onnx to the Pi.")


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fine-tune MobileNetV2 on ePillID and export ONNX"
    )
    parser.add_argument(
        "--epillid_dir", type=Path,
        default=Path(__file__).parent / "ePillID_data",
        help="Root of the ePillID dataset (contains all_labels.csv)",
    )
    parser.add_argument(
        "--img_source", type=str, default="consumer",
        choices=["consumer", "reference", "segmented", "all"],
        help="Which image set to train on (default: consumer)",
    )
    parser.add_argument("--epochs",     type=int,   default=30)
    parser.add_argument("--batch_size", type=int,   default=64)
    parser.add_argument("--lr_phase1",  type=float, default=1e-3)
    parser.add_argument("--lr_phase2",  type=float, default=1e-5)
    args = parser.parse_args()

    if not (args.epillid_dir / "all_labels.csv").exists():
        raise SystemExit(
            f"\nall_labels.csv not found in: {args.epillid_dir}\n\n"
            "Expected layout:\n"
            "  ePillID_data/\n"
            "    all_labels.csv\n"
            "    classification_data/\n"
            "      fcn_mix_weight/dc_224/\n"
            "      fcn_mix_weight/dr_224/\n"
        )

    trained = train(
        epillid_dir = args.epillid_dir,
        epochs      = args.epochs,
        batch_size  = args.batch_size,
        lr_phase1   = args.lr_phase1,
        lr_phase2   = args.lr_phase2,
        img_source  = args.img_source,
    )
    export_onnx(trained, args.epillid_dir)
