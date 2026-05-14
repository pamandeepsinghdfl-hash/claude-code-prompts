# ─── Global YouTube Shorts Factory — production image ───────────────────
# Use the slim Python base + add ffmpeg + libsndfile (for moviepy/whisper).
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=UTC

# System deps: ffmpeg for editing, libsndfile for audio, fonts for captions.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
        fontconfig \
        fonts-dejavu-core \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first to maximise layer cache.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy project.
COPY . .

# Bake in the Montserrat font (used by captions + thumbnail) if present.
# Operators should drop their own .ttf into data/fonts before building.
RUN mkdir -p data/fonts data/music data/stock_footage logs output/shorts output/thumbnails output/workdir credentials

# Default: run the scheduler. To run once, override CMD.
CMD ["python", "scheduler.py"]
