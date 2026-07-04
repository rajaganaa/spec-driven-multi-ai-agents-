# T03: FAQ Form Component (Create/Update)

## Feature
F06

## Role
coder

## Goal
Develop a reusable FAQ form component for creating and updating FAQ entries.

## Context Files (max 5)
- frontend/src/components/FAQForm.js
- frontend/src/services/api.js
- specs/features/F06-ReactAdminDashboard.md

## Instructions
1. Create `frontend/src/components/FAQForm.js` that accepts props for initial data (for editing an existing FAQ) and an `onSubmit` handler. 2. The form should include input fields for 'question' and 'answer'. 3. Implement basic client-side validation for required fields (question, answer). 4. The `onSubmit` handler should be responsible for calling the appropriate `api.js` method (`createFAQ` for new entries or `updateFAQ` for existing ones) based on whether initial data was provided.

## Acceptance Criteria
- [ ] A reusable `FAQForm` component exists with input fields for 'question' and 'answer'.
- [ ] The `FAQForm` can be used to create new FAQ entries, submitting the data via an API call.
- [ ] The `FAQForm` can be pre-populated with existing FAQ data for editing, and submitting it makes an update API call.
- [ ] Form submissions include valid data for both 'question' and 'answer'.

## Definition of Done
(none)

## Status
pending
