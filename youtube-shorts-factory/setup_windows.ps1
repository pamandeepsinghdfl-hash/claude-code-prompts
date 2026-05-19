# Pixel Hours Factory — One-click Windows setup
#
# Run this from PowerShell INSIDE the extracted project folder:
#   .\setup_windows.ps1
#
# What it does:
#   1. Checks for Python 3.11+ and ffmpeg; tells you how to install if missing
#   2. Creates a Python virtual environment (.venv) and installs all deps
#   3. Downloads the Montserrat-Black caption font into data/fonts/
#   4. Re-generates the brand assets with the real font
#   5. Creates a fresh .env from .env.example if you don't have one
#   6. Creates the credentials/, logs/, output/ folders
#   7. Validates the entire setup and prints what to do next
#
# Re-running this script is safe — it skips any step that's already done.

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

function Write-Step($n, $msg) {
    Write-Host ""
    Write-Host "[$n] $msg" -ForegroundColor Cyan
}

function Write-Ok($msg)   { Write-Host "  OK  $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  !!  $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "  XX  $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "========================================================" -ForegroundColor Magenta
Write-Host "   Pixel Hours Factory - Windows Setup" -ForegroundColor Magenta
Write-Host "========================================================" -ForegroundColor Magenta

# ─── 1. Check Python ─────────────────────────────────────────────────────
Write-Step 1 "Checking Python 3.11+"
$pythonOk = $false
foreach ($exe in @("python", "python3", "py")) {
    try {
        $ver = & $exe --version 2>&1
        if ($ver -match "Python 3\.(11|12)\.") {
            Write-Ok "Found $ver at: $((Get-Command $exe).Source)"
            $script:PY = $exe
            $pythonOk = $true
            break
        }
    } catch {}
}
if (-not $pythonOk) {
    Write-Fail "Python 3.11 or 3.12 is required."
    Write-Host ""
    Write-Host "  Install one of:" -ForegroundColor Yellow
    Write-Host "    winget install Python.Python.3.11" -ForegroundColor Yellow
    Write-Host "  OR download from https://python.org/downloads/" -ForegroundColor Yellow
    Write-Host "    (tick 'Add Python to PATH' during install)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Then close + reopen PowerShell and re-run this script." -ForegroundColor Yellow
    exit 1
}

# ─── 2. Check ffmpeg ─────────────────────────────────────────────────────
Write-Step 2 "Checking ffmpeg"
try {
    $ffmpeg = & ffmpeg -version 2>&1 | Select-Object -First 1
    Write-Ok "Found: $ffmpeg"
} catch {
    Write-Fail "ffmpeg is required for video rendering."
    Write-Host ""
    Write-Host "  Install with:" -ForegroundColor Yellow
    Write-Host "    winget install Gyan.FFmpeg" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Close + reopen PowerShell so PATH refreshes, then re-run this script." -ForegroundColor Yellow
    exit 1
}

# ─── 3. Virtual environment ──────────────────────────────────────────────
Write-Step 3 "Setting up Python virtual environment (.venv)"
if (Test-Path ".venv") {
    Write-Ok ".venv already exists (skipping)"
} else {
    & $PY -m venv .venv
    Write-Ok ".venv created"
}

# Activate for this session
$activate = ".\.venv\Scripts\Activate.ps1"
if (-not (Test-Path $activate)) {
    Write-Fail "Activate script not found at $activate"
    exit 1
}
# Soften execution policy if needed
try {
    & $activate
    Write-Ok "venv activated"
} catch {
    Write-Warn "PowerShell execution policy is blocking .ps1 scripts."
    Write-Host "  Fix once with:" -ForegroundColor Yellow
    Write-Host "    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned" -ForegroundColor Yellow
    Write-Host "  Then re-run this script." -ForegroundColor Yellow
    exit 1
}

# ─── 4. Install dependencies ─────────────────────────────────────────────
Write-Step 4 "Installing Python dependencies (this can take 5-10 min)"
& python -m pip install --upgrade pip --quiet
& pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Fail "pip install failed. Scroll up for the error and paste it to Claude."
    exit 1
}
Write-Ok "All dependencies installed"

# ─── 5. Download Montserrat-Black caption font ───────────────────────────
Write-Step 5 "Downloading Montserrat-Black caption font"
$fontPath = "data\fonts\Montserrat-Black.ttf"
if (Test-Path $fontPath) {
    Write-Ok "Font already exists at $fontPath (skipping)"
} else {
    $url = "https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-Black.ttf"
    try {
        Invoke-WebRequest -Uri $url -OutFile $fontPath -UseBasicParsing
        Write-Ok "Downloaded $fontPath"
    } catch {
        Write-Warn "Couldn't download font. Get it manually from:"
        Write-Host "    https://fonts.google.com/specimen/Montserrat" -ForegroundColor Yellow
        Write-Host "    Drop Montserrat-Black.ttf into data\fonts\" -ForegroundColor Yellow
    }
}

# ─── 6. Regenerate brand assets with the real font ───────────────────────
Write-Step 6 "Regenerating brand assets (logo + banner) with Montserrat"
if (Test-Path $fontPath) {
    & python scripts\generate_brand.py
    Write-Ok "Brand assets in data\brand\ are now production-grade"
} else {
    Write-Warn "Skipped — Montserrat-Black.ttf is missing"
}

# ─── 7. Create folders the factory needs at runtime ──────────────────────
Write-Step 7 "Creating runtime folders"
foreach ($d in @("credentials", "logs", "output\shorts", "output\thumbnails", "output\workdir", "data\music", "data\stock_footage")) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Force -Path $d | Out-Null
        Write-Ok "Created $d"
    }
}

# ─── 8. Create .env if missing ───────────────────────────────────────────
Write-Step 8 "Setting up .env"
if (Test-Path ".env") {
    Write-Ok ".env already exists (preserving your keys)"
} else {
    Copy-Item ".env.example" ".env"
    Write-Ok "Created .env from .env.example"
}

# Recommend small Whisper for first dry-run
$envContent = Get-Content ".env" -Raw
if ($envContent -match "WHISPER_MODEL=large-v3" -and -not ($envContent -match "WHISPER_MODEL=small")) {
    Write-Warn "Tip: edit .env and set WHISPER_MODEL=small + WHISPER_COMPUTE_TYPE=int8 for a fast first dry-run on CPU."
}

# ─── 9. Validate ─────────────────────────────────────────────────────────
Write-Step 9 "Validating Python imports"
& python -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8')) for p in pathlib.Path('src').rglob('*.py')]; print('all src/ files parse OK')"
& python -c "import yaml; yaml.safe_load(open('config.yaml', encoding='utf-8')); print('config.yaml is valid YAML')"

# ─── Done ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "   Setup complete!" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps (read carefully):" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Open .env in Notepad and fill in:"
Write-Host "       YOUTUBE_API_KEY=<your YouTube Data API v3 key>"
Write-Host "       GROQ_API_KEY=<your Groq key from console.groq.com>"
Write-Host ""
Write-Host "  2. Drop credentials\client_secret.json into the project."
Write-Host "     Get it from Google Cloud Console -> APIs -> Credentials"
Write-Host "     -> OAuth 2.0 Client (Desktop app) -> Download JSON"
Write-Host ""
Write-Host "  3. (Optional) Drop royalty-free MP3s into data\music\"
Write-Host ""
Write-Host "  4. Do a dry-run:"
Write-Host "       .\.venv\Scripts\Activate.ps1"
Write-Host "       python main.py --dry-run"
Write-Host ""
Write-Host "  5. Check the output:"
Write-Host "       explorer output\shorts"
Write-Host ""
Write-Host "  6. Real run (uploads + schedules to Pixel Hours):"
Write-Host "       python main.py"
Write-Host ""
Write-Host "  When stuck, paste any error in chat and Claude will help." -ForegroundColor Yellow
Write-Host ""
