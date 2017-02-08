#!/usr/bin/env python3.5

# Copyright (C) 2017 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import os
import subprocess
import sys
import tempfile


class OverlayfsMount():

    def __init__(self, lower_dir, mount_point):
        self.lower_dir = lower_dir
        self.mount_point = mount_point

    def __repr__(self):
        return "<OverlayfsMount:%r over %r>" % (self.mount_point,
                                                self.lower_dir)

    def __enter__(self):
        self.upper_dir = tempfile.TemporaryDirectory()
        self.work_dir = tempfile.TemporaryDirectory()
        option_string = ("lowerdir=%s,upperdir=%s,workdir=%s" %
                         (self.lower_dir, self.upper_dir.name,
                          self.work_dir.name))
        subprocess.check_call(["mount", "-t", "overlay", "-o",
                               option_string, "overlay", self.mount_point],
                              stderr=subprocess.PIPE)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        subprocess.check_call(["umount", "--lazy", self.mount_point])


_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
_IN_DIRECTORY_SCRIPT = os.path.join(_SCRIPT_DIR, "in-directory")


def _in_directory(directory_path, command):
    return [_IN_DIRECTORY_SCRIPT, directory_path] + command


def _parse_proc_mounts():
    with open("/proc/mounts") as file_:
        for line in file_:
            yield line.split()


def _find_mounts():
    all_mounts = set(part[1] for part in _parse_proc_mounts())
    mount_points = {"/", "/usr", "/bin", "/etc", "/lib", "/dev", "/home",
                    "/boot", "/opt", "/run", "/root", "/var"}
    return all_mounts.intersection(mount_points)


class SandboxFs:

    def __init__(self, holes=None):
        self.holes = [] if holes is None else holes
        self.holes += ["/dev/null"]
        for hole in self.holes:
            if not hole.startswith("/"):
                raise ValueError("Holes must be absolute paths: %r" % hole)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mount_point = self.temp_dir.name
        self.overlay_mounts = []

    def __repr__(self):
        return ("<SandboxFs:%r mounts:%r>" %
                (self.temp_dir.name, len(self.overlay_mounts)))

    def __enter__(self):
        self.overlay_mounts = [
            OverlayfsMount(mount_point,
                           self.mount_point + mount_point).__enter__()
            for mount_point in sorted(_find_mounts())]
        for hole in self.holes:
            subprocess.check_call(["mount", "--bind", hole,
                                   self.mount_point + hole])
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        for hole in reversed(self.holes):
            subprocess.check_call(["umount", self.mount_point + hole])
        for mount in reversed(self.overlay_mounts):
            mount.__exit__(None, None, None)
        self.overlay_mounts = []

    def command(self, command, env=None):
        return (["chroot", self.mount_point] +
                _in_directory(os.getcwd(), command))


if __name__ == "__main__":
    try:
        divider_index = sys.argv.index("--")
        holes, command = sys.argv[1:divider_index], sys.argv[divider_index+1:]
    except ValueError:
        holes, command = None, sys.argv[1:]
    with SandboxFs(holes) as sandbox:
        subprocess.check_call(sandbox.command(command))
