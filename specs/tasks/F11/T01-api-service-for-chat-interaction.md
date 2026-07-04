# T01: API Service for Chat Interaction

## Feature
F11

## Role
coder

## Goal
Implement a function to interact with the backend /chat endpoint.

## Context Files (max 5)
- frontend/src/services/api.js
- specs/features/F11-Frontend_Chat_User_Interface.md

## Instructions
Create a new file 'frontend/src/services/api.js' if it doesn't exist. Implement an async function, e.g., 'sendMessage', that takes a message string, constructs a POST request to '/chat' with the message in the body, and returns the chatbot's response. Use 'fetch' or 'axios'.

## Acceptance Criteria
- [ ] A function 'sendMessage(message: string)' exists in 'frontend/src/services/api.js'.
- [ ] Calling 'sendMessage("hello")' makes a POST request to '/chat' with a JSON body '{"message": "hello"}'.
- [ ] The function correctly parses and returns the JSON response from the backend.

## Definition of Done
(none)

## Status
pending
