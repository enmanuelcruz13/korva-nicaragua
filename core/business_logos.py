"""Generador de avatares para negocios basados en su actividad.

Crea un logo por defecto (logo 'auto') cuyo ícono corresponde al giro del negocio
detectado por palabras clave del nombre o por su sector. Se regraba en cada seed
para que los archivos existan tras cada rebuild de Render (disco efímero).
"""
import unicodedata
import os

from PIL import Image, ImageDraw, ImageFont

SIZE = 512

# Paletas por sector
PALETTES = {
    'alimentos': ((252, 186, 3, 255), (146, 64, 14, 255)),      # ámbar
    'agropecuario': ((74, 222, 128, 255), (24, 101, 47, 255)),  # verde campo
    'artesanias': ((45, 212, 191, 255), (15, 82, 74, 255)),     # turquesa
    'tecnologia': ((96, 165, 250, 255), (30, 64, 175, 255)),    # azul
    'textil': ((244, 114, 182, 255), (131, 24, 67, 255)),       # rosa
    'servicios': ((129, 140, 248, 255), (49, 46, 129, 255)),    # índigo
    'otros': ((148, 163, 184, 255), (30, 41, 59, 255)),         # pizarra
}
DEFAULT_PALETTE = PALETTES['otros']


def _norm(s):
    s = unicodedata.normalize('NFD', s)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn').lower()


def _motif(name, sector):
    """Elige un ícono según lo que hace el negocio."""
    n = _norm(name)
    if any(k in n for k in ('cafe', 'coffee', 'tostador', 'finca')):
        return 'coffee'
    if any(k in n for k in ('pesc', 'maris', 'camaron', 'camar', 'pesque')):
        return 'fish'
    if any(k in n for k in ('carne', 'carnic', 'embut')):
        return 'meat'
    if any(k in n for k in ('ganad', 'lecher')):
        return 'cow'
    if any(k in n for k in ('panader', 'panific', 'reposter', 'torta')):
        return 'bread'
    if any(k in n for k in ('mader', 'aserrader')):
        return 'tree'
    if any(k in n for k in ('termal', 'turismo', 'aventur', 'agroturis', 'ecoturis')):
        return 'mountain'
    if any(k in n for k in ('granos', 'agric', 'agro', 'cafe')):
        return 'wheat'
    if sector == 'alimentos':
        return 'coffee'
    if sector == 'agropecuario':
        return 'wheat'
    if sector == 'artesanias':
        return 'pot'
    if sector == 'tecnologia':
        return 'chip'
    if sector == 'textil':
        return 'shirt'
    if sector == 'servicios':
        return 'shield'
    return 'box'


def _font(size):
    try:
        return ImageFont.truetype('DejaVuSans-Bold.ttf', size)
    except Exception:
        return ImageFont.load_default(size)


def _gradient(size, colors):
    top, bottom = colors
    img = Image.new('RGB', (size, size))
    px = img.load()
    for y in range(size):
        t = y / (size - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        for x in range(size):
            px[x, y] = (r, g, b)
    return img


def _round(img, radius):
    mask = Image.new('L', img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1], radius=radius, fill=255)
    out = img.convert('RGBA')
    out.putalpha(mask)
    return out


# ---------- Dibujos de íconos (centrados en la insignia blanca) ----------

def _inner():
    layer = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    return ImageDraw.Draw(layer), layer


def _icon_coffee(d, cx, cy, s, c):
    # taza
    d.rounded_rectangle((cx - int(.38 * s), cy - int(.30 * s), cx + int(.36 * s), cy + int(.28 * s)),
                        radius=int(.10 * s), fill=c)
    d.rectangle((cx - int(.38 * s), cy - int(.02 * s), cx + int(.36 * s), cy + int(.05 * s)), fill=c)
    d.ellipse((cx - int(.34 * s), cy + int(.26 * s), cx + int(.32 * s), cy + int(.34 * s)), fill=c)
    # asa
    d.arc((cx + int(.28 * s), cy - int(.22 * s), cx + int(.58 * s), cy + int(.18 * s)),
          start=-60, end=90, fill=c, width=int(.075 * s))
    # vapor
    for dx in (-int(.29 * s), -int(.15 * s), -int(.01 * s)):
        d.arc((cx + dx - int(.09 * s), cy - int(.52 * s), cx + dx + int(.09 * s), cy - int(.30 * s)),
              start=180, end=360, fill=c, width=int(.05 * s))


def _icon_fish(d, cx, cy, s, c):
    d.ellipse((cx - int(.42 * s), cy - int(.22 * s), cx + int(.34 * s), cy + int(.22 * s)), fill=c)
    d.polygon(((cx + int(.30 * s), cy), (cx + int(.60 * s), cy - int(.26 * s)), (cx + int(.60 * s), cy + int(.26 * s))),
              fill=c)
    d.ellipse((cx - int(.24 * s), cy - int(.07 * s), cx - int(.10 * s), cy + int(.07 * s)), fill=(255, 255, 255, 255))
    d.arc((cx + int(.12 * s), cy - int(.08 * s), cx + int(.28 * s), cy + int(.08 * s)), start=-90, end=90,
          fill=(255, 255, 255, 255), width=int(.04 * s))


def _icon_meat(d, cx, cy, s, c):
    pts = [(cx - int(.44 * s), cy - int(.16 * s)), (cx - int(.06 * s), cy - int(.28 * s)),
           (cx + int(.34 * s), cy - int(.10 * s)), (cx + int(.40 * s), cy + int(.14 * s)),
           (cx + int(.08 * s), cy + int(.30 * s)), (cx - int(.34 * s), cy + int(.20 * s))]
    d.polygon(pts, fill=c)
    d.line((cx + int(.14 * s), cy - int(.16 * s), cx + int(.02 * s), cy + int(.12 * s)),
           fill=(255, 255, 255, 255), width=int(.045 * s))
    d.line((cx + int(.02 * s), cy + int(.12 * s), cx + int(.16 * s), cy + int(.14 * s)),
           fill=(255, 255, 255, 255), width=int(.045 * s))


def _icon_bread(d, cx, cy, s, c):
    d.rounded_rectangle((cx - int(.44 * s), cy - int(.10 * s), cx + int(.44 * s), cy + int(.30 * s)),
                        radius=int(.16 * s), fill=c)
    d.arc((cx - int(.44 * s), cy - int(.30 * s), cx + int(.44 * s), cy + int(.20 * s)), start=0, end=180,
          fill=c, width=int(.14 * s))
    for dx in (-int(.22 * s), 0, int(.22 * s)):
        d.line((cx + dx - int(.06 * s), cy - int(.02 * s), cx + dx + int(.06 * s), cy + int(.18 * s)),
               fill=(255, 255, 255, 200), width=int(.04 * s))


def _icon_wheat(d, cx, cy, s, c):
    d.line((cx, cy + int(.40 * s), cx, cy - int(.34 * s)), fill=c, width=int(.05 * s))
    for angle, dx, dy in ((-45, -.12, -.16), (-30, -.16, -.02), (30, .16, -.02), (45, .12, -.16),
                          (-45, .12, -.16), (45, -.12, -.16)):
        # granos: pequeñas elipses a ambos lados
        pass
    for i, dx in enumerate((-int(.20 * s), int(.20 * s))):
        d.ellipse((cx + dx - int(.10 * s), cy - int(.30 * s) + i * int(.05 * s),
                   cx + dx + int(.10 * s), cy - int(.10 * s) + i * int(.05 * s)), fill=c)
    d.ellipse((cx - int(.16 * s), cy - int(.42 * s), cx + int(.16 * s), cy - int(.10 * s)), fill=c)


def _icon_tree(d, cx, cy, s, c):
    d.polygon(((cx, cy - int(.44 * s)), (cx - int(.40 * s), cy + int(.10 * s)), (cx + int(.40 * s), cy + int(.10 * s))),
              fill=c)
    d.rectangle((cx - int(.08 * s), cy + int(.10 * s), cx + int(.08 * s), cy + int(.40 * s)), fill=(120, 70, 30, 255))


def _icon_cow(d, cx, cy, s, c):
    d.ellipse((cx - int(.28 * s), cy - int(.26 * s), cx + int(.28 * s), cy + int(.26 * s)), fill=c)
    d.polygon(((cx - int(.26 * s), cy - int(.16 * s)), (cx - int(.42 * s), cy - int(.30 * s)),
               (cx - int(.34 * s), cy - int(.02 * s))), fill=c)
    d.polygon(((cx + int(.26 * s), cy - int(.16 * s)), (cx + int(.42 * s), cy - int(.30 * s)),
               (cx + int(.34 * s), cy - int(.02 * s))), fill=c)
    for dx in (-int(.09 * s), int(.01 * s)):
        d.ellipse((cx + dx - int(.04 * s), cy + int(.08 * s), cx + dx + int(.06 * s), cy + int(.18 * s)),
                  fill=(255, 255, 255, 255))
        d.ellipse((cx + dx - int(.015 * s), cy + int(.10 * s), cx + dx + int(.025 * s), cy + int(.14 * s)),
                  fill=(60, 30, 10, 255))


def _icon_chip(d, cx, cy, s, c):
    d.rounded_rectangle((cx - int(.34 * s), cy - int(.34 * s), cx + int(.34 * s), cy + int(.34 * s)),
                        radius=int(.06 * s), fill=c)
    d.rounded_rectangle((cx - int(.18 * s), cy - int(.18 * s), cx + int(.18 * s), cy + int(.18 * s)),
                        radius=int(.04 * s), fill=(255, 255, 255, 255))
    for dx in (-int(.44 * s), -int(.22 * s), 0, int(.22 * s), int(.44 * s)):
        d.line((cx + dx, cy - int(.46 * s), cx + dx, cy - int(.10 * s)), fill=c, width=int(.045 * s))
        d.line((cx + dx, cy + int(.10 * s), cx + dx, cy + int(.46 * s)), fill=c, width=int(.045 * s))
        d.line((cx - int(.46 * s), cy + dx, cx - int(.10 * s), cy + dx), fill=c, width=int(.045 * s))
        d.line((cx + int(.10 * s), cy + dx, cx + int(.46 * s), cy + dx), fill=c, width=int(.045 * s))


def _icon_shirt(d, cx, cy, s, c):
    d.polygon(((cx - int(.34 * s), cy - int(.40 * s)), (cx - int(.44 * s), cy + int(.02 * s)),
               (cx - int(.28 * s), cy + int(.06 * s)), (cx - int(.20 * s), cy - int(.02 * s)),
               (cx - int(.14 * s), cy + int(.38 * s)), (cx + int(.14 * s), cy + int(.38 * s)),
               (cx + int(.20 * s), cy - int(.02 * s)), (cx + int(.28 * s), cy + int(.06 * s)),
               (cx + int(.44 * s), cy + int(.02 * s)), (cx + int(.34 * s), cy - int(.40 * s)),
               (cx + int(.06 * s), cy - int(.28 * s)), (cx - int(.06 * s), cy - int(.28 * s))), fill=c)


def _icon_pot(d, cx, cy, s, c):
    d.polygon(((cx, cy - int(.42 * s)), (cx + int(.36 * s), cy), (cx, cy + int(.42 * s)),
               (cx - int(.36 * s), cy)), fill=c)
    d.line((cx - int(.24 * s), cy, cx + int(.24 * s), cy), fill=(255, 255, 255, 255), width=int(.035 * s))
    d.line((cx, cy - int(.28 * s), cx, cy + int(.28 * s)), fill=(255, 255, 255, 200), width=int(.035 * s))


def _icon_shield(d, cx, cy, s, c):
    d.polygon(((cx, cy - int(.44 * s)), (cx - int(.38 * s), cy - int(.26 * s)), (cx - int(.38 * s), cy + int(.02 * s)),
               (cx, cy + int(.38 * s)), (cx + int(.38 * s), cy + int(.02 * s)), (cx + int(.38 * s), cy - int(.26 * s))),
              fill=c)
    d.line((cx - int(.16 * s), cy - int(.02 * s), cx - int(.02 * s), cy + int(.12 * s)),
           fill=(255, 255, 255, 255), width=int(.05 * s))
    d.line((cx - int(.02 * s), cy + int(.12 * s), cx + int(.18 * s), cy - int(.10 * s)),
           fill=(255, 255, 255, 255), width=int(.05 * s))


def _icon_box(d, cx, cy, s, c):
    d.polygon(((cx, cy - int(.40 * s)), (cx + int(.40 * s), cy - int(.20 * s)), (cx + int(.40 * s), cy + int(.16 * s)),
               (cx, cy + int(.36 * s)), (cx - int(.40 * s), cy + int(.16 * s)), (cx - int(.40 * s), cy - int(.20 * s))),
              fill=c)
    d.line((cx - int(.40 * s), cy - int(.20 * s), cx, cy), fill=(255, 255, 255, 220), width=int(.04 * s))
    d.line((cx + int(.40 * s), cy - int(.20 * s), cx, cy), fill=(255, 255, 255, 220), width=int(.04 * s))
    d.line((cx, cy, cx, cy + int(.36 * s)), fill=(255, 255, 255, 220), width=int(.04 * s))


def _icon_mountain(d, cx, cy, s, c):
    d.polygon(((cx - int(.46 * s), cy + int(.28 * s)), (cx - int(.12 * s), cy - int(.30 * s)),
               (cx + int(.14 * s), cy + int(.04 * s)), (cx + int(.30 * s), cy - int(.16 * s)),
               (cx + int(.46 * s), cy + int(.28 * s))), fill=c)
    d.line((cx - int(.46 * s), cy + int(.28 * s), cx + int(.46 * s), cy + int(.28 * s)),
           fill=c, width=int(.05 * s))


_ICONS = {
    'coffee': _icon_coffee,
    'fish': _icon_fish,
    'meat': _icon_meat,
    'bread': _icon_bread,
    'wheat': _icon_wheat,
    'tree': _icon_tree,
    'cow': _icon_cow,
    'chip': _icon_chip,
    'shirt': _icon_shirt,
    'pot': _icon_pot,
    'shield': _icon_shield,
    'box': _icon_box,
    'mountain': _icon_mountain,
}


def make_business_logo(business_name, sector):
    """Genera y devuelve un objeto Image RGBA con el avatar del negocio."""
    motif = _motif(business_name, sector)
    top, bottom = PALETTES.get(sector, DEFAULT_PALETTE)
    img = _round(_gradient(SIZE, (top, bottom)), radius=int(SIZE * 0.12))

    draw = ImageDraw.Draw(img)
    # insignia blanca
    cx = cy = SIZE // 2
    draw.ellipse((cx - 180, cy - 180, cx + 180, cy + 180), fill=(255, 255, 255, 255),
                 outline=(255, 255, 255, 120), width=6)

    icon_color = top
    ov, icon_layer = _inner()
    _ICONS.get(motif, _icon_box)(ov, cx, cy - 30, 150, icon_color)
    img = Image.alpha_composite(img, icon_layer)

    # iniciales del negocio
    words = [w for w in business_name.replace('-', ' ').split() if w and w.lower() not in ('de', 'del', 'la', 'el', 'los', 'las', 'y', 'e', 'o')]
    initials = ''.join(w[0] for w in words[:2]).upper()
    if initials:
        f = _font(int(SIZE * 0.12))
        d2 = ImageDraw.Draw(img)
        w = d2.textlength(initials, font=f)
        d2.text(((SIZE - w) / 2, cy + 118), initials, font=f, fill=icon_color)

    return img


def save_business_logo(username, business_name, sector, media_root):
    """Guarda el logo en MEDIA_ROOT/logos/auto_<username>.png y devuelve su 'name' relativo."""
    logos_dir = os.path.join(media_root, 'logos')
    os.makedirs(logos_dir, exist_ok=True)
    rel_name = f'logos/auto_{username}.png'
    img = make_business_logo(business_name, sector)
    img.save(os.path.join(media_root, rel_name), 'PNG')
    return rel_name