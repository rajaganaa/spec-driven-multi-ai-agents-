# T07: Test Authorization for FAQ Management Endpoints

## Feature
F12

## Role
tester

## Goal
Verify that knowledge base management endpoints are correctly protected by authentication and authorization.

## Context Files (max 5)
- app/api/v1/endpoints/faqs.py
- app/auth/dependencies.py
- app/auth/security.py

## Instructions
Write integration tests to cover access to the FAQ management endpoints (`POST /faqs`, `PUT /faqs/{id}`, `DELETE /faqs/{id}`). Test attempts to access these endpoints without a token, with an invalid token, and with a valid token. Ensure appropriate HTTP status codes are returned.

## Acceptance Criteria
- [ ] Accessing `POST /faqs` without a JWT results in an HTTP 401 Unauthorized response.
- [ ] Accessing `PUT /faqs/{id}` without a JWT results in an HTTP 401 Unauthorized response.
- [ ] Accessing `DELETE /faqs/{id}` without a JWT results in an HTTP 401 Unauthorized response.
- [ ] Accessing these endpoints with an invalid or expired JWT results in an HTTP 401 Unauthorized response.
- [ ] Accessing these endpoints with a valid JWT successfully processes the request (e.g., creates an FAQ, updates an FAQ, deletes an FAQ).

## Definition of Done
- All protected FAQ management endpoints are thoroughly tested for correct authorization enforcement.

## Status
pending
