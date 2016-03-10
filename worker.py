#!/usr/bin/env python3

# Copyright (C) 2015-2016 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import asyncio
import os
import signal
import subprocess

import psutil

import tools


def _make_process_nicest(pid):
    process = psutil.Process(pid)
    process.nice(19)
    process.ionice(psutil.IOPRIO_CLASS_IDLE)


class Worker:

    def __init__(self, sandbox, is_already_paused, is_being_tested):
        self.sandbox = sandbox
        self.is_already_paused = is_already_paused
        self.is_being_tested = is_being_tested
        self.result = None
        self.process = None
        self.child_pid = None

    @asyncio.coroutine
    def create_process(self):
        if self.sandbox is None:
            command = [__file__]
        else:
            cache_path = os.path.join(os.getcwd(), tools.CACHE_PATH)
            cache_mount = self.sandbox.mount_point + cache_path
            subprocess.check_call(["sudo", "mount", "--bind", cache_path,
                                   cache_mount])
            command = self.sandbox.command([__file__])
        create = asyncio.create_subprocess_exec(
            *command, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        self.process = yield from create
        pid_line = yield from self.process.stdout.readline()
        self.child_pid = int(pid_line.strip())

    @asyncio.coroutine
    def run_tool(self, path, tool):
        self.process.stdin.write(("%s\n%s\n" %
                                  (tool.__qualname__, path)).encode("utf-8"))
        data = yield from self.process.stdout.readline()
        return tools.Status(int(data))

    @asyncio.coroutine
    def job_runner(self, summary, log, jobs_added_event,
                   appearance_changed_event):
        yield from self.create_process()
        _make_process_nicest(self.child_pid)
        while True:
            yield from jobs_added_event.wait()
            while True:
                # _regulate_temperature(log)  # My fan is broken
                try:
                    self.result = summary.get_closest_placeholder()
                except StopIteration:
                    self.result = None
                    if summary.result_total == summary.completed_total:
                        log.log_message("All results are up to date.")
                        if self.is_being_tested:
                            os.kill(os.getpid(), signal.SIGINT)
                    break
                yield from self.result.run(log, appearance_changed_event,
                                           self)
                summary.completed_total += 1
            jobs_added_event.clear()

    def pause(self):
        if self.result is not None and \
           self.result.status == tools.Status.running:
            os.kill(self.child_pid, signal.SIGSTOP)
            self.result.set_status(tools.Status.paused)

    def continue_(self):
        if self.result is not None and \
           self.result.status == tools.Status.paused:
            self.result.set_status(tools.Status.running)
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
