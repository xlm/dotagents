---
name: automate-releases
description: Set up automated semver releases for a GitHub repo - git-cliff picks the version from conventional commits, a bot commits and tags it, and a GitHub release publishes the notes and any built artifacts.
disable-model-invocation: true
---

# Automate releases

Install the release flow in [`templates/`](templates/) into the target repo.
The templates carry the logic. This skill holds the decisions to make and the
invariants to keep while adapting them, most learned from a failed release.

| Template | Goes to | Adapt |
| --- | --- | --- |
| `cliff.toml` | `cliff.toml` | Commit groups, if the repo wants others |
| `release.py` | `scripts/release.py` | The constants at the top |
| `test_release.py` | `scripts/test_release.py` | Cases for any code you add |
| `release.yml` | `.github/workflows/release.yml` | Gate name, branch, artifact prefix, or the build job removed |

## Steps

1. **Decide.** Read the target repo's workflows, version files and history,
   then ask the user one numbered list, each item with a recommended answer:
   - Default branch, and the workflow that gates a release. The gate must
     run on push to the default branch.
   - Where the version lives: files bumped in a `release: X.Y.Z` commit, or
     tag only.
   - First version, and the tag or commit release notes start after when
     earlier history is not conventional.
   - Artifacts to build and attach, and their file prefix.
   - Bump policy. Default: `feat` bumps minor, breaking changes bump minor
     while on 0.x.

   Done when every item has an answer.
2. **Install.** Copy the templates to their destinations and adapt them:
   - `release.py`: set `BRANCH`, `GATE_WORKFLOW` (the gate's file name),
     `FIRST_VERSION`, `NOTES_START` and `VERSION_FILES`. Each
     `VERSION_FILES` regex captures exactly one version, e.g.
     `('pom.xml', r'<revision>([^<]*)</revision>')`. For Maven, use a
     CI-friendly `${revision}${changelist}` version with `changelist`
     defaulting to `-SNAPSHOT`, so only local builds carry it.
   - `release.yml`: set `workflows: [...]` to the gate's `name:` and the
     branch in `branches` and `ref`.
   - With artifacts, write `.github/workflows/build.yml` as a reusable
     workflow (`workflow_call` with a `ref` input) that checks out `ref`,
     builds, and uploads artifacts named `<prefix>-*` whose files are also
     named `<prefix>-*`. Publish attaches only those files and fails when
     none are found. Call it from the gate
     too, so PRs build the same way. Replace `<project>` in `release.yml`
     with the prefix.
   - Without artifacts, delete the `build` job, remove it from
     `publish.needs`, and delete the artifact download step and the empty
     assets check.
   - Make the gate run `python3 -m unittest discover -s scripts -p "test_*.py"`.
   - Add a README "Releases" section for maintainers, covering how to cut a
     release, how to recover one, and the repo rules below.

   Done when every invariant below still holds.
3. **Verify locally.** Done when all of these pass, with output shown:
   - `actionlint .github/workflows/*.yml`
   - `python3 -m unittest discover -s scripts -p "test_*.py"`
   - `git cliff --bumped-version` prints the expected next version, or with
     no tags yet, `git cliff <NOTES_START>..HEAD --tag <first> --strip all`
     prints the expected first notes.
4. **Verify the first release** after the PR merges. Done when the Release
   run has pushed the tag (and the `release:` commit with version files),
   the GitHub release has the notes and every artifact, and any Release run
   for a `release:` commit was skipped.

## Invariants

**Trigger**
- Release runs on `workflow_run` of the gate on the default branch, only
  when that run succeeded on a `push` and its head commit does not start
  with `release:`. Otherwise every release commit starts another release.
- `concurrency` sits on the `tag` job, not the workflow. A group holds one
  pending run, and skipped runs at workflow level take that slot and cancel
  a queued real release.
- Permissions stay at `contents: write` and `actions: read`.

**Script**
- It releases only the fetched head of the branch, and rechecks the gate
  for that SHA, because the triggering run may belong to an older commit.
  The drift test keeps the gate name in `release.yml` equal to the gate
  workflow's `name:`, because renaming the gate otherwise stops releases
  silently.
- Versions come only from `git cliff --bumped-version` (or `FIRST_VERSION`)
  and must pass the strict semver check. `cliff.toml` skips `release:`
  commits and its `tag_pattern` matches release tags only. For a `v` prefix,
  change `SEMVER`, the tag commands and `tag_pattern` together.
- The bot commits and tags as `github-actions[bot]` and pushes with
  `git push --atomic`, so the commit and tag land together or not at all.
- A tagged head without a published release is recovered under the same
  version, so rerunning a failed Release is always safe.

**Artifacts**
- A tag or release created with `GITHUB_TOKEN` does not trigger other
  workflows, so artifacts are built inside Release, at the new tag.
- Publishing comes last, so a failed build never leaves a release without
  downloads. A retry deletes a leftover draft and keeps its tag. Published
  assets include the version.

**Workflow hygiene**
- Fixed, sentence-case job names. GitHub shows a skipped job's `${{ }}`
  name as raw text, so the version goes in the run summary.
- Every step is named for what it does.
- git-cliff and the runner image are pinned. When installing, update each
  action to its current major version
  (`gh api repos/actions/<name>/releases/latest`), since older ones run on
  deprecated Node versions.

**Repo rules** (check them and report any conflict before installing)
- The bot pushes straight to the default branch, so rulesets requiring PRs
  or signed commits on that branch block it.
- Merge PRs with rebase merge so commit types survive and pick the bump.
- Never force-push the default branch. Rewriting a `release:` commit can
  leave its tag off the branch and block releases until fixed by hand.
- A push landing while a release publishes can start a second build and
  publish of the same version, and one of them may fail. Rerun Release if
  the GitHub release is then missing.
