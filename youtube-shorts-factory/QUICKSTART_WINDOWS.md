# Pixel Hours Factory — Windows quick-start

Everything you need to go from "downloaded the zip" to "Shorts auto-uploading
to YouTube," in order.

## Prerequisites (install once, ~5 min)

Open **PowerShell as Administrator** and run:

```powershell
winget install Python.Python.3.11
winget install Gyan.FFmpeg
```

Close PowerShell completely, then open a **new** PowerShell window so PATH refreshes.

Verify:
```powershell
python --version    # Python 3.11.x
ffmpeg -version     # ffmpeg version 6.x or newer
```

## Setup (one command, ~10 min)

In the same PowerShell window, navigate to wherever you extracted the zip:

```powershell
cd C:\Users\<you>\code\youtube-shorts-factory
.\setup_windows.ps1
```

If you see "running scripts is disabled," run this once and try again:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

The script will:
1. Confirm Python + ffmpeg are installed
2. Create `.venv\` and install all Python packages (~2 GB download)
3. Download Montserrat-Black.ttf into `data\fonts\`
4. Regenerate brand logo + banner using the real font
5. Create the `.env` file (you'll edit it in the next step)
6. Validate the whole project

## Get your 3 API keys (~15 min)

### Key 1 — YouTube Data API v3 (sourcing trending videos)

1. Sign into Google as `pixelhours@gmail.com` (your new brand account)
2. Go to https://console.cloud.google.com/
3. Top bar → "Select a project" → **New project** → name it `pixel-hours` → Create
4. Wait for the project to be selected (top bar)
5. https://console.cloud.google.com/apis/library/youtube.googleapis.com → **Enable**
6. Left menu → **APIs & Services** → **Credentials**
7. **+ Create credentials** → **API key** → copy the key (starts with `AIza...`)
8. Click **Restrict key** → "API restrictions" → tick **YouTube Data API v3** → Save

### Key 2 — OAuth 2.0 Client (uploading to your channel)

Still in https://console.cloud.google.com/apis/credentials:

1. **+ Create credentials** → **OAuth client ID**
2. If asked, configure consent screen first:
   - **User Type**: External → Create
   - **App name**: Pixel Hours Factory
   - **Support / developer email**: your `pixelhours@gmail.com`
   - Save & continue → leave scopes default → Save & continue
   - **Test users** → **+ Add Users** → `pixelhours@gmail.com` → Save & continue
3. Back to Create credentials → **OAuth client ID**:
   - **Application type**: **Desktop app** (NOT Web app)
   - Name: `pixel-hours-desktop`
   - Create → **Download JSON**
4. Rename the downloaded file to `client_secret.json`
5. Move it into `youtube-shorts-factory\credentials\client_secret.json`

### Key 3 — Groq (free LLM for hook detection)

1. https://console.groq.com/ → sign up
2. Left sidebar → **API Keys** → **Create API key**
3. Copy it (starts with `gsk_...`)

## Fill in `.env` (~2 min)

Open `.env` in Notepad:

```powershell
notepad .env
```

Set only these lines:

```
YOUTUBE_API_KEY=AIza...your_youtube_key...
GROQ_API_KEY=gsk_...your_groq_key...
WHISPER_MODEL=small
WHISPER_COMPUTE_TYPE=int8
```

Leave everything else as defaults. Save + close.

## First dry-run (~20 min)

```powershell
.\.venv\Scripts\Activate.ps1
python main.py --dry-run
```

What happens:
1. Calls YouTube API to find trending videos across 15 regions
2. Picks the 6 best by viral + copyright score
3. Downloads audio
4. Transcribes with Whisper (slow part on CPU)
5. Asks Groq to pick the viral moment
6. Translates to English + renders 9:16 Shorts with captions
7. Writes outputs to `output\shorts\*.mp4`
8. **Does NOT upload anything**

After it finishes:
```powershell
explorer output\shorts
```
Open the MP4s and check:
- ✅ Vertical 9:16
- ✅ Bold English captions covering the entire clip
- ✅ Subscribe CTA appears around the 70% mark
- ✅ Sound is intact

Read the run report:
```powershell
type logs\$(Get-Date -Format yyyy-MM-dd)\report.json
```

## First real run (~30 min, opens browser)

```powershell
python main.py
```

The **first time** it tries to upload, it opens your browser:

1. Sign in with `pixelhours@gmail.com`
2. The "Choose an account" screen shows your personal channel AND
   the Pixel Hours brand channel — **pick Pixel Hours**
3. You'll see "Google hasn't verified this app" warning → click
   **Advanced** → **Go to Pixel Hours Factory (unsafe)** → Continue
4. Approve scopes
5. Browser shows "The authentication flow has completed"

The script auto-saves the OAuth token to `credentials\token.json`. After
this, no browser flow is ever needed again.

When the script finishes, go to https://studio.youtube.com → Content →
you should see 6 Shorts listed as **Scheduled** at 04/08/12/16/20/00 UTC.

## Daily automation

To have the factory run automatically every day at 00:00 UTC:

```powershell
python scheduler.py
```

Leave this running. It runs the full pipeline once a day. To run it as a
Windows service so it survives reboots, install NSSM:

```powershell
winget install NSSM.NSSM
nssm install PixelHours "C:\Users\$env:USERNAME\code\youtube-shorts-factory\.venv\Scripts\python.exe" "C:\Users\$env:USERNAME\code\youtube-shorts-factory\scheduler.py"
nssm start PixelHours
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `redirect_uri_mismatch` | OAuth client is Web app, must be Desktop app. Re-create. |
| `Access blocked: this app's request is invalid` | Add `pixelhours@gmail.com` as a test user in OAuth consent screen. |
| `quotaExceeded` | YouTube API quota hit. Drop to 4 Shorts/day in `config.yaml`. |
| `forbidden: youtubeSignupRequired` | The Google account you authorized has no YouTube channel yet. |
| `failedPrecondition` on thumbnail | Channel not verified at youtube.com/verify. |
| Whisper takes forever | Set `WHISPER_MODEL=small` and `WHISPER_COMPUTE_TYPE=int8` in `.env`. |
| `Could not find Montserrat-Black.ttf` | Re-run `setup_windows.ps1` or download manually to `data\fonts\`. |
| `ffmpeg: command not found` | Close & reopen PowerShell so PATH updates after `winget install`. |
| `pip install` fails on `faster-whisper` | Try `pip install faster-whisper==1.0.3 --no-binary ctranslate2` |

## File map (where things live on your PC)

```
youtube-shorts-factory\
├── setup_windows.ps1          ← THE ONE-CLICK INSTALLER
├── QUICKSTART_WINDOWS.md      ← This file
├── main.py                    ← Run the factory once: python main.py
├── scheduler.py               ← Run daily at 00:00 UTC: python scheduler.py
├── config.yaml                ← Tune the factory (niches, regions, captions)
├── .env                       ← API keys (create from .env.example)
├── credentials\
│   ├── client_secret.json     ← You drop this in from Google Cloud Console
│   └── token.json             ← Auto-generated on first OAuth
├── data\
│   ├── brand\                 ← Logo + banner (upload to YouTube)
│   ├── fonts\                 ← Montserrat-Black.ttf (auto-downloaded)
│   ├── music\                 ← Drop royalty-free MP3s here
│   └── stock_footage\         ← Optional CC0 footage
├── output\
│   ├── shorts\                ← Final MP4s
│   └── thumbnails\            ← Thumbnail JPGs
└── logs\
    └── YYYY-MM-DD\
        ├── factory.log        ← Full run log
        └── report.json        ← JSON summary of what got published
```

## What the factory does on a typical day

Once a day at 00:00 UTC, it:
1. Hits the YouTube API across 15 regions (US, IN, BR, ID, MX, JP, KR, SA, etc.)
2. Scores ~300-500 candidate videos for viral potential + copyright safety
3. Picks the top 6 (or falls back to public-domain stories if none are safe)
4. For each: downloads audio → transcribes → LLM picks the best 18-55s window
   → translates to English → re-downloads just that segment → renders 9:16
   with karaoke captions + subscribe CTA + loop-perfect ending → generates
   thumbnail → composes title with "PART N/6 -" prefix → uploads with publishAt
   schedule → pins a hook question as the first comment
5. Writes everything to `logs\YYYY-MM-DD\report.json`

The 6 Shorts then publish at 04/08/12/16/20/00 UTC.

## Cost per month (rough)

- YouTube Data API: free (default 10k units/day; you may need a quota increase
  for 6/day — request one at console.cloud.google.com)
- Groq: free tier covers ~100 LLM calls/day; you'll use ~30
- Anthropic Claude (optional, recommended): ~$5-15/mo if you switch
  `LLM_PROVIDER_ORDER=anthropic,groq,openai`
- Whisper: runs locally on your PC, free
- Storage: ~5 GB/month for raw downloads + outputs (auto-cleaned)
- Power: your PC needs to be on for the scheduler. Use a small VPS ($5/mo)
  if you want it on always.

Total: $0-25/month depending on LLM choice.
