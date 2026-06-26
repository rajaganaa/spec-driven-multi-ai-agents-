# T06: Apply Security to FAQ Endpoints

## Feature
F03

## Role
coder

## Goal
Protect FAQ management API endpoints, requiring authentication for all and 'admin' role for creation, update, and deletion.

## Context Files (max 5)
- specs/features/F03-user-auth.md
- main.py
- dependencies.py

## Instructions
Locate the existing FAQ endpoints (as per F02). Apply the `get_current_user` dependency to all FAQ endpoints to ensure they require authentication. Specifically apply `require_role('admin')` to FAQ creation (POST), update (PUT/PATCH), and deletion (DELETE) endpoints in `main.py`.

## Acceptance Criteria
- [ ] Accessing FAQ read (GET) or list (GET) endpoints without a valid JWT token results in a 401 Unauthorized error.
- [ ] Accessing FAQ read (GET) or list (GET) endpoints with a valid JWT token (any role) is successful.
- [ ] Accessing FAQ creation, update, or deletion endpoints with a valid JWT but without an 'admin' role results in a 403 Forbidden error.
- [ ] Accessing FAQ creation, update, or deletion endpoints with a valid JWT from an 'admin' user is successful.

## Definition of Done
(none)

## Status
pending
