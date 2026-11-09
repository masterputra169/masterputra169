# DESIGN.md

Design direction for the profile README and every image `scripts/build.py` draws. Drafted from the existing design during the antislop pass of 2026-11-09; the owner should confirm or edit it.

## Read

Reading this as: a developer profile for recruiters, collaborators and other builders, in the visual language of a trading dashboard, dial **ENERGY 2 / RHYTHM 2 / MOTION 1**.

- **ENERGY 2**: one loud moment (the gradient name and the live BTC chart), everything else calm.
- **RHYTHM 2**: one consistent card language, broken by the featured project (the only card with a product flow) and the stats card.
- **MOTION 1**: nothing moves. GitHub serves every image as `<img>`, and browsers do not pass `prefers-reduced-motion` into image documents, so any animation would ignore that setting. The chart already reads as live because its data is refreshed every 15 minutes.

## Identity

- **Focal point:** the name plus the live BTC/USD 15m panel. It is the one thing on the page no other profile has, and it states the "market side of crypto" story without a sentence.
- **Motif:** market data rendered honestly: candles, an EMA line, a real time axis, and a source and timestamp under every live number.
- **Voice:** plain, specific, sentence case. No uppercase tracking labels, no terminal costume.

## Color

Two core colors on a neutral base, defined in `THEMES`:

| Token | Dark | Light | Why |
|---|---|---|---|
| `cyan` | #22d3ee | #0e7490 | Primary: data (EMA, activity bars, flow dots, top language) |
| `violet` | #c084fc | #9333ea | Secondary: only in the name gradient and the second language |
| `mint` / `rose` | #34d399 / #fb7185 | #059669 / #be123c | Semantic only: price up/down and the "Live" status |
| neutrals | `text`, `muted`, `line`, `n1`, `n2` | | Everything else |

- The cyan to violet gradient appears once, on the name, because the name is the focal point. Nowhere else.
- No glow, no radial orbs, no dot-grid backgrounds, no colored card edges: cards are distinguished by content, not by an arbitrary color each.
- Every text color clears WCAG AA (4.5:1) against the panel, chip and GitHub page background in both themes. `dim`, `n1` and `n2` are for lines and bars only.

## Typography

- **Inter** for all text: it stays legible at the small sizes an image is scaled down to, and its tabular figures keep prices and counts aligned.
- **JetBrains Mono** only for market and machine data (pair, price change, time axis, data source, username, token names in the flow): monospace marks "this is data", as on a trading terminal.
- Minimum drawn size is 19 units (`LABEL`). Each layout is shown at roughly 0.6× to 1.5×, so no text renders below about 11px.

## Layout

- Two layouts per image: `WIDE` (960 units) for viewports of 1012px and up, `NARROW` (480 units) below. README.md picks one with `<source media="(max-width: 1011px)">`. The breakpoint is where GitHub moves the profile sidebar, which is where the README width jumps.
- Narrow layouts stack: the chart moves under the name, KPI tiles go 2 by 2, chips wrap.
- Every project card is full width and its own link. Two cards side by side could not collapse on a phone, because the `width` attribute on `<img>` cannot change with the screen.
- Section titles are real Markdown headings so screen readers, the GitHub outline and translation can use them.
- Radius: 7 for chips, tags and badges, 10 to 12 for rows and tiles, 16 to 20 for panels. Nothing is a full pill.

## Components and their reasons

- **Arrow on each card:** the whole card is a link to its repo, and the arrow is the only visual cue that an image is clickable.
- **"Live" badge:** shown only on projects with a deployed site. The dot is static: the state is real, so it does not need motion to be noticed.
- **"How it works" on DollarKilat:** three steps because the product flow really is three steps (client pays USDC, Solana settles, spend through QRIS).
- **Connect buttons:** drawn by `build.py` and placed with `height="48"`, so each keeps a 48px tap target at every screen width.
- **Demo data:** if every live source and the cache fail, the header and stats say "Demo data" instead of showing invented numbers as real.

## Known platform limits

- GitHub strips `style`, `fetchpriority` and `loading` from README HTML, so full-width images cannot reserve their height before they load (R-40). The page uses fewer images than before (no section-title images) to keep the shift small.
- Images cannot show hover or focus states. GitHub's own link focus ring is the only focus indicator.
- The contribution snake comes from Platane/snk and animates on a loop. It is the one moving element left; drop it from README.md to reach MOTION 1 fully.
