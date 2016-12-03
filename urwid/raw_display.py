#!/usr/bin/python
#
# Urwid raw display module
#    Copyright (C) 2004-2009  Ian Ward
#
#    This library is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Lesser General Public
#    License as published by the Free Software Foundation; either
#    version 2.1 of the License, or (at your option) any later version.
#
#    This library is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public
#    License along with this library; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Urwid web site: http://excess.org/urwid/

"""
Direct terminal UI implementation
"""

import os
import select
import sys
import termios
import tty

from urwid import escape

from urwid.display_common import BaseScreen, RealTerminal


class Screen(BaseScreen, RealTerminal):
    def __init__(self, input=sys.stdin, output=sys.stdout):
        """Initialize a screen that directly prints escape codes to an output
        terminal.
        """
        super(Screen, self).__init__()
        self._keyqueue = []
        self.prev_input_resize = 0
        self.set_input_timeouts()
        self._mouse_tracking_enabled = False
        self._next_timeout = None

        # Our connections to the world
        self._term_output_file = output
        self._term_input_file = input

    def set_input_timeouts(self, max_wait=None, complete_wait=0.125,
        resize_wait=0.125):
        """
        Set the get_input timeout values.  All values are in floating
        point numbers of seconds.

        max_wait -- amount of time in seconds to wait for input when
            there is no input pending, wait forever if None
        complete_wait -- amount of time in seconds to wait when
            get_input detects an incomplete escape sequence at the
            end of the available input
        resize_wait -- amount of time in seconds to wait for more input
            after receiving two screen resize requests in a row to
            stop Urwid from consuming 100% cpu during a gradual
            window resize operation
        """
        self.max_wait = max_wait
        if max_wait is not None:
            if self._next_timeout is None:
                self._next_timeout = max_wait
            else:
                self._next_timeout = min(self._next_timeout, self.max_wait)
        self.complete_wait = complete_wait
        self.resize_wait = resize_wait

    def set_mouse_tracking(self, enable=True):
        """
        Enable (or disable) mouse tracking.

        After calling this function get_input will include mouse
        click events along with keystrokes.
        """
        enable = bool(enable)
        if enable == self._mouse_tracking_enabled:
            return

        self._mouse_tracking(enable)
        self._mouse_tracking_enabled = enable

    def _mouse_tracking(self, enable):
        if enable:
            self.write(escape.MOUSE_TRACKING_ON)
        else:
            self.write(escape.MOUSE_TRACKING_OFF)

    def _start(self, alternate_buffer=True):
        """
        Initialize the screen and input mode.

        alternate_buffer -- use alternate screen buffer
        """
        if alternate_buffer:
            self.write(escape.SWITCH_TO_ALTERNATE_BUFFER)
            self._rows_used = None
        else:
            self._rows_used = 0

        fd = self._term_input_file.fileno()
        if os.isatty(fd):
            self._old_termios_settings = termios.tcgetattr(fd)
            tty.setcbreak(fd)

        self._alternate_buffer = alternate_buffer
        self._next_timeout = self.max_wait

        if not self._signal_keys_set:
            self._old_signal_keys = self.tty_signal_keys(fileno=fd)

        self._mouse_tracking(self._mouse_tracking_enabled)

        return super(Screen, self)._start()

    def _stop(self):
        """
        Restore the screen.
        """

        fd = self._term_input_file.fileno()
        if os.isatty(fd):
            termios.tcsetattr(fd, termios.TCSADRAIN,
        self._old_termios_settings)

        self._mouse_tracking(False)

        move_cursor = ""
        if self._alternate_buffer:
            move_cursor = escape.RESTORE_NORMAL_BUFFER

        self.write(
            escape.SI
            + move_cursor
            + escape.SHOW_CURSOR)
        self.flush()

        if self._old_signal_keys:
            self.tty_signal_keys(*(self._old_signal_keys + (fd,)))

        super(Screen, self)._stop()


    def write(self, data):
        """Write some data to the terminal.

        You may wish to override this if you're using something other than
        regular files for input and output.
        """
        self._term_output_file.write(data)

    def flush(self):
        """Flush the output buffer.

        You may wish to override this if you're using something other than
        regular files for input and output.
        """
        self._term_output_file.flush()

    def get_input(self, raw_keys=False):
        """Return pending input as a list.

        raw_keys -- return raw keycodes as well as translated versions

        This function will immediately return all the input since the
        last time it was called.  If there is no input pending it will
        wait before returning an empty list.  The wait time may be
        configured with the set_input_timeouts function.

        If raw_keys is False (default) this function will return a list
        of keys pressed.  If raw_keys is True this function will return
        a ( keys pressed, raw keycodes ) tuple instead.

        Examples of keys returned:

        * ASCII printable characters:  " ", "a", "0", "A", "-", "/"
        * ASCII control characters:  "tab", "enter"
        * Escape sequences:  "up", "page up", "home", "insert", "f1"
        * Key combinations:  "shift f1", "meta a", "ctrl b"
        * Window events:  "window resize"

        When a narrow encoding is not enabled:

        * "Extended ASCII" characters:  "\\xa1", "\\xb2", "\\xfe"

        When a wide encoding is enabled:

        * Double-byte characters:  "\\xa1\\xea", "\\xb2\\xd4"

        When utf8 encoding is enabled:

        * Unicode characters: u"\\u00a5", u'\\u253c"

        Examples of mouse events returned:

        * Mouse button press: ('mouse press', 1, 15, 13),
                              ('meta mouse press', 2, 17, 23)
        * Mouse drag: ('mouse drag', 1, 16, 13),
                      ('mouse drag', 1, 17, 13),
                      ('ctrl mouse drag', 1, 18, 13)
        * Mouse button release: ('mouse release', 0, 18, 13),
                                ('ctrl mouse release', 0, 17, 23)
        """
        assert self._started

        self._wait_for_input_ready(self._next_timeout)
        keys, raw = self.parse_input(None, None, self.get_available_raw_input())

        # Avoid pegging CPU at 100% when slowly resizing
        if keys==['window resize'] and self.prev_input_resize:
            while True:
                self._wait_for_input_ready(self.resize_wait)
                keys, raw2 = self.parse_input(None, None, self.get_available_raw_input())
                raw += raw2
                #if not keys:
                #    keys, raw2 = self._get_input(
                #        self.resize_wait)
                #    raw += raw2
                if keys!=['window resize']:
                    break
            if keys[-1:]!=['window resize']:
                keys.append('window resize')

        if keys==['window resize']:
            self.prev_input_resize = 2
        elif self.prev_input_resize == 2 and not keys:
            self.prev_input_resize = 1
        else:
            self.prev_input_resize = 0

        if raw_keys:
            return keys, raw
        return keys


    _input_timeout = None
    _partial_codes = None

    def get_available_raw_input(self):
        """
        Return any currently-available input.  Does not block.

        This method is only used by the default `hook_event_loop`
        implementation; you can safely ignore it if you implement your own.
        """
        codes = self._get_keyboard_codes()

        if self._partial_codes:
            codes = self._partial_codes + codes
            self._partial_codes = None

        return codes

    def parse_input(self, event_loop, callback, codes, wait_for_more=True):
        """
        Read any available input from get_available_raw_input, parses it into
        keys, and calls the given callback.

        The current implementation tries to avoid any assumptions about what
        the screen or event loop look like; it only deals with parsing keycodes
        and setting a timeout when an incomplete one is detected.

        `codes` should be a sequence of keycodes, i.e. bytes.  A bytearray is
        appropriate, but beware of using bytes, which only iterates as integers
        on Python 3.
        """
        # Note: event_loop may be None for 100% synchronous support, only used
        # by get_input.  Not documented because you shouldn't be doing it.
        if self._input_timeout and event_loop:
            event_loop.remove_alarm(self._input_timeout)
            self._input_timeout = None

        original_codes = codes
        processed = []
        try:
            while codes:
                run, codes = escape.process_keyqueue(
                    codes, wait_for_more)
                processed.extend(run)
        except escape.MoreInputRequired:
            # Set a timer to wait for the rest of the input; if it goes off
            # without any new input having come in, use the partial input
            k = len(original_codes) - len(codes)
            processed_codes = original_codes[:k]
            self._partial_codes = codes

            def _parse_incomplete_input():
                self._input_timeout = None
                self._partial_codes = None
                self.parse_input(
                    event_loop, callback, codes, wait_for_more=False)
            if event_loop:
                self._input_timeout = event_loop.alarm(
                    self.complete_wait, _parse_incomplete_input)

        else:
            processed_codes = original_codes
            self._partial_codes = None

        if callback:
            callback(processed, processed_codes)
        else:
            # For get_input
            return processed, processed_codes

    def _get_keyboard_codes(self):
        codes = []
        while True:
            code = self._getch_nodelay()
            if code < 0:
                break
            codes.append(code)
        return codes

    def _wait_for_input_ready(self, timeout):
        ready = None
        fd_list = [self._term_input_file.fileno()]
        while True:
            try:
                if timeout is None:
                    ready,w,err = select.select(
                        fd_list, [], fd_list)
                else:
                    ready,w,err = select.select(
                        fd_list,[],fd_list, timeout)
                break
            except select.error as e:
                if e.args[0] != 4:
                    raise
        return ready

    def _getch(self, timeout):
        ready = self._wait_for_input_ready(timeout)
        if self._term_input_file.fileno() in ready:
            return ord(os.read(self._term_input_file.fileno(), 1))
        return -1

    def _getch_nodelay(self):
        return self._getch(0)


def _test():
    import doctest
    doctest.testmod()

if __name__=='__main__':
    _test()
