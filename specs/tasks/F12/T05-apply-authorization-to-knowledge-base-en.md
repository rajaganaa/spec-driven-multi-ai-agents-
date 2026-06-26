# T05: Apply Authorization to Knowledge Base Endpoints

## Feature
F12

## Role
coder

## Goal
Integrate the authentication dependency to protect the knowledge base management endpoints.

## Context Files (max 5)
- app/api/v1/endpoints/faqs.py
- app/auth/dependencies.py

## Instructions
Modify the `POST /faqs`, `PUT /faqs/{id}`, and `DELETE /faqs/{id}` endpoints in 'app/api/v1/endpoints/faqs.py' to require the `get_current_user` dependency. This ensures that only authenticated users can access these management functions.

## Acceptance Criteria
- [ ] The `POST /faqs` endpoint requires a valid JWT for access.
- [ ] The `PUT /faqs/{id}` endpoint requires a valid JWT for access.
- [ ] The `DELETE /faqs/{id}` endpoint requires a valid JWT for access.
- [ ] Accessing these endpoints without a valid JWT results in an HTTP 401 Unauthorized response.

## Definition of Done
- FAQ management endpoints are protected by authentication.

## Status
pending
