"""Score a predictions CSV against an answer CSV.

    python code/evaluation/main.py --pred output.csv --answers dataset/sample_output.csv

Metrics:
  verdict accuracy      exact verdict match
  rrn accuracy          the right failed transaction was identified
  money accuracy        outstanding_inr and compensation_inr both exact
  step F1               set overlap of (phase, operation, rrn, amount, evidence_id) per case
  sequence accuracy     steps_json exactly equal, order included
  row accuracy          every field exact
"""
import argparse
import csv
import json
import sys

FIELDS = ["complaint_id", "verdict", "rrn", "outstanding_inr", "compensation_inr", "steps_json"]


def load(path):
    with open(path, newline="") as fh:
        rd = csv.DictReader(fh)
        if rd.fieldnames != FIELDS:
            sys.exit(f"{path}: header must be exactly {','.join(FIELDS)} (got {rd.fieldnames})")
        return {r["complaint_id"]: r for r in rd}


def step_key(s):
    return (s.get("phase"), s.get("operation"), str(s.get("rrn")), round(float(s.get("amount_inr", 0)), 2),
            s.get("evidence_id", ""))


def parse_steps(txt):
    try:
        v = json.loads(txt)
        return v if isinstance(v, list) else None
    except Exception:
        return None


def money(x):
    try:
        return round(float(x), 2)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--answers", required=True)
    ap.add_argument("--show-misses", type=int, default=10)
    a = ap.parse_args()
    gold, pred = load(a.answers), load(a.pred)

    n = len(gold)
    c = dict(verdict=0, rrn=0, money=0, seq=0, row=0)
    tp = fp = fn = 0
    misses = []
    for cid, g in gold.items():
        p = pred.get(cid)
        if p is None:
            misses.append((cid, "missing row"))
            fn += len(parse_steps(g["steps_json"]) or [])
            continue
        gs, ps = parse_steps(g["steps_json"]), parse_steps(p["steps_json"])
        ok_v = p["verdict"] == g["verdict"]
        ok_r = p["rrn"] == g["rrn"]
        ok_m = money(p["outstanding_inr"]) == money(g["outstanding_inr"]) and \
            money(p["compensation_inr"]) == money(g["compensation_inr"])
        ok_s = ps is not None and [step_key(s) for s in ps] == [step_key(s) for s in gs] and \
            [s.get("step_no") for s in ps] == list(range(1, len(ps) + 1))
        c["verdict"] += ok_v
        c["rrn"] += ok_r
        c["money"] += ok_m
        c["seq"] += ok_s
        c["row"] += ok_v and ok_r and ok_m and ok_s
        gk = [step_key(s) for s in gs]
        pk = [step_key(s) for s in (ps or [])]
        rem = list(gk)
        for k in pk:
            if k in rem:
                rem.remove(k)
                tp += 1
            else:
                fp += 1
        fn += len(rem)
        if not (ok_v and ok_r and ok_m and ok_s):
            why = []
            if not ok_v: why.append(f"verdict {p['verdict']} != {g['verdict']}")
            if not ok_r: why.append(f"rrn {p['rrn']} != {g['rrn']}")
            if not ok_m: why.append(f"money ({p['outstanding_inr']},{p['compensation_inr']}) != ({g['outstanding_inr']},{g['compensation_inr']})")
            if ok_v and ok_r and ok_m and not ok_s: why.append("steps differ")
            misses.append((cid, "; ".join(why)))
    extra = set(pred) - set(gold)

    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    print(f"cases               {n}")
    for k, label in [("verdict", "verdict accuracy"), ("rrn", "rrn accuracy"), ("money", "money accuracy"),
                     ("seq", "sequence accuracy"), ("row", "row accuracy")]:
        print(f"{label:<20}{c[k]}/{n} = {c[k]/n:.1%}")
    print(f"step precision      {prec:.1%}   recall {rec:.1%}   F1 {f1:.1%}")
    print(f"weighted score      {(0.30*c['verdict']/n + 0.10*c['rrn']/n + 0.20*c['money']/n + 0.25*f1 + 0.15*c['seq']/n)*100:.1f} / 100")
    if extra:
        print(f"extra rows not in answers: {len(extra)}")
    for cid, why in misses[:a.show_misses]:
        print(f"  MISS {cid}: {why}")


if __name__ == "__main__":
    main()
