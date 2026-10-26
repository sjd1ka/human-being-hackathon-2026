# Chat, Review Panel, Agent Map and Run Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show judges what Purrpose's agent roles actually did for each answer: a chat page with a right-hand panel (Review and Agent map tabs) and a `/dashboard` page of every run since the server started.

**Architecture:** A bounded in-process run store records each review run (real or fictional) with ordered, timed steps and tool events. Chat responses carry a reference to the run they produced, or a "no new run" note. Plain browser JavaScript builds the Agent map and Review views from backend fields only, with pure model-building functions tested in Node.

**Tech Stack:** Python 3.12 standard library (`unittest`, `http.server`), plain JavaScript (no build step, no packages), Node 24 for JS tests, existing CSP (`script-src 'self'`, no inline scripts or styles).

**Spec:** `docs/superpowers/specs/2026-10-26-chat-review-agent-map-design.md` (read it first; this plan does not repeat its reasoning).

## Global Constraints

- No new Python or npm packages. No external assets, fonts or CDNs. No inline `<script>` or `style=""` (CSP).
- Render all source, user and backend text with `textContent`; no `innerHTML` with data in new code.
- Agents are code roles: never show per-agent token counts. Tokens appear only on the NVIDIA tool, and only when `new_cloud_calls > 0` for that chat turn.
- Fixed note text on the Agent map: `Agents are code roles in one process. The AI model is used only where marked.`
- Role to agent mapping: `coordinator` → `orchestrator` ("Orchestrator"); `identity_risk`, `rescue_need`, `funding_channel` → `collector` ("Evidence Collector"); `evaluator` → `evaluator` ("Evidence Evaluator"); `dispute_resolver` → `resolver` ("Dispute Resolver").
- Card order: orchestrator, collector, evaluator, resolver.
- Run store cap: 50 runs, newest first, process memory only, cleared on restart.
- Overall review status labels, exact copy: `Information available`, `More information needed`, `Unable to assess`.
- Funding values that are null render as `Not stated`, never `0`.
- Chats last for one visit: no `localStorage` or `sessionStorage` for transcripts or runs. (The existing colour-scheme preference in `localStorage` stays.)
- Real and fictional runs carry `scenario_type`; fictional ones always show `Fictional example`.
- Never call NVIDIA in tests. Never add automatic retries. Keep the 65 s client timeout.
- Commits: no Co-Authored-By or "Generated with" lines (team rule). Work on branch `feature/agent-map`.
- In a cloud session H-MEM tests skip (no reference checkout); report skipped tests as skipped, not passed.

## Review Focus

1. **A cached Lucy read** (`/api/research/read` within 60 s returns `cached: true`): must not add a second run; the chat's `agent_run` says the recent read was reused. Test in Task 3.
2. **H-MEM not configured or failing**: the run still records, tool row shows `not configured` / `recall failed` / `save failed`, and the map renders. Test in Task 2 and Task 4.
3. **More than 50 runs**: oldest dropped; asking for a dropped ID returns `{'status': 'run_not_found'}`, not an error page. Test in Task 1.
4. **Model call failed or invalid** (`model_intent.status` is `failed` or `invalid_output`): the NVIDIA tool shows the failure and "answered with fixed phrases", never tokens it doesn't have. Test in Task 4.
5. **Hostile text** (a source or chat message containing `<script>`): appears as literal text in map, log and review. Test in Task 4 (model keeps raw string) plus the `innerHTML` grep in Task 7.

---

### Task 1: Run store and agent-map model (backend)

**Files:**
- Create: `purrpose/runs.py`
- Test: `purrpose/test_runs.py`

**Interfaces:**
- Produces:
  - `AGENT_OF: dict[str, str]` (role → agent key, per Global Constraints).
  - `AGENT_LABEL: dict[str, str]` (`orchestrator` → `Orchestrator`, etc.).
  - `class RunStore(cap: int = 50)`:
    - `add(review: dict, *, kind: str, started_at: float, ended_at: float, tools: list[dict]) -> str` stores a normalized run and returns `run_id` (reuse `review['run_id']` when present). `kind` is `'real'` or `'fictional'`.
    - `tag_session(run_id: str, session_id: str) -> None`.
    - `summaries() -> list[dict]` newest first; each `{run_id, kind, case_id, case_name, status, started_at, duration_ms, session_label}` (`session_label` = first 8 chars of session ID or `None`).
    - `get(run_id: str) -> dict` returns the full run, or `{'status': 'run_not_found', 'run_id': run_id}`.
  - Normalized run shape: `{run_id, kind, scenario_type, case_id, case_name, status, started_at, ended_at, duration_ms, session_id, steps: [{seq, role, agent, action, at_ms, details}], tools: [...], agents: [{agent, label, ran: bool, step_count, duration_ms, decision, skipped_reason}]}`.
  - `agents` is computed: an agent `ran` if any step maps to it; `skipped_reason` comes from a `coordinator`/`skip_role` step's `skipped_role` or `reason` when present, else `'not needed in this run'`; `decision` is the last step's `action` for that agent, with underscores replaced by spaces.

- [ ] **Step 1: Write failing tests** in `purrpose/test_runs.py`:
  - `test_add_normalizes_roles_to_agents`: a review with trace roles `coordinator, identity_risk, evaluator, dispute_resolver` gives `steps[i]['agent']` of `orchestrator, collector, evaluator, resolver`.
  - `test_skipped_agent_reported_with_reason`: a trace with no `dispute_resolver` step gives the resolver entry `ran is False` and `skipped_reason == 'not needed in this run'`; a `skip_role` step with `skipped_role='rescue_need', reason='Required facts already validated'` makes the collector's `skipped_reason` that reason only if no collector step ran.
  - `test_cap_drops_oldest_and_missing_id_is_status`: add 51 runs with cap 50; `summaries()` has 50 items, newest first; `get(first_id) == {'status': 'run_not_found', 'run_id': first_id}`.
  - `test_no_tokens_on_agents`: no key containing `token` appears anywhere in `agents`.
  - `test_kind_kept_separate`: a fictional and a real run keep their own `kind` and `scenario_type` in summaries.
- [ ] **Step 2:** Run `python -m unittest purrpose.test_runs -v`. Expected: FAIL (module not found).
- [ ] **Step 3:** Implement `purrpose/runs.py` per the Interfaces block (use `collections.OrderedDict` or a list; `deepcopy` stored and returned data so callers can't mutate the store).
- [ ] **Step 4:** Run `python -m unittest purrpose.test_runs -v`. Expected: PASS.
- [ ] **Step 5:** Commit: `git add purrpose/runs.py purrpose/test_runs.py && git commit -m "Add bounded run store and agent-map model"`.

### Task 2: Step timings and tool events in the real review

**Files:**
- Modify: `purrpose/real_review.py` (`review_real_observations`, the `event` helper and the memory recall/save blocks)
- Test: `purrpose/test_real_review.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: each trace entry gains `at_ms: int` (milliseconds since the review started, `time.monotonic()` based). The result gains `tools: list[dict]` with entries `{'tool': 'hmem', 'operation': 'recall'|'save', 'status': 'ok'|'failed'|'not_configured', 'duration_ms': int, 'memory_id': str|None}` and `duration_ms: int` for the whole review. With no memory, `tools` has one entry `{'tool': 'hmem', 'operation': 'recall', 'status': 'not_configured', 'duration_ms': 0, 'memory_id': None}`.

- [ ] **Step 1: Write failing tests** in `purrpose/test_real_review.py` using the existing `observed()` helper:
  - `test_steps_are_timed_in_order`: every trace entry has an int `at_ms`, and `at_ms` values never decrease.
  - `test_tools_without_memory_report_not_configured`: `review_real_observations(observed())['tools'] == [{'tool': 'hmem', 'operation': 'recall', 'status': 'not_configured', 'duration_ms': 0, 'memory_id': None}]`.
  - `test_memory_failure_is_a_failed_tool_event`: with a stub memory whose `call` raises `MemoryUnavailable`, `tools[0]['status'] == 'failed'` and `result['status'] == 'review_incomplete'` (existing behaviour kept).
- [ ] **Step 2:** Run `python -m unittest purrpose.test_real_review -v`. Expected: the three new tests FAIL; existing tests pass.
- [ ] **Step 3:** Implement: record `start = time.monotonic()` at the top; `event()` adds `at_ms`; time each `memory.call` and append a tool entry; set `result['duration_ms']` before returning.
- [ ] **Step 4:** Run `python -m unittest purrpose.test_real_review -v`. Expected: PASS (H-MEM-only tests may skip).
- [ ] **Step 5:** Commit: `git commit -am "Time real review steps and record H-MEM tool events"`.

### Task 3: Server wiring, chat run references and client methods

**Files:**
- Modify: `purrpose/server.py` (`LocalApp.__init__`, `remember_run`, `dispatch` for `/api/research/read`, new routes)
- Modify: `purrpose/conversation.py` (`reply` and the refresh branch of `match`)
- Modify: `purrpose/web/api-client.js`
- Test: `purrpose/test_server.py`, `purrpose/test_research_chat.py`, `purrpose/test_api_client.cjs`

**Interfaces:**
- Consumes: `RunStore` from Task 1; `tools`, `duration_ms`, `at_ms` from Task 2.
- Produces:
  - `LocalApp.runs: RunStore`.
  - Real runs recorded in the `/api/research/read` branch only when a new review ran (not when the cached branch returns). The read response gains `run_id`.
  - Fictional runs recorded in `remember_run` (kind `'fictional'`; `started_at`/`ended_at` taken around `journeys.review` by the caller, or from the core trace's first and last `recorded_at`).
  - New POST routes (allowed fields): `/api/runs` → `set()`, returns `{'runs': app.runs.summaries(), 'scope': 'Runs since this server started; cleared on restart.'}`; `/api/runs/get` → `{'run_id'}`, returns `app.runs.get(run_id)`.
  - Every `/api/chat` response gains `agent_run`: `{'run_id': str|None, 'note': str, 'model': None|{'route', 'status', 'intent', 'new_cloud_calls', 'total_tokens'}}`. `note` is `'New review run'` when a run was produced this turn; `'Reused a recent source read; no new run'` for a cached read; otherwise `'Answered from saved results; no agents ran'`. `total_tokens` comes from the provider's last trace entry `usage.total_tokens` only when `new_cloud_calls > 0`, else `None`. When a run is produced, the conversation calls `app.runs.tag_session(run_id, session_id)`.
  - `api-client.js` gains `runs: () => request('/api/runs', {})` and `run: (runId) => request('/api/runs/get', {run_id: runId})`.

- [ ] **Step 1: Write failing tests:**
  - `test_server.py::test_runs_endpoints_list_and_get`: POST `/api/research/read` is network-bound, so instead call `self.app.runs.add(...)` with a minimal review, then POST `/api/runs` lists it and `/api/runs/get` returns it; an unknown ID returns `status == 'run_not_found'`.
  - `test_server.py::test_runs_endpoints_keep_request_guards`: missing `X-Purrpose-Local` on `/api/runs` gives 403 `local_request_required`; an extra field gives 400.
  - `test_research_chat.py::test_refresh_reports_run_and_cached_read_does_not`: with the reader stubbed via `patch('purrpose.server.bounded_read', return_value={'status': 'read_complete', 'sources': []})` (pattern from `test_explicit_refresh_only_and_bounded_cache`), "refresh Lucy" returns `agent_run.run_id` not None and `note == 'New review run'`; an immediate second refresh returns `run_id is None`, `note == 'Reused a recent source read; no new run'`, and `len(app.runs.summaries()) == 1`.
  - `test_research_chat.py::test_plain_follow_up_has_no_run`: "Lucy what evidence is missing?" after selecting Lucy returns `agent_run.note == 'Answered from saved results; no agents ran'`.
  - `test_api_client.cjs`: `runs()` posts `{}` to `/api/runs` with the local header; `run('x')` posts `{run_id: 'x'}` to `/api/runs/get`.
- [ ] **Step 2:** Run `python -m unittest purrpose.test_server purrpose.test_research_chat -v` and `node purrpose/test_api_client.cjs`. Expected: new tests FAIL.
- [ ] **Step 3:** Implement per the Interfaces block. Add `agent_run` in one place in `Conversation.reply` so every return path carries it.
- [ ] **Step 4:** Run the same commands, then the full suite `python -m unittest discover -s purrpose -t . -p "test_*.py"`. Expected: all PASS (H-MEM tests may skip).
- [ ] **Step 5:** Commit: `git commit -am "Record runs, add run endpoints and chat run references"`.

### Task 4: Agent map view model and panel tab

**Files:**
- Create: `purrpose/web/agent-map.js` (pure `buildMapModel` + DOM `renderAgentMap`)
- Create: `purrpose/test_agent_map.cjs`
- Modify: `purrpose/web/design-home.html` (two-column layout: chat left, panel right with tab buttons `Review` and `Agent map`), `purrpose/web/design-home.css`, `purrpose/web/design-home.js` (chat answers render on the left; "See how this was worked out" link selects the run)
- Modify: `purrpose/server.py` (serve `/agent-map.js`), `purrpose/doctor.py` asset list if it enumerates web files

**Interfaces:**
- Consumes: run shape from Task 1; `agent_run` from Task 3; `api.run(id)`.
- Produces (exported like `api-client.js`, via `module.exports` in Node and `globalThis` in the browser):
  - `buildMapModel(run, agentRun) -> {header: string, note: string, fictional: bool, cards: [{agent, label, state: 'done'|'warn'|'skipped', line: string, duration: string}], tools: [{tool, text}], log: {[agent]: [{text, result}]}}`.
    - `header`: `Run · {K} agents ran · {seconds} s`.
    - `state` is `warn` for the evaluator when a step action contains `conflict` or `chronology`; `skipped` when `ran` is false; else `done`.
    - `tools` order: NVIDIA, H-MEM, Zetaris, Nightshift. NVIDIA text: `NVIDIA Nemotron · {n} call · {t} tokens` when `agentRun.model.new_cloud_calls > 0` and `total_tokens` is a number; `NVIDIA Nemotron · call failed, answered with fixed phrases` when status is `failed`/`invalid_output`; `NVIDIA Nemotron · not used` otherwise. H-MEM text from `run.tools`. Zetaris: `Zetaris · not connected yet`. Nightshift: `Nightshift · not connected`.
  - `buildMapModel(null, agentRun)` (no run) returns `cards: []` and `header` equal to `agentRun.note`.
  - `renderAgentMap(container: HTMLElement, model) -> void` (textContent only; clicking a card shows that agent's log below the cards).

- [ ] **Step 1: Write failing Node tests** in `purrpose/test_agent_map.cjs` (plain `assert`, run with `node`):
  - cards come out in order orchestrator, collector, evaluator, resolver, with the resolver `skipped` when it did not run;
  - no card or tool text for an agent contains `token`; only the NVIDIA tool may;
  - failed model status gives the failed-call text and no tokens;
  - H-MEM `not_configured` gives `H-MEM · not configured`;
  - a step detail containing `<script>x</script>` appears unchanged in `log` strings;
  - a fictional run sets `fictional: true`;
  - `buildMapModel(null, {note: 'Answered from saved results; no agents ran'})` gives no cards and that header;
  - `note` equals the fixed note text in Global Constraints.
- [ ] **Step 2:** Run `node purrpose/test_agent_map.cjs`. Expected: FAIL (module missing).
- [ ] **Step 3:** Implement `agent-map.js`; then the page: panel with two tab buttons (`role="tablist"`, arrow-key switching), Agent map tab calls `api.run(agent_run.run_id)` when a run exists and renders; otherwise renders the no-run model. The chat sidebar lists this visit's chats (client memory only; "New chat" makes a new `crypto.randomUUID()` session). Each answer keeps the existing follow-up buttons (`action()` in `design-home.js`) and gains a collapsed "Sources & limits" `<details>` showing the answer's source links and `limits`/notices from the response. Use the reader stub `patch('purrpose.server.bounded_read', ...)` as `test_research_chat.py` already does.
- [ ] **Step 4:** Run `node purrpose/test_agent_map.cjs` and `python -m unittest purrpose.test_server -v`. Expected: PASS.
- [ ] **Step 5:** Commit: `git add -A purrpose/web purrpose/test_agent_map.cjs purrpose/server.py purrpose/doctor.py && git commit -m "Add Agent map panel to the chat page"`.

### Task 5: Review tab

**Files:**
- Create: `purrpose/web/review-panel.js` (pure `buildReviewModel` + DOM `renderReview`)
- Create: `purrpose/test_review_panel.cjs`
- Modify: `purrpose/web/design-home.js`, `design-home.css`, `purrpose/server.py` (serve `/review-panel.js`)

**Interfaces:**
- Consumes: existing chat response fields `research`, `results` (supporter contract), `live_read`, `organization_review` (see `FRONTEND_INTEGRATION.md`).
- Produces: `buildReviewModel(chatResult) -> null | {kind: 'case'|'organization', title, status, explanation, fictional: bool, sections: [{name, status, items: [{text, source_url?, detail?}]}]}`.
  - `status` rules: `Information available` only when a synthetic result has `qualified === true`; `Unable to assess` when `live_read.status` is not `read_complete` and no saved research exists; otherwise `More information needed`.
  - Case sections, in order: `Organization identity`, `Claims and evidence`, `Funding`, `Questions to ask the rescue`. Funding items: target, raised, remaining, each labelled `Reported by the rescue` or `Confirmed`, and `Not stated` when null.
  - Organization requests (`organization_review` present): `kind: 'organization'`, one section per `gap_checklist` entry, keeping `privacy_note` and `guarantee`.
  - Returns `null` when the answer has no case or organization content (the tab then shows "Ask about a case to see its review").

- [ ] **Step 1: Write failing Node tests** in `purrpose/test_review_panel.cjs` using a trimmed real Lucy chat response (capture one from a local run, remove long text) and a fictional qualified one:
  - Lucy gives `More information needed`, four sections in the stated order, remaining amount `Not stated`;
  - fictional qualified gives `Information available` and `fictional: true`;
  - an incomplete live read with no saved research gives `Unable to assess`;
  - an organization response gives `kind: 'organization'` with the privacy note kept;
  - no section status is worded as a negative finding (none contains `fraud`, `fake`, `scam`, `failed check`).
- [ ] **Step 2:** Run `node purrpose/test_review_panel.cjs`. Expected: FAIL.
- [ ] **Step 3:** Implement and render into the Review tab; source links reuse the existing HTTPS host allowlist in `design-home.js` (move `link()` into a shared helper if both files need it).
- [ ] **Step 4:** Run `node purrpose/test_review_panel.cjs`. Expected: PASS.
- [ ] **Step 5:** Commit: `git commit -am "Add Review tab built from backend review fields"`.

### Task 6: `/dashboard` page

**Files:**
- Create: `purrpose/web/dashboard.html`, `purrpose/web/dashboard.js`, `purrpose/web/dashboard.css`
- Modify: `purrpose/server.py` (routes `/dashboard.html`, `/dashboard.js`, `/dashboard.css`), `purrpose/web/design-home.html` (header link "Dashboard")
- Test: `purrpose/test_server.py`

**Interfaces:**
- Consumes: `api.runs()`, `api.run(id)`, `buildMapModel`, `renderAgentMap`.
- Produces: a page listing runs (time, short session label, case, `Real` or `Fictional example`, result, duration); selecting one renders its Agent map and step log; page text states `Runs since this server started; cleared on restart.`; a Refresh button reloads the list (no polling).

- [ ] **Step 1: Write failing test** `test_server.py::test_dashboard_page_served_with_local_assets`: GET `/dashboard.html` returns 200 HTML that references `/api-client.js`, `/agent-map.js`, `/dashboard.js` and contains no `<script>` body and no `http` asset URLs.
- [ ] **Step 2:** Run `python -m unittest purrpose.test_server -v`. Expected: FAIL (404).
- [ ] **Step 3:** Implement the page and routes.
- [ ] **Step 4:** Run `python -m unittest purrpose.test_server -v`. Expected: PASS.
- [ ] **Step 5:** Commit: `git commit -am "Add run dashboard page"`.

### Task 7: Polish, phone layout, verification and docs

**Files:**
- Modify: `purrpose/web/design-home.css`, `dashboard.css` (polish), `purrpose/FRONTEND_INTEGRATION.md`, `HANDOFF.md`, `README.md` (root "How Purrpose works" links), `purrpose/README.md`

- [ ] **Step 1:** Run the `impeccable` skill on the chat page and dashboard (palette and type from `design/README.md`: gradient `#4B7BFF` → `#A993FF` → `#FF3D9A`, text `#1B1B1F`, background `#FBFAF7`, warm alternative kept; light theme). Apply its fixes.
- [ ] **Step 2:** Phone layout: at 390 px the panel becomes a sheet over the chat with the same two tabs; no horizontal scroll (`document.documentElement.scrollWidth <= 390`).
- [ ] **Step 3:** Safety grep: `grep -n "innerHTML" purrpose/web/agent-map.js purrpose/web/review-panel.js purrpose/web/dashboard.js` returns nothing; `grep -n "localStorage\|sessionStorage" purrpose/web/*.js` shows only the existing colour-scheme lines.
- [ ] **Step 4:** Full checks: `python -m unittest discover -s purrpose -t . -p "test_*.py"`, `node purrpose/test_api_client.cjs`, `node purrpose/test_agent_map.cjs`, `node purrpose/test_review_panel.cjs`. Expected: all pass; record the skipped count honestly.
- [ ] **Step 5:** Browser check without a model key (`python -m purrpose.server`): ask "I want to help a cat" → Lucy → "refresh Lucy" (live read of the two configured articles) → Agent map shows Orchestrator, Evidence Collector, Evidence Evaluator, Dispute Resolver with times; a second refresh says the recent read was reused; `/dashboard.html` lists the run. Ask for the fictional demo and confirm its run is labelled `Fictional example`. No page errors.
- [ ] **Step 6:** Update docs with what actually runs and what was actually checked (including skipped tests). Commit: `git commit -am "Polish chat panel and dashboard; update docs"`.
- [ ] **Step 7:** Push the branch and open a pull request against `main` with a plain summary and the check results; no attribution lines.
