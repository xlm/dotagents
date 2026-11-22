"""External-free release tests. Install alongside release.py in scripts/."""

import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest import mock

import release


class VersionTests(unittest.TestCase):
    def test_strict_versions(self):
        for value in ('0.0.0', '1.2.3', '12.34.56'):
            with self.subTest(valid=value):
                self.assertEqual(release.validate_version(value), value)
        cases = {'empty': '', 'prefix': 'v1.0.0', 'leading zero': '01.0.0',
                 'minor zero': '1.00.0', 'patch zero': '1.0.00', 'missing': '1.0',
                 'newline': '1.0.0\n', 'unicode': '１.0.0', 'negative': '-1.0.0',
                 'suffix': '1.0.0-beta', 'metadata': '1.0.0+build',
                 'space': ' 1.0.0', 'separator': '1x0x0', 'quote': '"1.0.0"'}
        for case, value in cases.items():
            with self.subTest(case=case), self.assertRaises(ValueError):
                release.validate_version(value)


class GateTests(unittest.TestCase):
    def test_newest_matching_push_run(self):
        success = dict(id=1, head_sha='abc', head_branch=release.BRANCH,
                       event='push', status='completed', conclusion='success')
        cases = {'success': ([success], True), 'missing': ([], False),
                 'failed': ([dict(success, conclusion='failure')], False),
                 'pending': ([dict(success, status='in_progress')], False),
                 'other SHA': ([dict(success, head_sha='def')], False),
                 'other branch': ([dict(success, head_branch='other')], False),
                 'other event': ([dict(success, event='pull_request')], False),
                 'newest failed': ([success, dict(success, id=2, conclusion='failure')], False),
                 'newest success': ([dict(success, id=0, conclusion='failure'), success], True)}
        for case, (runs, expected) in cases.items():
            with self.subTest(case=case), mock.patch.object(
                    release, 'run', return_value=json.dumps({'workflow_runs': runs})) as command:
                self.assertEqual(release.checks_passed('abc'), expected)
                endpoint = command.call_args.args[2]
                self.assertIn(f'/workflows/{release.GATE_WORKFLOW}/runs?', endpoint)
                self.assertIn('event=push&head_sha=abc', endpoint)

    def test_workflow_gate_name_does_not_drift(self):
        workflows = Path(__file__).resolve().parent.parent / '.github/workflows'
        trigger = re.search(r'^\s+workflows:\s*\[([^\]]+)\]',
                            (workflows / 'release.yml').read_text(), re.M)
        name = re.search(r'^name:\s*(.+)$',
                         (workflows / release.GATE_WORKFLOW).read_text(), re.M)
        self.assertIsNotNone(trigger)
        self.assertIsNotNone(name)
        self.assertEqual(trigger[1].strip().strip('\'"'), name[1].strip().strip('\'"'))


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.file = self.root / 'version.txt'
        self.original = b'prefix\r\nversion=0.0.0\r\n\xffsuffix\n'
        self.file.write_bytes(self.original)
        self.tags = self.head_tags = ''
        self.gate = True
        self.count = '1'
        self.bump = '0.2.0'
        self.published = True
        self.commands = []
        self.fail = None
        for patcher in (mock.patch.object(release, 'ROOT', self.root),
                        mock.patch.object(release, 'NOTES', self.root / 'notes'),
                        mock.patch.object(release, 'VERSION_FILES', []),
                        mock.patch.object(release, 'NOTES_START', None),
                        mock.patch.dict(os.environ, {'GITHUB_OUTPUT': str(self.root / 'output')}),
                        mock.patch.object(release, 'checks_passed', side_effect=lambda sha: self.gate),
                        mock.patch.object(release, 'release_exists', side_effect=lambda tag: self.published),
                        mock.patch.object(release, 'run', side_effect=self.command)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def command(self, *args):
        self.commands.append(args)
        if self.fail and args[:len(self.fail)] == self.fail:
            raise subprocess.CalledProcessError(1, args)
        if args[:3] == ('git', 'tag', '--merged'):
            return self.tags
        if args[:3] == ('git', 'tag', '--points-at'):
            return self.head_tags
        if args[:2] == ('git', 'rev-parse'):
            return 'abc'
        if args[:2] == ('git', 'rev-list'):
            return self.count
        if args[:2] == ('git-cliff', '--bumped-version'):
            return self.bump
        return '## Notes' if args[0] == 'git-cliff' else ''

    def output(self):
        file = self.root / 'output'
        return file.read_text() if file.exists() else ''

    def test_first_release(self):
        self.tags = 'v9.0.0\noriginal'
        release.main()
        self.assertEqual(self.commands[:2], [
            ('git', 'fetch', 'origin', release.BRANCH, '--tags'),
            ('git', 'checkout', '--detach', f'origin/{release.BRANCH}')])
        self.assertIn(('git-cliff', '--tag', '0.1.0', '--strip', 'all'), self.commands)
        self.assertIn(('git', 'push', '--atomic', 'origin', f'HEAD:{release.BRANCH}', '0.1.0'), self.commands)
        self.assertEqual(self.output(), 'version=0.1.0\n')
        self.assertEqual((self.root / 'notes').read_text(), '## Notes\n')
        self.assertFalse(any(cmd[:2] == ('git', 'commit') for cmd in self.commands))

    def test_first_notes_start(self):
        with mock.patch.object(release, 'NOTES_START', 'original'):
            release.main()
        self.assertIn(('git-cliff', 'original..HEAD', '--tag', '0.1.0', '--strip', 'all'), self.commands)

    def test_next_release_with_optional_version_files(self):
        for case, files, initial, committed in (
                ('tag only', [], self.original, False),
                ('changed', [('version.txt', r'version=([^\r\n]*)')], self.original, True),
                ('unchanged', [('version.txt', r'version=([^\r\n]*)')],
                 self.original.replace(b'0.0.0', b'0.2.0'), False)):
            with self.subTest(case=case), mock.patch.object(release, 'VERSION_FILES', files):
                self.file.write_bytes(initial)
                self.commands.clear()
                self.tags = '0.1.0'
                release.main()
                self.assertEqual(('git', 'commit', '-m', 'release: 0.2.0') in self.commands, committed)
                self.assertIn(('git', 'tag', '0.2.0'), self.commands)
                if files:
                    self.assertEqual(self.file.read_bytes(), self.original.replace(b'0.0.0', b'0.2.0'))

    def test_version_file_validation(self):
        cases = {'zero matches': (b'none', r'version=([^\r\n]*)'),
                 'two matches': (b'version=1\nversion=2', r'version=([^\r\n]*)'),
                 'no group': (b'version=1', r'version=.*'),
                 'two groups': (b'version=1', r'(version)=(.*)'),
                 'unmatched group': (b'version=', r'version=(1)?')}
        for case, (content, pattern) in cases.items():
            with self.subTest(case=case), mock.patch.object(
                    release, 'VERSION_FILES', [('version.txt', pattern)]):
                self.file.write_bytes(content)
                with self.assertRaises(ValueError):
                    release.update_versions('1.0.0')
                self.assertEqual(self.file.read_bytes(), content)

    def test_all_files_validated_before_writing(self):
        (self.root / 'other.txt').write_bytes(b'missing')
        files = [('version.txt', r'version=([^\r\n]*)'), ('other.txt', r'version=(.*)')]
        with mock.patch.object(release, 'VERSION_FILES', files), self.assertRaises(ValueError):
            release.update_versions('1.0.0')
        self.assertEqual(self.file.read_bytes(), self.original)

    def test_invalid_first_version(self):
        with mock.patch.object(release, 'FIRST_VERSION', 'v1.0.0'), self.assertRaises(ValueError):
            release.main()
        self.assertEqual(self.output(), '')

    def test_gate_lookup_failure(self):
        error = subprocess.CalledProcessError(1, 'gh')
        with mock.patch.object(release, 'checks_passed', side_effect=error):
            with self.assertRaises(subprocess.CalledProcessError):
                release.main()
        self.assertEqual(self.output(), '')

    def test_recovery(self):
        cases = {'first all history': ('0.1.0', None, ()),
                 'first baseline': ('0.1.0', 'original', ('original..HEAD',)),
                 'later': ('0.2.0\n0.1.0', None, ('0.1.0..HEAD',))}
        for case, (tags, baseline, history) in cases.items():
            with self.subTest(case=case), mock.patch.object(release, 'NOTES_START', baseline):
                self.commands.clear()
                self.tags = tags
                self.head_tags = tags.splitlines()[0]
                self.published = False
                release.main()
                self.assertIn(('git-cliff', *history, '--strip', 'all'), self.commands)
                self.assertFalse(any(cmd[:2] in (('git', 'push'), ('git', 'commit')) for cmd in self.commands))

    def test_stop_conditions(self):
        for case in ('published', 'gate failed', 'no commits'):
            with self.subTest(case=case):
                self.commands.clear()
                self.tags = '0.1.0'
                self.head_tags = '0.1.0' if case == 'published' else ''
                self.gate = case != 'gate failed'
                self.count = '0'
                release.main()
                self.assertEqual(self.output(), '')
                self.assertFalse(any(cmd[0] == 'git-cliff' for cmd in self.commands))

    def test_failures_do_not_output_a_version(self):
        for case, command in {'notes': ('git-cliff',), 'push': ('git', 'push')}.items():
            with self.subTest(case=case):
                self.fail = command
                with self.assertRaises(subprocess.CalledProcessError):
                    release.main()
                self.assertEqual(self.output(), '')

    def test_invalid_version_does_not_edit_files(self):
        self.tags = '0.1.0'
        self.bump = 'v1.0.0'
        with self.assertRaises(ValueError):
            release.main()
        self.assertEqual(self.file.read_bytes(), self.original)


class CommandTests(unittest.TestCase):
    def test_stderr_printed_before_reraise(self):
        for stderr in ('remote: push rejected\n', '', None):
            error = subprocess.CalledProcessError(1, 'git', stderr=stderr)
            with self.subTest(stderr=stderr), mock.patch(
                    'release.subprocess.run', side_effect=error), mock.patch(
                    'release.sys.stderr', new_callable=io.StringIO) as output:
                with self.assertRaises(subprocess.CalledProcessError) as raised:
                    release.run('git', 'push')
                self.assertIs(raised.exception, error)
                self.assertEqual(output.getvalue(), stderr or '')

    @mock.patch('release.subprocess.run')
    def test_bot_identity(self, command):
        command.return_value.stdout = ' value\n'
        self.assertEqual(release.run('git', 'status'), 'value')
        for role in ('AUTHOR', 'COMMITTER'):
            self.assertEqual(command.call_args.kwargs['env'][f'GIT_{role}_NAME'], release.BOT_NAME)
            self.assertEqual(command.call_args.kwargs['env'][f'GIT_{role}_EMAIL'], release.BOT_EMAIL)

    def test_release_lookup(self):
        for case, response, expected in (('published', 'false', True), ('draft', 'true', False)):
            with self.subTest(case=case), mock.patch.object(release, 'run', return_value=response):
                self.assertEqual(release.release_exists('0.1.0'), expected)
        for message in ('release not found', 'HTTP 404', 'HTTP 403', 'network failure'):
            error = subprocess.CalledProcessError(1, 'gh', stderr=message)
            with self.subTest(message=message), mock.patch.object(release, 'run', side_effect=error):
                if message in ('release not found', 'HTTP 404'):
                    self.assertFalse(release.release_exists('0.1.0'))
                else:
                    with self.assertRaises(subprocess.CalledProcessError):
                        release.release_exists('0.1.0')


if __name__ == '__main__':
    unittest.main()
