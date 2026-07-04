# T01: User Model, Schemas & Password Hashing

## Feature
F03

## Role
coder

## Goal
Define the User database model, Pydantic schemas for authentication, and a utility for secure password hashing and verification.

## Context Files (max 5)
- specs/features/F03-user-auth.md
- models.py
- schemas.py
- auth.py

## Instructions
Create a `User` model in `models.py` with fields for `username` (unique), `hashed_password`, and `role` (defaulting to 'user'). Define Pydantic schemas in `schemas.py` for `UserCreate`, `UserLogin`, and `Token`. Implement `hash_password` and `verify_password` functions in `auth.py` using bcrypt.

## Acceptance Criteria
- [ ] `models.py` contains a `User` model with `username`, `hashed_password`, and `role` fields.
- [ ] `schemas.py` defines `UserCreate`, `UserLogin`, and `Token` Pydantic schemas.
- [ ] `auth.py` includes `hash_password(password: str) -> str` and `verify_password(plain_password: str, hashed_password: str) -> bool` functions using bcrypt.

## Definition of Done
(none)

## Status
pending
