# T03: Test Chatbot API Functionality and HIPAA Compliance

## Feature
F16

## Role
tester

## Goal
Verify the end-to-end functionality of the chatbot API, including correct FAQ matching and strict adherence to the HIPAA non-persistence requirement.

## Context Files (max 5)
- specs/features/F16-Chatbot_Interaction_API_(HIPAA-Aware).md
- routers/chatbot.py
- services/chatbot_logic.py

## Instructions
Write comprehensive integration tests for the `POST /api/chatbot/ask` endpoint. These tests must cover scenarios including: successful FAQ matching for various common questions, handling of 'no match' questions, and edge cases like empty or malformed inputs. Crucially, implement explicit checks to confirm that user input questions (and any derived data) are *not* persisted in any logs, databases, or temporary storage after API calls, effectively verifying HIPAA compliance.

## Acceptance Criteria
- [ ] Integration tests for `POST /api/chatbot/ask` are written and successfully pass.
- [ ] Tests verify that various valid user questions receive relevant FAQ answers.
- [ ] Tests confirm that questions with no match receive the designated 'no match' response.
- [ ] Tests verify that empty or malformed questions are handled gracefully, returning appropriate error messages or status codes.
- [ ] Explicit tests are in place to confirm that user input questions and any data derived from them are *not* persisted in any log files, databases, or other storage mechanisms after API calls, using techniques such as mock storage inspection or log file checks.

## Definition of Done
- Comprehensive integration tests for `POST /api/chatbot/ask` are written and executed.
- All tests pass, covering functional requirements and HIPAA non-persistence compliance.
- Test reports confirm the absence of user input data persistence.

## Status
pending
