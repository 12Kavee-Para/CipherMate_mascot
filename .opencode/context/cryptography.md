# Cryptography | PRD §1.3

## Concepts and boundaries
Hashing (SHA-256) produces a digest, not encryption. Authenticated encryption protects confidentiality and detects tampering under the key. Digital signatures provide integrity and evidence of control of a signing key; identity depends on trusted public-key binding. Use established libraries; never invent primitives or formats in a model response.

## Target capability registry
| Operation | Inputs | Expected result |
|---|---|---|
| crypto.hash | source | SHA-256 fingerprint |
| crypto.compare | source, baseline_ref | match / mismatch / no trusted baseline |
| crypto.encrypt | source, destination, key_ref | authenticated encrypted artifact |
| crypto.decrypt | source, destination, key_ref | plaintext only after authentication |
| crypto.identify_format | source | recognized metadata / unknown |
| crypto.key_create | purpose, supported algorithm, label | opaque key reference |
| crypto.key_manage | key_ref, allowed lifecycle action | metadata/status only |
| crypto.sign | source, signature_destination, key_ref | signature artifact |
| crypto.verify | source, signature_ref, public_key_ref | valid / invalid / indeterminate |

## Implementation assumptions
Earlier CipherMate starter supports version-marked Fernet authenticated encryption and SHA-256; it does not yet support signatures, vault-backed keys or arbitrary formats. Fernet is not AES-GCM. For future formats consider established AEAD APIs (e.g. AES-GCM with correct nonce discipline), Ed25519 signatures and secure key custody. A password-based format needs a vetted KDF, random salt and stored parameters. Do not select algorithms solely because the model suggests them; backend manifest decides.

## Security / errors
Preserve original input. Authenticate relevant metadata and ciphertext; never publish plaintext on invalid authentication. Report wrong/missing key and unsupported format without exposing details. No plaintext keys or passwords in model input. Key creation, rotation, signing and decryption are security-sensitive; backend determines approvals. Ciphertext without reliable metadata -> algorithm unknown. A trusted earlier digest or signature is needed to claim no change. Sign exact intended bytes; verify against trusted key identity and signature artifact.

## Example
"Has report.txt changed?" -> request baseline_ref if missing; a fresh digest alone cannot answer. "Decrypt broken.cm" -> if authentication fails, no destination publication; report failure and preserve original ciphertext.
