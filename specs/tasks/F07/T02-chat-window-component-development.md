# T02: Chat Window Component Development

## Feature
F07

## Role
coder

## Goal
Develop a reusable React component for displaying chat messages within the interface.

## Context Files (max 5)
- specs/features/F07-React-User-Chat-Interface.md
- frontend/src/components/ChatWindow.js

## Instructions
Create the `frontend/src/components/ChatWindow.js` React component. This component should accept an array of message objects as props, where each message object contains a sender (e.g., 'user', 'chatbot') and the message text. It should display these messages in an ordered list, differentiating between user questions and chatbot answers.

## Acceptance Criteria
- [ ] The `ChatWindow` component is created in `frontend/src/components/ChatWindow.js`.
- [ ] It accepts a `messages` prop, which is an array of objects `{ sender: string, text: string }`.
- [ ] The component iterates through the `messages` array and displays each message.
- [ ] User and chatbot messages are visually distinguishable (e.g., different styling, alignment).

## Definition of Done
(none)

## Status
pending
