# Connect a front end to Purrpose

This is the current **local fixture API**, not a deployed production service. Read this before replacing the existing browser UI. Product policy remains in `first draft/guidance/FULL_GUIDANCE.md`.

## Quick start

1. From repository root run `python -m purrpose.server` (Python 3.12 tested). No API keys or cloud calls are needed. Without explicit H-MEM configuration, history is unavailable; it is not simulated as successful.
2. Open http://127.0.0.1:8766/ . Opening HTML through file:// will not connect correctly.
3. Integrate the design into `purrpose/web/index.html`, `app.css`, and `app.js`, preserving API semantics below. Keep backups/branches and preserve other developers' work.
4. Load `/api-client.js` before application JavaScript. The current page already does this. It exposes `createPurrposeClient()` and uses relative same-origin routes. It contains no provider secrets.
5. Keep the server bound to 127.0.0.1. This application has no production authentication. Do not expose it publicly or disable origin checks to connect a separately hosted design. A future separate frontend server requires a deliberately reviewed proxy/deployment setup; it is not configured here.

Example browser use:

```javascript
const api = createPurrposeClient();
const health = await api.status();
const result = await api.supporter({city: 'Ottawa'});
// Or explicit region-wide consent:
const regional = await api.supporter({city: null, region_wide: true});
// One ID per browser conversation; new chat gets a fresh ID:
const session = crypto.randomUUID();
const answer = await api.chat(session, 'I want to help a cat');
// Render untrusted strings with textContent, never innerHTML.
```

## Actual operations

All POST requests require JSON Content-Type, `X-Purrpose-Local: 1`, own origin, and <=4096 encoded body bytes. Requests execute serially. Unsupported fields are rejected. The client handles these headers. Do not send private donor or medical documents, credentials, model names, SQL or arbitrary tool instructions.

| Method and route | Client method | JSON request | Main response |
|---|---|---|---|
| GET /api/status | status() | none | mode, memory, nightshift, cloud_inference_in_this_server, model_provider (null when off: route, model, ready, config_error, connection, budget), public_web_fetching, payments, public_fixture_link, limitation |
| POST /api/supporter | supporter(preferences) | city:string/null, region_wide:boolean, allow_expansion:boolean; all optional | status=needs_preference/no_city_match/results |
| POST /api/organization | organization(publicLinks) | public_links: nonempty string array | status=gap_review/unsupported_links |
| POST /api/chat | chat(sessionId,message) | session_id:1–80 ASCII letters/digits/hyphens; message:1–1500 nonblank characters | reply, mode (bounded_intent_matching or model_intent_validated), new_cloud_calls (0 or 1), optional model_intent (route, model, prompt_version, status used/cached/failed/invalid_output, intent, error_category), optional results |
| POST /api/history | history(cutoff) | cutoff:null or ISO datetime with timezone | status=recorded_review/partial_legacy_record/history_unavailable |
| POST /api/update | demoUpdate(action,requestId) | action:clarify/more_funds/fully_funded/source_outage; request_id:1–100 characters | status, optional review, update_events, idempotent_replay |
| POST /api/debug | debug() | {} | latest_run, update_events, model_trace (sanitized: no keys, message text or reasoning), new_cloud_calls |
| POST /api/runs | runs() | {} | runs (newest first: run_id, kind real/fictional, scenario_type, case_id, case_name, status, started_at, duration_ms, session_label), scope |
| POST /api/runs/get | run(runId) | run_id:string | full run (steps with agent, role, action, at_ms, details; tools; agents) or `{status:'run_not_found'}` |

Update and debug are **demo/developer controls**, not normal donor features. `/api/update` changes a synthetic funding source; it does not accept real organization updates. Source notifications exist as a backend fixture capability, not an arbitrary public URL fetch endpoint.

### Supporter discovery

- `{}` asks for preference without selecting a city.
- `{city:'Toronto'}` currently has no match. Display `question` and ask permission before expansion. Do not silently set allow_expansion.
- `{city:'Toronto',allow_expansion:true}` explicitly permits broader supported Ontario cases.
- `{city:null,region_wide:true}` explicitly requests the region.
- `results` supplies arrays `qualified`, `pending`, `no_current_gap`. Preserve server order: case city, full organization name, case name. All current cases are fictional.
- Display `message`, `coverage` and optional `expansion_question`. Empty arrays do not mean every Ontario rescue has been searched.

### Case card contract

Each card contains `case_id`, `organization_full_name`, `case_name`, `case_city`, `scenario_type`, `qualified`, `remaining_minor`, `currency`, `funding_notice`, `review_date`, `evidence`, `unknowns`, `unpassed_requirements`, `risk_hold`, `external_donation_url`, `limitations`, and `registration_category`.

- Amounts are integer cents. `100000` means CAD 1,000.00. **null means unknown**, not zero. `0` means no current disclosed gap. Do not compute qualification or a replacement remainder in the frontend.
- Keep `funding_notice` beside amounts; it explains disclosure limitations.
- Show full organization name, case city, evidence and unknowns. A single checked case does not certify an entire organization.
- Current `qualified=true` is only a synthetic gate pass; label it “Meets synthetic checks”, not “verified charity”. Current external_donation_url is null; do not invent a Donate action or real payment destination.
- Evidence entries contain field, value, source_id, reference, publisher, source_date, location, scenario_type and optional extraction_provenance. Synthetic references are identifiers, not live clickable web sources. Do not make a synthetic:// identifier look like an official website.
- Use unpassed_requirements for readable explanations; unknowns holds structured field gaps. Never translate absence into fraud.

### Organization view

Only the displayed `https://example.invalid/purrpose/maple` fixture page and its configured funding page are supported. Unknown URLs return unsupported_links and materials_fetched=false. They are not fetched. Supplying a link does not establish authority to represent the organization.

Render `gap_checklist` entries: what_to_add, why, where_to_obtain_or_publish, next_check, field, condition. Keep privacy_note and guarantee. Organizations should publish appropriate evidence on their own public channels, not upload private materials into this app. Adding recommendations does not guarantee qualification.

### Chat and history

Chat is bounded bilingual intent matching, not a connected general model. `results`, if present, uses the supporter contract. Keep response prose and evidence together. Session state is process-local, max100 sessions; browser chat IDs are not login credentials. Preferences are not a permanent donor profile. Current case evidence is shared by this demo; conversations have separate selections. Do not use this as a multi-user production design.

A history result is what the system had recorded at its actual system_recorded_at time. source_review_date is distinct. `recorded_result` can be null for partial legacy records; do not reconstruct it using current data. A 200 history_unavailable is a normal application state. No H-MEM configuration yields unavailable; configured-memory failure yields HTTP503. Latest means latest retained review, not a new real-web check.

### Runs, the Agent map and the Review tab

`/home.html` is a chat with a right-hand panel; `/dashboard.html` lists runs. The run store (`purrpose/runs.py`) is process memory only: the last 50 runs, newest first, cleared on restart, never written to disk. A run is recorded when a new real review runs (`/api/research/read`, not on a cached read) or a fictional review runs (`remember_run`). Every `/api/chat` response carries `agent_run`: `{run_id, note, model}`. `note` is `New review run`, `Reused a recent source read; no new run`, or `Answered from saved results; no agents ran`. `model` is null without a configured model, else `{route, status, intent, new_cloud_calls, total_tokens}`; `total_tokens` is set only when `new_cloud_calls > 0` for that turn. Agents are code roles (coordinator, collector, evaluator, resolver) in one process; tokens are never shown per agent.

`/agent-map.js` (`buildMapModel`, `renderAgentMap`) and `/review-panel.js` (`buildReviewModel`, `renderReview`) are pure view models over backend fields, rendered with `textContent` only. Review statuses: `Information available` (only a qualified fictional case), `More information needed`, `Unable to assess`. Missing funding figures read `Not stated`, never 0. `purrpose/fixtures/chat-samples.json` holds trimmed real chat responses used by `test_review_panel.cjs`; a Python test checks their shape against the live backend.

## Loading and failure behavior

Disable duplicate submissions while an operation is running. Keep entered text when an error occurs. Never display the previous successful review as though the failed request completed. Historical/saved content can remain visible with its timestamp and a clear stale-result label.

The shared client defaults to a 65-second timeout, no automatic retries. A client timeout does **not** cancel backend work or prove it failed. Report an uncertain result. If manually retrying a demo update, reuse the same request ID and identical action; a new ID represents a new task. Update idempotency is in-process only and resets at restart. Other calls, including chat, have no idempotency guarantee; do not automatically resubmit them.

| HTTP/code | Meaning and UI response |
|---|---|
| 400 invalid_request | Invalid/unsupported request; correct input, do not retry unchanged. Unknown POST route currently also returns400. |
| 403 local_request_required/host_rejected | Wrong host/origin/header; check same-origin setup. Do not disable safeguards. |
| 413 body_limit | Shorten request; byte limit also applies to multibyte text. |
| 415 json_required | Send JSON. |
| 503 memory_unavailable | Memory could not complete; show incomplete operation, not fake success. |
| 500 operation_failed | Backend failed; preserve uncertainty and inspect local debug/logs. |
| client timeout_result_unknown/network_result_unknown | No confirmed result; do not automatically retry. |
| client invalid_response | Server response was not valid JSON. |

Default user views exclude internal execution traces. Debug is explicit local development inspection, not a production operator access-control implementation.

## Integration checks before handoff

1. Fresh server: Ottawa result is pending with unknown remainder because grant inclusion is unresolved.
2. Organization fixture review lists the missing funding clarification.
3. Demo control `clarify` makes the remainder CAD1,000 and passes synthetic gates. Query through the newly designed UI; do not hard-code the amount.
4. `more_funds` makes the remainder CAD500; `fully_funded` makes it zero and not a current funding recommendation.
5. `source_outage` keeps the case pending. Show uncertainty; do not reuse an old pass as current.
6. Toronto requires explicit expansion. Chat supports the screenshot phrase “I want to find cat that need help in ontario”. New chat must not inherit the prior session's active selection.
7. With actual H-MEM configured, read a saved timestamp and query that cutoff after an update: the earlier summary stays earlier. Without it, show unavailable.
8. Check mobile layout, keyboard labels, safe text rendering, visible sources/limitations and error states.

Run `node purrpose/test_api_client.cjs` for client mapping/error/timeout/no-retry checks and `python -m unittest discover -s purrpose -t . -q` for application tests. Actual H-MEM tests require PURRPOSE_HMEM_REFERENCE; skips are not passes. See MEMORY_VERIFICATION.md and README.md for configuration.

## Honest integration status

Local Python review and selected actual H-MEM memory operations work. Real Lucy observations and a separate synthetic case are both available; real qualification remains pending. NVIDIA had one real extraction test plus a recorded replay. Separately, when a chat model is configured, every ordinary chat message makes at most one bounded intent-classification call (direct NVIDIA tested); the reply, amounts and status are still written by code. Show `model_intent` honestly and never claim zero model calls when `new_cloud_calls` is 1. Zetaris historical identity was queried separately; it is not wired into current case cards. Nightshift remains unconnected (direct NVIDIA calls are not Nightshift use). General model-written conversation, arbitrary URL retrieval, approved current regional risk coverage and production deployment remain incomplete; only two fixed real articles can be retrieved. Existing API credentials do not authorize new spending.

### Saved research assessment route

POST `/api/research` takes `{}` with the same local JSON/origin headers. It returns saved_manual_research, pending_verification, qualified=false, remaining_minor=null, assessment_date, source_observed_on, latest_reported_state, sources, date_issues, gates, next_evidence and limitations. All six real gates remain not_established. This is a separate manually collected dossier, not a supporter-qualified case or live website recheck. The research page uses this route. It cannot modify the synthetic case or supply private evidence.

### Live public-reader route

POST `/api/research/read` with `{}` reads only two backend-configured Lucy articles after robots checking. Returns status=read_complete/read_incomplete, observed_at, cached, sources with read status/error and optional text/content_sha256/published_metadata. qualified remains false; remaining_minor remains null. Text is untrusted, may include related-content text and is not a verified medical statement. No automatic requalification or model call occurs. A60-second in-process attempt cache prevents repeated clicks; cached attempts retain their timestamp. Worker deadline25seconds plus bounded memory operations; use65seconds UI timeout and do not automatically retry. No arbitrary URL argument is accepted.

Live-read responses now include `analysis`: narrow sourced text candidates with quote offsets/hash, timezone-normalized metadata dates, unknown funding, pending status and limitations. Candidate extraction is not independent verification. A failed/partial retrieval cannot confirm the latest real-world state. No model is invoked. The interface displays these fields separately from saved manual findings.

Chat response can now carry `research` instead of `results` after explicit Lucy selection. Render it as saved real-source research, not as a qualified/synthetic recommendation. Follow-ups use the stored manual observations; no source refresh is implied. The dossier includes official_identity_observation and external_form_observation with manual method/date and remaining gates. Explicit fixture discovery exits this research context. New conversation IDs do not inherit it.

Explicit `refresh Lucy` (or `重新检查官网` within Lucy context) adds `live_read` to the chat response and invokes only the existing fixed two-article reader. Display per-source status/error and observed_at, and preserve cached labels. Saved manual identity/allocation are not refreshed. Follow-ups after incomplete refresh disclose that saved findings are not confirmed current. This does not enable general web search, model inference, payment or case qualification.

Real-reader responses now add `review`: pending/incomplete status, changed sources, latest_retrieved_statement, gaps and memory status/IDs. Default view omits internal trace. H-MEM unavailable remains explicit. POST `/api/research/history` with optional cutoff reads only REAL-LUCY-GHS. Chat `Lucy history` returns research_history. UI timeout is now65seconds to accommodate reader and memory deadlines; the earlier30second default is superseded. Status public_web_fetching now reports two_fixed_articles_only, not general web discovery.

`organization(publicLinks)` now supports the two exact configured Lucy article links as well as the separate fictional fixture. Real response has mode=real_public_research, gap_checklist[].responsible_party=organization/system, existing_observations and optional latest_runtime_review. materials_fetched=false; representation_authority_verified=false. New arbitrary URLs and mixed unsupported links are not fetched. Render responsibility, privacy and guarantee. Chat may return organization_review for `Lucy organization checklist`; this is not a supporter qualification result.

`supporter` additionally accepts collection=real/synthetic. API default remains synthetic for compatibility; the visible UI defaults to real. Real discovery supports only a saved curated Ontario-context lead; city match is never inferred from office address. Region-wide/expansion consent can include Lucy as pending with null treatment city. Render coverage and uncertainty; no web search or new evidence checks occurred. The UI's Discuss this real lead button enters the existing Lucy chat. Before synthetic demos explicitly choose the fictional collection.

New chat discovery defaults to real research; after choosing anywhere in Ontario, Lucy follow-ups stay real. City names alone no longer select a fictional case. For fixture chat demonstration explicitly say fictional Ottawa or 模拟 渥太华. The HTTP supporter route keeps its legacy API default; clients should always provide collection explicitly.

Feedback view is a local prototype: notes are stored only in process memory, not delivered to a reviewer, and disappear on server restart. POST /api/feedback accepts session_id, request_id, kind=preference/correction/policy_suggestion, message1–800chars and city only for preference (Ottawa/Toronto/Ontario). All requests use existing same-origin/local headers. Returns status/recorded_at/notice, unchanged-facts/qualification/policy flags, storage disclosure and idempotent_replay. Preference affects only that chat's subsequent real discovery; correction is a lead with no fetch; suggestion never changes policy. Never imply feedback certifies facts or has been escalated externally. API client offers feedback(data); current UI shares chatSession and retains the same request ID for an unchanged manual retry after an error.


## Portable startup check

Run `python -m purrpose.doctor` before setup. It checks local assets, Python, Ontario timezone support and Node, with optional --reference to inspect only configured reference presence. It has no network/secret/memory access and installs nothing. File presence is not an integration pass. README.md is now the authoritative current startup document; INCREMENT_NOTES.md preserves superseded development descriptions.
