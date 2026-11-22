"""All five plugin manifests must share an unprefixed SemVer 2.0.0 string."""

import json
from pathlib import Path
import re


MANIFESTS = ('.devin-plugin/plugin.json', '.claude-plugin/plugin.json',
             '.codex-plugin/plugin.json', '.github/plugin/plugin.json',
             '.cursor-plugin/plugin.json')
NUMBER = r'(?:0|[1-9][0-9]*)'
IDENTIFIER = rf'(?:{NUMBER}|[0-9]*[A-Za-z-][0-9A-Za-z-]*)'
SEMVER = re.compile(
    rf'{NUMBER}\.{NUMBER}\.{NUMBER}'
    rf'(?:-{IDENTIFIER}(?:\.{IDENTIFIER})*)?'
    r'(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?'
)


def validate_version(version):
    if not isinstance(version, str) or SEMVER.fullmatch(version) is None:
        raise ValueError(f'invalid unprefixed semver: {version!r}')
    return version


def read_manifests(root):
    manifests = []
    for relative in MANIFESTS:
        path = Path(root) / relative
        manifest = json.loads(path.read_text())
        if not isinstance(manifest, dict) or 'name' not in manifest:
            raise ValueError(f'{relative} must be an object with a name')
        manifests.append((path, manifest))
    return manifests


def check_versions(root):
    versions = [validate_version(manifest.get('version'))
                for _, manifest in read_manifests(root)]
    if len(set(versions)) != 1:
        raise ValueError('plugin manifest versions differ')
    return versions[0]


def set_version(root, version):
    validate_version(version)
    manifests = read_manifests(root)
    for path, manifest in manifests:
        updated = {}
        for key, value in manifest.items():
            if key != 'version':
                updated[key] = value
            if key == 'name':
                updated['version'] = version
        path.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + '\n')
