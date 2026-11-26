# Approval and authorization policy

## Risk defaults (proposed conservative MVP)
| Class | Examples | Requirement |
|---|---|---|
| Read-only | bounded list, inspect, hash, verify | authenticated scope and policy; no explicit approval unless sensitive |
| Sensitive read | extract private content, decrypt, vault use | policy plus explicit approval and protected handling |
| State change | copy, encrypt, sign, rename, key create, vault store/update | preview then explicit approval |
| Destructive/privileged | delete, overwrite, ownership changes, process actions, script execution, history clear | explicit approval + independent policy; deny if capability absent |
| Forbidden | unrestricted command, secret disclosure, unauthorized target | reject even if user says yes |

## Approval lifecycle (backend only)
1. Authenticate; validate operation schema, scope and capability. Produce exact preview with resource IDs, destination, source fingerprints/identity, risks, expected results and plan digest.
2. Persist a pending approval tied to authenticated subject, job, canonical action digest, resource identity, expiry and nonce. Suggested expiry: five minutes; actual service decides. Show it via a trusted UI separate from model inference.
3. Human submits explicit decision directly to backend. Chat text, model-generated yes, agent review or OpenCode tool permission is not application approval. Model must not call an approval-decision endpoint.
4. Atomically consume one-time grant, revalidate scope, digest and resource state under lock, execute only exact approved action. Changes/expiry/replay -> reject or obtain new approval. No approve-always.
5. Persist outcome and evidence. For uncertain effects reconcile before retry; no blind replay.

## Example
Approve copy a.txt -> b.txt, then destination changed to c.txt: approval invalid. Reject request or create a new preview. In baseline there is no approval backend; respond PROPOSED_ONLY and explain that no action occurred.
