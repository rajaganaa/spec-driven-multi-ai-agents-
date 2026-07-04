# EVAL08: Review a snippet for a security issue

## Feature
FEVAL

## Role
reviewer

## Goal
Identify a SQL-injection vulnerability in a provided snippet and reject it with clear feedback.

## Context Files (max 5)
- search.py

## Instructions
A file `search.py` already exists containing a `search_users(name)` function that builds a SQL query via raw f-string interpolation of `name` directly into the query text (a SQL-injection vulnerability). Review this code. Do not fix it yourself — your job as Reviewer is to reject it and clearly explain the specific vulnerability and what should be done instead (parameterized queries).

## Acceptance Criteria
- [ ] The review explicitly identifies SQL injection (or unsanitized/unparameterized query construction) as the problem
- [ ] The review recommends parameterized queries (or equivalent, e.g. an ORM) as the fix
- [ ] The task is not marked as approved/passing given this unresolved vulnerability

## Definition of Done
(none)

## Status
pending
