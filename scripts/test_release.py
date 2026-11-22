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
from release import BOT, GitHub, Release


class GitHubTests(unittest.TestCase):
    def setUp(self):
        self.run = mock.Mock()
        self.github = GitHub('xlm/dotagents', self.run)

    def check(self, **changes):
        return dict(id=1, name='check-plugins', head_sha='abc',
                    app={'slug': 'github-actions'}, status='completed',
                    conclusion='success', **changes)

    def test_successful_check(self):
        self.run.return_value = json.dumps({'check_runs': [self.check()]})
        self.assertTrue(self.github.checks_succeeded('abc'))
        self.run.assert_called_once_with([
            'gh', 'api', 'repos/xlm/dotagents/commits/abc/check-runs?per_page=100&page=1'])

    def test_missing_failed_pending_and_unrelated_checks(self):
        changes = [None, {'conclusion': 'failure'}, {'conclusion': 'cancelled'},
                   {'status': 'in_progress', 'conclusion': None},
                   {'name': 'check-plugins-other'}, {'name': 'Check-plugins'},
                   {'name': 'check-plugins\n'}, {'head_sha': 'other'},
                   {'app': {'slug': 'other'}}]
        for change in changes:
            with self.subTest(change=change):
                runs = [] if change is None else [{**self.check(), **change}]
                self.run.return_value = json.dumps({'check_runs': runs})
                self.assertFalse(self.github.checks_succeeded('abc'))

    def test_newer_failed_rerun_overrides_older_success(self):
        newer = {**self.check(), 'id': 2, 'conclusion': 'failure'}
        self.run.return_value = json.dumps({'check_runs': [newer, self.check()]})
        self.assertFalse(self.github.checks_succeeded('abc'))

    def test_pagination(self):
        unrelated = {**self.check(), 'name': 'other'}
        self.run.side_effect = [json.dumps({'check_runs': [unrelated] * 100}),
                                json.dumps({'check_runs': [self.check()]})]
        self.assertTrue(self.github.checks_succeeded('abc'))
        self.assertIn('page=2', self.run.call_args.args[0][-1])

    def test_existing_release(self):
        self.run.return_value = '{"tag_name": "0.3.0"}'
        self.assertTrue(self.github.release_exists('0.3.0'))

    def test_only_not_found_means_release_is_missing(self):
        self.run.side_effect = subprocess.CalledProcessError(1, 'gh', stderr='HTTP 404')
        self.assertFalse(self.github.release_exists('0.3.0'))
        for message in ('HTTP 403', 'HTTP 500', 'network failure'):
            with self.subTest(message=message):
                self.run.side_effect = subprocess.CalledProcessError(1, 'gh', stderr=message)
                with self.assertRaises(subprocess.CalledProcessError):
                    self.github.release_exists('0.3.0')

    def test_check_api_errors_propagate(self):
        self.run.side_effect = subprocess.CalledProcessError(1, 'gh', stderr='HTTP 403')
        with self.assertRaises(subprocess.CalledProcessError):
            self.github.checks_succeeded('abc')


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / 'work'
        self.remote = Path(directory.name) / 'remote.git'
        self.root.mkdir()
        self.env = {**os.environ, **BOT, 'GIT_CONFIG_NOSYSTEM': '1',
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
        self.github = mock.Mock()
        self.github.checks_succeeded.return_value = True
        self.github.release_exists.return_value = False
        self.notes = '## 0.3.0\n\n- New skill'
        self.commands = []
        self.published = []
        self.publish_error = False
        self.push_error = False
        self.bump = '0.3.0'
        self.release = Release(self.root, 'xlm/dotagents', run=self.run_command,
                               github=self.github)

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root, env=self.env,
                              check=True, capture_output=True, text=True).stdout.strip()

    def run_command(self, args):
        self.commands.append(args)
        if args[0] == 'git-cliff':
            return self.bump if '--bumped-version' in args else self.notes
        if args[:3] == ['gh', 'release', 'create']:
            if self.publish_error:
                raise subprocess.CalledProcessError(1, args, stderr='publication failed')
            path = Path(args[args.index('--notes-file') + 1])
            self.published.append((args[3], path.read_text(), args))
            self.github.release_exists.return_value = True
            return ''
        if args[:2] == ['git', 'push'] and self.push_error:
            raise subprocess.CalledProcessError(1, args, stderr='main moved')
        return self.release.command(args)

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
            self.release.release()
        return output.getvalue()

    def test_success_releases_checked_current_main(self):
        checked = self.change()
        self.assertIn('Published release 0.3.0.', self.execute())
        self.github.checks_succeeded.assert_called_once_with(checked)
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
        self.assertEqual(self.published[0][:2], ('0.3.0', self.notes + '\n'))
        self.assertIn('xlm/dotagents', self.published[0][2])

    def test_failed_publication_recovers_without_new_commit_or_push(self):
        self.change()
        self.publish_error = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.execute()
        head = self.git('rev-parse', 'HEAD')
        self.commands.clear()
        self.github.checks_succeeded.reset_mock()
        self.publish_error = False
        self.assertIn('Recovered GitHub release 0.3.0.', self.execute())
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        self.assertIn(['git-cliff', '--current', '--strip', 'all'], self.commands)
        self.assertEqual(self.published[0][:2], ('0.3.0', self.notes + '\n'))
        self.assertFalse(any(args[:2] == ['git', 'push'] for args in self.commands))
        self.github.checks_succeeded.assert_not_called()

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
        self.github.checks_succeeded.return_value = False
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
        self.github.checks_succeeded.assert_called_once_with(latest)
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
        with self.assertRaisesRegex(ValueError, 'not tagged'):
            self.execute()
        self.assertFalse(self.published)
        self.github.checks_succeeded.assert_not_called()

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
