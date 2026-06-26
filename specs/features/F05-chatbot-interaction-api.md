# F05: Chatbot Interaction API

## Goal
Create an API endpoint that processes user questions, queries the stored medical FAQs to find relevant answers, and returns them, ensuring secure handling of user input.

## Acceptance Criteria
- [ ] POST /chatbot/ask accepts a user's question.
- [ ] The API searches the FAQ database (F03) for the most relevant answer.
- [ ] The API returns the best matching answer or a default 'no match found' response.
- [ ] User question input is sanitized to prevent injection attacks.
- [ ] No personally identifiable information from user questions is stored persistently by the chatbot logic.

## Files Likely Touched
- main.py
- chatbot_logic.py
- crud.py
- schemas.py

## Dependencies
- F02
- F04

## Assigned Lead
fullstack-developer

## Status
planning
