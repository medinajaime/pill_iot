"""
preprocess.py — Image preprocessing for the optical chamber.

Pipeline:
  1. Perspective correction  — camera is tilted 45 deg, so X is foreshortened
                               by cos(45°) = 0.707; we stretch X by 1.414 to
                               recover the pill's true top-down aspect ratio.
  2. Pill segmentation       — Otsu threshold on the matte-white background.
  3. Crop + square-pad       — tight crop around pill, padded to square.
  4. Resize                  — 224×224 for MobileNetV2 input.
  5. Normalise               — float32 in [-1, 1] (MobileNetV2 convention).
  6. Classical features      — HSV colour histogram + shape descriptors.
                               Used alongside the neural embedding for matching.
"""

from typing import Tuple, Optional
import cv2
import numpy as np
from PIL import Image

# ── physical constants (from CAD) ─────────────────────────────────────────────

_TILT_DEG   = 45.0
X_STRETCH   = 1.0 / np.cos(np.radians(_TILT_DEG))   # ≈ 1.4142

# ── model input ───────────────────────────────────────────────────────────────

MODEL_INPUT_SIZE = (224, 224)   # (width, height) for cv2.resize

# ── helpers ───────────────────────────────────────────────────────────────────

def _pil_to_bgr(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def _bgr_to_pil(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))


# ── step 1: perspective correction ───────────────────────────────────────────

def correct_perspective(bgr: np.ndarray) -> np.ndarray:
    """
    Stretch the X-axis by 1/cos(45°) to undo the camera tilt foreshortening.
    Applied before segmentation so shape features are correct.
    """
    h, w = bgr.shape[:2]
    new_w = int(round(w * X_STRETCH))
    return cv2.resize(bgr, (new_w, h), interpolation=cv2.INTER_LINEAR)


# ── step 2: pill segmentation ─────────────────────────────────────────────────

def segment_pill(
    bgr: np.ndarray,
) -> Tuple[Optional[np.ndarray], dict]:
    """
    Separate pill from matte-white PETG background via Otsu thresholding.
    Returns (binary_mask uint8, stats_dict) or (None, {}) if nothing found.
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # Otsu threshold: white BG → high value → pill is the dark blob
    _, mask = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    # Morphological cleanup: close small holes, remove noise
    kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kern, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kern, iterations=1)

    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        return None, {}

    # Largest contour = pill
    pill_cnt = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(pill_cnt)

    # Sanity check: reject tiny blobs (dust) and blobs filling the whole frame
    img_area = bgr.shape[0] * bgr.shape[1]
    if area < 200 or area > img_area * 0.90:
        return None, {}

    clean = np.zeros_like(mask)
    cv2.drawContours(clean, [pill_cnt], -1, 255, cv2.FILLED)

    x, y, w, h = cv2.boundingRect(pill_cnt)
    M = cv2.moments(pill_cnt)
    denom = M["m00"] if M["m00"] else 1.0
    cx = int(M["m10"] / denom)
    cy = int(M["m01"] / denom)

    stats = {
        "bbox":     (x, y, w, h),
        "centroid": (cx, cy),
        "area_px":  area,
    }
    return clean, stats


# ── steps 3-4: crop and square-pad ───────────────────────────────────────────

def _crop_to_pill(
    bgr: np.ndarray,
    mask: np.ndarray,
    pad_frac: float = 0.15,
) -> np.ndarray:
    """Tight crop around mask bounding rect with proportional padding."""
    x, y, w, h = cv2.boundingRect(mask)
    px = int(w * pad_frac)
    py = int(h * pad_frac)
    H, W = bgr.shape[:2]

    x1, y1 = max(0, x - px), max(0, y - py)
    x2, y2 = min(W, x + w + px), min(H, y + h + py)

    crop      = bgr[y1:y2, x1:x2].copy()
    crop_mask = mask[y1:y2, x1:x2]
    crop[crop_mask == 0] = 255      # restore white background outside pill
    return crop


def _pad_to_square(bgr: np.ndarray, fill: int = 255) -> np.ndarray:
    h, w = bgr.shape[:2]
    size  = max(h, w)
    out   = np.full((size, size, 3), fill, dtype=np.uint8)
    dy    = (size - h) // 2
    dx    = (size - w) // 2
    out[dy:dy + h, dx:dx + w] = bgr
    return out


# ── step 6: classical feature extraction ─────────────────────────────────────
#
# Returns a 68-dim float32 vector: [64-dim HSV histogram | 4-dim shape].
# HSV is more robust to LED brightness drift than BGR:
#   H (hue, 32 bins, 0-180) captures colour identity.
#   S (saturation, 32 bins, 0-255) captures how vivid vs white/grey the pill is.
#   V (value/brightness) is skipped — it varies with LED intensity.
# Shape features are dimensionless ratios, stable across registration sessions.

_HIST_BINS_H = 32
_HIST_BINS_S = 32
CLASSICAL_DIM = _HIST_BINS_H + _HIST_BINS_S + 4   # 68


def extract_features(bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Compute 68-dim classical feature vector from full-resolution pill region.
    Call this BEFORE cropping/resizing so shape ratios are accurate.

    Returns float32 array of shape (68,).
    """
    hsv      = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    pill_mask = (mask > 0).astype(np.uint8)

    # — HSV histogram (pill pixels only) —
    h_hist = cv2.calcHist([hsv], [0], pill_mask, [_HIST_BINS_H], [0, 180]).flatten()
    s_hist = cv2.calcHist([hsv], [1], pill_mask, [_HIST_BINS_S], [0, 256]).flatten()

    # L1 normalise so different pill sizes give comparable histograms
    h_hist = h_hist / (h_hist.sum() + 1e-7)
    s_hist = s_hist / (s_hist.sum() + 1e-7)

    # — Shape features —
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        cnt  = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(cnt)
        peri = cv2.arcLength(cnt, True)
        x, y, bw, bh = cv2.boundingRect(cnt)

        # Rotation-invariant elongation: short/long side ratio; 1.0=square, →0=needle
        aspect_ratio = min(bw, bh) / (max(bw, bh) + 1e-7)
        # 1.0 = perfect circle; elongated capsule → lower value
        circularity  = (4 * np.pi * area) / (peri ** 2 + 1e-7)
        # how much of bounding rect is filled (tablets → high, capsules → lower)
        extent       = area / (bw * bh + 1e-7)
        # relative size vs image area — helps distinguish small (#5) from large (#000)
        img_area     = bgr.shape[0] * bgr.shape[1]
        rel_area     = area / (img_area + 1e-7)
    else:
        aspect_ratio = circularity = extent = rel_area = 0.0

    shape_vec = np.array(
        [aspect_ratio, circularity, extent, rel_area], dtype=np.float32
    )

    return np.concatenate([h_hist, s_hist, shape_vec]).astype(np.float32)


# ── main entry point ──────────────────────────────────────────────────────────

def preprocess(
    img: Image.Image,
    target_size: Tuple[int, int] = MODEL_INPUT_SIZE,
) -> Tuple[np.ndarray, dict]:
    """
    Full preprocessing pipeline.

    Parameters
    ----------
    img : PIL Image (RGB)
    target_size : (width, height) for model input

    Returns
    -------
    arr  : float32 [H, W, 3] normalised to [-1, 1]  — model input
    meta : dict with keys:
             pill_found       bool
             bbox             (x, y, w, h)
             centroid         (cx, cy)
             area_px          float
             classical        np.ndarray (68,) — HSV hist + shape features
    """
    bgr = _pil_to_bgr(img)

    # 1. Perspective correction
    bgr = correct_perspective(bgr)

    # 2. Segment
    mask, stats = segment_pill(bgr)
    if mask is None:
        blank = np.ones((*target_size[::-1], 3), dtype=np.float32)
        return blank, {"pill_found": False}

    stats["pill_found"] = True

    # 3. Classical features — computed on full-res corrected image
    stats["classical"] = extract_features(bgr, mask)

    # 4. Crop
    cropped = _crop_to_pill(bgr, mask)

    # 5. Square pad
    squared = _pad_to_square(cropped)

    # 6. Resize (target_size is (W, H) for cv2)
    resized = cv2.resize(squared, target_size, interpolation=cv2.INTER_AREA)

    # 7. BGR → RGB, normalise to [-1, 1]
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    arr = rgb.astype(np.float32) / 127.5 - 1.0

    return arr, stats


def preprocess_for_display(img: Image.Image) -> Image.Image:
    """Return a perspective-corrected, cropped pill image suitable for display."""
    bgr  = _pil_to_bgr(img)
    bgr  = correct_perspective(bgr)
    mask, _ = segment_pill(bgr)
    if mask is None:
        return img
    cropped = _crop_to_pill(bgr, mask)
    squared = _pad_to_square(cropped)
    return _bgr_to_pil(squared)
