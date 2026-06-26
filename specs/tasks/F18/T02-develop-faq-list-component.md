# T02: Develop FAQ List Component

## Feature
F18

## Role
coder

## Goal
Create a reusable React component to display a browsable list of FAQs.

## Context Files (max 5)
- specs/features/F18-Chatbot_User_Interface_&_FAQ_Display.md
- src/components/FAQList.js
- src/services/api.js

## Instructions
Develop the `FAQList` React component in `src/components/FAQList.js`. This component should utilize the `getFAQs()` function from `src/services/api.js` to fetch and display the general FAQs. Each FAQ item should present both the question and its corresponding answer clearly.

## Acceptance Criteria
- [ ] The `src/components/FAQList.js` component is created and renders a list of FAQs.
- [ ] FAQs are fetched using the `getFAQs()` API call.
- [ ] Each FAQ item displays both a question and its answer in a readable format.

## Definition of Done
(none)

## Status
pending
