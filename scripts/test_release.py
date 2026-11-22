import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from plugin_versions import MANIFESTS, check_versions
import release


class CommandTests(unittest.TestCase):
    def test_failed_command_prints_stderr_and_preserves_error(self):
        for stderr in ('remote: push rejected\n', '', None):
            error = subprocess.CalledProcessError(1, 'git', stderr=stderr)
            with self.subTest(stderr=stderr), mock.patch(
                    'release.subprocess.run', side_effect=error), mock.patch(
                    'release.sys.stderr', new_callable=io.StringIO) as output:
                with self.assertRaises(subprocess.CalledProcessError) as raised:
                    release.run('git', 'push')
                self.assertIs(raised.exception, error)
                self.assertEqual(output.getvalue(), stderr or '')

    def test_missing_release_detection_preserves_stderr(self):
        error = subprocess.CalledProcessError(1, 'gh', stderr='HTTP 404\n')
        with mock.patch('release.subprocess.run', side_effect=error), mock.patch(
                'release.sys.stderr', new_callable=io.StringIO) as output:
            self.assertFalse(release.release_exists('0.3.0'))
            self.assertEqual(output.getvalue(), 'HTTP 404\n')


class GitHubTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch('release.run', side_effect=self.query)
        self.run = patcher.start()
        self.addCleanup(patcher.stop)
        self.runs = []

    def query(self, *args):
        return subprocess.run(['jq', '-r', args[-1]],
                              input=json.dumps({'check_runs': self.runs}),
                              check=True, capture_output=True, text=True).stdout.strip()

    def check(self, **changes):
        return dict(id=1, name='check-plugins', head_sha='abc',
                    app={'slug': 'github-actions'}, status='completed',
                    conclusion='success', **changes)

    def test_successful_check(self):
        self.runs = [self.check()]
        self.assertTrue(release.checks_passed('abc'))
        self.run.assert_called_once()
        self.assertEqual(self.run.call_args.args[:4], (
            'gh', 'api', 'repos/{owner}/{repo}/commits/abc/check-runs'
            '?check_name=check-plugins&filter=latest', '--jq'))

    def test_missing_failed_pending_and_unrelated_checks(self):
        changes = [None, {'conclusion': 'failure'}, {'conclusion': 'cancelled'},
                   {'status': 'in_progress', 'conclusion': None},
                   {'name': 'check-plugins-other'}, {'name': 'Check-plugins'},
                   {'name': 'check-plugins\n'}, {'head_sha': 'other'},
                   {'app': {'slug': 'other'}}]
        for change in changes:
            with self.subTest(change=change):
                self.runs = [] if change is None else [{**self.check(), **change}]
                self.assertFalse(release.checks_passed('abc'))

    def test_newer_failed_rerun_overrides_older_success(self):
        newer = {**self.check(), 'id': 2, 'conclusion': 'failure'}
        self.runs = [newer, self.check()]
        self.assertFalse(release.checks_passed('abc'))
        self.runs.reverse()
        self.assertFalse(release.checks_passed('abc'))
        self.runs = [self.check(), {**newer, 'conclusion': 'success', 'id': 3}]
        self.assertTrue(release.checks_passed('abc'))

    def test_existing_release(self):
        self.run.side_effect = None
        self.run.return_value = ''
        self.assertTrue(release.release_exists('0.3.0'))
        self.run.assert_called_once_with('gh', 'release', 'view', '0.3.0')

    def test_only_not_found_means_release_is_missing(self):
        for message in ('HTTP 404', 'release not found'):
            with self.subTest(message=message):
                self.run.side_effect = subprocess.CalledProcessError(1, 'gh', stderr=message)
                self.assertFalse(release.release_exists('0.3.0'))
        for message in ('HTTP 403', 'HTTP 500', 'network failure'):
            with self.subTest(message=message):
                self.run.side_effect = subprocess.CalledProcessError(1, 'gh', stderr=message)
                with self.assertRaises(subprocess.CalledProcessError):
                    release.release_exists('0.3.0')

    def test_check_api_errors_propagate(self):
        self.run.side_effect = subprocess.CalledProcessError(1, 'gh', stderr='HTTP 403')
        with self.assertRaises(subprocess.CalledProcessError):
            release.checks_passed('abc')


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / 'work'
        self.remote = Path(directory.name) / 'remote.git'
        self.root.mkdir()
        self.env = {**os.environ, 'GIT_AUTHOR_NAME': 'fixture',
                    'GIT_AUTHOR_EMAIL': 'fixture@example.invalid',
                    'GIT_COMMITTER_NAME': 'fixture',
                    'GIT_COMMITTER_EMAIL': 'fixture@example.invalid',
                    'GIT_CONFIG_NOSYSTEM': '1',
                    'GIT_CONFIG_GLOBAL': os.devnull}
        self.git('init', '--bare', '--initial-branch=main', str(self.remote))
        self.git('init', '--initial-branch=main')
        self.git('remote', 'add', 'origin', str(self.remote))
        for relative in MANIFESTS:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'name': 'xlm', 'version': '0.2.0'}, indent=2) + '\n')
        scripts = self.root / 'scripts'
        scripts.mkdir()
        for name in ('check-plugins.py', 'plugin_versions.py'):
            shutil.copyfile(Path(__file__).with_name(name), scripts / name)
        self.git('add', *MANIFESTS, 'scripts/check-plugins.py', 'scripts/plugin_versions.py')
        self.git('commit', '-m', 'test: baseline')
        self.git('tag', '0.2.0')
        self.git('push', 'origin', 'HEAD:main', '0.2.0')
        self.checks_passed = mock.Mock(return_value=True)
        self.release_exists = mock.Mock(return_value=False)
        self.notes = '## 0.3.0\n\n- New skill'
        self.commands = []
        self.published = []
        self.publish_error = False
        self.push_error = False
        self.bump = '0.3.0'
        self.real_run = release.run
        for patcher in (mock.patch('release.ROOT', self.root),
                        mock.patch('release.run', side_effect=self.run_command),
                        mock.patch('release.checks_passed', self.checks_passed),
                        mock.patch('release.release_exists', self.release_exists)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root, env=self.env,
                              check=True, capture_output=True, text=True).stdout.strip()

    def run_command(self, *args, input=None):
        args = list(args)
        self.commands.append(args)
        if args[0] == 'git-cliff':
            return self.bump if '--bumped-version' in args else self.notes
        if args[:3] == ['gh', 'release', 'create']:
            if self.publish_error:
                raise subprocess.CalledProcessError(1, args, stderr='publication failed')
            self.published.append((args[3], input, args))
            self.release_exists.return_value = True
            return ''
        if args[:2] == ['git', 'push'] and self.push_error:
            raise subprocess.CalledProcessError(1, args, stderr='main moved')
        return self.real_run(*args, input=input)

    def change(self, message='feat: new skill'):
        self.git('checkout', 'main')
        marker = self.root / 'marker.txt'
        marker.write_text(message)
        self.git('add', 'marker.txt')
        self.git('commit', '-m', message)
        self.git('push', 'origin', 'HEAD:main')
        return self.git('rev-parse', 'HEAD')

    def execute(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            release.main()
        return output.getvalue()

    def test_success_releases_checked_current_main(self):
        checked = self.change()
        self.git('tag', 'unrelated')
        self.assertIn('Published release 0.3.0.', self.execute())
        self.checks_passed.assert_called_once_with(checked)
        self.assertEqual(check_versions(self.root), '0.3.0')
        self.assertEqual(self.git('show', '-s', '--format=%s'), 'release: 0.3.0')
        self.assertEqual(self.git('show', '-s', '--format=%an|%ae|%cn|%ce'),
                         'github-actions[bot]|'
                         '41898282+github-actions[bot]@users.noreply.github.com|'
                         'github-actions[bot]|'
                         '41898282+github-actions[bot]@users.noreply.github.com')
        head = self.git('rev-parse', 'HEAD')
        self.assertEqual(self.git('rev-parse', '0.3.0'), head)
        self.assertEqual(self.git('--git-dir=' + str(self.remote), 'rev-parse', 'main'), head)
        self.assertEqual(self.git('--git-dir=' + str(self.remote), 'rev-parse', '0.3.0'), head)
        self.assertIn(['git', 'push', '--atomic', 'origin', 'HEAD:main', '0.3.0'],
                      self.commands)
        self.assertEqual(self.published[0][:2], ('0.3.0', self.notes))
        self.assertEqual(self.published[0][2],
                         ['gh', 'release', 'create', '0.3.0', '--notes-file', '-'])

    def test_failed_publication_recovers_without_new_commit_or_push(self):
        self.change()
        self.publish_error = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.execute()
        head = self.git('rev-parse', 'HEAD')
        self.commands.clear()
        self.checks_passed.reset_mock()
        self.publish_error = False
        self.assertIn('Recovered GitHub release 0.3.0.', self.execute())
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        self.assertIn(['git-cliff', '--current', '--strip', 'all'], self.commands)
        self.assertEqual(self.published[0][:2], ('0.3.0', self.notes))
        self.assertFalse(any(args[:2] == ['git', 'push'] for args in self.commands))
        self.checks_passed.assert_not_called()

    def test_existing_release_is_noop(self):
        self.change()
        self.execute()
        head = self.git('rev-parse', 'HEAD')
        self.commands.clear()
        self.assertIn('Release 0.3.0 already exists.', self.execute())
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        self.assertEqual(len(self.published), 1)
        self.assertFalse(any(args[0] == 'git-cliff' for args in self.commands))

    def test_main_without_successful_check_is_noop(self):
        head = self.change()
        self.checks_passed.return_value = False
        self.assertIn('no successful Check plugins run', self.execute())
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        self.assertEqual(check_versions(self.root), '0.2.0')
        self.assertFalse(self.published)
        self.assertFalse(any(args[0] == 'git-cliff' for args in self.commands))

    def test_no_commits_since_tag_is_noop(self):
        self.assertIn('No commits since the last release.', self.execute())
        self.assertFalse(self.published)
        self.assertEqual(check_versions(self.root), '0.2.0')

    def test_old_checkout_releases_latest_checked_main(self):
        old = self.git('rev-parse', 'HEAD')
        latest = self.change()
        self.git('checkout', '--detach', old)
        self.execute()
        self.checks_passed.assert_called_once_with(latest)
        self.assertEqual(self.git('show', 'HEAD:marker.txt'), 'feat: new skill')

    def test_push_failure_does_not_publish(self):
        head = self.change()
        self.push_error = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.execute()
        self.assertEqual(self.git('--git-dir=' + str(self.remote), 'rev-parse', 'main'), head)
        self.assertFalse(self.published)

    def test_invalid_bump_does_not_change_manifests(self):
        self.change()
        self.bump = 'v0.3.0'
        with self.assertRaises(ValueError):
            self.execute()
        self.assertEqual(check_versions(self.root), '0.2.0')
        self.assertFalse(self.published)

    def test_release_commit_requires_matching_tag(self):
        self.change('release: 0.3.0')
        with self.assertRaisesRegex(SystemExit, 'not tagged'):
            self.execute()
        self.assertFalse(self.published)
        self.checks_passed.assert_not_called()

    def test_malformed_release_subject_cannot_bypass_checks(self):
        for message in ('release:v0.3.0', 'release: v0.3.0', 'release: 0.3',
                        'release: ０.3.0', 'release: 0.3.0 extra'):
            with self.subTest(message=message):
                self.change(message)
                with self.assertRaises(ValueError):
                    self.execute()
        self.assertFalse(self.published)


if __name__ == '__main__':
    unittest.main()
