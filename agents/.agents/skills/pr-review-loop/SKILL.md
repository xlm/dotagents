---
name: pr-review-loop
description: Fix or rebut outstanding Devin Review flags on a PR, one invariant per round.
triggers:
  - user
  - model
permissions:
  allow:
    - Read(**)
    - Write(**)
    - Exec(git)
    - Exec(gh)
    - Exec(sleep)
    - mcp__devin__devin_review_manage
---

# PR Review Loop

A *round* is one full pass: collect the outstanding flags, name the invariant they share, fix or rebut it, run the relevant tests when fixing, commit and push when fixing, and trigger the next review. Batching by invariant keeps the commit history clean and prevents a chain of review-fix commits. Run each round in one continuous turn, blocking on the review result, until the review is clean or a stop condition fires.

## Prepare the loop state

Before the first round, create a todo list with a single `Loop state` item. Set `round=1` there. Keep that single `Loop state` item as the only place for `round`, `pr_url`, `pr_url_confirmed`, `branch_matches`, `invariant`, `round_type` (`fix` or `rebuttal`), `plan` (fix plan or rebuttal text), and `stop reason`; update it each round.

Bind `pr_url` to the PR for the current branch - do not use an arbitrary or example PR URL:

1. Run `gh pr view --json url,headRefName` from the worktree.
2. If `gh` fails or no PR exists for the current branch, ask the user for the PR URL and stop.
3. Compare `headRefName` with `git branch --show-current`. If they do not match, stop and ask the user for the correct PR URL.
4. Display the derived `pr_url` to the user and ask for explicit confirmation. Only after confirmation, record `pr_url` in the `Loop state` item and set `pr_url_confirmed: true` and `branch_matches: true`.
5. If the user does not confirm, stop.

**Done when:** the todo list exists with a single `Loop state` item and `round=1`, `pr_url`, `pr_url_confirmed: true`, and `branch_matches: true` are set in it.

## Stop conditions

The loop stops when the user sends one of these messages at any point:

- The user says one or all flags are resolved, overriding the review output.
- The user asks you to stop (e.g., daily quota is full).

Point-in-time conditions are checked inside the loop steps where they become knowable.

## Poll the review status

Run this after triggering a review.

Call `mcp__devin__devin_review_manage` with `action: get_status` and the `pr_url` from `Loop state`. Read the `status` value from the result.

- If the `status` is `pending` or `running`, wait with `sleep 5` and call `get_status` again.
- If the `status` is a terminal state that is not `completed` (e.g. `failed`, `error`), update the `Loop state` item with `stop reason: review failed` and proceed to `## Final tidy`.

**Done when:** the review `status` is `completed`.

## The loop

1. **Outstanding flags collected.**
   - Call `mcp__devin__devin_review_manage` with `action: get_status` and the `pr_url` from `Loop state`.
   - If the status is a terminal state that is not `completed` (e.g. `failed`, `error`), update the `Loop state` item with `stop reason: review failed` and proceed to `## Final tidy`.
   - `action: trigger` starts a real Devin Review run on `pr_url`; call it only when `Loop state` has `pr_url_confirmed: true` and `branch_matches: true`.
   - If `get_status` reports that no review exists, call `mcp__devin__devin_review_manage` with `action: trigger` and the `pr_url` from `Loop state`. If the status is `pending` or `running`, leave the active review running.
   - Run `## Poll the review status`.
   - Once the status is `completed`, call `mcp__devin__devin_review_manage` with `action: get_findings` and the `pr_url` from `Loop state`.
   - If a programmatic path is unavailable, ask the user to paste the outstanding flags.
   - The `get_findings` output lists the review's findings. Keep findings whose status is `open`; drop `resolved` or `dismissed` entries.
   - If the filtered list is empty, the review is clean. Update the `Loop state` item with `stop reason: review clean` and proceed to `## Final tidy`.

   **Done when:** the filtered list of confirmed-open flags is known, or the agent is in `## Final tidy`.

2. **Invariants named and a single fix or rebuttal decided.**
   - Group the open flags by the invariant they point at. If the flags cannot be grouped into a single invariant, are contradictory, or need a product decision, update the `Loop state` item with `stop reason: flags unclear/contradictory` and proceed to `## Final tidy`.
   - Read the existing `invariant` and `round_type` values from the `Loop state` item. If a previous `invariant` is set and it matches the new invariant, the same invariant has been flagged again - update the `Loop state` item with `stop reason: repeated invariant` and proceed to `## Final tidy`. Otherwise, record it as the `invariant` field.
   - Decide whether this round is a **fix round** or a **rebuttal round** and record `round_type` in the `Loop state` item.
     - In a **fix round**, the invariant is real. State the invariant and design one fix for it. If a flag reports one bypass of a guard, see the [testing.md guard code rule](../../rules/testing.md#guard-code) and fix the whole class, not just the reported instance. Record the fix plan as the `plan` field in the `Loop state` item.
     - In a **rebuttal round**, the flagged invariant is wrong. Preserve the current code and draft a rebuttal that includes the flag text, severity, location, round, and the reason it is wrong. Surface the rebuttal for the user to post. Record the rebuttal as the `plan` field in the `Loop state` item.

   **Done when:** the `Loop state` item has `invariant`, `round_type`, and `plan` set, and either the round is a fix round with a stated invariant and a described single fix, or the round is a rebuttal round with a drafted rebuttal and unchanged current code.

3. **Fix applied and tests passing.**
   - If this is a rebuttal round, the current code is unchanged; skip to step 5.
   - Apply the fix immediately.
   - For guard or validator changes, write the attack matrix (the valid, invalid, and bypass input tests the [testing.md guard code rule](../../rules/testing.md#guard-code) requires) as tests first, then run the relevant test suite.
   - Discover the test command from the repo's `AGENTS.md`; if absent, infer from manifests (`package.json` scripts, `pyproject.toml`, etc.); if still unclear, ask the user.
   - If the suite fails, fix the failure and rerun it. If it still fails, show the failures and ask the user whether to approve a test skip.

   **Done when:** for a fix round, the fix is applied and the test suite passes, or the user has approved a test skip; for a rebuttal round, the code is unchanged and the agent is proceeding to step 5.

4. **Round committed and pushed once.**
   - If this is a rebuttal round, no code has changed; skip to step 5.
   - Commit as logical commits per [git-workflow.md](../../rules/git-workflow.md), or as `fixup!` commits targeting the commits they amend (invoke the `fixup-squash` skill for the mechanics).
   - Push once per round; the round gets exactly one push:
     ```
     git push
     ```

   **Done when:** for a fix round, the round is committed and pushed exactly once; for a rebuttal round, the step is skipped and the agent is proceeding to step 5.

5. **Next review triggered and completed.**
   - Call `mcp__devin__devin_review_manage` with `action: trigger` and the `pr_url` from `Loop state` (requires `pr_url_confirmed: true` and `branch_matches: true`).
   - Run `## Poll the review status`.

   **Done when:** the review `status` is `completed`, or the agent is in `## Final tidy` with `stop reason: review failed`.

6. **Loop ended or continued.**
   - If the user sent one of the messages in `## Stop conditions`, update the `Loop state` item with the appropriate stop reason and proceed to `## Final tidy`.
   - If the `round` value in the `Loop state` item is 5 (the fifth round has completed), update the `Loop state` item with `stop reason: fifth round reached` and proceed to `## Final tidy`.
   - Otherwise, increment `round` in the `Loop state` todo item and return to step 1.

   **Done when:** the `Loop state` item is updated and the agent is either back at step 1 or in `## Final tidy`.

## Final tidy

Run before the user views the branch, regardless of how the loop ended.

Invoke the `pre-push-review` skill and show the commit log from `origin/main..HEAD` so the user reviews the new commits added during the loop. If the branch is not based on `origin/main`, substitute the correct base (e.g. `origin/<base-branch>` or `git merge-base --fork-point origin/main HEAD`).

Run:
```
git log --oneline origin/main..HEAD
```

If the branch is a chain of review-fix commits, propose a rebuild and get explicit user approval before force-pushing. Present the final commit story so the user knows what to review.

**Done when:** `pre-push-review` has run and the commit log from the correct base to `HEAD` is shown.
