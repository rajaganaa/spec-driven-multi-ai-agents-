# T02: Basic Chat UI Components

## Feature
F11

## Role
coder

## Goal
Develop foundational React components for displaying messages and accepting user input.

## Context Files (max 5)
- frontend/src/components/MessageInput.js
- frontend/src/components/ChatWindow.js
- specs/features/F11-Frontend_Chat_User_Interface.md

## Instructions
1. Create 'frontend/src/components/MessageInput.js'. This component should include a text input field and a submit button. It should expose an 'onSubmit' prop that gets called with the current input value when the button is clicked or Enter is pressed. 2. Create 'frontend/src/components/ChatWindow.js'. This component should accept a 'messages' prop (an array of message objects, e.g., '{ sender: 'user' | 'bot', text: string }') and render them in a scrollable container. Each message should clearly indicate its sender.

## Acceptance Criteria
- [ ] 'frontend/src/components/MessageInput.js' renders a text input and a button.
- [ ] Submitting the input (button click or Enter key) triggers the 'onSubmit' prop with the current text content.
- [ ] 'frontend/src/components/ChatWindow.js' renders a list of messages.
- [ ] Messages from 'user' and 'bot' are visually distinguishable.
- [ ] The chat window is scrollable if content overflows.

## Definition of Done
(none)

## Status
pending
