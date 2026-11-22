#!/usr/bin/env python3
"""Release the current head of main after Check plugins passes.

If main ends in a tagged release commit, recover its missing GitHub release.
Otherwise, if main's checks passed and commits exist since the last tag,
bump all four manifests, commit, tag, push, and publish.
"""

import os
from pathlib import Path
import subprocess
import sys

from plugin_versions import MANIFESTS, set_version, validate_version

ROOT = Path(__file__).resolve().parent.parent
BOT_NAME = 'github-actions[bot]'
BOT_EMAIL = '41898282+github-actions[bot]@users.noreply.github.com'


def run(*args, input=None):
    """Run a command in the repo as the bot and return its stdout."""
    env = {**os.environ,
           'GIT_AUTHOR_NAME': BOT_NAME, 'GIT_AUTHOR_EMAIL': BOT_EMAIL,
           'GIT_COMMITTER_NAME': BOT_NAME, 'GIT_COMMITTER_EMAIL': BOT_EMAIL}
    try:
        result = subprocess.run(args, cwd=ROOT, env=env, input=input,
                                check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        if error.stderr:
            print(error.stderr, file=sys.stderr, end='')
        raise
    return result.stdout.strip()


def checks_passed(sha):
    """True if the newest GitHub Actions check-plugins run succeeded."""
    return run('gh', 'api', f'repos/{{owner}}/{{repo}}/commits/{sha}/check-runs'
               '?check_name=check-plugins&filter=latest', '--jq',
               '[.check_runs[] | select(.name == "check-plugins" and '
               f'.head_sha == "{sha}" and .app.slug == "github-actions")] '
               '| max_by(.id) | .status == "completed" and .conclusion == "success"') == 'true'


def release_exists(version):
    try:
        run('gh', 'release', 'view', version)
        return True
    except subprocess.CalledProcessError as error:
        if not any(message in (error.stderr or '')
                   for message in ('release not found', 'HTTP 404')):
            raise
        return False


def publish(version, notes):
    run('gh', 'release', 'create', version, '--notes-file', '-', input=notes)


def recover(version):
    if version not in run('git', 'tag', '--points-at', 'HEAD').splitlines():
        sys.exit(f'FAIL: release commit is not tagged {version}')
    if release_exists(version):
        print(f'Release {version} already exists.')
        return
    publish(version, run('git-cliff', '--current', '--strip', 'all'))
    print(f'Recovered GitHub release {version}.')


def release_new():
    last_tag = run('git', 'describe', '--tags', '--abbrev=0', '--match', '[0-9]*.[0-9]*.[0-9]*')
    if run('git', 'rev-list', '--count', f'{last_tag}..HEAD') == '0':
        print('No commits since the last release.')
        return
    version = validate_version(run('git-cliff', '--bumped-version'))
    notes = run('git-cliff', '--unreleased', '--bump', '--strip', 'all')
    set_version(ROOT, version)
    run(sys.executable, 'scripts/check-plugins.py', '--versions-only')
    run('git', 'add', *MANIFESTS)
    run('git', 'commit', '-m', f'release: {version}')
    run('git', 'tag', version)
    run('git', 'push', '--atomic', 'origin', 'HEAD:main', version)
    publish(version, notes)
    print(f'Published release {version}.')


def main():
    run('git', 'fetch', 'origin', 'main', '--tags')
    run('git', 'checkout', '--detach', 'origin/main')
    subject = run('git', 'show', '-s', '--format=%s')
    if subject.startswith('release:'):
        recover(validate_version(subject.removeprefix('release: ')))
    elif checks_passed(run('git', 'rev-parse', 'HEAD')):
        release_new()
    else:
        print('Main has no successful Check plugins run. Nothing to release.')


if __name__ == '__main__':
    main()
