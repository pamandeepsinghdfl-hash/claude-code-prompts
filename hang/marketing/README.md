# Hang — marketing assets

- `hang-marketing-trailer.mp4` — **the full marketing video** (72s, 9:16). Hook → 6
  vox-pop interview beats → real screen-recorded app demo → push-to-talk beat → CTA.
  Built from genuine footage throughout: the interview beats are animated HUD-style
  caption cards (styled in the app's own look), not fabricated human video, and the
  middle section is a real screen capture of the live app. See "Why not AI-generated
  street-interview footage?" below.
- `trailer_part1.html` / `trailer_part3.html` — source for the animated caption-card
  scenes (open in a browser to preview; these are what got screen-recorded to produce
  the trailer's non-demo segments).
- `hang-app-demo.mp4` — the raw app-only screen recording (tutorial → status →
  filters → radius → profile → push-to-talk), also used as the trailer's middle act.
- `street-interview-script.md` — shoot-ready vox-pop script + shot list, for a real
  film crew or a future AI-video pipeline (see below).
- `character-sheet-preview.png` / `hero-key-art-preview.png` — low-res thumbnails of
  AI-generated concept art. Full resolution lives in Canva:
  - Character sheet: https://www.canva.com/M/MAHZzqgaEp0
  - Hero key art: https://www.canva.com/M/MAHZzixtUCM

## Why not AI-generated street-interview footage?

Canva's AI video generator (Seedance) is wired up and could produce the actual
filmed-looking street interviews from `street-interview-script.md`, but it's gated
behind a paid Canva plan upgrade the account doesn't currently have — generating a
video there returns: "Switch to a paid Canva plan to create your video." Upgrading
costs real money, so that's a call for the account owner, not something to do
automatically. If/when that's upgraded, the script is already written in
production-ready shot form and can go straight into `create-video`.
