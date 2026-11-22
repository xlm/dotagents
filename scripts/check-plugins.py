#!/usr/bin/env python3
"""Smoke-test this repo as a Codex, Claude Code and Copilot CLI plugin.

Checks, in order:
  1. Shared metadata: both marketplaces and all four manifest versions agree.
  2. Codex: installs, lists the expected xlm:* skills, and its
     session-start hook prints the root AGENTS.md.
  3. Claude Code: the same three checks.
  4. Copilot CLI: installs, lists the expected skills, and its hook command
     returns the root AGENTS.md in JSON additionalContext.

Run: scripts/check-plugins.py (or --versions-only without the CLIs)
Needs Python 3 with PyYAML, bash, jq, codex, claude and copilot. Set CODEX_BIN,
CLAUDE_BIN or COPILOT_BIN to use other binaries. No login is needed, and every install
goes into a temporary home that is deleted afterwards.

Each PASS line confirms one check. The first FAIL stops the run and names
a likely cause.

Not covered: real model sessions, the Devin plugin, and
native Windows (issue #7).
"""

import argparse
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import sys
import tempfile
import time

import yaml

from plugin_versions import check_versions


def fail(message, cause):
    sys.exit(f'FAIL: {message}, likely cause: {cause}')


def resolve_binary(name):
    binary = shutil.which(name)
    if binary is None:
        sys.exit(f'FAIL: {name} not found, likely cause: not installed or wrong *_BIN')
    # Make relative overrides absolute before chdir, without following symlinks.
    return os.path.abspath(binary)


def json_equal(left, right):
    # JSON distinguishes booleans from numbers, unlike Python equality.
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            json_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            json_equal(a, b) for a, b in zip(left, right)
        )
    return isinstance(left, bool) == isinstance(right, bool) and left == right


def check_metadata(root):
    try:
        claude_shelf = json.loads((root / '.claude-plugin/marketplace.json').read_text())
        codex_shelf = json.loads((root / '.agents/plugins/marketplace.json').read_text())
        shelves_match = all(json_equal(claude_shelf.get(field), codex_shelf.get(field))
                            for field in ('name', 'plugins'))
    except (OSError, json.JSONDecodeError, AttributeError):
        shelves_match = False
    if not shelves_match:
        fail('marketplace name or plugin list differs', 'marketplace metadata drift')

    try:
        manifests = [json.loads((root / folder / 'plugin.json').read_text())
                     for folder in ('.devin-plugin', '.claude-plugin',
                                    '.codex-plugin', '.github/plugin')]
    except (OSError, json.JSONDecodeError):
        fail('plugin name differs', 'manifest metadata drift')
    if not all(isinstance(manifest, dict) for manifest in manifests):
        fail('plugin name differs', 'manifest metadata drift')
    for field in ('name', 'description', 'author'):
        values = [manifest.get(field) for manifest in manifests]
        if any(value is None for value in values) or not all(
            json_equal(values[0], value) for value in values[1:]
        ):
            fail(f'plugin {field} differs', 'manifest metadata drift')
    print('PASS: marketplace and manifest metadata agree', flush=True)


def check_manifest_versions(root):
    try:
        version = check_versions(root)
    except (OSError, ValueError) as error:
        fail(str(error), 'manifest version drift')
    print(f'PASS: all five plugin versions agree ({version})', flush=True)


def codex_install(root, codex, work):
    with (work / 'install.log').open('w') as log:
        commands = [
            [codex, 'plugin', 'marketplace', 'add', str(root)],
            [codex, 'plugin', 'add', 'xlm@dotagents'],
        ]
        for command in commands:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
            if result.returncode != 0:
                sys.exit(result.returncode)


def without_synced_skills(root, actual, expected):
    # Local installs bundle synced skills, but they are not repository expectations.
    synced = set()
    for skill in (root / 'agents/.agents/skills/synced').rglob('SKILL.md'):
        frontmatter = yaml.safe_load(skill.read_text().split('---', 2)[1])
        synced.add('xlm:' + frontmatter['name'])
    return actual - (synced - expected)


def prompt_skill_names(prompt):
    return set(re.findall(r'xlm:[a-z0-9-]+', prompt))


def codex_skills(root, codex, work):
    # Codex lists implicitly invocable skills, using its own policy metadata.
    expected = set()
    for skill in (root / 'agents/.agents/skills').glob('*/SKILL.md'):
        frontmatter = yaml.safe_load(skill.read_text().split('---', 2)[1])
        metadata = skill.parent / 'agents/openai.yaml'
        policy = yaml.safe_load(metadata.read_text()) if metadata.exists() else {}
        if policy.get('policy', {}).get('allow_implicit_invocation', True):
            expected.add('xlm:' + frontmatter['name'])
    if not expected:
        fail('expected skill set is empty', 'missing Codex-invocable skills')

    prompt = subprocess.run(
        [codex, 'debug', 'prompt-input', 'hi'], cwd=work / 'empty',
        text=True, capture_output=True, check=True, timeout=30,
    ).stdout
    actual = prompt_skill_names(prompt)
    actual = without_synced_skills(root, actual, expected)
    if actual != expected:
        fail(f'skills differ: missing={sorted(expected - actual)}, '
             f'unexpected={sorted(actual - expected)}', 'Codex skill discovery paths')
    print(f'PASS: {len(expected)} expected xlm:* skills listed', flush=True)


def read_hook_reply(server):
    # Read raw chunks so multiple buffered replies cannot hide from select().
    selector = selectors.DefaultSelector()
    selector.register(server.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + 30
    pending = b''
    while time.monotonic() < deadline:
        if not selector.select(timeout=max(0, deadline - time.monotonic())):
            break
        chunk = os.read(server.stdout.fileno(), 65536)
        if not chunk:
            break
        pending += chunk
        while b'\n' in pending:
            line, pending = pending.split(b'\n', 1)
            message = json.loads(line)
            if message.get('id') == 2:
                return message
    return None


def list_codex_hooks(server, work):
    requests = [
        {'id': 1, 'method': 'initialize',
         'params': {'clientInfo': {'name': 'check-plugins', 'version': '0'}}},
        {'method': 'initialized'},
        {'id': 2, 'method': 'hooks/list',
         'params': {'cwds': [str(work / 'empty')]}},
    ]
    for request in requests:
        server.stdin.write(json.dumps({'jsonrpc': '2.0', **request}) + '\n')
    server.stdin.flush()
    response = read_hook_reply(server)
    if response is None or 'error' in response:
        fail(f'hooks/list failed: {response}', 'Codex app-server response')

    groups = response['result']['data']
    hooks = [hook for group in groups for hook in group['hooks']]
    session_hooks = [hook for hook in hooks
                     if hook['pluginId'] == 'xlm@dotagents'
                     and hook['eventName'] == 'sessionStart'
                     and hook['source'] == 'plugin'
                     and hook['enabled']]
    if not session_hooks:
        fail('xlm sessionStart hook not listed', 'Codex hook registration')
    if any(group['errors'] for group in groups):
        fail(f'hook errors: {groups}', 'Codex hook configuration')
    print('PASS: xlm sessionStart hook listed (trust via /hooks)')
    return session_hooks


def codex_hook(root, codex, work):
    with (work / 'app-server.log').open('w') as log:
        server = subprocess.Popen(
            [codex, 'app-server'], cwd=work / 'empty', text=True,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
        )
        try:
            hooks = list_codex_hooks(server, work)
            rules = (root / 'AGENTS.md').read_text()
            # Exercise Codex's expanded command without supplying a root ourselves.
            env = {key: value for key, value in os.environ.items()
                   if key not in ('PLUGIN_ROOT', 'CLAUDE_PLUGIN_ROOT')}
            for hook in hooks:
                result = subprocess.run(
                    ['bash', '-c', hook['command']], cwd=work / 'empty', env=env,
                    text=True, capture_output=True, timeout=30,
                )
                if result.returncode != 0 or not rules or rules not in result.stdout:
                    fail('xlm sessionStart hook did not print root AGENTS.md',
                         'hook command or cached rules')
            print('PASS: xlm sessionStart hook prints root AGENTS.md')
        finally:
            server.terminate()
            server.communicate(timeout=10)


def claude_environment(work):
    # Allowlist variables instead of inheriting credentials or plugin-root overrides.
    home = work / 'claude-home'
    return {
        'HOME': str(home),
        'CLAUDE_CONFIG_DIR': str(work / 'claude-config'),
        'XDG_CONFIG_HOME': str(home / '.config'),
        'XDG_CACHE_HOME': str(home / '.cache'),
        'PATH': os.environ['PATH'],
        'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1',
    }


def run_claude(claude, work, args, label, check=True):
    try:
        result = subprocess.run(
            [claude, *args], cwd=work / 'empty', env=claude_environment(work),
            stdin=subprocess.DEVNULL, text=True, capture_output=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        fail(f'Claude Code {label}: {error}', 'CLI execution or timeout')
    (work / f'claude-{label}.log').write_text(result.stdout + result.stderr)
    if check and result.returncode != 0:
        fail(f'Claude Code {label} failed: {result.stderr.strip()}',
             'CLI or marketplace configuration')
    return result


def claude_install(root, claude, work):
    (work / 'claude-home').mkdir()
    (work / 'claude-config').mkdir()

    # Snapshot expected names before installation. Manual-only skills still appear.
    expected = set()
    for skill in (root / 'agents/.agents/skills').glob('*/SKILL.md'):
        frontmatter = yaml.safe_load(skill.read_text().split('---', 2)[1])
        if frontmatter.get('user-invocable', True):
            expected.add('xlm:' + skill.parent.name)
    if not expected:
        fail('Claude Code expected skill set is empty', 'missing user-invocable skills')

    run_claude(claude, work, ['plugin', 'marketplace', 'add', str(root)], 'marketplace')
    run_claude(claude, work, ['plugin', 'install', 'xlm@dotagents'], 'install')
    listing = run_claude(claude, work, ['plugin', 'list', '--json'], 'list')
    try:
        plugins = json.loads(listing.stdout)
    except json.JSONDecodeError:
        fail('Claude Code plugin list is not JSON', 'CLI output format')
    if not any(plugin['id'] == 'xlm@dotagents' and plugin['enabled'] is True
               for plugin in plugins):
        fail('Claude Code xlm@dotagents not listed as enabled', 'install or enablement')
    print('PASS: Claude Code xlm@dotagents installed and enabled', flush=True)
    return expected


def claude_session(claude, work):
    # Authentication fails after initialization and hook execution, without inference.
    session = run_claude(
        claude, work, ['-p', 'hi', '--output-format', 'stream-json', '--verbose'],
        'session', check=False,
    )
    try:
        events = [json.loads(line) for line in session.stdout.splitlines() if line]
    except json.JSONDecodeError:
        fail('Claude Code session output is not JSON', 'CLI output format')
    initializations = [event for event in events
                       if event.get('type') == 'system' and event.get('subtype') == 'init']
    if (len(initializations) != 1 or initializations[0].get('apiKeySource') != 'none'
            or session.returncode != 1
            or not any(event.get('error') == 'authentication_failed' for event in events)):
        fail('Claude Code expected an initialized no-login session',
             'authentication or session startup')
    return initializations[0], events


def claude_skills(claude, work, expected):
    initialization, events = claude_session(claude, work)
    actual = {name for name in initialization['slash_commands'] if name.startswith('xlm:')}
    if actual != expected:
        fail(f'Claude Code skills differ: missing={sorted(expected - actual)}, '
             f'unexpected={sorted(actual - expected)}', 'skill paths or invocation frontmatter')
    print(f'PASS: Claude Code {len(expected)} expected xlm:* skills listed', flush=True)
    return events


def claude_hook(root, events):
    rules = (root / 'AGENTS.md').read_text()
    if not rules or not any(
        event.get('type') == 'system' and event.get('subtype') == 'hook_response'
        and event.get('hook_event') == 'SessionStart' and event.get('exit_code') == 0
        and event.get('outcome') == 'success' and rules in event.get('stdout', '')
        for event in events
    ):
        fail('Claude Code SessionStart hook did not print root AGENTS.md',
             'hook registration, command, or rules')
    print('PASS: Claude Code SessionStart hook prints root AGENTS.md')


def copilot_skill_names(output):
    """Read only indented skill entries in the Plugin skills section."""
    names = set()
    in_plugins = False
    for line in output.splitlines():
        if line == 'Plugin skills:':
            in_plugins = True
        elif line and not line[0].isspace():
            in_plugins = False
        elif in_plugins and line.strip():
            name, separator, description = line.strip().partition(' - ')
            if not separator or not name or not description:
                raise ValueError(f'malformed Copilot plugin skill: {line}')
            names.add(name)
    return names


def run_copilot(copilot, work, args, label):
    home = work / 'copilot-home'
    env = {
        'HOME': str(home),
        'COPILOT_HOME': str(work / 'copilot-config'),
        'XDG_CONFIG_HOME': str(home / '.config'),
        'XDG_CACHE_HOME': str(home / '.cache'),
        'PATH': os.environ['PATH'],
    }
    try:
        result = subprocess.run(
            [copilot, *args], cwd=work / 'empty', env=env,
            stdin=subprocess.DEVNULL, text=True, capture_output=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        fail(f'Copilot CLI {label}: {error}', 'CLI execution or timeout')
    (work / f'copilot-{label}.log').write_text(result.stdout + result.stderr)
    if result.returncode != 0:
        fail(f'Copilot CLI {label} failed: {result.stderr.strip()}',
             'CLI or marketplace configuration')
    return result.stdout


def copilot_install(root, copilot, work):
    (work / 'copilot-home').mkdir()
    run_copilot(copilot, work, ['plugin', 'marketplace', 'add', str(root)], 'marketplace')
    run_copilot(copilot, work, ['plugin', 'install', 'xlm@dotagents'], 'install')
    listing = run_copilot(copilot, work, ['plugin', 'list', '--json'], 'list')
    try:
        plugins = json.loads(listing)
    except json.JSONDecodeError:
        fail('Copilot CLI plugin list is not JSON', 'CLI output format')
    if not any(plugin['name'] == 'xlm' and plugin['marketplace'] == 'dotagents'
               and plugin['enabled'] is True for plugin in plugins):
        fail('Copilot CLI xlm@dotagents not listed as enabled', 'install or enablement')
    print('PASS: Copilot CLI xlm@dotagents installed and enabled', flush=True)


def copilot_skills(root, copilot, work):
    # Copilot lists all plugin skills, including manual-only skills, without policy filtering.
    expected = {
        yaml.safe_load(skill.read_text().split('---', 2)[1])['name']
        for skill in (root / 'agents/.agents/skills').glob('*/SKILL.md')
    }
    if not expected:
        fail('Copilot CLI expected skill set is empty', 'missing skills')
    listing = run_copilot(copilot, work, ['skill', 'list'], 'skills')
    try:
        actual = copilot_skill_names(listing)
    except ValueError as error:
        fail(str(error), 'CLI output format')
    if actual != expected:
        fail(f'Copilot CLI skills differ: missing={sorted(expected - actual)}, '
             f'unexpected={sorted(actual - expected)}', 'skill paths or discovery')
    print(f'PASS: Copilot CLI {len(expected)} expected plugin skills listed', flush=True)


def copilot_hook(root, work):
    config = json.loads((root / '.github/plugin/hooks.json').read_text())
    command = config['hooks']['sessionStart'][0]['bash']
    try:
        result = subprocess.run(
            ['bash', '-c', command], cwd=work / 'empty',
            env={'PATH': os.environ['PATH'], 'PLUGIN_ROOT': str(root)},
            stdin=subprocess.DEVNULL, text=True, capture_output=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        fail(f'Copilot CLI hook: {error}', 'hook command execution or timeout')
    if result.returncode != 0:
        fail(f'Copilot CLI hook failed: {result.stderr.strip()}', 'hook command or jq')
    try:
        context = json.loads(result.stdout)['additionalContext']
    except (json.JSONDecodeError, KeyError, TypeError):
        fail('Copilot CLI hook returned no JSON additionalContext', 'hook output format')
    rules = (root / 'AGENTS.md').read_text()
    if not isinstance(context, str) or not rules or rules not in context:
        fail('Copilot CLI hook did not return root AGENTS.md', 'hook command or rules')
    print('PASS: Copilot CLI sessionStart hook returns root AGENTS.md in additionalContext')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--versions-only', action='store_true',
                        help='check manifest versions without installing plugins')
    args = parser.parse_args()
    root = Path(__file__).absolute().parent.parent
    check_manifest_versions(root)
    if args.versions_only:
        return
    codex = resolve_binary(os.environ.get('CODEX_BIN') or 'codex')
    claude = resolve_binary(os.environ.get('CLAUDE_BIN') or 'claude')
    copilot = resolve_binary(os.environ.get('COPILOT_BIN') or 'copilot')
    os.chdir(root)

    print('Shared metadata', flush=True)
    check_metadata(root)

    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        (work / 'home').mkdir()
        (work / 'empty').mkdir()
        os.environ['CODEX_HOME'] = str(work / 'home')
        os.environ['RUST_LOG'] = 'error'

        print('\nCodex', flush=True)
        codex_install(root, codex, work)
        codex_skills(root, codex, work)
        codex_hook(root, codex, work)

        print('\nClaude Code', flush=True)
        expected = claude_install(root, claude, work)
        events = claude_skills(claude, work, expected)
        claude_hook(root, events)

        print('\nCopilot CLI', flush=True)
        copilot_install(root, copilot, work)
        copilot_skills(root, copilot, work)
        copilot_hook(root, work)


if __name__ == '__main__':
    main()
