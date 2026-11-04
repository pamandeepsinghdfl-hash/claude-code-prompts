# Visual psychology pass — what was actually researched, and what got applied

A note on terminology first, since it matters: what follows is **UX and cognitive-
psychology heuristics**, sourced from a mix of one peer-reviewed study and a number of
industry blogs/reference guides. It is **not medical or clinical research** — there's no
neuroscience lab or peer-reviewed medical literature behind a map app's status chips.
Calling it "medical studies" would overclaim what this is. Below is what was actually
found, how strong the evidence is, and exactly what changed in the app as a result.

## What was researched (via web search, not invented)

**Color & attention** — thin evidence base. The one real study found (Andersen & Maier,
a small controlled study, 11 participants) found primary colors capture visual attention
more than secondary colors; it did *not* find strong evidence that color *meaning*
(e.g. "red = urgent") shapes early attention. Most other color-psychology claims
circulating online (e.g. "90% of snap judgments are based on color alone") are
unsourced marketing-blog numbers — not used here as justification for anything.

**Four UX heuristics**, each sourced from secondary/reference sources (UX Planet,
Parallel HQ, and others), not primary academic papers:
- **Fitts's Law** — bigger, closer, easier-to-reach targets get used more. Reasonably
  well established as a basic HCI principle going back decades, even if today's sources
  here are blogs restating it.
- **Hick's Law** — more choices, slower decisions (roughly logarithmic). Same caveat.
- **Von Restorff effect ("isolation effect")** — the one visually different item in a
  group is what gets remembered/noticed.
- **Peak-end rule** — people judge an experience mostly by its most intense moment and
  how it ended, not the average of the whole thing.

## What actually changed in the app because of this

1. **Von Restorff isolation on the two new badges.** The Free/Premium distinction
   (Walkie-Talkie vs. text messaging) needed to register in under a second. Both badges
   use colors that don't appear anywhere else in the app's palette — mint-green for
   "Free," gold for "Premium" — specifically so they're the visual "odd one out"
   against the existing cyan/magenta HUD scheme, not blended into it.
2. **Fitts's Law on the age-gate and paywall CTAs.** Both primary buttons
   (`#age-gate-submit`, `#paywall-unlock`) are full-width, large tap targets sitting
   where a thumb naturally rests on a phone — same placement pattern already used by
   "Set status" in the self-bar, kept consistent rather than introducing a new pattern.
3. **Peak-end rule on the age-gate's close.** It doesn't just silently disappear — it
   ends on an explicit, positive toast ("You're all set 🎉" / "some categories are
   hidden for your account") so the *end* of that interaction is a clear, deliberately
   warm beat, not a blank cut to the map.
4. **Hick's Law — deliberately not over-applied.** The status grid already has 13
   options; splitting it into sub-menus to "reduce choices" would have added navigation
   steps, which Fitts's Law penalizes more than Hick's Law rewards here. Left as a single
   grid; the category chips already let people narrow what they see, which is the
   lower-cost way to cut down the choice set at *browse* time instead of *select* time.

## Honest limits

No A/B testing exists for any of this — there's no user base yet to test against, and
the color-psychology evidence specifically is too thin to treat as more than a loose
direction (contrast and isolation, not specific "this color converts better" claims).
Treat this document as a design rationale, not proof the changes work better — that
needs real users.

## Sources
- [The attentional capture of colour in visual interface design (Strathprints)](https://strathprints.strath.ac.uk/78532)
- [The Attentional Capture of Colour in Visual Interface Design: A Controlled-Environment Study (DTU)](https://orbit.dtu.dk/en/publications/the-attentional-capture-of-colour-in-visual-interface-design-a-co/)
- [Laws of UX outside the screens (UX Planet)](https://uxplanet.org/laws-of-ux-outside-the-screens-d44298c85d94)
- [10 UX Laws in their Simplest Form (uxfol.io)](https://blog.uxfol.io/ux-laws/)
- [UX laws & design principles (Parallel HQ)](https://www.parallelhq.com/blog/ux-laws-design-principles)
- [Inside User's Minds: psychology principles in digital products (Medium/Welld-tech)](https://medium.com/welld-tech/inside-users-minds-how-to-apply-psychology-principles-to-increase-the-user-experience-of-digital-89928cd5039b)
