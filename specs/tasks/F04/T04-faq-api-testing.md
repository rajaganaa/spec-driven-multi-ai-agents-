# T04: FAQ API Testing

## Feature
F04

## Role
tester

## Goal
Develop and execute comprehensive unit and integration tests for the FAQ management API.

## Context Files (max 5)
- specs/features/F04.md
- main.py
- crud.py
- models.py
- schemas.py

## Instructions
Write a test suite covering:
- Successful creation, retrieval, update, and deletion of FAQs by an 'admin' user.
- Retrieval of FAQs by any authenticated user.
- Attempted creation, update, and deletion by non-'admin' authenticated users (should result in 403 Forbidden).
- Attempted access to non-existent FAQ entries (should result in 404 Not Found).
- Validation of data structure for responses (e.g., `question`, `answer`, `created_at`, `updated_at` fields).

## Acceptance Criteria
- [ ] Tests exist for successfully creating an FAQ with an 'admin' user.
- [ ] Tests exist for successfully retrieving all FAQs and a specific FAQ.
- [ ] Tests confirm that non-'admin' users cannot create, update, or delete FAQs (403 Forbidden response).
- [ ] Tests confirm that attempting to retrieve, update, or delete a non-existent FAQ returns a 404 Not Found response.
- [ ] Tests verify that FAQ responses include `question`, `answer`, `created_at`, and `updated_at`.
- [ ] All tests pass successfully.

## Definition of Done
- Comprehensive test suite for F04 is implemented and all tests pass.

## Status
pending
