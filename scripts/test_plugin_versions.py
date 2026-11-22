import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from plugin_versions import MANIFESTS, check_versions, set_version, validate_version


class VersionTests(unittest.TestCase):
    def test_valid_semver(self):
        for version in ('0.0.0', '0.2.0', '1.2.3', '10.20.30',
                        '1.0.0-alpha.0', '1.0.0-0A.x-y+001.build', '1.0.0+001'):
            with self.subTest(version=version):
                self.assertEqual(validate_version(version), version)

    def test_invalid_and_bypass_inputs(self):
        for version in (None, True, 123, 1.2, [], {}, '', 'v1.2.3', 'V1.2.3',
                        '1.2', '1', '1.2.3.4', '01.2.3', '1.02.3', '1.2.03',
                        '-1.2.3', '1.2.-3', ' 1.2.3', '1.2.3 ', '1.2.3\n',
                        '1.2.3\x00', '"1.2.3"', '１.2.3', '١.2.3', '1\u0301.2.3',
                        '1,2,3', '1x2x3', '123', '1.2.3-', '1.2.3+',
                        '1.2.3-01', '1.2.3-a..b', '1.2.3+a_b', '1.2.3+é'):
            with self.subTest(version=version), self.assertRaises(ValueError):
                validate_version(version)


class ManifestVersionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for relative in MANIFESTS:
            path = self.root / relative
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'name': 'xlm', 'version': '0.2.0',
                                        'description': 'Rules', 'agents': []}, indent=2) + '\n')

    def test_matching_versions(self):
        self.assertEqual(check_versions(self.root), '0.2.0')

    def test_invalid_or_missing_version_in_each_manifest(self):
        for relative in MANIFESTS:
            path = self.root / relative
            original = path.read_text()
            for value in (None, '0.3.0', 'v1.2.3', '1.2', 123, True):
                with self.subTest(path=relative, value=value):
                    manifest = json.loads(original)
                    if value is None:
                        del manifest['version']
                    else:
                        manifest['version'] = value
                    path.write_text(json.dumps(manifest))
                    with self.assertRaises(ValueError):
                        check_versions(self.root)
                    path.write_text(original)

    def test_writer_inserts_after_name_and_preserves_repo_format(self):
        for relative in MANIFESTS:
            path = self.root / relative
            path.write_text(path.read_text().replace('  "version": "0.2.0",\n', ''))
        set_version(self.root, '1.2.3')
        for relative in MANIFESTS:
            self.assertEqual((self.root / relative).read_text(),
                             '{\n  "name": "xlm",\n  "version": "1.2.3",\n'
                             '  "description": "Rules",\n  "agents": []\n}\n')
        self.assertEqual(check_versions(self.root), '1.2.3')

    def test_writer_updates_existing_version(self):
        before = [(self.root / path).read_text() for path in MANIFESTS]
        set_version(self.root, '0.3.0-rc.1+build')
        self.assertEqual(check_versions(self.root), '0.3.0-rc.1+build')
        self.assertEqual([text.replace('0.2.0', '0.3.0-rc.1+build') for text in before],
                         [(self.root / path).read_text() for path in MANIFESTS])

    def test_invalid_version_does_not_write(self):
        before = [(self.root / path).read_bytes() for path in MANIFESTS]
        with self.assertRaises(ValueError):
            set_version(self.root, 'v1.2.3')
        self.assertEqual(before, [(self.root / path).read_bytes() for path in MANIFESTS])

    def test_bad_manifest_does_not_partially_write(self):
        path = self.root / MANIFESTS[-1]
        for content in ('{', '[]', '{}', ''):
            with self.subTest(content=content):
                path.write_text(content)
                with self.assertRaises(ValueError):
                    set_version(self.root, '1.2.3')
                self.assertEqual(json.loads((self.root / MANIFESTS[0]).read_text())['version'], '0.2.0')
        path.unlink()
        with self.assertRaises(OSError):
            check_versions(self.root)

    def test_check_script_reports_success_and_failure(self):
        spec = importlib.util.spec_from_file_location(
            'version_checks', Path(__file__).with_name('check-plugins.py'))
        checks = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checks)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            checks.check_manifest_versions(self.root)
        self.assertIn('PASS: all four plugin versions agree (0.2.0)', output.getvalue())
        (self.root / MANIFESTS[0]).unlink()
        with self.assertRaisesRegex(SystemExit, 'manifest version drift'):
            checks.check_manifest_versions(self.root)

    def test_fast_flag_never_resolves_cli_binaries(self):
        spec = importlib.util.spec_from_file_location(
            'fast_checks', Path(__file__).with_name('check-plugins.py'))
        checks = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checks)
        with mock.patch('sys.argv', ['check-plugins.py', '--versions-only']), \
                mock.patch.object(checks, 'check_manifest_versions') as check, \
                mock.patch.object(checks, 'resolve_binary', side_effect=AssertionError):
            checks.main()
        check.assert_called_once()


if __name__ == '__main__':
    unittest.main()
