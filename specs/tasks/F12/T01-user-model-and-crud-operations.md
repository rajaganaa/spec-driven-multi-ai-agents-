# T01: User Model and CRUD Operations

## Feature
F12

## Role
coder

## Goal
Define the User model and implement basic CRUD operations for user management, including secure password storage.

## Context Files (max 5)
- app/models/user.py
- app/crud/user.py

## Instructions
Define a SQLAlchemy User model in 'app/models/user.py' with fields for id, username, and a hashed password. Implement CRUD functions in 'app/crud/user.py' to create, retrieve, and update user records.

## Acceptance Criteria
- [ ] The User model is correctly defined with an ID, username, and password hash field.
- [ ] A function to create a new user with a hashed password exists in app/crud/user.py.
- [ ] A function to retrieve a user by username exists in app/crud/user.py.
- [ ] A function to retrieve a user by ID exists in app/crud/user.py.

## Definition of Done
- User model defined.
- CRUD operations for users implemented.

## Status
pending
