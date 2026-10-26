# Plan: local Zetaris with CRA charity data

Status: plan only, 26 October 2026. Nothing below is built yet.

## Why local

The hackathon Participant Setup Guide (updated 21 Oct 2026) says "Zetaris and Meterless must be running on your machine to be eligible" and "For this hackathon, everyone runs Zetaris locally in Docker". The only alternative it offers is Zetaris in your own AWS account. The current adapter (`zetaris.py`) only accepts a remote SSL JDBC instance, which the team's AWS server provided; that server is unreachable at the moment. Josh approved switching to local on 26 Oct 2026, following the hackathon rules. The remote JDBC path stays in the code for later.

## Data source

Government of Canada open data, "2024 List of charities" (CRA, T3010 returns), dataset `80c00cdb-1358-415c-bb8b-0de7f12675b8` on open.canada.ca. Each table has a CKAN `datastore_search` API. Use the `/data/api/action/` path; `/data/api/3/action/` reset connections in testing.

| Bookmark (REST table) | Resource ID | Filter | Rows (checked 26 Oct) | Feeds |
|---|---|---|---|---|
| `ontario_animal_identity` | `694fdc72-eae4-4ee0-83eb-832ab7b230e3` (Identification) | `{"Category":"0180","Province":"ON"}`, `limit=1000` | 376 | Identity and location |
| `ontario_animal_programs` | `1f16eb1b-cc03-4c95-a81c-0fdc0722c5ee` (Charitable programs) | by BN list or same category join | not counted yet | Does the charity actually do animal care |
| `ontario_animal_financial` (optional) | `e545170c-3689-4833-b2a8-e9e83100ab59` (Financial data) | by BN | not counted yet | Background only, never case funding |

Checked by hand on 26 Oct: Toronto Cat Rescue `720884691RR0001` (Etobicoke) and The Guelph Humane Society Incorporated `119236305RR0001` (Guelph) are both in the Identification table with category 0180. Guelph's 2024 program text mentions shelter, adoption and spay/neuter. CKAN returns 100 rows by default, so `limit=1000` is required.

Not used: Directors/officers (personal information, no check needs it), General information (Y/N codes, low value). A revoked or annulled charities list for the risk check is a stretch goal; no queryable source is confirmed yet.

## Setup statements (to run once per machine)

Syntax from the Zetaris Lightning SQL reference (`zetaris-getting-started/docs/guides/zetaris-lightning-sql-commands.md` §6.2, confirmed by Exa research on zetaris.github.io). One statement per call. Saved as `purrpose/zetaris_setup.sql` when built.

```sql
CREATE LIGHTNING DATABASE CRA_CHARITIES_2024 DESCRIBE BY "CRA 2024 List of charities, open.canada.ca";

CREATE LIGHTNING REST TABLE ontario_animal_identity FROM CRA_CHARITIES_2024 REQUEST (
  endpoint "https://open.canada.ca/data/api/action/datastore_search?resource_id=694fdc72-eae4-4ee0-83eb-832ab7b230e3&filters=%7B%22Category%22%3A%220180%22%2C%22Province%22%3A%22ON%22%7D&limit=1000",
  method "GET",
  http_encoding "URLENCODED",
  response_type "JSON",
  insecure_ssl "false"
) HEADER () BODY ();
```

Read rows with `LATERAL VIEW explode(result.records) AS fact`, the same shape the remote `IDENTITY_SQL` already uses. The exact inferred schema must be checked after creation (`DESCRIBE`), because Zetaris does not document CKAN specifically.

## Speed and reliability

A REST table may call its source again on every query (Zetaris SQL companion guide). open.canada.ca reset some connections during testing. Plan: try `OFFSITE CACHE TABLE CRA_CHARITIES_2024.ontario_animal_identity TO FILE WITH (expireInSec "-1")` (documented in §19.4; untested on REST tables). If it works, label results with the cache time. If it does not, keep live queries and show a source failure as "registry unavailable", never as a failed charity check.

## Purrpose changes

1. `zetaris.py`: add a local REST mode next to remote JDBC, chosen by an explicit setting (`ZETARIS_MODE=local_rest` or `remote_jdbc`). No silent fallback between them. REST call format copied from `zetaris-getting-started/scripts/run_sql.py` (`/sql-editor/sqls/run`, Bearer key, `X-Org-ID: 1`, fresh UUID `X-Request-ID`), port 18888 on Josh's PC.
2. Query: fixed read-only SQL with the charity number inserted only after it matches `^\d{9}RR\d{4}$`. The number comes from case data, never from chat text.
3. Result: reuse `normalize_identity` and `supporter_identity_view`. 2024 data never sets `current_registration_verified` or `case_qualified`.
4. Evaluator: compare returned legal name and city with the saved manual CRA observation for Lucy; show supported, conflict or unverified. Gate stays pending.
5. Flow: an explicit step ("check charity registry"), with its own timeout, separate from "refresh Lucy" (a first Zetaris query takes about 30 s; the UI deadline is 65 s). Result saved into the H-MEM review so history shows when the registry was checked.
6. Trace: each call appears in `/api/debug` (query name, duration, row count, error category; no key).
7. Sample mode for judges: opt-in, clearly labelled cached rows; never a silent substitute for a failed live query.

Tests first: charity-number validation, no chat-text path to SQL, missing configuration is "unavailable" (not pass, not fraud), sanitized errors with no key in output, historical-only semantics, explicit mode with no fallback.

## Before starting

- Free about 8 GB for Docker (close PowerPoint, Todoist, most Chrome tabs), start Docker Desktop, `docker compose up -d` in `zetaris-platform-extract/zetaris-platform`, then `./verify.sh`.
- First check that Zetaris itself can reach open.canada.ca (one `CREATE REST SESSION TABLE` preview).
- Josh adds `ZETARIS_API_KEY` to `.env.local` himself, or Purrpose reads `zetaris-getting-started/.env.local` via a flag.
- Timebox: if Zetaris start-up or source creation fails twice, stop and report.
- Update FULL_GUIDANCE §Zetaris and HANDOFF with the local decision; mark Zetaris "running" in the diagram only once it is in the live flow.
