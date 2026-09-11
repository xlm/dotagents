# dotagents

Version-controlled home for general `.agents/skills`.

This repo uses [GNU Stow](https://www.gnu.org/software/stow/) to symlink the `agents` package into `~`, so `npx skills` installs and updates write directly into the repo and can be reviewed with `git diff`.

## Install

From the repo root:

```bash
stow -t ~ -S agents
```

This makes `~/.agents` a symlink to `agents/.agents` in this repo.

## Uninstall

From the repo root:

```bash
stow -t ~ -D agents
```

This removes the `~/.agents` symlink. The files stay in `agents/.agents`.

## Install a third-party skill

```bash
npx skills add <pack> -g -a universal -s <skill>
```

For example, from Matt Pocock's skill pack:

```bash
npx skills add mattpocock/skills -g -a universal -s code-review
```

## Update skills

```bash
npx skills update
```

## Review and commit

After installing or updating, review the changes and commit them:

```bash
git diff
git add agents/
git commit
```
