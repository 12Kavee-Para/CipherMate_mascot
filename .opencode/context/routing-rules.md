# Routing and inter-agent proposal contract

Version 1.0. Names below are target operation IDs, not implemented OpenCode tools. An actual backend capability registry determines availability. Proposal-only mode never executes.

## Routing rules
| Intent | Owner |
|---|---|
| Discover, search, inspect, copy, organize, deduplicate, summarize, delete files | file-agent |
| Encrypt, decrypt, sign, verify, hash, compare fingerprints, key lifecycle | crypto-agent |
| Store, list, update, use, delete credentials | vault-agent |
| File modes/owner, users, groups, processes, resources, network, script templates | linux-agent |
| General conversation, history, status, clarification, multi-domain ordering | ciphermate |
| Context discovery | context-scout |

Hash for duplicate discovery can be a trusted internal file-service operation; standalone cryptographic fingerprints route to crypto-agent. Metadata routes to file-agent unless specifically about Linux permission/ownership. Do not invoke all agents for every request.

## Proposal schema (illustrative; enforce with backend discriminated unions)
```json
{"schema_version":"1.0","agent":"file-agent","decision":"propose","operation":"file.copy","parameters":{"source":"a.txt","destination":"b.txt"},"reason":"Create a separate copy","postconditions":["source unchanged","destination matches source"],"approval_hint":"required"}
```
Fields: schema_version fixed; agent known ID; decision = propose/clarify/reject/unsupported; operation = registered ID or null; parameters = operation-specific nonsecret object (empty for non-propose); reason = safe short explanation; postconditions = descriptive array (not authority); approval_hint = required/not_required/unknown (advisory only). For clarify add `questions` array; no action execution. No unknown keys, raw credentials, shell strings, model-generated approval claims or user identity fields. The backend assigns job ID, operation digest, authenticated identity, authoritative risk and actual postconditions. The LLM's free-text output is not automatically validated by Markdown.

## Shared operation registry (target)
- Files: file.list, file.search, file.inspect, file.copy, file.move, file.rename, file.organize, file.duplicates, file.extract, file.summarize, file.delete.
- Crypto: crypto.hash, crypto.compare, crypto.encrypt, crypto.decrypt, crypto.identify_format, crypto.key_create, crypto.key_manage, crypto.sign, crypto.verify.
- Vault: vault.store, vault.list, vault.update, vault.use, vault.delete.
- Linux: linux.inspect, linux.permissions, linux.users, linux.groups, linux.processes, linux.resources, linux.system, linux.network, linux.disk_usage, linux.chmod, linux.chown, linux.process_action, script.propose, script.execute_template.
- System: history.list, history.clear, job.status. These are backend/system functions; orchestrator must not implement them itself.

## Planning and coordination
Simple task -> one specialist. Complex task -> ordered proposals with dependencies; never invent outputs of earlier tasks. Read-only independent tasks may be parallelized after backend validation. Serialize mutations in the MVP; lock resource sets for later concurrency. No direct peer execution, recursive delegation or agent-controlled approval. Max four specialist calls and one replan per request in the initial prompt; implement hard budgets in the runtime.

## Example
"Search PDFs then encrypt selected files" -> propose file.search -> wait for verified results/selection -> propose crypto.encrypt for exact targets -> policy/approval -> execution -> verify. Do not submit a guessed batch.
