# T03: Implement POST /chat Endpoint

## Feature
F10

## Role
coder

## Goal
Create a new API endpoint POST `/chat` that uses the `qa_service`.

## Context Files (max 5)
- specs/features/F10-Chat_Interaction_API.md
- app/api/v1/endpoints/chat.py
- app/services/qa_service.py

## Instructions
Add a new POST endpoint `/chat` to `app/api/v1/endpoints/chat.py`. This endpoint should accept a JSON payload containing a 'question' string, call the `qa_service.process_question` method, and return the chatbot's answer as a JSON response. Implement appropriate error handling for invalid input.

## Acceptance Criteria
- [ ] The file `app/api/v1/endpoints/chat.py` defines a `POST /chat` endpoint.
- [ ] The endpoint accepts a JSON payload with a mandatory `question` field (string).
- [ ] The endpoint successfully calls `qa_service.process_question` with the provided question.
- [ ] The endpoint returns a JSON response in the format `{"answer": "..."}` containing the processed answer.
- [ ] Error handling for missing or invalid `question` in the payload returns an appropriate HTTP error (e.g., 400 Bad Request).
- [ ] Responses from the endpoint do not contain any sensitive user data.

## Definition of Done
(none)

## Status
pending
