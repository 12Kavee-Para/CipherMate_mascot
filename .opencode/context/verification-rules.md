# Verification, errors and recovery

## Status vocabulary
Planning: PROPOSED_ONLY, NEEDS_CLARIFICATION, REJECTED, UNSUPPORTED, CONFIGURATION_ERROR. Integrated backend lifecycle: RECEIVED, PLANNED, AWAITING_APPROVAL, RUNNING, VERIFYING, COMPLETED, FAILED, REJECTED, EXPIRED, INDETERMINATE. HTTP success or an agent assertion is not proof of completion. Only verified backend evidence supports COMPLETED. Map actual API status values explicitly.

## Postconditions (deterministic checks)
| Domain | Evidence |
|---|---|
| File copy/organize | expected destination, digest/identity checks, source preserved unless approved move |
| Duplicate scan | bounded candidates and exact digest groups; no implicit delete |
| Encryption/decryption | authentication success, new output, original unchanged; wrong key/tamper leaves no plaintext |
| Fingerprint comparison | trusted reference exists; match/mismatch recorded |
| Signatures | trusted key reference, valid/invalid verification; do not equate validity with identity |
| Vault | scoped broker result; no plaintext in result/log/session |
| Linux | actual permissions, ownership, process identity or bounded system result |
| Script | exact reviewed artifact, exit status, side effects and expected postconditions |
| History | authorized sanitized events and timestamps; clear only within permitted retention scope |

## Failure classifications
- Missing parameter -> clarify. Unsupported capability -> unsupported. Policy/auth/approval failure -> reject. No automatic retry.
- Transient read-only failure -> at most two bounded retries with jitter and deadline, if backend proves safe. Never retry uncertain mutation. Use idempotency keys and reconciliation.
- Ambiguous side effect, crash, timeout or mismatch -> INDETERMINATE, stop dependent tasks, inspect actual state. Preserve originals and safe evidence. Obtain new approval if plan changes.
- Verification failure -> FAILED or INDETERMINATE, never silently fix or report success.

## Example
Network response lost after copy -> check job status and destination under lock; do not submit copy again. Unknown job after restart -> reconcile manually. A rejected delete must leave source unchanged. In proposal-only mode no verification evidence exists.
