# T01: Implement API Service for Chatbot and FAQs

## Feature
F18

## Role
coder

## Goal
Create and implement functions in the API service for fetching FAQs and sending chatbot queries.

## Context Files (max 5)
- specs/features/F18-Chatbot_User_Interface_&_FAQ_Display.md
- src/services/api.js

## Instructions
Implement two asynchronous functions in `src/services/api.js`: one to fetch a list of general FAQs and another to send a user query to the chatbot backend and retrieve its response. These functions should handle potential API errors gracefully.

## Acceptance Criteria
- [ ] A function `getFAQs()` is implemented in `src/services/api.js` that successfully retrieves a list of FAQ objects from the backend.
- [ ] A function `sendChatbotQuery(query)` is implemented in `src/services/api.js` that successfully sends a user query string and receives a chatbot response string from the backend.

## Definition of Done
(none)

## Status
pending
