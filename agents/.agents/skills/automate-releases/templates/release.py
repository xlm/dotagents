#!/usr/bin/env python3
"""Tag gated releases and prepare notes for a separate publishing job."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlencode, quote

BRANCH = 'main'  # Branch to release.
GATE_WORKFLOW = 'ci.yml'  # File name of the gating workflow.
FIRST_VERSION = '0.1.0'  # Version when no release tags exist.
NOTES_START = None  # Tag or commit to exclude from first notes, or all history.
VERSION_FILES = []  # (path, regex) pairs, each with one version capture group.

ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / 'release-notes.md'
SEMVER = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)')
BOT_NAME = 'github-actions[bot]'
BOT_EMAIL = '41898282+github-actions[bot]@users.noreply.github.com'


def validate_version(version):
    """Accept only three bare, ASCII numeric components without leading zeros."""
    if not SEMVER.fullmatch(version):
        raise ValueError(f'Invalid release version: {version!r}')
    return version


def run(*args):
    """Run a command as the release bot and return its output."""
    env = {**os.environ,
           'GIT_AUTHOR_NAME': BOT_NAME, 'GIT_AUTHOR_EMAIL': BOT_EMAIL,
           'GIT_COMMITTER_NAME': BOT_NAME, 'GIT_COMMITTER_EMAIL': BOT_EMAIL}
    try:
        return subprocess.run(args, cwd=ROOT, env=env, check=True,
                              capture_output=True, text=True).stdout.strip()
    except subprocess.CalledProcessError as error:
        if error.stderr:
            print(error.stderr, file=sys.stderr, end='')
        raise


def checks_passed(sha):
    """Require the newest push run for this exact branch and SHA to succeed."""
    query = urlencode({'branch': BRANCH, 'event': 'push', 'head_sha': sha,
                       'per_page': 100})
    endpoint = ('repos/{owner}/{repo}/actions/workflows/'
                f'{quote(GATE_WORKFLOW, safe="")}/runs?{query}')
    runs = json.loads(run('gh', 'api', endpoint))['workflow_runs']
    matching = [item for item in runs if item['head_sha'] == sha
                and item['head_branch'] == BRANCH and item['event'] == 'push']
    latest = max(matching, key=lambda item: item['id'], default={})
    return latest.get('status') == 'completed' and latest.get('conclusion') == 'success'


def release_exists(version):
    """Return whether this version has a published release, not a draft."""
    try:
        return run('gh', 'release', 'view', version, '--json', 'isDraft',
                   '--jq', '.isDraft') == 'false'
    except subprocess.CalledProcessError as error:
        if not any(message in (error.stderr or '')
                   for message in ('release not found', 'HTTP 404')):
            raise
        return False


def output(version, notes):
    """Save notes and pass the version to downstream jobs only after success."""
    NOTES.write_text(notes + '\n', encoding='utf-8')
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
        stream.write(f'version={version}\n')
    print(f'Prepared release {version}.')


def update_versions(version):
    """Replace only the captured version bytes, validating all files first."""
    updates = {}
    for path, pattern in VERSION_FILES:
        regex = re.compile(pattern.encode('utf-8'))
        if regex.groups != 1:
            raise ValueError(f'Expected one version capture group for {path}')
        file = ROOT / path
        before = updates.get(file, file.read_bytes())
        matches = list(regex.finditer(before))
        if len(matches) != 1 or matches[0].start(1) < 0:
            raise ValueError(f'Expected one version match in {path}')
        start, end = matches[0].span(1)
        updates[file] = before[:start] + version.encode('ascii') + before[end:]
    changed = []
    for file, after in updates.items():
        if file.read_bytes() != after:
            file.write_bytes(after)
            changed.append(str(file.relative_to(ROOT)))
    return changed


def main():
    """Release the latest branch head or recover a tagged, unpublished release."""
    run('git', 'fetch', 'origin', BRANCH, '--tags')
    run('git', 'checkout', '--detach', f'origin/{BRANCH}')
    tags = [tag for tag in run('git', 'tag', '--merged', 'HEAD',
                              '--sort=-version:refname').splitlines()
            if SEMVER.fullmatch(tag)]
    head_tags = run('git', 'tag', '--points-at', 'HEAD').splitlines()
    for index, tag in enumerate(tags):
        if tag in head_tags:
            if release_exists(tag):
                print(f'Release {tag} already exists.')
                return
            previous = tags[index + 1] if index + 1 < len(tags) else NOTES_START
            history = [f'{previous}..HEAD'] if previous else []
            output(tag, run('git-cliff', *history, '--strip', 'all'))
            return
    if not checks_passed(run('git', 'rev-parse', 'HEAD')):
        print(f'The latest {GATE_WORKFLOW} push run for {BRANCH} has not passed. Nothing to release.')
        return
    if tags and run('git', 'rev-list', '--count', f'{tags[0]}..HEAD') == '0':
        print('No commits since the last release.')
        return
    if tags:
        version = validate_version(run('git-cliff', '--bumped-version'))
        notes = run('git-cliff', '--unreleased', '--bump', '--strip', 'all')
    else:
        version = validate_version(FIRST_VERSION)
        history = [f'{NOTES_START}..HEAD'] if NOTES_START else []
        notes = run('git-cliff', *history, '--tag', version, '--strip', 'all')
    changed = update_versions(version)
    if changed:
        run('git', 'add', '--', *changed)
        run('git', 'commit', '-m', f'release: {version}')
    run('git', 'tag', version)
    run('git', 'push', '--atomic', 'origin', f'HEAD:{BRANCH}', version)
    output(version, notes)


if __name__ == '__main__':
    main()
