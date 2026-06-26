# T04: API Integration Tests for FAQ Endpoints

## Feature
F15

## Role
tester

## Goal
Write comprehensive integration tests for all FAQ API endpoints to ensure their correct functionality.

## Context Files (max 5)
- tests/test_faqs.py
- routers/faqs.py
- schemas/faq.py

## Instructions
Create a new test file `tests/test_faqs.py`. Write integration tests using a test client (e.g., `FastAPI TestClient`) to cover all CRUD operations for the FAQ API. Tests should verify successful creation, retrieval (all and by ID), updating, and deletion. Include tests for edge cases like attempting to retrieve, update, or delete non-existent FAQs.

## Acceptance Criteria
- [ ] Tests confirm that `POST /api/faqs` successfully creates an FAQ and returns the correct data and status code.
- [ ] Tests confirm that `GET /api/faqs` successfully retrieves a list of FAQs, including newly created ones.
- [ ] Tests confirm that `GET /api/faqs/{id}` retrieves the correct FAQ by ID and returns a 404 for a non-existent ID.
- [ ] Tests confirm that `PUT /api/faqs/{id}` successfully updates an FAQ and returns a 404 for a non-existent ID.
- [ ] Tests confirm that `DELETE /api/faqs/{id}` successfully deletes an FAQ and returns a 404 for a non-existent ID.
- [ ] Tests verify that no PHI is present in the mock data or test responses.

## Definition of Done
(none)

## Status
pending
