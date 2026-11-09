#!/usr/bin/env python3
"""Builds every image on the masterputra169 profile README.

Runs every 15 minutes in GitHub Actions (.github/workflows/build.yml) and writes into --out:
  header-{dark,light}[-narrow].svg   live BTC/USD 15m panel (Coinbase → Kraken → cache)
  stats-{dark,light}[-narrow].svg    GitHub activity card (GraphQL → cache)
  card-*-{dark,light}[-narrow].svg   project cards
  stack-, footer-                    static pieces
  connect-*-{dark,light}.svg         48px-tall link buttons

Every big image comes in two layouts: WIDE (960 units) for viewports ≥1012px and
NARROW (480 units) for anything smaller; README.md picks one with <source media>.
Design direction and the reason behind each choice live in DESIGN.md.
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
    # Two core colors (cyan, violet) on a neutral base. Mint and rose only mark price up/down and live status.
    # Every text color clears WCAG AA (4.5:1) on panel, chip and GitHub's page background; dim and the n* tones are for lines and bars only.
    "dark": dict(
        bg1="#070a12", bg2="#0a0f1e", panel="#0c1222", chip="#070a12", line="#1c2740",
        muted="#8b98ad", dim="#3b4a66", text="#cbd5e1", bright="#f1f5f9",
        cyan="#22d3ee", violet="#c084fc", mint="#34d399", mint_text="#34d399", rose="#fb7185",
        n1="#64748b", n2="#334155", panel_op=0.92,
    ),
    "light": dict(
        bg1="#ffffff", bg2="#f3f6fb", panel="#ffffff", chip="#f6f8fc", line="#dfe5ef",
        muted="#5b6b82", dim="#94a3b8", text="#334155", bright="#0f172a",
        cyan="#0e7490", violet="#9333ea", mint="#059669", mint_text="#047857", rose="#be123c",
        n1="#94a3b8", n2="#cbd5e1", panel_op=1.0,
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


def svg_doc(w: float, h: float, label: str, body: str, style: str = "", defs: str = "") -> str:
    """Wraps body in an <svg>, embedding only the glyphs that appear in its text."""
    w, h = round(w), round(h)
    texts = re.findall(r">([^<>]+)<", body)
    chars = html.unescape("".join(texts))
    font_css = FONTS.css(chars)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{esc(label)}"><title>{esc(label)}</title>'
            f"<defs>{defs}</defs><style>{font_css}.s{{font-family:{SANS}}}.m{{font-family:{MONO}}}{style}"
            f"</style>{body}</svg>\n")


# ── layout primitives ────────────────────────────────────────────────────────
# GitHub scales each image to the README width. WIDE is served to viewports ≥1012px (README ≈ 580–870px wide),
# NARROW to smaller ones (README ≈ 310–720px), so either layout is shown at roughly 0.6× to 1.5× its own size.
# At 0.6× a 19-unit label is still ≈11px on screen, which is why nothing below LABEL is ever drawn.
WIDE, NARROW = 960, 480
LABEL, BODY = 19, 22

# MOTION dial 1: no animation. GitHub serves these as <img>, and browsers do not pass prefers-reduced-motion
# into image documents, so the only motion that respects that setting everywhere is none.


def pad_of(W):
    return 28 if W == NARROW else 40


def tw(text, size, weight=500, mono=False):
    return FONTS.width(text, size, mono, weight)


def wrap(text, size, maxw, weight=400, sep=" "):
    """Greedy word wrap using real font metrics."""
    lines, cur = [], ""
    for word in text.split(sep):
        cand = f"{cur}{sep}{word}" if cur else word
        if cur and tw(cand, size, weight) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    return lines + ([cur] if cur else [])


def lines_svg(lines, x, y, size, lh, fill, cls="s", weight=None, anchor=None):
    spans = "".join(f'<tspan x="{x:.0f}" dy="{0 if i == 0 else lh}">{esc(s)}</tspan>' for i, s in enumerate(lines))
    fw = f' font-weight="{weight}"' if weight else ""
    an = f' text-anchor="{anchor}"' if anchor else ""
    return f'<text x="{x:.0f}" y="{y:.0f}" class="{cls}" font-size="{size}"{fw}{an} fill="{fill}">{spans}</text>'


def chips(t, items, x0, y0, maxw, size=LABEL, h=38, gap=10):
    """Flows chips left to right and wraps them inside maxw. Returns (svg, bottom_y)."""
    out, x, y = [], x0, y0
    for s in items:
        w = round(tw(s, size, 500) + 28)
        if x > x0 and x + w > x0 + maxw:
            x, y = x0, y + h + gap
        out.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}" rx="7" fill="{t["chip"]}" stroke="{t["line"]}"/>'
                   f'<text x="{x + w / 2:.1f}" y="{y + h / 2 + size * .36:.1f}" text-anchor="middle" class="s" font-size="{size}" '
                   f'font-weight="500" fill="{t["text"]}">{esc(s)}</text>')
        x += w + gap
    return "".join(out), y + h


def live_badge(t, right_x, y):
    """Marks a project whose site is deployed. Static dot: the state is real, so it needs no animation to be noticed."""
    w = round(tw("Live", LABEL, 600) + 46)
    x = right_x - w
    return (f'<g transform="translate({x} {y})"><rect width="{w}" height="38" rx="7" fill="{t["mint"]}" fill-opacity=".1" '
            f'stroke="{t["mint"]}" stroke-opacity=".5"/><circle cx="17" cy="19" r="4.5" fill="{t["mint"]}"/>'
            f'<text x="30" y="{19 + LABEL * .36:.1f}" class="s" font-size="{LABEL}" font-weight="600" fill="{t["mint_text"]}">Live</text></g>'), x


def arrow(t, x, y):
    """The whole card is a link to its repo; the arrow is the only cue that an image is clickable."""
    return (f'<g transform="translate({x:.0f} {y:.0f})"><rect width="38" height="38" rx="8" fill="{t["chip"]}" stroke="{t["line"]}"/>'
            f'<path d="M14 24 L24 14 M15.5 14 H24 V22.5" fill="none" stroke="{t["text"]}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round"/></g>')


def shell(t, W, H, rx=16):
    return f'<rect x=".75" y=".75" width="{W - 1.5:.1f}" height="{H - 1.5:.1f}" rx="{rx}" fill="{t["panel"]}" stroke="{t["line"]}" stroke-width="1.5"/>'


def brand_grad(t, gid="brand"):
    return (f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{t["cyan"]}"/>'
            f'<stop offset="1" stop-color="{t["violet"]}"/></linearGradient>')


# ── data: BTC ────────────────────────────────────────────────────────────────
def fetch_btc() -> dict | None:
    """Last 24 × 15m BTC/USD candles as [t, o, h, l, c]."""
    try:
        rows = json.loads(http("https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=900"))
        rows = sorted(rows, key=lambda r: r[0])[-25:]  # [time, low, high, open, close, vol]
        return {"source": "COINBASE", "fetched": int(dt.datetime.now(dt.timezone.utc).timestamp()), "candles": [[r[0], r[3], r[2], r[1], r[4]] for r in rows]}
    except Exception as e:  # noqa: BLE001
        log("coinbase failed:", e)
    try:
        j = json.loads(http("https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=15"))
        key = next(k for k in j["result"] if k != "last")
        rows = j["result"][key][-25:]
        return {"source": "KRAKEN", "fetched": int(dt.datetime.now(dt.timezone.utc).timestamp()), "candles": [[int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])] for r in rows]}
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
    return {"demo": True, "created": "2023-05-16T00:00:00Z", "followers": 5, "repos": 19, "stars": 6,
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
    return dt.date.fromisoformat(s).strftime("%b %-d") if s else "n/a"


# ── header ───────────────────────────────────────────────────────────────────
def header(t, btc, W):
    narrow = W == NARROW
    pad = pad_of(W) if narrow else 48
    col = W - 2 * pad if narrow else 452

    # identity block
    name_fs = 76
    while tw("MasterPutra", name_fs, 800) - 10 * name_fs * .04 > col:
        name_fs -= 2
    y = pad + 8 + name_fs * .74
    left = [f'<text x="{pad - 3}" y="{y:.0f}" class="s" font-size="{name_fs}" font-weight="800" '
            f'letter-spacing="{-name_fs * .04:.1f}" fill="url(#brand)">MasterPutra</text>']
    roles = wrap("Web3 Developer · dApp Builder · Quant Builder", 24, col, 500, sep=" · ")
    y += 46
    left.append(lines_svg(roles, pad, y, 24, 33, t["text"], weight=500))
    y += 33 * (len(roles) - 1) + 40
    tagline = wrap("Shipping on-chain products for real users.", BODY, col)
    left.append(lines_svg(tagline, pad, y, BODY, 31, t["muted"]))
    y += 31 * (len(tagline) - 1) + 26
    ch, left_bottom = chips(t, ["Solana", "EVM · Base", "Prediction markets", "ML signals"], pad, y, col)
    left.append(ch)

    # BTC/USD 15m panel
    ph = 322
    if narrow:
        px, py, pw = pad, left_bottom + 32, W - 2 * pad
        H = py + ph + pad
    else:
        px, py, pw = 540, 40, W - 40 - 540
        H = max(py + ph + 40, left_bottom + 48)
        py = (H - ph) / 2
    ix, iw = px + 24, pw - 48
    c = btc["candles"][-24:]
    lo_all, hi_all = min(r[3] for r in c), max(r[2] for r in c)
    rng = (hi_all - lo_all) * 0.06 or 1
    lo_all, hi_all = lo_all - rng, hi_all + rng
    top, bot = py + 112, py + 238
    yv = lambda v: bot - (v - lo_all) / (hi_all - lo_all) * (bot - top)  # noqa: E731
    step = iw / len(c)
    bw = step * .58
    cds, pts, ema = [], [], c[0][4]
    for i, (_, o, h, l, cl) in enumerate(c):
        cx = ix + i * step + step / 2
        col_ = t["mint"] if cl >= o else t["rose"]
        bt, bb = yv(max(o, cl)), yv(min(o, cl))
        cds.append(f'<line x1="{cx:.1f}" y1="{yv(h):.1f}" x2="{cx:.1f}" y2="{yv(l):.1f}" stroke="{col_}" stroke-width="1.5"/>'
                   f'<rect x="{cx - bw / 2:.1f}" y="{bt:.1f}" width="{bw:.1f}" height="{max(bb - bt, 1.6):.1f}" rx="1.5" fill="{col_}"/>')
        ema += (cl - ema) * (2 / 10)
        pts.append((cx, yv(ema)))
    path = "M" + " L".join(f"{a:.1f} {b:.1f}" for a, b in pts)
    ex, ey = pts[-1]
    last, first = c[-1][4], c[0][1]
    chg = (last / first - 1) * 100
    chg_col = t["mint_text"] if chg >= 0 else t["rose"]
    ts = dt.datetime.fromtimestamp(btc.get("fetched", c[-1][0] + 900), dt.timezone.utc).astimezone(WIB)
    live = btc["source"] != "DEMO"
    status = f"{btc['source'].title()} · {ts:%H:%M} WIB" if live else "Demo data, live feed unavailable"
    # real time axis: open time of four candles across the window
    axis = []
    for k, anchor in ((0, "start"), (8, "middle"), (16, "middle"), (len(c) - 1, "end")):
        lbl = dt.datetime.fromtimestamp(c[k][0], dt.timezone.utc).astimezone(WIB).strftime("%H:%M")
        ax = ix if anchor == "start" else ix + iw if anchor == "end" else ix + k * step + step / 2
        axis.append(f'<text x="{ax:.1f}" y="{bot + 30:.0f}" text-anchor="{anchor}" class="m" font-size="{LABEL}" fill="{t["muted"]}">{lbl}</text>')
    price = f"${last:,.0f}"
    grid = "".join(f'<line x1="{ix:.0f}" y1="{gy:.0f}" x2="{ix + iw:.0f}" y2="{gy:.0f}"/>' for gy in (top, (top + bot) / 2, bot))
    panel = f"""
<rect x="{px}" y="{py:.0f}" width="{pw}" height="{ph}" rx="14" fill="{t['panel']}" fill-opacity="{t['panel_op']}" stroke="{t['line']}"/>
<text x="{ix}" y="{py + 40:.0f}" class="m" font-size="{LABEL}" fill="{t['muted']}"><tspan fill="{t['bright']}" font-weight="700">BTC/USD</tspan> · 15m</text>
<text x="{ix + iw}" y="{py + 40:.0f}" text-anchor="end" class="m" font-size="{LABEL}" fill="{t['muted']}"><tspan fill="{t['cyan']}">━</tspan> EMA 9</text>
<text x="{ix - 1}" y="{py + 88:.0f}" class="s" font-size="34" font-weight="700" letter-spacing="-.6" fill="{t['bright']}" style="font-variant-numeric:tabular-nums">{price}</text>
<text x="{ix + tw(price, 34, 700) + 12:.1f}" y="{py + 87:.0f}" class="m" font-size="{LABEL}" font-weight="700" fill="{chg_col}">{'+' if chg >= 0 else ''}{chg:.2f}%<tspan fill="{t['muted']}" font-weight="400"> 6h</tspan></text>
<g stroke="{t['line']}" stroke-dasharray="3 6">{grid}</g>
<path d="{path} L{ex:.1f} {bot:.0f} L{pts[0][0]:.1f} {bot:.0f} Z" fill="url(#ef)"/>
{''.join(cds)}
<path d="{path}" fill="none" stroke="{t['cyan']}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="{ex:.1f}" cy="{ey:.1f}" r="4.5" fill="{t['cyan']}"/>
{''.join(axis)}
<circle cx="{ix + 5}" cy="{py + ph - 30:.0f}" r="4.5" fill="{t['mint'] if live else t['muted']}"/>
<text x="{ix + 18}" y="{py + ph - 23:.0f}" class="m" font-size="{LABEL}" fill="{t['muted']}">{esc(status)}</text>"""
    defs = (f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t["bg1"]}"/>'
            f'<stop offset="1" stop-color="{t["bg2"]}"/></linearGradient>{brand_grad(t)}'
            f'<linearGradient id="ef" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["cyan"]}" stop-opacity=".2"/>'
            f'<stop offset="1" stop-color="{t["cyan"]}" stop-opacity="0"/></linearGradient>')
    body = (f'<rect x=".75" y=".75" width="{W - 1.5}" height="{H - 1.5:.1f}" rx="20" fill="url(#bg)" stroke="{t["line"]}" stroke-width="1.5"/>'
            + "".join(left) + panel)
    label = f"MasterPutra: Web3 Developer, dApp Builder, Quant Builder. BTC/USD {price} ({chg:+.2f}% over 6h)"
    return svg_doc(W, H, label, body, defs=defs)


# ── project cards ────────────────────────────────────────────────────────────
FLOW = [("USDC", "client pays"), ("Solana", "settles in under 1s"), ("QRIS", "spend in IDR")]


def card_top(t, W, pad, kind, status):
    """Meta line on the left, status badge and link arrow on the right. Returns (svg, baseline of meta line)."""
    ax = W - pad - 38
    badge, _ = live_badge(t, ax - 10, pad - 4) if status else ("", ax)
    meta = f'<text x="{pad}" y="{pad + 22}" class="s" font-size="{LABEL}" font-weight="500" fill="{t["muted"]}">{esc(kind)}</text>'
    return meta + badge + arrow(t, ax, pad - 4), pad + 22


def featured(t, p, W):
    """DollarKilat, the project that is live and earning: full width, the only card with a product flow."""
    narrow = W == NARROW
    pad = pad_of(W)
    col = W - 2 * pad if narrow else 440
    top, y = card_top(t, W, pad, p["kind"], p.get("status"))
    y += 62
    out = [top, f'<text x="{pad - 2}" y="{y}" class="s" font-size="46" font-weight="800" letter-spacing="-1.4" fill="{t["bright"]}">{esc(p["title"])}</text>']
    desc = wrap(p["desc"], BODY, col)
    y += 44
    out.append(lines_svg(desc, pad, y, BODY, 32, t["text"]))
    y += 32 * (len(desc) - 1) + 26
    tags, left_bottom = chips(t, p["tags"], pad, y, col)
    out.append(tags)

    if narrow:
        fx, fy, fw = pad, left_bottom + 40, col
    else:
        fx, fy, fw = 520, pad + 72, W - pad - 520
    rows, ry = [f'<text x="{fx}" y="{fy}" class="s" font-size="{LABEL}" font-weight="500" fill="{t["muted"]}">How it works</text>'], fy + 16
    for i, (name, sub) in enumerate(FLOW):
        rows.append(f'<g><rect x="{fx}" y="{ry}" width="{fw}" height="52" rx="10" fill="{t["chip"]}" stroke="{t["line"]}"/>'
                    f'<circle cx="{fx + 22}" cy="{ry + 26}" r="5" fill="{t["cyan"]}"/>'
                    f'<text x="{fx + 38}" y="{ry + 33}" class="m" font-size="{LABEL}" font-weight="700" fill="{t["bright"]}">{name}</text>'
                    f'<text x="{fx + fw - 18}" y="{ry + 33}" text-anchor="end" class="s" font-size="{LABEL}" fill="{t["muted"]}">{esc(sub)}</text></g>')
        ry += 52
        if i < len(FLOW) - 1:
            cx, gy = fx + 22, ry + 12
            rows.append(f'<path d="M{cx - 6} {gy - 3} L{cx} {gy + 3} L{cx + 6} {gy - 3}" fill="none" stroke="{t["muted"]}" '
                        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')
            ry += 24
    out += rows
    H = max(left_bottom, ry) + pad
    return svg_doc(W, H, f'{p["title"]}: {p["desc"]}', shell(t, W, H) + "".join(out))


def card(t, p, W):
    pad = pad_of(W)
    inner = W - 2 * pad
    top, y = card_top(t, W, pad, p["kind"], p.get("status"))
    y += 50
    out = [top, f'<text x="{pad - 1}" y="{y}" class="s" font-size="34" font-weight="700" letter-spacing="-.8" fill="{t["bright"]}">{esc(p["title"])}</text>']
    desc = wrap(p["desc"], BODY, min(inner, 760))
    y += 40
    out.append(lines_svg(desc, pad, y, BODY, 32, t["text"]))
    y += 32 * (len(desc) - 1) + 24
    tags, bottom = chips(t, p["tags"], pad, y, inner)
    out.append(tags)
    H = bottom + pad
    return svg_doc(W, H, f'{p["title"]}: {p["desc"]}', shell(t, W, H) + "".join(out))


# ── stack ────────────────────────────────────────────────────────────────────
STACK = [
    ("Languages", ["TypeScript", "JavaScript", "Python", "Solidity", "SQL"]),
    ("Product", ["Next.js", "React", "Tailwind", "Node.js", "Express", "Laravel", "Vercel"]),
    ("Data · Infra", ["PostgreSQL", "Prisma", "Supabase", "MongoDB", "Redis", "Firebase", "Docker", "Cloudflare"]),
    ("Web3", ["Solana", "EVM · Base", "Hardhat", "Privy", "Wallet UX", "IPFS"]),
    ("Markets", ["Polymarket CLOB", "Hyperliquid", "Kelly sizing", "Backtesting", "Telegram alerts"]),
    ("ML", ["XGBoost", "LightGBM", "LSTM", "Pandas", "NumPy", "Drift detection"]),
]


def stack(t, W):
    narrow = W == NARROW
    pad = pad_of(W)
    label_w = 0 if narrow else 160
    out, y = [], pad
    for label, items in STACK:
        lab = f'<text x="{pad}" y="{y + (LABEL if narrow else 19 + LABEL * .36):.0f}" class="s" font-size="{LABEL}" font-weight="600" fill="{t["muted"]}">{esc(label)}</text>'
        if narrow:
            y += 32
        ch, bottom = chips(t, items, pad + label_w, y, W - 2 * pad - label_w)
        out.append(lab + ch)
        y = bottom + (26 if narrow else 14)
    H = y - (26 if narrow else 14) + pad
    alt = ". ".join(f"{l}: {', '.join(i)}" for l, i in STACK)
    return svg_doc(W, H, alt, shell(t, W, H) + "".join(out))


# ── stats ────────────────────────────────────────────────────────────────────
NON_CODE = {"HTML", "CSS", "SCSS", "Less", "Jupyter Notebook", "Batchfile", "PowerShell", "Shell",
            "Dockerfile", "Makefile", "Procfile", "Hack", "EJS", "Handlebars"}


def stats_card(t, s, W):
    narrow = W == NARROW
    pad = pad_of(W)
    (cur, cs, ce), (best, bs, be) = streaks(s["days"])
    total = sum(s["days"].values())
    since = dt.datetime.fromisoformat(s["created"].replace("Z", "+00:00")).strftime("%b %Y")
    fetched = dt.datetime.fromisoformat(s["fetched"]).astimezone(WIB)
    updated = "Demo data, GitHub API unavailable" if s.get("demo") else f"Updated {fetched:%d %b %H:%M} WIB"
    out = []
    y = pad + 22
    out.append(f'<text x="{pad}" y="{y}" class="s" font-size="{LABEL}" fill="{t["muted"]}"><tspan class="m" font-weight="700" fill="{t["bright"]}">@{USER}</tspan>'
               f'<tspan dx="12">GitHub activity</tspan></text>')
    if narrow:
        y += 30
        out.append(f'<text x="{pad}" y="{y}" class="s" font-size="{LABEL}" fill="{t["muted"]}">{esc(updated)}</text>')
    else:
        out.append(f'<text x="{W - pad}" y="{y}" text-anchor="end" class="s" font-size="{LABEL}" fill="{t["muted"]}">{esc(updated)}</text>')

    kpis = [
        ("Contributions", f"{total:,}", "", f"since {since}"),
        ("Current streak", f"{cur}", " days", f"{fmt_day(cs)} – {fmt_day(ce)}" if cur else "none right now"),
        ("Longest streak", f"{best}", " days", f"{fmt_day(bs)} – {fmt_day(be)}" if best else "none yet"),
        ("Stars earned", f"{s['stars']}", "", f"{s['repos']} public repos"),
    ]
    cols, gap, th = (2 if narrow else 4), 12, 128
    tile_w = (W - 2 * pad - gap * (cols - 1)) / cols
    ty0 = y + 26
    for i, (lab, val, unit, sub) in enumerate(kpis):
        r, c_ = divmod(i, cols)
        x, ty = pad + c_ * (tile_w + gap), ty0 + r * (th + gap)
        out.append(f'<g><rect x="{x:.1f}" y="{ty:.0f}" width="{tile_w:.1f}" height="{th}" rx="12" fill="{t["chip"]}" stroke="{t["line"]}"/>'
                   f'<text x="{x + 20:.1f}" y="{ty + 34:.0f}" class="s" font-size="{LABEL}" font-weight="500" fill="{t["muted"]}">{lab}</text>'
                   f'<text x="{x + 18:.1f}" y="{ty + 84:.0f}" class="s" font-size="44" font-weight="800" letter-spacing="-1.2" fill="{t["bright"]}">{val}'
                   f'<tspan font-size="{LABEL}" font-weight="500" letter-spacing="0" fill="{t["muted"]}">{unit}</tspan></text>'
                   f'<text x="{x + 20:.1f}" y="{ty + 113:.0f}" class="s" font-size="{LABEL}" fill="{t["muted"]}">{esc(sub)}</text></g>')
    y = ty0 + (len(kpis) // cols) * (th + gap) - gap + 44

    # 52-week activity
    aw = W - 2 * pad if narrow else 500
    ds = sorted(s["days"])[-364:]
    weeks = [sum(s["days"][d] for d in ds[i:i + 7]) for i in range(0, len(ds), 7)]
    mx = max(weeks) or 1
    step = aw / len(weeks)
    bh, by = 90, y + 112
    bars = []
    for i, v in enumerate(weeks):
        h = max(3, v / mx * bh)
        bars.append(f'<rect x="{pad + i * step:.1f}" y="{by - h:.1f}" '
                    f'width="{step * .68:.1f}" height="{h:.1f}" rx="2" fill="{t["cyan"] if v else t["line"]}"/>')
    out.append(f'<text x="{pad}" y="{y}" class="s" font-size="{LABEL}" font-weight="500" fill="{t["muted"]}">52-week activity</text>'
               f'<text x="{pad + aw:.0f}" y="{y}" text-anchor="end" class="s" font-size="{LABEL}" fill="{t["muted"]}">peak {mx}/wk</text>' + "".join(bars))

    # languages: top three by bytes plus the rest as "Other"
    langs = sorted(((k, v) for k, v in s["langs"].items() if k not in NON_CODE), key=lambda kv: -kv[1])
    tot = sum(v for _, v in langs) or 1
    top = [(k, v) for k, v in langs[:3] if v / tot >= 0.01]
    other = tot - sum(v for _, v in top)
    if other / tot >= 0.01:
        top.append(("Other", other))
    pal = [t["cyan"], t["violet"], t["n1"], t["n2"]]
    if narrow:
        lx, ly, lw = pad, by + 44, W - 2 * pad
    else:
        lx, ly, lw = pad + aw + 60, y, W - pad - (pad + aw + 60)
    seg, x = [], lx
    for i, (k, v) in enumerate(top):
        w = v / tot * lw
        seg.append(f'<rect x="{x:.1f}" y="{ly + 20}" width="{max(w - 2, 1):.1f}" height="12" fill="{pal[i]}"/>')
        x += w
    legend = []
    for i, (k, v) in enumerate(top):
        cy = ly + 66 + i * 30
        legend.append(f'<circle cx="{lx + 6}" cy="{cy - 6}" r="5.5" fill="{pal[i]}"/>'
                      f'<text x="{lx + 22}" y="{cy}" class="s" font-size="{LABEL}" font-weight="500" fill="{t["text"]}">{esc(k)}</text>'
                      f'<text x="{lx + lw}" y="{cy}" text-anchor="end" class="m" font-size="{LABEL}" fill="{t["muted"]}">{v / tot * 100:.1f}%</text>')
    out.append(f'<text x="{lx}" y="{ly}" class="s" font-size="{LABEL}" font-weight="500" fill="{t["muted"]}">Top languages</text>'
               f'<clipPath id="lc"><rect x="{lx}" y="{ly + 20}" width="{lw}" height="12" rx="6"/></clipPath><g clip-path="url(#lc)">{"".join(seg)}</g>' + "".join(legend))
    H = max(by, ly + 66 + (len(top) - 1) * 30 + 6) + pad
    label = f"GitHub activity: {total:,} contributions, current streak {cur} days, longest {best} days, {s['stars']} stars"
    if s.get("demo"):
        label += " (demo data)"
    return svg_doc(W, H, label, shell(t, W, H, 20) + "".join(out))


# ── footer ───────────────────────────────────────────────────────────────────
def footer(t, W):
    narrow = W == NARROW
    pad = pad_of(W)
    mid = W / 2
    body = [f'<line x1="{pad}" y1="20" x2="{mid - 22}" y2="20" stroke="{t["line"]}" stroke-width="1.5"/>'
            f'<line x1="{mid + 22}" y1="20" x2="{W - pad}" y2="20" stroke="{t["line"]}" stroke-width="1.5"/>'
            f'<rect x="-8" y="-8" width="16" height="16" rx="3" transform="translate({mid} 20) rotate(45)" fill="none" stroke="{t["cyan"]}" stroke-width="2"/>']
    a, b = "“in code we trust,", "in markets we hunt”"
    if narrow:
        body.append(f'<text x="{mid}" y="72" text-anchor="middle" class="s" font-size="24" fill="{t["text"]}">{a}</text>'
                    f'<text x="{mid}" y="104" text-anchor="middle" class="s" font-size="24" font-weight="700" fill="{t["cyan"]}">{b}</text>')
        y = 144
    else:
        body.append(f'<text x="{mid}" y="74" text-anchor="middle" class="s" font-size="24" fill="{t["text"]}">{a} '
                    f'<tspan font-weight="700" fill="{t["cyan"]}">{b}</tspan></text>')
        y = 112
    body.append(f'<text x="{mid}" y="{y}" text-anchor="middle" class="s" font-size="{LABEL}" fill="{t["muted"]}">Built in Indonesia · shipped on-chain</text>')
    return svg_doc(W, y + 20, "In code we trust, in markets we hunt. Built in Indonesia, shipped on-chain.", "".join(body))


# ── connect buttons ──────────────────────────────────────────────────────────
CONNECT = [("x", "X @masterputra6969"), ("linkedin", "LinkedIn"), ("github", "GitHub"), ("dollarkilat", "dollarkilat.xyz")]


def button(t, label):
    """README shows these at height=48, so they keep a 48px tap target at every screen width."""
    w = round(tw(label, LABEL, 600) + 44)
    body = (f'<rect x=".75" y=".75" width="{w - 1.5}" height="46.5" rx="9" fill="{t["panel"]}" stroke="{t["line"]}" stroke-width="1.5"/>'
            f'<text x="{w / 2:.1f}" y="{24 + LABEL * .36:.1f}" text-anchor="middle" class="s" font-size="{LABEL}" font-weight="600" fill="{t["bright"]}">{esc(label)}</text>')
    return svg_doc(w, 48, label, body)


# ── content ──────────────────────────────────────────────────────────────────
FEATURED = dict(title="DollarKilat", kind="Featured · Solana payments", status="Live",
                tags=["Solana", "Next.js", "TypeScript", "PWA", "QRIS"],
                desc="Get paid in USDC, spend anywhere via QRIS. A Solana PWA for Indonesian freelancers, built for Colosseum Frontier 2026.")
CARDS = [
    dict(slug="polymarket-btc", kind="Quant · ML", title="Polymarket BTC 15m",
         desc="XGBoost + LightGBM ensemble trading BTC 15-min markets: drift detection, auto-retrain, live React dashboard.",
         tags=["TypeScript", "XGBoost", "LightGBM"]),
    dict(slug="anyaman", kind="Media · Full-stack", title="Anyaman", status="Live",
         desc="Peace-journalism portal with moderated discussion and AI-assisted articles. Next.js 15, Supabase, Auth.js.",
         tags=["Next.js", "Postgres", "Prisma"]),
    dict(slug="crypto-suite", kind="Education · Security", title="Crypto Suite",
         desc="19 cipher algorithms, classical to modern, with interactive visuals and step-by-step guides.",
         tags=["React", "JavaScript", "Crypto"]),
    dict(slug="simple-web3", kind="Web3 · EVM", title="Simple Web3 Web",
         desc="Ethereum + Base on-chain data surface with Privy login, readable for people new to Web3.",
         tags=["JavaScript", "Ethereum", "Privy"]),
]


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
    log("btc source:", btc["source"], "| stats fetched:", stats.get("fetched"), "| demo stats:", bool(stats.get("demo")))
    (out / "data/btc.json").write_text(json.dumps(btc))
    (out / "data/stats.json").write_text(json.dumps(stats))

    files = {}
    for name, t in THEMES.items():
        for suffix, W in (("", WIDE), ("-narrow", NARROW)):
            files[f"header-{name}{suffix}.svg"] = header(t, btc, W)
            files[f"stats-{name}{suffix}.svg"] = stats_card(t, stats, W)
            files[f"stack-{name}{suffix}.svg"] = stack(t, W)
            files[f"footer-{name}{suffix}.svg"] = footer(t, W)
            files[f"card-dollarkilat-{name}{suffix}.svg"] = featured(t, FEATURED, W)
            for p in CARDS:
                files[f"card-{p['slug']}-{name}{suffix}.svg"] = card(t, p, W)
        for slug, label in CONNECT:
            files[f"connect-{slug}-{name}.svg"] = button(t, label)
    for fn, svg in files.items():
        (out / fn).write_text(svg, encoding="utf-8")
    log(f"wrote {len(files)} svgs, {sum(len(v) for v in files.values()) / 1024:.0f} KB total")


if __name__ == "__main__":
    main()
