# Caregiver Control Manual — Marketing Test Run Prompt

Use this prompt when creating a Life System Builder project to market **The Caregiver Control Manual**.

## Core prompt

```text
Create a marketing-focused caregiving control system manual for adult children coordinating care for an aging parent.

Positioning:
- This is not a passive reading experience. It is a working control system.
- Emphasize practical, legal, financial, and logistical decision support.
- Stress crisis prevention and operational readiness over inspiration-only messaging.

Structural context to include:
- 8 operational domains: cognitive awareness, legal authority, financial control, benefits/funding, home & safety, care operations, family governance, end-of-life system.
- Cascade chain logic: a change in one domain triggers required review/actions in connected domains.
- Master operating rules: documents before decisions; worksheets are required outputs; complete before crisis; one owner per function; log decisions contemporaneously; perform cascade reviews; maintain recurring review cadence.
- Command center model: documentation hub, master contact list, communication protocol, review calendar, emergency packet.

Marketing facts to call out explicitly:
- 13 chapters
- 50+ worksheets

Audience and tone:
- Primary: family caregivers and adult children.
- Secondary: care managers and elder-law referral partners.
- Tone: authoritative, practical, compassionate, and execution-oriented.

Output goal:
Produce messaging architecture suitable for landing pages, sales one-pagers, webinar copy, and referral-partner outreach.
```

## API test payload (example)

```json
{
  "title": "Caregiver Control Manual Marketing Test",
  "lifeEvent": "Create a marketing-focused caregiving control system manual for adult children coordinating care for an aging parent.",
  "audience": "Family caregivers, care managers, elder-law referral partners",
  "tone": "authoritative, practical, crisis-prevention focused",
  "context": "Manual positioning from source pages: not a passive read, but a working control system. Core framework uses 8 operational domains with cascade triggers across domains. Domain set includes cognitive awareness, legal authority, financial control, benefits/funding, home safety, care operations, family governance, and end-of-life. Includes master operating rules: documents before decisions; worksheets required outputs; complete before crisis; one owner per function; log decisions contemporaneously; cascade reviews; regular review cadence. Includes command center concept with documentation hub, master contacts, communication protocol, review calendar, emergency packet. Orientation sequence highlights early legal/financial setup, funding runway, role assignment, and crisis quick-index. Product facts to emphasize: 13 chapters and 50+ worksheets.",
  "formattingProfile": "professional_print",
  "artifactDensity": "high"
}
```

## Observed test-run status in this environment

- Project creation succeeded.
- Pipeline stage `system_architecture` starts successfully with the prompt and enters `running` state in this environment.
- If your environment still uses legacy Chat Completions wiring, ensure the provider and base URL are aligned to one API format.
