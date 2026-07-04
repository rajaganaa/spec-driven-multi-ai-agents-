# T01: FAQ Data Model and Schemas

## Feature
F04

## Role
coder

## Goal
Define the SQLAlchemy model and Pydantic schemas for medical FAQ entries.

## Context Files (max 5)
- specs/features/F04.md
- models.py
- schemas.py

## Instructions
Create an `FAQ` SQLAlchemy model in `models.py` with fields: `id` (primary key), `question`, `answer`, `created_at` (default current timestamp), `updated_at` (nullable, defaults to `created_at` on creation, updates on modification). Create `FAQBase`, `FAQCreate`, and `FAQOut` Pydantic schemas in `schemas.py` to reflect the FAQ structure for request and response bodies.

## Acceptance Criteria
- [ ] The `models.py` file contains an `FAQ` SQLAlchemy model with the specified fields and types.
- [ ] The `schemas.py` file contains `FAQBase`, `FAQCreate`, and `FAQOut` Pydantic models for FAQ data.
- [ ] The `FAQCreate` schema correctly defines input fields for creating a new FAQ (question, answer).
- [ ] The `FAQOut` schema correctly defines output fields for an FAQ, including `id`, `question`, `answer`, `created_at`, and `updated_at`.

## Definition of Done
- FAQ model and schemas are implemented according to the spec.

## Status
pending
