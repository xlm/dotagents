import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import yaml


spec = importlib.util.spec_from_file_location(
    'check_plugins', Path(__file__).with_name('check-plugins.py'),
)
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


class WithoutSyncedSkillsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.synced = self.root / 'agents/.agents/skills/synced'

    def add_skill(self, path, name):
        skill = self.synced / path / 'SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text(f'---\nname: {name}\ndescription: Local skill.\n---\n')
        return skill

    def test_absent_synced_directory_preserves_inventory(self):
        actual = {'xlm:owned', 'xlm:unexpected'}
        self.assertEqual(checks.without_synced_skills(self.root, actual, {'xlm:owned'}), actual)

    def test_empty_synced_directory_preserves_inventory(self):
        self.synced.mkdir(parents=True)
        self.assertEqual(checks.without_synced_skills(self.root, set(), set()), set())

    def test_nested_synced_skill_uses_frontmatter_name(self):
        self.add_skill('source/folder-name', 'synced-name')
        actual = {'xlm:owned', 'xlm:synced-name', 'xlm:unexpected'}
        self.assertEqual(
            checks.without_synced_skills(self.root, actual, {'xlm:owned'}),
            {'xlm:owned', 'xlm:unexpected'},
        )

    def test_synced_collision_preserves_expected_name(self):
        self.add_skill('collision', 'owned')
        self.assertEqual(
            checks.without_synced_skills(self.root, {'xlm:owned'}, {'xlm:owned'}),
            {'xlm:owned'},
        )

    def test_synced_skill_cannot_fill_missing_expected_name(self):
        self.add_skill('other', 'other')
        self.assertEqual(
            checks.without_synced_skills(self.root, {'xlm:other'}, {'xlm:owned'}),
            set(),
        )

    def test_malformed_synced_metadata_fails_closed(self):
        skill = self.add_skill('invalid', 'invalid')
        skill.write_text('---\nname: [\n---\n')
        with self.assertRaises(yaml.YAMLError):
            checks.without_synced_skills(self.root, {'xlm:invalid'}, set())


class CopilotSkillNamesTests(unittest.TestCase):
    def test_plugin_names_preserve_punctuation_and_digits(self):
        self.assertEqual(
            checks.copilot_skill_names(
                'Plugin skills:\n  nextjs16 - Description.\n  code-review - More - detail.\n'
            ),
            {'nextjs16', 'code-review'},
        )

    def test_other_sections_and_description_mentions_are_ignored(self):
        output = ('Personal skills:\n  personal - Plugin skills:\n\n'
                  'Plugin skills:\n  owned - Description.\n\n'
                  'Builtin skills:\n  builtin - Description.\n')
        self.assertEqual(checks.copilot_skill_names(output), {'owned'})

    def test_empty_or_missing_section(self):
        for output in ('', 'Plugin skills:\n\n', 'Builtin skills:\n  other - Other.\n'):
            with self.subTest(output=output):
                self.assertEqual(checks.copilot_skill_names(output), set())

    def test_heading_must_match_exactly(self):
        cases = {
            'wrong capitalization': 'plugin skills:',
            'missing colon': 'Plugin skills',
            'indented heading': '  Plugin skills:',
        }
        for case, heading in cases.items():
            with self.subTest(case=case, heading=heading):
                self.assertEqual(
                    checks.copilot_skill_names(heading + '\n  other - Other.\n'), set(),
                )

    def test_malformed_entry_is_rejected(self):
        cases = {
            'missing separator': 'missing-separator',
            'missing description': 'name - ',
            'missing name': ' - Description.',
            'missing spaces around separator': 'name-Description.',
        }
        for case, entry in cases.items():
            with self.subTest(case=case, entry=entry), self.assertRaises(ValueError):
                checks.copilot_skill_names('Plugin skills:\n  ' + entry + '\n')


class PromptSkillNamesTests(unittest.TestCase):
    def test_names_keep_digits_and_hyphens(self):
        prompt = '- xlm:code-review: Review.\n- xlm:nextjs16 (file: x)\n'
        self.assertEqual(
            checks.prompt_skill_names(prompt), {'xlm:code-review', 'xlm:nextjs16'},
        )

    def test_other_namespaces_are_ignored(self):
        self.assertEqual(checks.prompt_skill_names('other:skill xlmx:no'), set())


class SessionContextTests(unittest.TestCase):
    def output(self, **hook_output):
        return json.dumps({'hookSpecificOutput': hook_output})

    def test_session_start_context_is_returned(self):
        output = self.output(hookEventName='SessionStart', additionalContext='# Rules\n')
        self.assertEqual(checks.session_context(output), '# Rules\n')

    def test_plain_text_and_invalid_json_are_rejected(self):
        for output in ('# Rules\n', '{"hookSpecificOutput": ', ''):
            self.assertIsNone(checks.session_context(output), output)

    def test_other_shapes_are_rejected(self):
        for output in (
            json.dumps({'additionalContext': '# Rules'}),
            json.dumps({'additional_context': '# Rules'}),
            json.dumps(['# Rules']),
            json.dumps({'hookSpecificOutput': '# Rules'}),
        ):
            self.assertIsNone(checks.session_context(output), output)

    def test_wrong_event_or_context_type_is_rejected(self):
        for output in (
            self.output(hookEventName='UserPromptSubmit', additionalContext='# Rules'),
            self.output(additionalContext='# Rules'),
            self.output(hookEventName='SessionStart'),
            self.output(hookEventName='SessionStart', additionalContext=['# Rules']),
            self.output(hookEventName='SessionStart', additionalContext=None),
        ):
            self.assertIsNone(checks.session_context(output), output)


class CursorHookTests(unittest.TestCase):
    def run_hook(self, result, manifest=None):
        """Run cursor_hook on a fake plugin, with the hook command replaced by `result`."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.cursor-plugin').mkdir()
            (root / 'hooks').mkdir()
            (root / 'AGENTS.md').write_text('# Rules\n')
            (root / '.cursor-plugin/plugin.json').write_text(json.dumps(manifest or {}))
            hook = {'type': 'command', 'command': 'print rules'}
            (root / 'hooks/hooks.json').write_text(
                json.dumps({'hooks': {'SessionStart': [{'hooks': [hook]}]}}))
            effect = result if isinstance(result, Exception) else None
            with mock.patch.object(checks.subprocess, 'run', side_effect=effect,
                                   return_value=result) as run, \
                    contextlib.redirect_stdout(io.StringIO()):
                checks.cursor_hook(root, root)
            return run, root

    def reply(self, stdout, returncode=0):
        return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr='')

    def context(self, text):
        return json.dumps({'hookSpecificOutput': {
            'hookEventName': 'SessionStart', 'additionalContext': text}})

    def test_rules_from_cursor_root_pass(self):
        run, root = self.run_hook(self.reply(self.context('Global rules:\n\n# Rules\n')))
        self.assertEqual(run.call_args.args[0], ['bash', '-c', 'print rules'])
        env = run.call_args.kwargs['env']
        self.assertEqual(env['CURSOR_PLUGIN_ROOT'], str(root))
        self.assertNotIn('CLAUDE_PLUGIN_ROOT', env)
        self.assertNotIn('PLUGIN_ROOT', env)

    def test_own_hooks_field_fails(self):
        with self.assertRaisesRegex(SystemExit, 'own hooks'):
            self.run_hook(self.reply(self.context('# Rules\n')), {'hooks': './hooks.json'})

    def test_bad_hook_results_fail(self):
        for result in (
            self.reply('# Rules\n'),
            self.reply(self.context('# Rules\n'), returncode=1),
            self.reply(self.context('# Other rules\n')),
            self.reply(''),
        ):
            with self.subTest(result=result):
                with self.assertRaisesRegex(SystemExit, 'CURSOR_PLUGIN_ROOT'):
                    self.run_hook(result)

    def test_execution_errors_fail(self):
        for error in (OSError('no bash'), subprocess.TimeoutExpired('bash', 30)):
            with self.subTest(error=error):
                with self.assertRaisesRegex(SystemExit, 'Cursor hook: '):
                    self.run_hook(error)


if __name__ == '__main__':
    unittest.main()
