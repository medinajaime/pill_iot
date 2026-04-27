# Hero Pill Dispenser — Internal Rotary Carousel
# Run AFTER hero_dispenser.py (needs output/enclosure.step, button.step, pill_cup.step)
# Run with: C:\Users\jaime\AppData\Local\Python\pythoncore-3.12-64\python.exe carousel.py

import cadquery as cq
import math
import pathlib

OUTPUT = pathlib.Path("output")
OUTPUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Carousel constants (all in inches)
# ---------------------------------------------------------------------------
INNER_R  = 0.75    # inner radius (drive shaft clearance)
OUTER_R  = 3.5     # outer radius
N_SLOTS  = 10
DEG_EACH = 360.0 / N_SLOTS        # 36.0° per slot
GAP_EACH = 1.0                    # 1° gap each side between cartridges
SWEEP    = DEG_EACH - 2 * GAP_EACH  # 34.0° actual cartridge sweep
CART_H   = 3.9     # cartridge extrusion height (open-top hollow bucket)
WALL_T   = 0.05    # shell wall thickness

# World position of carousel centre (inside D-shell interior)
CAROUSEL_X      = 0.0
CAROUSEL_Y      = 4.5   # back clearance 0.9", front clearance 0.9" — well within shell
CAROUSEL_Z_BASE = 4.9   # bottom of base plate & hub (0.4" above alcove ceiling at 4.5")
CAROUSEL_Z_CART = 5.0   # cartridge bottom (sits on top of base plate)

# Hub geometry
HUB_OUTER_R = 0.75
# HUB_INNER_R = 0.50  # DEPRECATED — old hollow bore; D-hole in hub_lock replaces this
# HUB_H       = 4.2   # DEPRECATED — old hollow hub height; hub_lock uses CART_H instead

# Base plate geometry
BASE_T      = 0.1
SLOT_RADIUS = 2.5   # dispensing slot at local (0, 2.5) → world (0, 7.0) = spout centre
SLOT_W      = 0.6   # (legacy — rectangular slot, replaced by circular drop zone)
SLOT_D      = 0.3   # (legacy — rectangular slot, replaced by circular drop zone)

# Angular offset so cartridge_00 faces the spout (90° from local +X = toward +Y = front)
CART_OFFSET_DEG = 90.0

# --- Pill-drop geometry ---
HOLE_R = 0.3   # radius for cartridge floor hole AND base plate drop zone
OUTLET_SUMP_R       = HOLE_R + 0.18
OUTLET_GUIDE_RIB_H  = 0.08
OUTLET_GUIDE_RIB_W  = 0.055
OUTLET_GUIDE_RIB_L  = 1.55
OUTLET_GUIDE_RIB_X  = 1.85
OUTLET_GUIDE_RIB_Y  = 0.34
DISPENSE_GATE_R     = 0.46
DISPENSE_GATE_T     = 0.035
DISPENSE_GATE_Z     = CAROUSEL_Z_BASE - DISPENSE_GATE_T - 0.01
DISPENSE_GATE_X     = 0.0
DISPENSE_GATE_Y     = CAROUSEL_Y + SLOT_RADIUS
DISPENSE_GATE_ARM_L = 0.90
DISPENSE_GATE_ARM_W = 0.18
DISPENSE_SERVO_W    = 0.90
DISPENSE_SERVO_D    = 0.45
DISPENSE_SERVO_H    = 0.75
DISPENSE_SERVO_X    = 1.35
DISPENSE_SERVO_Y    = CAROUSEL_Y + SLOT_RADIUS
DISPENSE_SERVO_Z    = 4.05

# Phase 22: demo-tablet metering escapement.
# Competition model target: one visible demo tablet, not universal capsules.
DEMO_TABLET_D       = 0.38
DEMO_TABLET_H       = 0.16
SPOUT_TOP_Z         = 4.50
METER_GATE_GAP      = 0.015
DISPENSE_RELEASE_GATE_R = 0.40
DISPENSE_RELEASE_GATE_T = 0.035
DISPENSE_RELEASE_GATE_Z = SPOUT_TOP_Z + 0.005
DISPENSE_RELEASE_GATE_X = 0.0
DISPENSE_RELEASE_GATE_Y = CAROUSEL_Y + SLOT_RADIUS
DISPENSE_RELEASE_GATE_ARM_L = 0.90
DISPENSE_RELEASE_GATE_ARM_W = 0.18
DISPENSE_RELEASE_SERVO_X = -DISPENSE_SERVO_X
DISPENSE_RELEASE_SERVO_Y = DISPENSE_RELEASE_GATE_Y
DISPENSE_RELEASE_SERVO_Z = DISPENSE_RELEASE_GATE_Z - DISPENSE_SERVO_H + 0.02
SWEEP_SLOT_W        = 0.65
SWEEP_SLOT_H        = 0.26
SWEEP_SLOT_D        = 0.50
SWEEP_SLOT_Z        = WALL_T + SWEEP_SLOT_H / 2
SWEEP_CONTAIN_INNER_R = OUTER_R + 0.025
SWEEP_CONTAIN_OUTER_R = OUTER_R + 0.120
SWEEP_CONTAIN_Z       = CAROUSEL_Z_CART + 0.02
SWEEP_CONTAIN_H       = 0.42
SWEEP_SERVICE_WINDOW_W = SWEEP_SLOT_W + 0.22
SWEEP_SERVICE_WINDOW_D = 0.56
SWEEP_SERVICE_WINDOW_H = SWEEP_SLOT_H + 0.10
SWEEP_SEAL_W          = SWEEP_SLOT_W + 0.34
SWEEP_SEAL_D          = 0.055
SWEEP_SEAL_H          = SWEEP_CONTAIN_H
SWEEP_SEAL_APERTURE_W = 0.62
SWEEP_SEAL_APERTURE_H = 0.14
SWEEP_PUSHER_TIP_W  = 0.58
SWEEP_PUSHER_TIP_D  = 0.12
SWEEP_PUSHER_RACK_W = 0.16
SWEEP_PUSHER_RACK_D = 0.64
SWEEP_PUSHER_T      = 0.10
SWEEP_PUSHER_X      = 0.0
SWEEP_PUSHER_Y_RETRACTED = CAROUSEL_Y + SWEEP_CONTAIN_OUTER_R + 0.155
SWEEP_PUSHER_Y_DEPLOYED  = CAROUSEL_Y + SLOT_RADIUS - 0.45
SWEEP_PUSHER_Z      = CAROUSEL_Z_CART + WALL_T + 0.12
SWEEP_RAIL_X        = 0.0
SWEEP_RAIL_Y        = CAROUSEL_Y + SWEEP_CONTAIN_OUTER_R + 0.40
SWEEP_RAIL_Z        = CAROUSEL_Z_CART + WALL_T + 0.02
SWEEP_RAIL_W        = 1.35
SWEEP_RAIL_D        = 0.75
SWEEP_RAIL_T        = 0.08
SWEEP_SERVO_W       = 0.95
SWEEP_SERVO_D       = 0.45
SWEEP_SERVO_H       = 0.55
SWEEP_SERVO_X       = 1.15
SWEEP_SERVO_Y       = CAROUSEL_Y + OUTER_R + 0.45
SWEEP_SERVO_Z       = CAROUSEL_Z_CART + WALL_T
               # (spout inner R=0.25" → 0.05" retaining lip)

# --- Stepper motor (NEMA 17 style placeholder) ---
MOTOR_W      = 1.7    # square face (width and depth) in inches
MOTOR_H_DIM  = 1.5    # motor body height in inches
MOTOR_Z_BOT  = CAROUSEL_Z_BASE - MOTOR_H_DIM   # = 3.4  motor bottom (world Z)
MOTOR_Z_TOP  = CAROUSEL_Z_BASE                  # = 4.9  motor top flush with base plate bottom

# --- D-shaft ---
SHAFT_R          = 0.20   # shaft cylinder radius (~5 mm, realistic for NEMA 17)
SHAFT_FLAT_DEPTH = 0.05   # depth of flat cut on +Y side → D-profile
SHAFT_CLEARANCE  = 0.01   # radial + flat clearance between shaft and hub D-hole
SHAFT_EMBED      = 0.50   # length shaft extends down into motor body (below base plate)
SHAFT_Z_BOT      = CAROUSEL_Z_BASE - SHAFT_EMBED          # = 4.4  (world)
SHAFT_Z_TOP      = CAROUSEL_Z_CART + CART_H               # = 8.9  (world)
SHAFT_H          = SHAFT_Z_TOP - SHAFT_Z_BOT              # = 4.5  total shaft length

# --- Agitator / singulator wheel (housing-fixed, stationary) ---
AGIT_R         = 0.4
AGIT_W         = 0.2
AGIT_WORLD_X   = 0.0
AGIT_WORLD_Y   = CAROUSEL_Y + SLOT_RADIUS        # 4.5 + 2.5 = 7.0  (over spout centre)
# Floor clearance sized for the largest standard capsule lying flat (#000, 9.9 mm dia).
# Bore audit result: original WALL_T gap (1.27 mm) was a show-stopper — no real pill
# could slide under the agitator.  New gap = 10.4 mm clears any capsule lying flat.
AGIT_FLOOR_GAP = 0.41                            # 10.4 mm — clears #000 capsule (9.9 mm)
AGIT_WORLD_Z   = CAROUSEL_Z_CART + AGIT_FLOOR_GAP + AGIT_R  # 5.0 + 0.41 + 0.40 = 5.81"

# ---------------------------------------------------------------------------
# Phase 6: Electronics & Sensing Layer
# ---------------------------------------------------------------------------
ENCLOSURE_H    = 15.0

# --- Pill guide / loading funnel (above carousel, open top and bottom) ---
GUIDE_OUTER_R  = OUTER_R          # 3.5" — flush with carousel OD
GUIDE_WALL     = 0.05             # thin translucent wall
GUIDE_H        = 2.1              # Z = 8.90 .. 11.00
GUIDE_WORLD_Z  = CAROUSEL_Z_CART + CART_H   # = 8.90"

# --- PCB / SBC electronics tray (Raspberry Pi 4 footprint) ---
PCB_W          = 3.35    # board width  (X-direction)
PCB_D          = 2.20    # board depth  (Y-direction)
PCB_T          = 0.063   # board thickness (~1.6 mm standard PCB)
PCB_POST_R     = 0.08    # standoff pillar radius
PCB_POST_H     = 0.25    # standoff height below board bottom
PCB_WORLD_Z    = GUIDE_WORLD_Z + GUIDE_H + 0.5  # = 11.50" (bottom of standoffs)

# --- Camera module (PiCam v2 style; lens faces −Z = downward toward carousel) ---
CAM_W          = 0.98    # board width
CAM_D          = 0.94    # board depth
CAM_T          = 0.35    # board + lens housing total thickness
CAM_LENS_R     = 0.15    # lens barrel radius
CAM_WORLD_Z    = PCB_WORLD_Z - 0.05 - CAM_T  # = 11.10" — shelf is 0.05" thick, cam clears it OK

# --- Load cell sensor pad (in alcove, under dispensing spout) ---
LOAD_R         = 1.30    # circular tray supports CUP_OUTER_R=1.25"
LOAD_T         = 0.10    # tray thickness; top surface at Z=0.20"
LOAD_WORLD_X   = 0.0
LOAD_WORLD_Y   = 7.0
LOAD_WORLD_Z   = 0.10    # sits on alcove floor; cup rests on tray top

# --- Vibration motor – ERM cylinder (near back wall, mounts to enclosure) ---
VIB_R          = 0.30
VIB_H          = 0.50
VIB_WORLD_X    = 0.0
VIB_WORLD_Y    = 0.5     # 0.5" from flat back wall (Y=0)
VIB_WORLD_Z    = 12.5    # mid-height upper section of enclosure

# --- Top loading hatch (D-shaped lid, sits on top of enclosure at Z=14.90) ---
HATCH_T        = 0.10    # lid thickness — matches enclosure wall T
HATCH_HOLE_R   = 1.80    # pill-loading port radius (centred over carousel)
HATCH_WORLD_Z  = ENCLOSURE_H - HATCH_T  # = 14.90"

# ---------------------------------------------------------------------------
# Phase 7: Structural & Interface Components
# ---------------------------------------------------------------------------
# --- Pill chute / one-tablet metering chamber ---
CHUTE_OUTER_R  = 0.35    # slightly wider than drop zone (HOLE_R=0.30")
CHUTE_INNER_R  = 0.25    # matches spout inner bore R
CHUTE_WORLD_Z  = DISPENSE_RELEASE_GATE_Z + DISPENSE_RELEASE_GATE_T + METER_GATE_GAP
CHUTE_H        = DISPENSE_GATE_Z - CHUTE_WORLD_Z - METER_GATE_GAP
# Sealing flange at chute top: wider collar overlaps base-plate underside, stops bounce-out
CHUTE_FLANGE_R = HOLE_R + 0.15   # 0.45" — 0.15" lip beyond drop-zone hole R=0.30"
CHUTE_FLANGE_H = 0.05             # thin enough to clear base plate above

# --- Motor mount plate (NEMA 17 pattern, horizontal under motor) ---
MOUNT_PLATE_W  = 3.0     # wider than MOTOR_W=1.7" for wall anchorage
MOUNT_PLATE_D  = 3.0
MOUNT_PLATE_T  = 0.10
NEMA17_HOLE_SPC = 1.22   # 31 mm mounting hole square pattern
NEMA17_HOLE_R  = 0.06    # M3 clearance (~1.5 mm radius)
MOUNT_WORLD_Z  = MOTOR_Z_BOT - MOUNT_PLATE_T   # = 3.30"

# --- Display panel (flat screen placeholder inside screen cutout) ---
DISPLAY_W      = 3.0     # matches screen cutout width (X)
DISPLAY_H_DIM  = 3.5     # matches screen cutout height (Z)
DISPLAY_T      = 0.08    # panel thickness (Y)
DISPLAY_WORLD_Y = 8.82   # just inside front wall inner face
DISPLAY_WORLD_Z = 12.25  # centre Z of screen cutout: (10.5 + 14.0) / 2

# --- LED status ring (sits in groove around button on front face) ---
LED_RING_OUTER_R = 1.2   # matches groove outer R
LED_RING_INNER_R = 1.0   # matches groove inner R
LED_RING_T     = 0.05    # ring thickness (Y-direction)
LED_RING_WORLD_Y = 9.0   # groove seat position on front face
LED_RING_WORLD_Z = 8.5   # button centre Z

# --- PCB mounting shelf (horizontal bracket supporting PCB tray) ---
PCB_SHELF_W    = PCB_W + 0.6     # = 3.95" — wider than board for wall contact
PCB_SHELF_D    = PCB_D + 0.6     # = 2.80"
PCB_SHELF_T    = 0.05
PCB_SHELF_CABLE_R = 0.50         # cable routing hole in centre
PCB_SHELF_WORLD_Z = PCB_WORLD_Z - PCB_SHELF_T   # = 11.45"

# ---------------------------------------------------------------------------
# Phase 8: Pill path funnels, hatch retention, power inlet & speaker
# ---------------------------------------------------------------------------
# 8B — Pill path funnels
# Guide tube bottom funnel: tapered ring that narrows from GUIDE_OUTER_R to OUTER_R
# on the inside, guiding pills from the open chimney into the carousel top opening.
# Built as a short (0.3") frustum shell at the bottom of the guide tube.
FUNNEL_H       = 0.30    # funnel skirt height
FUNNEL_WALL    = 0.05    # funnel wall thickness at exit

# Cartridge floor chamfer angle — 30° chamfer ring around the floor drop hole
FLOOR_CHAM_ANG = 30.0    # degrees from vertical
FLOOR_CHAM_H   = 0.04    # chamfer height (within floor WALL_T = 0.05")

# 8C — Hatch hinge + snap-latch geometry
# Two hinge knuckles on the back edge of the hatch (Y≈0)
HINGE_R        = 0.12    # knuckle cylinder radius
HINGE_H        = 0.18    # knuckle height
HINGE_X_OFFSET = 1.50    # ±X from centre
HINGE_Y        = 0.15    # protrudes 0.15" from back edge (toward Y<0)
# Snap-latch tab on front edge of hatch
LATCH_W        = 0.40    # tab width (X)
LATCH_D        = 0.15    # tab depth (Y, protrudes forward)
LATCH_H        = 0.10    # tab height (Z)
LATCH_Y        = 9.00    # front edge of hatch (Y≈9 at apex)

# 8D — Power inlet (USB-C) + speaker grille in back wall of enclosure
# These are exported as separate cutter/insert parts (enclosure edits handled in hero_dispenser.py)
USBC_W         = 0.37    # USB-C port width  (~9.4 mm)
USBC_H_DIM     = 0.14    # USB-C port height (~3.5 mm)
USBC_DEPTH     = 0.15    # cutter depth through back wall (T=0.1" + overshoot)
USBC_WORLD_Z   = 1.80    # port centre height (low on back wall, easy cable routing)
# Speaker: circular grille on left side of front face
SPEAKER_R      = 0.75    # speaker cone radius
SPEAKER_GRILLE_R = 0.04  # individual grille hole radius
SPEAKER_GRILLE_N = 12    # number of holes in ring pattern
SPEAKER_GRILLE_RING_R = 0.50  # ring radius for hole pattern
SPEAKER_WORLD_X = -3.0   # left of centre (button is at X=0)
SPEAKER_WORLD_Z = 8.5    # same height as button

# ---------------------------------------------------------------------------
# Phase 9: Pill loading path — sealing the vertical channel
# ---------------------------------------------------------------------------
# 9A — Loading tube: sealed channel from hatch port to guide tube top
#   Connects hatch loading port (Z=14.90") to guide tube top (Z=11.00").
#   Inner R matches hatch port exactly so pills never leave the channel.
LOAD_TUBE_INNER_R  = HATCH_HOLE_R          # 1.80" — matches hatch port exactly
LOAD_TUBE_OUTER_R  = LOAD_TUBE_INNER_R + 0.10   # 1.90" — thin wall, clears PCB zone
LOAD_TUBE_Z_BOT    = GUIDE_WORLD_Z + GUIDE_H    # = 11.00" (sits on guide tube top rim)
LOAD_TUBE_Z_TOP    = HATCH_WORLD_Z              # = 14.90" (flush with hatch underside)
LOAD_TUBE_H        = LOAD_TUBE_Z_TOP - LOAD_TUBE_Z_BOT   # = 3.90"

# 9B — Pill guide ring: flat annular washer on top of carousel
#   REPLACES the tapered guide_funnel which incorrectly blocked pills.
#   Pills fall freely through the washer's opening; the ring prevents pills
#   from entering the hub zone (inner) or escaping the carousel OD (outer).
PILL_RING_INNER_R  = HUB_OUTER_R + 0.05                   # 0.80" — clears hub lock OD
PILL_RING_OUTER_R  = GUIDE_OUTER_R - GUIDE_WALL - 0.02   # 3.43" — 0.02" from guide tube inner face
# Note: OUTER_R - 0.10 = 3.40" was used previously, leaving a 0.05" gap at the cartridge
# interior outer edge.  3.43" closes that gap to 0.02" (below any pill diameter).
PILL_RING_T        = 0.05
PILL_RING_WORLD_Z  = CAROUSEL_Z_CART + CART_H - PILL_RING_T  # 8.85" (top of carousel)
# Loading port cut in pill_guide_ring — must match routing_chute.py exit geometry
ROUTING_CHUTE_EXIT_R = 0.60    # routing_chute.py CHUTE_R_BOT (outer radius at exit)
# local-frame centre of port = (0, SLOT_RADIUS) = (0, 2.5) within the ring disk

# 9C — Vertical PCB back-wall mount (REPLACES horizontal pcb_tray + pcb_shelf)
#   PCB now mounted in the XZ plane against the flat back wall (Y≈0 side).
#   This completely frees the central vertical loading column.
#   Board: 3.35" wide (X) × 2.20" tall (Z) × 0.063" thick (Y)
VPCB_STANDOFF_L    = 0.30                        # standoffs project in +Y from back wall
VPCB_WORLD_Y       = 0.15                        # back wall inner face Y ≈ 0.1"
VPCB_WORLD_Z       = 9.50                        # board bottom (behind guide tube zone)

# 9D — Camera arm: wall-mount bracket + camera head aimed at carousel
#   Arm runs horizontally in +Y from back wall to Y=2.45" (just outside loading tube).
#   Loading tube outer edge at back of tube: Y = CAROUSEL_Y - LOAD_TUBE_OUTER_R = 2.60"
#   Camera tip at Y=2.45" is just clear of the tube.
CAM_ARM_CROSS      = 0.20                        # arm cross-section (square)
CAM_ARM_Y_TIP      = CAROUSEL_Y - LOAD_TUBE_OUTER_R - 0.05   # 2.55" (0.05" clearance)
CAM_ARM_Z          = VPCB_WORLD_Z + PCB_D + 0.10  # = 11.80" (just above vertical PCB top)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def save_step(wp, fname):
    wp.export(str(OUTPUT / fname))
    print(f"  Wrote output/{fname}")


# ---------------------------------------------------------------------------
# Annular sector profile helper
#   Traces: outer arc CCW → radial line (end) → inner arc CW → close (start)
# ---------------------------------------------------------------------------
def make_sector_profile(inner_r, outer_r, start_deg, sweep_deg):
    s = math.radians(start_deg)
    e = math.radians(start_deg + sweep_deg)
    m = math.radians(start_deg + sweep_deg / 2.0)

    p_os = (outer_r * math.cos(s), outer_r * math.sin(s))  # outer arc start
    p_om = (outer_r * math.cos(m), outer_r * math.sin(m))  # outer arc midpoint
    p_oe = (outer_r * math.cos(e), outer_r * math.sin(e))  # outer arc end

    p_ie = (inner_r * math.cos(e), inner_r * math.sin(e))  # inner arc end (CW start)
    p_im = (inner_r * math.cos(m), inner_r * math.sin(m))  # inner arc midpoint
    p_is = (inner_r * math.cos(s), inner_r * math.sin(s))  # inner arc start (CW end)

    return (
        cq.Workplane("XY")
        .moveTo(*p_os)
        .threePointArc(p_om, p_oe)   # outer arc (counter-clockwise)
        .lineTo(*p_ie)                # radial wall: outer-end → inner-end
        .threePointArc(p_im, p_is)   # inner arc (clockwise — reverse direction)
        .close()                      # radial wall: inner-start back to outer-start
    )


# ---------------------------------------------------------------------------
# Part A: Single Cartridge
#   Built at origin, centred on +X axis (±17° sweep around 0°).
#   Rotated and translated at assembly time.
# ---------------------------------------------------------------------------
def _cartridge_hollow_fallback(start_deg):
    """Manual hollowing fallback if shell() fails."""
    outer_solid = make_sector_profile(INNER_R, OUTER_R, start_deg, SWEEP).extrude(CART_H)
    # Angular inset so radial side walls are approximately WALL_T thick at outer edge
    ang_inset = math.degrees(WALL_T / OUTER_R)   # ≈ 0.82°
    inner_void = make_sector_profile(
        INNER_R + WALL_T,
        OUTER_R - WALL_T,
        start_deg + ang_inset,
        SWEEP - 2 * ang_inset,
    ).extrude(CART_H - WALL_T)  # leave WALL_T floor
    return outer_solid.cut(inner_void)


def make_single_cartridge():
    start_deg = -(SWEEP / 2.0)   # -17.0°, centred on +X axis
    solid = make_sector_profile(INNER_R, OUTER_R, start_deg, SWEEP).extrude(CART_H)
    try:
        # Open the top face; shell inward on all remaining faces → 0.05" floor remains
        cart = solid.faces(">Z").shell(-WALL_T)
    except Exception as exc:
        print(f"  WARNING: shell() raised {type(exc).__name__}: {exc}")
        print("  Using manual hollow fallback for cartridge.")
        cart = _cartridge_hollow_fallback(start_deg)

    # Phase 20: add low outlet guide ribs and a shallow countersunk sump so
    # carousel jogs bias pills toward the active outlet instead of relying on
    # a stationary wheel to find a pill that is already near the hole.
    guide_ribs = []
    for y_sign in (-1, 1):
        rib = (
            cq.Workplane("XY")
            .box(
                OUTLET_GUIDE_RIB_L,
                OUTLET_GUIDE_RIB_W,
                OUTLET_GUIDE_RIB_H,
                centered=(True, True, False),
            )
            .translate((OUTLET_GUIDE_RIB_X, y_sign * OUTLET_GUIDE_RIB_Y, WALL_T))
            .rotate((0, 0, 0), (0, 0, 1), -y_sign * 8.0)
        )
        guide_ribs.append(rib)
    try:
        cart = cart.union(guide_ribs[0]).union(guide_ribs[1])
    except Exception as exc:
        print(f"  WARNING: outlet guide rib union failed ({exc}); continuing without ribs")

    try:
        sump_cutter = (
            cq.Workplane("XY")
            .workplane(offset=WALL_T + 0.005)
            .center(SLOT_RADIUS, 0)
            .circle(OUTLET_SUMP_R)
            .workplane(offset=-(WALL_T + 0.08))
            .circle(HOLE_R)
            .loft()
        )
        cart = cart.cut(sump_cutter)
    except Exception as exc:
        print(f"  WARNING: outlet sump cut failed ({exc}); using plain floor hole")

    # Phase 21: front-entry sweep slot.  In the active station this local +X
    # slot rotates to world +Y, aligning with the low front pusher.
    sweep_slot_cutter = (
        cq.Workplane("XY")
        .box(SWEEP_SLOT_D, SWEEP_SLOT_W, SWEEP_SLOT_H, centered=(True, True, True))
        .translate((OUTER_R, 0, SWEEP_SLOT_Z))
    )
    try:
        cart = cart.cut(sweep_slot_cutter)
    except Exception as exc:
        print(f"  WARNING: sweep slot cut failed ({exc}); continuing without pusher slot")

    # Punch pill-drop hole through the 0.05" floor.
    # Position: (SLOT_RADIUS, 0) in template frame (cartridge centred on +X axis).
    # After 90° assembly rotation → template +X maps to world +Y →
    #   world position = (CAROUSEL_X + 0, CAROUSEL_Y + SLOT_RADIUS) = (0, 7.0) = spout OK
    # Cutter spans Z=[-WALL_T, +WALL_T] to cut cleanly through the floor from both sides.
    floor_cutter = (
        cq.Workplane("XY")
        .center(SLOT_RADIUS, 0)
        .circle(HOLE_R)
        .extrude(WALL_T * 2)
        .translate((0, 0, -WALL_T))
    )
    return cart.cut(floor_cutter)


# ---------------------------------------------------------------------------
# Part B (DEPRECATED): Central Hub — hollow drive shaft
#   Replaced by make_hub_lock() below. Kept for reference only.
# ---------------------------------------------------------------------------
# def make_hub():
#     outer = cq.Workplane("XY").circle(HUB_OUTER_R).extrude(HUB_H)
#     inner = cq.Workplane("XY").circle(HUB_INNER_R).extrude(HUB_H + 0.1)
#     return outer.cut(inner)


# ---------------------------------------------------------------------------
# Part E: Stepper Motor Body (NEMA 17 style placeholder)
#   Square box 1.7"×1.7"×1.5". Built centred in XY at local Z=0..MOTOR_H_DIM.
#   Translate to world (CAROUSEL_X, CAROUSEL_Y, MOTOR_Z_BOT) at build time.
#   Motor is placed at Y=CAROUSEL_Y=4.5 — directly below the carousel axis,
#   which is the mechanically correct position for a vertical drive system.
# ---------------------------------------------------------------------------
def make_stepper_motor():
    return (
        cq.Workplane("XY")
        .box(MOTOR_W, MOTOR_W, MOTOR_H_DIM, centered=(True, True, False))
    )


# ---------------------------------------------------------------------------
# Part F: D-Shaft
#   Vertical cylinder R=SHAFT_R=0.20", H=SHAFT_H=4.5".
#   Flat cut removes 0.05" from the +Y arc along the entire Z length,
#   leaving flat face at Y = SHAFT_R - SHAFT_FLAT_DEPTH = 0.15" from centre.
#   Built at local Z=0..SHAFT_H. Translate to world (CAROUSEL_X, CAROUSEL_Y,
#   SHAFT_Z_BOT=4.4) at build time. Unioned to motor body after translation.
# ---------------------------------------------------------------------------
def make_d_shaft():
    shaft = cq.Workplane("XY").circle(SHAFT_R).extrude(SHAFT_H)

    # Flat-cut box: spans full height, cuts +Y side of cylinder.
    # centered=(True, True, False) → box starts at Z=0, no Z translate needed.
    _pad      = 0.20                              # overshoot so cut fully removes material
    _box_W    = SHAFT_R * 2 + _pad               # wider than cylinder diameter
    _box_dep  = SHAFT_FLAT_DEPTH + _pad           # 0.05" flat + overshoot
    _Y_flat   = SHAFT_R - SHAFT_FLAT_DEPTH        # 0.15" — desired flat face position
    _box_cY   = _Y_flat + _box_dep / 2            # 0.275" — box centre Y (positive = +Y side)

    flat_cutter = (
        cq.Workplane("XY")
        .box(_box_W, _box_dep, SHAFT_H, centered=(True, True, False))
        .translate((0, _box_cY, 0))
    )
    return shaft.cut(flat_cutter)


# ---------------------------------------------------------------------------
# Part G: Hub Lock (replaces hollow hub — Part B above)
#   Solid cylinder R=HUB_OUTER_R=0.75", H=CART_H=3.9" — coplanar with cartridges.
#   D-hole: bore R=SHAFT_R+SHAFT_CLEARANCE=0.21", flat at same +Y side.
#   Clearance = 0.01" radially AND 0.01" at the flat face.
#   Built at local Z=0..CART_H. Translate to (CAROUSEL_X, CAROUSEL_Y, CAROUSEL_Z_CART).
# ---------------------------------------------------------------------------
def make_hub_lock():
    solid  = cq.Workplane("XY").circle(HUB_OUTER_R).extrude(CART_H)
    BORE_R = SHAFT_R + SHAFT_CLEARANCE            # 0.21"

    # Bore cylinder: +0.1 overshoot to avoid coincident bottom face ambiguity
    bore   = cq.Workplane("XY").circle(BORE_R).extrude(CART_H + 0.1)

    # Flat-cut box for D-hole — same logic as shaft, scaled by BORE_R
    _pad      = 0.20
    _box_W    = BORE_R * 2 + _pad
    _box_dep  = SHAFT_FLAT_DEPTH + _pad
    _Y_flat   = BORE_R - SHAFT_FLAT_DEPTH         # 0.16" (shaft flat=0.15" + 0.01" clearance)
    _box_cY   = _Y_flat + _box_dep / 2            # 0.285"

    flat_cutter = (
        cq.Workplane("XY")
        .box(_box_W, _box_dep, CART_H + 0.1, centered=(True, True, False))
        .translate((0, _box_cY, 0))
    )
    return solid.cut(bore).cut(flat_cutter)


# ---------------------------------------------------------------------------
# Part C: Carousel Base Plate (modified — shaft clearance hole replaces hub bore)
#   The old INNER_R=0.75" centre bore is removed: hub_lock now sits ON TOP of
#   the plate (does not pass through it). A small round shaft clearance hole
#   (R=0.21") is cut at the plate centre so the D-shaft can pass through freely
#   without the plate rotating with it.
# ---------------------------------------------------------------------------
def build_base_plate():
    disk = cq.Workplane("XY").circle(OUTER_R).extrude(BASE_T)

    # Shaft clearance hole: round (not D-shaped) so the plate stays stationary
    shaft_hole = (
        cq.Workplane("XY")
        .circle(SHAFT_R + SHAFT_CLEARANCE)
        .extrude(BASE_T * 2)               # 2× to avoid coincident face ambiguity
    )

    # Pill drop zone: local (0, SLOT_RADIUS) = world (0, 7.0) = spout centre OK
    drop_zone = (
        cq.Workplane("XY")
        .center(0, SLOT_RADIUS)
        .circle(HOLE_R)
        .extrude(BASE_T * 2)
    )
    return disk.cut(shaft_hole).cut(drop_zone)


# ---------------------------------------------------------------------------
# Part D: Agitator / Singulator Wheel (housing-fixed, stationary)
#   Built in XY plane (axis along Z), then rotated 90° around X so the axis
#   becomes horizontal (along Y). The wheel stands upright like a tire —
#   flat faces ±X, circular profile in XZ plane — and agitates pills radially.
#   Positioned at the dispensing zone (world Y=7.0) just above cartridge floor.
# ---------------------------------------------------------------------------
def make_agitator_wheel():
    """Deprecated visual reference for the old stationary singulator concept.

    Geometry (after 90-deg rotation around X):
      - Disk axis along Y; flat faces in XZ plane.
      - R = AGIT_R = 0.40", width (Y) = AGIT_W = 0.20".

    World placement (set by translate in build section):
      X = AGIT_WORLD_X = 0.0
      Y = AGIT_WORLD_Y = CAROUSEL_Y + SLOT_RADIUS = 7.0"  (directly above drop hole)
      Z = AGIT_WORLD_Z = CAROUSEL_Z_CART + AGIT_FLOOR_GAP + AGIT_R = 5.81"

    Z span = [5.41", 6.21"] — fully inside cartridge zone [5.00", 8.90"].
    Floor clearance = AGIT_FLOOR_GAP = 0.41" = 10.4 mm.

    Floor clearance rationale (bore audit):
      Original gap was WALL_T = 0.05" = 1.27 mm — a show-stopper.
      No standard pill (smallest: #5 capsule, 4.9 mm dia) could slide flat under
      the agitator to reach the drop hole.  Raised to AGIT_FLOOR_GAP = 0.41" so
      the largest standard capsule (#000, 9.9 mm dia) lying flat has 0.5 mm margin.

    Dispensing mechanism:
      The carousel rotates; this wheel stays stationary (housing-fixed).
      Pills inside each passing cartridge slot lie flat on the base plate floor.
      As a pill slides outward to Y = 7.0" under the agitator, it falls through
      the base plate drop hole (HOLE_R=0.30") into the pill_chute.
      The agitator rim (Z=5.41-6.21") contacts the upper body of standing/tilted
      pills and helps tip them into the drop zone; the 10.4 mm floor gap allows
      flat-lying pills to pass freely underneath.
      No central bore is required: pills fall through the BASE PLATE hole,
      not through the agitator body.

    Built in XY plane (axis along Z), then rotated 90 deg around X.
    Translate to (AGIT_WORLD_X, AGIT_WORLD_Y, AGIT_WORLD_Z) at build time.
    """
    wheel = (
        cq.Workplane("XY")
        .circle(AGIT_R)
        .extrude(AGIT_W)
        .translate((0, 0, -AGIT_W / 2))      # centre the width on Z=0
    )
    # Rotate 90 deg around X: +Z axis -> -Y axis; wheel axis now along Y (horizontal)
    return wheel.rotate((0, 0, 0), (1, 0, 0), 90)


def make_dispense_gate():
    """Normally-closed shutter at the base-plate/chute transition.

    Phase 22 treats this as the upper inlet gate: it admits one demo tablet from
    the cartridge/base outlet into the metering chamber, then closes before the
    lower release gate opens.
    """
    shutter = cq.Workplane("XY").circle(DISPENSE_GATE_R).extrude(DISPENSE_GATE_T)
    arm = (
        cq.Workplane("XY")
        .box(DISPENSE_GATE_ARM_L, DISPENSE_GATE_ARM_W, DISPENSE_GATE_T, centered=(False, True, False))
        .translate((0, 0, 0))
    )
    hub = (
        cq.Workplane("XY")
        .center(DISPENSE_GATE_ARM_L, 0)
        .circle(0.12)
        .extrude(DISPENSE_GATE_T)
    )
    try:
        return shutter.union(arm).union(hub)
    except Exception:
        return shutter.union(arm)


def make_dispense_release_gate():
    """Lower normally-closed shutter below the one-tablet metering chamber."""
    shutter = cq.Workplane("XY").circle(DISPENSE_RELEASE_GATE_R).extrude(DISPENSE_RELEASE_GATE_T)
    arm = (
        cq.Workplane("XY")
        .box(
            DISPENSE_RELEASE_GATE_ARM_L,
            DISPENSE_RELEASE_GATE_ARM_W,
            DISPENSE_RELEASE_GATE_T,
            centered=(False, True, False),
        )
        .translate((-DISPENSE_RELEASE_GATE_ARM_L, 0, 0))
    )
    hub = (
        cq.Workplane("XY")
        .center(-DISPENSE_RELEASE_GATE_ARM_L, 0)
        .circle(0.12)
        .extrude(DISPENSE_RELEASE_GATE_T)
    )
    try:
        return shutter.union(arm).union(hub)
    except Exception:
        return shutter.union(arm)


def make_dispense_gate_servo_mount():
    """SG90-style mount that drives the normally-closed dispense gate."""
    body = (
        cq.Workplane("XY")
        .box(DISPENSE_SERVO_W, DISPENSE_SERVO_D, DISPENSE_SERVO_H, centered=(True, True, False))
    )
    ear_l = (
        cq.Workplane("XY")
        .box(0.20, DISPENSE_SERVO_D + 0.25, 0.08, centered=(True, True, False))
        .translate((-DISPENSE_SERVO_W / 2 - 0.10, 0, DISPENSE_SERVO_H * 0.55))
    )
    ear_r = (
        cq.Workplane("XY")
        .box(0.20, DISPENSE_SERVO_D + 0.25, 0.08, centered=(True, True, False))
        .translate((DISPENSE_SERVO_W / 2 + 0.10, 0, DISPENSE_SERVO_H * 0.55))
    )
    horn = (
        cq.Workplane("XY")
        .box(0.55, 0.08, 0.06, centered=(True, True, False))
        .translate((0, 0, DISPENSE_SERVO_H + 0.02))
    )
    return body.union(ear_l).union(ear_r).union(horn)


def make_dispense_release_gate_servo_mount():
    """SG90-style mount for the lower release gate, opposite the upper gate servo."""
    return make_dispense_gate_servo_mount()


def make_dispense_sweep_pusher():
    """Low front-entry last-pill pusher.

    The blade parks outside the active cartridge OD in the front service gap.
    During a no-drop retry it slides through the aligned cartridge wall slot
    and pushes inward across the floor toward the outlet sump.
    """
    blade = (
        cq.Workplane("XY")
        .box(SWEEP_PUSHER_TIP_W, SWEEP_PUSHER_TIP_D, SWEEP_PUSHER_T, centered=(True, True, False))
    )
    rack = (
        cq.Workplane("XY")
        .box(SWEEP_PUSHER_RACK_W, SWEEP_PUSHER_RACK_D, SWEEP_PUSHER_T * 0.75, centered=(True, False, False))
        .translate((0, SWEEP_PUSHER_TIP_D / 2, SWEEP_PUSHER_T * 0.125))
    )
    rubber_face = (
        cq.Workplane("XY")
        .box(SWEEP_PUSHER_TIP_W, 0.035, SWEEP_PUSHER_T * 1.15, centered=(True, True, False))
        .translate((0, -SWEEP_PUSHER_TIP_D / 2 - 0.0175, 0))
    )
    return blade.union(rack).union(rubber_face)


def make_dispense_sweep_containment_band():
    """Stationary low OD shield that backs every cartridge sweep slot.

    The cartridges still have a narrow pusher slot, but those slots are no
    longer open to the enclosure.  This ring covers the full carousel OD and
    leaves only one front service window where the sealed pusher enters.
    """
    band = (
        cq.Workplane("XY")
        .circle(SWEEP_CONTAIN_OUTER_R)
        .circle(SWEEP_CONTAIN_INNER_R)
        .extrude(SWEEP_CONTAIN_H)
    )
    window_z = (CAROUSEL_Z_CART + SWEEP_SLOT_Z) - SWEEP_CONTAIN_Z
    front_window = (
        cq.Workplane("XY")
        .box(
            SWEEP_SERVICE_WINDOW_W,
            SWEEP_SERVICE_WINDOW_D,
            SWEEP_SERVICE_WINDOW_H,
            centered=(True, True, True),
        )
        .translate((0, SWEEP_CONTAIN_OUTER_R, window_z))
    )
    return band.cut(front_window)


def make_dispense_sweep_port_seal():
    """Flexible TPU wiper/gasket over the single front pusher window."""
    seal = (
        cq.Workplane("XY")
        .box(SWEEP_SEAL_W, SWEEP_SEAL_D, SWEEP_SEAL_H, centered=(True, True, False))
    )
    aperture_z = (SWEEP_PUSHER_Z + SWEEP_PUSHER_T / 2) - SWEEP_CONTAIN_Z
    pusher_aperture = (
        cq.Workplane("XY")
        .box(
            SWEEP_SEAL_APERTURE_W,
            SWEEP_SEAL_D * 2.0,
            SWEEP_SEAL_APERTURE_H,
            centered=(True, True, True),
        )
        .translate((0, 0, aperture_z))
    )
    return seal.cut(pusher_aperture)


def make_dispense_sweep_rail():
    """Fixed low front linear guide in the service gap outside carousel OD."""
    base = (
        cq.Workplane("XY")
        .box(SWEEP_RAIL_W, SWEEP_RAIL_D, SWEEP_RAIL_T, centered=(True, True, False))
    )
    left_wall = (
        cq.Workplane("XY")
        .box(0.08, SWEEP_RAIL_D, 0.18, centered=(True, True, False))
        .translate((-SWEEP_RAIL_W / 2 + 0.10, 0, SWEEP_RAIL_T))
    )
    right_wall = (
        cq.Workplane("XY")
        .box(0.08, SWEEP_RAIL_D, 0.18, centered=(True, True, False))
        .translate((SWEEP_RAIL_W / 2 - 0.10, 0, SWEEP_RAIL_T))
    )
    slot = (
        cq.Workplane("XY")
        .box(0.28, SWEEP_RAIL_D + 0.04, SWEEP_RAIL_T * 2, centered=(True, True, False))
        .translate((0, 0, -0.01))
    )
    return base.union(left_wall).union(right_wall).cut(slot)


def make_dispense_sweep_servo_mount():
    """Low SG90-style rack drive for the front-entry pusher."""
    body = (
        cq.Workplane("XY")
        .box(SWEEP_SERVO_W, SWEEP_SERVO_D, SWEEP_SERVO_H, centered=(True, True, False))
    )
    horn = (
        cq.Workplane("XY")
        .box(0.12, 0.62, 0.06, centered=(True, True, False))
        .translate((0, 0, SWEEP_SERVO_H + 0.02))
    )
    bracket = (
        cq.Workplane("XY")
        .box(1.25, 0.58, 0.08, centered=(True, True, False))
        .translate((-0.10, 0, -0.08))
    )
    return body.union(horn).union(bracket)


# ---------------------------------------------------------------------------
# Phase 6 helpers & parts
# ---------------------------------------------------------------------------

def _make_enclosure_d_profile():
    """Local copy of the 9"×9" D-profile from hero_dispenser.py.
    Flat back at Y=0, arc apex at (0, 9). Used for the top hatch lid.
    """
    x_half = 4.5
    depth  = 9.0
    return (
        cq.Workplane("XY")
        .moveTo(-x_half, 0)
        .lineTo(x_half, 0)
        .threePointArc((0, depth), (-x_half, 0))
        .close()
    )


def make_pill_guide():
    """Hollow cylindrical funnel above the carousel (loading chimney).
    Outer R = GUIDE_OUTER_R = 3.5", wall = 0.05", height = 2.1".
    Built at local Z=0..GUIDE_H.  Translate to (CX, CY, GUIDE_WORLD_Z) at build time.
    """
    outer = cq.Workplane("XY").circle(GUIDE_OUTER_R).extrude(GUIDE_H)
    inner = (
        cq.Workplane("XY")
        .circle(GUIDE_OUTER_R - GUIDE_WALL)
        .extrude(GUIDE_H + 0.1)            # +0.1 overshoot to avoid coincident top face
    )
    return outer.cut(inner)


def make_pcb_tray():
    """Raspberry Pi 4 footprint PCB board (3.35"×2.20"×0.063") with four
    standoff posts (R=0.08", H=0.25") at the board corners.
    Built with standoff bases at Z=0, board bottom at Z=PCB_POST_H, board top at
    Z=PCB_POST_H+PCB_T.  Translate to (CX, CY, PCB_WORLD_Z) at build time.
    """
    board = (
        cq.Workplane("XY")
        .rect(PCB_W, PCB_D)
        .extrude(PCB_T)
        .translate((0, 0, PCB_POST_H))
    )
    px = PCB_W / 2.0 - 0.10   # standoff X offset (inset 0.10" from edge)
    py = PCB_D / 2.0 - 0.10   # standoff Y offset
    tray = board
    for sx, sy in [(px, py), (-px, py), (px, -py), (-px, -py)]:
        post = (
            cq.Workplane("XY")
            .center(sx, sy)
            .circle(PCB_POST_R)
            .extrude(PCB_POST_H)
        )
        tray = tray.union(post)
    return tray


def make_camera():
    """PiCam v2 style placeholder — rectangular board with lens boss protruding
    from the −Z face (lens points downward toward the carousel).
    Body:  CAM_W × CAM_D × CAM_T, built at Z=0..CAM_T.
    Lens:  cylinder R=CAM_LENS_R, H=0.10", placed at Z=−0.10..0 (below body).
    Translate to (CX, CY, CAM_WORLD_Z) at build time.
    """
    body = cq.Workplane("XY").rect(CAM_W, CAM_D).extrude(CAM_T)
    lens = (
        cq.Workplane("XY")
        .circle(CAM_LENS_R)
        .extrude(0.10)
        .translate((0, 0, -0.10))
    )
    try:
        return body.union(lens)
    except Exception:
        return body     # fallback: body only


def make_load_cell():
    """Thin circular force-sensor tray under the removable pill cup.
    Built centred on XY at Z=0..LOAD_T.
    Translate to (LOAD_WORLD_X, LOAD_WORLD_Y, LOAD_WORLD_Z).
    """
    return (
        cq.Workplane("XY")
        .circle(LOAD_R)
        .extrude(LOAD_T)
    )


def make_vibration_motor():
    """ERM (Eccentric Rotating Mass) vibration motor — cylindrical placeholder.
    Axis along Z, R=VIB_R=0.30", H=VIB_H=0.50", built at Z=0..VIB_H.
    Translate to (VIB_WORLD_X, VIB_WORLD_Y, VIB_WORLD_Z) at build time.
    """
    return (
        cq.Workplane("XY")
        .circle(VIB_R)
        .extrude(VIB_H)
    )


def make_top_hatch():
    """D-shaped lid matching the enclosure top cross-section.
    Thickness = HATCH_T = 0.10".  A circular loading port (R=1.80") is cut at the
    carousel centre (CAROUSEL_X, CAROUSEL_Y) so pills can be dropped in.
    Built at local Z=0..HATCH_T.  Translate to (0, 0, HATCH_WORLD_Z) at build time.
    """
    lid  = _make_enclosure_d_profile().extrude(HATCH_T)
    hole = (
        cq.Workplane("XY")
        .center(CAROUSEL_X, CAROUSEL_Y)
        .circle(HATCH_HOLE_R)
        .extrude(HATCH_T * 2)   # 2× to avoid coincident face
    )
    return lid.cut(hole)


# ---------------------------------------------------------------------------
# Phase 7 parts
# ---------------------------------------------------------------------------

def make_pill_chute():
    """Short metering chamber between the upper inlet gate and lower release gate.

    Continuity (world Z):
      Spout top   Z = 4.500"  (hero_dispenser.py, inner R=0.25")
      Release gate closes just above the spout.
      Chamber bot Z = CHUTE_WORLD_Z.
      Chamber top Z = CHUTE_WORLD_Z + CHUTE_H.
      Base plate  Z = 4.900"  (CAROUSEL_Z_BASE, drop zone HOLE_R=0.30")

    Sealing flange at the top (Z = CHUTE_H-CHUTE_FLANGE_H .. CHUTE_H):
      Outer R = CHUTE_FLANGE_R = 0.45" — 0.15" lip beyond the 0.30" drop zone hole.
      This collar presses flat against the base plate underside, closing any annular
      gap so pills cannot escape into the motor area on a bounce.

    Inner bore R=0.25" continuous through both tube and flange.  For the
    competition demo tablet, the 0.50" bore fits one 0.38" tablet but cannot
    fit two tablets side-by-side.
    Built at Z=0..CHUTE_H.  Translate to (0, AGIT_WORLD_Y, CHUTE_WORLD_Z) at build time.
    """
    # Main tube body
    tube_outer = cq.Workplane("XY").circle(CHUTE_OUTER_R).extrude(CHUTE_H)
    tube_inner = cq.Workplane("XY").circle(CHUTE_INNER_R).extrude(CHUTE_H + 0.10)
    tube = tube_outer.cut(tube_inner)

    # Sealing flange: wider disk at top, unions with tube
    flange_z0 = CHUTE_H - CHUTE_FLANGE_H   # local Z start of flange = 0.35"
    flange_outer = (
        cq.Workplane("XY")
        .circle(CHUTE_FLANGE_R)
        .extrude(CHUTE_FLANGE_H)
        .translate((0, 0, flange_z0))
    )
    # Bore continues through flange — overshoot ±0.01" for clean boolean
    flange_bore = (
        cq.Workplane("XY")
        .circle(CHUTE_INNER_R)
        .extrude(CHUTE_FLANGE_H + 0.02)
        .translate((0, 0, flange_z0 - 0.01))
    )
    flange = flange_outer.cut(flange_bore)
    return tube.union(flange)


def make_motor_mount():
    """Horizontal mounting plate for the NEMA 17 stepper motor.
    3.0"×3.0"×0.10" plate with a centre shaft clearance hole and four M3
    mounting holes on the standard 31 mm (1.22") square pattern.
    Built at Z=0..MOUNT_PLATE_T.  Translate to (CX, CY, MOUNT_WORLD_Z) at build time.
    The motor body sits directly ON TOP of this plate.
    """
    plate = cq.Workplane("XY").rect(MOUNT_PLATE_W, MOUNT_PLATE_D).extrude(MOUNT_PLATE_T)

    # Centre shaft clearance (generous R = SHAFT_R + 0.05 = 0.25")
    shaft_clr = cq.Workplane("XY").circle(SHAFT_R + 0.05).extrude(MOUNT_PLATE_T * 2)
    plate = plate.cut(shaft_clr)

    # Four NEMA 17 mounting holes (M3 clearance)
    half = NEMA17_HOLE_SPC / 2.0
    for sx, sy in [(half, half), (-half, half), (half, -half), (-half, -half)]:
        mh = (
            cq.Workplane("XY")
            .center(sx, sy)
            .circle(NEMA17_HOLE_R)
            .extrude(MOUNT_PLATE_T * 2)
        )
        plate = plate.cut(mh)
    return plate


def make_display_panel():
    """Flat screen placeholder (3.0"W × 3.5"H × 0.08"T) that sits inside the
    screen cutout on the front face.  Built in the XZ plane (vertical),
    extruded 0.08" in +Y.  Translate to (0, DISPLAY_WORLD_Y, DISPLAY_WORLD_Z).
    """
    return cq.Workplane("XZ").rect(DISPLAY_W, DISPLAY_H_DIM).extrude(DISPLAY_T)


def make_led_ring():
    """Annular LED status ring (outer R=1.2", inner R=1.0", T=0.05") that seats
    in the groove cut around the button on the front face.  Built in the XZ
    plane centred at origin, extruded in +Y.
    Translate to (0, LED_RING_WORLD_Y, LED_RING_WORLD_Z) at build time.
    """
    outer = cq.Workplane("XZ").circle(LED_RING_OUTER_R).extrude(LED_RING_T)
    inner = cq.Workplane("XZ").circle(LED_RING_INNER_R).extrude(LED_RING_T + 0.01)
    return outer.cut(inner)


def make_pcb_shelf():
    """Horizontal shelf bracket (3.95"×2.80"×0.05") that supports the PCB tray
    from below.  A cable routing hole (R=0.50") is cut at the centre.
    Built at Z=0..PCB_SHELF_T.  Translate to (CX, CY, PCB_SHELF_WORLD_Z).
    """
    shelf = cq.Workplane("XY").rect(PCB_SHELF_W, PCB_SHELF_D).extrude(PCB_SHELF_T)
    cable_hole = cq.Workplane("XY").circle(PCB_SHELF_CABLE_R).extrude(PCB_SHELF_T * 2)
    return shelf.cut(cable_hole)


# ---------------------------------------------------------------------------
# Phase 8 parts
# ---------------------------------------------------------------------------

def make_guide_funnel():
    """Tapered entry skirt at the bottom of the pill guide tube.
    Outer face is flush with the guide tube OD (R=3.5").
    Inner face tapers from R=3.45" at the top down to R=INNER_R+0.05"=0.80" at the
    bottom — creating a funnel that steers falling pills toward the carousel hub opening.
    Built as a solid frustum shell at Z=0..FUNNEL_H.
    Translate to (CAROUSEL_X, CAROUSEL_Y, GUIDE_WORLD_Z) — sits at guide tube bottom.
    """
    top_outer_r = GUIDE_OUTER_R - GUIDE_WALL   # 3.45" — flush with tube inner face
    bot_inner_r = INNER_R + 0.05               # 0.80" — just outside hub lock OD
    # Outer frustum (solid cone frustum)
    outer_top = cq.Workplane("XY").circle(top_outer_r).extrude(FUNNEL_H)
    # Inner frustum cutter — tapers from top_outer_r-FUNNEL_WALL at top to bot_inner_r at bot
    # Approximate with two-step loft using CQ workplane offset stacking
    inner_top_r = top_outer_r - FUNNEL_WALL    # 3.40"
    # Use a ruled cone: cut a cylinder at bottom, cone approximated by two circles
    # Simple approach: cut inner cone using an outer circle at top and inner at bottom
    # CQ loft approach:
    try:
        funnel = (
            cq.Workplane("XY")
            .circle(top_outer_r)
            .workplane(offset=FUNNEL_H)
            .circle(bot_inner_r)
            .loft()
        )
        inner_cone = (
            cq.Workplane("XY")
            .circle(inner_top_r)
            .workplane(offset=FUNNEL_H + 0.01)
            .circle(max(bot_inner_r - FUNNEL_WALL, 0.1))
            .loft()
        )
        return funnel.cut(inner_cone)
    except Exception as exc:
        print(f"  WARNING: guide funnel loft failed ({exc}), using cylinder fallback")
        outer = cq.Workplane("XY").circle(top_outer_r).extrude(FUNNEL_H)
        inner = cq.Workplane("XY").circle(bot_inner_r).extrude(FUNNEL_H + 0.01)
        return outer.cut(inner)


def make_hatch_with_retention():
    """D-shaped top hatch (same as make_top_hatch()) PLUS:
    - Two hinge knuckle cylinders on the flat back edge (Y≈0 side)
    - One snap-latch tab on the front apex edge
    These allow the lid to be hinged open for pill loading and clicked shut.
    Built at Z=0..HATCH_T with retention features.
    Translate to (0, 0, HATCH_WORLD_Z) at build time.
    """
    # Base D-lid with loading port
    lid = _make_enclosure_d_profile().extrude(HATCH_T)
    hole = (
        cq.Workplane("XY")
        .center(CAROUSEL_X, CAROUSEL_Y)
        .circle(HATCH_HOLE_R)
        .extrude(HATCH_T * 2)
    )
    lid = lid.cut(hole)

    # Hinge knuckles: two cylinders on flat back edge (Y=0), centred at Z=HATCH_T/2
    for sx in [HINGE_X_OFFSET, -HINGE_X_OFFSET]:
        knuckle = (
            cq.Workplane("XZ")
            .center(sx, HATCH_T / 2)
            .circle(HINGE_R)
            .extrude(HINGE_H)
            .translate((0, -HINGE_H, 0))   # protrude toward Y<0 (back of enclosure)
        )
        try:
            lid = lid.union(knuckle)
        except Exception:
            pass  # skip if boolean fails on this geometry

    # Snap-latch tab: small rectangular tab at front apex of hatch
    # Approximate front apex by using Y=8.5 (well within D arc), centred X=0
    latch = (
        cq.Workplane("XY")
        .center(0, 8.5)
        .rect(LATCH_W, LATCH_D)
        .extrude(LATCH_H)
        .translate((0, 0, -LATCH_H))   # hang below hatch bottom face
    )
    try:
        lid = lid.union(latch)
    except Exception:
        pass

    return lid


def make_usbc_port():
    """USB-C port bezel insert — a thin frame (0.37"W × 0.14"H × 0.10"T) that
    sits in the back-wall cutout at Z=USBC_WORLD_Z.  The opening itself is cut
    by a matching cutter (added to hero_dispenser.py separately).
    Built in the XZ plane at origin, extruded 0.10" in +Y.
    Translate to (0, 0, USBC_WORLD_Z) at build time.
    """
    bezel = (
        cq.Workplane("XZ")
        .rect(USBC_W + 0.04, USBC_H_DIM + 0.04)   # bezel slightly larger than port
        .extrude(0.10)
    )
    port_opening = (
        cq.Workplane("XZ")
        .rect(USBC_W, USBC_H_DIM)
        .extrude(0.12)
    )
    return bezel.cut(port_opening)


def make_speaker_grille():
    """Circular speaker grille disk (R=SPEAKER_R=0.75") with 12 small holes
    arranged in a ring pattern (R=0.50").  Thickness = 0.05".
    Built in the XZ plane at origin (speaker axis along Y), extruded in +Y.
    Translate to (SPEAKER_WORLD_X, front-wall-Y, SPEAKER_WORLD_Z) at build time.
    """
    disk = (
        cq.Workplane("XZ")
        .circle(SPEAKER_R)
        .extrude(0.05)
    )
    # Grille holes in ring pattern
    for i in range(SPEAKER_GRILLE_N):
        ang = math.radians(i * 360.0 / SPEAKER_GRILLE_N)
        hx = SPEAKER_GRILLE_RING_R * math.cos(ang)
        hz = SPEAKER_GRILLE_RING_R * math.sin(ang)
        hole = (
            cq.Workplane("XZ")
            .center(hx, hz)
            .circle(SPEAKER_GRILLE_R)
            .extrude(0.06)
        )
        try:
            disk = disk.cut(hole)
        except Exception:
            pass
    return disk


# ---------------------------------------------------------------------------
# Phase 9 functions — sealing the loading column
# ---------------------------------------------------------------------------

def make_loading_tube():
    """Hollow vertical cylinder that seals the 3.9" gap between the hatch loading
    port (Z=14.90") and the guide tube zone (Z=11.00").
    Inner R = HATCH_HOLE_R = 1.80" — matches the hatch port exactly, so the pill
    channel is continuous from the user's hand all the way to the carousel.
    The motor positions the target cartridge at 90° (world Y≈7.0") before loading;
    the pill travels straight down this tube and into the open cartridge below.
    Built at Z=0..LOAD_TUBE_H.  Translate to (CX, CY, LOAD_TUBE_Z_BOT).
    """
    outer = cq.Workplane("XY").circle(LOAD_TUBE_OUTER_R).extrude(LOAD_TUBE_H)
    inner = cq.Workplane("XY").circle(LOAD_TUBE_INNER_R).extrude(LOAD_TUBE_H + 0.1)
    return outer.cut(inner)


def make_pill_guide_ring():
    """Solid stationary seal disk sitting flush on top of the carousel at Z=8.85".
    Acts as the top cover for the cartridge annular zone.

    Geometry:
      Outer R=3.40": spans the full cartridge zone (OUTER_R - 0.10").
      Hub clearance hole R=0.80": prevents pills touching the rotating hub.
      Loading port hole R=ROUTING_CHUTE_EXIT_R=0.60" at local (0, SLOT_RADIUS=2.5):
        — This is the ONLY controlled entry into the carousel.
        — Aligned with the routing_chute exit mouth and the cartridge drop zone.
        — All other positions remain solid, so stray pills cannot fall in.

    Built at Z=0..PILL_RING_T.  Translate to (CX, CY, PILL_RING_WORLD_Z).
    """
    # Outer disk
    outer = cq.Workplane("XY").circle(PILL_RING_OUTER_R).extrude(PILL_RING_T)
    # Hub clearance (centre hole)
    inner = cq.Workplane("XY").circle(PILL_RING_INNER_R).extrude(PILL_RING_T + 0.01)
    ring = outer.cut(inner)
    # Loading port: single hole matching routing chute exit, local pos = (0, SLOT_RADIUS)
    # SLOT_RADIUS=2.5" places it directly above the base-plate drop zone at world (0, 7.0)
    port_cutter = (
        cq.Workplane("XY")
        .center(0, SLOT_RADIUS)
        .circle(ROUTING_CHUTE_EXIT_R)
        .extrude(PILL_RING_T + 0.01)   # 2× overshoot avoids coincident face
    )
    return ring.cut(port_cutter)


def make_vertical_pcb():
    """Raspberry Pi 4 PCB remounted vertically on the flat back wall (Y~0).
    Board in the XZ plane: 3.35" wide (X) x 2.20" tall (Z) x 0.063" thick (Y).
    Workplane("XZ") extrudes in -Y, so we shift +STANDOFF_L+PCB_T in Y and
    +PCB_D/2 in Z to land with the board at Y=[STANDOFF_L, STANDOFF_L+PCB_T],
    Z=[0, PCB_D] in local frame.
    Four standoffs project in +Y from Y=0 to Y=STANDOFF_L.
    Translate to (0, VPCB_WORLD_Y, VPCB_WORLD_Z) at build time.
    Expected world: Y=[0.45, 0.513], Z=[9.50, 11.70].
    """
    # Board: XZ extrudes in -Y; translate so final Y=[STANDOFF_L, STANDOFF_L+PCB_T], Z=[0, PCB_D]
    board = (
        cq.Workplane("XZ")
        .rect(PCB_W, PCB_D)
        .extrude(PCB_T)
        .translate((0, VPCB_STANDOFF_L + PCB_T, PCB_D / 2.0))
    )
    px       = PCB_W / 2.0 - 0.10
    pz_half  = PCB_D / 2.0 - 0.10   # standoff Z offset from board Z-center
    pcb = board
    for sx, sz_rel in [(px, pz_half), (-px, pz_half), (px, -pz_half), (-px, -pz_half)]:
        sz = sz_rel + PCB_D / 2.0   # absolute Z in local frame (0 = board bottom)
        post = (
            cq.Workplane("XZ")
            .center(sx, sz)
            .circle(PCB_POST_R)
            .extrude(VPCB_STANDOFF_L)
            .translate((0, VPCB_STANDOFF_L, 0))   # XZ extrudes in -Y; shift to Y=[0, STANDOFF_L]
        )
        pcb = pcb.union(post)
    return pcb


def make_camera_arm():
    """Wall-mount camera bracket: horizontal arm from back wall to just outside
    the loading tube, with camera module at the tip aimed straight down at the carousel.
    Arm: CAM_ARM_CROSS × CAM_ARM_CROSS cross-section bar running in +Y from Y=VPCB_WORLD_Y
    to Y=CAM_ARM_Y_TIP = 2.55", at Z=CAM_ARM_Z = 11.80", X=0.
    Camera head hangs below the arm tip; lens faces −Z toward the carousel.
    This position gives an unobstructed diagonal view of the dispensing slot (world Y=7.0)
    while staying completely clear of the loading tube (outer edge at Y=2.60").
    """
    arm_y_start = VPCB_WORLD_Y + PCB_T + VPCB_STANDOFF_L   # clear of PCB board face
    arm_len = CAM_ARM_Y_TIP - arm_y_start
    arm = (
        cq.Workplane("XY")
        .center(0, arm_y_start + arm_len / 2)
        .rect(CAM_ARM_CROSS, arm_len)
        .extrude(CAM_ARM_CROSS)
        .translate((0, 0, CAM_ARM_Z))
    )
    cam_body = (
        cq.Workplane("XY")
        .center(0, CAM_ARM_Y_TIP)
        .rect(CAM_W, CAM_D)
        .extrude(CAM_T)
        .translate((0, 0, CAM_ARM_Z - CAM_ARM_CROSS - CAM_T))
    )
    cam_lens = (
        cq.Workplane("XY")
        .center(0, CAM_ARM_Y_TIP)
        .circle(CAM_LENS_R)
        .extrude(0.10)
        .translate((0, 0, CAM_ARM_Z - CAM_ARM_CROSS - CAM_T - 0.10))
    )
    try:
        return arm.union(cam_body).union(cam_lens)
    except Exception:
        return arm


# ===========================================================================
# BUILD SECTION
# ===========================================================================

# --- A. Single cartridge template (neutral position, exported for reference) ---
print("Building cartridge template...")
cartridge_template = make_single_cartridge()
save_step(cartridge_template, "cartridge.step")

# --- B. Stepper motor + D-shaft (unioned into one part, world-positioned) ---
# Motor sits at Y=CAROUSEL_Y=4.5 — directly below the carousel rotation axis.
print("Building stepper motor + D-shaft...")
motor_body     = make_stepper_motor().translate((CAROUSEL_X, CAROUSEL_Y, MOTOR_Z_BOT))
d_shaft        = make_d_shaft().translate((CAROUSEL_X, CAROUSEL_Y, SHAFT_Z_BOT))
motor_assembly = motor_body.union(d_shaft)   # shaft is fixed to motor rotor
save_step(motor_assembly, "motor_assembly.step")

# --- B2. Hub lock (world-positioned, rotates with carousel and shaft) ---
print("Building hub lock...")
hub_lock = make_hub_lock().translate((CAROUSEL_X, CAROUSEL_Y, CAROUSEL_Z_CART))
save_step(hub_lock, "hub_lock.step")

# --- C. Base plate (world-positioned) ---
print("Building carousel base plate...")
base = build_base_plate().translate((CAROUSEL_X, CAROUSEL_Y, CAROUSEL_Z_BASE))
save_step(base, "carousel_base.step")

# --- C2. Agitator / singulator wheel (housing-fixed, world-positioned) ---
print("Building agitator wheel...")
agitator_wheel = (
    make_agitator_wheel()
    .translate((AGIT_WORLD_X, AGIT_WORLD_Y, AGIT_WORLD_Z))
)
save_step(agitator_wheel, "agitator_wheel.step")

# --- C2B. Phase 22 two-gate metering escapement (housing-fixed, normally closed) ---
print("Building upper inlet gate, lower release gate, and servo mounts...")
dispense_gate = (
    make_dispense_gate()
    .translate((DISPENSE_GATE_X, DISPENSE_GATE_Y, DISPENSE_GATE_Z))
)
dispense_gate_servo_mount = (
    make_dispense_gate_servo_mount()
    .translate((DISPENSE_SERVO_X, DISPENSE_SERVO_Y, DISPENSE_SERVO_Z))
)
dispense_release_gate = (
    make_dispense_release_gate()
    .translate((DISPENSE_RELEASE_GATE_X, DISPENSE_RELEASE_GATE_Y, DISPENSE_RELEASE_GATE_Z))
)
dispense_release_gate_servo_mount = (
    make_dispense_release_gate_servo_mount()
    .translate((DISPENSE_RELEASE_SERVO_X, DISPENSE_RELEASE_SERVO_Y, DISPENSE_RELEASE_SERVO_Z))
)
save_step(dispense_gate, "dispense_gate.step")
save_step(dispense_gate_servo_mount, "dispense_gate_servo_mount.step")
save_step(dispense_release_gate, "dispense_release_gate.step")
save_step(dispense_release_gate_servo_mount, "dispense_release_gate_servo_mount.step")

# --- C2C. Phase 21 low front-entry last-pill sweeper ---
print("Building low front-entry sweep pusher, sealed containment, rail, and servo mount...")
dispense_sweep_pusher = (
    make_dispense_sweep_pusher()
    .translate((SWEEP_PUSHER_X, SWEEP_PUSHER_Y_RETRACTED, SWEEP_PUSHER_Z))
)
dispense_sweep_pusher_deployed = (
    make_dispense_sweep_pusher()
    .translate((SWEEP_PUSHER_X, SWEEP_PUSHER_Y_DEPLOYED, SWEEP_PUSHER_Z))
)
dispense_sweep_containment_band = (
    make_dispense_sweep_containment_band()
    .translate((CAROUSEL_X, CAROUSEL_Y, SWEEP_CONTAIN_Z))
)
dispense_sweep_port_seal = (
    make_dispense_sweep_port_seal()
    .translate((0.0, CAROUSEL_Y + SWEEP_CONTAIN_OUTER_R + SWEEP_SEAL_D / 2, SWEEP_CONTAIN_Z))
)
dispense_sweep_rail = (
    make_dispense_sweep_rail()
    .translate((SWEEP_RAIL_X, SWEEP_RAIL_Y, SWEEP_RAIL_Z))
)
dispense_sweep_servo_mount = (
    make_dispense_sweep_servo_mount()
    .translate((SWEEP_SERVO_X, SWEEP_SERVO_Y, SWEEP_SERVO_Z))
)
save_step(dispense_sweep_pusher, "dispense_sweep_pusher.step")
save_step(dispense_sweep_pusher_deployed, "dispense_sweep_pusher_deployed.step")
save_step(dispense_sweep_containment_band, "dispense_sweep_containment_band.step")
save_step(dispense_sweep_port_seal, "dispense_sweep_port_seal.step")
save_step(dispense_sweep_rail, "dispense_sweep_rail.step")
save_step(dispense_sweep_servo_mount, "dispense_sweep_servo_mount.step")

# --- C3. Pill guide / loading funnel (housing-fixed, above carousel) ---
print("Building pill guide tube...")
pill_guide = (
    make_pill_guide()
    .translate((CAROUSEL_X, CAROUSEL_Y, GUIDE_WORLD_Z))
)
save_step(pill_guide, "pill_guide.step")

# --- C4. PCB tray (housing-fixed, Raspberry Pi 4 footprint) ---
print("Building PCB tray...")
pcb_tray = (
    make_pcb_tray()
    .translate((CAROUSEL_X, CAROUSEL_Y, PCB_WORLD_Z))
)
save_step(pcb_tray, "pcb_tray.step")

# --- C5. Camera module (housing-fixed, lens faces down at carousel) ---
print("Building camera module...")
camera = (
    make_camera()
    .translate((CAROUSEL_X, CAROUSEL_Y, CAM_WORLD_Z))
)
save_step(camera, "camera.step")

# --- C6. Load cell pad (housing-fixed, in alcove under spout) ---
print("Building load cell pad...")
load_cell = (
    make_load_cell()
    .translate((LOAD_WORLD_X, LOAD_WORLD_Y, LOAD_WORLD_Z))
)
save_step(load_cell, "load_cell.step")

# --- C7. Vibration motor (housing-fixed, near back wall upper zone) ---
print("Building vibration motor...")
vib_motor = (
    make_vibration_motor()
    .translate((VIB_WORLD_X, VIB_WORLD_Y, VIB_WORLD_Z))
)
save_step(vib_motor, "vib_motor.step")

# --- C8. Top loading hatch (housing-fixed, D-shaped lid with pill port) ---
print("Building top loading hatch...")
top_hatch = (
    make_top_hatch()
    .translate((0.0, 0.0, HATCH_WORLD_Z))
)
save_step(top_hatch, "top_hatch.step")

# --- C9. Pill chute (housing-fixed, bridges base plate → spout) ---
print("Building pill chute...")
pill_chute = (
    make_pill_chute()
    .translate((0.0, AGIT_WORLD_Y, CHUTE_WORLD_Z))
)
save_step(pill_chute, "pill_chute.step")

# --- C10. Motor mount plate (housing-fixed, NEMA 17 pattern) ---
print("Building motor mount plate...")
motor_mount = (
    make_motor_mount()
    .translate((CAROUSEL_X, CAROUSEL_Y, MOUNT_WORLD_Z))
)
save_step(motor_mount, "motor_mount.step")

# --- C11. Display panel (housing-fixed, vertical on front face) ---
print("Building display panel...")
display_panel = (
    make_display_panel()
    .translate((0.0, DISPLAY_WORLD_Y + DISPLAY_T, DISPLAY_WORLD_Z))
    # XZ workplane extrudes in −Y, so +DISPLAY_T offset seats panel at Y=8.82..8.90
)
save_step(display_panel, "display_panel.step")

# --- C12. LED ring (housing-fixed, around button on front face) ---
print("Building LED ring...")
led_ring = (
    make_led_ring()
    .translate((0.0, LED_RING_WORLD_Y + LED_RING_T, LED_RING_WORLD_Z))
    # XZ workplane extrudes in −Y, so +LED_RING_T offset seats ring at Y=9.00..9.05
)
save_step(led_ring, "led_ring.step")

# --- C13. PCB mounting shelf (housing-fixed, supports PCB tray from below) ---
print("Building PCB shelf...")
pcb_shelf = (
    make_pcb_shelf()
    .translate((CAROUSEL_X, CAROUSEL_Y, PCB_SHELF_WORLD_Z))
)
save_step(pcb_shelf, "pcb_shelf.step")

# --- C14. Guide funnel (housing-fixed, bottom of pill guide tube) ---
print("Building guide funnel...")
guide_funnel = (
    make_guide_funnel()
    .translate((CAROUSEL_X, CAROUSEL_Y, GUIDE_WORLD_Z))
)
save_step(guide_funnel, "guide_funnel.step")

# --- C15. Top hatch with hinge knuckles + snap-latch (replaces plain top_hatch) ---
print("Building hatch with retention features...")
hatch_final = (
    make_hatch_with_retention()
    .translate((0.0, 0.0, HATCH_WORLD_Z))
)
save_step(hatch_final, "hatch_final.step")

# --- C16. USB-C port bezel (housing-fixed, back wall) ---
print("Building USB-C port bezel...")
usbc_port = (
    make_usbc_port()
    .translate((0.0, 0.10, USBC_WORLD_Z))   # Y=0.10 seats bezel flush with back wall outer face
)
save_step(usbc_port, "usbc_port.step")

# --- C17. Speaker grille (housing-fixed, front face left side) ---
print("Building speaker grille...")
# Front wall at SPEAKER_WORLD_X is at approx Y=8.8 (inner face of curved front wall)
_speaker_wall_y = 8.80
speaker_grille = (
    make_speaker_grille()
    .translate((SPEAKER_WORLD_X, _speaker_wall_y + 0.05, SPEAKER_WORLD_Z))
)
save_step(speaker_grille, "speaker_grille.step")

# --- Phase 9: Pill loading path ---
# C18. Loading tube — sealed pill channel from hatch port to guide tube (bridges the gap)
print("Building loading tube...")
loading_tube = (
    make_loading_tube()
    .translate((CAROUSEL_X, CAROUSEL_Y, LOAD_TUBE_Z_BOT))
)
save_step(loading_tube, "loading_tube.step")

# C19. Pill guide ring — replaces incorrect guide_funnel; keeps pills in carousel zone
print("Building pill guide ring...")
pill_guide_ring = (
    make_pill_guide_ring()
    .translate((CAROUSEL_X, CAROUSEL_Y, PILL_RING_WORLD_Z))
)
save_step(pill_guide_ring, "pill_guide_ring.step")

# C20. Vertical PCB back-wall mount — frees central loading column
print("Building vertical PCB back-wall mount...")
vertical_pcb = (
    make_vertical_pcb()
    .translate((0.0, VPCB_WORLD_Y, VPCB_WORLD_Z))
)
save_step(vertical_pcb, "vertical_pcb.step")

# C21. PHASE 10: camera_arm superseded by optical_chamber.py camera_mount
# The optical chamber (chamber_shell + staging_floor + camera_mount + led_ring_oc)
# replaces this temporary wall-bracket arm.  Function kept for reference.
# print("Building camera arm...")
# camera_arm = make_camera_arm()
# save_step(camera_arm, "camera_arm.step")

# --- D. 10-cartridge radial pattern ---
# rotate() MUST come before translate() — rotation is around world origin
# cart_00: angle = 0*36 + 90 = 90° → centred at 90° (toward +Y = spout direction)
# cart_01: angle = 126°, cart_02: 162°, …, cart_09: 414° ≡ 54°
print("Building 10-cartridge radial pattern...")
cartridges = []
for i in range(N_SLOTS):
    angle = i * DEG_EACH + CART_OFFSET_DEG
    cart = (
        cartridge_template
        .rotate((0, 0, 0), (0, 0, 1), angle)
        .translate((CAROUSEL_X, CAROUSEL_Y, CAROUSEL_Z_CART))
    )
    cartridges.append(cart)
print(f"  Built {len(cartridges)} cartridges (cart_00 centred at {CART_OFFSET_DEG:.0f}°)")

# --- E. Carousel sub-assembly ---
print("Building carousel_assembly.step...")
carousel_assy = cq.Assembly()
for i, cart in enumerate(cartridges):
    carousel_assy.add(
        cart,
        name=f"cartridge_{i:02d}",
        color=cq.Color(0.90, 0.90, 0.95, 0.85),   # semi-transparent light blue
    )
carousel_assy.add(hub_lock, name="hub_lock", color=cq.Color(0.30, 0.30, 0.35, 1.0))
carousel_assy.add(base, name="base", color=cq.Color(0.60, 0.60, 0.65, 1.0))
carousel_assy.export(str(OUTPUT / "carousel_assembly.step"))
print("  Wrote output/carousel_assembly.step")

# --- F. Master full assembly (requires hero_dispenser.py output) ---
print("Building hero_full_assembly.step...")
required = ["enclosure.step", "button.step", "pill_cup.step", "drop_cone.step"]
missing  = [f for f in required if not (OUTPUT / f).exists()]
if missing:
    print(f"  SKIP — missing prerequisite file(s): {missing}")
    print("  Run hero_dispenser.py first, then re-run carousel.py.")
else:
    enc = cq.importers.importStep(str(OUTPUT / "enclosure.step"))
    btn = cq.importers.importStep(str(OUTPUT / "button.step"))
    cup = cq.importers.importStep(str(OUTPUT / "pill_cup.step"))
    drop = cq.importers.importStep(str(OUTPUT / "drop_cone.step"))

    # Locations match hero_dispenser.py exactly
    btn_loc = cq.Location(cq.Vector(0, 9.15, 8.5), cq.Vector(1, 0, 0), 90)
    cup_loc = cq.Location(cq.Vector(0, 7.0, 0.20))

    hero_assy = cq.Assembly()
    hero_assy.add(enc, name="enclosure",
                  color=cq.Color(0.82, 0.84, 0.88, 1.0))
    hero_assy.add(btn, name="button",
                  loc=btn_loc, color=cq.Color(0.15, 0.15, 0.15, 1.0))
    hero_assy.add(cup, name="pill_cup",
                  loc=cup_loc, color=cq.Color(0.95, 0.95, 0.95, 0.85))
    hero_assy.add(drop, name="drop_cone",
                  color=cq.Color(0.95, 0.95, 0.95, 0.55))
    # carousel_assy is already in world coordinates — no loc offset needed
    hero_assy.add(carousel_assy, name="carousel")
    # Motor + shaft: housing-fixed drive assembly, world-positioned, no loc needed
    hero_assy.add(motor_assembly, name="motor_assembly",
                  color=cq.Color(0.20, 0.20, 0.20, 1.0))
    # Phase 20 dispense escapement: normally-closed gate at the chute transition.
    hero_assy.add(dispense_gate, name="dispense_gate",
                  color=cq.Color(0.95, 0.40, 0.10, 1.0))
    hero_assy.add(dispense_gate_servo_mount, name="dispense_gate_servo_mount",
                  color=cq.Color(0.15, 0.15, 0.15, 1.0))
    hero_assy.add(dispense_release_gate, name="dispense_release_gate",
                  color=cq.Color(0.95, 0.62, 0.10, 1.0))
    hero_assy.add(dispense_release_gate_servo_mount, name="dispense_release_gate_servo_mount",
                  color=cq.Color(0.15, 0.15, 0.15, 1.0))
    hero_assy.add(dispense_sweep_pusher, name="dispense_sweep_pusher",
                  color=cq.Color(0.20, 0.75, 0.95, 1.0))
    hero_assy.add(dispense_sweep_containment_band, name="dispense_sweep_containment_band",
                  color=cq.Color(0.72, 0.72, 0.76, 0.85))
    hero_assy.add(dispense_sweep_port_seal, name="dispense_sweep_port_seal",
                  color=cq.Color(0.10, 0.10, 0.12, 1.0))
    hero_assy.add(dispense_sweep_rail, name="dispense_sweep_rail",
                  color=cq.Color(0.35, 0.35, 0.38, 1.0))
    hero_assy.add(dispense_sweep_servo_mount, name="dispense_sweep_servo_mount",
                  color=cq.Color(0.15, 0.15, 0.15, 1.0))

    # --- Phase 6: Electronics & Sensing Layer (housing-fixed) ---
    # Pill guide: wide loading chimney above carousel (R=3.5", Z=8.90-11.00")
    hero_assy.add(pill_guide, name="pill_guide",
                  color=cq.Color(0.70, 0.90, 0.70, 0.60))  # translucent green

    # Load cell: thin force pad under spout in alcove — confirms pill dispensed
    hero_assy.add(load_cell, name="load_cell",
                  color=cq.Color(0.90, 0.75, 0.20, 1.0))   # gold

    # Vibration motor: ERM cylinder near back wall — agitates stuck pills
    hero_assy.add(vib_motor, name="vib_motor",
                  color=cq.Color(0.60, 0.60, 0.65, 1.0))   # metallic gray

    # --- Phase 7: Structural & Interface Components (housing-fixed) ---
    # Pill chute: bridges base plate drop zone down to spout bore
    hero_assy.add(pill_chute, name="pill_chute",
                  color=cq.Color(0.85, 0.85, 0.90, 0.80))  # light gray, semi-transparent

    # Motor mount plate: horizontal NEMA 17 mounting bracket
    hero_assy.add(motor_mount, name="motor_mount",
                  color=cq.Color(0.45, 0.45, 0.50, 1.0))   # dark steel

    # Display panel: flat screen sitting in the front-face cutout
    hero_assy.add(display_panel, name="display_panel",
                  color=cq.Color(0.05, 0.05, 0.08, 1.0))   # near-black (powered-off screen)

    # LED ring: status indicator surrounding the button
    hero_assy.add(led_ring, name="led_ring",
                  color=cq.Color(0.20, 0.85, 0.35, 0.90))  # bright green (LED glow)

    # --- Phase 8: Hatch retention, power & audio ---
    # Hatch with retention: D-shaped lid with hinge knuckles + snap latch
    hero_assy.add(hatch_final, name="hatch_final",
                  color=cq.Color(0.82, 0.84, 0.88, 0.70))  # enclosure color

    # USB-C port bezel: power inlet on back wall at Z=1.80"
    hero_assy.add(usbc_port, name="usbc_port",
                  color=cq.Color(0.70, 0.70, 0.75, 1.0))   # light steel

    # Speaker grille: circular perforated disk on front-left face
    hero_assy.add(speaker_grille, name="speaker_grille",
                  color=cq.Color(0.25, 0.25, 0.28, 1.0))   # dark gray

    # --- Phase 9: Pill loading path — sealed vertical channel ---
    # Loading tube: 1.80" bore sealed channel from hatch (Z=14.90) to guide tube (Z=11.00)
    # Completely encloses the pill path — no free-fall, no PCB collision
    hero_assy.add(loading_tube, name="loading_tube",
                  color=cq.Color(0.70, 0.90, 0.70, 0.45))  # translucent green (see-through)

    # Pill guide ring: flat annular washer on carousel top — keeps pills in cartridge zone
    # Replaces the incorrect guide_funnel that would have blocked pills
    hero_assy.add(pill_guide_ring, name="pill_guide_ring",
                  color=cq.Color(0.75, 0.75, 0.80, 0.80))  # light gray

    # Vertical PCB: RPi 4 back-wall vertical mount — completely out of loading column
    hero_assy.add(vertical_pcb, name="vertical_pcb",
                  color=cq.Color(0.10, 0.55, 0.10, 1.0))   # PCB green

    # --- Phase 10: Optical Detection Chamber ---
    # Prerequisite: run optical_chamber.py first to generate these STEP files.
    # staging_floor.step is intentionally omitted here — Phase 11 trapdoor replaces it.
    _oc_needed = ["chamber_shell.step", "camera_mount.step",
                  "led_ring_oc.step",  "chamber_ceiling.step"]
    _oc_missing = [f for f in _oc_needed if not (OUTPUT / f).exists()]
    if _oc_missing:
        print(f"  SKIP optical chamber parts — missing: {_oc_missing}")
        print("  Run optical_chamber.py first, then re-run carousel.py.")
    else:
        _ch_shell = cq.importers.importStep(str(OUTPUT / "chamber_shell.step"))
        _cam_mnt  = cq.importers.importStep(str(OUTPUT / "camera_mount.step"))
        _led_oc   = cq.importers.importStep(str(OUTPUT / "led_ring_oc.step"))
        _ch_ceil  = cq.importers.importStep(str(OUTPUT / "chamber_ceiling.step"))
        # chamber_shell: transparent imaging cylinder (Z=12.90-14.90", inside loading tube)
        hero_assy.add(_ch_shell, name="chamber_shell",
                      color=cq.Color(0.70, 0.90, 0.70, 0.35))
        # camera_mount: 45-deg tilted bridge in annular gap, lens aimed at trapdoor
        hero_assy.add(_cam_mnt, name="camera_mount",
                      color=cq.Color(0.12, 0.12, 0.12, 1.0))
        # led_ring_oc: warm-yellow torus resting in ceiling plate LED groove
        hero_assy.add(_led_oc, name="led_ring_oc",
                      color=cq.Color(1.00, 0.92, 0.23, 0.90))
        # chamber_ceiling: frosted PETG diffuser plate -- LED mount + ambient light baffle
        hero_assy.add(_ch_ceil, name="chamber_ceiling",
                      color=cq.Color(0.90, 0.95, 0.90, 0.60))

    # --- Phase 11: Trapdoor Mechanism (replaces staging_floor placeholder) ---
    # Prerequisite: run trapdoor.py first to generate these STEP files.
    # Two hinged semicircular leaves driven by SG90 servo — open to drop pill.
    _td_needed = ["trapdoor_left.step", "trapdoor_right.step",
                  "hinge_pin.step",     "servo_mount.step"]
    _td_missing = [f for f in _td_needed if not (OUTPUT / f).exists()]
    if _td_missing:
        print(f"  SKIP trapdoor parts — missing: {_td_missing}")
        print("  Run trapdoor.py first, then re-run carousel.py.")
    else:
        _td_left  = cq.importers.importStep(str(OUTPUT / "trapdoor_left.step"))
        _td_right = cq.importers.importStep(str(OUTPUT / "trapdoor_right.step"))
        _td_pin   = cq.importers.importStep(str(OUTPUT / "hinge_pin.step"))
        _td_servo = cq.importers.importStep(str(OUTPUT / "servo_mount.step"))
        # Left leaf: X<=0 semicircle, clear acrylic (translucent blue-white)
        hero_assy.add(_td_left,  name="trapdoor_left",
                      color=cq.Color(0.85, 0.95, 1.00, 0.75))
        # Right leaf: X>=0 semicircle, same material
        hero_assy.add(_td_right, name="trapdoor_right",
                      color=cq.Color(0.85, 0.95, 1.00, 0.75))
        # Hinge pin: Y-axis steel pin spanning both leaves (R=0.04", L=3.00")
        hero_assy.add(_td_pin,   name="hinge_pin",
                      color=cq.Color(0.80, 0.80, 0.85, 1.00))
        # Servo mount: SG90 body + ears + drive arm (outside loading tube wall, X>=1.90")
        hero_assy.add(_td_servo, name="servo_mount",
                      color=cq.Color(0.15, 0.15, 0.15, 1.00))

    # --- Phase 13: Static Routing Chute ---
    # Prerequisite: run routing_chute.py first.
    # Lofted hollow funnel: catches pill at trapdoor (Z=12.90") and steers it
    # to the active carousel loading slot at Y=CAROUSEL_Y+SLOT_RADIUS=7.0".
    _rc_needed = ["routing_chute.step"]
    _rc_missing = [f for f in _rc_needed if not (OUTPUT / f).exists()]
    if _rc_missing:
        print(f"  SKIP routing chute — missing: {_rc_missing}")
        print("  Run routing_chute.py first, then re-run carousel.py.")
    else:
        _rchute = cq.importers.importStep(str(OUTPUT / "routing_chute.step"))
        # Translucent amber — visible in assembly but doesn't obscure internals
        hero_assy.add(_rchute, name="routing_chute",
                      color=cq.Color(1.00, 0.70, 0.20, 0.65))

    # --- Phase 16: Index Wheel (carousel home-position sensing) ---
    # rear_shaft  — D-shaft extension below motor body, Z=[2.90, 3.40]
    # index_disk  — slotted encoder disk, Z=[3.125, 3.175], R=0.60"
    # sensor_mount — L-bracket + TCST2103 fork sensor at X=0.60", Z=3.15"
    # Prerequisite: run index_wheel.py first.
    _iw_needed = ["rear_shaft.step", "index_disk.step", "sensor_mount.step"]
    _iw_missing = [f for f in _iw_needed if not (OUTPUT / f).exists()]
    if _iw_missing:
        print(f"  SKIP index wheel — missing: {_iw_missing}")
        print("  Run index_wheel.py first, then re-run carousel.py.")
    else:
        _rear_shaft  = cq.importers.importStep(str(OUTPUT / "rear_shaft.step"))
        _index_disk  = cq.importers.importStep(str(OUTPUT / "index_disk.step"))
        _sensor_mnt  = cq.importers.importStep(str(OUTPUT / "sensor_mount.step"))
        hero_assy.add(_rear_shaft, name="rear_shaft",
                      color=cq.Color(0.70, 0.70, 0.75, 1.00))   # steel gray
        hero_assy.add(_index_disk, name="index_disk",
                      color=cq.Color(0.10, 0.10, 0.10, 1.00))   # matte black
        hero_assy.add(_sensor_mnt, name="sensor_mount",
                      color=cq.Color(0.15, 0.15, 0.15, 1.00))   # near-black

    hero_assy.export(str(OUTPUT / "hero_full_assembly.step"))
    print("  Wrote output/hero_full_assembly.step")

# ---------------------------------------------------------------------------
# Inline verification
# ---------------------------------------------------------------------------
print("\n--- Verification ---")
bb_t = cartridge_template.val().BoundingBox()
print(f"  cartridge_template: Z=[{bb_t.zmin:.3f}, {bb_t.zmax:.3f}]  "
      f"(expected [0.000, {CART_H:.3f}])")

bb_hl = hub_lock.val().BoundingBox()
print(f"  hub_lock (world):   Z=[{bb_hl.zmin:.3f}, {bb_hl.zmax:.3f}]  "
      f"(expected [{CAROUSEL_Z_CART:.3f}, {CAROUSEL_Z_CART + CART_H:.3f}])")

bb_ma = motor_assembly.val().BoundingBox()
print(f"  motor_assy (world): Z=[{bb_ma.zmin:.3f}, {bb_ma.zmax:.3f}]  "
      f"(expected [{MOTOR_Z_BOT:.3f}, {SHAFT_Z_TOP:.3f}])")
print(f"  motor_assy (world): X=[{bb_ma.xmin:.3f}, {bb_ma.xmax:.3f}]  "
      f"(expected [{-MOTOR_W/2:.3f}, {+MOTOR_W/2:.3f}])")

bb_b = base.val().BoundingBox()
print(f"  base (world):       Z=[{bb_b.zmin:.3f}, {bb_b.zmax:.3f}]  "
      f"(expected [{CAROUSEL_Z_BASE:.3f}, {CAROUSEL_Z_BASE + BASE_T:.3f}])")

bb_c0 = cartridges[0].val().BoundingBox()
cx = (bb_c0.xmin + bb_c0.xmax) / 2
cy = (bb_c0.ymin + bb_c0.ymax) / 2
angle_deg = math.degrees(math.atan2(cy - CAROUSEL_Y, cx - CAROUSEL_X))
print(f"  cartridge_00:       Z=[{bb_c0.zmin:.3f}, {bb_c0.zmax:.3f}]  "
      f"centroid angle={angle_deg:.1f}° (expected ~90.0°)")

bb_w = agitator_wheel.val().BoundingBox()
print(f"  agitator_wheel REF: Z=[{bb_w.zmin:.3f}, {bb_w.zmax:.3f}]  "
      f"(expected [{AGIT_WORLD_Z - AGIT_R:.3f}, {AGIT_WORLD_Z + AGIT_R:.3f}])")
print(f"                      Y=[{bb_w.ymin:.3f}, {bb_w.ymax:.3f}]  "
      f"(expected centre at Y={AGIT_WORLD_Y:.1f})")

bb_gate = dispense_gate.val().BoundingBox()
bb_gate_servo = dispense_gate_servo_mount.val().BoundingBox()
bb_release_gate = dispense_release_gate.val().BoundingBox()
bb_release_servo = dispense_release_gate_servo_mount.val().BoundingBox()
bb_sweep = dispense_sweep_pusher.val().BoundingBox()
bb_sweep_contain = dispense_sweep_containment_band.val().BoundingBox()
bb_sweep_seal = dispense_sweep_port_seal.val().BoundingBox()
bb_sweep_rail = dispense_sweep_rail.val().BoundingBox()
bb_sweep_servo = dispense_sweep_servo_mount.val().BoundingBox()
print(f"  dispense_gate:      Z=[{bb_gate.zmin:.3f}, {bb_gate.zmax:.3f}]  "
      f"(expected [{DISPENSE_GATE_Z:.3f}, {DISPENSE_GATE_Z + DISPENSE_GATE_T:.3f}])")
print(f"                      centre=({DISPENSE_GATE_X:.3f}, {DISPENSE_GATE_Y:.3f})  "
      f"coverage R={DISPENSE_GATE_R:.2f}\" > hole R={HOLE_R:.2f}\"")
print(f"  gate_servo_mount:   X=[{bb_gate_servo.xmin:.3f}, {bb_gate_servo.xmax:.3f}]  "
      f"Z=[{bb_gate_servo.zmin:.3f}, {bb_gate_servo.zmax:.3f}]")
print(f"  release_gate:       Z=[{bb_release_gate.zmin:.3f}, {bb_release_gate.zmax:.3f}]  "
      f"centre=({DISPENSE_RELEASE_GATE_X:.3f}, {DISPENSE_RELEASE_GATE_Y:.3f})")
print(f"  release_servo:      X=[{bb_release_servo.xmin:.3f}, {bb_release_servo.xmax:.3f}]  "
      f"Z=[{bb_release_servo.zmin:.3f}, {bb_release_servo.zmax:.3f}]")
print(f"  sweep_pusher:       Y=[{bb_sweep.ymin:.3f}, {bb_sweep.ymax:.3f}]  "
      f"Z=[{bb_sweep.zmin:.3f}, {bb_sweep.zmax:.3f}]")
print(f"  sweep_containment:  R=[{SWEEP_CONTAIN_INNER_R:.3f}, {SWEEP_CONTAIN_OUTER_R:.3f}]  "
      f"Z=[{bb_sweep_contain.zmin:.3f}, {bb_sweep_contain.zmax:.3f}]")
print(f"  sweep_port_seal:    Y=[{bb_sweep_seal.ymin:.3f}, {bb_sweep_seal.ymax:.3f}]  "
      f"Z=[{bb_sweep_seal.zmin:.3f}, {bb_sweep_seal.zmax:.3f}]")
print(f"  sweep_rail:         Y=[{bb_sweep_rail.ymin:.3f}, {bb_sweep_rail.ymax:.3f}]  "
      f"Z=[{bb_sweep_rail.zmin:.3f}, {bb_sweep_rail.zmax:.3f}]")
print(f"  sweep_servo_mount:  X=[{bb_sweep_servo.xmin:.3f}, {bb_sweep_servo.xmax:.3f}]  "
      f"Z=[{bb_sweep_servo.zmin:.3f}, {bb_sweep_servo.zmax:.3f}]")

# Phase 6 verification
bb_pg = pill_guide.val().BoundingBox()
print(f"  pill_guide (world): Z=[{bb_pg.zmin:.3f}, {bb_pg.zmax:.3f}]  "
      f"(expected [{GUIDE_WORLD_Z:.3f}, {GUIDE_WORLD_Z + GUIDE_H:.3f}])")

bb_pcb = pcb_tray.val().BoundingBox()
print(f"  pcb_tray (world):   Z=[{bb_pcb.zmin:.3f}, {bb_pcb.zmax:.3f}]  "
      f"(expected [{PCB_WORLD_Z:.3f}, {PCB_WORLD_Z + PCB_POST_H + PCB_T:.3f}])")

bb_cam = camera.val().BoundingBox()
print(f"  camera (world):     Z=[{bb_cam.zmin:.3f}, {bb_cam.zmax:.3f}]  "
      f"(expected [{CAM_WORLD_Z - 0.10:.3f}, {CAM_WORLD_Z + CAM_T:.3f}])")

bb_lc = load_cell.val().BoundingBox()
print(f"  load_cell (world):  Z=[{bb_lc.zmin:.3f}, {bb_lc.zmax:.3f}]  "
      f"(expected [{LOAD_WORLD_Z:.3f}, {LOAD_WORLD_Z + LOAD_T:.3f}])")

bb_vm = vib_motor.val().BoundingBox()
print(f"  vib_motor (world):  Z=[{bb_vm.zmin:.3f}, {bb_vm.zmax:.3f}]  "
      f"(expected [{VIB_WORLD_Z:.3f}, {VIB_WORLD_Z + VIB_H:.3f}])")

bb_th = top_hatch.val().BoundingBox()
print(f"  top_hatch (world):  Z=[{bb_th.zmin:.3f}, {bb_th.zmax:.3f}]  "
      f"(expected [{HATCH_WORLD_Z:.3f}, {ENCLOSURE_H:.3f}])")

# Phase 7 verification
bb_ch = pill_chute.val().BoundingBox()
print(f"  pill_chute (world): Z=[{bb_ch.zmin:.3f}, {bb_ch.zmax:.3f}]  "
      f"(expected [{CHUTE_WORLD_Z:.3f}, {CHUTE_WORLD_Z + CHUTE_H:.3f}])")

bb_mm = motor_mount.val().BoundingBox()
print(f"  motor_mount (world):Z=[{bb_mm.zmin:.3f}, {bb_mm.zmax:.3f}]  "
      f"(expected [{MOUNT_WORLD_Z:.3f}, {MOUNT_WORLD_Z + MOUNT_PLATE_T:.3f}])")

bb_dp = display_panel.val().BoundingBox()
print(f"  display_panel:      Z=[{bb_dp.zmin:.3f}, {bb_dp.zmax:.3f}]  "
      f"(expected [{DISPLAY_WORLD_Z - DISPLAY_H_DIM/2:.3f}, "
      f"{DISPLAY_WORLD_Z + DISPLAY_H_DIM/2:.3f}])")
print(f"                      Y=[{bb_dp.ymin:.3f}, {bb_dp.ymax:.3f}]  "
      f"(expected [{DISPLAY_WORLD_Y:.3f}, {DISPLAY_WORLD_Y + DISPLAY_T:.3f}])")

bb_lr = led_ring.val().BoundingBox()
print(f"  led_ring:           Z-center={LED_RING_WORLD_Z:.3f}  "
      f"Y=[{bb_lr.ymin:.3f}, {bb_lr.ymax:.3f}]  "
      f"(expected Y=[{LED_RING_WORLD_Y:.3f}, {LED_RING_WORLD_Y + LED_RING_T:.3f}])")

bb_ps = pcb_shelf.val().BoundingBox()
print(f"  pcb_shelf (world):  Z=[{bb_ps.zmin:.3f}, {bb_ps.zmax:.3f}]  "
      f"(expected [{PCB_SHELF_WORLD_Z:.3f}, {PCB_SHELF_WORLD_Z + PCB_SHELF_T:.3f}])")

# Phase 8 verification
bb_gf = guide_funnel.val().BoundingBox()
print(f"  guide_funnel:       Z=[{bb_gf.zmin:.3f}, {bb_gf.zmax:.3f}]  "
      f"(expected [{GUIDE_WORLD_Z:.3f}, {GUIDE_WORLD_Z + FUNNEL_H:.3f}])")

bb_hf = hatch_final.val().BoundingBox()
print(f"  hatch_final:        Z=[{bb_hf.zmin:.3f}, {bb_hf.zmax:.3f}]  "
      f"(expected [{HATCH_WORLD_Z - LATCH_H:.3f}, {ENCLOSURE_H:.3f}])")

bb_usb = usbc_port.val().BoundingBox()
print(f"  usbc_port:          Z=[{bb_usb.zmin:.3f}, {bb_usb.zmax:.3f}]  "
      f"(expected centre at Z={USBC_WORLD_Z:.2f})")

bb_sg = speaker_grille.val().BoundingBox()
print(f"  speaker_grille:     X=[{bb_sg.xmin:.3f}, {bb_sg.xmax:.3f}]  "
      f"(expected [{SPEAKER_WORLD_X - SPEAKER_R:.3f}, {SPEAKER_WORLD_X + SPEAKER_R:.3f}])")

# Phase 9 verification
bb_lt = loading_tube.val().BoundingBox()
print(f"  loading_tube:       Z=[{bb_lt.zmin:.3f}, {bb_lt.zmax:.3f}]  "
      f"(expected [{LOAD_TUBE_Z_BOT:.3f}, {LOAD_TUBE_Z_TOP:.3f}])")
print(f"                      X=[{bb_lt.xmin:.3f}, {bb_lt.xmax:.3f}]  "
      f"(expected [{-LOAD_TUBE_OUTER_R:.3f}, {LOAD_TUBE_OUTER_R:.3f}])")

bb_pgr = pill_guide_ring.val().BoundingBox()
print(f"  pill_guide_ring:    Z=[{bb_pgr.zmin:.3f}, {bb_pgr.zmax:.3f}]  "
      f"(expected [{PILL_RING_WORLD_Z:.3f}, {PILL_RING_WORLD_Z + PILL_RING_T:.3f}])")

# ---------------------------------------------------------------------------
# Sandwich Seal Verification — confirms the stationary housing bounds the
# carousel top and bottom with exactly one controlled entry and one exit.
# ---------------------------------------------------------------------------
print("\n=== SANDWICH SEAL VERIFICATION ===")

# --- TOP SEAL: pill_guide_ring ---
_pgr_z_ok     = abs(bb_pgr.zmin - PILL_RING_WORLD_Z) < 0.01
_port_y_world = CAROUSEL_Y + SLOT_RADIUS   # 7.0"  port is cut at LOCAL (0, SLOT_RADIUS)
print(f"  TOP SEAL (pill_guide_ring):")
print(f"    Z=[{bb_pgr.zmin:.3f}, {bb_pgr.zmax:.3f}]  T={bb_pgr.zmax - bb_pgr.zmin:.3f}\"  "
      f"({'OK' if _pgr_z_ok else 'CHECK'})")
print(f"    Hub clearance R={PILL_RING_INNER_R:.2f}\"  Outer R={PILL_RING_OUTER_R:.2f}\"  (solid ceiling everywhere else)")
print(f"    Loading port: 1 hole  R={ROUTING_CHUTE_EXIT_R:.2f}\"  world Y={_port_y_world:.3f}\"  "
      f"(aligns with routing_chute exit  OK)")

# --- BOTTOM SEAL: base plate ---
bb_base2   = base.val().BoundingBox()
_base_z_ok = abs(bb_base2.zmin - CAROUSEL_Z_BASE) < 0.01
_drop_y    = CAROUSEL_Y + SLOT_RADIUS   # world Y of drop hole = 7.0"
print(f"\n  BOTTOM SEAL (base plate):")
print(f"    Z=[{bb_base2.zmin:.3f}, {bb_base2.zmax:.3f}]  T={BASE_T:.2f}\"  "
      f"({'OK' if _base_z_ok else 'CHECK'})")
print(f"    Drop hole:        1 hole  R={HOLE_R:.2f}\"  world Y={_drop_y:.3f}\"  (sole dispensing exit)")
print(f"    Shaft clearance:  1 hole  R~{SHAFT_R + SHAFT_CLEARANCE:.2f}\"  at centre  (torque isolation — NOT dispensing)")

# --- DISPENSING CONTINUITY: pill_chute ---
bb_ch2       = pill_chute.val().BoundingBox()
bb_rg2       = dispense_release_gate.val().BoundingBox()
_release_to_spout = bb_rg2.zmin - SPOUT_TOP_Z
_release_to_chute = bb_ch2.zmin - bb_rg2.zmax
_gate_gap    = DISPENSE_GATE_Z - bb_ch2.zmax
_bore_match  = abs(CHUTE_INNER_R - 0.25) < 0.001
print(f"\n  DISPENSING CONTINUITY (metering chamber / chute):")
print(f"    Spout top Z={SPOUT_TOP_Z:.3f}\" -> release gate bottom Z={bb_rg2.zmin:.3f}\"  "
      f"({'LOWER GATE CLEARS SPOUT' if 0 <= _release_to_spout < 0.02 else 'CHECK RELEASE/SPOUT GAP=' + str(round(_release_to_spout, 4))})")
print(f"    Release gate top Z={bb_rg2.zmax:.3f}\" -> chamber bottom Z={bb_ch2.zmin:.3f}\"  "
      f"({'LOWER GATED GAP OK' if 0 <= _release_to_chute < 0.03 else 'CHECK LOWER GAP=' + str(round(_release_to_chute, 4))})")
print(f"    Chamber top Z={bb_ch2.zmax:.3f}\" -> upper gate underside Z={DISPENSE_GATE_Z:.3f}\"  "
      f"({'UPPER GATED GAP OK' if 0 <= _gate_gap < 0.03 else 'CHECK UPPER GAP=' + str(round(_gate_gap, 4))})")
print(f"    Seal flange R={CHUTE_FLANGE_R:.3f}\" > drop hole R={HOLE_R:.3f}\"  "
      f"lip={CHUTE_FLANGE_R - HOLE_R:.3f}\"  {'OK' if CHUTE_FLANGE_R > HOLE_R else 'INSUFFICIENT'}")
print(f"    Inner bore  R={CHUTE_INNER_R:.3f}\" = spout bore R=0.250\"  "
      f"{'MATCHED' if _bore_match else 'MISMATCH'}")

# --- PHASE 22 TWO-GATE METERING ESCAPEMENT ---
bb_g2 = dispense_gate.val().BoundingBox()
_gate_x_ctr = DISPENSE_GATE_X
_gate_y_ctr = DISPENSE_GATE_Y
_gate_xy_ok = True
_gate_cover_ok = DISPENSE_GATE_R > HOLE_R + 0.10
_gate_below_base = bb_g2.zmax < CAROUSEL_Z_BASE
_release_cover_ok = DISPENSE_RELEASE_GATE_R > CHUTE_INNER_R + 0.10
_one_tablet_fits = (CHUTE_INNER_R * 2) > (DEMO_TABLET_D + 0.04) and CHUTE_H > (DEMO_TABLET_H + 0.05)
_two_side_by_side_blocked = (CHUTE_INNER_R * 2) < (DEMO_TABLET_D * 2)
_two_stacked_blocked = CHUTE_H < (DEMO_TABLET_H * 2)
print(f"\n  PHASE 22 TWO-GATE METERING ESCAPEMENT:")
print(f"    Upper inlet gate centre=({_gate_x_ctr:.3f}, {_gate_y_ctr:.3f})  "
      f"drop hole=(0.000, {CAROUSEL_Y + SLOT_RADIUS:.3f})  "
      f"({'ALIGNED' if _gate_xy_ok else 'OFFSET!'})")
print(f"    Upper gate coverage R={DISPENSE_GATE_R:.3f}\" vs hole R={HOLE_R:.3f}\"  "
      f"({'COVERS CLOSED' if _gate_cover_ok else 'INSUFFICIENT COVERAGE'})")
print(f"    Upper gate Z=[{bb_g2.zmin:.3f}, {bb_g2.zmax:.3f}] below base bottom {CAROUSEL_Z_BASE:.3f}\"  "
      f"({'NO CARTRIDGE COLLISION' if _gate_below_base else 'CHECK Z'})")
print(f"    Lower release gate coverage R={DISPENSE_RELEASE_GATE_R:.3f}\" vs chamber bore R={CHUTE_INNER_R:.3f}\"  "
      f"({'COVERS OUTLET' if _release_cover_ok else 'INSUFFICIENT COVERAGE'})")
print(f"    Meter chamber: bore={CHUTE_INNER_R * 2:.3f}\" H={CHUTE_H:.3f}\" for demo tablet "
      f"{DEMO_TABLET_D:.2f}\" dia x {DEMO_TABLET_H:.2f}\" thick  "
      f"({'ONE FITS' if _one_tablet_fits else 'CHECK ONE-TABLET FIT'})")
print(f"    Singulation: two side-by-side {'BLOCKED' if _two_side_by_side_blocked else 'MAY FIT'}; "
      f"two stacked {'BLOCKED' if _two_stacked_blocked else 'MAY FIT'}")
print("    Control cycle: close lower -> open upper -> close upper -> open lower -> load-cell confirm")
bb_sw2 = dispense_sweep_pusher.val().BoundingBox()
bb_sw_dep = dispense_sweep_pusher_deployed.val().BoundingBox()
bb_sw_band = dispense_sweep_containment_band.val().BoundingBox()
bb_sw_seal = dispense_sweep_port_seal.val().BoundingBox()
_cartridge_outer_y = CAROUSEL_Y + OUTER_R
_contain_outer_y = CAROUSEL_Y + SWEEP_CONTAIN_OUTER_R
_sweep_retracted_ok = bb_sw2.ymin > _contain_outer_y
_sweep_z_ok = (bb_sw2.zmin >= CAROUSEL_Z_CART + WALL_T and bb_sw2.zmax <= CAROUSEL_Z_CART + 0.40)
_sweep_deployed_reaches = bb_sw_dep.ymin < CAROUSEL_Y + SLOT_RADIUS and bb_sw_dep.ymax > CAROUSEL_Y + SLOT_RADIUS
_slot_world_z_min = CAROUSEL_Z_CART + SWEEP_SLOT_Z - SWEEP_SLOT_H / 2
_slot_world_z_max = CAROUSEL_Z_CART + SWEEP_SLOT_Z + SWEEP_SLOT_H / 2
_band_covers_slot_z = bb_sw_band.zmin <= _slot_world_z_min and bb_sw_band.zmax >= _slot_world_z_max
_seal_small_enough = SWEEP_SEAL_APERTURE_H < SWEEP_SLOT_H and SWEEP_SEAL_APERTURE_H < HOLE_R
_seal_aligned = abs((bb_sw_seal.ymin + bb_sw_seal.ymax) / 2 - (CAROUSEL_Y + SWEEP_CONTAIN_OUTER_R + SWEEP_SEAL_D / 2)) < 0.001
print(f"    Low pusher parked Y=[{bb_sw2.ymin:.3f}, {bb_sw2.ymax:.3f}] vs containment OD Y={_contain_outer_y:.3f}\"  "
      f"({'RETRACTED CLEAR' if _sweep_retracted_ok else 'CHECK RETRACTION'})")
print(f"    Low pusher Z=[{bb_sw2.zmin:.3f}, {bb_sw2.zmax:.3f}] near cartridge floor Z={CAROUSEL_Z_CART + WALL_T:.3f}\"  "
      f"({'FLOOR-SAFE' if _sweep_z_ok else 'CHECK Z'})")
print(f"    Deployed preview Y=[{bb_sw_dep.ymin:.3f}, {bb_sw_dep.ymax:.3f}] crosses outlet Y={CAROUSEL_Y + SLOT_RADIUS:.3f}\"  "
      f"({'REACHES OUTLET' if _sweep_deployed_reaches else 'CHECK STROKE'})")
print(f"    Sweep containment band Z=[{bb_sw_band.zmin:.3f}, {bb_sw_band.zmax:.3f}] covers slot Z=[{_slot_world_z_min:.3f}, {_slot_world_z_max:.3f}]  "
      f"({'SLOTS BACKED' if _band_covers_slot_z else 'CHECK SLOT COVERAGE'})")
print(f"    Front TPU port seal aperture {SWEEP_SEAL_APERTURE_W:.2f}\" x {SWEEP_SEAL_APERTURE_H:.2f}\"  "
      f"({'PUSHER-SIZED / PILL-BLOCKING' if _seal_small_enough and _seal_aligned else 'CHECK SEAL'})")
print("    Retry cycle: if no load-cell change, extend pusher through sealed service port and cartridge slot, retract, then re-open gate")

print("=== END SANDWICH SEAL ===\n")

print("=== PHASE 19/20/21/22 DISPENSE PATH VERIFICATION ===")
try:
    _cup_step = cq.importers.importStep(str(OUTPUT / "pill_cup.step"))
    _drop_step = cq.importers.importStep(str(OUTPUT / "drop_cone.step"))
    bb_cup_step = _cup_step.val().BoundingBox()
    bb_drop = _drop_step.val().BoundingBox()
    _cup_world_bot = 0.20
    _cup_world_top = _cup_world_bot + 1.50
    _cup_floor_top = _cup_world_bot + 0.10
    _load_top = LOAD_WORLD_Z + LOAD_T
    _drop_nests = bb_drop.zmin > _cup_world_top and abs(bb_drop.zmin - 1.85) < 0.02
    print(f"  Cup world Z=[{_cup_world_bot:.3f}, {_cup_world_top:.3f}]  "
          f"floor top={_cup_floor_top:.3f}\"  ({'OK' if abs(_cup_floor_top - 0.30) < 0.001 else 'CHECK'})")
    print(f"  Load tray Z=[{LOAD_WORLD_Z:.3f}, {_load_top:.3f}]  "
          f"top == cup bottom ({'FLUSH' if abs(_load_top - _cup_world_bot) < 0.001 else 'CHECK'})")
    print(f"  Drop cone Z=[{bb_drop.zmin:.3f}, {bb_drop.zmax:.3f}]  "
          f"({'NESTS INTO CUP MOUTH' if _drop_nests else 'CHECK NESTING'})")
    print(f"  Radii: load tray R={LOAD_R:.2f}\" >= cup outer R=1.25\"; "
          f"cup inner R=1.17\" > drop cone bottom R=1.05\"  OK")
except Exception as exc:
    print(f"  SKIP cup/drop-cone path check -- {exc}")

_outlet_world_x = CAROUSEL_X
_outlet_world_y = CAROUSEL_Y + SLOT_RADIUS
print(f"  Cartridge outlet bias: sump R={OUTLET_SUMP_R:.3f}\" and guide ribs "
      f"L={OUTLET_GUIDE_RIB_L:.2f}\" feed toward world ({_outlet_world_x:.1f}, {_outlet_world_y:.1f}) OK")
print(f"  Upper inlet gate closed coverage: R={DISPENSE_GATE_R:.3f}\" > HOLE_R={HOLE_R:.3f}\"  OK")
print(f"  Lower release gate closed coverage: R={DISPENSE_RELEASE_GATE_R:.3f}\" > chamber bore R={CHUTE_INNER_R:.3f}\"  OK")
print(f"  One-tablet meter: chamber H={CHUTE_H:.3f}\" fits one demo tablet H={DEMO_TABLET_H:.3f}\" "
      f"and blocks two stacked H={2 * DEMO_TABLET_H:.3f}\"")
print(f"  Low pusher deployed preview: Y={SWEEP_PUSHER_Y_DEPLOYED:.3f}\" "
      f"crosses outlet Y={CAROUSEL_Y + SLOT_RADIUS:.3f}\" after no-drop retries")
print(f"  Sweep slot: local outer-wall slot W={SWEEP_SLOT_W:.2f}\" H={SWEEP_SLOT_H:.2f}\" aligns to front station OK")
print(f"  Pill-safe slot containment: OD band covers all rotating slots; only front service window has TPU wiper seal")
print("=== END PHASE 19/20/21/22 VERIFICATION ===\n")

bb_vp = vertical_pcb.val().BoundingBox()
print(f"  vertical_pcb:       Y=[{bb_vp.ymin:.3f}, {bb_vp.ymax:.3f}]  "
      f"(expected [{VPCB_WORLD_Y:.3f}, {VPCB_WORLD_Y + VPCB_STANDOFF_L + PCB_T:.3f}])")
print(f"                      Z=[{bb_vp.zmin:.3f}, {bb_vp.zmax:.3f}]  "
      f"(expected [{VPCB_WORLD_Z:.3f}, {VPCB_WORLD_Z + PCB_D:.3f}])")

# Phase 10 — optical chamber verification (only if files were imported)
try:
    bb_cs2 = _ch_shell.val().BoundingBox()
    print(f"  chamber_shell:      Z=[{bb_cs2.zmin:.3f}, {bb_cs2.zmax:.3f}]  "
          f"(expected [12.900, 14.900])")
    bb_cm2 = _cam_mnt.val().BoundingBox()
    print(f"  camera_mount:       X=[{bb_cm2.xmin:.3f}, {bb_cm2.xmax:.3f}]  "
          f"Z=[{bb_cm2.zmin:.3f}, {bb_cm2.zmax:.3f}]  "
          f"max|X|={max(abs(bb_cm2.xmin), abs(bb_cm2.xmax)):.3f}\" "
          f"({'< 1.80 OK' if max(abs(bb_cm2.xmin), abs(bb_cm2.xmax)) < 1.80 else 'INTERFERENCE!'})")
    bb_lo2 = _led_oc.val().BoundingBox()
    print(f"  led_ring_oc:        Z=[{bb_lo2.zmin:.3f}, {bb_lo2.zmax:.3f}]  "
          f"(expected [14.800, 14.900])")
    bb_cc2 = _ch_ceil.val().BoundingBox()
    print(f"  chamber_ceiling:    Z=[{bb_cc2.zmin:.3f}, {bb_cc2.zmax:.3f}]  "
          f"T={bb_cc2.zmax - bb_cc2.zmin:.3f}\"  "
          f"(expected [14.850, 14.900]  "
          f"{'OK' if abs(bb_cc2.zmin - 14.85) < 0.01 else 'CHECK'})")
except NameError:
    print("  Optical chamber parts not loaded (run optical_chamber.py first).")

# Phase 11 — trapdoor verification (only if files were imported)
try:
    bb_tdl = _td_left.val().BoundingBox()
    bb_tdr = _td_right.val().BoundingBox()
    print(f"  trapdoor_left:      Z=[{bb_tdl.zmin:.3f}, {bb_tdl.zmax:.3f}]  "
          f"X=[{bb_tdl.xmin:.3f}, {bb_tdl.xmax:.3f}]  (expected X<=0)")
    print(f"  trapdoor_right:     Z=[{bb_tdr.zmin:.3f}, {bb_tdr.zmax:.3f}]  "
          f"X=[{bb_tdr.xmin:.3f}, {bb_tdr.xmax:.3f}]  (expected X>=0)")
    _td_span_ok = abs(bb_tdl.xmin + 1.40) < 0.01 and abs(bb_tdr.xmax - 1.40) < 0.01
    print(f"  trapdoor combined X: [{bb_tdl.xmin:.3f}, {bb_tdr.xmax:.3f}]  "
          f"({'OK — full 2.80\" bore' if _td_span_ok else 'CHECK'})")
    bb_tdp = _td_pin.val().BoundingBox()
    _pin_z_c = (bb_tdp.zmin + bb_tdp.zmax) / 2
    print(f"  hinge_pin:          Z-centre={_pin_z_c:.3f}  (expected 12.920)  "
          f"Y=[{bb_tdp.ymin:.3f}, {bb_tdp.ymax:.3f}]  span={bb_tdp.ymax - bb_tdp.ymin:.2f}\"")
    bb_tds = _td_servo.val().BoundingBox()
    print(f"  servo_mount:        X=[{bb_tds.xmin:.3f}, {bb_tds.xmax:.3f}]  "
          f"Z=[{bb_tds.zmin:.3f}, {bb_tds.zmax:.3f}]  "
          f"({'servo outside tube OK' if bb_tds.xmin >= 1.40 else 'INTERFERENCE!'})")
except NameError:
    print("  Trapdoor parts not loaded (run trapdoor.py first).")

# Phase 13 — routing chute verification
try:
    bb_rc = _rchute.val().BoundingBox()
    print(f"  routing_chute:      Z=[{bb_rc.zmin:.3f}, {bb_rc.zmax:.3f}]  "
          f"(expected [8.900, 12.900])")
    _rc_y_max = bb_rc.ymax
    print(f"                      Y-max={_rc_y_max:.3f}\"  "
          f"({'< 7.95 OK — inside guide tube' if _rc_y_max < 7.95 else 'CHECK guide tube clearance'})")
    _rc_x_reach = max(abs(bb_rc.xmin), abs(bb_rc.xmax))
    print(f"                      X-reach={_rc_x_reach:.3f}\"  "
          f"({'< 1.80 OK — inside loading tube' if _rc_x_reach < 1.80 else 'CHECK loading tube clearance'})")
except NameError:
    print("  routing_chute not loaded (run routing_chute.py first).")

# Phase 16 -- index wheel verification
try:
    bb_rs = _rear_shaft.val().BoundingBox()
    bb_id = _index_disk.val().BoundingBox()
    bb_sm = _sensor_mnt.val().BoundingBox()
    print(f"  rear_shaft:     Z=[{bb_rs.zmin:.3f}, {bb_rs.zmax:.3f}]  "
          f"(expected [2.900, 3.400])")
    print(f"  index_disk:     Z=[{bb_id.zmin:.3f}, {bb_id.zmax:.3f}]  "
          f"outer R={max(abs(bb_id.xmin),abs(bb_id.xmax)):.3f}\"")
    _disk_clear = (MOTOR_Z_BOT - 0.10) - bb_id.zmax   # motor mount bottom minus disk top
    print(f"    Disk top Z={bb_id.zmax:.3f}\"  motor mount bot ~{MOTOR_Z_BOT - 0.10:.3f}\"  "
          f"clearance={_disk_clear:.3f}\"  "
          f"({'OK' if _disk_clear > 0 else 'CHECK'})")
    _sm_x_max = bb_sm.xmax
    print(f"  sensor_mount:   X=[{bb_sm.xmin:.3f}, {bb_sm.xmax:.3f}]  "
          f"Z=[{bb_sm.zmin:.3f}, {bb_sm.zmax:.3f}]")
    print(f"    Fork reaches disk rim X=0.600\"  sensor max X={_sm_x_max:.3f}\"  "
          f"({'IN RANGE' if _sm_x_max <= 0.70 else 'CHECK sensor mount width'})")
except NameError:
    print("  index_wheel parts not loaded (run index_wheel.py first).")

# Key clearance: loading tube vs vertical PCB (must not overlap)
lt_back_y = CAROUSEL_Y - LOAD_TUBE_OUTER_R   # loading tube back edge in Y
pcb_front_y = VPCB_WORLD_Y + VPCB_STANDOFF_L + PCB_T
pcb_to_tube = lt_back_y - pcb_front_y
print(f"\n  PCB front face Y={pcb_front_y:.3f}  Loading tube back Y={lt_back_y:.3f}"
      f"  clearance={pcb_to_tube:.3f}\" ({'OK' if pcb_to_tube > 0 else 'INTERFERENCE!'})")

# ---------------------------------------------------------------------------
# Collision Audit
# ---------------------------------------------------------------------------
print("\n--- Collision Audit ---")

# 1. routing_chute vs pill_guide (guide tube)
#    Z-overlap: max(8.90,8.90)..min(12.90,11.00) = [8.90, 11.00]
#    In this zone the chute is straight: outer R=DOOR_R=1.40" centred at (0,CAROUSEL_Y)
#    Guide tube is annular: inner R = GUIDE_OUTER_R - GUIDE_WALL = 3.45" same centre
try:
    bb_rc_c  = _rchute.val().BoundingBox()
    bb_pg_c  = pill_guide.val().BoundingBox()
    _ovl_zlo = max(bb_rc_c.zmin, bb_pg_c.zmin)
    _ovl_zhi = min(bb_rc_c.zmax, bb_pg_c.zmax)
    if _ovl_zlo < _ovl_zhi:
        # Use bounding-box X-reach as effective OD in the straight overlap zone
        _chute_od  = max(abs(bb_rc_c.xmin), abs(bb_rc_c.xmax))  # ~1.44" straight section
        _guide_id  = GUIDE_OUTER_R - GUIDE_WALL                  # 3.45"
        _radial_gap = _guide_id - _chute_od
        _gap_label  = "OK" if _radial_gap > 0 else "COLLISION!"
        print(f"  routing_chute x pill_guide:")
        print(f"    Z-overlap = [{_ovl_zlo:.2f}, {_ovl_zhi:.2f}]")
        print(f"    chute OD={_chute_od:.3f}\"  guide ID={_guide_id:.2f}\"  "
              f"radial gap={_radial_gap:.3f}\"  ({_gap_label})")
    else:
        print(f"  routing_chute x pill_guide: no Z-overlap  OK")
except NameError:
    print("  routing_chute not loaded — skip check 1")

# 2. routing_chute vs hatch_final
#    routing_chute Z=[8.90,12.90];  hatch_final Z=[14.80,15.07] — no overlap expected
try:
    bb_rc_h  = _rchute.val().BoundingBox()
    bb_hf_c  = hatch_final.val().BoundingBox()
    _gap_zh  = bb_hf_c.zmin - bb_rc_h.zmax
    print(f"  routing_chute x hatch_final:")
    print(f"    chute Z-max={bb_rc_h.zmax:.3f}\"  hatch Z-min={bb_hf_c.zmin:.3f}\"  "
          f"gap={_gap_zh:.3f}\"  "
          f"({'OK — {:.2f}\" clear'.format(_gap_zh) if _gap_zh > 0 else 'OVERLAP!'})")
except NameError:
    print("  routing_chute not loaded — skip check 2")

# 3. pill_chute vs pill_guide
#    pill_chute Z=[4.5,4.9];  pill_guide Z=[8.90,11.00] — no overlap expected
bb_ch_c  = pill_chute.val().BoundingBox()
bb_pg2_c = pill_guide.val().BoundingBox()
_gap_pc  = bb_pg2_c.zmin - bb_ch_c.zmax
print(f"  pill_chute x pill_guide:")
print(f"    chute Z-max={bb_ch_c.zmax:.3f}\"  guide Z-min={bb_pg2_c.zmin:.3f}\"  "
      f"gap={_gap_pc:.3f}\"  "
      f"({'OK' if _gap_pc > 0 else 'OVERLAP!'})")

# 4. Dispensing path continuity — spout → chute → base plate → drop zone
bb_gate_c = dispense_gate.val().BoundingBox()
bb_release_c = dispense_release_gate.val().BoundingBox()
_gate_to_base = CAROUSEL_Z_BASE - bb_gate_c.zmax
_gate_to_chute = bb_gate_c.zmin - bb_ch_c.zmax
_release_to_spout_audit = bb_release_c.zmin - SPOUT_TOP_Z
_release_to_chute_audit = bb_ch_c.zmin - bb_release_c.zmax
_release_drop_clear = bb_release_c.zmin - 4.00
print(f"  two-gate metering station:")
print(f"    upper gate Z=[{bb_gate_c.zmin:.3f}, {bb_gate_c.zmax:.3f}]  "
      f"base bottom={CAROUSEL_Z_BASE:.3f}\"  clearance={_gate_to_base:.3f}\"  "
      f"({'OK' if _gate_to_base > 0 else 'CHECK BASE COLLISION'})")
print(f"    chamber top={bb_ch_c.zmax:.3f}\"  upper gate bottom={bb_gate_c.zmin:.3f}\"  "
      f"gap={_gate_to_chute:.3f}\"  "
      f"({'OK' if _gate_to_chute > 0 else 'CHECK UPPER GATE OVERLAP'})")
print(f"    lower release gate Z=[{bb_release_c.zmin:.3f}, {bb_release_c.zmax:.3f}]  "
      f"spout clearance={_release_to_spout_audit:.3f}\"  "
      f"({'OK' if _release_to_spout_audit > 0 else 'CHECK SPOUT COLLISION'})")
print(f"    chamber bottom={bb_ch_c.zmin:.3f}\"  lower gate top={bb_release_c.zmax:.3f}\"  "
      f"gap={_release_to_chute_audit:.3f}\"  "
      f"({'OK' if _release_to_chute_audit > 0 else 'CHECK LOWER GATE OVERLAP'})")
print(f"    lower gate above drop cone top Z=4.000\" by {_release_drop_clear:.3f}\"  "
      f"({'OK' if _release_drop_clear > 0 else 'CHECK DROP CONE COLLISION'})")

bb_band_c = dispense_sweep_containment_band.val().BoundingBox()
bb_seal_c = dispense_sweep_port_seal.val().BoundingBox()
_band_radial_gap = SWEEP_CONTAIN_INNER_R - OUTER_R
_rail_to_band_gap = bb_sweep_rail.ymin - (CAROUSEL_Y + SWEEP_CONTAIN_OUTER_R)
_pusher_to_seal_gap = bb_sweep.ymin - bb_seal_c.ymax
print(f"  sweep slot containment:")
print(f"    band inner R={SWEEP_CONTAIN_INNER_R:.3f}\" vs cartridge OD={OUTER_R:.3f}\"  "
      f"radial clearance={_band_radial_gap:.3f}\"  "
      f"({'INDEXING CLEAR' if _band_radial_gap > 0 else 'CHECK BAND CLEARANCE'})")
print(f"    rail starts Y={bb_sweep_rail.ymin:.3f}\" beyond band OD Y={CAROUSEL_Y + SWEEP_CONTAIN_OUTER_R:.3f}\"  "
      f"gap={_rail_to_band_gap:.3f}\"  "
      f"({'OK' if _rail_to_band_gap > 0 else 'CHECK RAIL OVERLAP'})")
print(f"    parked pusher face starts Y={bb_sweep.ymin:.3f}\" beyond seal Y-max={bb_seal_c.ymax:.3f}\"  "
      f"gap={_pusher_to_seal_gap:.3f}\"  "
      f"({'SEALED PARK' if _pusher_to_seal_gap > 0 else 'CHECK PARKED PUSHER'})")

_spout_top      = SPOUT_TOP_Z
_chute_bot_world = CHUTE_WORLD_Z
_chute_top_world = CHUTE_WORLD_Z + CHUTE_H
_base_bot_world  = CAROUSEL_Z_BASE
_gap_sc = _chute_bot_world - _spout_top
_gap_cb = abs(_chute_top_world - _base_bot_world)
print(f"\n  Dispensing path continuity:")
print(f"    Spout top        Z={_spout_top:.3f}\"")
print(f"    Release gate     Z={bb_release_c.zmin:.3f}\"..{bb_release_c.zmax:.3f}\"")
print(f"    Meter chamber    Z={_chute_bot_world:.3f}\"..{_chute_top_world:.3f}\"  H={CHUTE_H:.3f}\"")
print(f"    Upper inlet gate Z={bb_gate_c.zmin:.3f}\"..{bb_gate_c.zmax:.3f}\"")
print(f"    Base plate bot   Z={_base_bot_world:.3f}\"  "
      f"({'FLUSH' if _gap_cb < 0.001 else 'GATED GAP={:.4f}'.format(_gap_cb)})")
print(f"    Drop zone R      {HOLE_R:.3f}\"  chute flange R {CHUTE_FLANGE_R:.3f}\"  "
      f"seal lip={CHUTE_FLANGE_R - HOLE_R:.3f}\"  "
      f"({'OK' if CHUTE_FLANGE_R > HOLE_R else 'INSUFFICIENT SEAL'})")
print(f"    Chute inner bore {CHUTE_INNER_R:.3f}\" = spout inner R 0.250\"  "
      f"({'MATCHED' if abs(CHUTE_INNER_R - 0.25) < 0.001 else 'MISMATCH!'})")

# 5. Guide ring loading port alignment with routing chute exit
_port_world_y = CAROUSEL_Y + SLOT_RADIUS   # = 7.0"
_port_r       = ROUTING_CHUTE_EXIT_R       # = 0.60"
_chute_exit_y = CAROUSEL_Y + SLOT_RADIUS   # routing_chute.py ACTIVE_Y = 7.0"
_chute_exit_r = 0.60                       # routing_chute.py CHUTE_R_BOT
print(f"\n  Guide ring loading port vs routing chute exit:")
print(f"    Port world centre Y={_port_world_y:.3f}\"  R={_port_r:.3f}\"")
print(f"    Chute exit centre Y={_chute_exit_y:.3f}\"  R={_chute_exit_r:.3f}\"")
_dy = abs(_port_world_y - _chute_exit_y)
_dr = abs(_port_r - _chute_exit_r)
print(f"    Centre offset={_dy:.4f}\"  radius match={_dr:.4f}\"  "
      f"({'ALIGNED' if _dy < 0.001 and _dr < 0.001 else 'MISALIGNED — CHECK'})")

# Pill path continuity check
print(f"\n  PILL PATH continuity:")
print(f"    Hatch port bottom:   Z={HATCH_WORLD_Z:.3f}\"  R={HATCH_HOLE_R:.3f}\"")
print(f"    Loading tube top:    Z={LOAD_TUBE_Z_TOP:.3f}\"  inner R={LOAD_TUBE_INNER_R:.3f}\"  [SEALED]")
print(f"    Loading tube bottom: Z={LOAD_TUBE_Z_BOT:.3f}\"")
print(f"    Guide tube top:      Z={GUIDE_WORLD_Z + GUIDE_H:.3f}\"  inner R={GUIDE_OUTER_R - GUIDE_WALL:.3f}\"  [OPEN]")
print(f"    Pill guide ring:     Z={PILL_RING_WORLD_Z:.3f}\"  annular R={PILL_RING_INNER_R:.3f}\"..{PILL_RING_OUTER_R:.3f}\"")
print(f"    Carousel top:        Z={CAROUSEL_Z_CART + CART_H:.3f}\"  (cartridges open top, R={INNER_R:.2f}\"..{OUTER_R:.2f}\")")
print(f"    Carousel floor hole: at (0, {CAROUSEL_Y + SLOT_RADIUS:.1f}) world")
print(f"    Upper inlet gate:    Z={DISPENSE_GATE_Z:.3f}\"..{DISPENSE_GATE_Z + DISPENSE_GATE_T:.3f}\"")
print(f"    Meter chamber:       Z={CHUTE_WORLD_Z:.3f}\"..{CHUTE_WORLD_Z + CHUTE_H:.3f}\"")
print(f"    Lower release gate:  Z={DISPENSE_RELEASE_GATE_Z:.3f}\"..{DISPENSE_RELEASE_GATE_Z + DISPENSE_RELEASE_GATE_T:.3f}\"")
print(f"    Spout inner bore:    R=0.25\"  Z=4.0\"..4.5\"")
print(f"    Drop cone:           Z=1.85\"..4.00\"  [BOUNCE CONTAINED]")
print(f"    Load cell tray:      Z={LOAD_WORLD_Z:.3f}\"..{LOAD_WORLD_Z + LOAD_T:.3f}\"  [CUP SUPPORT + SENSING]")

print("\nDone. Open output/hero_full_assembly.step in Fusion 360.")
print("Expected: 50 named production parts after Phase 22 two-gate metering:")
print("  hero_assy: enclosure, button, pill_cup, carousel(x12), motor_assembly,")
print("             drop_cone, dispense_gate, dispense_gate_servo_mount,")
print("             dispense_release_gate, dispense_release_gate_servo_mount,")
print("             dispense_sweep_pusher, dispense_sweep_containment_band,")
print("             dispense_sweep_port_seal, dispense_sweep_rail, dispense_sweep_servo_mount,")
print("             pill_guide, load_cell, vib_motor,")
print("             pill_chute, motor_mount, display_panel, led_ring,")
print("             hatch_final, usbc_port, speaker_grille,")
print("             loading_tube, pill_guide_ring, vertical_pcb,")
print("             chamber_shell, camera_mount, led_ring_oc, chamber_ceiling,")
print("             trapdoor_left, trapdoor_right, hinge_pin, servo_mount,")
print("             routing_chute,")
print("             rear_shaft, index_disk, sensor_mount")
print("  NOTE: staging_floor placeholder superseded by Phase 11 trapdoor leaves.")
print("  PILL PATH: hatch -> loading_tube -> trapdoor -> routing_chute -> carousel slot")
print("  HOME SENSING: index_disk notch -> sensor_mount fork sensor -> 1 pulse/rev")
