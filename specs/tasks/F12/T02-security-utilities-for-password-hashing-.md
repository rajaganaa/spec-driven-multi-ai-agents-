# T02: Security Utilities for Password Hashing and JWT

## Feature
F12

## Role
coder

## Goal
Implement utilities for secure password hashing/verification and JSON Web Token (JWT) creation/decoding.

## Context Files (max 5)
- app/auth/security.py
- app/models/user.py

## Instructions
Implement functions in 'app/auth/security.py' for hashing plain text passwords, verifying hashed passwords, creating JWTs, and decoding JWTs to extract user identifiers. Use a secure hashing algorithm (e.g., bcrypt) and ensure JWTs include an expiration time.

## Acceptance Criteria
- [ ] A function `hash_password(password: str) -> str` is implemented and returns a securely hashed password.
- [ ] A function `verify_password(plain_password: str, hashed_password: str) -> bool` is implemented and correctly compares passwords.
- [ ] A function `create_access_token(data: dict) -> str` is implemented and generates a valid JWT with an expiry.
- [ ] A function `decode_access_token(token: str) -> Optional[str]` is implemented and correctly decodes the JWT to return the subject (e.g., username), or None if invalid/expired.

## Definition of Done
- Password hashing/verification utilities are functional.
- JWT creation/decoding utilities are functional.

## Status
pending
