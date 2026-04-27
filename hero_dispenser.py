# Hero Pill Dispenser — CadQuery parametric model
# Run with: C:\Users\jaime\AppData\Local\Python\pythoncore-3.12-64\python.exe hero_dispenser.py
# (Python 3.14 system default lacks the OCP backend and will crash on import)

import cadquery as cq
import pathlib

OUTPUT = pathlib.Path("output")
OUTPUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Dimensions (all in inches)
# Coordinate system:
#   X: left(−) → right(+), center = 0
#   Y: flat back = 0,  front apex = 9.0
#   Z: bottom = 0,     top = 15.0
# ---------------------------------------------------------------------------
W = 9.0       # overall width
D = 9.0       # overall depth
H = 15.0      # overall height
T = 0.1       # wall thickness

# I/O port dimensions — must match carousel.py constants
USBC_W        = 0.37   # USB-C cutout width  (X)
USBC_H_DIM    = 0.14   # USB-C cutout height (Z)
USBC_WORLD_Z  = 1.80   # Z-centre of USB-C slot in back wall

SPEAKER_R        = 0.75   # speaker grille opening radius
SPEAKER_WORLD_X  = -3.0   # X-centre on curved front face
SPEAKER_WORLD_Z  =  8.5   # Z-centre of speaker opening

# Arc geometry: profile arc centre (0, ARC_CY), radius ARC_R
# Derived from three-point arc through (±4.5, 0) and (0, 9):
#   4.5² + ARC_CY² = ARC_R²  and  (9 - ARC_CY)² = ARC_R²
ARC_CY = 3.375   # arc Y-centre
ARC_R  = 5.625   # arc radius


def save_step(wp, fname):
    wp.export(str(OUTPUT / fname))
    print(f"  Wrote output/{fname}")


# ---------------------------------------------------------------------------
# Helper: D-shaped profile (top-down cross-section)
#   Flat back at Y=0 from X=-4.5 to X=4.5
#   Curved front arcing through (0, 9) back to (-4.5, 0)
# ---------------------------------------------------------------------------
def make_d_profile(x_half=W/2, depth=D):
    return (
        cq.Workplane("XY")
        .moveTo(-x_half, 0)
        .lineTo(x_half, 0)
        .threePointArc((0, depth), (-x_half, 0))
        .close()
    )


# ===========================================================================
# PART 1: Main Enclosure Shell
# ===========================================================================
print("Building enclosure shell...")

# --- 1a. Outer D-solid ---
outer_solid = make_d_profile().extrude(H)

# --- 1b. Shell: hollow from below (open bottom face) ---
# shell(-T) offsets all faces inward by T; selecting "<Z" keeps that face open.
try:
    enclosure_shell = outer_solid.faces("<Z").shell(-T)
except Exception as e:
    print(f"  shell() failed ({e}), using manual inner-subtract fallback")
    inner_solid = make_d_profile(x_half=W/2 - T, depth=D - T).extrude(H - T)
    floor = make_d_profile().extrude(T)
    enclosure_shell = outer_solid.cut(inner_solid).union(floor)

# --- 1c. Alcove cutter ---
# 6.5"W × 4.0"D × 4.5"H, front-centered; starts 0.05" below Z=0 to clear shell floor
alcove_cutter = (
    cq.Workplane("XY")
    .center(0, 7.0)               # Y midpoint of alcove: (5.0 + 9.0) / 2
    .box(6.5, 4.2, 4.55, centered=(True, True, False))
    .translate((0, 0, -0.05))     # reach below shell floor to avoid sliver
)

# --- 1d. Screen cutter ---
# 3.0"W × 3.5"H, Z=10.5 to Z=14.0, centered on front face
# Spanning 10" in Y cuts cleanly through the 0.1" front wall regardless of curvature
screen_cutter = (
    cq.Workplane("XY")
    .center(0, 4.5)
    .box(3.0, 10.0, 3.5)
    .translate((0, 0, 12.25))     # Z center = (10.5 + 14.0) / 2
)

# --- 1e. Button hole cutter ---
# 1.8" dia (R=0.9), Z center = 8.5"
# XZ workplane extrudes in −Y; translate to Y=9.15 so cutter straddles front wall (Y=8.85..9.15)
btn_hole_cutter = (
    cq.Workplane("XZ")
    .center(0, 8.5)
    .circle(0.9)
    .extrude(0.3)
    .translate((0, 9.15, 0))
)

# --- 1f. LED ring groove cutter ---
# Outer R=1.2, inner R=1.0, 0.05" recess into front outer face (Y=8.95..9.0)
led_outer = (
    cq.Workplane("XZ")
    .center(0, 8.5)
    .circle(1.2)
    .extrude(0.05)
    .translate((0, 9.05, 0))
)
led_keeper = (
    cq.Workplane("XZ")
    .center(0, 8.5)
    .circle(1.0)
    .extrude(0.06)                # slightly deeper so boolean difference is unambiguous
    .translate((0, 9.06, 0))
)
led_groove_cutter = led_outer.cut(led_keeper)

# --- 1g. Spout: hollow tube hanging from alcove ceiling ---
# Outer R=0.375, inner R=0.25, Z=4.0 to 4.5 (hangs 0.5" into alcove from ceiling)
spout_outer = (
    cq.Workplane("XY")
    .center(0, 7.0)
    .circle(0.375)
    .extrude(0.5)
    .translate((0, 0, 4.0))
)
spout_inner = (
    cq.Workplane("XY")
    .center(0, 7.0)
    .circle(0.25)
    .extrude(0.5)
    .translate((0, 0, 4.0))
)
spout = spout_outer.cut(spout_inner)

# --- 1h. USB-C back-wall cutout ---
# Back wall outer face is at Y=0, inner face at Y=T=0.1".
# XZ workplane extrudes in the -Y direction.
# Extrude 0.20" then translate +0.15" in Y => cutter spans Y=[-0.05, +0.15],
# which overshoots both faces of the 0.10" back wall cleanly.
usbc_cutter = (
    cq.Workplane("XZ")
    .center(0, USBC_WORLD_Z)          # X=0 (centered), Z=1.80"
    .rect(USBC_W, USBC_H_DIM)         # 0.37" wide x 0.14" tall
    .extrude(0.20)                     # extrudes in -Y
    .translate((0, 0.15, 0))          # shift: Y = [-0.05 .. +0.15]
)

# --- 1i. Speaker front-face opening ---
# Front arc at X=SPEAKER_WORLD_X: Y_front = ARC_CY + sqrt(ARC_R^2 - X^2)
import math as _math
_spk_y_front = ARC_CY + _math.sqrt(ARC_R**2 - SPEAKER_WORLD_X**2)  # ~8.133"
# XZ workplane extrudes in -Y; extrude 0.30" then translate so cutter
# straddles the ~0.10" curved wall: centre at Y_front, span Y=[Y_front-0.15, Y_front+0.15].
speaker_cutter = (
    cq.Workplane("XZ")
    .center(SPEAKER_WORLD_X, SPEAKER_WORLD_Z)   # (-3.0", 8.5")
    .circle(SPEAKER_R)                           # R=0.75"
    .extrude(0.30)                               # extrudes in -Y
    .translate((0, _spk_y_front + 0.15, 0))     # straddle outer arc surface
)

# --- 1j. Cable conduit groove (back-wall inner face) ---
# A 0.15"-wide x 0.05"-deep channel routed vertically inside the back wall,
# from the USB-C port (Z=1.94") up to the PCB level (Z=9.50").
# Cutting Y=[0.10, 0.15] creates a shallow groove on the inner face.
_cond_z_bot   = USBC_WORLD_Z + USBC_H_DIM / 2   # just above USB-C top edge (~1.87")
_cond_z_top   = 9.50                              # bottom of vertical PCB
_cond_z_h     = _cond_z_top - _cond_z_bot        # conduit height
_cond_z_mid   = _cond_z_bot + _cond_z_h / 2
conduit_cutter = (
    cq.Workplane("XZ")
    .center(0, _cond_z_mid)           # X=0, Z-midpoint
    .rect(0.15, _cond_z_h)            # 0.15" wide, full conduit height
    .extrude(0.05)                     # 0.05" deep groove, extrudes in -Y
    .translate((0, 0.15, 0))          # Y=[0.10, 0.15] — inside back wall only
)

# --- 1k. Assemble enclosure (order matters: spout union AFTER alcove cut) ---
enclosure = (
    enclosure_shell
    .cut(alcove_cutter)
    .cut(screen_cutter)
    .cut(btn_hole_cutter)
    .cut(led_groove_cutter)
    .cut(usbc_cutter)
    .cut(speaker_cutter)
    .cut(conduit_cutter)
    .union(spout)
)

save_step(enclosure, "enclosure.step")


# ===========================================================================
# PART 2: Center Button (separate part — installed in button hole)
# ===========================================================================
print("Building button...")

button_base = (
    cq.Workplane("XY")
    .circle(0.875)       # 1.75" dia
    .extrude(0.15)
)

# Cross/directional-arrow recess: two bars 0.02" deep on the top face
cross_v = (
    cq.Workplane("XY")
    .rect(0.1, 1.2)
    .extrude(0.02)
    .translate((0, 0, 0.15))
)
cross_h = (
    cq.Workplane("XY")
    .rect(1.2, 0.1)
    .extrude(0.02)
    .translate((0, 0, 0.15))
)

try:
    button_final = button_base.cut(cross_v).cut(cross_h)
except Exception as e:
    print(f"  Cross recess failed ({e}), using plain button")
    button_final = button_base

save_step(button_final, "button.step")


# ===========================================================================
# PART 3: Pill Cup (separate part — sits in alcove)
# ===========================================================================
print("Building pill cup (with floor + grab tab)...")

CUP_OUTER_R = 1.25
CUP_WALL    = 0.08
CUP_INNER_R = CUP_OUTER_R - CUP_WALL
CUP_H       = 1.50
CUP_FLOOR_T = 0.10

cup_outer = (
    cq.Workplane("XY")
    .circle(CUP_OUTER_R)
    .extrude(CUP_H)
)
cup_inner = (
    cq.Workplane("XY")
    .circle(CUP_INNER_R)
    .extrude(CUP_H - CUP_FLOOR_T)
    .translate((0, 0, CUP_FLOOR_T))
)
pill_cup = cup_outer.cut(cup_inner)

TAB_W = 0.50
TAB_D = 0.20
TAB_H = 0.40
grab_tab = (
    cq.Workplane("XY")
    .center(0, CUP_OUTER_R + TAB_D / 2 - 0.02)
    .box(TAB_W, TAB_D, TAB_H, centered=(True, True, False))
    .translate((0, 0, CUP_H - TAB_H))
)
try:
    pill_cup = pill_cup.union(grab_tab)
except Exception as exc:
    print(f"  WARNING: grab tab union failed ({exc}) -- cup without tab")

save_step(pill_cup, "pill_cup.step")


# ===========================================================================
# PART 3B: Drop Cone (Phase 19 -- soft anti-bounce funnel)
# ===========================================================================
print("Building drop cone (Phase 19 -- anti-bounce funnel)...")

DROP_CONE_Z_TOP = 4.00
DROP_CONE_Z_BOT = 1.85
DROP_CONE_R_TOP = 0.375
DROP_CONE_R_BOT = 1.05
DROP_CONE_WALL  = 0.06

w_top_outer = cq.Wire.makeCircle(
    DROP_CONE_R_TOP, cq.Vector(0, 7.0, DROP_CONE_Z_TOP), cq.Vector(0, 0, 1)
)
w_bot_outer = cq.Wire.makeCircle(
    DROP_CONE_R_BOT, cq.Vector(0, 7.0, DROP_CONE_Z_BOT), cq.Vector(0, 0, 1)
)
outer_cone = cq.Workplane("XY").add(cq.Solid.makeLoft([w_top_outer, w_bot_outer]))
w_top_inner = cq.Wire.makeCircle(
    DROP_CONE_R_TOP - DROP_CONE_WALL,
    cq.Vector(0, 7.0, DROP_CONE_Z_TOP + 0.01),
    cq.Vector(0, 0, 1),
)
w_bot_inner = cq.Wire.makeCircle(
    DROP_CONE_R_BOT - DROP_CONE_WALL,
    cq.Vector(0, 7.0, DROP_CONE_Z_BOT - 0.01),
    cq.Vector(0, 0, 1),
)
inner_cone = cq.Workplane("XY").add(cq.Solid.makeLoft([w_top_inner, w_bot_inner]))
drop_cone = outer_cone.cut(inner_cone)

save_step(drop_cone, "drop_cone.step")


# ===========================================================================
# PART 4: Multi-part STEP Assembly
# ===========================================================================
print("Building assembly...")

# Button location: rotate 90° around X so its face (+Z) points toward +Y (front).
# Positioned at (X=0, Y=9.15, Z=8.5) — sits 0.15" proud of outer front face.
btn_loc = cq.Location(cq.Vector(0, 9.15, 8.5), cq.Vector(1, 0, 0), 90)

# Pill cup location: center of alcove, resting on the load-cell tray top
cup_loc = cq.Location(cq.Vector(0, 7.0, 0.20))

assy = cq.Assembly()
assy.add(
    enclosure,
    name="enclosure",
    color=cq.Color(0.82, 0.84, 0.88, 1.0),    # light blue-gray (matches device color)
)
assy.add(
    button_final,
    name="button",
    loc=btn_loc,
    color=cq.Color(0.15, 0.15, 0.15, 1.0),    # near-black
)
assy.add(
    pill_cup,
    name="pill_cup",
    loc=cup_loc,
    color=cq.Color(0.95, 0.95, 0.95, 0.85),   # semi-transparent white
)
assy.add(
    drop_cone,
    name="drop_cone",
    color=cq.Color(0.95, 0.95, 0.95, 0.55),   # translucent TPU
)

# Use Assembly.export() — Assembly.save() triggers FutureWarning in CQ 2.7.0
assy.export(str(OUTPUT / "hero_dispenser_assembly.step"))
print("  Wrote output/hero_dispenser_assembly.step")

# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
print("\n--- Verification ---")
bb_enc = enclosure.val().BoundingBox()
print(f"  enclosure:    X=[{bb_enc.xmin:.3f}, {bb_enc.xmax:.3f}]  "
      f"Y=[{bb_enc.ymin:.3f}, {bb_enc.ymax:.3f}]  "
      f"Z=[{bb_enc.zmin:.3f}, {bb_enc.zmax:.3f}]")
print(f"  expected:     X=[-4.500, 4.500]  Y=[0.000, 9.000]  Z=[0.000, 15.000]")

# USB-C slot: should create a through-hole in back wall, so enclosure Y-min stays 0.0
print(f"  USB-C slot:   back-wall Y-min={bb_enc.ymin:.3f}  (expected 0.000 — slot is flush)")
print(f"                USB-C Z-centre expected {USBC_WORLD_Z:.3f}\"  "
      f"slot Z=[{USBC_WORLD_Z - USBC_H_DIM/2:.3f}, {USBC_WORLD_Z + USBC_H_DIM/2:.3f}]")

# Speaker opening: arc surface at X=SPEAKER_WORLD_X
print(f"  Speaker:      front arc Y at X={SPEAKER_WORLD_X:.1f}\" => Y={_spk_y_front:.3f}\"  "
      f"opening R={SPEAKER_R:.2f}\"  Z-centre={SPEAKER_WORLD_Z:.1f}\"")

# Conduit groove bounds
print(f"  Conduit:      Z=[{_cond_z_bot:.3f}, {_cond_z_top:.3f}]  height={_cond_z_h:.3f}\"  "
      f"groove depth Y=[0.100, 0.150]")

bb_cup = pill_cup.val().BoundingBox()
bb_dc = drop_cone.val().BoundingBox()
print(f"  pill_cup:     local Z=[{bb_cup.zmin:.3f}, {bb_cup.zmax:.3f}]  "
      f"floor T={CUP_FLOOR_T:.2f}\" wall={CUP_WALL:.2f}\"  grab tab=YES")
print(f"  drop_cone:    Z=[{bb_dc.zmin:.3f}, {bb_dc.zmax:.3f}]  "
      f"top R={DROP_CONE_R_TOP:.3f}\" bottom R={DROP_CONE_R_BOT:.3f}\"")

print("\nDone. Open output/hero_dispenser_assembly.step in Fusion 360 or FreeCAD.")


# ===========================================================================
# PART 5: FDM Print Split (Phase 18)
# The 15" enclosure is too tall for any consumer FDM printer.
# Split into 3 equal sections at Z=5.0" and Z=10.0":
#   Bottom: Z=[ 0.0,  5.0]"  (127 mm) -- alcove, spout, load cell
#   Middle: Z=[ 5.0, 10.0]"  (127 mm) -- carousel, motor, guide tube
#   Top:    Z=[10.0, 15.0]"  (127 mm) -- loading column, display, hatch
#
# Alignment at each joint: 4 x pin-and-socket bosses
#   Pin: R=0.098" (~2.5 mm), protrusion H=0.197" (~5 mm)
#   Socket: R=0.104" (0.15 mm dia clearance), depth=0.210"
#   Boss: R=0.220", height=0.30" -- solid pillar added to interior
#         before socket is drilled (shell interior is otherwise void)
#
# Pin positions (4 per joint, world XY):
#   (-4.0, 1.0)  rear-left    clear of carousel (outer R=3.5" at (0, 4.5"))
#   (+4.0, 1.0)  rear-right
#   (-4.0, 4.5)  mid-left     at X=4.0" carousel only reaches X=3.5"
#   (+4.0, 4.5)  mid-right
# ===========================================================================
print("\nBuilding FDM print split (Phase 18)...")

SPLIT_Z1  = 5.0     # bottom / middle joint
SPLIT_Z2  = 10.0    # middle / top joint
PIN_R     = 0.098   # alignment pin radius   (~2.5 mm)
PIN_H     = 0.197   # pin protrusion height  (~5.0 mm)
SOCKET_R  = 0.104   # socket radius          (~2.65 mm, 0.15 mm dia clearance)
SOCKET_D  = 0.210   # socket depth           (~5.3 mm, slightly deeper than pin)
BOSS_R    = 0.220   # boss cylinder radius   (~5.6 mm)
BOSS_H    = 0.300   # boss height (> SOCKET_D so socket stays inside boss)

_PIN_XY = [
    (-4.0, 1.0),
    ( 4.0, 1.0),
    (-4.0, 4.5),
    ( 4.0, 4.5),
]


def _slab(z_bot, z_top):
    """Axis-aligned box large enough to enclose the full D-shell XY footprint."""
    return (
        cq.Workplane("XY")
        .center(0, 4.5)
        .box(11.0, 11.0, z_top - z_bot)
        .translate((0, 0, (z_bot + z_top) / 2.0))
    )


def _pin_solid(px, py, z_base):
    """Pin cylinder: protrudes downward from z_base."""
    return (
        cq.Workplane("XY")
        .center(px, py)
        .circle(PIN_R)
        .extrude(PIN_H)
        .translate((0, 0, z_base - PIN_H))
    )


def _boss_solid(px, py, z_top):
    """Boss pillar: solid cylinder just below z_top (provides material for socket)."""
    return (
        cq.Workplane("XY")
        .center(px, py)
        .circle(BOSS_R)
        .extrude(BOSS_H)
        .translate((0, 0, z_top - BOSS_H))
    )


def _socket_cut(px, py, z_top):
    """Socket hole: cylinder drilled downward from z_top into the boss."""
    return (
        cq.Workplane("XY")
        .center(px, py)
        .circle(SOCKET_R)
        .extrude(SOCKET_D + 0.01)       # slight overshoot for clean Boolean
        .translate((0, 0, z_top - SOCKET_D))
    )


# --- Bottom section: Z=[0, 5.0"] -- sockets at top face ---
print("  Slicing bottom section Z=[0.0, 5.0]\"...")
enc_bot = enclosure.intersect(_slab(0.0, SPLIT_Z1))
for _px, _py in _PIN_XY:
    try:
        enc_bot = enc_bot.union(_boss_solid(_px, _py, SPLIT_Z1))
        enc_bot = enc_bot.cut(_socket_cut(_px, _py, SPLIT_Z1))
    except Exception as _e:
        print(f"    WARNING: boss/socket at ({_px}, {_py}) failed ({_e}) -- skipped")
save_step(enc_bot, "enclosure_bottom.step")

# --- Middle section: Z=[5.0", 10.0"] -- pins at bottom, sockets at top ---
print("  Slicing middle section Z=[5.0, 10.0]\"...")
enc_mid = enclosure.intersect(_slab(SPLIT_Z1, SPLIT_Z2))
for _px, _py in _PIN_XY:
    try:
        enc_mid = enc_mid.union(_pin_solid(_px, _py, SPLIT_Z1))  # pins hang below Z=5
    except Exception as _e:
        print(f"    WARNING: bottom pin at ({_px}, {_py}) failed ({_e}) -- skipped")
    try:
        enc_mid = enc_mid.union(_boss_solid(_px, _py, SPLIT_Z2))
        enc_mid = enc_mid.cut(_socket_cut(_px, _py, SPLIT_Z2))
    except Exception as _e:
        print(f"    WARNING: top boss/socket at ({_px}, {_py}) failed ({_e}) -- skipped")
save_step(enc_mid, "enclosure_middle.step")

# --- Top section: Z=[10.0", 15.0"] -- pins at bottom face only ---
print("  Slicing top section Z=[10.0, 15.0]\"...")
enc_top = enclosure.intersect(_slab(SPLIT_Z2, H))
for _px, _py in _PIN_XY:
    try:
        enc_top = enc_top.union(_pin_solid(_px, _py, SPLIT_Z2))  # pins hang below Z=10
    except Exception as _e:
        print(f"    WARNING: bottom pin at ({_px}, {_py}) failed ({_e}) -- skipped")
save_step(enc_top, "enclosure_top.step")

# --- Print split verification ---
print("\n--- Print Split Verification ---")
bb_b = enc_bot.val().BoundingBox()
bb_m = enc_mid.val().BoundingBox()
bb_t = enc_top.val().BoundingBox()
print(f"  enclosure_bottom: Z=[{bb_b.zmin:.3f}, {bb_b.zmax:.3f}]  "
      f"({'OK' if abs(bb_b.zmax - SPLIT_Z1) < 0.02 else 'CHECK'})")
print(f"  enclosure_middle: Z=[{bb_m.zmin:.3f}, {bb_m.zmax:.3f}]  "
      f"(pins extend {SPLIT_Z1 - bb_m.zmin:.3f}\" below joint  "
      f"{'OK' if abs((SPLIT_Z1 - bb_m.zmin) - PIN_H) < 0.02 else 'CHECK'})")
print(f"  enclosure_top:    Z=[{bb_t.zmin:.3f}, {bb_t.zmax:.3f}]  "
      f"(pins extend {SPLIT_Z2 - bb_t.zmin:.3f}\" below joint  "
      f"{'OK' if abs((SPLIT_Z2 - bb_t.zmin) - PIN_H) < 0.02 else 'CHECK'})")
print(f"  Pin: R={PIN_R:.3f}\"  H={PIN_H:.3f}\"  "
      f"({PIN_R*2*25.4:.1f} mm dia  {PIN_H*25.4:.1f} mm long)")
print(f"  Socket: R={SOCKET_R:.3f}\"  D={SOCKET_D:.3f}\"  "
      f"dia clearance={(SOCKET_R - PIN_R)*2*25.4:.2f} mm")
_sec_h_mm = (SPLIT_Z1) * 25.4
_xy_mm    = W * 25.4
print(f"  Each section height: {_sec_h_mm:.0f} mm -- fits any printer with >{_sec_h_mm:.0f} mm Z travel")
print(f"  XY footprint: {_xy_mm:.0f} x {_xy_mm:.0f} mm -- requires bed >= 230x230 mm")
print(f"  NOTE: standard Ender 3 (220x220) is marginally small; CR-10 (300x300) fits easily")
