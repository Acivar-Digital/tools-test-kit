# Stakeholder Test (T21)

Tests `/stakeholders` management command and the `/add` intake flow.

## Flow
1. `/stakeholders` → Shows management menu
2. `/add` or `/add <relation>` → initiates stakeholder collection
3. Sets `session.step = STAKEHOLDER_COLLECTING`
4. Initializes `session.metadata["stakeholder_collected"] = {"relation_category": relation}`
5. LLM Conductor evaluates remaining required fields (`alias`, `dob`, `location`, `gender`)

## Prerequisites
- User must have a report
- Admin or feature code

## Verification
- Response contains management options
- Session step set to `STAKEHOLDER_COLLECTING`
- **Intake Flow**: `/add` correctly seeds the `stakeholder_collected` dict with the selected `relation_category` so the LLM does not redundantly ask for the relationship at the end of the bio intake.
- **Skipped in GOLD** — complex multi-user flow
