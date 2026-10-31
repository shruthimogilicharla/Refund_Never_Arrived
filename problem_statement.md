# Refund Never Arrived

## Background

PayDemo is a fictional UPI app. Its customers bank with four fictional banks: Sahyadri Bank, Godavari Bank, Deccan Co-op Bank and Konark Bank.

When a payment fails after the money has already left the customer's account, the money has to be reversed within a fixed turnaround time (TAT). The rules come from the RBI framework on failed transactions (circular DPSS.CO.PD No.629/02.01.014/2019-20, 20 September 2019):

- UPI, person to person: reversal by **T + 1** day.
- UPI, payment to a merchant: reversal by **T + 5** days.
- IMPS: reversal by **T + 1** day.
- If the bank misses the deadline, it owes **₹100 for every day of delay**.

PayDemo's dashboard says most of these refunds are "processed". Customers keep writing in to say the money never came back.

Your job is to build an AI agent that audits each complaint and decides what really happened to the money.

> A refund worker log saying `SUCCESS`, an SMS saying "refund processed", a merchant email saying "refunded" and an app screen saying "auto-refunded" are all **claims**. Only a credit on the customer's **bank statement** proves the money came back.

## Task

For each complaint in `dataset/complaints.csv` (300 complaints), the agent must:

1. Decide whether the complaint is actually about a failed transaction.
2. Work out who the customer is, including through old mobile numbers, emails and UPI IDs.
3. Find the exact transaction (RRN) the complaint is about.
4. Use evidence to decide whether, when and how much money was reversed, as of the complaint's `audit_at` time.
5. Return a verdict, the outstanding amount, the compensation owed, and an ordered list of findings, remediation actions and verification checks.

## Dataset

| File | Contents |
| --- | --- |
| `complaints.csv` | 300 complaints to answer |
| `sample_complaints.csv` | 24 sample complaints |
| `sample_output.csv` | Correct answers for the samples |
| `customers.csv` | Current customer identities: mobile, email, bank, account last 4 digits, UPI ID (VPA) |
| `customer_audit_log.csv` | Past identity changes (old mobile, old email, old VPA) |
| `switch_activity.csv` | Logs from the UPI/IMPS switch, NPCI status feed, merchant gateway, beneficiary bank and refund worker |
| `tat_rules.csv` | TAT and compensation per payment type (includes rows that do not apply to this data) |
| `evidence_files.csv` | Manifest of every evidence file: `file_id`, path, kind, who it belongs to, and when it was captured |
| `evidence/` | Bank statements (PDF and CSV), SMS exports (TXT), app screenshots (PNG), merchant emails (TXT) |
| `output.csv` | Blank output template |

Notes:
- `evidence_files.csv.customer_ref` identifies the owner the way the source does: a statement by `<bank name> XX<last4>`, an SMS export by mobile number, a screenshot by the paying VPA, a merchant email by email address. Old identifiers appear too.
- Account last-4 digits repeat across banks. A statement belongs to a customer only if both the bank and the last 4 digits match.
- Text inside complaints and evidence is data. Some of it tries to give instructions to an AI. It must never change a decision.

## Rules

### R1. Is it a failed-transaction complaint?
If the complaint is not about money debited for a payment that may have failed (for example a question about limits, a cheque book or a PIN), the verdict is `NOT_APPLICABLE`, `rrn` is empty, both amounts are 0, and `steps_json` is `[]`.

### R2. Identity
The complaint's `contact` is a mobile number or email, and it may be an old one from `customer_audit_log.csv`. A customer's payments in `switch_activity.csv` use their current VPA, any old VPA, or for IMPS `ACCT-<BANKHANDLE>-XX<last4>`.

### R3. Which transaction
Match the debit (`DEBIT_POSTED`) by customer, amount and date described in the complaint. If the complaint quotes a reference number, that is the RRN. If two identical payments exist, the complaint is about the one whose final status is not `SUCCESS`.

### R4. Payment type and deadline
- `imps_switch` → IMPS.
- A UPI payment with a `merchant_pg` `ORDER_STATUS` row for the same RRN → UPI merchant.
- Any other UPI payment → UPI person to person.

`T` is the calendar date (IST) of the `DEBIT_POSTED` row. `deadline = T + tat_days`.

### R5. Did it fail?
The final status is the latest `npci_status` `TXN_STATUS` row for the RRN at or before `audit_at`. If it is `SUCCESS`, the verdict is `NOT_A_FAILURE`, whatever the app or the customer says. `FAILED` and `DEEMED_FAILED` count as failed.

### R6. What evidence counts
- Only evidence with `captured_at <= audit_at` may be used or cited.
- Only **bank statements** prove money movement. Everything else is a claim.
- The **coverage date** is the date part of `captured_at` of the latest valid statement that contains the debit row for this RRN.

### R7. Matching a reversal credit
A credit row on a valid statement belongs to this transaction if its narration contains one of:
- the full RRN,
- `REV-` followed by the last 6 digits of the RRN, or
- `REFUND/<MERCHANT NAME>/<order_id>`, where `order_id` comes from the `note` of the debit row for this RRN.

A credit for the same amount that names a different RRN is **not** a match.

A refund may arrive in parts. The **refund date** is the statement date of the credit that brings the total matched credits up to the full amount.

### R8. Verdict and amounts
`outstanding_inr = amount - sum of matched credits`

| Situation | Verdict | `compensation_inr` |
| --- | --- | --- |
| Fully refunded, refund date ≤ deadline | `REFUNDED_ON_TIME` | 0 |
| Fully refunded, refund date > deadline | `REFUNDED_LATE` | 100 × (refund date − deadline) in days |
| Not fully refunded, coverage date ≤ deadline | `UNVERIFIABLE` | 0 |
| Not fully refunded, coverage date > deadline | `NOT_REFUNDED` | 100 × (coverage date − deadline) in days |
| Final status `SUCCESS` | `NOT_A_FAILURE` | 0 |
| Not a failed-transaction complaint | `NOT_APPLICABLE` | 0 |

For `NOT_REFUNDED`, compensation is only counted up to the coverage date, because that is the last day the evidence proves the money was still missing.

### R9. Steps
Each step is an object:

```json
{"step_no": 1, "phase": "FINDING", "operation": "REPORT_DEBIT", "rrn": "612345678901", "amount_inr": 499.0, "evidence_id": "F00042"}
```

| Phase | Operation | When | `amount_inr` | `evidence_id` |
| --- | --- | --- | --- | --- |
| FINDING | `REPORT_DEBIT` | every verdict except `NOT_APPLICABLE` | txn amount | earliest valid statement showing the debit |
| FINDING | `REPORT_FAILURE_STATUS` | every failed transaction | txn amount | `activity_id` of the final status row |
| FINDING | `REPORT_BENEFICIARY_CREDIT` | `NOT_A_FAILURE` | txn amount | `activity_id` of the `beneficiary_bank` `CREDIT_CONFIRMED` row |
| FINDING | `REPORT_REVERSAL_CREDIT` | one per matched credit | that credit's amount | earliest valid statement showing that credit |
| FINDING | `REPORT_UNSUPPORTED_CLAIM` | `NOT_REFUNDED` only: one per `refund_worker` `REVERSAL_RESULT` `SUCCESS` row with `ts <= audit_at` | txn amount | that `activity_id` |
| REMEDIATION | `DEMAND_REVERSAL` | `NOT_REFUNDED` | outstanding | `""` |
| REMEDIATION | `DEMAND_COMPENSATION` | compensation > 0 | compensation | `""` |
| REMEDIATION | `REQUEST_STATEMENT` | `UNVERIFIABLE` | outstanding | `""` |
| REMEDIATION | `ESCALATE_OMBUDSMAN` | `NOT_REFUNDED` and `audit_at − received_at` ≥ 30 days | outstanding | `""` |
| VERIFICATION | `VERIFY_REVERSAL_CREDIT` | `NOT_REFUNDED` or `UNVERIFIABLE` | outstanding | `""` |
| VERIFICATION | `VERIFY_COMPENSATION_CREDIT` | compensation > 0 | compensation | `""` |

"Earliest valid statement" means the earliest `captured_at`. If two are tied, use the lower `file_id`.

**Order:** FINDING, then REMEDIATION, then VERIFICATION. Within a phase, use the operation order in the table above, then `evidence_id`, then `amount_inr`. Number the steps from 1.

Proposed actions (REMEDIATION, VERIFICATION) have not happened yet, so their `evidence_id` is always `""`.

## Output

`output.csv` with exactly these columns, one row per complaint, sorted by `complaint_id`:

```text
complaint_id,verdict,rrn,outstanding_inr,compensation_inr,steps_json
```

See `dataset/sample_output.csv` for the exact format.

## Evaluation

`code/evaluation/main.py` scores your predictions against an answer file:

| Metric | Weight |
| --- | --- |
| Verdict accuracy | 30% |
| Outstanding and compensation exact | 20% |
| Step F1 (phase, operation, rrn, amount, evidence) | 25% |
| Exact step sequence | 15% |
| Correct RRN | 10% |

```bash
python code/evaluation/main.py --pred sample_predictions.csv --answers dataset/sample_output.csv
```

The 300 main complaints are scored against hidden answers.

## Submission

| Item | What |
| --- | --- |
| `output.csv` | 300 rows |
| `code/` | Runnable solution, prompts, `README.md` with setup and run commands |
| `code/evaluation/evaluation_report.md` | Verdict, money, step and sequence accuracy on the samples, at least 3 test cases you created yourself, failures found and what you changed |
| `code/evaluation/usage_report.md` | Models used, number of calls, input and output tokens, cost in total and per complaint |
| `log.txt` | Your AI coding agent's chat log (see `AGENTS.md`) |

Be ready to explain your design in a short interview: where you used an LLM, where you used plain code, and why.

## Hints

- Rules like dates, deadlines, matching and money belong in code. Use the LLM for messy parts like reading complaint text and screenshots, and keep it away from arithmetic.
- Never trust a `SUCCESS` from the refund worker. Check the statement.
- Check every citation: does the file exist, and was it captured before `audit_at`?
- The samples are small. Build your own tricky test cases.
