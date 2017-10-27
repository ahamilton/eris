#!/usr/bin/env python3.6

# Copyright (C) 2017 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import os
import subprocess
import sys
import tempfile


VIGIL_PATH = os.path.realpath(os.path.dirname(__file__))


def cmd(command):
    subprocess.check_call(command, shell=True)


def mount_squashfs_iso(iso, squashfs_path, mount_point):
    cmd("mkdir iso && sudo mount -o loop %s iso" % iso)
    cmd("mkdir lower && sudo mount -t squashfs iso/%s lower" % squashfs_path)
    cmd("mkdir upper work %s && sudo mount -t overlay "
        "-o lowerdir=lower,upperdir=upper,workdir=work overlay %s" %
        (mount_point, mount_point))


def umount_squashfs_iso(mount_point):
    cmd("sudo umount %s && sudo rm -rf upper work %s" %
        (mount_point, mount_point))
    cmd("sudo umount lower && rmdir lower")
    cmd("sudo umount iso && rmdir iso")


def run_in_container(container, command):
    option = "--directory" if os.path.isdir(container) else "--image"
    cmd("sudo systemd-nspawn --quiet --chdir=/vigil --overlay=%s:/vigil "
        '%s=%s /bin/bash --login -c "%s"' %
        (VIGIL_PATH, option, container, command))


def build_ubuntu():
    cmd("sudo debootstrap zesty ubuntu.part")
    run_in_container("ubuntu.part",
                     "ln -sf /lib/systemd/resolv.conf /etc/resolv.conf")
    run_in_container("ubuntu.part",
                     "sed -i -e 's/main/main restricted universe"
                     " multiverse/g' /etc/apt/sources.list")
    run_in_container("ubuntu.part", "apt-get update")
    os.rename("ubuntu.part", "ubuntu")


def build_fedora():
    image = "Fedora-Cloud-Base-25-1.3.x86_64.raw"
    cmd("wget --continue https://dl.fedoraproject.org/pub/fedora/linux/"
        "releases/25/CloudImages/x86_64/images/%s.xz" % image)
    cmd("unxz %s.xz" % image)
    os.rename(image, "fedora")


def build_debian():
    cmd("sudo debootstrap --components=main,contrib,non-free "
        "--include=sudo jessie debian.part")
    run_in_container("debian.part", "apt-get update")
    os.rename("debian.part", "debian")


ARCHLINUX_ISO = "archlinux-2017.06.01-x86_64.iso"


def build_archlinux():
    cmd("wget --continue http://mirrors.kernel.org/archlinux/iso/2017.06.01/"
        + ARCHLINUX_ISO)
    mount_squashfs_iso(ARCHLINUX_ISO, "arch/x86_64/airootfs.sfs", "archlinux")
    run_in_container("archlinux", "pacman-key --init")
    run_in_container("archlinux", "pacman-key --populate archlinux")
    run_in_container("archlinux", "pacman -Syyu --noconfirm")


def remove_archlinux():
    umount_squashfs_iso("archlinux")
    os.remove(ARCHLINUX_ISO)


OPENSUSE_ISO = "openSUSE-Tumbleweed-GNOME-Live-x86_64-Current.iso"


def build_opensuse():
    cmd("wget --continue https://download.opensuse.org/tumbleweed/iso/"
        + OPENSUSE_ISO)
    mount_squashfs_iso(OPENSUSE_ISO, "openSUSE-tumbleweed-livecd-gnome"
                       "-read-only.x86_64-2.8.0", "opensuse")


def remove_opensuse():
    umount_squashfs_iso("opensuse")
    os.remove(OPENSUSE_ISO)


PIXEL_ISO = "2016-12-13-pixel-x86-jessie.iso"


def build_pixel():
    cmd("wget --continue http://downloads.raspberrypi.org/pixel_x86/images/"
        "pixel_x86-2016-12-13/" + PIXEL_ISO)
    mount_squashfs_iso(PIXEL_ISO, "live/filesystem.squashfs", "pixel")
    cmd("sudo rm pixel/etc/resolv.conf")
    cmd("echo 'nameserver 127.0.0.53' | sudo dd of=pixel/etc/resolv.conf")
    run_in_container("pixel", "apt-get update")


def remove_pixel():
    umount_squashfs_iso("pixel")
    os.remove(PIXEL_ISO)


def build_gentoo():
    tar_file = "stage3-amd64-20170525.tar.bz2"
    cmd("wget --continue http://distfiles.gentoo.org/releases/amd64/"
        "autobuilds/20170525/" + tar_file)
    cmd("mkdir -p gentoo.part")
    cmd("sudo tar --directory=gentoo.part -xjf " + tar_file)
    os.remove(tar_file)
    run_in_container("gentoo.part", "emerge --sync")
    run_in_container("gentoo.part", "emerge sudo")
    os.rename("gentoo.part", "gentoo")


def main():
    work_path = (tempfile.mkdtemp(prefix="test_distributions-")
                 if len(sys.argv) == 1 else sys.argv[1])
    os.chdir(work_path)
    cmd("sudo apt-get install -y systemd-container debootstrap xz-utils wget")
    # FIX: Reenable: fedora debian archlinux opensuse pixel gentoo
    for distribution in ["ubuntu"]:
        if os.path.exists(distribution):
            print("%s container already exists." % distribution)
        else:
            print("Building %s container..." % distribution)
            globals()["build_" + distribution]()
        print("Installing vigil's dependencies in %s..." % distribution)
        run_in_container(distribution, "./install-dependencies")
        print("Installing vigil in %s..." % distribution)
        run_in_container(distribution, "apt-get install --yes python3-pip")
        run_in_container(distribution, "pip3 install .")
        print("Testing vigil in %s..." % distribution)
        run_in_container(distribution, "./test-all")
        print("Running vigil in %s..." % distribution)
        run_in_container(distribution, "vigil --help")
        print("Successfully installed vigil in %s." % distribution)
        print("Removing %s container..." % distribution)
        try:
            globals()["remove_" + distribution]()
        except KeyError:
            cmd("sudo rm -rf " + distribution)
    os.rmdir(work_path)
    print("Finished.")


if __name__ == "__main__":
    main()
