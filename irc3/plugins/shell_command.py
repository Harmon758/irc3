# -*- coding: utf-8 -*-
import os
import irc3
from irc3 import asyncio
from irc3.compat import text_type
from functools import partial
from irc3.plugins.command import Commands
__doc__ = '''
=================================================
:mod:`irc3.plugins.shell_command` Shell commands
=================================================

Allow to quickly add commands map to a shell command.
The bot will print stdout/stderr

..
    >>> from irc3.testing import IrcBot
    >>> from irc3.testing import ini2config

Usage::

    >>> config = ini2config("""
    ... [bot]
    ... includes =
    ...     irc3.plugins.shell_command
    ... [irc3.plugins.shell_command]
    ... myscript = /tmp/myscript
    ... # optional command configuration
    ... myscript.permission = runmyscrypt  # default permission is admin
    ... myscript.public = false  # default is true
    ... """)
    >>> bot = IrcBot(**config)

Then the uname command will be available::

    >>> bot.test(':gawel!user@host PRIVMSG #chan :!help myscript')
    PRIVMSG #chan :Run $ /tmp/myscript
    PRIVMSG #chan :!myscript [<args>...]

    >>> bot.test(':gawel!user@host PRIVMSG #chan :!myscript')

If the user provides some arguments then those will be available as an
environment var (to avoid shell injection) names ``IRC3_COMMAND_ARGS``
'''


@irc3.plugin
class Shell(object):

    requires = [Commands.__module__]

    def __init__(self, context):
        self.log = context.log
        self.context = context
        self.config = self.context.config[__name__]
        for k, v in self.config.items():
            if v.startswith('#') or '.' in k:
                continue
            dirname = os.path.abspath(v)
            if os.path.isdir(dirname):
                self.log.debug('Scanning for scripts in %s', dirname)
                for root, dirs, filenames in os.walk(dirname):
                    for filename in filenames:
                        binary = os.path.join(root, filename)
                        if os.access(binary, os.X_OK):
                            name = os.path.splitext(filename)[0]
                            self.register_command(name, binary)
            else:
                self.register_command(k, v)

    def register_command(self, k, v):
        meth = partial(self.shell_command, v)
        meth.__name__ = k
        meth.__doc__ = '''Run $ %s
        %%%%%s [<args>...]
        ''' % (v, k)
        p = {'permission': 'admin'}
        for opt in ('permission', 'public'):
            opt_key = '%s.%s' % (k, opt)
            if opt_key in self.config:
                p[opt] = self.config[opt_key]
        self.log.debug('Register command %s: $ %s', k, v)
        commands = self.context.get_plugin(Commands)
        commands[k] = (p, asyncio.coroutine(meth))

    def shell_command(self, command, mask, target, args, **kwargs):
        env = os.environ.copy()
        env['IRC3_COMMAND_ARGS'] = ' '.join(args['<args>'])
        proc = yield from asyncio.create_subprocess_shell(
            command, shell=True, env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT)
        yield from proc.wait()
        lines = yield from proc.stdout.read()
        if not isinstance(lines, text_type):
            lines = lines.decode('utf8')
        return lines.split(u'\n')