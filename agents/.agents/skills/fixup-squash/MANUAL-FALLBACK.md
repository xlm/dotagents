# Manual fallback for fixup-squash

Use this when `git rebase -i --autosquash "$base"` from `fixup-squash` stops
before completion or the editor still opens.

Assumes the variables from `SKILL.md` are already set: `$base`, `$branch`,
`$target`, `$target_kind`, `$type`, and `$baseline`.

## 1. Abort the rebase and stage the unpushed changes

```bash
git rebase --abort 2>/dev/null || true
git reset --soft "$base"
```

`git reset --soft "$base"` leaves every unpushed change staged.

**Done when:** `git diff --cached` shows the combined unpushed changes and the
rebase is no longer in progress (`git status` shows a normal working tree).

## 2. Rebuild the series

Review the combined diff:

```bash
git diff --cached
```

If you need to rebuild the series commit by commit, clear the index with a mixed
reset:

```bash
git reset
```

Stage and commit each logical change in the intended order with the intended
messages. If you are unsure about the messages, end this skill and invoke
`propose-commit`.

**Done when:** the unpushed series is rebuilt, `git log --oneline "$base"..HEAD`
contains only the intended commits, and the working tree and index are clean.

## 3. Verify and return

Review the final series:

```bash
git log --oneline "$base"..HEAD
```

Then return to `SKILL.md` at step 6 to verify the tree against the baseline and
clean up.

**Done when:** the target commit contains the staged follow-up changes; the
target commit message is the original message for `fixup!` or the combined
message for `squash!`; and the series is ready for the tree check in
`SKILL.md` step 6.
