"""Stage 3: find the one debit the complaint is about."""
from .data import ts


class MatchError(Exception):
    pass


def final_status(ds, rrn, audit_at):
    rows = [a for a in ds.by_rrn[rrn] if a["system"] == "npci_status" and ts(a["ts"]) <= audit_at]
    return max(rows, key=lambda a: a["ts"]) if rows else None


def find_debit(ds, ident, cids, intake, audit_at):
    """Return (customer_id, debit_row). Raises MatchError unless exactly one debit fits."""
    cands = []
    for cid in cids:
        for ref in ident.payer_refs[cid]:
            for a in ds.debits_by_payer.get(ref, []):
                if abs(float(a["amount_inr"]) - intake.amount) > 0.005:
                    continue
                if intake.day and ts(a["ts"]).date() != intake.day:
                    continue
                if ts(a["ts"]) > audit_at:
                    continue
                cands.append((cid, a))
    if intake.ref:
        cands = [c for c in cands if c[1]["rrn"] == intake.ref]
    if len(cands) > 1:
        # two identical payments: the complaint is about the one that did not succeed
        cands = [c for c in cands if (final_status(ds, c[1]["rrn"], audit_at) or {}).get("result") != "SUCCESS"]
    if len(cands) != 1:
        raise MatchError(f"{len(cands)} candidate debits")
    return cands[0]
