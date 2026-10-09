"""Compétences données par un objet (sorts, effets passifs) et leur explication, sans interface (testable seul).

skill_refs : compétences citées par les stats d'un objet (« +x to <compétence> », chances de lancer, charges, aura),
avec le niveau donné ; en option, celles que l'objet modifie sans en donner de niveau (mentions : temps de recharge,
stat cachée liée à un texte d'effet, stat propre à une compétence). skill_tooltip : explication d'une compétence comme l'infobulle du jeu : nom, description, niveau
donné par l'objet, puis ses lignes chiffrées calculées pour ce niveau (mxl_skill_calc : valeurs qui ne dépendent que du
niveau ; les autres lignes ne sont pas affichées).
Affichage au survol : mxl_skill_view.
"""
import stat_ids as S
from mxl_data import strip_colors
from mxl_skill_calc import skill_calc, Grey
from i18n import tr
from mxl_theme import WHITE, GREY, GAME_COLORS

AURA = 151   # aura donnée par l'objet (param = compétence, valeur = niveau)
COOLDOWN_REDUCTION = 309   # « <compétence> Cooldown Reduced by x » (descfunc 33, param = compétence)
# stats cachées (descfunc 0, param = compétence) qui accompagnent un texte d'effet propre à l'objet (stat 375 et
# voisines) : la compétence modifiée (✅ Vision of the Furies : 383 Fire Elementals, « Fire Elementals: cooldown
# reduced by 10% » ; Soulmender : 399 Veil King ; Back To The Abyss : 397 / 399 Night Hawks)
HIDDEN_SKILL_STATS = (180, 383, 393, 396, 397, 399)
# stats propres à une compétence, nommée dans leur libellé (« Bonus Damage to Bloodlust ») : la compétence que les
# objets désignent ailleurs (« +x to Bloodlust » : 500 et non ses copies 1025 / 1858, toutes lisent ces stats)
SKILL_OWN_STATS = {279: 1204,                  # Lion Stance Damage Bonus
                   380: 500, 381: 500,         # (Elemental) Damage to Bloodlust
                   387: 435, 388: 435, 389: 435,   # Damage / Elemental Damage / Duration Bonus to Mark of the Wild
                   446: 1216,                  # Damage to Protector Spirit
                   468: 1486,                  # Damage to Vessel of Retribution
                   481: 1231}                  # to Runemaster Defense Bonus


def skill_refs(lo, hi, data, mentions=False):
    """{nom affiché: (n° de compétence, niveau minimal, niveau maximal)} des compétences nommées données par des stats
    ({id, param, value}) à leur valeur minimale (lo) et maximale (hi ; les mêmes listes pour un objet réel) :
    « +x to <compétence> » (stats 97 / 107 : param = compétence, valeur = niveau), chances de lancer et charges
    (param = compétence × 64 + niveau), aura (stat 151).
    mentions : aussi les compétences que l'objet modifie sans en donner de niveau (skill_mentions), niveaux None."""
    out = skill_mentions(lo, data) if mentions else {}
    for a, b in zip(lo, hi):
        sid, p = a['id'], a.get('param')
        if p is None or sid not in data.isc:
            continue
        if sid in (S.SINGLE_SKILL, S.SINGLE_SKILL_2, AURA):
            skill, levels = p, (a['value'], b['value'])
        elif data.isc[sid]['func'] == 15 or sid in S.CHANCE_TO_CAST or sid == S.CHARGES:
            skill, levels = p >> 6, (p & 63, b['param'] & 63)
        else:
            continue
        name = data.skill_names.get(skill)
        if name and '\n' not in name:
            known = out.get(name)
            if known and known[1] is None:   # simple mention : le niveau donné l'emporte
                known = None
            levels = (min(levels), max(levels))
            out[name] = (skill, min(levels[0], known[1]) if known else levels[0], max(levels[1], known[2]) if known else levels[1])
    return out


def cast_only_skills(stats, data):
    """Noms des compétences que les stats donnent seulement par des chances de lancer (« x% Chance to cast level y
    <compétence> on … ») et / ou des charges (« Level x <compétence> (n/n Charges) ») : jamais payées en mana.
    Chance de lancer : lancée sans contrôle ni retrait de mana (D2Game.dll 0x6fd114f0 -> 0x6fcbfd00 avec son dernier
    paramètre à 1, qui saute 0x6fcbfd5a et le retrait 0x6fcbfe71). Charges : le retrait de mana de Median XL
    (D2Sigma.dll 0x100a1c20) lit l'objet porteur de la compétence (+0x34, D2Common.dll 10304 ; −1 sans objet) et retire
    alors une charge (stat 204, D2Game.dll 0x6fcbf4a0) au lieu de la mana. Une compétence aussi donnée par « +x to » ou
    une aura n'en fait pas partie : le personnage peut la lancer lui-même."""
    cast, other = set(), set()
    for s in stats:
        sid, p = s['id'], s.get('param')
        if p is None or sid not in data.isc:
            continue
        if sid == S.CHARGES or data.isc[sid]['func'] == 15 or sid in S.CHANCE_TO_CAST:
            cast.add(data.skill_names.get(p >> 6))
        elif sid in (S.SINGLE_SKILL, S.SINGLE_SKILL_2, AURA):
            other.add(data.skill_names.get(p))
    return {n for n in cast - other if n}


def skill_mentions(stats, data):
    """{nom affiché: (n° de compétence, None, None)} des compétences que des stats modifient sans en donner de
    niveau : temps de recharge réduit (stat 309), stat cachée liée à un texte d'effet (HIDDEN_SKILL_STATS), stat propre
    à une compétence (SKILL_OWN_STATS). Le premier nom trouvé l'emporte (noms en double : Night Hawks 1396 / 2943)."""
    out = {}
    for s in stats:
        sid = s['id']
        if sid == COOLDOWN_REDUCTION or sid in HIDDEN_SKILL_STATS:
            skill = s.get('param')
        else:
            skill = SKILL_OWN_STATS.get(sid)
        name = data.skill_names.get(skill) if skill is not None else None
        if name and '\n' not in name:
            out.setdefault(name, (skill, None, None))
    return out


def game_colors(texts, grey=()):
    """Couleurs des lignes comme le jeu les dessine (D2Win.dll 0x6f8f2940) : texts (affichés de haut en bas, une ligne de
    texte multiple s'affichant de bas en haut) forment un seul tampon dessiné de bas en haut ; un code ÿc + caractère
    change la couleur courante, qui continue sur les lignes au-dessus jusqu'au code suivant (blanc au départ ; code
    invalide : blanc). Les textes d'indices grey (valeurs non calculées) restent en gris, sans couper la couleur courante.
    Retourne les lignes de haut en bas, chacune en morceaux [(couleur, texte)]."""
    import re
    color, out = WHITE, []
    for i in reversed(range(len(texts))):
        for part in texts[i].split('\n'):   # ordre du tampon : de bas en haut
            segments = []
            for token in re.split('(ÿc.)', part):
                if token.startswith('ÿc') and len(token) == 3:
                    code = token[2]
                    color = code if 0 <= ord(code) - ord('0') < 13 and code in GAME_COLORS else WHITE
                elif token:
                    segments.append([GREY if i in grey else color, token])
            if segments:
                segments[0][1] = segments[0][1].lstrip()
                segments[-1][1] = segments[-1][1].rstrip()
            segments = [tuple(s) for s in segments if s[1]] or [(GREY if i in grey else color, '')]
            out.append(segments)
    return out[::-1]


def skill_tooltip(skill, lo, hi, data, char=None, segments=False, mana=True):
    """Lignes [(couleur, texte)] de l'explication d'une compétence, dans la forme de l'infobulle du jeu : nom,
    description (une ou plusieurs lignes), ligne vide, « Current Skill Level: n » (plage « a to b » dans le catalogue),
    puis ses lignes chiffrées (mxl_skill_calc) : lignes « dsc2 » (« item granted passive skill »), puis celles
    du niveau actuel et le coût en mana. Une ligne de texte multiple s'affiche de bas en haut, comme dans le jeu. Sans
    valeur non calculée est en gris : « … varies by character » (sans personnage de référence) ou « … not calculated »
    (avec), ou une note grise sous « Current Skill Level » (« (values depend on character) », « (some values not
    calculated) »).
    Couleurs des lignes chiffrées : celles des codes du jeu dans leurs textes (game_colors), « Current Skill Level » et
    ce qui est au-dessus en blanc (✅ captures d'Ignis Fatuus : « item granted passive skill » en bleu, et de Blood
    Skeleton : lignes dsc2 sans code en blanc).
    char : personnage de référence (mxl_save.load_character) ou None : niveau, points investis (mxl_skill_calc).
    segments : lignes en morceaux de couleurs [[(couleur, texte)…]] (une ligne peut changer de couleur) ; sinon
    [(couleur du début, texte)]."""
    lines = [[(WHITE, data.skill_names.get(skill) or f'#{skill}')]]
    # description : texte de plusieurs lignes stocké de bas en haut, comme le jeu le dessine (« of one of your
    # creatures\nrelinquishes control » s'affiche « relinquishes control » au-dessus)
    lines += [[(WHITE, strip_colors(part).strip())] for part in reversed((data.skill_desc.get(skill) or '').split('\n'))
              if strip_colors(part).strip()]
    level = str(lo) if lo == hi else f'{lo} to {hi}'
    lines += [[(WHITE, '')], [(WHITE, data.key('StrSkill2') + level)]]
    calc = skill_calc(data)
    groups = calc.grouped_lines(skill, lo, hi, char, colors=True, mana=mana)
    if not groups and not data.skill_desc.get(skill):   # compétence sans fiche dans le jeu (Thunder Wave…)
        # ce que ses données disent quand même : tir de projectiles (Arrow) ou bonus temporaire (Celerity) vérifiés,
        # sinon part des dégâts de l'arme
        shots = (calc.shot_lines(skill, lo, hi, char) or calc.buff_lines(skill, lo, hi, char)
                 or calc.heal_lines(skill, lo, hi, char) or calc.spin_lines(skill, lo, hi, char)
                 or calc.nova_lines(skill, lo, hi, char) or calc.curse_lines(skill, lo, hi, char)
                 or calc.ring_chain_lines(skill, lo, hi, char) or calc.turret_lines(skill, lo, hi, char)
                 or calc.delayed_ring_lines(skill, lo, hi, char) or calc.fire_ground_lines(skill, lo, hi, char)
                 or calc.shatter_lines(skill, lo, hi, char) or calc.ring_burst_lines(skill, lo, hi, char))
        wdm = calc.weapon_damage(skill)
        found = shots or ([wdm] if wdm else [])
        groups = ([('desc', found)] if found else []) + [('note', [Grey(tr('skill.no_details'))])]
    texts = [t for group, ts in groups for t in ts]
    lines += game_colors(texts, grey={i for i, t in enumerate(texts) if isinstance(t, Grey)})
    if segments:
        return lines
    return [(line[0][0], ''.join(t for _, t in line)) for line in lines]
