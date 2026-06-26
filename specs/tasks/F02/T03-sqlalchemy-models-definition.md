# T03: SQLAlchemy Models Definition

## Feature
F02

## Role
coder

## Goal
Define SQLAlchemy models for User and FAQ entities.

## Context Files (max 5)
- specs/features/F02-backend-foundation.md
- models.py
- database.py

## Instructions
Create or update `models.py` to define `User` and `FAQ` SQLAlchemy models, inheriting from `Base` in `database.py`. The `User` model should include `id`, `email`, and `hashed_password`. The `FAQ` model should include `id`, `question`, and `answer`.

## Acceptance Criteria
- [ ] A `User` SQLAlchemy model is defined with `id` (primary key), `email` (unique), and `hashed_password` fields.
- [ ] An `FAQ` SQLAlchemy model is defined with `id` (primary key), `question`, and `answer` fields.
- [ ] Both models correctly inherit from `Base`.

## Definition of Done
(none)

## Status
pending
