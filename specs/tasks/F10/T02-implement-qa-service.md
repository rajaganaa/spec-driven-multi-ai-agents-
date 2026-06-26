# T02: Implement QA Service

## Feature
F10

## Role
coder

## Goal
Implement `app/services/qa_service.py` to integrate the chatbot engine and knowledge base.

## Context Files (max 5)
- specs/features/F10-Chat_Interaction_API.md
- app/services/qa_service.py
- app/core/chatbot.py

## Instructions
Implement the `qa_service.py` based on the design from T01. Ensure the service contains a method (e.g., `process_question`) that orchestrates calls to the core chatbot engine (F01) and the knowledge base (F02) to generate an answer. Assume existing interfaces for F01 and F02.

## Acceptance Criteria
- [ ] The file `app/services/qa_service.py` is created and contains a `process_question(question: str) -> str` method or similar interface.
- [ ] The `process_question` method calls the core chatbot engine (F01) with the user's question.
- [ ] The `process_question` method retrieves relevant information from the knowledge base (F02) based on the question or chatbot's intermediate output.
- [ ] The method successfully synthesizes a single coherent answer from the chatbot and knowledge base inputs.

## Definition of Done
(none)

## Status
pending
