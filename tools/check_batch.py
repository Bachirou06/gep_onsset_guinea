"""Sanity checks on a finished batch; writes CHECKS.md into the batch folder.

    python tools/check_batch.py GuineaRuns/Outputs/<batch> [--reference-bu078 <million USD>]

Checks (Task 10 of the implementation plan):
  1. every scenario's Total Population2040 equals the projected population within 2 persons;
  2. Non-electrified Population2040 is 0 everywhere (100 percent access reached);
  3. the five reference scenarios share every lever except the two tiers;
  4. optional: BU_g0.078 total investment 2040 within 5 percent of a reference figure.
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("batch")
    ap.add_argument("--reference-bu078", type=float, default=None,
                    help="total investment 2040 (million USD) of the spike's reproduction of D2_BOT_0.078")
    a = ap.parse_args(argv)
    batch = Path(a.batch)
    comp = pd.read_csv(batch / "comparison_summary.csv")
    ids = list(dict.fromkeys(comp.scenario_id))
    lines = [f"# Checks on batch {batch.name}", ""]
    ok_all = True

    def check(name, ok, detail):
        nonlocal ok_all
        ok_all &= bool(ok)
        lines.append(f"- {'PASS' if ok else 'FAIL'}: {name}. {detail}")

    manifests = {sid: json.loads((batch / sid / "manifest.json").read_text(encoding="utf-8")) for sid in ids}
    pop_target = {sid: m["calibration"]["end_year_pop"] for sid, m in manifests.items()}

    tot = comp[(comp.technology == "Total") & (comp.year == 2040)].set_index("scenario_id")
    worst = max(abs(tot.loc[sid, "population"] - pop_target[sid]) for sid in ids)
    check("Total Population2040 equals the projected population", worst <= 2,
          f"largest gap {worst:.0f} persons over {len(ids)} scenarios")

    ne = comp[(comp.technology == "Non-electrified") & (comp.year == 2040)]
    check("Non-electrified Population2040 is zero everywhere", (ne.population == 0).all(),
          f"max {ne.population.max():.0f}")

    refs = [sid for sid in ids if sid.endswith("_g0.1")]
    diff_keys = set()
    base = None
    for sid in refs:
        p = manifests[sid]["parameters"]
        if base is None:
            base = p
            continue
        diff_keys |= {k for k in p if p[k] != base[k]}
    check("Reference scenarios differ only through the tiers",
          diff_keys <= {"urban_target_tier", "rural_target_tier"},
          f"keys that differ across {len(refs)} reference scenarios: {sorted(diff_keys)}")

    if a.reference_bu078 is not None and "BU_g0.078" in tot.index:
        inv = tot.loc["BU_g0.078", "investment_musd"]
        rel = abs(inv - a.reference_bu078) / a.reference_bu078
        check("BU_g0.078 total investment 2040 within 5 percent of the spike's D2_BOT_0.078 reproduction",
              rel <= 0.05, f"{inv:.2f} vs {a.reference_bu078:.2f} million USD ({rel:.1%})")

    lines += ["", "## Total investment 2040 by scenario (million USD)", "",
              "| Scenario | Urban tier | Rural tier | Grid cost | Investment 2040 | New connections 2040 | Capacity 2040 (MW) |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for sid in ids:
        r = tot.loc[sid]
        lines.append(f"| {sid} | {r.urban_target_tier} | {r.rural_target_tier} | {r.grid_generation_cost} | "
                     f"{r.investment_musd:,.2f} | {r.new_connections:,.0f} | {r.capacity_mw:,.2f} |")
    secs = sum(m["seconds"] for m in manifests.values())
    lines += ["", f"Wall-clock model time: {secs / 60:.1f} minutes for {len(ids)} scenarios.",
              f"Overall: {'PASS' if ok_all else 'FAIL'}"]
    (batch / "CHECKS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
