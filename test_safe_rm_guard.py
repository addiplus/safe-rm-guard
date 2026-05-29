"""
Behavior matrix for safe-rm-guard. Runs under pytest, or standalone:

    python -m pytest test_safe_rm_guard.py
    python test_safe_rm_guard.py
"""
from safe_rm_guard import is_dangerous_rm_command

# (command, expected_dangerous)
CASES = [
    # --- safe: must NOT be blocked ---
    ("rm -f notes.log", False),
    ("rm one.log; grep -rf 'pat' .", False),
    ("rm a.txt && tar -rf archive.tar b.txt", False),
    ('echo "backup (rm is hook-blocked); cp only"; cp a b', False),
    ('echo "rm -rf /tmp"', False),
    ("git rm --cached secret.txt", False),
    ("npm run format", False),
    ("rm file.ts && rmdir dir", False),
    # --- dangerous: must be blocked ---
    ("rm -rf /", True),
    ("rm -rf build/", True),
    ("rm -fr ~", True),
    ("rm --recursive --force /tmp", True),
    ("cd x && rm -rf /tmp", True),
    ("echo $(rm -rf /tmp)", True),
    ("find . -exec rm -rf {} \\;", True),
    ("find . | xargs rm -rf", True),
    ("find . | xargs -0 -n1 rm -rf", True),
    ("sudo rm -rf /", True),
]


def test_matrix():
    for command, expected in CASES:
        assert is_dangerous_rm_command(command) is expected, command


def _selftest():
    failures = 0
    for command, expected in CASES:
        got = is_dangerous_rm_command(command)
        ok = got is expected
        failures += not ok
        print(f"{'ok ' if ok else 'XX '} block={got!s:5} expect={expected!s:5}  {command}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return failures


if __name__ == '__main__':
    raise SystemExit(1 if _selftest() else 0)
