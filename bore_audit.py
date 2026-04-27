# Pill Bore Audit — Hero Pill Dispenser
# Run with: C:\Users\jaime\AppData\Local\Python\pythoncore-3.12-64\python.exe bore_audit.py

import math

SEP = "=" * 72

print(SEP)
print("PILL BORE AUDIT -- Hero Pill Dispenser")
print(SEP)

# ---------------------------------------------------------------------------
# Current apertures (all radii in inches)
# ---------------------------------------------------------------------------
ROUTING_EXIT_R = 0.60   # ROUTING_CHUTE_EXIT_R (guide ring loading port)
HOLE_R         = 0.30   # base plate drop hole
CHUTE_INNER_R  = 0.25   # pill chute inner bore  (= spout inner bore)
AGIT_R         = 0.40   # agitator wheel radius
AGIT_WORLD_Z   = 5.45   # agitator wheel Z-centre
CART_Z         = 5.00   # cartridge floor Z (= CAROUSEL_Z_CART)
AGIT_GAP_IN    = AGIT_WORLD_Z - AGIT_R - CART_Z   # floor-to-agitator gap

def d_mm(r_in):
    return r_in * 2 * 25.4

print()
print("-- Current apertures (radius in\" / diameter in mm) --")
rows = [
    ("Routing chute exit / guide ring port", ROUTING_EXIT_R),
    ("Base plate drop hole",                  HOLE_R),
    ("Pill chute inner bore (= spout bore)",  CHUTE_INNER_R),
]
for name, r in rows:
    print(f"  {name:<44}  R={r:.3f}\"   diam={d_mm(r):.1f} mm")

# ---------------------------------------------------------------------------
# Standard capsule sizes (dia and length in mm)
# ---------------------------------------------------------------------------
capsules = [
    ("000", 9.9,  26.1),
    ("00",  8.5,  23.3),
    ("0",   7.6,  21.7),
    ("1",   6.9,  19.4),
    ("2",   6.4,  18.0),
    ("3",   5.8,  15.9),
    ("4",   5.3,  14.3),
    ("5",   4.9,  11.1),
]

HOLE_D  = d_mm(HOLE_R)
CHUTE_D = d_mm(CHUTE_INNER_R)
AGIT_GAP_MM = AGIT_GAP_IN * 25.4

print()
print("-- Standard hard-gelatin capsule sizes --")
hdr = f"  {'Size':<6}  {'Dia(mm)':<9}  {'Len(mm)':<9}  {'Drop hole':<19}  {'Chute bore':<19}  Orientation"
print(hdr)
print("  " + "-" * 88)
for size, dia, length in capsules:
    hok = f"OK (+{HOLE_D-dia:.1f}mm)" if dia < HOLE_D else f"STUCK ({dia-HOLE_D:.1f}mm wide)"
    cok = f"OK (+{CHUTE_D-dia:.1f}mm)" if dia < CHUTE_D else f"STUCK ({dia-CHUTE_D:.1f}mm wide)"
    ori = "flat OK" if dia < AGIT_GAP_MM else "UPRIGHT only (dia > agit gap)"
    print(f"  #{size:<5}  {dia:<9.1f}  {length:<9.1f}  {hok:<19}  {cok:<19}  {ori}")

# ---------------------------------------------------------------------------
# Common tablets / softgels
# ---------------------------------------------------------------------------
tablets = [
    ("Aspirin 81 mg",      6.0,  3.5),
    ("Metoprolol 25 mg",   7.0,  3.0),
    ("Ibuprofen 200 mg",  10.0,  4.5),
    ("Vitamin D3 tab",    12.0,  5.0),
    ("Fish oil softgel",  14.0,  7.0),
]
print()
print("-- Common tablets / softgels --")
hdr2 = f"  {'Type':<22}  {'Dia(mm)':<9}  {'Thk(mm)':<9}  {'Drop hole':<24}  Chute bore"
print(hdr2)
print("  " + "-" * 82)
for name, dia, thk in tablets:
    hok = f"OK (+{HOLE_D-dia:.1f}mm)" if dia < HOLE_D else f"STUCK ({dia-HOLE_D:.1f}mm wide)"
    cok = f"OK (+{CHUTE_D-dia:.1f}mm)" if dia < CHUTE_D else f"STUCK ({dia-CHUTE_D:.1f}mm wide)"
    print(f"  {name:<22}  {dia:<9.1f}  {thk:<9.1f}  {hok:<24}  {cok}")

# ---------------------------------------------------------------------------
# Agitator clearance analysis
# ---------------------------------------------------------------------------
print()
print("-- Agitator clearance --")
print(f"  Agitator bottom Z = {AGIT_WORLD_Z:.3f} - {AGIT_R:.3f} = {AGIT_WORLD_Z-AGIT_R:.3f}\"")
print(f"  Cartridge floor Z = {CART_Z:.3f}\"")
print(f"  Floor gap         = {AGIT_GAP_IN:.4f}\" = {AGIT_GAP_MM:.2f} mm")
print(f"  Smallest capsule (#5) dia = 4.9 mm  >>  {AGIT_GAP_MM:.1f} mm gap")
print(f"  RESULT: NO standard pill can lie flat under the current agitator")

# Required new agitator Z for flat pills (target: #000, 9.9 mm)
target_dia_mm = 9.9
needed_gap_in = target_dia_mm / 25.4 + 0.5/25.4   # dia + 0.5 mm clearance
new_agit_z    = CART_Z + needed_gap_in + AGIT_R
print()
print(f"  To allow ANY capsule (#000 = {target_dia_mm} mm dia) to slide flat:")
print(f"    Required gap    = {needed_gap_in*25.4:.1f} mm = {needed_gap_in:.4f}\"")
print(f"    AGIT_WORLD_Z    = {CART_Z:.3f} + {needed_gap_in:.4f} + {AGIT_R:.3f} = {new_agit_z:.4f}\"")
print(f"    New agit Z span = [{new_agit_z-AGIT_R:.4f}\", {new_agit_z+AGIT_R:.4f}\"]")
print(f"    Cartridge zone  = [{CART_Z:.3f}\", 8.900\"]  --> still INSIDE zone  OK")

# ---------------------------------------------------------------------------
# Bore resize recommendation (to support large softgels)
# ---------------------------------------------------------------------------
print()
print("-- Bore resize for large softgels (14 mm dia) --")
softgel_dia = 14.0
new_chute_r = math.ceil((softgel_dia / 2.0 + 1.5) / 25.4 * 1000) / 1000   # +1.5 mm radial clearance
new_hole_r  = new_chute_r + 0.05   # drop hole 0.05\" wider than bore
new_flange_r = new_hole_r + 0.15   # maintain 0.15\" sealing lip
print(f"  Target pill: fish oil softgel {softgel_dia:.0f} mm dia")
print(f"  New CHUTE_INNER_R = {new_chute_r:.3f}\"  (diam = {d_mm(new_chute_r):.1f} mm, +{d_mm(new_chute_r)-softgel_dia:.1f} mm clearance)")
print(f"  New HOLE_R        = {new_hole_r:.3f}\"  (diam = {d_mm(new_hole_r):.1f} mm)")
print(f"  New CHUTE_FLANGE_R = {new_flange_r:.3f}\"  (sealing lip = 0.15\" maintained)")
print(f"  New spout inner R  = {new_chute_r:.3f}\"  (match chute bore)")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
print(SEP)
print("VERDICT -- 3 issues, priority-ordered")
print(SEP)
print()
print("  ISSUE 1 [SHOW-STOPPER]  Agitator floor gap = 1.27 mm")
print("    No real pill can slide flat under the agitator to reach the drop hole.")
print(f"    Fix: raise AGIT_WORLD_Z  5.450\" -> {new_agit_z:.3f}\"")
print(f"         gap becomes {needed_gap_in*25.4:.1f} mm -- clears any capsule lying flat")
print("    File: carousel.py")
print()
print("  ISSUE 2 [RELIABILITY]  Open-top cartridges -- pills spill on rotation")
print("    Without lids, pills tumble between cartridge sectors as the carousel")
print("    rotates, mixing medications. Sorting becomes unreliable.")
print("    Fix: cartridge_lid -- annular cap, R_inner=hub clearance, R_outer=3.50\"")
print("         single dispensing hole at SLOT_RADIUS (same size as drop hole)")
print("    File: new part  cartridge_lid.py")
print()
print("  ISSUE 3 [OPTIONAL]  Fish oil softgels (14 mm dia) stuck in chute")
print("    All standard capsules (#000-#5) and tablets <=12 mm pass through OK.")
print(f"    Fix (if needed): increase CHUTE_INNER_R  0.25\" -> {new_chute_r:.3f}\"")
print(f"                     increase HOLE_R          0.30\" -> {new_hole_r:.3f}\"")
print(f"                     increase spout bore      0.25\" -> {new_chute_r:.3f}\"")
print("    Files: carousel.py, hero_dispenser.py")
print()
print("  NOT AN ISSUE  Bore diameters for standard capsules")
print("    Drop hole  15.2 mm: all capsules #000-#5 fit (upright)  OK")
print("    Chute bore 12.7 mm: all capsules #000-#5 fit (upright)  OK")
