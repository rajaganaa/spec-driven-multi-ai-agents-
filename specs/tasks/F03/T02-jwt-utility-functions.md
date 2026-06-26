# T02: JWT Utility Functions

## Feature
F03

## Role
coder

## Goal
Implement functions for creating, decoding, and validating JWT tokens.

## Context Files (max 5)
- specs/features/F03-user-auth.md
- auth.py
- schemas.py

## Instructions
In `auth.py`, implement functions to `create_access_token` (taking user data like ID and role) and `decode_access_token` (which handles token validation and expiration). Define a JWT secret key and algorithm.

## Acceptance Criteria
- [ ] `auth.py` contains `create_access_token(data: dict) -> str` which generates a JWT with `sub` (user ID) and `role` claims.
- [ ] `auth.py` contains `decode_access_token(token: str) -> dict` which decodes and validates the JWT, raising an error for invalid or expired tokens.

## Definition of Done
(none)

## Status
pending
