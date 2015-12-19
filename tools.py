# -*- coding: utf-8 -*-

# Copyright (C) 2015 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

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


def _convert_lscolor_code_to_charstyle(lscolor_code):
    if lscolor_code is None:
        return termstr.CharStyle()
    parts = lscolor_code.split(";")
    if len(parts) == 1:
        # Is this correct?
        is_bold = parts[0] == "1"
        fg_color = termstr.Color.white
    else:
        is_bold = len(parts) == 4 and parts[3] == "1"
        fg_color = int(parts[2])
    return termstr.CharStyle(fg_color, is_bold=is_bold)


def sandbox_command(command):
    # Deps: firejail http://l3net.wordpress.com/projects/firejail/
    # return ["firejail", "--overlay", "-c"] + command
    # return ["firejail", "-c"] + command
    return command


def fix_input(input_):
    input_str = input_.decode("utf-8") if isinstance(input_, bytes) else input_
    return input_str.replace("\t", " " * 4)


def _do_command(command, **kwargs):
    stdout, stderr = "", ""
    try:
        process = subprocess.Popen(sandbox_command(command),
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, **kwargs)
        stdout, stderr = process.communicate()
    except subprocess.CalledProcessError:
        pass
    return fix_input(stdout), fix_input(stderr), process.returncode


def _run_command(path, command, status_text=Status.success):
    status, output = status_text, ""
    try:
        process = subprocess.Popen(sandbox_command(command),
                                   stdout=subprocess.PIPE,
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
    return _run_command(path, ["linguist", path], Status.info)


def mp3info(path):
    stdout, stderr, returncode = _do_command(["mp3info", "-x", path])
    source_widget = fill3.Text(stdout)
    return Status.info, source_widget
mp3info.dependencies = ["mp3info"]


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


def md5(path):  # Deps: coreutils
    # stdout, stderr, returncode = _do_command(["md5sum", path])
    # stdout = stdout.decode("utf-8")
    # return stdout.split()[0]
    with open(path, "rb") as file:
        return hashlib.md5(file.read()).hexdigest()


def metadata(path):  # Deps: file, coreutils

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
    stdout, stderr, returncode = _do_command(
        ["file", "--dereference", "--brief", "--uncompress", "--mime", path])
    mime_type = stdout
    stdout, stderr, returncode = _do_command(
        ["file", "--dereference", "--brief", "--uncompress", path])
    file_type = stdout
    md5sum = md5(path)
    stdout, stderr, returncode = _do_command(["sha1sum", path])
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


def pylint3(path):
    return _run_command(path, ["python3", "-m", "pylint", "--errors-only",
                               path])
pylint3.dependencies = {"pylint3"}


def pyflakes(path):
    return _run_command(path, ["python3", "-m", "pyflakes", path])
pyflakes.dependencies = {"pyflakes"}


def pep8(path):
    return _run_command(path, ["python3", "-m", "pep8", path])
pep8.dependencies = {"python3-pep8"}


def _has_shebang_line(path):
    with open(path, "rb") as file_:
        return file_.read(2) == "#!"


_python_console_lexer = pygments.lexers.PythonConsoleLexer()


def unittests(path):
    if str(path).endswith("_test.py"):
        cmd = [path] if _has_shebang_line(path) else ["python3", path]
        stdout, stderr, returncode = _do_command(["timeout", "20"] + cmd)
        markup = pygments.lex(stderr, _python_console_lexer)
        status = Status.success if returncode == 0 else Status.failure
        native_style = pygments.styles.get_style_by_name("native")
        code = fill3.Code(markup, native_style)
        return status, code
    else:
        return Status.placeholder, fill3.Text("No tests.")
unittests.dependencies = {"python3"}


def gut(path):
    status, output = Status.info, ""
    try:
        output = subprocess.check_output(
            ["/home/ahamilton/code/python-gut/gut.py", path])
    except subprocess.CalledProcessError:
        status = Status.failure
    source_widget = _syntax_highlight_code(fix_input(output), path)
    return status, source_widget


def pydoc3(path):
    status, output = Status.info, ""
    try:
        output = subprocess.check_output(
            ["timeout", "20", "pydoc3", path])
        output = fix_input(output)
    except subprocess.CalledProcessError:
        status = Status.placeholder
    if not output.startswith("Help on module"):
        status = Status.placeholder
    return status, fill3.Text(output)
pydoc3.dependencies = {"python3"}


def modulefinder(path):
    return _run_command(
        path, ["python3", "-m", "modulefinder", path], Status.info)
modulefinder.dependencies = {"python3"}


def python_syntax(path):
    return _run_command(path, ["python3", "-m", "py_compile", path])
python_syntax.dependencies = {"python3"}


def disassemble_pyc(path):
    bytecode = open(path, "rb").read()
    stringio = io.StringIO()
    dis.dis(bytecode, file=stringio)
    stringio.seek(0)
    return Status.info, fill3.Text(stringio.read())

# def disassemble_pyc(path):  # Deps: found on internet
#     code_path = os.path.dirname(sys.argv[0])
#     disassemble_path = os.path.join(code_path, "disassemble.py")
#     return _run_command(path, ["python", disassemble_path, path],
#                         Status.info)


def perldoc(path):
    stdout, stderr, returncode = _do_command(["perldoc", path])
    return ((Status.info, fill3.Text(stdout)) if returncode == 0
            else (Status.placeholder, fill3.Text(stderr)))
perldoc.dependencies = {"perl-doc"}


def python_tidy(path):  # Deps: found on internet?
    stdout, stderr, returncode = _do_command(["python", "python-tidy.py",
                                              path])
    return Status.info, _syntax_highlight_code(stdout, path)


def mccabe(path):
    command = ["python3", "/usr/lib/python3/dist-packages/mccabe.py", path]
    return _run_command(path, command, Status.info)
mccabe.dependencies = {"python3-mccabe"}


def perltidy(path):
    stdout, stderr, returncode = _do_command(["perltidy", "-st", path])
    return Status.info, _syntax_highlight_code(stdout, path)
perltidy.dependencies = {"perltidy"}


def perl_syntax(path):
    return _run_command(path, ["perl", "-c", path])
perl_syntax.dependencies = {"perl"}


def objdump_headers(path):
    return _run_command(path, ["objdump", "--all-headers", path], Status.info)
objdump_headers.dependencies = {"binutils"}


def objdump_disassemble(path):
    stdout, stderr, returncode = _do_command(
        ["objdump", "--disassemble", "--reloc", "--dynamic-reloc", path])
    import pygments.lexers.asm
    lexer = pygments.lexers.asm.ObjdumpLexer()
    return Status.success, fill3.Text(list(pygments.lex(stdout, lexer)))
objdump_disassemble.dependencies = {"binutils"}


def readelf(path):
    return _run_command(path, ["readelf", "--all", path], Status.info)
readelf.dependencies = {"binutils"}


def dump_pickle(path):
    with open(path, "rb") as file_:
        object_ = pickle.load(file_)
    return Status.info, fill3.Text(pprint.pformat(object_.__dict__))


def unzip(path):
    return _run_command(path, ["unzip", "-l", path], Status.info)
unzip.dependencies = {"unzip"}


def tar_gz(path):
    return _run_command(path, ["tar", "ztvf", path], Status.info)
tar_gz.dependencies = {"tar"}


def tar_bz2(path):
    return _run_command(path, ["tar", "jtvf", path], Status.info)
tar_bz2.dependencies = {"tar"}


def csv(path):
    return _run_command(path, ["head", "--lines=20", path], Status.info)
csv.dependencies = {"coreutils"}


def nm(path):
    return _run_command(path, ["nm", "--demangle", path], Status.info)
nm.dependencies = {"binutils"}


def pdf2txt(path):
    return _run_command(path, ["pdf2txt", path], Status.info)
pdf2txt.dependencies = {"python-pdfminer"}


def html2text(path):
    return _run_command(path, ["html2text", path], Status.info)
html2text.dependencies = {"html2text"}


def html_syntax(path):
    # Maybe only show errors
    stdout, stderr, returncode = _do_command(["tidy", path])
    status = Status.success if returncode == 0 else Status.failure
    return status, fill3.Text(stderr)
html_syntax.dependencies = {"tidy"}


def tidy(path):
    stdout, stderr, returncode = _do_command(["tidy", path])
    return Status.info, fill3.Text(stdout)
tidy.dependencies = {"tidy"}


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
    return _run_command(path, ["php", "--syntax-check", path])
php5_syntax.dependencies = {"php5"}


def flog(path):  # Deps: "gem install flog"
    return _run_command(path, ["flog", path], Status.info)


# def csstidy(path):  # Deps: csstidy
#     stdout, stderr, returncode = _do_command(["csstidy", path])
#     status = Status.info if returncode == 0 else Status.failure
#     source_widget = _syntax_highlight_code(stdout, path)
#     return status, source_widget


def python3_coverage(path):
    test_path = path[:-(len(".py"))] + "_test.py"
    if os.path.exists(test_path):
        with tempfile.TemporaryDirectory() as temp_dir:
            coverage_path = os.path.join(temp_dir, "coverage")
            env = os.environ.copy()
            env["COVERAGE_FILE"] = coverage_path
            stdout, stderr, returncode = _do_command(
                ["timeout", "20", "python3-coverage", "run", test_path],
                env=env)
            assert returncode == 0, returncode
            stdout, stderr, returncode = _do_command(
                ["python3-coverage", "annotate", "--directory", temp_dir,
                 os.path.normpath(path)], env=env)
            with open(os.path.join(temp_dir, path + ",cover"), "r") as f:
                stdout = f.read()
        return Status.info, fill3.Text(stdout)
    else:
        return Status.placeholder, fill3.Text("No corresponding test file: " +
                                              os.path.normpath(test_path))
python3_coverage.dependencies = {"python3-coverage"}


def profile(path):
    stdout, stderr, returncode = _do_command(
        ["timeout", "20", "python3", "-m", "cProfile", "--sort=cumulative",
         path])
    return Status.info, fill3.Text(stdout)
profile.dependencies = {"python3"}


def _jlint_tool(tool_type, path):
    stdout, stderr, returncode = _do_command([tool_type, path])
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


def generic_tools():
    return [metadata, pygments_]


def tools_for_extension():
    return {
        "py": [python_syntax, unittests, pydoc3, python3_coverage, profile,
               pep8, pyflakes, pylint3, gut, modulefinder],  # mccabe
        "pyc": [disassemble_pyc],
        "pl": [perl_syntax, perldoc, perltidy],
        "pm": [perl_syntax, perldoc, perltidy],
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
        try:
            dependencies_all.update(tool.dependencies)
        except AttributeError:
            continue
    return dependencies_all


# def _extensions_for_tool(tools_for_extension):
#     result = {}
#     for extension, tools in tools_for_extension.items():
#         for tool in tools:
#             if tool in result:
#                 result[tool].append(extension)
#             else:
#                 result[tool] = [extension]
#     return result


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
    # return [Tool(tool) for tool in (generic_tools() + extra_tools)]
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


@functools.lru_cache(maxsize=100)
def _path_colored(path):
    color_code = lscolors.color_code_for_path(path, LS_COLOR_CODES)
    char_style = _convert_lscolor_code_to_charstyle(color_code)
    path = path[2:]
    dirname, basename = os.path.split(path)
    if dirname == "":
        return termstr.TermStr(basename, char_style)
    else:
        dirname = dirname + os.path.sep
        color_code = lscolors.color_code_for_path(dirname, LS_COLOR_CODES)
        dir_style = _convert_lscolor_code_to_charstyle(color_code)
        return (termstr.TermStr(dirname, dir_style) +
                termstr.TermStr(basename, char_style))


@functools.lru_cache(maxsize=100)
def _tool_name_colored(tool, path):
    if tool in generic_tools():
        char_style = termstr.CharStyle((255, 255, 255), (0, 0, 0),
                                       is_bold=True)
    else:
        # extensions = _extensions_for_tool(tools_for_extension())[tool]
        # color_code = (
        #     LS_COLOR_CODES.get("." + extensions[0], None)
        #     if len(extensions) == 1
        #     else lscolors.color_code_for_path(path, LS_COLOR_CODES))
        color_code = lscolors.color_code_for_path(path, LS_COLOR_CODES)
        char_style = _convert_lscolor_code_to_charstyle(color_code)
    return termstr.TermStr(tool.__name__, char_style)
