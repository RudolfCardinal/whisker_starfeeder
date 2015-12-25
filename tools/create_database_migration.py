#!/usr/bin/env python

import argparse
import os
import subprocess
import sys
if sys.version_info[0] < 3:
    raise AssertionError("Need Python 3")

N_SEQUENCE_CHARS = 4  # like Django

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
CODE_DIR = os.path.join(PROJECT_BASE_DIR, 'starfeeder')
ALEMBIC_VERSIONS_DIR = os.path.join(CODE_DIR, 'alembic', 'versions')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("message", help="Revision message")
    args = parser.parse_args()

    _, _, existing_version_filenames = next(os.walk(ALEMBIC_VERSIONS_DIR),
                                            (None, None, []))
    current_seq_strs = [x[:N_SEQUENCE_CHARS]
                        for x in existing_version_filenames]
    current_seq_strs.sort()
    if not current_seq_strs:
        current_seq_str = None
        new_seq_no = 1
    else:
        current_seq_str = current_seq_strs[-1]
        new_seq_no = max(int(x) for x in current_seq_strs) + 1
    new_seq_str = str(new_seq_no).zfill(N_SEQUENCE_CHARS)

    print("""
Generating new revision with Alembic...
    Last revision was: {}
    New revision will be: {}
    [If it fails with "Can't locate revision identified by...", you might need
    to DROP the alembic_version table.]
    """.format(current_seq_str, new_seq_str))

    sys.path.append(PROJECT_BASE_DIR)
    os.chdir(CODE_DIR)
    subprocess.call(['alembic', 'revision',
                     '--autogenerate',
                     '-m', args.message,
                     '--rev-id', new_seq_str])
