# T05: End-to-End User Interface Testing

## Feature
F18

## Role
tester

## Goal
Verify the full functionality and compliance of the chatbot and FAQ user interface.

## Context Files (max 5)
- specs/features/F18-Chatbot_User_Interface_&_FAQ_Display.md
- src/pages/HomePage.js
- src/components/Chatbot.js
- src/components/FAQList.js

## Instructions
Conduct comprehensive manual and/or automated tests to ensure all acceptance criteria for F18 are met. Test the chatbot's interaction flow, the display and browsability of FAQs, the prominence and wording of the PHI disclaimer, and confirm the absence of client-side chat history storage. If backend APIs are not fully ready, use mocked responses for the API service layer.

## Acceptance Criteria
- [ ] A user can successfully input a question into the chatbot and receive a response, which is displayed dynamically.
- [ ] The chatbot response accurately reflects a matched FAQ answer (using mocked data if the backend is not integrated).
- [ ] The browsable list of general FAQs is displayed correctly on the page and is navigable.
- [ ] The disclaimer advising users not to enter PHI is clearly visible and prominently positioned near the chatbot input area.
- [ ] No chat history (user inputs or chatbot responses) is found in browser storage (e.g., Local Storage, Session Storage) or persists in the component's state after a page reload or component unmount.

## Definition of Done
(none)

## Status
pending
