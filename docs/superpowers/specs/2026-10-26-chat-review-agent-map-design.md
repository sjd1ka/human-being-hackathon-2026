# Design: chat, review panel, Agent map and run dashboard

Date: 26 October 2026. Decided with Josh in a brainstorming session. Submission deadline: 27 October 2026, 23:45 UTC.

## Why

Hackathon judges review a 1–4 minute demo video, a slide deck and the repository. They need to see the agents work, not be told about it. The team also needs a way to see which step failed when something breaks. The current page (`purrpose/web/design-home.*`) shows answers only; the agent steps sit in `/api/debug` as raw JSON.

Josh's words: the dashboard is "the backend view of what the agents did", for "a judge watching the agents work", and it "will also help us understand the workflow better and diagnose if something goes wrong".

## Sources and priority

When sources disagree, the higher one wins (Josh's ranking):

1. Repository guidance: `first draft/guidance/` (FULL_GUIDANCE, AGENTS, OPEN_DECISIONS), `AGENTS.md`, `NEXT_DEVELOPER.md`, `purrpose/FRONTEND_INTEGRATION.md`, `design/README.md`.
2. Teammate front-end research: "Purrpose — Front-End Research and Fundraiser Review Screen" (PDF, not in the repo).
3. Teammate chat-first HTML demo: "Purrpose | Chat-first UX demo" (not in the repo).

Use the `impeccable` skill for design and polish passes while building.

## Goals

1. One page: chat on the left, a right-hand panel with two tabs, **Review** and **Agent map**.
2. An Agent map showing which agent roles ran for an answer, what each decided, how long it took and which tools it used, with a step log per agent.
3. A `/dashboard` page listing every run since the server started, each opening its own Agent map and step log.
4. A Review tab following the front-end research's sections, populated only from real backend fields.

## Non-goals

- Turning the code roles into separate AI-model agents (discussed and rejected; can go on the deck as future work).
- Saving chats across visits. Chats last for one visit; the sidebar lists only this visit's chats (Josh, 26 Oct).
- Any personal profile on the server.
- Pasting arbitrary fundraiser URLs or entering details by hand (the research suggests it; the repo forbids arbitrary fetching and private evidence intake, so the repo wins). Unknown links stay "not assessed".
- Zetaris integration (separate plan: `purrpose/ZETARIS_LOCAL_PLAN.md`) and Nightshift (its web edition has no app endpoint; see that plan's research notes).

## Anti-goals (would be a failure even if it works)

- Showing per-agent token counts or implying each agent is a model. The four agents are code roles in one process; tokens appear only on the NVIDIA tool where a call really happened.
- A replayed or scripted map. Every card and step comes from what the backend recorded for that run.
- Missing information shown as a red flag or a negative finding.
- Any fictional data shown without its fictional label, or real and fictional runs mixed in one map.
- A synthetic pass presented as Lucy qualifying.

## The page

### Left: chat

- Existing `/api/chat` and `api-client.js`; existing intent handling, including the optional NVIDIA intent model.
- Sidebar: "This visit" list of chats (client memory only; a new chat gets a new session ID). No `localStorage` for transcripts.
- Each assistant answer that produced a run gets a link, "See how this was worked out", which selects that run in the panel.
- Kept from the teammate demo: follow-up suggestion buttons, a "Sources & limits" expander per answer.
- Dropped from it: canned answers, emoji logo, violet palette, browser `alert`/`confirm` dialogs.

### Right: panel with two tabs

**Review tab** (front-end research §3–§4):

- Summary: case and organization name, one overall status, one-line explanation.
- Overall status labels, mapped from backend fields:
  - "Information available": all six gates pass (only possible for the labelled fictional case).
  - "More information needed": a review exists with some sourced evidence and unresolved gates (Lucy today).
  - "Unable to assess": the source read failed or no usable evidence exists.
- Sections, each with its own status: organization identity; claims and evidence (claim, source link, what it supports, what remains unverified); funding (target, raised, remaining, each marked "reported by the rescue" or "confirmed", and "not stated" when null, never zero); missing information with respectful questions to ask the rescue (from the existing gap list).
- For organization requests, the tab shows the existing gap checklist (`gap_checklist`) instead.
- Fictional case: a persistent "Fictional example" label on the tab.

**Agent map tab** (Anthropic-style cards):

- Header: "Run N of this chat · K agents ran · total time".
- Cards in flow order: Orchestrator → Evidence Collector → Evidence Evaluator ⇄ Dispute Resolver, then "Six checks → result". Each card: status dot, name, one-line decision, duration.
- Agents that did not run are greyed out with the reason (for example "skipped: no conflict found").
- Tool row: NVIDIA Nemotron (calls and tokens, only if a call happened in this run), H-MEM (recall/save and memory ID), Zetaris (shown as "not connected yet" until that plan is built), Nightshift ("not connected").
- Clicking a card opens its step log underneath: one line per recorded step, in order, with the step's result.
- Fixed note: "Agents are code roles in one process. The AI model is used only where marked."
- When an answer came from saved research without a new review (most Lucy follow-ups), the map says so plainly ("Answered from the saved review of <time>; no agents ran") rather than showing an empty or stale map.

Role names map from the backend: `coordinator` → Orchestrator; `identity_risk`, `rescue_need`, `funding_channel` → Evidence Collector (show the sub-role on each step); `evaluator` → Evidence Evaluator; `dispute_resolver` → Dispute Resolver (README agent table).

### `/dashboard`

- List of runs since server start, newest first: time, chat (short session label), case, real or fictional, result, duration.
- Selecting a run shows the same Agent map and step log.
- Process memory only, capped (suggest the last 50 runs); cleared on restart. Says so on the page.
- Loopback only, same request guards as other pages; not an authorization boundary.

### Phone width

At 390 px the panel becomes a sheet that slides over the chat, with the same two tabs. No horizontal scroll.

## Backend changes needed

Current state (checked 26 Oct): `real_review.py` records `{role, action, ...details}` steps without timings; `core.py` (synthetic) records steps with `recorded_at`; `/api/debug` returns only the latest real and synthetic run plus `model_trace`; chat responses carry no run ID.

1. A bounded in-process run store: each review run gets an ID, start/end time, case, scenario type, session ID, ordered steps and tool events.
2. Step timing: record start/end (or duration) per step in `real_review.py`, matching what `core.py` already records.
3. Tool events: H-MEM recall/save with duration and memory ID; the article reader with per-source status; NVIDIA intent calls linked to the run or chat turn from `model_trace` (calls, tokens, validated intent; never prompts or keys).
4. Chat responses include the run ID when a run happened, or a "no new run" marker naming the saved review used.
5. Read endpoints: list runs, get one run. Same POST/header rules as existing endpoints.
6. Tests first (repo uses `unittest`): run store cap and ordering; steps keep backend order; real and fictional runs never mix; no prompt text, keys or raw exceptions in run output; chat turn without a review returns the "no new run" marker; skipped roles are reported with a reason.

## Look

- Josh's logo and the Lovable-style cool palette, with the warm alternative, from `design/README.md`. Light theme. Inter or system fallback, as in `design-home`.
- No external assets, no inline scripts (existing CSP). Text from sources and users rendered with `textContent`.

## Order of work (builder's call unless Josh changes it)

1. Run store, timings, tool events, run endpoints (with tests).
2. Agent map tab and step log.
3. Review tab.
4. `/dashboard` page.
5. `impeccable` polish pass, phone layout check, browser verification.

If time runs short, stop after 2; the map is the piece the demo video needs most.

## Left to the builder

File structure (extend `design-home.*` or add a new page), component code, exact copy, card visuals, and how the run store is wired, provided the rules above hold. Update `FRONTEND_INTEGRATION.md`, `HANDOFF.md` and `README.md` with what actually runs.
