# T02: FAQ CRUD Operations

## Feature
F04

## Role
coder

## Goal
Implement database interaction functions for FAQ Create, Read, Update, and Delete operations in `crud.py`.

## Context Files (max 5)
- specs/features/F04.md
- crud.py
- models.py
- schemas.py

## Instructions
In `crud.py`, implement the following functions:
- `create_faq(db, faq: schemas.FAQCreate)`: Creates a new FAQ entry.
- `get_faq(db, faq_id: int)`: Retrieves a single FAQ entry by ID.
- `get_faqs(db, skip: int = 0, limit: int = 100)`: Retrieves a list of all FAQ entries.
- `update_faq(db, faq_id: int, faq_data: schemas.FAQCreate)`: Updates an existing FAQ entry. The `updated_at` field should be automatically set to the current timestamp.
- `delete_faq(db, faq_id: int)`: Deletes an FAQ entry by ID. All functions should handle database sessions correctly and return appropriate data or `None` if not found.

## Acceptance Criteria
- [ ] The `crud.py` file contains `create_faq`, `get_faq`, `get_faqs`, `update_faq`, and `delete_faq` functions.
- [ ] `create_faq` successfully adds a new FAQ to the database.
- [ ] `get_faq` retrieves the correct FAQ or `None` if not found.
- [ ] `get_faqs` returns a list of FAQs, respecting `skip` and `limit`.
- [ ] `update_faq` modifies the specified FAQ and updates its `updated_at` timestamp.
- [ ] `delete_faq` removes the specified FAQ from the database.
- [ ] All functions handle database sessions and commit/rollback where necessary.

## Definition of Done
- FAQ CRUD functions are implemented and tested against the database.

## Status
pending
