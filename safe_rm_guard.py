#!/usr/bin/env python3
"""
safe-rm-guard: a Claude Code PreToolUse hook that blocks dangerous recursive
deletes (rm -rf and friends) WITHOUT the false positives that plague naive
keyword/regex detectors.

Usage as a Claude Code hook (.claude/settings.json):

    {
      "hooks": {
        "PreToolUse": [
          {
            "matcher": "Bash",
            "hooks": [
              { "type": "command", "command": "python /path/to/safe_rm_guard.py" }
            ]
          }
        ]
      }
    }

The hook reads the PreToolUse JSON on stdin. If the Bash command is a dangerous
recursive delete it prints a message to stderr and exits 2 (which blocks the
tool call). Otherwise it exits 0. It fails OPEN: malformed input never blocks.

CLI / testing mode:

    python safe_rm_guard.py "rm -rf /"          -> DANGEROUS (exit 1)
    python safe_rm_guard.py "rm -f notes.log"   -> safe      (exit 0)
    python safe_rm_guard.py --selftest          -> run the behavior matrix
"""
import json
import re
import sys


def is_dangerous_rm_command(command: str) -> bool:
    """
    Return True if `command` contains a dangerous recursive delete.

    The command is split on shell separators (; & | newline backtick) and into
    command-substitution bodies ($(...)), so that the word "rm" appearing in an
    echo/comment, or flags belonging to OTHER commands (e.g. `grep -rf`,
    `tar -rf`), can never combine into a false match. A segment is flagged only
    when its command word is `rm` -- or `rm` invoked via `find -exec`/`-execdir`/
    `xargs` -- AND it is recursive+force, or a recursive delete aimed at a broad
    path.
    """
    def _dangerous(flags):
        recursive = any(
            (t.startswith('-') and not t.startswith('--') and 'r' in t[1:])
            or t == '--recursive'
            for t in flags
        )
        force = any(
            (t.startswith('-') and not t.startswith('--') and 'f' in t[1:])
            or t == '--force'
            for t in flags
        )
        if recursive and force:
            return True
        if recursive:
            broad_paths = {'/', '/*', '~', '~/', '.', '..', '*'}
            non_flag = [t.strip('"').strip("'") for t in flags if not t.startswith('-')]
            if any(t in broad_paths or t.startswith('$home') for t in non_flag):
                return True
        return False

    for segment in re.split(r'[;&|\n`]+|\$\(', command.lower()):
        tokens = segment.split()
        # Skip leading `sudo` and `VAR=value` env-assignment prefixes.
        while tokens and (tokens[0] == 'sudo' or ('=' in tokens[0] and not tokens[0].startswith('-'))):
            tokens = tokens[1:]
        if not tokens:
            continue
        # (a) rm as the segment's own command word (not merely the letters "rm").
        if tokens[0] == 'rm' and _dangerous(tokens[1:]):
            return True
        # (b) rm wrapped by `find -exec`/`-execdir` or `xargs`
        #     e.g.  find . -exec rm -rf {} \;   |   ... | xargs -0 rm -rf
        for i in range(1, len(tokens)):
            if tokens[i] != 'rm':
                continue
            prev = tokens[i - 1]
            wrapped = prev in ('-exec', '-execdir', 'xargs')
            if not wrapped:
                # xargs may sit a few flag-tokens back (xargs -0 -n1 rm -rf)
                j = i - 1
                while j >= 0 and tokens[j].startswith('-'):
                    j -= 1
                wrapped = j >= 0 and tokens[j] == 'xargs'
            if wrapped and _dangerous(tokens[i + 1:]):
                return True
    return False


def main() -> None:
    # CLI mode: test a command (or run the self-test matrix).
    if len(sys.argv) > 1:
        if sys.argv[1] == '--selftest':
            from test_safe_rm_guard import _selftest
            sys.exit(1 if _selftest() else 0)
        command = ' '.join(sys.argv[1:])
        if is_dangerous_rm_command(command):
            print('DANGEROUS: recursive delete blocked')
            sys.exit(1)
        print('safe')
        sys.exit(0)

    # Hook mode: read the Claude Code PreToolUse JSON from stdin.
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)  # fail open

    if data.get('tool_name') != 'Bash':
        sys.exit(0)

    command = data.get('tool_input', {}).get('command', '')
    if is_dangerous_rm_command(command):
        print('BLOCKED: dangerous recursive delete prevented by safe-rm-guard', file=sys.stderr)
        sys.exit(2)  # exit 2 blocks the tool call in Claude Code

    sys.exit(0)


if __name__ == '__main__':
    main()
