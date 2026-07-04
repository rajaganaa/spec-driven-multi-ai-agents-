# T03: Authentication Endpoints: Register and Login

## Feature
F12

## Role
coder

## Goal
Implement the `/auth/register` and `/auth/login` API endpoints to allow user registration and authentication.

## Context Files (max 5)
- app/api/v1/endpoints/auth.py
- app/crud/user.py
- app/auth/security.py

## Instructions
Create `POST /auth/register` and `POST /auth/login` endpoints in 'app/api/v1/endpoints/auth.py'. The register endpoint should hash the password before storing the user via CRUD functions. The login endpoint should verify credentials and return a JWT upon successful authentication.

## Acceptance Criteria
- [ ] The `POST /auth/register` endpoint successfully creates a new user with a securely hashed password.
- [ ] The `POST /auth/login` endpoint returns a JWT upon successful authentication with correct credentials.
- [ ] The `POST /auth/login` endpoint returns an appropriate error (e.g., 401 Unauthorized) for incorrect credentials.

## Definition of Done
- Registration endpoint fully implemented.
- Login endpoint fully implemented.

## Status
pending
