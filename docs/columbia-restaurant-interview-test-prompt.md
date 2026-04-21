# Columbia Restaurant (Ybor City) — Sommelier/Assistant Manager Test Prompt

Use this prompt to test whether the pipeline can produce a **specific, non-generic, operations-first interview prep system**.

## Core prompt

```text
I’m interviewing on Tuesday to become Assistant Manager and the first Sommelier in Columbia Restaurant history at the Ybor City Tampa location. The interview is with the COO and I expect heavy operations questions.

Build me an interview operations playbook that includes:
- How to define the first-sommelier role without disrupting service standards.
- Daily/weekly operating rhythms across FOH, beverage, and kitchen coordination.
- Wine program SOPs: inventory, storage, breakage controls, cost controls, vendor cadence, by-the-glass freshness controls, and menu engineering.
- Service execution standards: table-side recommendation flow, pairing framework, guest upsell ethics, and recovery protocol if a pairing misses.
- KPI dashboard with practical ranges: beverage COGS %, bottle mix, by-the-glass wastage, check average lift, attach rate, and training completion.
- 30/60/90-day rollout plan with quick wins and risk controls.
- Cross-functional communication plan with GM, chef, bar lead, and floor supervisors.
- A list of likely COO operations questions and strong answer structures.

Context and constraints:
- This is a legacy, high-reputation restaurant with established systems.
- I need to come across as operationally rigorous, respectful of existing culture, and measurable in execution.
- Tone should be specific, practical, and non-generic.

Output goal:
Produce a print-ready interview operations system with worksheets/checklists I can rehearse from before Tuesday.
```

## API test payload (example)

```json
{
  "title": "Columbia Ybor Interview Ops Prep",
  "lifeEvent": "Interviewing Tuesday for Assistant Manager and first Sommelier role at Columbia Restaurant Ybor City (Tampa) with COO; expect operations-heavy questions.",
  "audience": "Candidate preparing for COO operations interview",
  "tone": "specific, practical, measurable, respectful of legacy operations",
  "context": "Need role charter for first sommelier in restaurant history; must integrate with existing service model and leadership chain. Emphasis on SOPs, KPI ownership, cost controls, and 30/60/90 rollout.",
  "formattingProfile": "professional_print",
  "artifactDensity": "high"
}
```

## Evaluation checklist for this scenario

Use this checklist to verify output quality (especially anti-generic and operations depth):

- Includes a concrete first-90-days operating plan with owners and cadence.
- Defines operational SOPs for wine program, not just wine education content.
- Provides measurable KPI targets with formulas and review frequency.
- Includes a realistic COO-question bank and structured answer framework.
- Contains rehearsable worksheets (opening/closing, inventory cycle count, pre-shift brief, service recovery).
- Avoids generic business clichés and references real restaurant floor execution details.

## Expected pass signal

A strong run should read like an operator’s packet (role charter + SOP + KPIs + rehearsal drills), not a generic career-advice article.
