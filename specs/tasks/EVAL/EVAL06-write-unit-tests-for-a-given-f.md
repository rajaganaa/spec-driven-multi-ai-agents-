# EVAL06: Write unit tests for a given function

## Feature
FEVAL

## Role
tester

## Goal
Write pytest unit tests for an existing, already-implemented function.

## Context Files (max 5)
- is_palindrome.py

## Instructions
A file `is_palindrome.py` already exists in this project with a function `is_palindrome(s: str) -> bool` (case-insensitive, ignores non-alphanumeric characters). Write `test_is_palindrome.py` with pytest tests covering: a simple palindrome, a non-palindrome, a palindrome with mixed case, a palindrome with spaces/punctuation (e.g. 'A man a plan a canal Panama'), and the empty string.

## Acceptance Criteria
- [ ] test_is_palindrome.py exists and is discoverable by pytest
- [ ] Running pytest on test_is_palindrome.py passes
- [ ] At least 4 distinct test cases are present, covering the scenarios listed in the instructions

## Definition of Done
(none)

## Status
pending
