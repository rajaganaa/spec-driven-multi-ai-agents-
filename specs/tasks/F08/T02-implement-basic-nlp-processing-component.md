# T02: Implement Basic NLP Processing Components

## Feature
F08

## Role
coder

## Goal
Implement core natural language processing functionalities like tokenization and keyword extraction.

## Context Files (max 5)
- app/core/chatbot.py
- specs/features/F08-Backend_API_Infrastructure_&_Core_Chatbot_Engine.md

## Instructions
Create or update 'app/core/chatbot.py'. Implement at least two functions: one for basic text tokenization (splitting text into words/tokens) and another for simple keyword extraction (e.g., based on a predefined list or simple heuristics). These functions should be standalone and testable.

## Acceptance Criteria
- [ ] A 'tokenize_text' function exists within 'app/core/chatbot.py' that takes a string and returns a list of strings (tokens).
- [ ] A 'extract_keywords' function exists within 'app/core/chatbot.py' that takes a string (or list of tokens) and returns a list of strings (keywords).
- [ ] Both functions can process sample input without errors.

## Definition of Done
(none)

## Status
pending
