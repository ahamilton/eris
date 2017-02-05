
# Copyright (C) 2011, 2015-2017 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import os
import os.path
import stat
import syslog


FILE_KEY = "fi"
DIRECTORY_KEY = "di"
OTHER_WRITABLE_KEY = "ow"
EXECUTABLE_KEY = "ex"
SETUID_KEY = "su"
SETGUID_KEY = "sg"
SYMLINK_KEY = "ln"
ORPHAN_KEY = "or"
PIPE_KEY = "pi"
CHARACTER_DEVICE_KEY = "cd"
BLOCK_DEVICE_KEY = "bd"
STICKY_KEY = "st"
STICKY_OTHER_WRITABLE_KEY = "tw"
SOCKET_KEY = "so"
MISSING_KEY = "mi"
MULTI_HARDLINK_KEY = "mh"


def _parse_ls_colors(ls_codes):
    color_codes = {}
    for entry in ls_codes.split(":"):
        if "=" not in entry:
            continue
        entry_key, entry_value = entry.split("=")
        if entry_key.startswith("*."):
            entry_key = entry_key[1:]
        color_codes[entry_key] = entry_value
    assert color_codes != {}, color_codes
    return color_codes


_DEFAULT_COLOR_CODES = \
    {BLOCK_DEVICE_KEY: '01;33', SYMLINK_KEY: '01;36',
     STICKY_OTHER_WRITABLE_KEY: '30;42', DIRECTORY_KEY: '01;34',
     SETUID_KEY: '37;41', CHARACTER_DEVICE_KEY: '01;33', SOCKET_KEY: '01;35',
     EXECUTABLE_KEY: '01;32', STICKY_KEY: '37;44',
     OTHER_WRITABLE_KEY: '34;42', PIPE_KEY: '33', SETGUID_KEY: '30;43',
     ORPHAN_KEY: '40;31;01'}


def get_color_codes(environment):
    if "LS_COLORS" in environment:
        try:
            return _parse_ls_colors(environment["LS_COLORS"])
        except:
            syslog.syslog("Syntax error in LS_COLORS environment variable. "
                          "Using default colors.")
    return _DEFAULT_COLOR_CODES


def color_key_for_path(path, color_codes, is_link_target=True):
    # see print_color_indicator in the file 'ls.c' in the coreutils codebase
    if not os.path.lexists(path):
        return MISSING_KEY
    elif os.path.islink(path):
        if is_link_target:
            try:
                link_path = os.path.join(os.path.dirname(path),
                                         os.readlink(path))
                file_stat = os.stat(link_path)
            except OSError:
                return ORPHAN_KEY
        else:
            return SYMLINK_KEY
    else:
        file_stat = os.stat(path)
    mode = file_stat.st_mode
    if stat.S_ISREG(mode):
        if mode & stat.S_ISUID and SETUID_KEY in color_codes:
            return SETUID_KEY
        elif mode & stat.S_ISGID and SETGUID_KEY in color_codes:
            return SETGUID_KEY
        elif ((mode & stat.S_IXUSR or mode & stat.S_IXGRP or
               mode & stat.S_IXOTH) and EXECUTABLE_KEY in color_codes):
            return EXECUTABLE_KEY
        elif file_stat.st_nlink > 1 and MULTI_HARDLINK_KEY in color_codes:
            return MULTI_HARDLINK_KEY
        else:
            return FILE_KEY
    elif stat.S_ISDIR(mode):
        if (mode & stat.S_ISVTX and mode & stat.S_IWOTH and
                STICKY_OTHER_WRITABLE_KEY in color_codes):
            return STICKY_OTHER_WRITABLE_KEY
        elif (mode & stat.S_IWOTH) != 0 and OTHER_WRITABLE_KEY in color_codes:
            return OTHER_WRITABLE_KEY
        elif (mode & stat.S_ISVTX) != 0 and STICKY_KEY in color_codes:
            return STICKY_KEY
        else:
            return DIRECTORY_KEY
    for test_function, color_key in [(stat.S_ISFIFO, PIPE_KEY),
                                     (stat.S_ISSOCK, SOCKET_KEY),
                                     (stat.S_ISBLK, BLOCK_DEVICE_KEY),
                                     (stat.S_ISCHR, CHARACTER_DEVICE_KEY)]:
        if test_function(mode):
            return color_key
    return ORPHAN_KEY


def color_code_for_path(path, color_codes):
    def get_extension(basename, color_codes):
        parts = basename.split(".")
        if len(parts) == 2:
            extension = "." + parts[1]
            if extension in color_codes:
                return extension
        elif len(parts) > 2:
            for extension in color_codes:
                if extension.startswith(".") and \
                   basename.endswith(extension):
                    return extension
    target_link = color_codes.get(SYMLINK_KEY, None)
    color_key = color_key_for_path(path, color_codes,
                                   target_link == "target")
    if color_key == FILE_KEY:
        filename = os.path.basename(path)
        if "." in filename:
            extension = get_extension(filename, color_codes)
            if extension is not None:
                color_key = extension
    return color_codes.get(color_key, None)
