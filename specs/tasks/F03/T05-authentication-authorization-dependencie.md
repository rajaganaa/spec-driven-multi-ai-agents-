# T05: Authentication & Authorization Dependencies

## Feature
F03

## Role
coder

## Goal
Create FastAPI dependencies for JWT token validation and role-based access control.

## Context Files (max 5)
- specs/features/F03-user-auth.md
- dependencies.py
- auth.py
- models.py

## Instructions
In `dependencies.py`, implement `get_current_user` which extracts and decodes the JWT from the request header, validates it (using T02's utilities), fetches the corresponding user from the database, and returns the user object. Implement `require_role(role: str)` which is a dependency that uses `get_current_user` and checks if the authenticated user has the specified role.

## Acceptance Criteria
- [ ] `dependencies.py` contains `get_current_user` that, when applied to an endpoint, successfully retrieves the `User` object from a valid JWT.
- [ ] `get_current_user` raises `HTTPException(401)` if no token is provided, the token is invalid, or expired.
- [ ] `dependencies.py` contains `require_role(role: str)` which raises `HTTPException(403)` if the authenticated user's role does not match the required role.

## Definition of Done
(none)

## Status
pending
