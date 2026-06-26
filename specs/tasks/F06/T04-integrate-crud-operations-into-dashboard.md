# T04: Integrate CRUD Operations into Dashboard

## Feature
F06

## Role
coder

## Goal
Integrate the create, update, and delete functionalities into the Admin Dashboard, utilizing the `FAQForm` component.

## Context Files (max 5)
- frontend/src/pages/AdminDashboard.js
- frontend/src/components/FAQForm.js
- frontend/src/services/api.js
- specs/features/F06-ReactAdminDashboard.md

## Instructions
1. In `frontend/src/pages/AdminDashboard.js`, add a button or link to enable administrators to add new FAQs. Clicking this should display or navigate to the `FAQForm` for creation. 2. For each FAQ item listed, add an 'Edit' button that, when clicked, displays the `FAQForm` pre-filled with that FAQ's data for updating. 3. For each FAQ item listed, add a 'Delete' button that, when confirmed, triggers a deletion via the `api.js` service. 4. After any successful create, update, or delete operation, refresh the FAQ list displayed on the dashboard.

## Acceptance Criteria
- [ ] Administrators can click a prominent UI element (e.g., button) to add a new FAQ, which correctly presents the `FAQForm` for creation.
- [ ] New FAQ entries are successfully created via the `FAQForm` and immediately appear in the FAQ list on the dashboard.
- [ ] Each FAQ in the list has an 'Edit' option that correctly opens the `FAQForm` pre-filled with the FAQ's current data.
- [ ] Edited FAQ entries are successfully updated via the `FAQForm` and the changes are immediately reflected in the FAQ list.
- [ ] Each FAQ in the list has a 'Delete' option that, upon confirmation, successfully removes the FAQ entry from the backend and the displayed list.

## Definition of Done
(none)

## Status
pending
