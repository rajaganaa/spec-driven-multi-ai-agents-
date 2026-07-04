# T01: Chatbot API Service Integration

## Feature
F07

## Role
coder

## Goal
Implement the API service layer to communicate with the medical FAQ chatbot backend.

## Context Files (max 5)
- specs/features/F07-React-User-Chat-Interface.md
- frontend/src/services/api.js

## Instructions
Create or update `frontend/src/services/api.js` to include a function, e.g., `postQuestion`, that sends a POST request to the `/api/chatbot/ask` endpoint (F04's endpoint) with the user's question and handles the response. Ensure proper error handling.

## Acceptance Criteria
- [ ] A new function `postQuestion` exists in `frontend/src/services/api.js`.
- [ ] The `postQuestion` function sends a POST request to `/api/chatbot/ask`.
- [ ] The request body contains the user's question in the format expected by F04.
- [ ] The function correctly returns the chatbot's answer upon successful response.
- [ ] Basic error handling is implemented for API call failures.

## Definition of Done
(none)

## Status
pending
