# dotagents

_dot agents, not [no ~asians~ agents](https://www.youtube.com/watch?v=0YM9Ereg2Zo)_

Version-controlled home for general agent rules and skills.

This repo can be used in five ways:

1. Devin plugin
2. Claude Code plugin
3. Codex plugin
4. Copilot CLI plugin
5. Stow package

| | Devin plugin | Claude Code plugin | Codex plugin | Copilot CLI plugin | Stow package |
|---|---|---|---|---|---|
| What it gives | A global, always-on `AGENTS.md` for Devin, plus namespaced skills | A global, always-on `AGENTS.md` for Claude Code, plus namespaced skills | A global `AGENTS.md` for Codex via a hook you trust once, plus namespaced skills | A global, always-on `AGENTS.md` for Copilot CLI, plus skills | Only skills, symlinked into `~/.agents/skills` for any `.agents`-aware tool |
| How skills appear | `/xlm:<skill>` (e.g. `/xlm:code-review`) | `/xlm:<skill>` (e.g. `/xlm:code-review`) | `xlm:<skill>` (e.g. `xlm:code-review`) in the skill picker | `/<skill>` (e.g. `/code-review`) | `/<skill>` (e.g. `/code-review`) |
| `AGENTS.md` | Included: the repo root `AGENTS.md` is loaded by Devin | Included: the shared `SessionStart` hook injects the repo root `AGENTS.md` | Included: the shared `SessionStart` hook injects it once trusted via `/hooks` | Included: its own `sessionStart` hook wraps the repo root `AGENTS.md` in JSON | Not included: there is no universal global `AGENTS.md` path. Devin uses `~/.config/devin/AGENTS.md`, Claude `~/.claude/CLAUDE.md`, Cursor `~/.cursor/rules/*.mdc`, and so on. Stow only handles skills. |
| Install (CLI) | `devin plugins install .` | `claude plugin marketplace add ./` then `claude plugin install xlm@dotagents` | `codex plugin marketplace add ./` then `codex plugin add xlm@dotagents` | `copilot plugin marketplace add ./` then `copilot plugin install xlm@dotagents` | `stow -t ~ -S agents` |
| Install (Cloud) | `devin plugins install <owner>/dotagents` plus an account/enterprise/org/repo manifest. See details below | Not covered here | Not covered here | Not covered here | Not available - Stow is a local symlink |

If your tool has a plugin here, the plugin is the simplest path: one install, global rules, and skills. If you want unnamespaced skills or use another `.agents`-aware tool, use Stow. Do not combine a plugin and Stow in the same tool unless you are happy seeing each skill twice (`/code-review` and `/xlm:code-review`).

Inside this repo, Claude Code, Codex and Copilot CLI also load `AGENTS.md` as project instructions, so the rules appear twice here and nowhere else.

## Devin plugin

### Local only

From the repo root:
```bash
# Install via local clone
devin plugins install --local .

# Or install via git repo
devin plugins install xlm/dotagents

# Verify
devin plugins list
# Should list xlm

# Remove
devin plugins remove xlm
```

Installing makes the repo's root `AGENTS.md` an always-on rule in every Devin session and exposes the skills in `agents/.agents/skills` under the `xlm:` namespace, e.g. `/xlm:code-review`.

Local plugins are linked directly to the source folder, so edits to `AGENTS.md` or skill files take effect on the next Devin session - no reinstall or `devin plugins update` needed.

### Cloud

Install plugin via the Devin web app and set appropriate scopes. It is recommended to use the GitHub repo. This will propagate to Devin CLI too.

See https://docs.devin.ai/product-guides/plugins

## Claude Code plugin

The manifest is `.claude-plugin/plugin.json`. `.claude-plugin/marketplace.json` makes the repo a one-plugin marketplace named `dotagents`, which is how Claude Code installs plugins.

From the repo root:
```bash
# Install via local clone
claude plugin marketplace add ./
claude plugin install xlm@dotagents

# Or install via git repo
claude plugin marketplace add xlm/dotagents
claude plugin install xlm@dotagents

# Verify
claude plugin list
# Should list xlm@dotagents

# Remove
claude plugin uninstall xlm@dotagents
claude plugin marketplace remove dotagents
```

Inside a session, `/plugin` offers the same actions.

Installing injects the repo's root `AGENTS.md` into every Claude Code session through a `SessionStart` hook (it runs again after `/clear` and compaction), and exposes the skills in `agents/.agents/skills` under the `xlm:` namespace, e.g. `/xlm:code-review`. The namespace also keeps this repo's `code-review` apart from Claude Code's built-in `/code-review`.

A plugin installed from a local clone is read from that folder. Skill edits take effect on the next session or after `/reload-plugins`. `AGENTS.md` edits take effect on the next session, or after `/clear` or compaction, because `/reload-plugins` does not rerun the `SessionStart` hook. To try the plugin without installing it, run `claude --plugin-dir .`.

The manifest sets `"agents": []`. Without it Claude Code treats the stow package's `agents/` folder as its default subagent folder and registers every rule and skill doc as a subagent.

The manifest sets no `version`. Claude Code then versions a git install by commit, so the [update commands](#deploying-changes) pick up every push. With a pinned version it keeps the cached copy until the version changes.

## Codex plugin

Tested with Codex CLI 0.171.0. The manifest is `.codex-plugin/plugin.json`, and `.agents/plugins/marketplace.json` is the native Codex marketplace named `dotagents`. Codex prefers these over the Claude manifest and marketplace when both exist. Unlike Claude, Codex keeps the marketplace outside its manifest folder. See [Repo layout](#repo-layout).

From the repo root:
```bash
# Install via local clone
codex plugin marketplace add ./
codex plugin add xlm@dotagents

# Or install via git repo
codex plugin marketplace add xlm/dotagents
codex plugin add xlm@dotagents

# Verify
codex plugin list
# Should list xlm@dotagents as installed and enabled
codex debug prompt-input hi | grep -oE 'xlm:[a-z-]+' | sort -u

# Remove
codex plugin remove xlm@dotagents
codex plugin marketplace remove dotagents
```

The prompt lists implicitly invocable skills. Codex reads `policy.allow_implicit_invocation` from each skill's `agents/openai.yaml`, not Claude's `disable-model-invocation` frontmatter. Skills with that policy set to `false` remain available for explicit invocation but are absent from the prompt's skill list.

Open `/hooks` in a Codex session and trust the plugin's session-start hook once. Newly installed plugin hooks are untrusted, so installing alone does not inject rules. Start a new session after trusting it. Codex tracks both the hook command and the installed plugin bundle, so updating even `AGENTS.md` alone requires renewed trust.

Codex installs are cached copies in `$CODEX_HOME/plugins/cache/`, even for local clones, so follow [Deploying changes](#deploying-changes) after editing or pulling updates.

## Copilot CLI plugin

Tested with Copilot CLI 1.0.114. The manifest is `.github/plugin/plugin.json`, the legacy Copilot format, with skills at `agents/.agents/skills`. Copilot reads `.claude-plugin/marketplace.json`, so the repo is also a one-plugin `dotagents` marketplace for Copilot and no separate marketplace file is needed.

From the repo root:
```bash
# Install via local clone
copilot plugin marketplace add ./
copilot plugin install xlm@dotagents

# Or install via git repo
copilot plugin marketplace add xlm/dotagents
copilot plugin install xlm@dotagents

# Verify
copilot plugin list
# Should list xlm@dotagents

# Remove
copilot plugin uninstall xlm@dotagents
copilot plugin marketplace remove dotagents
```

The manifest cannot reuse the shared `hooks/hooks.json`. That hook prints `AGENTS.md` as raw text, which Copilot ignores. Copilot's `sessionStart` only injects rules from a JSON `additionalContext` object, so the manifest points at its own hook in `.github/plugin/hooks.json` that wraps the output with `jq`. Copilot ignores a `hooks` object inlined in the manifest. `jq` must be on `PATH`.

Skills appear unnamespaced under "Plugin skills" in `copilot skill list`, e.g. `/code-review`. A same-named personal skill, such as the stow package's at `~/.agents/skills`, wins the collision and the plugin copy is not listed.

A plugin installed from a local clone is loaded live from that folder, so edits take effect on the next session. `copilot plugin install <path>` instead copies the plugin under `~/.copilot/installed-plugins/` and is deprecated in favour of the marketplace route.

The manifest sets no `version`. `copilot plugin update` refreshes the installed copy without one.

Uninstalling a live plugin only disables it, because nothing was copied. Removing the marketplace completes removal.

A signed-in Copilot CLI 1.0.114 session was seen to receive the root `AGENTS.md` rules from both a local clone and a git install.

## Stow package

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

Installing makes `~/.agents` a symlink to `agents/.agents` in the repo. Any `.agents`-aware tool, such as Devin, sees the skills at `~/.agents/skills` and exposes them unnamespaced, e.g. `/code-review`.

The Codex app writes synced skills into `~/.agents/skills/synced/`, which is `agents/.agents/skills/synced/` when stowed. A local plugin install from that checkout bundles those skills too, even though the folder is gitignored.

## Updating `AGENTS.md` and skills

### External skills

To add or update external skills you'll need to stow first so they write to the repo.

From the repo root:
```bash
# Stow first i.e. ensure ~/.agents is symlinked to the repo's stow package (if applicable)
stow -t ~ -S agents

# Added or updated skills land in ~/.agents
npx skills add <pack> -g -a universal -s <skill>
npx skills update

# Unstow (if applicable)
stow -t ~ -D agents
```

### Deploying changes

#### Devin

If you have installed the Devin plugin [locally](#local-only), you can directly update the repo. New sessions will pick up new rules/skills immediately.

If you have installed via [Cloud](#cloud) then new Cloud sessions will automatically pick up changes but Devin CLI will need an update:
```bash
devin plugins update xlm
```

The manifest sets no `version`, which Devin treats as optional metadata. Devin caches a git install by commit, so `devin plugins update` picks up every push and `devin plugins list` shows the plugin as `unversioned`.

Starting a Devin CLI session does not refresh an installed git plugin. In 3000.14.30821 a session start left a local git install on its old commit, and only installed newly required organization plugins.

#### Claude Code

If you have installed the [Claude Code plugin](#claude-code-plugin) from a local clone, you can directly update the repo. New sessions will pick up new rules/skills immediately.

If you have installed the Claude Code plugin from the git repo, refresh it after pushing:
```bash
claude plugin marketplace update dotagents
claude plugin update xlm@dotagents
```

Claude Code can do this itself at session start, but auto-update is off by default for third-party marketplaces. Turn it on under `/plugin` > Marketplaces > dotagents. See [Claude Code plugin docs](https://code.claude.com/docs/en/discover-plugins.md).

#### Codex

For the [Codex plugin](#codex-plugin), local clone edits need a reinstall because Codex caches a copy:
```bash
codex plugin remove xlm@dotagents
codex plugin add xlm@dotagents
```

For a Codex git install, refresh after pushing:
```bash
codex plugin marketplace upgrade dotagents
```

The upgrade command refreshes installed plugins too. It is only for git marketplaces, not local clones. A reinstall is also possible after refreshing the git marketplace. Reinstalling without refreshing can reuse the old marketplace snapshot.

The Codex manifest needs no `version`. In 0.171.0, git marketplace upgrade picked up new commits both without a version and with an unchanged explicit version. Unlike Claude Code, a fixed version did not block the refresh. Without a version the cache directory ends in `local`, and with a version it ends in that version.

The Codex docs describe no automatic refresh. The 0.171.0 config schema does have `marketplaces.<name>.auto_update`, default `false`, but this was not tested.

Start a new Codex session after updating. Use `/hooks` to renew trust when the installed plugin bundle changes, including edits to `AGENTS.md` or the hook command. Before deploying plugin changes, run `scripts/check-plugins.py`.

#### Copilot CLI

If you have installed the [Copilot CLI plugin](#copilot-cli-plugin) from a local clone via the marketplace, you can directly update the repo. The plugin loads live from the folder, so edits take effect on the next session and there is nothing to refresh.

If you have installed the Copilot CLI plugin from the git repo, refresh it after pushing:
```bash
copilot plugin marketplace update dotagents
copilot plugin update xlm@dotagents
```

`copilot plugin marketplace update dotagents` only re-fetches the catalog. `copilot plugin update xlm@dotagents` pulls the new plugin files.

Custom marketplaces do not auto-update by default. Set `autoUpdate: true` on the `dotagents` entry of `extraKnownMarketplaces` in your user settings to update at the start of each interactive or `-p` session. See the [Copilot CLI plugin reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference).

Before deploying plugin changes, run `scripts/check-plugins.py`.

#### Stow

If you are using [stow](#stow-package), you can directly update the repo. New sessions will pick up new rules/skills immediately.

## Repo layout

Each tool reads its own manifest and, where it uses one, its own marketplace. The rules, skills and hook are shared.

| Path | Purpose | Read by |
|---|---|---|
| `AGENTS.md` | Global rules | Devin directly, Claude Code and Codex via the hook, Copilot CLI via its own hook |
| `agents/` | Stow package. `stow -t ~ -S agents` links `~/.agents` to `agents/.agents/` | Stow |
| `agents/.agents/skills/` | Shared skills | Every plugin, and Stow users |
| `agents/.agents/rules/` | Shared rule docs, listed in the `AGENTS.md` index. Skills reference them as `../../rules/<doc>.md` | Agents, on demand |
| `hooks/hooks.json` | Shared session-start hook that prints the root `AGENTS.md` | Claude Code, Codex |
| `.devin-plugin/plugin.json` | Devin manifest | Devin |
| `.claude-plugin/plugin.json` | Claude Code manifest | Claude Code, and Codex as a fallback |
| `.claude-plugin/marketplace.json` | Claude Code marketplace `dotagents` | Claude Code, Copilot CLI, and Codex as a fallback |
| `.codex-plugin/plugin.json` | Codex manifest | Codex |
| `.agents/plugins/marketplace.json` | Codex marketplace `dotagents` | Codex |
| `.github/plugin/plugin.json` | Copilot CLI manifest | Copilot CLI |
| `.github/plugin/hooks.json` | Copilot CLI `sessionStart` hook | Copilot CLI |
| `scripts/check-plugins.py` | Shared metadata plus Codex, Claude Code and Copilot CLI install, skill and hook checks, also run by `.github/workflows/check-plugins.yml` | You and GitHub Actions |

Where each tool looks:

| Tool | Manifest | Marketplace |
|---|---|---|
| Devin | `.devin-plugin/plugin.json` | None. `devin plugins install` takes the repo directly |
| Claude Code | `.claude-plugin/plugin.json` | `.claude-plugin/marketplace.json` |
| Codex | `.codex-plugin/plugin.json` | `.agents/plugins/marketplace.json` |
| Copilot CLI | `.github/plugin/plugin.json` | `.claude-plugin/marketplace.json` (shared with Claude Code) |

Things that are easy to get wrong:

- **The Codex marketplace is not in `.codex-plugin/`.** Claude keeps its manifest and marketplace together, but Codex only reads a marketplace from `.agents/plugins/marketplace.json`, or the Claude or Cursor marketplace as a fallback. Codex 0.171.0 rejects a `.codex-plugin/marketplace.json`.
- **Root `.agents/` is not `agents/.agents/`.** The root `.agents/` holds only the Codex marketplace, and any other root `.agents/` state is gitignored. Skills and rules go in `agents/.agents/`. Anything else under the root `.agents/` is not exposed by any plugin.
- **Shared metadata is repeated.** `name`, `description` and `author` appear in all four manifests, and the marketplace name and plugin list appear in both marketplaces. Change them together. `scripts/check-plugins.py` fails if they differ.

### Shared hook

The shared hook in `hooks/hooks.json` uses `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`: `PLUGIN_ROOT` is the open Agent Plugins name (set by Codex), and Claude Code only sets `CLAUDE_PLUGIN_ROOT`. Tools such as Cursor or Gemini need their own manifest before any hook runs. Copilot CLI keeps its own hook in `.github/plugin/hooks.json` because it needs a JSON `additionalContext` object, not raw stdout.

## Checking plugins

To check metadata for all four manifests and both marketplaces, plus install, skill discovery and hook output for Codex, Claude Code and Copilot CLI, without logging in:
```bash
# Requires Python 3 with PyYAML, codex, claude, copilot, bash and jq on PATH
scripts/check-plugins.py
```

The check uses throwaway Codex, Claude Code and Copilot CLI homes and removes them afterwards. Set `CODEX_BIN`, `CLAUDE_BIN` or `COPILOT_BIN` to test binaries outside `PATH`. Claude Code's no-login session lists user-invocable skills, including manual-only skills, and fires the hook before authentication fails. Copilot CLI lists all plugin skills without invocation-policy filtering. Its hook command is run directly and checked for JSON `additionalContext` containing the root `AGENTS.md`. The check does not call a model, so it cannot show that a trusted Codex session receives the rules or that Copilot injects them into a session. GitHub Actions runs the same check with Codex pinned to 0.171.0, Claude Code to 2.1.330 and Copilot CLI to 1.0.114. The Ubuntu runner includes `jq`.

A signed-in Codex session with the hook trusted was seen to receive the root `AGENTS.md` rules with no `~/.codex/AGENTS.md` present.
