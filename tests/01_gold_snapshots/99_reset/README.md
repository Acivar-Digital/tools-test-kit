# 06_reset — `/reset` Command

## Scenario

User sends `/reset`. Bot resets session to START, clearing all profile data and metadata. User record in DB is NOT deleted.

## Key Facts

- Deletes session from DB
- Clears all profile data (pillars, strength, elements, etc.)
- Clears metadata (intake_mode, tailoring, etc.)
- User record persists (id, role, tier, is_admin)
- Next message starts fresh from START state

## Verification Points

| # | Check | Expected |
|---|-------|----------|
| 1 | HTTP response | 200 |
| 2 | Bot message contains | "reset" |
| 3 | Session deleted | No session in DB for user |
| 4 | User record persists | User 999 still in Users table |
| 5 | No Traceback | ✅ |
