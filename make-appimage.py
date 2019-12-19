#!/usr/bin/env python3.7

# Copyright (C) 2017-2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import os
import pickle
import sys
import tempfile

import test_distributions


ERIS_PATH = os.path.realpath(os.path.dirname(__file__))
cmd = test_distributions.cmd


def all_paths(path):
    for entry in os.scandir(path):
        if entry.is_dir(follow_symlinks=False):
            yield from all_paths(entry.path)
        else:
            yield entry.path


def relative_paths(root_path, paths):
    root_len = len(root_path)
    for path in paths:
        yield "." + path[root_len:]


def make_sub_container(src_root, dest_root, paths):
    for path in paths:
        dest_path = os.path.join(dest_root, path)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        os.link(os.path.join(src_root, path), dest_path)


def filter_paths(paths, excluded):
    return [path for path in paths if excluded not in path]


def make_ubuntu_base():
    if os.path.exists("base_paths"):
        with open("base_paths", "rb") as file_:
            base_paths = pickle.load(file_)
    else:
        test_distributions.build_ubuntu()
        base_paths = relative_paths("ubuntu", all_paths("ubuntu"))
        base_paths = filter_paths(base_paths, "python3")
        with open("base_paths", "wb") as file_:
            pickle.dump(base_paths, file_)
    return base_paths


def install_eris():
    run_in_container = test_distributions.run_in_container
    run_in_container("ubuntu", "./install-dependencies")
    run_in_container("ubuntu", "pip3 install -I .")


def make_app_dir(app_dir, new_paths):
    os.mkdir(app_dir)
    make_sub_container("ubuntu", app_dir, new_paths)
    cmd(f"cp -a {ERIS_PATH}/tests {app_dir}")
    cmd(f"cp -a {ERIS_PATH}/test-all {app_dir}")
    cmd(f"cp {ERIS_PATH}/appimage/* {app_dir}")


def cleanup_app_dir(app_dir):
    cmd(f"rm -rf {app_dir}/usr/share/go*")
    cmd(f"rm -rf {app_dir}/usr/lib/go*")
    cmd(f"rm -rf {app_dir}/root")


def make_appimage(app_dir):
    cmd("wget --continue https://github.com/AppImage/AppImageKit/releases/"
        "download/12/appimagetool-x86_64.AppImage")
    cmd("chmod +x appimagetool-x86_64.AppImage")
    cmd("ARCH=x86_64 ./appimagetool-x86_64.AppImage --comp xz " + app_dir)


def main(work_path):
    assert os.getuid() == 0 and os.getgid() == 0, "Need to be root."
    os.chdir(work_path)
    base_paths = make_ubuntu_base()
    install_eris()
    post_install_paths = relative_paths("ubuntu", all_paths("ubuntu"))
    new_paths = set(post_install_paths) - set(base_paths)
    new_paths = filter_paths(new_paths, "/var/cache/apt/archives")
    app_dir = "eris.AppDir"
    if os.path.exists(app_dir):
        cmd("sudo rm -rf " + app_dir)
    make_app_dir(app_dir, new_paths)
    cleanup_app_dir(app_dir)
    make_appimage(app_dir)


if __name__ == "__main__":
    work_path = (tempfile.mkdtemp(prefix="make-appimage-")
                 if len(sys.argv) == 1 else sys.argv[1])
    main(work_path)
