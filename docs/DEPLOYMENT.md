# Deployment and GitHub handoff

## 1. Local acceptance

Follow README. Run offline tests and fixtures first; validate the actual DeepSeek API with synthetic prompts. Do not expose the server until you have validated auth, quotas, upload handling, approval, download and logs. Keep your existing `.opencode` folder intact. This application imports Markdown instructions, not OpenCode permissions. OpenCode is a separate development harness; its own permission and model compatibility must be tested independently.

## 2. Push source to GitHub

Use a private repository for initial work. Create an empty repo via https://github.com/new (do not initialize with README if pushing a new local history). If you already have a repo, clone it and copy this source into a new branch after inspecting conflicts; do not overwrite the existing `.git` directory. Do not add runtime state, fixtures with keys, tokens or `.venv`. A private repository is not a secret vault.

```bash
cd ~/projects/CipherMate_Backend
# Only for a NEW repository:
git init -b main
git status --short --untracked-files=all
git add .opencode backend frontend docs scripts deploy tests .github AGENTS.md PRD.md README.md opencode.json requirements.txt requirements-dev.txt requirements-lock.txt .gitignore .env.example
# Inspect exact files staged; stop if any credentials or private state appear.
git diff --cached --stat
git diff --cached --name-only
git diff --cached --check
git commit -m "Implement CipherMate single-agent Python backend"
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

For existing repositories use a feature branch, `git remote -v`, commit reviewed changes and push `git push -u origin feature/ciphermate-backend`, then open a pull request. No force push. Authenticate using GitHub CLI `gh auth login`, SSH or your configured Git credential helper; never put a token in the remote URL. GitHub Actions runs the offline pytest suite automatically. It needs no DeepSeek key. Review CI logs and require passing tests before merge. If a secret was committed, revoke/rotate it immediately and coordinate history remediation; `.gitignore` cannot remove already tracked secrets.

## 3. Stage on Bonscore (example only)

Hosting stack, DNS, OS and website authentication are not known. If the current website is static or shared hosting without Python service support, deploy this backend on a separate VPS/application host. Use `ciphermate.bonscore.com` as an isolated origin where practical; the demo will be available at `/ciphermate/` and API at `/api/ciphermate/`. Configure DNS and HTTPS on that host. If using `www.bonscore.com/ciphermate/`, merge routes with the current application carefully. Use a dedicated origin where practical. The revised UI does not collect a token. Before hosting it, wire Bonscore authentication to the API through a trusted server-side identity adapter, with CSRF protection for cookie sessions. Until then hosted UI calls correctly return 401. Do not use local demo mode behind Nginx or any tunnel. Never expose an OpenCode server, port 8000 or direct SQLite file to the internet. Do not enable CM_LAB_LINUX on the website host.

For a Linux VPS using systemd/Nginx, after creating the `ciphermate` non-root service account and `/opt/ciphermate` source directory, install the venv and locked dependencies there. Use read-only application source for the service account; it should write only to its private state directory. Configure `/etc/ciphermate/runtime.env` with root-owned mode 0600, actual secret values from a secure provisioning process (systemd EnvironmentFile syntax: `KEY=value`, not `export KEY=...`; quote JSON correctly). Set `CM_DB_PATH=/var/lib/ciphermate/state.sqlite3`, `CM_LAB_LINUX=0`, `CM_LOCAL_DEMO=0`, stable master key, unique per-user tokens and DeepSeek key. Do not reuse local development keys. Do not publish values in this guide, Git or shell history. `deploy/ciphermate.service` creates the private state directory. Review then install unit, reload daemon, start service and inspect only sanitized status. For example:

```bash
sudo cp deploy/ciphermate.service /etc/systemd/system/ciphermate.service
sudo systemctl daemon-reload
sudo systemctl enable --now ciphermate
curl -fsS http://127.0.0.1:8000/api/ciphermate/health
```

Review and merge `deploy/nginx-snippet.conf` into the correct TLS vhost, with its documented rate-limit zone in `http {}`. Do not copy it over an existing server configuration. Test `sudo nginx -t` before `sudo systemctl reload nginx`. Verify external HTTPS, token-protected endpoints, upload size limits, reverse-proxy timeout and denial of direct worker ports. Configure firewall, private database backups and monitoring. A 5 MiB file limit requires reverse proxy to allow the raw upload body; multipart is deliberately not used. Do not log request headers/bodies, query strings with filenames or secret-entry data.

## 4. Public release gate

Before public launch replace manual bearer tokens with actual Bonscore identity/SSO and user-bound authorization; rate limit all authenticated and unauthenticated routes using the proxy; manage account revocation; implement CSRF protection for cookie auth; add user-visible deletion/retention, encrypted backups, key rotation, file scanning/type controls when enabling parsing, quota enforcement/maintenance, and provider privacy disclosure. Threat-model prompt injection and model output; review model response rendering and authorization tests. SQLite is adequate for this bounded one-worker MVP, not unbounded uploads/high throughput. Move to a durable DB + encrypted object storage and isolate worker services if scaling. Do not mount a general shell or production host filesystem. Independent security review is required before processing sensitive real documents. Performance targets are not yet benchmarked.

## 5. Optional MCP later

Not necessary for the website because FastAPI is its direct integration. If you later want the original OpenCode agents to execute tools, implement a private MCP adapter over the same typed endpoints: capabilities, submit proposal, scoped job status, scoped history. Bind account from authenticated transport and never expose approval, secret-entry, arbitrary HTTP/shell, or bearer credentials to the model. Keep actual MCP configuration disabled until tested on the installed OpenCode version. Direct Python and MCP share a service layer; MCP should not duplicate policy logic.
