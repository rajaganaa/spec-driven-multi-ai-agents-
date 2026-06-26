# T02: Database Connection & Session

## Feature
F02

## Role
coder

## Goal
Establish and validate a PostgreSQL database connection using SQLAlchemy.

## Context Files (max 5)
- specs/features/F02-backend-foundation.md
- database.py
- config.py

## Instructions
Create or update `database.py` to configure SQLAlchemy, including `engine`, `SessionLocal`, and `Base` for declarative models. Use the `DATABASE_URL` from `config.py`.

## Acceptance Criteria
- [ ] SQLAlchemy engine is created using `DATABASE_URL` from `config.py`.
- [ ] A `SessionLocal` class is defined for database session management.
- [ ] A `Base` declarative base is defined for models.
- [ ] A `get_db` dependency is provided for FastAPI to manage database sessions.

## Definition of Done
(none)

## Status
pending
