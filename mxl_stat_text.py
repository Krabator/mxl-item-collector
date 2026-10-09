"""Texte des stats comme le jeu les affiche (Median XL 2.14.5) : formats d'affichage (descfunc), regroupements,
valeurs par niveau ou par point d'attribut, plages « [min-max] » et ventilation par source (objet, runeword, objets
sertis). Utilisé par l'infobulle d'un objet (mxl_tooltip), celle du catalogue (mxl_catalog_tooltip) et l'édition
(mxl_edit). Segments de texte : (code couleur, texte), codes nommés dans mxl_theme.
"""
import re
from i18n import tr
import stat_ids as S
from mxl_data import strip_colors
from mxl_theme import WHITE, RED, BLUE, GREY, BRIGHT_GOLD, GAME_COLORS
from mxl_rules import (CLASS_ONLY_KEYS, stat_hidden, text_missing, stat_range, mods_stats, stat_label, gem_group,
                        is_rune, is_innate_damage, worst_best)

ATTR_KEYS = {S.STRENGTH: 'strength', S.ENERGY: 'energy', S.DEXTERITY: 'dexterity', S.VITALITY: 'vitality'}


# ---------------------------------------------------------------- textes des stats

def regen_shown(v):
    """Régénération affichée (descfunc 32 de Median XL, D2Sigma.dll 0x10077800) : valeur / 10 tronquée vers zéro, au
    moins 1 si elle est positive, au plus −1 si elle est négative (1125 -> 112 ; 5 -> 1)."""
    t = int(v / 10)
    return max(1, t) if v > 0 else min(-1, t) if v < 0 else 0


def _num(func, v):
    plus = f'+{v}' if v >= 0 else str(v)
    return {1: plus, 2: f'{plus}%', 3: str(v), 4: f'{plus}%', 5: f'{v * 100 // 128}%',
            6: plus, 7: f'{v}%', 8: f'{plus}%', 9: str(v), 10: f'{v * 100 // 128}%', 12: plus,
            13: plus, 20: f'{-v}%', 32: f'+{regen_shown(v)}' if v >= 0 else str(regen_shown(v)),
            38: f'{v}%'}.get(func)   # 38 : « Activation Frequency 15% » (✅ documentation : Elder Law)


def _num_rate(func, x):
    """Nombre non entier (valeur par niveau) au format d'affichage func, comme _num : signe, « % », régénération ÷ 10
    (format 32 : ✅ Staff of Herding, 480 / 32 par niveau -> 1.5 Life Regenerated per Second)."""
    if func == 32:
        x /= 10
    num = f'+{x:.10g}' if x >= 0 and func in (1, 2, 4, 6, 8, 12, 13, 32) else f'{x:.10g}'
    return num + ('%' if func in (2, 4, 7, 8) else '')


def _fmt(func, val, s1, s2, v, num=None):
    num = num or _num(func, v)
    if num is None:
        return None
    # 2e texte (« (Based on Character Level) ») toujours en fin de ligne, après la valeur si elle suit le texte
    # (✅ documentation : Battlemaiden « Weapon Physical Damage 2.4375% (Based on Character Level) »)
    s2 = f' {s2}' if func in (6, 7, 8, 9, 10) and not text_missing(s2) else ''
    return f'{s1}{s2}' if val == 0 else f'{num} {s1}{s2}' if val == 1 else f'{s1} {num}{s2}'


def socket_contents(it, data):
    """[(objet serti, source, stats)] : gemme / rune → source 'G' / 'R', bonus fixes (gems.bin) du groupe du porteur
    (arme, armure, bouclier) ; joyau → source 'J', ses propres stats. Définition unique du contenu des sockets."""
    out = []
    for sub in it.get('socketed', []):
        groups = data.gems.get(sub['code'])
        if groups:
            out.append((sub, 'R' if is_rune(sub, data) else 'G', mods_stats(groups[gem_group(it, data)], data)))
        else:
            out.append((sub, 'J', sub.get('stats', [])))
    return out


def range_key(sid, param):
    """Clé de stat_ranges : n° de stat, ou (n°, param) pour une stat à param (deux « +x to <compétence> »)."""
    return sid if param is None else (sid, param)


def stat_ranges(it, data):
    """{clé range_key: [(valeur, (min, max) ou None, source), …]} : une entrée par source, dans l'ordre
    B (base de l'objet : affixes, sous-qualité Superior), RW (runeword), puis objets sertis : R (rune),
    G (gemme), J (joyau, plage = celle de ses propres affixes). Plage None si fixe (min = max) ou inconnue."""
    res = {}

    def add(key, v, r, src):
        res.setdefault(key, []).append((v, r if r and r[0] != r[1] else None, src))
    from mxl_orbs import orb_shares, own_value_ok
    orbs = orb_shares(it, data)
    for stat_list, src in (('stats', 'B'), ('stats_runeword', 'RW')):
        for st in it.get(stat_list, []):
            key, v = range_key(st['id'], st.get('param')), st['value']
            shares = orbs.get((st['id'], st.get('param')), []) if src == 'B' else []
            if not shares:
                add(key, v, stat_range(it, st['id'], data, stat_list, st.get('param')), src)
                continue
            # Mystic Orbs (mxl_orbs.orb_shares, valeurs actuelles) : B = reste ; B impossible pour l'objet (hors de sa
            # plage, ou ≠ 0 sans stats propres) = valeurs des orbes changées depuis leur pose : source 'B!' (en rouge)
            own = v - sum(x for _, x in shares)
            ok = own_value_ok(it, st['id'], st.get('param'), own, data)
            if own or not ok:
                add(key, own, None, 'B' if ok else 'B!')
            for _, x in shares:
                add(key, x, None, 'O')
    for sub, src, stats in socket_contents(it, data):
        if src == 'J':   # joyau : ses stats, avec la plage de ses propres affixes
            for st in stats:
                add(range_key(st['id'], st.get('param')), st['value'],
                    stat_range(sub, st['id'], data, 'stats', st.get('param')), 'J')
        else:            # gemme / rune : bonus fixes, additionnés par stat
            tot = {}
            for st in stats:
                tot[st['id']] = tot.get(st['id'], 0) + st['value']
            for sid, v in tot.items():
                add(sid, v, None, src)
    return res


def is_per_level(sid, data):
    """Stat « par niveau du personnage » (op ∈ {2, 4, 5}, base = stat 12 niveau)."""
    c = data.isc[sid]
    return c['op_base'] == S.LEVEL and c['op'] in (2, 4, 5)


def per_level(sid, v, data, char=None):
    """Valeur d'une stat « par niveau » : (valeur × niveau du personnage) >> op_param (niveau 1 sans personnage)."""
    return (v * (char['level'] if char else 1)) >> data.isc[sid]['op_param'] if is_per_level(sid, data) else v


def shown_value(sid, v, data, char=None):
    """Valeur telle que le jeu l'affiche (par niveau, régénération ÷ 10, pénétration négative)."""
    c = data.isc[sid]
    v = per_level(sid, v, data, char)
    if c['func'] == 32:
        v = regen_shown(v)
    if c['func'] == 20:
        v = -v
    return v


def _rng(worst, best):
    """Plage « [moins bonne - meilleure] » : « 11-25 » ; avec un nombre négatif « -4 to -5 », « -5 to -1 »."""
    return f'{worst}-{best}' if worst >= 0 and best >= 0 else f'{worst} to {best}'


def is_percent(sid, data):
    """Vrai si la stat s'affiche en pourcentage (règle d'affichage descfunc)."""
    return '%' in (_num(data.isc[sid]['func'], 1) or '')


def range_segs(sids, ranges, data, char=None, conv=None, color=BLUE, pct=False, below=False):
    """Plages d'une valeur : (segments sur la même ligne, segments de la ligne en dessous).
    - une seule source à variance (base ou runeword) : « [min-max] » en gris ;
    - plusieurs sources, ou source sertie (rune, gemme, joyau, même seule) : ventilation « (B:50% [35-50] + RW:35% [24-35]) » : parenthèses, « + » et étiquettes
      de source en blanc (B base, RW runeword, R rune, G gemme, J joyau), valeur (avec « % » si pct) dans la
      couleur de la stat, plage en gris. Sur la même ligne, ou sur la ligne en dessous si below
      (pourcentage de dégâts / de défense) ;
    - ligne min-max (2 stats) : les deux parties séparées par « / ». conv : conversion spéciale (poison)."""
    if not ranges:
        return [], []
    unit = '%' if pct else ''
    f = conv or (lambda sid, v: shown_value(sid, v, data, char))
    # plage de la moins bonne à la meilleure valeur (worst_best : décision du 30/09)
    rng = lambda r, sid: f"[{_rng(*(f(sid, v) for v in worst_best(sid, r[0], r[1], data)))}]"

    def part(key):   # (plusieurs sources ?, segments) ; clé range_key
        src = ranges.get(key, [])
        sid = key[0] if isinstance(key, tuple) else key
        if len(src) > 1 or (src and src[0][2] in ('R', 'G', 'J', 'O', 'B!')):   # serti, orbe : source toujours indiquée
            segs = []
            for k, (v, r, kind) in enumerate(src):
                # 'B!' : part propre impossible (valeurs des Mystic Orbs changées depuis leur pose) : « B: » en rouge
                val_color = RED if kind == 'B!' else color
                segs += ([(WHITE, ' + ')] if k else []) + [(WHITE, f"{kind.rstrip('!')}:"), (val_color, f"{f(sid, v)}{unit}")]
                segs += [(GREY, ' ' + rng(r, sid))] if r else []
            return True, segs
        if src and src[0][1]:
            return False, [(GREY, ' ' + rng(src[0][1], sid))]
        return False, []
    parts = [x for x in (part(sid) for sid in sids) if x[1]]
    if not parts:
        return [], []
    if len(parts) == 1 and not parts[0][0]:
        return parts[0][1], []
    if len(parts) > 1 and not any(m for m, _ in parts):
        return [(GREY, ' [' + ' / '.join(sg[0][1].strip(' []') for _, sg in parts) + ']')], []   # « [a-b / c-d] »
    out = []
    for k, (m, segs) in enumerate(parts):
        out += ([(WHITE, ' / ')] if k else []) + segs
    if below:
        return [], [(WHITE, '(')] + out + [(WHITE, ')')]
    return [(WHITE, ' (')] + out + [(WHITE, ')')], []


# texte « Adds x-y … Damage » des couples min / max de MIN_MAX_PAIRS (clés tbl), dans cet ordre
RANGE_TEXT = {(S.FIRE_MIN, S.FIRE_MAX): 'strModFireDamageRange', (S.LIGHTNING_MIN, S.LIGHTNING_MAX): 'strModLightningDamageRange',
              (S.MAGIC_MIN, S.MAGIC_MAX): 'strModMagicDamageRange', (S.COLD_MIN, S.COLD_MAX): 'strModColdDamageRange',
              (S.MIN_DAMAGE, S.MAX_DAMAGE): 'strModMinDamageRange'}


def _merge_stats(stats):
    """Stats identiques (même stat, même param : objet + sertis + runeword) additionnées, dans l'ordre ; plusieurs
    sources qui s'annulent (ex. runeword -3 % + rune +3 %) : total nul, ligne non affichée."""
    merged, order, count = {}, [], {}
    for s in stats:
        k = (s['id'], s['param'])
        count[k] = count.get(k, 0) + 1
        if k in merged:
            merged[k] = dict(merged[k], value=merged[k]['value'] + s['value'])
        else:
            merged[k] = dict(s)
            order.append(k)
    return [merged[k] for k in order if not (count[k] > 1 and merged[k]['value'] == 0)]


def _grouped_lines(ids, data, add, two_handed=True, ranged=()):
    """Lignes qui regroupent plusieurs stats, affichées avant les autres : poison (dégâts totaux sur la durée),
    dégâts plats en double, plages « Adds x-y <élément> Damage ». Renvoie les stats ainsi traitées."""
    done = set()
    if S.POISON_MIN in ids:   # poison : 1/256 par frame pendant la durée (POISON_LENGTH, frames de 1/25 s) ; total
        # arrondi à l'entier le plus proche (✅ documentation : Fangskin Scales 300 × 5 / 256 = 5,86 -> 6, Silver Scorpion
        # 362,5 -> 363 ; les 12 lignes des pages Tiered, Sacred et Sets où l'arrondi change la valeur, aucune démentie)
        ln = ids.get(S.POISON_LENGTH, 0)
        total = lambda v: (v * ln + 128) // 256
        lo, hi = total(ids[S.POISON_MIN]), total(ids.get(S.POISON_MAX, ids[S.POISON_MIN]))
        sec = max(1, ln // 25)
        add(S.POISON_MIN, data.key('strModPoisonDamage').replace('%d', str(lo), 1).replace('%d', str(sec), 1) if lo == hi
            else data.key('strModPoisonDamageRange') % (lo, hi, sec),
            [S.POISON_MIN] if lo == hi else [S.POISON_MIN, S.POISON_MAX], lambda sid, v: total(v))
        done |= {S.POISON_MIN, S.POISON_MAX, S.POISON_LENGTH}
    # dégâts plats égaux en version une main et deux mains (une propriété les donne tous) : une seule ligne, celle
    # de l'objet : deux mains pour une arme à deux mains (priorité plus basse, ✅ Jared's Fragmentor, Claymore),
    # une main sinon (✅ documentation : Helepolis, casque, « +38 to Maximum Damage » en tête des affixes)
    for a, b in ((S.MIN_DAMAGE, S.MIN_DAMAGE_2), (S.MAX_DAMAGE, S.MAX_DAMAGE_2)):
        if a in ids and ids.get(b) == ids[a] and not (S.MIN_DAMAGE in ids and S.MAX_DAMAGE in ids):
            done.add(a if two_handed else b)
    for (a, b), key in RANGE_TEXT.items():
        if a in ids and b in ids:
            single = key[:-len('Range')]   # minimum = maximum : texte du jeu à une valeur, « +20 Fire Damage »
            if ids[a] == ids[b] and a not in ranged and b not in ranged and data.key(single) != single:   # (✅ Magebane)
                add(a, data.key(single) % ids[a], [a, b])
            else:
                add(a, data.key(key) % (ids[a], ids[b]), [a, b])
            done |= {a, b} | ({S.MIN_DAMAGE_2, S.MAX_DAMAGE_2, S.THROW_MIN_DAMAGE, S.THROW_MAX_DAMAGE} if a == S.MIN_DAMAGE
                              else {S.COLD_LENGTH} if a == S.COLD_MIN else set())
    return done


def _innate_damage_line(c, v, p, s1, data, char):
    """« Innate Lightning Damage: 5 (13.0% of Strength) » : chaîne 11600 + élément ; dégâts = valeur % × attribut du
    personnage (✅ Throwing Axe, Force 43 ; attribut « Strength » non vérifié ailleurs). param = élément (octet bas :
    0 feu, 1 foudre, 2 froid, 3 poison, 4 magie, 5 tri) + attribut (octet haut : n° de stat 0 Force, 1 Énergie,
    2 Dextérité, 3 Vitalité) ✅ Throwing Axe (1 = foudre / Force), Hexblade (512 = feu / Dextérité).
    Sans personnage : pas de valeur calculée (✅ documentation : « Innate Tri-Elemental Damage: (54.0% of Dexterity) »)."""
    elem, attr = (p or 0) & 0xFF, (p or 0) >> 8
    raw = data.strings.get(11600 + elem, ('', s1))[1]
    attr_name = data.isc[attr]['desc'].replace('to ', '', 1) if attr in data.isc else '?'
    have = ATTR_KEYS.get(attr)
    num_col = raw[raw.index('%d') - 1] if '%d' in raw and raw[raw.index('%d') - 3:raw.index('%d') - 1] == 'ÿc' else WHITE
    parts = raw.replace('ÿc0', '').split('%d')
    head = parts[0].replace('ÿc' + num_col, '')
    tail = parts[1].replace('%.1f%%', f'{v:.1f}%').replace('%s', attr_name)
    if char and have:   # pas de plage : sans signification
        return c['prio'], WHITE, head, [(num_col, str(v * char[have] // 100)), (WHITE, tail)], []
    return c['prio'], WHITE, head, [(WHITE, tail.lstrip())], []


class ColoredText(str):
    """Texte d'une ligne (str : texte simple, pour les écrans qui n'affichent que le texte) et ses morceaux de couleur
    segs [(couleur, texte)] (codes couleur du jeu dans la ligne : « +10 to » bleu puis « Ranged Egg Trap » or) ;
    couleur None : celle de la ligne (segments())."""

    def __new__(cls, segs):
        obj = str.__new__(cls, ''.join(t for _, t in segs))
        obj.segs = list(segs)
        return obj


def game_code(ch):
    """Couleur d'un code ÿc + caractère comme D2Win.dll (caractère − '0' de 0 à 12, sinon blanc)."""
    return ch if 0 <= ord(ch) - ord('0') < 13 and ch in GAME_COLORS else WHITE


def parse_codes(raw, color):
    """Morceaux [(couleur, texte)] d'un texte du jeu avec ses codes ÿc, à partir de la couleur color (None : couleur de
    la ligne) ; et la couleur active à la fin (elle continue sur la suite du texte, comme dans le jeu)."""
    segs = []
    for token in re.split('(ÿc.)', raw):
        if token.startswith('ÿc') and len(token) == 3:
            color = game_code(token[2])
        elif token:
            segs.append((color, token))
    return segs, color


def segments(color, text):
    """Morceaux de couleur d'une ligne de stat de couleur color (texte simple : un seul morceau)."""
    segs = getattr(text, 'segs', None)
    return [(c or color, t) for c, t in segs] if segs else [(color, text)]


def joined(color, text, inline):
    """Ligne complète (texte puis morceaux inline) sans perdre les couleurs d'un ColoredText."""
    if not inline:
        return text
    if isinstance(text, ColoredText):
        return ColoredText(segments(color, text) + list(inline))
    return text + ''.join(x for _, x in inline)


def text_func_color(c, v):
    """Couleur d'un texte du jeu de descfunc 31 / 34 (D2Sigma.dll 0x10077720 / 0x10077cb0) : 31 = valeur − 1 (0 à
    12 ; sinon bleu) ; 34 = or vif (8)."""
    if c['func'] == 34:
        return BRIGHT_GOLD
    return chr(ord('0') + v - 1) if isinstance(v, int) and 1 <= v <= 13 and chr(ord('0') + v - 1) in GAME_COLORS else BLUE


def _skill_text_lines(c, sid, p, data, v=None):
    """Median XL, descfunc 31 et 34 : texte du jeu n° param (compétences d'objet), plusieurs lignes affichées de bas en
    haut. Couleur de départ (text_func_color) : descfunc 31 = valeur de la stat − 1 (✅ D2Sigma.dll 0x10077720 ; ex.
    Gotterdammerung « Ragh nar Rook » valeur 8 -> or 7, Astral Blade valeur 4 -> bleu), 34 = or vif ; puis les codes ÿc
    du texte, qui changent la couleur jusqu'au code suivant, y compris sur les lignes suivantes du texte (✅
    documentation : Black Razor « ÿc8Cast a random… » / « ÿc1It also applies to you », Iron Shard ÿc5 sur 3 lignes) ;
    plusieurs couleurs dans une ligne : ColoredText."""
    parts, code = [], text_func_color(c, v)
    for part in data.strings.get(p, ('', ''))[1].split('\n'):
        segs, end = parse_codes(part, code)
        code = end
        if strip_colors(part).strip():
            parts.append((segs[0][0], ColoredText(segs) if len({x for x, _ in segs}) > 1 else strip_colors(part)))
    return [(c['prio'], col, part, [], []) for col, part in reversed(parts)]


def _named(prefix, raw, plain):
    """« <prefix><nom> » : nom du jeu avec ses codes couleur (ColoredText ; préfixe dans la couleur de la ligne), ou le
    nom simple s'il n'a pas de code."""
    if 'ÿc' not in (raw or ''):
        return prefix + plain
    segs, _ = parse_codes(raw, None)
    return ColoredText([(None, prefix)] + segs)


def _stat_text(s, c, v, p, s1, data, char, attr_num):
    """Texte d'une stat selon son format d'affichage (descfunc), ou None : ligne absente."""
    sid = s['id']
    if c['func'] in (27, 28, 33, 37) and p is not None and p in data.skill_hidden:
        return None   # compétence cachée dans l'infobulle des objets (skills2.bin @0x31, D2Sigma.dll 0x100af880 ; ✅
        # documentation : pas de « +1 to Chillstring Gematria », « +1 to Jerhyn's Tawiz »)
    if c['func'] == 27 and p is not None:   # « +x to <compétence> (<classe> Only) » (stat 107) : classe de la compétence
        name = data.skill_names.get(p)          # (✅ documentation : Shadowsabre « +15 to Way of the Raven (Assassin Only) »)
        if not name:
            return None
        cls = data.skill_class.get(p, 255)
        line = _named(f"{_num(1, v)} to ", data.skill_names_raw.get(p), name)
        suffix = f" {data.key(CLASS_ONLY_KEYS[cls])}" if cls < len(CLASS_ONLY_KEYS) else ''
        return ColoredText(segments(None, line) + [(None, suffix)]) if isinstance(line, ColoredText) and suffix else line + suffix
    if c['func'] == 28:   # « +x to <compétence> » (stat 97) ; compétence sans nom : ligne absente (✅ Undead Crown)
        name = data.skill_names.get(p) if p is not None else None
        return _named(f"{_num(1, v)} to ", data.skill_names_raw.get(p), name) if name else None   # nom à sa couleur
        # (✅ documentation : Strixclaw « +10 to » bleu puis « Ranged Egg Trap » or, nom « ÿc4Ranged Egg Trap »)
    if c['func'] == 3 and c['val'] == 0:
        return s1                                           # texte seul (Mega Impact)
    if c['func'] == 36:   # Median XL : texte seul, seulement si la valeur vaut 2 (D2Sigma.dll 0x10077ff7) : « Orb Effects
        return s1 if v == 2 else None   # … Doubled » ; 4 (Natalya's Deception) : rien, sa ligne « Quadrupled » est à part
    if c['func'] == 23 and p is not None:
        # « 2% Reanimate as: <monstre> » : param = monstre (monstats), valeur = chance (comme dans le jeu, ✅
        # documentation : Shadowfang « 2% Reanimate as: Veil Terror ») ; -1 = plage de monstres (catalogue)
        if 0 <= p < len(data.monster_names):   # nom du monstre à sa couleur (✅ documentation : Sanctuary « Edyrem » jaune)
            return _named(f"{v}% {s1} ", data.monster_names_raw[p], data.monster_names[p])
        return f"{v}% {s1} {tr('tooltip.random_monster')}"
    if c['func'] == 33 and p is not None:
        # Median XL : « %s Cooldown Reduced by %.1g seconds » (stat 309) : param = compétence, valeur en images de jeu
        # (25 par seconde : ✅ documentation, The Worshipper « Bend the Shadows Cooldown Reduced by 1 seconds »)
        return s1.replace('%s', data.skill(p), 1).replace('%.1g', f'{v / 25:.1g}', 1) + ' seconds'
    casts = p is not None and (c['func'] == 15 or sid in S.CHANCE_TO_CAST or sid == S.CHARGES)
    if casts and (not data.skill_names.get(p >> 6) or (p >> 6) in data.skill_hidden):
        return None   # chance de lancer (descfunc 15 : toutes, on Death Blow…) / charges d'une compétence sans nom
        # (effet interne, ✅ documentation, Black Razor) ou cachée dans l'infobulle des objets (skills2.bin @0x31, ✅
        # documentation : Staff of Shadows, pas de « Chance to cast … Slayer »)
    if sid == S.CHARGES and p is not None:
        # « Level 10 Inner Fire (5/5 Charges) » : valeur = charges max × 256 + charges (✅ documentation : Malus Domestica)
        return f"{data.key('ModStre10b')} {p & 63} {data.skill(p >> 6)} " + s1.replace('%d', str(v & 255), 1).replace(
            '%d', str(v >> 8), 1)
    if '%d' in s1 or (p is not None and sid in S.CHANCE_TO_CAST):
        return stat_label(dict(s, desc=s1), data)           # texte avec valeurs intégrées (chance de lancer…)
    if c['func'] == 38:   # param sans rôle dans le texte (« Activation Frequency 15% »)
        return _fmt(c['func'], c['val'], s1, c['str2'], v)
    if p is not None:
        return f"{_num(1, v)} {stat_label(dict(s, desc=s1), data)}"   # +x à une classe / compétence
    txt = _fmt(c['func'], c['val'], s1, c['str2'], v, attr_num) or f'{_num(1, v)} {s1}'
    return txt + tr('tooltip.level1') if is_per_level(sid, data) and not char and attr_num is None else txt


def stat_lines(stats, data, char=None, ranges=None, prio=False, two_handed=True, per_level_rate=False, ranged=()):
    """Lignes (couleur, texte, plages) des stats telles que le jeu les affiche : tri par priorité décroissante,
    regroupements (attributs, dégâts élémentaires, poison), stats cachées omises, doublons fusionnés.
    char : personnage, pour les stats « par niveau » ((valeur × niveau) >> op_param, ✅ Shark niv. 15).
    ranges : stat_ranges(), pour ajouter « [min-max] » (vide sinon). prio : priorité en tête de chaque ligne.
    two_handed : objet à deux mains (dégâts plats en double : version deux mains affichée ; sinon une main).
    per_level_rate : sans personnage, stat « par niveau » affichée par niveau (« 0.125% … (Based on Character Level) »,
    ✅ documentation, The Xiphos) au lieu de sa valeur au niveau 1 suivie de « [level 1] ».
    ranged : stats tirées sur une plage (catalogue) : jamais regroupées avec d'autres, chacune étant tirée séparément
    (✅ documentation : Catechumen, 4 résistances « (11 to 20)% » et non « Elemental Resists »)."""
    stats = _merge_stats(stats)
    ids = {s['id']: s['value'] for s in stats}
    out, keys = [], []
    seq = -1   # rang de la stat en cours dans la liste (-1 : lignes regroupées)

    def push(line, sid, sub=0):
        """Ligne et sa clé de tri : priorité décroissante, puis n° de stat croissant, puis ordre inverse de la liste
        (✅ documentation : chances de lancer de même stat, Astral Blade, Qarak's Will, Eternal Vigil ; Movement Speed
        avant la chance de lancer de même priorité, Feltongue) ; sub : ordre des lignes d'un même texte."""
        out.append(line)
        keys.append((-line[0], sid, -seq, sub))

    def add(sid, text, sids=None, conv=None, param=None):
        col = data.isc[sid]['color'] or BLUE
        # texte de la stat sur plusieurs lignes : de bas en haut, comme le jeu (✅ documentation : Adjudicator, « Holy… » /
        # « Unholy… » / « Nephalem… ») ; pas les noms de compétence sur deux lignes (« Chillstring\nGematria », non vérifié)
        if '\n' in text and '\n' in (data.isc[sid]['pos'] or '') + (data.isc[sid]['neg'] or ''):
            for sub, part in enumerate(reversed(text.split('\n'))):
                push((data.isc[sid]['prio'], col, part, [], []), sid, sub)
            return
        inline, below = range_segs(sids or [range_key(sid, param)], ranges, data, char, conv, col, is_percent(sid, data))
        push((data.isc[sid]['prio'], col, text, inline, below), sid)

    done = _grouped_lines(ids, data, add, two_handed, ranged)
    for seq, s in enumerate(stats):
        sid, v, c = s['id'], s['value'], data.isc[s['id']]
        if sid in done:
            continue
        # groupe de stats égales (ex. « +x to all Attributes ») : une seule ligne
        grp = data.stat_group[sid]   # stats du même groupe d'affichage (vide : pas de groupe)
        if len(grp) > 1 and all(x in ids and ids[x] == v and x not in ranged for x in grp):
            txt = _fmt(c['gfunc'], c['gval'], c['gpos'] if v >= 0 else c['gneg'], c['gstr2'], v)
            if txt:
                done.update(grp)
                add(sid, txt, [sid])
                continue
        # pas de done.add(sid) : une autre stat de même numéro et d'autre param (ex. « +x to <compétence> » pour
        # deux compétences, ✅ Jeweled Crown : Psionic Storm et Psicrown) doit aussi s'afficher
        s1 = c['pos'] if v >= 0 else c['neg']
        if stat_hidden(sid, data, v):
            continue
        attr_num = None
        if per_level_rate and not char and is_per_level(sid, data):   # valeur par niveau (voir la docstring)
            attr_num = _num_rate(c['func'], v / (1 << c['op_param']))
        v = per_level(sid, v, data, char)
        p = s['param']
        # stat proportionnelle à un attribut (✅ stat 442 : (valeur × Force) >> 8) : sans personnage, valeur par point
        # (documentation : 12 -> 0.046875%)
        if c['op'] in (2, 4, 5) and c['op_base'] in ATTR_KEYS:
            if char:
                v = (v * char[ATTR_KEYS[c['op_base']]]) >> c['op_param']
            else:
                # nombre exact (✅ documentation : Shroud Royal « 0.01171875% »)
                attr_num = f"{v / (1 << c['op_param']):.10g}" + ('%' if '%' in (_num(c['func'], 1) or '') else '')
        if is_innate_damage(sid, data):
            push(_innate_damage_line(c, v, p, s1, data, char), sid)
        elif c['func'] in (31, 34) and p is not None:
            for sub, line in enumerate(_skill_text_lines(c, sid, p, data, v)):
                push(line, sid, sub)
        else:
            txt = _stat_text(s, c, v, p, s1, data, char, attr_num)
            if txt is not None:
                add(sid, txt, param=p)
    seen, res = set(), []   # tri (push), textes en double retirés
    for _, (pr, col, t, inline, below) in sorted(zip(keys, out), key=lambda x: x[0]):
        if t not in seen:
            seen.add(t)
            res.append((pr, col, t, inline, below) if prio else (col, t, inline, below))
    return res
