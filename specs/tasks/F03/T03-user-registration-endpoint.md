# T03: User Registration Endpoint

## Feature
F03

## Role
coder

## Goal
Implement the `/auth/register` endpoint to allow new user creation with hashed passwords.

## Context Files (max 5)
- specs/features/F03-user-auth.md
- main.py
- auth.py
- models.py
- schemas.py

## Instructions
Create a POST endpoint at `/auth/register` in `main.py`. It should accept a `UserCreate` schema, hash the provided password using the utility from T01, create a new `User` in the database, and return a success message.

## Acceptance Criteria
- [ ] A POST request to `/auth/register` with a unique username and password successfully creates a new user in the database with a hashed password and 'user' role.
- [ ] Attempting to register with an existing username returns an appropriate HTTP error (e.g., 400 Bad Request).

## Definition of Done
(none)

## Status
pending
