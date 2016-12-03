#!/usr/bin/python
# Urwid common display code
#    Copyright (C) 2004-2011  Ian Ward
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

import os
import sys
import termios

from urwid.util import StoppingContext


class RealTerminal(object):
    def __init__(self):
        super(RealTerminal,self).__init__()
        self._signal_keys_set = False
        self._old_signal_keys = None

    def tty_signal_keys(self, intr=None, quit=None, start=None,
        stop=None, susp=None, fileno=None):
        """
        Read and/or set the tty's signal character settings.
        This function returns the current settings as a tuple.

        Use the string 'undefined' to unmap keys from their signals.
        The value None is used when no change is being made.
        Setting signal keys is done using the integer ascii
        code for the key, eg.  3 for CTRL+C.

        If this function is called after start() has been called
        then the original settings will be restored when stop()
        is called.
        """
        if fileno is None:
            fileno = sys.stdin.fileno()
        if not os.isatty(fileno):
            return

        tattr = termios.tcgetattr(fileno)
        sattr = tattr[6]
        skeys = (sattr[termios.VINTR], sattr[termios.VQUIT],
            sattr[termios.VSTART], sattr[termios.VSTOP],
            sattr[termios.VSUSP])

        if intr == 'undefined': intr = 0
        if quit == 'undefined': quit = 0
        if start == 'undefined': start = 0
        if stop == 'undefined': stop = 0
        if susp == 'undefined': susp = 0

        if intr is not None: tattr[6][termios.VINTR] = intr
        if quit is not None: tattr[6][termios.VQUIT] = quit
        if start is not None: tattr[6][termios.VSTART] = start
        if stop is not None: tattr[6][termios.VSTOP] = stop
        if susp is not None: tattr[6][termios.VSUSP] = susp

        if intr is not None or quit is not None or \
            start is not None or stop is not None or \
            susp is not None:
            termios.tcsetattr(fileno, termios.TCSADRAIN, tattr)
            self._signal_keys_set = True

        return skeys


class ScreenError(Exception):
    pass

class BaseScreen():
    """
    Base class for Screen classes (raw_display.Screen, .. etc)
    """

    def __init__(self):
        super(BaseScreen,self).__init__()
        self._palette = {}
        self._started = False

    started = property(lambda self: self._started)

    def start(self, *args, **kwargs):
        """Set up the screen.  If the screen has already been started, does
        nothing.

        May be used as a context manager, in which case :meth:`stop` will
        automatically be called at the end of the block:

            with screen.start():
                ...

        You shouldn't override this method in a subclass; instead, override
        :meth:`_start`.
        """
        if not self._started:
            self._start(*args, **kwargs)
        self._started = True
        return StoppingContext(self)

    def _start(self):
        pass

    def stop(self):
        if self._started:
            self._stop()
        self._started = False

    def _stop(self):
        pass


def _test():
    import doctest
    doctest.testmod()

if __name__=='__main__':
    _test()
