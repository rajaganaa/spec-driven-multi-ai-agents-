# T04: User Login Endpoint

## Feature
F03

## Role
coder

## Goal
Implement the `/auth/login` endpoint to authenticate users and return a JWT token upon successful login.

## Context Files (max 5)
- specs/features/F03-user-auth.md
- main.py
- auth.py
- models.py
- schemas.py

## Instructions
Create a POST endpoint at `/auth/login` in `main.py`. It should accept a `UserLogin` schema, verify the password using the utility from T01, and if successful, generate a JWT token using the utility from T02, returning it in a `Token` schema.

## Acceptance Criteria
- [ ] A POST request to `/auth/login` with correct username and password returns a valid JWT access token.
- [ ] The returned JWT token contains the user's ID and role.
- [ ] A POST request to `/auth/login` with incorrect username or password returns an `HTTPException` (e.g., 401 Unauthorized).

## Definition of Done
(none)

## Status
pending
