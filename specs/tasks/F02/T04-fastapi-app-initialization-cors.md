# T04: FastAPI App Initialization & CORS

## Feature
F02

## Role
coder

## Goal
Initialize the core FastAPI application and configure essential CORS middleware.

## Context Files (max 5)
- specs/features/F02-backend-foundation.md
- main.py
- config.py

## Instructions
Create or update `main.py` to initialize the FastAPI application. Integrate CORS middleware using `config.py` settings to allow access from the frontend, specifically `http://localhost:3000` or a configured environment variable.

## Acceptance Criteria
- [ ] A FastAPI application instance `app` is created in `main.py`.
- [ ] CORS middleware is added to the FastAPI app.
- [ ] The CORS configuration allows origins that include 'http://localhost:3000' and permits common HTTP methods and headers.

## Definition of Done
(none)

## Status
pending
