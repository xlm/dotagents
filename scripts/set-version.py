#!/usr/bin/env python3
"""Set the shared plugin manifest version."""

import argparse
from pathlib import Path

from plugin_versions import set_version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version')
    args = parser.parse_args()
    try:
        set_version(Path(__file__).resolve().parent.parent, args.version)
    except (OSError, ValueError) as error:
        parser.exit(1, f'FAIL: {error}\n')


if __name__ == '__main__':
    main()
