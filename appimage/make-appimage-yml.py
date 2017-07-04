#!/usr/bin/env python3

# Copyright (C) 2017 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import vigil.tools as tools


dist_deps = set()
for dependency in tools.dependencies("ubuntu"):
    if "/" in dependency:
        raise ValueError
    else:
        dist_deps.add(dependency)
dist_deps.update({"python3-pygments", "python3-pyinotify", "python3-docopt",
                  "util-linux", "python3-pil"})
dep_list = "\n    - ".join(sorted(dist_deps))
print("""app: vigil-code-monitor
union: true

ingredients:
  packages:
    - %s
  dist: zesty
  sources:
    - deb http://archive.ubuntu.com/ubuntu/ zesty main universe

script:
  - export APPDIR=$(pwd)
  - export PYTHONPATH=$APPDIR/usr/share/pyshared
  - mkdir -p $PYTHONPATH
  - (cd $VIGIL_PATH; /usr/bin/python3 setup.py install \
     --prefix=$APPDIR/usr --install-lib=$PYTHONPATH)
  - cp $VIGIL_PATH/appimage/vigil-icon.png .
  - cp -a $VIGIL_PATH/tests .
  - cp $VIGIL_PATH/test-all tests
  - cat > vigil.desktop <<\EOF
  - [Desktop Entry]
  - Type=Application
  - Name=Vigil Code Monitor
  - Comment=Vigil maintains an up-to-date set of reports for every file in a codebase.
  - Exec=vigil
  - Terminal=true
  - Icon=vigil-icon.png
  - Categories=Application;
  - EOF
""" % dep_list)
