"""
demo_server.py - HTTP integration server for the Hero Smart Pill Dispenser.

Run on the laptop/server machine:
    python demo_server.py

Then enter http://<your-ip>:5000 in the Flutter app.

Prototype Camera Mode:
  The Flutter phone camera stands in for the future dispenser inspection
  camera. The app uploads one pill photo at a time to /detect, the server runs
  real ONNX inference when available, and /load_pill only animates routing
  after the app accepts the detection result.
"""

import json
import pathlib
import sys
import threading
import time
from flask import Flask, request, jsonify, send_file, redirect
try:
    from flask_cors import CORS as _CORS
    _HAS_CORS = True
except ImportError:
    _HAS_CORS = False

HERE = pathlib.Path(__file__).parent

# ── QR code for easy setup ─────────────────────────────────────────────────────
_SETUP_QR_PNG: bytes | None = None   # generated on startup

def _generate_setup_qr(local_ip: str) -> None:
    """Generate a QR-code PNG containing the server connection payload.

    Payload (JSON): {"type":"pill_dispenser","url":"http://<ip>:5000","serial":"<serial>"}
    Served at /setup.png.  The /setup page renders it full-screen for scanning.

    Requires:  pip install qrcode[pil]
    Falls back silently if qrcode is not installed.
    """
    global _SETUP_QR_PNG
    import io
    payload = json.dumps({
        "type":   "pill_dispenser",
        "url":    f"http://{local_ip}:5000",
        "serial": DEVICE_INFO["serial_number"],
    })
    try:
        import qrcode  # type: ignore
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=12,
            border=4,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        _SETUP_QR_PNG = buf.getvalue()
        print(f"[demo] Setup QR generated  →  http://{local_ip}:5000/setup")
    except ImportError:
        print("[demo] qrcode library not found — /setup.png will be unavailable")
        print("       Install with:  pip install qrcode[pil]")
    except Exception as e:
        print(f"[demo] QR generation failed: {e}")

# Windows PowerShell often defaults to cp1252, which cannot print arrows,
# Chinese medication names, or status symbols from background threads.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ── tunable delays ────────────────────────────────────────────────────────────
DISPENSE_DELAY_S = 2.0   # seconds between dispense command and confirmation
APP_HEARTBEAT_TIMEOUT_S = 10.0
DETECTION_MODE = "skipped"

# ── future real inference setup (RTX 5080) ───────────────────────────────────
# Not invoked while DETECTION_MODE is "skipped"; kept so real detection can be
# wired back in later without changing the app/server workflow.

_model   = None   # EmbeddingModel  (model.py)
_db      = None   # PillDatabase    (database.py)
_matcher = None   # PillMatcher     (model.py)
_REAL_INFERENCE_OK = False   # set True by _load_real_inference() on startup

# Per-medication embedding accumulators for auto-registration
# nhi_code → list of (embedding, classical, ref_image_path)
_accumulators: dict = {}
MIN_REG_SAMPLES = 3   # auto-register profile after this many MATCHes
RECENT_IMG = HERE / "recent_capture.jpg"   # last uploaded capture (served to viewer)
_last_detection = None

# Future pill images: any .jpg/.png under detection/demo_pills/<med_id>/
# e.g.  demo_pills/AC23456100/pill_001.jpg
DEMO_PILLS_DIR = HERE / "demo_pills"

def _load_real_inference():
    """Try to load the ONNX model + database for real GPU inference."""
    global _model, _db, _matcher
    try:
        import sys
        sys.path.insert(0, str(HERE))
        from model import EmbeddingModel, PillMatcher
        from database import PillDatabase

        onnx_path = HERE / "models" / "pill_embedding.onnx"
        if not onnx_path.exists():
            return False

        _model   = EmbeddingModel(onnx_path)
        _db      = PillDatabase(HERE / "data" / "profiles")
        _matcher = PillMatcher()
        print(f"[demo] Real inference: ONNX model loaded from {onnx_path}")
        print(f"[demo]   Execution providers: {_model._sess.get_providers()}")
        return True
    except Exception as e:
        print(f"[demo] Real inference unavailable ({e})")
        return False

def _infer_pill_image(image_path: pathlib.Path, expected_nhi: str = "") -> dict:
    """
    Run real ONNX inference on the captured image.

    Pipeline:
      1. preprocess (perspective + Otsu segmentation + 224×224 + classical features)
      2. ONNX embedding (1280-dim, L2-normalised)
      3. Match against locked profiles in PillDatabase
      4. If no locked profiles yet, fall back to per-prescription accumulator
         matching (against samples we've seen so far for each medication)
      5. If still no match, use NHI priors (colour/shape from prescription)
      6. Auto-accumulate the embedding; commit profile when n >= MIN_REG_SAMPLES

    Returns dict with: result, confidence, nhi_code, top_candidates,
                       auto_registered, accumulator_n, image_quality.
    """
    from PIL import Image as PILImage
    import numpy as np
    from preprocess import preprocess

    img = PILImage.open(image_path).convert("RGB")
    try:
        arr, meta = preprocess(img)
    except Exception as e:
        return {"result": "NO_MATCH", "confidence": 0.0, "nhi_code": None,
                "reason": f"preprocess_failed: {e}", "top_candidates": []}

    if not meta.get("pill_found"):
        return {"result": "NO_MATCH", "confidence": 0.0, "nhi_code": None,
                "reason": "no_pill_in_image", "top_candidates": []}

    embedding = _model.embed(arr)
    classical = meta["classical"]

    # ── 1. Match against LOCKED profiles ──────────────────────────────────
    ref_embs, ref_cls, locked_codes = _db.get_all_profiles()
    if len(locked_codes) > 0:
        nhi_code, conf, result = _matcher.match(
            embedding, classical, ref_embs, ref_cls, locked_codes)
    else:
        nhi_code, conf, result = None, 0.0, "NO_MATCH"

    # ── 2. Augment with ACCUMULATOR profiles (medications still warming up)
    # Build a virtual reference set from the per-medication accumulators.
    acc_embs, acc_cls, acc_codes = [], [], []
    for code, samples in _accumulators.items():
        if not samples:
            continue
        # Mean of samples (L2-normalised for embeddings)
        mean_emb = np.mean([s[0] for s in samples], axis=0)
        n = np.linalg.norm(mean_emb)
        mean_emb = mean_emb / n if n > 1e-8 else mean_emb
        mean_cls = np.mean([s[1] for s in samples], axis=0)
        acc_embs.append(mean_emb)
        acc_cls.append(mean_cls)
        acc_codes.append(code)

    if acc_embs:
        a_embs = np.stack(acc_embs).astype(np.float32)
        a_cls  = np.stack(acc_cls).astype(np.float32)
        a_nhi, a_conf, a_result = _matcher.match(
            embedding, classical, a_embs, a_cls, acc_codes)
        # If accumulator-based match is stronger, prefer it
        if a_conf > conf:
            nhi_code, conf, result = a_nhi, a_conf, a_result

    # ── 3. NHI prior fallback (cold start — first ever pill of any med) ──
    top_candidates = []
    prior_debug = ""
    if result == "NO_MATCH" and _db is not None:
        try:
            prior = _nhi_prior_match(classical, meta)
            if prior:
                nhi_code, conf, result = prior["nhi_code"], prior["confidence"], prior["result"]
                top_candidates = prior.get("top", [])
                prior_debug = f"prior_used: {nhi_code} {result} {conf:.3f}"
            else:
                prior_debug = f"prior_returned_None _db={_db is not None} _rx={len(_rx)}"
        except Exception as e:
            import traceback
            prior_debug = f"prior_EXCEPTION: {e!r} | {traceback.format_exc()[:200]}"

    # ── 4. Build top-candidates list for UI display ──────────────────────
    if not top_candidates and (len(locked_codes) > 0 or acc_codes):
        # Compute scores against everything we know about
        all_embs = list(ref_embs) + acc_embs
        all_cls  = list(ref_cls)  + acc_cls
        all_codes = list(locked_codes) + acc_codes
        sims = []
        for i, code in enumerate(all_codes):
            neural = float(np.dot(all_embs[i], embedding))
            sims.append((neural, code))
        sims.sort(reverse=True)
        for s, c in sims[:3]:
            med = _slot_for_nhi(c)
            top_candidates.append({
                "nhi_code": c,
                "name":     med.get("medicationName", c) if med else c,
                "score":    round(float(s), 3),
            })

    # ── 5. Auto-accumulation: if MATCH and not yet locked, save sample ──
    auto_registered = False
    if result == "MATCH" and nhi_code and not _db.is_registered(nhi_code):
        _accumulators.setdefault(nhi_code, []).append((embedding.copy(),
                                                       classical.copy(),
                                                       str(image_path)))
        if len(_accumulators[nhi_code]) >= MIN_REG_SAMPLES:
            try:
                samples = _accumulators[nhi_code]
                mean_emb = np.mean([s[0] for s in samples], axis=0)
                n = np.linalg.norm(mean_emb)
                mean_emb = (mean_emb / n) if n > 1e-8 else mean_emb
                mean_cls = np.mean([s[1] for s in samples], axis=0)
                ref_paths = [pathlib.Path(s[2]) for s in samples]
                _db.register_profile(nhi_code, mean_emb, mean_cls,
                                     ref_paths, len(samples))
                auto_registered = True
                _accumulators[nhi_code] = []   # clear accumulator after locking
                print(f"[demo] Auto-registered profile for {nhi_code} ({len(samples)} samples)")
            except Exception as e:
                print(f"[demo] Auto-register failed for {nhi_code}: {e}")

    return {
        "result":          result,
        "confidence":      float(conf),
        "nhi_code":        nhi_code,
        "top_candidates":  top_candidates,
        "auto_registered": auto_registered,
        "accumulator_n":   len(_accumulators.get(nhi_code, [])) if nhi_code else 0,
        "image_quality":   {
            "pill_found":   meta.get("pill_found", False),
            "fill_ratio":   round(float(meta.get("fill_ratio", 0.0)), 3),
        },
        "_prior_debug":    prior_debug,
    }


def _slot_for_nhi(nhi_code: str) -> dict:
    """Return the slot dict for a given NHI code, or empty dict."""
    if not nhi_code: return {}
    for slot, med in _slots.items():
        if (med.get("nhi_code") == nhi_code or
                med.get("nhiCode") == nhi_code or
                med.get("nhicCode") == nhi_code or
                med.get("medicationId") == nhi_code):
            return med
    return {}


def _med_nhi_code(med: dict, fallback: str = "") -> str:
    """Canonical NHI code field used by the app/server/detection pipeline."""
    return str(
        med.get("nhi_code")
        or med.get("nhiCode")
        or med.get("nhicCode")
        or med.get("medicationId")
        or fallback
    )


def _nhi_prior_match(classical, meta) -> dict:
    """
    Cold-start fallback: when no profiles or accumulators exist, use the
    NHI-declared colour and shape from the prescription to score each
    medication. Returns the best-matching medication or None.
    """
    import numpy as np
    # NB: `not _db` would evaluate True when no profiles registered yet
    # (PillDatabase defines __len__). Use explicit None check.
    if _db is None or not _rx:
        return None

    # Simple scoring: detected dominant colour vs declared colour, plus
    # circularity vs declared shape.  classical[64:68] = shape features.
    detected_circularity = float(classical[64]) if len(classical) > 64 else 0.5

    SHAPE_CIRC = {"round": 0.90, "circle": 0.90, "oval": 0.70,
                  "capsule": 0.55, "oblong": 0.50}

    scores = []
    for med in _rx:
        shape = (med.get("pillShape") or "round").lower()
        target_circ = SHAPE_CIRC.get(shape, 0.7)
        shape_score = 1.0 - abs(detected_circularity - target_circ)
        # Colour scoring is fuzzy — without HSV histogram comparison just use
        # uniform weight. The prior gives weak confidence; real matching
        # takes over once the profile is locked.
        score = max(0.0, shape_score)
        scores.append((score, med))

    scores.sort(key=lambda x: x[0], reverse=True)
    if not scores:
        return None
    best_score, best_med = scores[0]
    margin = best_score - (scores[1][0] if len(scores) > 1 else 0.0)
    confidence = max(0.05, min(0.30, margin))   # always low-confidence
    result = "UNSURE" if confidence > 0.10 else "NO_MATCH"
    if best_score > 0.8:
        result = "MATCH"   # very strong shape + only one matching pill
    return {
        "nhi_code":   best_med.get("nhi_code") or best_med.get("medicationId"),
        "confidence": float(confidence),
        "result":     result,
        "top": [{"nhi_code": m.get("nhi_code") or m.get("medicationId"),
                 "name":     m.get("medicationName", "?"),
                 "score":    round(float(s), 3)} for s, m in scores[:3]],
    }


def _sync_prescription_to_db():
    """Push the active prescription into PillDatabase so NHI priors and
    profile registration know about this user's medications."""
    if _db is None:
        return
    try:
        meds = []
        for slot, m in _slots.items():
            nhi = _med_nhi_code(m, f"slot{slot}")
            meds.append({
                "nhi_code": nhi,
                "name_en":  m.get("medicationName", ""),
                "name_zh":  m.get("medicationName", ""),
                "color":    (m.get("pillColor") or "white").lower(),
                "shape":    (m.get("pillShape") or "round").lower(),
                "slot":     int(slot) if str(slot).isdigit() else 1,
            })
        _db.load_prescription(meds)
        print(f"[demo] Synced {len(meds)} medications into PillDatabase")
    except Exception as e:
        print(f"[demo] PillDatabase sync failed: {e}")

app   = Flask("demo_dispenser")
if _HAS_CORS:
    _CORS(app)   # allow phone (different IP) to POST to laptop server

# ── Pi-like persistent device identity ────────────────────────────────────────
# A real Raspberry Pi has a fixed serial number, firmware version, and stored
# state across reboots. We simulate that with a JSON file next to demo_server.py.
DEVICE_INFO = {
    "device_id":          "HERO-PI-DEMO-001",
    "serial_number":      "SPD-2026-TW-00001",
    "firmware_version":   "1.0.0-demo",
    "model":              "Hero Smart Pill Dispenser",
    "compartment_count":  10,
    "boot_time":          time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    "uptime_started":     time.time(),
}

STATE_FILE = HERE / "pi_state.json"

_rx   = []                         # active prescription
_slots: dict = {}                  # slot -> medication info
_slot_state: dict = {}             # slot -> loading/dispense state
_state = {
    "status": "idle",
    "loading_slot": None,
    "loading_med": None,
    "dispensing": False,
    "active_slot": None,
    "last_event": None,
    "app_last_seen": None,
    "app_client": None,
    "paired_user_id": None,        # set on first /app/connect, cleared on /app/disconnect+reset
}


def _save_state():
    """Persist the Pi's slot inventory + paired user to disk."""
    try:
        STATE_FILE.write_text(json.dumps({
            "device_info": {k: v for k, v in DEVICE_INFO.items() if k != "uptime_started"},
            "slots":       _slots,
            "slot_state":  _slot_state,
            "paired_user_id": _state.get("paired_user_id"),
            "saved_at":    time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        }, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[demo] Could not save state: {e}")


def _load_state():
    """Restore the Pi's persisted state on boot."""
    global _slots, _slot_state, _rx
    if not STATE_FILE.exists():
        return
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        _slots      = data.get("slots", {}) or {}
        _slot_state = data.get("slot_state", {}) or {}
        _rx         = list(_slots.values())
        _state["paired_user_id"] = data.get("paired_user_id")
        loaded = sum(1 for s in _slot_state.values() if (s.get("pillCount") or 0) > 0)
        print(f"[demo] Pi state restored: {len(_slots)} medications, {loaded} slots loaded")
    except Exception as e:
        print(f"[demo] Could not restore state: {e}")

# ── event log (for polling viewer) ───────────────────────────────────────────
# Each event gets an auto-incrementing integer ID.
# The viewer polls /events/recent?since=<id> and receives everything newer.
_event_log: list = []        # list of dicts, each has "_id" key
_event_id   = 0
_event_lock = threading.Lock()
_EVENT_LOG_MAX = 200         # keep last 200 events


# ── helpers ───────────────────────────────────────────────────────────────────

def _push(event: dict):
    """Record event in the poll log for app/status polling."""
    global _event_id
    _state["last_event"] = event.get("event")
    with _event_lock:
        _event_id += 1
        entry = dict(event)
        entry["_id"] = _event_id
        _event_log.append(entry)
        if len(_event_log) > _EVENT_LOG_MAX:
            _event_log.pop(0)
    print(f"[demo] event: {event.get('event','?')}")


def _set_status(s: str):
    _state["status"] = s
    _push({"event": "status", "value": s})
    print(f"[demo] status → {s}")


def _app_connected() -> bool:
    last_seen = _state.get("app_last_seen")
    return bool(last_seen and (time.time() - last_seen) <= APP_HEARTBEAT_TIMEOUT_S)


def _touch_app(client_name: str = "flutter"):
    _state["app_last_seen"] = time.time()
    _state["app_client"] = client_name or "flutter"


def _slot_payload():
    return [dict(v) for _, v in sorted(_slot_state.items(), key=lambda item: int(item[0]))]


def _status_payload():
    return {
        "status": _state["status"],
        "app_connected": _app_connected(),
        "app_last_seen": _state["app_last_seen"],
        "app_client": _state["app_client"],
        "prescription_loaded": bool(_rx),
        "prescription_count": len(_rx),
        "slots": _slot_payload(),
        "loading_slot": _state["loading_slot"],
        "loading_med": _state["loading_med"],
        "dispensing": _state["dispensing"],
        "active_slot": _state["active_slot"],
        "last_event": _state["last_event"],
        "detection_mode": DETECTION_MODE,
        "inference_loaded": _REAL_INFERENCE_OK,
    }


def _normalise_slot(slot) -> str:
    return str(slot or "1")


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/device_info")
def get_device_info():
    """Identify the Pi: serial, firmware, uptime, paired status."""
    uptime = time.time() - DEVICE_INFO["uptime_started"]
    return jsonify({
        **{k: v for k, v in DEVICE_INFO.items() if k != "uptime_started"},
        "uptime_seconds": int(uptime),
        "paired_user_id": _state.get("paired_user_id"),
        "is_paired":      _state.get("paired_user_id") is not None,
        "loaded_slots":   sum(1 for s in _slot_state.values()
                              if (s.get("pillCount") or 0) > 0),
        "total_slots":    DEVICE_INFO["compartment_count"],
        "current_status": _state["status"],
    })


@app.post("/reset")
def post_reset():
    """Factory-reset the Pi: clear all stored slots, prescription, and pairing.
    Useful for the demo when starting fresh."""
    global _rx, _slots, _slot_state
    _rx, _slots, _slot_state = [], {}, {}
    _state["paired_user_id"] = None
    _state["status"]         = "idle"
    _state["dispensing"]     = False
    _state["active_slot"]    = None
    _state["loading_slot"]   = None
    _state["loading_med"]    = None
    if STATE_FILE.exists():
        try: STATE_FILE.unlink()
        except: pass
    _push({"event": "device_reset"})
    print("[demo] Device reset to factory state")
    return jsonify({"ok": True})


@app.post("/app/connect")
def post_app_connect():
    """Flutter app announces that it is connected to this server."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    _touch_app(str(data.get("client", "flutter")))
    # First connect after a fresh boot/reset: pair the device to this user
    if user_id and not _state.get("paired_user_id"):
        _state["paired_user_id"] = str(user_id)
        _save_state()
        _push({"event": "device_paired", "user_id": str(user_id)})
        print(f"[demo] Device paired to user {user_id}")
    _push({"event": "app_connected", "client": _state["app_client"]})
    return jsonify({
        "ok": True,
        "device_info": {k: v for k, v in DEVICE_INFO.items() if k != "uptime_started"},
        **_status_payload(),
    })


@app.post("/app/heartbeat")
def post_app_heartbeat():
    """Flutter app keeps the HTTP demo session alive."""
    data = request.get_json(silent=True) or {}
    _touch_app(str(data.get("client", _state.get("app_client") or "flutter")))
    return jsonify({"ok": True, "app_connected": True})


@app.post("/app/disconnect")
def post_app_disconnect():
    """Flutter app intentionally disconnects from this server."""
    _state["app_last_seen"] = None
    _state["app_client"] = None
    _push({"event": "app_disconnected"})
    return jsonify({"ok": True, **_status_payload()})


@app.post("/prescription")
def post_prescription():
    """App sends the full medication list after QR/OCR scan."""
    global _rx, _slots, _slot_state
    data = request.get_json(force=True)
    raw_meds = data.get("medications", [])[:10]
    _rx = []
    _slots = {}
    for i, med in enumerate(raw_meds):
        slot = _normalise_slot(med.get("compartmentId", med.get("slot", i + 1)))
        normalised = dict(med)
        normalised["compartmentId"] = slot
        normalised["nhi_code"] = _med_nhi_code(normalised, normalised.get("medicationId", f"slot{slot}"))
        _rx.append(normalised)
        _slots[slot] = normalised
    _slot_state = {}
    for slot, med in _slots.items():
        qty = max(1, int(med.get("quantity") or 1))   # seed from prescription quantity
        _slot_state[slot] = {
            "compartmentNumber": int(slot),
            "medicationId": str(med.get("medicationId", "")),
            "nhiCode": _med_nhi_code(med),
            "medicationName": med.get("medicationName", f"slot {slot}"),
            "pillCount": qty,
            "isEmpty": False,
            "needsRefill": False,
            "loaded": True,
        }
    print(f"[demo] Prescription loaded: {len(_slots)} medications")
    for slot, med in _slots.items():
        print(f"       slot {slot} - {med.get('medicationName','?')}")
    _save_state()
    # Push the prescription into PillDatabase so NHI priors and registration
    # can identify these medications during /detect calls.
    if _REAL_INFERENCE_OK:
        _sync_prescription_to_db()
        # Reset accumulators when a new prescription arrives
        _accumulators.clear()
    _push({"event": "prescription_ack", "count": len(_slots),
           "slots": list(_slots.keys())})
    return jsonify({"ok": True, "count": len(_slots),
                    "slots": list(_slots.keys()),
                    "detection_mode": "real" if _REAL_INFERENCE_OK else "skipped"})


@app.post("/start_loading")
def post_start_loading():
    """App says 'user is now loading pills into slot N'."""
    data = request.get_json(force=True)
    slot = _normalise_slot(data.get("slot", "1"))
    med_id = str(data.get("med_id", data.get("medicationId", "")))

    _state["loading_slot"] = slot
    _state["loading_med"] = med_id
    _state["active_slot"] = slot
    _set_status("loading")

    med_name = _slots.get(slot, {}).get("medicationName", med_id)
    print(f"[demo] Start Prototype Camera Mode loading slot {slot} - {med_name}")
    _push({
        "event": "loading_started",
        "slot": slot,
        "med_id": med_id,
        "med_name": med_name,
        "detection_mode": DETECTION_MODE,
    })

    return jsonify({
        "ok": True,
        "slot": slot,
        "med_id": med_id,
        "detection_mode": DETECTION_MODE,
    })


@app.post("/stop_loading")
def post_stop_loading():
    """App says user finished loading this medication."""
    data = request.get_json(silent=True) or {}
    slot = _normalise_slot(data.get("slot") or _state["loading_slot"])
    med = _slots.get(slot, {})
    default_count = int(med.get("quantity") or 1)
    total = int(data.get("pill_count", data.get("total_pills", default_count)))

    _slot_state.setdefault(slot, {
        "compartmentNumber": int(slot),
        "medicationId": str(med.get("medicationId", "")),
        "medicationName": med.get("medicationName", f"slot {slot}"),
        "pillCount": 0,
        "isEmpty": True,
        "needsRefill": False,
        "loaded": False,
    })
    _slot_state[slot].update({
        "pillCount": total,
        "isEmpty": total <= 0,
        "needsRefill": total <= 0,
        "loaded": True,
    })

    _state["loading_slot"] = None
    _state["loading_med"] = None
    _state["active_slot"] = None
    _set_status("idle")
    _push({
        "event": "loading_complete",
        "slot": slot,
        "total_pills": total,
        "detection_mode": DETECTION_MODE,
    })
    return jsonify({
        "ok": True,
        "slot": slot,
        "total_pills": total,
        "detection_mode": DETECTION_MODE,
    })


# ── load + dispense locks (only one operation in flight at a time) ───────────
_load_lock     = threading.Lock()
_dispense_lock = threading.Lock()


@app.post("/load_pill")
def post_load_pill():
    """User confirms they have placed a pill in the detection chamber for the
    given slot. Server runs the timed loading sequence, emitting events so the
    3D viewer can animate the pill through chamber → chute → slot.

    Request body:  {"slot": 1, "med_id": "..."}  (med_id optional; uses prescription)
    """
    data    = request.get_json(force=True)
    slot    = _normalise_slot(data.get("slot", "1"))
    med     = _slots.get(slot, {})
    name    = med.get("medicationName", f"slot {slot}")
    med_id  = str(data.get("med_id", med.get("medicationId", "")))

    if not _load_lock.acquire(blocking=False):
        return jsonify({"ok": False, "reason": "loading_already_in_progress"}), 409

    threading.Thread(target=_run_load_sequence,
                     args=(slot, name, med_id), daemon=True).start()
    return jsonify({"ok": True, "slot": slot, "med_name": name})


def _run_load_sequence(slot: str, med_name: str, med_id: str):
    """Timed event sequence for routing an already-detected pill into a slot.

    NOTE: This function is called AFTER /detect has already confirmed the
    pill identity via real ONNX inference. It only handles the mechanical
    routing animation — no fake detection events are emitted here."""
    try:
        _state["loading_slot"] = slot
        _state["loading_med"]  = med_id
        _state["active_slot"]  = slot
        _set_status("loading")
        _push({"event": "load_started", "slot": slot, "med_name": med_name, "med_id": med_id})
        # Carousel pre-positions the target slot under the routing chute exit
        _push({"event": "carousel_rotate", "slot": slot})
        time.sleep(1.0)
        # Hatch closes (pill was already detected via /detect)
        _push({"event": "hatch_close"})
        time.sleep(0.4)
        _push({"event": "trapdoor_open"})
        time.sleep(0.4)
        _push({"event": "pill_routing", "slot": slot, "med_name": med_name})
        time.sleep(1.6)
        _push({"event": "trapdoor_close"})
        # Pill arrives in the carousel slot
        _push({"event": "pill_in_slot", "slot": slot, "med_name": med_name})
        time.sleep(1.0)

        # Update slot state — increment pill count
        st = _slot_state.setdefault(slot, {
            "compartmentNumber": int(slot),
            "medicationId":      med_id,
            "medicationName":    med_name,
            "pillCount":         0, "isEmpty": True,
            "needsRefill":       False, "loaded": False,
        })
        st["pillCount"]  = int(st.get("pillCount") or 0) + 1
        st["isEmpty"]    = False
        st["needsRefill"] = False
        st["loaded"]     = True

        _push({"event": "slot_loaded", "slot": slot, "med_name": med_name,
               "pill_count": st["pillCount"]})
        _state["loading_slot"] = None
        _state["loading_med"]  = None
        _state["active_slot"]  = None
        _set_status("idle")
        _save_state()
        print(f"[demo] Loaded {med_name} into slot {slot} (count={st['pillCount']})")
    finally:
        _load_lock.release()


@app.post("/dispense")
def post_dispense():
    """App triggers a dispense (scheduled or manual). Runs a timed sequence
    so the 3D viewer can animate the pill from slot → chute → cup."""
    data = request.get_json(force=True)
    slot = _normalise_slot(data.get("slot", "1"))
    med  = _slots.get(slot, {})
    name = med.get("medicationName", f"slot {slot}")

    slot_state = _slot_state.get(slot)
    if not slot_state:
        # Slot not in state — auto-create. Use prescription data if available;
        # otherwise create a synthetic entry so the animation always runs.
        qty = max(1, int(_slots.get(slot, {}).get("quantity") or 4))
        slot_state = _slot_state.setdefault(slot, {
            "compartmentNumber": int(slot),
            "medicationId": str(med.get("medicationId", f"med_{slot}")),
            "nhiCode": _med_nhi_code(med) if med else "",
            "medicationName": name,
            "pillCount": qty,
            "isEmpty": False,
            "needsRefill": False,
            "loaded": True,
        })
        print(f"[demo] Auto-created slot state for slot {slot} with qty={qty}")
    if int(slot_state.get("pillCount") or 0) <= 0:
        # Refill to prescription quantity (or 4 if unknown) so demo never stalls
        refill = max(1, int(_slots.get(slot, {}).get("quantity") or 4))
        slot_state["pillCount"] = refill
        slot_state["isEmpty"]   = False
        slot_state["loaded"]    = True
        print(f"[demo] Auto-refilled slot {slot} to {refill} pills for demo")

    if not _dispense_lock.acquire(blocking=False):
        # Return 200 so Dio doesn't throw — app will see ok:false and handle it
        return jsonify({"ok": False, "reason": "dispense_in_progress"})

    threading.Thread(target=_run_dispense_sequence,
                     args=(slot, name, med.get("medicationId", "")), daemon=True).start()
    return jsonify({"ok": True, "slot": slot, "dispensing": True})


def _run_dispense_sequence(slot: str, med_name: str, med_id: str):
    """Timed event sequence for dispensing one pill from the named slot."""
    try:
        slot_state = _slot_state[slot]
        _state["dispensing"]  = True
        _state["active_slot"] = slot
        _set_status("dispensing")
        print(f"[demo] Dispense {med_name} from slot {slot}")
        _push({"event": "dispense_started", "slot": slot, "med_name": med_name, "med_id": med_id})
        time.sleep(0.5)
        _push({"event": "carousel_rotate", "slot": slot, "med_name": med_name})
        time.sleep(1.2)
        _push({"event": "slot_opening", "slot": slot, "med_name": med_name})
        time.sleep(0.5)
        _push({"event": "dispense_gate_open"})
        time.sleep(0.6)
        _push({"event": "pill_falling", "slot": slot, "med_name": med_name})
        time.sleep(1.5)
        _push({"event": "dispense_release_gate_open"})
        time.sleep(0.4)
        _push({"event": "pill_in_cup", "slot": slot, "med_name": med_name})
        time.sleep(0.8)
        _push({"event": "dispense_release_gate_close"})
        _push({"event": "dispense_gate_close"})

        # Decrement count
        slot_state["pillCount"]   = max(0, int(slot_state.get("pillCount") or 0) - 1)
        slot_state["isEmpty"]     = slot_state["pillCount"] <= 0
        slot_state["needsRefill"] = slot_state["isEmpty"]

        _push({
            "event":     "dispense_complete",
            "slot":      slot,
            "med_id":    med_id,
            "med_name":  med_name,
            "remaining": slot_state["pillCount"],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        })
        _state["dispensing"]  = False
        _state["active_slot"] = None
        _set_status("idle")
        _save_state()
    finally:
        _dispense_lock.release()


@app.post("/confirm")
def post_confirm():
    """App sends YES/NO for a held pill (UNSURE result)."""
    data      = request.get_json(force=True)
    confirmed = bool(data.get("confirmed", False))
    slot = _normalise_slot(data.get("slot") or ((_last_detection or {}).get("slot")) or "1")
    _push({
        "event": "confirmation_received",
        "confirmed": confirmed,
        "slot": slot,
        "detected_nhi": (_last_detection or {}).get("detected_nhi"),
        "detected_name": (_last_detection or {}).get("detected_name"),
    })
    return jsonify({"ok": True, "confirmed": confirmed, "slot": slot})


@app.get("/status")
def get_status():
    return jsonify(_status_payload())


@app.get("/")
def get_root():
    """Redirect root to the 3D viewer."""
    return redirect("/viewer")


@app.get("/viewer")
def get_viewer():
    """Serve the interactive 3D digital twin viewer — never cached."""
    viewer_path = pathlib.Path(__file__).parent / "viewer.html"
    resp = send_file(viewer_path, mimetype="text/html")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.get("/setup.png")
def get_setup_qr_png():
    """Serve the setup QR code as a PNG image."""
    import io as _io
    if _SETUP_QR_PNG is None:
        return jsonify({"error": "QR not generated — install qrcode[pil]"}), 503
    return send_file(_io.BytesIO(_SETUP_QR_PNG), mimetype="image/png",
                     max_age=0, conditional=False)


@app.get("/setup")
def get_setup_page():
    """Standalone setup page — shows the QR code for the Flutter app to scan.

    In production this will be displayed on the dispenser's LCD screen.
    For the demo, open http://<ip>:5000/setup in a browser on the same network.
    """
    import socket as _socket
    try:
        _s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        _s.connect(("8.8.8.8", 80))
        _ip = _s.getsockname()[0]
        _s.close()
    except Exception:
        _ip = "127.0.0.1"

    serial   = DEVICE_INFO["serial_number"]
    firmware = DEVICE_INFO["firmware_version"]
    has_qr   = _SETUP_QR_PNG is not None
    qr_block = (
        f'<img src="/setup.png" alt="Setup QR Code" '
        f'style="width:280px;height:280px;border:4px solid #4CAF50;border-radius:12px;">'
        if has_qr else
        '<div style="width:280px;height:280px;display:flex;align-items:center;justify-content:center;'
        'border:4px dashed #aaa;border-radius:12px;color:#888;font-size:14px;text-align:center;padding:16px;">'
        'QR unavailable<br><small>pip install qrcode[pil]</small></div>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Hero Pill Dispenser — Setup</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: linear-gradient(135deg, #1a237e 0%, #283593 50%, #1565c0 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }}
    .card {{
      background: white;
      border-radius: 24px;
      padding: 40px 48px;
      text-align: center;
      box-shadow: 0 20px 60px rgba(0,0,0,0.4);
      max-width: 480px;
      width: 100%;
    }}
    .logo {{
      font-size: 48px;
      margin-bottom: 8px;
    }}
    h1 {{
      color: #1a237e;
      font-size: 22px;
      font-weight: 700;
      margin-bottom: 4px;
    }}
    .subtitle {{
      color: #666;
      font-size: 14px;
      margin-bottom: 32px;
    }}
    .qr-wrap {{
      display: flex;
      justify-content: center;
      margin-bottom: 28px;
    }}
    .instructions {{
      background: #f0f4ff;
      border-radius: 12px;
      padding: 16px 20px;
      text-align: left;
      margin-bottom: 24px;
    }}
    .instructions p {{
      font-size: 14px;
      color: #333;
      line-height: 1.6;
    }}
    .instructions ol {{
      font-size: 14px;
      color: #333;
      line-height: 2;
      padding-left: 20px;
    }}
    .url-box {{
      background: #e8f5e9;
      border: 2px solid #4CAF50;
      border-radius: 10px;
      padding: 12px 20px;
      font-family: monospace;
      font-size: 16px;
      font-weight: 700;
      color: #1b5e20;
      margin-bottom: 20px;
      word-break: break-all;
    }}
    .meta {{
      display: flex;
      justify-content: center;
      gap: 24px;
      font-size: 12px;
      color: #999;
    }}
    .meta span {{ white-space: nowrap; }}
    .dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%;
             background: #4CAF50; margin-right: 6px; animation: pulse 1.5s infinite; }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 1; }}
      50% {{ opacity: 0.3; }}
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">💊</div>
    <h1>Hero Smart Pill Dispenser</h1>
    <p class="subtitle">Scan this QR code with the Hero app to connect</p>

    <div class="qr-wrap">
      {qr_block}
    </div>

    <div class="url-box">
      <span class="dot"></span>http://{_ip}:5000
    </div>

    <div class="instructions">
      <ol>
        <li>Open the <strong>Hero</strong> app</li>
        <li>Go to <strong>Settings → Pair Dispenser</strong></li>
        <li>Tap <strong>"Scan Dispenser QR Code"</strong></li>
        <li>Point your camera at the QR code above</li>
      </ol>
    </div>

    <div class="meta">
      <span>Serial: {serial}</span>
      <span>Firmware: v{firmware}</span>
    </div>
  </div>
</body>
</html>"""


@app.get("/model/hero_full_assembly.glb")
def get_model_glb():
    """Serve the Fusion 360 GLB export for the Three.js viewer."""
    glb_path = pathlib.Path(__file__).parent.parent / "output" / "hero_full_assembly.glb"
    if not glb_path.exists():
        return jsonify({"error": "GLB not found — export from Fusion 360 first",
                        "expected_path": str(glb_path)}), 404
    resp = send_file(glb_path, mimetype="model/gltf-binary")
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ── REAL pill detection endpoint (the main selling point) ────────────────────

@app.post("/detect")
def post_detect():
    """
    Run REAL ONNX inference on an uploaded pill image.

    Accepts multipart/form-data:
      slot  — target carousel slot (string or int)
      image — JPEG/PNG of a single pill (taken by the phone camera)

    Returns:
      result      MATCH | UNSURE | NO_MATCH
      confidence  0.0–1.0
      detected_nhi   NHI code identified by the model
      detected_name  medication name from the prescription
      expected_name  what the user was supposed to load
      matches_expected  True if detected NHI belongs to the requested slot
      top_candidates    [{nhi_code, name, score} ...] top-3 closest matches
      auto_registered   True if this image triggered profile-locking
      accumulator_n     samples seen so far for this medication

    Side effects:
      - Saves uploaded image to RECENT_IMG (served at /recent_capture.jpg)
      - Pushes detection_started + detection_complete events to the viewer
      - Registers profile to detection/data/profiles/ when MIN_REG_SAMPLES reached
    """
    global _last_detection
    if not _REAL_INFERENCE_OK:
        return jsonify({"ok": False, "reason": "inference_not_loaded",
                        "hint": "ONNX model or dependencies missing — check server log"}), 503
    if "image" not in request.files:
        return jsonify({"ok": False, "reason": "missing_image"}), 400

    f    = request.files["image"]
    slot = _normalise_slot(request.form.get("slot", "1"))
    expected = _slots.get(slot, {})
    expected_name = expected.get("medicationName", "?")
    expected_nhi  = _med_nhi_code(expected) if expected else ""

    # Save the live capture so the viewer can display it
    try:
        f.save(RECENT_IMG)
    except Exception as e:
        return jsonify({"ok": False, "reason": f"save_failed: {e}"}), 500

    _push({"event":         "detection_started",
           "slot":          slot,
           "expected_name": expected_name})

    try:
        result = _infer_pill_image(RECENT_IMG, expected_nhi or "")
    except Exception as e:
        _push({"event": "detection_error", "slot": slot, "reason": str(e)})
        return jsonify({"ok": False, "reason": str(e)}), 500

    detected_nhi  = result.get("nhi_code")
    detected_med  = _slot_for_nhi(detected_nhi) if detected_nhi else {}
    detected_name = detected_med.get("medicationName") or detected_nhi or "?"
    matches_expected = bool(detected_nhi and (
        detected_nhi == expected_nhi or
        detected_med.get("compartmentId") == expected.get("compartmentId")
    ))

    payload = {
        "event":            "detection_complete",
        "slot":             slot,
        "result":           result["result"],
        "confidence":       round(result["confidence"], 3),
        "detected_nhi":     detected_nhi,
        "detected_name":    detected_name,
        "med_name":         detected_name,
        "expected_name":    expected_name,
        "matches_expected": matches_expected,
        "top_candidates":   result.get("top_candidates", []),
        "auto_registered":  result.get("auto_registered", False),
        "accumulator_n":    result.get("accumulator_n", 0),
        "debug_reason":     result.get("reason", ""),
        "debug_rx_count":   len(_rx),
        "debug_locked":     len(_db._index) if _db else 0,
        "debug_image_quality": result.get("image_quality", {}),
        "debug_prior":      result.get("_prior_debug", ""),
    }
    _last_detection = dict(payload)
    _push(payload)
    print(f"[detect] slot={slot} expected={expected_name} → "
          f"{result['result']} {result['confidence']:.2f} "
          f"detected={detected_name} {'OK' if matches_expected else 'MISMATCH'}")

    return jsonify({"ok": True, **payload})


@app.get("/recent_capture.jpg")
def get_recent_capture():
    """Serve the most recently uploaded pill image to the 3D viewer."""
    if not RECENT_IMG.exists():
        return ("", 404)
    resp = send_file(RECENT_IMG, mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return resp


@app.get("/dataset_images")
def get_dataset_images():
    """
    List available ePillID dataset images for viewer test panel.
    Returns up to 200 entries: [{filename, label, is_ref, is_front}, ...].
    """
    import csv
    csv_path = HERE / "ePillID_data" / "all_labels.csv"
    img_dir  = HERE / "ePillID_data" / "classification_data" / "fcn_mix_weight" / "dc_224"
    if not csv_path.exists():
        return jsonify({"ok": False, "reason": "dataset not found"}), 404
    rows = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                fname = row.get("images", "")
                # Only include images that actually exist
                if (img_dir / fname).exists():
                    rows.append({
                        "filename": fname,
                        "label":    row.get("label", ""),
                        "is_ref":   row.get("is_ref", "False") == "True",
                        "is_front": row.get("is_front", "False") == "True",
                    })
                if len(rows) >= 200:
                    break
    except Exception as e:
        return jsonify({"ok": False, "reason": str(e)}), 500
    return jsonify({"ok": True, "images": rows, "total": len(rows)})


@app.get("/dataset_images/<filename>")
def get_dataset_image(filename: str):
    """Serve a specific ePillID dataset image by filename (e.g. 42.jpg)."""
    from werkzeug.utils import secure_filename as _sf
    safe = _sf(filename)
    img_path = HERE / "ePillID_data" / "classification_data" / "fcn_mix_weight" / "dc_224" / safe
    if not img_path.exists():
        return ("", 404)
    return send_file(img_path, mimetype="image/jpeg")


# ── mechanical demo sequence ──────────────────────────────────────────────────

_demo_lock = threading.Lock()


@app.post("/run_demo")
def post_run_demo():
    """Trigger the full mechanical demo animation sequence in the viewer."""
    if not _demo_lock.acquire(blocking=False):
        return jsonify({"ok": False, "reason": "demo_already_running"}), 409
    slot = int((request.get_json(silent=True) or {}).get("slot", 1))
    threading.Thread(target=_run_demo_sequence, args=(slot,), daemon=True).start()
    return jsonify({"ok": True, "slot": slot})


def _run_demo_sequence(slot: int = 1):
    """Emit the full LOAD + DISPENSE event sequence so the viewer's cutaway
    transparency, pill flow path, and stage overlays all activate."""
    def wait(s): time.sleep(s)
    try:
        # If no prescription is loaded, seed a placeholder so med_name renders
        if not _slots.get(str(slot)):
            _slots[str(slot)] = {
                "compartmentId":  str(slot),
                "medicationId":   "demo-med",
                "medicationName": "Demo Pill",
                "quantity":       1,
            }
        med_name = _slots[str(slot)].get("medicationName", "Demo Pill")
        med_id   = _slots[str(slot)].get("medicationId",   "demo-med")
        slot_str = str(slot)

        # ── LOAD PHASE ──────────────────────────────────────────────────────
        _set_status("loading")
        _push({"event": "load_started", "slot": slot_str,
               "med_name": med_name, "med_id": med_id})
        _push({"event": "carousel_rotate", "slot": slot_str})
        wait(1.2)
        _push({"event": "hatch_open"})
        wait(0.9)
        _push({"event": "pill_in_chamber", "slot": slot_str, "med_name": med_name})
        wait(2.0)
        _push({"event": "detection_complete", "slot": slot_str,
               "med_name": med_name, "result": "MATCH", "confidence": 0.97})
        wait(0.8)
        _push({"event": "hatch_close"})
        wait(0.5)
        _push({"event": "trapdoor_open"})
        wait(0.4)
        _push({"event": "pill_routing", "slot": slot_str, "med_name": med_name})
        wait(2.0)
        _push({"event": "trapdoor_close"})
        _push({"event": "pill_in_slot", "slot": slot_str, "med_name": med_name})
        wait(1.4)
        _push({"event": "slot_loaded", "slot": slot_str,
               "med_name": med_name, "pill_count": 1})
        # Update slot state so the dispense check passes
        st = _slot_state.setdefault(slot_str, {
            "compartmentNumber": slot, "medicationId": med_id,
            "medicationName": med_name, "pillCount": 0,
            "isEmpty": True, "needsRefill": False, "loaded": False,
        })
        st["pillCount"]  = max(1, int(st.get("pillCount") or 0) + 1)
        st["isEmpty"]    = False
        st["loaded"]     = True
        _set_status("idle")
        wait(1.5)   # Brief pause before dispense phase

        # ── DISPENSE PHASE ──────────────────────────────────────────────────
        _set_status("dispensing")
        _push({"event": "dispense_started", "slot": slot_str,
               "med_name": med_name, "med_id": med_id})
        wait(0.6)
        _push({"event": "carousel_rotate", "slot": slot_str, "med_name": med_name})
        wait(1.0)
        _push({"event": "slot_opening", "slot": slot_str, "med_name": med_name})
        wait(0.6)
        _push({"event": "dispense_gate_open"})
        wait(0.6)
        _push({"event": "pill_falling", "slot": slot_str, "med_name": med_name})
        wait(1.7)
        _push({"event": "dispense_release_gate_open"})
        wait(0.4)
        _push({"event": "pill_in_cup", "slot": slot_str, "med_name": med_name})
        wait(1.0)
        _push({"event": "dispense_release_gate_close"})
        _push({"event": "dispense_gate_close"})
        st["pillCount"]   = max(0, int(st.get("pillCount") or 0) - 1)
        st["isEmpty"]     = st["pillCount"] <= 0
        st["needsRefill"] = st["isEmpty"]
        _push({"event": "dispense_complete", "slot": slot_str,
               "med_id": med_id, "med_name": med_name,
               "remaining": st["pillCount"],
               "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")})
        _set_status("idle")
        print(f"[demo] Full demo complete (slot {slot}, {med_name})")
    finally:
        _demo_lock.release()


# Track which client IPs have polled (for one-time connect log)
_polled_ips: set = set()

@app.get("/events/recent")
def get_events_recent():
    """
    Polling endpoint for the Flutter app and any local status client.

    Returns all events whose _id is greater than <since>, plus the latest
    server state and next event id. This is state reporting only; it does
    not create an app connection.
    """
    # First poll from each client IP gets logged so the terminal shows activity
    client_ip = request.remote_addr or "?"
    if client_ip not in _polled_ips:
        _polled_ips.add(client_ip)
        print(f"[demo] Viewer connected from {client_ip}")

    since = int(request.args.get("since", 0))
    with _event_lock:
        new_events = [e for e in _event_log if e["_id"] > since]
        latest_id  = _event_id
    return jsonify({
        "status": _state["status"],
        "app_connected": _app_connected(),
        "events": new_events,
        "next_id": latest_id,
        "state": _status_payload(),
    })


# ── startup ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import socket

    # Print local IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = "127.0.0.1"
    finally:
        s.close()

    # Restore persisted Pi state from disk (slot inventory, pairing)
    _load_state()

    # Generate setup QR code (requires: pip install qrcode[pil])
    _generate_setup_qr(local_ip)

    # Boot real ML inference (ONNX MobileNetV2 + classical features)
    _REAL_INFERENCE_OK = _load_real_inference()
    if _REAL_INFERENCE_OK:
        DETECTION_MODE = "real"
        # Sync any persisted prescription into PillDatabase so NHI priors work
        if _rx and _db:
            _sync_prescription_to_db()
    else:
        DETECTION_MODE = "skipped"

    _push({"event": "device_boot", "device_id": DEVICE_INFO["device_id"],
           "firmware": DEVICE_INFO["firmware_version"],
           "detection_mode": DETECTION_MODE})

    print()
    print("=" * 60)
    print("  Hero Pill Dispenser - HTTP Integration Server")
    print("=" * 60)
    print(f"  Device ID:  {DEVICE_INFO['device_id']}")
    print(f"  Serial:     {DEVICE_INFO['serial_number']}")
    print(f"  Firmware:   v{DEVICE_INFO['firmware_version']}")
    print(f"  Detection:  {DETECTION_MODE}")
    print()
    print(f"  Local IP:   {local_ip}")
    print(f"  App URL:    http://{local_ip}:5000")
    print(f"  Setup QR:   http://{local_ip}:5000/setup   ← open in browser to pair")
    print(f"  3D Viewer:  http://{local_ip}:5000/viewer")
    print()
    print("  API:")
    print("    POST /app/connect    mark Flutter app connected")
    print("    POST /app/heartbeat  keep Flutter app session alive")
    print("    POST /app/disconnect clear Flutter app session")
    print("    POST /prescription   load medication list from app")
    print("    POST /detect         upload prototype camera pill photo")
    print("    GET  /recent_capture.jpg latest uploaded pill image")
    print("    POST /load_pill      route accepted pill into slot")
    print("    POST /confirm        confirm an unsure detection")
    print("    POST /start_loading  mark loading session active")
    print("    POST /stop_loading   finish manual loading session")
    print("    POST /dispense       trigger pill dispense")
    print("    GET  /status         current device state (JSON)")
    print("    GET  /events/recent  polling event log")
    print("    GET  /setup          setup QR code page (browser)")
    print("    GET  /setup.png      setup QR code image")
    print("=" * 60)
    print()

    # Prefer Waitress — handles polling reliably on Windows.
    # Install with:  pip install waitress
    try:
        from waitress import serve as _waitress_serve
        print(f"  WSGI:       Waitress")
        print(f"  Polling:    GET /events/recent")
        print("=" * 60)
        print()
        _waitress_serve(app, host="0.0.0.0", port=5000, threads=16)
    except ImportError:
        print(f"  WSGI:       Werkzeug dev server  (install waitress for production)")
        print("=" * 60)
        print()
        app.run(host="0.0.0.0", port=5000, threaded=True)
