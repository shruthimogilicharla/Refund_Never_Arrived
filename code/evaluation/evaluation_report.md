# Evaluation report

## Results

Scored with `code/evaluation/main.py`.

| Set | Verdict | RRN | Money exact | Step F1 | Sequence exact | Row exact |
| --- | --- | --- | --- | --- | --- | --- |
| 24 samples (`sample_output.csv`) | 24/24 | 24/24 | 24/24 | 100% | 24/24 | 24/24 |
| 300 main complaints (organizer answer key) | 300/300 | 300/300 | 300/300 | 100% | 300/300 | 300/300 |

Read these numbers honestly. The challenge, its answer key and this solution were all built from the same written rules (`problem_statement.md`), so a perfect score shows the code follows those rules exactly. It does not show the agent would survive messier real-world data. The complaint text here is generated from templates, so plain regex reads it correctly every time.

`code/main.py` also runs `refund/validate.py` on every output: header, sorted IDs, verdict values, `[]` for `NOT_APPLICABLE`, step numbering and order, empty evidence on proposed steps, and that every cited file or activity exists and was captured at or before `audit_at`.

## Verdict mix in the final output

| Verdict | Count |
| --- | --- |
| NOT_REFUNDED | 113 |
| REFUNDED_LATE | 79 |
| REFUNDED_ON_TIME | 68 |
| NOT_A_FAILURE | 19 |
| UNVERIFIABLE | 12 |
| NOT_APPLICABLE | 9 |

## Test cases I created (`tests/test_cases.py`)

Each test builds a tiny dataset with one trap in it.

| Test | Trap | Expected |
| --- | --- | --- |
| `test_refund_worker_success_is_only_a_claim` | Refund worker logs `SUCCESS`, statement shows no credit | `NOT_REFUNDED`, the claim reported as `REPORT_UNSUPPORTED_CLAIM`, ₹800 compensation |
| `test_split_refund_late` | ₹400 on time + ₹600 four days late, one matched by `REV-<last6>` | `REFUNDED_LATE`, ₹400 (late counted from the day the full amount arrived) |
| `test_same_amount_credit_for_other_rrn_is_not_a_refund` | ₹1000 credit for a different RRN | Not matched, `NOT_REFUNDED` |
| `test_statement_after_audit_is_ignored` | The only statement showing the refund was captured after `audit_at` | `UNVERIFIABLE`, that file never cited |
| `test_merchant_refund_by_order_id_and_t_plus_5` | Refund narration has only the order ID; merchant deadline is T+5 | `REFUNDED_ON_TIME` |
| `test_old_mobile_resolves` | Complaint sent from an old mobile number | Right customer and RRN |
| `test_injection_in_complaint_changes_nothing` | Complaint tells the AI to mark it refunded | Still `NOT_REFUNDED` |
| `test_twin_payment_picks_the_failed_one` | Two identical ₹1000 payments 5 minutes apart, one succeeded | The failed RRN |
| `test_escalate_after_30_days` | No refund, 34 days since the complaint | `ESCALATE_OMBUDSMAN` added |
| `test_not_applicable` | Question about UPI limits | `NOT_APPLICABLE`, `[]` |
| `test_on_time` | Plain on-time reversal | `REFUNDED_ON_TIME` |
| `test_samples_end_to_end` | Full run on the 24 samples | 24/24 exact |

## Failures found and fixes

| Problem | What happened | Fix |
| --- | --- | --- |
| Split refunds with identical lines | Two refund parts with the same date, amount and narration were counted once when de-duplicating across statements | Count copies inside each statement and treat each copy as its own credit, cited from the earliest statement that has it |
| Coverage date | Using the latest statement of the account included statements unrelated to this transaction | Coverage = latest valid statement that actually contains this debit |
| Account owner | Matching statements by last 4 digits alone hit another customer's account at a different bank | Statements are matched on bank name + last 4 |
| IMPS payer | IMPS payer refs were ambiguous across banks | Payer ref includes the bank handle: `ACCT-<HANDLE>-XX<last4>` |
| Two identical payments | Amount + date matched two debits | Keep the one whose final NPCI status is not `SUCCESS` |

## Design limits

- Complaint reading uses regex by default. On real customer text it would miss things like "1.2k", "yesterday" or Telugu/Hindi text. The `--llm` mode lets a model read the text instead, behind the gate described in the README.
- Screenshots, SMS and merchant emails are never used to decide anything. In this data that is correct by rule. In real life they could help find the RRN when the complaint doesn't give one.
