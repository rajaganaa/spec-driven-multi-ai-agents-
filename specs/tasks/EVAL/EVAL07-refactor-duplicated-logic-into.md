# EVAL07: Refactor duplicated logic into a helper

## Feature
FEVAL

## Role
coder

## Goal
Remove duplicated validation logic by extracting a shared helper function.

## Context Files (max 5)
- user_forms.py

## Instructions
A file `user_forms.py` already exists with two functions, `validate_signup_form` and `validate_login_form`, that each independently check whether an `email` field looks like a valid email (contains '@' and a '.' after it) with near-identical code. Extract that duplicated check into a single helper function `_is_valid_email(email: str) -> bool` and have both existing functions call it, without changing either function's existing behavior or signature.

## Acceptance Criteria
- [ ] A function named _is_valid_email exists in user_forms.py
- [ ] validate_signup_form and validate_login_form both call _is_valid_email instead of duplicating the check inline
- [ ] Existing behavior is unchanged: valid emails still pass, invalid ones still fail, for both functions

## Definition of Done
(none)

## Status
pending
