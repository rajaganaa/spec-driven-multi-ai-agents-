# F15: FAQ Content Management API

## Goal
Provide API endpoints for administrative management (CRUD) of medical FAQ content.

## Acceptance Criteria
- [ ] POST /api/faqs successfully creates a new FAQ entry with a question, answer, and category.
- [ ] GET /api/faqs retrieves a list of all FAQ entries.
- [ ] GET /api/faqs/{id} retrieves a specific FAQ entry by its ID.
- [ ] PUT /api/faqs/{id} updates an existing FAQ entry.
- [ ] DELETE /api/faqs/{id} removes an FAQ entry.
- [ ] The API ensures that no Personal Health Information (PHI) is processed or stored via these FAQ content management endpoints.

## Files Likely Touched
- routers/faqs.py
- schemas/faq.py
- crud/faq.py

## Dependencies
- F14

## Assigned Lead
backend

## Status
planning
