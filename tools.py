# -*- coding: utf-8 -*-

# Copyright (C) 2015-2016 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import ast
import contextlib
import dis
import functools
import hashlib
import io
import math
import os
import os.path
import pickle
import pprint
import pwd
import stat
import subprocess
import tempfile
import time

import lscolors
import pygments
import pygments.lexers
import pygments.styles
import traceback

import fill3
import gut
import termstr


class Status:

    success = 1
    failure = 2
    info = 3
    error = 4
    placeholder = 5
    running = 6
    empty = 7
    paused = 8


_STATUS_COLORS = [(Status.success, termstr.Color.green),
                  (Status.failure, termstr.Color.red),
                  (Status.info, termstr.Color.white),
                  (Status.placeholder, termstr.Color.grey_100),
                  (Status.running, termstr.Color.yellow)]


STATUS_MEANINGS = [
    (Status.info, "Normal"), (Status.success, "No problems"),
    (Status.failure, "Problems"), (Status.placeholder, "Not applicable"),
    (Status.running, "Running"), (Status.empty, "Pending"),
    (Status.error, "Error")]
_STATUS_TO_TERMSTR = {
    status: termstr.TermStr(" ", termstr.CharStyle(fg_color=color))
    for status, color in _STATUS_COLORS}
_STATUS_TO_TERMSTR[Status.error] = termstr.TermStr(
    "E ", termstr.CharStyle(fg_color=termstr.Color.red))
_STATUS_TO_TERMSTR[Status.empty] = ". "
_STATUS_TO_TERMSTR_SIMPLE = {
    status: termstr.TermStr(" ", termstr.CharStyle(bg_color=color))
    for status, color in _STATUS_COLORS}
_STATUS_TO_TERMSTR_SIMPLE[Status.error] = termstr.TermStr(
    "E", termstr.CharStyle(bg_color=termstr.Color.red))
_STATUS_TO_TERMSTR_SIMPLE[Status.empty] = "."


LS_COLOR_CODES = lscolors.get_color_codes(os.environ)


def fix_input(input_):
    input_str = input_.decode("utf-8") if isinstance(input_, bytes) else input_
    return input_str.replace("\t", " " * 4)


def _do_command(command, **kwargs):
    stdout, stderr = "", ""
    with contextlib.suppress(subprocess.CalledProcessError):
        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, **kwargs)
        stdout, stderr = process.communicate()
    return fix_input(stdout), fix_input(stderr), process.returncode


def _run_command(command, status_text=Status.success):
    status, output = status_text, ""
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        output = stdout + stderr
    except subprocess.CalledProcessError:
        status = Status.failure
    if process.returncode != 0:
        status = Status.failure
    return status, fill3.Text(fix_input(output))


def _syntax_highlight_code(text, path):
    lexer = pygments.lexers.get_lexer_for_filename(path, text)
    tokens = pygments.lex(text, lexer)
    native_style = pygments.styles.get_style_by_name("native")
    return fill3.Code(tokens, native_style)


def pygments_(path):
    with open(path) as file_:
        try:
            text = file_.read()
        except UnicodeDecodeError:
            return Status.placeholder, fill3.Text("Not unicode")
        else:
            try:
                source_widget = _syntax_highlight_code(fix_input(text), path)
            except pygments.util.ClassNotFound:
                return Status.placeholder, fill3.Text("No lexer found")
    return Status.info, source_widget
pygments_.dependencies = ["python3-pygments"]


def linguist(path):
    # Dep: ruby?, ruby-dev, libicu-dev, cmake, "gem install github-linguist"
    return _run_command(["linguist", path], Status.info)


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


def md5(path):
    with open(path, "rb") as file:
        return hashlib.md5(file.read()).hexdigest()


def metadata(path):

    def _detail(value, unit):
        return (" (%s)" % value if unit is None else " (%s %s)" %
                (value, unit))
    is_symlink = "yes" if os.path.islink(path) else "no"
    stat_result = os.stat(path)
    permissions = stat.filemode(stat_result.st_mode)
    hardlinks = str(stat_result.st_nlink)
    group = [pwd.getpwuid(stat_result.st_gid).pw_name,
             _detail(stat_result.st_gid, "gid")]
    owner = [pwd.getpwuid(stat_result.st_uid).pw_name,
             _detail(stat_result.st_uid, "uid")]
    modified, created, access = [
        [time.asctime(time.gmtime(seconds)), _detail(int(seconds), "secs")]
        for seconds in (stat_result.st_mtime, stat_result.st_ctime,
                        stat_result.st_atime)]
    size = [_pretty_bytes(stat_result.st_size),
            _detail(stat_result.st_size, "bytes")]
    stdout, *rest = _do_command(
        ["file", "--dereference", "--brief", "--uncompress", "--mime", path])
    mime_type = stdout
    stdout, *rest = _do_command(
        ["file", "--dereference", "--brief", "--uncompress", path])
    file_type = stdout
    md5sum = md5(path)
    stdout, *rest = _do_command(["sha1sum", path])
    sha1sum = stdout.split()[0]
    permissions_value = [permissions,
                         _detail(_permissions_in_octal(permissions), None)]
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
            text.append("%-15s: %s\n" % (name, "".join(value)))
    return (Status.info, fill3.Text("".join(text)))
metadata.dependencies = {"file", "coreutils"}


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


_python_console_lexer = pygments.lexers.PythonConsoleLexer()


def python_unittests(path):
    if str(path).endswith("_test.py"):
        python_version = _python_version(path)
        cmd = [path] if _has_shebang_line(path) else [python_version, path]
        stdout, stderr, returncode = _do_command(["timeout", "20"] + cmd)
        markup = pygments.lex(stderr, _python_console_lexer)
        status = Status.success if returncode == 0 else Status.failure
        native_style = pygments.styles.get_style_by_name("native")
        code = fill3.Code(markup, native_style)
        return status, code
    else:
        return Status.placeholder, fill3.Text("No tests.")
python_unittests.dependencies = {"python", "python3"}


def pydoc(path):
    pydoc_exe = "pydoc3" if _python_version(path) == "python3" else "pydoc"
    status, output = Status.info, ""
    try:
        output = subprocess.check_output(
            ["timeout", "20", pydoc_exe, path])
        output = fix_input(output)
    except subprocess.CalledProcessError:
        status = Status.placeholder
    if not output.startswith("Help on module"):
        status = Status.placeholder
    return status, fill3.Text(output)
pydoc.dependencies = {"python", "python3"}


def _colorize_coverage_report(text):
    line_color = {"> ": termstr.Color.green, "! ": termstr.Color.red,
                  "  ": None}
    return fill3.join("", [termstr.TermStr(line).fg_color(line_color[line[:2]])
                           for line in text.splitlines(keepends=True)])


def python_coverage(path):
    test_path = path[:-(len(".py"))] + "_test.py"
    if os.path.exists(test_path):
        with tempfile.TemporaryDirectory() as temp_dir:
            python_exe = "%s-coverage" % _python_version(path)
            coverage_path = os.path.join(temp_dir, "coverage")
            env = os.environ.copy()
            env["COVERAGE_FILE"] = coverage_path
            stdout, *rest = _do_command(
                ["timeout", "60", python_exe, "run", test_path], env=env)
            stdout, *rest = _do_command(
                [python_exe, "annotate", "--directory", temp_dir,
                 os.path.normpath(path)], env=env)
            with open(os.path.join(temp_dir, path + ",cover"), "r") as f:
                stdout = f.read()
        return Status.info, fill3.Text(_colorize_coverage_report(stdout))
    else:
        return Status.placeholder, fill3.Text("No corresponding test file: " +
                                              os.path.normpath(test_path))
python_coverage.dependencies = {"python-coverage", "python3-coverage"}


def python_profile(path):
    stdout, *rest = _do_command(["timeout", "20", _python_version(path), "-m",
                                 "cProfile", "--sort=cumulative", path])
    return Status.info, fill3.Text(stdout)
python_profile.dependencies = {"python", "python3"}


def pep8(path):
    return _run_command([_python_version(path), "-m", "pep8", path])
pep8.dependencies = {"pep8", "python3-pep8"}


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
    source_widget = _syntax_highlight_code(fix_input(output), path)
    return Status.info, source_widget
python_gut.dependencies = set()


def python_modulefinder(path):
    return _run_command([_python_version(path), "-m", "modulefinder", path],
                        Status.info)
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
    status = Status.failure if max_score > 10 else Status.success
    return status, fill3.Text(_colorize_mccabe(stdout, python_version))
python_mccabe.dependencies = {"python-mccabe", "python3-mccabe"}


def python_tidy(path):  # Deps: found on internet?
    stdout, *rest = _do_command(["python", "python-tidy.py", path])
    return Status.info, _syntax_highlight_code(stdout, path)


def disassemble_pyc(path):
    bytecode = open(path, "rb").read()
    stringio = io.StringIO()
    dis.dis(bytecode, file=stringio)
    stringio.seek(0)
    return Status.info, fill3.Text(stringio.read())
disassemble_pyc.dependencies = set()


def perl_syntax(path):
    return _run_command(["perl", "-c", path])
perl_syntax.dependencies = {"perl"}


def perldoc(path):
    stdout, stderr, returncode = _do_command(["perldoc", path])
    return ((Status.info, fill3.Text(stdout)) if returncode == 0
            else (Status.placeholder, fill3.Text(stderr)))
perldoc.dependencies = {"perl-doc"}


def perltidy(path):
    stdout, *rest = _do_command(["perltidy", "-st", path])
    return Status.info, _syntax_highlight_code(stdout, path)
perltidy.dependencies = {"perltidy"}


def perl6_syntax(path):
    return _run_command(["perl6", "-c", path])
perl6_syntax.dependencies = {"perl6"}


def _jlint_tool(tool_type, path):
    stdout, *rest = _do_command([tool_type, path])
    status = (Status.success
              if b"Verification completed: 0 reported messages." in stdout
              else Status.failure)
    return status, fill3.Text(stdout)


def antic(path):
    return _jlint_tool("antic", path)
antic.dependencies = {"jlint"}


def jlint(path):
    return _jlint_tool("jlint", path)
jlint.dependencies = {"jlint"}


def splint(path):
    stdout, stderr, returncode = _do_command(["splint", "-preproc", path])
    status = Status.success if returncode == 0 else Status.failure
    return status, fill3.Text(stdout + stderr)
splint.dependencies = {"splint"}


def objdump_headers(path):
    return _run_command(["objdump", "--all-headers", path], Status.info)
objdump_headers.dependencies = {"binutils"}


def objdump_disassemble(path):
    stdout, *rest = _do_command(
        ["objdump", "--disassemble", "--reloc", "--dynamic-reloc", path])
    import pygments.lexers.asm
    lexer = pygments.lexers.asm.ObjdumpLexer()
    return Status.success, fill3.Text(list(pygments.lex(stdout, lexer)))
objdump_disassemble.dependencies = {"binutils"}


def readelf(path):
    return _run_command(["readelf", "--all", path], Status.info)
readelf.dependencies = {"binutils"}


def mp3info(path):
    stdout, *rest = _do_command(["mp3info", "-x", path])
    source_widget = fill3.Text(stdout)
    return Status.info, source_widget
mp3info.dependencies = ["mp3info"]


def dump_pickle(path):
    with open(path, "rb") as file_:
        object_ = pickle.load(file_)
    return Status.info, fill3.Text(pprint.pformat(object_.__dict__))
dump_pickle.dependencies = set()


def unzip(path):
    return _run_command(["unzip", "-l", path], Status.info)
unzip.dependencies = {"unzip"}


def tar_gz(path):
    return _run_command(["tar", "ztvf", path], Status.info)
tar_gz.dependencies = {"tar"}


def tar_bz2(path):
    return _run_command(["tar", "jtvf", path], Status.info)
tar_bz2.dependencies = {"tar"}


def csv(path):
    return _run_command(["head", "--lines=20", path], Status.info)
csv.dependencies = {"coreutils"}


def nm(path):
    return _run_command(["nm", "--demangle", path], Status.info)
nm.dependencies = {"binutils"}


def pdf2txt(path):
    return _run_command(["pdf2txt", path], Status.info)
pdf2txt.dependencies = {"python-pdfminer"}


def html_syntax(path):
    # Maybe only show errors
    stdout, stderr, returncode = _do_command(["tidy", path])
    status = Status.success if returncode == 0 else Status.failure
    return status, fill3.Text(stderr)
html_syntax.dependencies = {"tidy"}


def tidy(path):
    stdout, *rest = _do_command(["tidy", path])
    return Status.info, fill3.Text(stdout)
tidy.dependencies = {"tidy"}


def html2text(path):
    return _run_command(["html2text", path], Status.info)
html2text.dependencies = {"html2text"}


def bcpp(path):
    stdout, stderr, returncode = _do_command(["bcpp", "-fi", path])
    status = Status.info if returncode == 0 else Status.failure
    source_widget = _syntax_highlight_code(stdout, path)
    return status, source_widget
bcpp.dependencies = {"bcpp"}


def uncrustify(path):
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "uncrustify.cfg")
        stdout, stderr, returncode = _do_command(
            ["uncrustify", "--detect", "-f", path, "-o", config_path])
        if returncode != 0:
            raise AssertionError
        stdout, stderr, returncode = _do_command(
            ["uncrustify", "-c", config_path, "-f", path])
    status = Status.info if returncode == 0 else Status.failure
    source_widget = _syntax_highlight_code(stdout, path)
    return status, source_widget
uncrustify.dependencies = {"uncrustify"}


def php5_syntax(path):
    return _run_command(["php", "--syntax-check", path])
php5_syntax.dependencies = {"php5"}


def flog(path):  # Deps: "gem install flog"
    return _run_command(["flog", path], Status.info)
flog.dependencies = set()


# def csstidy(path):  # Deps: csstidy
#     stdout, stderr, returncode = _do_command(["csstidy", path])
#     status = Status.info if returncode == 0 else Status.failure
#     source_widget = _syntax_highlight_code(stdout, path)
#     return status, source_widget


def generic_tools():
    return [metadata, pygments_]


def tools_for_extension():
    return {
        "py": [python_syntax, python_unittests, pydoc, python_coverage,
               python_profile, pep8, pyflakes, pylint, python_gut,
               python_modulefinder, python_mccabe],
        "pyc": [disassemble_pyc],
        "pl": [perl_syntax, perldoc, perltidy],
        "pm": [perl_syntax, perldoc, perltidy],
        "t": [perl_syntax, perldoc, perltidy],
        "p6": [perl6_syntax],
        "pm6": [perl6_syntax],
        "java": [antic, uncrustify],
        "class": [jlint],
        "c": [splint, uncrustify],
        "h": [splint, uncrustify],
        "o": [objdump_headers, objdump_disassemble, readelf],
        "mp3": [mp3info],
        "pickle": [dump_pickle],
        "zip": [unzip],
        "tar.gz": [tar_gz],
        "tgz": [tar_gz],
        "tar.bz2": [tar_bz2],
        "csv": [csv],
        "a": [nm],
        "so": [nm],
        "pdf": [pdf2txt],
        "html": [html_syntax, tidy, html2text],
        "cpp": [bcpp, uncrustify],
        "php": [php5_syntax],
        "rb": [flog]
        # "css": [csstidy]
    }


def tools_all():
    tools_ = set(generic_tools())
    for tool_list in tools_for_extension().values():
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
    extra_tools = [] if ext == "" else tools_for_extension().get(ext[1:], [])
    return generic_tools() + extra_tools


def _get_python_traceback_lexer():
    return pygments.lexers.PythonTracebackLexer()


def _get_python_console_lexer():
    return pygments.lexers.PythonConsoleLexer()


def run_tool_no_error(path, tool):
    try:
        status, result = tool(path)
    except:
        # Maybe use code.InteractiveInterpreter.showtraceback() ?
        tokens = pygments.lex(traceback.format_exc(),
                              _get_python_traceback_lexer())
        native_style = pygments.styles.get_style_by_name("native")
        status, result = Status.error, fill3.Code(tokens, native_style)
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
    color_code = lscolors.color_code_for_path(path, LS_COLOR_CODES)
    return (termstr.CharStyle() if color_code is None else
            _convert_lscolor_code_to_charstyle(color_code))


@functools.lru_cache(maxsize=100)
def _path_colored(path):
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
def _tool_name_colored(tool, path):
    char_style = (termstr.CharStyle(is_bold=True) if tool in generic_tools()
                  else _charstyle_of_path(path))
    return termstr.TermStr(tool.__name__, char_style)
