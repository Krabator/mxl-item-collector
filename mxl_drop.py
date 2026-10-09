"""Où un objet peut tomber d'un monstre, affiché sous l'infobulle (coffre et écran Library) : plage de niveaux de zone
(« Drops from area level 10 to 50 », « 77+ »), sources spéciales, ou rien ; pour un unique sacré dont la base porte
plusieurs uniques (sacrés, bijoux, joyaux, reliques, charmes…), sa part parmi eux par tranche de niveau.

Chemin réel de la chute, d'après les classes de trésor du jeu (mxl_data.Data.treasure_classes) : les monstres
ordinaires et élites tirent dans « Normal » et « Elite », qui montent de palier avec le niveau du monstre comme le fait
D2Common (ordinal 10634 : on avance tant que la classe suivante a le même groupe et un niveau ≤ au niveau du monstre).
Pour chaque niveau de 1 au plus haut niveau de zone, on relève ce qui est atteignable : groupes de bases (weapN, armoN :
bases de niveau N-2 à N, fabriqués par le jeu) et codes d'objets cités directement (bijoux, joyaux, reliques…).
Niveau de l'objet = niveau du monstre (Nightmare / Hell : celui de la zone ; Normal : celui du monstre, que l'on
assimile à la zone, choix du 07/10). Un unique / objet de set doit avoir un niveau ≤ ; sacrés : Hell
seulement (wiki officiel « Difficulty Levels »). Choix de l'unique sur une base : uniques de niveau ≤ au niveau de
l'objet, tirés au prorata de leur rareté (Diablo II).
Non traité : niveau des affixes des objets magiques et rares (pas d'information pour eux), boss, coffres et zones
spéciales (au-delà de « Only from special monsters or areas »).
"""
import math
from collections import namedtuple
from i18n import tr
from mxl_rules import unique_row, set_row, table_row

PLAIN = ('low', 'normal', 'superior')   # qualités sans niveau propre : celui de l'objet de base seul
HEADS = ('Normal', 'Elite')             # classes de trésor des monstres ordinaires et élites (montée de palier)
# « World Drops » : classes presque entièrement faites de « rien » (ex. relique : 1 tirage sur 6 000) ; un objet atteint
# seulement par elles est signalé « (world drop, extremely rare) » (07/10, observation en jeu)
WORLD_DROPS = ('World Drops', 'World Drops (H)')

# status : 'range' (niveaux lo à hi, hi None = jusqu'au plus haut niveau de zone), 'special' (pas des monstres ordinaires,
# mais cité par une autre classe : boss, coffres, zones spéciales), 'never' (cité par aucune classe de trésor)
# world : atteint seulement par WORLD_DROPS (monstres ordinaires et élites)
Drop = namedtuple('Drop', 'status lo hi hell world', defaults=(False,))


def sacred(code, data):
    """Vrai pour un objet de base sacré (« (Sacred) » en fin de nom)."""
    return data.base(code).name.endswith('(Sacred)')


def _upgrade(tcs, k, mlvl):
    """Classe atteinte depuis k pour un monstre de niveau mlvl (montée de palier de D2Common)."""
    while k + 1 < len(tcs) and tcs[k]['group'] and tcs[k + 1]['group'] == tcs[k]['group'] and tcs[k + 1]['level'] <= mlvl:
        k += 1
    return k


def _leaves(tcs, index, k, seen, skip=()):
    """Groupes de bases et codes d'objets atteignables depuis la classe k (poids > 0), sans descendre dans les classes
    nommées dans skip."""
    if k in seen:
        return set()
    seen.add(k)
    out = set()
    for it, p in tcs[k]['items']:
        if p > 0 and it not in skip:
            out |= _leaves(tcs, index, index[it], seen, skip) if it in index else {it.strip()}
    return out


def reach(data):
    """({élément: (premier niveau, dernier niveau)} atteignable par les monstres ordinaires et élites, éléments cités
    par une classe quelconque, plus haut niveau de zone, éléments atteints seulement par WORLD_DROPS), calculé une fois
    par jeu de tables."""
    cached = getattr(data, '_drop_reach', None)
    if cached:
        return cached
    tcs = data.treasure_classes
    index = {t['name']: k for k, t in enumerate(tcs)}
    top = max(max(v) for v in data.areas.values())
    levels, direct = {}, set()
    for head in HEADS:
        if head not in index:
            continue
        for mlvl in range(1, top + 1):
            k = _upgrade(tcs, index[head], mlvl)
            for leaf in _leaves(tcs, index, k, set()):
                lo, hi = levels.get(leaf, (mlvl, mlvl))
                levels[leaf] = (min(lo, mlvl), max(hi, mlvl))
            direct |= _leaves(tcs, index, k, set(), WORLD_DROPS)
    cited = {it.strip() for t in tcs for it, p in t['items'] if p > 0}
    data._drop_reach = levels, cited, top, set(levels) - direct
    return data._drop_reach


def drop_key(code, data):
    """Ce que les classes de trésor citent pour cet objet : groupe de bases (arme / armure : weapN / armoN, N = niveau de
    base arrondi au multiple de 3 supérieur) ou code d'objet."""
    b = data.base(code)
    if b.kind in ('weapons', 'armor'):
        return ('weap' if b.kind == 'weapons' else 'armo') + str(3 * math.ceil(max(b.qlvl, 1) / 3))
    return code.strip()


def drop_range(code, row_level, data, hell_only=False):
    """Drop d'un objet de base code et d'un niveau d'unique / de set row_level (0 sans) ; hell_only : au moins le plus
    petit niveau de zone de Hell."""
    levels, cited, top, world = reach(data)
    key = drop_key(code, data)
    if key not in levels:
        return Drop('special' if key in cited else 'never', None, None, hell_only)
    first, last = levels[key]
    lo = max(first, row_level or 0, data.base(code).qlvl)
    if hell_only:
        lo = max(lo, min(h for _, _, h in data.areas.values() if h))
    if lo > last:   # unique de niveau trop haut pour les monstres qui tirent cette base
        return Drop('special' if key in cited else 'never', None, None, hell_only)
    return Drop('range', lo, None if last >= top else last, hell_only, key in world)


def item_drop_level(it, data):
    """Drop d'un objet, ou None : objet magique, rare, artisanal, runeword (niveau des affixes non traité), unique qui ne
    tombe pas (rareté 0), objet sans arme ni armure de base (qualités simples)."""
    q = it.get('quality')
    if q in ('unique', 'set'):
        row = unique_row(it, data) if q == 'unique' else set_row(it, data)
        if row is None or (q == 'unique' and row.get('rarity', 1) == 0) or it.get('runeword'):
            return None
        return drop_range(it['code'], row.get('level'), data, sacred(it['code'], data))
    if q in PLAIN and not it.get('runeword') and data.base(it['code']).kind in ('weapons', 'armor'):
        return drop_range(it['code'], 0, data)
    return None


def entry_drop_level(entry, data):
    """Drop d'une entrée du catalogue, ou None si elle ne tombe pas."""
    if not entry['droppable']:
        return None
    return drop_range(entry['code'], table_row(entry['key'], data).get('level'), data, sacred(entry['code'], data))


def drop_text(drop):
    """Ligne sous l'infobulle : « Drops from area level 10 to 50 », « … 77+ », « (world drop, extremely rare) » pour un
    objet des seules « World Drops », « (Hell only) » pour un unique / set sacré, « Only from special monsters or areas », « Does not drop from monsters » ; '' sans information (None)."""
    if drop is None:
        return ''
    if drop.status != 'range':
        return tr('drop.special' if drop.status == 'special' else 'drop.never')
    text = tr('drop.area_to', lo=drop.lo, hi=drop.hi) if drop.hi else tr('drop.area_from', lo=drop.lo)
    return text + (tr('drop.world') if drop.world else '') + (tr('drop.hell_only') if drop.hell else '')


MAX_SHARE_PARTS = 4   # tranches affichées au plus ; au-delà : les 3 premières, « … », la dernière


def unique_shares(row_index, data, drop):
    """Part d'un unique parmi les uniques de sa base qui tombent (rareté > 0), par tranche de niveau : (tranches
    [(début, fin ou None, part en %)], niveau de zone ?). À partir de son niveau minimum de chute (drop.lo) ; objet des
    seules sources spéciales : à partir de son propre niveau, en niveau d'objet (pas de plage de zone connue). ([],
    True) s'il est seul sur sa base ou ne tombe jamais. Toutes les bases partagées : sacrées, bijoux, joyaux, reliques,
    charmes… (choix du 07/10)."""
    me = data.uniques[row_index]
    if drop is None or drop.status == 'never':
        return [], True
    rivals = [(u.get('level') or 0, u.get('rarity', 0)) for u in data.uniques
              if u.get('code') == me['code'] and u.get('rarity', 0) > 0]
    if len(rivals) < 2:
        return [], True
    area = drop.status == 'range'
    lo, hi = (drop.lo, drop.hi) if area else (me.get('level') or 0, None)
    top = hi or reach(data)[2]
    cuts = sorted({lvl for lvl, _ in rivals if lo < lvl <= top} | {lo})
    out = []
    for k, start in enumerate(cuts):
        end = cuts[k + 1] - 1 if k + 1 < len(cuts) else hi
        total = sum(r for lvl, r in rivals if lvl <= start)
        out.append((start, end, 100 * me['rarity'] / total))
    return out, area


def _pct(p):
    """Pourcentage : une décimale (« 83.6% », « 100% » sans « .0 »), deux sous 0,1 % (« 0.05% »)."""
    s = f'{p:.1f}' if p >= 0.1 else f'{p:.2f}'
    return (s[:-2] if s.endswith('.0') else s) + '%'


def merged_shares(shares):
    """Tranches voisines au même pourcentage affiché fusionnées (« 2.8% (105-109) · 2.8% (110-119) » -> « 2.8%
    (105-119) », choix du 07/10) : [(début, fin ou None, texte du pourcentage)]."""
    out = []
    for start, end, p in shares:
        text = _pct(p)
        if out and out[-1][2] == text:
            out[-1] = (out[-1][0], end, text)
        else:
            out.append((start, end, text))
    return out


def share_text(shares, area=True):
    """« Share among uniques of this base: 0.3% (area level 130+) » ; plusieurs tranches : « 100% (105-119) ·
    83.6% (120-129) · 83.3% (130+) », tranches au même pourcentage affiché fusionnées, puis au plus MAX_SHARE_PARTS
    (sinon les 3 premières, « … », la dernière) ; sources spéciales : niveau d'objet (« item level »). '' sans
    tranche."""
    parts = merged_shares(shares)
    if not parts:
        return ''
    span = lambda s, e: f'{s}+' if e is None else f'{s}-{e}'
    word = tr('drop.area_word' if area else 'drop.item_word')
    if len(parts) == 1:
        s, e, p = parts[0]
        return tr('drop.share', parts=f'{p} ({word} {span(s, e)})')
    if len(parts) > MAX_SHARE_PARTS:
        parts = parts[:MAX_SHARE_PARTS - 1] + [None] + parts[-1:]
    text = ' · '.join('…' if x is None else f'{x[2]} ({span(x[0], x[1])})' for x in parts)
    return tr('drop.share', parts=text) if area else tr('drop.share_item', parts=text)


def item_drop_lines(it, data):
    """Lignes sous l'infobulle d'un objet : chute, puis part parmi les uniques de sa base (unique sur une base
    partagée)."""
    drop = item_drop_level(it, data)
    lines = [drop_text(drop)]
    if unique_row(it, data) is not None:
        lines.append(share_text(*unique_shares(it['set_unique_id'], data, drop)))
    return [x for x in lines if x]


def entry_drop_lines(entry, data):
    """Lignes sous l'infobulle d'une entrée du catalogue (comme item_drop_lines)."""
    drop = entry_drop_level(entry, data)
    lines = [drop_text(drop)]
    if entry['kind'] == 'unique':
        lines.append(share_text(*unique_shares(entry['row'], data, drop)))
    return [x for x in lines if x]
