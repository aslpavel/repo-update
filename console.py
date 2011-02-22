#! /usr/bin/env python3
# AUTHOR: Pavel Aslanov
# DESCRIPTION: all kind of console helpers
# MODIFIED: 02/17/2011

import sys, os, contextlib, termios, tty, fcntl, struct

# helpers
#{{{ no_echo ()
@contextlib.contextmanager
def no_echo ():
    with flags (off = termios.ECHO):
        yield
#}}}
#{{{ flags (on = ..., off = ...)
@contextlib.contextmanager
def flags (on = None, off = None):
    if sys.stdin.isatty ():
        fd = sys.stdin.fileno ()
        attr_old = termios.tcgetattr (fd)
        attr_new = list (attr_old)
        if on:
            attr_new [3] |= on
        if off:
            attr_new [3] &= ~off
        try:
            termios.tcsetattr (fd, termios.TCSADRAIN, attr_new)
            yield
        finally:
            termios.tcsetattr (fd, termios.TCSADRAIN, attr_old)
    else:
        yield
#}}}
#{{{ pending (message)
@contextlib.contextmanager
def pending (*messages):
    busy_status = ((' [', '35;01'), ('BUSY', '35'), (']', '35;01'))
    fail_status = ((' [', '35;01'), ('FAIL', '31;01'), (']\n','35;01'))
    done_status = ((' [', '35;01'), ('DONE', '32;01'), (']\n', '35;01'))

    #{{{ calculate caption
    symbols = width () - 7
    caption = []
    for message in messages:
        if isinstance (message, str):
            # simple string
            if len (message) > symbols:
                # last chunk
                caption.append (message [symbols:])
                symbols = 0
                break
            else:
                caption.append (message)
                symbols -= len (message)
        else:
            # colored string
            text, attr = message
            if len (text) > symbols:
                # last chunk
                caption.append ((text [symbols:], attr))
                symbols = 0
                break
            else:
                caption.append (message)
                symbols -= len (text)
    if symbols != 0:
        caption.append (' ' * symbols)
    #}}}

    class Status:
        def __init__ (self):
            self.failed = False
            self.message = None
            self.supressed = False

        def __call__ (self, *messages):
            self.messages = messages
            self.failed = True

        def supress (self):
            """supres further output"""
            self.supressed = True

    write (sys.stderr, *caption)
    status = Status ()

    isatty = sys.stderr.isatty ()
    if isatty:
        sys.stderr.write ('\x1b7')
        write (sys.stderr, *busy_status)

    try:
        yield status
    except Exception as e:
        status ('unhandled exception ', (str(e), '37;01'), ' was chought\n')
        raise
    finally:
        if not status.supressed:
            if isatty:
                sys.stderr.write ('\x1b8')
            if status.failed:
                write (sys.stderr, *fail_status)
                if len(status.messages):
                    error (*status.messages)
            else:
                write (sys.stderr, *done_status)
#}}}
#{{{ read ()
def read ():
    if sys.stdin.isatty ():
        fd = sys.stdin.fileno ()
        attr = termios.tcgetattr (fd)
        try:
            tty.setraw (fd)
            return sys.stdin.read (1)
        finally:
            termios.tcsetattr (fd, termios.TCSADRAIN, attr)
    return sys.stdin.read (1)
#}}}
#{{{ write (stream, *chunks)
def write (stream, *chunks):
    if stream.isatty ():
        for chunk in chunks:
            if isinstance (chunk, str):
                stream.write (chunk)
            else:
                try:
                    stream.write ('\x1b[{}m'.format(chunk[1]))
                    stream.write (chunk[0])
                finally:
                    stream.write ('\x1b[00m')
    else:
        for chunk in chunks:
            if isinstance (chunk, str):
                stream.write (chunk)
            else:
                stream.write (chunk[0])
    stream.flush ()
#}}}
#{{{ width ()
def width ():
    if sys.stdout.isatty ():
        rows, columns, xpixel, ypixel = struct.unpack (
            'HHHH',
            fcntl.ioctl (
                sys.stdout.fileno (),
                termios.TIOCGWINSZ,
                struct.pack ('HHHH', 0, 0, 0, 0)
            )
        )
        return columns
    else:
        return 80
#}}}
#{{{ ask (message, default)
def ask( *message, default ):
    if sys.stdin.isatty ():
        yes = ((' [', '35;01'), ('Y', '35'), ('/n]?', '35;01'))
        no = ((' [y/', '35;01'), ('N', '35'), (']?', '35;01'))
        ans = (yes, ('n', 'N')) if default else (no, ('y', 'Y'))

        # ask question
        question = [ (':: ', '35;01') ]
        question.extend (message)
        question.extend (ans [0])
        write (sys.stderr, *question)

        # read resutls
        try:
            if read () in ans[1]:
                return not default
            else:
                return default
        finally:
            sys.stderr.write ('\n')
            sys.stderr.flush ()
    else:
        return default
#}}}
#{{{ progress (message, length = 30)
@contextlib.contextmanager
def progress (*messages, length = 30):
    #{{{ bar drawer
    class Bar (object):
        def __init__ (self, length):
            self.length = length - 7
            self.value = 0
            self.tty = False
            if sys.stderr.isatty ():
                self.tty = True
                write (sys.stderr, ('[', '35'), '\x1b7',
                    ('-' * self.length, '35;01'),
                    ('] ', '35'), ('  0%', '37;01'))

        @property
        def Value (self):
            return self.value

        @Value.setter
        def Value (self, value):
            if self.tty and (value <= 1.0 or value >= 0):
                self.value = value
                draw = int (round (self.length * value))
                write (sys.stderr, '\x1b8', (draw * '#', '35;01'),
                    ((self.length - draw) * '-', '35;01'), ('] ', '35'),
                    ('{:>3}%'.format (int (round (value * 100.0))), '37;01'))
    #}}}
    #{{{ calculate caption
    symbols = width () - length
    caption = []
    for message in messages:
        if isinstance (message, str):
            # simple string
            if len (message) > symbols:
                # last chunk
                caption.append (message [symbols:])
                symbols = 0
                break
            else:
                caption.append (message)
                symbols -= len (message)
        else:
            # colored string
            text, attr = message
            if len (text) > symbols:
                # last chunk
                caption.append ((text [symbols:], attr))
                symbols = 0
                break
            else:
                caption.append (message)
                symbols -= len (text)

    if symbols != 0:
        caption.append (' ' * symbols)
    #}}}

    write (sys.stderr, *caption)
    bar = Bar (length)
    failed = False

    try:
        yield bar
    except BaseException as e:
        failed = True
        raise
    finally:
        if not failed:
            bar.Value = 1.0
        write (sys.stderr, '\n')
#}}}

# logging
def error (*message):
    write (sys.stderr, (':: error ', '31;01'), *message)
def warning (*message):
    write (sys.stderr, (':: warning ', '33;01'), *message)
def info (*message):
    write (sys.stderr, (':: info ', '32;01'), *message)

def Test ():
    import time

    count = 10
    with progress ((':: progress test', '35;01')) as bar:
        for i in range (count + 1):
            time.sleep (1)
            bar.Value = i/count

    while True:
        with pending((':: wait ', '35;01'), 'for something') as fail:
            try:
                time.sleep (5)
                break
            except BaseException:
                fail ('exception was caught\n')
        if ask (('restart', '35;01'), default=True):
            continue
        break

#{{{ .entrypoint
if __name__ == '__main__':
    try:
        with no_echo ():
            Test ()
    except KeyboardInterrupt:
        warning ('interrupted by user\n')
        sys.exit (1)
#}}}
# vim: ft=python :
