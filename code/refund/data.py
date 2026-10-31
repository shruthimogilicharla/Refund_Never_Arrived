"""Load the dataset once and build the indexes every stage shares."""
import csv
import os
from collections import defaultdict
from datetime import datetime


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def ts(s):
    return datetime.fromisoformat(s)


class Dataset:
    def __init__(self, root):
        self.root = root
        p = lambda name: os.path.join(root, name)
        self.customers = {c["customer_id"]: c for c in read_csv(p("customers.csv"))}
        self.audit_log = read_csv(p("customer_audit_log.csv"))
        self.activities = read_csv(p("switch_activity.csv"))
        self.files = {f["file_id"]: f for f in read_csv(p("evidence_files.csv"))}
        self.tat = {r["applies_to"]: (int(r["tat_days"]), int(r["compensation_inr_per_day"]))
                    for r in read_csv(p("tat_rules.csv"))}

        self.by_rrn = defaultdict(list)
        self.debits_by_payer = defaultdict(list)
        for a in self.activities:
            self.by_rrn[a["rrn"]].append(a)
            if a["event"] == "DEBIT_POSTED":
                self.debits_by_payer[a["payer_ref"]].append(a)

        self.statements_by_ref = defaultdict(list)
        for f in self.files.values():
            if f["kind"] == "bank_statement":
                self.statements_by_ref[f["customer_ref"]].append(f)

    def path(self, file_row):
        return os.path.join(self.root, file_row["path"])
