# T03: Main Chat Page Integration and Logic

## Feature
F11

## Role
coder

## Goal
Integrate the chat components into App.js, manage the chat state, and connect the UI to the API service.

## Context Files (max 5)
- frontend/src/App.js
- frontend/src/components/ChatWindow.js
- frontend/src/components/MessageInput.js
- frontend/src/services/api.js
- specs/features/F11-Frontend_Chat_User_Interface.md

## Instructions
1. In 'frontend/src/App.js', import and use 'ChatWindow' and 'MessageInput'. 2. Manage the chat history state (an array of message objects) using 'useState'. 3. Implement a handler for 'MessageInput''s 'onSubmit' prop. This handler should: Add the user's message to the chat history. Call the 'sendMessage' function from 'api.js' with the user's message. Upon receiving a response from the API, add the chatbot's response to the chat history. Clear the input field after submission.

## Acceptance Criteria
- [ ] 'frontend/src/App.js' renders both 'ChatWindow' and 'MessageInput'.
- [ ] Typing a message in 'MessageInput' and submitting it displays the user's message in 'ChatWindow'.
- [ ] After a user message is submitted, a call is made to the 'sendMessage' API service.
- [ ] The chatbot's response received from 'sendMessage' is displayed in 'ChatWindow' below the user's message.
- [ ] The input field is cleared after a message is sent.

## Definition of Done
(none)

## Status
pending
