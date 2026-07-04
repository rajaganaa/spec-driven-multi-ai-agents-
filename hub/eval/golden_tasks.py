"""
hub/eval/golden_tasks.py — the fixed golden-task suite for hub/eval/runner.py

Each GoldenTask is deliberately shaped like a real task spec (same
fields spec_loader.py's markdown template expects — see
hub/agents/feature_lead.py's TaskPlanItem) so hub/eval/runner.py can
render it straight into a real task spec file and run it through the
*actual* hub/runner/task_runner.py pipeline, not a simulation of it.

`rubric` is separate from `acceptance_criteria`: acceptance_criteria are
the same concrete, checkable bullets a real Feature Lead would write,
and are what gates pass/fail (see hub/eval/schemas.py's docstring).
`rubric` items are softer, quality-of-implementation criteria (style,
robustness, absence of an anti-pattern) that the judge still scores
per-item, but that don't gate pass/fail on their own — the same
distinction a human code reviewer draws between "this doesn't meet
spec" (blocking) and "this could be cleaner" (nice-to-have).

Kept intentionally small and dependency-free (pure stdlib, no
filesystem/network access, no fixtures) — plain string content only, so
each task can run in an empty, throwaway project sandbox with zero
setup beyond what hub/eval/runner.py writes itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class GoldenTask:
    id: str
    title: str
    role: str  # coder | tester | reviewer | explorer
    goal: str
    instructions: str
    acceptance_criteria: List[str]
    context_files: List[str] = field(default_factory=list)
    rubric: List[str] = field(default_factory=list)
    definition_of_done: List[str] = field(default_factory=list)
    seed_files: dict = field(default_factory=dict)  # {relative_path: content} written into the
    # project sandbox before the task runs — for tasks whose instructions
    # reference a file that must already exist (a bug to fix, code to
    # test, code to review). Keys match context_files where applicable.
    expect_rejection: bool = False  # True when a "reviewer requested changes" result
                                 # IS the correct, expected outcome (not a failure to retry)


GOLDEN_TASKS: List[GoldenTask] = [
    GoldenTask(
        id="EVAL01",
        title="FizzBuzz function",
        role="coder",
        goal="Implement a standard FizzBuzz function.",
        instructions=(
            "Create `fizzbuzz.py` with a function `fizzbuzz(n: int) -> str` that returns "
            "'Fizz' if n is divisible by 3, 'Buzz' if divisible by 5, 'FizzBuzz' if divisible "
            "by both, and str(n) otherwise."
        ),
        acceptance_criteria=[
            "fizzbuzz.py exists and defines a function named fizzbuzz",
            "fizzbuzz(15) returns 'FizzBuzz'",
            "fizzbuzz(3) returns 'Fizz' and fizzbuzz(5) returns 'Buzz'",
            "fizzbuzz(7) returns '7'",
        ],
        rubric=["Function has a docstring or clear naming", "No unnecessary complexity for this simple task"],
    ),
    GoldenTask(
        id="EVAL02",
        title="String reversal utility",
        role="coder",
        goal="Implement a function that reverses a string without using slicing or the built-in reversed().",
        instructions=(
            "Create `reverse_string.py` with a function `reverse_string(s: str) -> str` that "
            "returns the input string reversed. Do not use Python slicing (`s[::-1]`) or the "
            "built-in `reversed()` — implement the reversal logic explicitly (e.g. a loop)."
        ),
        acceptance_criteria=[
            "reverse_string.py exists and defines reverse_string",
            "reverse_string('hello') returns 'olleh'",
            "reverse_string('') returns ''",
            "Implementation does not use slicing (s[::-1]) or reversed()",
        ],
        rubric=["Handles the empty-string case without a special-cased branch that looks bolted on"],
    ),
    GoldenTask(
        id="EVAL03",
        title="Fix an off-by-one bug",
        role="coder",
        goal="Fix a pre-existing off-by-one bug in a provided function.",
        instructions=(
            "A file `buggy_range_sum.py` already exists in this project with a function "
            "`range_sum(a: int, b: int) -> int` that is supposed to return the sum of all "
            "integers from a to b, inclusive, but has an off-by-one bug (it excludes b). "
            "Fix the bug in place — do not rewrite the function from scratch or rename it."
        ),
        acceptance_criteria=[
            "range_sum(1, 5) returns 15 (1+2+3+4+5)",
            "range_sum(3, 3) returns 3",
            "The function signature and file name are unchanged",
        ],
        rubric=["The fix is a minimal, targeted change rather than a full rewrite"],
        context_files=["buggy_range_sum.py"],
        seed_files={
            "buggy_range_sum.py": (
                "def range_sum(a: int, b: int) -> int:\n"
                '    """Return the sum of all integers from a to b, inclusive."""\n'
                "    total = 0\n"
                "    for i in range(a, b):  # BUG: excludes b, should be range(a, b + 1)\n"
                "        total += i\n"
                "    return total\n"
            ),
        },
    ),
    GoldenTask(
        id="EVAL04",
        title="Input validation for a divide function",
        role="coder",
        goal="Add proper error handling to a divide function that currently crashes on division by zero.",
        instructions=(
            "Create `safe_divide.py` with a function `safe_divide(a: float, b: float) -> float` "
            "that performs a / b, but raises a `ValueError` with a clear message if b is 0, "
            "instead of letting a ZeroDivisionError propagate."
        ),
        acceptance_criteria=[
            "safe_divide.py exists and defines safe_divide",
            "safe_divide(10, 2) returns 5.0",
            "safe_divide(10, 0) raises ValueError (not ZeroDivisionError)",
        ],
        rubric=["The ValueError message actually explains the problem (mentions zero/division)"],
    ),
    GoldenTask(
        id="EVAL05",
        title="Simple in-memory key-value store class",
        role="coder",
        goal="Implement a minimal in-memory key-value store with get/set/delete.",
        instructions=(
            "Create `kv_store.py` with a class `KVStore` supporting: `set(key, value)`, "
            "`get(key, default=None)` (returns default if key is missing), and "
            "`delete(key)` (no error if the key doesn't exist)."
        ),
        acceptance_criteria=[
            "kv_store.py exists and defines a class KVStore",
            "After store.set('a', 1), store.get('a') returns 1",
            "store.get('missing') returns None by default, and store.get('missing', 'x') returns 'x'",
            "store.delete('a') does not raise, and calling delete on a nonexistent key also does not raise",
        ],
        rubric=["Internal storage is a plain dict, not over-engineered with unnecessary abstraction"],
    ),
    GoldenTask(
        id="EVAL06",
        title="Write unit tests for a given function",
        role="tester",
        goal="Write pytest unit tests for an existing, already-implemented function.",
        instructions=(
            "A file `is_palindrome.py` already exists in this project with a function "
            "`is_palindrome(s: str) -> bool` (case-insensitive, ignores non-alphanumeric "
            "characters). Write `test_is_palindrome.py` with pytest tests covering: a simple "
            "palindrome, a non-palindrome, a palindrome with mixed case, a palindrome with "
            "spaces/punctuation (e.g. 'A man a plan a canal Panama'), and the empty string."
        ),
        acceptance_criteria=[
            "test_is_palindrome.py exists and is discoverable by pytest",
            "Running pytest on test_is_palindrome.py passes",
            "At least 4 distinct test cases are present, covering the scenarios listed in the instructions",
        ],
        rubric=["Test names clearly describe what each test checks"],
        context_files=["is_palindrome.py"],
        seed_files={
            "is_palindrome.py": (
                "import re\n\n\n"
                "def is_palindrome(s: str) -> bool:\n"
                '    """Case-insensitive palindrome check, ignoring non-alphanumeric characters."""\n'
                '    cleaned = re.sub(r"[^a-zA-Z0-9]", "", s).lower()\n'
                "    return cleaned == cleaned[::-1]\n"
            ),
        },
    ),
    GoldenTask(
        id="EVAL07",
        title="Refactor duplicated logic into a helper",
        role="coder",
        goal="Remove duplicated validation logic by extracting a shared helper function.",
        instructions=(
            "A file `user_forms.py` already exists with two functions, `validate_signup_form` "
            "and `validate_login_form`, that each independently check whether an `email` field "
            "looks like a valid email (contains '@' and a '.' after it) with near-identical "
            "code. Extract that duplicated check into a single helper function `_is_valid_email"
            "(email: str) -> bool` and have both existing functions call it, without changing "
            "either function's existing behavior or signature."
        ),
        acceptance_criteria=[
            "A function named _is_valid_email exists in user_forms.py",
            "validate_signup_form and validate_login_form both call _is_valid_email instead of "
            "duplicating the check inline",
            "Existing behavior is unchanged: valid emails still pass, invalid ones still fail, "
            "for both functions",
        ],
        rubric=["No leftover duplicated validation code remains after the refactor"],
        context_files=["user_forms.py"],
        seed_files={
            "user_forms.py": (
                "def validate_signup_form(email: str, password: str) -> bool:\n"
                '    if "@" not in email or "." not in email.split("@")[-1]:\n'
                "        return False\n"
                "    return len(password) >= 8\n\n\n"
                "def validate_login_form(email: str, password: str) -> bool:\n"
                '    if "@" not in email or "." not in email.split("@")[-1]:\n'
                "        return False\n"
                "    return bool(password)\n"
            ),
        },
    ),
    GoldenTask(
        id="EVAL08",
        title="Review a snippet for a security issue",
        role="reviewer",
        goal="Identify a SQL-injection vulnerability in a provided snippet and reject it with clear feedback.",
        instructions=(
            "A file `search.py` already exists containing a `search_users(name)` function "
            "that builds a SQL query via raw f-string interpolation of `name` directly into the "
            "query text (a SQL-injection vulnerability). Review this code. Do not fix it "
            "yourself — your job as Reviewer is to reject it and clearly explain the specific "
            "vulnerability and what should be done instead (parameterized queries)."
        ),
        acceptance_criteria=[
            "The review explicitly identifies SQL injection (or unsanitized/unparameterized "
            "query construction) as the problem",
            "The review recommends parameterized queries (or equivalent, e.g. an ORM) as the fix",
            "The task is not marked as approved/passing given this unresolved vulnerability",
        ],
        rubric=["Feedback is specific to the actual vulnerable line, not generic security advice"],
        context_files=["search.py"],
        expect_rejection=True,
        seed_files={
            "search.py": (
                "def search_users(name, db_connection):\n"
                '    query = f"SELECT * FROM users WHERE name = \'{name}\'"\n'
                "    cursor = db_connection.cursor()\n"
                "    cursor.execute(query)\n"
                "    return cursor.fetchall()\n"
            ),
        },
    ),
]
