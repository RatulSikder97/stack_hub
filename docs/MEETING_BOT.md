# Meeting Bot — Tech Spec

The "real-time meeting bot" path lets a user paste a Zoom / Google Meet /
Microsoft Teams URL into Stack Hub. A bot joins the call, records audio,
transcribes it, and returns the transcript text to the brief composer.

This document specifies the components, contracts, and operational details
of that path. For the wider Stack Hub architecture see [`README.md`](../README.md);
for deployment, see [`DEPLOYMENT.md`](DEPLOYMENT.md).

---

## 1. External services

The meeting bot is an integration on top of two SaaS providers. Stack Hub
itself does not run any audio infrastructure.

| Service | Role | Account-level config |
|---|---|---|
| **Recall.ai** | Headless meeting bot. Joins the call as an attendee, captures audio, hands the audio stream to a transcription provider, exposes the resulting transcript via REST. | API key in `.env` (`RECALL_API_KEY`). Workspace lives in a single AWS region (currently `ap-northeast-1`). |
| **Deepgram** | Speech-to-text provider. Receives the audio stream from Recall and returns word-level transcript JSON. Required only for non-English meetings; English meetings can use Recall's free `meeting_captions` passthrough. | Deepgram API key pasted into the **Recall dashboard → Settings → Integrations → Deepgram**. Stack Hub never sees this key directly. |

Recall handles the bot lifecycle, audio pipeline, S3 storage, and webhook
emission. Deepgram (when enabled) handles the ASR. Stack Hub is a thin
client over Recall's REST API.

---

## 2. Architecture

```
┌──────────────┐                                    ┌──────────────┐
│  React SPA   │  POST /api/meeting/bot             │              │
│  /meetings   │ ─────────────────────────────────▶ │              │
│              │  GET  /api/meeting/bot/{id}  (poll)│   FastAPI    │
│              │ ─────────────────────────────────▶ │  api.py      │
│              │  DELETE /api/meeting/bot/{id}      │              │
│              │ ─────────────────────────────────▶ │              │
└──────────────┘                                    └──────┬───────┘
                                                           │
                                                           │ pipeline.recall.RecallClient
                                                           │ (httpx + Token auth)
                                                           ▼
                                              ┌────────────────────────┐
                                              │   Recall.ai REST API   │
                                              │  ap-northeast-1        │
                                              │                        │
                                              │  POST /bot/            │
                                              │  GET  /bot/{id}/       │
                                              │  POST /bot/{id}/       │
                                              │       leave_call/      │
                                              └──────┬─────────────────┘
                                                     │
                                                     │  (joins meeting,
                                                     │   streams audio
                                                     │   to ASR provider)
                                                     ▼
                            ┌──────────────────────────────────────────────┐
                            │  Deepgram WebSocket                          │
                            │  wss://api.deepgram.com/v1/listen            │
                            │  ?model=nova-3&language=bn                   │
                            │                                              │
                            │  (when RECALL_TRANSCRIPTION_PROVIDER=        │
                            │   deepgram_streaming; otherwise the meeting  │
                            │   platform's own captions are used)          │
                            └──────────────────────────────────────────────┘
                                                     │
                                                     │  diarized JSON stored
                                                     ▼
                                              ┌──────────────────────────┐
                                              │  S3 (Recall-managed)     │
                                              │  presigned download_url  │
                                              │  in bot.recordings[0].   │
                                              │  media_shortcuts.        │
                                              │  transcript.data         │
                                              └──────────────────────────┘
```

The browser polls Stack Hub. Stack Hub polls Recall. Recall is the system
of record for bot state. The transcript is fetched lazily — only when the
bot reaches `done` does Stack Hub follow the presigned S3 URL and parse
the JSON.

---

## 3. Module layout

```
scripts/pipeline/recall.py
├── RecallClient                       # synchronous httpx wrapper
│   ├── create_bot(meeting_url, ...)   # POST /bot/
│   ├── get_status(bot_id)             # GET  /bot/{id}/
│   ├── leave_call(bot_id)             # POST /bot/{id}/leave_call/
│   ├── _fetch_transcript_text(...)    # follows media_shortcuts.transcript
│   └── _download_json_url(url)        # no-auth GET for S3 presigned URLs
│
├── _STATE_MAP                         # Recall status_changes → simplified state
├── _simplify_state(codes)             # walks codes latest-first
├── _build_provider_options(...)       # builds recording_config options dict
├── _format_transcript(payload)        # multi-shape transcript → "Speaker: text"
├── RecallBotStatus (dataclass)        # what the API endpoint returns to the SPA
└── RecallError / RecallNotConfigured  # typed exceptions

scripts/pipeline/web/api.py
└── routes:
    ├── POST   /api/meeting/bot              → RecallClient.create_bot
    ├── GET    /api/meeting/bot/{bot_id}     → RecallClient.get_status
    ├── DELETE /api/meeting/bot/{bot_id}     → RecallClient.leave_call
    └── POST   /api/meeting/parse            → ingest pasted .vtt/.srt/.txt
                                               (parallel to the bot path)
```

`RecallClient` is constructed per-request and is otherwise stateless. Tests
inject a fake `httpx.Client` to script HTTP responses without network I/O.

---

## 4. Configuration

All configuration is environment-variable driven. Defaults live in
[`.env.example`](../.env.example).

| Variable | Required | Default | Notes |
|---|---|---|---|
| `RECALL_API_KEY` | yes (for bot path) | — | 40-char Recall token. Region-locked to the workspace it was issued in. |
| `RECALL_BASE_URL` | no | `https://ap-northeast-1.recall.ai/api/v1` | Override only if your workspace lives in a different region. |
| `RECALL_TRANSCRIPTION_PROVIDER` | no | `meeting_captions` | One of: `meeting_captions`, `deepgram_streaming`, `assembly_ai_streaming`, etc. |
| `RECALL_TRANSCRIPTION_LANGUAGE` | no | _empty_ | BCP-47 / Deepgram-style code (`en`, `bn`, `hi`, …). Ignored by `meeting_captions`. |
| `RECALL_TRANSCRIPTION_MODEL` | no | _empty_ | Provider-specific model name (`nova-3` for Deepgram + Bengali). |

Per-call overrides: `RecallClient.create_bot()` accepts the same three
transcription params as kwargs, which take precedence over env. CLI tools
or future per-meeting UI controls can use this without restarting the app.

---

## 5. Data flow

```
SPA          FastAPI         RecallClient        Recall.ai           Deepgram        S3
 │              │                  │                  │                   │           │
 │ POST /bot    │                  │                  │                   │           │
 │─────────────▶│                  │                  │                   │           │
 │              │ create_bot()     │                  │                   │           │
 │              │─────────────────▶│                  │                   │           │
 │              │                  │ POST /bot/       │                   │           │
 │              │                  │─────────────────▶│                   │           │
 │              │                  │     {bot_id}     │                   │           │
 │              │                  │◀─────────────────│                   │           │
 │              │     bot_id       │                  │                   │           │
 │              │◀─────────────────│                  │                   │           │
 │ {bot_id}     │                  │                  │                   │           │
 │◀─────────────│                  │                  │                   │           │
 │                                                    │                   │           │
 │ poll loop (every ~3s):                             │  joins meeting    │           │
 │                                                    │──────────────────▶│           │
 │ GET /bot/{id}                                      │  streams audio    │           │
 │─────────────▶│                  │                  │──────────────────▶│           │
 │              │ get_status()     │                  │                   │ writes    │
 │              │─────────────────▶│                  │  transcript JSON  │ JSON      │
 │              │                  │ GET /bot/{id}/   │◀──────────────────│──────────▶│
 │              │                  │─────────────────▶│                   │           │
 │              │                  │ status_changes,  │                   │           │
 │              │                  │ recordings[*]    │                   │           │
 │              │                  │◀─────────────────│                   │           │
 │              │                  │ if state==done:  │                   │           │
 │              │                  │   GET <s3_url>   │                   │           │
 │              │                  │─────────────────────────────────────────────────▶│
 │              │                  │   diarized JSON  │                   │           │
 │              │                  │◀─────────────────────────────────────────────────│
 │              │ {state, codes,   │                  │                   │           │
 │              │  transcript}     │                  │                   │           │
 │              │◀─────────────────│                  │                   │           │
 │ status JSON  │                  │                  │                   │           │
 │◀─────────────│                  │                  │                   │           │
```

The polling loop in the SPA stops the moment `state == "done"` arrives;
that is the only signal the transcript is ready. See §6 for why
`call_ended` is **not** a terminal state.

---

## 6. State machine

Recall emits a sequence of `status_changes`. Stack Hub collapses them into
one of five UI-facing states:

| Recall code | Simplified state | Meaning |
|---|---|---|
| `ready` | `queued` | Bot row created; not yet acting. |
| `joining_call` | `joining` | Dialing in. |
| `in_waiting_room` | `joining` | Waiting for host admit. |
| `in_call_not_recording` | `in_call` | Joined; not yet recording (e.g. permission gating). |
| `in_call_recording` | `in_call` | Audio is being captured + streamed to ASR. |
| `call_ended` | _(unmapped — falls back)_ | **Bot has left, transcript is still being finalized.** Stack Hub explicitly does NOT map this to `done`. `_simplify_state` walks back to the previous known code, typically `in_call_recording → in_call`, so the SPA keeps polling. |
| `recording_done` | `done` | Final transcript is on S3; safe to fetch. |
| `done` | `done` | Same as above (Recall sometimes emits both). |
| `fatal` | `error` | Bot could not join / lost connection / provider rejected. The `message` field carries Recall's reason. |

> **Why `call_ended` is unmapped:** historically it was mapped to `done`,
> which caused the SPA to stop polling the moment the bot left the call —
> before Recall had finalized the recording. The transcript fetch then ran
> against a not-yet-existent file and returned empty. The fix: rely on
> `recording_done` / `done` as the only terminal-success states. See
> [`tests/test_recall.py::test_simplify_state_call_ended_is_transient_not_done`](../tests/test_recall.py).

---

## 7. Transcript retrieval

When the bot reaches a terminal state, `RecallClient._fetch_transcript_text`
walks the recordings array on the bot:

```
bot.recordings[i].media_shortcuts.transcript.data.download_url
```

This is a **presigned S3 URL** that expires within ~30 minutes. Stack Hub
follows it with a no-auth GET (the AWS signature is in the URL itself) and
parses the JSON file Recall has uploaded.

The JSON shape Recall produces (`diarized-processed1.1.json`):

```json
[
  {
    "participant": {"id": 100, "name": "Ratul Sikder", "is_host": true},
    "words": [
      {"text": "Hi",       "start_timestamp": {"relative": 10.7, ...}},
      {"text": "everyone", "start_timestamp": {"relative": 11.0, ...}}
    ],
    "language_code": "en"
  },
  ...
]
```

`_format_transcript` collapses this into the `Speaker: text` lines the
brief composer expects, joining adjacent same-speaker utterances.

> **Legacy endpoint warning:** `GET /bot/{id}/transcript/` is hard-deprecated
> and now returns HTTP 400 with `"This is a legacy endpoint, please use the
> updated endpoint here instead"`. Stack Hub no longer attempts it. A small
> fallback for `bot.recordings[i].transcript` (older inline shape) is kept
> for safety, but the primary path is the S3 download.

---

## 8. HTTP API

All routes require a logged-in user (`Depends(require_user)`) unless the
deploy sets `AUTH_DISABLED=true`. All routes return 503 if `RECALL_API_KEY`
is unset, and 502 if the upstream Recall call raises `RecallError`.

| Method | Path | Body | Response | Notes |
|---|---|---|---|---|
| `POST` | `/api/meeting/bot` | `{"meeting_url": "...", "bot_name": "..."}` | `{"bot_id": "..."}` | Creates a bot. `meeting_url` must be a Zoom / Meet / Teams URL Recall accepts. |
| `GET` | `/api/meeting/bot/{bot_id}` | — | `BotStatusResponse` (state, raw codes, transcript_text, error) | Polled by the SPA every ~3s. Cheap on Recall's side; rate-limited at 300/min/workspace. |
| `DELETE` | `/api/meeting/bot/{bot_id}` | — | `{"bot_id": "...", "left": true}` | Best-effort. Idempotent — Recall accepts leave requests on already-left bots. |
| `POST` | `/api/meeting/parse` | `{"content": "...vtt/.srt/.txt..."}` | `TranscriptParseResponse` | Bypasses Recall entirely; ingests pasted captions for users without bot access. |

See [`scripts/pipeline/web/api.py`](../scripts/pipeline/web/api.py) for
full request/response models.

---

## 9. Cost model

Per 60-minute Bengali meeting with the default Deepgram + nova-3 setup:

| Line item | Provider | Approx | Notes |
|---|---|---|---|
| Bot-minute fee | Recall.ai | ~$0.50 | Charged regardless of transcription provider. |
| Transcription | Deepgram nova-3 streaming | ~$0.35 | ~$0.0058/audio-min. Free tier ($200 credit) covers ~575 hours. |
| Transcript storage | Recall.ai (S3) | $0 | Included; default retention is `forever`. |
| **Total** | | **~$0.85** | |

For English meetings, set `RECALL_TRANSCRIPTION_PROVIDER=meeting_captions`
(or unset it) — Zoom's native captions are routed through Recall at no
additional fee. Total drops to ~$0.50.

> **Rate limits.** Deepgram's free tier hits a soft cap around 25 concurrent
> connections; Recall's REST is 300 req/min per workspace. Stack Hub's
> ~3-second polling interval stays well under both even with multiple
> simultaneous bots.

---

## 10. Setup checklist

For a fresh Stack Hub instance:

1. **Sign up for Recall.ai** at https://www.recall.ai/. Note which AWS
   region the dashboard URL shows (`us-east-1`, `us-west-2`, `eu-central-1`,
   `ap-northeast-1`). The API token issued is locked to that region.
2. Copy the API key and put it in `.env`:
   ```
   RECALL_API_KEY=<40-char token>
   ```
3. If your workspace is **not** in `ap-northeast-1`, override the base URL:
   ```
   RECALL_BASE_URL=https://<your-region>.recall.ai/api/v1
   ```
4. (Optional, for non-English meetings) **Sign up for Deepgram** at
   https://deepgram.com. Pick "Speech to Text" during onboarding. Generate
   an API key. Then in the **Recall dashboard → Settings → Integrations →
   Deepgram**, paste the Deepgram key. Recall now has authority to call
   Deepgram on your behalf.
5. (Optional) Configure the transcription provider in `.env`:
   ```
   RECALL_TRANSCRIPTION_PROVIDER=deepgram_streaming
   RECALL_TRANSCRIPTION_LANGUAGE=bn
   RECALL_TRANSCRIPTION_MODEL=nova-3
   ```
6. Deploy. The compose stack picks up `.env` on `docker compose up -d`.

---

## 11. Operations

### Deployment

The image is built and pushed to GHCR by CI on merge to `main`. The
Lightsail box must `docker compose pull && docker compose up -d` to pick
up new images. See [`DEPLOYMENT.md`](DEPLOYMENT.md).

Code-only changes need a `pull`; env-only changes (e.g. swapping the
Deepgram model) only need an `up -d` so compose re-reads `.env`.

### Monitoring

Recall emits webhooks for every `status_change` (configurable per workspace),
and a structured ERROR log when a transcription provider fails:

```json
{
  "severity": "ERROR",
  "message": "Failed to connect to transcription provider deepgram: ...",
  "bot_id": "...",
  "timestamp": "..."
}
```

Stack Hub does not currently consume Recall webhooks — it polls. Adding a
webhook receiver (`POST /api/webhooks/recall`) with Svix signature
verification is tracked as a future enhancement.

### Cost containment

Recall and Deepgram both expose per-day spend caps in their dashboards.
Set them. Bots that fail to leave gracefully (process crash, OS reboot)
keep accruing bot-minutes — `automatic_leave` in the bot creation payload
mitigates this.

---

## 12. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `POST /api/meeting/bot` → 503, detail mentions `RECALL_API_KEY` | Env var missing on the deployed box. | Add `RECALL_API_KEY=...` to `.env` and `docker compose up -d`. |
| `POST /api/meeting/bot` → 502, detail `recall.ai POST /bot/ -> 401: ...wrong region...` | API key is for a different Recall region than `RECALL_BASE_URL`. | Verify which region the Recall dashboard URL shows. Set `RECALL_BASE_URL` (or change the workspace) to match. |
| `POST /api/meeting/bot` → 502, detail `transcription_options...This field is not allowed` | Running an old image; the deprecated payload shape is still being sent. | `docker compose pull && docker compose up -d`. |
| UI shows `Done` with status pill `call_ended` but transcript editor is empty | Old image, old state map mapping `call_ended → done`. | `docker compose pull`. The current code waits for `recording_done`. |
| Bot completes but transcript text contains nonsense English words for non-English audio (e.g. `"Staghabni"` for Bengali) | `RECALL_TRANSCRIPTION_PROVIDER=meeting_captions` was used for a non-English meeting. Zoom's native captions are English-only. | Switch to `deepgram_streaming` + the right language code. See §10. |
| Recall log: `Failed to connect to transcription provider deepgram: ...Bad Request...` | Deepgram rejected the connection parameters. Almost always: the model doesn't support the language. | Bengali requires `nova-3` (not `nova-2`). Hindi works on `nova-2`. Check Deepgram's language matrix at https://developers.deepgram.com/docs/models-languages-overview. |
| Recall log: `Deepgram is not configured for this workspace` | Deepgram API key was added to your Deepgram account but never pasted into the **Recall** dashboard. | Recall dashboard → Settings → Integrations → Deepgram → paste the key. |
| Bot stuck in `joining_call` indefinitely | Host has not admitted the bot from the waiting room, OR Zoom requires a registration link. | Have the host admit the bot. For Zoom registration-required meetings, paste the *registration-confirmed* URL, not the public registration page. |

---

## 13. References

- Recall.ai docs: https://docs.recall.ai/
- Recall bot create reference: https://docs.recall.ai/reference/bot_create
- Recall transcript retrieve reference: https://docs.recall.ai/reference/transcript_retrieve
- Deepgram language + model matrix: https://developers.deepgram.com/docs/models-languages-overview
- Source: [`scripts/pipeline/recall.py`](../scripts/pipeline/recall.py)
- Tests: [`tests/test_recall.py`](../tests/test_recall.py)
