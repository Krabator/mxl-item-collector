"""Description des objets comme l'infobulle du jeu (Median XL 2.14.5) : infobulle d'un objet (sections section_*),
règles communes avec l'infobulle du catalogue (mxl_catalog_tooltip), exigences. Texte des stats : mxl_stat_text.

Une infobulle = liste de lignes ; une ligne = liste de segments (code couleur, texte).
Codes couleur = ceux du jeu (ÿc + caractère), nommés dans mxl_theme : WHITE '0', RED '1', GREEN '2', BLUE '3',
GOLD '4', GREY '5', BRIGHT_GOLD '8', YELLOW '9', PURPLE ';' ; les codes lus dans les textes du jeu restent tels quels.
Voir docs/ihm.md pour les règles vérifiées.
"""
from i18n import tr
import stat_ids as S
from mxl_data import strip_colors
from mxl_theme import WHITE, RED, GREEN, BLUE, GOLD, GREY, BRIGHT_GOLD, YELLOW, PURPLE
from mxl_rules import (CLASS_ONLY_KEYS, affix_sources, affix, mods_stats, CLASSES, GEM_GROUPS, is_rune, item_type_codes, special_name,
                        unique_row, set_row, ethereal_base, base_defense_range)
from mxl_stat_text import socket_contents, stat_ranges, range_segs, stat_lines, segments

BARBARIAN = CLASSES.index('Barbarian')   # seule classe qui manie les épées à deux mains à une main


# ---------------------------------------------------------------- infobulle d'un objet

NAME_COLOR = {'low': GREY, 'normal': WHITE, 'superior': WHITE, 'magic': BLUE, 'set': GREEN,
              'rare': YELLOW, 'unique': GOLD, 'crafted': BRIGHT_GOLD, 'honorific': GREEN}   # honorifique : vert en jeu
# classe d'arme : table de D2Sigma.dll @0x101857F8 (type d'objet, chaîne), testée dans cet ordre, parents compris
WEAPON_CLASS = [(26, 4085), (28, 4078), (30, 4079), (32, 4080), (38, 4081), (44, 4082), (33, 4083), (27, 4084),
                (34, 4086), (35, 4087), (67, 21258), (88, 21258), (68, 4085), (25, 4085), (57, 4077), (166, 4086),
                (167, 4086), (257, 4079), (258, 4084), (259, 4085), (198, 11237), (199, 11237), (245, 4079), (279, 4085)]


# ---- texte de vitesse d'attaque : reconstitué depuis D2Sigma.dll (fonction 0x1007CE60) et D2Common (ordinal 10592)
# v = (images × 256) / ((100 + stat 93 de l'objet − WSM) × vitesse d'animation / 100), divisions entières,
# animation = classe du personnage + mode A1 + catégorie de l'arme (animdata.d2). ✅ 6 armes sur 6.
# Catégorie : 1 si v < 10, 5 si v >= 28, sinon SPEED_TABLE[v - 10][colonne] ; texte = clé tbl 4088 + catégorie.
CLASS_TOKENS = ['AM', 'SO', 'NE', 'PA', 'BA', 'DR', 'AS']
SPEED_COLUMNS = [(0, 2), (1, 4), (1, 4), (0, 3), (0, 3), (1, 4), (0, 3)]   # par classe : (arme, arc / arbalète)
SPEED_TABLE = [(1, 1, 1, 1, 1), (1, 1, 1, 1, 1), (1, 1, 1, 1, 1), (1, 1, 2, 1, 1), (2, 1, 2, 2, 1),   # v = 10 à 14
               (2, 1, 2, 2, 2), (2, 2, 3, 2, 2), (3, 2, 3, 3, 2), (3, 2, 3, 3, 3), (3, 2, 4, 3, 3),   # v = 15 à 19
               (4, 3, 4, 4, 3), (4, 3, 4, 4, 4), (4, 3, 5, 4, 4), (5, 4, 5, 5, 4), (5, 4, 5, 5, 5),   # v = 20 à 24
               (5, 4, 5, 5, 5), (5, 5, 5, 5, 5), (5, 5, 5, 5, 5)]                                     # v = 25 à 27
SPEED_KEYS = ['WeaponAttackFastest', 'WeaponAttackVeryFast', 'WeaponAttackFast', 'WeaponAttackNormal',
              'WeaponAttackSlow', 'WeaponAttackVerySlow', 'WeaponAttackSlowest']


def attack_speed_text(it, data, char, ias):
    """« Very Fast Attack Speed »… pour ce personnage, ou None (personnage ou animation inconnus)."""
    if not char or char['cls'] >= len(CLASS_TOKENS):
        return None
    frames, speed = data.anim.get(f"{CLASS_TOKENS[char['cls']]}A1{data.base(it['code']).wclass.upper()}", (0, 0))
    div = (100 + ias - data.base(it['code']).wsm) * speed // 100
    if not frames or div <= 0:
        return None
    v = frames * 256 // div
    col = SPEED_COLUMNS[char['cls']][1 if item_type_codes(it, data) & {'bow', 'xbow'} else 0]
    cat = 1 if v < 10 else 5 if v >= 28 else SPEED_TABLE[v - 10][col]
    return data.key(SPEED_KEYS[cat])


def name_lines(it, data):
    """Lignes du nom (codes couleur ÿc du texte brut) dans l'ordre d'affichage : le jeu affiche les textes
    sur plusieurs lignes de bas en haut (✅ « Arcane Shards (2) » / « Cube Reagent »). [(code couleur ou None, texte)]"""
    raw = data.base(it['code']).name_raw or it['name']
    out = []
    for part in reversed(raw.split('\n')):
        code = part[2] if part.startswith('ÿc') and len(part) > 2 else None
        out.append((code, strip_colors(part)))
    return out


def name_color(it, data):
    if 'runeword' in it:
        return GOLD
    code = name_lines(it, data)[0][0]   # couleur imposée par le nom lui-même (gemmes ÿc;, Arcane Shards ÿc8…)
    if code and code != WHITE:
        return code
    if is_rune(it, data):
        return PURPLE
    q = it.get('quality')
    if q in (None, 'normal', 'superior') and (it.get('ethereal') or it.get('has_sockets')):
        return GREY   # objet éthéré / à sockets sans qualité : gris
    return NAME_COLOR.get(q, WHITE)


CLASS_STAT = 463   # Median XL : classe imposée par l'objet lui-même, valeur = classe + 1 (✅ Azgar's Crystal 6 = Druide)


def item_class(it, data):
    """Classe de personnage imposée : stat CLASS_STAT de l'objet (uniques de Median XL, ✅ documentation : Azgar's
    Crystal « (Druid Only) », Shadowfang « (Necromancer Only) »), sinon type d'objet (itemtypes.bin u8 @0x21), ou None."""
    own = next((s['value'] for s in it.get('stats', []) if s['id'] == CLASS_STAT), 0)
    if 0 < own <= len(CLASSES):
        return own - 1
    for t in data.type_ancestors(data.base(it['code']).type):
        c = data.itype_class[t]
        if c < len(CLASSES):
            return c
    return None


def required_level(it, data):
    """Niveau requis = max(niveau de base, niveau requis de chaque affixe, de l'unique). ✅ vérifié sur 26 objets."""
    lv = [data.base(it['code']).level_req]
    u = unique_row(it, data) or set_row(it, data)
    if u:
        lv.append(u['level_req'])
    for kind, sid in affix_sources(it):
        a = affix(data, kind, sid)
        if a:
            lv.append(a['level_req'])
    lv += [required_level(sub, data) for sub in it.get('socketed', [])]   # runes / joyaux sertis (✅ Shark : Eld = 8)
    return stats_level_req(max(lv), it.get('stats', []), data)


def stats_level_req(level, stats, data):
    """Niveau requis level ajusté par les stats de l'objet : + « Required Level » (stat 92, ✅ documentation : Suicide
    Note 100 + 10), puis au moins le niveau requis de chaque compétence donnée par « +x to <compétence> » (stats 97 /
    107, ✅ documentation : Grim Fang, Holy Fire niveau 20) ; pas les chances de lancer ni les charges. Règle retrouvée
    sur 1331 des 1332 infobulles des pages Tiered et Sacred Uniques de la documentation."""
    level += sum(s['value'] for s in stats if s['id'] == S.LEVEL_REQ)
    return max([level] + [data.skill_req.get(s.get('param'), 0) for s in stats
                          if s['id'] in (S.SINGLE_SKILL, S.SINGLE_SKILL_2)])


# ---------------------------------------------------------------- règles communes aux deux infobulles
# (objet : sections section_* ; entrée du catalogue : sections catalog_*)

ETHEREAL_REQ = 10   # objet éthéré : exigences de Force et de Dextérité réduites de 10
# bonus de dégâts par point d'attribut, dans l'ordre du jeu : Dextérité puis Force (clé du texte, indice dans
# ItemBase.dmg_bonus, attribut du personnage, texte « (x per <attribut>)% » du catalogue)
DMG_BONUS = (('charmontohit2X', 1, 'dexterity', 'tooltip.per_dexterity'),
             ('charmontohit1X', 0, 'strength', 'tooltip.per_strength'))


def special_name_lines(text, col):
    """Nom propre (texte du jeu, une ou plusieurs lignes) : lignes affichées de bas en haut comme le jeu
    (✅ « Arcane Shards (2) » / « Cube Reagent », « (Druid Challenge Item) » / « Caoi Dulra Fruit »)."""
    return [[(col, strip_colors(part))] for part in reversed(text.split('\n'))]


def base_name_lines(it, data, col, prefix=''):
    """Nom de l'objet de base (avec son tier, « Claymore (2) ») : 1re ligne à la couleur de la qualité précédée de
    prefix (Superior, basse qualité), lignes suivantes à leur propre couleur."""
    return [[(col if k == 0 else (code or WHITE), (prefix if k == 0 else '') + part)]
            for k, (code, part) in enumerate(name_lines(it, data))]


def title_lines(name, base):
    """Titre de l'infobulle : lignes du nom propre, puis celles du nom de base sauf celles qui répètent une ligne du
    nom (« Bone Chimes » / « Bone Chimes », reliques, charmes, objets de quête, Item Design : une seule fois)."""
    text = lambda line: ''.join(t for _, t in line).strip().lower()
    seen = {text(line) for line in name}
    return name + [line for line in base if text(line) not in seen]


def required_attr(req, reduction, ethereal):
    """Exigence de Force / Dextérité réduite par « Requirements -x% » (stat 91) et de ETHEREAL_REQ si éthéré."""
    return req * (100 + reduction) // 100 - (ETHEREAL_REQ if ethereal else 0)


def block_line(data, block, modified=False):
    """« Chance to Block: x% » ; valeur en bleu si l'objet la modifie (« Base Block Chance », ✅ documentation : Danmaku).
    block : nombre ou texte (plage du catalogue)."""
    if not modified:
        return [(WHITE, f"{data.key('ItemStats1r')}{block}%")]
    return [(WHITE, data.key('ItemStats1r')), (BLUE, f'{block}%')]


def sockets_line(data, n):
    """« Socketed (n) », en bleu."""
    return [(BLUE, f"{data.key('Socketable')} ({n})")]


def assemble(ctx, sections):
    """Infobulle : lignes des sections, dans l'ordre (contexte partagé par les sections)."""
    lines = []
    for section in sections:
        lines += section(ctx)
    return lines


def all_stats(it, data):
    """Stats affichées : objet + runeword + objets sertis (gemmes / runes selon le type de l'objet)."""
    stats = list(it.get('stats', [])) + list(it.get('stats_runeword', []))
    for _, _, sub_stats in socket_contents(it, data):
        stats += sub_stats
    return stats


class TooltipContext:
    """Données partagées par les sections de l'infobulle d'un objet : objet, tables, personnage (char : couleurs
    rouges des exigences, bonus Force / Dextérité, dégâts innés ; None sinon), stats affichées (objet + runeword +
    objets sertis), leurs totaux par stat (ids) et leurs plages par source (ranges). shown : stats déjà affichées par
    une section (pourcentage de dégâts ou de défense), pas répétées dans la liste des stats.
    Une infobulle construite autrement (ex. entrée du catalogue) peut fournir son propre contexte aux mêmes sections."""

    def __init__(self, it, data, char=None):
        self.it, self.data, self.char = it, data, char
        self.stats = all_stats(it, data)
        self.ranges = stat_ranges(it, data)
        self.ids = {}
        for st in self.stats:
            self.ids[st['id']] = self.ids.get(st['id'], 0) + st['value']
        self.types = item_type_codes(it, data)
        self.shown = set()

    def base(self):
        return self.data.base(self.it['code'])

    def pct_ranges(self, sid):
        """Plages d'un pourcentage de dégâts / de défense : ventilation par source sur la ligne du dessous."""
        return range_segs([sid], self.ranges, self.data, self.char, pct=True, below=True)


def section_name(ctx):
    """Nom : nom propre (rare, unique, runeword), lignes du nom de base (préfixe Superior / basse qualité), runes du
    runeword."""
    it, data, out = ctx.it, ctx.data, []
    col = name_color(it, data)
    special = special_name(it, data)
    if special:
        out += special_name_lines(special, col)
    name = list(out)   # lignes du nom propre : une ligne du nom de base qui les répète n'est pas affichée (title_lines)
    prefix = ''
    if 'runeword' in it:
        pass   # runeword : nom de base seul, en gris (✅ Shark)
    elif it.get('quality') == 'superior':
        prefix = data.key('Hiquality') + ' '
    elif it.get('quality') == 'low' and it.get('subquality', 99) < len(data.low_quality):
        prefix = data.key(data.low_quality[it['subquality']]) + ' '   # ✅ Low Quality, Discarded
    if 'runeword' in it:   # runeword : toutes les lignes du nom de base en gris
        out += [[(GREY, part)] for _, part in name_lines(it, data)]
    else:
        out = title_lines(name, base_name_lines(it, data, col, prefix))
    if 'runeword' in it:
        # « Eld Rune » -> Eld ; Enchanted Rune : dernière ligne du nom (« Ol Rune »)
        runes = ''.join(name_lines(s, data)[0][1].split()[0] for s in it.get('socketed', []) if is_rune(s, data))
        if runes:
            out.append([(GOLD, runes)])
    return out


def section_damage(ctx):
    """Dégâts de l'arme, dans l'ordre du jeu (lancer, une main, deux mains ; ✅ Javelin), chacun sur 3 lignes : dégâts
    de base de la table (ajout de l'éditeur, pas de variance), dégâts du jeu = base × (100 + ED) / 100 + dégâts plats
    avec l'ED entre parenthèses (✅ Shark 7 to 14 (+85%)), ventilation de l'ED (une seule fois)."""
    data, ids, out = ctx.data, ctx.ids, []
    base = ctx.base()
    bd = base.damage
    if not bd:
        return out
    ed = ids.get(S.ENH_DAMAGE_MAX, 0)
    for key, (a, b), fmin, fmax, kind in (('ItemStats1n', bd['throw'], S.THROW_MIN_DAMAGE, S.THROW_MAX_DAMAGE, 'throw'),
                                          ('ItemStats1l', bd['one_hand'], S.MIN_DAMAGE, S.MAX_DAMAGE, 'one_hand'),
                                          ('ItemStats1m', bd['two_hand'], S.MIN_DAMAGE_2, S.MAX_DAMAGE_2, 'two_hand')):
        # ✅ Throwing Axe : 2 mains 1-1 non affiché (pas à deux mains) ; Hexblade : lancer 1-1 non affiché (pas « thro ») ;
        # arme à deux mains avec dégâts à une main (épées) : « One-Hand Damage » pour un Barbare seulement
        # (✅ Jared's Fragmentor, Claymore, personnage Nécromancien : ligne absente)
        if not b or (key == 'ItemStats1m' and not base.two_handed) or (key == 'ItemStats1n' and 'thro' not in ctx.types) \
                or (key == 'ItemStats1l' and base.two_handed and not (ctx.char and ctx.char['cls'] == BARBARIAN)):
            continue
        a, b = (ethereal_base(v, ctx.it.get('ethereal')) for v in (a, b))   # éthéré : dégâts de base × 1,25
        lo, hi = a * (100 + ed) // 100 + ids.get(fmin, 0), b * (100 + ed) // 100 + ids.get(fmax, 0)
        segs, below = [(WHITE, f"{data.key(key)} {lo} to {hi}")], []
        if ed and ids.get(S.ENH_DAMAGE_MIN) == ed:
            inline, below = ctx.pct_ranges(S.ENH_DAMAGE_MAX)
            segs += [(WHITE, ' ('), (BLUE, f'+{ed}%'), (WHITE, ')')] + inline
            below = below if S.ENH_DAMAGE_MAX not in ctx.shown else []   # ventilation une seule fois
            ctx.shown |= {S.ENH_DAMAGE_MAX, S.ENH_DAMAGE_MIN}
        out.append([(WHITE, tr('tooltip.base_damage.' + kind, lo=a, hi=b))])
        out.append(segs)
        if below:
            out.append(below)
    return out


def section_quantity(ctx):
    """Quantité des objets empilables (après les dégâts ✅ Javelin, avant les exigences)."""
    it = ctx.it
    return [[(WHITE, f"{ctx.data.key('ItemStats1i')} {it['quantity']}")]] if 'quantity' in it else []


def section_defense(ctx):
    """Défense sur 3 lignes : défense de base stockée et plage de la table (ajout de l'éditeur ; max+1 si l'objet a de
    l'Enhanced Defense), défense du jeu = stockée × (100 + ED%) / 100 + défense plate avec l'ED entre parenthèses
    (✅ 5 objets), ventilation de l'ED."""
    it, data, ids = ctx.it, ctx.data, ctx.ids
    if 'defense' not in it:
        return []
    ed = ids.get(S.ENH_DEFENSE, 0)
    dv = it['defense'] * (100 + ed) // 100 + ids.get(S.DEFENSE, 0)
    segs, below = [(WHITE, f"{data.key('ItemStats1h')} {dv}")], []
    if ed:
        inline, below = ctx.pct_ranges(S.ENH_DEFENSE)
        segs += [(WHITE, ' ('), (BLUE, f'+{ed}%'), (WHITE, ')')] + inline
        ctx.shown.add(S.ENH_DEFENSE)
    lo, hi = base_defense_range(it, data)   # plage de la table, × 1,25 si éthéré
    out = [[(WHITE, tr('tooltip.base_defense', v=it['defense'])), *([(GREY, f' [{lo}-{hi}]')] if lo != hi else [])], segs]
    return out + ([below] if below else [])


def section_block(ctx):
    """Chance de blocage des boucliers : base + « Base Block Chance » de l'objet (stat 20, ✅ documentation : Danmaku,
    1 + 3 (Amazone) + 1 = 5 %) + bonus de la classe du personnage."""
    block = ctx.base().block
    if 'shld' not in ctx.types or not block:
        return []
    bonus = ctx.ids.get(S.BASE_BLOCK, 0)
    blk = block + bonus + (ctx.data.block_factor[ctx.char['cls']] if ctx.char else 0)
    return [block_line(ctx.data, blk, bool(bonus))]


def section_requirements(ctx):
    """Exigences, en rouge si le personnage ne les remplit pas."""
    return [[(RED if unmet else WHITE, txt)] for txt, unmet in requirements(ctx.it, ctx.data, ctx.char)]


def section_weapon(ctx):
    """Armes : classe d'arme et texte de vitesse d'attaque, bonus de dégâts Force / Dextérité."""
    it, data, char, out = ctx.it, ctx.data, ctx.char, []
    if 'weap' not in ctx.types:
        return out
    anc = data.type_ancestors(ctx.base().type)
    wc = next((sidx for t, sidx in WEAPON_CLASS if t in anc), None)
    if wc:
        spd = attack_speed_text(it, data, char, ctx.ids.get(S.ATTACK_SPEED, 0))
        out.append([(WHITE, f"{data.s(wc)} - {spd}" if spd else data.s(wc))])
    for key, k, attr, _ in DMG_BONUS:
        bonus = ctx.base().dmg_bonus[k]
        if bonus:
            out.append([(WHITE, f"{data.key(key)} {bonus * char[attr] // 100}%" if char
                         else f"{data.key(key)} {bonus}% / 100 pts")])
    return out


def section_usage(ctx):
    """Textes d'usage (D2Sigma.dll 0x1007C930 / 0x10079C10) : à sertir, charme, à ouvrir, à lire."""
    it, data, out = ctx.it, ctx.data, []
    if ctx.types & {'gem', 'jewl', 'rune'} or data.gems.get(it['code']):
        out.append([(WHITE, data.key('ExInsertSocketsX'))])
    elif 'char' in ctx.types:
        out.append([(WHITE, data.key('Charmdes'))])
    if it['code'] == 'box ':
        out.append([(WHITE, data.key('RightClicktoOpen'))])
    elif it['code'] == 'bkd ' or ctx.base().spell == 13:
        out.append([(WHITE, data.key('RightClicktoRead'))])
    return out


def section_stats(ctx):
    """Stats : gemme / rune = bonus par type d'objet (ligne vide puis titre de chaque groupe, ✅ capture Diamond) ;
    sinon stats de l'objet dans l'ordre du jeu, avec plages et ventilation par source (ligne du dessous), sans celles
    déjà affichées par une autre section."""
    it, data, char, out = ctx.it, ctx.data, ctx.char, []
    if data.gems.get(it['code']):
        for key, mods in zip(GEM_GROUPS, data.gems[it['code']]):
            out.append([(WHITE, '')])
            out.append([(GOLD, data.key(key))])
            out += [[(WHITE, t)] for _, t, _, _ in stat_lines(mods_stats(mods, data), data, char)]
        return out
    for c, t, inline, below in stat_lines([s for s in ctx.stats if s['id'] not in ctx.shown], data, char, ctx.ranges,
                                          two_handed=bool(ctx.base().two_handed)):
        out.append([*segments(c, t), *inline])   # texte à plusieurs couleurs : ColoredText
        if below:
            out.append(below)
    return out


def ethereal_line(data):
    """« Ethereal », en gris, après les exigences (et la ligne de l'arme) : ✅ capture de Glyph Basher (Totem Shield
    éthéré, avant « Prefixes: 3 ») ; documentation du jeu (Storm Blade, après « Dexterity Damage Bonus »)."""
    return [(GREY, data.key('EtherealQ'))]


def section_ethereal(ctx):
    """Objet éthéré : ligne « Ethereal » (ethereal_line)."""
    return [ethereal_line(ctx.data)] if ctx.it.get('ethereal') else []


def section_sockets(ctx):
    """Nombre de sockets, en bleu, en fin d'infobulle."""
    return [sockets_line(ctx.data, ctx.it['sockets'])] if ctx.it.get('sockets') else []


# sections de l'infobulle d'un objet, dans l'ordre du jeu (les stats après les sections qui en affichent certaines)
ITEM_SECTIONS = (section_name, section_damage, section_quantity, section_defense, section_block, section_requirements,
                 section_weapon, section_ethereal, section_usage, section_stats, section_sockets)


def item_tooltip(it, data, char=None, sections=ITEM_SECTIONS):
    """Lignes de l'infobulle du jeu (+ ajouts de l'éditeur : plages, ventilation, valeurs de base) : sections
    assemblées dans l'ordre. char = personnage (load_character) ou None."""
    return assemble(TooltipContext(it, data, char), sections)


def requirements(it, data, char=None):
    """Exigences de l'objet dans l'ordre du jeu, [(texte, non remplie)] : classe imposée, niveau, Force, Dextérité
    (réduites par la stat 91 « Requirements -x% », −10 si éthéré). « non remplie » = le personnage char ne la
    remplit pas (toujours False sans personnage). Source unique des lignes rouges et du fond rouge des cases."""
    out = []
    cls = item_class(it, data)
    if cls is not None:
        out.append((data.key(CLASS_ONLY_KEYS[cls]), bool(char) and char['cls'] != cls))
    rl = required_level(it, data)
    if rl > 0:
        out.append((f"{data.key('ItemStats1p')} {rl}", bool(char) and char['level'] < rl))
    reduction = sum(s['value'] for s in all_stats(it, data) if s['id'] == S.REQUIREMENTS)
    rs, rd = data.base(it['code']).req_str_dex
    for key, req, attr in (('ItemStats1e', rs, 'strength'), ('ItemStats1f', rd, 'dexterity')):
        if req:
            req = required_attr(req, reduction, it.get('ethereal'))
            if req > 0:
                out.append((f"{data.key(key)} {req}", bool(char) and char[attr] < req))
    return out


def requirements_unmet(it, data, char):
    """Vrai si le personnage ne peut pas utiliser l'objet : la case est alors rouge dans le coffre du jeu."""
    return any(unmet for _, unmet in requirements(it, data, char))
