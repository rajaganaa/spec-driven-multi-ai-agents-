# F10: Chat Interaction API

## Goal
Integrate the core chatbot engine with the knowledge base to provide an interactive API endpoint for users to ask questions and receive answers.

## Acceptance Criteria
- [ ] A POST /chat endpoint accepts a JSON payload containing a 'question' string.
- [ ] The /chat endpoint successfully processes the question using the core chatbot engine (F01).
- [ ] The /chat endpoint retrieves relevant answers from the PostgreSQL knowledge base (F02).
- [ ] The /chat endpoint returns a JSON response containing the chatbot's answer.
- [ ] Chat responses do not expose or store any sensitive user data by default.

## Files Likely Touched
- app/api/v1/endpoints/chat.py
- app/services/qa_service.py
- app/core/chatbot.py

## Dependencies
- F08
- F09

## Assigned Lead
backend

## Status
planning
