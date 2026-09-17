# dotagents

_dot agents, not [no ~asians~ agents](https://www.youtube.com/watch?v=0YM9Ereg2Zo)_

Version-controlled home for general agent rules and skills.

This repo can be used in two ways:

1. Devin plugin
2. Stow package

| | Devin plugin | Stow package |
|---|---|---|
| What it gives | A global, always-on `AGENTS.md` for Devin, plus namespaced skills | Only skills, symlinked into `~/.agents/skills` for any `.agents`-aware tool |
| How skills appear | `/xlm:<skill>` (e.g. `/xlm:code-review`) | `/<skill>` (e.g. `/code-review`) |
| `AGENTS.md` | Included: the repo root `AGENTS.md` is loaded by Devin | Not included: there is no universal global `AGENTS.md` path. Devin uses `~/.config/devin/AGENTS.md`, Claude `~/.claude/CLAUDE.md`, Cursor `~/.cursor/rules/*.mdc`, and so on. Stow only handles skills. |
| Install (CLI) | `devin plugins install .` | `stow -t ~ -S agents` |
| Install (Cloud) | `devin plugins install <owner>/dotagents` plus an account/enterprise/org/repo manifest. See details below | Not available - Stow is a local symlink |

If you primarily use Devin, the plugin is the simplest path: one install, global rules, and skills. If you want unnamespaced skills or need to support a non-Devin `.agents`-aware tool, use Stow. Do not use both at the same time for Devin skills unless you are happy seeing each skill twice (`/code-review` and `/xlm:code-review`).

## Devin Plugin

### Local Only

From the repo root:
```bash
# Install via local clone
devin plugins install .

# Install via git repo
devin plugins install xlm/dotagents

# Verify
devin plugins list
# Should list xlm

# Remove
devin plugins remove xlm
```

Installing makes the repo's root `AGENTS.md` an always-on rule in every Devin session and exposes the skills in `agents/.agents/skills` under the `xlm:` namespace, e.g. `/xlm:code-review`.

Local plugins are linked directly to the source folder, so edits to `AGENTS.md` or skill files take effect on the next Devin session - no reinstall or `devin plugins update` needed.

Shared rule docs live in `agents/.agents/rules/` (`~/.agents/rules/` under stow). The `AGENTS.md` index lists them. Skills reference them as `../../rules/<doc>.md`.

### Cloud

Install plugin via the Devin web app and set appropriate scopes. It is recommended to use the GitHub repo. This will propagate to Devin CLI too.

See https://docs.devin.ai/product-guides/plugins

## Stow Package

From the repo root:
```bash
# Install
stow -t ~ -S agents

# Verify
ls -al ~ | grep agents

# Remove
stow -t ~ -D agents
# The files in the repo are unaffected
```

Installing makes `~/.agents` a symlink to `agents/.agents` in the repo. Devin (and any other `.agents`-aware tool) sees the skills at `~/.agents/skills` and exposes them unnamespaced, e.g. `/code-review`.


## Updating `AGENTS.md` and skills

### External skills

To add or update external skills you'll need to stow first so they write to the repo.

From the repo root:
```bash
# Stow first i.e. ensure ~/.agents is symlinked to the repo's stow package (if applicable)
stow -t ~ -S agents 

# Updates skills are in ~/.agents
npx skills add <pack> -g -a universal -s <skill>
npx skills update

# Unstow (if applicable)
stow -t ~ -D agents
```

### Deploying changes
If you have installed the Devin plugin [locally](#local-only) or are using [stow](#stow-package) then you can directly update the repo. New sessions will pick up new rules/skills immediately.

If you have installed via [Cloud](#cloud) then new Cloud sessions will automatically pick up changes but Devin CLI will need an update:
```bash
devin plugins update xlm
```
