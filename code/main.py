"""Refund Never Arrived - audit agent.

    python code/main.py                      # 300 complaints -> output.csv
    python code/main.py --sample             # 24 samples -> sample_predictions.csv
    python code/main.py --explain R0042      # one complaint with its full trace
    python code/main.py --llm                # also let the LLM read complaint text (needs LLM_API_KEY)
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from refund.data import Dataset, read_csv  # noqa: E402
from refund.engine import FIELDS  # noqa: E402
from refund.evidence import StatementCache  # noqa: E402
from refund.identity import IdentityIndex  # noqa: E402
from refund.llm import LLMReader  # noqa: E402
from refund.pipeline import run_one  # noqa: E402
from refund.validate import validate  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=os.path.join(ROOT, "dataset"))
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--explain", metavar="COMPLAINT_ID")
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()

    ds = Dataset(a.dataset)
    ident, stmts = IdentityIndex(ds), StatementCache(ds)
    llm = LLMReader(usage_path=os.path.join(ROOT, "llm_usage.jsonl")) if a.llm else None
    if a.llm and not llm.enabled:
        sys.exit("--llm needs LLM_API_KEY (or OPENAI_API_KEY) in the environment")

    complaints_file = "sample_complaints.csv" if a.sample else "complaints.csv"
    complaints = read_csv(os.path.join(a.dataset, complaints_file))
    if a.explain:
        allc = complaints + read_csv(os.path.join(a.dataset, "sample_complaints.csv" if not a.sample else "complaints.csv"))
        c = next((x for x in allc if x["complaint_id"] == a.explain), None)
        if not c:
            sys.exit(f"unknown complaint {a.explain}")
        trace = []
        row = run_one(ds, ident, stmts, c, llm, trace)
        print(c["complaint_text"], "\n")
        print("\n".join("  - " + t for t in trace))
        print("\n", {k: v for k, v in row.items() if k != "steps_json"})
        print(row["steps_json"])
        return

    rows = sorted((run_one(ds, ident, stmts, c, llm) for c in complaints), key=lambda r: r["complaint_id"])
    out = a.out or os.path.join(ROOT, "sample_predictions.csv" if a.sample else "output.csv")
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    errs = validate(out, a.dataset, complaints_file)
    print(f"wrote {len(rows)} rows to {out}; validation: {'OK' if not errs else errs[:5]}")
    if llm:
        print(f"LLM calls {llm.calls}, input tokens {llm.in_tokens}, output tokens {llm.out_tokens}")


if __name__ == "__main__":
    main()
