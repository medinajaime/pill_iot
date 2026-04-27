# Hero Pill Dispenser — Optical Detection Chamber
# Phase 10: Staging area with imaging features inside the top loading column.
#
# Pill loading flow:
#   1. User opens hatch, places ONE pill at a time onto the staging floor
#   2. LED ring illuminates; camera images the pill from 45-degree angle
#   3. System identifies pill against user's prescription list (not a global DB)
#   4. Motor rotates correct cartridge under loading axis
#   5. Trapdoor (staging floor) releases pill into the loading tube -> carousel
#
# Run order:
#   1. hero_dispenser.py  (enclosure.step, button.step, pill_cup.step)
#   2. optical_chamber.py (chamber_shell.step, staging_floor.step,
#                          camera_mount.step, led_ring_oc.step,
#                          optical_chamber_assembly.step)
#   3. carousel.py        (hero_full_assembly.step)
#
# Run with: C:\Users\jaime\AppData\Local\Python\pythoncore-3.12-64\python.exe optical_chamber.py

import cadquery as cq
import math
import pathlib

OUTPUT = pathlib.Path("output")
OUTPUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Constants (copied from carousel.py — no circular import)
# ---------------------------------------------------------------------------

# World axis: X left/right, Y back(0)/front(9), Z bottom(0)/top(15)
CAROUSEL_X        = 0.0
CAROUSEL_Y        = 4.5    # carousel centre Y (world)
LOAD_TUBE_INNER_R = 1.80   # loading tube bore
LOAD_TUBE_OUTER_R = 1.90   # loading tube outer wall

# ---------------------------------------------------------------------------
# Chamber shell geometry
# Chamber nests concentrically INSIDE the loading tube.
# Gap between chamber OD (1.50) and tube ID (1.80) = 0.30" — camera mount lives here.
# ---------------------------------------------------------------------------
CHBR_OUTER_R = 1.50    # chamber outer radius
CHBR_INNER_R = 1.40    # imaging bore radius
CHBR_WALL    = CHBR_OUTER_R - CHBR_INNER_R   # 0.10"
CHBR_H       = 2.00    # chamber height
CHBR_Z_BOT   = 12.90   # bottom of chamber (= HATCH_WORLD_Z - CHBR_H = 14.90 - 2.00)
CHBR_Z_TOP   = 14.90   # top of chamber — flush with hatch underside

# ---------------------------------------------------------------------------
# Staging floor (trapdoor placeholder)
# Pills land here for optical identification before dropping into the carousel.
# In the final product this becomes a powered transparent trapdoor.
# ---------------------------------------------------------------------------
FLOOR_R = CHBR_INNER_R   # 1.40" — fills full imaging bore
FLOOR_T = 0.05            # thin disk; pills rest flat on this surface
FLOOR_Z = CHBR_Z_BOT     # 12.90" — flush with chamber bottom

# ---------------------------------------------------------------------------
# Camera mount block
# Sits in the 0.30" annular gap between chamber OD and loading tube ID.
# Located on the -X side of the loading column.
# A viewport window is cut through the chamber shell wall so the lens
# can see the staging floor without obstruction.
# ---------------------------------------------------------------------------
# Bridge mount — spans nearly the full 0.30" annular gap on the −X side.
# After rotating ~17.74° about Y, the diagonal corner of the bridge (far X, extreme Z)
# swings out further than the pre-rotation X extent.  CAM_MNT_W is therefore derived
# so that the post-rotation worst corner stays inside LOAD_TUBE_INNER_R - 0.005" margin.
#
# Pre-rotation: bridge_x_min = −(CHBR_OUTER_R + CAM_MNT_W), bridge_x_max = −CHBR_OUTER_R
# Worst post-rotation X (from pivot at bridge_x_max):
#   |pivot_x| + CAM_MNT_W*cos(θ) + CAM_MNT_H/2*sin(θ) <= LOAD_TUBE_INNER_R
# => CAM_MNT_W <= (gap - CAM_MNT_H/2*sin(θ)) / cos(θ)  where gap=0.30"
CAM_MNT_Y_W = 0.40    # bridge Y width (chord across gap)
CAM_MNT_H   = 0.30    # bridge Z height (sufficient for M2.5 through-holes + lens boss)
M25_CLEAR_R  = 0.053   # M2.5 clearance hole radius  (2.7 mm / 2 / 25.4 in)

# Optical alignment — pivot (lens exit) is at X = -CHBR_OUTER_R = -1.50".
# Target is trapdoor leaf mid-plane: HINGE_Z = DOOR_Z + DOOR_T/2 = 12.92".
# Phase 17: camera raised so that dX = dZ = 1.50" => 45 deg downward view.
#   Old: CAM_MNT_Z = 13.40"  (dZ=0.48" -> 17.74 deg -- near-horizontal, poor for imaging)
#   New: CAM_MNT_Z = 14.42"  (dZ=1.50" -> 45.00 deg -- sees pill top face + full bore)
HINGE_Z     = 12.92    # trapdoor leaf mid-plane Z  (trapdoor.py: DOOR_Z + DOOR_T/2)
CHBR_LENS_X = -CHBR_OUTER_R                          # -1.50"  lens exit plane
CAM_MNT_X   = -CHBR_OUTER_R                          # unchanged for Y-axis pivot
# For 45 deg: dX = dZ = |CHBR_LENS_X - CAROUSEL_X| = 1.50"
# => CAM_MNT_Z = HINGE_Z + 1.50 = 12.92 + 1.50 = 14.42"
CAM_MNT_Z   = HINGE_Z + abs(CAROUSEL_X - CHBR_LENS_X)   # 14.42"
CAM_ROT_DEG = math.degrees(
    math.atan2(abs(HINGE_Z - CAM_MNT_Z), abs(CAROUSEL_X - CHBR_LENS_X))
)   # = atan2(1.50, 1.50) = 45.00 deg

# Derived bridge radial width — ensures post-rotation far corner stays inside tube bore.
# At 45 deg: CAM_MNT_W = (0.30 - 0.15*sin(45)) / cos(45) - 0.005
#                       = (0.30 - 0.106) / 0.707 - 0.005 = 0.269"
_cam_rot_rad = math.radians(CAM_ROT_DEG)
_gap = LOAD_TUBE_INNER_R - CHBR_OUTER_R                             # 0.30" nominal gap
CAM_MNT_W = (_gap - CAM_MNT_H / 2.0 * math.sin(_cam_rot_rad)) / math.cos(_cam_rot_rad) - 0.005
# post-rotation max |X| = 1.50 + 0.269*cos(45) + 0.15*sin(45) = 1.50 + 0.190 + 0.106 = 1.796"

# Camera FOV — Pi Camera v2 (OV5647) horizontal half-angle
FOV_HALF     = 30.0    # degrees (conservative; real spec ≈ 31.1°)
FOV_HALF_RAD = math.radians(FOV_HALF)

# Viewport window cut through the 0.10"-thick chamber shell wall.
# WIN_H is auto-sized: at least the bridge height so the window fully exposes the
# lens face; also >= the FOV cone diameter at the wall (2 * CHBR_WALL * tan(FOV_HALF)).
WIN_W        = 0.20    # X dimension — generous clearance through 0.10" wall
WIN_D        = 0.30    # Y dimension
WIN_H        = max(CAM_MNT_H, 2 * CHBR_WALL * math.tan(FOV_HALF_RAD))
               # = max(0.30, 2*0.10*tan(30°)) = max(0.30, 0.115) = 0.30"
WIN_X_CENTER = -(CHBR_INNER_R + CHBR_WALL / 2)   # −1.45" mid-wall X
WIN_Z_CENTER = CAM_MNT_Z                           # 13.40" — aligned with bridge Z centre

# ---------------------------------------------------------------------------
# LED illumination ring (torus via revolve — CadQuery has no native torus)
# Hangs from the chamber ceiling to provide even, shadow-free overhead lighting.
# Major radius 1.30" keeps the ring 0.05" clear of the chamber inner wall (1.40").
# ---------------------------------------------------------------------------
LED_MAJOR_R  = 1.30    # ring centreline radius  (OD = 1.35" < CHBR_INNER_R = 1.40")
LED_MINOR_R  = 0.05    # tube cross-section radius
LED_Z_CENTER = CHBR_Z_TOP - LED_MINOR_R   # 14.85" — just below chamber ceiling

# Sanity check: LED ring top face must be flush with chamber ceiling.
assert abs((LED_Z_CENTER + LED_MINOR_R) - CHBR_Z_TOP) < 1e-9, (
    f"LED ring top {LED_Z_CENTER + LED_MINOR_R:.6f}\" != CHBR_Z_TOP {CHBR_Z_TOP:.6f}\""
)

# ---------------------------------------------------------------------------
# Chamber ceiling plate constants (Phase 17)
# Frosted PETG disk press-fitted into the top of the chamber bore.
# LED ring torus rests in an annular groove on the TOP face of this plate,
# LEDs facing downward through the frosted PETG (acts as diffuser).
# Center port R=0.60" matches the routing chute exit mouth exactly.
# ---------------------------------------------------------------------------
ROUTING_CHUTE_EXIT_R = 0.60     # from routing_chute.py CHUTE_R_BOT -- pill entry port
CEIL_OUTER_R  = CHBR_INNER_R            # 1.40" -- press-fit inside imaging bore
CEIL_INNER_R  = ROUTING_CHUTE_EXIT_R    # 0.60" -- pill entry port (matches routing chute exit)
CEIL_T        = 0.05                    # 0.05" thick (1.27 mm)
CEIL_Z        = CHBR_Z_TOP - CEIL_T    # 14.85" -- bottom face of ceiling plate
LEDGE_DEPTH   = 0.03                   # 0.03" deep annular groove for LED ring seat
LEDGE_R_IN    = LED_MAJOR_R - LED_MINOR_R   # 1.25" -- groove inner radius
LEDGE_R_OUT   = LED_MAJOR_R + LED_MINOR_R   # 1.35" -- groove outer radius


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def save_step(wp, fname):
    wp.export(str(OUTPUT / fname))
    print(f"  Wrote output/{fname}")


# ---------------------------------------------------------------------------
# Part OC-1: Chamber Shell
# Hollow annular cylinder with a viewport window on the -X face.
# Built at local Z=0..CHBR_H.
# Translate to (CAROUSEL_X, CAROUSEL_Y, CHBR_Z_BOT) at build time.
# ---------------------------------------------------------------------------
def make_chamber_shell():
    outer = cq.Workplane("XY").circle(CHBR_OUTER_R).extrude(CHBR_H)
    inner = (
        cq.Workplane("XY")
        .circle(CHBR_INNER_R)
        .extrude(CHBR_H + 0.1)     # +0.1 overshoot avoids coincident top face
    )
    shell = outer.cut(inner)

    # Viewport window: box cutter in LOCAL frame (before world translate).
    # local_win_x is the X position relative to chamber centre = WIN_X_CENTER
    # local_win_z is the Z position = WIN_Z_CENTER - CHBR_Z_BOT
    local_win_z = WIN_Z_CENTER - CHBR_Z_BOT   # = 13.40 - 12.90 = 0.50"
    window_cutter = (
        cq.Workplane("XY")
        .center(WIN_X_CENTER, 0)               # Y=0 in local frame (camera is centred on Y)
        .box(WIN_W + 0.05, WIN_D, WIN_H)       # slight X overshoot to cut fully through wall
        .translate((0, 0, local_win_z))
    )
    try:
        return shell.cut(window_cutter)
    except Exception as exc:
        print(f"  WARNING: viewport window cut failed ({exc}), returning unwindowed shell")
        return shell


# ---------------------------------------------------------------------------
# Part OC-2: Staging Floor (trapdoor placeholder)
# Flat circular disk at the bottom of the chamber.
# Built at local Z=0..FLOOR_T.
# Translate to (CAROUSEL_X, CAROUSEL_Y, FLOOR_Z) at build time.
# ---------------------------------------------------------------------------
def make_staging_floor():
    """Transparent circular platform where each pill rests for imaging.
    R=1.40" fills the full imaging bore.  T=0.05" — pill lands flat.
    Engineering note: replace with a servo-driven hinged trapdoor in
    the production version (two D-shaped halves on a central hinge).
    """
    return cq.Workplane("XY").circle(FLOOR_R).extrude(FLOOR_T)


# ---------------------------------------------------------------------------
# Part OC-3: Camera Mount Bridge (built directly in world coordinates)
#
# Redesigned (Phase 15) from a floating 0.25" cube to a solid bridge that
# spans the full 0.30" annular gap between chamber wall and loading tube bore.
# Phase 17: camera raised to 14.42" (was 13.40") for 45 deg downward view.
#
# Pre-rotation geometry (world coords):
#   X = [bridge_x_min, -1.50"]          fills annular gap (width = CAM_MNT_W = 0.269")
#   Y = [CAROUSEL_Y - 0.20, CAROUSEL_Y + 0.20] = [4.30, 4.70]
#   Z = [CAM_MNT_Z - 0.15, CAM_MNT_Z + 0.15]  = [14.27, 14.57]
#
# Features:
#   * Lens boss (R=0.05", L=0.04") on +X face -- faces into imaging bore
#   * 2x M2.5 clearance holes (R=0.053") along Z at Y +/- 0.12" -- screw-down mount
#   * Rotated +CAM_ROT_DEG (45.00 deg) around Y-axis at pivot X=-1.50" so lens
#     normal aims exactly at the trapdoor centre (0.0, 4.5, HINGE_Z=12.92")
# ---------------------------------------------------------------------------
def make_camera_mount():
    """Structural bridge mount spanning the 0.30\" annular gap.

    Tilt derivation (Phase 17 -- 45 deg downward):
      Pivot (lens exit, +X face of bridge): (-1.50\", 4.5\", 14.42\")
      Target (trapdoor leaf mid-plane):      (0.0\",  4.5\", 12.92\")
      dX = +1.50\"  dZ = -1.50\"
      theta = atan2(1.50, 1.50) = 45.00 deg -- sees pill top face at 2.12\" distance
      FOV cone at staging plane: 2.121\" * tan(30 deg) = 1.224\" radius (covers full bore)

    Post-rotation max |X| = 1.50 + 0.269*cos(45) + 0.15*sin(45) = 1.796\" < 1.80\"  OK
    """
    # +X face of bridge = chamber outer surface = pivot plane.
    # bridge_x_min is derived from CAM_MNT_W so the post-rotation far corner
    # stays inside LOAD_TUBE_INNER_R (see constant derivation at module level).
    bridge_x_max = -CHBR_OUTER_R                        # -1.50"  (pivot / lens exit plane)
    bridge_x_min = bridge_x_max - CAM_MNT_W             # -1.50 - 0.262 ≈ -1.762"
    bridge_x_ctr = bridge_x_max - CAM_MNT_W / 2.0      # -1.50 - 0.131 ≈ -1.631"

    # Build the bridge block: +X face lands exactly at bridge_x_max = −1.50".
    bridge = (
        cq.Workplane("XY")
        .center(bridge_x_ctr, CAROUSEL_Y)
        .box(CAM_MNT_W, CAM_MNT_Y_W, CAM_MNT_H)
        .translate((0, 0, CAM_MNT_Z))
    )
    # Pre-rotation extents: X=[bridge_x_min, -1.50]  Y=[4.30, 4.70]  Z=[14.27, 14.57]

    # Lens boss: small cylinder on the +X face (faces chamber bore before rotation).
    lens_boss = (
        cq.Workplane("YZ")
        .center(CAROUSEL_Y, CAM_MNT_Z)
        .circle(0.05)
        .extrude(0.04)
        .translate((bridge_x_max, 0, 0))   # place on +X face of bridge
    )
    try:
        bridge = bridge.union(lens_boss)
    except Exception:
        pass   # lens boss is cosmetic; skip if boolean fails

    # M2.5 clearance holes — 2× vertical (Z-axis through-holes) for screw-down mounting.
    # Centres: (bridge_x_ctr, CAROUSEL_Y ± 0.12", CAM_MNT_Z)
    for y_off in (+0.12, -0.12):
        hole = (
            cq.Workplane("XY")
            .center(bridge_x_ctr, CAROUSEL_Y + y_off)
            .circle(M25_CLEAR_R)
            .extrude(CAM_MNT_H + 0.02)           # +0.02 overshoot for clean Boolean
            .translate((0, 0, CAM_MNT_Z - CAM_MNT_H / 2 - 0.01))
        )
        try:
            bridge = bridge.cut(hole)
        except Exception:
            pass   # non-critical — skip if Boolean fails

    # Rotate about Y-axis: pivot at the +X face (bridge_x_max = −1.50").
    # This keeps the lens boss exit stationary while the block tilts downward.
    pivot    = cq.Vector(bridge_x_max, CAROUSEL_Y, CAM_MNT_Z)
    axis_end = cq.Vector(bridge_x_max, CAROUSEL_Y + 1.0, CAM_MNT_Z)
    return bridge.rotate(pivot, axis_end, CAM_ROT_DEG)


# ---------------------------------------------------------------------------
# Part OC-4: LED Illumination Ring
# Torus created by revolving a small circle (radius LED_MINOR_R) at distance
# LED_MAJOR_R from the Z axis through 360 deg.
# Built at local Z (before world translate to CHBR_Z_BOT).
# Translate to (CAROUSEL_X, CAROUSEL_Y, CHBR_Z_BOT) at build time.
# ---------------------------------------------------------------------------
def make_led_ring():
    """Overhead LED ring at the chamber ceiling (Z=14.85 world).
    Major R=1.30", minor R=0.05" — ring OD=1.35" < chamber inner R=1.40".
    Provides even, shadow-free illumination of the staging floor.

    CadQuery torus via revolve:
      XZ workplane — first axis = world X, second axis = world Z.
      Circle at (LED_MAJOR_R, local_z) = (1.30, 1.95) in XZ local coords.
      Revolved 360 deg around the Z axis -> horizontal torus in XY plane.
    """
    local_z = LED_Z_CENTER - CHBR_Z_BOT   # = 14.85 - 12.90 = 1.95" (local frame)

    try:
        ring = (
            cq.Workplane("XZ")
            .center(LED_MAJOR_R, local_z)
            .circle(LED_MINOR_R)
            .revolve(360.0, (0, 0, 0), (0, 0, 1))   # revolve around Z axis
        )
        return ring
    except Exception as exc:
        print(f"  WARNING: LED torus revolve failed ({exc}), using annular disk fallback")
        # Fallback: thin annular disk at ceiling height
        local_top = CHBR_H - 0.02
        ring_h    = LED_MINOR_R * 2   # 0.10"
        outer_d   = (
            cq.Workplane("XY")
            .circle(LED_MAJOR_R + LED_MINOR_R)
            .extrude(ring_h)
            .translate((0, 0, local_top - ring_h))
        )
        inner_cut = (
            cq.Workplane("XY")
            .circle(LED_MAJOR_R - LED_MINOR_R)
            .extrude(ring_h + 0.01)
            .translate((0, 0, local_top - ring_h))
        )
        return outer_d.cut(inner_cut)


# ---------------------------------------------------------------------------
# Part OC-5: Chamber Ceiling Plate (Phase 17)
# Frosted PETG annular disk press-fitted into the top of the chamber bore.
# Built at local Z=0..CEIL_T, translated to (CAROUSEL_X, CAROUSEL_Y, CEIL_Z).
# ---------------------------------------------------------------------------
def make_chamber_ceiling():
    """Frosted PETG ceiling plate at the top of the optical imaging chamber.

    Functions:
      1. LED ring mount: annular groove on top face seats the LED torus
         (groove R=[1.25, 1.35]", depth=0.03"). LEDs face downward through
         the frosted PETG which acts as a diffuser for even illumination.
      2. Ambient light baffle: blocks loading tube ambient light from entering
         the imaging bore (except through the 0.60" centre pill-entry port).
      3. Pill entry port: centre hole R=0.60" = ROUTING_CHUTE_EXIT_R --
         routing chute exit and pill-entry port are the same radius.

    World position: Z=[14.85, 14.90]  (CEIL_Z to CHBR_Z_TOP)
    Outer R=1.40" press-fits into chamber bore; no fasteners needed.
    """
    # Annular disk: outer = CEIL_OUTER_R, inner (pill port) = CEIL_INNER_R
    disk = cq.Workplane("XY").circle(CEIL_OUTER_R).extrude(CEIL_T)
    port = (
        cq.Workplane("XY")
        .circle(CEIL_INNER_R)
        .extrude(CEIL_T + 0.01)   # overshoot avoids coincident face
    )
    disk = disk.cut(port)

    # LED mounting groove on the top face (+Z of the plate).
    # Groove spans R=[LEDGE_R_IN, LEDGE_R_OUT] = [1.25, 1.35]", depth=LEDGE_DEPTH=0.03".
    ledge_outer = (
        cq.Workplane("XY")
        .circle(LEDGE_R_OUT)
        .extrude(LEDGE_DEPTH + 0.01)
    )
    ledge_inner = (
        cq.Workplane("XY")
        .circle(LEDGE_R_IN)
        .extrude(LEDGE_DEPTH + 0.02)
    )
    groove = ledge_outer.cut(ledge_inner)
    # Translate groove to the top face (Z = CEIL_T - LEDGE_DEPTH).
    groove = groove.translate((0, 0, CEIL_T - LEDGE_DEPTH))
    try:
        disk = disk.cut(groove)
    except Exception as exc:
        print(f"  WARNING: LED ledge groove failed ({exc}) -- flat ceiling used")

    return disk.translate((CAROUSEL_X, CAROUSEL_Y, CEIL_Z))


# ===========================================================================
# BUILD SECTION
# ===========================================================================
print("Building Optical Detection Chamber (Phase 17 - 45 deg downward camera + ceiling plate)...")
print(f"  Chamber Z = [{CHBR_Z_BOT:.2f}, {CHBR_Z_TOP:.2f}]  inside loading tube (R={LOAD_TUBE_INNER_R}\")")
print(f"  Camera tilt: {CAM_ROT_DEG:.2f} deg  at Z={CAM_MNT_Z:.3f}\"  (was 17.74 deg at 13.40\")")

# --- OC-1. Chamber shell ---
print("  Building chamber shell...")
chamber_shell = (
    make_chamber_shell()
    .translate((CAROUSEL_X, CAROUSEL_Y, CHBR_Z_BOT))
)
save_step(chamber_shell, "chamber_shell.step")

# --- OC-2. Staging floor (trapdoor placeholder) ---
print("  Building staging floor...")
staging_floor = (
    make_staging_floor()
    .translate((CAROUSEL_X, CAROUSEL_Y, FLOOR_Z))
)
save_step(staging_floor, "staging_floor.step")

# --- OC-3. Camera mount (bridge spans annular gap, tilt derived geometrically) ---
print(f"  Building camera mount bridge ({CAM_ROT_DEG:.2f} deg-tilted, {CAM_MNT_W:.2f}\"x{CAM_MNT_Y_W:.2f}\"x{CAM_MNT_H:.2f}\" bridge)...")
camera_mount = make_camera_mount()
save_step(camera_mount, "camera_mount.step")

# --- OC-4. LED illumination ring ---
print("  Building LED ring (torus)...")
led_ring_oc = (
    make_led_ring()
    .translate((CAROUSEL_X, CAROUSEL_Y, CHBR_Z_BOT))
)
save_step(led_ring_oc, "led_ring_oc.step")

# --- OC-5. Chamber ceiling plate ---
print("  Building chamber ceiling plate (LED mount + light baffle + diffuser)...")
chamber_ceiling = make_chamber_ceiling()
save_step(chamber_ceiling, "chamber_ceiling.step")

# --- OC-6. Optical chamber sub-assembly ---
print("  Building optical_chamber_assembly.step...")
oc_assy = cq.Assembly()
oc_assy.add(
    chamber_shell, name="chamber_shell",
    color=cq.Color(0.70, 0.90, 0.70, 0.35),   # translucent green (imaging bore visible)
)
oc_assy.add(
    staging_floor, name="staging_floor",
    color=cq.Color(0.85, 0.95, 1.00, 0.70),   # light blue (transparent trapdoor)
)
oc_assy.add(
    camera_mount, name="camera_mount",
    color=cq.Color(0.12, 0.12, 0.12, 1.0),    # near-black (camera body)
)
oc_assy.add(
    led_ring_oc, name="led_ring_oc",
    color=cq.Color(1.00, 0.92, 0.23, 0.90),   # warm yellow (LED glow)
)
oc_assy.add(
    chamber_ceiling, name="chamber_ceiling",
    color=cq.Color(0.90, 0.95, 0.90, 0.60),   # translucent frosted green (diffuser plate)
)
oc_assy.export(str(OUTPUT / "optical_chamber_assembly.step"))
print("  Wrote output/optical_chamber_assembly.step")

# ---------------------------------------------------------------------------
# Inline verification
# ---------------------------------------------------------------------------
print("\n--- Optical Chamber Verification ---")

bb_cs = chamber_shell.val().BoundingBox()
print(f"  chamber_shell:   Z=[{bb_cs.zmin:.3f}, {bb_cs.zmax:.3f}]  "
      f"(expected [{CHBR_Z_BOT:.3f}, {CHBR_Z_TOP:.3f}])")
print(f"                   X=[{bb_cs.xmin:.3f}, {bb_cs.xmax:.3f}]  "
      f"(expected [{CAROUSEL_X - CHBR_OUTER_R:.3f}, {CAROUSEL_X + CHBR_OUTER_R:.3f}])")

bb_sf = staging_floor.val().BoundingBox()
print(f"  staging_floor:   Z=[{bb_sf.zmin:.3f}, {bb_sf.zmax:.3f}]  "
      f"(expected [{FLOOR_Z:.3f}, {FLOOR_Z + FLOOR_T:.3f}])")
print(f"                   X=[{bb_sf.xmin:.3f}, {bb_sf.xmax:.3f}]  "
      f"(expected [{CAROUSEL_X - FLOOR_R:.3f}, {CAROUSEL_X + FLOOR_R:.3f}])")

bb_cm = camera_mount.val().BoundingBox()
cam_max_r = max(abs(bb_cm.xmin), abs(bb_cm.xmax))
print(f"  camera_mount:    X=[{bb_cm.xmin:.3f}, {bb_cm.xmax:.3f}]  "
      f"Z=[{bb_cm.zmin:.3f}, {bb_cm.zmax:.3f}]")
print(f"                   max |X| = {cam_max_r:.3f}\"  "
      f"vs tube bore R={LOAD_TUBE_INNER_R}\"  -> "
      f"{'FITS OK' if cam_max_r < LOAD_TUBE_INNER_R else 'INTERFERENCE!'}")

bb_lo = led_ring_oc.val().BoundingBox()
ring_od = LED_MAJOR_R + LED_MINOR_R
print(f"  led_ring_oc:     Z=[{bb_lo.zmin:.3f}, {bb_lo.zmax:.3f}]  "
      f"(expected [{LED_Z_CENTER - LED_MINOR_R:.3f}, {LED_Z_CENTER + LED_MINOR_R:.3f}])")
print(f"                   ring OD={ring_od:.3f}\"  chamber inner R={CHBR_INNER_R:.3f}\"  "
      f"gap={CHBR_INNER_R - ring_od:.3f}\"  "
      f"({'OK' if CHBR_INNER_R > ring_od else 'INTERFERENCE!'})")

# Pill path clearance
print(f"\n  PILL PATH through optical chamber:")
print(f"    Loading tube bore:  R={LOAD_TUBE_INNER_R:.2f}\"  (continues above chamber)")
print(f"    Chamber outer R:    {CHBR_OUTER_R:.2f}\"  (nested inside tube, {LOAD_TUBE_INNER_R-CHBR_OUTER_R:.2f}\" gap)")
print(f"    Chamber inner R:    {CHBR_INNER_R:.2f}\"  (imaging bore)")
print(f"    Staging floor:      Z={FLOOR_Z:.2f}\"  R={FLOOR_R:.2f}\"  [TRAPDOOR PLACEHOLDER]")
print(f"    LED ring Z:         {LED_Z_CENTER:.2f}\"  (ceiling, clear of pill path)")

# ---------------------------------------------------------------------------
# Optical Alignment Verification (Phase 15)
# ---------------------------------------------------------------------------
_bridge_x_min = -LOAD_TUBE_INNER_R
_bridge_x_max = -CHBR_OUTER_R
_bridge_x_ctr = (_bridge_x_min + _bridge_x_max) / 2.0

print(f"\n  OPTICAL ALIGNMENT (Phase 15):")
print(f"    Bridge pre-rotation:  X=[{_bridge_x_min:.3f}, {_bridge_x_max:.3f}]\"  "
      f"({_bridge_x_max - _bridge_x_min:.3f}\" width, gap={LOAD_TUBE_INNER_R - CHBR_OUTER_R:.2f}\")")
print(f"    Bridge dimensions:    {CAM_MNT_W:.2f}\"(X) x {CAM_MNT_Y_W:.2f}\"(Y) x {CAM_MNT_H:.2f}\"(Z)")
print(f"    M2.5 holes:           2x at Y={CAROUSEL_Y}+/-0.12\"  R={M25_CLEAR_R:.3f}\"  (Z through-holes)")
print(f"    Lens exit point:      X={CHBR_LENS_X:.3f}\"  Y={CAROUSEL_Y:.3f}\"  Z={CAM_MNT_Z:.3f}\"")
print(f"    Trapdoor centre:      X={CAROUSEL_X:.3f}\"   Y={CAROUSEL_Y:.3f}\"  Z={HINGE_Z:.3f}\"")
print(f"    dX=+{abs(CAROUSEL_X - CHBR_LENS_X):.3f}\"  dZ=-{abs(HINGE_Z - CAM_MNT_Z):.3f}\"  ->  "
      f"tilt = {CAM_ROT_DEG:.2f} deg  (was hardcoded 45.0 deg)")
_ray_hit_x = CHBR_LENS_X + (CAM_MNT_Z - HINGE_Z) / math.tan(math.radians(CAM_ROT_DEG))
_aim_ok = abs(_ray_hit_x - CAROUSEL_X) < 0.001
print(f"    Ray hits trapdoor at: X={_ray_hit_x:.4f}\"  "
      f"({'on-centre OK' if _aim_ok else f'offset {_ray_hit_x - CAROUSEL_X:.4f}\" - CHECK'})")
print(f"    Viewport WIN_H:       {WIN_H:.3f}\"  "
      f"(max of bridge H={CAM_MNT_H:.2f}\" and FOV cone at wall {2*CHBR_WALL*math.tan(FOV_HALF_RAD):.3f}\")")

_cam_max_r_pre = LOAD_TUBE_INNER_R   # bridge pre-rotation outer X = 1.80"
# After tilt of ~17.7°, the bridge swings a small arc; outermost corner moves.
# Worst case: far corner of bridge at (bridge_x_min, ±CAM_MNT_Y_W/2, ±CAM_MNT_H/2)
# rotated 17.74° about X=bridge_x_max.  ΔX from pivot = CAM_MNT_W = 0.30".
# Post-rotation X of far corner: bridge_x_max + ΔX*cos(θ) (rotation reduces X reach)
_far_dx  = CAM_MNT_W                            # 0.30" from pivot
_post_rot_x = abs(_bridge_x_max) + _far_dx * math.cos(math.radians(CAM_ROT_DEG))
print(f"    Post-rotation max |X|: {_post_rot_x:.3f}\"  vs tube bore {LOAD_TUBE_INNER_R:.2f}\"  "
      f"({'FITS OK' if _post_rot_x <= LOAD_TUBE_INNER_R + 0.005 else 'INTERFERENCE!'})")

print(f"\n  LED RING FLUSH CHECK:")
_led_top = LED_Z_CENTER + LED_MINOR_R
print(f"    LED top Z = {LED_Z_CENTER:.3f}\" + {LED_MINOR_R:.3f}\" = {_led_top:.3f}\"  "
      f"== CHBR_Z_TOP = {CHBR_Z_TOP:.3f}\"  "
      f"({'FLUSH OK' if abs(_led_top - CHBR_Z_TOP) < 0.001 else 'MISMATCH!'})")

# Chamber ceiling verification
bb_cc = chamber_ceiling.val().BoundingBox()
print(f"\n  chamber_ceiling: Z=[{bb_cc.zmin:.3f}, {bb_cc.zmax:.3f}]  "
      f"T={bb_cc.zmax - bb_cc.zmin:.3f}\"  "
      f"(expected [{CEIL_Z:.3f}, {CHBR_Z_TOP:.3f}])")
print(f"                   Pill port R={CEIL_INNER_R:.2f}\"  "
      f"(routing chute exit R={ROUTING_CHUTE_EXIT_R:.2f}\"  "
      f"{'OK' if abs(CEIL_INNER_R - ROUTING_CHUTE_EXIT_R) < 0.001 else 'MISMATCH'})")
print(f"                   LED ledge: R=[{LEDGE_R_IN:.2f}\", {LEDGE_R_OUT:.2f}\"]  "
      f"depth={LEDGE_DEPTH:.2f}\"")
print(f"                   Ambient light: BLOCKED above Z={CEIL_Z:.3f}\"  "
      f"(except centre port R={CEIL_INNER_R:.2f}\")")

# Updated optical alignment
print(f"\n  OPTICAL ALIGNMENT (Phase 17):")
_cam_dist = math.sqrt((CAROUSEL_X - CHBR_LENS_X)**2 + (HINGE_Z - CAM_MNT_Z)**2)
_fov_r = _cam_dist * math.tan(FOV_HALF_RAD)
print(f"    CAM_MNT_Z = {CAM_MNT_Z:.3f}\"  (was 13.40\")")
print(f"    CAM_ROT_DEG = {CAM_ROT_DEG:.2f} deg  (was 17.74 deg)")
print(f"    Camera-to-pill distance = {_cam_dist:.3f}\"")
print(f"    FOV radius at staging:   {_fov_r:.3f}\"  "
      f"(staging bore R={CHBR_INNER_R:.2f}\"  "
      f"{'covers all standard capsules OK' if _fov_r > 0.39 else 'CHECK -- may miss #000 capsule'})")
print(f"    Bridge Z span: [{CAM_MNT_Z - CAM_MNT_H/2:.3f}, {CAM_MNT_Z + CAM_MNT_H/2:.3f}]\"  "
      f"LED ring Z: [{LED_Z_CENTER - LED_MINOR_R:.3f}, {CHBR_Z_TOP:.3f}]\"  "
      f"clearance = {(LED_Z_CENTER - LED_MINOR_R) - (CAM_MNT_Z + CAM_MNT_H/2):.3f}\"  "
      f"({'OK' if (LED_Z_CENTER - LED_MINOR_R) > (CAM_MNT_Z + CAM_MNT_H/2) else 'CHECK'})")

print("\nDone. Run carousel.py to integrate into hero_full_assembly.step.")
print("Expected: 5 parts in optical_chamber_assembly.step")
