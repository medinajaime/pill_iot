# Hero Pill Dispenser — Static Routing Chute (Phase 13)
# Run AFTER trapdoor.py and BEFORE carousel.py.
# Run with: C:\Users\jaime\AppData\Local\Python\pythoncore-3.12-64\python.exe routing_chute.py
#
# Purpose: catch pills released by the trapdoor at Z=12.90" and steer them
# radially outward to the active carousel loading slot at Y=7.0".
#
# Three-profile loft rationale:
#   A direct 2-profile loft (top@(0,4.5) -> bottom@(0,7.0)) creates a slant cone
#   whose cross-section at Z=11.0" (loading tube bottom) reaches 2.21" from the
#   tube axis — exceeding the 1.80" loading-tube bore.  Adding a "knee" wire at
#   Z=11.0" that holds R=1.40" centred at (0,4.5) keeps the upper section
#   straight inside the tube; only the lower section sweeps to the exit.

import cadquery as cq
import pathlib

OUTPUT = pathlib.Path("output")
OUTPUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Constants  (copied from carousel.py / trapdoor.py — no circular import)
# ---------------------------------------------------------------------------
CAROUSEL_X        = 0.0
CAROUSEL_Y        = 4.5
SLOT_RADIUS       = 2.5

DOOR_Z            = 12.90   # trapdoor.py  DOOR_Z
DOOR_R            = 1.40    # trapdoor.py  DOOR_R = CHBR_INNER_R

LOAD_TUBE_Z_BOT   = 11.0    # carousel.py  LOAD_TUBE_Z_BOT
LOAD_TUBE_INNER_R =  1.80   # carousel.py  LOAD_TUBE_INNER_R  (clearance ref)

PILL_RING_WORLD_Z =  8.85   # carousel.py  PILL_RING_WORLD_Z
PILL_RING_T       =  0.05   # carousel.py  PILL_RING_T

CHUTE_WALL        =  0.08   # shell wall thickness

# Derived geometry
ACTIVE_Y    = CAROUSEL_Y + SLOT_RADIUS          # 7.0"  active loading slot Y-centre
CHUTE_Z_TOP = DOOR_Z                            # 12.90" flush with closed trapdoor
CHUTE_Z_MID = LOAD_TUBE_Z_BOT                  # 11.00" loading tube bottom
CHUTE_Z_BOT = PILL_RING_WORLD_Z + PILL_RING_T  # 8.90"  just above pill guide ring
CHUTE_R_TOP = DOOR_R                            # 1.40"  matches trapdoor bore
CHUTE_R_BOT = 0.60                              # exit radius over loading slot

# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def make_routing_chute():
    """3-profile lofted hollow funnel:
      w_top : R=1.40" @ (0, 4.5, 12.90) — inside loading tube
      w_mid : R=1.40" @ (0, 4.5, 11.00) — loading tube knee (keeps tube clearance)
      w_bot : R=0.60" @ (0, 7.0,  8.90) — exit over active loading slot
    Hollowed by subtracting an inner loft (R - CHUTE_WALL).
    Inner cutter extended ±0.01" in Z to avoid coincident-face ambiguity.
    """
    # --- outer loft ---
    w_top = cq.Wire.makeCircle(
        CHUTE_R_TOP, cq.Vector(CAROUSEL_X, CAROUSEL_Y, CHUTE_Z_TOP), cq.Vector(0, 0, 1))
    w_mid = cq.Wire.makeCircle(
        CHUTE_R_TOP, cq.Vector(CAROUSEL_X, CAROUSEL_Y, CHUTE_Z_MID), cq.Vector(0, 0, 1))
    w_bot = cq.Wire.makeCircle(
        CHUTE_R_BOT, cq.Vector(CAROUSEL_X, ACTIVE_Y,   CHUTE_Z_BOT), cq.Vector(0, 0, 1))

    outer_solid = cq.Solid.makeLoft([w_top, w_mid, w_bot])
    outer = cq.Workplane("XY").add(outer_solid)

    # --- inner loft (±0.01" Z overshoot for clean open ends) ---
    ri_top = CHUTE_R_TOP - CHUTE_WALL   # 1.32"
    ri_bot = CHUTE_R_BOT - CHUTE_WALL   # 0.52"

    wi_top = cq.Wire.makeCircle(
        ri_top, cq.Vector(CAROUSEL_X, CAROUSEL_Y, CHUTE_Z_TOP + 0.01), cq.Vector(0, 0, 1))
    wi_mid = cq.Wire.makeCircle(
        ri_top, cq.Vector(CAROUSEL_X, CAROUSEL_Y, CHUTE_Z_MID), cq.Vector(0, 0, 1))
    wi_bot = cq.Wire.makeCircle(
        ri_bot, cq.Vector(CAROUSEL_X, ACTIVE_Y,   CHUTE_Z_BOT - 0.01), cq.Vector(0, 0, 1))

    inner_solid = cq.Solid.makeLoft([wi_top, wi_mid, wi_bot])
    inner = cq.Workplane("XY").add(inner_solid)

    return outer.cut(inner)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
print("Building static routing chute (Phase 13)...")

routing_chute = make_routing_chute()

routing_chute.export(str(OUTPUT / "routing_chute.step"))
print("  Wrote output/routing_chute.step")

# Named assembly for standalone preview
rc_assy = cq.Assembly()
rc_assy.add(routing_chute, name="routing_chute",
            color=cq.Color(1.00, 0.70, 0.20, 0.65))
rc_assy.export(str(OUTPUT / "routing_chute_assembly.step"))
print("  Wrote output/routing_chute_assembly.step")

# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
print("\n--- Routing Chute Verification ---")
bb = routing_chute.val().BoundingBox()

print(f"  Z: [{bb.zmin:.3f}, {bb.zmax:.3f}]  (expected [{CHUTE_Z_BOT:.3f}, {CHUTE_Z_TOP:.3f}])")
z_ok = abs(bb.zmin - CHUTE_Z_BOT) < 0.02 and abs(bb.zmax - CHUTE_Z_TOP) < 0.02
print(f"       {'OK' if z_ok else 'CHECK Z bounds'}")

# Upper section must stay within loading tube bore (R=1.80 from axis at (0,4.5))
x_reach = max(abs(bb.xmin), abs(bb.xmax))
print(f"  X reach at top:   {x_reach:.3f}\"  (loading tube inner = {LOAD_TUBE_INNER_R:.2f}\"  "
      f"{'OK' if x_reach <= LOAD_TUBE_INNER_R else 'INTERFERENCE!'})")

# Bottom exit — Y-max = ACTIVE_Y + CHUTE_R_BOT = 7.0 + 0.60 = 7.60"
# Guide tube inner from carousel centre (0,4.5): GUIDE_OUTER_R - GUIDE_WALL = 3.45"
# Max Y distance from carousel centre = bb.ymax - CAROUSEL_Y
y_max_dist = bb.ymax - CAROUSEL_Y
guide_inner = 3.45
print(f"  Y-max dist from carousel centre: {y_max_dist:.3f}\"  "
      f"(guide tube inner = {guide_inner:.2f}\"  "
      f"{'OK' if y_max_dist < guide_inner else 'CHECK guide tube clearance'})")
print(f"  Y-max (world):    {bb.ymax:.3f}\"  (expected {ACTIVE_Y + CHUTE_R_BOT:.3f}\")")

# Exit mouth centre Y
exit_y_centre = ACTIVE_Y
cartridge_y_min = CAROUSEL_Y + 0.75   # INNER_R = 0.75"
cartridge_y_max = CAROUSEL_Y + 3.50   # OUTER_R = 3.50"
print(f"\n  Exit mouth centre Y = {exit_y_centre:.3f}\"  "
      f"cartridge slot Y = [{cartridge_y_min:.3f}, {cartridge_y_max:.3f}]  "
      f"({'ALIGNED' if cartridge_y_min <= exit_y_centre <= cartridge_y_max else 'MISALIGNED!'})")
print(f"  Exit mouth R = {CHUTE_R_BOT:.2f}\"  "
      f"Y span = [{exit_y_centre - CHUTE_R_BOT:.2f}, {exit_y_centre + CHUTE_R_BOT:.2f}]\"")
print(f"  Pill guide ring inner R = 0.80\" (centre at CAROUSEL_Y)  "
      f"exit R={CHUTE_R_BOT:.2f}\" < 0.80\" ring hole  "
      f"{'OK — pills clear ring hole' if CHUTE_R_BOT < 0.80 else 'CHECK'}")

print("\nDone.")
print("Run order: hero_dispenser.py -> optical_chamber.py -> trapdoor.py -> routing_chute.py -> carousel.py")
