"""Estimate net worth by education for SCF families with children and draw the figures.

Reads the summary extract files that get_data.py saved in data/raw/, computes
survey-weighted means and medians for every survey year, writes the plotted series to
data/processed/networth_by_education.csv, and saves:
  figure.png         mean net worth (the reproduction)
  figure_median.png  median net worth (the extension)

Definitions (all from the Fed's summary-extract macro, bulletin.macro.txt):
  population  families with KIDS > 0: at least one child or stepchild of the reference
              person or spouse/partner living in the household (no age limit)
  groups      EDCL == 4 -> "BA or more"; EDCL in (1, 2) -> "HS or less";
              EDCL == 3 (some college or associate degree) is excluded
  dollars     the extracts are already in 2025 dollars; no further adjustment is made
  weights     WGT (= X42001 / 5); all five implicates are pooled, as in the Fed's tables
  median      first value at which the cumulative weight reaches half the total

Usage:  python plot.py
"""

import re
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
DOLLAR_BASIS = "2025 dollars (September 2025 R-CPI-U-RS, as published in the SCF summary extract)"
GROUPS = {"BA or more": [4], "HS or less": [1, 2]}
KEEP = ["X1", "XX1", "Y1", "YY1", "WGT", "NETWORTH", "KIDS", "EDCL", "MARRIED"]
REQUIRED = ["WGT", "NETWORTH", "KIDS", "EDCL"]


def survey_years():
    years = sorted(int(re.search(r"scfp(\d{4})excel", p.name).group(1))
                   for p in RAW.glob("scfp*excel.zip"))
    if not years:
        raise SystemExit("No summary extracts in data/raw/. Run: python get_data.py")
    return years


def load_year(year, extra=()):
    """Load one summary extract with standard family and implicate identifiers."""
    keep = set(KEEP) | set(extra)
    d = pd.read_csv(RAW / f"scfp{year}excel.zip", usecols=lambda c: c in keep)
    # 1989 public file uses X1/XX1; later files use Y1/YY1 (see bulletin.macro.txt).
    fam, rec = ("XX1", "X1") if "XX1" in d.columns else ("YY1", "Y1")
    d = d.rename(columns={fam: "family_id", rec: "record_id"})
    d["implicate"] = d["record_id"] - 10 * d["family_id"]
    if not d["implicate"].between(1, 5).all() or not (d.groupby("family_id").size() == 5).all():
        raise ValueError(f"{year}: expected exactly five implicates (1-5) per family")
    missing = d[REQUIRED].isna().any(axis=1)
    d.attrs["n_missing_records"] = int(missing.sum())
    d = d[~missing]  # none in the 1989-2025 files; kept explicit in case of revisions
    if (d["WGT"] <= 0).any():
        raise ValueError(f"{year}: non-positive weights")
    d["year"] = year
    return d


def weighted_mean(x, w):
    return float(np.sum(w * x) / np.sum(w))


def weighted_median(x, w):
    """Smallest value whose cumulative weight share is at least 0.5 (the Fed's rule)."""
    x, w = np.asarray(x, float), np.asarray(w, float)
    order = np.argsort(x, kind="mergesort")
    cum = np.cumsum(w[order])
    return float(x[order][np.searchsorted(cum, 0.5 * cum[-1])])


def estimate(years):
    rows = []
    for year in years:
        d = load_year(year)
        kids = d[d["KIDS"] > 0]
        for group, codes in GROUPS.items():
            g = kids[kids["EDCL"].isin(codes)]
            counts = dict(
                n_families=g["family_id"].nunique(),
                n_families_per_implicate=len(g) / 5,
                weighted_families_millions=g["WGT"].sum() / 1e6,
                share_negative_networth=float(np.sum(g["WGT"] * (g["NETWORTH"] < 0)) / g["WGT"].sum()),
                n_missing_records_dropped=d.attrs["n_missing_records"],
            )
            for stat, fn in [("mean", weighted_mean), ("median", weighted_median)]:
                rows.append(dict(survey_year=year, education_group=group, statistic=stat,
                                 net_worth=round(fn(g["NETWORTH"], g["WGT"]), 2),
                                 dollar_basis=DOLLAR_BASIS, **counts))
    return pd.DataFrame(rows)


def journal_figure(table, stat, number, path):
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
        "font.size": 11, "axes.linewidth": 0.8,
    })
    styles = {"BA or more": dict(marker="o", linestyle="-"),
              "HS or less": dict(marker="s", linestyle="--")}
    fig, ax = plt.subplots(figsize=(8, 4.6), dpi=200)
    fig.subplots_adjust(left=0.12, right=0.93, top=0.97, bottom=0.14)
    t = table[table["statistic"] == stat]
    years = sorted(t["survey_year"].unique())
    for group, style in styles.items():
        s = t[t["education_group"] == group].sort_values("survey_year")
        ax.plot(s["survey_year"], s["net_worth"] / 1e3, color="black", linewidth=1.3,
                markersize=6, markerfacecolor="white", markeredgewidth=1.2, label=group, **style)
        last = s.iloc[-1]
        ax.annotate(f"${last['net_worth'] / 1e3:,.0f}K", (last["survey_year"], last["net_worth"] / 1e3),
                    xytext=(7, 0), textcoords="offset points", va="center", fontsize=10)
    ax.set_xticks(years)
    ax.set_xlim(years[0] - 1, years[-1] + 1.5)
    # End the axis on a labeled round value above the highest point.
    ymax = t["net_worth"].max() / 1e3
    ax.set_ylim(0, ymax * 1.08)
    ax.set_ylim(0, min(v for v in ax.get_yticks() if v >= ymax * 1.02))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xlabel("Survey year", fontsize=12)
    ax.set_ylabel(f"{stat.capitalize()} net worth\n(thousands of 2025 dollars)", fontsize=12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(direction="out", length=4, width=0.8, labelsize=10)
    ax.legend(loc="upper left", frameon=False, ncol=2, fontsize=11, handlelength=3)

    span = f"{years[0]}–{years[-1]}"
    caption = (f"Figure {number}. {stat.capitalize()} net worth of families with children, "
               f"by education of the reference person, {span}.")
    estimator = ("Survey-weighted means pooling all five implicates" if stat == "mean" else
                 "Survey-weighted medians of the pooled five-implicate distribution")
    note = ("Note: Families with at least one child or stepchild of the reference person or "
            "spouse/partner living at home (any age). BA or more: bachelor's degree or higher; "
            "HS or less: high-school diploma/GED or less; some college or associate degree "
            f"excluded. {estimator}. Values in September-2025 dollars (R-CPI-U-RS), as supplied "
            "in the Fed's extract.")
    source = (f"Source: Federal Reserve Board, Survey of Consumer Finances, {span} "
              "summary extract public data.")
    # Caption block below the plot; the tight bounding box keeps it from being clipped.
    fig.text(0.02, -0.03, caption, fontsize=12, va="top")
    fig.text(0.02, -0.09, textwrap.fill(note, 132, break_on_hyphens=False) + "\n" + source, fontsize=9, va="top",
             linespacing=1.4)
    fig.savefig(path, facecolor="white", bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def main():
    years = survey_years()
    table = estimate(years)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out = PROCESSED / "networth_by_education.csv"
    table.to_csv(out, index=False)
    print(f"Wrote {out.relative_to(ROOT)}")
    journal_figure(table, "mean", 1, ROOT / "figure.png")
    journal_figure(table, "median", 2, ROOT / "figure_median.png")
    print("Wrote figure.png and figure_median.png")
    wide = table.pivot_table(index="survey_year", columns=["statistic", "education_group"],
                             values="net_worth")
    gaps = pd.concat({stat: pd.DataFrame({
        "ba_or_more": wide[(stat, "BA or more")], "hs_or_less": wide[(stat, "HS or less")],
        "dollar_gap": wide[(stat, "BA or more")] - wide[(stat, "HS or less")],
        "ratio": (wide[(stat, "BA or more")] / wide[(stat, "HS or less")]).round(3)})
        for stat in ["mean", "median"]}, names=["statistic"]).reset_index()
    gaps.to_csv(PROCESSED / "gap_and_ratio.csv", index=False)
    print(f"Wrote {(PROCESSED / 'gap_and_ratio.csv').relative_to(ROOT)}")
    print((wide / 1e3).round(1).to_string())


if __name__ == "__main__":
    main()
