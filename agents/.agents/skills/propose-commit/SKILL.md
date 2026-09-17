---
name: propose-commit
description: Propose a Conventional Commit message for staged changes. Stop on empty diffs or blockers, classify the change, validate against the commit-msg hook when present, then wait for user approval.
triggers:
  - user
  - model
---

# Propose Commit

Wait for user approval before committing. Aim for a message the user can accept
with little or no editing.

## 0. Detect the commit-msg hook

```
hook="$(git rev-parse --git-path hooks)/commit-msg"
```

If `$hook` exists and is executable, the proposed message can be validated
against the same rules that will run at commit time. If not, note that hook
validation is unavailable and skip step 4. Never set `core.hooksPath` or
otherwise mutate repo or git config to activate a hook.

**Done when:** you know whether a commit-msg hook is available for validation.

## 1. Inspect and classify the staged diff

Run `git diff --cached --stat` and `git diff --cached`.

- **No staged changes**: the diff is empty. Stop and tell the user there is
  nothing to commit.
- Otherwise, load [git-commits.md](../../rules/git-commits.md) and apply its
  blocker and classification rules to the diff.

**Done when:** one of: the diff is empty and the user has been told there is
nothing to commit; the diff contains blockers and the user has been asked to
clean up; or every staged change is classified and any doc-split decision is
made (or the user is asked).

## 2. Propose a subject line

Write a subject line that follows
[git-commits.md](../../rules/git-commits.md#subject-and-body). Prefer an existing
scope. The scope-listing command is in
[git-commits.md](../../rules/git-commits.md#scope).

If the subject has a scope, verify it appears in that list (e.g. re-run with
`| grep -qxF '<scope>'`). If it does not, stop: show the full scope list and ask
the user to confirm the new scope or pick an existing one. If the list is
empty, warn that this would be the first scope in history and proceed only if
the scope is appropriate.

**Done when:** a subject line is written, is ≤50 characters, uses an allowed
Conventional Commit type and a single scope or none, does not restate the
type or start with a vague verb, and any scope present is in the history list
or explicitly confirmed by the user.

## 3. Propose a body

Add a body only when the `why` is not obvious from the subject and diff.
Explain context, trade-offs, or non-obvious consequences. Keep it to 1-3 short
sentences and wrap at 72 characters.

For the full body rules, see the
[subject and body rules in git-commits.md](../../rules/git-commits.md#subject-and-body).

**Done when:** a body is written, or the subject and diff already make the `why` clear.

## 4. Validate against the hook

Skip this step if step 0 found no executable commit-msg hook.

Write the proposed message to a temp file and run the hook before
presenting it. If the hook rejects it, fix the message and re-run the hook.
Only present a message the hook has accepted. Do not include comment lines in
the proposal.

```
msg_file=$(mktemp)
printf '%s\n' "$message" > "$msg_file"
"$hook" "$msg_file" && rm -f "$msg_file"
```

The Devin attribution footer is appended by the CLI at commit time. Do not
include it in the proposal and do not flag it.

**Done when:** the hook accepts the message, or no hook is present.

## 5. Show and wait

Present the proposed message in a code block:

```
<type>(<scope>): <description>

<body, if any>
```

Then briefly explain why the type and scope fit the diff. Wait for the user to
approve, edit, or reject. Do not commit until the user confirms the message.
If the user confirms and asks you to commit, follow the
[Before committing instructions in git-workflow.md](../../rules/git-workflow.md#before-committing)
to compose the final commit.

**Done when:** the user confirms the message or tells you to stop.
