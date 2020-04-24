#!/usr/bin/python3.8

# Copyright (C) 2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import json
import os
import subprocess
import sys


USAGE = """Make a flatpak build of eris.

Usage: build-flatpak.sh <manifest_path> <build_dir> <state_dir>

e.g. # build-flatpak.sh com.github.ahamilton.eris.json eris-build flatpak-cache

The script should only be run from the root of the local eris repository.
"""


def patch_manifest(manifest_path, patched_manifest_path):
    with open(manifest_path) as manifest_file:
        manifest = json.load(manifest_file)
    eris_module = manifest["modules"][-1]
    eris_module["sources"][0]["url"] = "file://" + os.getcwd()
    with open(patched_manifest_path, "w") as patched_manifest_file:
        json.dump(manifest, patched_manifest_file, indent=2)


def main(argv):
    if len(argv) != 4:
        print(USAGE)
        sys.exit(1)
    manifest_path, build_dir, state_dir = argv[1:4]
    patched_manifest_path = "manifests-cache/patched-manifest.json"
    patch_manifest(manifest_path, patched_manifest_path)
    subprocess.run(["flatpak-builder", build_dir, patched_manifest_path,
                    "--force-clean", "--state-dir", state_dir,
                    "--disable-updates"], check=True)
    subprocess.run(["flatpak", "build", build_dir, "test-all"], check=True)
    subprocess.run(["flatpak", "build", build_dir, "eris", "--help"],
                   check=True)
    print("Build successful:", build_dir)


if __name__ == "__main__":
    main(sys.argv)
