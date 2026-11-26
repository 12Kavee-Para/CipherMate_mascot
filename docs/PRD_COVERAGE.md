# Coverage and engineering assumptions

Source: uploaded CipherMate PRD and agent pack. Original files preserved; changes are additive. The following is the actual beta scope, not a promise that all PRD acceptance criteria pass.

| Requirement | Implemented | Deferred / limitation |
|---|---|---|
| 1.1 Conversation | OpenRouter or DeepSeek planner, strict JSON, local offline grammar, uploads, clarification/status, browser preview | Live model not tested; no conversation memory, token streaming, actual subagent invocation or autonomous multi-step plans |
| 1.2 Files | Private logical file names, search (substring/extension), metadata, copy/move/rename/delete with approval, duplicates by SHA-256, uploads/downloads | No filesystem access to visitor PC; no recursive host browsing; virtual organization by move; no document extraction/summarization; no MIME-based parsing |
| 1.3 Crypto | SHA-256 comparison against supplied trusted reference, Fernet CM-FERNET-1, Ed25519 key generation, public key export, detached signatures and verification, format marker | No other formats, password KDF, embedded PDF signatures, key rotation or external trust chain; marker not proof of authenticity |
| 1.4 Vault | Encrypted at rest, private entry/update, metadata-only list, deletion, keys used inside crypto service | No external API credential-use operations, general plaintext retrieval, HSM/KMS or secure hardware, persistent rotation workflow |
| 1.5 Linux | Lab-only system and resource metrics; logical file metadata separate | Real host permissions, ownership, users/groups, process control and network inspection not exposed. Lab flag off by default. No access to user device |
| 1.6 Scripts | Fixed diagnostic preview and lab-only fixed Python diagnostic execution with approval | No arbitrary Bash execution, no privilege escalation; script generation beyond fixed template deferred |
| 1.7 History | Durable jobs and redacted events, scoped status/history, approved history event clearing | Job records retained; no conversation storage, secure erasure, retention worker |
| NFR security | Token scopes, typed operations, encrypted BLOBs and vault values, transactional approvals, no overwrite | Private beta auth; no public SSO, external security audit, separate KMS, tenant process isolation; metadata plaintext and provider sees submitted chat text |
| NFR reliability | SQLite transaction atomicity, version checks, idempotency keys for direct jobs, bounded model retries | Single worker, no distributed queue or automatic crash reconciliation of external side effects (none enabled), no load benchmark |

Architecture decisions: one LLM, no dynamic subagents; Markdown retained as reference modules; one operation per turn; SQLite encrypted small objects rather than OS file paths; no n8n, MCP optional; server-side OpenRouter or DeepSeek JSON API; manual private invite tokens; one-process bounded concurrency. These are implementation choices, not mandated PRD decisions. File uploads and private vault updates are explicit user actions; no model access to those endpoints. Model outputs are untrusted, and its free text cannot establish authorization or real execution. Sensitive data pasted into the chat is forwarded to provider; don't use real confidential material in beta.
