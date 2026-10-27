# Setup and reproduction

## Access checklist

The repository contains code, not a provisioned service. To reproduce the integrated application you need:

- Python 3.12+, Node.js 24+, Git and Java 21 (tested on Windows).
- The official Meterless H-MEM reference source and writable local storage.
- Your own NVIDIA API key with access to `nvidia/nemotron-3.5-lightning-30b-a3b`, if you want live model intent classification.
- An authorized running Zetaris Lightning instance. The demonstrated instance runs on AWS; no Docker/local Zetaris installation is required on your laptop.
- A vendor-provided Lightning JDBC JAR, JDBC username/password and an SSL-enabled remote URL. Get the driver and connection string from your Zetaris administrator. Neither is supplied here.
- Public outbound access to the configured instance, NVIDIA and permitted government/rescue websites. Do not expose this local development server publicly.

The app does not call AWS management APIs, create AWS resources or need AWS IAM access keys. A different compatible Zetaris deployment can work, but the fixed schema/table contract below must match. This portable recipe is documented from the validated configuration; it is not a claim that a new cloud instance has been provisioned or tested by a clean clone.

## 1. Python dependencies

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env.local
```

Edit `.env.local` privately. It is ignored by Git. Existing environment variables override file values, so check old shell settings if the selected route differs from the file. Never print the file to diagnose a connection.

`JPype1` and `JayDeBeApi` are for the JDBC Python process. The web server and most tests use the standard library. `tzdata` supplies timezone data on Windows.

## 2. Meterless H-MEM

Clone the official source beside this repository:

```powershell
git clone https://github.com/Meterless/Meterless.git ../meterless
git -C ../meterless checkout 1742dec56a66e58eef9dda2d2b865823758ca8cd
node --version
```

Tested reference: `../meterless/engines/hmem/reference/src/index.ts`, upstream revision above, Node 24.18.0. Purrpose runs the official TypeScript reference through its Node bridge; it does not require the Nightshift desktop app to use H-MEM. Engine licensing remains with the upstream project.

Local readiness check (no network/model call):

```powershell
.\.venv\Scripts\python.exe -m purrpose.doctor --reference ../meterless/engines/hmem/reference/src/index.ts
```

Memory is stored under the state path and workspace you select. Reuse both to recall earlier records; keep different deployments/workspaces separate. Do not commit the state directory.

## 3. NVIDIA (optional live intent classification)

Set these privately in `.env.local`:

- `PURRPOSE_MODEL_PROVIDER=nvidia_direct`
- `NVIDIA_API_KEY`: your key
- `NVIDIA_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b`
- All `PURRPOSE_MODEL_*` budget limits from the example

The example permits at most 3 model requests per server process, 128 output tokens per request, a 10-second timeout and no automatic retry. This is an application limit, not a claim about your real remaining credit. Obtain the account holder's budget approval. Do not reset the server to silently renew an agreed allowance.

Ordinary-language requests in the AWS-connected chat can use the model's validated intent to enter directory discovery. URL reads, explicit refreshes and safety/ambiguity handling can stay code-only. Repeated identical request/context pairs may use the intent cache; Agent map distinguishes cached from new calls. API success is established only after a request returns successfully, not by a startup `ready` label.

Leave the provider blank to disable models. Invalid output, exhausted caps or a failed call fall back to bounded code interpretation without silently changing provider. Evidence checks and answer text remain code-based.

## 4. AWS-hosted Zetaris JDBC

Fill the four `ZETARIS_*` JDBC settings in `.env.local`. Use absolute paths for `ZETARIS_JDBC_JAR`. The preflight requires a remote host and `ssl=true` in the JDBC URL. Use the exact vendor/admin connection URL. Do not disable TLS validation.

Locate the existing JVM library. On Windows with Java 21 it is commonly:

```text
C:/Program Files/Java/<your-jdk-folder>/bin/server/jvm.dll
```

On Linux/macOS use the appropriate `libjvm.so`/`libjvm.dylib` path and a Python environment with the same JDBC packages. Java, Python and the JAR must be compatible.

The fixed remote adapter expects these tables in database `DONATION_FEASIBILITY_20261022`:

| Table | Purpose |
|---|---|
| `ontario_animal_directory` | CRA 2024 Ontario animal-charity directory, capped at 1000 source records |
| `tcr_identity` | Toronto Cat Rescue historical identity diagnostic |

Ask the instance administrator to inspect/provision the schema using [zetaris-schema.sql](zetaris-schema.sql). This file contains one-time DDL: it is never run by application startup and must not be executed against an existing database blindly. Creating an instance or connector is a separate account-owner action. The user-facing app issues fixed read-only SELECTs; it does not accept user SQL or write to government data.

`purrpose/ontario_directory_create.sql` records the previously validated directory connector statement. Table names are pinned in `purrpose/directory.py` and `purrpose/zetaris.py`; different database names require a deliberate adapter change and retest.

## 5. Start the integrated demo

After configuration, from PowerShell:

```powershell
.\scripts\start_demo.ps1 `
  -HMemReference ../meterless/engines/hmem/reference/src/index.ts `
  -EnableZetaris `
  -Jvm 'C:/Program Files/Java/<your-jdk-folder>/bin/server/jvm.dll'
```

The default Python is `.venv/Scripts/python.exe`; `-Python` and `-JdbcPython` accept another existing Python environment. `-EnvFile`, `-State`, `-Workspace` and `-Port` are configurable. No user-specific absolute paths or credentials are embedded in the launcher.

If Windows blocks PowerShell scripts under its execution policy, leave that policy unchanged and use this equivalent explicit Python command:

```powershell
.\.venv\Scripts\python.exe -m purrpose.server --port 8767 `
  --env-file .env.local `
  --reference ../meterless/engines/hmem/reference/src/index.ts `
  --state purrpose/.state/hmem --workspace purrpose-demo `
  --zetaris-remote-env .env.local `
  --zetaris-python .venv/Scripts/python.exe `
  --zetaris-jvm 'C:/Program Files/Java/<your-jdk-folder>/bin/server/jvm.dll'
```

Open `/home.html`, `/app.html`, `/dashboard.html` or `/architecture.html` on `http://127.0.0.1:8767`. `/registry.html` is a separate fixed identity diagnostic. The localhost URL works only on the machine running the server. GitHub Pages cannot host this Python/Java backend.

## 6. Confirm integration status

Use the chat and its execution records. Confirm Zetaris SELECT results, a new NVIDIA call where intended, H-MEM save and a later recall. Open Agent map on the corresponding reply. A configured endpoint, installed package or old screenshot does not prove current use. Website 403s, redirects and robots restrictions can legitimately prevent a read.

## Nightshift (primary AI provider)

Nightshift is the primary model route: `PURRPOSE_MODEL_PROVIDER=meterless`, with the NVIDIA key held inside Nightshift rather than in `.env.local`. Install, NVIDIA lane, token and checks are in [NIGHTSHIFT.md](NIGHTSHIFT.md). It was live-verified on 27 October 2026 with Nightshift 1.2.7 for Windows and a pinned `nvidia/nemotron-3.5-lightning-30b-a3b` lane. The Web edition does not provide the 8088 endpoint. Never paste an NVIDIA key into a runtime-token field.

`nvidia_direct` remains a separate, explicitly labelled route for development; it is never reported as Nightshift use. Credentials and API credits are not included.
