# CipherMate | Bonscore Python backend

Runnable code-first single-agent prototype. No n8n, MCP or OpenCode server is required at runtime. The original six Markdown agent profiles and nine context files, PRD and OpenCode config are preserved byte-for-byte; the Python adapter reads the profiles as domain instructions and loads all nine context references once, rather than launching subagents. `context-scout.md` remains available for OpenCode testing; its runtime discovery role is replaced by deterministic loading. `AGENTS.md` remains the original development reference. The trusted Python registry, not the old prompt capability list, determines which operations really work.

## Quick start (Ubuntu, Python 3.13)

From the extracted `CipherMate_Backend` directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
bash scripts/run_local.sh
```

The launcher creates private runtime configuration only if absent and starts a direct, loopback-only local demo. Open http://127.0.0.1:8000/ (redirects to `/ciphermate/`). There is no token entry, login form or authentication connection button. Workspace tools opens private workspace tools, not a login screen. The owner is automatically selected for local browser requests. The opt-in `CM_LOCAL_DEMO=1` mode requires a single `owner` account; requests must come directly from loopback with a loopback Host, no forwarded headers, and same-origin writes. It is NOT website authentication; anyone with local access to this machine can use the demo. Do not use it on a shared/untrusted computer, behind a proxy, in a tunnel, or on an internet-facing server. Do not change the bind address or remove `--no-proxy-headers`.

The existing SQLite database, master key and API bearer token remain outside Git under `~/.local/state/ciphermate/` (0700 directory, 0600 config). Preserve and securely back up the key and data. Existing configuration is not regenerated. Uploaded files are private logical objects, not OS paths.

Offline smoke-test mode needs no external account. Try `list files`, upload `report.txt`, then `hash report.txt`, `duplicates`, `copy report.txt to copy.txt`, `vault list`. Approve the exact displayed job if required. To test encryption import a disposable Fernet key via the private vault form or submit `crypto.key_create` through the API, then type `encrypt report.txt to report.cm using lab-key` and `decrypt report.cm to decoded.txt using lab-key` (approve separately). Download and compare outputs. A 5 MiB input may exceed the 5 MiB output limit after encryption; it fails without changing originals. For arbitrary natural language enable DeepSeek.

## Enable OpenRouter

CipherMate reads its server-side credential from `OPENROUTER_API_KEY`. On 2026-11-27, one live request to `openai/gpt-4o-mini` used a synthetic question about storing a fictional password. OpenRouter returned HTTP 200. CipherMate validated the reply as an answer with no proposed operation. Automated provider tests use simulated responses.

The [localhost test video](docs/demo/localhost-tests.webm) shows the [synthetic report](docs/demo/sample-report.txt) being uploaded, encrypted, decrypted and downloaded in offline mode. The downloaded bytes matched the upload. The final segment lists the results of all 37 local tests. See the [30-case guide](docs/TEST_CASES.md) for sample inputs and expected outcomes.

In Bash, enter a fresh server-side credential at the hidden prompt. OpenRouter takes precedence when both providers are configured. Set `OPENROUTER_MODEL` to an account-enabled model supporting JSON output (default `openai/gpt-4o-mini`).

```bash
read -rsp 'OpenRouter key: ' OPENROUTER_API_KEY
echo
export OPENROUTER_API_KEY
bash scripts/run_local.sh
```

Chat text goes to the provider. Use the private vault form for credentials and the upload form for files.

## Enable DeepSeek (one model, no tool execution inside the model)

Stop the local server with Ctrl+C. In the same private terminal, enter the API key without echo:

```bash
read -rsp 'DeepSeek API key: ' DEEPSEEK_API_KEY; echo
export DEEPSEEK_API_KEY
export CM_MODEL=deepseek-flash
CM_LOCAL_DEMO=1 python -m uvicorn backend.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log --no-proxy-headers --limit-concurrency 32
```

These commands use Bash. If using Zsh, run `bash` first and activate the venv/source the runtime config again. `deepseek-v4-pro` is an alternative model ID if enabled in your account. Verify current provider docs https://api-docs.deepseek.com/quick_start/pricing/ and JSON mode https://api-docs.deepseek.com/guides/json_mode/. The adapter uses the official API endpoint, JSON mode, disabled thinking for lower latency, bounded output and at most one retry. A valid JSON object is not authorization: Pydantic and operation-specific schemas validate it. Never send confidential text or credentials to the chat endpoint; chat messages are sent to the model provider, not uploaded bytes, keys, history or runtime credentials. The model gets no approval endpoint or token. No automatic model retry of executed operations. No persistent conversational memory or automatic multi-step execution; every turn describes one exact task. A failed model call does not fall back silently to a different action. Direct DeepSeek access was not tested in this run.

## Backend API (all routes under `/api/ciphermate`)

Except `/health`, endpoints require bearer authentication by default. The explicit local demo exception is described above. The browser no longer contains a token entry or sets an Authorization header itself. Before hosted use, integrate Bonscore authenticated sessions/OIDC and CSRF checks, or an authenticated server-side gateway that maps verified users to backend bearer credentials (never trust client-supplied identity headers). The hosted browser will receive 401 until this integration is done. Never embed tokens in JavaScript or commit them. Keep `CM_LOCAL_DEMO=0` in hosted environments.

| Method / path | Function |
|---|---|
| GET /health | Liveness only |
| GET /capabilities | Exact enabled operation schemas |
| POST /chat | Natural-language or offline input, one proposal |
| POST /files?name=docs/a.txt | Raw octet-stream file upload |
| GET /download?name=docs/a.txt | Scoped file bytes, attachment |
| POST /jobs | Submit typed operation; optional Idempotency-Key header |
| GET /jobs/{id} | Scoped status and results |
| POST /jobs/{id}/approval | Human approves or rejects exact plan_digest |
| POST /vault/entry | Explicit private import/create, not an LLM tool |
| PUT /vault/entry | Explicit private replacement, not an LLM tool |
| GET /history | Last 100 scoped operation events |

Example `POST /jobs` JSON (not an approval):

```json
{"schema_version":"1.0","agent":"crypto-agent","decision":"propose","operation":"crypto.encrypt","parameters":{"source":"report.txt","destination":"report.cm","key_ref":"lab-key"}}
```

Response `AWAITING_APPROVAL` includes a server-assigned job ID, exact parameters, plan digest, and expiry. The human-controlled UI posts `{"approve":true,"plan_digest":"<returned digest>"}`. Never post approval automatically from model output. Read-only registered operations execute synchronously; all modeled state changes require approval. Private uploads and private credential entry/replacement are explicit user UI actions, not model operations. `COMPLETED` on a signature verification job means the check ran; inspect `result.valid` to know whether the signature was valid. HTTP errors have stable `error_code`; execution failures are job results.

## Test the actual previous fixtures

Keep the previous fixture ZIP OUTSIDE the repository. It contains disposable private keys. Run:

```bash
python -m scripts.verify_fixtures ~/Downloads/CipherMate_Validation_Fixtures.zip
```

It creates a temporary database and imports the synthetic files/keys without deploying them. Test actual detached raw Ed25519 signatures and the `CM-FERNET-1` format. It does not call the LLM. `docs/PRD_COVERAGE.md` maps outstanding requirements. The 20 earlier manual tests remain separate from automated tests. No public data or real credentials were used.

## Deployment and GitHub

Read [DEPLOYMENT.md](docs/DEPLOYMENT.md) and [RUNBOOK.md](docs/RUNBOOK.md). The `deploy/` folder includes sample systemd and Nginx snippets, not auto-installed configuration. Do not overwrite an existing Bonscore site. Prefer isolated private staging on a dedicated subdomain until security review. Use `.github/workflows/tests.yml` to run offline tests on pushes and pull requests. No remote repo was created or pushed by this package.

## Constraints

Private beta, one Python worker, small encrypted SQLite BLOBs, 200 files / 50 MiB plaintext quota per account, 5 MiB per artifact, up to 100 vault entries, 2000 jobs/account. Mutations serialized through SQLite transactions. Job and file metadata (names, labels, SHA-256, operation parameters) are not encrypted; use disk encryption and metadata minimization if sensitive. Backup DB and master key separately. No production-ready claims, no public enrollment, no arbitrary shell or privileged Linux commands. Linux metrics disabled by default; only enable in a disposable dedicated lab environment (not Bonscore host). No general credential egress, no PDF extraction/summarization, no actual remote PC access, no general script execution. Vault updates invalidate pending approvals referencing changed keys; replacing/deleting a key may make old ciphertext irrecoverable. Deletion is logical, not guaranteed physical erasure from backups/journals. No automatic durable job cleanup or key rotation. Public release requires security review, real auth, per-tenant isolation tests and deployment-specific controls.

## Chat and workspace tools

Chat and Connect each display a brief introduction. Click or tap a card, or focus its heading and press Enter, to expand its description in place. Type requests in the chat box. Use **Workspace tools** to open Files, Secure vault, or Operation history. Closing the chat reveals an **Open chat** button.

### Try actual operations without an AI API key

1. Workspace tools → Files → select a synthetic `report.txt` and upload it.
2. Chat: `list files`, then `hash report.txt`.
3. Chat: `create key fernet lab-key` and approve; use a unique label if it already exists.
4. Chat: `encrypt report.txt to report.cm using lab-key` and approve.
5. Chat: `decrypt report.cm to decoded.txt using lab-key` and approve.
6. Workspace tools → Files → download `decoded.txt` and compare it with the original. Connect → Operation history to inspect completed jobs.
7. To sign: `create key ed25519 lab-sign-key`, `public-key lab-sign-key to pub.pem`, `sign report.txt to report.sig using lab-sign-key` (approve each), then `verify report.txt with report.sig using pub.pem`. Check `result.valid`, not just COMPLETED. Existing names are not overwritten.
8. Voice → Start microphone → say “list files” → review the text → Send. If unavailable, type the same request. Try Read last reply if speech synthesis is supported.

The original 15 Markdown files and security/API contracts remain unchanged. `backend/chat.py` extends only the deterministic offline grammar to make more of the existing operations testable without a provider. The UI does not add arbitrary shell execution or external connections. Public hosting still requires real website authentication, HTTPS and deployment security review. See `docs/DEPLOYMENT.md`.
