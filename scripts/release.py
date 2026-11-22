#!/usr/bin/env python3
"""Publish current main only after its checks pass, or recover a tagged release."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from plugin_versions import MANIFESTS, set_version, validate_version


BOT = {
    'GIT_AUTHOR_NAME': 'github-actions[bot]',
    'GIT_AUTHOR_EMAIL': '41898283+github-actions[bot]@users.noreply.github.com',
    'GIT_COMMITTER_NAME': 'github-actions[bot]',
    'GIT_COMMITTER_EMAIL': '41898283+github-actions[bot]@users.noreply.github.com',
}


class GitHub:
    def __init__(self, repository, run):
        self.repository = repository
        self.run = run

    def api(self, path):
        return json.loads(self.run(['gh', 'api', f'repos/{self.repository}/{path}']))

    def checks_succeeded(self, sha):
        runs = []
        page = 1
        while True:
            batch = self.api(f'commits/{sha}/check-runs?per_page=100&page={page}')['check_runs']
            runs.extend(run for run in batch
                        if run['name'] == 'check-plugins'
                        and run['head_sha'] == sha
                        and run['app']['slug'] == 'github-actions')
            if len(batch) < 100:
                break
            page += 1
        if not runs:
            return False
        latest = max(runs, key=lambda run: run['id'])
        return latest['status'] == 'completed' and latest['conclusion'] == 'success'

    def release_exists(self, version):
        try:
            self.api(f'releases/tags/{version}')
        except subprocess.CalledProcessError as error:
            if 'HTTP 404' not in (error.stderr or ''):
                raise
            return False
        return True


class Release:
    def __init__(self, root, repository, run=None, github=None):
        self.root = Path(root)
        self.run = run or self.command
        self.github = github or GitHub(repository, self.run)
        self.repository = repository

    def command(self, args):
        result = subprocess.run(args, cwd=self.root, env={**os.environ, **BOT},
                                check=True, capture_output=True, text=True)
        return result.stdout.strip()

    def git(self, *args):
        return self.run(['git', *args])

    def publish(self, version, notes):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'release-notes.md'
            path.write_text(notes + '\n')
            self.run(['gh', 'release', 'create', version, '--repo', self.repository,
                      '--notes-file', str(path)])

    def release(self):
        self.git('fetch', 'origin', 'main', '--tags')
        self.git('checkout', '--detach', 'origin/main')
        sha = self.git('rev-parse', 'HEAD')
        message = self.git('show', '-s', '--format=%s', 'HEAD')
        if message.startswith('release:'):
            version = validate_version(message.removeprefix('release: '))
            if version not in self.git('tag', '--points-at', 'HEAD').splitlines():
                raise ValueError('release commit is not tagged with its version')
            if self.github.release_exists(version):
                print(f'Release {version} already exists.')
                return
            notes = self.run(['git-cliff', '--current', '--strip', 'all'])
            self.publish(version, notes)
            print(f'Recovered GitHub release {version}.')
            return

        if not self.github.checks_succeeded(sha):
            print('Current main has no successful Check plugins run. Nothing to release.')
            return
        latest = self.git('describe', '--tags', '--abbrev=0', '--match', '[0-9]*.[0-9]*.[0-9]*')
        if self.git('rev-list', '--count', f'{latest}..HEAD') == '0':
            print('No commits since the last release.')
            return
        version = validate_version(self.run(['git-cliff', '--bumped-version']))
        notes = self.run(['git-cliff', '--unreleased', '--bump', '--strip', 'all'])
        set_version(self.root, version)
        self.run([sys.executable, str(self.root / 'scripts/check-plugins.py'), '--versions-only'])
        self.git('add', *MANIFESTS)
        self.git('commit', '-m', f'release: {version}')
        self.git('tag', version)
        self.git('push', '--atomic', 'origin', 'HEAD:main', version)
        self.publish(version, notes)
        print(f'Published release {version}.')


def main():
    try:
        Release(Path(__file__).resolve().parent.parent,
                os.environ['GITHUB_REPOSITORY']).release()
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError) as error:
        detail = error.stderr if isinstance(error, subprocess.CalledProcessError) else str(error)
        sys.exit(f'FAIL: {detail}')


if __name__ == '__main__':
    main()
