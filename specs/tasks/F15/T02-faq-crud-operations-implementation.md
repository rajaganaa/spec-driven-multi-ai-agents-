# T02: FAQ CRUD Operations Implementation

## Feature
F15

## Role
coder

## Goal
Implement functions for creating, reading (all and by ID), updating, and deleting FAQ entries in the database.

## Context Files (max 5)
- crud/faq.py
- schemas/faq.py

## Instructions
Implement the following CRUD functions within `crud/faq.py`: `create_faq` (takes `FAQCreate` schema and DB session, returns `FAQ` model), `get_faqs` (takes DB session, returns list of `FAQ` models), `get_faq` (takes FAQ ID and DB session, returns `FAQ` model or None), `update_faq` (takes FAQ ID, `FAQUpdate` schema, and DB session, returns updated `FAQ` model or None), and `delete_faq` (takes FAQ ID and DB session, returns boolean indicating success/failure).

## Acceptance Criteria
- [ ] The `create_faq` function correctly adds a new FAQ entry to the database and returns the created `FAQ` model instance.
- [ ] The `get_faqs` function retrieves and returns a list of all `FAQ` entries from the database.
- [ ] The `get_faq` function retrieves a specific `FAQ` entry by its ID, returning the `FAQ` model instance if found, or `None` otherwise.
- [ ] The `update_faq` function correctly modifies an existing `FAQ` entry by ID with the provided data, returning the updated `FAQ` model instance or `None` if the ID does not exist.
- [ ] The `delete_faq` function successfully removes an `FAQ` entry by ID, returning `True` on success or `False` if the ID does not exist.

## Definition of Done
(none)

## Status
pending
