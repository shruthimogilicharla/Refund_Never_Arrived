"""Build a one-page visual demo of the agent: docs/index.html (opens in any browser, also works on GitHub Pages).

    python code/dashboard.py            # all 300 complaints + 24 samples
"""
import json
import os
import sys
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from refund.data import Dataset, read_csv  # noqa: E402
from refund.evidence import StatementCache  # noqa: E402
from refund.identity import IdentityIndex  # noqa: E402
from refund.pipeline import run_one  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    data_dir = os.path.join(ROOT, "dataset")
    ds = Dataset(data_dir)
    ident, stmts = IdentityIndex(ds), StatementCache(ds)
    files = ds.files
    acts = {a["activity_id"]: a for a in ds.activities}
    items = []
    for fname, group in [("complaints.csv", "main"), ("sample_complaints.csv", "sample")]:
        for c in read_csv(os.path.join(data_dir, fname)):
            trace = []
            row = run_one(ds, ident, stmts, c, None, trace)
            steps = json.loads(row["steps_json"])
            for s in steps:
                ev = s["evidence_id"]
                if ev in files:
                    s["evidence_label"] = f"{files[ev]['kind'].replace('_', ' ')} · {files[ev]['path'].split('/')[-1]}"
                elif ev in acts:
                    a = acts[ev]
                    s["evidence_label"] = f"{a['system']} · {a['event']} · {a['result']}"
            items.append({"id": c["complaint_id"], "group": group, "text": c["complaint_text"],
                          "contact": c["contact"], "received": c["received_at"][:16].replace("T", " "),
                          "audit": c["audit_at"][:16].replace("T", " "), "verdict": row["verdict"], "rrn": row["rrn"],
                          "outstanding": float(row["outstanding_inr"]), "comp": int(row["compensation_inr"]),
                          "trace": trace, "steps": steps})
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    out = os.path.join(ROOT, "docs", "index.html")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_template.html"), encoding="utf-8") as fh:
        html = fh.read().replace("/*__DATA__*/[]", json.dumps(items, ensure_ascii=False))
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"dashboard: {out}")
    if "--no-open" not in sys.argv:
        webbrowser.open("file://" + out.replace("\\", "/"))


if __name__ == "__main__":
    main()
