# T01: Environment Configuration

## Feature
F02

## Role
coder

## Goal
Implement loading of environment variables for sensitive configurations.

## Context Files (max 5)
- specs/features/F02-backend-foundation.md
- config.py

## Instructions
Create or update `config.py` to define a `Settings` class using Pydantic's BaseSettings to load `DATABASE_URL` and `SECRET_KEY` from environment variables, providing sensible defaults for development.

## Acceptance Criteria
- [ ] A `Settings` class exists in `config.py`.
- [ ] It loads `DATABASE_URL` and `SECRET_KEY` from environment variables.
- [ ] Sensitive configurations are not hardcoded.

## Definition of Done
(none)

## Status
pending
