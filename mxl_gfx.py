"""Icônes des objets (Median XL 2.14.5) : décodage des fichiers DC6 et extraction en PNG dans data/items/.

Recherche d'un fichier dans l'ordre du jeu : MPQ de Median XL (« itemsgfx » = medianxl-aXRlbXNnZng.mpq),
puis patch_d2.mpq, d2exp.mpq, d2data.mpq. Palette : data\\global\\palette\\act1\\pal.dat (256 × BGR).
"""
import os, glob, struct
from PIL import Image
from mpq import MPQ

LAYER_OPACITY = {1: 1.0, 2: 0.5, 3: 0.5}   # calques 2 et 3 à 50 % pour garder le calque 1 prépondérant (choix du 26/09)
ETHEREAL_OPACITY = 0.5   # objet éthéré : icône (calque 1) à 50 % sur le fond de la case, translucide comme dans le jeu

ITEMS_DIR = r'data\global\items'
PALETTE = r'data\global\palette\act1\pal.dat'


def open_archives(game_dir):
    """MPQ dans l'ordre de priorité du jeu (Median XL d'abord)."""
    names = sorted(glob.glob(os.path.join(game_dir, 'medianxl-*.mpq')))
    names += [os.path.join(game_dir, n) for n in ('patch_d2.mpq', 'd2exp.mpq', 'd2data.mpq')]
    return [MPQ(n) for n in names if os.path.exists(n)]


def read_file(archives, name):
    for m in archives:
        if m.find(name) is not None:
            return m.read(name)
    return None


def load_palette(archives):
    raw = read_file(archives, PALETTE)
    return [(raw[i * 3 + 2], raw[i * 3 + 1], raw[i * 3]) for i in range(256)]   # BGR -> RGB


def decode_dc6(raw, palette, frame=0):
    """Image RGBA de la frame d'un DC6. En-tête : version, flags, encodage, terminaison, directions,
    frames par direction (6 × u32), puis pointeurs de frames (u32). Frame : flip, largeur, hauteur,
    décalages x / y, inconnu, bloc suivant, longueur (8 × u32), données RLE. RLE : 0x80 = ligne suivante,
    bit 7 = saut de (b & 0x7F) pixels transparents, sinon b pixels (indices de palette). Lignes de bas en haut
    sauf si flip."""
    dirs, fpd = struct.unpack_from('<II', raw, 16)
    ptr = struct.unpack_from('<I', raw, 24 + 4 * frame)[0]
    flip, w, h, ox, oy, _, _, length = struct.unpack_from('<8I', raw, ptr)
    data = raw[ptr + 32:ptr + 32 + length]
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    px = img.load()
    x, y = 0, 0 if flip else h - 1
    i = 0
    while i < len(data):
        b = data[i]; i += 1
        if b == 0x80:
            x = 0; y += 1 if flip else -1
        elif b & 0x80:
            x += b & 0x7F
        else:
            for _ in range(b):
                if 0 <= x < w and 0 <= y < h:
                    r, g, bl = palette[data[i]]
                    px[x, y] = (r, g, bl, 255)
                x += 1; i += 1
    return img


def icon_names(data):
    """Noms des fichiers d'icônes utiles : icône d'inventaire de chaque objet, variantes des types d'objets, icônes
    propres des uniques et des objets de set."""
    return ({n for n in (b.inv_file for b in data.bases.values()) if n} | {n for var in data.itype_gfx for n in var if n}
            | {r['inv_file'] for r in data.uniques + data.set_items if r['inv_file']})


def extract_icons(game_dir, data, out='data/items', progress=None):
    """Décode toutes les icônes en PNG dans out/. Renvoie (extraites, introuvables).
    progress(fait, total) est appelé après chaque icône."""
    archives = open_archives(game_dir)
    palette = load_palette(archives)
    os.makedirs(out, exist_ok=True)
    ok, missing = 0, []
    names = sorted(icon_names(data))
    for k, n in enumerate(names):
        raw = read_file(archives, f'{ITEMS_DIR}\\{n}.dc6')
        if raw is None:
            missing.append(n)
        else:
            decode_dc6(raw, palette).save(os.path.join(out, n + '.png'))
            ok += 1
        if progress:
            progress(k + 1, len(names))
    return ok, missing


def icon_name(it, data):
    """Nom de l'icône d'un objet : icône propre de l'unique ou de l'objet de set (table), sinon icône de base."""
    from mxl_rules import unique_row, set_row
    row = unique_row(it, data) or set_row(it, data)
    return row['inv_file'] if row and row['inv_file'] else base_icon_name(it, data)


def has_variants(code, data):
    """Le type de l'objet a plusieurs apparences (variantes, tirées au hasard sur chaque exemplaire), sauf objet de
    quête à icône dédiée (icône d'aucun autre objet de base du même type : ✅ Amulet of the Viper « invvip »,
    Time-Lost Relic ; la relique générique, icône « invgswe » partagée avec d'autres reliques, garde ses variantes)."""
    b = data.base(code)
    var = data.itype_gfx[b.type] if 0 <= b.type < len(data.itype_gfx) else []
    if sum(1 for v in var if v) < 2:
        return False
    if b.quest and b.inv_file:
        shared = sum(1 for o in data.bases.values() if o.type == b.type and o.inv_file.lower() == b.inv_file.lower())
        return shared > 1
    return True


def base_icon_name(it, data):
    """Icône sans icône propre : variante du type d'objet choisie par le champ « image » de l'objet (bagues,
    amulettes, joyaux, charmes…), sinon icône d'inventaire de l'objet de base."""
    t = data.base(it['code']).type
    var = data.itype_gfx[t] if 0 <= t < len(data.itype_gfx) else []
    if has_variants(it['code'], data) and it.get('image') is not None and it['image'] < len(var) and var[it['image']]:
        return var[it['image']]
    return data.base(it['code']).inv_file


UI_FILES = {'gemsocket': r'data\global\ui\PANEL\gemsocket.dc6'}   # slot de sertissage (28 × 28)

# icônes des compétences (48 × 48) : un fichier DC6 par classe (n° de classe 0 à 6) + un fichier commun (compétences
# sans classe, 255) dans le thème de Median XL ; image = n° d'icône de la compétence (Data.skill_icon)
SKILL_ICONS_DIR = r'data\global\themes\classic_sigma\game\skills'
SKILL_ICON_FILES = ('ama', 'sor', 'nec', 'pal', 'bar', 'dru', 'ass')
SKILL_ICON_SHARED = 'shared'


def skill_icon_file(sid, data):
    """Nom du fichier PNG de l'icône d'une compétence dans data/skills (« shared_92 »), ou None : pas de fiche, ou
    compétence sans description dont l'icône est l'image 0 du fichier commun (« ? » : Thunder Wave). Une compétence
    décrite garde l'icône que le jeu lui donne, même « ? » (Thunder Hammer Nova)."""
    if sid not in data.skill_icon:
        return None
    cls = data.skill_class.get(sid, 255)
    group = SKILL_ICON_FILES[cls] if cls < len(SKILL_ICON_FILES) else SKILL_ICON_SHARED
    if group == SKILL_ICON_SHARED and data.skill_icon[sid] == 0 and not data.skill_desc.get(sid):
        return None
    return f'{group}_{data.skill_icon[sid]}'


def skill_icon_image(archives, palette, name, cache=None):
    """Image de l'icône name (« <fichier>_<n° d'image> »), ou None (fichier ou image absents). cache : fichiers DC6
    déjà lus."""
    group, frame = name.rsplit('_', 1)
    cache = {} if cache is None else cache
    if group not in cache:
        cache[group] = read_file(archives, f'{SKILL_ICONS_DIR}\\icons-{group}.dc6')
    raw = cache[group]
    if raw is None:
        return None
    dirs, per_dir = struct.unpack_from('<II', raw, 16)
    return decode_dc6(raw, palette, int(frame)) if int(frame) < dirs * per_dir else None


def extract_skill_icons(game_dir, data, out='data/skills', progress=None):
    """Icônes des compétences nommées en PNG dans out/ (une par image utilisée). Renvoie (extraites, introuvables)."""
    archives = open_archives(game_dir)
    palette = load_palette(archives)
    os.makedirs(out, exist_ok=True)
    names = sorted({skill_icon_file(sid, data) for sid in data.skill_names if data.skill_names[sid]} - {None})
    ok, missing, cache = 0, [], {}
    for k, n in enumerate(names):
        img = skill_icon_image(archives, palette, n, cache)
        if img is None:
            missing.append(n)
        else:
            img.save(os.path.join(out, n + '.png'))
            ok += 1
        if progress:
            progress(k + 1, len(names))
    return ok, missing


def extract_ui(game_dir, out='data/items'):
    """Graphismes d'interface utiles (slot de sertissage) en PNG dans out/."""
    archives = open_archives(game_dir)
    palette = load_palette(archives)
    os.makedirs(out, exist_ok=True)
    for n, path in UI_FILES.items():
        raw = read_file(archives, path)
        if raw:
            decode_dc6(raw, palette).save(os.path.join(out, n + '.png'))


ICON_CELL = 28   # taille d'une case dans les icônes du jeu (DC6), en pixels


def socket_positions(w, h, n, cell=ICON_CELL):
    """Coins haut-gauche (en pixels, cases de 28 px) des n slots d'un objet de w × h cases, disposition du jeu :
    1 colonne centrée (objets d'une case de large, ou 1 à 3 slots), 4 = carré 2 × 2, 5 = X (2 + 1 + 2),
    6 = 2 × 3 ; ensemble centré dans l'objet. ✅ Warp Blade 1 × 3 et Scale Mail 2 × 3 à 2 slots."""
    if w == 1 or n <= 3 and h >= n:
        cells = [(0, k) for k in range(n)]
        cols, rows = 1, n
    elif n == 3:        # objet 2 × 2 : 2 en haut, 1 centré en bas
        cells, cols, rows = [(0, 0), (1, 0), (0.5, 1)], 2, 2
    elif n == 4:
        cells, cols, rows = [(0, 0), (1, 0), (0, 1), (1, 1)], 2, 2
    elif n == 5:
        cells, cols, rows = [(0, 0), (1, 0), (0.5, 1), (0, 2), (1, 2)], 2, 3
    else:
        cells, cols, rows = [(k % 2, k // 2) for k in range(n)], 2, (n + 1) // 2
    x0, y0 = (w - cols) * cell / 2, (h - rows) * cell / 2
    return [(round(x0 + cx * cell), round(y0 + cy * cell)) for cx, cy in cells]


def icon_layers(it, data, bg, folder='data/items'):
    """Les 3 calques de l'image d'un objet (vocabulaire du projet, voir docs/ihm.md), chacun une image
    RGBA de w × h cases de 28 px, transparente hors de son contenu, à superposer dans l'ordre 1, 2, 3 :
    - calque 1 : fond de la case (bg) + icône de l'objet ;
    - calque 2 : slots de sertissage **vides** (un slot occupé par un objet serti n'est pas dessiné). Le jeu les fusionne en mode « screen » sur l'objet (le noir du slot laisse
      voir l'objet, l'anneau s'éclaircit) : ce calque contient donc les pixels déjà fusionnés avec le calque 1,
      uniquement là où le slot a des pixels ;
    - calque 3 : objets sertis (runes, gemmes, joyaux), dans les premiers slots.
    Les calques 2 et 3 sont rendus à l'opacité LAYER_OPACITY (50 %) ; objet éthéré : icône du calque 1 à
    ETHEREAL_OPACITY (50 %) sur le fond.
    Renvoie {1: image, 2: image ou None, 3: image ou None}, ou None si l'icône de l'objet est absente."""
    from PIL import ImageChops
    # icône propre de l'unique / objet de set, sinon (ou pas encore extraite : data/ d'avant) icône de base
    paths = [os.path.join(folder, f'{n}.png') for n in (icon_name(it, data), base_icon_name(it, data)) if n]
    path = next((p for p in paths if os.path.exists(p)), None)
    if not path:
        return None
    w, h = data.base(it['code']).size
    size = (w * ICON_CELL, h * ICON_CELL)
    layer1 = Image.new('RGBA', size, bg)
    icon = Image.open(path).convert('RGBA')
    layer1.alpha_composite(icon, ((size[0] - icon.width) // 2, (size[1] - icon.height) // 2))
    if it.get('ethereal'):   # éthéré : icône estompée sur le fond (le calque 2 est fusionné avec ce calque estompé)
        layer1 = Image.blend(Image.new('RGBA', size, bg), layer1, ETHEREAL_OPACITY)
    layers = {1: layer1, 2: None, 3: None}
    n = it.get('sockets') or 0
    sock_path = os.path.join(folder, 'gemsocket.png')
    if not n or not os.path.exists(sock_path):
        return layers
    sock = Image.open(sock_path).convert('RGBA')
    pos = socket_positions(w, h, n)
    layer2 = Image.new('RGBA', size, (0, 0, 0, 0))
    filled = len(it.get('socketed', []))   # les objets sertis occupent les premiers slots
    for x, y in pos[filled:]:   # seuls les slots vides sont dessinés
        under = layer1.crop((x, y, x + ICON_CELL, y + ICON_CELL)).convert('RGB')
        blended = ImageChops.screen(under, sock.convert('RGB')).convert('RGBA')
        layer2.paste(blended, (x, y), sock)          # seulement là où le slot a des pixels
    layers[2] = layer2 if len(pos) > filled else None   # aucun slot vide : pas de calque 2
    subs = it.get('socketed', [])
    if subs:
        layer3 = Image.new('RGBA', size, (0, 0, 0, 0))
        for (x, y), sub in zip(pos, subs):
            sn = icon_name(sub, data)
            sp = os.path.join(folder, f'{sn}.png') if sn else None
            if sp and os.path.exists(sp):
                g = Image.open(sp).convert('RGBA')
                layer3.alpha_composite(g, (x + (ICON_CELL - g.width) // 2, y + (ICON_CELL - g.height) // 2))
        layers[3] = layer3
    for k in (2, 3):   # opacité des calques 2 et 3
        if layers[k] is not None and LAYER_OPACITY[k] < 1:
            a = layers[k].getchannel('A').point(lambda v, f=LAYER_OPACITY[k]: round(v * f))
            layers[k].putalpha(a)
    return layers
