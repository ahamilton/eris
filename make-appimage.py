#!/usr/bin/python3

# Copyright (C) 2017 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import os
import pickle
import sys
import tempfile

import test_distributions


VIGIL_PATH = os.path.realpath(os.path.dirname(__file__))
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
    return [path for path in paths if not excluded in path]


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


# FIX: This isn`t making the correct libunionpreload.
# def make_libunionpreload():
#     #See https://github.com/AppImage/AppImages/blob/master/recipes/meta/Recipe
#     temp_dir = tempfile.mkdtemp()
#     cmd("wget -q https://raw.githubusercontent.com/mikix/deb2snap/"
#         "blob/847668c4a89e2d4a1711fe062a4bae0c7ab81bd0/src/preload.c "
#         "-O - | sed -e 's|SNAPPY|UNION|g' | sed -e 's|SNAPP|UNION|g' | "
#         "sed -e 's|SNAP|UNION|g' | sed -e 's|snappy|union|g' "
#         "> %s/libunionpreload.c" % temp_dir)
#     cmd("gcc -shared -fPIC %s/libunionpreload.c -o libunionpreload.so "
#         '-ldl -DUNION_LIBNAME="libunionpreload.so"' % temp_dir)
#     cmd("strip libunionpreload.so")


def make_app_dir(app_dir, new_paths):
    os.mkdir(app_dir)
    make_sub_container("ubuntu", app_dir, new_paths)
    cmd("cp -a %s/tests %s" % (VIGIL_PATH, app_dir))
    cmd("cp -a %s/test-all %s" % (VIGIL_PATH, app_dir))
    cmd("cp %s/appimage/* %s" % (VIGIL_PATH, app_dir))
    # if not os.path.exists("libunionpreload.so"):
    #     make_libunionpreload()
    # cmd("cp libunionpreload.so " + app_dir)


def make_appimage(app_dir):
    cmd("wget --continue https://github.com/AppImage/AppImageKit/releases/"
        "download/continuous/appimagetool-x86_64.AppImage")
    cmd("chmod +x appimagetool-x86_64.AppImage")
    cmd("./appimagetool-x86_64.AppImage " + app_dir)


def main(work_path):
    assert os.getuid() == 0 and os.getgid() == 0, "Need to be root."
    os.chdir(work_path)
    base_paths = make_ubuntu_base()
    test_distributions.run_in_container("ubuntu", "./install-dependencies")
    test_distributions.run_in_container(
        "ubuntu", "sed -i -e 's/\/usr\/bin\/python/\/usr\/bin\/env python/g' "
        "/usr/bin/pdf2txt")  # libunionpreload doesn't trick shebangs?
    test_distributions.run_in_container("ubuntu", "apt-get install --yes python3-pip")
    test_distributions.run_in_container("ubuntu", "pip3 install -I .")
    post_install_paths = relative_paths("ubuntu", all_paths("ubuntu"))
    new_paths = set(post_install_paths) - set(base_paths)
    new_paths = filter_paths(new_paths, "/var/cache/apt/archives")
    app_dir = "vigil.AppDir"
    if os.path.exists(app_dir):
        cmd("sudo rm -rf " + app_dir)
    make_app_dir(app_dir, new_paths)
    make_appimage(app_dir)


if __name__ == "__main__":
    work_path = (tempfile.mkdtemp(prefix="make-appimage2-")
                 if len(sys.argv) == 1 else sys.argv[1])
    main(work_path)
