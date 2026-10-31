"""Stages 4-5: judge the money at audit_at and write the ordered plan.

Every rule here comes from problem_statement.md. Nothing in this file reads complaint text, SMS,
screenshots or emails, so nothing written there can change a verdict.
"""
import json
from collections import Counter
from datetime import timedelta

from .data import ts
from .matcher import final_status

OP_ORDER = ["REPORT_DEBIT", "REPORT_FAILURE_STATUS", "REPORT_BENEFICIARY_CREDIT", "REPORT_REVERSAL_CREDIT",
            "REPORT_UNSUPPORTED_CLAIM", "DEMAND_REVERSAL", "DEMAND_COMPENSATION", "REQUEST_STATEMENT",
            "ESCALATE_OMBUDSMAN", "VERIFY_REVERSAL_CREDIT", "VERIFY_COMPENSATION_CREDIT"]
PHASES = ["FINDING", "REMEDIATION", "VERIFICATION"]
FIELDS = ["complaint_id", "verdict", "rrn", "outstanding_inr", "compensation_inr", "steps_json"]


def payment_type(ds, debit):
    if debit["system"] == "imps_switch":
        return "IMPS"
    if any(a["system"] == "merchant_pg" and a["event"] == "ORDER_STATUS" for a in ds.by_rrn[debit["rrn"]]):
        return "UPI_MERCHANT"
    return "UPI_P2P"


def order_id(debit):
    note = debit.get("note", "")
    return note.split("order=", 1)[1].split()[0] if "order=" in note else None


def is_reversal_for(narration, rrn, order):
    if rrn in narration or f"REV-{rrn[-6:]}" in narration:
        return True
    return bool(order) and narration.startswith("REFUND/") and narration.endswith("/" + order)


def build_row(complaint_id, verdict, rrn="", outstanding=0.0, compensation=0, steps=()):
    steps = sorted(steps, key=lambda s: (PHASES.index(s[0]), OP_ORDER.index(s[1]), s[3], s[2]))
    out = [{"step_no": i + 1, "phase": ph, "operation": op, "rrn": rrn, "amount_inr": round(amt, 2),
            "evidence_id": ev} for i, (ph, op, amt, ev) in enumerate(steps)]
    return {"complaint_id": complaint_id, "verdict": verdict, "rrn": rrn, "outstanding_inr": f"{outstanding:.2f}",
            "compensation_inr": int(compensation), "steps_json": json.dumps(out, separators=(",", ":"))}


def audit(ds, ident, stmts, complaint_id, cid, debit, audit_at, received_at, trace=None):
    trace = trace if trace is not None else []
    rrn = debit["rrn"]
    amount = round(float(debit["amount_inr"]), 2)

    # R6: only statements captured at or before audit_at, owned by bank + last4
    owned = [f for f in ds.statements_by_ref[ident.statement_ref(cid)] if ts(f["captured_at"]) <= audit_at]
    owned.sort(key=lambda f: (f["captured_at"], f["file_id"]))
    with_debit = [f for f in owned if any(rrn in r.narration and r.debit > 0 for r in stmts.rows(f["file_id"]))]
    trace.append(f"{len(owned)} valid statements, {len(with_debit)} show the debit")
    if not with_debit:
        raise ValueError(f"{complaint_id}: no valid statement shows debit {rrn}")
    steps = [("FINDING", "REPORT_DEBIT", amount, with_debit[0]["file_id"])]

    # R5: final NPCI status decides failure, not the app or the customer
    fin = final_status(ds, rrn, audit_at)
    trace.append(f"final status {fin['result']} ({fin['activity_id']})")
    if fin["result"] == "SUCCESS":
        ben = [a for a in ds.by_rrn[rrn] if a["system"] == "beneficiary_bank" and a["event"] == "CREDIT_CONFIRMED"
               and ts(a["ts"]) <= audit_at]
        if ben:
            steps.append(("FINDING", "REPORT_BENEFICIARY_CREDIT", amount, ben[0]["activity_id"]))
        return build_row(complaint_id, "NOT_A_FAILURE", rrn, 0, 0, steps)
    steps.append(("FINDING", "REPORT_FAILURE_STATUS", amount, fin["activity_id"]))

    # R4: deadline
    ptype = payment_type(ds, debit)
    tat_days, per_day = ds.tat[ptype]
    deadline = ts(debit["ts"]).date() + timedelta(days=tat_days)
    trace.append(f"{ptype}: T={ts(debit['ts']).date()} deadline={deadline}")

    # R7: matched reversal credits, each counted once, cited from the earliest statement that shows it
    order = order_id(debit)
    first_seen = {}
    for f in owned:
        copies = Counter()
        for r in stmts.rows(f["file_id"]):
            if r.credit > 0 and is_reversal_for(r.narration, rrn, order):
                key = (r.day, r.narration, r.credit)
                copies[key] += 1
                first_seen.setdefault(key + (copies[key],), f["file_id"])
    credited, refund_day = 0.0, None
    for (day, narr, amt, _), fid in sorted(first_seen.items()):
        credited = round(credited + amt, 2)
        steps.append(("FINDING", "REPORT_REVERSAL_CREDIT", amt, fid))
        trace.append(f"credit {amt} on {day} in {fid}: {narr}")
        if refund_day is None and credited >= amount - 0.005:
            refund_day = day
    outstanding = round(max(0.0, amount - credited), 2)
    coverage = ts(with_debit[-1]["captured_at"]).date()
    trace.append(f"credited {credited}, outstanding {outstanding}, coverage {coverage}")

    # R8 + R9
    if outstanding <= 0.005:
        late = max(0, (refund_day - deadline).days)
        if late == 0:
            return build_row(complaint_id, "REFUNDED_ON_TIME", rrn, 0, 0, steps)
        comp = late * per_day
        steps += [("REMEDIATION", "DEMAND_COMPENSATION", comp, ""), ("VERIFICATION", "VERIFY_COMPENSATION_CREDIT", comp, "")]
        return build_row(complaint_id, "REFUNDED_LATE", rrn, 0, comp, steps)

    if coverage <= deadline:
        steps += [("REMEDIATION", "REQUEST_STATEMENT", outstanding, ""),
                  ("VERIFICATION", "VERIFY_REVERSAL_CREDIT", outstanding, "")]
        return build_row(complaint_id, "UNVERIFIABLE", rrn, outstanding, 0, steps)

    comp = (coverage - deadline).days * per_day
    for a in ds.by_rrn[rrn]:
        if a["system"] == "refund_worker" and a["event"] == "REVERSAL_RESULT" and a["result"] == "SUCCESS" \
                and ts(a["ts"]) <= audit_at:
            steps.append(("FINDING", "REPORT_UNSUPPORTED_CLAIM", amount, a["activity_id"]))
            trace.append(f"refund worker claimed SUCCESS ({a['activity_id']}) but no credit on statement")
    steps += [("REMEDIATION", "DEMAND_REVERSAL", outstanding, ""), ("VERIFICATION", "VERIFY_REVERSAL_CREDIT", outstanding, "")]
    if comp > 0:
        steps += [("REMEDIATION", "DEMAND_COMPENSATION", comp, ""), ("VERIFICATION", "VERIFY_COMPENSATION_CREDIT", comp, "")]
    if audit_at - received_at >= timedelta(days=30):
        steps.append(("REMEDIATION", "ESCALATE_OMBUDSMAN", outstanding, ""))
    return build_row(complaint_id, "NOT_REFUNDED", rrn, outstanding, comp, steps)
