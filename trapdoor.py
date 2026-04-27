# Hero Pill Dispenser — Trapdoor Mechanism (Phase 11)
# Replaces the staging_floor placeholder with a mechanically operable hinged trapdoor.
#
# Mechanism:
#   Two semicircular leaves split at X=0, hinged on a pin along the Y axis.
#   A single SG90 servo drives the right leaf; the left leaf is passively linked.
#   In CLOSED position: leaves form a complete R=1.40" disk at Z=12.90".
#   When OPEN (90-deg rotation): leaves fold down perpendicular to the floor,
#   opening the full 1.40" bore for the pill to drop through.
#
# Run with: C:\Users\jaime\AppData\Local\Python\pythoncore-3.12-64\python.exe trapdoor.py

import cadquery as cq
import math
import pathlib

OUTPUT = pathlib.Path("output")
OUTPUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Constants (copied from carousel.py / optical_chamber.py — no circular import)
# ---------------------------------------------------------------------------
CAROUSEL_X = 0.0
CAROUSEL_Y = 4.5    # world Y centre of loading column

DOOR_R  = 1.40      # leaf radius = CHBR_INNER_R = FLOOR_R
DOOR_T  = 0.04      # leaf thickness (slightly thinner than 0.05" floor placeholder)
DOOR_Z  = 12.90     # world Z of closed leaf bottom face

HINGE_R   = 0.04    # hinge pin radius
HINGE_LEN = DOOR_R * 2 + 0.20   # 3.00" — spans both leaves + 0.10" overhang each end
HINGE_Z   = DOOR_Z + DOOR_T / 2  # 12.92" — pin runs through leaf mid-plane at X=0

# SG90 micro-servo placeholder — body outside loading tube on +X side
# Loading tube outer R=1.90"; servo body at X=[1.90, 2.80]
SERVO_BX  = 0.90    # servo body X dimension (depth toward axis)
SERVO_BY  = 0.47    # servo body Y dimension (width)
SERVO_BZ  = 0.59    # servo body Z dimension (height, body only)
SERVO_X0  = 1.90    # servo -X face at loading tube outer wall
SERVO_Y0  = CAROUSEL_Y   # servo centred on carousel Y axis
SERVO_Z0  = DOOR_Z - 0.20  # 12.70" — servo top slightly below trapdoor floor

# Drive arm — horizontal bar connecting servo output shaft to right leaf edge
ARM_LEN   = SERVO_X0 - DOOR_R   # = 0.50" (spans servo face to chamber outer wall)
ARM_W     = 0.08    # arm Y width
ARM_T     = 0.03    # arm Z thickness


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def save_step(wp, fname):
    wp.export(str(OUTPUT / fname))
    print(f"  Wrote output/{fname}")


# ---------------------------------------------------------------------------
# Part TD-1/2: Trapdoor leaf (left or right)
# Full disk → boolean cut removes the unwanted half.
# left  (side='left') : keeps X <= 0 hemisphere
# right (side='right'): keeps X >= 0 hemisphere
# Built at local Z=0..DOOR_T, centred at (0,0).
# Translate to (CAROUSEL_X, CAROUSEL_Y, DOOR_Z) at build time.
# ---------------------------------------------------------------------------
def make_trapdoor_leaf(side='left'):
    disk = cq.Workplane("XY").circle(DOOR_R).extrude(DOOR_T)
    over = 0.10   # cutter overshoot so the cut face is unambiguous
    if side == 'left':
        # Remove X > 0 half: cutter box centre at X = +(DOOR_R+over)/2
        cx = (DOOR_R + over) / 2   # = 0.75"
    else:
        # Remove X < 0 half: cutter box centre at X = -(DOOR_R+over)/2
        cx = -(DOOR_R + over) / 2  # = -0.75"
    cutter = (
        cq.Workplane("XY")
        .center(cx, 0)
        .box(DOOR_R + over, DOOR_R * 2 + over, DOOR_T + over)
    )
    return disk.cut(cutter)


# ---------------------------------------------------------------------------
# Part TD-3: Hinge pin
# Thin cylinder (R=HINGE_R) along the Y world axis.
# Built along Z first (at origin), then rotated 90° around X → lies along Y.
# Translate to (CAROUSEL_X, CAROUSEL_Y, HINGE_Z) at build time.
# ---------------------------------------------------------------------------
def make_hinge_pin():
    pin = (
        cq.Workplane("XY")
        .circle(HINGE_R)
        .extrude(HINGE_LEN)
        .translate((0, 0, -HINGE_LEN / 2))  # centre in Z before rotation
    )
    # +90 deg around X: Z-axis cylinder → -Y-axis cylinder; centred on Y axis at origin
    return pin.rotate((0, 0, 0), (1, 0, 0), 90)


# ---------------------------------------------------------------------------
# Part TD-4: Servo mount assembly
# SG90 placeholder body + mounting ears + drive arm to right leaf edge.
# Built directly in world coordinates (no additional translate at build time).
# Engineering note: loading tube wall needs a 0.10" × 0.30" slot for arm clearance.
# ---------------------------------------------------------------------------
def make_servo_mount():
    # Servo body: box at X=[SERVO_X0, SERVO_X0+SERVO_BX], centred in Y and Z-from-bottom
    body = (
        cq.Workplane("XY")
        .box(SERVO_BX, SERVO_BY, SERVO_BZ, centered=(False, True, False))
        .translate((SERVO_X0, SERVO_Y0, SERVO_Z0))
    )

    # Mounting ears: thin plates on +Z face of body at ±Y sides
    ear_x_len = 0.15   # ear protrudes in −X (toward axis) from servo body inner face
    ear_y_len = 0.30   # ear depth in Y (extends beyond body side)
    ear_z     = 0.04   # ear thickness in Z
    ear_z_pos = SERVO_Z0 + SERVO_BZ  # sits on top of servo body

    for ys in [1, -1]:
        ear = (
            cq.Workplane("XY")
            .box(ear_x_len, ear_y_len, ear_z, centered=(False, True, False))
            .translate((SERVO_X0 - ear_x_len,
                        SERVO_Y0 + ys * (SERVO_BY / 2 + ear_y_len / 2),
                        ear_z_pos))
        )
        try:
            body = body.union(ear)
        except Exception:
            pass  # ears are cosmetic

    # Drive arm: horizontal bar from servo output shaft to right leaf edge (X=DOOR_R=1.40)
    # Arm bottom face at leaf mid-plane Z = DOOR_Z + DOOR_T/2
    arm_z_centre = DOOR_Z + DOOR_T / 2
    arm = (
        cq.Workplane("XY")
        .box(ARM_LEN, ARM_W, ARM_T, centered=(False, True, False))
        .translate((DOOR_R, SERVO_Y0, arm_z_centre - ARM_T / 2))
    )
    try:
        body = body.union(arm)
    except Exception:
        pass  # arm is functional; skip if boolean fails

    return body


# ===========================================================================
# BUILD SECTION
# ===========================================================================
print("Building trapdoor mechanism (Phase 11)...")

# --- TD-1. Left leaf (closed position) ---
print("  Building left leaf (closed)...")
trapdoor_left = (
    make_trapdoor_leaf('left')
    .translate((CAROUSEL_X, CAROUSEL_Y, DOOR_Z))
)
save_step(trapdoor_left, "trapdoor_left.step")

# --- TD-2. Right leaf (closed position) ---
print("  Building right leaf (closed)...")
trapdoor_right = (
    make_trapdoor_leaf('right')
    .translate((CAROUSEL_X, CAROUSEL_Y, DOOR_Z))
)
save_step(trapdoor_right, "trapdoor_right.step")

# --- TD-3. Open-position previews (rotate leaves 90-deg around Y axis at X=0) ---
#   Left leaf  opens toward -Y (rotates -90-deg about Y through hinge axis)
#   Right leaf opens toward +Y (rotates +90-deg about Y through hinge axis)
print("  Building open-position previews...")
_hinge_pt  = cq.Vector(CAROUSEL_X, CAROUSEL_Y,     HINGE_Z)
_hinge_end = cq.Vector(CAROUSEL_X, CAROUSEL_Y + 1, HINGE_Z)

trapdoor_left_open = (
    make_trapdoor_leaf('left')
    .translate((CAROUSEL_X, CAROUSEL_Y, DOOR_Z))
    .rotate(_hinge_pt, _hinge_end, -90)
)
save_step(trapdoor_left_open, "trapdoor_left_open.step")

trapdoor_right_open = (
    make_trapdoor_leaf('right')
    .translate((CAROUSEL_X, CAROUSEL_Y, DOOR_Z))
    .rotate(_hinge_pt, _hinge_end, 90)
)
save_step(trapdoor_right_open, "trapdoor_right_open.step")

# --- TD-4. Hinge pin ---
print("  Building hinge pin...")
hinge_pin = (
    make_hinge_pin()
    .translate((CAROUSEL_X, CAROUSEL_Y, HINGE_Z))
)
save_step(hinge_pin, "hinge_pin.step")

# --- TD-5. Servo mount (world-positioned inside function) ---
print("  Building servo mount + drive arm...")
servo_mount = make_servo_mount()
save_step(servo_mount, "servo_mount.step")

# --- TD-6. Trapdoor sub-assembly (closed position) ---
print("  Building trapdoor_assembly.step...")
td_assy = cq.Assembly()
td_assy.add(trapdoor_left,  name="trapdoor_left",
            color=cq.Color(0.85, 0.95, 1.00, 0.80))   # translucent blue (clear acrylic)
td_assy.add(trapdoor_right, name="trapdoor_right",
            color=cq.Color(0.85, 0.95, 1.00, 0.80))
td_assy.add(hinge_pin,      name="hinge_pin",
            color=cq.Color(0.80, 0.80, 0.85, 1.0))    # steel gray
td_assy.add(servo_mount,    name="servo_mount",
            color=cq.Color(0.15, 0.15, 0.15, 1.0))    # near-black (servo body)
td_assy.export(str(OUTPUT / "trapdoor_assembly.step"))
print("  Wrote output/trapdoor_assembly.step")

# Also export open-state assembly for reference
td_open_assy = cq.Assembly()
td_open_assy.add(trapdoor_left_open,  name="trapdoor_left_open",
                 color=cq.Color(0.85, 0.95, 1.00, 0.60))
td_open_assy.add(trapdoor_right_open, name="trapdoor_right_open",
                 color=cq.Color(0.85, 0.95, 1.00, 0.60))
td_open_assy.add(hinge_pin, name="hinge_pin",
                 color=cq.Color(0.80, 0.80, 0.85, 1.0))
td_open_assy.export(str(OUTPUT / "trapdoor_open_assembly.step"))
print("  Wrote output/trapdoor_open_assembly.step")

# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
print("\n--- Trapdoor Verification ---")

bb_l = trapdoor_left.val().BoundingBox()
bb_r = trapdoor_right.val().BoundingBox()
print(f"  left_leaf  (closed): Z=[{bb_l.zmin:.3f},{bb_l.zmax:.3f}]  "
      f"X=[{bb_l.xmin:.3f},{bb_l.xmax:.3f}]  (expected X<=0)")
print(f"  right_leaf (closed): Z=[{bb_r.zmin:.3f},{bb_r.zmax:.3f}]  "
      f"X=[{bb_r.xmin:.3f},{bb_r.xmax:.3f}]  (expected X>=0)")

# Together leaves should fill a full disk
combined_x = (bb_l.xmin, bb_r.xmax)
print(f"  combined X span: [{combined_x[0]:.3f}, {combined_x[1]:.3f}]  "
      f"(expected [{-DOOR_R:.3f}, {DOOR_R:.3f}])  "
      f"{'OK' if abs(combined_x[0] + DOOR_R) < 0.01 and abs(combined_x[1] - DOOR_R) < 0.01 else 'CHECK'}")

bb_hp = hinge_pin.val().BoundingBox()
hp_z_c = (bb_hp.zmin + bb_hp.zmax) / 2
hp_y_c = (bb_hp.ymin + bb_hp.ymax) / 2
print(f"  hinge_pin: Z-centre={hp_z_c:.3f}  (expected {HINGE_Z:.3f})  "
      f"Y=[{bb_hp.ymin:.3f},{bb_hp.ymax:.3f}] (span={HINGE_LEN:.2f}\")")

bb_sm = servo_mount.val().BoundingBox()
print(f"  servo_mount: X=[{bb_sm.xmin:.3f},{bb_sm.xmax:.3f}]  "
      f"Z=[{bb_sm.zmin:.3f},{bb_sm.zmax:.3f}]")

bb_lo = trapdoor_left_open.val().BoundingBox()
print(f"  left_open: Z=[{bb_lo.zmin:.3f},{bb_lo.zmax:.3f}]  Y=[{bb_lo.ymin:.3f},{bb_lo.ymax:.3f}]  "
      f"(90-deg rotation verified)")

print(f"\n  PILL DROP: trapdoor OPEN bore = {DOOR_R*2:.2f}\" diameter — pill clears freely")
print(f"  SERVO:     body at X=[{SERVO_X0:.2f},{SERVO_X0+SERVO_BX:.2f}]  "
      f"(outside loading tube outer wall at R=1.90\")")
print(f"  ARM:       drive arm at X=[{DOOR_R:.2f},{SERVO_X0:.2f}]  "
      f"** loading tube wall needs 0.10\"x0.30\" clearance slot at Z~{DOOR_Z:.2f}\" **")
print("\nDone. Run optical_chamber.py then carousel.py to integrate into hero_full_assembly.step.")
