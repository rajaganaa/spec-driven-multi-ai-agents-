# T03: FAQ API Endpoints

## Feature
F04

## Role
coder

## Goal
Implement secure FastAPI endpoints in `main.py` for managing medical FAQ entries.

## Context Files (max 5)
- specs/features/F04.md
- main.py
- crud.py
- schemas.py

## Instructions
In `main.py`, create FastAPI endpoints:
- `POST /faqs`: Allows authenticated 'admin' users to create new FAQs. Returns the created FAQ.
- `GET /faqs`: Returns a list of all FAQs.
- `GET /faqs/{faq_id}`: Returns a specific FAQ entry by ID. Handles `faq_id` not found.
- `PUT /faqs/{faq_id}`: Allows authenticated 'admin' users to update an FAQ. Handles `faq_id` not found.
- `DELETE /faqs/{faq_id}`: Allows authenticated 'admin' users to delete an FAQ. Handles `faq_id` not found.Ensure proper dependency injection for database sessions and current authenticated user, leveraging existing authentication mechanisms (F02, F03).

## Acceptance Criteria
- [ ] The `POST /faqs` endpoint exists, requires authentication and 'admin' role, and successfully creates an FAQ.
- [ ] The `GET /faqs` endpoint exists and returns a list of all FAQs.
- [ ] The `GET /faqs/{faq_id}` endpoint exists, returns a specific FAQ, and returns 404 if the ID is not found.
- [ ] The `PUT /faqs/{faq_id}` endpoint exists, requires authentication and 'admin' role, updates an FAQ, and returns 404 if the ID is not found.
- [ ] The `DELETE /faqs/{faq_id}` endpoint exists, requires authentication and 'admin' role, deletes an FAQ, and returns 404 if the ID is not found.
- [ ] All endpoints correctly use `crud.py` functions and `schemas.py` models for request/response validation.

## Definition of Done
- FAQ API endpoints are implemented in `main.py`.

## Status
pending
