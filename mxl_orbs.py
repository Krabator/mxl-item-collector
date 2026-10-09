"""Mystic Orbs appliqués à un objet, et explication d'un orbe au survol, sans interface (testable seul).

Le jeu (D2Sigma, pas de recette du cube) enregistre dans l'objet un compteur par orbe : stat 290 (ORB_COUNT), param
= n° de ligne de mysticorbs.bin (mxl_data.Data.mystic_orbs), valeur = nombre d'applications ; stat 289 (ORBS_DOUBLED) :
multiplicateur de l'objet, appliqué à chaque orbe posé dessus (règle confirmée en jeu, 08/10) : absente = 1 (objet
ordinaire), 2 = « Doubled » (objets honorifiques, 10 uniques), 4 = « Quadrupled » (Natalya's Deception). Certains orbes
verrouillent leurs contraires en ajoutant à leur compteur (mod 403 de leur ligne : Apple of Discord <-> Apple of
Discord 2 ; Imperfect Spheres entre elles) : orbes réellement appliqués = solution de compteur = appliqués + verrous,
cherchée par petits groupes ; solution non unique (paire Apple of Discord, verrous symétriques) : orbes du groupe
donnés ensemble.
Objet de chaque ligne (nom, icône) : orb_item. Explication au survol (orb_tooltip) : comme l'infobulle de l'orbe en jeu
(✅ capture de Crystal of Tears ; wiki officiel « Unique Mystic Orbs » : effets, niveau requis, limite par objet).
Effets : ceux de la table actuelle ; un objet garde les valeurs du jour de l'application (✅ Soul Track : Idol of Stars
+14 Force / Dextérité, Periapt of Life +10 vie par seconde, contre +13 et +40 aujourd'hui).
"""
import math
from itertools import product
from mxl_theme import WHITE, GREY

ORB_COUNT = 290      # compteur d'un orbe (param = ligne de mysticorbs.bin)
ORBS_DOUBLED = 289   # multiplicateur des effets des orbes de l'objet (2 : honorifiques, 10 uniques ; 4 : Natalya's Deception)
ORB_PROP = 403       # propriété du compteur, dans les mods d'une ligne d'orbe : verrou d'un autre orbe
REQ_LEVEL_PROP = 78  # propriété « +x Required Level » (stat 92) : niveau requis ajouté par l'orbe, dans l'explication
ORB_NAME_COLOR = 'o'   # nom d'un orbe : orange de la capture en jeu (mxl_theme.GAME_COLORS['o'])
# icône d'un orbe générique (sans objet propre) selon les objets qui l'acceptent (texte de restriction de sa ligne :
# ✅ les 48 orbes génériques) : (Weapon Only), (Armor Only), (Ring, Amulet or Quiver Only), (Any Equippable Item)
CATEGORY_ICON = {11655: 'orb_weap', 11656: 'orb_armo', 11657: 'orb_misc', 11658: 'orb_any'}
GENERIC, NAMED, SOULFORGED = range(48), range(48, 79), (*range(79, 93), 97, 98)
NAMED_ROWS = (*NAMED, 93, 94, 95, 96, 99, 100)   # lignes des orbes à objet propre (nom en deux lignes)
# combinaisons essayées au plus pour démêler un groupe d'orbes verrouillés (applied_orbs) : objets réels très en
# dessous (3 Imperfect Spheres posées 1 fois : 8) ; au-delà (compteurs anormaux, fichier abîmé) : groupe donné
# ensemble, sans gel de l'affichage (audit du 09/10)
MAX_COMBINATIONS = 100_000


def orb_item(k, data):
    """Code de l'objet « Mystic Orb » de la ligne k de mysticorbs.bin, ou None (orbe générique : 48 objets « 01+ »… dont
    le lien avec la ligne est dans le code du jeu, pas dans les tables). Correspondance relevée dans les tables (08/10,
    ✅ noms identiques sauf « Relic of Yaerius » = objet « Hand of Yaerius ») : lignes 48-78 -> &66-&96, 93-96 ->
    &97-&100 (Weight of Talent, 3 Imperfect Spheres), 99-100 -> &101-&102 (Apple of Discord 2, Eye of Beholder),
    Soulforged (lignes 79-92, 97, 98) -> mo01-mo16."""
    if k in NAMED:
        code = f'&{k + 18}'
    elif 93 <= k <= 96:
        code = f'&{k + 4}'
    elif k in (99, 100):
        code = f'&{k + 2}'
    elif k in SOULFORGED:
        code = f'mo{SOULFORGED.index(k) + 1:02d}'
    else:
        return None
    code = code.ljust(4)
    return code if code in data.bases and 'Mystic Orb' in data.base(code).name else None


def orb_name(k, data):
    """Nom d'un orbe dans la liste des orbes appliqués : orbe nommé = nom de son objet (« Crystal of Tears », « Hand of
    Yaerius ») ; générique = nom de sa ligne, « MO - Vitality » -> « Vitality Orb » ; Soulforged : « Rare MO - Max
    Life » -> « Max Life Orb (Soulforged) »."""
    orbs = data.mystic_orbs
    if not 0 <= k < len(orbs):
        return f'#{k}'
    code = orb_item(k, data)
    name = orbs[k]['name']
    if code and k not in SOULFORGED:
        item = data.base(code).name.split('\n')[-1]
        twins = [j for j in NAMED_ROWS if j != k and orb_item(j, data)
                 and data.base(orb_item(j, data)).name.split('\n')[-1] == item]
        if not twins:
            return item
        # même nom d'objet pour plusieurs orbes (3 Imperfect Spheres, 2 Apple of Discord) : variante de la ligne
        return name.replace(' - ', ' (') + ')' if ' - ' in name else name
    for prefix, suffix in (('Rare MO - ', ' Orb (Soulforged)'), ('MO - ', ' Orb')):
        if name.startswith(prefix):
            return name[len(prefix):] + suffix
    return name


def orb_icon(k, data):
    """Fichier d'icône (data/items, sans extension) d'un orbe : celle de son objet, sinon celle de sa catégorie."""
    code = orb_item(k, data)
    if code:
        return data.base(code).inv_file
    orbs = data.mystic_orbs
    return CATEGORY_ICON.get(orbs[k]['only'], 'orb_any') if 0 <= k < len(orbs) else 'orb_any'


def _game_lines(raw):
    """Lignes d'un texte du jeu [[(code couleur, texte)]] dans l'ordre d'affichage (de bas en haut, comme le jeu,
    voir mxl_tooltip.name_lines) ; code de couleur ÿc en tête de ligne, WHITE sinon."""
    from mxl_data import strip_colors
    out = []
    for part in reversed(raw.split('\n')):
        code = part[2] if part.startswith('ÿc') and len(part) > 2 else WHITE
        if strip_colors(part).strip():
            out.append([(code, strip_colors(part))])
    return out


def orb_tooltip(k, data):
    """Explication d'un orbe, comme son infobulle en jeu (✅ capture chez un vendeur, 08/10) sans « Right-Click
    to Apply » (retiré à sa demande) : [[(code couleur, texte)…]] par ligne : nom (orange ; orbe nommé : son nom puis
    « Mystic Orb »), Soulforged : « Rare items only », restriction en gris (« (Armor Only) »…), effets de la table
    (mxl_catalog_tooltip.mods_lines, couleurs du jeu) avec « +x Required Level », « Limit per item: n », puis une note
    grise : valeurs actuelles de l'orbe."""
    from i18n import tr
    from mxl_catalog_tooltip import mods_lines
    from mxl_stat_text import segments
    orb = data.mystic_orbs[k]
    code = orb_item(k, data)
    raw = data.base(code).name_raw if code else 'ÿc8Mystic Orb'
    lines = [[(ORB_NAME_COLOR, text) for _, text in line] for line in _game_lines(raw)]
    if k in SOULFORGED:   # « Rare items only » (texte du jeu avec « Right-Click to Apply », retiré)
        right_click = data.key('GavinMOs')
        lines += [line for line in _game_lines(data.key('RareGavin')) if line[0][1] != right_click]
    only = data.strings.get(orb['only']) if orb['only'] else None
    if only:
        lines.append([(GREY, only[1])])
    mods = [(m['prop'], m['param'], m['min'], m['max']) for m in orb['mods']]
    if orb['req_level']:
        mods.append((REQ_LEVEL_PROP, 0, orb['req_level'], orb['req_level']))
    lines += [segments(color, text) for color, text in mods_lines(mods, data)]
    lines.append([(WHITE, f"{data.key('12387')} {orb['limit']}")])   # « Limit per item: »
    lines.append([(GREY, tr('orbs.current_values'))])
    return lines


def orb_shares(it, data):
    """Part des Mystic Orbs dans chaque stat de l'objet, aux valeurs actuelles des orbes : {(stat, param): [(ligne de
    mysticorbs.bin, valeur enregistrée)]} = mods de l'orbe (valeur fixe) × nombre posé × multiplicateur de l'objet ;
    orbes indiscernables (paire Apple of Discord) écartés : on ne sait pas lequel a été posé. Niveau requis ajouté par
    l'orbe : jamais compté (non ventilé, décision du 08/10)."""
    from mxl_rules import mods_stats
    found, factor = applied_orbs(it, data)
    out = {}
    for rows, n in found:
        if len(rows) != 1 or not 0 <= rows[0] < len(data.mystic_orbs):
            continue
        orb = data.mystic_orbs[rows[0]]
        for st in mods_stats([(m['prop'], m['param'], m['min'], m['max']) for m in orb['mods']], data, 'max'):
            out.setdefault((st['id'], st.get('param')), []).append((rows[0], st['value'] * n * factor))
    return out


NO_OWN_STATS = ('honorific', 'low', 'normal', 'superior')   # objets sans stats propres hors auto-affixe de la base


def own_value_ok(it, sid, param, value, data):
    """La part propre de l'objet (B, stat moins la part des orbes) est-elle possible ? Plage de la stat pour l'objet
    (mxl_rules.stat_range : affixes, table de l'unique / du set, auto-affixe) ; sans plage : 0 pour un objet sans stats
    propres (honorifique : rien hors auto-affixe de la base, règle du 08/10 ; normal, supérieur),
    inconnue sinon (seule une part négative est alors impossible)."""
    from mxl_rules import stat_range
    rng = stat_range(it, sid, data, 'stats', param)
    if rng is not None:
        lo, hi = min(rng), max(rng)
        return lo <= value <= hi
    if it.get('quality') in NO_OWN_STATS:
        return value == 0
    return value >= 0


def orb_mismatch(it, data):
    """Vrai si une stat de l'objet a une part propre impossible une fois retirée la part des orbes (valeurs des orbes
    changées depuis leur pose) : « B » en rouge dans l'infobulle (mxl_stat_text.stat_ranges), note sous la liste."""
    shares = orb_shares(it, data)
    for st in it.get('stats', []):
        key = (st['id'], st.get('param'))
        if key in shares and not own_value_ok(it, st['id'], st.get('param'),
                                              st['value'] - sum(x for _, x in shares[key]), data):
            return True
    return False


def _groups(counts, orbs):
    """Groupes d'orbes liés par des verrous (dans les deux sens), parmi ceux qui ont un compteur."""
    links = {p: set() for p in counts}
    for q in counts:
        for p, _ in (orbs[q]['locks'] if 0 <= q < len(orbs) else ()):
            if p in links:
                links[q].add(p)
                links[p].add(q)
    seen, out = set(), []
    for p in sorted(counts):
        if p in seen:
            continue
        group, todo = [], [p]
        while todo:
            x = todo.pop()
            if x not in seen:
                seen.add(x)
                group.append(x)
                todo += links[x]
        out.append(sorted(group))
    return out


def applied_orbs(it, data):
    """(orbes appliqués, multiplicateur) d'un objet : [(lignes de mysticorbs.bin, nombre)], une ligne par orbe, ou
    plusieurs lignes quand les verrous ne permettent pas de les distinguer ; tri par nombre décroissant puis nom ;
    multiplicateur des effets (stat ORBS_DOUBLED, 1 sans elle). ([], multiplicateur) sans compteur."""
    orbs = data.mystic_orbs
    counts = {s['param']: s['value'] for s in it.get('stats', []) if s['id'] == ORB_COUNT and s['value'] > 0}
    factor = next((s['value'] for s in it.get('stats', []) if s['id'] == ORBS_DOUBLED and s['value'] > 1), 1)
    out = []
    for group in _groups(counts, orbs):
        if len(group) == 1:
            out.append(((group[0],), counts[group[0]]))
            continue
        lock = {(q, p): v for q in group for p, v in orbs[q]['locks'] if p in group}
        if math.prod(counts[p] + 1 for p in group) > MAX_COMBINATIONS:
            out.append((tuple(group), max(counts[p] for p in group)))
            continue
        sols = [a for a in product(*(range(counts[p] + 1) for p in group))
                if all(a[i] + sum(a[j] * lock.get((q, p), 0) for j, q in enumerate(group)) == counts[p]
                       for i, p in enumerate(group))]
        if len(sols) == 1:
            out += [((p,), n) for p, n in zip(group, sols[0]) if n]
        else:   # indiscernables (verrous symétriques) : ensemble, nombre total d'orbes de la plus grande solution
            out.append((tuple(group), max(sum(a) for a in sols) if sols else max(counts[p] for p in group)))
    name = lambda rows: ' / '.join(orb_name(r, data) for r in rows)
    return sorted(out, key=lambda x: (-x[1], name(x[0]))), factor


def orb_lines(it, data):
    """(titre, [(lignes de mysticorbs.bin, texte « 5 × Periapt of Life », [(ligne, début, fin) de chaque nom dans le
    texte]]) de la section « Mystic Orbs » sous l'infobulle, ou None sans orbe ; les positions des noms servent au
    survol (orb_tooltip)."""
    from i18n import tr
    found, factor = applied_orbs(it, data)
    if not found:
        return None
    mult = {1: '', 2: tr('orbs.doubled'), 4: tr('orbs.quadrupled')}.get(factor, tr('orbs.factor', n=factor))
    title = tr('orbs.title') + mult + tr('orbs.total', n=sum(n for _, n in found))
    out = []
    for rows, n in found:
        marker = '\0'
        text = tr('orbs.line', n=n, name=marker)
        start, spans, names = text.index(marker), [], []
        for r in rows:
            name = orb_name(r, data)
            spans.append((r, start, start + len(name)))
            names.append(name)
            start += len(name) + len(' / ')
        out.append((rows, text.replace(marker, ' / '.join(names)), spans))
    return title, out
