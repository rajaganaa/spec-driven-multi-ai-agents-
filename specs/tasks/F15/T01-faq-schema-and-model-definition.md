# T01: FAQ Schema and Model Definition

## Feature
F15

## Role
coder

## Goal
Define the Pydantic schema for FAQ request/response and the SQLAlchemy ORM model for database interaction.

## Context Files (max 5)
- schemas/faq.py

## Instructions
Create Pydantic models for `FAQBase`, `FAQCreate`, `FAQUpdate`, and `FAQInDB` to handle request/response validation. Define the SQLAlchemy ORM model for `FAQ` with fields for `id` (primary key, auto-increment), `question` (string), `answer` (string), and `category` (string). Ensure the SQLAlchemy model maps correctly to a database table.

## Acceptance Criteria
- [ ] A Pydantic schema `FAQBase` exists with fields `question` (str), `answer` (str), `category` (str).
- [ ] Pydantic schemas `FAQCreate` (inheriting from `FAQBase`) and `FAQUpdate` (inheriting from `FAQBase`, optional fields) are defined.
- [ ] A Pydantic schema `FAQInDB` exists, inheriting from `FAQBase` and adding `id` (int).
- [ ] An SQLAlchemy ORM model `FAQ` is defined, mapping to a database table with `id` (Integer, primary_key, autoincrement), `question` (String), `answer` (String), and `category` (String).

## Definition of Done
(none)

## Status
pending
