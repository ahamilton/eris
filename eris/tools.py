#!/usr/bin/python3.7
# -*- coding: utf-8 -*-

# Copyright (C) 2015-2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import contextlib
import enum
import functools
import importlib
import importlib.resources
import math
import os
import os.path
import pickle
import pwd
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import traceback

import pygments
import pygments.lexers
import pygments.styles
import toml

import eris
import eris.fill3 as fill3
import eris.gut as gut
import eris.lscolors as lscolors
import eris.termstr as termstr


PYTHON_VERSION = "3.7"
PYTHON_EXECUTABLE = "python" + PYTHON_VERSION
CACHE_PATH = ".eris"


if "PYGMENT_STYLE" not in os.environ:
    os.environ["PYGMENT_STYLE"] = "native"


class Status(enum.IntEnum):

    ok = 1
    problem = 2
    normal = 3
    error = 4
    not_applicable = 5
    running = 6
    pending = 7
    timed_out = 8


_STATUS_COLORS = {Status.ok: termstr.Color.green,
                  Status.problem: termstr.Color.red,
                  Status.normal: termstr.Color.grey_200,
                  Status.not_applicable: termstr.Color.grey_100,
                  Status.running: termstr.Color.blue,
                  Status.timed_out: termstr.Color.purple}
STATUS_MEANINGS = [
    (Status.normal, "Normal"), (Status.ok, "Ok"),
    (Status.problem, "Problem"), (Status.not_applicable, "Not applicable"),
    (Status.running, "Running"), (Status.timed_out, "Timed out"),
    (Status.pending, "Pending"), (Status.error, "Error")
]
STATUS_TO_TERMSTR = {
    status: termstr.TermStr(" ", termstr.CharStyle(bg_color=color))
    for status, color in _STATUS_COLORS.items()}
STATUS_TO_TERMSTR[Status.error] = termstr.TermStr(
    "E", termstr.CharStyle(bg_color=termstr.Color.red))
STATUS_TO_TERMSTR[Status.pending] = "."


def get_ls_color_codes():
    if "LS_COLORS" not in os.environ:
        script = os.path.join(os.path.dirname(__file__), "LS_COLORS.sh")
        with open(script) as file_:
            codes = file_.readline().strip()[len("LS_COLORS='"):-len("';")]
            os.environ["LS_COLORS"] = codes
    return lscolors.get_color_codes(os.environ)


_LS_COLOR_CODES = get_ls_color_codes()
TIMEOUT = 60


def _printable(text):
    return "".join(char if ord(char) > 31 or char in ["\n", "\t"] else "#"
                   for char in text)


def _fix_input(input_):
    return _printable(input_).expandtabs(tabsize=4)


def _do_command(command, **kwargs):
    completed_process = subprocess.run(command, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True,
                                       **kwargs)
    return (_fix_input(completed_process.stdout),
            _fix_input(completed_process.stderr), completed_process.returncode)


def _run_command(command, success_status=None, error_status=None,
                 has_color=False, timeout=None, **kwargs):
    success_status = Status.ok if success_status is None else success_status
    error_status = Status.problem if error_status is None else error_status
    if has_color:
        process = subprocess.run(command, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True,
                                 timeout=timeout, **kwargs)
        stdout, stderr, returncode = (
            termstr.TermStr.from_term(process.stdout),
            termstr.TermStr.from_term(process.stderr), process.returncode)
    else:
        stdout, stderr, returncode = _do_command(command, timeout=timeout)
    result_status = success_status if returncode == 0 else error_status
    return result_status, (stdout + stderr)


def deps(**kwargs):
    def decorating_func(func):
        for key, value in kwargs.items():
            setattr(func, key, value)
        return func
    return decorating_func


def _syntax_highlight(text, lexer, style):
    def _parse_rgb(hex_rgb):
        if hex_rgb.startswith("#"):
            hex_rgb = hex_rgb[1:]
        return tuple(eval("0x"+hex_rgb[index:index+2]) for index in [0, 2, 4])

    def _char_style_for_token_type(token_type, default_bg_color,
                                   default_style):
        try:
            token_style = style.style_for_token(token_type)
        except KeyError:
            return default_style
        fg_color = (termstr.Color.black if token_style["color"] is None
                    else _parse_rgb(token_style["color"]))
        bg_color = (default_bg_color if token_style["bgcolor"] is None
                    else _parse_rgb(token_style["bgcolor"]))
        return termstr.CharStyle(fg_color, bg_color, token_style["bold"],
                                 token_style["italic"],
                                 token_style["underline"])
    default_bg_color = _parse_rgb(style.background_color)
    default_style = termstr.CharStyle(bg_color=default_bg_color)
    text = fill3.join(
        "", [termstr.TermStr(text, _char_style_for_token_type(
            token_type, default_bg_color, default_style))
             for token_type, text in pygments.lex(text, lexer)])
    text_widget = fill3.Text(text, pad_char=termstr.TermStr(" ").bg_color(
        default_bg_color))
    return fill3.join("\n", text_widget.text)


def _syntax_highlight_using_path(text, path):
    lexer = pygments.lexers.get_lexer_for_filename(path, text)
    style = pygments.styles.get_style_by_name(os.environ["PYGMENT_STYLE"])
    return _syntax_highlight(text, lexer, style)


def linguist(path):
    # Dep: ruby?, ruby-dev, libicu-dev, cmake, "gem install github-linguist"
    return _run_command(["linguist", path], Status.normal)


def _permissions_in_octal(permissions):
    result = []
    for part_index in range(3):
        index = part_index * 3 + 1
        part = permissions[index:index+3]
        digit = sum(2 ** (2 - index) for index, element in enumerate(part)
                    if element != "-")
        result.append(str(digit))
    return "".join(result)


def _pretty_bytes(bytes):
    if bytes == 0:
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    unit_index = int(math.floor(math.log(bytes, 1024)))
    power = math.pow(1024, unit_index)
    conversion = round(bytes/power, 2)
    return f"{conversion} {units[unit_index]}"


@deps(deps={"file", "coreutils"}, executables={"file"})
def metadata(path):

    def detail(value, unit):
        result = f" ({value})" if unit is None else f" ({value} {unit})"
        return termstr.TermStr(result).fg_color(termstr.Color.grey_100)
    is_symlink = "yes" if os.path.islink(path) else "no"
    stat_result = os.stat(path)
    permissions = stat.filemode(stat_result.st_mode)
    hardlinks = str(stat_result.st_nlink)
    group = [pwd.getpwuid(stat_result.st_gid).pw_name,
             detail(stat_result.st_gid, "gid")]
    owner = [pwd.getpwuid(stat_result.st_uid).pw_name,
             detail(stat_result.st_uid, "uid")]
    modified, created, access = [
        [time.asctime(time.gmtime(seconds)), detail(int(seconds), "secs")]
        for seconds in (stat_result.st_mtime, stat_result.st_ctime,
                        stat_result.st_atime)]
    size = [_pretty_bytes(stat_result.st_size),
            detail(stat_result.st_size, "bytes")]
    stdout, *rest = _do_command(
        ["file", "--dereference", "--brief", "--uncompress", "--mime", path])
    mime_type = stdout
    stdout, *rest = _do_command(
        ["file", "--dereference", "--brief", "--uncompress", path])
    file_type = stdout
    permissions_value = [permissions,
                         detail(_permissions_in_octal(permissions), None)]
    text = []
    for line in [
            ("size", size), ("permissions", permissions_value), None,
            ("modified time", modified), ("creation time", created),
            ("access time", access), None,
            ("owner", owner), ("group", group), None,
            ("hardlinks", hardlinks), ("symlink", is_symlink), None,
            ("mime type", mime_type.strip()),
            ("file type", file_type.strip())]:
        if line is None:
            text.append("\n")
        else:
            name, value = line
            name = termstr.TermStr(name + ":").fg_color(
                termstr.Color.blue).ljust(16)
            text.append(name + fill3.join("", value) + "\n")
    return (Status.normal, fill3.join("", text))


@deps(deps={"pip/pygments"}, url="python3-pygments")
def contents(path):
    with open(path) as file_:
        try:
            head = file_.read(200)
            tail = file_.read()
        except UnicodeDecodeError:
            return Status.not_applicable, "Not unicode"
    text = _fix_input(head + tail)
    try:
        text = _syntax_highlight_using_path(text, path)
    except pygments.util.ClassNotFound:
        pass
    return Status.normal, text


def _has_shebang_line(path):
    with open(path, "rb") as file_:
        return file_.read(2) == b"#!"


def _is_python_test_file(path):
    path = str(os.path.basename(path))
    return path.endswith("_test.py") or path.startswith("test_")


@deps(url="https://docs.python.org/3/library/unittest.html")
def python_unittests(path):
    if _is_python_test_file(path):
        command = ([path] if _has_shebang_line(path)
                   else [PYTHON_EXECUTABLE, path])
        stdout, stderr, returncode = _do_command(command, timeout=TIMEOUT)
        status = Status.ok if returncode == 0 else Status.problem
        return status, (stdout + "\n" + stderr)
    else:
        return Status.not_applicable, "No tests."


@deps(deps={"pip/pytest", "pip/pytest-cov"},
      url="https://docs.pytest.org/en/latest/", executables={"pytest"})
def pytest(path):
    command = [PYTHON_EXECUTABLE, "-m", "pytest", "--cov=.",
               "--doctest-modules", "--color=yes", path]
    with tempfile.TemporaryDirectory() as temp_dir:
        env = os.environ.copy()
        env["COVERAGE_FILE"] = os.path.join(temp_dir, "coverage")
        process = subprocess.run(command, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True,
                                 timeout=TIMEOUT, env=env)
    stdout, stderr, returncode = (
        termstr.TermStr.from_term(process.stdout),
        termstr.TermStr.from_term(process.stderr), process.returncode)
    if returncode == 5:
        status = Status.not_applicable
    else:
        status = Status.ok if returncode == 0 else Status.problem
    return status, (stdout + stderr)


@deps(deps={"pip/mypy"}, url="http://mypy-lang.org/", executables={"mypy"})
def mypy(path):
    stdout, stderr, returncode = _do_command(
        [PYTHON_EXECUTABLE, "-m", "mypy", "--ignore-missing-imports", path],
        timeout=TIMEOUT)
    status = Status.ok if returncode == 0 else Status.problem
    return status, stdout


def _colorize_coverage_report(lines):
    line_color = {"> ": termstr.Color.green, "! ": termstr.Color.red,
                  "  ": None}
    return fill3.join("", [termstr.TermStr(line).fg_color(line_color[line[:2]])
                           for line in lines])


@deps(deps={"pip/coverage"}, url="https://coverage.readthedocs.io/")
def python_coverage(path):
    coverage_path = ".coverage"
    if not os.path.exists(coverage_path):
        return Status.not_applicable, f'No "{coverage_path}" file.'
    if os.stat(path).st_mtime > os.stat(coverage_path).st_mtime:
        return (Status.not_applicable,
                f'File has been modified since "{coverage_path}"'
                ' file was generated.')
    path = os.path.normpath(path)
    with tempfile.TemporaryDirectory() as temp_dir:
        _do_command([PYTHON_EXECUTABLE, "-m", "coverage",
                     "annotate", "--directory", temp_dir, path])
        cover_filename = path.replace("/", "_") + ",cover"
        with open(os.path.join(temp_dir, cover_filename), "r") as f:
            lines = f.read().splitlines(keepends=True)
    failed_lines = [line for line in lines if line.startswith("! ")]
    status = Status.ok if not failed_lines else Status.normal
    return status, _colorize_coverage_report(lines)


@deps(url="https://github.com/ahamilton/eris/blob/master/gut.py")
def python_gut(path):
    with open(path) as module_file:
        output = gut.gut_module(module_file.read())
    source_widget = _syntax_highlight_using_path(_fix_input(output), path)
    return Status.normal, source_widget


def _get_mccabe_line_score(line):
    position, function_name, score = line.split()
    return int(score)


def _colorize_mccabe(text):
    return fill3.join("", [
        termstr.TermStr(line).fg_color(termstr.Color.yellow)
        if _get_mccabe_line_score(line) > 10 else line
        for line in text.splitlines(keepends=True)])


@deps(deps={"pip/mccabe"}, url="https://pypi.org/project/mccabe/")
def python_mccabe(path):
    stdout, *rest = _do_command([PYTHON_EXECUTABLE, "-m", "mccabe", path])
    max_score = 0
    with contextlib.suppress(ValueError):  # When there are no lines
        max_score = max(_get_mccabe_line_score(line)
                        for line in stdout.splitlines())
    status = Status.problem if max_score > 10 else Status.ok
    return status, _colorize_mccabe(stdout)


# FIX: Reenable when pydisasm is not causing problems
# @deps(deps={"pip/xdis"}, executables={"pydisasm"},
#       url="https://pypi.python.org/pypi/xdis")
# def pydisasm(path):
#     return _run_command(["pydisasm", path], Status.normal,
#                         Status.not_applicable)


@deps(deps={"perltidy"}, url="http://perltidy.sourceforge.net/",
      executables={"perltidy"})
def perltidy(path):
    stdout, *rest = _do_command(["perltidy", "-st", path])
    return Status.normal, _syntax_highlight_using_path(stdout, path)


@deps(deps={"tidy"}, url="tidy", executables={"tidy"})
def html_syntax(path):
    # Stop tidy from modifiying input path by piping in input.
    tidy_process = subprocess.run(f"cat {shlex.quote(path)} | tidy",
                                  capture_output=True, text=True, shell=True)
    status = Status.ok if tidy_process.returncode == 0 else Status.problem
    return status, _fix_input(tidy_process.stderr)


@deps(deps={"pandoc"}, url="pandoc", executables={"pandoc"})
def pandoc(path):
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = os.path.join(temp_dir, "temp.html")
        _do_command(["pandoc", "-t", "html", "-o", temp_path, path])
        return elinks(temp_path)


MAX_IMAGE_SIZE = 200


def _resize_image(image, new_width):
    import PIL.Image  # Here to avoid 'Segmentation Fault' in install-tools
    scale = new_width / image.width
    return image.resize((int(image.width * scale), int(image.height * scale)),
                        PIL.Image.ANTIALIAS)


def _image_to_text(image):
    text = "▀" * image.width
    data = list(image.getdata())
    width = image.width
    rows = [data[row_index*width:(row_index+1)*width]
            for row_index in range(image.height)]
    if image.height % 2 == 1:
        rows.append([None] * image.width)
    return fill3.join("\n", [
        termstr.TermStr(text, tuple(termstr.CharStyle(
            fg_color=top_pixel, bg_color=bottom_pixel)
            for top_pixel, bottom_pixel in zip(rows[index],
                                               rows[index+1])))
        for index in range(0, image.height, 2)])


@deps(deps={"pip/pillow"}, url="http://python-pillow.github.io/")
def pil(path):
    import PIL.Image
    with open(path, "rb") as image_file:
        with PIL.Image.open(image_file).convert("RGB") as image:
            if image.width > MAX_IMAGE_SIZE:
                image = _resize_image(image, MAX_IMAGE_SIZE)
            return Status.normal, _image_to_text(image)


@deps(deps={"pip/svglib"}, url="https://github.com/deeplook/svglib")
def svglib(path):
    import svglib.svglib
    import reportlab.graphics.renderPM
    drawing = svglib.svglib.svg2rlg(path)
    image = reportlab.graphics.renderPM.drawToPIL(drawing)
    if image.width > MAX_IMAGE_SIZE:
        image = _resize_image(image, MAX_IMAGE_SIZE)
    return Status.normal, _image_to_text(image)


@deps(deps={"go/github.com/golang/go/src/cmd/godoc"},
      url="https://github.com/golang/go", executables={"godoc"})
def godoc(path):
    with tempfile.TemporaryDirectory() as temp_dir:
        symlink_path = os.path.join(temp_dir, "file.go")
        os.symlink(os.path.abspath(path), symlink_path)
        stdout, stderr, returncode = _do_command(["godoc", "."], cwd=temp_dir)
        os.remove(symlink_path)
    return Status.normal, stdout


def make_tool_function(dependencies, command, url=None, success_status=None,
                       error_status=None, has_color=False, timeout=None):
    if url is None:
        url = dependencies[0]
    command = command.split()
    executables = set([command[0]])
    success_status = None if success_status is None else Status[success_status]
    error_status = None if error_status is None else Status[error_status]
    @deps(deps=set(dependencies), url=url, executables=executables)
    def func(path):
        return _run_command(command + [path], success_status, error_status,
                            has_color, timeout)
    return func


elinks, git_blame, git_log = None, None, None  # For linters.
with importlib.resources.open_text(eris, "tools.toml") as tools_toml_file:
    tools_toml = toml.load(tools_toml_file)
tools_for_extensions = tools_toml["tools_for_extensions"]
del tools_toml["tools_for_extensions"]
for tool_name, tool_toml in tools_toml.items():
    tool_func = make_tool_function(**tool_toml)
    tool_func.__name__ = tool_func.__qualname__ = tool_name
    globals()[tool_name] = tool_func

#############################


def log_error(message=None):
    message = traceback.format_exc() if message is None else message + "\n"
    with open("/tmp/eris.log", "a") as log_file:
        log_file.write(message)


def lru_cache_with_eviction(maxsize=128, typed=False):
    versions = {}
    make_key = functools._make_key

    def evict(*args, **kwds):
        key = make_key(args, kwds, typed)
        if key in versions:
            versions[key] += 1

    def decorating_function(user_function):

        def remove_version(*args, **kwds):
            return user_function(*args[1:], **kwds)
        new_func = functools.lru_cache(maxsize=maxsize, typed=typed)(
            remove_version)

        def add_version(*args, **kwds):
            key = make_key(args, kwds, typed)
            return new_func(*((versions.setdefault(key, 0),) + args), **kwds)
        add_version.versions = versions
        add_version.cache_info = new_func.cache_info
        add_version.evict = evict
        return functools.update_wrapper(add_version, user_function)
    return decorating_function


def dump_pickle_safe(object_, path, protocol=pickle.HIGHEST_PROTOCOL,
                     open=open):
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "wb") as file_:
            pickle.dump(object_, file_, protocol=protocol)
    except (OSError, KeyboardInterrupt):
        os.remove(tmp_path)
    else:
        os.rename(tmp_path, path)


@functools.lru_cache()
def compression_open_func(compression):
    return (open if compression == "none" else
            importlib.import_module(compression).open)


class Result:

    COMPLETED_STATUSES = {
        Status.ok, Status.problem, Status.normal, Status.error,
        Status.not_applicable, Status.timed_out}

    def __init__(self, path, tool):
        self.path = path
        self.tool = tool
        self.compression = None
        self.pickle_path = os.path.join(CACHE_PATH, path + "-" + tool.__name__)
        self.scroll_position = (0, 0)
        self.status = Status.pending

    @property
    @lru_cache_with_eviction(maxsize=50)
    def result(self):
        unknown_label = fill3.Text("?")
        if self.status == Status.pending or self.compression is None:
            return unknown_label
        try:
            with compression_open_func(self.compression)(
                    self.pickle_path, "rb") as pickle_file:
                return pickle.load(pickle_file)
        except FileNotFoundError:
            return unknown_label

    @result.setter
    def result(self, value):
        os.makedirs(os.path.dirname(self.pickle_path), exist_ok=True)
        dump_pickle_safe(value, self.pickle_path,
                         open=compression_open_func(self.compression))
        Result.result.fget.evict(self)

    def set_status(self, status):
        self.status = status
        self.entry.appearance_cache = None

    @property
    def is_completed(self):
        return self.status in Result.COMPLETED_STATUSES

    async def run(self, log, appearance_changed_event, runner):
        tool_name = tool_name_colored(self.tool, self.path)
        path = path_colored(self.path)
        log.log_message(["Running ", tool_name, " on ", path, "…"])
        self.set_status(Status.running)
        appearance_changed_event.set()
        start_time = time.time()
        new_status = await runner.run_tool(self.path, self.tool)
        Result.result.fget.evict(self)
        end_time = time.time()
        self.set_status(new_status)
        appearance_changed_event.set()
        log.log_message(
            ["Finished running ", tool_name, " on ", path, ". ",
             STATUS_TO_TERMSTR[new_status],
             f" {round(end_time - start_time, 2)} secs"])

    def reset(self):
        self.set_status(Status.pending)

    def appearance_min(self):
        return [STATUS_TO_TERMSTR[self.status]]

    def get_pages_dir(self):
        return self.pickle_path + ".pages"

    def delete(self):
        with contextlib.suppress(FileNotFoundError):
            os.remove(self.pickle_path)
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(self.get_pages_dir())
        Result.result.fget.evict(self)

    def as_html(self):
        html, styles = termstr.TermStr(
            STATUS_TO_TERMSTR[self.status]).as_html()
        return (f'<a title="{self.tool.__name__}" '
                f'href="{self.path}/{self.tool.__name__}">{html}</a>', styles)


def generic_tools():
    return [contents, metadata]


TOOLS_FOR_EXTENSIONS = []
for extensions, tool_names in tools_for_extensions:
    TOOLS_FOR_EXTENSIONS.append(
        (extensions, [globals()[tool_name] for tool_name in tool_names]))


@functools.lru_cache(maxsize=1)
def _tools_for_extension():
    result = {}
    for extensions, tools in TOOLS_FOR_EXTENSIONS:
        for extension in extensions:
            result[extension] = tools
    return result


def tools_all():
    tools_ = set(generic_tools())
    tools_.add(git_blame)
    tools_.add(git_log)
    for tool_list in _tools_for_extension().values():
        tools_.update(set(tool_list))
    return tools_


def tool_dependencies(tool):
    try:
        return tool.deps
    except AttributeError:
        return set()


def dependencies():
    dependencies_all = set()
    for tool in tools_all():
        dependencies_all.update(tool_dependencies(tool))
    return dependencies_all


def splitext(path):
    root, ext = os.path.splitext(path)
    if "." in root:
        for compound_ext in [".tar.gz", ".tar.bz2"]:
            if path.endswith(compound_ext):
                return path[:-len(compound_ext)], path[-len(compound_ext):]
    return root, ext


@functools.lru_cache()
def is_tool_available(tool):
    try:
        return all(shutil.which(executable) for executable in tool.executables)
    except AttributeError:
        return True


def tools_for_path(path):
    git_tools = [git_blame, git_log] if os.path.exists(".git") else []
    root, ext = splitext(path)
    extra_tools = [] if ext == "" else _tools_for_extension().get(ext[1:], [])
    tools = generic_tools() + git_tools + extra_tools
    return [tool for tool in tools if is_tool_available(tool)]


def run_tool_no_error(path, tool):
    try:
        return tool(path)
    except subprocess.TimeoutExpired:
        return Status.timed_out, "Timed out"
    except UnicodeDecodeError:
        return Status.not_applicable, "Result not in UTF-8"
    except Exception:
        return Status.error, _syntax_highlight(
            traceback.format_exc(), pygments.lexers.PythonTracebackLexer(),
            pygments.styles.get_style_by_name(os.environ["PYGMENT_STYLE"]))


def _convert_lscolor_code_to_charstyle(lscolor_code):
    parts = lscolor_code.split(";")
    if len(parts) == 1:
        is_bold = parts[0] == "1"
        fg_color = None
    elif len(parts) == 2:
        is_bold = False
        fg_color = int(parts[1])
    else:
        is_bold = len(parts) == 4 and parts[3] == "1"
        fg_color = int(parts[2])
    return termstr.CharStyle(fg_color=fg_color, is_bold=is_bold)


def _charstyle_of_path(path):
    color_code = lscolors.color_code_for_path(path, _LS_COLOR_CODES)
    return (termstr.CharStyle() if color_code is None else
            _convert_lscolor_code_to_charstyle(color_code))


@functools.lru_cache(maxsize=100)
def path_colored(path):
    char_style = _charstyle_of_path(path)
    path = path[2:]
    dirname, basename = os.path.split(path)
    if dirname == "":
        return termstr.TermStr(basename, char_style)
    else:
        dirname = dirname + os.path.sep
        dir_style = _charstyle_of_path(os.path.sep)
        parts = [termstr.TermStr(part, dir_style)
                 for part in dirname.split(os.path.sep)]
        path_sep = termstr.TermStr(os.path.sep).fg_color(
            termstr.Color.grey_100)
        dir_name = fill3.join(path_sep, parts)
        return dir_name + termstr.TermStr(basename, char_style)


@functools.lru_cache(maxsize=100)
def tool_name_colored(tool, path):
    char_style = (termstr.CharStyle(is_bold=True) if tool in generic_tools()
                  else _charstyle_of_path(path))
    return termstr.TermStr(tool.__name__, char_style)


@functools.lru_cache()
def get_homepage_of_package(package):
    line = subprocess.getoutput(f"dpkg-query --status {package}|grep Homepage")
    return line.split()[1]


def url_of_tool(tool):
    try:
        url = tool.url
        return url if url.startswith("http") else get_homepage_of_package(url)
    except AttributeError:
        return None


if __name__ == "__main__":
    tool_name, path = sys.argv[1:3]
    tool = locals()[tool_name]
    valid_tools = tools_for_path(path)
    assert tool in valid_tools, valid_tools
    status, text = run_tool_no_error(path, tool)
    print(text)
    sys.exit(0 if status in [Status.ok, Status.normal] else 1)
