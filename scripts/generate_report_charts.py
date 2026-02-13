"""Generate charts for the NSA claims data analysis report (PNG files)."""

import json, re, pathlib
from collections import Counter
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

sns.set_theme(style="whitegrid", font_scale=1.05)

DATA_ROOT = pathlib.Path(__file__).resolve().parent.parent / "data" / "datasets"
OUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "docs" / "report_charts"
OUT_DIR.mkdir(exist_ok=True)

ACCENT = "#00528A"
GREEN = "#4CAF50"
RED = "#E53935"
GRAY = "#607D8B"

# ── Load & normalize ────────────────────────────────────────────────────────

def load_gt(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

gt_seed = load_gt(DATA_ROOT / "nsa-motor-seed-v1/ground_truth.json")
gt_eval1 = load_gt(DATA_ROOT / "nsa-motor-eval-v1/ground_truth.json")
gt_eval2 = load_gt(DATA_ROOT / "nsa-motor-holdout/ground_truth.json")

BRAND_MAP = {
    "alfa romeo": "Alfa Romeo", "audi": "Audi", "bentley": "Bentley",
    "bmw": "BMW", "citroen": "Citroën", "citroën": "Citroën",
    "cupra": "Cupra", "fiat": "Fiat", "ford": "Ford", "hyundai": "Hyundai",
    "jeep": "Jeep", "land rover": "Land Rover", "mercedes": "Mercedes",
    "mini": "Mini", "mitsubishi": "Mitsubishi", "nissan": "Nissan",
    "peugeot": "Peugeot", "porsche": "Porsche", "renault": "Renault",
    "rolls royce": "Rolls-Royce", "rolls-royce": "Rolls-Royce",
    "seat": "Seat", "skoda": "Skoda", "subaru": "Subaru",
    "volkswagen": "Volkswagen", "vw": "Volkswagen",
}

def extract_brand(v):
    if not v:
        return "Unknown"
    vl = v.lower().strip()
    for key in sorted(BRAND_MAP, key=len, reverse=True):
        if vl.startswith(key):
            return BRAND_MAP[key]
    return v.split()[0].title()

def normalize(claim, dataset):
    row = {
        "claim_id": str(claim["claim_id"]),
        "dataset": dataset,
        "decision": claim["decision"],
        "denial_reason": claim.get("denial_reason"),
        "vehicle": claim.get("vehicle"),
        "currency": claim.get("currency", "CHF"),
        "total_approved_amount": claim.get("total_approved_amount") or claim.get("approved_amount"),
        "deductible": claim.get("deductible"),
        "parts_approved": claim.get("parts_approved"),
        "labor_approved": claim.get("labor_approved"),
        "total_material_labor": claim.get("total_material_labor_approved"),
        "reimbursement_rate_pct": claim.get("reimbursement_rate_pct"),
        "language": claim.get("language"),
    }
    raw_date = claim.get("date")
    if raw_date:
        for fmt in ("%d/%m/%Y", "%d.%m.%Y"):
            try:
                row["date"] = datetime.strptime(raw_date, fmt)
                break
            except ValueError:
                continue
    if "date" not in row:
        row["date"] = None
    return row

rows = []
for c in gt_seed["claims"]:  rows.append(normalize(c, "seed-v1"))
for c in gt_eval1["claims"]: rows.append(normalize(c, "eval-v1"))
for c in gt_eval2["claims"]: rows.append(normalize(c, "eval-v2"))

df = pd.DataFrame(rows)
df["brand"] = df["vehicle"].apply(extract_brand)

approved = df[df["decision"] == "APPROVED"].copy()
denied = df[df["decision"] == "DENIED"].copy()


# ── Denial classification ────────────────────────────────────────────────────

def classify_denial(reason):
    if not reason: return "Unknown"
    r = reason.lower()
    if any(k in r for k in ["police n'est pas valide","garantie est échue","limite de kilométrage",
        "ausserhalb der versicherten periode","nicht valide","non-payment","premium",
        "prämie","lapses","nicht gültig"]):
        return "Policy not valid / expired"
    if any(k in r for k in ["folgeschäden","dommages causés","consequential","distribution","caused by"]):
        return "Consequential / root-cause damage"
    if any(k in r for k in ["wear part","verschleissteil","usure","brake disc","brake pad",
        "bremsscheib","bremsbelag"]):
        return "Wear parts excluded"
    if any(k in r for k in ["above 100,000 km","ab 100.000 km","no coverage for the following components above"]):
        return "Mileage exclusion"
    if any(k in r for k in ["nicht über die garantie versichert","nicht von der garantie",
        "nicht über die garantie abgedeckt","nicht abgedeckt","nicht versichert","keine kosten",
        "n'est pas couvert","ne sont pas couvert","not covered","nur die teile","only covers parts",
        "uniquement les pièces","ausschliesslich die teile","only parts listed","only parts declared",
        "only parts mentioned","explicitly excluded","explicitement exclu"]):
        return "Part not covered"
    return "Other"

denied["denial_category"] = denied["denial_reason"].apply(classify_denial)

# Denied parts by system
PART_PATTERNS = {
    r"scheinwerfer|headlight": "Headlights",
    r"querlenker|control arm|bras de suspension|suspension arm": "Control arm",
    r"parktikelfilter.?sensor|dpf.?sensor": "DPF sensor",
    r"nox.?sensor": "NOx sensor",
    r"kabelbaum|wiring harness|faisceau": "Wiring harness",
    r"motorsteuergerät|control unit|calculateur": "ECU",
    r"heizungsventil|heating valve": "Heating valve",
    r"kühlsystem|cooling system|refroidiss": "Cooling system",
    r"hochdruckpumpe|high.?pressure pump|pompe haute pression": "High-pressure pump",
    r"zahnriemen|timing belt|courroie de distribution": "Timing belt",
    r"ad.?blue|harnstoff": "AdBlue system",
    r"software.?update": "Software update",
    r"lenkrad|steering wheel|volant": "Steering wheel",
    r"wasserpumpe|water pump|pompe.+eau": "Water pump",
    r"filtre.+huile|ölfilter|oil filter support|support du filtre": "Oil filter housing",
    r"couvre.?culasse|couvercle de soupape|valve cover|ventildeckel": "Valve cover",
    r"gaines? d.?etancheite|dichtung|gasket|seal|joint": "Gaskets / seals",
    r"egr|recirculation des gaz|abgasrückführ": "EGR valve",
    r"turbo|compressor|intercooler|lader": "Turbo / compressor",
    r"hybrid|batterie|battery": "Hybrid / battery",
    r"parking.?sensor|einparkhilfe|capteur de stationnement": "Parking sensors",
    r"brake disc|brake pad|bremsscheib|bremsbelag|frein": "Brake discs / pads",
    r"hose|schlauch|flexible|tuyau": "Hoses",
}

SYSTEM_MAP = {
    "EGR valve": "Emissions", "AdBlue system": "Emissions", "DPF sensor": "Emissions",
    "NOx sensor": "Emissions",
    "Gaskets / seals": "Seals & Gaskets", "Valve cover": "Seals & Gaskets",
    "Oil filter housing": "Seals & Gaskets",
    "Software update": "Electronics / Software", "Wiring harness": "Electronics / Software",
    "ECU": "Electronics / Software", "Parking sensors": "Electronics / Software",
    "Headlights": "Electronics / Software",
    "Turbo / compressor": "Engine / Powertrain", "Timing belt": "Engine / Powertrain",
    "High-pressure pump": "Engine / Powertrain",
    "Water pump": "Cooling / Heating", "Heating valve": "Cooling / Heating",
    "Cooling system": "Cooling / Heating",
    "Control arm": "Chassis / Steering", "Steering wheel": "Chassis / Steering",
    "Brake discs / pads": "Wear parts", "Hoses": "Wear parts",
    "Hybrid / battery": "Hybrid / EV",
}

part_counter = Counter()
for reason in denied["denial_reason"].dropna():
    for pattern, part in PART_PATTERNS.items():
        if re.search(pattern, reason.lower()):
            part_counter[part] += 1

system_counter = Counter()
for part, count in part_counter.items():
    system_counter[SYSTEM_MAP.get(part, "Other")] += count


# ═══════════════════════════════════════════════════════════════════════════
# CHART 1 — Decision Split (donut)
# ═══════════════════════════════════════════════════════════════════════════

fig, ax = plt.subplots(figsize=(5, 5))
vals = [42, 42]
colors = [GREEN, RED]
wedges, texts, autotexts = ax.pie(
    vals, labels=["Approved\n(42)", "Denied\n(42)"], colors=colors,
    autopct="%1.0f%%", startangle=90, pctdistance=0.78,
    wedgeprops=dict(width=0.45, edgecolor="white", linewidth=2),
    textprops=dict(fontsize=12, fontweight="bold"),
)
for at in autotexts:
    at.set_fontsize(13)
    at.set_fontweight("bold")
    at.set_color("white")
ax.set_title("Decision Split (n = 84)", fontsize=14, fontweight="bold", pad=16, color="#1A1A2E")
fig.tight_layout()
fig.savefig(OUT_DIR / "01_decision_split.png", dpi=180, bbox_inches="tight", facecolor="white")
plt.close(fig)
print("  [1/6] Decision split donut")


# ═══════════════════════════════════════════════════════════════════════════
# CHART 2 — Denial Reason Categories
# ═══════════════════════════════════════════════════════════════════════════

cat_counts = denied["denial_category"].value_counts()

fig, ax = plt.subplots(figsize=(7, 3.5))
bars = ax.barh(
    range(len(cat_counts)), cat_counts.values,
    color=[RED if i == 0 else "#EF9A9A" for i in range(len(cat_counts))],
    edgecolor="white", linewidth=1,
)
ax.set_yticks(range(len(cat_counts)))
ax.set_yticklabels(cat_counts.index, fontsize=10)
ax.invert_yaxis()
ax.set_xlabel("Number of claims", fontsize=10)
ax.set_title("Why Claims Get Denied", fontsize=13, fontweight="bold", color="#1A1A2E")
for i, v in enumerate(cat_counts.values):
    ax.text(v + 0.4, i, f"{v}  ({v/len(denied)*100:.0f}%)", va="center", fontsize=10, color="#333")
ax.set_xlim(0, cat_counts.max() * 1.35)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
fig.tight_layout()
fig.savefig(OUT_DIR / "02_denial_reasons.png", dpi=180, bbox_inches="tight", facecolor="white")
plt.close(fig)
print("  [2/6] Denial reasons")


# ═══════════════════════════════════════════════════════════════════════════
# CHART 3 — Denied Parts by System
# ═══════════════════════════════════════════════════════════════════════════

sys_df = pd.DataFrame(sorted(system_counter.items(), key=lambda x: -x[1]), columns=["system", "count"])

fig, ax = plt.subplots(figsize=(7, 4))
palette = sns.color_palette("RdYlBu_r", len(sys_df))
ax.barh(range(len(sys_df)), sys_df["count"], color=palette, edgecolor="white", linewidth=1)
ax.set_yticks(range(len(sys_df)))
ax.set_yticklabels(sys_df["system"], fontsize=10)
ax.invert_yaxis()
ax.set_xlabel("Denial mentions", fontsize=10)
ax.set_title("Denied Parts by Vehicle System", fontsize=13, fontweight="bold", color="#1A1A2E")
for i, v in enumerate(sys_df["count"]):
    ax.text(v + 0.2, i, str(v), va="center", fontsize=10, fontweight="bold", color="#333")
ax.set_xlim(0, sys_df["count"].max() * 1.25)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
fig.tight_layout()
fig.savefig(OUT_DIR / "03_denied_systems.png", dpi=180, bbox_inches="tight", facecolor="white")
plt.close(fig)
print("  [3/6] Denied systems")


# ═══════════════════════════════════════════════════════════════════════════
# CHART 4 — Approved Amount Distribution + Parts/Labor pie
# ═══════════════════════════════════════════════════════════════════════════

has_amount = approved[approved["total_approved_amount"].notna()]
has_split = approved[approved["parts_approved"].notna() & approved["labor_approved"].notna()]

fig, axes = plt.subplots(1, 2, figsize=(10, 4))

# Histogram
axes[0].hist(has_amount["total_approved_amount"], bins=14, color=ACCENT, edgecolor="white", alpha=0.9)
axes[0].axvline(has_amount["total_approved_amount"].median(), color=RED, linestyle="--", linewidth=1.5,
                label=f'Median: CHF {has_amount["total_approved_amount"].median():,.0f}')
axes[0].axvline(has_amount["total_approved_amount"].mean(), color="#FF9800", linestyle="--", linewidth=1.5,
                label=f'Mean: CHF {has_amount["total_approved_amount"].mean():,.0f}')
axes[0].set_xlabel("Approved Amount (CHF)", fontsize=10)
axes[0].set_ylabel("Number of claims", fontsize=10)
axes[0].set_title("Payout Distribution", fontsize=12, fontweight="bold", color="#1A1A2E")
axes[0].legend(fontsize=9)
axes[0].xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
axes[0].spines["top"].set_visible(False)
axes[0].spines["right"].set_visible(False)

# Parts vs Labor donut
parts_total = has_split["parts_approved"].sum()
labor_total = has_split["labor_approved"].sum()
wedges, texts, autotexts = axes[1].pie(
    [parts_total, labor_total],
    labels=[f"Parts\nCHF {parts_total:,.0f}", f"Labor\nCHF {labor_total:,.0f}"],
    colors=["#1976D2", "#90CAF9"],
    autopct="%1.0f%%", startangle=90, pctdistance=0.78,
    wedgeprops=dict(width=0.45, edgecolor="white", linewidth=2),
    textprops=dict(fontsize=10),
)
for at in autotexts:
    at.set_fontsize(12)
    at.set_fontweight("bold")
axes[1].set_title("Parts vs. Labor Split", fontsize=12, fontweight="bold", color="#1A1A2E")

fig.tight_layout()
fig.savefig(OUT_DIR / "04_financials.png", dpi=180, bbox_inches="tight", facecolor="white")
plt.close(fig)
print("  [4/6] Financial profile")


# ═══════════════════════════════════════════════════════════════════════════
# CHART 5 — Brand Volume & Approval Rate
# ═══════════════════════════════════════════════════════════════════════════

brand_stats = df.groupby("brand").agg(
    total=("claim_id", "count"),
    approved=("decision", lambda x: (x == "APPROVED").sum()),
).sort_values("total", ascending=False).head(10)
brand_stats["denied"] = brand_stats["total"] - brand_stats["approved"]
brand_stats["rate"] = (brand_stats["approved"] / brand_stats["total"] * 100).round(1)

fig, ax = plt.subplots(figsize=(8, 4.5))
y = range(len(brand_stats))
ax.barh(y, brand_stats["approved"], color=GREEN, edgecolor="white", label="Approved")
ax.barh(y, brand_stats["denied"], left=brand_stats["approved"], color=RED, edgecolor="white", label="Denied")
ax.set_yticks(y)
ax.set_yticklabels(brand_stats.index, fontsize=10)
ax.invert_yaxis()
ax.set_xlabel("Number of claims", fontsize=10)
ax.set_title("Claims by Brand — Approved vs. Denied", fontsize=13, fontweight="bold", color="#1A1A2E")
ax.legend(loc="lower right", fontsize=9)
for i, (tot, rate) in enumerate(zip(brand_stats["total"], brand_stats["rate"])):
    ax.text(tot + 0.3, i, f"{rate:.0f}% appr.", va="center", fontsize=9, color="#555")
ax.set_xlim(0, brand_stats["total"].max() * 1.35)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
fig.tight_layout()
fig.savefig(OUT_DIR / "05_brands.png", dpi=180, bbox_inches="tight", facecolor="white")
plt.close(fig)
print("  [5/6] Brand volume")


# ═══════════════════════════════════════════════════════════════════════════
# CHART 6 — Claims Over Time
# ═══════════════════════════════════════════════════════════════════════════

has_date = df[df["date"].notna()].copy()
has_date["month"] = has_date["date"].dt.to_period("M")
monthly = has_date.groupby(["month", "decision"]).size().unstack(fill_value=0)

fig, ax = plt.subplots(figsize=(7, 4))
x = range(len(monthly))
labels = [str(m) for m in monthly.index]
w = 0.35
ax.bar([i - w/2 for i in x], monthly.get("APPROVED", 0), w, color=GREEN, edgecolor="white", label="Approved")
ax.bar([i + w/2 for i in x], monthly.get("DENIED", 0), w, color=RED, edgecolor="white", label="Denied")
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=10)
ax.set_ylabel("Number of claims", fontsize=10)
ax.set_title("Claims Over Time", fontsize=13, fontweight="bold", color="#1A1A2E")
ax.legend(fontsize=9)
# Add totals on top
for i in x:
    total = monthly.iloc[i].sum()
    ax.text(i, total + 0.5, str(total), ha="center", fontsize=10, fontweight="bold", color="#333")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
fig.tight_layout()
fig.savefig(OUT_DIR / "06_timeline.png", dpi=180, bbox_inches="tight", facecolor="white")
plt.close(fig)
print("  [6/6] Timeline")


print(f"\nAll charts saved to: {OUT_DIR}")
