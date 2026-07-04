# T03: Chatbot Page UI and Logic Implementation

## Feature
F07

## Role
coder

## Goal
Implement the core chat functionality on the Chatbot page, managing conversation state and user interaction.

## Context Files (max 5)
- specs/features/F07-React-User-Chat-Interface.md
- frontend/src/pages/Chatbot.js
- frontend/src/components/ChatWindow.js
- frontend/src/services/api.js

## Instructions
Create `frontend/src/pages/Chatbot.js`. This page should contain: an input field for user questions, a button to submit questions, and integrate the `ChatWindow` component to display the conversation history. Use the `api.js` service to send user questions to the backend and update the conversation history with both the user's question and the chatbot's answer. Maintain the conversation history in the component's state.

## Acceptance Criteria
- [ ] A `Chatbot` page component is created in `frontend/src/pages/Chatbot.js`.
- [ ] The page includes an input field for users to type questions.
- [ ] A button or submission mechanism exists to send the question.
- [ ] User-submitted questions are added to the conversation history displayed by `ChatWindow`.
- [ ] The `postQuestion` function from `api.js` is called when a question is submitted.
- [ ] Chatbot answers received from the API are added to the conversation history and displayed.
- [ ] The conversation history persists within the current session on the page.

## Definition of Done
(none)

## Status
pending
