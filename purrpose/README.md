# Purrpose local application

A working local demo for evidence-based animal-rescue discovery and public-information gap review. It contains **one real pending lead** (Lucy and her kittens) and a **separate fictional workflow**. Nightshift is not connected. An optional chat model (direct NVIDIA or Meterless Runtime, explicitly configured) can classify chat intent; code still writes every answer. No payment functions.

## Start on your computer

Use Python3.12 or newer (tested3.12.14). Run from repository root:

```text
python -m purrpose.doctor
python -m purrpose.server
```

Open http://127.0.0.1:8766/ . This address refers to the computer running the server; it is not a public/shareable hosted URL. No API keys, paid model requests or GPU are needed to open the page. The doctor checks local files/runtime only; it does not prove provider connectivity. On systems without Ontario timezone data, configure it before real-source date analysis; do not silently use a fixed UTC offset.

Without H-MEM configuration, memory/history is explicitly unavailable. To enable the official reference (requires Node24; tested24.18.0):

```text
python -m purrpose.doctor --reference /absolute/path/to/Meterless/engines/hmem/reference/src/index.ts
python -m purrpose.server --reference /absolute/path/to/Meterless/engines/hmem/reference/src/index.ts --state purrpose/.state/hmem --workspace your-demo
```

Use your own configured absolute reference path. No developer-specific paths or credentials are assumed. The tested external reference revision is1742dec56a66e58eef9dda2d2b865823758ca8cd. Source: https://github.com/Meterless/Meterless/tree/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/hmem/reference . It is not vendored or installed automatically. See MEMORY_VERIFICATION.md. Restart resets fixture source contents, chat, feedback and recent-read cache; H-MEM history persists in its configured workspace. Use a new workspace for an isolated demonstration, never delete old state just to reset a demo.

## Optional chat model

Copy `.env.example` to `.env.local` (git-ignored), add your own NVIDIA key and keep or change the caps, then start with:

```text
python -m purrpose.server --env-file .env.local
```

Environment variables work too. With `PURRPOSE_MODEL_PROVIDER` set, every ordinary chat message is classified by the configured model; a validator checks the intent and the existing code writes the reply. Safety refusals, negations, two-city requests and explicit `refresh Lucy` stay code-only. Missing caps block model calls; failures and invalid output fall back to bounded matching, labelled in the response. There are no retries and no automatic switch between providers. `nvidia_direct` is not Nightshift use; the `meterless` route follows the provider contract but has not been tested against a running runtime. See MODEL_PROVIDER_VERIFICATION.md.

## Try the real donor journey

1. In Talk to Purrpose say `I want to help a cat`, then `anywhere in Ontario`.
2. The curated Lucy lead is pending, never a qualified recommendation. Ask `How much is still needed?` or `Where does the money go?`.
3. Say `refresh Lucy` to explicitly read the two configured public articles. No general web search, arbitrary links, video or donation-form automation. Robots limits, size/time caps, cached-attempt labels and failure states apply.
4. With real H-MEM configured, that read enters conditional code-role review and stores sourced pending observations; ask `Lucy history` to read the retained review. It is not a fresh check.
5. Sources, dates, unknowns and limitations remain visible. The manual CRA/form observations are not refreshed by the article reader. No case budget/raised total is established; amount remains unknown.

Alternative: I want to help → Real leads → Anywhere in Ontario → Check cases → Discuss this real lead. City-specific results do not infer treatment location from the charity office.

## Try the organization journey

Check our information → Use Lucy public page → Review information. Or say `Lucy organization checklist`. The saved-research checklist distinguishes organization-published material from unfinished system checks. Organizations update their own appropriate public channels; no private uploads are accepted. A link does not establish representation authority or guarantee support. This screen does not fetch again; request a separate permitted refresh.

## Separate fictional demonstration

Choose Fictional workflow demo in I want to help, or explicitly say `fictional Ottawa`. Demo controls modify only this fictional source. Clarifying a separate grant changes an unknown gap to CAD1,000. Real H-MEM retains earlier and later synthetic reviews. History tab currently queries the fictional case; Lucy history is in chat. No synthetic result can qualify Lucy. Detailed scenario/CLI notes remain in INCREMENT_NOTES.md as development history, not current product status.

## Feedback

Feedback distinguishes session-only city preference, unverified Lucy correction lead and proposed policy rule. No correction changes facts or qualification; no suggestion changes policy. Notes remain only in server process memory, are not delivered to a reviewer, and disappear on restart. Do not enter private information.

## Actual integrations

- Official local H-MEM: sourced review save/recall/history, including the real pending path when configured.
- Public retrieval: only two fixed Lucy articles; rule-based candidate extraction with source quotes and date conversion. Not general model reasoning or clinical authenticity verification.
- NVIDIA: one separately authorized real extraction (281tokens) and validated replay; that allowance is exhausted. Separately, the optional chat-intent provider made live direct NVIDIA calls on the account owner's own key under owner-approved caps (MODEL_PROVIDER_VERIFICATION.md). Without configuration, page operations do not call NVIDIA.
- Zetaris: separate read-only historical identity query succeeded; current Lucy case is not connected through Zetaris.
- Nightshift: unconnected. A Meterless Runtime provider adapter exists but no runtime has been reachable, so it is untested. Direct NVIDIA calls are not Nightshift use.
- No current real six-gate qualification, production hosting/authentication/concurrency, full regional risk coverage or general web discovery.

## Validation

```text
python -m unittest discover -s purrpose -t . -q
node purrpose/test_api_client.cjs
```

For actual H-MEM integration tests set PURRPOSE_HMEM_REFERENCE to your absolute official reference file first. Without it those tests skip, not pass. No test command above requests a paid model or real website. Browser live retrieval was verified separately; see REAL_REVIEW_VERIFICATION.md and HANDOFF.md for actual run evidence.

## Continue development

Read root START_HERE.md, current HANDOFF.md and the normative first draft/guidance package. Use FRONTEND_INTEGRATION.md for Josh's/another front end, and COACH_DEMO_RUNBOOK.md for a short demonstration. Current UI is a functional prototype, not the final visual design. Secrets, local state and raw read diagnostics stay out of Git. Local changes are not shared until an explicitly authorized commit/push. No public deployment or third-party messaging is implied.

## Connected designed home

Open http://127.0.0.1:8766/home.html for the connected adaptation of Josh's actual upstream home/logo design. The original full demo workspace remains at `/`. See DESIGN_INTEGRATION.md for source commit, modifications and test evidence. No fake authentication or arbitrary/social-page retrieval is implied by this design.

### Chat, Review tab, Agent map and run dashboard
`/home.html` is a chat (this visit's chats only, nothing saved) with a right-hand panel. **Review** shows the case from backend fields only; **Agent map** shows which code roles ran for an answer, timings, and the tool row (NVIDIA Nemotron only when a call really happened, H-MEM, Zetaris and Nightshift marked not connected). `/dashboard.html` lists the last 50 runs since the server started (cleared on restart). More checks: `node purrpose/test_agent_map.cjs`, `node purrpose/test_review_panel.cjs`.

### Organization walkthrough
Open `/organizations.html` (also linked as **I’m a rescue organization** on the designed home). This is a fully fictional, no-installation walkthrough served by the local app. It shows what public evidence an organization should add, how it publishes on its own website, and how a later recheck affects the supporter view. All data and recheck results are simulated; independent verification remains pending. No APIs, models, uploads or payments are used by this page. The existing real Lucy checklist is linked separately.

## Mentor presentation and relay
Open `/architecture.html` for the backend roles, feedback loop, tool layers and present limitations. Read root `NEXT_DEVELOPER.md` for the current handoff and next agreed priority: unify supporter / organization / both intents in one chat. This is next work, not an existing feature.
