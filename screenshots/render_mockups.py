"""Render faithful PNG mockups of the VoiceTasker UI (offline, PIL only).

Same palette/layout/copy as demo.html + real pipeline data.
Outputs: screenshots/tasks.png, screenshots/ideas.png, screenshots/graph.png
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent
FD = "/usr/share/fonts/truetype/dejavu"


def font(name, size):
    return ImageFont.truetype(f"{FD}/{name}.ttf", size)


F_TITLE = font("DejaVuSans-Bold", 19)
F_BIG = font("DejaVuSans-Bold", 30)
F_TAB = font("DejaVuSans-Bold", 15)
F_BODY = font("DejaVuSans-Bold", 13)
F_SMALL = font("DejaVuSans-Bold", 12)
F_TINY = font("DejaVuSans", 12)
F_MONO = font("DejaVuSansMono", 14)
F_TIER = font("DejaVuSans-Bold", 30)

BG = (11, 14, 20)
PANEL = (18, 24, 38)
CARD = (22, 28, 44)
TRACK = (13, 18, 32)
LINE = (35, 44, 66)
TXT = (232, 237, 247)
DIM = (139, 148, 173)
CYAN = (34, 211, 238)
VIOLET = (167, 139, 250)
PINK = (244, 114, 182)
GREEN = (52, 211, 153)
GOLD = (251, 191, 36)
ORANGE = (251, 146, 60)
RED = (248, 113, 113)
HEAT = [(43, 15, 84), (76, 29, 149), (14, 165, 233), (103, 232, 249), (254, 240, 138)]


def glow(base, cx, cy, r, color):
    """Soft radial glow via layered translucent ellipses."""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(12, 0, -1):
        rr = r * i / 12
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                  fill=color + (int(90 * (1 - i / 13)),))
    return Image.alpha_composite(base.convert("RGBA"), layer)


def header(d, W):
    d.text((40, 22), "Voice", font=F_BIG, fill=TXT)
    tx = 40 + d.textlength("Voice", font=F_BIG) + 2
    d.text((tx, 22), "Tasker", font=F_BIG, fill=CYAN)
    d.rounded_rectangle([W - 330, 24, W - 40, 60], 18, fill=(15, 42, 29),
                        outline=(29, 92, 58), width=1)
    d.ellipse([W - 302, 34, W - 290, 46], fill=GREEN)
    d.text((W - 280, 34), "LIVE · simulator · heuristic", font=F_SMALL, fill=GREEN)


def tabs(d, W, active=0):
    labels = ["Tasks", "Projects", "Timeline", "Ideas", "Graph"]
    tw = (W - 80) / len(labels)
    d.rounded_rectangle([40, 80, W - 40, 132], 16, fill=PANEL, outline=LINE, width=1)
    for i, lab in enumerate(labels):
        cx = 40 + tw * i
        if i == active:
            d.rounded_rectangle([cx + 6, 86, cx + tw - 6, 126], 10, fill=(22, 78, 99))
            d.text((cx + tw / 2, 96), lab, font=F_TAB, fill=(255, 255, 255), anchor="ma")
        else:
            d.text((cx + tw / 2, 96), lab, font=F_TAB, fill=DIM, anchor="ma")


def visualizer(img, x, y, w, h):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x, y, x + w, y + h], 16, fill=(11, 14, 20))
    mid = y + h * 0.30
    for amp, freq, phase, col, wd in [(34, 3.0, 0.0, CYAN, 3),
                                      (26, 3.6, 2.1, VIOLET, 2),
                                      (18, 4.3, 4.2, PINK, 2)]:
        pts = [(x + px, mid + amp * math.sin(px / w * freq * math.pi * 2 + phase))
               for px in range(0, w + 1, 6)]
        d.line(pts, fill=col, width=wd, joint="curve")
    img = glow(img, x + w / 2, y + h * 0.30, 64, CYAN)
    d = ImageDraw.Draw(img)
    d.ellipse([x + w / 2 - 11, y + h * 0.30 - 11, x + w / 2 + 11, y + h * 0.30 + 11],
              fill=(224, 250, 255))
    top = y + h * 0.58
    bars, bh = 14, (h * 0.42 - 12) / 14
    for i in range(bars):
        m = 0.9 * math.exp(-i / (bars * 0.42)) * (0.75 + 0.25 * math.sin(i * 1.7))
        bw = w * (0.12 + 0.85 * m)
        col = HEAT[min(4, int(m * 5))]
        d.rounded_rectangle([x + 14, top + i * bh, x + 14 + bw - 28, top + i * bh + bh - 2],
                            2, fill=col)
    return img


def pill(d, x, y, label, color):
    w = 24 + int(len(label) * 7.4)
    d.rounded_rectangle([x, y, x + w, y + 24], 12, fill=PANEL, outline=color, width=1)
    d.text((x + w / 2, y + 4), label, font=F_SMALL, fill=color, anchor="ma")
    return w


def task_card(img, y, W, title, cat, catcol, dep_label, order, pct, time_s):
    d = ImageDraw.Draw(img)
    x, w, h = 40, W - 80, 118
    d.rounded_rectangle([x, y, x + w, y + h], 24, fill=CARD, outline=LINE, width=1)
    d.rounded_rectangle([x + 22, y + 24, x + 52, y + 54], 9, outline=(59, 71, 99), width=2)
    d.text((x + 66, y + 26), title, font=F_TITLE, fill=TXT)
    px = x + 66
    px += pill(d, px, y + 58, cat, catcol) + 8
    if order:
        d.rounded_rectangle([px, y + 58, px + 118, y + 82], 12, fill=(42, 51, 80),
                            outline=(59, 71, 99), width=1)
        d.text((px + 59, y + 62), f"#{order} in order", font=F_SMALL,
               fill=(205, 214, 234), anchor="ma")
        px += 126
    if dep_label:
        dw = 128 + int(len(dep_label) * 6.6)
        d.rounded_rectangle([px, y + 58, px + dw, y + 82], 12, fill=(42, 51, 80),
                            outline=(59, 71, 99), width=1)
        d.text((px + 12, y + 62), "waits on: " + dep_label, font=F_SMALL,
               fill=(205, 214, 234))
    d.text((x + w - 150, y + 28), time_s, font=F_BODY, fill=DIM, anchor="ra")
    d.rounded_rectangle([x + 66, y + 90, x + w - 260, y + 99], 4, fill=TRACK)
    fw = (w - 326) * pct / 100
    if fw > 2:
        d.rounded_rectangle([x + 66, y + 90, x + 66 + fw, y + 99], 4, fill=CYAN)
    d.text((x + w - 248, y + 86), f"{pct}%", font=F_TINY, fill=DIM, anchor="ra")
    # play button (drawn triangle) + menu (3 dots)
    d.rounded_rectangle([x + w - 120, y + 22, x + w - 82, y + 60], 12,
                        fill=(27, 36, 56), outline=LINE, width=1)
    bx, by = x + w - 101, y + 41
    d.polygon([(bx - 6, by - 8), (bx - 6, by + 8), (bx + 8, by)], fill=TXT)
    d.rounded_rectangle([x + w - 72, y + 22, x + w - 34, y + 60], 12,
                        fill=(27, 36, 56), outline=LINE, width=1)
    for i in range(3):
        d.ellipse([x + w - 56, y + 31 + i * 9, x + w - 50, y + 37 + i * 9], fill=TXT)
    return img


def render_tasks():
    W, H = 1280, 1010
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(d, W)
    tabs(d, W, 0)
    d.rounded_rectangle([40, 148, W - 40, 478], 24, fill=PANEL, outline=LINE, width=1)
    img = visualizer(img, 60, 166, W - 120, 210)
    d = ImageDraw.Draw(img)
    d.text((60, 388), "> …and THEN I can finally set up librechat on top of all that.  [+ task]",
           font=F_MONO, fill=CYAN)
    for i, lab in enumerate(["Replay voice demo", "Use my real mic", "Win+Space overlay"]):
        bx = 60 + i * 220
        d.rounded_rectangle([bx, 418, bx + 204, 458], 12,
                            fill=(14, 116, 144) if i == 0 else (27, 36, 56),
                            outline=None if i == 0 else LINE, width=1)
        d.text((bx + 102, 430), lab, font=F_BODY, fill=TXT, anchor="ma")
    d.text((44, 500), "PROJECT: HOMELAB REVIVAL", font=F_SMALL, fill=DIM)
    y = 516
    img = task_card(img, y, W, "Reinstall docker", "dev", CYAN, "", 1, 12, "3/20m")
    y += 130
    img = task_card(img, y, W, "Grab all my api keys and env vars and base urls together",
                    "ops", VIOLET, "Reinstall docker", 2, 0, "0/20m")
    y += 130
    img = task_card(img, y, W, "Set up librechat on top of all that", "dev", CYAN,
                    "Grab all my api keys…", 3, 0, "0/45m")
    img.save(OUT / "tasks.png")
    print("wrote tasks.png")


def render_ideas():
    W, H = 1280, 560
    tiers = [("S", GOLD, [("Voice task tracker", "9.4 · nov 10")]),
             ("A", VIOLET, [("BrowserUse MCP", "8.1 · lev 9")]),
             ("B", CYAN, [("Overlay standups", "7.0 · NEW")]),
             ("C", GREEN, [("Meal-planner bot", "4.8"), ("Tab janitor", "4.1")]),
             ("D", ORANGE, [("Rewrite in Rust", "3.2")]),
             ("F", RED, [("Blockchain todos", "1.4")])]
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(d, W)
    tabs(d, W, 3)
    d.rounded_rectangle([40, 148, W - 40, 488], 24, fill=PANEL, outline=LINE, width=1)
    cw = (W - 80 - 28 * 7) / 6
    for i, (tier, col, ideas) in enumerate(tiers):
        cx = 40 + 28 + i * (cw + 28)
        d.rounded_rectangle([cx, 176, cx + cw, 426], 18, fill=CARD, outline=LINE, width=1)
        d.text((cx + cw / 2, 190), tier, font=F_TIER, fill=col, anchor="ma")
        iy = 240
        for title, sub in ideas:
            d.rounded_rectangle([cx + 10, iy, cx + cw - 10, iy + 62], 12,
                                fill=TRACK, outline=LINE, width=1)
            d.text((cx + 20, iy + 10), title[:22], font=F_SMALL, fill=TXT)
            d.text((cx + 20, iy + 34), sub, font=F_TINY, fill=DIM)
            iy += 72
    d.text((W / 2, 514), 'TIER_JUDGE: "Rare + shippable with your stack." · next: scaffold the STT loop',
           font=F_TINY, fill=DIM, anchor="ma")
    img.save(OUT / "ideas.png")
    print("wrote ideas.png")


def render_graph():
    W, H = 1280, 560
    nodes = [("dev", .12, .30, 14, CYAN), ("ops", .12, .72, 14, VIOLET),
             ("Browser Auto", .38, .30, 20, PINK), ("Homelab", .38, .72, 20, VIOLET),
             ("Research", .66, .16, 11, GREEN), ("MCP build", .66, .36, 13, CYAN),
             ("Test", .88, .30, 10, DIM), ("Docker", .62, .62, 12, GREEN),
             ("API keys", .78, .74, 12, CYAN), ("LibreChat", .92, .60, 12, DIM)]
    edges = [(0, 2, 0), (1, 3, 0), (2, 4, 0), (2, 5, 0), (5, 6, 1),
             (3, 7, 0), (7, 8, 1), (8, 9, 1)]
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(d, W)
    tabs(d, W, 4)
    gx, gy, gw, gh = 60, 166, W - 120, 300
    d.rounded_rectangle([40, 148, W - 40, 496], 24, fill=PANEL, outline=LINE, width=1)
    d.rounded_rectangle([gx, gy, gx + gw, gy + gh], 16, fill=(11, 14, 20))
    P = [(gx + n[1] * gw, gy + n[2] * gh) for n in nodes]
    for a, b, dep in edges:
        d.line([P[a], P[b]], fill=CYAN if dep else (59, 71, 99), width=3 if dep else 2)
    for (label, _, _, r, col), (px, py) in zip(nodes, P):
        img = glow(img, px, py, r + 14, col)
    d = ImageDraw.Draw(img)
    for (label, _, _, r, col), (px, py) in zip(nodes, P):
        d.ellipse([px - r, py - r, px + r, py + r], fill=col)
        d.text((px, py + r + 6), label, font=F_SMALL, fill=TXT, anchor="ma")
    d.text((W / 2, 522), "size = priority · color = status · cyan = depends-on",
           font=F_TINY, fill=DIM, anchor="ma")
    img.save(OUT / "graph.png")
    print("wrote graph.png")


def render_projects():
    W, H = 1280, 800
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(d, W)
    tabs(d, W, 1)
    d.rounded_rectangle([40, 148, W - 40, 736], 24, fill=PANEL, outline=LINE, width=1)
    d.text((60, 168), "PROJECTS · GROUPED BY CATEGORY", font=F_SMALL, fill=DIM)
    sections = [
        ("dev", CYAN, [("Browser Automation",
                        [("Research browser automation", 80), ("Build the BrowserUse MCP", 10),
                         ("Test automations", 0)])]),
        ("ops", VIOLET, [("Homelab revival",
                          [("Reinstall docker", 12), ("Grab all my api keys and env vars…", 0),
                           ("Set up librechat on top of all that", 0)])]),
    ]
    y = 198
    for cat, col, projs in sections:
        d.ellipse([60, y, 72, y + 12], fill=col)
        n = sum(len(ts) for _, ts in projs)
        d.text((82, y - 3), f"{cat.upper()} · {len(projs)} PROJECT(S) · {n} TASK(S)",
               font=F_SMALL, fill=DIM)
        y += 30
        for name, ts in projs:
            avg = round(sum(p for _, p in ts) / len(ts))
            cardh = 104 + len(ts) * 34
            d.rounded_rectangle([60, y, W - 60, y + cardh], 18, fill=CARD, outline=LINE, width=1)
            d.text((80, y + 14), name, font=F_BODY, fill=TXT)
            d.text((80, y + 36), f"{len(ts)} task(s) · {avg}% avg progress", font=F_TINY, fill=DIM)
            d.rounded_rectangle([80, y + 58, W - 80, y + 67], 4, fill=TRACK)
            if avg > 0:
                d.rounded_rectangle([80, y + 58, 80 + (W - 160) * avg / 100, y + 67], 4, fill=CYAN)
            ry = y + 78
            for title, pct in ts:
                dot = GREEN if pct >= 100 else (CYAN if pct > 0 else (59, 71, 99))
                d.ellipse([80, ry + 7, 89, ry + 16], fill=dot)
                d.text((100, ry + 3), title, font=F_TINY, fill=TXT)
                d.text((W - 80, ry + 3), f"{pct}%", font=F_TINY, fill=DIM, anchor="ra")
                ry += 34
            y += cardh + 14
    d.text((W / 2, 762), "click a project to jump to its tasks", font=F_TINY, fill=DIM, anchor="ma")
    img.save(OUT / "projects.png")
    print("wrote projects.png")


def main():
    for stale in OUT.glob("*.svg"):
        stale.unlink()
    render_tasks()
    render_ideas()
    render_graph()
    render_projects()


if __name__ == "__main__":
    main()
