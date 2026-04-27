"""
test_full_pipeline.py — Identification test using real classical features.

ePillID images are already top-down 224×224 crops, so we can't apply
the Pi-camera-specific perspective correction from preprocess.py.
Instead we:
  • Embed with training-consistent transforms (Resize→CenterCrop→ImageNet normalise)
    and feed directly to the ONNX session (bypassing the [-1,1] conversion in
    model.py that is designed for Pi camera images).
  • Extract classical HSV+shape features using OpenCV on the raw image
    (Otsu segmentation without perspective correction).

This gives an accurate picture of the combined neural+classical pipeline
performance when inputs are correctly preprocessed.

Usage:
    python test_full_pipeline.py [--epillid_dir ePillID_data] [--n_pills 10]
"""

import sys
import argparse
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))

# Import classical feature extraction and matching logic
from preprocess import extract_features, segment_pill, _pil_to_bgr, CLASSICAL_DIM
from model import PillMatcher, CONF_HIGH, CONF_LOW, ONNX_PATH, _MEAN, _STD

try:
    import onnxruntime as ort
except ImportError:
    raise SystemExit("pip install onnxruntime")

# ── ImageNet-consistent val transform (matches train.py val_tf) ───────────────

IMG_SIZE = 224
_RESIZE  = int(IMG_SIZE * 1.14)   # = 255


def _val_transform(img: Image.Image) -> np.ndarray:
    """
    Returns [1, 3, 224, 224] float32 ImageNet-normalised array
    (same as torchvision val_tf used during training).
    """
    # Resize shorter side to 255
    w, h = img.size
    scale = _RESIZE / min(w, h)
    img   = img.resize((int(w * scale), int(h * scale)), Image.BILINEAR)

    # CenterCrop 224×224
    w, h = img.size
    x0   = (w - IMG_SIZE) // 2
    y0   = (h - IMG_SIZE) // 2
    img  = img.crop((x0, y0, x0 + IMG_SIZE, y0 + IMG_SIZE))

    # → float32 CHW, normalise with ImageNet stats
    arr  = np.array(img, dtype=np.float32) / 255.0          # [224, 224, 3] in [0,1]
    arr  = (arr - _MEAN) / _STD                              # ImageNet normalised
    chw  = arr.transpose(2, 0, 1)[np.newaxis]               # [1, 3, 224, 224]
    return chw.astype(np.float32)


def _extract_classical_epillid(img: Image.Image) -> np.ndarray:
    """
    Classical HSV+shape features from an ePillID image.
    Uses Otsu segmentation WITHOUT perspective correction
    (ePillID images are already top-down).
    Returns (68,) float32, or zeros if no pill found.
    """
    bgr  = _pil_to_bgr(img)
    mask, _ = segment_pill(bgr)
    if mask is None:
        return np.zeros(CLASSICAL_DIM, dtype=np.float32)
    return extract_features(bgr, mask)


def _l2_norm(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 1e-8 else v


# ── ONNX session ──────────────────────────────────────────────────────────────

def _build_session(onnx_path: Path) -> ort.InferenceSession:
    providers = (
        ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if "CUDAExecutionProvider" in ort.get_available_providers()
        else ["CPUExecutionProvider"]
    )
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort.InferenceSession(str(onnx_path), opts, providers)


# ── ePillID helpers ───────────────────────────────────────────────────────────

def load_epillid_groups(epillid_dir: Path, min_images: int = 3) -> dict:
    """Return {label: [image_path, ...]} for classes with >= min_images consumer photos."""
    df = pd.read_csv(epillid_dir / "all_labels.csv")
    consumer = df[~df["is_ref"]].copy()

    root   = epillid_dir / "classification_data"
    groups = defaultdict(list)
    for _, row in consumer.iterrows():
        p = root / row["image_path"]
        if p.exists():
            groups[row["label"]].append(p)

    return {k: v for k, v in groups.items() if len(v) >= min_images}


# ── embed + classical ─────────────────────────────────────────────────────────

def embed_image(sess: ort.InferenceSession, input_name: str, img_path: Path):
    """
    Returns (embedding [1280], classical [68]).
    Embedding uses training-consistent val transforms → ONNX directly.
    """
    img = Image.open(img_path).convert("RGB")

    # Neural embedding (ImageNet-normalised → ONNX)
    inp = _val_transform(img)
    out = sess.run(None, {input_name: inp})[0]
    emb = _l2_norm(out[0])

    # Classical features (Otsu on raw image, no perspective correction)
    cls = _extract_classical_epillid(img)

    return emb, cls


# ── main test ─────────────────────────────────────────────────────────────────

def run_test(epillid_dir: Path, n_pills: int, n_ref: int):
    if not ONNX_PATH.exists():
        raise SystemExit(f"ONNX model not found: {ONNX_PATH}\nRun train.py first.")

    sess       = _build_session(ONNX_PATH)
    input_name = sess.get_inputs()[0].name
    matcher    = PillMatcher()

    groups = load_epillid_groups(epillid_dir, min_images=n_ref + 1)
    labels = sorted(groups.keys())[:n_pills]
    if len(labels) < n_pills:
        print(f"Warning: only {len(labels)} classes with >= {n_ref+1} consumer images")

    # ── Registration ──────────────────────────────────────────────────────────
    ref_embeddings, ref_classicals, nhi_codes = [], [], []

    print(f"\nRegistering {len(labels)} pill types ({n_ref} reference images each)...")
    for label in labels:
        paths = groups[label]
        embs, clss = [], []
        for p in paths[:n_ref]:
            emb, cls = embed_image(sess, input_name, p)
            embs.append(emb)
            clss.append(cls)

        ref_embeddings.append(_l2_norm(np.mean(embs, axis=0)))
        ref_classicals.append(np.mean(clss, axis=0))
        nhi_codes.append(label)

    ref_embs = np.stack(ref_embeddings).astype(np.float32)
    ref_cls  = np.stack(ref_classicals).astype(np.float32)

    # ── Identification ────────────────────────────────────────────────────────
    print(f"\nThresholds: CONF_HIGH={CONF_HIGH}  CONF_LOW={CONF_LOW}")
    print(f"Classical weight: {matcher.classical_weight}\n")

    correct = wrong = 0
    for true_label in nhi_codes:
        query_path = groups[true_label][n_ref]
        emb, cls   = embed_image(sess, input_name, query_path)

        pred_code, confidence, result = matcher.match(
            emb, cls, ref_embs, ref_cls, nhi_codes
        )

        ok  = pred_code == true_label
        tag = "[OK]" if ok else "[XX]"
        if ok:
            correct += 1
        else:
            wrong += 1

        true_short = true_label[:30]
        pred_short = (pred_code or "")[:30]
        print(f"  {tag}  true={true_short:<30s}  pred={pred_short:<30s}  conf={confidence:.3f}  {result}")

    total = correct + wrong
    pct   = 100 * correct / total if total else 0.0
    print(f"\nAccuracy: {correct}/{total}  ({pct:.1f}%)")

    # ── Calibration report ────────────────────────────────────────────────────
    from model import CONF_HIGH, CONF_LOW
    print(f"\nNote: MATCH >= {CONF_HIGH} | UNSURE {CONF_LOW}-{CONF_HIGH} | NO_MATCH < {CONF_LOW}")
    print("Classical features help most when pills differ in colour or shape.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epillid_dir", default="ePillID_data")
    parser.add_argument("--n_pills", type=int, default=10)
    parser.add_argument("--n_ref",   type=int, default=2)
    args = parser.parse_args()

    run_test(
        epillid_dir = Path(args.epillid_dir),
        n_pills     = args.n_pills,
        n_ref       = args.n_ref,
    )
