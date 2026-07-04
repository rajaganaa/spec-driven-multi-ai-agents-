# T02: Admin Dashboard (FAQ Listing)

## Feature
F06

## Role
coder

## Goal
Create the main Admin Dashboard page to display a list of all medical FAQ entries.

## Context Files (max 5)
- frontend/src/pages/AdminDashboard.js
- frontend/src/services/api.js
- frontend/src/App.js
- specs/features/F06-ReactAdminDashboard.md

## Instructions
1. Create `frontend/src/pages/AdminDashboard.js`. 2. In `AdminDashboard.js`, fetch the list of FAQ entries using the `api.js` service (ensuring the authentication token is used). 3. Render the fetched FAQs in a clear, readable list format, displaying at least the question and answer for each entry. 4. Ensure that access to this page is restricted to authenticated users, redirecting unauthenticated users to the login page.

## Acceptance Criteria
- [ ] Authenticated administrators can access `/admin/dashboard`.
- [ ] The `/admin/dashboard` page displays a list of all FAQ entries fetched securely from the backend API.
- [ ] Each FAQ entry in the list clearly shows its question and answer.

## Definition of Done
(none)

## Status
pending
