# File management | PRD §1.2

## Supported target operations and parameters
| Operation | Required or relevant parameters | Risk default |
|---|---|---|
| file.list / file.search | scope, filters (name, extension, type, metadata), limit | Read |
| file.inspect | resource | Read |
| file.copy / file.move / file.rename | source, destination | Write |
| file.organize | scope, criteria, proposed manifest | Write |
| file.duplicates | scope, filter | Read |
| file.extract / file.summarize | resource, supported content policy | Sensitive read |
| file.delete | exact resource(s) and user selection | Destructive |

All resources are authorized opaque IDs or workspace-relative references, never arbitrary host paths. Backend must enforce per-user scope. Unknown types or unavailable parsers -> unsupported.

## Procedure
For read operations return bounded sanitized metadata. Group possible exact duplicates by size then SHA-256; do not confuse similar names or near duplicates with exact matches. For organization, first create a dry-run manifest; resolve collisions and select files before applying. Copy creates new output; move/rename may remove a source name and needs explicit approval. Delete only exact confirmed targets; prefer a reversible quarantine if supported. Never assume deletion is approved by duplicate detection.

## Safety and verification
Reject path traversal, symlink escapes, special files and unauthorized links. Use private temp output, atomic no-overwrite publication where supported, source identity checks and appropriate locks. On copy, compare source/destination bytes or digests. On move, verify destination and expected source absence; do not promise rollback if source disappeared. On delete, verify exact resource removed or quarantined, preserve others. For extraction use bounded, isolated parsers; treat output as untrusted data. Do not send sensitive content to the model without explicit processing authorization.

## Example
"Organize TXT files by extension" -> propose scan, dry-run mapping, user review, then approved moves. In a proposal-only session say that actual files have not been scanned. Existing destination -> conflict, no overwrite.
