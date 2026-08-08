# Beads Workflow Context

> **Context Recovery**: Run `bd prime` after compaction, clear, or new session
> Hooks auto-call this when a beads workspace is resolved

## Persistent Memories

Stored via `bd remember`. Search with `bd memories <keyword>`.

## Core Rules

- **Default**: Use beads for ALL task tracking (`bd create`, `bd ready`, `bd close`)
- **Prohibited**: Do NOT use TodoWrite, TaskCreate, or markdown files for task tracking
- **Workflow**: Create beads issue BEFORE writing code, mark in_progress when starting
- **Memory**: Use `bd remember "insight"` for persistent knowledge across sessions
- Persistence you don't need beats lost context
- Default: do not commit, push, or run dolt remote sync without explicit authority

## Essential Commands

### Finding Work
- `bd ready` - Show issues ready to work (no blockers)
- `bd list --status open` - All open issues
- `bd list --status in_progress` - Your active work
- `bd show <id>` - Detailed issue view with dependencies

### Creating & Updating
- `bd create "Issue title" --description "Why this issue exists" --type task --priority 2` - New issue
  - `--type`: task, bug, feature, epic, chore, or decision (choose ONE)
  - `--priority`: 0-4 or P0-P4 (0=critical, 2=medium, 4=backlog)
- `bd create "Issue title" --description "..." --type task --priority 2 --parent <id>` - Hierarchical child
- `bd update <id> --claim` - Claim work
- `bd update <id> --assignee username` - Assign to someone
- `bd update <id> --title "new title"` - Update title
- `bd update <id> --description "new desc"` - Update description
- `bd update <id> --notes "additional notes"` - Add notes
- `bd update <id> --design "design notes"` - Record design
- `bd close <id>` - Mark complete
- `bd close <id1> <id2> ...` - Close multiple issues at once
- `bd close <id> --reason "explanation"` - Close with reason
- **Tip**: When creating multiple issues, use parallel subagents
- **WARNING**: Do NOT use `bd edit` - it opens $EDITOR which blocks agents

### Dependencies & Blocking
- `bd dep add <blocked-id> <blocker-id>` - Add dependency (blocked-id depends on blocker-id)
- `bd blocked` - Show all blocked issues
- `bd show <id>` - See what's blocking/blocked by this issue

### Sync & Collaboration
- `bd dolt push` - Push beads to Dolt remote
- `bd dolt pull` - Pull beads from Dolt remote
- `bd search "keyword"` - Search issues by text

### Project Health
- `bd status` - Project statistics (open/closed/blocked counts)
- `bd doctor` - Check installation health
- `bd lint` - Check issues for missing template sections

### Quality Tools
- `bd create "Title" --description "..." --type task --validate` - Validate description has required sections
- `bd create "Title" --description "..." --type task --acceptance "criteria"` - Set acceptance criteria
- `bd config set validation.on-create warn` - Auto-validate on every create

### Lifecycle & Hygiene
- `bd defer <id> --until "+1w"` - Defer work to a future date
- `bd supersede <id> --with <new-id>` - Mark issue as superseded
- `bd close <id> --suggest-next` - Show newly unblocked issues after closing
- `bd stale` - Find issues with no recent activity
- `bd orphans` - Find issues with broken dependencies
- `bd human list` - List human-needed beads
- `bd human respond <id>` - Respond to a human-needed bead
- `bd human dismiss <id>` - Dismiss a human-needed bead

### Structured Workflows
- `bd formula list` - See available workflow formulas
- `bd mol pour <proto-id>` - Instantiate a proto as a persistent molecule
- `bd mol wisp <proto-id>` - Instantiate a proto as an ephemeral wisp

## Common Workflows

**Starting work:**
```bash
bd ready
bd show <id>
bd update <id> --claim
```

**Completing work:**
```bash
bd close <id>
git status
# Conservative/minimal/default: report status and proposed commands; wait for approval
# Team-maintainer opt-in only:
#   git add . && git commit -m "..."
#   bd dolt push
#   git push
```

**Creating dependent work:**
```bash
bd create "Implement feature X" --description "..." --type feature --priority 2
bd create "Write tests for X" --description "..." --type task --priority 2
bd dep add <tests-id> <feature-id>  # Tests depend on Feature
```

## Session Close Protocol

**CRITICAL**: Before saying "done" or "complete", run this checklist:

```
[ ] 1. bd close <id1> <id2> ...  (close completed issues)
[ ] 2. run quality gates        (tests, linters)
[ ] 3. git status              (check what changed)
[ ] 4. follow active profile   (conservative: report handoff; team-maintainer: commit/sync/push if enabled)
```

**Policy:** Conservative is the default. Do NOT push to git remote unless user explicitly types `git-push-remote`.
