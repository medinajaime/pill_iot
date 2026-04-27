# Hero Pill Dispenser — Bill of Materials Generator
# Reads every production STEP file in output/, computes bounding-box dimensions
# and estimated volume, assigns material + process suggestions, and writes:
#   output/bom.csv   — machine-readable
#   output/bom.txt   — human-readable report
#
# Run with: C:\Users\jaime\AppData\Local\Python\pythoncore-3.12-64\python.exe bom.py
# Run AFTER all build scripts have produced their STEP files.

import cadquery as cq
import pathlib
import csv
import math

OUTPUT = pathlib.Path("output")

# ---------------------------------------------------------------------------
# Parts catalogue
# Assembly files, test files, open-position previews, and deprecated parts
# are excluded — only production parts that appear in hero_full_assembly.step.
# ---------------------------------------------------------------------------

# (filename_stem, description, qty, material, process, color_suggestion)
CATALOGUE = [
    # Enclosure & cosmetic shell
    ("enclosure",        "D-profile main enclosure shell (9\"W x 9\"D x 15\"H)",     1, "PETG",         "FDM — 3-section split", "Light blue-gray"),
    ("button",           "Centre multi-directional button cap",                        1, "PETG",         "FDM",                   "Black"),
    ("pill_cup",         "Dispensing cup with solid floor and front grab tab",          1, "PETG",         "FDM",                   "White"),
    ("drop_cone",        "Anti-bounce funnel between spout and pill cup",              1, "TPU 95A",      "FDM -- flexible nozzle","Translucent white"),
    ("hatch_final",      "Top loading hatch lid with hinge knuckles + snap latch",    1, "PETG",         "FDM",                   "Light blue-gray"),
    ("usbc_port",        "USB-C port bezel insert",                                   1, "PETG",         "FDM",                   "Light steel"),
    ("speaker_grille",   "Speaker grille — 12-hole ring pattern",                     1, "PETG",         "FDM",                   "Dark gray"),
    ("display_panel",    "Touchscreen display placeholder panel",                      1, "Off-the-shelf","3.5\" TFT LCD module",  "Black"),
    ("led_ring",         "Front-face status LED ring (outer R=1.2\")",               1, "Off-the-shelf","NeoPixel ring",          "N/A"),

    # Carousel assembly
    ("cartridge",        "Pill storage cartridge (×10 installed)",                   10, "PETG",         "FDM",                   "Translucent amber"),
    ("carousel_base",    "Carousel base plate (stationary, 0.10\" thick)",            1, "PETG",         "FDM",                   "Dark steel"),
    ("hub_lock",         "Central hub lock ring — couples D-shaft to carousel",       1, "PETG",         "FDM",                   "Gray"),

    # Drive train
    ("motor_assembly",   "NEMA 17 stepper motor + D-shaft placeholder",               1, "Off-the-shelf","NEMA 17 42x42x47mm",    "Black"),
    ("motor_mount",      "NEMA 17 motor mount plate (3\"x3\"x0.10\")",               1, "PETG",         "FDM",                   "Dark steel"),
    ("dispense_gate",    "Upper inlet gate for one-tablet metering chamber",          1, "PETG",         "FDM",                   "Orange"),
    ("dispense_gate_servo_mount", "SG90 mount for upper inlet gate",                  1, "PETG",         "FDM",                   "Black"),
    ("dispense_release_gate", "Lower release gate below one-tablet metering chamber", 1, "PETG",         "FDM",                   "Amber"),
    ("dispense_release_gate_servo_mount", "SG90 mount for lower release gate",        1, "PETG",         "FDM",                   "Black"),
    ("dispense_sweep_pusher", "Low front-entry TPU last-pill pusher",                1, "TPU 95A",      "FDM -- flexible nozzle","Blue"),
    ("dispense_sweep_containment_band", "Stationary OD shield backing all cartridge sweep slots", 1, "PETG", "FDM",              "Light gray"),
    ("dispense_sweep_port_seal", "Flexible TPU wiper sealing the single pusher service window", 1, "TPU 95A", "FDM -- flexible nozzle","Black"),
    ("dispense_sweep_rail", "Low front linear guide rail for sweep pusher",           1, "PETG",         "FDM",                   "Dark gray"),
    ("dispense_sweep_servo_mount", "Low SG90/rack mount for front-entry pusher",      1, "PETG",         "FDM",                   "Black"),

    # Pill handling — mechanical
    ("pill_guide",       "Guide tube / loading chimney (R=3.5\", H=2.1\")",          1, "PETG",         "FDM — translucent",     "Translucent green"),
    ("pill_guide_ring",  "Top seal ring — solid ceiling with single loading port",    1, "PETG",         "FDM",                   "Light gray"),
    ("pill_chute",       "One-tablet metering chamber / sealed dispense chute",       1, "PETG",         "FDM",                   "Light gray"),
    ("agitator_wheel",   "Singulator paddle — stationary, sweeps pills to drop hole", 1, "PETG",         "FDM",                   "Red"),
    ("pill_cup",         "Pill catch cup in alcove",                                  1, "PETG",         "FDM",                   "White"),
    ("load_cell",        "Circular load-cell tray under removable pill cup",           1, "Off-the-shelf","HX711 + 1kg load cell", "Gold"),

    # Loading column
    ("loading_tube",     "Vertical loading tube (inner R=1.80\", H=3.9\")",          1, "PETG",         "FDM — translucent",     "Translucent green"),
    ("routing_chute",    "Static routing chute — lofted funnel, trapdoor to slot",    1, "PETG",         "FDM",                   "Translucent amber"),

    # Trapdoor mechanism
    ("trapdoor_left",    "Trapdoor left leaf (semicircle, X<=0)",                     1, "Matte White PETG","FDM or laser-cut",   "Matte White"),
    ("trapdoor_right",   "Trapdoor right leaf (semicircle, X>=0)",                    1, "Matte White PETG","FDM or laser-cut",   "Matte White"),
    ("hinge_pin",        "Trapdoor hinge pin (Y-axis, R=0.04\", L=3.00\")",          1, "Steel",        "Off-the-shelf rod",     "Silver"),
    ("servo_mount",      "SG90 servo body + ears + drive arm assembly",               1, "Off-the-shelf","SG90 micro servo",      "Dark gray"),

    # Optical detection chamber
    ("chamber_shell",    "Optical detection chamber cylinder (R=1.50\", H=2.00\")",  1, "Clear PETG",   "FDM — translucent",     "Translucent green"),
    ("camera_mount",     "Camera mount bridge — 45-deg downward in annular gap",      1, "PETG",         "FDM",                   "Black"),
    ("led_ring_oc",      "Optical chamber LED ring (torus, R=1.30\", at ceiling)",   1, "Off-the-shelf","LED ring / bare LEDs",  "Warm yellow"),
    ("chamber_ceiling",  "Frosted PETG ceiling plate — LED mount + light baffle + diffuser", 1, "Frosted PETG", "FDM — translucent", "Translucent white"),

    # Electronics
    ("vertical_pcb",     "Raspberry Pi 4 PCB — vertical back-wall mount",            1, "Off-the-shelf","Raspberry Pi 4 Model B","Green PCB"),
    ("vib_motor",        "Vibration motor (agitation assist, R=0.30\")",             1, "Off-the-shelf","ERM coin vibration motor","Gray"),
    ("camera",           "Camera module — main imaging sensor",                       1, "Off-the-shelf","Pi Camera v2 / OV5647", "Black"),

    # Phase 16 — Index wheel / home-position sensing
    ("rear_shaft",       "Rear D-shaft extension below motor body (R=0.20\", L=0.50\")", 1, "Steel",      "Off-the-shelf rod",     "Silver"),
    ("index_disk",       "Slotted encoder disk — 1 notch, R=0.60\", T=0.05\"",       1, "PETG",         "FDM",                   "Black"),
    ("sensor_mount",     "TCST2103 fork sensor L-bracket mount",                      1, "PETG",         "FDM",                   "Black"),
    ("optical_interrupter", "TCST2103 fork optical interrupter (home pulse sensor)",  1, "Off-the-shelf","TCST2103",              "Black"),
]

# Deduplicate by stem (pill_cup appears twice above — keep first)
_seen = set()
CATALOGUE_DEDUPED = []
for row in CATALOGUE:
    if row[0] not in _seen:
        _seen.add(row[0])
        CATALOGUE_DEDUPED.append(row)
CATALOGUE = [row for row in CATALOGUE_DEDUPED if row[0] != "agitator_wheel"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def inches_to_mm(v):
    return round(v * 25.4, 2)

def bbox_volume_in3(bb):
    """Approximate bounding-box volume in cubic inches."""
    dx = bb.xmax - bb.xmin
    dy = bb.ymax - bb.ymin
    dz = bb.zmax - bb.zmin
    return dx * dy * dz

def load_part(stem):
    path = OUTPUT / f"{stem}.step"
    if not path.exists():
        return None
    try:
        wp = cq.importers.importStep(str(path))
        return wp
    except Exception as e:
        print(f"  WARNING: could not load {stem}.step — {e}")
        return None

# ---------------------------------------------------------------------------
# Build BOM rows
# ---------------------------------------------------------------------------

rows = []
print("Reading STEP files and computing bounding boxes...")

for (stem, desc, qty, material, process, color) in CATALOGUE:
    wp = load_part(stem)
    if wp is None:
        dims_in = ("?", "?", "?")
        dims_mm = ("?", "?", "?")
        vol_in3 = "?"
        vol_cm3 = "?"
        note = "STEP missing"
    else:
        bb = wp.val().BoundingBox()
        dx = round(bb.xmax - bb.xmin, 3)
        dy = round(bb.ymax - bb.ymin, 3)
        dz = round(bb.zmax - bb.zmin, 3)
        dims_in = (dx, dy, dz)
        dims_mm = (inches_to_mm(dx), inches_to_mm(dy), inches_to_mm(dz))
        vol_box = bbox_volume_in3(bb)
        vol_in3 = round(vol_box, 4)
        vol_cm3 = round(vol_box * 16.387, 3)
        note = ""
        print(f"  {stem:25s}  {dx:.3f}\" x {dy:.3f}\" x {dz:.3f}\"  vol~{vol_in3:.3f} in3")

    rows.append({
        "Part":        stem,
        "Description": desc,
        "Qty":         qty,
        "W_in":        dims_in[0],
        "D_in":        dims_in[1],
        "H_in":        dims_in[2],
        "W_mm":        dims_mm[0],
        "D_mm":        dims_mm[1],
        "H_mm":        dims_mm[2],
        "Vol_in3":     vol_in3,
        "Vol_cm3":     vol_cm3,
        "Material":    material,
        "Process":     process,
        "Color":       color,
        "Note":        note,
    })

# ---------------------------------------------------------------------------
# Write CSV
# ---------------------------------------------------------------------------
csv_path = OUTPUT / "bom.csv"
fieldnames = ["Part","Description","Qty",
              "W_in","D_in","H_in","W_mm","D_mm","H_mm",
              "Vol_in3","Vol_cm3","Material","Process","Color","Note"]
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
print(f"\nWrote output/bom.csv  ({len(rows)} parts)")

# ---------------------------------------------------------------------------
# Write human-readable report
# ---------------------------------------------------------------------------
txt_path = OUTPUT / "bom.txt"
with open(txt_path, "w", encoding="utf-8") as f:
    f.write("=" * 100 + "\n")
    f.write("HERO SMART PILL DISPENSER — BILL OF MATERIALS\n")
    f.write("All dimensions in inches (mm in parentheses). Vol = bounding-box volume estimate.\n")
    f.write("=" * 100 + "\n\n")

    # Group by material category
    groups = {
        "FDM Printed Parts (PETG)": [],
        "FDM Printed Parts (Clear/Translucent)": [],
        "Off-the-Shelf Components": [],
        "Hardware": [],
        "Other": [],
    }
    for r in rows:
        mat = r["Material"]
        if "Off-the-shelf" in mat:
            groups["Off-the-Shelf Components"].append(r)
        elif "Steel" in mat or "rod" in mat.lower():
            groups["Hardware"].append(r)
        elif "clear" in mat.lower() or "translucent" in mat.lower() or "acrylic" in mat.lower():
            groups["FDM Printed Parts (Clear/Translucent)"].append(r)
        elif "PETG" in mat or "FDM" in mat:
            groups["FDM Printed Parts (PETG)"].append(r)
        else:
            groups["Other"].append(r)

    total_fdm_vol = 0.0
    total_clear_vol = 0.0

    for group_name, group_rows in groups.items():
        if not group_rows:
            continue
        f.write(f"--- {group_name} ---\n")
        f.write(f"{'#':<3} {'Part':<22} {'Qty':<4} {'W x D x H (in)':<28} {'W x D x H (mm)':<30} {'Vol (cm3)':<12} Description\n")
        f.write("-" * 145 + "\n")
        n = 1
        for r in group_rows:
            if r["W_in"] == "?":
                dim_in = "? x ? x ?"
                dim_mm = "? x ? x ?"
                vol_str = "?"
            else:
                dim_in = f"{r['W_in']} x {r['D_in']} x {r['H_in']}"
                dim_mm = f"{r['W_mm']} x {r['D_mm']} x {r['H_mm']}"
                vol_str = str(r["Vol_cm3"])
                if isinstance(r["Vol_cm3"], float):
                    if "PETG" in r["Material"] or "FDM" in r["Material"]:
                        total_fdm_vol += r["Vol_cm3"] * r["Qty"]
                    if "clear" in r["Material"].lower() or "acrylic" in r["Material"].lower():
                        total_clear_vol += r["Vol_cm3"] * r["Qty"]
            note = f"  [{r['Note']}]" if r["Note"] else ""
            f.write(f"{n:<3} {r['Part']:<22} {r['Qty']:<4} {dim_in:<28} {dim_mm:<30} {vol_str:<12} {r['Description']}{note}\n")
            n += 1
        f.write("\n")

    f.write("=" * 100 + "\n")
    f.write("MATERIAL SUMMARY\n")
    f.write(f"  PETG printed volume (bounding-box upper bound): ~{total_fdm_vol:.1f} cm3\n")
    f.write(f"  At 20% infill, estimated filament volume:       ~{total_fdm_vol * 0.20:.1f} cm3\n")
    f.write(f"  At 1.24 g/cm3 (PETG density):                  ~{total_fdm_vol * 0.20 * 1.24:.0f} g\n")
    f.write(f"  Clear acrylic/PETG printed volume:              ~{total_clear_vol:.1f} cm3\n")
    f.write("\n")
    f.write("FDM PRINT SPLIT (enclosure only):\n")
    f.write("  The 15\" tall enclosure is sectioned into 3 horizontal pieces:\n")
    f.write("    Bottom  Z=0.0\" to Z=5.0\"  (127mm) — alcove, spout, load cell\n")
    f.write("    Middle  Z=5.0\" to Z=10.0\" (127mm) — carousel, motor, guide tube\n")
    f.write("    Top     Z=10.0\" to Z=15.0\" (127mm) — loading column, display, hatch\n")
    f.write("  Alignment: 4 x 5mm pin-and-socket joints per split plane\n")
    f.write("  Fastening: M3 brass heat inserts + M3x8 screws at 4 corners per joint\n")
    f.write("\n")
    f.write("PURCHASING NOTES:\n")
    f.write("  - NEMA 17 stepper: e.g. 17HS4401 (40Ncm), ~$10\n")
    f.write("  - SG90 servo: standard 9g micro servo, ~$2\n")
    f.write("  - Load cell: 1kg bar type + HX711 ADC board, ~$5\n")
    f.write("  - Raspberry Pi 4: 2GB or 4GB, ~$35–55\n")
    f.write("  - Pi Camera v2: 8MP OV5647, ~$25\n")
    f.write("  - LED ring: NeoPixel 16-LED ring (front) + bare LEDs (optical chamber), ~$8\n")
    f.write("  - ERM vibration motor: 10mm coin type, ~$2\n")
    f.write("  - Hinge pin: 1mm steel rod cut to 76mm, ~$1\n")
    f.write("=" * 100 + "\n")

print(f"Wrote output/bom.txt")
print(f"\nSummary: {len(rows)} unique parts catalogued.")
print(f"Open output/bom.csv in Excel or output/bom.txt for the full report.")
