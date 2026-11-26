# Linux operations and scripts | PRD §§1.5–1.6

## Operation catalog (target)
| Operation | Scope / parameters |
|---|---|
| linux.inspect / linux.permissions | authorized resource |
| linux.users / linux.groups | approved metadata view |
| linux.processes / linux.resources | approved scope, bounded count |
| linux.system / linux.network / linux.disk_usage | approved read-only host/scope summary |
| linux.chmod | resource, exact octal mode |
| linux.chown | resource, authorized owner/group references |
| linux.process_action | stable process_ref, registered action/signal |
| script.propose | task, approved template candidate |
| script.execute_template | template_id, version, digest, validated arguments |

## Execution boundary
Never expose arbitrary command strings or a general shell as agent tools. Implement typed operations in Python or fixed argv allowlists (`shell=False`), validated parameters, isolated process identity, controlled environment, bounded output/time, no inherited sensitive variables and no implicit elevation. Restrict target account and workspace. An allowlisted executable alone is not sufficient: restrict flags, paths, child processes and resources. For process actions recheck PID start time/owner to avoid PID reuse; for chmod/chown verify exact file identity and policy. Default deny privileged actions unless a purpose-built authorized broker exists.

## Script workflow
Generate or select a reviewed script template, explain exact intended actions and effects, show the exact content/version/hash and validated arguments before execution. Human approval is bound to that artifact. Execute only in a suitable isolated environment using a trusted runner; never run arbitrary model-generated Bash. Unsupported template -> provide draft as text or decline execution. Return sanitized exit status/output/error; an exit code of 0 alone is not proof of requested postconditions.

## Examples
"Show memory usage" -> linux.resources (read-only). "chmod report.txt to 640" -> preview before/after, policy/approval, verify actual mode. "Run sudo or unrestricted shell" -> reject; offer supported scoped operations. If the host refuses permissions, report denied rather than bypassing.
