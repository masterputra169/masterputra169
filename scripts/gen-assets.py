"""Generates every self-hosted SVG used by the masterputra169 profile README."""
import os
import random
import sys
from xml.sax.saxutils import escape

OUT = sys.argv[1] if len(sys.argv) > 1 else "assets"
os.makedirs(OUT, exist_ok=True)

# ── design tokens ────────────────────────────────────────────────────────────
INK = "#070a12"
PANEL = "#0c1222"
LINE = "#1c2740"
MUTED = "#64748b"
TEXT = "#cbd5e1"
BRIGHT = "#f1f5f9"
CYAN = "#22d3ee"
INDIGO = "#818cf8"
VIOLET = "#c084fc"
MINT = "#34d399"
ROSE = "#fb7185"

SANS = "'Inter','Segoe UI',-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif"
MONO = "'JetBrains Mono','SFMono-Regular',ui-monospace,Menlo,Consolas,'DejaVu Sans Mono',monospace"

BRAND_GRAD = f"""<linearGradient id="brand" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{CYAN}"/><stop offset=".55" stop-color="{INDIGO}"/><stop offset="1" stop-color="{VIOLET}"/>
    </linearGradient>"""


def write(name, svg):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(svg.strip() + "\n")
    print("wrote", name)


# ── header ───────────────────────────────────────────────────────────────────
def candles():
    """A deterministic, mostly-bullish 15m BTC-looking series inside the chart panel."""
    rnd = random.Random(169)
    price, series = 100.0, []
    for i in range(15):
        drift = 1.25 if i not in (4, 5, 9) else -1.6
        o = price
        c = o + drift + rnd.uniform(-1.1, 1.4)
        hi = max(o, c) + rnd.uniform(0.3, 1.3)
        lo = min(o, c) - rnd.uniform(0.3, 1.3)
        series.append((o, hi, lo, c))
        price = c
    lo_all = min(s[2] for s in series)
    hi_all = max(s[1] for s in series)
    top, bot = 118, 286

    def y(v):
        return bot - (v - lo_all) / (hi_all - lo_all) * (bot - top)

    out, ema_pts, ema = [], [], series[0][3]
    for i, (o, hi, lo, c) in enumerate(series):
        x = 806 + i * 26.5
        up = c >= o
        col = MINT if up else ROSE
        body_top, body_bot = y(max(o, c)), y(min(o, c))
        out.append(
            f'<g class="cd" style="animation-delay:{0.15 + i * 0.07:.2f}s">'
            f'<line x1="{x + 6:.1f}" y1="{y(hi):.1f}" x2="{x + 6:.1f}" y2="{y(lo):.1f}" stroke="{col}" stroke-width="1.6"/>'
            f'<rect x="{x:.1f}" y="{body_top:.1f}" width="12" height="{max(body_bot - body_top, 2):.1f}" rx="2" fill="{col}" fill-opacity="{0.9 if up else 0.85}"/>'
            f"</g>"
        )
        ema = ema + (c - ema) * 0.35
        ema_pts.append((x + 6, y(ema)))
    path = "M" + " L".join(f"{px:.1f} {py:.1f}" for px, py in ema_pts)
    return "\n      ".join(out), path, ema_pts[-1]


def header():
    cds, ema_path, (ex, ey) = candles()
    chips = [("SOLANA", 72, 96), ("EVM · BASE", 180, 134), ("PREDICTION MARKETS", 326, 214), ("ML SIGNALS", 552, 134)]
    chip_svg = "\n    ".join(
        f'<g class="chip" style="animation-delay:{0.9 + i * 0.1:.1f}s"><rect x="{x}" y="342" width="{w}" height="34" rx="17" fill="{PANEL}" stroke="{LINE}"/>'
        f'<text x="{x + w / 2}" y="364" text-anchor="middle" class="mono" font-size="13" letter-spacing="1.6" fill="{TEXT}">{escape(t)}</text></g>'
        for i, (t, x, w) in enumerate(chips)
    )
    blocks = ["0x7a", "0x3f", "0xc1", "0x9e", "0x5d"]
    block_svg = "\n      ".join(
        f'<g><rect x="{804 + i * 82}" y="318" width="56" height="26" rx="6" fill="{INK}" stroke="{LINE}"/>'
        f'<text x="{832 + i * 82}" y="335.5" text-anchor="middle" class="mono" font-size="11" fill="{MUTED}">{b}</text>'
        f'<rect x="{804 + i * 82}" y="318" width="56" height="26" rx="6" fill="none" stroke="{CYAN}" stroke-opacity="0">'
        f'<animate attributeName="stroke-opacity" values="0;0;.9;0;0" keyTimes="0;{i * 0.18:.2f};{i * 0.18 + 0.06:.2f};{i * 0.18 + 0.16:.2f};1" dur="3.2s" repeatCount="indefinite"/></rect></g>'
        for i, b in enumerate(blocks)
    )
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 420" width="1280" height="420" role="img" aria-label="MasterPutra — Web3 Developer, dApp Builder, Quant Builder">
  <title>MasterPutra — Web3 Developer · dApp Builder · Quant Builder</title>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{INK}"/><stop offset="1" stop-color="#0a0f1e"/>
    </linearGradient>
    <radialGradient id="glowC" cx="1010" cy="70" r="520" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{CYAN}" stop-opacity=".20"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glowV" cx="170" cy="470" r="560" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{VIOLET}" stop-opacity=".18"/><stop offset="1" stop-color="{VIOLET}" stop-opacity="0"/>
    </radialGradient>
    <pattern id="dots" width="26" height="26" patternUnits="userSpaceOnUse">
      <circle cx="1.5" cy="1.5" r="1.1" fill="#1a2338"/>
    </pattern>
    <linearGradient id="fade" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#fff" stop-opacity=".9"/><stop offset=".6" stop-color="#fff" stop-opacity=".35"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
    </linearGradient>
    <mask id="dotMask"><rect width="1280" height="420" fill="url(#fade)"/></mask>
    {BRAND_GRAD}
    <linearGradient id="emaFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{CYAN}" stop-opacity=".22"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/>
    </linearGradient>
    <clipPath id="frame"><rect width="1280" height="420" rx="26"/></clipPath>
  </defs>
  <style>
    .sans{{font-family:{SANS}}}
    .mono{{font-family:{MONO}}}
    .rise{{opacity:0;animation:rise .8s cubic-bezier(.2,.7,.2,1) forwards}}
    .chip{{opacity:0;animation:rise .6s ease-out forwards}}
    .cd{{opacity:0;transform-box:fill-box;transform-origin:50% 100%;animation:grow .55s cubic-bezier(.2,.8,.2,1) forwards}}
    .ema{{stroke-dasharray:520;stroke-dashoffset:520;animation:draw 1.6s 1.2s ease-out forwards}}
    .emaFill{{opacity:0;animation:show 1s 2.2s forwards}}
    .live{{animation:pulse 1.6s ease-in-out infinite}}
    @keyframes rise{{from{{opacity:0;transform:translateY(12px)}}to{{opacity:1;transform:none}}}}
    @keyframes grow{{from{{opacity:0;transform:scaleY(.15)}}to{{opacity:1;transform:none}}}}
    @keyframes draw{{to{{stroke-dashoffset:0}}}}
    @keyframes show{{to{{opacity:1}}}}
    @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.25}}}}
    @media (prefers-reduced-motion:reduce){{*{{animation:none!important;opacity:1!important;stroke-dashoffset:0!important}}}}
  </style>

  <g clip-path="url(#frame)">
    <rect width="1280" height="420" fill="url(#bg)"/>
    <rect width="1280" height="420" fill="url(#dots)" mask="url(#dotMask)"/>
    <rect width="1280" height="420" fill="url(#glowC)"/>
    <rect width="1280" height="420" fill="url(#glowV)"/>

    <!-- identity -->
    <g class="rise" style="animation-delay:.05s">
      <text x="72" y="96" class="mono" font-size="19"><tspan fill="{CYAN}">~/masterputra</tspan><tspan fill="{MUTED}"> $ whoami</tspan></text>
    </g>
    <g class="rise" style="animation-delay:.2s">
      <text x="68" y="206" class="sans" font-size="104" font-weight="800" letter-spacing="-4" fill="url(#brand)">MasterPutra</text>
    </g>
    <g class="rise" style="animation-delay:.38s">
      <text x="72" y="256" class="sans" font-size="27" font-weight="500" fill="{TEXT}">Web3 Developer <tspan fill="{MUTED}">·</tspan> dApp Builder <tspan fill="{MUTED}">·</tspan> Quant Builder</text>
    </g>
    <g class="rise" style="animation-delay:.55s">
      <text x="72" y="304" class="mono" font-size="18" fill="{MUTED}"><tspan fill="{MINT}">❯</tspan> shipping on-chain products for real users <tspan fill="{CYAN}">▋<animate attributeName="fill-opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1.05s" repeatCount="indefinite"/></tspan></text>
    </g>
    {chip_svg}

    <!-- market panel -->
    <g class="rise" style="animation-delay:.1s">
      <rect x="780" y="58" width="440" height="304" rx="18" fill="{PANEL}" fill-opacity=".88" stroke="{LINE}"/>
      <text x="804" y="92" class="mono" font-size="13" fill="{MUTED}" letter-spacing="1"><tspan fill="{BRIGHT}">BTC/USD</tspan>  ·  15m  ·  signal</text>
      <circle cx="1144" cy="87.5" r="4.5" fill="{MINT}" class="live"/>
      <text x="1196" y="92" text-anchor="end" class="mono" font-size="12" fill="{MINT}" letter-spacing="1.5">LIVE</text>
      <g stroke="{LINE}" stroke-dasharray="3 6">
        <line x1="800" y1="128" x2="1200" y2="128"/><line x1="800" y1="182" x2="1200" y2="182"/><line x1="800" y1="236" x2="1200" y2="236"/><line x1="800" y1="290" x2="1200" y2="290"/>
      </g>
      <path class="emaFill" d="{ema_path} L{ex:.1f} 290 L812 290 Z" fill="url(#emaFill)"/>
      {cds}
      <path class="ema" d="{ema_path}" fill="none" stroke="{CYAN}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="{ex:.1f}" cy="{ey:.1f}" r="5" fill="{CYAN}" class="live"/>
      <line x1="832" y1="331" x2="1160" y2="331" stroke="{LINE}" stroke-width="2"/>
      {block_svg}
      <circle r="3.5" fill="{CYAN}"><animateMotion dur="3.2s" repeatCount="indefinite" path="M832 331 L1160 331"/></circle>
    </g>

    <rect x="0" y="416" width="1280" height="4" fill="url(#brand)" opacity=".85"/>
  </g>
</svg>"""


# ── section divider / title chip ─────────────────────────────────────────────
def section(slug, idx, title):
    w = 1280
    svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} 64" width="{w}" height="64" role="img" aria-label="{escape(title)}">
  <title>{escape(title)}</title>
  <defs>{BRAND_GRAD}
    <linearGradient id="rule" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{INDIGO}" stop-opacity=".7"/><stop offset="1" stop-color="{INDIGO}" stop-opacity="0"/></linearGradient>
  </defs>
  <text x="6" y="42" font-family="{MONO}" font-size="18" fill="{CYAN}" letter-spacing="2">{idx}</text>
  <text x="50" y="44" font-family="{SANS}" font-size="30" font-weight="700" fill="url(#brand)" letter-spacing="-.5">{escape(title)}</text>
  <rect x="{70 + len(title) * 17.5:.0f}" y="34" width="{w}" height="1.5" fill="url(#rule)"/>
</svg>"""
    write(f"section-{slug}.svg", svg)


# ── project card ─────────────────────────────────────────────────────────────
def card(slug, idx, kind, title, lines, tags, accent, status=None):
    W, H = 640, 300
    desc = "".join(
        f'<tspan x="36" dy="{0 if i == 0 else 29}">{escape(l)}</tspan>' for i, l in enumerate(lines)
    )
    tag_svg, x = [], 36
    for t in tags:
        w = round(len(t) * 9.2 + 30)
        tag_svg.append(
            f'<rect x="{x}" y="236" width="{w}" height="30" rx="15" fill="{accent}" fill-opacity=".08" stroke="{accent}" stroke-opacity=".35"/>'
            f'<text x="{x + w / 2:.1f}" y="256" text-anchor="middle" font-family="{MONO}" font-size="14" fill="{TEXT}">{escape(t)}</text>'
        )
        x += w + 10
    badge = ""
    if status:
        bw = round(len(status) * 8.2 + 34)
        badge = (
            f'<g transform="translate({W - 36 - bw - 46} 34)"><rect width="{bw}" height="26" rx="13" fill="{MINT}" fill-opacity=".1" stroke="{MINT}" stroke-opacity=".45"/>'
            f'<circle cx="14" cy="13" r="3.5" fill="{MINT}"><animate attributeName="opacity" values="1;.25;1" dur="1.6s" repeatCount="indefinite"/></circle>'
            f'<text x="{bw / 2 + 7:.1f}" y="17.5" text-anchor="middle" font-family="{MONO}" font-size="11.5" fill="{MINT}" letter-spacing="1">{escape(status)}</text></g>'
        )
    svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{escape(title)} — {escape(' '.join(lines))}">
  <title>{escape(title)}</title>
  <defs>
    <linearGradient id="edge" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{accent}" stop-opacity=".75"/><stop offset=".45" stop-color="{LINE}"/><stop offset="1" stop-color="{LINE}"/>
    </linearGradient>
    <radialGradient id="glow" cx="{W}" cy="0" r="380" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{accent}" stop-opacity=".16"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/>
    </radialGradient>
    <pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#172034"/></pattern>
    <clipPath id="c"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="20"/></clipPath>
  </defs>
  <g clip-path="url(#c)">
    <rect width="{W}" height="{H}" fill="{PANEL}"/>
    <rect width="{W}" height="{H}" fill="url(#dots)" opacity=".7"/>
    <rect width="{W}" height="{H}" fill="url(#glow)"/>
    <rect x="0" y="0" width="5" height="{H}" fill="{accent}" opacity=".9"/>
  </g>
  <rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="20" fill="none" stroke="url(#edge)" stroke-width="1.5"/>
  <text x="36" y="52" font-family="{MONO}" font-size="13" letter-spacing="2"><tspan fill="{accent}">{idx}</tspan><tspan fill="{MUTED}">  /  {escape(kind.upper())}</tspan></text>
  {badge}
  <g transform="translate({W - 64} 30)"><rect width="30" height="30" rx="9" fill="{INK}" stroke="{LINE}"/>
    <path d="M11 19 L19 11 M12.5 11 H19 V17.5" fill="none" stroke="{TEXT}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></g>
  <text x="34" y="108" font-family="{SANS}" font-size="34" font-weight="750" fill="{BRIGHT}" letter-spacing="-.8">{escape(title)}</text>
  <text x="36" y="148" font-family="{SANS}" font-size="20" fill="{TEXT}" fill-opacity=".86">{desc}</text>
  {''.join(tag_svg)}
</svg>"""
    write(f"card-{slug}.svg", svg)


# ── stack panel (text chips, no third-party logos) ───────────────────────────
def stack():
    rows = [
        ("WEB3", CYAN, ["Solana", "EVM · Base", "Solidity", "Hardhat", "Privy", "Wallet UX", "IPFS"]),
        ("MARKETS", MINT, ["Polymarket CLOB", "Hyperliquid", "Kelly sizing", "Backtesting", "Telegram alerts"]),
        ("ML · DATA", VIOLET, ["XGBoost", "LightGBM", "LSTM", "Pandas", "NumPy", "Drift detection"]),
    ]
    W, H = 1280, 232
    body = []
    for r, (label, col, items) in enumerate(rows):
        y = 34 + r * 66
        body.append(
            f'<circle cx="40" cy="{y + 17}" r="4" fill="{col}"/>'
            f'<text x="56" y="{y + 22}" font-family="{MONO}" font-size="14" letter-spacing="2.4" fill="{col}">{label}</text>'
        )
        x = 212
        for t in items:
            w = round(len(t) * 9.4 + 34)
            body.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="34" rx="10" fill="{INK}" stroke="{LINE}"/>'
                f'<text x="{x + w / 2:.1f}" y="{y + 22.5}" text-anchor="middle" font-family="{SANS}" font-size="15.5" font-weight="500" fill="{TEXT}">{escape(t)}</text>'
            )
            x += w + 10
    svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Web3, markets and ML stack">
  <title>Web3 · Markets · ML stack</title>
  <defs><pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#172034"/></pattern></defs>
  <rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="20" fill="{PANEL}" stroke="{LINE}"/>
  <rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="20" fill="url(#dots)" opacity=".6"/>
  <line x1="188" y1="30" x2="188" y2="{H - 30}" stroke="{LINE}"/>
  {''.join(body)}
</svg>"""
    write("stack.svg", svg)


# ── footer ───────────────────────────────────────────────────────────────────
def footer():
    svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 150" width="1280" height="150" role="img" aria-label="In code we trust, in markets we hunt">
  <title>In code we trust, in markets we hunt</title>
  <defs>{BRAND_GRAD}
    <linearGradient id="fadeL" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{INDIGO}" stop-opacity="0"/><stop offset=".5" stop-color="{INDIGO}" stop-opacity=".8"/><stop offset="1" stop-color="{INDIGO}" stop-opacity="0"/></linearGradient>
  </defs>
  <style>.p{{animation:p 2.4s ease-in-out infinite}}@keyframes p{{0%,100%{{opacity:.35}}50%{{opacity:1}}}}</style>
  <rect x="140" y="40" width="1000" height="1.5" fill="url(#fadeL)"/>
  <g transform="translate(640 41)">
    <rect x="-9" y="-9" width="18" height="18" rx="4" transform="rotate(45)" fill="#070a12" stroke="url(#brand)" stroke-width="2"/>
    <rect x="-3.5" y="-3.5" width="7" height="7" rx="1.5" transform="rotate(45)" fill="{CYAN}" class="p"/>
  </g>
  <text x="640" y="96" text-anchor="middle" font-family="{MONO}" font-size="20" fill="{MUTED}" letter-spacing=".5">“in code we trust, <tspan fill="url(#brand)" font-weight="700">in markets we hunt</tspan>”</text>
  <text x="640" y="128" text-anchor="middle" font-family="{MONO}" font-size="13" fill="#3b4a66" letter-spacing="3">BUILT IN INDONESIA · SHIPPED ON-CHAIN</text>
</svg>"""
    write("footer.svg", svg)


if __name__ == "__main__":
    write("header.svg", header())
    for s in [("about", "01", "About"), ("work", "02", "Selected Work"), ("stack", "03", "Stack"),
              ("activity", "04", "Activity"), ("connect", "05", "Connect")]:
        section(*s)
    card("dollarkilat", "01", "Solana · Payments", "DollarKilat",
         ["Get paid in USDC, spend anywhere via QRIS.", "PWA for Indonesian freelancers — Colosseum", "Frontier 2026 hackathon build."],
         ["Solana", "Next.js", "TypeScript", "QRIS"], CYAN, status="LIVE")
    card("polymarket-btc", "02", "Quant · ML", "Polymarket BTC 15m",
         ["XGBoost + LightGBM ensemble trading BTC", "binary markets — drift detection, auto-retrain,", "Telegram alerts, live React dashboard."],
         ["TypeScript", "XGBoost", "LightGBM", "React"], MINT)
    card("anyaman", "03", "Media · Full-stack", "Anyaman",
         ["Peace-journalism portal with moderated", "discussion and AI-assisted article workflows.", "Next.js 15 · Supabase · Prisma · Auth.js."],
         ["Next.js", "Postgres", "Prisma", "Auth.js"], VIOLET, status="LIVE")
    card("hybrid-bot", "04", "Automation", "Polymarket Hybrid Bot",
         ["Automated execution for BTC 15-minute", "markets — research loop, entry logic and", "practical live signal testing."],
         ["Python", "CLOB API", "Signals"], INDIGO)
    card("crypto-suite", "05", "Education · Security", "Crypto Suite",
         ["19 cipher algorithms, classical to modern,", "with interactive visualizations, real-time", "analytics and step-by-step guides."],
         ["React", "JavaScript", "Cryptography"], ROSE)
    card("simple-web3", "06", "Web3 · EVM", "Simple Web3 Web",
         ["Ethereum + Base on-chain explorer surface", "with Privy login — readable blockchain", "data for people new to Web3."],
         ["JavaScript", "Ethereum", "Base", "Privy"], "#60a5fa")
    stack()
    footer()
