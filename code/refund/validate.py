"""Check a finished output CSV against the contract before submitting.

    python -m refund.validate output.csv --dataset dataset --complaints complaints.csv   (run from code/)
"""
import argparse
import csv
import json
import os
import sys

from .data import read_csv, ts
from .engine import FIELDS, OP_ORDER, PHASES

VERDICTS = {"REFUNDED_ON_TIME", "REFUNDED_LATE", "NOT_REFUNDED", "UNVERIFIABLE", "NOT_A_FAILURE", "NOT_APPLICABLE"}


def validate(out_path, dataset, complaints_file):
    errors = []
    complaints = {c["complaint_id"]: c for c in read_csv(os.path.join(dataset, complaints_file))}
    files = {f["file_id"]: f for f in read_csv(os.path.join(dataset, "evidence_files.csv"))}
    acts = {a["activity_id"]: a for a in read_csv(os.path.join(dataset, "switch_activity.csv"))}
    with open(out_path, newline="") as fh:
        rd = csv.DictReader(fh)
        if rd.fieldnames != FIELDS:
            return [f"header must be {','.join(FIELDS)}"]
        rows = list(rd)
    ids = [r["complaint_id"] for r in rows]
    if ids != sorted(complaints):
        errors.append("rows must be exactly the complaint ids, sorted")
    for r in rows:
        cid = r["complaint_id"]
        audit_at = ts(complaints[cid]["audit_at"]) if cid in complaints else None
        if r["verdict"] not in VERDICTS:
            errors.append(f"{cid}: bad verdict {r['verdict']}")
        try:
            steps = json.loads(r["steps_json"])
        except json.JSONDecodeError:
            errors.append(f"{cid}: steps_json is not JSON"); continue
        if r["verdict"] == "NOT_APPLICABLE" and steps:
            errors.append(f"{cid}: NOT_APPLICABLE must have []")
        if [s["step_no"] for s in steps] != list(range(1, len(steps) + 1)):
            errors.append(f"{cid}: step numbers must run 1..n")
        keys = [(PHASES.index(s["phase"]), OP_ORDER.index(s["operation"]), s["evidence_id"], s["amount_inr"]) for s in steps]
        if keys != sorted(keys):
            errors.append(f"{cid}: steps out of order")
        for s in steps:
            ev = s["evidence_id"]
            if s["phase"] != "FINDING":
                if ev:
                    errors.append(f"{cid}: proposed step {s['operation']} must have empty evidence_id")
                continue
            src = files.get(ev) or acts.get(ev)
            if not src:
                errors.append(f"{cid}: unknown evidence {ev}")
            elif audit_at and ts(src.get("captured_at") or src["ts"]) > audit_at:
                errors.append(f"{cid}: evidence {ev} is after audit_at")
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("output")
    ap.add_argument("--dataset", default="dataset")
    ap.add_argument("--complaints", default="complaints.csv")
    a = ap.parse_args()
    errs = validate(a.output, a.dataset, a.complaints)
    for e in errs[:50]:
        print("ERROR", e)
    print("OK" if not errs else f"{len(errs)} problems")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
