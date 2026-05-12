"""
warmup_profiles.py
==================
Pre-lock pill detection profiles before a live demo.

Usage
-----
1. Start demo_server.py first:
       python demo_server.py

2. Send the demo prescription (or do it from the Flutter app).
   The server must know which medications exist before warm-up.

3. Run this script from the detection/ folder:
       python warmup_profiles.py --url http://localhost:5000 --pills-dir demo_pills

   Or to warm up a specific slot only:
       python warmup_profiles.py --slot 1

What it does
------------
For every medication slot it finds pills images in
  demo_pills/<slot_or_nhi_code>/  (jpg / png)

It sends the images one by one to POST /detect.
After 3 MATCHes the server auto-locks the profile.
The script shows a live progress table and stops early if a profile locks.

Synthetic pill generation (--generate flag)
------------------------------------------
If you don't have real photos yet, use --generate to create simple synthetic
beige-ellipse-on-white images (these work with the Otsu segmenter).
They won't be accurate for real detection but let you verify the pipeline
end-to-end before the photo session.

    python warmup_profiles.py --generate --slots 1,2,3
"""

import argparse
import io
import pathlib
import sys
import time

try:
    import requests
except ImportError:
    print("[warmup] requests not installed — pip install requests")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _colour_for(result: str) -> str:
    """ANSI colour code for the terminal."""
    if result == "MATCH":    return "\033[92m"   # green
    if result == "UNSURE":   return "\033[93m"   # yellow
    if result == "NO_MATCH": return "\033[91m"   # red
    return "\033[0m"


def _reset() -> str:
    return "\033[0m"


def _detect(base_url: str, slot: int, image_path: pathlib.Path) -> dict:
    """POST /detect with a pill image and return the parsed JSON response."""
    with open(image_path, "rb") as f:
        data = f.read()
    resp = requests.post(
        f"{base_url}/detect",
        files={"image": ("pill.jpg", io.BytesIO(data), "image/jpeg")},
        data={"slot": str(slot)},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _get_status(base_url: str) -> dict:
    """GET /status to check which profiles are locked."""
    try:
        return requests.get(f"{base_url}/status", timeout=5).json()
    except Exception:
        return {}


def _make_synthetic_pill(width: int = 400, height: int = 400,
                          pill_colour=(210, 190, 150)) -> bytes:
    """
    Create a minimal JPEG: beige pill ellipse on a white background.
    Works with the Otsu segmenter (dark pill on bright background).
    Requires Pillow.
    """
    try:
        from PIL import Image as PILImage, ImageDraw
    except ImportError:
        print("[warmup] Pillow not installed — pip install Pillow")
        sys.exit(1)

    img = PILImage.new("RGB", (width, height), (240, 240, 240))
    draw = ImageDraw.Draw(img)
    cx, cy = width // 2, height // 2
    rx, ry = int(width * 0.30), int(height * 0.22)
    draw.ellipse([(cx - rx, cy - ry), (cx + rx, cy + ry)], fill=pill_colour)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Main warm-up logic
# ─────────────────────────────────────────────────────────────────────────────

def warmup(base_url: str, pills_dir: pathlib.Path,
           target_slots: list[int] | None, min_matches: int,
           delay_s: float):
    """
    Iterate over pill images in pills_dir and call /detect until each
    slot's profile is locked (auto_registered == True) or we run out of images.
    """
    # Fetch initial server status to find active slots
    status = _get_status(base_url)
    slots_info = status.get("slots", {})

    if not slots_info:
        print("[warmup] WARNING: No slots returned from /status — "
              "send the prescription first.\n"
              "         Continuing anyway with whatever is in pills_dir …\n")

    # Resolve which slots to warm up
    if target_slots:
        slot_list = target_slots
    else:
        slot_list = sorted(int(s) for s in slots_info.keys()) if slots_info else []
        if not slot_list:
            # Fall back to sub-directories in pills_dir
            slot_list = sorted(
                int(p.name) for p in pills_dir.iterdir()
                if p.is_dir() and p.name.isdigit()
            )

    if not slot_list:
        print("[warmup] No slots to warm up.  "
              "Run --generate first or send a prescription from the app.")
        return

    print(f"[warmup] Warming up {len(slot_list)} slot(s): {slot_list}")
    print(f"         Server: {base_url}")
    print(f"         Min matches before stopping: {min_matches}\n")

    overall_ok = True
    for slot in slot_list:
        slot_dir = pills_dir / str(slot)
        if not slot_dir.exists():
            print(f"  Slot {slot}: no directory {slot_dir} — skipping")
            continue

        images = sorted(
            p for p in slot_dir.iterdir()
            if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        )
        if not images:
            print(f"  Slot {slot}: directory empty — skipping")
            continue

        med_name = slots_info.get(str(slot), {}).get("medicationName", f"Slot {slot}")
        print(f"  Slot {slot}  [{med_name}]  ({len(images)} image(s) available)")

        match_count   = 0
        locked        = False

        for i, img_path in enumerate(images):
            try:
                result = _detect(base_url, slot, img_path)
            except Exception as e:
                print(f"    [{i+1}/{len(images)}] ERROR: {e}")
                continue

            det     = result.get("result", "ERROR").upper()
            conf    = result.get("confidence", 0.0)
            acc_n   = result.get("accumulator_n", 0)
            auto_reg = result.get("auto_registered", False)
            col     = _colour_for(det)

            status_str = (
                f"    [{i+1:>2}/{len(images)}]  "
                f"{col}{det:<8}{_reset()}"
                f"  conf={conf:.3f}"
                f"  acc={acc_n}/{min_matches}"
            )
            if auto_reg:
                status_str += "  \033[92m✓ PROFILE LOCKED\033[0m"
                locked = True

            print(status_str)

            if det == "MATCH":
                match_count += 1

            if auto_reg or match_count >= min_matches:
                locked = True
                break

            if delay_s > 0:
                time.sleep(delay_s)

        if locked:
            print(f"  ✅  Slot {slot} profile LOCKED after {match_count} match(es)\n")
        else:
            print(f"  ⚠️   Slot {slot}: {match_count} match(es) — "
                  f"profile NOT locked (need {min_matches} images)\n")
            overall_ok = False

    if overall_ok:
        print("🎉  All profiles locked — dispenser is ready for the demo!")
    else:
        print("⚠️   Some profiles not locked.  "
              "Add more images under demo_pills/<slot>/ and re-run.")


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic image generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_synthetic(pills_dir: pathlib.Path, slots: list[int], count: int):
    """Write `count` synthetic pill JPEGs into demo_pills/<slot>/."""
    import random
    PILL_COLOURS = [
        (210, 190, 150),  # beige / generic
        (255, 235, 170),  # yellow
        (200, 170, 210),  # lavender
        (170, 205, 230),  # light blue
        (230, 175, 175),  # light pink
    ]
    print(f"[warmup] Generating {count} synthetic images for slots {slots}")
    for slot in slots:
        slot_dir = pills_dir / str(slot)
        slot_dir.mkdir(parents=True, exist_ok=True)
        colour = PILL_COLOURS[slot % len(PILL_COLOURS)]
        for i in range(1, count + 1):
            # Slightly vary colour per image for realism
            jitter = lambda v: max(0, min(255, v + random.randint(-10, 10)))
            c = tuple(jitter(x) for x in colour)
            data = _make_synthetic_pill(pill_colour=c)
            out  = slot_dir / f"synthetic_{i:03d}.jpg"
            out.write_bytes(data)
        print(f"  Slot {slot}: {count} images written to {slot_dir}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Warm up pill detection profiles before a demo.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--url",       default="http://localhost:5000",
                    help="Base URL of demo_server.py (default: http://localhost:5000)")
    ap.add_argument("--pills-dir", default=str(pathlib.Path(__file__).parent / "demo_pills"),
                    help="Directory containing per-slot pill images "
                         "(default: detection/demo_pills/)")
    ap.add_argument("--slot",      type=int, default=None,
                    help="Warm up a single slot only")
    ap.add_argument("--slots",     default=None,
                    help="Comma-separated list of slots to warm up, e.g. 1,2,3")
    ap.add_argument("--min-matches", type=int, default=3,
                    help="Stop per-slot after this many MATCHes (default: 3)")
    ap.add_argument("--delay",     type=float, default=0.3,
                    help="Seconds to wait between requests (default: 0.3)")
    ap.add_argument("--generate",  action="store_true",
                    help="Generate synthetic pill images (use before real photo session)")
    ap.add_argument("--generate-count", type=int, default=5,
                    help="Number of synthetic images per slot (default: 5)")
    args = ap.parse_args()

    pills_dir = pathlib.Path(args.pills_dir)

    # Resolve target slots
    target_slots: list[int] | None = None
    if args.slot:
        target_slots = [args.slot]
    elif args.slots:
        target_slots = [int(s.strip()) for s in args.slots.split(",") if s.strip()]

    if args.generate:
        if not target_slots:
            # Default to slots 1–5 for synthetic generation
            target_slots = list(range(1, 6))
        generate_synthetic(pills_dir, target_slots, args.generate_count)
        print("[warmup] Synthetic images created.  "
              "Re-run without --generate to start warm-up.\n")
        return

    warmup(
        base_url=args.url.rstrip("/"),
        pills_dir=pills_dir,
        target_slots=target_slots,
        min_matches=args.min_matches,
        delay_s=args.delay,
    )


if __name__ == "__main__":
    main()
