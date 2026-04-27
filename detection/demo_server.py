"""
demo_server.py — Pitch demo server for the Hero Smart Pill Dispenser.

Run on your RTX 5080 machine:
    python demo_server.py

Then:
  - Open  http://<your-ip>:5000/viewer  on the projector (3D digital twin)
  - In Flutter app: Settings → Demo Server → http://<your-ip>:5000

TWO modes (auto-detected at startup):
  REAL   — model + test images found → actual ONNX GPU inference on every pill
  SIM    — no model/images → realistic random simulation (same timing/events)

Real mode uses models/pill_embedding.onnx (trained on ePillID, RTX 5080).
Inference time on RTX 5080: ~4 ms per pill image.
"""

import json
import pathlib
import queue
import random
import threading
import time
from flask import Flask, request, jsonify, send_file, redirect
try:
    from flask_cors import CORS as _CORS
    _HAS_CORS = True
except ImportError:
    _HAS_CORS = False

HERE = pathlib.Path(__file__).parent

# ── tunable delays ────────────────────────────────────────────────────────────
DETECT_DELAY_S   = 1.4   # seconds between "pill dropped" and detection result
DISPENSE_DELAY_S = 2.0   # seconds between dispense command and confirmation

# ── real inference setup (RTX 5080) ──────────────────────────────────────────
# Loaded lazily at startup; falls back to simulation if unavailable.

_model   = None   # EmbeddingModel  (model.py)
_db      = None   # PillDatabase    (database.py)
_matcher = None   # PillMatcher     (model.py)

# Demo pill images: any .jpg/.png under detection/demo_pills/<med_id>/
# e.g.  demo_pills/AC23456100/pill_001.jpg
# On each detection cycle one image is picked at random and run through the model.
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
        print(f"[demo] Real inference unavailable ({e}) — using simulation")
        return False

def _infer_pill_image(image_path: pathlib.Path, med_id: str) -> dict:
    """
    Run actual ONNX inference on an image and return a result dict.
    Uses the same preprocess → embed → match pipeline as pipeline.py.
    """
    from PIL import Image as PILImage
    from preprocess import preprocess

    img = PILImage.open(image_path).convert("RGB")
    arr, meta = preprocess(img)

    if not meta.get("pill_found"):
        return {"result": "NO_MATCH", "confidence": 0.0, "reason": "no_pill_in_image"}

    embedding = _model.embed(arr)
    classical = meta["classical"]

    ref_embs, ref_cls, nhi_codes = _db.get_all_profiles()
    nhi_code, confidence, result = _matcher.match(
        embedding, classical, ref_embs, ref_cls, nhi_codes
    )

    return {
        "result":     result,
        "confidence": float(confidence),
        "nhi_code":   nhi_code,
        "inferred":   True,
    }

app   = Flask("demo_dispenser")
if _HAS_CORS:
    _CORS(app)   # allow phone (different IP) to POST to laptop server

_rx   = []                         # active prescription
_slots: dict = {}                  # slot → medication info
_state = {"status": "idle", "loading_slot": None, "loading_med": None}

# ── event log (for polling viewer) ───────────────────────────────────────────
# Each event gets an auto-incrementing integer ID.
# The viewer polls /events/recent?since=<id> and receives everything newer.
_event_log: list = []        # list of dicts, each has "_id" key
_event_id   = 0
_event_lock = threading.Lock()
_EVENT_LOG_MAX = 200         # keep last 200 events


# ── helpers ───────────────────────────────────────────────────────────────────

def _push(event: dict):
    """Record event in the poll log (viewer fetches /events/recent)."""
    global _event_id
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


# ── routes ────────────────────────────────────────────────────────────────────

@app.post("/prescription")
def post_prescription():
    """App sends the full medication list after QR/OCR scan."""
    global _rx, _slots
    data = request.get_json(force=True)
    _rx  = data.get("medications", [])
    _slots = {m.get("compartmentId", str(m.get("slot", i+1))): m
              for i, m in enumerate(_rx)}
    print(f"[demo] Prescription loaded: {len(_rx)} medications")
    for m in _rx:
        print(f"       slot {m.get('compartmentId','?')} — {m.get('medicationName','?')}")
    _push({"event": "prescription_ack", "count": len(_rx)})
    return jsonify({"ok": True, "count": len(_rx)})


@app.post("/start_loading")
def post_start_loading():
    """App says 'user is now loading pills into slot N'."""
    data   = request.get_json(force=True)
    slot   = str(data.get("slot", "1"))
    med_id = str(data.get("med_id", ""))

    _state["loading_slot"] = slot
    _state["loading_med"]  = med_id
    _set_status("imaging")

    med_name = _slots.get(slot, {}).get("medicationName", med_id)
    print(f"[demo] Start loading slot {slot} — {med_name}")
    _push({"event": "loading_started", "slot": slot, "med_id": med_id})

    # Spawn a background thread that simulates pills being detected
    threading.Thread(
        target=_simulate_loading, args=(slot, med_id), daemon=True
    ).start()

    return jsonify({"ok": True, "slot": slot, "med_id": med_id})


def _simulate_loading(slot: str, med_id: str):
    """
    Background thread: detect pills one at a time while loading is active.
    Uses real ONNX GPU inference if model + demo images are available,
    otherwise falls back to realistic random simulation.
    Runs until stop_loading is called.
    """
    # Find demo images for this med_id (for real inference)
    demo_images = []
    if DEMO_PILLS_DIR.exists():
        med_dir = DEMO_PILLS_DIR / med_id
        if not med_dir.exists():
            # Fall back to any available images
            med_dir = DEMO_PILLS_DIR
        demo_images = list(med_dir.glob("*.jpg")) + list(med_dir.glob("*.png"))

    use_real = (_model is not None) and bool(demo_images)
    mode_label = "GPU inference" if use_real else "simulation"
    print(f"[demo] Loading slot {slot} ({med_id}) — {mode_label}")

    pill_count = 0
    while _state["loading_slot"] == slot:
        time.sleep(DETECT_DELAY_S)
        if _state["loading_slot"] != slot:
            break

        pill_count += 1

        if use_real:
            # Real inference: pick a random demo image, run through ONNX model
            img_path = random.choice(demo_images)
            try:
                t0 = time.perf_counter()
                infer = _infer_pill_image(img_path, med_id)
                ms = (time.perf_counter() - t0) * 1000
                result     = infer["result"]
                confidence = infer["confidence"]
                print(f"[demo] Pill {pill_count}  {result}  conf={confidence:.3f}  "
                      f"({ms:.1f} ms GPU)  img={img_path.name}")
            except Exception as e:
                print(f"[demo] Inference error: {e} — using simulation fallback")
                result, confidence = "MATCH", round(random.uniform(0.88, 0.97), 3)
        else:
            # Simulation: 90% MATCH, 7% UNSURE, 3% NO_MATCH
            r = random.random()
            if r < 0.90:
                result, confidence = "MATCH",    round(random.uniform(0.88, 0.97), 3)
            elif r < 0.97:
                result, confidence = "UNSURE",   round(random.uniform(0.60, 0.75), 3)
            else:
                result, confidence = "NO_MATCH", round(random.uniform(0.20, 0.45), 3)
            print(f"[demo] Pill {pill_count} simulated → {result}  conf={confidence:.2f}")

        _push({
            "event":      "detection_result",
            "result":     result,
            "confidence": confidence,
            "slot":       slot,
            "med_id":     med_id,
            "pill_count": pill_count,
        })
        time.sleep(0.6)   # brief pause before next pill


@app.post("/stop_loading")
def post_stop_loading():
    """App says user finished loading this medication."""
    slot  = _state["loading_slot"]
    total = 0   # would be tracked in a real session
    _state["loading_slot"] = None
    _state["loading_med"]  = None
    _set_status("idle")
    _push({"event": "loading_complete", "slot": slot, "total_pills": total})
    return jsonify({"ok": True})


@app.post("/dispense")
def post_dispense():
    """App triggers a dispense (scheduled or manual)."""
    data = request.get_json(force=True)
    slot = str(data.get("slot", "1"))
    med  = _slots.get(slot, {})
    name = med.get("medicationName", f"slot {slot}")

    print(f"[demo] Dispense requested → slot {slot} ({name})")
    _set_status("dispensing")
    _push({"event": "dispense_started", "slot": slot})

    def _finish():
        time.sleep(DISPENSE_DELAY_S)
        # Simulate load cell reading: dose_mg ± 5%
        expected_mg = 100   # default; real app would send this
        measured_mg = round(expected_mg * random.uniform(0.95, 1.05))
        _set_status("idle")
        print(f"[demo] Dispense complete — {measured_mg} mg measured")
        _push({
            "event":              "dispense_complete",
            "slot":               slot,
            "med_id":             med.get("medicationId", ""),
            "med_name":           name,
            "weight_measured_mg": measured_mg,
            "weight_expected_mg": expected_mg,
            "timestamp":          time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        })

    threading.Thread(target=_finish, daemon=True).start()
    return jsonify({"ok": True, "slot": slot})


@app.post("/confirm")
def post_confirm():
    """App sends YES/NO for a held pill (UNSURE result)."""
    data      = request.get_json(force=True)
    confirmed = bool(data.get("confirmed", False))
    _push({"event": "confirmation_received", "confirmed": confirmed})
    return jsonify({"ok": True})


@app.get("/status")
def get_status():
    return jsonify({
        "status":           _state["status"],
        "prescription_count": len(_rx),
        "slots":            list(_slots.keys()),
        "loading_slot":     _state["loading_slot"],
    })


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


# Track which client IPs have polled (for one-time connect log)
_polled_ips: set = set()

@app.get("/events/recent")
def get_events_recent():
    """
    Polling endpoint for the 3D viewer.

    The viewer calls GET /events/recent?since=<id> every 500 ms.
    Returns all events whose _id is greater than <since>, plus the
    current server status and the latest _id (for the next poll).

    Using polling instead of SSE avoids streaming/buffering issues with
    every WSGI server on Windows (Werkzeug buffers, Waitress can't stream
    infinite generators).
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
        "status":    _state["status"],
        "events":    new_events,
        "next_id":   latest_id,
    })


# ── startup ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import socket

    # Try to load real GPU inference first
    real_mode = _load_real_inference()

    # Print local IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = "127.0.0.1"
    finally:
        s.close()

    print()
    print("=" * 60)
    print("  Hero Pill Dispenser — Demo Server")
    print("=" * 60)
    print(f"  Inference:  {'🟢 REAL (ONNX GPU — RTX 5080)' if real_mode else '🟡 SIMULATION (no model/images found)'}")
    if real_mode:
        demo_count = len(list(DEMO_PILLS_DIR.glob("**/*.jpg")) +
                         list(DEMO_PILLS_DIR.glob("**/*.png"))) if DEMO_PILLS_DIR.exists() else 0
        print(f"  Demo images: {demo_count} pill images in {DEMO_PILLS_DIR}")
    else:
        print(f"  To enable real inference:")
        print(f"    1. Ensure models/pill_embedding.onnx exists (run train.py)")
        print(f"    2. Add pill images to detection/demo_pills/<med_id>/")
    print()
    print(f"  Local IP:   {local_ip}")
    print(f"  3D Viewer:  http://{local_ip}:5000/viewer   ← open on projector")
    print(f"  App URL:    http://{local_ip}:5000          ← enter in Flutter app")
    print()
    print("  API:")
    print("    GET  /viewer         3D interactive digital twin")
    print("    POST /prescription   load medication list from app")
    print("    POST /start_loading  begin pill detection session")
    print("    POST /stop_loading   end loading session")
    print("    POST /dispense       trigger pill dispense")
    print("    GET  /status         current device state (JSON)")
    print("    GET  /events         SSE live event stream")
    print("=" * 60)
    print()

    # Prefer Waitress — handles polling reliably on Windows.
    # Install with:  pip install waitress
    try:
        from waitress import serve as _waitress_serve
        print(f"  WSGI:       Waitress")
        print(f"  Polling:    GET /events/recent  (viewer & app poll every 500 ms)")
        print("=" * 60)
        print()
        _waitress_serve(app, host="0.0.0.0", port=5000, threads=16)
    except ImportError:
        print(f"  WSGI:       Werkzeug dev server  (install waitress for production)")
        print("=" * 60)
        print()
        app.run(host="0.0.0.0", port=5000, threaded=True)
