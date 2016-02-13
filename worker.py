#!/usr/bin/env python3

# Copyright (C) 2015-2016 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import os
import signal
import subprocess

import psutil

import tools


def make_process_nicest(pid):
    process = psutil.Process(pid)
    process.nice(19)
    process.ionice(psutil.IOPRIO_CLASS_IDLE)


class Worker:

    def __init__(self, sandbox):
        self.sandbox = sandbox
        if sandbox is None:
            self.process = subprocess.Popen(
                [__file__], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
        else:
            cache_path = os.path.join(os.getcwd(), tools._CACHE_PATH)
            self.cache_mount = sandbox.mount_point + cache_path
            subprocess.check_call(["sudo", "mount", "--bind", cache_path,
                                   self.cache_mount])
            self.process = sandbox.Popen([__file__])
        self.child_pid = int(self.process.stdout.readline())
        make_process_nicest(self.child_pid)

    def run_tool(self, path, tool):
        self.process.stdin.write(("%s\n%s\n" %
                                  (tool.__qualname__, path)).encode("utf-8"))
        self.process.stdin.flush()
        return tools.Status(int(self.process.stdout.readline()))

    def pause(self):
        os.kill(self.child_pid, signal.SIGSTOP)

    def continue_(self):
        os.kill(self.child_pid, signal.SIGCONT)


def main():
    print(os.getpid(), flush=True)
    while True:
        tool_name, path = input(), input()
        tool = getattr(tools, tool_name)
        result = tools.Result(path, tool)
        status, result.result = tools.run_tool_no_error(path, tool)
        print(status.value, flush=True)


if __name__ == "__main__":
    main()
