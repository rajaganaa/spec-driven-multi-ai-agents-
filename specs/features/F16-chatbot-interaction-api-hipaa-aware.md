# F16: Chatbot Interaction API (HIPAA-Aware)

## Goal
Implement an API endpoint that processes user questions and returns relevant FAQ answers, adhering to HIPAA principles by not processing or storing PHI from user inputs.

## Acceptance Criteria
- [ ] POST /api/chatbot/ask accepts a user question as a string.
- [ ] The API processes the user question to find the most relevant answer from the stored FAQs.
- [ ] The API returns the matched FAQ answer (or a 'no match' response) as the chatbot's reply.
- [ ] The API explicitly *does not* store user question inputs or derived information that could potentially contain PHI.
- [ ] Any user input received by this API is treated as ephemeral and not persisted in any logs or databases.

## Files Likely Touched
- routers/chatbot.py
- services/chatbot_logic.py

## Dependencies
- F14

## Assigned Lead
backend

## Status
planning
