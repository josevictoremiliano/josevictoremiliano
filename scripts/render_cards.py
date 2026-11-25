"""Desenha os cards SVG animados do README a partir de data/stats.json.

    python scripts/render_cards.py            # cards animados em cards/
    STATIC=1 python scripts/render_cards.py   # último quadro, sem animação (p/ screenshot)

Cada card sai em duas versões (light/dark) para o <picture> do README.
Tudo fica dentro do SVG: o README do GitHub não roda JS nem CSS, mas um SVG
servido como <img> roda o próprio <style> (keyframes) e SMIL.
"""
import base64
import json
import os
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "cards"
STATIC = os.environ.get("STATIC") == "1"

THEMES = {
    "light": dict(bg="#f8f7f3", card="#ffffff", ink="#1e1e1e", ink2="#424242", muted="#8f8f8f",
                  line="#e2e0da", soft="#efede6", orange="#fd853a", coral="#f7714e", bar="#2a2a2a"),
    "dark": dict(bg="#0a0d0e", card="#111517", ink="#f3f1ea", ink2="#c9c9c9", muted="#8b8b8b",
                 line="#23292b", soft="#1a2023", orange="#fd853a", coral="#f7714e", bar="#d9d6cc"),
}

FONTS = {  # família CSS -> arquivo subset
    "JV Display": "baloo2-800",
    "JV Body": "bai-400",
    "JV Body Medium": "bai-500",
    "JV Hand": "hand-400",
    "JV Mono": "mono-500",
}
MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


# --------------------------------------------------------------------------- texto
@lru_cache(None)
def _metrics(name: str):
    f = TTFont(ROOT / "fonts" / f"{name}.woff2")
    return f.getBestCmap(), f["hmtx"].metrics, f["head"].unitsPerEm


def text_w(text: str, family: str, size: float, spacing: float = 0) -> float:
    cmap, hmtx, upm = _metrics(FONTS[family])
    adv = sum(hmtx[cmap[ord(c)]][0] if ord(c) in cmap else upm * 0.5 for c in text)
    return adv / upm * size + spacing * len(text)


def wrap(text: str, family: str, size: float, max_w: float) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and text_w(trial, family, size) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur] if cur else lines


def x(s) -> str:
    return escape(str(s))


# --------------------------------------------------------------------------- base
CLASS_FONT = {"d": "JV Display", "b": "JV Body", "bm": "JV Body Medium", "h": "JV Hand", "m": "JV Mono"}


@lru_cache(None)
def font_css(families: frozenset) -> str:
    """Só embute as fontes que o card realmente usa (cada uma pesa 5–11 KB)."""
    rules = []
    for fam, file in FONTS.items():
        if fam not in families:
            continue
        b64 = base64.b64encode((ROOT / "fonts" / f"{file}.woff2").read_bytes()).decode()
        rules.append(f"@font-face{{font-family:'{fam}';src:url(data:font/woff2;base64,{b64}) format('woff2');}}")
    return "".join(rules)


BASE_CSS = """
.d{font-family:'JV Display',sans-serif;font-weight:800}
.b{font-family:'JV Body',sans-serif}
.bm{font-family:'JV Body Medium',sans-serif}
.h{font-family:'JV Hand',cursive}
.m{font-family:'JV Mono',monospace;font-weight:500;letter-spacing:.08em}
.up{animation:up .8s cubic-bezier(.2,.7,.2,1) both}
.fade{animation:fade .9s ease both}
.pop{animation:pop .55s cubic-bezier(.3,1.5,.5,1) both;transform-box:fill-box;transform-origin:center}
.grow{animation:grow .9s cubic-bezier(.2,.7,.2,1) both;transform-box:fill-box;transform-origin:bottom}
.draw{stroke-dasharray:var(--len);animation:draw 1.6s cubic-bezier(.5,0,.2,1) both}
.spin{animation:spin 28s linear infinite;transform-box:fill-box;transform-origin:center}
.blink{animation:blink 1s steps(1) infinite}
.pulse{animation:pulse 2.4s ease-in-out infinite;transform-box:fill-box;transform-origin:center}
@keyframes up{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes pop{from{opacity:0;transform:scale(.4)}to{opacity:1;transform:none}}
@keyframes grow{from{transform:scaleY(0)}to{transform:none}}
@keyframes draw{from{stroke-dashoffset:var(--len)}to{stroke-dashoffset:0}}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes blink{50%{opacity:0}}
@keyframes pulse{0%,100%{opacity:.35;transform:scale(1)}50%{opacity:1;transform:scale(1.25)}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""


def d(delay: float) -> str:
    """Atributo de atraso da animação CSS."""
    return f' style="animation-delay:{delay:.2f}s"'


def svg(w: int, h: int, body: str, t: dict, title: str) -> str:
    static = "*{animation:none!important}" if STATIC else ""
    used = {c for cls in re.findall(r'class="([^"]*)"', body) for c in cls.split()}
    families = frozenset(CLASS_FONT[c] for c in used if c in CLASS_FONT)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{x(title)}"><title>{x(title)}</title>'
        f"<style>{font_css(families)}{BASE_CSS}{static}</style>"
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="22" fill="{t["card"]}" stroke="{t["line"]}"/>'
        f"{body}</svg>"
    )


def smil(markup: str) -> str:
    return "" if STATIC else markup


def count_up(value: int, cx: float, y: float, cls: str, size: int, fill: str, start: float,
             anchor: str = "start", frames: int = 18, dur: float = 1.1) -> str:
    """Número que conta de 0 até value: um <text> por quadro, trocados com SMIL <set>."""
    final = f"{value:,}".replace(",", ".")
    common = f'x="{cx}" y="{y}" class="{cls}" font-size="{size}" fill="{fill}" text-anchor="{anchor}"'
    if STATIC:
        return f"<text {common}>{final}</text>"
    out, dt = [], dur / frames
    for k in range(1, frames + 1):
        p = 1 - (1 - k / frames) ** 3  # ease-out
        v = f"{round(value * p):,}".replace(",", ".")
        last = k == frames
        timing = 'fill="freeze"' if last else f'dur="{dt:.3f}s"'
        out.append(f'<text {common} opacity="0">{v}<set attributeName="opacity" to="1" '
                   f'begin="{start + (k - 1) * dt:.3f}s" {timing}/></text>')
    return "".join(out)


# --------------------------------------------------------------------------- dados
def load() -> dict:
    s = json.loads((ROOT / "data" / "stats.json").read_text(encoding="utf-8"))
    days = [(date.fromisoformat(dt), n) for dt, n in s["days"]]
    longest = run = 0
    for _, n in days:
        run = run + 1 if n else 0
        longest = max(longest, run)
    current = 0
    for i, (_, n) in enumerate(reversed(days)):
        if n:
            current += 1
        elif i == 0:
            continue  # hoje ainda sem commit não quebra a sequência
        else:
            break
    months: dict[tuple, int] = {}
    for dt, n in days:
        months[(dt.year, dt.month)] = months.get((dt.year, dt.month), 0) + n
    s["months"] = sorted(months.items())[-12:]
    s["weeks"] = [sum(n for _, n in days[i:i + 7]) for i in range(0, len(days), 7)]
    s["longest"], s["current"] = longest, current
    s["active_days"] = sum(1 for _, n in days if n)
    return s


# --------------------------------------------------------------------------- cards
def hero(t: dict) -> str:
    W, H = 880, 320
    name = "José Victor"
    name_w = text_w(name, "JV Display", 84)
    # círculos à direita, ecoando a logo do portfólio
    cx, cy = 748, 160
    rings = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{t["line"]}" stroke-width="1.5" class="pop"{d(0.15 + i * 0.12)}/>'
        for i, r in enumerate((44, 78, 112))
    )
    orbit = (
        f'<g><circle cx="{cx}" cy="{cy - 78}" r="6.5" fill="{t["orange"]}"/>'
        + smil(f'<animateTransform attributeName="transform" type="rotate" from="0 {cx} {cy}" to="360 {cx} {cy}" dur="9s" repeatCount="indefinite"/>')
        + "</g>"
        f'<g><circle cx="{cx + 112}" cy="{cy}" r="4.5" fill="{t["coral"]}"/>'
        + smil(f'<animateTransform attributeName="transform" type="rotate" from="360 {cx} {cy}" to="0 {cx} {cy}" dur="16s" repeatCount="indefinite"/>')
        + "</g>"
    )
    dashed = (f'<circle cx="{cx}" cy="{cy}" r="95" fill="none" stroke="{t["orange"]}" stroke-width="1.5" '
              f'stroke-dasharray="2 10" stroke-linecap="round" class="spin" opacity=".8"/>')
    mono = (f'<text x="{cx}" y="{cy + 12}" text-anchor="middle" class="d pop" font-size="36" fill="{t["ink"]}"{d(0.5)}>'
            f'jv<tspan fill="{t["orange"]}">.</tspan></text>')

    shine = smil(
        '<animateTransform attributeName="gradientTransform" type="translate" '
        'values="-520 0;-520 0;980 0" keyTimes="0;.6;1" dur="6s" begin="1.2s" repeatCount="indefinite"/>'
    )
    defs = (
        f'<defs><linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="260" y2="0">'
        f'<stop offset="0" stop-color="{t["ink"]}"/><stop offset=".45" stop-color="{t["orange"]}"/>'
        f'<stop offset=".55" stop-color="{t["coral"]}"/><stop offset="1" stop-color="{t["ink"]}"/>{shine}'
        f"</linearGradient></defs>"
    )
    hand_x = 56 + name_w + 14
    body = (
        defs + dashed + rings + orbit + mono
        + f'<text x="56" y="78" class="m up" font-size="13" fill="{t["orange"]}"{d(0)}>&gt; OLÁ, EU SOU'
        f'<tspan class="blink" fill="{t["orange"]}"> _</tspan></text>'
        + f'<text x="52" y="158" class="d up" font-size="84" fill="url(#shine)"{d(0.1)}>{x(name)}</text>'
        + f'<g class="pop"{d(1.1)}><text x="{hand_x}" y="108" class="h" font-size="30" fill="{t["coral"]}" '
        f'transform="rotate(-10 {hand_x} 108)">oi!</text></g>'
        + f'<text x="56" y="200" class="bm up" font-size="24" fill="{t["ink2"]}"{d(0.25)}>Desenvolvedor Full Stack &amp; Designer</text>'
        + f'<text x="56" y="232" class="b up" font-size="16" fill="{t["muted"]}"{d(0.4)}>'
        "Transformo ideias em produtos digitais — dev, design, automação e IA.</text>"
        + chips(t, 56, 266, ["Rio Grande do Norte — BR", "jotav.me", "pt-BR · en"], 0.55)
    )
    return svg(W, H, body, t, "José Victor — Desenvolvedor Full Stack & Designer")


def chips(t: dict, x0: float, y: float, items: list[str], start: float, size: int = 12) -> str:
    out, cx = [], x0
    for i, label in enumerate(items):
        w = text_w(label.upper(), "JV Mono", size, size * 0.08) + 26
        dot = f'<circle cx="{cx + 13}" cy="{y}" r="3" fill="{t["orange"]}" class="pulse"{d(i * 0.4)}/>' if i == 0 else ""
        pad = 22 if i == 0 else 13
        w += 9 if i == 0 else 0
        out.append(
            f'<g class="up"{d(start + i * 0.08)}><rect x="{cx}" y="{y - 14}" width="{w}" height="28" rx="14" '
            f'fill="{t["soft"]}"/>{dot}<text x="{cx + pad}" y="{y + 4.5}" class="m" font-size="{size}" '
            f'fill="{t["ink2"]}">{x(label.upper())}</text></g>'
        )
        cx += w + 8
    return "".join(out)


def tile(t: dict, kicker: str, value: int, caption: str, viz: str, title: str) -> str:
    W, H = 286, 168
    body = (
        f'<text x="24" y="38" class="m up" font-size="11" fill="{t["muted"]}">{x(kicker)}</text>'
        + count_up(value, 22, 100, "d", 56, t["ink"], 0.2)
        + f'<text x="24" y="134" class="b up" font-size="14" fill="{t["ink2"]}"{d(0.5)}>{x(caption)}</text>'
        + viz
    )
    return svg(W, H, body, t, title)


def tile_contrib(t: dict, s: dict) -> str:
    w = s["weeks"][-26:]
    weeks = [w[i] + w[i + 1] for i in range(0, len(w) - 1, 2)]  # quinzenas: linha mais limpa
    top = max(weeks) or 1
    x0, x1, y0, y1 = 186, 262, 28, 66
    pts = [(x0 + i * (x1 - x0) / (len(weeks) - 1), y1 - n / top * (y1 - y0)) for i, n in enumerate(weeks)]
    path = "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in pts)
    length = sum(((pts[i + 1][0] - pts[i][0]) ** 2 + (pts[i + 1][1] - pts[i][1]) ** 2) ** 0.5 for i in range(len(pts) - 1))
    viz = (f'<path d="{path}" fill="none" stroke="{t["orange"]}" stroke-width="2.2" stroke-linejoin="round" '
           f'stroke-linecap="round" class="draw" style="--len:{length:.0f};animation-delay:.3s"/>'
           f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="3.5" fill="{t["orange"]}" class="pop"{d(1.8)}/>')
    return tile(t, "CONTRIBUIÇÕES", s["total"], "nos últimos 12 meses", viz, f"{s['total']} contribuições no último ano")


def tile_streak(t: dict, s: dict) -> str:
    # 14 últimos dias como quadradinhos
    last = [n for _, n in s["days"][-14:]]
    viz = "".join(
        f'<rect x="{168 + (i % 7) * 14}" y="{30 + (i // 7) * 14}" width="10" height="10" rx="2.5" '
        f'fill="{t["orange"] if n else t["soft"]}" class="pop"{d(0.3 + i * 0.05)}/>'
        for i, n in enumerate(last)
    )
    cap = f"dias seguidos · atual: {s['current']}"
    return tile(t, "MAIOR SEQUÊNCIA", s["longest"], cap, viz, f"Maior sequência: {s['longest']} dias")


def tile_repos(t: dict, s: dict) -> str:
    x0, w, y = 168, 98, 34
    segs, cx = [], x0
    for i, lang in enumerate(s["languages"]):
        lw = w * lang["pct"] / sum(l["pct"] for l in s["languages"])
        segs.append(f'<rect x="{cx:.1f}" y="{y}" width="{max(lw - 2, 1):.1f}" height="8" rx="2" fill="{lang["color"]}" '
                    f'class="pop"{d(0.3 + i * 0.08)}/>')
        cx += lw
    names = "".join(
        f'<g class="fade"{d(0.6 + i * 0.08)}><circle cx="{x0 + 3}" cy="{y + 20.5 + i * 14}" r="3" fill="{l["color"]}"/>'
        f'<text x="{x0 + 11}" y="{y + 24 + i * 14}" class="b" font-size="10.5" fill="{t["muted"]}">{x(l["name"])}</text></g>'
        for i, l in enumerate(s["languages"][:3])
    )
    cap = f"públicos · {s['followers']} seguidores"
    return tile(t, "REPOSITÓRIOS", s["repos"], cap, "".join(segs) + names, f"{s['repos']} repositórios públicos")


def activity(t: dict, s: dict) -> str:
    W, H = 880, 270
    months = s["months"]
    top = max(n for _, n in months) or 1
    best = max(months, key=lambda m: m[1])
    x0, x1, base, hmax = 56, 824, 214, 120
    slot = (x1 - x0) / len(months)
    bw = slot * 0.56
    bars = []
    for i, ((yr, mo), n) in enumerate(months):
        h = max(n / top * hmax, 3)
        bx = x0 + i * slot + (slot - bw) / 2
        color = t["orange"] if (yr, mo) == best[0] else t["bar"]
        delay = 0.25 + i * 0.07
        bars.append(
            f'<rect x="{bx:.1f}" y="{base - h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="6" fill="{color}" '
            f'class="grow"{d(delay)}/>'
            f'<text x="{bx + bw / 2:.1f}" y="{base - h - 9:.1f}" text-anchor="middle" class="m fade" font-size="11" '
            f'fill="{t["orange"] if (yr, mo) == best[0] else t["muted"]}"{d(delay + 0.6)}>{n}</text>'
            f'<text x="{bx + bw / 2:.1f}" y="{base + 24}" text-anchor="middle" class="m" font-size="11" '
            f'fill="{t["muted"]}">{MONTHS[mo - 1].upper()}</text>'
        )
    (by, bm), bn = best
    body = (
        f'<text x="56" y="50" class="m up" font-size="12" fill="{t["muted"]}">ATIVIDADE · ÚLTIMOS 12 MESES</text>'
        f'<text x="824" y="50" text-anchor="end" class="b up" font-size="14" fill="{t["ink2"]}"{d(0.1)}>'
        f'{s["active_days"]} dias ativos · pico em <tspan fill="{t["orange"]}" class="bm">{MONTHS[bm - 1]}/{str(by)[2:]}</tspan></text>'
        f'<line x1="{x0}" y1="{base + .5}" x2="{x1}" y2="{base + .5}" stroke="{t["line"]}"/>'
        + "".join(bars)
    )
    return svg(W, H, body, t, f"Atividade no GitHub: {s['total']} contribuições em 12 meses")


STACK = [
    ("React", "#61dafb"), ("Next.js", None), ("TypeScript", "#3178c6"), ("Laravel", "#ff2d20"),
    ("PHP", "#777bb4"), ("Node.js", "#5fa04e"), ("Rust", "#dea584"), ("Tauri", "#ffc131"),
    ("Svelte", "#ff3e00"), ("Tailwind", "#38bdf8"), ("WordPress", "#21759b"), ("MySQL", "#4479a1"),
    ("PostgreSQL", "#4169e1"), ("Figma", "#a259ff"), ("n8n", "#ea4b71"), ("Docker", "#2496ed"),
]


def stack(t: dict) -> str:
    W = 880
    size, gap, row_h = 15, 10, 44
    rows, cur, cw = [], [], 0
    for item in STACK:
        w = text_w(item[0], "JV Body Medium", size) + 46
        if cur and cw + w > 768:
            rows.append((cur, cw - gap))
            cur, cw = [], 0
        cur.append((item, w))
        cw += w + gap
    rows.append((cur, cw - gap))
    H = 86 + len(rows) * row_h + 22
    out, k = [], 0
    for r, (items, total_w) in enumerate(rows):
        cx = 56
        y = 86 + r * row_h
        for (label, color), w in items:
            dot = color or t["ink"]
            out.append(
                f'<g class="pop"{d(0.15 + k * 0.045)}><rect x="{cx}" y="{y}" width="{w:.1f}" height="34" rx="17" '
                f'fill="{t["soft"]}" stroke="{t["line"]}"/><circle cx="{cx + 19}" cy="{y + 17}" r="5" fill="{dot}"/>'
                f'<text x="{cx + 32}" y="{y + 22.5}" class="bm" font-size="{size}" fill="{t["ink"]}">{x(label)}</text></g>'
            )
            cx += w + gap
            k += 1
    body = (
        f'<text x="56" y="50" class="m up" font-size="12" fill="{t["muted"]}">STACK DO DIA A DIA</text>'
        f'<g class="fade"{d(1.2)}><text x="790" y="50" text-anchor="end" class="h" font-size="21" fill="{t["coral"]}" '
        f'transform="rotate(-3 790 50)">do design ao deploy</text></g>'
        f'<path d="M796 38 C 818 34, 826 50, 818 68 M810 62 l8 7 l4 -10" fill="none" stroke="{t["coral"]}" '
        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="draw" style="--len:80;animation-delay:1.5s"/>'
        + "".join(out)
    )
    return svg(W, H, body, t, "Stack: " + ", ".join(n for n, _ in STACK))


PROJECTS = {
    "larafim": dict(
        kicker="OPEN SOURCE · WINDOWS", title="Larafim",
        text="Gerenciador local de PHP, Node e bancos de dados para Windows: cada projeto no seu domínio .offline, "
             "com a sua versão de PHP, tudo ao mesmo tempo.",
        tags=["Rust", "Tauri 2", "Svelte 5"], link="github.com/josevictoremiliano/larafim"),
    "screvo": dict(
        kicker="PRODUTO PESSOAL", title="Screvo",
        text="Compartilhamento de tela sem complicação: crie uma sala temporária, envie o link e reúna todo mundo "
             "no navegador, sem conta e sem instalação.",
        tags=["Tempo real", "Sem cadastro", "Sem instalação"], link="screvo.painel.jotav.me"),
}


def project(t: dict, p: dict) -> str:
    W, H = 434, 250
    lines = wrap(p["text"], "JV Body", 14.5, W - 64)
    text = "".join(
        f'<text x="30" y="{112 + i * 21}" class="b up" font-size="14.5" fill="{t["ink2"]}"{d(0.25 + i * 0.05)}>{x(l)}</text>'
        for i, l in enumerate(lines)
    )
    tags, cx = [], 30
    for i, tag in enumerate(p["tags"]):
        w = text_w(tag.upper(), "JV Mono", 10.5, 0.84) + 20
        tags.append(f'<g class="pop"{d(0.5 + i * 0.07)}><rect x="{cx}" y="198" width="{w:.1f}" height="24" rx="12" '
                    f'fill="{t["soft"]}"/><text x="{cx + 10}" y="214" class="m" font-size="10.5" fill="{t["ink2"]}">'
                    f'{x(tag.upper())}</text></g>')
        cx += w + 6
    body = (
        f'<text x="30" y="44" class="m up" font-size="11" fill="{t["orange"]}">{x(p["kicker"])}</text>'
        f'<g class="up"{d(0.1)}><circle cx="388" cy="42" r="18" fill="{t["soft"]}"/>'
        f'<path d="M382 48 L394 36 M385 36 H394 V45" fill="none" stroke="{t["ink"]}" stroke-width="2.2" '
        f'stroke-linecap="round" stroke-linejoin="round"/></g>'
        f'<text x="28" y="84" class="d up" font-size="36" fill="{t["ink"]}"{d(0.1)}>{x(p["title"])}</text>'
        + text + "".join(tags)
    )
    return svg(W, H, body, t, f"{p['title']} — {p['text']}")


# --------------------------------------------------------------------------- main
def main() -> None:
    s = load()
    OUT.mkdir(exist_ok=True)
    for name, t in THEMES.items():
        files = {
            "hero": hero(t), "tile-contrib": tile_contrib(t, s), "tile-streak": tile_streak(t, s),
            "tile-repos": tile_repos(t, s), "activity": activity(t, s), "stack": stack(t),
            **{f"repo-{k}": project(t, p) for k, p in PROJECTS.items()},
        }
        for f, content in files.items():
            (OUT / f"{f}-{name}.svg").write_text(content, encoding="utf-8")
    print(f"{len(list(OUT.glob('*.svg')))} cards em {OUT}{' (STATIC)' if STATIC else ''}")


if __name__ == "__main__":
    main()
