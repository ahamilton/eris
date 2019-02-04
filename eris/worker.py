#!/usr/bin/env python3.7

# Copyright (C) 2015-2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import asyncio
import os
import signal

import eris.tools as tools


class Worker:

    AUTOSAVE_MESSAGE = "Auto-saving..."
    unsaved_jobs_total = 0

    def __init__(self, is_already_paused, is_being_tested):
        self.is_already_paused = is_already_paused
        self.is_being_tested = is_being_tested
        self.result = None
        self.process = None
        self.child_pgid = None

    async def create_process(self):
        create = asyncio.create_subprocess_exec(
            "eris-worker", stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            preexec_fn=os.setsid)
        self.process = await create
        pid_line = await self.process.stdout.readline()
        self.child_pgid = int(pid_line.strip())
        os.setpriority(os.PRIO_PGRP, self.child_pgid, 19)

    async def run_tool(self, path, tool):
        self.process.stdin.write(f"{tool.__qualname__}\n{path}\n".encode("utf-8"))
        data = await self.process.stdout.readline()
        return tools.Status(int(data))

    async def job_runner(self, screen, summary, log, jobs_added_event,
                   appearance_changed_event):
        await self.create_process()
        while True:
            await jobs_added_event.wait()
            while True:
                try:
                    self.result = await summary.get_closest_placeholder()
                except StopAsyncIteration:
                    self.result = None
                    break
                await self.result.run(log, appearance_changed_event, self)
                Worker.unsaved_jobs_total += 1
                if Worker.unsaved_jobs_total == 100:
                    log.log_message(Worker.AUTOSAVE_MESSAGE)
                    screen.save()
                summary.completed_total += 1
                if summary.result_total == summary.completed_total:
                    log.log_message("All results are up to date.")
                    log.log_message(Worker.AUTOSAVE_MESSAGE)
                    screen.save()
                    if self.is_being_tested:
                        os.kill(os.getpid(), signal.SIGINT)
            jobs_added_event.clear()

    def pause(self):
        if self.result is not None and \
           self.result.status == tools.Status.running:
            os.killpg(self.child_pgid, signal.SIGSTOP)
            self.result.set_status(tools.Status.paused)

    def continue_(self):
        if self.result is not None and \
           self.result.status == tools.Status.paused:
            self.result.set_status(tools.Status.running)
            os.killpg(self.child_pgid, signal.SIGCONT)

    def kill(self):
        if self.child_pgid is not None:
            os.killpg(self.child_pgid, signal.SIGKILL)


def main():
    print(os.getpgid(os.getpid()), flush=True)
    try:
        while True:
            tool_name, path = input(), input()
            tool = getattr(tools, tool_name)
            result = tools.Result(path, tool)
            status, result.result = tools.run_tool_no_error(path, tool)
            print(status.value, flush=True)
    except:
        tools.log_error()


if __name__ == "__main__":
    main()
