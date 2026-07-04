# T06: Test User Registration and Login Flow

## Feature
F12

## Role
tester

## Goal
Verify the functionality of the user registration and login endpoints, including JWT generation.

## Context Files (max 5)
- app/api/v1/endpoints/auth.py
- app/auth/security.py
- app/crud/user.py

## Instructions
Write integration tests to cover the full user registration and login flow. Test successful registration, registration with existing username, successful login, and login with incorrect credentials. Verify that successful login returns a valid JWT.

## Acceptance Criteria
- [ ] A new user can successfully register via `POST /auth/register`.
- [ ] Attempting to register with an existing username returns an appropriate error.
- [ ] An existing user can successfully log in via `POST /auth/login` and receives a JWT.
- [ ] Login with incorrect username or password returns an HTTP 401 Unauthorized error.
- [ ] The returned JWT from a successful login is valid and decodable using the configured security key.

## Definition of Done
- All authentication endpoints are thoroughly tested for correct behavior and error handling.

## Status
pending
