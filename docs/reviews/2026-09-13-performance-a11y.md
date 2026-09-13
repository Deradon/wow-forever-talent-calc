# Performance and accessibility review - web/

Date: 2026-09-13. Reviewed: `web/` at the state that deploys to
<https://deradon.github.io/wow-forever-talent-calc/>, nine real classes in
`data/talents/`, 971 crops in `data/review/`, 312 icons in `web/public/icons/`.

Method: `npm run build` (no `VITE_BASE`), `npm run preview` on
<http://localhost:4173>, Chromium via Playwright with CDP network/CPU
throttling and request logging, `curl -I` against the live Pages deployment,
WCAG 2.1 contrast computed from the CSS custom properties.

## 1. Measurements

### 1.1 Build output

`npm run build`: 2.8 s wall, type-check included. `dist/` holds 1291 files.

| Group | Files | Raw | Gzip |
|---|---:|---:|---:|
| **dist total** | **1291** | **18.84 MiB** (19,756,339 B; `du` reports 22 MB incl. block overhead) | - |
| Crop PNGs (`assets/*.png`) | 966 | 17.47 MiB (18,320,951 B) | n/a (already compressed) |
| - of which icon crops (`*.icon.png`, 36 px) | 470 src | 1.06 MiB, avg 2.4 kB | |
| - of which frame crops (tooltip screenshots) | 501 src | 16.41 MiB, avg 34.4 kB, max 92 kB | |
| Icons (`icons/*.jpg`, 56 px) | 312 | 569 KiB (582,566 B), avg 1.9 kB | n/a |
| Main JS chunk (`assets/index-*.js`) | 1 | 493,984 B | 137,308 B |
| Class chunks (one per class) | 9 | 344,644 B | 63,741 B |
| CSS | 1 | 13,207 B | 4,010 B |
| HTML + favicon | 2 | 987 B | ~700 B |

Crops **are** eagerly referenced: `src/data/crops.ts` uses an eager
`import.meta.glob(..., { query: '?url' })`, so all 971 path→URL pairs are
inlined into the main chunk. Measured: **92,392 B raw (18.7 % of
`index-*.js`)**, and removing that region drops the gzipped chunk from
138,492 B to 121,893 B, i.e. **~16.6 kB gzip**. The PNG bytes themselves are
not fetched until referenced - that part of the design works.

But the *calculator* only needs 72 of those entries (talents with
`iconSource: "crop"`, 1-13 per class). The remaining 398 icon crops and all
501 frame crops are used solely by `#/review/<class>`.

Approximate code attribution of the main chunk (esbuild metafile on
`src/main.tsx`; esbuild tree-shakes worse than Vite's rolldown, so treat as an
upper bound): react-dom 210 kB min, **zod 449 kB min (upper bound)**,
@floating-ui + tabbable 43 kB, app source 35 kB. Arithmetic against the real
494 kB chunk (494 - 92 crop map - ~222 React - ~43 floating-ui - ~35 app)
leaves **~100 kB minified / ~25 kB gzip for zod**.

### 1.2 First load over the network (cold cache, Chromium)

| Route | Requests | Encoded bytes on the wire | Notes |
|---|---:|---:|---|
| `#/` (landing) | 11 subresources | **202 kB** | index.js 139.5 kB + CSS 4.0 kB + **all 9 class chunks 58 kB**. No images. |
| `#/paladin` | 55 | **~248 kB** | 147 kB text (index.js + CSS + 1 class chunk) + **51 images, 101 kB** (40 icon JPGs, 12 icon crops - one talent falls back to initials). |
| `#/review/paladin` | 19 (first viewport) | **~558 kB** | 147 kB text + 15 lazy crops 411 kB. Full scroll pulls all 55 frame crops (1.83 MiB) + 52 icon crops (124 kB) = **1.95 MiB**. |

`loading="lazy"` on the review crops works: only what is near the viewport is
fetched.

### 1.3 Time to interactive (4x CPU throttle)

| Condition | load | FCP | Interactive (cells in DOM) |
|---|---:|---:|---:|
| No throttle, `#/` | 67 ms | 96 ms | 138 ms |
| Fast 3G (1.6 Mbps, 150 ms RTT), `#/` | 1192 ms | 1312 ms | 1331 ms |
| Fast 3G, `#/paladin` | 1189 ms | 1272 ms | **1708 ms** |
| 4G (9 Mbps, 60 ms RTT), `#/paladin` | 442 ms | 536 ms | 847 ms |

The main chunk alone takes 845 ms to download on Fast 3G. Nothing renders
before it: the HTML ships an empty `#root`.

### 1.4 Interaction cost

Event Timing API, processing duration per event, `#/paladin` (52 cells,
3 trees on one page):

| Interaction | 1x CPU | 4x CPU | 6x CPU |
|---|---:|---:|---:|
| `mouseover` / `pointerover` (hover a cell) | 0.0-0.3 ms | 0.1-1.0 ms | 0.3-2.0 ms |
| `click` (spend a point) | 4.4 ms avg / 5.8 max | **25.5 ms avg** | **37.0 ms avg / 44.1 max** |

**Hover is clean** - the tooltip lives in `TalentCell`'s own `open` state, so
only the hovered cell re-renders (measured ~6 DOM mutations per hover, all in
the portal). There is no grid-wide re-render on hover.

Spending a point does re-render the entire `ClassPage`: all 52 `TalentCell`s,
a fresh `canAdd()` per cell, and the three `Arrows` SVGs. ~15 DOM mutations
per click. At 44 ms worst case on a 6x-throttled CPU this still sits inside
the 200 ms "good INP" budget, so it is a watch-item, not a defect - but it
scales linearly with talents per page.

### 1.5 Caching on GitHub Pages

```
GET /wow-forever-talent-calc/                        cache-control: max-age=600
GET /wow-forever-talent-calc/assets/index-*.js       cache-control: max-age=600, etag W/"...", content-encoding: gzip (141,404 B)
GET /wow-forever-talent-calc/assets/index-*.css      cache-control: max-age=600
```

GitHub Pages serves **every** file with `max-age=600`, including
content-hashed, immutable assets, and does not allow custom headers. After ten
minutes a repeat visitor revalidates every asset: 3 conditional requests on
the calculator plus up to 51 for the icons, ~500 on a fully scrolled review
page. Gzip is applied; Brotli is not.

`robots.txt` → 404, `sitemap.xml` → 404.

## 2. Findings

Severity: **P1** = fix before sharing the link widely, **P2** = next pass,
**P3** = nice to have.

### Performance

| # | Sev | Finding | Fix |
|---|---|---|---|
| P-1 | P2 | The landing page eagerly `loadClass()`es **all nine classes** (`ClassPicker.tsx` `useEffect`) to print tree names and talent counts - 344 kB raw / 58 kB gzip, 9 extra requests, for text that is a few hundred bytes. | Generate a tiny `classes-index.json` at build time (id, className, tree names, talent/reviewed/needs-review counts) and have the picker read only that. Keep the full load for the class route. |
| P-2 | P2 | The eager crop registry puts **92 kB raw / ~17 kB gzip** of paths into the main chunk, of which ~95 % is only needed by `#/review/<class>`. | Split `crops.ts`: keep an eager map for the 72 `iconSource: "crop"` icons actually used by the calculator (or move those files under `web/public/crops/` and build the URL from the path, needing zero registry), and move the review-only glob into a module that `ReviewPage` imports dynamically. Saves ~17 kB gzip off every first load. |
| P-3 | P2 | **zod (~100 kB min / ~25 kB gzip est.) ships to every visitor** to re-validate JSON that `validate-data` and `schema.test.ts` already validate in CI, on every build. | Validate at build time only. Either gate `parseClass` behind `import.meta.env.DEV` and cast in production, or switch to `zod/mini`. Biggest single byte win in the main chunk. |
| P-4 | P2 | Frame crops are PNG screenshots averaging 34 kB; a fully scrolled review page is **1.95 MiB per class, 17.5 MiB in `dist/`**. | Emit WebP (q≈80) or AVIF alongside in the pipeline - typically 70-85 % smaller for this content - and keep PNG only as the archival source in `data/review/`. Also add `width`/`height` to `.review-frame` images. |
| P-5 | P3 | A class page makes **51 image requests** (40 icon JPGs + 12 crops). Cheap over HTTP/2, but each one costs a revalidation round-trip after 10 minutes (see P-7). | Build one icon sprite sheet (or a per-class sheet) and address icons by `background-position`; or at minimum ship the icons as WebP (312 files, 569 KiB → ~200 KiB). |
| P-6 | P3 | `index.html` renders nothing until the 139 kB main chunk arrives (845 ms on Fast 3G). | Add `<link rel="modulepreload">` for the class chunk when the hash already names a class, and put a minimal skeleton/loading panel in the static HTML so FCP does not wait on JS. `preconnect` is not applicable - the app fetches nothing cross-origin. |
| P-7 | P2 | GitHub Pages caps hashed assets at `max-age=600`; they can never be cached immutably. | Either accept it (304s are small) or move hosting to Cloudflare Pages/Netlify where a `_headers` file can set `Cache-Control: public, max-age=31536000, immutable` for `/assets/*` - `vite.config.ts` already anticipates a custom domain. Worth doing once the review route with its ~500 assets is public. |
| P-8 | P3 | Every point spent re-renders all 52 cells (25 ms at 4x CPU, 44 ms at 6x). | Wrap `TalentCell` in `React.memo` and hoist `onAdd`/`onRemove` to stable callbacks keyed by talent id (they are currently new closures each render, which defeats memo). Only needed if pages grow past ~80 talents. |

### Accessibility

| # | Sev | Finding | Fix |
|---|---|---|---|
| A-1 | **P1** | **Keyboard users cannot remove a point.** `TalentCell` spreads `{...getReferenceProps()}` *after* its own `onKeyDown`, and `useDismiss` contributes an `onKeyDown`, so the component's handler is overwritten and never runs. Verified in the browser: `Enter`/`Space` add a rank, `Backspace`/`Delete`/`-` do nothing (`defaultPrevented === false` on the cell's keydown). Right-click still refunds, and `web/README.md` documents Backspace as working. No e2e test covers it. | Pass the handlers through floating-ui: `{...getReferenceProps({ onClick, onContextMenu, onKeyDown })}`. Add a Playwright case next to the existing right-click test in `tests/smoke.spec.ts`. |
| A-2 | **P1** | **Touch devices never see a tooltip.** `useHover` does not fire for touch, and `useFocus` defaults to `visibleOnly: true`, so a tap (which is not `:focus-visible`) does not open it either. Confirmed on an emulated Pixel 7: tap adds a rank, zero `.tooltip` nodes appear. Talent descriptions, rank text, requirement lines and provenance are unreachable on phones and tablets. | Add a touch path: `useClick` with a tap toggling the tooltip and a second tap (or an explicit "+" hit area) spending the point, or a long-press. Whatever the gesture, make the tooltip dismissible by tapping elsewhere (`useDismiss` already handles that) and drop `pointer-events: none` for that mode so it can be scrolled. |
| A-3 | **P1** | **Touch devices cannot remove a point at all** - removal is right-click or the (broken) Backspace. The only escape is Reset. | Long-press to refund, or a small "−" affordance on the cell once `rank > 0`, alongside the A-2 gesture. |
| A-4 | **P1** | **The tooltip is invisible to screen readers.** The floating element carries `role="tooltip"` but the cell has no `aria-describedby` (verified: `null`), so SR users hear only "Improved Seals, rank 0 of 3, button" - no description, no "Requires 5 points in …", no next-rank text. | Add `useRole(context, { role: 'tooltip' })` to the `useInteractions` list - floating-ui then wires `id`/`aria-describedby` automatically. |
| A-5 | P2 | Locked cells are ordinary focusable buttons that silently do nothing on activation; no `aria-disabled`, and the label omits state. Every cell reads as plain `"<name>, rank X of Y"` regardless of locked / available / maxed / flagged-for-review. | Extend the label, e.g. `"Healing Light, rank 0 of 3, locked: requires 5 points in Holy"`, and set `aria-disabled="true"` (keep it focusable so the reason is discoverable). Include the `?` review flag in the label too - it is currently a CSS `::after` glyph with no text equivalent. |
| A-6 | P2 | Nothing is announced when a point is spent. "Points left", "Required level" and the per-tree counters update silently (no `[aria-live]` anywhere on the page). | Put `aria-live="polite"` on the header's summary span, or add a visually hidden live region announcing "Holy 5, 46 points left, required level 34". |
| A-7 | P2 | **No `<main>` landmark and no skip link**, and the 52 cell buttons sit in the middle of the tab order (55 focusables on a class page) - reaching the footer or the second tree's Reset means tabbing through a whole tree. `<header>` inside `ClassPage` plus the app-level `<nav>`/`<footer>` gives banner/contentinfo, but the content itself is an unlabelled `div`. | Wrap `Body` in `<main id="main">`, add a skip link as the first focusable element, and implement the WAI grid pattern in `.tree-grid`: roving `tabindex` with arrow keys moving between cells, so the grid is one tab stop. |
| A-8 | P2 | `PageTabs` uses `role="tablist"`/`role="tab"` with `aria-selected` but there is no `role="tabpanel"`, no `aria-controls`, and no arrow-key roving - an incomplete ARIA pattern that misleads SR users. | Either complete it (ids, `aria-controls`, `tabIndex={-1}` on inactive tabs, Left/Right handling, `role="tabpanel"` + `aria-labelledby` on the tree container) or drop the roles and use plain buttons with `aria-pressed`. |
| A-9 | P3 | Locked-cell border `#555` on the tree background is **2.60:1**, below the 3:1 required for non-text UI state (WCAG 1.4.11). It is one of only two locked cues (the other is a greyscale filter on the icon, also a non-text cue). | Lift to ~`#6f6f6f` (3.0:1) or higher, and make sure "locked" is also conveyed in text (see A-5). |
| A-10 | P3 | Route changes update `document.title` but do not move focus or announce; after clicking a class card, focus stays on the (now removed) link and reverts to `<body>`. | On route change, focus the new `<h1>` (`tabIndex={-1}`) or announce the new title in a live region. |
| A-11 | P3 | No `prefers-reduced-motion` block - currently harmless, because the app has no transitions or animations at all (only a `filter: brightness` on `.btn:hover`). Flagged so it is not forgotten when motion is added. | Add the media query when the first transition lands. |
| A-12 | P3 | Icon `<img>` elements carry no `width`/`height` attributes. No CLS in practice - the cell is a fixed 44 px box - but review-page frames (`max-width: 300px; height: auto`) do shift as they lazy-load. | Emit intrinsic dimensions with the crop metadata and set them on `.review-frame`. |

### SEO / sharing

| # | Sev | Finding | Fix |
|---|---|---|---|
| S-1 | P2 | **No Open Graph or Twitter card tags.** Every shared build link - the whole point of the URL codec - previews as the bare title plus the generic description. | Add `og:title`, `og:description`, `og:type`, `og:url`, `og:image` (a 1200x630 PNG in `public/`) and `twitter:card=summary_large_image` to `index.html`. |
| S-2 | P2 | **Hash routing means one crawlable URL.** `#/paladin`, `#/review/paladin` and every build string are invisible to crawlers; the site cannot rank for "WoW Forever paladin talent calculator". | Prerender one real HTML file per class (`/paladin/index.html`) with a class-specific `<title>`, description and OG tags that then hands off to the hash route; or switch to path routing plus the GitHub Pages `404.html` SPA fallback. A build-time loop over `data/talents/*.json` makes this ~30 lines of Vite plugin. |
| S-3 | P3 | No `robots.txt` (404), no `sitemap.xml` (404), no `<link rel="canonical">`. | Ship both from `public/`; the sitemap lists the prerendered class URLs from S-2. Consider `noindex` for `#/review/*`. |
| S-4 | P3 | No `theme-color`, no `apple-touch-icon`, no `og:locale`. | One-line additions to `index.html`. |

## 3. Accessibility checklist

| Check | Result |
|---|---|
| Cells reachable by keyboard, in logical DOM order | **Pass** - native `<button>`s, source order = row/column order |
| `Enter` / `Space` spends a point | **Pass** (verified: rank 0 → 1 → 2) |
| A key removes a point | **Fail** - A-1, the handler is overwritten by floating-ui |
| Focus survives the re-render after spending | **Pass** |
| Visible focus indicator on cells | **Pass** - `.cell:focus-visible` white 2 px ring, 21:1 against the cell |
| Visible focus indicator on buttons/links | **Pass** - UA default preserved (no global `outline: none`) |
| Tooltip opens on keyboard focus | **Pass** (`useFocus`) |
| Tooltip dismissible with Escape | **Pass** (`useDismiss`) |
| Tooltip associated via `aria-describedby` | **Fail** - A-4 |
| Tooltip reachable on touch | **Fail** - A-2 |
| Point removal possible on touch | **Fail** - A-3 |
| Cell `aria-label` present | **Pass** - `"<name>, rank X of Y"` |
| Cell state (locked / maxed / flagged) exposed non-visually | **Fail** - A-5 |
| Live announcement of point/level changes | **Fail** - A-6 |
| `<main>` landmark | **Fail** - A-7 |
| `<nav>` / `<footer>` landmarks | **Pass** |
| Skip link | **Fail** - A-7 |
| One `<h1>` per route, sane heading order (h1 → h2 per tree) | **Pass** |
| Document title reflects the route | **Pass** - `"Paladin 0/0/0 - WoW Forever Talent Calculator"`, `"Review Paladin - …"` |
| Route change announced / focus managed | **Fail** - A-10 |
| `lang` attribute | **Pass** (`en`) |
| Decorative images have `alt=""`; meaningful ones have text | **Pass** - 52/52 cell icons `alt=""`, review frames `alt="Tooltip crop of <name>"` |
| Tab roles complete | **Fail** - A-8 |
| Touch target size ≥ 44 px | **Pass** - cells are exactly 44x44 |
| No horizontal scroll at 320 / 400 / 768 px | **Pass** (measured `scrollWidth == clientWidth` at all three) |
| `prefers-reduced-motion` honoured | **Pass by default** - no animation exists (A-11) |
| `color-scheme` declared | **Pass** (`dark`) |
| Text contrast ≥ 4.5:1 | **Pass** - all 30 measured text pairs, 5.2:1 to 18.8:1 |
| Non-text/UI contrast ≥ 3:1 | **Fail** on one: locked border 2.60:1 (A-9) |

### Contrast ratios (computed, WCAG 2.1)

| Foreground on background | Ratio | AA text | AA non-text |
|---|---:|---|---|
| gold `#ffd100` heading on panel `#161d33` | 11.43 | Pass | Pass |
| gold-dim `#c8a24a` link on bg `#07090f` | 8.27 | Pass | Pass |
| gold-dim `#c8a24a` link on panel `#0f1526` | 7.55 | Pass | Pass |
| text `#f0e6d2` on panel | 14.67 | Pass | Pass |
| text-dim `#b8b0a0` on bg (12 px footer/tagline) | 9.25 | Pass | Pass |
| text-dim `#b8b0a0` on panel2 | 7.76 | Pass | Pass |
| inactive tab text-dim on `#0b101c` | 8.83 | Pass | Pass |
| green badge `#1eff00` on `#0b0b0b` (11 px) | 14.40 | Pass | Pass |
| grey badge `#8d8d8d` on `#0b0b0b` (11 px) | 5.93 | Pass | Pass |
| gold badge `#ffd100` on `#0b0b0b` (11 px) | 13.47 | Pass | Pass |
| tooltip desc `#ffffdd` on tooltip bg | 18.82 | Pass | Pass |
| tooltip "next rank" dimmed (0.7 alpha) | 9.41 | Pass | Pass |
| tooltip provenance `#8f98b3` (11 px) | 6.68 | Pass | Pass |
| tooltip caveat `#e2a640` (12 px) | 8.92 | Pass | Pass |
| tooltip requirement red `#ff4040` | 5.54 | Pass | Pass |
| error red `#ff4040` on panel | 5.24 | Pass | Pass |
| notice `#ffe3a0` on `#2b2210` | 12.51 | Pass | Pass |
| review flag `#000` on `#f0a020` | 9.75 | Pass | Pass |
| icon fallback initials `#ddd` on gradient | 9.91 | Pass | Pass |
| **cell border grey `#8d8d8d` vs grid bg** | 5.84 | n/a | Pass |
| **cell border green `#1eff00` vs grid bg** | 14.17 | n/a | Pass |
| **cell border gold `#ffd100` vs grid bg** | 13.26 | n/a | Pass |
| **locked border `#555555` vs grid bg** | **2.60** | n/a | **Fail** |
| panel border `#7a6230` vs bg | 3.43 | n/a | Pass |
| disabled button gold @ 0.5 on `#221c33` | 3.74 | n/a | Pass (disabled controls are exempt) |

Grid background taken as `#0a0d18`, the darkest point of the tree-grid
gradient stack (the lightest point, `#1f2a4a`, is lighter and so only
improves the ratios for dark foregrounds - the locked border fails at both
ends).

## 4. Suggested order of work

1. A-1 (keyboard refund) + regression test - it is a two-line fix to a
   documented feature that does not work.
2. A-2/A-3 (touch: tooltip and refund) - the app is currently unusable on a
   phone beyond spending points blind.
3. A-4 (`useRole`) - one line, unlocks the tooltip for screen readers.
4. P-3 (drop zod from the client) + P-2 (split the crop registry) - together
   ~40 kB gzip off every first load, no behaviour change.
5. P-1 (landing-page class index) - removes 9 requests / 58 kB from the first
   page anyone sees.
6. S-1/S-2 (OG tags + per-class prerender) - the share link is the product.
7. Everything else as capacity allows; revisit P-7 (immutable caching) if the
   host ever moves off GitHub Pages.
