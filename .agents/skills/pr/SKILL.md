---
name: pr
description: Push the current feature branch and create or update a GitHub pull request for this repository when the user asks to open or publish a PR. Use the complete branch diff and any supplied issue references.
---

# Create pull request

Follow the repository's `AGENTS.md`. Describe the whole proposed change, including
earlier commits or sessions. Treat the final diff as authoritative when history
contains partial or reverted work. Create a draft only when requested.

## Resolve the branch and target

Inspect status, current branch, fetch and push remotes, and upstream tracking.
Resolve the target GitHub repository from Git configuration rather than personal
settings. For a fork, target the upstream repository and identify the head as
`<fork-owner>:<branch>`.

Use an explicit base supplied by the user. Otherwise read the target repository's
configured default branch through the GitHub integration or
`gh repo view <owner/repo> --json defaultBranchRef`. Use the remote symbolic HEAD
only as a fallback. Fetch the resolved base before reviewing the branch.

Stop and resolve the cause when fetching fails, HEAD is detached, or there are
no commits ahead of the base. If on the base branch, create a feature branch using
the name supplied by the user or ask for a name before publishing.

If tracked or untracked changes remain, do not silently include or discard them.
If the user asked to commit them, use the sibling [commit skill](../commit/SKILL.md)
with the authorized scope. Otherwise ask whether to commit them or publish only
the existing commits. Reinspect the branch after any commit.

## Review and validate

Inspect all proposed commits and the complete merge-base diff:

```sh
git log <base-ref>..HEAD --format='%h %s%n%b'
git diff <base-ref>...HEAD --stat
git diff <base-ref>...HEAD --name-status
git diff <base-ref>...HEAD
git diff <base-ref>...HEAD --check
```

Stop if the final diff is empty. Check for unintended files and credentials.
Run relevant `AGENTS.md` validation using current workspace manifests, reusing
results only when they still apply to the current changes. Report failed or
unavailable checks accurately.

## Write the title and description

Follow documented title rules and established repository style. Use the type,
scope, and breaking-change conventions from the
[commit skill](../commit/SKILL.md#write-the-message), based on the complete branch
diff rather than the latest commit. Do not use emoji in the title or description.
Keep the title within 72 characters unless repository rules say otherwise. Use
classic dashes (`-`).

Read any repository PR template and preserve its required fields. Lead with the
concrete problem and resulting behavior. Include decisions, risks, migrations, or
dependencies only when they help reviewers assess the change. An obvious change
usually needs one or two sentences plus relevant validation; scale detail to the
complexity. State what was checked and any meaningful validation gaps, without
claiming checks that did not run.

Deduplicate issue references from the user request, branch, commits, and diff.
Use `Refs` for bare references and preserve explicit `Fixes` or `Closes` linkage.
Never invent issue links or strengthen references into closing linkage.

## Publish

Use a connected GitHub integration when available, otherwise an authenticated
`gh` CLI. Resolve missing authentication before publication. Do not require a
particular teammate's credentials, global skills, or absolute filesystem paths.

1. Search all PR states for the resolved target, base, and head. Update a matching
   open PR instead of creating a duplicate. If a matching closed or merged PR
   makes a new publication ambiguous, ask for direction before retrying.
2. Push the current branch to the resolved push remote and branch. Preserve its
   existing upstream when appropriate; without one use
   `git push -u <push-remote> <branch>`. Resolve ambiguous remotes or a mismatched
   upstream destination before pushing. Never force-push without explicit
   authorization. If push output fails or is ambiguous, continue only after
   confirming the remote branch SHA equals local HEAD.
3. Create or update the PR with an explicit target, base, head, title, body, and
   requested draft state. Preserve an existing PR's draft state unless the user
   asks to change it. Never use auto-filled content.

With `gh`, write multiline Markdown to a temporary file outside the repository
and use `--body-file <path>` with `gh pr create` or `gh pr edit`. Do not interpolate
the body into shell commands. On ambiguous creation or update output, query the
PR before retrying to avoid duplicates. Leave unrelated PR fields unchanged;
request reviewers, merge, or change issue state only when authorized.

Confirm the PR's URL, title, head, base, and draft state. If the host provides a
PR attachment tool, attach every created PR to the current chat and attach an
existing PR when updating it. Return the URL, title, head and base, ready or draft
state, and relevant validation results or limitations.
