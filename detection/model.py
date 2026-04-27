"""
model.py — ONNX Runtime embedding model + pill matching.

The model is a MobileNetV2 backbone (fine-tuned on ePillID via train.py)
exported to ONNX. It outputs a 1280-dim L2-normalised embedding per image.

Input convention (must match train.py):
    [1, 3, 224, 224] float32, ImageNet-normalised:
        pixel = (rgb/255 - mean) / std
        mean = [0.485, 0.456, 0.406]
        std  = [0.229, 0.224, 0.225]

    Note: preprocess.py outputs MobileNetV2 Keras convention ([-1,1]).
    This file handles the re-normalisation before feeding the ONNX model.

Matching — three-tier confidence:
    MATCH    confidence ≥ CONF_HIGH  → auto-route
    UNSURE   CONF_LOW ≤ conf < HIGH  → hold, notify app for confirmation
    NO_MATCH confidence < CONF_LOW   → hold, alert caregiver
"""

from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

# ── ONNX Runtime ──────────────────────────────────────────────────────────────

try:
    import onnxruntime as ort
    _ORT_OK = True
except ImportError:
    _ORT_OK = False

# ── paths ─────────────────────────────────────────────────────────────────────

MODEL_DIR  = Path(__file__).parent / "models"
ONNX_PATH  = MODEL_DIR / "pill_embedding.onnx"

# ── ImageNet normalisation (torchvision convention used in train.py) ──────────

_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# ── confidence thresholds ─────────────────────────────────────────────────────
#
# Confidence = margin between top-1 and top-2 combined similarity score.
# Calibrated on ePillID consumer photos in a 10-pill identification task:
#   correct-pill margins typically: 0.04 – 0.15
#   wrong-pill margins (confused pairs): < 0.05
#
# Tune CONF_HIGH down further once you have real Taiwan pill images:
# if the chamber lighting gives clean segmentation, margins should widen.

CONF_HIGH = 0.10   # ≥ this → MATCH (auto-route)
CONF_LOW  = 0.04   # < this → NO_MATCH (alert); between → UNSURE (ask user)

# How much weight to give classical features vs neural embedding.
# Classical features (HSV histogram, shape) are strong on colour and size —
# exactly what differentiates most prescription pill types.
CLASSICAL_WEIGHT = 0.35

RESULT_MATCH    = "MATCH"
RESULT_UNSURE   = "UNSURE"
RESULT_NO_MATCH = "NO_MATCH"


# ── embedding model ───────────────────────────────────────────────────────────

class EmbeddingModel:
    """
    Wraps the ONNX pill-embedding model.

    Accepts images pre-processed by preprocess.py (float32 [224,224,3] in [-1,1])
    and handles the re-normalisation to ImageNet stats internally.
    """

    def __init__(self, model_path: Path = ONNX_PATH):
        if not _ORT_OK:
            raise RuntimeError(
                "onnxruntime is not installed.\n"
                "  Pi:          pip install onnxruntime\n"
                "  Dev machine: pip install onnxruntime  (or onnxruntime-gpu)"
            )
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"ONNX model not found: {model_path}\n"
                "Run train.py first to generate models/pill_embedding.onnx,\n"
                "then copy it to the Pi."
            )

        # Provider selection — RTX 5080 (CUDA 12.8) gets full GPU path.
        # TensorrtExecutionProvider is fastest on NVIDIA but requires TRT install;
        # CUDAExecutionProvider is always available with onnxruntime-gpu.
        available = ort.get_available_providers()
        if "TensorrtExecutionProvider" in available:
            providers = [
                ("TensorrtExecutionProvider", {
                    "trt_max_workspace_size": 1 << 30,   # 1 GB workspace
                    "trt_fp16_enable": True,              # FP16 on RTX 5080
                }),
                "CUDAExecutionProvider",
                "CPUExecutionProvider",
            ]
        elif "CUDAExecutionProvider" in available:
            providers = [
                ("CUDAExecutionProvider", {
                    "device_id": 0,
                    "arena_extend_strategy": "kNextPowerOfTwo",
                    "cudnn_conv_algo_search": "EXHAUSTIVE",
                    "do_copy_in_default_stream": True,
                }),
                "CPUExecutionProvider",
            ]
        else:
            providers = ["CPUExecutionProvider"]

        sess_opts = ort.SessionOptions()
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_opts.intra_op_num_threads = 1   # GPU path; CPU threads not needed
        self._sess       = ort.InferenceSession(str(model_path), sess_opts, providers)
        self._input_name = self._sess.get_inputs()[0].name
        _active = self._sess.get_providers()[0]
        print(f"[model] Inference provider: {_active}")

    def embed(self, arr: np.ndarray) -> np.ndarray:
        """
        arr : [224, 224, 3] float32 in [-1, 1]  (preprocess.py output)
        Returns [1280] L2-normalised float32.
        """
        # preprocess.py: pixel = rgb/127.5 - 1  →  rgb = (pixel + 1) * 127.5
        # ONNX model expects: (rgb/255 - mean) / std
        rgb    = (arr + 1.0) * 127.5 / 255.0               # [224,224,3] in [0,1]
        normed = (rgb - _MEAN) / _STD                       # ImageNet normalised
        # ONNX expects [batch, channels, H, W]
        chw    = normed.transpose(2, 0, 1)[np.newaxis]      # [1, 3, 224, 224]
        out    = self._sess.run(None, {self._input_name: chw.astype(np.float32)})[0]
        return _l2_norm(out[0])                              # [1280]


# ── matching ──────────────────────────────────────────────────────────────────

class PillMatcher:
    """
    Compares a query pill against all registered profiles.
    Primary signal: neural cosine similarity.
    Secondary signal: classical HSV + shape feature distance.
    """

    def __init__(
        self,
        conf_high:        float = CONF_HIGH,
        conf_low:         float = CONF_LOW,
        classical_weight: float = CLASSICAL_WEIGHT,
    ):
        self.conf_high        = conf_high
        self.conf_low         = conf_low
        self.classical_weight = classical_weight

    def match(
        self,
        query_emb: np.ndarray,          # [1280]
        query_cls: np.ndarray,          # [68]
        ref_embeddings: np.ndarray,     # [N, 1280]
        ref_classicals: np.ndarray,     # [N, 68]
        nhi_codes: List[str],
    ) -> Tuple[Optional[str], float, str]:
        """
        Returns (best_nhi_code, confidence, result_label).
        """
        n = len(nhi_codes)
        if n == 0:
            return None, 0.0, RESULT_NO_MATCH

        # Neural: cosine similarity (both vectors are L2-normalised)
        neural_sims = (ref_embeddings @ query_emb).astype(np.float32)   # [N]

        # Classical: combined histogram + shape similarity
        cls_sims = np.array(
            [_classical_similarity(query_cls, ref_classicals[i]) for i in range(n)],
            dtype=np.float32,
        )

        combined = (
            (1.0 - self.classical_weight) * neural_sims
            + self.classical_weight       * cls_sims
        )

        best_idx = int(np.argmax(combined))
        best_sim = float(combined[best_idx])

        if n == 1:
            # Only one reference — use absolute similarity mapped to [0,1]
            confidence = float((best_sim + 1.0) / 2.0)
        else:
            sorted_sims = np.sort(combined)[::-1]
            # Margin in [0, 2]; clamp to [0, 1] as confidence
            confidence  = float(np.clip(sorted_sims[0] - sorted_sims[1], 0.0, 1.0))

        if confidence >= self.conf_high:
            result = RESULT_MATCH
        elif confidence >= self.conf_low:
            result = RESULT_UNSURE
        else:
            result = RESULT_NO_MATCH

        return nhi_codes[best_idx], confidence, result


# ── classical similarity helpers ──────────────────────────────────────────────

def _classical_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Similarity in [0,1] from a 68-dim classical feature vector.
    [0:32]  H histogram  → chi-squared similarity
    [32:64] S histogram  → chi-squared similarity
    [64:68] shape feats  → L2 distance → similarity
    """
    h_sim    = _chi2_sim(a[:32],  b[:32])
    s_sim    = _chi2_sim(a[32:64], b[32:64])
    shp_dist = float(np.linalg.norm(a[64:] - b[64:]))
    shp_sim  = 1.0 / (1.0 + shp_dist)
    return 0.5 * h_sim + 0.3 * s_sim + 0.2 * shp_sim


def _chi2_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Chi-squared histogram similarity: 1.0 = identical histograms."""
    denom = a + b + 1e-8
    dist  = float(np.sum((a - b) ** 2 / denom))
    return float(np.exp(-dist))


def _l2_norm(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 1e-8 else v
