#!/usr/bin/env python3
import os
import subprocess
import shutil
from pathlib import Path
from argparse import ArgumentParser


def recursive_unlink(root_path):
    for path in root_path.iterdir():
        if path.is_file():
            path.unlink()
        else:
            recursive_unlink(path)
    root_path.rmdir()

def remove_patches():
    recursive_unlink(Path("patches"))

def generate():
    remove_patches()
    for root, dirs, files in os.walk("printer_ui"):
        for dirname in dirs:
            path = Path(os.path.join(root, dirname))
            origPath = "printer_ui-orig" / Path(os.path.join(root, dirname)).relative_to("printer_ui")
            patchPath = "patches" / Path(os.path.join(root, dirname)).relative_to("printer_ui")
            if (os.path.isdir(path)):
                diff = subprocess.run(["diff", "-urN", origPath.as_posix(), path.as_posix()], check=False, capture_output=True)
                if (len(diff.stdout) > 0):
                    os.makedirs(patchPath, exist_ok=True)
        for filename in files:
            path = Path(os.path.join(root, filename))
            origPath = "printer_ui-orig" / Path(os.path.join(root, filename)).relative_to("printer_ui")
            patchPath = "patches" / Path(os.path.join(root, filename+".patch")).relative_to("printer_ui")
            binPath = "patches" / Path(os.path.join(root, filename)).relative_to("printer_ui")
            if path.is_file() and not str(path).endswith("~") and not str(path).endswith(".orig") and not str(path).endswith(".rej"):
                diff = subprocess.run(["diff", "-u", "--label", origPath.as_posix(), origPath.as_posix(), "--label", path.as_posix(), path.as_posix()], check=False, capture_output=True)
                with open(path, 'rb') as f:
                    editedFileLength = len(f.read())
                if diff.returncode == 2:
                    if diff.stderr.decode().strip().endswith(f"{origPath}: No such file or directory"):
                        print(f"Copying new file: {path}")
                        shutil.copy2(path, binPath)
                    else:
                        print(f"Error: {diff.stderr.decode()}")
                        exit(1)
                elif len(diff.stdout)*(70 / 100) > editedFileLength:
                    print(f"Copying rewritten file: {path}")
                    shutil.copy2(path, binPath)
                elif len(diff.stdout) > 0:
                    if (diff.stdout.decode().startswith("Binary")):
                        print(f"Copying binary file: {path}")
                        shutil.copy2(path, binPath)
                    else:
                        print(f"Writing patch for: {path}")
                        with open(patchPath, 'wb') as patchFile:
                            patchFile.write(diff.stdout)

def apply():
    for root, dirs, files in os.walk("patches"):
        for dirname in dirs:
            path = Path(os.path.join(root, dirname))
            applyPath = "printer_ui" / Path(os.path.join(root, dirname)).relative_to("patches")
            if (os.path.isdir(path)):
                os.makedirs(applyPath, exist_ok=True)
        for filename in files:
            path = Path(os.path.join(root, filename))
            applyPath = "printer_ui" / Path(os.path.join(root, filename)).relative_to("patches")
            if path.is_file():
                if not path.name.endswith(".patch"):
                    print(f"Copying file: {path}")
                    shutil.copy2(path, applyPath)
                else:
                    print(f"Applying patch: {path}")
                    with open(path, 'rb') as patchFile:
                        subprocess.run(["patch", "-N", "-p1", "-dprinter_ui"], input=patchFile.read())

if __name__ == "__main__":
    parser = ArgumentParser(
        description='Generate and apply patches for printer_ui/bbl_screen'
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-g', '--generate', dest='generate', action='store_true', default=False)
    group.add_argument('-a', '--apply', dest='apply', action='store_true', default=False)

    args = parser.parse_args()

    if args.generate:
        generate()
    elif args.apply:
        apply()
    else:
        parser.print_help()