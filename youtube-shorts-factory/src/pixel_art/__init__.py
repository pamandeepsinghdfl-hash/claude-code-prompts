"""Pixel-art Shorts pipeline (replaces the podcast-sourcing pipeline).

Six modules:
  - story_writer    -> LLM generates a cozy short scene prompt + caption
  - image_generator -> Pollinations.ai (free) -> AI pixel-art still
  - animator        -> ffmpeg parallax + Ken Burns + ambient particles
  - music_picker    -> picks a random CC0 lofi track from data/music/
  - renderer        -> stitches it all together with caption + watermark
  - factory_pixel   -> top-level orchestrator (called by main.py / scheduler)
"""
