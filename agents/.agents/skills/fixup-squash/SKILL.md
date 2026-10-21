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

`$base` is the upstream base of the unpushed series, `origin/main` unless the
branch tracks another base. Set it in every new shell:

```bash
base=origin/main
```

## 1. Identify the target commit or commit separately

List the unpushed series, the files it touches, and the follow-up (tracked and
untracked):

```bash
git log --oneline "$base"..HEAD
git diff --name-only "$base"..HEAD
git diff HEAD
git status --short
```

If the series is empty, or the follow-up changes only documentation or comments
on files the series does not touch, stage the follow-up and end this skill by
invoking `propose-commit`.

Otherwise, pick the commit to fold into from
`git log --format='%H %s' "$base"..HEAD` and record its full SHA as `target`.
More than one plausible match means you stop and ask the user to disambiguate.

**Done when:** the follow-up is staged and `propose-commit` is invoked, or
`target` is the SHA of exactly one commit in `"$base"..HEAD`.

## 2. Choose the marker

| Follow-up | Marker |
|---|---|
| Small follow-up that only completes the original feature | `fixup!` |
| Bug fix for an earlier commit still on the branch | `fixup!` |
| New design decision or rationale that expands an earlier feature | `squash!` |

`fixup!` keeps the target's message. `squash!` carries a body with the
rationale the reviewer needs.

## 3. Create the marker commit

Stage the follow-up, then:

- `fixup!`: `git commit --fixup="$target"`
- `squash!`: `git commit --squash="$target" -m "<rationale>"` (git supplies the
  `squash! ...` subject and `-m` becomes the body)

**Done when:** `git log --oneline -1` shows the marker commit pointing at the
target, and for `squash!`, `git log -1 --format='%b'` is not empty.

## 4. Fold with rebase

Run the rebase with editors disabled so the todo and commit-message prompts
are bypassed:

```bash
GIT_EDITOR=true GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash "$base"
```

A `squash!` result uses the combined message as-is. Run `git commit --amend`
afterwards if that message should be edited.

On a conflict, resolve each file so the commit being replayed keeps only its
own change. `git show ORIG_HEAD:<file>` is the final state the series must
converge on. Then continue with the same editor settings:

```bash
GIT_EDITOR=true GIT_SEQUENCE_EDITOR=true git rebase --continue
```

> Manual fallback: if a conflict cannot be resolved that way or the editor still opens, follow `MANUAL-FALLBACK.md` instead of step 5. Its resets move `ORIG_HEAD`, so it ends with its own tree check.

**Done when:** the rebase completes, `git log --oneline "$base"..HEAD` shows no
remaining `fixup!` or `squash!` markers, and the working tree and index are
clean.

## 5. Verify the tree

A fold is a pure history rewrite, so the tree must match the pre-rebase tip.
`ORIG_HEAD` holds that tip through conflicts and `--continue`:

```bash
git diff --exit-code ORIG_HEAD HEAD
```

If it reports a difference, the rebase changed or dropped content. Stop and
investigate before pushing.

**Done when:** the diff is empty.
