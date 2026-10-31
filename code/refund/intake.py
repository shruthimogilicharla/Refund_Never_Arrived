"""Read the complaint: is it about a failed payment, and which amount, date and reference does it describe?

The text is data. Nothing in it can change a rule; at most it supplies an amount, a date and a reference,
and those are only accepted if they point at exactly one real debit (see matcher.py).
"""
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

FAILED_WORDS = re.compile(r"\b(fail(ed|ure)?|debited|deducted|money (got )?cut|refund|stuck|not received|reversed?)\b",
                          re.I)
AMOUNT = re.compile(r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d{1,2})?)", re.I)
DAY = re.compile(r"\bon (\d{1,2}) (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", re.I)
REF = re.compile(r"\b(?:ref(?:erence)?|utr|rrn)\s*(?:no\.?|number)?\s*:?\s*(\d{12})\b", re.I)


@dataclass
class Intake:
    is_failed_payment: bool
    amount: Optional[float] = None
    day: Optional[date] = None
    ref: Optional[str] = None
    source: str = "rules"


def parse(text, received_at: datetime) -> Intake:
    amt = AMOUNT.search(text)
    if not amt or not FAILED_WORDS.search(text):
        return Intake(False)
    amount = float(amt.group(1).replace(",", ""))
    d = DAY.search(text)
    day = None
    if d:
        day = datetime.strptime(f"{d.group(1)} {d.group(2)[:3].title()} {received_at.year}", "%d %b %Y").date()
        if day > received_at.date():  # complaint about late December, received in January
            day = day.replace(year=day.year - 1)
    ref = REF.search(text)
    return Intake(True, amount, day, ref.group(1) if ref else None)
