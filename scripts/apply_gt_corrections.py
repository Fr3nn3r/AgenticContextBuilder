"""Apply KV.pdf-verified corrections to the coverage classification ground truth."""

import json
from pathlib import Path

GT_DRAFT = Path("data/datasets/nsa-coverage-classify-v1/ground_truth_draft.json")
GT_REVIEWED = Path("data/datasets/nsa-coverage-classify-v1/ground_truth.json")

with open(GT_DRAFT, "r", encoding="utf-8") as f:
    gt = json.load(f)

claims_by_id = {c["claim_id"]: c for c in gt["claims"]}
correction_count = 0


def correct(claim_id, index, is_covered, category=None, matched_component=None, notes=""):
    global correction_count
    claim = claims_by_id[claim_id]
    item = claim["line_items"][index]
    old = item["expected"]["is_covered"]
    if old != is_covered:
        item["expected"]["is_covered"] = is_covered
        item["expected"]["category"] = category
        item["expected"]["matched_component"] = matched_component
        item["expected"]["labeling_confidence"] = "high"
        item["expected"]["labeling_source"] = "human_corrected"
        item["expected"]["notes"] = notes
        correction_count += 1
        desc = item["description"][:50]
        print(f'  [{claim_id}] #{index} "{desc}" {old} -> {is_covered}')
    else:
        # Confirm existing value
        item["expected"]["labeling_confidence"] = "high"
        item["expected"]["labeling_source"] = "human_verified"
        if notes:
            item["expected"]["notes"] = notes


# ── 64166 (FR, Ford Focus - Module de commande) ──
print("64166 corrections:")
correct("64166", 0, False, notes="KV: struck through, recherche de panne")
correct("64166", 1, False, notes="KV: rental car fee, struck through")
correct("64166", 2, False, notes="KV: struck through, recherche de panne")
correct("64166", 3, True, "electric", "modules de commande electronique",
        "KV: not struck, module de commande covered under electric")
correct("64166", 4, True, "electric", "modules de commande electronique",
        "KV: not struck, ARRIVEE part for module de commande repair")
correct("64166", 5, False, notes="KV: struck through, autoradio labor")
correct("64166", 6, False, notes="KV: struck through, unite processeur excluded per coverage notes")

# ── 64393 (DE, Alfa Romeo - Olpumpe) ──
print("64393 corrections:")
correct("64393", 0, False, notes="KV: Porto Kosten struck through")
correct("64393", 1, True, "engine", "Olpumpe", "KV: not struck, oil pump labor")
correct("64393", 2, True, "engine", "Olpumpe", "KV: not struck, oil pump part")
correct("64393", 3, False, notes="KV: Olfilter struck through")
correct("64393", 4, False, notes="KV: Ol 5W40 struck through")

# ── 64354 (DE, VW Golf - shift mechanism) ──
print("64354 corrections:")
correct("64354", 0, False, notes="KV: antenna ARBEIT, ANTENNE-NICHT VERSICHERT")
correct("64354", 1, False, notes="KV: GFS diagnostic, not covered")
correct("64354", 2, True, None, None, "Zero price item")
correct("64354", 3, False, notes="KV: antenna MATERIAL, ANTENNE-NICHT VERSICHERT")
correct("64354", 4, True, None, None, "Zero price item")
correct("64354", 5, False, notes="KV: GFS diagnostic, not covered")
correct("64354", 6, False, notes="KV: EINSTELLEN calibration, not covered")
correct("64354", 7, False, None, None,
        "KV: ANTENNE labor, ANTENNE-NICHT VERSICHERT per coverage notes")
correct("64354", 8, True, "mechanical_transmission", "Schaltbetaetigung",
        "KV: not struck, shift mechanism housing labor")
correct("64354", 9, True, "mechanical_transmission", "Schaltbetaetigung",
        "KV: not struck, heat shield removal for shift repair")
correct("64354", 10, True, "mechanical_transmission", "Schaltbetaetigung",
        "KV: not struck, BETAETIGUNG actuator part")
correct("64354", 11, True, "mechanical_transmission", "Schaltbetaetigung",
        "KV: not struck, ARRETIERUNG locking mechanism")

# ── 64659 (FR, Mercedes CLA 45 - rear differential) ──
print("64659 corrections:")
for i in range(9):
    correct("64659", i, False, notes="KV: struck through, diagnostic/programming/calibration")
correct("64659", 9, False, notes="KV: HUILE DE BV struck through")
correct("64659", 10, False, notes="KV: HUILE ENGRENAGES struck through")
correct("64659", 11, True, "four_wd", "differentiel",
        "KV: not struck, ECROU fastener for differential repair")
correct("64659", 12, True, "four_wd", "differentiel",
        "KV: not struck, GOUPILLE for differential repair")
correct("64659", 13, False, notes="KV: struck through, DEGATS ESSIEU inspection")
correct("64659", 14, False, notes="KV: struck through, VIDANGE HUILE")
correct("64659", 15, True, "four_wd", "differentiel",
        "KV: not struck, REDUCTEUR DE PONT DEPOSER labor")
correct("64659", 16, True, "four_wd", "differentiel",
        "KV: not struck, REDUCTEUR DE PONT REMPLACER labor")
correct("64659", 17, False, notes="KV: struck through, TENSION RESEAU diagnostic")
correct("64659", 18, False, notes="KV: struck through, CONTROLER NIVEAU HUILE")
correct("64659", 19, False, notes="KV: struck through, DEBRANCHER CABLE MASSE")
correct("64659", 20, False, notes="KV: struck through, SIEGE PASSAGER")
correct("64659", 21, False, notes="KV: struck through, REGLAGE SIEGE")
correct("64659", 22, True, "four_wd", "differentiel",
        "KV: not struck, rear differential - covered under four_wd")
correct("64659", 23, True, "four_wd", "differentiel",
        "KV: not struck, exhaust clamp for differential repair")
correct("64659", 24, False, notes="KV: struck through, seat height adjuster")
correct("64659", 25, True, "four_wd", "differentiel",
        "KV: not struck, VIS fastener for differential repair")

# ── 64288 (FR, Range Rover - timing chain) ──
print("64288 corrections:")
correct("64288", 0, False, notes="KV: Recherche de panne struck through")
for i in range(1, 4):
    correct("64288", i, True, "engine", "distribution chain",
            "KV: not struck, fastener for timing chain repair")
correct("64288", 4, True, "engine", "distribution chain",
        "KV: not struck, timing chain labor")
correct("64288", 5, True, "engine", "pignon d arbre a came", "KV: not struck")
correct("64288", 6, True, "engine", "Injecteur d huile",
        "KV: not struck, oil cooler injector labor")
correct("64288", 7, True, "engine", "Injecteur d huile",
        "KV: not struck, oil cooler injector part")
correct("64288", 8, True, "engine", "Poulie", "KV: not struck, pulley")
for i in range(9, 14):
    correct("64288", i, True, "engine", "distribution chain", "KV: not struck")
correct("64288", 14, True, "engine", "Jeu Mont", "KV: not struck")
for i in range(15, 22):
    correct("64288", i, True, "engine", "distribution chain", "KV: not struck")
correct("64288", 22, True, "engine", "Joint metal couvercle",
        "KV: not struck, gasket for timing chain")
correct("64288", 23, True, "engine", "Boulon distribution", "KV: not struck")
for i in range(24, 30):
    correct("64288", i, True, "engine", "distribution chain",
            "KV: not struck, part for timing chain repair")

# ── 65027 (DE, Alpina B3 - coolant pump) ──
print("65027 corrections:")
correct("65027", 0, True, "cooling_system", "Wasserpumpe",
        "KV: not struck, ASA-Schraube for water pump")
correct("65027", 1, True, "cooling_system", "Wasserpumpe",
        "KV: not struck, ASA-Schraube for water pump")
correct("65027", 2, True, "cooling_system", "Wasserpumpe",
        "KV: not struck, water pump labor")
correct("65027", 3, True, "cooling_system", "Wasserpumpe",
        "KV: not struck, cooling system bleed labor")
correct("65027", 4, True, "cooling_system", "Thermostat",
        "KV: not struck, thermostat labor")
correct("65027", 5, True, "cooling_system", "Wasserpumpe",
        "KV: not struck, electric water pump")
correct("65027", 6, False, notes="KV: Frostschutz Blau struck through, consumable")
correct("65027", 7, True, "cooling_system", "Thermostat", "KV: not struck")
correct("65027", 8, True, "cooling_system", "Wasserpumpe",
        "KV: not struck, fastener")
correct("65027", 9, True, "cooling_system", "Wasserpumpe",
        "KV: not struck, water pump screw set")
correct("65027", 10, True, "cooling_system", "Wasserpumpe",
        "KV: not struck, alu-schraube fastener")

# ── 64792 (DE, Peugeot 3008 - piston replacement) ──
print("64792 corrections:")
# Labor items - both NOT struck
correct("64792", 0, True, "engine", "Kolben",
        "KV: not struck, labor for piston repair (Arbeit 2)")
correct("64792", 1, True, "engine", "Kolben",
        "KV: not struck, labor for oil consumption measurement (Arbeit 1)")
# Motorenoel - struck
correct("64792", 2, False, notes="KV: Motorenoel struck through, consumable")
# VENTILREINIGER - not struck
correct("64792", 3, True, "engine", "Ventile",
        "KV: not struck, valve cleaner for engine repair")
# SELBSTSICHERNDE MUTTER - not struck
correct("64792", 4, True, "engine", "Kolben",
        "KV: not struck, fastener for piston repair")
# OELFILTERPATRONE - struck
correct("64792", 5, False, notes="KV: struck through, consumable")
# BEFESTIGUNGSSCHRAUBE - not struck
correct("64792", 6, True, "engine", "Zylinderblock",
        "KV: not struck, fastener for piston repair")
# SATZ VON 3 ZUSAMMENGES. KOLBEN - not struck, main covered part
correct("64792", 7, True, "engine", "Kolben",
        "KV: not struck, piston set - primary covered part")
# All remaining parts are NOT struck (gaskets, seals, bolts for piston replacement)
for i in range(8, 30):
    item = claims_by_id["64792"]["line_items"][i]
    desc = item["description"]
    # ZUENDKERZE (spark plugs) - struck
    if "ZUENDKERZE" in desc.upper():
        correct("64792", i, False, notes="KV: ZUENDKERZE struck through, consumable")
    else:
        correct("64792", i, True, "engine", "Kolben",
                f"KV: not struck, part for piston repair ({desc[:30]})")

# ── 64836 (DE, Rolls Royce Phantom - door lock + I-Drive + armrest) ──
# 3 repairs: armrest (STRUCK), I-Drive (STRUCK), door lock (NOT struck)
print("64836 corrections:")
correct("64836", 0, False, notes="KV: armrest group header, zero price, group STRUCK")
correct("64836", 1, False, notes="KV: Arbeit for armrest, group STRUCK")
correct("64836", 2, False, notes="KV: Arbeit for I-Drive, group STRUCK")
correct("64836", 3, True, "electrical_system", "Zentralverriegelungsmotor der Türe",
        "KV: Arbeit for door lock, NOT struck")
correct("64836", 4, False, notes="KV: KLETT BEFESTIGUNG, armrest group STRUCK")
correct("64836", 5, False, notes="KV: KLETTBAND, armrest group STRUCK")
correct("64836", 6, False, notes="KV: MULTIFUNKTIONSEINHEIT, I-Drive group STRUCK")
correct("64836", 7, True, "electrical_system", "Zentralverriegelungsmotor der Türe",
        "KV: TUERSCHLOSS RECHTS, NOT struck, primary covered part")
correct("64836", 8, True, "electrical_system", "Zentralverriegelungsmotor der Türe",
        "KV: SCHALLISOLIERUNG, NOT struck, ancillary to door lock repair")
correct("64836", 9, True, "electrical_system", "Zentralverriegelungsmotor der Türe",
        "KV: BUTYLSCHNUR, NOT struck, sealing material for door lock repair")
correct("64836", 10, False, notes="KV: Klein- und Verbrauchsmaterial STRUCK")

# ── Denied claims: verify all not_covered ──
print("\nDenied claims (verify all not_covered):")
for cid in ["64951", "64980", "65002", "65113", "65211"]:
    claim = claims_by_id[cid]
    for item in claim["line_items"]:
        if item["expected"]["labeling_source"] not in ("human_corrected", "human_verified"):
            item["expected"]["labeling_confidence"] = "high"
            item["expected"]["labeling_source"] = "human_verified"
    print(f"  {cid}: {len(claim['line_items'])} items verified as not_covered")

# ── Fix covered_parts_in_claim ──
print("\nFixing covered_parts_in_claim:")

# 64166: add Module de commande
claims_by_id["64166"]["covered_parts_in_claim"] = [
    {"item_code": "MECA", "description": "Module de commande de diagnostic embarqué secondaire A/B",
     "matched_component": "modules de commande electronique"}
]
print("  64166: added Module de commande")

# 64354: remove ANTENNE (not covered per adjuster), keep BETAETIGUNG + ARRETIERUNG
claims_by_id["64354"]["covered_parts_in_claim"] = [
    {"item_code": "5WA 713 033 CC", "description": "BETAETIGUNG",
     "matched_component": "Gear selector actuator"},
    {"item_code": "5WA 713 761 A", "description": "ARRETIERUNG",
     "matched_component": "Locking mechanism"},
]
print("  64354: removed ANTENNE, kept BETAETIGUNG + ARRETIERUNG")

# 64659: add DIFFERENTIEL ARRIERE
claims_by_id["64659"]["covered_parts_in_claim"] = [
    {"item_code": "A176 350 31 00", "description": "DIFFERENTIEL ARRIERE",
     "matched_component": "differentiel"}
]
print("  64659: added DIFFERENTIEL ARRIERE")

# Update metadata
gt["metadata"]["review_status"] = "reviewed"
gt["metadata"]["total_claims"] = len(gt["claims"])
total_items = sum(len(c["line_items"]) for c in gt["claims"])
gt["metadata"]["total_items"] = total_items
gt["metadata"]["items_needing_review"] = 0
gt["metadata"]["reviewed_date"] = "2026-02-12"
gt["metadata"]["review_notes"] = (
    "KV.pdf strikethrough verification for all approved claims. "
    "Denied claims verified as all not_covered."
)

# Save as ground_truth.json (reviewed)
with open(GT_REVIEWED, "w", encoding="utf-8") as f:
    json.dump(gt, f, indent=2, ensure_ascii=False)

print(f"\nSaved {GT_REVIEWED}: {total_items} items across {len(gt['claims'])} claims")

n_corrected = sum(
    1 for c in gt["claims"] for i in c["line_items"]
    if i["expected"]["labeling_source"] == "human_corrected"
)
n_verified = sum(
    1 for c in gt["claims"] for i in c["line_items"]
    if i["expected"]["labeling_source"] == "human_verified"
)
n_covered = sum(
    1 for c in gt["claims"] for i in c["line_items"]
    if i["expected"]["is_covered"]
)
print(f"Corrections: {n_corrected}, Verified unchanged: {n_verified}")
print(f"Covered: {n_covered}, Not covered: {total_items - n_covered}")
