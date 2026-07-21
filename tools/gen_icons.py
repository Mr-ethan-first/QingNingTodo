# -*- coding: utf-8 -*-
"""
Generate 5 premium, on-brand "青柠待办" (Lime To-Do) icon candidates as PNG previews.
Brand palette (from src/theme.py, default "有机亲和" theme):
  primary   #5B8A3A (91,138,58)
  secondary #7BAE5C (123,174,92)
  light     #A8C97F (168,201,127)
Uses numpy + Pillow. Supersampled for smooth anti-aliased edges.
"""
import numpy as np
from PIL import Image, ImageFilter

S = 1024                      # work resolution (supersampled)
FINAL = 512                   # output preview resolution
SS = S // FINAL               # supersample factor baked into S already
AA = 1.6                      # anti-alias width in work px

def smooth(d):
    # d: SDF in px (negative inside). returns 0..1 alpha.
    return np.clip(0.5 - d / AA, 0.0, 1.0)

def sdf_round_box(px, py, cx, cy, hw, hh, r):
    qx = np.abs(px - cx) - (hw - r)
    qy = np.abs(py - cy) - (hh - r)
    ox = np.maximum(qx, 0.0); oy = np.maximum(qy, 0.0)
    outside = np.sqrt(ox * ox + oy * oy)
    inside = np.minimum(np.maximum(qx, qy), 0.0)
    return outside + inside - r

def sdf_circle(px, py, cx, cy, r):
    return np.sqrt((px - cx) ** 2 + (py - cy) ** 2) - r

def sdf_segment(px, py, ax, ay, bx, by, r):
    pax, pay = px - ax, py - ay
    bax, bay = bx - ax, by - ay
    dot = pax * bax + pay * bay
    denom = bax * bax + bay * bay
    h = np.clip(dot / denom, 0.0, 1.0) if denom > 0 else np.zeros_like(px)
    dx = pax - bax * h
    dy = pay - bay * h
    return np.sqrt(dx * dx + dy * dy) - r

def mix(c1, c2, t):
    c1 = np.array(c1, float); c2 = np.array(c2, float)
    return c1 * (1 - t) + c2 * t

def gradient_diag(H, W, top, bottom):
    # top-left lighter -> bottom-right darker
    yy, xx = np.mgrid[0:H, 0:W]
    t = (xx / float(W - 1) + yy / float(H - 1)) / 2.0
    top = np.array(top, float); bottom = np.array(bottom, float)
    return top[None, None, :] * (1 - t[:, :, None]) + bottom[None, None, :] * t[:, :, None]

def make_base(shape, g_top, g_bottom):
    """Return (rgb float HxWx3, alpha float HxW) for the icon tile with shadow."""
    H = W = S
    yy, xx = np.mgrid[0:H, 0:W]
    cx = cy = S / 2.0

    # --- drop shadow (soft, offset down) ---
    if shape == "disc":
        sd = sdf_circle(xx, yy, cx, cy + S * 0.018, S * 0.42)
    else:
        sd = sdf_round_box(xx, yy, cx, cy + S * 0.018, S * 0.44, S * 0.44, S * 0.22)
    shadow_a = smooth(sd) * 0.38
    sh_img = np.zeros((H, W, 4), float)
    sh_img[:, :, 0] = sh_img[:, :, 1] = sh_img[:, :, 2] = 0.0
    sh_img[:, :, 3] = shadow_a * 255.0
    sh_img = Image.fromarray(np.clip(sh_img, 0, 255).astype(np.uint8), "RGBA")
    sh_img = sh_img.filter(ImageFilter.GaussianBlur(S * 0.012))
    sh_rgb = np.array(sh_img)[:, :, :3].astype(float)
    sh_a = np.array(sh_img)[:, :, 3].astype(float) / 255.0

    # --- base tile gradient ---
    if shape == "disc":
        bd = sdf_circle(xx, yy, cx, cy, S * 0.42)
    else:
        bd = sdf_round_box(xx, yy, cx, cy, S * 0.44, S * 0.44, S * 0.22)
    ba = smooth(bd)
    base_rgb = gradient_diag(H, W, g_top, g_bottom)
    # subtle top highlight for premium depth
    hl = np.clip(1.0 - (yy / float(H)), 0, 1) ** 1.4
    base_rgb = mix(base_rgb, np.array([210, 230, 168]), (hl * 0.16)[:, :, None])
    return base_rgb, ba, sh_rgb, sh_a

def composite(base_rgb, ba, sh_rgb, sh_a, glyph_rgb, glyph_a):
    """Composite shadow + gradient tile + glyph."""
    H = W = S
    out = np.zeros((H, W, 3), float)
    # shadow
    out = out * (1 - sh_a[:, :, None]) + sh_rgb * sh_a[:, :, None]
    a_out = sh_a.copy()
    # base
    out = out * (1 - ba[:, :, None]) + base_rgb * ba[:, :, None]
    a_out = np.maximum(a_out, ba)
    # glyph
    out = out * (1 - glyph_a[:, :, None]) + glyph_rgb * glyph_a[:, :, None]
    a_out = np.maximum(a_out, glyph_a)
    img = np.dstack([np.clip(out, 0, 255), np.clip(a_out * 255, 0, 255)])
    img = Image.fromarray(img.astype(np.uint8), "RGBA")
    img = img.resize((FINAL, FINAL), Image.LANCZOS)
    return img

def glyph_check():
    yy, xx = np.mgrid[0:S, 0:S]
    cx = cy = S / 2.0
    s = S * 0.5
    # two thick rounded segments forming a check
    d1 = sdf_segment(xx, yy, cx - s * 0.36, cy + s * 0.04, cx - s * 0.10, cy + s * 0.30, S * 0.058)
    d2 = sdf_segment(xx, yy, cx - s * 0.10, cy + s * 0.30, cx + s * 0.40, cy - s * 0.34, S * 0.058)
    d = np.minimum(d1, d2)
    return smooth(d), np.array([255, 255, 255], float)

def glyph_leaf():
    yy, xx = np.mgrid[0:S, 0:S]
    cx = cy = S / 2.0
    s = S * 0.46
    # leaf = rotated ellipse (rx small, ry large) minus a small tip notch
    ang = -np.pi / 4.0
    dx = xx - cx; dy = yy - cy
    rx = dx * np.cos(ang) - dy * np.sin(ang)
    ry = dx * np.sin(ang) + dy * np.cos(ang)
    # normalized ellipse SDF (approx via metaball-ish): use (rx/a)^2+(ry/b)^2 <=1
    a = s * 0.22; b = s * 0.5
    e = (rx / a) ** 2 + (ry / b) ** 2 - 1.0
    d = e * (a * 0.5)  # scale to ~px
    # vein: thin capsule along major axis
    vd = sdf_segment(xx, yy, cx - rxW(s), cy - ryW(s), cx + rxW(s), cy + ryW(s), S * 0.012)
    d = np.minimum(d, vd)
    return smooth(d), np.array([255, 255, 255], float)

def rxW(s): return s * 0.34 * 0.7071
def ryW(s): return s * 0.34 * 0.7071

def glyph_list():
    yy, xx = np.mgrid[0:S, 0:S]
    cx = cy = S / 2.0
    s = S * 0.34
    # three checklist rows: bullet circle + line
    ds = []
    rows = [cy - s * 0.55, cy, cy + s * 0.55]
    for i, ry0 in enumerate(rows):
        bx = cx - s * 0.42
        # bullet
        bd = sdf_circle(xx, yy, bx, ry0, S * 0.035)
        # line
        ld = sdf_segment(xx, yy, bx + S * 0.07, ry0, cx + s * 0.42, ry0, S * 0.026)
        # first row gets a check inside bullet
        row = np.minimum(bd, ld)
        if i == 0:
            c1 = sdf_segment(xx, yy, bx - S * 0.018, ry0 + S * 0.004, bx - S * 0.004, ry0 + S * 0.018, S * 0.011)
            c2 = sdf_segment(xx, yy, bx - S * 0.004, ry0 + S * 0.018, bx + S * 0.020, ry0 - S * 0.018, S * 0.011)
            check = np.minimum(c1, c2)
            row = np.minimum(row, check)
        ds.append(row)
    d = np.minimum.reduce(ds)
    return smooth(d), np.array([255, 255, 255], float)

def glyph_lime():
    """Citrus slice: outer rind ring + white segment wedges + center."""
    yy, xx = np.mgrid[0:S, 0:S]
    cx = cy = S / 2.0
    R = S * 0.40
    r_outer = sdf_circle(xx, yy, cx, cy, R)
    r_inner = sdf_circle(xx, yy, cx, cy, R * 0.86)
    rind = np.maximum(r_outer, -r_inner)          # ring band
    # segments: radial wedges (white) cut into inner disc
    dx = xx - cx; dy = yy - cy
    ang = np.arctan2(dy, dx)
    n = 9
    seg = np.abs(((ang + np.pi) % (2 * np.pi / n)) - (np.pi / n))
    # wedge mask within inner disc
    wedge = np.maximum(r_inner, (np.pi / n - seg) - 0.06)  # thin white lines
    # pulp fill (inner disc soft white ring near rind)
    pulp = np.maximum(r_inner, -sdf_circle(xx, yy, cx, cy, R * 0.80))
    d = np.minimum(rind, np.minimum(wedge, pulp))
    # center dot
    d = np.minimum(d, sdf_circle(xx, yy, cx, cy, R * 0.10))
    return smooth(d), np.array([244, 251, 232], float)

def glyph_ring():
    yy, xx = np.mgrid[0:S, 0:S]
    cx = cy = S / 2.0
    s = S * 0.46
    ring = np.abs(sdf_circle(xx, yy, cx, cy, S * 0.30)) - S * 0.052
    c1 = sdf_segment(xx, yy, cx - s * 0.30, cy + s * 0.02, cx - s * 0.06, cy + s * 0.26, S * 0.05)
    c2 = sdf_segment(xx, yy, cx - s * 0.06, cy + s * 0.26, cx + s * 0.32, cy - s * 0.30, S * 0.05)
    d = np.minimum(ring, np.minimum(c1, c2))
    return smooth(d), np.array([255, 255, 255], float)

# ---- palette ----
PRIMARY = (91, 138, 58)
DARK = (70, 105, 43)      # #46692B depth
SECOND = (123, 174, 92)
LIME = (156, 200, 115)

icons = [
    # (name, shape, g_top, g_bottom, glyph_fn)
    ("1-check",   "square", SECOND, DARK,    glyph_check),
    ("2-leaf",    "square", (143,190,106), PRIMARY, glyph_leaf),
    ("3-list",    "square", (111,168,78), DARK, glyph_list),
    ("4-lime",    "disc",   LIME,  PRIMARY, glyph_lime),
    ("5-ring",    "square", SECOND, (63,99,38), glyph_ring),
]

outdir = "D:/WorkSpace/cloudbuddy/qingNingTodo/tools/icon_preview"
import os
os.makedirs(outdir, exist_ok=True)

paths = []
for name, shape, gt, gb, gfn in icons:
    base_rgb, ba, sh_rgb, sh_a = make_base(shape, gt, gb)
    glyph_a, glyph_rgb = gfn()
    img = composite(base_rgb, ba, sh_rgb, sh_a, glyph_rgb, glyph_a)
    p = os.path.join(outdir, f"icon_{name}.png")
    img.save(p)
    paths.append(p)
    print("saved", p)

# contact sheet 1x5
sheet_w = FINAL * 5 + 40
sheet = Image.new("RGBA", (sheet_w, FINAL + 20), (245, 247, 242, 255))
for i, p in enumerate(paths):
    im = Image.open(p)
    sheet.alpha_composite(im, (i * FINAL + 10, 10))
sheet.convert("RGB").save(os.path.join(outdir, "icon_sheet.png"))
print("saved sheet", os.path.join(outdir, "icon_sheet.png"))
