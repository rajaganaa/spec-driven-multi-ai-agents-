# T03: Develop Chatbot Interface Component with Disclaimer

## Feature
F18

## Role
coder

## Goal
Create the chatbot interaction component, including input, dynamic response display, PHI disclaimer, and temporary storage.

## Context Files (max 5)
- specs/features/F18-Chatbot_User_Interface_&_FAQ_Display.md
- src/components/Chatbot.js
- src/services/api.js

## Instructions
Implement the `Chatbot` React component in `src/components/Chatbot.js`. This component must include an input field for user questions, a display area for chatbot responses, and a prominent disclaimer advising users not to enter PHI. Ensure that chat history is not stored persistently on the client side; user input fields should be cleared after submission.

## Acceptance Criteria
- [ ] The `src/components/Chatbot.js` component is created and displays an input field for user questions.
- [ ] Chatbot responses are dynamically displayed within the component after a query is sent via `sendChatbotQuery(query)`.
- [ ] A prominent disclaimer about not entering PHI is visible within the chatbot interface.
- [ ] Chat history is not stored client-side (e.g., local storage, session storage, or persistent component state); user input is cleared after each submission.

## Definition of Done
(none)

## Status
pending
