# T04: Authentication Dependency for Protected Routes

## Feature
F12

## Role
coder

## Goal
Implement a FastAPI dependency to extract and validate JWTs from requests, providing authenticated user information.

## Context Files (max 5)
- app/auth/dependencies.py
- app/auth/security.py
- app/crud/user.py

## Instructions
Create a dependency function in 'app/auth/dependencies.py' (e.g., `get_current_user`) that expects an Authorization header with a Bearer token. This dependency should decode the JWT, retrieve the user from the database using 'app/crud/user.py', and raise an HTTPException for invalid or missing tokens.

## Acceptance Criteria
- [ ] A dependency `get_current_user` is implemented in 'app/auth/dependencies.py'.
- [ ] The dependency successfully extracts and decodes a valid JWT from the Authorization header.
- [ ] The dependency retrieves the corresponding user object from the database.
- [ ] The dependency raises an `HTTPException(401)` if the token is missing, invalid, or expired, or if the user is not found.

## Definition of Done
- Authentication dependency implemented and functional.

## Status
pending
