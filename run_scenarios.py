"""Run Guinea GEP-OnSSET scenarios from a control file.

    python run_scenarios.py Scenarios/guinea_scenarios.json                 # all, control-file order
    python run_scenarios.py Scenarios/guinea_scenarios.json --only BU_g0.1,BU_g0.22
    python run_scenarios.py Scenarios/guinea_scenarios.json --calibrate      # recalibrate first
    python run_scenarios.py Scenarios/guinea_scenarios.json --batch 2026-10-24_table1 --force
    python run_scenarios.py Scenarios/guinea_scenarios.json --dry-run        # resolved parameters, no run

Outputs land under paths.output_root/<batch>/<scenario_id>/ with the three CSVs
the notebook writes plus manifest.json; the batch folder holds
comparison_summary.csv and batch_log.txt.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "gep_onsset"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("control", help="path to the scenario control file (JSON)")
    ap.add_argument("--only", help="comma-separated scenario ids to run (default: all)")
    ap.add_argument("--batch", help="batch folder name under output_root (default: today's date)")
    ap.add_argument("--force", action="store_true", help="re-run scenarios that are already complete")
    ap.add_argument("--calibrate", action="store_true", help="run the calibration step first")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the resolved parameters of the selected scenarios and exit")
    a = ap.parse_args(argv)

    from scenario_control import ControlError, load_control
    from scenario_runner import run_batch, select_ids

    try:
        control = load_control(a.control)
        ids = [s.strip() for s in a.only.split(",")] if a.only else None
        selected = select_ids(control, ids)
        if a.dry_run:
            out = {sid: {"label": control.scenario(sid).label,
                         "legacy_name": control.scenario(sid).legacy_name,
                         "parameters": {k: (str(v) if isinstance(v, dict) and float("inf") in v else v)
                                        for k, v in control.resolved(sid).items()}}
                   for sid in selected}
            print(json.dumps({"control": str(control.path), "calibration": control.calibration,
                              "scenarios": out}, indent=2))
            return 0
        batch_dir = run_batch(control, ids, a.batch, force=a.force, calibrate_first=a.calibrate)
        print(f"done: {batch_dir}")
        return 0
    except ControlError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
