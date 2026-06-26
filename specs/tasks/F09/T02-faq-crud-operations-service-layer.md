# T02: FAQ CRUD Operations (Service Layer)

## Feature
F09

## Role
coder

## Goal
Implement core CRUD functions for managing FAQ entries in the database.

## Context Files (max 5)
- specs/features/F09-PostgreSQL_Knowledge_Base_Management.md
- app/crud/faq.py
- app/models/faq.py

## Instructions
Implement the following functions in `app/crud/faq.py`: `create_faq(db, faq_data)`, `get_faq(db, faq_id)`, `get_all_faqs(db, skip, limit)`, `update_faq(db, faq_id, faq_data)`, and `delete_faq(db, faq_id)`. These functions should interact with the `FAQ` model to perform the respective database operations.

## Acceptance Criteria
- [ ] The `app/crud/faq.py` file contains functions for creating, retrieving (single and all), updating, and deleting FAQ entries.
- [ ] All CRUD functions correctly interact with the `FAQ` model and database session.
- [ ] Error handling for non-existent IDs (e.g., for get, update, delete) is considered.

## Definition of Done
- CRUD functions for FAQs are implemented in `app/crud/faq.py`.
- Functions correctly use the SQLAlchemy ORM.
- Basic error handling for CRUD operations is in place.

## Status
pending
