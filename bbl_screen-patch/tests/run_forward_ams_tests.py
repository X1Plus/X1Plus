#!/usr/bin/env python3
"""Run the production AMS report handler without ARM trampolines or OEM files."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='alternate forward_shim.cpp for regression checks')
    parser.add_argument('--sanitize', action='store_true')
    args = parser.parse_args()
    tests = Path(__file__).resolve().parent
    source_path = args.source or tests.parent / 'forward_shim.cpp'
    source = source_path.read_text()
    # Compile these complete, unmodified production sections. Only the packet
    # envelope, logging and legacy callback are mocked in the C++ harness.
    sections = [
        ('enum hw_type_e {', '/*** JSON-side overrides ***/'),
        ('int (*CProtocal_original_ams_report)', '/* The other overrides mostly'),
    ]
    with tempfile.TemporaryDirectory(prefix='x1plus-ams-') as directory:
        build = Path(directory)
        implementation = []
        for start, end in sections:
            begin = source.index(start)
            finish = source.index(end, begin)
            line = source[:begin].count('\n') + 1
            implementation.append(f'#line {line} "{source_path.as_posix()}"\n' + source[begin:finish])
        (build / 'forward_ams_under_test.inc').write_text('\n'.join(implementation))
        command = shlex.split(os.environ.get('CXX', 'g++'))
        command += ['-std=c++11', '-Wall', '-Wextra', '-Werror', '-g', '-I', str(build)]
        if args.sanitize:
            command += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie']
        binary = build / 'forward_ams_tests'
        command += [str(tests / 'forward_ams_tests.cpp'), '-o', str(binary)]
        subprocess.run(command, check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
