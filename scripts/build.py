#!/usr/bin/env python3
"""Builds every image on the masterputra169 profile README.

Runs hourly in GitHub Actions (.github/workflows/build.yml) and writes into --out:
  header-{dark,light}.svg     live BTC/USD 15m panel (Coinbase → Kraken → cache)
  stats-{dark,light}.svg      GitHub activity card (GraphQL → cache)
  card-*-{dark,light}.svg     project cards
  stack-, section-*, footer-  static pieces
  data/btc.json, data/stats.json   last good data, reused when an API fails

Fonts (Inter + JetBrains Mono) are pulled from Google Fonts, subset to the exact
characters each SVG uses, and embedded as base64, so text renders identically on
every OS. Without network the SVGs fall back to the system font stack.

Local preview:  python3 scripts/build.py --out dist --mock
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import io
import json
import logging
import math
import os
import random
import re
import sys
import urllib.request
from pathlib import Path

USER = "masterputra169"
REPO = f"{USER}/{USER}"
CACHE_BASE = f"https://raw.githubusercontent.com/{REPO}/output/data"
WIB = dt.timezone(dt.timedelta(hours=7))
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
# Repos to leave out of the language breakdown (comma-separated names), e.g. copies of other people's code.
EXCLUDE_REPOS = {r.strip() for r in os.environ.get("EXCLUDE_REPOS", "").split(",") if r.strip()}

# ── themes ───────────────────────────────────────────────────────────────────
logging.getLogger("fontTools").setLevel(logging.ERROR)

THEMES = {
    "dark": dict(
        bg1="#070a12", bg2="#0a0f1e", panel="#0c1222", chip="#070a12", line="#1c2740", dots="#1a2338",
        muted="#64748b", dim="#3b4a66", text="#cbd5e1", bright="#f1f5f9",
        cyan="#22d3ee", indigo="#818cf8", violet="#c084fc", mint="#34d399", rose="#fb7185", blue="#60a5fa",
        glow=0.20, panel_op=0.88,
    ),
    "light": dict(
        bg1="#ffffff", bg2="#f3f6fb", panel="#ffffff", chip="#f6f8fc", line="#dfe5ef", dots="#dde3ee",
        muted="#64748b", dim="#94a3b8", text="#334155", bright="#0f172a",
        cyan="#0891b2", indigo="#4f46e5", violet="#9333ea", mint="#059669", rose="#e11d48", blue="#2563eb",
        glow=0.10, panel_op=0.94,
    ),
}
SANS = "MPSans,'Inter','Segoe UI',-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif"
MONO = "MPMono,'JetBrains Mono','SFMono-Regular',ui-monospace,Menlo,Consolas,monospace"


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def log(*a):
    print("[build]", *a, file=sys.stderr)


def http(url: str, headers: dict | None = None, data: bytes | None = None, timeout=20) -> bytes:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ── fonts ────────────────────────────────────────────────────────────────────
class Fonts:
    """Downloads Inter + JetBrains Mono once, subsets per SVG, measures text."""

    GOOGLE = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800"
              "&family=JetBrains+Mono:wght@400;500;700&display=swap")
    LOCAL = {  # used for metrics (and embedding) when Google Fonts is unreachable
        "sans": ["/usr/share/fonts/opentype/inter/Inter-Medium.otf", "/usr/share/fonts/truetype/inter/Inter-Medium.ttf"],
    }

    def __init__(self, offline: bool, local: bool = False):
        self.faces: list[dict] = []  # {family, weights:(lo,hi), data:bytes}
        self.metric_font = None
        try:
            import brotli  # noqa: F401  (needed for woff2)
            self.flavor = "woff2"
        except ImportError:
            self.flavor = "woff"
        if not offline:
            try:
                self._google()
            except Exception as e:  # noqa: BLE001
                log("google fonts unavailable:", e)
        if local and not self.faces:
            self._local()
        self._init_metrics()
        log(f"fonts: {len(self.faces)} faces, flavor={self.flavor}")

    def _google(self):
        css = http(self.GOOGLE).decode()
        blocks = re.findall(r"/\*\s*latin\s*\*/\s*@font-face\s*{([^}]*)}", css)
        by_url: dict[tuple[str, str], list[int]] = {}
        for b in blocks:
            fam = re.search(r"font-family:\s*'([^']+)'", b).group(1)
            w = int(re.search(r"font-weight:\s*(\d+)", b).group(1))
            url = re.search(r"url\(([^)]+)\)", b).group(1)
            by_url.setdefault((fam, url), []).append(w)
        for (fam, url), ws in by_url.items():
            self.faces.append(dict(family="MPSans" if fam == "Inter" else "MPMono",
                                   weights=(min(ws), max(ws) if len(ws) > 1 else min(ws)),
                                   variable=len(ws) > 1, data=http(url)))

    def _local(self):
        """Test path: embed locally installed fonts (Inter + DejaVu Sans Mono stand-in)."""
        base = "/usr/share/fonts"
        for fam, w, p in [("MPSans", 400, "opentype/inter/Inter-Regular.otf"), ("MPSans", 500, "opentype/inter/Inter-Medium.otf"),
                          ("MPSans", 700, "opentype/inter/Inter-Bold.otf"), ("MPSans", 800, "opentype/inter/Inter-ExtraBold.otf"),
                          ("MPMono", 400, "truetype/dejavu/DejaVuSansMono.ttf"), ("MPMono", 700, "truetype/dejavu/DejaVuSansMono-Bold.ttf")]:
            fp = Path(base) / p
            if fp.exists():
                self.faces.append(dict(family=fam, weights=(w, w), variable=False, data=fp.read_bytes()))

    def _init_metrics(self):
        from fontTools.ttLib import TTFont
        for f in self.faces:
            if f["family"] == "MPSans":
                try:
                    self.metric_font = TTFont(io.BytesIO(f["data"]))
                    return
                except Exception as e:  # noqa: BLE001
                    log("metric font from google failed:", e)
        for p in self.LOCAL["sans"]:
            if os.path.exists(p):
                self.metric_font = TTFont(p)
                return

    def width(self, text: str, size: float, mono=False, weight=500) -> float:
        if mono:
            return len(text) * 0.6 * size
        f = self.metric_font
        if f is None:
            return len(text) * 0.56 * size
        cmap, hmtx, upm = f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm
        w = sum(hmtx[cmap.get(ord(ch), cmap.get(32))][0] if cmap.get(ord(ch)) else upm * 0.5 for ch in text)
        bold = 1 + max(0, weight - 500) / 3000  # variable default is 400–500; widen bolds slightly
        return w / upm * size * bold

    def css(self, chars: str) -> str:
        if not self.faces:
            return ""
        from fontTools import subset
        out = []
        text = "".join(sorted(set(chars + " ")))
        for f in self.faces:
            opts = subset.Options()
            opts.flavor = self.flavor
            opts.layout_features = ["kern", "liga", "calt", "tnum", "case"]
            opts.name_IDs = []
            opts.notdef_outline = False
            fnt = subset.load_font(io.BytesIO(f["data"]), opts)
            sub = subset.Subsetter(opts)
            sub.populate(text=text)
            sub.subset(fnt)
            buf = io.BytesIO()
            subset.save_font(fnt, buf, opts)
            b64 = base64.b64encode(buf.getvalue()).decode()
            lo, hi = f["weights"]
            weight = f"{lo} {hi}" if f["variable"] else str(lo)
            out.append(f"@font-face{{font-family:{f['family']};font-weight:{weight};"
                       f"src:url(data:font/{self.flavor};base64,{b64}) format('{self.flavor}')}}")
        return "".join(out)


FONTS: Fonts  # set in main()


def svg_doc(w: int, h: int, label: str, body: str, style: str = "", defs: str = "") -> str:
    """Wraps body in an <svg>, embedding only the glyphs that appear in its text."""
    texts = re.findall(r">([^<>]+)<", body)
    chars = html.unescape("".join(texts))
    font_css = FONTS.css(chars)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{esc(label)}"><title>{esc(label)}</title>'
            f"<defs>{defs}</defs><style>{font_css}.s{{font-family:{SANS}}}.m{{font-family:{MONO}}}{style}"
            f"@media (prefers-reduced-motion:reduce){{*{{animation:none!important;opacity:1!important;"
            f"stroke-dashoffset:0!important}}}}</style>{body}</svg>\n")


def brand_grad(t, gid="brand"):
    return (f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{t["cyan"]}"/>'
            f'<stop offset=".55" stop-color="{t["indigo"]}"/><stop offset="1" stop-color="{t["violet"]}"/></linearGradient>')


def chip_w(text, size, mono, pad):
    return round(FONTS.width(text, size, mono) + pad * 2)


# ── data: BTC ────────────────────────────────────────────────────────────────
def fetch_btc() -> dict | None:
    """Last 24 × 15m BTC/USD candles as [t, o, h, l, c]."""
    try:
        rows = json.loads(http("https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=900"))
        rows = sorted(rows, key=lambda r: r[0])[-25:]  # [time, low, high, open, close, vol]
        return {"source": "COINBASE", "candles": [[r[0], r[3], r[2], r[1], r[4]] for r in rows]}
    except Exception as e:  # noqa: BLE001
        log("coinbase failed:", e)
    try:
        j = json.loads(http("https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=15"))
        key = next(k for k in j["result"] if k != "last")
        rows = j["result"][key][-25:]
        return {"source": "KRAKEN", "candles": [[int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])] for r in rows]}
    except Exception as e:  # noqa: BLE001
        log("kraken failed:", e)
    return None


def demo_btc() -> dict:
    rnd = random.Random(169)
    t0 = int(dt.datetime(2026, 10, 11, 8, tzinfo=dt.timezone.utc).timestamp())
    p, rows = 62000.0, []
    for i in range(25):
        o = p
        c = o + rnd.gauss(25, 90)
        rows.append([t0 + i * 900, o, max(o, c) + abs(rnd.gauss(0, 40)), min(o, c) - abs(rnd.gauss(0, 40)), c])
        p = c
    return {"source": "DEMO", "candles": rows}


# ── data: GitHub stats ───────────────────────────────────────────────────────
def gql(query: str, variables: dict) -> dict:
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not tok:
        raise RuntimeError("no GH_TOKEN")
    raw = http("https://api.github.com/graphql", {"Authorization": f"bearer {tok}", "Content-Type": "application/json"},
               json.dumps({"query": query, "variables": variables}).encode(), timeout=40)
    j = json.loads(raw)
    if j.get("errors"):
        raise RuntimeError(j["errors"])
    return j["data"]


def fetch_stats() -> dict | None:
    try:
        u = gql("""query($l:String!){user(login:$l){createdAt followers{totalCount}
          repositories(ownerAffiliations:OWNER,isFork:false,first:100,privacy:PUBLIC){totalCount nodes{name stargazerCount
            languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}}}}}""", {"l": USER})["user"]
        created = dt.datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00"))
        now = dt.datetime.now(dt.timezone.utc)
        parts = []
        for y in range(created.year, now.year + 1):
            frm = max(created, dt.datetime(y, 1, 1, tzinfo=dt.timezone.utc))
            to = min(now, dt.datetime(y, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc))
            parts.append(f'y{y}:contributionsCollection(from:"{frm.isoformat()}",to:"{to.isoformat()}")'
                         "{contributionCalendar{weeks{contributionDays{date contributionCount}}}}")
        cal = gql("query($l:String!){user(login:$l){" + " ".join(parts) + "}}", {"l": USER})["user"]
        days = {}
        for v in cal.values():
            for w in v["contributionCalendar"]["weeks"]:
                for d in w["contributionDays"]:
                    days[d["date"]] = d["contributionCount"]
        langs: dict[str, int] = {}
        stars = 0
        for r in u["repositories"]["nodes"]:
            stars += r["stargazerCount"]
            if r["name"] in EXCLUDE_REPOS:
                continue
            for e in r["languages"]["edges"]:
                langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
        return {"created": u["createdAt"], "followers": u["followers"]["totalCount"], "repos": u["repositories"]["totalCount"],
                "stars": stars, "langs": langs, "days": dict(sorted(days.items())), "fetched": now.isoformat()}
    except Exception as e:  # noqa: BLE001
        log("github stats failed:", e)
        return None


def mock_stats() -> dict:
    rnd = random.Random(7)
    start = dt.date(2025, 10, 12)
    days = {}
    for i in range(365):
        d = start + dt.timedelta(days=i)
        days[d.isoformat()] = 0 if rnd.random() < 0.45 else int(rnd.expovariate(0.25))
    for i in range(4):
        days[(dt.date(2026, 10, 11) - dt.timedelta(days=i)).isoformat()] = 3 + i
    return {"created": "2023-05-16T00:00:00Z", "followers": 5, "repos": 19, "stars": 6,
            "langs": {"TypeScript": 900, "JavaScript": 700, "Python": 420, "Rust": 90, "CSS": 120, "HTML": 60},
            "days": days, "fetched": "2026-10-11T14:00:00+00:00"}


def cached(name: str) -> dict | None:
    try:
        return json.loads(http(f"{CACHE_BASE}/{name}"))
    except Exception as e:  # noqa: BLE001
        log(f"no cache for {name}:", e)
        return None


def streaks(days: dict[str, int]):
    ds = sorted(days)
    best = (0, None, None)
    run, run_start = 0, None
    for d in ds:
        if days[d] > 0:
            run_start = run_start or d
            run += 1
            if run > best[0]:
                best = (run, run_start, d)
        else:
            run, run_start = 0, None
    # current streak: today may still be empty without breaking it
    cur, end = 0, None
    idx = len(ds) - 1
    if idx >= 0 and days[ds[idx]] == 0:
        idx -= 1
    while idx >= 0 and days[ds[idx]] > 0:
        cur += 1
        end = end or ds[idx]
        idx -= 1
    cur_start = ds[idx + 1] if cur else None
    return (cur, cur_start, end), best


def fmt_day(s):
    return dt.date.fromisoformat(s).strftime("%b %-d") if s else "—"


# ── header ───────────────────────────────────────────────────────────────────
def header(t, btc):
    c = btc["candles"][-24:]
    lo_all, hi_all = min(r[3] for r in c), max(r[2] for r in c)
    pad = (hi_all - lo_all) * 0.06 or 1
    lo_all, hi_all = lo_all - pad, hi_all + pad
    top, bot = 150, 292
    y = lambda v: bot - (v - lo_all) / (hi_all - lo_all) * (bot - top)  # noqa: E731
    step, x0, bw = 16.2, 810, 9
    cds, pts, ema = [], [], c[0][4]
    for i, (_, o, h, l, cl) in enumerate(c):
        x = x0 + i * step
        col = t["mint"] if cl >= o else t["rose"]
        bt, bb = y(max(o, cl)), y(min(o, cl))
        cds.append(f'<g class="cd" style="animation-delay:{0.2 + i * 0.045:.2f}s">'
                   f'<line x1="{x + bw / 2:.1f}" y1="{y(h):.1f}" x2="{x + bw / 2:.1f}" y2="{y(l):.1f}" stroke="{col}" stroke-width="1.5"/>'
                   f'<rect x="{x:.1f}" y="{bt:.1f}" width="{bw}" height="{max(bb - bt, 1.6):.1f}" rx="1.5" fill="{col}"/></g>')
        ema += (cl - ema) * (2 / 10)
        pts.append((x + bw / 2, y(ema)))
    path = "M" + " L".join(f"{a:.1f} {b:.1f}" for a, b in pts)
    ex, ey = pts[-1]
    last, first = c[-1][4], c[0][1]
    chg = (last / first - 1) * 100
    chg_col = t["mint"] if chg >= 0 else t["rose"]
    ts = dt.datetime.fromtimestamp(c[-1][0] + 900, dt.timezone.utc).astimezone(WIB)
    live = btc["source"] != "DEMO"
    status = f"{btc['source']} · {ts:%H:%M} WIB" if live else "DEMO DATA"

    chips = ["SOLANA", "EVM · BASE", "PREDICTION MARKETS", "ML SIGNALS"]
    chip_svg, x = [], 72
    for i, s in enumerate(chips):
        w = chip_w(s, 13, True, 18) + len(s) * 1.6
        chip_svg.append(f'<g class="rise" style="animation-delay:{0.85 + i * 0.08:.2f}s"><rect x="{x}" y="344" width="{w:.0f}" height="34" rx="17" fill="{t["chip"]}" stroke="{t["line"]}"/>'
                        f'<text x="{x + w / 2:.1f}" y="366" text-anchor="middle" class="m" font-size="13" letter-spacing="1.6" fill="{t["text"]}">{esc(s)}</text></g>')
        x += w + 10
    blocks = "".join(
        f'<rect x="{806 + i * 80}" y="318" width="58" height="26" rx="6" fill="{t["chip"]}" stroke="{t["line"]}"/>'
        f'<text x="{835 + i * 80}" y="335.5" text-anchor="middle" class="m" font-size="11" fill="{t["muted"]}">{h}</text>'
        f'<rect x="{806 + i * 80}" y="318" width="58" height="26" rx="6" fill="none" stroke="{t["cyan"]}" stroke-opacity="0">'
        f'<animate attributeName="stroke-opacity" values="0;0;.9;0;0" keyTimes="0;{i * .18:.2f};{i * .18 + .06:.2f};{i * .18 + .16:.2f};1" dur="3.2s" repeatCount="indefinite"/></rect>'
        for i, h in enumerate(["0x7a", "0x3f", "0xc1", "0x9e", "0x5d"]))

    defs = f"""<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t['bg1']}"/><stop offset="1" stop-color="{t['bg2']}"/></linearGradient>
<radialGradient id="gC" cx="1010" cy="60" r="520" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="{t['cyan']}" stop-opacity="{t['glow']}"/><stop offset="1" stop-color="{t['cyan']}" stop-opacity="0"/></radialGradient>
<radialGradient id="gV" cx="170" cy="470" r="560" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="{t['violet']}" stop-opacity="{t['glow'] * .9}"/><stop offset="1" stop-color="{t['violet']}" stop-opacity="0"/></radialGradient>
<pattern id="dots" width="26" height="26" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1.1" fill="{t['dots']}"/></pattern>
<linearGradient id="fade" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity=".9"/><stop offset=".6" stop-color="#fff" stop-opacity=".3"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
<mask id="dm"><rect width="1280" height="420" fill="url(#fade)"/></mask>{brand_grad(t)}
<linearGradient id="ef" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t['cyan']}" stop-opacity=".22"/><stop offset="1" stop-color="{t['cyan']}" stop-opacity="0"/></linearGradient>
<clipPath id="fr"><rect width="1280" height="420" rx="26"/></clipPath>"""
    style = (".rise{opacity:0;animation:rise .8s cubic-bezier(.2,.7,.2,1) forwards}"
             ".cd{opacity:0;transform-box:fill-box;transform-origin:50% 100%;animation:grow .5s cubic-bezier(.2,.8,.2,1) forwards}"
             ".ema{stroke-dasharray:600;stroke-dashoffset:600;animation:draw 1.6s 1.3s ease-out forwards}"
             ".ef{opacity:0;animation:show 1s 2.3s forwards}.live{animation:pulse 1.6s ease-in-out infinite}"
             "@keyframes rise{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}"
             "@keyframes grow{from{opacity:0;transform:scaleY(.15)}to{opacity:1;transform:none}}"
             "@keyframes draw{to{stroke-dashoffset:0}}@keyframes show{to{opacity:1}}"
             "@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}")
    border = f'<rect x=".5" y=".5" width="1279" height="419" rx="26" fill="none" stroke="{t["line"]}"/>' if t is THEMES["light"] else ""
    body = f"""<g clip-path="url(#fr)">
<rect width="1280" height="420" fill="url(#bg)"/><rect width="1280" height="420" fill="url(#dots)" mask="url(#dm)"/>
<rect width="1280" height="420" fill="url(#gC)"/><rect width="1280" height="420" fill="url(#gV)"/>
<g class="rise" style="animation-delay:.05s"><text x="72" y="96" class="m" font-size="19"><tspan fill="{t['cyan']}">~/masterputra</tspan><tspan fill="{t['muted']}"> $ whoami</tspan></text></g>
<g class="rise" style="animation-delay:.2s"><text x="67" y="206" class="s" font-size="106" font-weight="800" letter-spacing="-4.5" fill="url(#brand)">MasterPutra</text></g>
<g class="rise" style="animation-delay:.38s"><text x="72" y="258" class="s" font-size="29" font-weight="500" fill="{t['text']}">Web3 Developer <tspan fill="{t['dim']}">·</tspan> dApp Builder <tspan fill="{t['dim']}">·</tspan> Quant Builder</text></g>
<g class="rise" style="animation-delay:.55s"><text x="72" y="306" class="m" font-size="18" fill="{t['muted']}"><tspan fill="{t['mint']}">❯</tspan> shipping on-chain products for real users <tspan fill="{t['cyan']}">▋<animate attributeName="fill-opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1.05s" repeatCount="indefinite"/></tspan></text></g>
{''.join(chip_svg)}
<g class="rise" style="animation-delay:.1s">
<rect x="782" y="56" width="440" height="308" rx="18" fill="{t['panel']}" fill-opacity="{t['panel_op']}" stroke="{t['line']}"/>
<text x="806" y="88" class="m" font-size="12.5" letter-spacing="1.2" fill="{t['muted']}"><tspan fill="{t['bright']}" font-weight="700">BTC/USD</tspan> · 15M</text>
<circle cx="{1198 - FONTS.width(status, 11.5, True) - status.count(' ') * 0 - len(status) * 1.2 - 12:.1f}" cy="84" r="4" fill="{t['mint'] if live else t['muted']}" class="live"/>
<text x="1198" y="88" text-anchor="end" class="m" font-size="11.5" letter-spacing="1.2" fill="{t['muted']}">{esc(status)}</text>
<text x="805" y="128" class="s" font-size="30" font-weight="700" letter-spacing="-.6" fill="{t['bright']}" style="font-variant-numeric:tabular-nums">${last:,.0f}</text>
<text x="{805 + FONTS.width(f'${last:,.0f}', 30, weight=700) + 14:.1f}" y="127" class="m" font-size="14" font-weight="700" fill="{chg_col}">{'+' if chg >= 0 else ''}{chg:.2f}%<tspan fill="{t['muted']}" font-weight="400"> 6H</tspan></text>
<text x="1198" y="127" text-anchor="end" class="m" font-size="11" fill="{t['muted']}" letter-spacing="1"><tspan fill="{t['cyan']}">━</tspan> EMA 9</text>
<g stroke="{t['line']}" stroke-dasharray="3 6"><line x1="802" y1="150" x2="1202" y2="150"/><line x1="802" y1="197" x2="1202" y2="197"/><line x1="802" y1="244" x2="1202" y2="244"/><line x1="802" y1="292" x2="1202" y2="292"/></g>
<path class="ef" d="{path} L{ex:.1f} 292 L{pts[0][0]:.1f} 292 Z" fill="url(#ef)"/>
{''.join(cds)}
<path class="ema" d="{path}" fill="none" stroke="{t['cyan']}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="{ex:.1f}" cy="{ey:.1f}" r="4.5" fill="{t['cyan']}" class="live"/>
<line x1="835" y1="331" x2="1155" y2="331" stroke="{t['line']}" stroke-width="2"/>{blocks}
<circle r="3.5" fill="{t['cyan']}"><animateMotion dur="3.2s" repeatCount="indefinite" path="M835 331 L1155 331"/></circle>
</g>
<rect x="0" y="416" width="1280" height="4" fill="url(#brand)" opacity=".85"/></g>{border}"""
    label = f"MasterPutra — Web3 Developer · dApp Builder · Quant Builder. BTC/USD ${last:,.0f} ({chg:+.2f}% 6h)"
    return svg_doc(1280, 420, label, body, style, defs)


# ── section title ────────────────────────────────────────────────────────────
def section(t, idx, title):
    tw = FONTS.width(title, 30, weight=700)
    defs = brand_grad(t) + (f'<linearGradient id="rule" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{t["indigo"]}" stop-opacity=".6"/>'
                            f'<stop offset="1" stop-color="{t["indigo"]}" stop-opacity="0"/></linearGradient>')
    body = (f'<text x="6" y="42" class="m" font-size="17" fill="{t["cyan"]}" letter-spacing="2">{idx}</text>'
            f'<text x="50" y="44" class="s" font-size="30" font-weight="700" fill="url(#brand)" letter-spacing="-.6">{esc(title)}</text>'
            f'<rect x="{50 + tw + 22:.0f}" y="34" width="1280" height="1.5" fill="url(#rule)"/>')
    return svg_doc(1280, 64, title, body, defs=defs)


# ── cards ────────────────────────────────────────────────────────────────────
def _tags(t, tags, x, y, accent, size=15):
    out = []
    for s in tags:
        w = chip_w(s, size, True, 15)
        out.append(f'<rect x="{x:.0f}" y="{y}" width="{w}" height="32" rx="16" fill="{accent}" fill-opacity=".09" stroke="{accent}" stroke-opacity=".38"/>'
                   f'<text x="{x + w / 2:.1f}" y="{y + 21.5}" text-anchor="middle" class="m" font-size="{size}" fill="{t["text"]}">{esc(s)}</text>')
        x += w + 10
    return "".join(out), x


def _badge(t, label, right_x, y):
    w = chip_w(label, 12, True, 14) + 18 + len(label) * 1
    x = right_x - w
    return (f'<g transform="translate({x:.0f} {y})"><rect width="{w:.0f}" height="28" rx="14" fill="{t["mint"]}" fill-opacity=".1" stroke="{t["mint"]}" stroke-opacity=".45"/>'
            f'<circle cx="15" cy="14" r="3.6" fill="{t["mint"]}"><animate attributeName="opacity" values="1;.25;1" dur="1.6s" repeatCount="indefinite"/></circle>'
            f'<text x="{(w + 14) / 2:.1f}" y="18.5" text-anchor="middle" class="m" font-size="12" fill="{t["mint"]}" letter-spacing="1">{esc(label)}</text></g>'), x


def _card_shell(t, W, H, accent):
    defs = (f'<linearGradient id="edge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{accent}" stop-opacity=".8"/>'
            f'<stop offset=".45" stop-color="{t["line"]}"/><stop offset="1" stop-color="{t["line"]}"/></linearGradient>'
            f'<radialGradient id="glow" cx="{W}" cy="0" r="{W * .62:.0f}" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="{accent}" stop-opacity="{t["glow"] * .85:.2f}"/>'
            f'<stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>'
            f'<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="{t["dots"]}"/></pattern>'
            f'<clipPath id="c"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="22"/></clipPath>')
    body = (f'<g clip-path="url(#c)"><rect width="{W}" height="{H}" fill="{t["panel"]}"/><rect width="{W}" height="{H}" fill="url(#dots)" opacity=".7"/>'
            f'<rect width="{W}" height="{H}" fill="url(#glow)"/><rect width="5" height="{H}" fill="{accent}"/></g>'
            f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="22" fill="none" stroke="url(#edge)" stroke-width="1.5"/>')
    return defs, body


def _arrow(t, x, y):
    return (f'<g transform="translate({x} {y})"><rect width="32" height="32" rx="10" fill="{t["chip"]}" stroke="{t["line"]}"/>'
            f'<path d="M12 20 L20 12 M13.5 12 H20 V18.5" fill="none" stroke="{t["text"]}" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></g>')


def card(t, p):
    W, H = 640, 330
    accent = t[p["accent"]]
    defs, shell = _card_shell(t, W, H, accent)
    badge, bx = _badge(t, p["status"], W - 82, 36) if p.get("status") else ("", W - 82)
    desc = "".join(f'<tspan x="38" dy="{0 if i == 0 else 31}">{esc(s)}</tspan>' for i, s in enumerate(p["lines"]))
    tags, _ = _tags(t, p["tags"], 38, 262, accent)
    body = (shell + f'<text x="38" y="56" class="m" font-size="14" letter-spacing="2"><tspan fill="{accent}">{p["idx"]}</tspan>'
            f'<tspan fill="{t["muted"]}">  /  {esc(p["kind"].upper())}</tspan></text>{badge}{_arrow(t, W - 70, 34)}'
            f'<text x="36" y="118" class="s" font-size="40" font-weight="700" fill="{t["bright"]}" letter-spacing="-1">{esc(p["title"])}</text>'
            f'<text x="38" y="164" class="s" font-size="22" fill="{t["text"]}">{desc}</text>{tags}')
    return svg_doc(W, H, f'{p["title"]} — {" ".join(p["lines"])}', body, defs=defs)


def featured(t, p):
    """Full-width DollarKilat card with a USDC → Solana → QRIS flow."""
    W, H = 1280, 360
    accent = t["cyan"]
    defs, shell = _card_shell(t, W, H, accent)
    badge, _ = _badge(t, "LIVE · dollarkilat.xyz", W - 86, 38)
    desc = "".join(f'<tspan x="40" dy="{0 if i == 0 else 34}">{esc(s)}</tspan>' for i, s in enumerate(p["lines"]))
    tags, _ = _tags(t, p["tags"], 40, 290, accent, 15)
    nodes = [("USDC", "client pays", t["blue"]), ("SOLANA", "settles < 1s", t["violet"]), ("QRIS", "spend in IDR", t["mint"])]
    nx, ny, cy, step = 756, 160, 208, 170
    # travelling dot is drawn first so the (opaque) nodes sit on top of it
    flow = [f'<path d="M{nx + 64} {cy} H{nx + 2 * step + 64}" stroke="{t["line"]}" stroke-width="2" stroke-dasharray="2 6"/>'
            f'<circle r="5" fill="{accent}"><animateMotion dur="2.8s" repeatCount="indefinite" path="M{nx + 64} {cy} H{nx + 2 * step + 64}"/>'
            f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.1;.9;1" dur="2.8s" repeatCount="indefinite"/></circle>']
    for i, (n, sub, col) in enumerate(nodes):
        x = nx + i * step
        flow.append(f'<g class="rise" style="animation-delay:{.3 + i * .15:.2f}s"><rect x="{x}" y="{ny}" width="128" height="96" rx="16" fill="{t["chip"]}" stroke="{col}" stroke-opacity=".6"/>'
                    f'<circle cx="{x + 24}" cy="{ny + 29}" r="6" fill="{col}"/>'
                    f'<text x="{x + 38}" y="{ny + 34}" class="m" font-size="15" font-weight="700" fill="{t["bright"]}" letter-spacing="1">{n}</text>'
                    f'<text x="{x + 18}" y="{ny + 72}" class="s" font-size="15" fill="{t["muted"]}">{esc(sub)}</text></g>')
        if i < 2:
            ax = x + 128
            flow.append(f'<path d="M{ax + 18} {cy - 6} L{ax + 25} {cy} L{ax + 18} {cy + 6}" fill="none" stroke="{t["dim"]}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')
    flow_bg = f'<rect x="732" y="110" width="512" height="172" rx="20" fill="{t["panel"]}" fill-opacity=".6" stroke="{t["line"]}" stroke-dasharray="4 6"/>'
    style = ".rise{opacity:0;animation:rise .7s ease-out forwards}@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}"
    body = (shell + f'<text x="40" y="60" class="m" font-size="14" letter-spacing="2"><tspan fill="{accent}">01</tspan>'
            f'<tspan fill="{t["muted"]}">  /  FEATURED  ·  SOLANA PAYMENTS</tspan></text>{badge}{_arrow(t, W - 72, 36)}'
            f'<text x="38" y="138" class="s" font-size="58" font-weight="800" fill="{t["bright"]}" letter-spacing="-2">{esc(p["title"])}</text>'
            f'<text x="40" y="190" class="s" font-size="24" fill="{t["text"]}">{desc}</text>{tags}'
            f'{flow_bg}<text x="756" y="140" class="m" font-size="12" fill="{t["muted"]}" letter-spacing="2">HOW IT WORKS</text>{"".join(flow)}')
    return svg_doc(W, H, f'{p["title"]} — {" ".join(p["lines"])}', body, style, defs)


# ── stack ────────────────────────────────────────────────────────────────────
STACK = [
    ("LANGUAGES", "cyan", ["TypeScript", "JavaScript", "Python", "Solidity", "SQL"]),
    ("PRODUCT", "blue", ["Next.js", "React", "Tailwind", "Node.js", "Express", "Laravel", "Vercel"]),
    ("DATA · INFRA", "indigo", ["PostgreSQL", "Prisma", "Supabase", "MongoDB", "Redis", "Firebase", "Docker", "Cloudflare"]),
    ("WEB3", "violet", ["Solana", "EVM · Base", "Hardhat", "Privy", "Wallet UX", "IPFS"]),
    ("MARKETS", "mint", ["Polymarket CLOB", "Hyperliquid", "Kelly sizing", "Backtesting", "Telegram alerts"]),
    ("ML", "rose", ["XGBoost", "LightGBM", "LSTM", "Pandas", "NumPy", "Drift detection"]),
]


def stack(t):
    W, row_h = 1280, 58
    H = 40 + row_h * len(STACK)
    out = []
    for r, (label, key, items) in enumerate(STACK):
        y = 26 + r * row_h
        col = t[key]
        out.append(f'<circle cx="42" cy="{y + 17}" r="4" fill="{col}"/><text x="58" y="{y + 22}" class="m" font-size="13.5" letter-spacing="2.2" fill="{col}">{label}</text>')
        x = 236
        for s in items:
            w = chip_w(s, 16, False, 16)
            if x + w > W - 32:
                raise ValueError(f"stack row {label} overflows")
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="34" rx="10" fill="{t["chip"]}" stroke="{t["line"]}"/>'
                       f'<text x="{x + w / 2:.1f}" y="{y + 22.5}" text-anchor="middle" class="s" font-size="16" font-weight="500" fill="{t["text"]}">{esc(s)}</text>')
            x += w + 10
    defs = f'<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="{t["dots"]}"/></pattern>'
    body = (f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="22" fill="{t["panel"]}" stroke="{t["line"]}"/>'
            f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="22" fill="url(#dots)" opacity=".55"/>'
            f'<line x1="212" y1="28" x2="212" y2="{H - 28}" stroke="{t["line"]}"/>' + "".join(out))
    alt = " · ".join(f"{l}: {', '.join(i)}" for l, _, i in STACK)
    return svg_doc(W, H, alt, body, defs=defs)


# ── stats ────────────────────────────────────────────────────────────────────
def stats_card(t, s):
    W, H = 1280, 360
    (cur, cs, ce), (best, bs, be) = streaks(s["days"])
    total = sum(s["days"].values())
    since = dt.datetime.fromisoformat(s["created"].replace("Z", "+00:00")).strftime("%b %Y")
    kpis = [
        ("CONTRIBUTIONS", f"{total:,}", f"since {since}", t["cyan"]),
        ("CURRENT STREAK", f"{cur}", f"{fmt_day(cs)} – {fmt_day(ce)}" if cur else "start one today", t["mint"]),
        ("LONGEST STREAK", f"{best}", f"{fmt_day(bs)} – {fmt_day(be)}" if best else "—", t["violet"]),
        ("STARS EARNED", f"{s['stars']}", f"across {s['repos']} public repos", t["indigo"]),
    ]
    out = []
    tw, gap, x0 = 287, 12, 40
    for i, (lab, val, sub, col) in enumerate(kpis):
        x = x0 + i * (tw + gap)
        unit = " days" if "STREAK" in lab else ""
        vw = FONTS.width(val, 46, weight=800)
        out.append(f'<g class="rise" style="animation-delay:{.1 + i * .08:.2f}s"><rect x="{x}" y="72" width="{tw}" height="112" rx="16" fill="{t["chip"]}" stroke="{t["line"]}"/>'
                   f'<rect x="{x}" y="72" width="{tw}" height="3" rx="1.5" fill="{col}" opacity=".9"/>'
                   f'<text x="{x + 22}" y="104" class="m" font-size="12" letter-spacing="1.8" fill="{t["muted"]}">{lab}</text>'
                   f'<text x="{x + 20}" y="152" class="s" font-size="46" font-weight="800" letter-spacing="-1.5" fill="{t["bright"]}">{val}'
                   f'<tspan class="m" font-size="15" font-weight="400" letter-spacing="0" fill="{t["muted"]}">{unit}</tspan></text>'
                   f'<text x="{x + 22}" y="172" class="s" font-size="13.5" fill="{t["muted"]}">{esc(sub)}</text></g>')
    # 52-week activity bars
    ds = sorted(s["days"])[-364:]
    weeks = [sum(s["days"][d] for d in ds[i:i + 7]) for i in range(0, len(ds), 7)]
    mx = max(weeks) or 1
    bx, by, bh = 40, 322, 82
    bars = []
    for i, v in enumerate(weeks):
        h = max(3, v / mx * bh)
        bars.append(f'<rect class="bar" style="animation-delay:{.3 + i * .012:.3f}s" x="{bx + i * 13.4:.1f}" y="{by - h:.1f}" width="9.4" height="{h:.1f}" rx="2.5" '
                    f'fill="{"url(#barG)" if v else t["line"]}"/>')
    out.append(f'<text x="40" y="222" class="m" font-size="12" letter-spacing="1.8" fill="{t["muted"]}">52-WEEK ACTIVITY</text>'
               f'<text x="{bx + 52 * 13.4 - 4:.0f}" y="222" text-anchor="end" class="m" font-size="12" fill="{t["muted"]}">peak {mx}/wk</text>' + "".join(bars))
    # languages
    langs = sorted(((k, v) for k, v in s["langs"].items() if k not in ("HTML", "CSS", "SCSS", "Jupyter Notebook")),
                   key=lambda kv: -kv[1])
    tot = sum(v for _, v in langs) or 1
    top = langs[:5]
    other = tot - sum(v for _, v in top)
    if other > 0:
        top.append(("Other", other))
    pal = [t["cyan"], t["indigo"], t["violet"], t["mint"], t["rose"], t["dim"]]
    lx, ly, lw = 800, 244, 440
    seg, x = [], lx
    for i, (k, v) in enumerate(top):
        w = v / tot * lw
        seg.append(f'<rect x="{x:.1f}" y="{ly}" width="{max(w - 2, 1):.1f}" height="12" fill="{pal[i]}"/>')
        x += w
    legend = []
    for i, (k, v) in enumerate(top):
        cx, cy = lx + (i % 2) * 226, ly + 42 + (i // 2) * 28
        legend.append(f'<circle cx="{cx + 5}" cy="{cy - 5}" r="5" fill="{pal[i]}"/><text x="{cx + 18}" y="{cy}" class="s" font-size="15" font-weight="500" fill="{t["text"]}">{esc(k)}'
                      f'<tspan class="m" font-size="13" font-weight="400" fill="{t["muted"]}">  {v / tot * 100:.1f}%</tspan></text>')
    out.append(f'<text x="{lx}" y="222" class="m" font-size="12" letter-spacing="1.8" fill="{t["muted"]}">TOP LANGUAGES</text>'
               f'<clipPath id="lc"><rect x="{lx}" y="{ly}" width="{lw}" height="12" rx="6"/></clipPath><g clip-path="url(#lc)">{"".join(seg)}</g>' + "".join(legend))
    fetched = dt.datetime.fromisoformat(s["fetched"]).astimezone(WIB)
    defs = (f'<linearGradient id="barG" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{t["cyan"]}"/><stop offset="1" stop-color="{t["violet"]}"/></linearGradient>'
            f'<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="{t["dots"]}"/></pattern>')
    style = (".rise{opacity:0;animation:rise .7s ease-out forwards}.bar{transform-box:fill-box;transform-origin:50% 100%;animation:grow .6s ease-out both}"
             "@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}@keyframes grow{from{transform:scaleY(0)}to{transform:none}}")
    body = (f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="22" fill="{t["panel"]}" stroke="{t["line"]}"/>'
            f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="22" fill="url(#dots)" opacity=".5"/>'
            f'<text x="40" y="48" class="m" font-size="13" letter-spacing="2" fill="{t["muted"]}"><tspan fill="{t["bright"]}" font-weight="700">@{USER}</tspan>  ·  GITHUB ACTIVITY</text>'
            f'<text x="1240" y="48" text-anchor="end" class="m" font-size="12" fill="{t["dim"]}" letter-spacing="1">updated {fetched:%d %b %H:%M} WIB</text>'
            f'<line x1="770" y1="210" x2="770" y2="326" stroke="{t["line"]}"/>' + "".join(out))
    label = f"GitHub activity: {total:,} contributions, current streak {cur} days, longest {best} days, {s['stars']} stars"
    return svg_doc(W, H, label, body, style, defs)


# ── footer ───────────────────────────────────────────────────────────────────
def footer(t):
    defs = brand_grad(t) + (f'<linearGradient id="fl" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{t["indigo"]}" stop-opacity="0"/>'
                            f'<stop offset=".5" stop-color="{t["indigo"]}" stop-opacity=".7"/><stop offset="1" stop-color="{t["indigo"]}" stop-opacity="0"/></linearGradient>')
    style = ".p{animation:p 2.4s ease-in-out infinite}@keyframes p{0%,100%{opacity:.35}50%{opacity:1}}"
    body = (f'<rect x="140" y="40" width="1000" height="1.5" fill="url(#fl)"/><g transform="translate(640 41)">'
            f'<rect x="-9" y="-9" width="18" height="18" rx="4" transform="rotate(45)" fill="{t["bg1"]}" stroke="url(#brand)" stroke-width="2"/>'
            f'<rect x="-3.5" y="-3.5" width="7" height="7" rx="1.5" transform="rotate(45)" fill="{t["cyan"]}" class="p"/></g>'
            f'<text x="640" y="98" text-anchor="middle" class="m" font-size="21" fill="{t["muted"]}">“in code we trust, <tspan fill="url(#brand)" font-weight="700">in markets we hunt</tspan>”</text>'
            f'<text x="640" y="130" text-anchor="middle" class="m" font-size="13" fill="{t["dim"]}" letter-spacing="3">BUILT IN INDONESIA · SHIPPED ON-CHAIN</text>')
    return svg_doc(1280, 150, "In code we trust, in markets we hunt", body, style, defs)


# ── content ──────────────────────────────────────────────────────────────────
FEATURED = dict(title="DollarKilat", tags=["Solana", "Next.js", "TypeScript", "PWA", "QRIS"],
                lines=["Get paid in USDC, spend anywhere via QRIS.", "A Solana PWA for Indonesian freelancers,",
                       "built for Colosseum Frontier 2026."])
CARDS = [
    dict(slug="polymarket-btc", idx="02", kind="Quant · ML", title="Polymarket BTC 15m", accent="mint",
         lines=["XGBoost + LightGBM ensemble trading", "BTC 15-min markets: drift detection,", "auto-retrain, live React dashboard."],
         tags=["TypeScript", "XGBoost", "LightGBM"]),
    dict(slug="anyaman", idx="03", kind="Media · Full-stack", title="Anyaman", accent="violet", status="LIVE",
         lines=["Peace-journalism portal with moderated", "discussion and AI-assisted articles.", "Next.js 15 · Supabase · Auth.js."],
         tags=["Next.js", "Postgres", "Prisma"]),
    dict(slug="crypto-suite", idx="04", kind="Education · Security", title="Crypto Suite", accent="rose",
         lines=["19 cipher algorithms, classical to", "modern, with interactive visuals and", "step-by-step guides."],
         tags=["React", "JavaScript", "Crypto"]),
    dict(slug="simple-web3", idx="05", kind="Web3 · EVM", title="Simple Web3 Web", accent="blue",
         lines=["Ethereum + Base on-chain data surface", "with Privy login, readable for people", "new to Web3."],
         tags=["JavaScript", "Ethereum", "Privy"]),
]
SECTIONS = [("about", "01", "About"), ("work", "02", "Selected Work"), ("stack", "03", "Stack"),
            ("activity", "04", "Activity"), ("connect", "05", "Connect")]


def main():
    global FONTS
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    ap.add_argument("--mock", action="store_true", help="offline: demo data, no font download")
    ap.add_argument("--local-fonts", action="store_true", help="embed locally installed fonts (testing)")
    a = ap.parse_args()
    out = Path(a.out)
    (out / "data").mkdir(parents=True, exist_ok=True)
    FONTS = Fonts(offline=a.mock, local=a.local_fonts)

    btc = None if a.mock else fetch_btc()
    btc = btc or (None if a.mock else cached("btc.json")) or demo_btc()
    stats = mock_stats() if a.mock else (fetch_stats() or cached("stats.json") or mock_stats())
    log("btc source:", btc["source"], "| stats fetched:", stats.get("fetched"))
    (out / "data/btc.json").write_text(json.dumps(btc))
    (out / "data/stats.json").write_text(json.dumps(stats))

    files = {}
    for name, t in THEMES.items():
        files[f"header-{name}.svg"] = header(t, btc)
        files[f"stats-{name}.svg"] = stats_card(t, stats)
        files[f"stack-{name}.svg"] = stack(t)
        files[f"footer-{name}.svg"] = footer(t)
        files[f"card-dollarkilat-{name}.svg"] = featured(t, FEATURED)
        for p in CARDS:
            files[f"card-{p['slug']}-{name}.svg"] = card(t, p)
        for slug, idx, title in SECTIONS:
            files[f"section-{slug}-{name}.svg"] = section(t, idx, title)
    for fn, svg in files.items():
        (out / fn).write_text(svg, encoding="utf-8")
    log(f"wrote {len(files)} svgs, {sum(len(v) for v in files.values()) / 1024:.0f} KB total")


if __name__ == "__main__":
    main()
