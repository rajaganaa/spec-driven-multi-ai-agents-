# EVAL04: Input validation for a divide function

## Feature
FEVAL

## Role
coder

## Goal
Add proper error handling to a divide function that currently crashes on division by zero.

## Context Files (max 5)
(none)

## Instructions
Create `safe_divide.py` with a function `safe_divide(a: float, b: float) -> float` that performs a / b, but raises a `ValueError` with a clear message if b is 0, instead of letting a ZeroDivisionError propagate.

## Acceptance Criteria
- [ ] safe_divide.py exists and defines safe_divide
- [ ] safe_divide(10, 2) returns 5.0
- [ ] safe_divide(10, 0) raises ValueError (not ZeroDivisionError)

## Definition of Done
(none)

## Status
pending
