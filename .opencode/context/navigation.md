# CipherMate context navigation

Version 1.0 | static, reviewed knowledge index. All paths are relative to the runtime project root. This is a custom OAC-inspired index, not an automatic OpenCode context loader. The agent must explicitly read required files.

## Mandatory for operational requests
| File | Purpose |
|---|---|
| `.opencode/context/security-policy.md` | Trust boundaries and forbidden behavior |
| `.opencode/context/routing-rules.md` | Domain routing, proposal contract, planning limits |
| `.opencode/context/approval-policy.md` | State changes and independent approval |
| `.opencode/context/verification-rules.md` | Evidence, failure handling, response statuses |

## Domain selection
| Request | Agent ID | Context |
|---|---|---|
| File search, copy, metadata, duplicate detection, summarization | file-agent | `.opencode/context/file-management.md` |
| Encryption, decryption, signatures, fingerprints | crypto-agent | `.opencode/context/cryptography.md` |
| Credentials and secret use | vault-agent | `.opencode/context/vault-management.md` |
| System inspection, permissions, scripts | linux-agent | `.opencode/context/linux-operations.md` |

## Reading order
Security -> routing -> domain -> approval -> verification. ContextScout can return a ranked subset; mandatory policy is never optional for operations. If two files conflict, use the restrictive interpretation and flag for review. The backend is the actual policy authority, not the index. Files are read-only at runtime; only approved maintainers edit them.

## Example
"Find and encrypt duplicate PDFs" -> file-management + cryptography + all mandatory context. Do not load vault or Linux context unless required by the actual request. No user uploads or mutable job state belong here.
