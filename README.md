<p align="center">
  <img src="design/mascot/purrpose-kitten.png" width="224" alt="A fluffy orange kitten resting on a little patch of grass">
</p>

# Purrpose

### Before you give, see the evidence.

Purrpose helps people explore animal-rescue appeals through public evidence. Donors see what supports a claim and what still needs checking. Rescue organizations see what information they could publish to make their needs easier to understand.

**A fair chance to be seen, for organizations of every size.**

Built for the Open Agent Hackathon 2026. The current prototype focuses on Ontario, Canada.

## What you can do

- **Find rescue organizations** through a historical government directory queried via Zetaris.
- **Inspect a public website or appeal** and read source-linked observations.
- **Understand the gaps**: what was found, what was not found in the pages read, and what remains unverified.
- **Continue the conversation** using saved observations and Meterless H-MEM history.
- **See the work** in the Review, Agent map and Runs views, including actual tool status and model usage.

Ask naturally, for example:

> I'd like to support a cat rescue around Toronto. Could you help me find options?

Or share an organization's public URL and ask what information it could add.

Donors and organizations use one evidence system. The response changes with the question; the evidence standard stays the same.

## How it works

The coordinator selects a directory query, a bounded website investigation or a memory lookup. Follow-up questions can reuse observations; explicit refreshes read the source again. Source failures remain visible.

| Technology | Role |
|---|---|
| **Meterless Nightshift** | Primary AI provider. Purrpose sends each intent request to the local Nightshift Runtime, which routes it to an NVIDIA Nemotron lane. [Setup](docs/NIGHTSHIFT.md). |
| **NVIDIA Nemotron** | Nemotron 3.5 Lightning, reached through Nightshift, classifies the request. Code validates the model's output before choosing an action. |
| **Zetaris Lightning** | Read-only SQL queries over the connected public CRA 2024 charity directory. |
| **AWS** | Hosts the demonstrated Zetaris instance. The application does not provision AWS resources. |
| **Meterless H-MEM** | Saves and recalls scoped source observations and unresolved questions using the official reference engine. |
| **Python + HTML/CSS/JavaScript** | Local backend, basic evidence checks and conversational interface. |

Roles run as code in one process, with conditional checks and shared state. The model interprets requests; it does not authenticate medical evidence or certify trust. [Architecture](docs/ARCHITECTURE.md) describes the implemented paths and their limits.

## Run locally

Requirements: **Python 3.12+**. Connected H-MEM also needs **Node.js 24+**. A dedicated GPU is not required.

```powershell
git clone https://github.com/sjd1ka/human-being-hackathon-2026.git
cd human-being-hackathon-2026
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m purrpose.server --port 8767
```

Open [Purrpose](http://127.0.0.1:8767/home.html).

This minimal launch opens the interface without cloud credentials. **To enable live directory queries, NVIDIA and persistent H-MEM, follow [Setup](docs/SETUP.md).** You need your own authorized Zetaris connection, vendor JDBC driver, Java/JVM, NVIDIA key and configured budgets. Credentials, cloud services and API credits are not included.

## Current scope

Purrpose organizes evidence to support a decision. It does not process donations, issue fraud verdicts or guarantee that an appeal is trustworthy.

- Government directory records are historical; they do not establish current registration or medical need.
- Public website statements are not independently authenticated clinical documents.
- Funding remains unknown without corresponding verified costs and funds received.
- Website access and page coverage are limited. Login-protected content, social-media scraping, private uploads and media analysis are unsupported.
- Individual appeal links can be supplied directly; automatic discovery of a current medical fundraiser for every organization is not established.

Next steps include deeper evidence evaluation, broader permitted source coverage and automatic appeal discovery.

## Documentation

- [Installation and tool configuration](docs/SETUP.md)
- [Architecture and tool responsibilities](docs/ARCHITECTURE.md)
- [Tests and verification](docs/VALIDATION.md)

Source code and tests are in `purrpose/`. Original logo and mascot assets are in `design/`. Synthetic examples are explicitly labelled and kept separate from live observations.

Built by **Shiyuan Tian, Benedictus Josh Christian, Farwa Yaqub and Pimmy (Pimlada Cbys)**.
