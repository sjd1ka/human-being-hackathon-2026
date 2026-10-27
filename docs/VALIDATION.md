# Tests and verification

## Automated tests

From the repository root:

```powershell
$env:PURRPOSE_HMEM_REFERENCE=(Resolve-Path '../meterless/engines/hmem/reference/src/index.ts').Path
.\.venv\Scripts\python.exe -m unittest discover -s purrpose -t . -q
node purrpose/test_api_client.cjs
node purrpose/test_agent_map.cjs
node purrpose/test_review_panel.cjs
node purrpose/test_live_panels.cjs
```

The validated build passed **323 Python tests** with the official H-MEM reference configured, plus the four JavaScript checks. Without that reference, H-MEM integration tests skip. Remote transports use offline fixtures/mocks in automated tests; running the suite does not automatically spend model credit or provision cloud resources.

`python -m purrpose.doctor` checks local assets and runtime prerequisites without making external requests. A readiness check does not establish that a remote integration works.

## Live integrations verified

| Component | Observed behavior |
|---|---|
| AWS-hosted Zetaris | SSL JDBC connection and fixed read-only identity/directory SELECTs succeeded. The CRA 2024 source returned 376 Ontario animal-charity rows in the observed run. |
| NVIDIA Nemotron | A real hosted intent-classification request returned a validated organization-search intent and entered the directory workflow. |
| Meterless Nightshift | 27 Oct 2026, Nightshift 1.2.7 for Windows: six chat requests (`discover` Guelph, `select_real_case`, `allocation`, `history`, `about`, `list_organizations`) went Purrpose → Nightshift Runtime → `nvidia/nemotron-3.5-lightning-30b-a3b`. All returned validated intents in 0.7–1.0 s at about 565 tokens each, and the Nightshift receipts named that routed model. Before thinking was disabled for the pinned lane, about 40% of requests failed with Nightshift `502 empty_response`. |
| Meterless H-MEM | Official reference engine saved observations and retrieved records under the matching directory/website scope. |
| Public website reader | Read organizational pages and the explicitly supplied Lucy appeal/update while honoring applicable access rules. Failed or unsupported access remained incomplete. |

These are observations from the configured environment, not a guarantee of availability, source freshness or identical results on another account. Raw runtime captures, credentials and memory state are not distributed as future live answers.

## Boundaries

The current implementation does not independently authenticate clinical documents, certify current charity/risk status, guarantee remaining funding or produce a real qualified donation recommendation. It does not establish automatic individual-appeal discovery for every organization or a production hosted deployment.

See [Setup](SETUP.md) for reproducible configuration and [Architecture](ARCHITECTURE.md) for the distinction between live public observations, curated case logic and synthetic repair tests.
