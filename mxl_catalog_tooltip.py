"""Infobulle d'une entrée du catalogue (mxl_library.catalog) : unique ou objet de set sans exemplaire rangé,
construite depuis les tables du jeu (plages des affixes appliquées à la base), alignée sur la documentation du jeu.
Sections catalog_* sur un CatalogContext, assemblées comme celles d'un objet (mxl_tooltip.assemble), règles communes
partagées avec l'infobulle d'un objet.
"""
import re
from i18n import tr
import stat_ids as S
from mxl_theme import WHITE, RED, GREEN, BLUE, GOLD
from mxl_rules import table_row, mods_stats, item_type_codes, ethereal_base, higher_stored_is_better
from mxl_stat_text import stat_lines, segments, joined, ColoredText
from mxl_tooltip import (assemble, special_name_lines, base_name_lines, title_lines, required_attr, block_line, sockets_line,
                         stats_level_req, ethereal_line, DMG_BONUS, CLASS_ONLY_KEYS, item_class, BARBARIAN)

ED_LINE_PRIO = 134.5   # place de la ligne « Enhanced Damage » (voir catalog_affixes)


def merge_range_text(lo_text, hi_text):
    """Texte d'une stat à plage, depuis son texte à la moins bonne et à la meilleure valeur (dans cet ordre, décision du
    30/09) : chaque nombre qui diffère devient « (moins bonne to meilleure) » (« +4 to Maximum Damage » /
    « +6 … » -> « +(4 to 6) to Maximum Damage ») ; même signe : gardé devant la parenthèse (« -(4 to 5)% to Enemy
    Lightning Resistance », « -(5 to 1)% Attack Speed ») ; signes différents ou 0 : dans la parenthèse, sans « + »
    (« (-1 to 1)% », « (0 to -5)% to Enemy Fire Resistance »)."""
    if lo_text == hi_text:
        return lo_text
    if isinstance(lo_text, ColoredText) and isinstance(hi_text, ColoredText) and len(lo_text.segs) == len(hi_text.segs):
        # texte à plusieurs couleurs : plage écrite morceau par morceau
        return ColoredText([(c, merge_range_text(a, b)) for (c, a), (_, b) in zip(lo_text.segs, hi_text.segs)])
    number = r'([+-]?\d+(?:\.\d+)?)'
    a, b = re.split(number, lo_text), re.split(number, hi_text)
    if len(a) != len(b) or any(x != y for x, y in zip(a[0::2], b[0::2])):   # textes pas comparables : minimum
        return lo_text

    def span(x, y):
        if x == y:
            return x
        if x[0] in '+-' and y[0] == x[0]:   # même signe, gardé devant la parenthèse (« Requirements -(1 to 20)% »)
            return f'{x[0]}({x[1:]} to {y[1:]})'
        return f"({x.lstrip('+')} to {y.lstrip('+')})"
    return ''.join(span(x, y) for x, y in zip(a, b))


def _span(lo, hi):
    """« 7 » ou « (7 - 8) »."""
    return str(lo) if lo == hi else f'({lo} - {hi})'


def base_auto_mods(code, data):
    """Mods de l'auto-affixe d'un objet de base (groupe d'automagic @0xF8 de la table) pour un unique / objet de set :
    lignes du groupe qui peuvent apparaître sur ce type d'objet (apparition, types autorisés et non exclus) ; plusieurs
    lignes de mêmes mods (paliers) : plages élargies ; sinon la première. ✅ Mega Impact des faux Sacred (Raptor Scythe,
    Bonesplitter) ; rien pour la Crown (documentation du jeu). Paliers de tous niveaux : un exemplaire trouvé a le
    niveau du monstre, souvent plus haut que le niveau minimal de l'unique (✅ documentation : Lionpaw, Item Level 10,
    Movement Speed (10 to 40)%)."""
    g = data.base(code).auto_group
    if not g:
        return []
    # types de l'objet de base et de son second type (✅ documentation : Crystal Sword, auto-affixe du type 272 :
    # « Innate Cold Damage: (49.0% of Dexterity) », « Adds 160-250 Cold Damage »)
    types = data.type_ancestors(data.base(code).type) | data.type_ancestors(data.base(code).type2)
    rows = [a for a in data.affixes['automagic'] if a['group'] == g and a['spawnable'] and a['itypes'] & types
            and not a['etypes'] & types]
    if not rows:
        return []
    shape = lambda a: [(m['prop'], m['param']) for m in a['mods']]
    if all(shape(a) == shape(rows[0]) for a in rows):
        return [(m['prop'], m['param'], min(a['mods'][k]['min'] for a in rows), max(a['mods'][k]['max'] for a in rows))
                for k, m in enumerate(rows[0]['mods'])]
    return [(m['prop'], m['param'], m['min'], m['max']) for m in rows[0]['mods']]


class CatalogContext:
    """Données partagées par les sections de l'infobulle d'une entrée du catalogue (mxl_library.catalog) : entrée,
    ligne de table, objet de base, classe imposée, mods (ceux de la ligne + auto-affixe de la base) et leurs stats au
    minimum (lo) et au maximum (hi) des plages, éthéré, couleur de la qualité. Sans personnage."""

    def __init__(self, entry, data, ethereal=False, char=None):
        self.entry, self.data, self.char = entry, data, char   # char : personnage sélectionné (load_character) ou None
        self.row = table_row(entry['key'], data)
        self.base = data.base(entry['code'])
        self.it = dict(code=entry['code'])   # objet minimal : nom de base, types, classe imposée
        self.cls = item_class(self.it, data)
        self.types = item_type_codes(self.it, data)
        self.col = GOLD if entry['kind'] == 'unique' else GREEN
        mods = [(m['prop'], m['param'], m['min'], m['max']) for m in self.row.get('mods', [])]
        # propriété « ethereal » (✅ Iron Shard, 219), ou version éthérée demandée (exemplaire éthéré pas encore rangé)
        self.ethereal = ethereal or any(data.prop_func[m[0]] == 23 for m in mods)
        mods += base_auto_mods(entry['code'], data)   # auto-affixe de la base (✅ Mega Impact)
        self.mods = mods
        self.lo, self.hi = mods_stats(mods, data, 'min'), mods_stats(mods, data, 'max')
        own = item_class(dict(code=entry['code'], stats=self.lo), data)   # classe imposée par l'objet (stat 463)
        if own is not None:
            self.cls = own

    def total(self, sid):
        """(total au minimum, total au maximum) d'une stat."""
        return tuple(sum(st['value'] for st in stats if st['id'] == sid) for stats in (self.lo, self.hi))

    def base_value(self, v):
        """Dégâts / défense de base : × 1,25 (arrondi inférieur) si éthéré (mxl_rules.ethereal_base ; ✅ Iron Shard
        (297 - 360) to (335 - 390) ; défense : règle retenue, Totem Shield [42-82] -> [52-102])."""
        return ethereal_base(v, self.ethereal)


def catalog_name(ctx):
    """Nom propre puis nom de l'objet de base (avec son tier), à la couleur de la qualité ; ligne du nom de base qui
    répète le nom propre non affichée (title_lines)."""
    return title_lines(special_name_lines(ctx.data.key(ctx.row['name']), ctx.col), base_name_lines(ctx.it, ctx.data, ctx.col))


def catalog_damage(ctx):
    """Dégâts en plages : base × (100 + ED) / 100 + dégâts plats, au minimum et au maximum des plages ; valeurs en bleu
    si l'objet a de l'Enhanced Damage (documentation du jeu)."""
    base, data, out = ctx.base, ctx.data, []
    if not base.damage:
        return out
    ed = ctx.total(S.ENH_DAMAGE_MAX)
    for key, (a, b), fmin, fmax, shown in (
            ('ItemStats1n', base.damage['throw'], S.THROW_MIN_DAMAGE, S.THROW_MAX_DAMAGE, 'thro' in ctx.types),
            # avec un personnage : « One-Hand Damage » d'une arme à deux mains pour un Barbare seulement (comme
            # l'infobulle d'un objet) ; sans personnage : toujours (documentation du jeu)
            ('ItemStats1l', base.damage['one_hand'], S.MIN_DAMAGE, S.MAX_DAMAGE,
             not (ctx.char and base.two_handed and ctx.char['cls'] != BARBARIAN)),
            ('ItemStats1m', base.damage['two_hand'], S.MIN_DAMAGE_2, S.MAX_DAMAGE_2, base.two_handed)):
        if b and shown:
            a, b = ctx.base_value(a), ctx.base_value(b)
            mn = [a * (100 + e) // 100 + f for e, f in zip(ed, ctx.total(fmin))]
            mx = [b * (100 + e) // 100 + f for e, f in zip(ed, ctx.total(fmax))]
            # dégâts fixes (minimum = maximum) : une seule valeur (✅ documentation : Death Touch « One-Hand Damage: 12 »)
            text = str(mn[0]) if len(set(mn + mx)) == 1 else f"{_span(*mn)} to {_span(*mx)}"
            out.append([(WHITE, f"{data.key(key)} "), (BLUE if any(ed) else WHITE, text)])
    return out


def catalog_defense(ctx):
    """Défense (documentation du jeu) : « (a - b) to (c - d) » = défense de base minimale × (100 + ED min à max) / 100
    + défense plate minimale, puis défense de base maximale × (100 + ED min à max) / 100 + défense plate maximale
    (✅ Aidan's Lament, Black Masquerade) ; sans ED : « 968 to 1049 » ; valeurs en bleu si Enhanced Defense."""
    if ctx.base.def_range == (0, 0):
        return []
    ed, flat = ctx.total(S.ENH_DEFENSE), ctx.total(S.DEFENSE)
    at = lambda d, f: [d * (100 + e) // 100 + f for e in ed]
    lo, hi = (ctx.base_value(v) for v in ctx.base.def_range)
    text = _span(*at(lo, flat[0])) if (lo, flat[0]) == (hi, flat[1]) else \
        f"{_span(*at(lo, flat[0]))} to {_span(*at(hi, flat[1]))}"
    # valeurs en bleu si la défense est modifiée : Enhanced Defense ou défense plate (✅ documentation : The Allseeing
    # Eye, « +(31 to 50) Defense » sans ED)
    return [[(WHITE, f"{ctx.data.key('ItemStats1h')} "), (BLUE if any(ed) or any(flat) else WHITE, text)]]


def catalog_block(ctx):
    """Chance de blocage : base + « Base Block Chance » de l'objet (stat 20, plage « a to b », en bleu ; ✅
    documentation : Danmaku 5 %) + bonus de la classe imposée par l'objet, comme en jeu avec un personnage de cette
    classe (✅ documentation : The Sightless Eye, Amazon Only, 1 + 3 = 4 %) ; sans classe imposée : sans ce bonus."""
    if 'shld' not in ctx.types or not ctx.base.block:
        return []
    cls = ctx.char['cls'] if ctx.char else ctx.cls   # avec un personnage : bonus de sa classe (infobulle d'un objet)
    block = ctx.base.block + (ctx.data.block_factor[cls] if cls is not None else 0)
    lo, hi = (block + b for b in ctx.total(S.BASE_BLOCK))
    # plage : « 4 to 5% », sans parenthèses (✅ documentation : Zerae's Vindication)
    return [block_line(ctx.data, lo if lo == hi else f'{lo} to {hi}', any(ctx.total(S.BASE_BLOCK)))]


def catalog_requirements(ctx):
    """Restriction de classe en rouge (documentation du jeu), niveau requis, Force / Dextérité réduites par
    « Requirements -x% » (plage) et si éthéré : exigence annulée (Requirements -100%) absente, réduite en bleu.
    Avec un personnage (char) : chaque exigence en rouge s'il ne la remplit pas même à sa valeur la plus favorable
    (plage : la plus basse), sinon en blanc ; classe en rouge seulement si ce n'est pas la sienne."""
    data, base, char, out = ctx.data, ctx.base, ctx.char, []
    if ctx.cls is not None:
        out.append([(RED if not char or char['cls'] != ctx.cls else WHITE, data.key(CLASS_ONLY_KEYS[ctx.cls]))])
    level_req = max(base.level_req, ctx.row.get('level_req') or 0)
    lo, hi = (stats_level_req(level_req, stats, data) for stats in (ctx.lo, ctx.hi))
    if hi:
        text = f"{data.key('ItemStats1p')} {lo if lo == hi else f'{lo} to {hi}'}"
        out.append([(RED if char and char['level'] < min(lo, hi) else WHITE, text)])
    red = ctx.total(S.REQUIREMENTS)
    for key, req, attr in (('ItemStats1e', base.req_str_dex[0], 'strength'), ('ItemStats1f', base.req_str_dex[1], 'dexterity')):
        values = sorted(max(0, required_attr(req, r, ctx.ethereal)) for r in red)
        if values[1]:
            # plage d'exigence : « 58 to 72 » (✅ documentation, Herr Donner)
            text = str(values[0]) if values[0] == values[1] else f'{values[0]} to {values[1]}'
            if char and char[attr] < values[0]:
                out.append([(RED, f"{data.key(key)} {text}")])
            else:
                out.append([(WHITE, f"{data.key(key)} "), (BLUE if any(red) else WHITE, text)])
    return out


def catalog_item_level(ctx):
    """Niveau de l'objet de la table, uniques et objets de set (✅ documentation, page Sets : 147 sets à 1, 51 de 100 à
    130, tous identiques à la table)."""
    if ctx.row.get('level'):
        return [[(WHITE, tr('tooltip.item_level', n=ctx.row['level']))]]
    return []


def catalog_usage(ctx):
    """Joyau : « Can be Inserted into Socketed Items » (comme l'infobulle d'un objet, ✅ documentation : Heavenstone)."""
    return [[(WHITE, ctx.data.key('ExInsertSocketsX'))]] if 'jewl' in ctx.types else []


def catalog_weapon(ctx):
    """Bonus de dégâts par point d'attribut : sans personnage « (0.16 per Strength)% » ; avec un personnage, sa valeur
    (bonus × attribut / 100, comme l'infobulle d'un objet)."""
    char = ctx.char
    return [[(WHITE, f"{ctx.data.key(key)} {ctx.base.dmg_bonus[k] * char[attr] // 100}%" if char
              else f"{ctx.data.key(key)} {tr(per, v=f'{ctx.base.dmg_bonus[k] / 100:g}')}")]
            for key, k, attr, per in DMG_BONUS if ctx.base.dmg_bonus[k]]


def catalog_ethereal(ctx):
    """Objet éthéré : ligne « Ethereal » (ethereal_line, comme l'infobulle d'un objet)."""
    return [ethereal_line(ctx.data)] if ctx.ethereal else []


def catalog_affixes(ctx):
    """Affixes de l'entrée (mods de sa ligne de table et auto-affixe de sa base), avec leurs plages (mods_lines)."""
    return [segments(c, t) for c, t in mods_lines(ctx.mods, ctx.data, bool(ctx.base.two_handed), ctx.char)]


def mods_lines(mods, data, two_handed=False, char=None):
    """Lignes (couleur, texte) de mods de table (propriété, param, min, max) avec leurs plages « +(4 to 6) to Maximum
    Damage » : texte du jeu au minimum et au maximum, nombres différents fusionnés (merge_range_text), dans l'ordre du
    jeu ; Enhanced Damage en une ligne à sa place. Affixes d'une entrée du catalogue, bonus d'un set (set_bonus_lines).
    char : personnage sélectionné (stats par niveau à son niveau, dégâts innés selon ses attributs) ou None."""
    lo, hi = mods_stats(mods, data, 'min'), mods_stats(mods, data, 'max')
    for k, (a, b) in enumerate(zip(lo, hi)):   # réanimation sur une plage de monstres (param) : « Random Monster » ;
        # param négatif distinct : chaque affixe tire son monstre, pas de fusion (✅ Leoric's Legion : 3 fois « 1% »)
        if data.isc[a['id']]['func'] == 23 and a['param'] != b['param']:
            a['param'] = b['param'] = -1 - k
    # valeur nulle au minimum et au maximum (affixe réduit à 0 à ce tier) : ligne absente (✅ documentation : Vilehand
    # tier 1, « +0 to All Skills » absent) ; les stats de pur texte (sans nombre) restent
    text_only = lambda c: c['func'] in (0, 31, 34, 36) or (c['func'] == 3 and c['val'] == 0)
    zero = {k for k, (a, b) in enumerate(zip(lo, hi))
            if a['value'] == 0 and b['value'] == 0 and not text_only(data.isc[a['id']])}
    lo = [x for k, x in enumerate(lo) if k not in zero]
    hi = [x for k, x in enumerate(hi) if k not in zero]
    rest = lambda stats: [st for st in stats if st['id'] not in (S.ENH_DAMAGE_MAX, S.ENH_DAMAGE_MIN)]
    two = two_handed
    # stats tirées sur une plage et regroupables seulement avec des stats d'autres propriétés (tirages séparés : pas de
    # ligne groupée, ✅ Catechumen) ; une propriété qui donne tout le groupe (« all-stats », « res-all ») tire une seule
    # valeur pour toutes : ligne groupée gardée (✅ documentation : Lionpaw « +(7 to 10) to all Attributes »)
    mod_stats = [{x for x in data.props[m[0]] if x >= 0} for m in mods]

    def own_group(sid):
        grp = set(data.stat_group[sid])
        return any(grp <= st for st in mod_stats)
    ranged = {a['id'] for a, b in zip(lo, hi) if a['value'] != b['value'] and not own_group(a['id'])}
    # textes à la moins bonne et à la meilleure valeur de chaque stat (higher_stored_is_better : Requirements, Mana
    # Cost… meilleurs au minimum enregistré), pour écrire chaque plage dans ce sens
    better = [higher_stored_is_better(a['id'], data) for a in lo]
    worst = [a if up else b for a, b, up in zip(lo, hi, better)]
    best = [b if up else a for a, b, up in zip(lo, hi, better)]
    lo_lines = stat_lines(rest(worst), data, char, prio=True, two_handed=two, per_level_rate=True, ranged=ranged)
    hi_lines = stat_lines(rest(best), data, char, prio=True, two_handed=two, per_level_rate=True, ranged=ranged)
    if len(lo_lines) != len(hi_lines):   # regroupements différents au minimum et au maximum : valeurs minimales
        hi_lines = lo_lines
    # suite de la ligne (dégâts innés : « (54.0% of Dexterity) ») ; couleurs d'un texte à plusieurs couleurs gardées
    affixes = [(pr, c, merge_range_text(joined(c, t_lo, in_lo), joined(c, t_hi, in_hi)))
               for (pr, c, t_lo, in_lo, _), (_, _, t_hi, in_hi, _) in zip(lo_lines, hi_lines)]
    ed = tuple(sum(st['value'] for st in stats if st['id'] == S.ENH_DAMAGE_MAX) for stats in (lo, hi))
    if any(ed):   # dégâts améliorés (stats 17 / 18) : une ligne « +(41 to 60)% Enhanced Damage » (en jeu : dans la ligne
        # des dégâts). Place de la documentation, pas celle des stats 17 / 18 (179-180) : après la pénétration foudre
        # (135) et avant la pénétration froid (133) et les dégâts de sorts froid (134) (✅ Saber of the Stormsail,
        # Kraken's Cutlass, Sherazade, Blacktongue ; Jared's Fragmentor, Iron Shard, Reaper's Hand)
        affixes.append((ED_LINE_PRIO, BLUE,
                        merge_range_text(tr('edit.enhanced_damage', v=ed[0]), tr('edit.enhanced_damage', v=ed[1]))))
    return [(c, t) for _, c, t in sorted(affixes, key=lambda a: -a[0])]


def set_bonus_lines(set_id, data, char=None):
    """Bonus d'un set (sets.bin) comme la documentation du jeu : [(titre, [(couleur, texte)])], un titre par nombre de
    pièces portées (« Set Bonus with 2 or more set items: ») puis celui du set complet ; lignes en vert (couleur des
    objets de set ; textes du jeu à leur couleur), plages « (a to b) » comme les affixes (mods_lines). char :
    personnage sélectionné (stats par niveau à son niveau…) ou None."""
    s = data.sets[set_id] if 0 <= set_id < len(data.sets) else None
    if not s:
        return []
    groups = [(tr('set.bonus_partial', n=n), mods) for n, mods in sorted(s['partial'].items())]
    groups.append((tr('set.bonus_full'), s['full']))
    # couleur des stats ordinaires (bleu des affixes) -> vert ; textes du jeu : leur propre couleur (✅ documentation :
    # Creed « 1 Extra Target to Storm Crows » orange, Trophy Hunter « (Based on Trophies) » blanc)
    return [(title, [(GREEN if c == BLUE else c, t)
                     for c, t in mods_lines([(m['prop'], m['param'], m['min'], m['max']) for m in mods], data,
                                            char=char)])
            for title, mods in groups if mods]


def set_name(set_id, data):
    """(nom du set, sous-titre ou '') : « Pantheon », « (Amazon Bow Set) » (texte du jeu sur deux lignes, de bas en
    haut)."""
    parts = [p for p in data.sets[set_id]['name'].split('\n') if p.strip()] if 0 <= set_id < len(data.sets) else []
    return (parts[-1], parts[0] if len(parts) > 1 else '') if parts else (f'#{set_id}', '')


def catalog_sockets(ctx):
    """Unique ou objet de set (tous « Sacred ») : toujours le maximum de sockets de sa base (documentation du jeu)."""
    return [sockets_line(ctx.data, ctx.base.max_sockets)] if ctx.base.max_sockets else []


# sections de l'infobulle d'une entrée du catalogue, dans l'ordre de la documentation du jeu
CATALOG_SECTIONS = (catalog_name, catalog_damage, catalog_defense, catalog_block, catalog_requirements,
                    catalog_item_level, catalog_usage, catalog_weapon, catalog_ethereal, catalog_affixes, catalog_sockets)


def catalog_tooltip(entry, data, ethereal=False, char=None):
    """Infobulle d'une entrée du catalogue (unique ou objet de set sans exemplaire rangé) construite depuis les tables
    du jeu : sections CATALOG_SECTIONS, règles communes avec l'infobulle d'un objet (special_name_lines,
    base_name_lines, required_attr, block_line, DMG_BONUS, sockets_line). ethereal : version éthérée de l'entrée.
    char : personnage sélectionné (exigences en rouge, stats par niveau, bonus de dégâts, blocage de sa classe) ou
    None (comme la documentation du jeu)."""
    return assemble(CatalogContext(entry, data, ethereal, char), CATALOG_SECTIONS)
