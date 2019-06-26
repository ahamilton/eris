#!/bin/bash

# Copyright (C) 2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


USAGE="Make a flatpak build of eris.

Usage: build-flatpak.sh <manifest_path> <build_dir> <state_dir>

e.g. # build-flatpak.sh com.github.ahamilton.eris.json eris-build flatpak-cache"


if [ $# != 3 ]; then
    echo "$USAGE"
    exit 1
fi


set -e
set -x


MANIFEST_PATH="$1"
BUILD_DIR="$2"
STATE_DIR="$3"
rm -rf "$STATE_DIR/build"
flatpak-builder "$BUILD_DIR" "$MANIFEST_PATH" --force-clean \
		--state-dir="$STATE_DIR"
flatpak build "$BUILD_DIR" test-all
flatpak build "$BUILD_DIR" eris --help
echo "Build successfull: $BUILD_DIR"
