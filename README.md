# safe-rm-guard

A [Claude Code](https://docs.claude.com/claude-code) `PreToolUse` hook that blocks dangerous recursive deletes (`rm -rf` and friends), **without** the false positives that plague naive keyword/regex detectors.

> A guardrail, not a roadblock: it stops the catastrophic deletes and stays out of your way for everything else.

## The problem it solves

A common way to write a "block dangerous `rm`" hook is a greedy regex like:

```
\brm\s+.*-[a-z]*r[a-z]*f
```

That `\brm` matches the **letters** "rm" anywhere on the line, and the unanchored `.*` lets any later `-…r…f`-shaped token complete the match, even when that token belongs to a *different* command. The result is a hook that blocks safe, everyday commands:

| Command | Naive greedy hook | Reality |
|---|---|---|
| `rm one.log; grep -rf "pat" .` | ❌ blocked | safe: a single-file delete + a recursive grep |
| `rm a.txt && tar -rf archive.tar b.txt` | ❌ blocked | safe: `tar -rf` appends to an archive |
| `echo "backup (rm is hook-blocked); cp only"; cp a b` | ❌ blocked | safe: there is **no `rm` at all**, only the letters "rm" in a comment |

That last row is real. A backup script that *deliberately used `cp`* instead of `rm` was blocked anyway, because it *mentioned* "rm" in an echo and happened to contain `-first` (from a `print('R-first:')`) later on the same line. Two innocent fragments, combined by a greedy `.*`, looked like `rm … -…f`.

## How it works

`safe-rm-guard` parses instead of pattern-matching:

1. Split the command on shell separators (`;`, `&`, `|`, newline, backtick) and command-substitution openers (`$(`).
2. In each segment, find the **command word** (skipping `sudo` and `VAR=value` prefixes).
3. Flag the segment only if its command word is `rm` (or `rm` invoked via `find -exec`/`-execdir`/`xargs`) **and** it is recursive **and** forced (`-rf` in any spelling), or a recursive delete aimed at a broad path (`/`, `~`, `.`, `*`, …).

Because each segment must actually *be* an `rm` command, the word "rm" in an echo, or a flag from a neighbouring command, can never trigger it.

## Behavior

| Command | Result |
|---|---|
| `rm -rf /` | 🚫 blocked |
| `rm -rf build/` | 🚫 blocked |
| `cd x && rm -rf /tmp` | 🚫 blocked |
| `echo $(rm -rf /tmp)` | 🚫 blocked |
| `find . -exec rm -rf {} \;` | 🚫 blocked |
| `find . \| xargs rm -rf` | 🚫 blocked |
| `sudo rm -rf /` | 🚫 blocked |
| `rm -f notes.log` | ✅ allowed (single-file force delete) |
| `rm one.log; grep -rf "pat" .` | ✅ allowed |
| `git rm --cached secret.txt` | ✅ allowed |
| `echo "rm -rf /tmp"` | ✅ allowed (it's just an echo) |

## Install

Copy `safe_rm_guard.py` somewhere on your machine, then register it in `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "python /absolute/path/to/safe_rm_guard.py" }
        ]
      }
    ]
  }
}
```

The hook reads the `PreToolUse` JSON on stdin. If the Bash command is a dangerous recursive delete, it prints to stderr and exits `2` (which blocks the tool call). Otherwise it exits `0`.

## CLI / testing

```bash
python safe_rm_guard.py "rm -rf /"          # -> DANGEROUS (exit 1)
python safe_rm_guard.py "rm -f notes.log"   # -> safe      (exit 0)
python safe_rm_guard.py --selftest          # run the behavior matrix
```

## Tests

```bash
python -m pytest test_safe_rm_guard.py
# or, with no dependencies:
python test_safe_rm_guard.py
```

## Design notes

- **Fails open.** A hook that crashes or sees malformed input must never block your work, so it exits `0` on anything it can't parse.
- **Defense in depth, not a sandbox.** It catches the common catastrophic forms (`rm -rf`, broad-path recursive, compound, subshell, `find`/`xargs`-wrapped). It is intentionally *not* a complete adversarial sandbox. Heavily obfuscated deletes can still get through. Pair it with real backups and least-privilege.
- **No dependencies.** Pure standard-library Python 3.8+.

## License

MIT. See [LICENSE](LICENSE).
