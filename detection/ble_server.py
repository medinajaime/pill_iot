"""
ble_server.py — Pi BLE peripheral + HTTP fallback for app communication.

The Pi advertises as a BLE peripheral using the `bless` library.
If BLE is unavailable (dev machine, missing BlueZ), it falls back to a
lightweight Flask HTTP server on port 5000.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLE GATT layout  (UUIDs MUST match lib/services/dispenser_service.dart)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Service:   12345678-1234-1234-1234-123456789abc  (DISPENSER_SVC_UUID)
  Write char:  12345678-1234-1234-1234-123456789abd  (app → Pi)
  Notify char: 12345678-1234-1234-1234-123456789abe  (Pi → app)

Device name: "SPD-<serial>" — app pairBySerialNumber() filters on "SPD".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Write char protocol (app → Pi)  — matches dispenser_service.dart exactly
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Existing opcodes (coded in Flutter app, must NOT change):
  [0x01, slot]                          Dispense medication in slot N
  [0x02]                                Status request
  [0x03, ssid_len, ...ssid, ...pass]    WiFi configuration

Extended opcodes (new — Pi only, app support to be added):
  [0x10, len_hi, len_lo, ...utf8_json]  Full medication list JSON
  [0x11, slot, id_len, ...utf8_med_id]  Start loading session for slot
  [0x12]                                Stop loading session
  [0x13, 0|1]                           Pill confirmation (0=reject, 1=accept)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Notify char protocol (Pi → app)  — matches dispenser_service.dart exactly
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Existing opcodes (handled by _handleDeviceNotification in Flutter):
  [0x01, slot]                          Dispense complete
  [0x02, ...status_bytes]               Status update
  [0xFF, ...utf8_message]               Error

Extended opcodes (Pi → app, new):
  [0x10, result, confidence_pct]        Detection result
                                          result: 0=MATCH 1=NO_MATCH 2=UNSURE
                                          confidence_pct: 0-100 integer
  [0x11, slot, count]                   Pill count update for slot
  [0x12, slot, total]                   Loading session complete

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HTTP fallback endpoints (Flask, used when BLE unavailable)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  POST /prescription          body: {"medications": [...]}
  GET  /status                returns current device state
  POST /confirm               body: {"pill_id": "...", "confirmed": true}
  POST /dispense              body: {"slot": 1}
  POST /start_loading         body: {"slot": 1, "med_id": "AC23456100"}
  POST /stop_loading
  GET  /events                SSE stream of detection + dispense events
"""

import asyncio
import json
import os
import queue
import socket
import threading
from typing import Optional

# ── BLE (bless) ───────────────────────────────────────────────────────────────

try:
    from bless import (
        BlessServer,
        BlessGATTCharacteristic,
        GATTCharacteristicProperties,
        GATTAttributePermissions,
    )
    _BLESS_OK = True
except ImportError:
    _BLESS_OK = False

# ── HTTP (Flask) ──────────────────────────────────────────────────────────────

try:
    from flask import Flask, request, jsonify, Response, stream_with_context
    _FLASK_OK = True
except ImportError:
    _FLASK_OK = False

# ── UUIDs — MUST match lib/services/dispenser_service.dart ───────────────────

DISPENSER_SVC_UUID = "12345678-1234-1234-1234-123456789abc"
WRITE_CHAR_UUID    = "12345678-1234-1234-1234-123456789abd"  # app → Pi
NOTIFY_CHAR_UUID   = "12345678-1234-1234-1234-123456789abe"  # Pi → app

HTTP_PORT = 5000

# Opcodes (write char, app → Pi)
CMD_DISPENSE       = 0x01
CMD_STATUS_REQ     = 0x02
CMD_WIFI_CFG       = 0x03
CMD_MED_LIST       = 0x10   # extended: [0x10, len_hi, len_lo, ...json]
CMD_START_LOADING  = 0x11   # extended: [0x11, slot, id_len, ...med_id_utf8]
CMD_STOP_LOADING   = 0x12
CMD_CONFIRM        = 0x13   # extended: [0x13, 0|1]

# Opcodes (notify char, Pi → app)
EVT_DISPENSE_DONE  = 0x01
EVT_STATUS         = 0x02
EVT_ERROR          = 0xFF
EVT_DETECT_RESULT  = 0x10   # [0x10, result_code, confidence_pct]
EVT_PILL_COUNT     = 0x11   # [0x11, slot, count]
EVT_LOADING_DONE   = 0x12   # [0x12, slot, total_pills]

# Detection result codes (EVT_DETECT_RESULT byte 1)
DETECT_MATCH    = 0
DETECT_NO_MATCH = 1
DETECT_UNSURE   = 2


def _device_name() -> str:
    """
    Build 'SPD-XXXX' device name.  Uses last 4 chars of Pi serial from
    /proc/cpuinfo, or falls back to last 4 of hostname.
    The Flutter app's pairBySerialNumber() scans for names containing 'SPD'.
    """
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("Serial"):
                    serial = line.split(":")[1].strip()[-4:].upper()
                    return f"SPD-{serial}"
    except OSError:
        pass
    hostname = socket.gethostname()[-4:].upper()
    return f"SPD-{hostname}"


# ── shared state ──────────────────────────────────────────────────────────────

class _ServerState:
    """Thread-safe shared state between the BLE/HTTP layer and the pipeline."""

    def __init__(self):
        self._lock          = threading.Lock()
        self._status        = "idle"
        self._pending_pill  = None
        self._confirm_queue = queue.Queue()
        self._event_queue   = queue.Queue(maxsize=100)

        # Callbacks wired by the caller (main.py / pipeline)
        self.on_prescription: Optional[callable] = None
        self.on_dispense:     Optional[callable] = None
        self.on_start_loading: Optional[callable] = None   # (slot, med_id)
        self.on_stop_loading:  Optional[callable] = None

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    @status.setter
    def status(self, value: str):
        with self._lock:
            self._status = value
        self._push_raw(bytes([EVT_STATUS]) + value.encode("utf-8"))

    def set_pending_pill(self, result: dict):
        with self._lock:
            self._pending_pill = result
        # Notify app: detection result = UNSURE or NO_MATCH
        result_str = result.get("status", "")
        code = DETECT_UNSURE if result_str == "UNSURE" else DETECT_NO_MATCH
        conf = int(min(99, round(result.get("confidence", 0.0) * 100)))
        self._push_raw(bytes([EVT_DETECT_RESULT, code, conf]))

    def clear_pending_pill(self):
        with self._lock:
            self._pending_pill = None

    def notify_detect_match(self, slot: int, confidence: float):
        """Tell app a pill was successfully matched and routed."""
        conf = int(min(99, round(confidence * 100)))
        self._push_raw(bytes([EVT_DETECT_RESULT, DETECT_MATCH, conf]))

    def notify_dispense_complete(self, slot: int):
        """Tell app dispense is done — matches app's 0x01 handler."""
        self._push_raw(bytes([EVT_DISPENSE_DONE, slot & 0xFF]))

    def notify_pill_count(self, slot: int, count: int):
        self._push_raw(bytes([EVT_PILL_COUNT, slot & 0xFF, count & 0xFF]))

    def notify_loading_done(self, slot: int, total: int):
        self._push_raw(bytes([EVT_LOADING_DONE, slot & 0xFF, total & 0xFF]))

    def notify_error(self, message: str):
        """Tell app about an error — matches app's 0xFF handler."""
        self._push_raw(bytes([EVT_ERROR]) + message.encode("utf-8")[:200])

    def _push_raw(self, data: bytes):
        """Push raw bytes onto the notify queue."""
        try:
            self._event_queue.put_nowait(data)
        except queue.Full:
            self._event_queue.get_nowait()
            self._event_queue.put_nowait(data)

    async def wait_for_confirmation(self, timeout: float = 120.0) -> Optional[bool]:
        """Awaitable: returns True (accept), False (reject), or None (timeout)."""
        loop = asyncio.get_event_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, self._confirm_queue.get),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return None

    def receive_confirmation(self, confirmed: bool):
        self._confirm_queue.put(confirmed)


# ── write-char parser ─────────────────────────────────────────────────────────

def _parse_write(data: bytes, state: "_ServerState"):
    """
    Decode a write-char payload from the app and dispatch to callbacks.
    Handles both the existing Flutter binary protocol and new extended opcodes.
    """
    if not data:
        return
    opcode = data[0]

    if opcode == CMD_DISPENSE:
        # [0x01, slot]  — matches dispenser_service.dart dispenseMedication()
        slot = data[1] if len(data) > 1 else 1
        if state.on_dispense:
            threading.Thread(
                target=state.on_dispense, args=(int(slot),), daemon=True
            ).start()

    elif opcode == CMD_STATUS_REQ:
        # [0x02]  — matches dispenser_service.dart requestStatus()
        state._push_raw(bytes([EVT_STATUS]) + state.status.encode("utf-8"))

    elif opcode == CMD_WIFI_CFG:
        # [0x03, ssid_len, ...ssid_bytes, ...pass_bytes]
        # matches dispenser_service.dart configureWiFi()
        if len(data) > 2:
            ssid_len = data[1]
            ssid = data[2 : 2 + ssid_len].decode("utf-8", errors="replace")
            pwd  = data[2 + ssid_len :].decode("utf-8", errors="replace")
            print(f"[BLE] WiFi config: SSID={ssid!r}")
            # TODO: persist WiFi credentials and reconnect

    elif opcode == CMD_MED_LIST:
        # [0x10, len_hi, len_lo, ...utf8_json]
        if len(data) >= 4:
            length   = (data[1] << 8) | data[2]
            json_raw = data[3 : 3 + length]
            try:
                payload = json.loads(json_raw.decode("utf-8"))
                meds    = payload.get("medications", [])
                if state.on_prescription:
                    threading.Thread(
                        target=state.on_prescription, args=(meds,), daemon=True
                    ).start()
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                state.notify_error(f"Bad medication list: {e}")

    elif opcode == CMD_START_LOADING:
        # [0x11, slot, id_len, ...utf8_med_id]
        if len(data) >= 4:
            slot   = int(data[1])
            id_len = data[2]
            med_id = data[3 : 3 + id_len].decode("utf-8", errors="replace")
            if state.on_start_loading:
                threading.Thread(
                    target=state.on_start_loading, args=(slot, med_id), daemon=True
                ).start()

    elif opcode == CMD_STOP_LOADING:
        if state.on_stop_loading:
            threading.Thread(
                target=state.on_stop_loading, daemon=True
            ).start()

    elif opcode == CMD_CONFIRM:
        # [0x13, 0|1]
        confirmed = bool(data[1]) if len(data) > 1 else False
        state.receive_confirmation(confirmed)

    else:
        print(f"[BLE] Unknown opcode 0x{opcode:02X} — ignored")


# ── BLE server (bless) ────────────────────────────────────────────────────────

class BLEDispenser:
    """BLE GATT peripheral using the `bless` library (cross-platform BlueZ wrapper)."""

    def __init__(self, state: _ServerState):
        self.state = state
        self._server: Optional["BlessServer"] = None
        self._name = _device_name()

    async def _start(self):
        loop    = asyncio.get_event_loop()
        self._server = BlessServer(name=self._name, loop=loop)
        self._server.read_request_func  = self._on_read
        self._server.write_request_func = self._on_write

        await self._server.add_new_service(DISPENSER_SVC_UUID)

        _rw   = (GATTCharacteristicProperties.read |
                 GATTCharacteristicProperties.write)
        _ntf  = GATTCharacteristicProperties.notify
        _perm = (GATTAttributePermissions.readable |
                 GATTAttributePermissions.writeable)

        # Write characteristic — app sends commands here
        await self._server.add_new_characteristic(
            DISPENSER_SVC_UUID, WRITE_CHAR_UUID, _rw, None, _perm
        )
        # Notify characteristic — Pi pushes events here
        await self._server.add_new_characteristic(
            DISPENSER_SVC_UUID, NOTIFY_CHAR_UUID, _ntf, None, _perm
        )

        await self._server.start()
        print(f"[BLE] Advertising as '{self._name}'  service={DISPENSER_SVC_UUID}")

        asyncio.ensure_future(self._notify_loop())

    async def _notify_loop(self):
        """Forward queued byte payloads to the notify characteristic."""
        while True:
            await asyncio.sleep(0.05)
            try:
                data = self.state._event_queue.get_nowait()
            except queue.Empty:
                continue
            if self._server:
                char = self._server.get_characteristic(NOTIFY_CHAR_UUID)
                char.value = bytearray(data)
                await self._server.update_value(DISPENSER_SVC_UUID, NOTIFY_CHAR_UUID)

    def _on_read(self, char: "BlessGATTCharacteristic", **_) -> bytearray:
        if char.uuid == NOTIFY_CHAR_UUID:
            return bytearray(self.state.status.encode("utf-8"))
        return bytearray()

    def _on_write(self, char: "BlessGATTCharacteristic", value: bytearray, **_):
        if char.uuid == WRITE_CHAR_UUID:
            _parse_write(bytes(value), self.state)

    def start_in_thread(self):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self._start())
        loop.run_forever()


# ── HTTP server (Flask fallback) ──────────────────────────────────────────────

class HTTPDispenser:
    """Flask HTTP server — used when BLE unavailable (dev machine, CI, etc.)."""

    def __init__(self, state: _ServerState):
        self.state = state
        self.app   = Flask("pill_dispenser")
        self._register_routes()

    def _register_routes(self):
        state = self.state
        app   = self.app

        @app.post("/prescription")
        def post_prescription():
            data = request.get_json(force=True)
            meds = data.get("medications", [])
            if state.on_prescription:
                threading.Thread(
                    target=state.on_prescription, args=(meds,), daemon=True
                ).start()
            return jsonify({"ok": True, "count": len(meds)})

        @app.get("/status")
        def get_status():
            return jsonify({"status": state.status})

        @app.post("/confirm")
        def post_confirm():
            data      = request.get_json(force=True)
            confirmed = bool(data.get("confirmed", False))
            state.receive_confirmation(confirmed)
            return jsonify({"ok": True})

        @app.post("/dispense")
        def post_dispense():
            data = request.get_json(force=True)
            slot = int(data.get("slot", 0))
            if state.on_dispense:
                threading.Thread(
                    target=state.on_dispense, args=(slot,), daemon=True
                ).start()
            return jsonify({"ok": True})

        @app.post("/start_loading")
        def post_start_loading():
            data   = request.get_json(force=True)
            slot   = int(data.get("slot", 0))
            med_id = str(data.get("med_id", ""))
            if state.on_start_loading:
                threading.Thread(
                    target=state.on_start_loading, args=(slot, med_id), daemon=True
                ).start()
            return jsonify({"ok": True, "slot": slot, "med_id": med_id})

        @app.post("/stop_loading")
        def post_stop_loading():
            if state.on_stop_loading:
                threading.Thread(
                    target=state.on_stop_loading, daemon=True
                ).start()
            return jsonify({"ok": True})

        @app.get("/events")
        def get_events():
            """SSE stream — subscribe for real-time detection + dispense events."""
            def generate():
                while True:
                    try:
                        raw = state._event_queue.get(timeout=30)
                        # Convert bytes to a human-readable JSON event for SSE
                        opcode = raw[0] if raw else 0xFF
                        payload = list(raw)
                        yield f"data: {json.dumps({'opcode': opcode, 'bytes': payload})}\n\n"
                    except queue.Empty:
                        yield ": heartbeat\n\n"

            return Response(
                stream_with_context(generate()),
                mimetype="text/event-stream",
                headers={"Cache-Control": "no-cache"},
            )

    def start_in_thread(self, host: str = "0.0.0.0", port: int = HTTP_PORT):
        threading.Thread(
            target=lambda: self.app.run(host=host, port=port, threaded=True),
            daemon=True,
        ).start()
        print(f"[HTTP] Server running on http://{host}:{port}")


# ── public factory ────────────────────────────────────────────────────────────

def make_state() -> _ServerState:
    return _ServerState()


def start_server(state: _ServerState, prefer_ble: bool = True) -> _ServerState:
    """
    Start BLE or HTTP server in a background thread.
    Returns the shared state object so the pipeline can push events to it.

    Wire callbacks before calling this::

        state = make_state()
        state.on_prescription  = db.load_prescription
        state.on_dispense      = pipeline.dispense_slot
        state.on_start_loading = pipeline.arm_loading_session
        state.on_stop_loading  = pipeline.disarm_loading_session
        start_server(state)
    """
    if prefer_ble and _BLESS_OK:
        server = BLEDispenser(state)
        threading.Thread(target=server.start_in_thread, daemon=True).start()
    elif _FLASK_OK:
        server = HTTPDispenser(state)
        server.start_in_thread()
    else:
        print(
            "WARNING: Neither bless nor flask is installed.\n"
            "  pip install bless    (BLE peripheral, Pi)\n"
            "  pip install flask    (HTTP fallback, dev machine)"
        )
    return state
