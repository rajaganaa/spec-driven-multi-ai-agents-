# T04: Integrate Models & Initial Schema Creation

## Feature
F14

## Role
coder

## Goal
Integrate the database connection and models, and ensure the schema is created on application startup.

## Context Files (max 5)
- specs/features/F14-backend-core-db-setup.md
- main.py
- database.py
- models.py

## Instructions
Modify 'main.py' to include an event listener (e.g., a startup event) that ensures all defined SQLAlchemy models' tables are created in the database if they do not already exist. This should use the engine from 'database.py' and the Base metadata from 'models.py'.

## Acceptance Criteria
- [ ] The 'main.py' is modified to include a database initialization routine.
- [ ] Running the FastAPI application successfully connects to the configured PostgreSQL database.
- [ ] Upon application startup, the 'faqs' table is automatically created in the database if it doesn't already exist, matching the schema defined in 'models.py'.

## Definition of Done
- The 'main.py' is modified to include a database initialization routine.
- Running the FastAPI application successfully connects to the configured PostgreSQL database.
- Upon application startup, the 'faqs' table is automatically created in the database if it doesn't already exist, matching the schema defined in 'models.py'.

## Status
pending
