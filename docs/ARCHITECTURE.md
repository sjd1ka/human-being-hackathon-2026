# Architecture and tool responsibilities

## One evidence system, different questions

Donors and rescue organizations share the same source observations and evaluation boundaries. The chat changes how it organizes the response: a donor sees claims, source material and unresolved questions; an organization sees information it could publish or clarify. A stated organization role is not verified representation authority. Neither view changes the evidence standard or handles payments.

## Runtime layers

| Layer | Implementation | Current scope |
|---|---|---|
| Chat and request interpretation | `conversation.py`, `model_intent.py`, `everyday_intent.py`, `directory_chat.py`, `live_chat.py` | Optional Nemotron intent JSON; validated bounded operations and code fallback. Replies are code/templates. |
| Coordinator | `server.py`, `workflow_runs.py`, `runs.py` | Selects explicit operations, retains per-session context, records actual events. Serial local execution. |
| Directory and identity collection | `directory.py`, `zetaris.py`, `registry.py` | Real fixed JDBC SELECTs against the configured Zetaris; CRA historical identities only. |
| Website collection | `safe_web.py`, `url_discovery.py`, `site_discovery.py` | HTTPS public-DNS validation/IP pinning, robots checks, bounded same-host text pages, no redirect or retry. |
| Basic evidence/gap analysis | `organization_live.py` | Related text with quotes and offsets, not-found-in-read-pages labels and publication suggestions. Keywords do not establish identity, clinical truth or funding. |
| Curated case evaluation | `real_review.py`, `source_analysis.py` | Lucy's explicitly configured sources, conditional chronology resolution, open verification gates retained. This is separate from arbitrary URL checks. |
| Synthetic repair example | `core.py`, `fixtures/maple.json` | Code-role evaluator requests a bounded funding repair and re-evaluates. Fixture only; not autonomous live research. |
| Shared persistent observations | `memory.py`, `hmem-bridge.mjs` + official reference | Real H-MEM save/recall under scoped case IDs. Local storage is not a trust certificate. |
| Explanation and visibility | `web/design-home.js`, `web/review-panel.js`, `web/agent-map.js` | Findings, limits and actual executed operations. Unused tools stay unused. |

The UI groups specialized roles as Orchestrator, Evidence Collector, Evidence Evaluator and Dispute Resolver. Internal traces may separately name identity/risk, rescue need and funding/channel roles. These are code roles in one process, not separate autonomous models.

## Conditional behavior

- A missing city asks a question rather than starting a worldwide search.
- A permitted website is read; a blocked, redirected or unsupported site stops with a reason. Failed access is not wrongdoing.
- A follow-up can reuse the selected organization's existing read. An explicit refresh makes a new request.
- History chooses the directory scope or selected website scope. No unrelated Lucy facts should enter a new website answer.
- The curated Lucy evaluator can ask the resolver to examine dated pregnancy/birth statements. Only supported dated progression revises that account; it does not verify clinical need.
- A model failure or exhausted budget falls back to labelled code interpretation. The app never silently replaces providers or invents a successful tool call.

The arbitrary-website path currently lacks deep independent credibility evaluation and general automatic dispute resolution. A diagram containing those roles is not a claim that every role runs in every request.

## Sponsor technology

**NVIDIA:** hosted Nemotron interprets a natural-language request as an intent, city and region flag. Application code validates the JSON, then chooses a supported action. The model does not return authoritative evidence, SQL, URLs, amounts or qualification decisions. The direct route has been live-verified; it is optional and requires each operator's configuration and budget.

**Zetaris:** AWS-hosted Lightning connects the public CRA 2024 resource as REST tables, then returns structured rows to fixed read-only JDBC queries. A separate government contact-address API supplies historic website lineage. Website investigation itself uses the application's bounded reader, not Zetaris as a general internet search engine.

**AWS:** infrastructure hosting the demonstrated Zetaris instance. Not an additional application inference service, data scraper or requirement for AWS IAM keys on the laptop.

**Meterless H-MEM:** actual official reference-engine save/recall. A directory investigation has an aggregate memory scope; selecting its already-read website does not invent an additional website save. Explicit website reads have separate website scopes. Empty history is shown honestly.

**Nightshift:** primary model provider. Purrpose calls the local Nightshift Runtime (`127.0.0.1:8088/v1`, Bearer runtime token, `meterless-app: purrpose`, `meterless-scope: user`). Nightshift routes the request to a pinned NVIDIA Nemotron cloud lane that holds the NVIDIA key. For a pinned Nemotron lane the adapter disables model thinking, which avoids Nightshift's `empty_response` errors. Live-verified on 27 October 2026 (see [NIGHTSHIFT.md](NIGHTSHIFT.md)). Direct NVIDIA never counts as Nightshift.

**Codex / Cursor / Claude and design tools:** development, testing, research assistance and interface authoring. They are not evidence validators running inside the deployed application.

## State, limits and future scope

No source permissions are inferred from a user saying a site is good. Public technical access does not establish ownership or clinical authenticity. Related-story cards are excluded at recognizable headings, but arbitrary page structure can still require review.

The model cache and budget, sessions and last 50 Runs are process-local. H-MEM persists in the configured workspace. Restarting loses temporary context and must not silently replenish an approved spending allowance. The server binds only to 127.0.0.1 and is not a production multi-user service.

Full-version work includes document authentication, broader permitted media support, deeper cross-source evidence evaluation, automatic discovery of particular appeals and usability testing.
