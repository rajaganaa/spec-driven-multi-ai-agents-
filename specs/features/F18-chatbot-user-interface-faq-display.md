# F18: Chatbot User Interface & FAQ Display

## Goal
Create the user-facing interface for interacting with the chatbot and browsing FAQs, with clear guidance on HIPAA compliance.

## Acceptance Criteria
- [ ] A dedicated page or component allows users to input questions and view chatbot responses in a chat-like interface.
- [ ] Chatbot responses dynamically display the matched FAQ answer from the backend API.
- [ ] A separate section or component displays a browsable list of general FAQs fetched from the backend.
- [ ] The user interface prominently displays a disclaimer advising users *not* to enter Personal Health Information (PHI) into the chatbot.
- [ ] User input fields for the chatbot are designed to be temporary and do not store chat history on the client side.

## Files Likely Touched
- src/components/Chatbot.js
- src/components/FAQList.js
- src/pages/HomePage.js
- src/services/api.js

## Dependencies
- F17
- F16
- F15

## Assigned Lead
frontend

## Status
planning
