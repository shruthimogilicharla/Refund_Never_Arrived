"""Stage 2: a customer is a set of identifiers, current and old."""
from collections import defaultdict


class IdentityIndex:
    def __init__(self, ds):
        self.ds = ds
        self.by_contact = defaultdict(set)
        self.payer_refs = defaultdict(set)
        for c in ds.customers.values():
            cid = c["customer_id"]
            self.by_contact[c["mobile"]].add(cid)
            self.by_contact[c["email"].lower()].add(cid)
            handle = c["vpa"].split("@")[1]
            self.payer_refs[cid].add(c["vpa"])
            self.payer_refs[cid].add(f"ACCT-{handle.upper()}-XX{c['account_last4']}")
        for u in ds.audit_log:
            cid = u["customer_id"]
            if u["field"] == "mobile":
                self.by_contact[u["old_value"]].add(cid)
            elif u["field"] == "email":
                self.by_contact[u["old_value"].lower()].add(cid)
            elif u["field"] == "vpa":
                self.payer_refs[cid].add(u["old_value"])

    def resolve(self, contact):
        """Customer IDs reachable from a complaint contact (mobile or email, current or old)."""
        return sorted(self.by_contact.get(contact.strip().lower(), set()) |
                      self.by_contact.get(contact.strip(), set()))

    def statement_ref(self, cid):
        """Statements are owned by bank + last 4. Last 4 alone collides across banks."""
        c = self.ds.customers[cid]
        return f"{c['bank_name']} XX{c['account_last4']}"
