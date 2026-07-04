# EVAL03: Fix an off-by-one bug

## Feature
FEVAL

## Role
coder

## Goal
Fix a pre-existing off-by-one bug in a provided function.

## Context Files (max 5)
- buggy_range_sum.py

## Instructions
A file `buggy_range_sum.py` already exists in this project with a function `range_sum(a: int, b: int) -> int` that is supposed to return the sum of all integers from a to b, inclusive, but has an off-by-one bug (it excludes b). Fix the bug in place — do not rewrite the function from scratch or rename it.

## Acceptance Criteria
- [ ] range_sum(1, 5) returns 15 (1+2+3+4+5)
- [ ] range_sum(3, 3) returns 3
- [ ] The function signature and file name are unchanged

## Definition of Done
(none)

## Status
pending
