---
name: babysit
description: Take the current task's repository changes through commit, draft PR, validation, and squash merge into main. Resume from existing commits or an open PR when asked to babysit changes to main.
---

# Babysit

Invocation authorizes committing the current task's changes, pushing, creating
or updating its PR, marking it ready, and squash merging into main.
Follow `AGENTS.md` and preserve unrelated work.

1. Inspect the working tree, branch, and existing PR; fetch the latest main.
   On main or detached HEAD, create a feature branch using repository conventions.
   Use a fresh branch when the previous PR was merged. Stop if there is no change
   to publish.

2. If staged, unstaged, or untracked task changes exist, review and stage them,
   then use [commit](../commit/SKILL.md). Ask only when their scope is unclear.
   Otherwise use existing commits.

3. Use [pr](../pr/SKILL.md) to push and create a draft PR targeting main, or resume
   its existing open PR. Base its title and description on the complete diff,
   using the commit skill's naming conventions.

4. Run relevant local validation and wait for CI on the current head. Mark the
   PR ready when needed to trigger required CI. If no CI is configured, report
   that gap and use the applicable local checks. Fix failures within the task's
   scope, commit and push, then repeat validation. Resolve safe merge conflicts
   while preserving both changes. Stop and report unrelated failures, missing
   required checks, blocked approvals, ambiguous conflicts, or repeated failures
   without progress. Never bypass checks or branch protection, or force-push.

5. When validation passes and required approvals are satisfied, mark the PR
   ready and squash merge into main, guarded by the validated head SHA. Use the
   final PR title as the squash commit title and a concise description of the
   resulting change as its body. If the head changes, validate it again.

6. Verify the PR is merged. Return its URL, squash commit hash, validation
   results, and any remaining local changes.
