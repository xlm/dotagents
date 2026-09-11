# dotagents

Version-controlled home for general `.agents/skills`.

This repo uses [GNU Stow](https://www.gnu.org/software/stow/) to symlink the `dotagents` package into `~`, so `npx skills` installs and updates write directly into the repo and can be reviewed with `git diff`.

## One-time setup

```bash
cd /Users/xlm/dev/dotagents
stow -d . -t ~ dotagents
```

This makes `~/.agents` a symlink to `dotagents/.agents` in this repo.

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
git add dotagents/
git commit
```
