# Secure vault | PRD §1.4

## Target operations
| Operation | Agent-visible fields | Trusted broker responsibility |
|---|---|---|
| vault.store | label, credential_type | private entry, encryption/keyring storage |
| vault.list | optional label filter | authorized metadata only |
| vault.update | credential_ref | private replacement and rotation |
| vault.use | credential_ref, operation_id | authorize destination/scope, inject internally |
| vault.delete | credential_ref | explicit approval, deletion/revocation as supported |

## Secret flow
User -> private secret-entry UI -> authenticated vault broker -> OS keyring/KMS/encrypted store. Model sees only nonsecret reference, label when safe, and status. Broker -> approved service operation -> sanitized result. Raw secrets never pass through chat, prompt, model-visible tool arguments, CLI flags, shell history, normal logs or Markdown. Do not accept raw values even if the user asks. If accidentally received, do not repeat; advise rotation as appropriate.

## Access rules
Verify authenticated owner and scope on every read/use/update. A reference is not authorization. Permit only registered service operations and destinations; prevent arbitrary outbound URLs and raw header/body echo. No plaintext fallback when storage fails. Keyring choice is an engineering decision; confirm an actual secure backend is available, particularly on headless Linux. Do not equate an environment variable with secure persistent custody.

## Verification and recovery
List only authorized metadata. For store/update return opaque reference and status; for use return safe outcome, not secret; for delete verify removal according to backend semantics, distinguish local deletion from remote revocation. Do not automatically replay uncertain lifecycle changes.

## Example
"Save my API token as lab-token" -> propose vault.store with label; private entry happens outside chat. In baseline, no private UI exists, so state that the operation cannot be performed.
