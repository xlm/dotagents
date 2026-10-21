# Manual fallback for fixup-squash

Use this when `git rebase -i --autosquash "$base"` from `fixup-squash` stops
before completion or the editor still opens.

## 1. Abort the rebase and record the baseline

```bash
git rebase --abort 2>/dev/null || true
baseline=$(git rev-parse HEAD)
git reset --soft "$base"
```

`$baseline` is the marker commit's tip. The resets below move `ORIG_HEAD`, so
step 3 compares against `$baseline` instead. `git reset --soft "$base"` leaves
every unpushed change staged.

**Done when:** `$baseline` is printed and kept for later shells, `git diff
--cached` shows the combined unpushed changes, and no rebase is in progress.

## 2. Rebuild the series

To rebuild commit by commit, clear the index with `git reset`, then stage and
commit each logical change in the intended order with the intended messages.
The original commits stay reachable from `$baseline`: `git log "$base".."$baseline"`
lists them, and `git checkout <sha> -- <file>` restores a file as one of them
left it. A folded target keeps its original message, plus the rationale for
`squash!`. If you are unsure about a message, invoke `propose-commit`.

**Done when:** `git log --oneline "$base"..HEAD` contains only the intended
commits, the target commit holds the follow-up, and the working tree and index
are clean.

## 3. Verify the tree

```bash
git diff --exit-code "$baseline" HEAD
```

**Done when:** the diff is empty.
