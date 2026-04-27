"""
pipeline.py — End-to-end pill detection and sorting pipeline.

State machine per pill:
  IDLE → IMAGING → MATCHING → MATCH    → route (trapdoor opens, carousel moves)
                             → UNSURE  → hold, notify app, await confirmation
                             → NO_MATCH → hold, alert app

Auto-registration:
  When a pill matches an UNREGISTERED prescription medication with sufficient
  confidence (based on NHI colour/shape priors), it is auto-registered as the
  reference profile without user interaction. Once at least MIN_REG_SAMPLES pills
  of that type have been seen, the embedding is locked in.

  If the NHI priors alone are ambiguous (two white round tablets), the system
  emits UNSURE and the confirmation response from the app is used to finalise
  the registration.
"""

import asyncio
import base64
import io
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np
from PIL import Image

from database import PillDatabase
from model import EmbeddingModel, PillMatcher, RESULT_MATCH, RESULT_UNSURE, RESULT_NO_MATCH
from preprocess import preprocess, preprocess_for_display

# ── constants ─────────────────────────────────────────────────────────────────

MIN_REG_SAMPLES = 3     # accumulate this many pills before locking the profile
HOLD_TIMEOUT_S  = 120   # seconds to wait for confirmation before escalating

# NHI colour / shape strings (as they appear in the prescription JSON)
_NHI_COLOR_MAP = {
    "white":  np.array([200, 200, 200], dtype=np.float32),   # approximate BGR
    "yellow": np.array([40,  220, 220], dtype=np.float32),
    "red":    np.array([60,  60,  220], dtype=np.float32),
    "orange": np.array([40,  130, 230], dtype=np.float32),
    "pink":   np.array([160, 120, 230], dtype=np.float32),
    "blue":   np.array([200, 100, 80],  dtype=np.float32),
    "green":  np.array([60,  180, 80],  dtype=np.float32),
    "brown":  np.array([30,  60,  100], dtype=np.float32),
    "grey":   np.array([150, 150, 150], dtype=np.float32),
    "purple": np.array([170, 60,  120], dtype=np.float32),
}

_NHI_SHAPE_CIRCULARITY = {
    "round":   0.90,
    "oval":    0.70,
    "capsule": 0.55,
    "oblong":  0.50,
    "other":   0.65,
}


# ── per-pill accumulator for auto-registration ─────────────────────────────────

@dataclass
class _Accumulator:
    """Collects embeddings and classical features across multiple pills
    of the same type until MIN_REG_SAMPLES is reached."""
    nhi_code:    str
    embeddings:  List[np.ndarray] = field(default_factory=list)
    classicals:  List[np.ndarray] = field(default_factory=list)
    image_paths: List[Path]       = field(default_factory=list)

    def add(self, emb: np.ndarray, cls: np.ndarray, img_path: Path):
        self.embeddings.append(emb)
        self.classicals.append(cls)
        self.image_paths.append(img_path)

    @property
    def n(self) -> int:
        return len(self.embeddings)

    def mean_embedding(self) -> np.ndarray:
        m = np.mean(self.embeddings, axis=0)
        norm = np.linalg.norm(m)
        return m / norm if norm > 1e-8 else m

    def mean_classical(self) -> np.ndarray:
        return np.mean(self.classicals, axis=0)


# ── main pipeline class ───────────────────────────────────────────────────────

class DetectionPipeline:
    """
    Wires together camera, preprocessor, model, and database into the full
    loading-and-sorting flow.

    Parameters
    ----------
    db            : PillDatabase
    embedding_model : EmbeddingModel
    matcher       : PillMatcher
    camera        : ChamberCamera (or None for test-image mode)
    on_hold       : async callable(result_dict) → bool | None
                    Called when a pill is UNSURE or NO_MATCH.
                    Should notify the app and return True (route), False (discard),
                    or None (timeout). If None, the pill stays held.
    route_pill    : callable(slot: int) → None
                    Hardware callback: rotate carousel to slot and open trapdoor.
    save_dir      : directory for temporary reference images
    """

    def __init__(
        self,
        db:              PillDatabase,
        embedding_model: EmbeddingModel,
        matcher:         PillMatcher,
        camera=None,
        on_hold:         Optional[Callable] = None,
        route_pill:      Optional[Callable] = None,
        save_dir:        Path = Path(__file__).parent / "data" / "temp",
    ):
        self.db      = db
        self.model   = embedding_model
        self.matcher = matcher
        self.camera  = camera
        self.on_hold = on_hold
        self.route_pill = route_pill
        self.save_dir   = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # nhi_code → _Accumulator (for pills not yet fully registered)
        self._accumulators: Dict[str, _Accumulator] = {}

    # ── public entry point ────────────────────────────────────────────────────

    async def process_pill(self, raw_image: Optional[Image.Image] = None) -> dict:
        """
        Full pipeline for one pill.

        If raw_image is provided, skip camera capture (test mode).
        Returns a result dict describing what happened.
        """
        # 1. Capture
        if raw_image is None:
            if self.camera is None:
                raise RuntimeError("No camera and no raw_image provided.")
            raw_image = self.camera.capture_pill()

        # Save raw image for potential registration use
        ts       = int(time.time() * 1000)
        raw_path = self.save_dir / f"pill_{ts}.jpg"
        raw_image.save(raw_path, quality=92)

        # 2. Preprocess
        arr, meta = preprocess(raw_image)
        if not meta.get("pill_found"):
            return {"status": "no_pill", "message": "No pill detected in chamber."}

        # 3. Embed + extract classical features
        embedding = self.model.embed(arr)
        classical = meta["classical"]

        # 4. Match against registered profiles
        ref_embs, ref_cls, nhi_codes = self.db.get_all_profiles()
        nhi_code, confidence, result = self.matcher.match(
            embedding, classical, ref_embs, ref_cls, nhi_codes
        )

        # 5. Handle unregistered meds: try NHI prior matching
        if result == RESULT_NO_MATCH:
            nhi_code, confidence, result = self._match_against_prescription_priors(
                classical, meta
            )

        # 6. Build result payload
        display_img  = preprocess_for_display(raw_image)
        img_b64      = _image_to_b64(display_img)
        med_meta     = self.db.get_medication(nhi_code) if nhi_code else None

        payload = {
            "status":      result,
            "nhi_code":    nhi_code,
            "name_en":     med_meta.get("name_en", "") if med_meta else "",
            "name_zh":     med_meta.get("name_zh", "") if med_meta else "",
            "slot":        med_meta.get("slot")        if med_meta else None,
            "confidence":  round(confidence, 4),
            "image_b64":   img_b64,
            "registered":  self.db.is_registered(nhi_code) if nhi_code else False,
        }

        # 7. Dispatch
        if result == RESULT_MATCH:
            payload = await self._handle_match(payload, embedding, classical, raw_path)

        elif result == RESULT_UNSURE:
            payload = await self._handle_unsure(payload, embedding, classical, raw_path)

        else:  # NO_MATCH
            payload = await self._handle_no_match(payload)

        return payload

    # ── result handlers ───────────────────────────────────────────────────────

    async def _handle_match(
        self, payload: dict,
        embedding: np.ndarray, classical: np.ndarray, raw_path: Path
    ) -> dict:
        nhi_code = payload["nhi_code"]

        # Accumulate towards registration if this medication isn't locked yet
        if not self.db.is_registered(nhi_code):
            self._accumulate(nhi_code, embedding, classical, raw_path)
            if self._accumulators[nhi_code].n >= MIN_REG_SAMPLES:
                self._commit_registration(nhi_code)
                payload["auto_registered"] = True

        # Route the pill
        slot = payload["slot"]
        if slot and self.route_pill:
            self.route_pill(slot)
        payload["routed"] = True
        return payload

    async def _handle_unsure(
        self, payload: dict,
        embedding: np.ndarray, classical: np.ndarray, raw_path: Path
    ) -> dict:
        """Hold pill, ask for confirmation, route or discard based on response."""
        if self.on_hold is None:
            payload["routed"] = False
            payload["hold_reason"] = "no_confirm_handler"
            return payload

        try:
            confirmed = await asyncio.wait_for(
                self.on_hold(payload), timeout=HOLD_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            confirmed = None

        if confirmed is True:
            # User confirmed — accumulate and route
            nhi_code = payload["nhi_code"]
            if nhi_code:
                self._accumulate(nhi_code, embedding, classical, raw_path)
                if self._accumulators.get(nhi_code, _Accumulator("")).n >= MIN_REG_SAMPLES:
                    self._commit_registration(nhi_code)
                    payload["auto_registered"] = True
            slot = payload["slot"]
            if slot and self.route_pill:
                self.route_pill(slot)
            payload["routed"] = True

        elif confirmed is False:
            payload["routed"]      = False
            payload["hold_reason"] = "user_rejected"
        else:
            payload["routed"]      = False
            payload["hold_reason"] = "timeout"

        return payload

    async def _handle_no_match(self, payload: dict) -> dict:
        """Pill doesn't match anything in prescription — alert app."""
        if self.on_hold:
            await self.on_hold(payload)
        payload["routed"]      = False
        payload["hold_reason"] = "not_in_prescription"
        return payload

    # ── NHI prior matching ────────────────────────────────────────────────────

    def _match_against_prescription_priors(
        self, classical: np.ndarray, meta: dict
    ) -> tuple:
        """
        For unregistered medications: score each prescription entry against the
        observed classical features using NHI-declared colour and shape.
        Returns (nhi_code, confidence, result_label).
        """
        unregistered = self.db.unregistered_medications()
        if not unregistered:
            return None, 0.0, RESULT_NO_MATCH

        scores = []
        for med in unregistered:
            score = self._nhi_prior_score(classical, med)
            scores.append((score, med["nhi_code"]))

        scores.sort(reverse=True)
        best_score, best_code = scores[0]

        # Margin vs second-best
        if len(scores) > 1:
            margin     = scores[0][0] - scores[1][0]
            confidence = float(np.clip(margin * 2.0, 0.0, 1.0))
        else:
            confidence = float(np.clip(best_score, 0.0, 1.0))

        if confidence >= self.matcher.conf_high:
            result = RESULT_MATCH
        elif confidence >= self.matcher.conf_low:
            result = RESULT_UNSURE
        else:
            result = RESULT_NO_MATCH

        return best_code, confidence, result

    def _nhi_prior_score(self, classical: np.ndarray, med: dict) -> float:
        """Score how well the classical features match NHI-declared colour/shape."""
        score = 0.0

        # Colour check: compare observed H/S histogram peak against NHI colour
        nhi_color = med.get("color", "").lower()
        if nhi_color in _NHI_COLOR_MAP:
            # Hue histogram peak: find dominant H bin
            h_hist  = classical[:32]
            peak_h  = int(np.argmax(h_hist)) * (180 // 32)
            s_hist  = classical[32:64]
            avg_s   = float(np.dot(s_hist, np.linspace(0, 255, 32)))

            # White/grey pills have low saturation
            if nhi_color in ("white", "grey"):
                score += max(0.0, 1.0 - avg_s / 128.0)
            else:
                expected_h = _bgr_to_hue(_NHI_COLOR_MAP[nhi_color])
                hue_diff   = abs(peak_h - expected_h)
                hue_diff   = min(hue_diff, 180 - hue_diff)
                score += max(0.0, 1.0 - hue_diff / 90.0)

        # Shape check: compare circularity against NHI shape
        nhi_shape = med.get("shape", "other").lower()
        expected_circ = _NHI_SHAPE_CIRCULARITY.get(nhi_shape, 0.65)
        observed_circ = float(classical[65])   # index 65 = circularity feature
        shape_score   = max(0.0, 1.0 - abs(observed_circ - expected_circ))
        score += shape_score

        return score / 2.0   # normalise to [0, 1]

    # ── registration helpers ──────────────────────────────────────────────────

    def _accumulate(
        self, nhi_code: str, emb: np.ndarray, cls: np.ndarray, img_path: Path
    ):
        if nhi_code not in self._accumulators:
            self._accumulators[nhi_code] = _Accumulator(nhi_code)
        self._accumulators[nhi_code].add(emb, cls, img_path)

    def _commit_registration(self, nhi_code: str):
        """Write the accumulated mean embedding to the database."""
        acc = self._accumulators.get(nhi_code)
        if acc is None or acc.n == 0:
            return
        self.db.register_profile(
            nhi_code        = nhi_code,
            embedding       = acc.mean_embedding(),
            classical       = acc.mean_classical(),
            reference_images= acc.image_paths,
            n_samples       = acc.n,
        )
        del self._accumulators[nhi_code]


# ── utilities ─────────────────────────────────────────────────────────────────

def _image_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def _bgr_to_hue(bgr: np.ndarray) -> int:
    """Approximate dominant hue (0-180) from a BGR colour value."""
    import cv2
    pixel = bgr.astype(np.uint8).reshape(1, 1, 3)
    hsv   = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)
    return int(hsv[0, 0, 0])
