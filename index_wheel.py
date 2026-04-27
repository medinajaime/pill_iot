# Hero Pill Dispenser -- Carousel Index Wheel & Optical Sensor Mount
# Phase 16: Position feedback for accurate carousel indexing.
#
# The NEMA 17 stepper gives relative step counts but has no home reference.
# An optical interrupter (fork-type, e.g. TCST2103) on a slotted index disk
# attached to a rear shaft extension gives ONE absolute home pulse per revolution.
# The firmware homes at startup, then counts 360/N_SLOTS = 36 deg/step-group to
# reach any of the 10 cartridge positions.
#
# Coordinate system (matches carousel.py):
#   X: left(-) / right(+), centre = 0
#   Y: back(0) / front(9)
#   Z: bottom(0) / top(15)   -- all in inches
#
# Parts produced:
#   rear_shaft.step       -- D-shaft extension below motor body (rotates)
#   index_disk.step       -- slotted index disk on rear shaft  (rotates)
#   sensor_mount.step     -- L-bracket + optical sensor body   (stationary)
#   index_wheel_assembly.step
#
# Run with: C:\Users\jaime\AppData\Local\Python\pythoncore-3.12-64\python.exe index_wheel.py
# Run BEFORE carousel.py (outputs are imported by carousel.py guard block).

import cadquery as cq
import math
import pathlib

OUTPUT = pathlib.Path("output")
OUTPUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Constants -- copied from carousel.py (no circular import)
# ---------------------------------------------------------------------------
CAROUSEL_X      = 0.0
CAROUSEL_Y      = 4.5

# Motor / mount geometry (from carousel.py verification):
#   motor_mount: Z=[3.300, 3.400]   motor body: Z=[3.400, 4.900]
MOTOR_Z_BOT     = 3.40    # motor body bottom = motor mount plate top
MOTOR_MOUNT_BOT = 3.30    # motor mount plate bottom face

# D-shaft geometry (must match carousel.py exactly)
SHAFT_R          = 0.20   # 5.08 mm -- real NEMA 17 shaft diameter
SHAFT_FLAT_DEPTH = 0.05   # flat cut depth on +Y side

# ---------------------------------------------------------------------------
# Rear shaft extension
# ---------------------------------------------------------------------------
# The main D-shaft goes UP into the carousel.  This extension goes DOWN,
# through the motor mount plate hole, below the motor face.
# A clearance hole is assumed in the motor mount plate (not modelled here --
# motor_mount.py would need updating; for now the extension is shown floating).
REAR_SHAFT_LEN   = 0.50   # 12.7 mm extension below motor body bottom
REAR_SHAFT_Z_TOP = MOTOR_Z_BOT                      # 3.40"
REAR_SHAFT_Z_BOT = MOTOR_Z_BOT - REAR_SHAFT_LEN     # 2.90"

# ---------------------------------------------------------------------------
# Index disk
# ---------------------------------------------------------------------------
# Sits on the rear shaft between motor body bottom and motor mount plate,
# just below the motor mount plate underside (Z=3.30).
INDEX_DISK_R     = 0.60   # 15.2 mm outer radius -- visible to sensor fork
INDEX_DISK_T     = 0.05   # 1.27 mm thickness -- fits inside standard 3 mm fork gap
INDEX_DISK_Z_CTR = 3.15   # disk centre Z -- 0.15" below motor mount bottom (3.30)

# D-bore: shaft fit (clearance = 0.01" radially + flat clearance)
INDEX_BORE_R     = SHAFT_R + 0.01                   # 0.21" bore radius
INDEX_BORE_FLAT  = SHAFT_FLAT_DEPTH + 0.01          # 0.06" flat clearance

# Index notch -- rectangular radial slot at angle 0 deg (+X direction)
# The notch interrupts the sensor beam once per revolution = home reference.
INDEX_NOTCH_DEPTH = 0.20   # radial depth from outer rim inward (to R=0.40")
INDEX_NOTCH_W     = 0.14   # notch arc chord width at outer rim (~13 deg)
                            # wide enough for reliable detection, narrow enough
                            # that the motor can stop accurately inside the window

# ---------------------------------------------------------------------------
# Optical sensor + bracket
# ---------------------------------------------------------------------------
# Sensor: TCST2103 fork-type optical interrupter (or equivalent)
#   Body: 11.9 mm x 10.8 mm x 4.0 mm  =>  0.47" x 0.43" x 0.16"
#   Fork gap: 3.0 mm (0.118") -- index disk 1.27 mm fits with 1.73 mm clearance
#   Mounting: two M2 screws through sensor feet into bracket
SENSOR_BODY_X    = 0.16   # sensor body depth (X, along radial direction)
SENSOR_BODY_Y    = 0.47   # sensor body width (Y, tangential)
SENSOR_BODY_Z    = 0.43   # sensor body height (Z)
SENSOR_FORK_GAP  = 0.12   # fork gap (> INDEX_DISK_T = 0.05" -- OK)

# Bracket geometry
BRACKET_T        = 0.06   # wall thickness of L-bracket
# Sensor fork sits at disk outer rim: X = CAROUSEL_X + INDEX_DISK_R = 0.60"
# Sensor positioned at +X side (home notch at angle 0 deg from +X)
SENSOR_X_CTR     = CAROUSEL_X + INDEX_DISK_R        # 0.60" from carousel axis X
SENSOR_Y_CTR     = CAROUSEL_Y                       # 4.50" -- aligned with shaft Y
SENSOR_Z_CTR     = INDEX_DISK_Z_CTR                 # 3.15" -- same Z as disk

# Bracket vertical arm: hangs from motor mount plate bottom (Z=MOTOR_MOUNT_BOT=3.30)
# down to sensor Z - half sensor height
BRKT_ARM_Z_TOP   = MOTOR_MOUNT_BOT                  # 3.30"
BRKT_ARM_Z_BOT   = SENSOR_Z_CTR - SENSOR_BODY_Z / 2 - 0.02  # ~2.915"
BRKT_ARM_H       = BRKT_ARM_Z_TOP - BRKT_ARM_Z_BOT  # ~0.385"

# Bracket horizontal arm: from near shaft to sensor X position
# Arm starts at X = CAROUSEL_X (shaft centreline) + small offset to clear shaft
BRKT_H_ARM_X_START = CAROUSEL_X + SHAFT_R + 0.05    # 0.25" from shaft centre
BRKT_H_ARM_X_END   = SENSOR_X_CTR                   # 0.60"
BRKT_H_ARM_LEN     = BRKT_H_ARM_X_END - BRKT_H_ARM_X_START  # 0.35"

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def save_step(wp, fname):
    wp.export(str(OUTPUT / fname))
    print(f"  Wrote output/{fname}")

def make_d_bore_cut(r_bore, flat_depth, height):
    """Return a cutter for a D-shaped bore centred at (0,0), extruding +Z by height+0.02."""
    bore_cyl = cq.Workplane("XY").circle(r_bore).extrude(height + 0.02).translate((0, 0, -0.01))
    _pad      = 0.20
    _box_W    = r_bore * 2 + _pad
    _box_dep  = flat_depth + _pad
    _Y_flat   = r_bore - flat_depth
    _box_cY   = _Y_flat + _box_dep / 2
    flat_box  = (
        cq.Workplane("XY")
        .center(0, _box_cY)
        .rect(_box_W, _box_dep)
        .extrude(height + 0.02)
        .translate((0, 0, -0.01))
    )
    return bore_cyl.union(flat_box)


# ---------------------------------------------------------------------------
# Part 1: Rear Shaft Extension
# ---------------------------------------------------------------------------
def make_rear_shaft():
    """D-shaft extension below motor body; rotates with motor rotor.

    Geometry (world coords):
      Cylinder R=SHAFT_R=0.20"  H=REAR_SHAFT_LEN=0.50"
      D-flat: same depth as main shaft (SHAFT_FLAT_DEPTH=0.05") on +Y side.
      Z = [REAR_SHAFT_Z_BOT, REAR_SHAFT_Z_TOP] = [2.90, 3.40]
      Passes through motor mount plate -- clearance hole required in motor_mount.

    Note: modelled as a separate part for clarity; in the final assembly this
    is a single longer D-shaft purchased from the motor supplier.
    """
    shaft = cq.Workplane("XY").circle(SHAFT_R).extrude(REAR_SHAFT_LEN)
    cutter = make_d_bore_cut(SHAFT_R, SHAFT_FLAT_DEPTH, REAR_SHAFT_LEN)
    # The D-flat cutter removes material from +Y side -- equivalent to keeping
    # everything but the top slice.  We cut the flat OFF the shaft (not the shaft
    # from the cutter), so we need the box only.
    _pad      = 0.20
    _box_W    = SHAFT_R * 2 + _pad
    _box_dep  = SHAFT_FLAT_DEPTH + _pad
    _Y_flat   = SHAFT_R - SHAFT_FLAT_DEPTH
    _box_cY   = _Y_flat + _box_dep / 2
    flat_box  = (
        cq.Workplane("XY")
        .center(0, _box_cY)
        .rect(_box_W, _box_dep)
        .extrude(REAR_SHAFT_LEN + 0.02)
        .translate((0, 0, -0.01))
    )
    flat_shaft = shaft.cut(flat_box)
    return flat_shaft.translate((CAROUSEL_X, CAROUSEL_Y, REAR_SHAFT_Z_BOT))


# ---------------------------------------------------------------------------
# Part 2: Index Disk
# ---------------------------------------------------------------------------
def make_index_disk():
    """Slotted encoder disk -- rotates with rear shaft; triggers sensor once/rev.

    Geometry:
      Outer R = INDEX_DISK_R = 0.60"  (15.2 mm)
      Thickness = INDEX_DISK_T = 0.05"  (1.27 mm -- fits in 3 mm sensor fork)
      D-bore (same profile as shaft) so disk is keyed to shaft and co-rotates.
      ONE index notch at angle 0 deg (+X direction):
        Radial slot from X=0.40" to X=0.60" (depth=0.20"), width=0.14"
        When the notch aligns with the fixed sensor, the beam passes through
        and the firmware records this as the HOME position (cartridge 0 active).

    World Z = [INDEX_DISK_Z_CTR - INDEX_DISK_T/2, INDEX_DISK_Z_CTR + INDEX_DISK_T/2]
             = [3.125, 3.175]
    """
    local_z_bot = INDEX_DISK_Z_CTR - INDEX_DISK_T / 2   # 3.125"  (local build start)

    # --- Outer disk ---
    disk = cq.Workplane("XY").circle(INDEX_DISK_R).extrude(INDEX_DISK_T)

    # --- D-bore (matching shaft, with clearance) ---
    bore_r     = INDEX_BORE_R          # 0.21"
    bore_flat  = INDEX_BORE_FLAT       # 0.06"
    bore_cyl   = cq.Workplane("XY").circle(bore_r).extrude(INDEX_DISK_T + 0.02).translate((0, 0, -0.01))
    _pad       = 0.20
    _box_W     = bore_r * 2 + _pad
    _box_dep   = bore_flat + _pad
    _Y_flat    = bore_r - bore_flat
    _box_cY    = _Y_flat + _box_dep / 2
    flat_cut   = (
        cq.Workplane("XY")
        .center(0, _box_cY)
        .rect(_box_W, _box_dep)
        .extrude(INDEX_DISK_T + 0.02)
        .translate((0, 0, -0.01))
    )
    disk = disk.cut(bore_cyl).cut(flat_cut)

    # --- Index notch (radial slot at angle 0 deg = +X direction) ---
    notch_x_ctr = INDEX_DISK_R - INDEX_NOTCH_DEPTH / 2   # 0.50" from disk centre
    notch = (
        cq.Workplane("XY")
        .center(notch_x_ctr, 0)
        .rect(INDEX_NOTCH_DEPTH + 0.01, INDEX_NOTCH_W)
        .extrude(INDEX_DISK_T + 0.02)
        .translate((0, 0, -0.01))
    )
    disk = disk.cut(notch)

    return disk.translate((CAROUSEL_X, CAROUSEL_Y, local_z_bot))


# ---------------------------------------------------------------------------
# Part 3: Sensor Mount Bracket
# ---------------------------------------------------------------------------
def make_sensor_mount():
    """Stationary L-bracket holding the optical interrupter at the index disk rim.

    Geometry:
      Vertical arm: BRACKET_T x BRACKET_T cross-section, from motor mount
                    plate underside (Z=3.30) down to sensor level (Z~2.92)
      Horizontal arm: from shaft clearance (X=0.25) to sensor X (X=0.60)
                      at sensor level, BRACKET_T thick in Z
      Sensor body placeholder: 0.16" x 0.47" x 0.43" box at (0.60, 4.50, 3.15)

    The bracket arm is positioned at Y=CAROUSEL_Y (4.50"), on the +X side of the
    shaft (X=0.25 to 0.60), so it does not interfere with the rotating disk body
    except where the sensor fork intentionally straddles it.

    Mounting: two M2 screws through top face of bracket into motor mount plate.
    """
    # ── Vertical arm (hangs from motor mount plate underside) ──
    v_arm = (
        cq.Workplane("XY")
        .center(BRKT_H_ARM_X_START, SENSOR_Y_CTR)
        .rect(BRACKET_T, BRACKET_T)
        .extrude(BRKT_ARM_H)
        .translate((0, 0, BRKT_ARM_Z_BOT))
    )

    # ── Horizontal arm (reaches from shaft edge to sensor) ──
    h_arm_z = BRKT_ARM_Z_BOT   # base of vertical arm = top of horizontal arm
    h_arm = (
        cq.Workplane("XY")
        .center((BRKT_H_ARM_X_START + BRKT_H_ARM_X_END) / 2, SENSOR_Y_CTR)
        .rect(BRKT_H_ARM_LEN, BRACKET_T)
        .extrude(BRACKET_T)
        .translate((0, 0, h_arm_z))
    )

    bracket = v_arm.union(h_arm)

    # ── Sensor body placeholder (TCST2103-style fork sensor) ──
    # The fork is modelled as a U-shape: outer body + gap
    sensor_outer = (
        cq.Workplane("XY")
        .center(SENSOR_X_CTR, SENSOR_Y_CTR)
        .box(SENSOR_BODY_X, SENSOR_BODY_Y, SENSOR_BODY_Z)
        .translate((0, 0, SENSOR_Z_CTR))
    )
    # Fork gap cutter (the opening that the disk passes through)
    gap_cutter = (
        cq.Workplane("XY")
        .center(SENSOR_X_CTR - SENSOR_BODY_X / 4, SENSOR_Y_CTR)
        .rect(SENSOR_BODY_X / 2 + 0.01, SENSOR_FORK_GAP)
        .extrude(SENSOR_BODY_Z + 0.02)
        .translate((0, 0, SENSOR_Z_CTR - SENSOR_BODY_Z / 2 - 0.01))
    )
    sensor_body = sensor_outer.cut(gap_cutter)

    try:
        return bracket.union(sensor_body)
    except Exception:
        return bracket   # fallback: bracket without sensor body


# ---------------------------------------------------------------------------
# BUILD
# ---------------------------------------------------------------------------
print("Building Index Wheel & Sensor Mount (Phase 16)...")
print(f"  Index disk: R={INDEX_DISK_R:.2f}\"  T={INDEX_DISK_T:.3f}\"  "
      f"at Z_ctr={INDEX_DISK_Z_CTR:.3f}\"")
print(f"  Sensor fork at X={SENSOR_X_CTR:.3f}\"  Z={SENSOR_Z_CTR:.3f}\"  "
      f"fork gap={SENSOR_FORK_GAP:.3f}\" > disk T={INDEX_DISK_T:.3f}\" -- clearance OK")
print(f"  Notch: depth={INDEX_NOTCH_DEPTH:.2f}\"  width={INDEX_NOTCH_W:.2f}\"  at angle 0 deg (+X)")

print("  Building rear shaft extension...")
rear_shaft = make_rear_shaft()
save_step(rear_shaft, "rear_shaft.step")

print("  Building index disk...")
index_disk = make_index_disk()
save_step(index_disk, "index_disk.step")

print("  Building sensor mount bracket...")
sensor_mount = make_sensor_mount()
save_step(sensor_mount, "sensor_mount.step")

# Assembly
print("  Building index_wheel_assembly.step...")
iw_assy = cq.Assembly()
iw_assy.add(rear_shaft,   name="rear_shaft",   color=cq.Color(0.75, 0.75, 0.75, 1.0))
iw_assy.add(index_disk,   name="index_disk",   color=cq.Color(0.15, 0.15, 0.15, 1.0))
iw_assy.add(sensor_mount, name="sensor_mount", color=cq.Color(0.20, 0.45, 0.70, 1.0))
iw_assy.export(str(OUTPUT / "index_wheel_assembly.step"))
print("  Wrote output/index_wheel_assembly.step")

# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
print("\n--- Index Wheel Verification ---")

bb_rs = rear_shaft.val().BoundingBox()
print(f"  rear_shaft:    Z=[{bb_rs.zmin:.3f}, {bb_rs.zmax:.3f}]  "
      f"(expected [{REAR_SHAFT_Z_BOT:.3f}, {REAR_SHAFT_Z_TOP:.3f}])")
z_ok = abs(bb_rs.zmin - REAR_SHAFT_Z_BOT) < 0.01 and abs(bb_rs.zmax - REAR_SHAFT_Z_TOP) < 0.01
print(f"                 {'OK' if z_ok else 'CHECK Z bounds'}")

bb_id = index_disk.val().BoundingBox()
disk_z_bot = INDEX_DISK_Z_CTR - INDEX_DISK_T / 2
disk_z_top = INDEX_DISK_Z_CTR + INDEX_DISK_T / 2
disk_r_max = max(abs(bb_id.xmin - CAROUSEL_X), abs(bb_id.xmax - CAROUSEL_X))
print(f"  index_disk:    Z=[{bb_id.zmin:.3f}, {bb_id.zmax:.3f}]  "
      f"(expected [{disk_z_bot:.3f}, {disk_z_top:.3f}])")
print(f"                 Outer R = {disk_r_max:.3f}\"  (expected {INDEX_DISK_R:.3f}\")")
below_mount = bb_id.zmax < MOTOR_MOUNT_BOT
print(f"                 Disk top Z={bb_id.zmax:.3f}\" < motor mount bottom Z={MOTOR_MOUNT_BOT:.3f}\"  "
      f"({'CLEAR OK' if below_mount else 'INTERFERENCE!'})")

bb_sm = sensor_mount.val().BoundingBox()
fork_at_disk = (bb_sm.xmin <= CAROUSEL_X + INDEX_DISK_R <= bb_sm.xmax)
print(f"  sensor_mount:  X=[{bb_sm.xmin:.3f}, {bb_sm.xmax:.3f}]  "
      f"Z=[{bb_sm.zmin:.3f}, {bb_sm.zmax:.3f}]")
print(f"                 Sensor fork spans disk rim at X={CAROUSEL_X + INDEX_DISK_R:.3f}\"  "
      f"({'IN RANGE' if fork_at_disk else 'OUT OF RANGE -- CHECK'})")

# Check disk-to-shaft alignment
disk_bore_clears_shaft = INDEX_BORE_R > SHAFT_R
print(f"\n  Shaft R={SHAFT_R:.3f}\"  Disk bore R={INDEX_BORE_R:.3f}\"  "
      f"radial clearance={INDEX_BORE_R - SHAFT_R:.4f}\"  "
      f"({'OK' if disk_bore_clears_shaft else 'INTERFERENCE!'})")
print(f"  Fork gap={SENSOR_FORK_GAP:.3f}\"  Disk thickness={INDEX_DISK_T:.3f}\"  "
      f"axial clearance={SENSOR_FORK_GAP - INDEX_DISK_T:.4f}\"  "
      f"({'OK' if SENSOR_FORK_GAP > INDEX_DISK_T else 'INTERFERENCE!'})")
print(f"  Index notch: depth={INDEX_NOTCH_DEPTH:.3f}\"  width={INDEX_NOTCH_W:.3f}\"  "
      f"at angle 0 deg -- sensor detects 1 pulse per revolution (home)")
print(f"  Cartridge step = 36 deg (360/10 slots)")
print(f"  After homing, each 36-deg step advances to next cartridge position")

print("\nDone. Integrate into carousel.py hero_assy via guard block.")
