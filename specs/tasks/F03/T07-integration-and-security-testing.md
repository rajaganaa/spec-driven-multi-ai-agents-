# T07: Integration and Security Testing

## Feature
F03

## Role
tester

## Goal
Verify all authentication and authorization flows, including edge cases and error handling.

## Context Files (max 5)
- specs/features/F03-user-auth.md
- main.py
- auth.py
- dependencies.py

## Instructions
Write comprehensive integration tests covering user registration, login, JWT token validity, and role-based access control for the FAQ endpoints. Test successful flows, as well as scenarios with incorrect credentials, missing tokens, invalid tokens, expired tokens, and unauthorized user roles.

## Acceptance Criteria
- [ ] Tests confirm new user registration creates a user with a hashed password in the DB.
- [ ] Tests confirm successful login returns a valid JWT token.
- [ ] Tests confirm endpoints requiring authentication deny access without a valid JWT (401).
- [ ] Tests confirm endpoints requiring authentication grant access with a valid JWT.
- [ ] Tests confirm 'admin' protected endpoints deny access to non-'admin' roles (403).
- [ ] Tests confirm 'admin' protected endpoints grant access to 'admin' users.

## Definition of Done
(none)

## Status
pending
