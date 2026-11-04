# Hang — marketing assets

- `hang-marketing-trailer.mp4` — **the full marketing video** (72s, 9:16, with real
  narration + ambient audio). Cold-open punchline → hook → 7 vox-pop interview beats
  → real screen-recorded app demo (narrated) → mid-roll CTA → push-to-talk beat → CTA
  closer. Built from genuine footage/audio throughout: the interview beats are
  animated HUD-style caption cards (styled in the app's own look, not fabricated
  human video), the narration is real synthesized speech (espeak-ng + mbrola,
  installed and run locally — not a human voice actor, not claimed to be one), and
  the middle section is a real screen capture of the live app. Structure follows
  concrete findings in `research-viral-format.md`. See "Why not AI-generated
  street-interview footage?" below for why it isn't filmed/AI-generated human footage.
- `trailer_part1.html` / `trailer_part3.html` — source for the animated caption-card
  scenes (open in a browser to preview; these are what got screen-recorded to produce
  the trailer's non-demo segments). Scene timings are driven by the narration audio
  durations, not arbitrary guesses.
- `hang-app-demo.mp4` — the raw app-only screen recording (tutorial → status →
  filters → radius → profile → push-to-talk), also used as the trailer's middle act.
- `research-viral-format.md` — sourced research on what actually makes short-form
  street-interview-style marketing videos retain viewers, with the specific changes
  made to this trailer as a result (cold open, caption-first framing, mid-roll CTA).
- `launch-pamphlet.md` — one-page printable flyer for handing out at an in-person
  launch/meetup event.
- `launch-social-captions.md` — ready-to-post launch captions for TikTok, Instagram
  Reels, X/Twitter, and a LinkedIn founder-story post.
- `press-kit-blurb.md` — elevator pitch, about blurb, and quick facts for press/partner
  outreach. No invented usage stats — the app hasn't launched yet.
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
