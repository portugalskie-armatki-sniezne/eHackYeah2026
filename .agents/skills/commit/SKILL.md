---
name: commit
description: Create a Git commit from the complete staged changes in this repository, optionally using a message hint or issue reference. Push the current branch only when the user explicitly requests it.
---

# Create commit

Follow the repository's `AGENTS.md`. Write the message from everything staged now,
including work from earlier sessions or other contributors. Treat the user's
request as intent and an optional message hint.

## Inspect and validate

Read the status, complete staged diff, and recent commit style:

```sh
git status --short
git diff --cached --stat
git diff --cached --name-status
git diff --cached
git log -10 --format='%h %s%n%b'
git diff --cached --check
```

If nothing is staged, ask which changes to stage unless the user already specified
them. Stage only explicitly authorized paths. Otherwise commit the staged snapshot
without adding unstaged changes.

Inspect staged files for credentials and unintended changes. Run the checks in
`AGENTS.md` that apply to the staged changes, using current workspace manifests
to identify available application checks. Report failed or unavailable checks
accurately. If unstaged edits affect validation, explain that the check used the
working tree rather than the exact staged snapshot.

## Write the message

Follow documented commit rules and established history. The current style is:

```text
EMOJI TYPE(SCOPE): summary
```

Choose the predominant type from the whole staged result:

| Prefix | Purpose |
| --- | --- |
| `🚀 feat` | New behavior or capability |
| `🐛 fix` | Bug fix |
| `📚 docs` | Documentation only |
| `🛠️ refactor` | Code changes without new behavior or a bug fix |
| `⚡ perf` | Performance improvement |
| `🧪 test` | Tests only |
| `🧹 chore` | Tooling, dependencies, configuration, or maintenance |

Derive a short scope from the changed repository paths, such as `web`, `api`,
`db`, or `repo`. Omit it when no clear scope fits. Use a concise summary, lowercase
when natural, no trailing period, and a full title of at most 72 characters.
Use classic dashes (`-`).

An obvious change needs only a title. Otherwise add prose explaining the reason,
result, and any meaningful compatibility, migration, or rollout concerns. Mark
breaking changes with `!` after the scope or type and add a
`BREAKING CHANGE: <description>` body block.

Preserve and deduplicate supplied issue references. Use `Refs` for bare references;
retain `Fixes` or `Closes` only when that linkage is explicit. Never invent issues
or strengthen a reference into closing linkage.

## Commit and optionally push

Run `git commit` with the generated message through normal hooks. For multiline
messages, write the exact text to a temporary file outside the repository and use
`git commit -F <path>`. Do not bypass hooks or amend unless explicitly requested.
On failure, preserve the work and report the actionable error; do not retry with
weaker checks.

Push only when explicitly requested. Resolve the current branch and use the
remote specified by the user, otherwise its upstream remote, then `origin`, then
the sole configured remote. Ask if the destination remains ambiguous or HEAD is
detached. Push to the same branch name without force. Verify ambiguous push
output against the remote branch SHA before retrying.

Verify the result with `git status --short` and `git show --stat --oneline HEAD`.
Return the hash, title, relevant validation results, remaining changes, and the
push destination or failure when a push was requested.
