"""
database.py — Prescription-driven pill profile storage.

Two layers:
  1. Prescription  — the medication list imported from the app (NHI / OCR).
                     This is the ground truth for what pills are expected.
  2. Profiles      — per-medication registered profiles built automatically
                     from the first few pills the user physically loads.

Directory layout:
  data/profiles/
    prescription.json          — active prescription from app
    index.json                 — registered profile metadata
    <med_id>/
      embedding.npy            — mean L2-normalised embedding (1280-dim)
      classical.npy            — mean classical feature vector (68-dim)
      ref_00.jpg, ref_01.jpg … — reference images captured during auto-registration
"""

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

DEFAULT_DB_DIR = Path(__file__).parent / "data" / "profiles"


class PillDatabase:

    def __init__(self, db_dir: Path = DEFAULT_DB_DIR):
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)

        self._rx_path  = self.db_dir / "prescription.json"
        self._idx_path = self.db_dir / "index.json"

        self._prescription: List[dict] = self._load_json(self._rx_path, default=[])
        self._index: Dict[str, dict]   = self._load_json(self._idx_path, default={})

    # ── JSON helpers ──────────────────────────────────────────────────────────

    def _load_json(self, path: Path, default):
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return default

    def _save_json(self, path: Path, obj):
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── Prescription ──────────────────────────────────────────────────────────

    def load_prescription(self, medications: List[dict]):
        """
        Receive the medication list from the app (parsed from NHI QR / OCR).
        Each entry must have at minimum: nhi_code, name_en, slot.
        Clears and rebuilds the prescription; existing registered profiles
        for codes no longer in the prescription are removed.
        """
        self._prescription = medications
        self._save_json(self._rx_path, medications)

        active_codes = {m["nhi_code"] for m in medications}
        stale = [mid for mid, meta in self._index.items()
                 if meta["nhi_code"] not in active_codes]
        for mid in stale:
            self.delete_profile(mid)

    def get_prescription(self) -> List[dict]:
        return list(self._prescription)

    def get_medication(self, nhi_code: str) -> Optional[dict]:
        for m in self._prescription:
            if m["nhi_code"] == nhi_code:
                return m
        return None

    def prescription_medication_by_slot(self, slot: int) -> Optional[dict]:
        for m in self._prescription:
            if m.get("slot") == slot:
                return m
        return None

    # ── Profile registration ──────────────────────────────────────────────────

    def register_profile(
        self,
        nhi_code: str,
        embedding: np.ndarray,
        classical: np.ndarray,
        reference_images: List[Path],
        n_samples: int,
    ) -> str:
        """
        Create or overwrite the registered profile for a prescription medication.
        Returns the internal profile id.
        """
        med = self.get_medication(nhi_code)
        if med is None:
            raise ValueError(f"nhi_code '{nhi_code}' not in active prescription.")

        # Reuse existing id for this nhi_code if one exists, else create new
        existing_id = self._profile_id_for(nhi_code)
        profile_id  = existing_id or str(uuid.uuid4())
        profile_dir = self.db_dir / profile_id
        profile_dir.mkdir(exist_ok=True)

        np.save(profile_dir / "embedding.npy",  embedding.astype(np.float32))
        np.save(profile_dir / "classical.npy",  classical.astype(np.float32))

        saved_imgs = []
        for i, src in enumerate(reference_images):
            src = Path(src)
            if src.exists():
                dst = profile_dir / f"ref_{i:02d}{src.suffix}"
                shutil.copy2(src, dst)
                saved_imgs.append(str(dst))

        self._index[profile_id] = {
            "id":           profile_id,
            "nhi_code":     nhi_code,
            "name_en":      med.get("name_en", ""),
            "name_zh":      med.get("name_zh", ""),
            "slot":         med.get("slot"),
            "n_samples":    n_samples,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "image_paths":  saved_imgs,
        }
        self._save_json(self._idx_path, self._index)
        return profile_id

    def update_profile_embedding(
        self,
        nhi_code: str,
        new_embedding: np.ndarray,
        new_classical: np.ndarray,
        new_n_samples: int,
    ):
        """
        Update the stored embedding for a profile (called as more reference
        samples accumulate — running mean updated externally by the pipeline).
        """
        profile_id = self._profile_id_for(nhi_code)
        if profile_id is None:
            raise KeyError(f"No profile registered for nhi_code '{nhi_code}'.")
        profile_dir = self.db_dir / profile_id
        np.save(profile_dir / "embedding.npy", new_embedding.astype(np.float32))
        np.save(profile_dir / "classical.npy", new_classical.astype(np.float32))
        self._index[profile_id]["n_samples"] = new_n_samples
        self._save_json(self._idx_path, self._index)

    # ── Profile reads ─────────────────────────────────────────────────────────

    def get_profile(self, nhi_code: str) -> Optional[dict]:
        """Return profile dict including loaded numpy arrays, or None."""
        profile_id = self._profile_id_for(nhi_code)
        if profile_id is None:
            return None
        return self._load_profile(profile_id)

    def get_all_profiles(self) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Load all registered profiles.
        Returns (embeddings [N,1280], classicals [N,68], nhi_codes [N]).
        """
        embeddings, classicals, codes = [], [], []
        for pid, meta in self._index.items():
            emb_path = self.db_dir / pid / "embedding.npy"
            cls_path = self.db_dir / pid / "classical.npy"
            if emb_path.exists() and cls_path.exists():
                embeddings.append(np.load(emb_path))
                classicals.append(np.load(cls_path))
                codes.append(meta["nhi_code"])
        if not embeddings:
            return (
                np.empty((0, 1280), dtype=np.float32),
                np.empty((0, 68),   dtype=np.float32),
                [],
            )
        return (
            np.stack(embeddings).astype(np.float32),
            np.stack(classicals).astype(np.float32),
            codes,
        )

    def is_registered(self, nhi_code: str) -> bool:
        return self._profile_id_for(nhi_code) is not None

    def unregistered_medications(self) -> List[dict]:
        """Prescription medications that don't yet have a registered profile."""
        return [m for m in self._prescription
                if not self.is_registered(m["nhi_code"])]

    def registered_count(self) -> int:
        return len(self._index)

    def delete_profile(self, profile_id: str):
        if profile_id not in self._index:
            return
        shutil.rmtree(self.db_dir / profile_id, ignore_errors=True)
        del self._index[profile_id]
        self._save_json(self._idx_path, self._index)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _profile_id_for(self, nhi_code: str) -> Optional[str]:
        for pid, meta in self._index.items():
            if meta["nhi_code"] == nhi_code:
                return pid
        return None

    def _load_profile(self, profile_id: str) -> dict:
        meta = dict(self._index[profile_id])
        profile_dir = self.db_dir / profile_id
        meta["embedding"] = np.load(profile_dir / "embedding.npy")
        meta["classical"] = np.load(profile_dir / "classical.npy")
        return meta

    def __len__(self) -> int:
        return len(self._index)

    def __repr__(self) -> str:
        return (
            f"PillDatabase("
            f"{len(self._prescription)} rx meds, "
            f"{len(self._index)} registered, "
            f"dir={self.db_dir})"
        )
