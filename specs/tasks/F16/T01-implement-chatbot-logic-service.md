# T01: Implement Chatbot Logic Service

## Feature
F16

## Role
coder

## Goal
Develop the core service logic for processing user questions, matching FAQs, and ensuring HIPAA compliance regarding data persistence.

## Context Files (max 5)
- specs/features/F16-Chatbot_Interaction_API_(HIPAA-Aware).md
- services/chatbot_logic.py

## Instructions
Implement a function, e.g., `ask_chatbot(question: str)`, in `services/chatbot_logic.py`. This function should contain the logic to find the most relevant FAQ answer. It must ensure that no user input or derived information is stored persistently in any form (e.g., logs, database). The function should return the matched FAQ answer or a predefined 'no match' response.

## Acceptance Criteria
- [ ] A function named `ask_chatbot(question: str)` exists in `services/chatbot_logic.py`.
- [ ] The `ask_chatbot` function correctly identifies and returns a relevant FAQ answer based on the input question.
- [ ] If no relevant FAQ is found, the `ask_chatbot` function returns a consistent 'no match' response.
- [ ] The implementation explicitly ensures that no part of the user's question or any processed data derived from it is written to logs, databases, or any other persistent storage within this service.
- [ ] The service logic is unit-tested to ensure correctness and adherence to HIPAA compliance for data handling.

## Definition of Done
- The `services/chatbot_logic.py` file contains the implemented `ask_chatbot` function.
- The FAQ matching logic is correctly implemented.
- The function explicitly avoids persisting user input or derived data.
- Unit tests for the service logic pass and confirm functionality and non-persistence.

## Status
pending
