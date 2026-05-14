# Daily Decoded — channel setup sheet

Copy/paste this into YouTube Studio → Customization while setting up the channel.

## Identity

- **Channel name**: `Daily Decoded`
- **Handle**: `@dailydecoded`  *(check availability at https://youtube.com/@dailydecoded before claiming)*
- **Country**: United States  *(or wherever you're optimizing the algorithm cohort for; "Global" channels typically pick US for the largest English-speaking pool)*
- **Default language**: English
- **Made for kids**: **No**

## Profile picture

`data/brand/logo.png` → upload as channel profile picture (YouTube auto-crops to circle; the design is circle-safe).

## Banner

`data/brand/banner.png` (2560×1440) → upload as channel banner. Safe-zone text is centered so it'll render correctly on TV, desktop, and mobile.

## Description (paste verbatim into "About → Description")

The world's most interesting moments — translated to English so everyone can watch.

Daily Decoded is a daily Shorts channel that finds the best 60-second moments from podcasts, interviews, news, and viral clips across India, Brazil, Indonesia, the Middle East, Japan, Korea, Latin America, and beyond — and adds bold English captions so the language never gets in the way.

🌍 6 new Shorts every single day
🕒 04:00 · 08:00 · 12:00 · 16:00 · 20:00 · 00:00 UTC
✏️ Always with crystal-clear English captions
🎙️ Always crediting the original creator

If a moment moves a million people in another language, it can move a million more in English. We're the bridge.

Subscribe for one daily series — six Shorts that tell one bigger story.

## Channel keywords (paste into "Basic info → Keywords", comma-separated)

shorts, viral shorts, english captions, translated podcast, world news shorts, motivation shorts, mind blowing facts, inspiring stories, viral interviews, global content

## Default upload settings

YouTube Studio → Settings → Upload defaults:

- **Title**: *(leave empty — the factory generates titles)*
- **Description**: *(leave empty — the factory injects the full description per Short)*
- **Tags**: `shorts, viral, motivation, world, podcast`
- **Visibility**: Private  *(the factory uses publishAt to schedule; visibility flips automatically)*
- **Category**: People & Blogs
- **License**: Standard YouTube License
- **Allow embedding**: Yes
- **Publish to subscriptions feed and notify subscribers**: Yes
- **Comments**: On, hold potentially inappropriate comments for review
- **Show how many people like / dislike**: Yes
- **Language**: English (United States)

## Verification

Go to https://youtube.com/verify → phone verification. This unlocks custom thumbnails (the factory generates one per Short — without verification YouTube ignores them).

## Comment moderation (Tactic 4 dependency)

YouTube Studio → Settings → Community → Defaults:

- **Hold for review**: "Potentially inappropriate comments"
- **Blocked words**: add any niche-specific spam terms
- **Approved users**: leave default

The factory pins a hook question as the first comment (`post_pinned_question` in `youtube_uploader.py`). Make sure the channel allows comments — Studio → Settings → Channel → Advanced → Comments: **Allow all comments**.

## Cross-platform handle grabs (do these the same day)

```
https://x.com/dailydecoded
https://instagram.com/dailydecoded
https://tiktok.com/@dailydecoded
https://threads.net/@dailydecoded
```

Lock all four immediately even if you don't post yet. Squatters watch new YouTube channels for unclaimed handles.

## Channel art credit (optional metadata)

In channel description (bottom), add:
```
Branding: Daily Decoded design team
Engine: Daily Decoded production pipeline
```

Don't mention "automation" or "AI-generated" in the public description — YouTube doesn't penalize it, but human viewers do.
