# T04: Create Integration Tests for /chat Endpoint

## Feature
F10

## Role
tester

## Goal
Verify the functionality of the new `POST /chat` endpoint, including its integration with the `qa_service`.

## Context Files (max 5)
- specs/features/F10-Chat_Interaction_API.md
- app/api/v1/endpoints/chat.py
- app/services/qa_service.py

## Instructions
Write comprehensive integration tests for the `POST /chat` endpoint. These tests should cover successful interactions with valid questions, as well as error scenarios such as missing or malformed input. Ensure the tests confirm the response format and content, including the absence of sensitive user data.

## Acceptance Criteria
- [ ] New integration tests for the `POST /chat` endpoint are added to the test suite.
- [ ] Tests successfully send a valid question to `/chat` and assert that the response contains an `answer` field (non-empty string).
- [ ] Tests verify the endpoint's behavior when a `question` is missing or is not a string, expecting a 400 Bad Request or similar error.
- [ ] Tests confirm that no sensitive user data is inadvertently exposed in the `/chat` endpoint's responses.
- [ ] All newly added tests pass.

## Definition of Done
(none)

## Status
pending
