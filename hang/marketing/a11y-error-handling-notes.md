# Accessibility & error-handling audit — findings and fixes

Audited with real tools, not inspection-by-eye: [axe-core](https://github.com/dequelabs/axe-core)
4.9.1 (industry-standard automated accessibility checker, run via Playwright across the
age-gate, main map, profile sheet, and zoomed-out cluster screens) plus direct pixel
sampling of rendered screenshots to measure real WCAG contrast ratios, since translucent
glass panels defeat axe's own contrast checker (it reported `color-contrast` as
"incomplete — needs manual review" rather than pass/fail).

## Before → after (axe-core violation count)
| Screen | Before | After |
|---|---|---|
| Age gate | 2 | 0 |
| Main map | 3 | 0 |
| Profile sheet open | 3 | 0 |
| Cluster (zoomed out) view | *(not previously audited)* | 0 |

## What was actually broken

1. **`user-scalable=no` in the viewport meta tag** (axe: critical). Disables pinch-to-zoom
   text scaling — a WCAG 1.4.4 violation, and a common anti-pattern. Removed; Leaflet's own
   touch gestures are independent of browser-level zoom, so nothing else needed to change.
2. **`--muted` and `--faint` text colors measured below WCAG AA**, not estimated —
   sampled real rendered pixels behind the glass panels and computed actual contrast
   ratios: `--muted` came in at **4.21:1** (needs 4.5:1), `--faint` at **1.69–1.95:1**
   (badly failing — this affected the profile close button, the age-gate/paywall honesty
   disclaimers, and the auto-detect toggle label). Raised both until they clear 4.5:1
   with real margin against the measured range, and added a subtle text-shadow scrim to
   `.glass` content for additional legibility margin — translucent panels over a live map
   can't *guarantee* contrast in every lighting/terrain condition from color alone, which
   is an honest, inherent limit of this visual style, not something hidden.
3. **No landmark region** (axe: moderate, 18-20 nodes) — all page content sat outside any
   landmark. Wrapped the primary UI in `<main>`.
4. **`#nearby-avatars` scrollable strip wasn't keyboard-reachable** (axe: serious). Added
   `tabindex="0"`; its individual avatar items got `role="listitem"`, `tabindex="0"`,
   real `aria-label`s, and `Enter`/`Space` activation (they previously only responded to
   a mouse click).
5. **300 map markers (people, clusters, hot spots, community landmarks) had no
   accessible name at all** (axe: serious — `aria-command-name`). Leaflet's `alt` marker
   option only becomes an accessible name for plain image icons, not the `divIcon`
   markers this app uses — confirmed empirically (set `alt`, checked the rendered DOM,
   found no `aria-label` anywhere). Fixed by setting `aria-label` directly on each
   marker's element after creation, and re-applying it after every `setIcon()` call
   (which replaces the DOM node and silently wipes any attribute set before it) —
   relevant for driving-category markers, which get a new icon every movement tick for
   rotation, and cluster markers, which get a new icon on every membership change.
6. **Closed modals stayed in the keyboard Tab order** even though invisible
   (`opacity:0; pointer-events:none` isn't the same as being removed from the
   accessibility tree). Verified by tabbing through the page and landing on the hidden
   onboarding tutorial's "Skip" button. Fixed with the `inert` attribute, toggled off on
   open and back on on close, for every sheet/dialog.
7. **No visible keyboard focus indicator** on most controls — nearly everything uses
   `all:unset`, which silently strips the native focus ring along with the default
   styling. Added an explicit `:focus-visible` style; verified via real keyboard Tab
   navigation (not a mouse click, which correctly does *not* trigger `:focus-visible` —
   confirmed that distinction empirically after an initial test gave a false read).
8. **No `role="dialog"`/`aria-modal`** on any of the five sheets/overlays. Added to all
   five, plus `aria-label` naming each one.
9. **No Escape-to-close** anywhere. Added a global handler that closes whichever
   dismissible sheet is open, topmost first — the age gate is deliberately excluded
   since it's a required step, not a dismissible one.
10. **No `aria-hidden` on decorative emoji** inside controls that already had a visible
    label — fixed on the handful that mattered (self-avatar, the age-gate lock icon, the
    onboarding step icon, each nearby-avatar's icon).

## Error handling

- **No global error boundary existed.** An uncaught error anywhere left a silently
  frozen screen with zero explanation. Added a `window.addEventListener('error', ...)`
  and `unhandledrejection` handler that surfaces a toast instead. Verified by throwing a
  synthetic error and confirming the toast appears with the expected text.
- **No handling for the Leaflet CDN failing to load.** If the `<script>` tag serving
  Leaflet fails (offline, CDN outage, a script blocker), the very next line of code
  (`L.map(...)`) would throw immediately with no explanation. Added an explicit check
  that replaces the page with a clear message instead of a blank dark screen.
- **No handling for map tiles failing to load.** Added a one-shot `tileerror` listener
  that surfaces a toast rather than silently showing broken/missing tiles.
- Mic-permission denial (`getUserMedia` rejection in the push-to-talk flow) was already
  handled correctly with a clear on-screen message — checked, no change needed.

## What this audit did *not* try to fully solve

Full WCAG AA compliance on a map covered in emoji and live-updating markers has real,
honest limits — e.g. a screen-reader user still has no practical way to "browse" 300
live map markers the way a sighted user scans the map visually; the nearby-people strip
and its list semantics are the accessible alternative path to that same information, not
a replacement for genuinely rethinking the interaction model. That's a real product
question for a non-prototype version, not something four hours of CSS/ARIA fixes solves.
