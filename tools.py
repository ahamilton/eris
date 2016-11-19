# -*- coding: utf-8 -*-

# Copyright (C) 2015-2016 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import ast
import contextlib
import dis
import enum
import functools
import gzip
import hashlib
import io
import math
import os
import os.path
import pickle
import pwd
import stat
import subprocess
import tempfile
import time
import traceback

import pygments
import pygments.lexers
import pygments.styles

import fill3
import gut
import lscolors
import termstr


CACHE_PATH = ".vigil"


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
    paused = 8
    timed_out = 9


_STATUS_COLORS = {Status.ok: termstr.Color.green,
                  Status.problem: termstr.Color.red,
                  Status.normal: termstr.Color.white,
                  Status.not_applicable: termstr.Color.grey_100,
                  Status.running: termstr.Color.light_blue,
                  Status.paused: termstr.Color.yellow,
                  Status.timed_out: termstr.Color.purple}
STATUS_MEANINGS = [
    (Status.normal, "Normal"), (Status.ok, "Ok"),
    (Status.problem, "Problem"), (Status.not_applicable, "Not applicable"),
    (Status.running, "Running"), (Status.paused, "Paused"),
    (Status.timed_out, "Timed out"), (Status.pending, "Pending"),
    (Status.error, "Error")
]
_STATUS_TO_TERMSTR = {
    status: termstr.TermStr(" ", termstr.CharStyle(bg_color=color))
    for status, color in _STATUS_COLORS.items()}
_STATUS_TO_TERMSTR[Status.error] = termstr.TermStr(
    "E", termstr.CharStyle(bg_color=termstr.Color.red))
_STATUS_TO_TERMSTR[Status.pending] = "."
STATUS_CURSOR_COLORS = {Status.ok: termstr.Color.black,
                        Status.problem: termstr.Color.white,
                        Status.normal: termstr.Color.black,
                        Status.not_applicable: termstr.Color.white,
                        Status.running: termstr.Color.white,
                        Status.paused: termstr.Color.black,
                        Status.timed_out: termstr.Color.white}


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
    input_str = input_.decode("utf-8") if isinstance(input_, bytes) else input_
    return _printable(input_str).expandtabs(tabsize=4)


def _do_command(command, timeout=None, **kwargs):
    stdout, stderr = "", ""
    with contextlib.suppress(subprocess.CalledProcessError):
        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, **kwargs)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            raise
    return _fix_input(stdout), _fix_input(stderr), process.returncode


def _run_command(command, status_text=Status.ok):
    status, output = status_text, ""
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        output = stdout + stderr
    except subprocess.CalledProcessError:
        status = Status.problem
    if process.returncode != 0:
        status = Status.problem
    return status, fill3.Text(_fix_input(output))


def _syntax_highlight(text, lexer, style):
    def _parse_rgb(hex_rgb):
        if hex_rgb.startswith("#"):
            hex_rgb = hex_rgb[1:]
        return tuple(eval("0x"+hex_rgb[index:index+2]) for index in [0, 2, 4])

    def _char_style_for_token_type(token_type, default_bg_color):
        token_style = style.style_for_token(token_type)
        fg_color = (termstr.Color.black if token_style["color"] is None
                    else _parse_rgb(token_style["color"]))
        bg_color = (default_bg_color if token_style["bgcolor"] is None
                    else _parse_rgb(token_style["bgcolor"]))
        return termstr.CharStyle(fg_color, bg_color, token_style["bold"],
                                 token_style["italic"],
                                 token_style["underline"])
    default_bg_color = _parse_rgb(style.background_color)
    text = fill3.join(
        "", [termstr.TermStr(text, _char_style_for_token_type(
            token_type, default_bg_color))
             for token_type, text in pygments.lex(text, lexer)])
    return fill3.Text(text, pad_char=termstr.TermStr(" ").bg_color(
        default_bg_color))


def _syntax_highlight_using_path(text, path):
    lexer = pygments.lexers.get_lexer_for_filename(path, text)
    style = pygments.styles.get_style_by_name(os.environ["PYGMENT_STYLE"])
    return _syntax_highlight(text, lexer, style)


def pygments_(path):
    with open(path) as file_:
        try:
            text = file_.read()
        except UnicodeDecodeError:
            return Status.not_applicable, fill3.Text("Not unicode")
        else:
            try:
                source_widget = _syntax_highlight_using_path(_fix_input(text),
                                                             path)
            except pygments.util.ClassNotFound:
                return Status.normal, fill3.Text(text)
    return Status.normal, source_widget


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
    return "%s %s" % (conversion, units[unit_index])


def _md5(path):
    with open(path, "rb") as file:
        return hashlib.md5(file.read()).hexdigest()


def metadata(path):

    def detail(value, unit):
        result = (" (%s)" % value if unit is None else " (%s %s)" %
                  (value, unit))
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
    md5sum = _md5(path)
    stdout, *rest = _do_command(["sha1sum", path])
    sha1sum = stdout.split()[0]
    permissions_value = [permissions,
                         detail(_permissions_in_octal(permissions), None)]
    text = []
    for line in [
            ("size", size), ("permissions", permissions_value), None,
            ("modified time", modified), ("creation time", created),
            ("access time", access), None,
            ("owner", owner), ("group", group), None,
            ("hardlinks", hardlinks), ("symlink", is_symlink), None,
            ("md5", md5sum), ("sha1", sha1sum), None,
            ("mime type", mime_type.strip()),
            ("file type", file_type.strip())]:
        if line is None:
            text.append("\n")
        else:
            name, value = line
            name = termstr.TermStr(name + ":").fg_color(
                termstr.Color.light_blue).ljust(16)
            text.append(name + fill3.join("", value) + "\n")
    return (Status.normal, fill3.Text(fill3.join("", text)))
metadata.dependencies = {"file", "coreutils"}


def contents(path):
    root, ext = splitext(path)
    if ext == "":
        with open(path) as file_:
            return Status.normal, fill3.Text(_fix_input(file_.read()))
    else:
        return pygments_(path)
contents.dependencies = {"python3-pygments"}


def _is_python_syntax_correct(path, python_version):
    if python_version == "python":
        stdin, stdout, returncode = _do_command(
            ["python", "-c",
             "__import__('compiler').parse(open('%s').read())" % path])
        return returncode == 0
    else:  # python3
        with open(path) as f:
            source = f.read()
        try:
            ast.parse(source)
        except:
            return False
        return True


def _python_version(path):  # Need a better hueristic
    for version in ["python3", "python"]:
        if _is_python_syntax_correct(path, version):
            return version
    return "python3"


def python_syntax(path):
    python_version = _python_version(path)
    return _run_command([python_version, "-m", "py_compile", path])
python_syntax.dependencies = {"python", "python3"}


def _has_shebang_line(path):
    with open(path, "rb") as file_:
        return file_.read(2) == "#!"


def _is_python_test_file(path):
    path = str(os.path.basename(path))
    return path.endswith("_test.py") or path.startswith("test_")


def python_unittests(path):
    if _is_python_test_file(path):
        command = ([path] if _has_shebang_line(path)
                   else [_python_version(path), path])
        stdout, stderr, returncode = _do_command(command, timeout=TIMEOUT)
        status = Status.ok if returncode == 0 else Status.problem
        return status, fill3.Text(stdout + "\n" + stderr)
    else:
        return Status.not_applicable, fill3.Text("No tests.")
python_unittests.dependencies = {"python", "python3"}


def pydoc(path):
    pydoc_exe = "pydoc3" if _python_version(path) == "python3" else "pydoc"
    status, output = Status.normal, ""
    try:
        output = subprocess.check_output([pydoc_exe, path], timeout=TIMEOUT)
        output = _fix_input(output)
    except subprocess.CalledProcessError:
        status = Status.not_applicable
    if not output.startswith("Help on module"):
        status = Status.not_applicable
    return status, fill3.Text(output)
pydoc.dependencies = {"python", "python3"}


def mypy(path):
    stdout, stderr, returncode = _do_command(["mypy", path], timeout=TIMEOUT)
    status = Status.ok if returncode == 0 else Status.normal
    return status, fill3.Text(stdout)
mypy.dependencies = {"mypy"}


def _colorize_coverage_report(text):
    line_color = {"> ": termstr.Color.green, "! ": termstr.Color.red,
                  "  ": None}
    return fill3.join("", [termstr.TermStr(line).fg_color(line_color[line[:2]])
                           for line in text.splitlines(keepends=True)])


def python_coverage(path):
    # FIX: Also use test_*.py files.
    test_path = path[:-(len(".py"))] + "_test.py"
    if os.path.exists(test_path):
        with tempfile.TemporaryDirectory() as temp_dir:
            python_exe = "%s-coverage" % _python_version(path)
            coverage_path = os.path.join(temp_dir, "coverage")
            env = os.environ.copy()
            env["COVERAGE_FILE"] = coverage_path
            stdout, *rest = _do_command(
                [python_exe, "run", test_path], env=env, timeout=TIMEOUT)
            path = os.path.normpath(path)
            stdout, *rest = _do_command([python_exe, "annotate", "--directory",
                                         temp_dir, path], env=env)
            flat_path = path.replace("/", "_")
            with open(os.path.join(temp_dir, flat_path + ",cover"), "r") as f:
                stdout = f.read()
        return Status.normal, fill3.Text(_colorize_coverage_report(stdout))
    else:
        return Status.not_applicable, fill3.Text(
            "No corresponding test file: " + os.path.normpath(test_path))
python_coverage.dependencies = {"python-coverage", "python3-coverage"}


def python_profile(path):
    stdout, *rest = _do_command([_python_version(path), "-m", "cProfile",
                                 "--sort=cumulative", path], timeout=TIMEOUT)
    return Status.normal, fill3.Text(stdout)
python_profile.dependencies = {"python", "python3"}


def pycodestyle(path):
    cmd = (["pycodestyle"] if _python_version(path) == "python"
           else ["python3", "-m", "pycodestyle"])
    return _run_command(cmd + [path])
pycodestyle.dependencies = {"pycodestyle", "python3-pycodestyle"}


def pyflakes(path):
    return _run_command([_python_version(path), "-m", "pyflakes", path])
pyflakes.dependencies = {"pyflakes"}


def pylint(path):
    return _run_command([_python_version(path), "-m", "pylint",
                         "--errors-only", path])
pylint.dependencies = {"pylint", "pylint3"}


def python_gut(path):
    with open(path) as module_file:
        output = gut.gut_module(module_file.read())
    source_widget = _syntax_highlight_using_path(_fix_input(output), path)
    return Status.normal, source_widget
python_gut.dependencies = set()


def python_modulefinder(path):
    return _run_command([_python_version(path), "-m", "modulefinder", path],
                        Status.normal)
python_modulefinder.dependencies = {"python", "python3"}


def _get_mccabe_line_score(line, python_version):
    position, function_name, score = line.split()
    return int(score if python_version == "python3" else score[:-1])


def _colorize_mccabe(text, python_version):
    return fill3.join("", [
        termstr.TermStr(line).fg_color(termstr.Color.yellow)
        if _get_mccabe_line_score(line, python_version) > 10 else line
        for line in text.splitlines(keepends=True)])


def python_mccabe(path):
    python_version = _python_version(path)
    stdout, *rest = _do_command([python_version, "-m", "mccabe", path])
    max_score = 0
    with contextlib.suppress(ValueError):  # When there are no lines
        max_score = max(_get_mccabe_line_score(line, python_version)
                        for line in stdout.splitlines())
    status = Status.problem if max_score > 10 else Status.ok
    return status, fill3.Text(_colorize_mccabe(stdout, python_version))
python_mccabe.dependencies = {"python-mccabe", "python3-mccabe"}


def python_tidy(path):  # Deps: found on internet?
    stdout, *rest = _do_command(["python", "python-tidy.py", path])
    return Status.normal, _syntax_highlight_using_path(stdout, path)


def disassemble_pyc(path):
    with open(path, "rb") as file_:
        bytecode = file_.read()
    stringio = io.StringIO()
    dis.dis(bytecode, file=stringio)
    stringio.seek(0)
    return Status.normal, fill3.Text(stringio.read())
disassemble_pyc.dependencies = set()


def bandit(path):
    python_version = _python_version(path)
    stdout, stderr, returncode = _do_command(
        [python_version, "-m", "bandit.cli.main", "-f", "txt", path],
        timeout=TIMEOUT)
    status = Status.ok if returncode == 0 else Status.normal
    text = stdout if python_version == "python" else _fix_input(eval(stdout))
    text_without_timestamp = "".join(text.splitlines(keepends=True)[2:])
    return status, fill3.Text(text_without_timestamp)
bandit.dependencies = {"python-bandit", "python3-bandit"}
bandit.url = "python3-bandit"


def _perl_version(path):
    # stdout, stderr, returncode = _do_command(["perl", "-c", path])
    # return "perl6" if "Perl v6.0.0 required" in stderr else "perl"
    return "perl"


def perl_syntax(path):
    return _run_command([_perl_version(path), "-c", path])
# perl_syntax.dependencies = {"perl", "rakudo"}
perl_syntax.dependencies = {"perl"}


def perldoc(path):
    stdout, stderr, returncode = _do_command(["perldoc", "-t", path])
    return ((Status.normal, fill3.Text(stdout)) if returncode == 0
            else (Status.not_applicable, fill3.Text(stderr)))
perldoc.dependencies = {"perl-doc"}


def perltidy(path):
    stdout, *rest = _do_command(["perltidy", "-st", path])
    return Status.normal, _syntax_highlight_using_path(stdout, path)
perltidy.dependencies = {"perltidy"}


# def perl6_syntax(path):
#     return _run_command(["perl6", "-c", path])
# perl6_syntax.dependencies = {"rakudo"}


def splint(path):
    stdout, stderr, returncode = _do_command(["splint", "-preproc", path])
    status = Status.ok if returncode == 0 else Status.problem
    return status, fill3.Text(stdout + stderr)
splint.dependencies = {"splint"}


def objdump_headers(path):
    return _run_command(["objdump", "--all-headers", path], Status.normal)
objdump_headers.dependencies = {"binutils"}


def objdump_disassemble(path):
    return _run_command(
        ["objdump", "--disassemble", "--reloc", "--dynamic-reloc", path],
        Status.normal)
objdump_disassemble.dependencies = {"binutils"}


def readelf(path):
    return _run_command(["readelf", "--all", path], Status.normal)
readelf.dependencies = {"binutils"}


def unzip(path):
    return _run_command(["unzip", "-l", path], Status.normal)
unzip.dependencies = {"unzip"}


def tar_gz(path):
    return _run_command(["tar", "ztvf", path], Status.normal)
tar_gz.dependencies = {"tar"}


def tar_bz2(path):
    return _run_command(["tar", "jtvf", path], Status.normal)
tar_bz2.dependencies = {"tar"}


def nm(path):
    return _run_command(["nm", "--demangle", path], Status.normal)
nm.dependencies = {"binutils"}


def pdf2txt(path):
    return _run_command(["pdf2txt", path], Status.normal)
pdf2txt.dependencies = {"python-pdfminer"}


def html_syntax(path):
    # Maybe only show errors
    stdout, stderr, returncode = _do_command(["tidy", path])
    status = Status.ok if returncode == 0 else Status.problem
    return status, fill3.Text(stderr)
html_syntax.dependencies = {"tidy"}


def tidy(path):
    stdout, *rest = _do_command(["tidy", path])
    return Status.normal, fill3.Text(stdout)
tidy.dependencies = {"tidy"}


def html2text(path):
    return _run_command(["html2text", path], Status.normal)
html2text.dependencies = {"html2text"}


def bcpp(path):
    stdout, stderr, returncode = _do_command(["bcpp", "-fi", path])
    status = Status.normal if returncode == 0 else Status.problem
    return status, _syntax_highlight_using_path(stdout, path)
bcpp.dependencies = {"bcpp"}


def uncrustify(path):
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "uncrustify.cfg")
        stdout, stderr, returncode = _do_command(
            ["uncrustify", "--detect", "-f", path, "-o", config_path])
        if returncode == 0:
            stdout, stderr, returncode = _do_command(
                ["uncrustify", "-c", config_path, "-f", path])
    status = Status.normal if returncode == 0 else Status.problem
    return status, _syntax_highlight_using_path(stdout, path)
uncrustify.dependencies = {"uncrustify"}


def php5_syntax(path):
    return _run_command(["php", "--syntax-check", path])
php5_syntax.dependencies = {"php"}


#############################


LOG_PATH = os.path.join(os.getcwd(), "vigil.log")


def log_error(message=None):
    message = traceback.format_exc() if message is None else message + "\n"
    with open(LOG_PATH, "a") as log_file:
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


def status_to_str(status):
    return (_STATUS_TO_TERMSTR[status] if isinstance(status, enum.Enum)
            else status)


class Result:

    def __init__(self, path, tool):
        self.path = path
        self.tool = tool
        self.pickle_path = os.path.join(CACHE_PATH, path + "-" + tool.__name__)
        self.scroll_position = (0, 0)
        self.is_completed = False
        self.is_placeholder = True
        self.status = Status.pending

    @property
    @lru_cache_with_eviction(maxsize=50)
    def result(self):
        unknown_label = fill3.Text("?")
        if self.is_placeholder:
            return unknown_label
        try:
            with gzip.open(self.pickle_path, "rb") as pickle_file:
                return pickle.load(pickle_file)
        except FileNotFoundError:
            return unknown_label

    @result.setter
    def result(self, value):
        os.makedirs(os.path.dirname(self.pickle_path), exist_ok=True)
        dump_pickle_safe(value, self.pickle_path, open=gzip.open)
        Result.result.fget.evict(self)

    def set_status(self, status):
        self.status = status
        self.entry.appearance_cache = None

    async def run(self, log, appearance_changed_event, runner):
        self.is_placeholder = False
        tool_name = tool_name_colored(self.tool, self.path)
        path = path_colored(self.path)
        log.log_message(["Running ", tool_name, " on ", path, "..."])
        self.set_status(Status.running)
        if runner.is_already_paused:
            runner.is_already_paused = False
            runner.pause()
        appearance_changed_event.set()
        start_time = time.time()
        new_status = await runner.run_tool(self.path, self.tool)
        Result.result.fget.evict(self)
        end_time = time.time()
        self.set_status(new_status)
        appearance_changed_event.set()
        self.is_completed = True
        log.log_message(
            ["Finished running ", tool_name, " on ", path, ". ",
             status_to_str(new_status), " %s secs" %
             round(end_time - start_time, 2)])

    def reset(self):
        self.is_placeholder = True
        self.set_status(Status.pending)

    def appearance_min(self):
        return [status_to_str(self.status)]


def _generic_tools():
    return [contents, metadata]


TOOLS_FOR_EXTENSIONS = \
    [
        (["py"], [python_syntax, python_unittests, pydoc, mypy, python_coverage,
                  python_profile, pycodestyle, pyflakes, pylint, python_gut,
                  python_modulefinder, python_mccabe, bandit]),
        (["pyc"], [disassemble_pyc]),
        (["pl", "pm", "t"], [perl_syntax, perldoc, perltidy]),
        # (["p6", "pm6"], [perl6_syntax, perldoc]),
        (["pod", "pod6"], [perldoc]),
        (["java"], [uncrustify]),
        (["c", "h"], [splint, uncrustify]),
        (["o"], [objdump_headers, objdump_disassemble, readelf]),
        (["cpp"], [bcpp, uncrustify]),
        (["pdf"], [pdf2txt]),
        (["html"], [html_syntax, tidy, html2text]),
        (["php"], [php5_syntax]),
        (["zip"], [unzip]),
        (["tar.gz", "tgz"], [tar_gz]),
        (["tar.bz2"], [tar_bz2]),
        (["a", "so"], [nm]),
    ]


@functools.lru_cache(maxsize=1)
def _tools_for_extension():
    result = {}
    for extensions, tools in TOOLS_FOR_EXTENSIONS:
        for extension in extensions:
            result[extension] = tools
    return result


def tools_all():
    tools_ = set(_generic_tools())
    for tool_list in _tools_for_extension().values():
        tools_.update(set(tool_list))
    return tools_


def dependencies():
    dependencies_all = set()
    for tool in tools_all():
        dependencies_all.update(tool.dependencies)
    return dependencies_all


def splitext(path):
    root, ext = os.path.splitext(path)
    if "." in root:
        for compound_ext in [".tar.gz", ".tar.bz2"]:
            if path.endswith(compound_ext):
                return path[:-len(compound_ext)], path[-len(compound_ext):]
    return root, ext


def tools_for_path(path):
    root, ext = splitext(path)
    extra_tools = [] if ext == "" else _tools_for_extension().get(ext[1:], [])
    return _generic_tools() + extra_tools


def run_tool_no_error(path, tool):
    try:
        status, result = tool(path)
    except subprocess.TimeoutExpired:
        status, result = Status.timed_out, fill3.Text("Timed out")
    except:
        status, result = Status.error, _syntax_highlight(
            traceback.format_exc(), pygments.lexers.PythonTracebackLexer(),
            pygments.styles.get_style_by_name(os.environ["PYGMENT_STYLE"]))
    return status, result


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
        return (termstr.TermStr(dirname, _charstyle_of_path(dirname)) +
                termstr.TermStr(basename, char_style))


@functools.lru_cache(maxsize=100)
def tool_name_colored(tool, path):
    char_style = (termstr.CharStyle(is_bold=True) if tool in _generic_tools()
                  else _charstyle_of_path(path))
    return termstr.TermStr(tool.__name__, char_style)


@functools.lru_cache()
def get_homepage_of_package(package):
    line = subprocess.getoutput("dpkg-query --status %s | grep Homepage" % package)
    return line.split()[1]


def url_of_tool(tool):
    try:
        url = tool.url
        return url if url.startswith("http") else get_homepage_of_package(url)
    except AttributeError:
        return None
