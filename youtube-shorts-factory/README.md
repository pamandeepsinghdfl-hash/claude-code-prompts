# Global YouTube Shorts Factory

Production-ready Python pipeline that runs **every day at 00:00 UTC**, sources
trending content from the **entire world** (last 7 days), and publishes
**exactly 4 vertical Shorts** with **mandatory bold English captions** —
even when the source audio is Hindi, Spanish, Arabic, Japanese, Portuguese,
Korean, etc.

It is **copyright-first**: every candidate is scored for licensing risk before
download, and the system falls back to a 100% original public-domain pipeline
(global myths + AI voice + stock footage) when nothing safe is available.

## Highlights

- **Global sourcing** — YouTube Data API v3 across 15 region codes (US, IN, BR,
  ID, MX, JP, KR, SA, GB, DE, FR, NG, PH, EG, TR) + niche-keyword search with
  the Creative-Commons license filter.
- **Viral scoring** — view count + engagement velocity + cross-cultural
  appearance + LLM hook strength.
- **Multilingual transcription** — `faster-whisper` `large-v3` with word-level
  timestamps and language auto-detection.
- **Always-English captions** — DeepL (if configured) or LLM translation,
  rendered as TikTok-style **karaoke ASS subtitles** burnt into the video.
- **Viral moment detection** — LLM picks the best 18–60s window from the
  transcript and writes the hook.
- **Vertical 1080×1920 render** — ffmpeg pipeline with Ken Burns zoom,
  royalty-free music mix, optional watermark.
- **Pillow thumbnails** with big bold English title overlay.
- **Resumable upload** via YouTube Data API v3 with `publishAt` scheduling
  (so 4 Shorts auto-publish at 06:00 / 12:00 / 18:00 / 00:00 UTC).
- **APScheduler** daemon (or one-shot mode for cron / GitHub Actions / Render).
- **SQLite dedupe DB** prevents re-publishing the same source within N days.
- **Full fallback** — public-domain global stories + edge-tts narration + CC0
  stock footage from Pixabay.

## Folder structure

```
youtube-shorts-factory/
├── main.py                       # One-shot CLI: run the factory immediately
├── scheduler.py                  # APScheduler daemon (00:00 UTC daily)
├── config.yaml                   # All tunables (niches, regions, captions, ...)
├── .env.example                  # Copy → .env, fill in API keys
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .github/workflows/daily.yml   # GitHub Actions cron alternative
├── src/
│   ├── config.py                 # Pydantic config + secrets loader
│   ├── factory.py                # Top-level orchestrator
│   ├── sourcing/
│   │   ├── youtube_api.py        # Trending + search per region
│   │   ├── viral_scorer.py       # View / engagement / cross-cultural / hook
│   │   └── copyright_check.py    # 0–100 safety score
│   ├── download/downloader.py    # yt-dlp wrapper (full / segment / audio-only)
│   ├── transcription/
│   │   ├── whisper_transcriber.py# faster-whisper + word timestamps
│   │   └── translator.py         # DeepL → LLM fallback (always to English)
│   ├── analysis/
│   │   ├── llm_client.py         # Groq / OpenAI / Anthropic failover
│   │   └── viral_detector.py     # LLM moment picker + title/summary writer
│   ├── video/
│   │   ├── captions.py           # ASS karaoke caption writer
│   │   ├── editor.py             # ffmpeg 9:16 render with burnt-in captions
│   │   └── thumbnail.py          # Pillow vertical thumbnail
│   ├── upload/youtube_uploader.py# OAuth 2 resumable upload + publishAt
│   ├── fallback/public_domain.py # Stories + AI voice + stock footage path
│   └── utils/
│       ├── logger.py             # Daily logs + JSON run report
│       └── db.py                 # SQLAlchemy dedupe + history
├── data/
│   ├── public_domain_stories.json
│   ├── fonts/                    # Drop Montserrat-Black.ttf here
│   ├── music/                    # Royalty-free background tracks
│   └── stock_footage/            # Optional local fallback footage
├── output/
│   ├── shorts/                   # Final MP4s
│   ├── thumbnails/               # JPGs
│   └── workdir/                  # Intermediate (auto-cleaned)
├── logs/
│   └── YYYY-MM-DD/factory.log + report.json
└── credentials/
    ├── client_secret.json        # OAuth client (NOT committed)
    └── token.json                # Generated on first auth (NOT committed)
```

## Quick start (local)

```bash
cd youtube-shorts-factory

# 1. Python deps (Python 3.11 recommended)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. System deps
sudo apt-get install -y ffmpeg libsndfile1 fontconfig

# 3. Fonts (Montserrat Black)
curl -L https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-Black.ttf \
     -o data/fonts/Montserrat-Black.ttf

# 4. Configure
cp .env.example .env          # fill in YOUTUBE_API_KEY + at least one LLM key
# Put your OAuth client_secret.json in credentials/
# (Google Cloud Console → APIs & Services → Credentials → Desktop app)

# 5. Dry-run once (builds 4 videos, does NOT upload)
python main.py --dry-run

# 6. Real run (will open browser on first auth, then upload + schedule)
python main.py

# 7. Daemonise — runs every day at 00:00 UTC
python scheduler.py
```

The first `python main.py` will open a browser to authorize your YouTube
account. The token is saved to `credentials/token.json` and reused after.

## Configuration tour

`config.yaml` is your only knob:

- `schedule.shorts_per_day` — exactly **4** by default.
- `schedule.publish_slots_utc` — 4 evenly-spaced slots. Edit to taste.
- `niches` — rotated round-robin across slots.
- `sourcing.region_codes` — all 15 by default; add or remove regions.
- `sourcing.source_languages` — Whisper handles all; this filter only
  excludes when YouTube has tagged a language.
- `copyright.min_safety_score` — raise to 80 for max safety; lower
  values give the LLM more candidate variety.
- `viral.weight_*` — tune the scoring weights.
- `captions.style` — font, size, stroke, highlight colour. The default
  is bold white text with a 6 px black stroke, yellow word highlights,
  and 80 px safe margin so YouTube's UI doesn't cover anything.
- `metadata.description_template` — controls what every description
  contains (source URL, timestamp range, creator credit, summary,
  hashtags, CTA).

## API keys you need

| Service         | What it does                              | Required?                |
|-----------------|-------------------------------------------|--------------------------|
| YouTube Data v3 | Sourcing + upload                          | **Yes**                  |
| OAuth 2 client  | Upload as you                              | **Yes**                  |
| Groq            | Fast/cheap viral analysis + translation    | One of these LLMs is required |
| OpenAI          | Fallback LLM                               | Optional                 |
| Anthropic       | Fallback LLM                               | Optional                 |
| DeepL           | Higher-quality translation                 | Optional                 |
| Pixabay         | CC0 stock footage for fallback path        | Optional                 |

## Deployment

### Docker (recommended)

```bash
docker compose up -d --build
docker logs -f shorts-factory
```

The compose file mounts:
- `credentials/` — keeps OAuth tokens persistent across container restarts.
- `data/` — fonts + music live with the host, not the image.
- `output/` + `logs/` — so you can audit and back up artefacts.

> First-time auth is interactive. Run `docker compose run --rm shorts-factory
> python main.py --dry-run` once to complete the browser flow, then start the
> daemon. (On a headless server you can pre-generate `token.json` locally and
> mount it.)

### VPS / bare metal (systemd)

```ini
# /etc/systemd/system/shorts-factory.service
[Unit]
Description=Global YouTube Shorts Factory
After=network-online.target

[Service]
Type=simple
User=shorts
WorkingDirectory=/opt/youtube-shorts-factory
EnvironmentFile=/opt/youtube-shorts-factory/.env
ExecStart=/opt/youtube-shorts-factory/.venv/bin/python scheduler.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
sudo timedatectl set-timezone UTC
sudo systemctl enable --now shorts-factory
journalctl -u shorts-factory -f
```

### Render.com

1. New **Background Worker** → connect this repo.
2. Build command: `pip install -r youtube-shorts-factory/requirements.txt`.
3. Start command: `cd youtube-shorts-factory && python scheduler.py`.
4. Add all env vars from `.env.example`.
5. Set timezone to **UTC** in the service's settings.

### GitHub Actions (zero-server option)

`.github/workflows/daily.yml` runs the factory at 00:00 UTC on the shared
runners. You'll need to:

1. Add repo secrets (`YOUTUBE_API_KEY`, `GROQ_API_KEY`, etc.).
2. Add **`YT_OAUTH_CLIENT_SECRET_JSON`** and **`YT_OAUTH_TOKEN_JSON`** —
   the full contents of `credentials/client_secret.json` and
   `credentials/token.json` (generate the token locally first).
3. Re-trigger via `workflow_dispatch` to test before relying on the cron.

> GitHub-hosted runners have no GPU, so Whisper will use CPU. For
> reliability, pin `WHISPER_MODEL=small` or `medium` in repo variables.

### Cron (simplest)

```cron
0 0 * * * cd /opt/youtube-shorts-factory && /opt/youtube-shorts-factory/.venv/bin/python scheduler.py --once >> /var/log/shorts-factory.log 2>&1
```

## Best practices for staying copyright-safe while going global

1. **Prefer CC-licensed sources.** Sourcing filters with `videoLicense=creativeCommon`
   first. Anything else gets a heavy safety penalty.
2. **Lean on government, museum, and public-broadcaster channels** (NASA, VOA,
   .gov, UN, Library of Congress, Smithsonian, Internet Archive). Their
   uploads are explicitly free to remix.
3. **Stay transformative.** Always:
   - Crop to 9:16 (changes the visual frame).
   - Add **bold English captions** (already mandatory).
   - Re-time / re-pace with Ken Burns + cuts.
   - Add a small intro/outro card or branded watermark.
4. **Keep clips short (≤60 s).** Short, commentary-style clips with caption
   overlays are far more likely to qualify as fair use than wholesale re-uploads.
5. **Credit creators in every description.** The default
   `description_template` includes channel name, country, language, and the
   original URL with a precise timestamp range.
6. **Avoid licensed music** in the source clip. Background music in
   `data/music/` must be royalty-free (Pixabay, YouTube Audio Library,
   Free Music Archive CC0).
7. **Hard-block risky publishers.** `RISKY_CHANNEL_SUBSTRINGS` in
   `src/sourcing/copyright_check.py` excludes record labels (Vevo, Warner,
   Sony, UMG), studios (Disney, Marvel, HBO, Netflix), and major sports
   leagues (NBA, NFL, UFC, WWE, Premier League).
8. **Use the fallback liberally.** If `copyright.min_safety_score` filters
   everything out, the factory ships a fully original public-domain story
   instead — there is no penalty for using it.
9. **Throttle volume to 4/day.** This is well inside what manual creators
   produce and below the threshold for "spam-style" repetition.
10. **Never disable dedupe.** The 60-day window in `persistence.dedupe_window_days`
    is your firewall against accidental repeated uploads.

If you receive a ContentID claim:
- Inspect `logs/YYYY-MM-DD/report.json` to find which source it came from.
- Add the offending publisher to `RISKY_CHANNEL_SUBSTRINGS`.
- Bump `copyright.min_safety_score`.
- Consider disputing only if your edit is clearly transformative — otherwise
  let the claim stand.

## Run report

Every run writes `logs/YYYY-MM-DD/report.json`:

```json
{
  "started_at": "2026-05-14T00:00:00Z",
  "finished_at": "2026-05-14T00:42:18Z",
  "shorts_count": 4,
  "shorts": [
    {
      "niche": "viral_interviews_podcasts",
      "publish_at": "2026-05-14T06:00:00+00:00",
      "source_url": "https://www.youtube.com/watch?v=...",
      "source_creator": "...",
      "source_country_region": "IN",
      "source_language": "hi",
      "clip_start_s": 1245.0,
      "clip_end_s": 1287.5,
      "title": "🔥 This Hindi Interview Just Broke the Internet",
      "viral_score": 81.4,
      "copyright_score": 60,
      "video_path": "output/shorts/...mp4",
      "youtube_video_id": "abc123",
      "is_fallback": false
    }
  ],
  "errors": []
}
```

## Troubleshooting

- **OAuth fails on a headless server** — run `python main.py --dry-run`
  locally to generate `credentials/token.json`, then copy it to the server.
- **`Could not find Montserrat-Black.ttf`** — see `data/fonts/README.md`.
- **Captions are too small/big** — tune `captions.style.font_size` and
  `safe_margin_px` in `config.yaml`.
- **Whisper OOM** — set `WHISPER_MODEL=small` and `WHISPER_COMPUTE_TYPE=int8`.
- **YouTube quota exceeded** — sourcing reduces by lowering
  `sourcing.region_codes` or `sourcing.max_candidates_per_region`.
- **No safe candidates found** — the public-domain fallback runs
  automatically; check `report.json` to confirm.

## License

MIT — but the videos you ship are yours to keep / lose / monetize. The factory
is just the assembly line.
