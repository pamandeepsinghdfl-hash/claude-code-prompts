# Theme refresh — what was researched, and what changed

Researched via web search (current as of Nov 2026), not invented. Most sources are
agency/vendor blogs with commercial interests — treated as directional, not proof.

## What was found

- **Dark mode as the default surface, not an inverted light theme.** Several sources
  say 2026 dark UIs get their own tuned palette rather than a straight color swap —
  specifically warmer, less flat near-blacks instead of stark `#000`-adjacent tones.
- **"Glassmorphism 2.0" / "Liquid Glass."** Translucency + blur is still prominent but
  more refined — more transparent panels, soft specular edge highlights, layered
  depth — used selectively rather than on every surface.
- **Gradients now carry branding weight.** Multiple sources describe gradients moving
  from background decoration into buttons, text, and interactive elements as a
  consistent brand signature, rather than one-off color choices per component.
- **Adaptive/warm neutral palettes** displacing stark backgrounds, alongside a
  counter-trend toward bolder "dopamine" saturation in places.
- **Kinetic typography** — subtle motion in text/branding, not just static gradient fills.
- One source's specific numeric claims (e.g. "gradients in ~40% of top apps") couldn't
  be verified and aren't relied on here.

## What actually changed in `index.html`

1. **Background tuned warmer, not inverted.** `--bg` moved from flat `#07080C` to a
   deeper near-black with a visible violet cast (`#0A0712`), plus two very low-opacity
   radial glows (cyan top-left, pink bottom-right) behind the UI — a tuned dark surface
   rather than a straight darken.
2. **One signature three-stop "aurora" brand gradient** (`--brand-gradient`: cyan →
   violet → pink) replaces three different ad-hoc two-tone gradients that were
   previously scattered across the logo, "Set status," onboarding's "Next," and the
   age-gate's "Continue" button — now one consistent, recognizable gradient used
   everywhere branding needs weight, per the "gradients carry branding weight" finding.
3. **`.glass` panels refined toward "Liquid Glass."** More transparent background
   (0.72 → 0.62 opacity), stronger blur (22px → 26px), and a layered inset box-shadow
   that reads as a specular top-edge highlight plus bottom-edge depth, instead of a
   flat tinted panel.
4. **Subtle kinetic type on the logo** — the gradient text slowly shifts position over
   7s (respecting `prefers-reduced-motion`), a restrained version of the "motion as a
   core interface element" finding rather than anything attention-grabbing.
5. **Cohesion fix found during the audit, not from the trend research:** the filter
   chips and radius-control "active" states were using a plain white tint while the
   status grid's "active" state already used a cyan tint — now all three match.
6. **Map tile filter nudged** (`hue-rotate(-6deg)` → `-10deg`, slightly higher
   saturation) so the game-world map color cast pairs with the new violet/pink brand
   gradient instead of the old cyan-only one.

## What didn't change, on purpose

Category gradients (yoga green, smoking grey, coffee brown, etc.) stay as they were —
they're functional color-coding for telling activities apart at a glance, not brand
decoration, so homogenizing them into the new brand gradient would hurt usability for
a cosmetic win. Same reasoning for the Free/Premium badge colors from the previous
visual-psychology pass — those are deliberately NOT part of the brand gradient, since
their whole job is to be the "odd one out" (isolation effect) against everything else.

## Sources
- [UI Color Trends to Watch in 2026 (Updivision)](https://updivision.com/blog/post/ui-color-trends-to-watch-in-2026)
- [18 UI design trends for 2026 (daisyUI)](https://trends.daisyui.com/ui-design-trends-2026/)
- [Glassmorphism, neumorphism, liquid glass: what to use in 2026 (SetProduct)](https://setproduct.com/blog/liquid-glass-vs-glassmorphism)
- [9 Mobile App Design Trends for 2026 (UX Pilot)](https://uxpilot.ai/blogs/mobile-app-design-trends)
- [Overview of Top 15 UI/UX Trends in 2026 and Beyond (PixelPlex)](https://pixelplex.io/blog/ui-ux-trends/)
- [8 App Design Trends for 2026 (Moburst)](https://www.moburst.com/blog/top-mobile-web-design-trends/)
- [Trending icons: top icon design trends for 2026 (ManyPixels)](https://www.manypixels.co/blog/post/the-key-trends-in-icon-design-in-2022)
