# EVAL05: Simple in-memory key-value store class

## Feature
FEVAL

## Role
coder

## Goal
Implement a minimal in-memory key-value store with get/set/delete.

## Context Files (max 5)
(none)

## Instructions
Create `kv_store.py` with a class `KVStore` supporting: `set(key, value)`, `get(key, default=None)` (returns default if key is missing), and `delete(key)` (no error if the key doesn't exist).

## Acceptance Criteria
- [ ] kv_store.py exists and defines a class KVStore
- [ ] After store.set('a', 1), store.get('a') returns 1
- [ ] store.get('missing') returns None by default, and store.get('missing', 'x') returns 'x'
- [ ] store.delete('a') does not raise, and calling delete on a nonexistent key also does not raise

## Definition of Done
(none)

## Status
pending
