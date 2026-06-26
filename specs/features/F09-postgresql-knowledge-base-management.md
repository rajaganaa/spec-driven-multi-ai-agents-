# F09: PostgreSQL Knowledge Base Management

## Goal
Implement the data model for medical FAQs and provide CRUD operations for managing the knowledge base securely in PostgreSQL.

## Acceptance Criteria
- [ ] A PostgreSQL database schema for storing FAQs (question, answer, categories) is defined and migrable.
- [ ] Endpoints for GET /faqs (retrieve all), GET /faqs/{id} (retrieve single), POST /faqs (add new), PUT /faqs/{id} (update existing), and DELETE /faqs/{id} (remove) are implemented.
- [ ] Data persistence for FAQ entries is confirmed through unit and integration tests.

## Files Likely Touched
- app/models/faq.py
- app/crud/faq.py
- app/api/v1/endpoints/faqs.py
- app/db/database.py

## Dependencies
- F08

## Assigned Lead
backend

## Status
planning
