"""Stage 1: bank statements (PDF or CSV) become the same small row record.

Only statements are parsed for money movement. SMS, screenshots and merchant emails are claims, so the
engine never uses them to decide whether money came back.
"""
import csv
from dataclasses import dataclass
from datetime import date, datetime

import pdfplumber


@dataclass(frozen=True)
class Row:
    day: date
    narration: str
    debit: float
    credit: float


def _money(x):
    x = (x or "").replace(",", "").strip()
    return float(x) if x else 0.0


def parse_pdf(path):
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for r in table:
                    if not r or not r[0] or r[0].strip().lower() == "date":
                        continue
                    rows.append(Row(datetime.strptime(r[0].strip(), "%d/%m/%y").date(), (r[1] or "").strip(),
                                    _money(r[2]), _money(r[3])))
    return rows


def parse_csv(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        rd = csv.reader(fh)
        for r in rd:
            if not r or r[0].startswith("#") or r[0] == "txn_date":
                continue
            rows.append(Row(datetime.strptime(r[0], "%d-%b-%Y").date(), r[1].strip(), _money(r[2]), _money(r[3])))
    return rows


class StatementCache:
    """Parse each statement once and share it across all complaints."""

    def __init__(self, ds):
        self.ds = ds
        self._cache = {}

    def rows(self, file_id):
        if file_id not in self._cache:
            f = self.ds.files[file_id]
            path = self.ds.path(f)
            self._cache[file_id] = parse_pdf(path) if path.endswith(".pdf") else parse_csv(path)
        return self._cache[file_id]
