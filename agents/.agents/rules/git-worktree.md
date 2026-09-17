# Git worktrees

Isolate parallel or subagent work in a worktree under `.worktrees/`:

- Create from the main repo root: `git worktree add .worktrees/<name> -b <name>`; list with `git worktree list`; remove with `git worktree remove .worktrees/<name>`.
- Create worktrees only under `.worktrees/`, and keep the directory out of the index (`.gitignore` it if the repo does not already).
- Run worktree commands from the main repo root. From inside a worktree the new path nests under it and fails permission checks.
- Set a new worktree up like a fresh clone - it materializes tracked files only:
  - install dependencies and recreate gitignored local config (`.env`),
  - install hooks the repo ships (a `.githooks/` directory or an install script named in `AGENTS.md`).

Done when `git worktree list` shows the worktree under `.worktrees/` in the main repo root, with hooks, dependencies, and local config in place.
