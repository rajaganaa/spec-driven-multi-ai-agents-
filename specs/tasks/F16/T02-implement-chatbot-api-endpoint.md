# T02: Implement Chatbot API Endpoint

## Feature
F16

## Role
coder

## Goal
Create the FastAPI POST endpoint `/api/chatbot/ask` that accepts user questions and utilizes the chatbot logic service.

## Context Files (max 5)
- specs/features/F16-Chatbot_Interaction_API_(HIPAA-Aware).md
- routers/chatbot.py
- services/chatbot_logic.py

## Instructions
Implement a POST endpoint `/api/chatbot/ask` in `routers/chatbot.py`. This endpoint should accept a JSON body with a `question` field (string). It must call the `ask_chatbot` function from `services/chatbot_logic.py` and return its response. Ensure proper input validation for the `question` field and appropriate HTTP response formatting.

## Acceptance Criteria
- [ ] The API endpoint `POST /api/chatbot/ask` is correctly implemented in `routers/chatbot.py`.
- [ ] The endpoint successfully receives a JSON payload with a `question` string.
- [ ] The endpoint correctly calls the `ask_chatbot` function from `services/chatbot_logic.py`.
- [ ] The API endpoint returns the result from `ask_chatbot` as its HTTP response body.
- [ ] Input validation is in place for the `question` field to ensure it's a non-empty string.

## Definition of Done
- The `routers/chatbot.py` file implements the `POST /api/chatbot/ask` endpoint.
- The endpoint correctly integrates with the `ask_chatbot` function from `services/chatbot_logic.py`.
- Input validation for the `question` field is implemented.
- The endpoint is locally tested and responds correctly to valid and invalid inputs.

## Status
pending
