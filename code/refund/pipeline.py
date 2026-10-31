"""Run one complaint through all stages. The gate decides which reading of the complaint is trusted."""
from .data import ts
from .engine import audit, build_row
from .intake import parse
from .matcher import MatchError, find_debit


def try_match(ds, ident, cids, intake, audit_at):
    if not intake or not intake.is_failed_payment or intake.amount is None:
        return None
    try:
        return find_debit(ds, ident, cids, intake, audit_at)
    except MatchError:
        return None


def run_one(ds, ident, stmts, complaint, llm=None, trace=None):
    trace = trace if trace is not None else []
    cid_ = complaint["complaint_id"]
    received, audit_at = ts(complaint["received_at"]), ts(complaint["audit_at"])
    cids = ident.resolve(complaint["contact"])
    trace.append(f"contact {complaint['contact']} -> {cids or 'unknown'}")

    rules = parse(complaint["complaint_text"], received)
    model = llm.read(complaint["complaint_text"], received) if llm and llm.enabled else None
    m_rules = try_match(ds, ident, cids, rules, audit_at)
    m_model = try_match(ds, ident, cids, model, audit_at)

    # Gate: a reading is only trusted if it lands on exactly one real debit.
    if m_rules and m_model and m_rules[1]["rrn"] != m_model[1]["rrn"]:
        trace.append(f"GATE: rules and model disagree ({m_rules[1]['rrn']} vs {m_model[1]['rrn']}), keeping rules")
        match = m_rules
    else:
        match = m_rules or m_model
    if model is not None:
        trace.append(f"model read: failed={model.is_failed_payment} amount={model.amount} date={model.day} "
                     f"ref={model.ref} -> {'matched' if m_model else 'no unique debit'}")

    if match is None:
        says_failed = rules.is_failed_payment or (model is not None and model.is_failed_payment)
        if says_failed and cids:
            trace.append("GATE: complaint describes a failed payment but no unique debit found")
        trace.append("verdict NOT_APPLICABLE")
        return build_row(cid_, "NOT_APPLICABLE")
    cust, debit = match
    trace.append(f"debit {debit['rrn']} ({debit['activity_id']}) via {'rules' if match is m_rules else 'model'}")
    return audit(ds, ident, stmts, cid_, cust, debit, audit_at, received, trace)
