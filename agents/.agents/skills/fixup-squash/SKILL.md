---
name: fixup-squash
description: Fold a follow-up into an earlier unpushed commit, or commit it separately.
triggers:
  - user
  - model
---

# Fixup or Squash

Use this to keep review history clean: fold a follow-up into an earlier unpushed
commit, or commit a standalone change separately.

## Variables

### Derived

Derive `$base` and `$branch` before starting, and re-derive them in any new shell:

```bash
base=origin/main
branch=$(git branch --show-current)
```

`$baseline` is also derived. Step 4 writes it to `$(git rev-parse --git-path fixup-squash-baseline)`. Keep that recorded value. In a new shell, re-derive `$base` and `$branch`, then recover `$baseline` from that file:

```bash
baseline=$(cat "$(git rev-parse --git-path fixup-squash-baseline)")
```

If the branch uses a different upstream base, set `$base` to that (e.g.
`origin/<branch>` or the merge-base with the upstream branch).

### Set during the skill

- `type`: `fixup`, `squash`, or `none`. Set to `none` in step 1 when the
  follow-up is a separate commit. Otherwise set to `fixup` or `squash` in step 2.
- `target`: the commit SHA or exact subject to fold into (only when `type` is
  `fixup` or `squash`).
- `target_kind`: `sha` or `subject` (only when `type` is `fixup` or `squash`).
- `body`: the rationale or design decision for a `squash!` marker (only when
  `type` is `squash`). `fixup!` markers keep the original commit message. Only `squash!` markers need a body.

## 1. Identify the target commit or commit separately

List the unpushed series, the files it touches, and the files the follow-up
changes (tracked and untracked):

```bash
git log --oneline "$base"..HEAD
git diff --name-only "$base"..HEAD
git diff --name-only HEAD
git status --short
```

Use `git diff HEAD` and `git status --short` to inspect the follow-up. If the
series is empty, or the follow-up changes only documentation or comments on files
the series does not touch, the follow-up should be committed separately. Stage the
follow-up changes, set `type=none`, and end this skill by invoking `propose-commit`.

**Done when (separate):** `type` is `none`, the follow-up changes are staged,
and `propose-commit` is invoked.

Otherwise, pick the commit to fold into. Record it as a full SHA or as the exact
subject line that will follow the marker.

```bash
target=<sha-or-subject>
target_kind=sha  # or subject
```

If `target_kind` is `subject`, the subject must match exactly one commit in the
series. Before continuing, verify that `target` resolves to exactly one commit
between `$base` and `HEAD`:

- SHA target: `git log --format='%H' "$base"..HEAD | grep -cFx -e "$(git rev-parse --verify "$target" 2>/dev/null)" || true`
- Subject target: `git log --format='%s' "$base"..HEAD | grep -cFx -e "$target" || true`

The count must be `1`. If it is `0` or greater than `1`, stop and ask the user to
disambiguate.

**Done when (fold):** `target` and `target_kind` are set, and the check shows exactly
one matching commit between `$base` and `HEAD`.

## 2. Choose the marker

| Follow-up | Marker |
|---|---|
| Small follow-up that only completes the original feature | `fixup!` |
| Bug fix for an earlier commit still on the branch | `fixup!` |
| New design decision or rationale that expands an earlier feature | `squash!` |

The table above is the rule: `fixup!` folds the follow-up without extra
rationale. `squash!` preserves rationale the reviewer needs.

```bash
type=fixup  # or squash
```

**Done when:** `type` is `fixup` or `squash` and matches the table (fixup for a
small follow-up or bug fix, squash for rationale or a design decision).

## 3. Create the marker commit

Stage the follow-up changes.

For a `squash!` marker, set `body` to the rationale or design decision the
reviewer needs to see. `fixup!` markers keep the original commit message. Only `squash!` markers need a body.

- SHA target:
  - `fixup!`: `git commit --fixup="$target"`
  - `squash!`: `git commit --squash="$target" -m "$body"` (with `--squash`,
    git supplies the `squash! ...` subject and `-m` becomes the body)
- Subject target:
  - `fixup!`: `git commit -m "fixup! $target"`
  - `squash!`: one `-m` carrying subject and body, per [git-commits.md subject and body rules](../../rules/git-commits.md#subject-and-body):

    ```bash
    git commit -m "squash! $target

    $body"
    ```

**Done when:** the staged changes are committed with a `fixup!` or `squash!`
marker that points at the target, `git log --oneline -1` shows the marker
commit, and, for `squash!`, `git log -1 --format='%b'` is not empty.

## 4. Tag the pre-rewrite baseline

The pre-rewrite tip is now the marker commit. Capture it with a local,
branch-scoped tag so the final tree can be checked for accidental changes.
`git tag -f` makes this idempotent. In a detached HEAD, `${branch:-detached}`
falls back to `detached`.

```bash
baseline="pre-rewrite-baseline/${branch:-detached}"
git tag -f "$baseline" HEAD
printf '%s\n' "$baseline" > "$(git rev-parse --git-path fixup-squash-baseline)"
```

Keep the recorded `$baseline` value.

**Done when:** `git rev-parse "$baseline"` equals `git rev-parse HEAD`,
`git log -1 --oneline` still shows the marker commit from step 3, and
`cat "$(git rev-parse --git-path fixup-squash-baseline)"` returns the tag name.

## 5. Fold with rebase

Run the rebase with editors disabled so the todo and commit-message prompts
are bypassed:

```bash
GIT_EDITOR=true GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash "$base"
```

`GIT_SEQUENCE_EDITOR=true` bypasses the rebase todo editor. `GIT_EDITOR=true`
also bypasses the commit-message editor, which `squash!` markers would otherwise
open. A `squash!` result will then use the combined message as-is. Run
`git commit --amend` afterwards if that message should be edited.

Resolve any conflicts and run `git rebase --continue` with the same editor
settings:

```bash
GIT_EDITOR=true GIT_SEQUENCE_EDITOR=true git rebase --continue
```

> Manual fallback: if the rebase stops before completion or the editor still opens, follow `MANUAL-FALLBACK.md`, then return here to verify.

**Done when:** the rebase completes, `git log --oneline "$base"..HEAD` shows no
remaining `fixup!` or `squash!` markers (each folded into its target), and the
working tree and index are clean.

## 6. Verify the tree and clean up

Compare the post-rewrite tree to the pre-rewrite baseline:

```bash
git diff --exit-code "$baseline"..HEAD
```

A fixup or squash is a pure history rewrite, so the diff must be empty. If it
reports a difference, the rebase or manual rebuild accidentally changed or
dropped content. Stop and investigate before pushing.

Once the diff is empty, remove the local tag and the per-worktree metadata
file:

```bash
git tag -d "$baseline"
rm -f "$(git rev-parse --git-path fixup-squash-baseline)"
```

**Done when:** the tree diff above returned `0` before cleanup, `git tag -l
"$baseline"` lists nothing, and the `fixup-squash-baseline` file no longer
exists.
