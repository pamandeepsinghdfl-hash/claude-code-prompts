"""AI pixel-art image generator.

Cheap tier ($0/img): Pollinations.ai — free, no auth, no rate limits on
residential IPs. We append a strong pixel-art style suffix to every prompt
so the model lands in the right aesthetic.

Fallback chain (in order):
  1. Pollinations.ai with flux model      (free, decent pixel art)
  2. Pollinations.ai with turbo model     (free, faster, lower quality)
  3. Stability AI public endpoint         (if STABILITY_API_KEY set)
  4. Local procedural fallback            (PIL; matches what the prototype renders)

Returns: PIL Image at the requested resolution.
"""
from __future__ import annotations

import io
import logging
import os
import urllib.parse
from pathlib import Path
from typing import Optional

import httpx
from PIL import Image

log = logging.getLogger("pixel.image_gen")


STYLE_SUFFIX = (
    ", pixel art, 16-bit, detailed pixelart, SNES style, cozy lofi aesthetic, "
    "warm interior lighting, atmospheric, vertical composition"
)


class ImageGenerator:
    def __init__(self, width: int = 1080, height: int = 1920, timeout_s: int = 90):
        self.width = width
        self.height = height
        self.timeout_s = timeout_s
        self.stability_key = os.getenv("STABILITY_API_KEY")

    def generate(self, prompt: str, *, seed: Optional[int] = None,
                 save_to: Optional[Path] = None) -> Image.Image:
        full = prompt + STYLE_SUFFIX

        for attempt in (
            self._pollinations_flux,
            self._pollinations_turbo,
            self._stability,
            self._procedural_fallback,
        ):
            try:
                img = attempt(full, seed=seed)
                if img is not None:
                    if save_to:
                        save_to.parent.mkdir(parents=True, exist_ok=True)
                        img.save(save_to)
                    return img
            except Exception as e:  # noqa: BLE001
                log.warning("Image-gen attempt %s failed: %s", attempt.__name__, e)
                continue
        raise RuntimeError("All image-gen providers failed")

    # ─── Pollinations ────────────────────────────────────────────────────
    def _pollinations(self, prompt: str, *, seed: Optional[int], model: str) -> Optional[Image.Image]:
        encoded = urllib.parse.quote(prompt, safe="")
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width={self.width}&height={self.height}&nologo=true&model={model}"
        )
        if seed is not None:
            url += f"&seed={seed}"
        r = httpx.get(url, timeout=self.timeout_s, follow_redirects=True)
        if r.status_code != 200:
            log.info("Pollinations %s returned %d", model, r.status_code)
            return None
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        if img.size != (self.width, self.height):
            img = img.resize((self.width, self.height), Image.LANCZOS)
        return img

    def _pollinations_flux(self, prompt: str, *, seed: Optional[int]) -> Optional[Image.Image]:
        return self._pollinations(prompt, seed=seed, model="flux")

    def _pollinations_turbo(self, prompt: str, *, seed: Optional[int]) -> Optional[Image.Image]:
        return self._pollinations(prompt, seed=seed, model="turbo")

    # ─── Stability ───────────────────────────────────────────────────────
    def _stability(self, prompt: str, *, seed: Optional[int]) -> Optional[Image.Image]:
        if not self.stability_key:
            return None
        r = httpx.post(
            "https://api.stability.ai/v2beta/stable-image/generate/core",
            headers={
                "Authorization": f"Bearer {self.stability_key}",
                "Accept": "image/*",
            },
            files={"none": ""},
            data={
                "prompt": prompt,
                "aspect_ratio": "9:16",
                "output_format": "png",
                "seed": str(seed) if seed is not None else "0",
            },
            timeout=self.timeout_s,
        )
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB").resize(
            (self.width, self.height), Image.LANCZOS
        )

    # ─── Last-resort procedural ──────────────────────────────────────────
    def _procedural_fallback(self, prompt: str, *, seed: Optional[int]) -> Image.Image:
        """When everything else fails — use the prototype's procedural scene.

        Not pretty but lets the factory complete a run instead of crashing.
        """
        log.warning("Falling back to procedural pixel art for prompt: %s", prompt[:60])
        from PIL import ImageDraw, ImageFilter
        import random as _rand
        rng = _rand.Random(seed or hash(prompt) & 0xFFFFFFFF)

        sw, sh = 180, 320
        img = Image.new("RGB", (sw, sh), (30, 35, 50))
        d = ImageDraw.Draw(img)
        # Sky / window
        d.rectangle((40, 30, 140, 150), fill=(26, 37, 64))
        for _ in range(15):
            x = rng.randint(42, 138)
            y = rng.randint(80, 145)
            d.rectangle((x, y, x + 1, y + 1), fill=(164, 196, 255))
        # Floor + bed
        d.rectangle((0, 250, sw, sh), fill=(26, 29, 46))
        d.rectangle((10, 220, sw - 10, 290), fill=(42, 47, 74))
        # Soft warm glow
        glow = Image.new("RGB", (sw, sh), (0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse((-30, 30, 100, 200), fill=(80, 50, 0))
        glow = glow.filter(ImageFilter.GaussianBlur(20))
        img = Image.blend(img, glow, 0.2)
        return img.resize((self.width, self.height), Image.NEAREST)
