"""Règles du jeu sur les objets : affixes et mods d'origine des stats, plages autorisées, stats liées, stats
cachées, noms (rares, runewords), libellés, gemmes et runes serties. Fonctions sans état (tables passées en data)."""
import stat_ids as S
from i18n import tr


# Couples (min, max) affichés sur une même ligne (« Adds 5-6 Fire Damage »…) mais édités séparément :
# dégâts plats (arme, 2e arme, lancer), feu, foudre, magie, froid, poison
MIN_MAX_PAIRS = [(S.MIN_DAMAGE, S.MAX_DAMAGE), (S.MIN_DAMAGE_2, S.MAX_DAMAGE_2), (S.THROW_MIN_DAMAGE, S.THROW_MAX_DAMAGE),
                 (S.FIRE_MIN, S.FIRE_MAX), (S.LIGHTNING_MIN, S.LIGHTNING_MAX), (S.MAGIC_MIN, S.MAGIC_MAX),
                 (S.COLD_MIN, S.COLD_MAX), (S.POISON_MIN, S.POISON_MAX)]


def item_type_codes(it, data):
    """Codes des types de l'objet (itemtypes), parents compris : ex. {'rune', 'sock', 'misc'}."""
    return {data.itypes[t][0] for t in data.type_ancestors(data.base(it['code']).type)}


def is_rune(it, data):
    """Vrai pour une rune, d'après son type d'objet : runes r01… et Enchanted Runes rx01… (type 'rune')."""
    return 'rune' in item_type_codes(it, data)


def affix(data, kind, save_id):
    """kind = 'magicprefix' ou 'magicsuffix' ; save_id = valeur lue dans l'objet."""
    return data.affixes[kind][save_id - 1] if save_id else None


def affix_sources(it):
    """Liste des (table, id) des affixes qui ont généré les stats de l'objet."""
    src = []
    if it.get('prefix'): src.append(('magicprefix', it['prefix']))
    if it.get('suffix'): src.append(('magicsuffix', it['suffix']))
    for k, a in enumerate(it.get('rare_affixes') or []):   # rares : P, S, P, S, P, S
        if a: src.append(('magicprefix' if k % 2 == 0 else 'magicsuffix', a))
    if it.get('auto_affix'): src.append(('automagic', it['auto_affix']))
    return src


def mod_ranges(data, prop, param, lo, hi):
    """Traduit un mod (propriété, param, min, max) en {stat: (min, max)} selon la fonction
    de la propriété (vérifié sur le runeword Shark)."""
    func = data.prop_func[prop]
    stats = [x for x in data.props[prop] if x >= 0]
    if func == 11:                 # x % de chance de lancer une compétence : valeur = min (chance),
        return {stats[0]: (lo, lo)} if stats else {}   # param = compétence, max = niveau
    if func == 12:                 # param aléatoire (réanimation : monstre tiré entre min et max) : valeur fixe = param
        return {s_: (param, param) for s_ in stats}     # du mod (✅ Bonefiend : 2 %, monstres 3374 à 3381)
    raw_lo, raw_hi = lo, hi        # champs de la table tels quels (fonctions 15 / 16 : une stat chacun, voir plus bas)
    lo, hi = min(lo, hi), max(lo, hi)
    if func == 5:                  # dégâts min plats : arme principale, secondaire, lancer
        return {S.MIN_DAMAGE: (lo, hi), S.MIN_DAMAGE_2: (lo, hi), S.THROW_MIN_DAMAGE: (lo, hi)}
    if func == 6:                  # dégâts max plats
        return {S.MAX_DAMAGE: (lo, hi), S.MAX_DAMAGE_2: (lo, hi), S.THROW_MAX_DAMAGE: (lo, hi)}
    if func == 7:                  # dégâts améliorés : stats 17 et 18
        return {S.ENH_DAMAGE_MAX: (lo, hi), S.ENH_DAMAGE_MIN: (lo, hi)}
    if func == 17 and param:       # valeur « par niveau » portée par param
        return {stats[0]: (param, param)} if stats else {}
    funcs = data.prop_funcs[prop]
    if 15 in funcs or 16 in funcs:   # 15 = min, 16 = max, 17 = param (dégâts élémentaires : fixes, ✅ Throwing Axe)
        # champs pris tels quels, même si min > max (✅ documentation : set Archbishop Lazarus, propriété 250 min 100
        # max 50 : « +100% to Summon Life » et « +50% to Summon Damage », pas l'inverse)
        pick = {15: (raw_lo, raw_lo), 16: (raw_hi, raw_hi), 17: (param, param)}
        raw = [x for x in data.props[prop]]
        out = {st: pick[f] for st, f in zip(raw, funcs) if st >= 0 and f in pick}
        # dégâts plats (« Adds x-y Damage ») : aussi en deux mains et au lancer, comme les fonctions 5 / 6
        # (✅ documentation : Durandal, Qarak's Will, Carsomyr : Two-Hand Damage avec les dégâts plats)
        for one, others in ((S.MIN_DAMAGE, (S.MIN_DAMAGE_2, S.THROW_MIN_DAMAGE)),
                            (S.MAX_DAMAGE, (S.MAX_DAMAGE_2, S.THROW_MAX_DAMAGE))):
            if one in out:
                out.update({o: out[one] for o in others if o not in out})
        return out
    return {s_: (lo, hi) for s_ in stats}


def runeword_row(it, data):
    """Indice de la ligne de runes.bin de l'objet (via runes serties + type), ou None."""
    if 'runeword' not in it:
        return None
    runes = [data.item_index.index(s['code']) for s in it.get('socketed', [])
             if s['code'] in data.item_index and is_rune(s, data)]
    anc = data.type_ancestors(data.base(it['code']).type)
    rows = [i for i, (n, rr, ok, ex) in enumerate(data.runewords)
            if rr and rr == runes and anc & set(ok) and not anc & set(ex)]
    return rows[0] if len(rows) == 1 else None


def unique_row(it, data):
    """Ligne de uniqueitems.bin d'un unique (n° enregistré = n° de ligne), ou None : pas un unique, n° hors table
    (ex. 32767 des uniques de quête comme le Horadric Malus) ou ligne d'un autre objet de base (garde-fou)."""
    if it.get('quality') != 'unique':
        return None
    uid = it.get('set_unique_id')
    if uid is None or uid >= len(data.uniques) or data.uniques[uid]['code'] != it['code']:
        return None
    return data.uniques[uid]


def table_row(key, data):
    """Ligne de uniqueitems.bin ou setitems.bin d'une entrée du catalogue : clé 'unique:<n°>' ou 'set:<n°>' (une
    éventuelle suite, ex. la place éthérée ':eth', est ignorée)."""
    kind, row = key.split(':')[:2]
    return (data.uniques if kind == 'unique' else data.set_items)[int(row)]


def set_row(it, data):
    """Ligne de setitems.bin d'un objet de set (n° enregistré = n° de ligne, supposé), ou None : pas un objet de set,
    n° hors table ou ligne d'un autre objet de base (garde-fou)."""
    if it.get('quality') != 'set':
        return None
    sid = it.get('set_unique_id')
    if sid is None or sid >= len(data.set_items) or data.set_items[sid]['code'] != it['code']:
        return None
    return data.set_items[sid]


def auto_tiers(it, data):
    """Paliers de l'auto-affixe de l'objet, ou None. Un auto-affixe à paliers (ex. « InnateVelocity » des bottes :
    vitesse 10, 15… 40 selon l'ilvl) = lignes d'automagic du même groupe, mêmes mods, valeurs fixes. Paliers
    possibles : ligne actuelle + lignes qui peuvent apparaître sur cet objet (apparition, niveau <= ilvl <= niveau
    max, type autorisé et non exclu). Seulement si les stats du palier ne viennent d'aucun autre mod de l'objet
    (sinon la valeur ne dit pas quel palier choisir).
    Renvoie {'tiers': [(n° d'auto-affixe, {stat: valeur})…] triés par valeur, 'stats': stats du palier}."""
    aid = it.get('auto_affix')
    table = data.affixes['automagic']
    if not aid or aid > len(table):
        return None
    cur = table[aid - 1]
    shape = lambda a: [(m['prop'], m['param']) for m in a['mods']]
    types, ilvl = data.type_ancestors(data.base(it['code']).type), it.get('ilvl', 0)
    tiers = []
    for i, a in enumerate(table):
        if a['group'] != cur['group'] or shape(a) != shape(cur):
            continue
        if i + 1 != aid and not (a['spawnable'] and a['level'] <= ilvl and (not a['maxlevel'] or ilvl <= a['maxlevel'])
                                 and a['itypes'] & types and not a['etypes'] & types):
            continue
        values = {}
        for m in a['mods']:
            for sid, (lo, hi) in mod_ranges(data, m['prop'], m['param'], m['min'], m['max']).items():
                if lo != hi:
                    return None   # palier à plage : pas un palier fixe
                values[sid] = lo
        tiers.append((i + 1, values))
    if len(tiers) < 2:
        return None
    stats = set(tiers[0][1])
    others = [m for m in item_mods(it, data, tiers=False) if m not in
              [(mm['prop'], mm['param'], mm['min'], mm['max']) for mm in cur['mods']]]
    if any(stats & set(mod_ranges(data, *m)) for m in others):
        return None
    key = sorted(stats)[0]
    return dict(tiers=sorted(tiers, key=lambda t: t[1][key]), stats=stats)


def item_mods(it, data, stat_list='stats', tiers=True):
    """Mods (propriété, param, min, max) d'où viennent les stats d'une liste de l'objet :
    'stats' = sous-qualité Superior + affixes (magiques, rares, auto-affixe) + mods de l'unique ou de l'objet de set ;
    'stats_runeword' = mods du runeword. Auto-affixe à paliers (auto_tiers, si tiers) : ses mods couvrent tous
    les paliers possibles (min du plus petit, max du plus grand)."""
    if stat_list == 'stats_runeword':
        row = runeword_row(it, data)
        return [(m['prop'], m['param'], m['min'], m['max']) for m in data.runeword_mods[row]] if row is not None else []
    mods = []
    if it.get('quality') == 'superior' and 'subquality' in it:
        mods += [(m['prop'], m['param'], m['min'], m['max']) for m in data.quality_mods[it['subquality']]]
    at = auto_tiers(it, data) if tiers else None
    for kind, sid in affix_sources(it):
        a = affix(data, kind, sid)
        if kind == 'automagic' and at:   # mods élargis à tous les paliers possibles
            rows = [data.affixes['automagic'][t - 1]['mods'] for t, _ in at['tiers']]
            mods += [(m['prop'], m['param'], min(r[k]['min'] for r in rows), max(r[k]['max'] for r in rows))
                     for k, m in enumerate(a['mods'])]
            continue
        mods += [(m['prop'], m['param'], m['min'], m['max']) for m in (a['mods'] if a else [])]
    u = unique_row(it, data) or set_row(it, data)   # affixes propres d'un unique ou d'un objet de set
    if u:
        mods += [(m['prop'], m['param'], m['min'], m['max']) for m in u['mods']]
    return mods


def linked_stats(it, stat_id, data, stat_list='stats'):
    """Stats générées par le même mod et qui doivent rester égales
    (ex. 17/18 dégâts améliorés, 0/1/2/3 « tous les attributs »)."""
    for m in item_mods(it, data, stat_list):
        r = mod_ranges(data, *m)
        if stat_id in r and len(r) > 1 and len(set(r.values())) == 1:
            present = {s['id']: s['value'] for s in it.get(stat_list, [])}
            group = [x for x in r if x in present]
            if len({present[x] for x in group}) == 1:
                return group
    return [stat_id]


def is_innate_damage(sid, data):
    """Dégâts innés (descfunc 35, ex. « Innate Lightning Damage: 5 (13.0% of Strength) ») : dégâts calculés
    à partir d'un attribut du personnage. Règle du projet : pas de variance, jamais éditables, même si les
    tables donnent une plage à l'affixe."""
    return data.isc[sid]['func'] == 35




def stat_range(it, stat_id, data, stat_list='stats', param=None):
    """(min, max) autorisés pour une stat par les mods de l'objet ou du runeword (None si inconnu).
    Plusieurs mods donnant la même stat (ex. deux affixes d'un rare) : le jeu additionne, les plages aussi.
    param : param de la stat (ex. compétence de « +x to <compétence> ») : seuls les mods qui donnent ce param comptent
    (✅ Auto Da Fe : +(1 to 2) to Ignis Fatuus et +(3 to 4) to Flamefront, deux stats 97 : pas [4-6] pour chacune) ;
    aucun mod de ce param (param calculé autrement, ex. classe de « Skill Levels ») : tous les mods de la stat."""
    if stat_id in (S.PREFIX_COUNT, S.SUFFIX_COUNT):   # compteurs de préfixes/suffixes : pas une vraie plage
        return None
    if is_innate_damage(stat_id, data):   # dégâts innés : pas de variance (règle du projet)
        return None
    lo = hi = 0
    found = False
    mods = item_mods(it, data, stat_list)
    if param is not None:
        mods = [m for m in mods if any(s['id'] == stat_id and s['param'] == param for s in mods_stats([m], data))] or mods
    for prop, mod_param, mn, mx in mods:
        stats = [x for x in data.props[prop] if x >= 0]
        if stat_list == 'stats' and stat_id in S.ELEMENTAL_WITH_LENGTH and stat_id in stats \
                and stat_id == stats[-1] and len(stats) > 1:
            return (mod_param, mod_param) if mod_param else None   # durée (froid/poison) = param du mod
        r = mod_ranges(data, prop, mod_param, mn, mx)
        if stat_id in r:
            if stat_list == 'stats_runeword':   # runeword : 1er mod trouvé (comportement vérifié sur le Shark)
                return r[stat_id]
            lo, hi, found = lo + r[stat_id][0], hi + r[stat_id][1], True
    return (lo, hi) if found else None


# stats dont la valeur AFFICHÉE est meilleure quand elle est plus basse (le négatif est un avantage) : pénétration des
# résistances ennemies, exigences, coût en mana, prix des marchands, épuisement de l'endurance (« x% Faster Stamina
# Drain » = malus, Hellrush) ; toutes les autres : plus haut = meilleur (malus en négatif), Light Radius compris
# (décision du 30/09)
LOWER_IS_BETTER = frozenset(S.ENEMY_RESISTANCES + (S.REQUIREMENTS, S.MANA_COST, S.VENDOR_PRICES, S.STAMINA_DRAIN))


def higher_stored_is_better(sid, data):
    """Vrai si la valeur ENREGISTRÉE la plus haute est la meilleure : valeur affichée = enregistrée, sauf le format 20
    qui l'affiche en négatif (« -4% to Enemy Lightning Resistance » : 4 enregistré) ; meilleure valeur affichée = la
    plus haute, sauf LOWER_IS_BETTER."""
    return (data.isc[sid]['func'] != 20) != (sid in LOWER_IS_BETTER)


def worst_best(sid, lo, hi, data):
    """(moins bonne, meilleure) de deux valeurs enregistrées d'une stat : ordre des plages affichées (« [-4 to -5] »,
    « [-5 to -1] » pour un malus) et des curseurs d'édition (décision du 30/09)."""
    lo, hi = min(lo, hi), max(lo, hi)
    return (lo, hi) if higher_stored_is_better(sid, data) else (hi, lo)


def ethereal_base(v, ethereal):
    """Valeur de base (défense, dégâts) d'un objet éthéré : × 1,25 arrondi vers le bas (✅ en jeu : Totem Shield
    [42-82] -> [52-102] éthéré ; documentation du jeu : Iron Shard, dégâts) ; sinon inchangée."""
    return v * 5 // 4 if ethereal else v


def base_defense_range(it, data):
    """(min, max) de la défense de base de l'objet : plage de la table, × 1,25 si éthéré (ethereal_base)."""
    return tuple(ethereal_base(v, it.get('ethereal')) for v in data.base(it['code']).def_range)


ETHEREAL_PROP_FUNC = 23   # fonction de propriété « ethereal » d'une ligne d'unique / de set (objet toujours éthéré)


def indestructible_base(code, data):
    """Arme ou armure dont la base n'a pas de durabilité (arcs, arbalètes, 10 autres bases) : jamais éthérée (règle de
    Diablo II ; décision du 07/10 : ni place éthérée dans la collection, ni bascule éthérée)."""
    b = data.base(code)
    return b.kind in ('weapons', 'armor') and b.durability == 0


def row_always_ethereal(row, data):
    """Ligne d'unique / de set toujours éthérée (propriété « ethereal », ✅ Iron Shard, Tyrael's Might)."""
    return bool(row) and any(data.prop_func[m['prop']] == ETHEREAL_PROP_FUNC for m in row.get('mods', []))


def defense_range(it, data):
    """(min, max) éditables de la défense de base d'une armure (base_defense_range : éthérée comprise), ou None :
    fixe (min = max) ou objet avec Enhanced Defense, dont la défense de base vaut max + 1 (règle du jeu, non éditable)."""
    if 'defense' not in it:
        return None
    lo, hi = base_defense_range(it, data)
    if lo == hi or it['defense'] > hi:
        return None
    return lo, hi


def rare_name(it, data):
    """Nom d'un rare. Validé en jeu : 1er id - 183 = ligne de rareprefix, 2e id = ligne de raresuffix.
    Le texte à 0x26 est une clé de string.tbl (ex. 'PlagueRI' -> 'Plague')."""
    if 'rare_names' not in it:
        return None
    a, b = it['rare_names']
    p = a - len(data.rare_suffix)
    pre = data.rare_prefix[p] if 0 <= p < len(data.rare_prefix) else f'?{a}'
    suf = data.rare_suffix[b] if 0 <= b < len(data.rare_suffix) else f'?{b}'
    return f'{data.key(pre)} {data.key(suf)}'


def unique_name(it, data):
    """Nom d'un unique (uniqueitems.bin) ou d'un objet de set (setitems.bin), ou None."""
    u = unique_row(it, data) or set_row(it, data)
    return data.key(u['name']) if u else None


def special_name(it, data):
    """Nom propre de l'objet affiché au-dessus du nom de base : rare, unique ou runeword ; None sinon."""
    return rare_name(it, data) or unique_name(it, data) or runeword_name(it, data)


def runeword_name(it, data):
    """Nom du runeword, retrouvé via les runes serties et le type d'objet (l'id enregistré,
    ex. 419 pour la ligne 6 « Shark », n'est pas encore compris)."""
    if 'runeword' not in it:
        return None
    row = runeword_row(it, data)
    return data.key(data.runewords[row][0]) if row is not None else f"runeword #{it['runeword']}"


def text_missing(txt):
    """Texte de table absent : vide, ou marqueur « FLYING POLAR BUFFALO ERROR » des chaînes non définies."""
    return not txt or 'BUFFALO' in txt


# descfunc dont le texte ne vient pas de la stat : 28 (« +x to <compétence> »), 31 et 34 (texte du jeu n° param)
TEXT_ELSEWHERE = (27, 28, 31, 34)


def stat_hidden(sid, data, value=0):
    """Vrai si la stat n'apparaît pas dans l'infobulle du jeu : pas de texte (compteurs, marqueurs internes
    de MXL ; sauf descfunc TEXT_ELSEWHERE) ou descfunc 0 (ex. 372 « Cannot be Unsocketed »). Définition unique."""
    c = data.isc[sid]
    return (c['func'] not in TEXT_ELSEWHERE and text_missing(c['pos'] if value >= 0 else c['neg'])) or c['func'] == 0


CLASSES = ['Amazon', 'Sorceress', 'Necromancer', 'Paladin', 'Barbarian', 'Druid', 'Assassin']


def stat_label(s, data=None):
    """Libellé lisible d'une stat (corrige les descriptions génériques, nomme les compétences)."""
    p = s['param']
    if s['id'] == S.CLASS_SKILLS and p is not None and p < len(CLASSES):
        return f"to {CLASSES[p]} Skill Levels"   # param = classe (validé : 1 = Sorceress)
    desc = s['desc'] or tr('detail.hidden')
    if data and p is not None:
        if '%d%%' in desc and '%s' in desc:     # « x % Chance to cast level y <compétence> on … »
            return (desc.replace('%d%%', f"{s['value']}%", 1).replace('%d', str(p & 63), 1)
                        .replace('%s', data.skill(p >> 6), 1))
        if s['id'] in (S.SINGLE_SKILL, S.SINGLE_SKILL_2):                # +x à une compétence précise (param = compétence)
            return f"to {data.skill(p)}"
        if s['id'] == S.CHARGES:                      # charges : param = compétence × 64 + niveau
            return f"level {p & 63} {data.skill(p >> 6)} (charges)"
        if s['id'] in S.CHANCE_TO_CAST:          # autres « chance de lancer » (texte propre à MXL)
            sk = data.skill_names.get(p >> 6)
            return f"{desc} [{tr('skill.level', skill=sk, level=p & 63)}]" if sk else desc   # « Mega Impact » : sans nom
    return desc


def base_props(it, data=None):
    """Propriétés de base lisibles (défense, dégâts, durabilité, sockets, quantité, éthéré)."""
    base = []
    if 'defense' in it: base.append(tr('base.defense', v=it['defense']))
    bd = data.base(it['code']).damage if data else None
    if bd:
        for lab, (a, b) in (('throw', bd['throw']), ('one', bd['one_hand']), ('two', bd['two_hand'])):
            if b: base.append(tr('base.damage', kind=tr('base.kind.' + lab), a=a, b=b))
    if 'max_durability' in it:
        base.append(tr('base.durability', cur=it.get('durability', '-'), max=it['max_durability']))
    if it.get('sockets'): base.append(tr('base.sockets', n=it['sockets'], filled=len(it.get('socketed', []))))
    if 'quantity' in it:
        base.append(tr('base.quantity', q=it['quantity'], max=data.base(it['code']).stack_max if data else '?'))
    if it.get('ethereal'): base.append(tr('base.ethereal'))
    return base


def mods_stats(mods, data, which='min'):
    """Stats {id, param, value} produites par des mods (propriété, param, min, max) : mods fixes (gemmes, runes) ou,
    pour une plage, sa valeur minimale (which='min') ou maximale (which='max')."""
    stats = []
    for prop, param, lo, hi in mods:
        if data.prop_func[prop] == 21:   # « +x to <classe> Skill Levels » : classe = valeur fixe de la propriété, pas le
            param = data.prop_vals[prop][0]   # param du mod (✅ documentation : Durandal, « +(2 to 3) to Barbarian Skill
            # Levels » sur une Claymore sans classe imposée ; Eternal Bone Pile : une plage (1 to 2) par classe)
        if data.prop_func[prop] == 11:   # chance de lancer : param = compétence, min = chance, max = niveau
            sid = next((x for x in data.props[prop] if x >= 0), None)
            if sid is not None:
                stats.append(dict(id=sid, param=param * 64 + hi, value=lo))
            continue
        if data.prop_func[prop] == 19:   # charges : param = compétence, min = charges, max = niveau -> stat comme dans
            # un objet : param = compétence × 64 + niveau, valeur = charges max × 256 + charges (✅ documentation :
            # Malus Domestica « Level 10 Inner Fire (5/5 Charges) »)
            sid = next((x for x in data.props[prop] if x >= 0), None)
            if sid is not None:
                stats.append(dict(id=sid, param=param * 64 + hi, value=lo * 256 + lo))
            continue
        if data.prop_func[prop] == 12:   # param aléatoire (compétence, monstre) : param de la stat tiré entre min et
            # max, valeur = param du mod (✅ Aidan's Lament : 5 % de réanimer en un monstre 3374 à 3381)
            for sid in (x for x in data.props[prop] if x >= 0):
                stats.append(dict(id=sid, param=hi if which == 'max' else lo, value=param))
            continue
        for sid, (a, b) in mod_ranges(data, prop, param, lo, hi).items():
            if is_innate_damage(sid, data):   # dégâts innés : min = élément, max = pourcentage, param = attribut (n° de
                # stat) -> param de la stat = élément + attribut × 256 comme dans un objet (✅ Shard of Refraction :
                # 5 = tri-élémentaire, 54 %, 2 = Dextérité)
                stats.append(dict(id=sid, param=lo + (param << 8), value=hi))
                continue
            stats.append(dict(id=sid, param=param if data.isc[sid]['param'] else None, value=b if which == 'max' else a))
    return stats


CLASS_ONLY_KEYS = ['AmaOnly', 'SorOnly', 'NecOnly', 'PalOnly', 'BarOnly', 'DruOnly', 'AssOnly']   # « (Amazon Only) »…
GEM_GROUPS = ('GemXp3', 'GemXp4', 'GemXp2')   # clés tbl : « Weapons: », « Armor: », « Shields: »


def gem_group(parent, data):
    """Groupe de bonus d'une gemme / rune sertie dans parent : 0 arme, 1 armure, 2 bouclier."""
    kind = data.base(parent['code']).kind
    if kind == 'weapons':
        return 0
    return 2 if 'shld' in item_type_codes(parent, data) else 1
