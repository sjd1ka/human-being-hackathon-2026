# Nightshift setup (primary AI provider)

Purrpose sends its intent-classification requests to **Meterless Nightshift** on your own computer. Nightshift then calls **NVIDIA Nemotron** with your NVIDIA key. The app never sees the NVIDIA key; it only holds the Nightshift runtime token.

```
Purrpose  ──►  Nightshift (127.0.0.1:8088/v1)  ──►  NVIDIA Nemotron 3.5 Lightning (hosted)
```

Verified on 27 October 2026 with Nightshift 1.2.7 for Windows. The laptop had AMD integrated graphics and 13.9 GB of RAM, and every model ran in NVIDIA's cloud lane.

## What you need

- Windows 10 1809+ or 11 (x64). Mac and DGX editions also provide the 8088 endpoint. The **Web** edition does not, so don't use it for this.
- About 1 GB of disk and some free RAM. Nightshift pauses requests when memory runs critically low (see Troubleshooting).
- A free NVIDIA API key from https://build.nvidia.com (it starts with `nvapi-`).
- Purrpose set up as in [SETUP.md](SETUP.md).

No dedicated GPU is needed. The 1.2.7 build includes Vulkan and CPU backends, and cloud lanes don't use the GPU at all.

## 1. Download and check the installer

1. Open https://meterless.ai/Nightshift/WIN/ and download **`Nightshift_1.2.7_x64-setup.exe`** (654,073,220 bytes). Don't use the older 1.2.1–1.2.3 files or the "Online" installer.
2. Check its checksum in PowerShell:
   ```powershell
   (Get-FileHash "$env:USERPROFILE\Downloads\Nightshift_1.2.7_x64-setup.exe").Hash
   ```
   It must print `F30CFC10FED2510B7820C512E4EA78459967670E0A5FB2C7AF9D68B4B5F03D3A` (from the published `SHA256SUMS`).
3. Run it. The build is intentionally unsigned; the Meterless team confirmed this in the HackOS Help Meterless channel. So SmartScreen warns you: choose **More info → Run anyway**. It installs per user into `%LOCALAPPDATA%\Nightshift\` with no admin prompt.
4. If Windows asks about port 8089 (phone pairing), allow it on **private** networks only.

## 2. Connect NVIDIA inside Nightshift

1. Open Nightshift, then **Setup → Providers**. Under Cloud provider keys, choose **NVIDIA**, paste your `nvapi-…` key and save. It should say **configured**.
2. Open **Night → Lanes** (Ctrl+6) and use **+ Add lane** (or **Add to race**). Pick the cloud model **`nvidia/nemotron-3.5-lightning-30b-a3b`**. Wait for the card to show **ready** and "nvidia accepted the key".

The yellow "No lane has duty Judge or Verify" notice is about Nightshift's overnight jobs. Purrpose doesn't need it.

## 3. Give Purrpose the Nightshift token

1. In Nightshift, open **Console** (the plug icon, Ctrl+5) and **Reveal → Copy** the API key. This is the *runtime token*, not your NVIDIA key.
2. In your private `.env.local` (git-ignored, never commit it):
   ```
   PURRPOSE_MODEL_PROVIDER=meterless
   METERLESS_BASE_URL=http://127.0.0.1:8088/v1
   METERLESS_RUNTIME_TOKEN=<paste the Console key>
   METERLESS_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b
   ```
   Pin the exact Nemotron id rather than `meterless/auto`. That way every answer is visibly Nemotron, and Purrpose turns Nemotron's "thinking" off for it. Without that, Nightshift returns `502 empty_response` on many requests.
3. Keep the `PURRPOSE_MODEL_*` budget limits from `.env.example`, but give Nightshift more time than direct NVIDIA needs: `PURRPOSE_MODEL_TIMEOUT_SECONDS=60` (the chat page itself gives up after 65 s).

## 4. Check it works

Nightshift is up when this answers:
```powershell
curl.exe -s http://127.0.0.1:8088/healthz        # {"status":"ok","engine":"meterless"}
```

Start Purrpose with the same `--env-file` (see [SETUP.md](SETUP.md)). The console should print:
```
Chat model: meterless nvidia/nemotron-3.5-lightning-30b-a3b ready
Meterless discovery: online
```

Then open `/app.html` and ask, for example, *"how would I give money to help a cat?"*. Open **Agent map**: the tools list should show **"Nightshift · 1 call · request recorded · N tokens"**. `/api/status` now reports `"nightshift": "meterless_runtime_request_succeeded"`. In Nightshift's Console, the request appears under the app **purrpose** with its receipt (`routed_model: nvidia/nemotron-3.5-lightning-30b-a3b`).

On our run, six different questions each came back in 0.7–1.0 s at about 565 tokens, all routed to Nemotron 3.5 Lightning.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Meterless discovery: unauthorized` | Wrong token. Copy the **Console** key again; the NVIDIA key does not go here. |
| `Meterless discovery: offline` | Nightshift isn't running. Start it; closing its window keeps the runtime running. |
| Agent map: "failed" with `provider_http_error` | Look in `%LOCALAPPDATA%\ai.meterless.runtime\logs\meterlessd.log`. If it shows `admission posture → Pause (memory pressure critical)`, close heavy apps (Docker, WSL, VS Code, extra browser tabs) and minimise Nightshift. If Nightshift returns `empty_response`, check that `METERLESS_MODEL` is the pinned `nvidia/nemotron…` id. |
| `model_not_found` | The id must match `GET /v1/models` exactly; the card's display name isn't the id. |
| Purrpose answers "I did not confidently understand" and the Agent map shows no Nightshift row | No model is configured in the running server. Check `PURRPOSE_MODEL_PROVIDER=meterless` and that only **one** Purrpose server is on the port. On Windows two can share it: `Get-NetTCPConnection -LocalPort 8767 -State Listen`. |

Without Nightshift, Purrpose still runs: it falls back to labelled fixed-phrase matching and never silently switches to direct NVIDIA.
