# T04: Integrate Audit Logging into FAQ Administration Endpoints

## Feature
F13

## Role
coder

## Goal
Add audit logging capabilities to all administrative actions (create, update, delete) on FAQ knowledge base entries.

## Context Files (max 5)
- app/api/v1/endpoints/faqs.py
- app/crud/audit_log.py

## Instructions
Modify the `app/api/v1/endpoints/faqs.py` file to call the audit logging functions from `app/crud/audit_log.py` whenever an FAQ is created, updated, or deleted. Ensure relevant details about the action and the administrative user performing it are logged.

## Acceptance Criteria
- [ ] Creating a new FAQ entry via `app/api/v1/endpoints/faqs.py` results in a corresponding entry in the audit log.
- [ ] Updating an existing FAQ entry via `app/api/v1/endpoints/faqs.py` results in a corresponding entry in the audit log.
- [ ] Deleting an FAQ entry via `app/api/v1/endpoints/faqs.py` results in a corresponding entry in the audit log.
- [ ] Each audit log entry accurately captures the action type (e.g., 'FAQ_CREATE', 'FAQ_UPDATE', 'FAQ_DELETE'), the user performing the action, and the ID of the affected FAQ.

## Definition of Done
(none)

## Status
pending
