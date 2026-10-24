---
name: fixup-squash
description: Fold a follow-up or late commit into an earlier commit, reword a commit, or commit the follow-up separately.
triggers:
  - user
  - model
---

# Fixup or Squash

Use this to keep review history clean: fold a follow-up into an earlier commit
in the series, reword a commit's message, or commit a standalone change
separately.

`$base` is the upstream base of the series, `origin/main` unless the branch
tracks another base. Set it in every new shell:

```bash
base=origin/main
```

## 1. Identify the change and its target

List the series, the files it touches, and any uncommitted follow-up (tracked
and untracked):

```bash
git log --format='%H %s' "$base"..HEAD
git diff --name-only "$base"..HEAD
git diff HEAD
git status --short
```

The change is one of:

- **Uncommitted follow-up**: if the series is empty, or the follow-up changes
  only documentation or comments on files the series does not touch, stage it
  and end this skill by invoking `propose-commit`.
- **Late commit**: a commit already in the series that belongs in an earlier
  one. Record its full SHA as `late`.
- **Reword**: a commit whose message alone changes.

Record the full SHA of the commit to fold into or reword as `target`. More than
one plausible match means you stop and ask the user to disambiguate.

**Done when:** the follow-up is staged and `propose-commit` is invoked, or
`target` (and `late`, for a late commit) is the SHA of exactly one commit in
`"$base"..HEAD`.

## 2. Choose the marker

| Change | Marker |
|---|---|
| Small follow-up that only completes the original feature | `fixup!` |
| Bug fix for an earlier commit still on the branch | `fixup!` |
| New design decision or rationale that expands an earlier feature | `squash!` |
| Message-only reword | `amend!` |

`fixup!` keeps the target's message. `squash!` carries a body with the
rationale the reviewer needs. `amend!` replaces the target's message.

## 3. Create the marker commit

A subject can repeat in the series, so every marker names its target by full
SHA, which autosquash also matches.

For an uncommitted follow-up, stage it, then:

- `fixup!`: `git commit -m "fixup! $target"`
- `squash!`: `git commit -m "squash! $target" -m "<rationale>"`

A reword or a late commit takes an `amend!` marker. `--fixup=reword:` refuses
`-m`, so write the message through a file whose first line is the
`amend! <sha>` that autosquash matches:

```bash
reword() { # <sha> <new message>
  f="$(git rev-parse --absolute-git-dir)/REWORD_MSG"
  printf 'amend! %s\n\n%s\n' "$1" "$2" > "$f"
  GIT_EDITOR="cp '$f'" git commit -q --fixup=reword:"$1"; rm -f "$f"
}
```

- Reword: `reword "$target" "<new message>"`
- Late commit: rename it into a marker for the target. For `fixup!`:
  `reword "$late" "fixup! $target"`. For `squash!`, use `squash! $target`, a
  blank line, then the rationale.

Every rebase rewrites SHAs, so a marker only matches commits that existed when
it was made. Fold each late commit on its own, before creating any other
marker: rename it, run steps 4 and 5 twice, then re-read `target` and `late`
from step 1 for the next change. Create the remaining markers together, so one
rebase folds them all.

**Done when:** each marker's message names its target's full SHA (for a late
commit, the `fixup!` or `squash!` line inside its `amend!` message), and for
`squash!`, the marker carries the rationale.

## 4. Fold with rebase

Run the rebase with editors disabled so the todo and commit-message prompts
are bypassed:

```bash
GIT_EDITOR=true GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash "$base"
```

A `squash!` result uses the combined message as-is. Run `git commit --amend`
afterwards if that message should be edited.

A late commit takes two passes: the first rebase applies the `amend!`, which
renames it into a `fixup!` or `squash!` marker, and the second folds it. Run
steps 4 and 5 again until no marker remains.

On a conflict, resolve each file so the commit being replayed keeps only its
own change. `git show ORIG_HEAD:<file>` is the final state the series must
converge on. Then continue with the same editor settings:

```bash
GIT_EDITOR=true GIT_SEQUENCE_EDITOR=true git rebase --continue
```

> Manual fallback: if a conflict cannot be resolved that way or the editor still opens, follow `MANUAL-FALLBACK.md` instead of step 5. Its resets move `ORIG_HEAD`, so it ends with its own tree check.

**Done when:** the rebase completes, `git log --oneline "$base"..HEAD` shows no
remaining `fixup!`, `squash!`, or `amend!` markers, and the working tree and
index are clean.

## 5. Verify the tree

A fold or reword is a pure history rewrite, so the tree must match the
pre-rebase tip. `ORIG_HEAD` holds that tip through conflicts and `--continue`:

```bash
git diff --exit-code ORIG_HEAD HEAD
```

If it reports a difference, the rebase changed or dropped content. Stop and
investigate before pushing.

**Done when:** the diff is empty after every rebase.
