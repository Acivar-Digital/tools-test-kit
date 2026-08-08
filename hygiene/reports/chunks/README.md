# kit-hygiene reports — placeholder format samples

`chunks/` holds **sanitized format samples only** (`.placeholder.*`). They show
end users the SHAPE of a generated report without leaking real `src2/` paths,
live findings, or credentials.

| Placeholder file | Real report produced by | Format |
|---|---|---|
| `circular_deps_audit.placeholder.md` | `find_circular_deps` | Markdown summary |
| `registry_clashes.placeholder.json` | `find_registry_clashes` | Structured JSON |
| `audit_checkpoint.placeholder.jsonl` | checkpoints (per-audit) | JSON-lines checkpoint |

## How a real report is generated
Each scanner writes to `kit-hygiene/reports/` at runtime, e.g.:
- `circular_deps_audit.md` + `circular_deps_audit.json` + `circular_deps_checkpoint.jsonl`
- `registry_clashes.json` + `registry_clashes_checkpoint.jsonl`

Real reports use the **same schema** as the placeholders; only the values differ
(live `src2/` paths, line numbers, findings, ISO timestamps).
