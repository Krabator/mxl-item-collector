"""Explication des compétences : mise en forme des lignes, comme l'infobulle du jeu.

Chaque ligne de l'explication (skilldesc.bin) a un format, deux textes et deux formules. La table FORMATS associe à
chaque format reconnu son rendu (aiguillage de D2Client.dll 0x6fae16c0 pour 1 à 75, D2Sigma.dll 0x100a90d8 pour 76 et
77) et le libellé de sa ligne grise quand une valeur est inconnue (placeholder). Ajouter un format = une entrée dans
FORMATS. Textes avec leurs codes couleur du jeu (ÿc), retirés sauf pour l'infobulle (grouped_lines(colors=True)).
Fonctions qui reçoivent le calculateur (calc : mxl_skill_formula.FormulaEngine).
"""
import re, struct
from i18n import tr
from mxl_data import strip_colors
from mxl_skill_data import (Grey, Unsupported, Record, PoolProbe, NO_CALC, SKILLDESC_LINES, SKILLDESC_TEXT_A, SKILLDESC_TEXT_B,
                            SKILLDESC_CALC_A, SKILLDESC_CALC_B, SKILLDESC_STRMANA, SKILL_DESC, SKILL_ELEM_TYPE,
                            DESC_GROUP, DSC2_GROUP, ELEMENT_LABELS, LENGTH_LABELS, STR_SECOND, STR_SECONDS, STR_OVER,
                            STR_YARD, STR_YARDS, STR_WEAPON_DAMAGE, STR_PHYSICAL_DAMAGE, STR_TO_ATTACK_RATING,
                            STR_AVERAGE, STR_PER_SECOND, FRAMES_PER_SECOND, POOL_STATS, POOL_SAMPLES, SKILL_MANA_SHIFT,
                            SKILL_CALCS, SKILL_SRV_DO, SKILL_SRV_MISSILE_A, SRV_DO_SHOOT, MISSILE_SRC_DAMAGE,
                            SKILL_SRC_DAMAGE, SKILL_MIN_DAM, SKILL_MAX_DAM, SRV_DO_BUFF, SRV_DO_GIFT, SKILL_AURA_LEN,
                            SKILL_AURA_STATS, SKILL_AURA_CALCS, NO_STAT, SRV_DO_PULSE, STAT_LIFE_REGEN,
                            SRV_DO_LAUNCH, MISSILE_SRV_MOVE, SRV_MOVE_SPIN, MISSILE_SUBMISSILE, MISSILE_PARAM1,
                            MISSILE_RANGE, MISSILE_RANGE_LEV, SRV_DO_NOVA, NOVA_COUNT, SRV_DO_CURSE,
                            SKILL_AURA_RANGE_CALC, STAT_TOTAL_DEFENSE_PCT, MISSILE_SRV_HIT, SRV_HIT_RING,
                            MISSILE_HIT_SUBMISSILE, MISSILE_HIT_PARAM1, DIRECTIONS, SRV_HIT_RELAY, SKILL_SRV_MISSILE,
                            MISSILE_COLLIDE, MISSILE_SRV_DMG, SRV_DMG_CONVERT, MISSILE_DMG_CALC, MISSILE_ELEM,
                            SRV_HIT_AREA, MISSILE_HIT_CALC, SRV_HIT_SEEK, SRV_DO_PLACE)
import mxl_skill_mechanics as M


# ---------- textes et valeurs ----------
def text(calc, i):
    """Texte d'une ligne avec ses codes couleur du jeu (ÿc + caractère) ; '' si absent."""
    v = calc.data.strings.get(i) if 0 < i < 65535 else None
    t = v[1] if v else ''
    return '' if not strip_colors(t) or 'BUFFALO' in t else t


def desc_row(calc, skill):
    """Ligne de skilldesc.bin de la compétence, ou None."""
    k = calc.rec(skill).u16(SKILL_DESC)
    return calc.descs[k] if 0 < k < len(calc.descs) else None


def values(vs, sign=False):
    """Valeur au niveau le plus bas et au plus haut : « a », ou « a to b » si elles diffèrent."""
    f = (lambda v: f'{v:+d}') if sign else str
    a, b = (f(v) if isinstance(v, int) else v for v in vs)
    return a if a == b else f'{a} to {b}'


def mana_text(cost, decimal=True):
    """Coût en mana (256es) comme le jeu (D2Client.dll 0x6fadf7d0) : partie entière, puis une décimale tronquée si
    elle n'est pas nulle (« 8.7 ») ; decimal faux : entier seul (tronqué) ; None si rien à écrire (nul)."""
    whole, frac = cost >> 8, ((cost & 0xFF) * 10) >> 8
    if not decimal:
        return str(whole) if whole else None
    if not whole and not frac:
        return None
    return f'{whole}.{frac}' if frac else str(whole)


def mana_line(calc, skill, lo, hi, char, strmana):
    """Ligne de format 77 (Median XL, D2Sigma.dll 0x100a8cf0, sans charges) : texte du coût de la compétence et coût
    en mana (mxl_skill_mechanics.mana) ; rien si les formules de mana sont nulles ; entier (tronqué) si manashift vaut
    8, si le mana par niveau décalé dépasse 1 ou si le coût dépasse 25, sinon une décimale (mana_text)."""
    texts = []
    for lvl in (lo, hi):
        base, per = M.mana_parts(calc, skill, lvl, char)
        if not base and not per:
            return None
        shift = calc.rec(skill).u8(SKILL_MANA_SHIFT)
        cost = M.mana(calc, skill, lvl, char)
        txt = mana_text(cost, decimal=not (shift == 8 or (per << shift) > 0x100 or cost > 0x1900))
        if txt is None:
            return None
        texts.append(txt)
    return strmana + values(texts) if strmana else None


def seconds(calc, frames):
    """Durée en frames comme le jeu (D2Client.dll 0x6fade060) : « 2 seconds », « 1 second », « 2.4 seconds » (une
    décimale, tronquée) ; None si elle est nulle."""
    secs, frac = frames // FRAMES_PER_SECOND, (frames % FRAMES_PER_SECOND) * 10 // FRAMES_PER_SECOND
    if not secs and not frac:
        return None
    unit = calc.data.s(STR_SECOND if secs == 1 and not frac else STR_SECONDS)
    return (f'{secs}.{frac}' if frac else str(secs)) + unit


def yards(calc, v):
    """Rayon en yards (format 19, D2Client.dll 0x6fadf430) : v × 20 / 3 en dixièmes, au moins 1 yard ;
    « yard » seulement pour une partie entière de 1."""
    tenths = int(v * 20 / 3)
    whole, frac = int(tenths / 10), tenths - 10 * int(tenths / 10)
    whole = max(whole, 1)
    return (f'{whole}.{frac}' if frac else str(whole)) + calc.data.s(STR_YARD if whole == 1 else STR_YARDS)


def weapon_damage(calc, skill):
    """« 112% Weapon Damage » : part des dégâts de l'arme (wdm), ou None si elle est nulle — pour une compétence sans
    fiche dans le jeu (Thunder Wave), même valeur que la ligne des compétences décrites."""
    pct = M.weapon_damage_pct(calc, skill)
    return f'{pct}{calc.data.s(STR_WEAPON_DAMAGE)}' if pct else None


# compétences sans fiche dans le jeu dont le tir de projectiles a été vérifié une à une : n° -> (texte du verbe,
# projectile au singulier, au pluriel) ; vérifiées le 02/10 (D2Game.dll 0x6fc6d420) : Arrow (clc1 = 1 flèche,
# projectile 0 « arrow » à 128 / 128 des dégâts de l'arme), Knife Throw (clc1 = 1, projectile 36 à 128 / 128) ;
# aucune n'a de dégâts propres, niveau sans effet ; Thunder Hammer (clc1 = 1, projectile 774 dont l'explosion 328 est
# visuelle ; dégâts physiques de la compétence, 60 % des dégâts de l'arme : part de la compétence), Javelin (clc1 = 1,
# projectile 1 à 128 / 128), Thunder Wave (comme Thunder Hammer, mais clc1 = 1 + niveau marteaux, répartis par le
# tir, et 144 / 128 des dégâts de l'arme)
SHOT_SKILLS = {609: ('skill.fires', 'Arrow', 'Arrows'), 591: ('skill.throws', 'Knife', 'Knives'),
               605: ('skill.throws', 'Hammer', 'Hammers'), 588: ('skill.throws', 'Javelin', 'Javelins'),
               606: ('skill.throws', 'Hammer', 'Hammers')}


def shot_lines(calc, skill, lo, hi, char=None):
    """Lignes d'une compétence sans fiche qui tire des projectiles (srvdo 8), si elle est dans SHOT_SKILLS :
    « Fires 1 Arrow », « Throws 1 Knife » (nombre = clc1, du niveau lo au niveau hi), dégâts physiques propres de la
    compétence s'il y en a (« Physical Damage: », comme la ligne de format 9 ; sans personnage : « varies by
    character »), puis la part des dégâts de l'arme portée par le projectile : celle de la compétence (skills.bin
    @0x1A5) si elle n'est pas nulle, sinon celle du projectile (missiles.bin @0x12D), sinon 100 % (D2Sigma.dll
    0x1008a696) ; None si la compétence n'est pas dans SHOT_SKILLS."""
    r = calc.rec(skill)
    if skill not in SHOT_SKILLS or r.u16(SKILL_SRV_DO) != SRV_DO_SHOOT:
        return None
    if char is not None and not hasattr(char, 'skill_level'):   # sauvegarde lue : ses totaux (mxl_char_stats)
        from mxl_char_stats import character_stats
        char = character_stats(char, calc.data)
    counts = sorted({calc.skill_calc(skill, r.u32(SKILL_CALCS), lvl, char) for lvl in (lo, hi)})
    verb, one, many = SHOT_SKILLS[skill]
    n = str(counts[0]) if len(counts) == 1 else f'{counts[0]} to {counts[1]}'
    out = [tr(verb, n=n, what=one if counts == [1] else many)]
    if r.i32(SKILL_MIN_DAM) or r.i32(SKILL_MAX_DAM):   # dégâts physiques propres, ajoutés au projectile
        try:
            line = physical_line(calc, skill, lo, hi, char, '', None, None)
        except Unsupported:
            line = Grey(calc.data.s(STR_PHYSICAL_DAMAGE) + tr('skill.varies' if char is None else 'skill.not_calculated'))
        if line:
            out.append(line)
    src = r.u8(SKILL_SRC_DAMAGE) or calc.missile_rec(r.u16(SKILL_SRV_MISSILE_A)).u8(MISSILE_SRC_DAMAGE) or 128
    out.append(f'{M.muldiv(src, 100, 128)}{calc.data.s(STR_WEAPON_DAMAGE)}')
    return out


# compétences sans fiche dans le jeu dont le bonus temporaire (srvdo 25) a été vérifié une à une ; Celerity (✅ 02/10 :
# état 219, durée ln12 × (100 + stat 409 « Skill Duration ») / 100 = 250 images, Movement Speed min(ln34, 75),
# Cannot Be Frozen) ; Gift of Celerity (✅ 02/10 : srvdo 68, mêmes état, stats et durée, offerts aussi à l'allié
# touché par le projectile 817) ; Gift of Inner Fire (✅ 02/10 : srvdo 68, état 193, durée (50 − dm12) × (100 + Skill
# Duration) / 100 images, Life Regenerated = vie max / (50 − dm12) : toute la vie maximale sur la durée de base)
BUFF_SKILLS = {701: SRV_DO_BUFF, 704: SRV_DO_GIFT, 705: SRV_DO_GIFT}


def _heal_over_time(calc, skill, off, lvl, char):
    """Soin d'un bonus temporaire dont la stat est Life Regenerated (256es de vie par image) : (vie rendue, % de la
    vie maximale, durée en images), sur la durée de l'état ; sans personnage, avec un personnage témoin (vie 100, sans
    bonus de durée) : vie None."""
    from mxl_char_stats import CharacterStats
    r = calc.rec(skill)
    who = char if char is not None else CharacterStats(
        dict(cls=0, level=1, skills={}, items=[], base_stats={7: 100 << 8, 9: 0}), calc.data)
    frames = calc.skill_calc(skill, r.u32(SKILL_AURA_LEN), lvl, who)
    healed = calc.skill_calc(skill, off, lvl, who) * frames / 256
    pct = int(healed * 100 / who.max_life() + 0.5) if who.max_life() else 0
    return (int(healed) if char is not None else None), pct, frames


def _span(texts):
    return texts[0] if texts[0] == texts[-1] else f'{texts[0]} to {texts[-1]}'


def _span_seconds(calc, frames):
    """Durées (en images) du niveau bas au niveau haut : « 10 seconds », « 1.2 to 3.6 seconds »."""
    texts = [seconds(calc, f) for f in frames]
    if not texts[0] or texts[0] == texts[-1]:
        return texts[0]
    return f'{texts[0].split()[0]} to {texts[-1]}'


def buff_lines(calc, skill, lo, hi, char=None):
    """Lignes d'une compétence sans fiche qui pose un bonus temporaire (srvdo 25 ; srvdo 68 : aussi offert à un allié,
    ligne « On you, and on an ally hit by the projectile sent at the target: » en tête), si elle est dans BUFF_SKILLS : ses
    stats (aurastat1-6) écrites comme sur un objet, du niveau lo au niveau hi (« +(30 to 75)% Movement Speed »), puis
    « Duration: 10 seconds » (formule @0x60, en images ; avec la stat 409 du personnage : sans lui, « varies by
    character ») ; None sinon."""
    from mxl_stat_text import stat_lines
    from mxl_catalog_tooltip import merge_range_text
    r = calc.rec(skill)
    if skill not in BUFF_SKILLS or r.u16(SKILL_SRV_DO) != BUFF_SKILLS[skill]:
        return None
    if char is not None and not hasattr(char, 'skill_level'):
        from mxl_char_stats import character_stats
        char = character_stats(char, calc.data)
    out = [tr('skill.gift')] if BUFF_SKILLS[skill] == SRV_DO_GIFT else []
    healing = False
    for stat, off in zip(r.u16s(SKILL_AURA_STATS, 6), r.u32s(SKILL_AURA_CALCS, 6)):
        if stat == NO_STAT or off == NO_CALC:
            continue
        if stat == STAT_LIFE_REGEN:   # soin sur la durée de l'état : total plutôt que régénération par image
            heals = [_heal_over_time(calc, skill, off, lvl, char) for lvl in (lo, hi)]
            pct = _span([str(h[1]) for h in heals])
            span = _span_seconds(calc, [h[2] for h in heals])
            if heals[0][0] is None:
                out.append(tr('skill.heals_over_pct', pct=pct, d=span))
            else:
                out.append(tr('skill.heals_over', life=_span([str(h[0]) for h in heals]), pct=pct, d=span))
            healing = True
            continue
        try:
            texts = [stat_lines([{'id': stat, 'param': None, 'value': calc.skill_calc(skill, off, lvl, char)}],
                                calc.data) for lvl in (lo, hi)]
        except Unsupported:
            continue
        if texts[0] and texts[1]:
            out.append(merge_range_text(texts[0][0][1], texts[1][0][1]))
    if healing:   # la durée est dans la ligne du soin
        return out
    try:
        frames = [calc.skill_calc(skill, r.u32(SKILL_AURA_LEN), lvl, char) for lvl in (lo, hi)]
        shown = _span_seconds(calc, frames)
        if shown:
            out.append(tr('skill.duration', v=shown))
    except Unsupported:
        out.append(Grey(tr('skill.duration', v='') + tr('skill.varies' if char is None else 'skill.not_calculated')))
    return out


# compétences sans fiche dans le jeu qui soignent d'un coup, vérifiées une à une : n° -> % de la vie maximale au
# niveau lvl (au repos) ; Life Spark (✅ 02/10 : srvdo 18, état 444 pendant 1 image avec Life Regenerated = vie max ×
# niveau / 100 × clc1 de la compétence interne 2908 / 100 ; clc1 = 100 sauf pendant l'état 883, pénalité de 3 % par
# 1000 de vie maximale) : rend niveau % de la vie maximale
HEAL_SKILLS = {579: lambda lvl: lvl}


def heal_lines(calc, skill, lo, hi, char=None):
    """Lignes d'une compétence sans fiche qui soigne d'un coup (srvdo 18 : état d'une image avec régénération de
    vie, stat 74 en 256es de vie par image), si elle est dans HEAL_SKILLS : sans personnage « Heals (3 to 10)% of
    Maximum Life » ; avec, « Heals 26 to 87 Life (3 to 10% of Maximum Life) » (formule de la stat évaluée pour lui,
    ÷ 256) ; None sinon."""
    r = calc.rec(skill)
    if skill not in HEAL_SKILLS or r.u16(SKILL_SRV_DO) != SRV_DO_PULSE:
        return None
    pct = _span([str(HEAL_SKILLS[skill](lvl)) for lvl in (lo, hi)])
    off = next((o for st, o in zip(r.u16s(SKILL_AURA_STATS, 6), r.u32s(SKILL_AURA_CALCS, 6)) if st == STAT_LIFE_REGEN), None)
    if char is not None and off is not None:
        if not hasattr(char, 'skill_level'):
            from mxl_char_stats import character_stats
            char = character_stats(char, calc.data)
        try:
            life = _span([str(calc.skill_calc(skill, off, lvl, char) // 256) for lvl in (lo, hi)])
            return [tr('skill.heals_life', life=life, pct=pct)]
        except Unsupported:
            pass
    return [tr('skill.heals_pct', pct=pct if ' to ' not in pct else f'({pct})')]


# compétences sans fiche dans le jeu qui lancent un projectile tournant (srvdo 28 + srvmove 15), vérifiées une à
# une : n° -> (nom du sous-projectile, au pluriel) ; Flurry of Javelins (✅ 02/10 : lanceur 840, durée 20 + 3 × niveau
# images, un javelot 931 toutes les 3 images, direction + 19/64 à chaque fois, 128 / 128 des dégâts de l'arme ;
# explosion 966 visuelle)
SPIN_SKILLS = {490: ('Javelin', 'Javelins')}


def spin_lines(calc, skill, lo, hi, char=None):
    """Lignes d'une compétence sans fiche qui lance un projectile tournant (srvdo 28, srvmove 15), si elle est dans
    SPIN_SKILLS : « Throws 1 Javelin every 0.12 seconds, in a spiral (11 to 31 Javelins) », « Duration: 1.2 to 3.6 seconds » (durée de vie
    du lanceur) et la part des dégâts de l'arme de chaque sous-projectile (celle de la compétence, sinon la sienne,
    sinon 100 %) ; None sinon."""
    r = calc.rec(skill)
    if skill not in SPIN_SKILLS or r.u16(SKILL_SRV_DO) != SRV_DO_LAUNCH:
        return None
    launcher = calc.missile_rec(r.u16(SKILL_SRV_MISSILE_A))
    if launcher.u16(MISSILE_SRV_MOVE) != SRV_MOVE_SPIN:
        return None
    every = max(launcher.i32(MISSILE_PARAM1), 1)
    sub = calc.missile_rec(launcher.u16(MISSILE_SUBMISSILE))
    one, many = SPIN_SKILLS[skill]
    life = [launcher.i16(MISSILE_RANGE) + launcher.i16(MISSILE_RANGE_LEV) * lvl for lvl in (lo, hi)]
    # un sous-projectile dès l'image 0 puis toutes les param1 images tant que la durée de vie court (images 0 à
    # durée − 1) : durée / param1 arrondi au supérieur (image 0 déduite de la chaîne de Corrupted Vines)
    counts = [-(-f // every) for f in life]
    out = [tr('skill.spins', what=one, s=f'{every * 100 // FRAMES_PER_SECOND / 100:g}',
              n=_span([str(n) for n in counts]), many=many)]
    out.append(tr('skill.duration', v=_span_seconds(calc, life)))
    src = r.u8(SKILL_SRC_DAMAGE) or sub.u8(MISSILE_SRC_DAMAGE) or 128
    out.append(f'{M.muldiv(src, 100, 128)}{calc.data.s(STR_WEAPON_DAMAGE)}')
    return out


# compétences sans fiche dans le jeu qui lancent une nova (srvdo 22), vérifiées une à une : n° -> (projectile au
# singulier, au pluriel) ; Javelin Nova (✅ 02/10 : 64 javelots 1701, vitesse et portée fixes, 96 / 128 des dégâts de
# l'arme ; niveau sans effet)
NOVA_SKILLS = {625: ('Javelin', 'Javelins')}


def nova_lines(calc, skill, lo, hi, char=None):
    """Lignes d'une compétence sans fiche qui lance une nova (srvdo 22), si elle est dans NOVA_SKILLS :
    « Throws 64 Javelins in a ring » puis la part des dégâts de l'arme de chaque projectile (celle de la compétence,
    sinon celle du projectile srvmissileA, sinon 100 %) ; None sinon."""
    r = calc.rec(skill)
    if skill not in NOVA_SKILLS or r.u16(SKILL_SRV_DO) != SRV_DO_NOVA:
        return None
    _, many = NOVA_SKILLS[skill]
    out = [tr('skill.nova', n=NOVA_COUNT, what=many)]
    src = r.u8(SKILL_SRC_DAMAGE) or calc.missile_rec(r.u16(SKILL_SRV_MISSILE_A)).u8(MISSILE_SRC_DAMAGE) or 128
    out.append(f'{M.muldiv(src, 100, 128)}{calc.data.s(STR_WEAPON_DAMAGE)}')
    return out


# compétences sans fiche dans le jeu qui maudissent (srvdo 30), vérifiées une à une ; Rust Storm (✅ 02/10 : rayon 20,
# 200 images × (100 + Skill Duration) / 100, −40 % de défense totale (stat 182, ✅ D2Common.dll 10672), −8 % de résistance
# physique), Amplify Damage (rayon 4, 200 images, −20 % de résistance physique)
CURSE_SKILLS = {638, 66}


def curse_lines(calc, skill, lo, hi, char=None):
    """Lignes d'une compétence sans fiche qui maudit les ennemis alentour (srvdo 30), si elle est dans CURSE_SKILLS :
    « Curses enemies within 13.3 yards » (rayon, formule @0x64 : yards du format 19), les stats posées sur eux (textes
    du jeu ; stat 182 : « Total Defense -40% »), « Duration: 8 seconds » (avec la stat 409 du personnage) ; None sinon."""
    from mxl_stat_text import stat_lines
    from mxl_catalog_tooltip import merge_range_text
    r = calc.rec(skill)
    if skill not in CURSE_SKILLS or r.u16(SKILL_SRV_DO) != SRV_DO_CURSE:
        return None
    if char is not None and not hasattr(char, 'skill_level'):
        from mxl_char_stats import character_stats
        char = character_stats(char, calc.data)
    out = []
    try:
        radius = [yards(calc, calc.skill_calc(skill, r.u32(SKILL_AURA_RANGE_CALC), lvl, char)) for lvl in (lo, hi)]
        out.append(tr('skill.curse', r=_span(radius)))
    except Unsupported:
        pass

    def text(stat, v):
        if stat == STAT_TOTAL_DEFENSE_PCT:
            return tr('skill.total_defense', v=v)
        lines = stat_lines([{'id': stat, 'param': None, 'value': v}], calc.data)
        return lines[0][1] if lines else None
    for stat, off in zip(r.u16s(SKILL_AURA_STATS, 6), r.u32s(SKILL_AURA_CALCS, 6)):
        if stat == NO_STAT or off == NO_CALC:
            continue
        try:
            texts = [text(stat, calc.skill_calc(skill, off, lvl, char)) for lvl in (lo, hi)]
        except Unsupported:
            continue
        if texts[0] and texts[1]:
            out.append(merge_range_text(texts[0], texts[1]))
    try:
        shown = _span_seconds(calc, [calc.skill_calc(skill, r.u32(SKILL_AURA_LEN), lvl, char) for lvl in (lo, hi)])
        if shown:
            out.append(tr('skill.duration', v=shown))
    except Unsupported:
        out.append(Grey(tr('skill.duration', v='') + tr('skill.varies' if char is None else 'skill.not_calculated')))
    return out


# compétences sans fiche dans le jeu qui posent une chaîne d'anneaux (srvdo 28 à la cible, lanceurs immobiles qui se
# relaient par le déplacement 15 et finissent par l'impact 29), vérifiées une à une : n° -> (projectile final au
# singulier, au pluriel) ; Corrupted Vines (✅ 02/10 : 3687 -> 3688 -> 3689 -> 3690, anneaux de 13, 10, 7 et 6 lianes
# 3691 ondulantes, 255 / 128 des dégâts de l'arme de la compétence ; création du suivant à l'image 0 : déduite de la
# chaîne, portées de 1 à 4 images)
RING_CHAIN_SKILLS = {567: ('Vine', 'Vines')}


def ring_chain_lines(calc, skill, lo, hi, char=None):
    """Lignes d'une compétence sans fiche qui pose une chaîne d'anneaux (srvdo 28, RING_CHAIN_SKILLS) : « Releases 4
    rings of Vines on the target: 13, 10, 7 and 6 (36 in all) » (anneaux lus dans la chaîne : 64 / hitpar1 arrondi au
    supérieur pour chaque projectile à impact 29 ; suivant = sous-projectile si déplacement 15), puis la part des dégâts
    de l'arme (celle de la compétence, sinon celle du projectile final, sinon 100 %) ; None sinon."""
    r = calc.rec(skill)
    if skill not in RING_CHAIN_SKILLS or r.u16(SKILL_SRV_DO) != SRV_DO_LAUNCH:
        return None
    rings, final, m, seen = [], None, r.u16(SKILL_SRV_MISSILE_A), set()
    while m not in seen and m < len(calc.missiles):
        seen.add(m)
        rec = calc.missile_rec(m)
        if rec.u16(MISSILE_SRV_HIT) == SRV_HIT_RING:
            step = max(rec.i32(MISSILE_HIT_PARAM1), 1)
            rings.append(-(-DIRECTIONS // step))
            final = rec.u16(MISSILE_HIT_SUBMISSILE)
        if rec.u16(MISSILE_SRV_MOVE) != SRV_MOVE_SPIN:
            break
        m = rec.u16(MISSILE_SUBMISSILE)
    if not rings:
        return None
    one, many = RING_CHAIN_SKILLS[skill]
    shown = ', '.join(map(str, rings[:-1])) + f' and {rings[-1]}' if len(rings) > 1 else str(rings[0])
    out = [tr('skill.rings', k=len(rings), what=many, n=shown, total=sum(rings))]
    src = r.u8(SKILL_SRC_DAMAGE) or (calc.missile_rec(final).u8(MISSILE_SRC_DAMAGE) if final is not None else 0) or 128
    out.append(f'{M.muldiv(src, 100, 128)}{calc.data.s(STR_WEAPON_DAMAGE)}')
    return out


# compétences sans fiche dans le jeu qui posent des tourniquets (chaîne de projectiles immobiles relayés par les
# impacts 29 / 36, dont certains tirent sans arrêt par le déplacement 15), vérifiées une à une ; Athulua's Wrath
# (✅ 02/10 : srvmissile 2132 sur le personnage -> 2124 -> 2125 -> 2126 -> 2130, tourniquets 2127, 2128, 2129, 2130 :
# un projectile 2131 par image, pendant 300 + 3 × niveau images ; part de l'arme de la compétence 78 / 128) ;
# Punisher Barrage (✅ 02/10 : tir srvdo 8 de clc1 = 1 tourniquet 2880 immobile, 1 projectile 2881 par image pendant
# 75 images, pivot de 19 ; 2881 sans part de l'arme : 100 %)
TURRET_SKILLS = {754, 448}


def _turrets(calc, start, lvl):
    """Tourniquets d'une chaîne de projectiles : [(durée de vie, intervalle, projectile tiré)] — un projectile à
    déplacement 15 qui tire plus d'une fois dans sa vie est un tourniquet ; sinon il crée une fois son sous-projectile ;
    les impacts 29 (anneau : 64 / hitpar1) et 36 (relais : 1) passent à leur sous-projectile d'impact."""
    out, todo, seen = [], [(start, 1)], set()
    while todo:
        m, n = todo.pop()
        if m >= len(calc.missiles) or (m, n) in seen:
            continue
        seen.add((m, n))
        rec = calc.missile_rec(m)
        if rec.u16(MISSILE_SRV_MOVE) == SRV_MOVE_SPIN:
            every = max(rec.i32(MISSILE_PARAM1), 1)
            life = rec.i16(MISSILE_RANGE) + rec.i16(MISSILE_RANGE_LEV) * lvl
            if every < life:
                out += [(life, every, rec.u16(MISSILE_SUBMISSILE))] * n
            else:
                todo.append((rec.u16(MISSILE_SUBMISSILE), n))
        hit = rec.u16(MISSILE_SRV_HIT)
        if hit == SRV_HIT_RING:
            todo.append((rec.u16(MISSILE_HIT_SUBMISSILE), n * -(-DIRECTIONS // max(rec.i32(MISSILE_HIT_PARAM1), 1))))
        elif hit == SRV_HIT_RELAY:
            todo.append((rec.u16(MISSILE_HIT_SUBMISSILE), n))
    return out


def turret_lines(calc, skill, lo, hi, char=None):
    """Lignes d'une compétence sans fiche qui pose des tourniquets (TURRET_SKILLS) : « Places 4 spinning turrets
    where you stand », « Each fires 1 projectile every 0.04 seconds for 12.1 seconds (1212 in all) » et la part des
    dégâts de l'arme des projectiles tirés (celle de la compétence, sinon la leur, sinon 100 %) ; None sinon."""
    r = calc.rec(skill)
    if skill not in TURRET_SKILLS:
        return None
    if r.u16(SKILL_SRV_DO) == SRV_DO_SHOOT:   # tir : clc1 projectiles srvmissileA
        start, shots = r.u16(SKILL_SRV_MISSILE_A), max(calc.skill_calc(skill, r.u32(SKILL_CALCS), lo, char), 1)
    else:   # pas de srvdo : le projectile srvmissile, un seul
        start, shots = r.u16(SKILL_SRV_MISSILE), 1
    per_level = [_turrets(calc, start, lvl) * shots for lvl in (lo, hi)]
    if not per_level[0]:
        return None
    turrets = per_level[0]
    every = turrets[0][1]
    life = _span_seconds(calc, [t[0][0] for t in per_level])
    total = _span([str(sum(-(-t[0] // t[1]) for t in ts)) for ts in per_level])
    s = f'{every * 100 // FRAMES_PER_SECOND / 100:g}'
    if len(turrets) == 1:
        out = [tr('skill.turret'), tr('skill.turret_fire_one', s=s, d=life, total=total)]
    else:
        out = [tr('skill.turrets', n=len(turrets)), tr('skill.turret_fire', s=s, d=life, total=total)]
    src = r.u8(SKILL_SRC_DAMAGE) or calc.missile_rec(turrets[0][2]).u8(MISSILE_SRC_DAMAGE) or 128
    out.append(f'{M.muldiv(src, 100, 128)}{calc.data.s(STR_WEAPON_DAMAGE)}')
    return out


# compétences sans fiche dans le jeu qui laissent un anneau à retardement (tir srvdo 8 d'un projectile immobile qui
# crée un projectile d'attente, lequel finit par l'impact 29 en anneau), vérifiées une à une ; Devastation (✅ 02/10 :
# 1951 sur le personnage -> 1955 (93 images) -> 64 projectiles de feu 1954 ; 1952 -> 16 projectiles 1953 sans
# collision, visuels ; 1954 : 128 / 128 des dégâts de l'arme, fonction de dégâts 1 : 100 % du physique en feu)
DELAYED_RING_SKILLS = {612}
ELEMENT_NAMES = {1: 'Fire', 2: 'Lightning', 3: 'Magic', 4: 'Cold', 5: 'Poison'}


def _miss_constant(calc, off):
    """Valeur d'une formule de misscode.bin qui n'est qu'une constante (7 / 8 / 9 + valeur, puis 0), sinon None."""
    code = getattr(calc, '_misscode', None)
    if code is None:   # misscode.bin : code des formules des projectiles, lu une fois
        import os
        with open(os.path.join(calc.data.folder, 'misscode.bin'), 'rb') as f:
            code = calc._misscode = f.read()
    if off >= len(code):
        return None
    size = {7: 1, 8: 2, 9: 4}.get(code[off])
    if size is None or off + 1 + size >= len(code) or code[off + 1 + size] != 0:
        return None
    return int.from_bytes(code[off + 1:off + 1 + size], 'little', signed=True)


def delayed_ring_lines(calc, skill, lo, hi, char=None):
    """Lignes d'une compétence sans fiche qui laisse un anneau à retardement (DELAYED_RING_SKILLS) : « After 3.7
    seconds, releases 64 projectiles in a ring where you stood », la part des dégâts de l'arme de ces projectiles (celle
    de la compétence, sinon la leur, sinon 100 %) et leur conversion (« 100% of Physical Damage converted to Fire ») ;
    None sinon."""
    r = calc.rec(skill)
    if skill not in DELAYED_RING_SKILLS or r.u16(SKILL_SRV_DO) != SRV_DO_SHOOT:
        return None
    first = calc.missile_rec(r.u16(SKILL_SRV_MISSILE_A))
    if first.u16(MISSILE_SRV_MOVE) != SRV_MOVE_SPIN:
        return None
    waiting = calc.missile_rec(first.u16(MISSILE_SUBMISSILE))
    if waiting.u16(MISSILE_SRV_HIT) != SRV_HIT_RING:
        return None
    final_id = waiting.u16(MISSILE_HIT_SUBMISSILE)
    final = calc.missile_rec(final_id)
    if not final.u8(MISSILE_COLLIDE):
        return None
    count = -(-DIRECTIONS // max(waiting.i32(MISSILE_HIT_PARAM1), 1))
    delay = _span_seconds(calc, [waiting.i16(MISSILE_RANGE) + waiting.i16(MISSILE_RANGE_LEV) * lvl for lvl in (lo, hi)])
    out = [tr('skill.delayed_ring', d=delay, n=count)]
    src = r.u8(SKILL_SRC_DAMAGE) or final.u8(MISSILE_SRC_DAMAGE) or 128
    out.append(f'{M.muldiv(src, 100, 128)}{calc.data.s(STR_WEAPON_DAMAGE)}')
    elem = ELEMENT_NAMES.get(final.u8(MISSILE_ELEM))
    if final.u16(MISSILE_SRV_DMG) == SRV_DMG_CONVERT and elem and final.u32(MISSILE_DMG_CALC) != NO_CALC:
        pct = _miss_constant(calc, final.u32(MISSILE_DMG_CALC))
        if pct is not None and pct > 0:
            out.append(tr('skill.converted', pct=min(pct, 100), elem=elem))
    return out


# compétences sans fiche dans le jeu qui embrasent le sol (srvdo 28 à la cible, impact 9 : une case de feu par
# sous-case du disque), vérifiées une à une ; Fire Splash (✅ 02/10 : projectile 717, rayon hitpar1 5 = 3.3 yards,
# cases 716 de 25 images (formule d'impact) ; dégâts de feu de la compétence par image, hitshift 0 : par seconde
# comme un mur de feu)
FIRE_GROUND_SKILLS = {489}


def fire_ground_lines(calc, skill, lo, hi, char=None):
    """Lignes d'une compétence sans fiche qui embrase le sol (FIRE_GROUND_SKILLS) : « Sets the ground ablaze within
    3.3 yards of the target for 1 second » (rayon hitpar1 en yards du format 19, durée = formule d'impact @0x88) puis
    les dégâts par seconde de chaque case (ligne de format 26 : dégâts élémentaires de la compétence par image × 25 /
    256 ; sans personnage, « varies by character ») ; None sinon."""
    r = calc.rec(skill)
    if skill not in FIRE_GROUND_SKILLS or r.u16(SKILL_SRV_DO) != SRV_DO_LAUNCH:
        return None
    first = calc.missile_rec(r.u16(SKILL_SRV_MISSILE_A))
    if first.u16(MISSILE_SRV_HIT) != SRV_HIT_AREA or first.i32(MISSILE_HIT_PARAM1) <= 0:
        return None
    patch_rec = calc.missile_rec(first.u16(MISSILE_HIT_SUBMISSILE))
    life = _miss_constant(calc, first.u32(MISSILE_HIT_CALC)) if first.u32(MISSILE_HIT_CALC) != NO_CALC else None
    if not life:
        life = patch_rec.i16(MISSILE_RANGE)
    out = [tr('skill.ablaze', r=yards(calc, first.i32(MISSILE_HIT_PARAM1)), d=seconds(calc, life))]
    if char is not None and not hasattr(char, 'skill_level'):
        from mxl_char_stats import character_stats
        char = character_stats(char, calc.data)
    try:
        line = damage_line(calc, 26, skill, lo, hi, char, '')
    except Unsupported:
        etype = r.u8(SKILL_ELEM_TYPE)
        label = ELEMENT_LABELS.get(etype)
        line = Grey(calc.data.s(STR_AVERAGE) + calc.data.s(label) + tr('skill.varies' if char is None else 'skill.not_calculated')) if label else None
    if line:
        out.append(line)
    return out


# compétences sans fiche dans le jeu dont le projectile éclate en fin de vie vers des ennemis proches (tir srvdo 8,
# projectile sans collision, impact 20), vérifiées une à une ; Shatterblade (✅ 02/10 : lame 2182, 50 images, éclate
# vers 1 ennemi (hitpar2) dans un rayon de 30 (20 yards) ; éclat 2183 à 48 / 128 des dégâts de l'arme)
SHATTER_SKILLS = {462}


def shatter_lines(calc, skill, lo, hi, char=None):
    """Lignes d'une compétence sans fiche dont le projectile éclate en fin de vie (SHATTER_SKILLS) : « Throws a blade
    that shatters after 2 seconds, sending 1 shard at an enemy within 20 yards » puis la part des dégâts de l'arme de
    l'éclat (celle de la compétence, sinon la sienne, sinon 100 %) ; None sinon."""
    r = calc.rec(skill)
    if skill not in SHATTER_SKILLS or r.u16(SKILL_SRV_DO) != SRV_DO_SHOOT:
        return None
    blade = calc.missile_rec(r.u16(SKILL_SRV_MISSILE_A))
    if blade.u16(MISSILE_SRV_HIT) != SRV_HIT_SEEK or blade.u8(MISSILE_COLLIDE) or blade.i32(MISSILE_HIT_PARAM1) <= 0:
        return None
    shard = calc.missile_rec(blade.u16(MISSILE_HIT_SUBMISSILE))
    life = _span_seconds(calc, [blade.i16(MISSILE_RANGE) + blade.i16(MISSILE_RANGE_LEV) * lvl for lvl in (lo, hi)])
    count = max(blade.i32(MISSILE_HIT_PARAM1 + 4), 1)
    out = [tr('skill.shatter' if count == 1 else 'skill.shatter_many', d=life, n=count,
              r=yards(calc, blade.i32(MISSILE_HIT_PARAM1)))]
    src = r.u8(SKILL_SRC_DAMAGE) or shard.u8(MISSILE_SRC_DAMAGE) or 128
    out.append(f'{M.muldiv(src, 100, 128)}{calc.data.s(STR_WEAPON_DAMAGE)}')
    return out


# compétences sans fiche dans le jeu qui libèrent des anneaux autour du lanceur après un délai (srvdo 17, relais
# 29 / 15), vérifiées une à une ; Spike Rush (✅ 02/10 : 3259 sur le personnage, 13 images -> 3260 (tourniquet de 2
# images) -> 2 × 3261 -> 2 anneaux de 64 pointes 3258 aux images 14 et 15 ; part de l'arme de la compétence 192 / 128)
RING_BURST_SKILLS = {378}


def _bursts(calc, start, lvl):
    """Anneaux de projectiles qui touchent (collision non nulle) produits par une chaîne : [(image de départ,
    nombre, projectile)] ; chaîne : déplacement 15 (sous-projectile toutes les param1 images pendant la vie, dès
    l'image 0), impacts 29 / 36 / 45 en fin de vie (anneau de 64 / hitpar1, relais, hitpar1 exemplaires)."""
    out, todo = [], [(start, 0, 1)]
    while todo and len(todo) < 10000:
        m, t, n = todo.pop()
        if m >= len(calc.missiles):
            continue
        rec = calc.missile_rec(m)
        life = rec.i16(MISSILE_RANGE) + rec.i16(MISSILE_RANGE_LEV) * lvl
        if rec.u16(MISSILE_SRV_MOVE) == SRV_MOVE_SPIN:
            every = max(rec.i32(MISSILE_PARAM1), 1)
            for k in range(-(-life // every)):
                todo.append((rec.u16(MISSILE_SUBMISSILE), t + k * every, n))
        hit, sub = rec.u16(MISSILE_SRV_HIT), rec.u16(MISSILE_HIT_SUBMISSILE)
        count = {SRV_HIT_RING: -(-DIRECTIONS // max(rec.i32(MISSILE_HIT_PARAM1), 1)), SRV_HIT_RELAY: 1,
                 45: max(rec.i32(MISSILE_HIT_PARAM1), 1)}.get(hit)
        if count and sub < len(calc.missiles):
            if calc.missile_rec(sub).u8(MISSILE_COLLIDE):
                out.append((t + life, n * count, sub))
            else:
                todo.append((sub, t + life, n * count))
    return sorted(out)


def ring_burst_lines(calc, skill, lo, hi, char=None):
    """Lignes d'une compétence sans fiche qui libère des anneaux autour du lanceur après un délai (srvdo 17,
    RING_BURST_SKILLS) : « After 0.5 seconds, releases 2 rings of 64 projectiles around you (128 in all) » puis la part
    des dégâts de l'arme (celle de la compétence, sinon celle des projectiles, sinon 100 %) ; None sinon."""
    r = calc.rec(skill)
    if skill not in RING_BURST_SKILLS or r.u16(SKILL_SRV_DO) != SRV_DO_PLACE:
        return None
    shots = max(calc.skill_calc(skill, r.u32(SKILL_CALCS), lo, char), 1)
    bursts = _bursts(calc, r.u16(SKILL_SRV_MISSILE_A), lo) * shots
    if not bursts or len({b[1] for b in bursts}) != 1:
        return None
    out = [tr('skill.ring_bursts', d=seconds(calc, bursts[0][0]), k=len(bursts), n=bursts[0][1],
              total=sum(b[1] for b in bursts))]
    src = r.u8(SKILL_SRC_DAMAGE) or calc.missile_rec(bursts[0][2]).u8(MISSILE_SRC_DAMAGE) or 128
    out.append(f'{M.muldiv(src, 100, 128)}{calc.data.s(STR_WEAPON_DAMAGE)}')
    return out


def desc_line(func, a, b, va, vb):
    """Texte d'une ligne de format func (textes a, b ; valeurs [niveau bas, niveau haut] des formules A et B, ou None),
    d'après l'aiguillage de D2Client.dll (0x6fae16c0) ; « +v » : signe + devant une valeur positive ou nulle. Rien si
    la valeur est nulle (formats 2 à 7, 20, 21, 63). Formats reconnus (autres : None, ligne non affichée) :
    2 : a + « +v » + b ; 3 : a + v + b (0x6fadd9b0) ; 4 : a + « +v » ; 5 : a + v (0x6faddca0) ; 6 : « +v » + a ;
    7 : v + a (0x6faddbf0) ; 18 : texte a seul ; 20 : a + « +v% » + b ; 21 : a + « v% » + b (0x6fadd8e0) ;
    35 : « a: x-y » ; 38 : a + « x-y » + b, ou comme 3 si x = y (0x6fadf6e0) ; 59 : b + a + « x-y » (0x6fadd220) ;
    63 : « a: » + « +v% » + « b » (0x6fadce10) ; 65 : « a: b » (0x6fadcb60) ; 66 : a où « %d » = v (0x6fadc9f0) ;
    77 : rien."""
    def vals(v, plus=False):
        f = (lambda x: f'+{x}' if x >= 0 else str(x)) if plus else str
        return f(v[0]) if f(v[0]) == f(v[1]) else f'{f(v[0])} to {f(v[1])}'

    def pairs(lo, hi):   # « x-y » (« x » si x = y), au niveau bas puis au niveau haut
        p = [str(x) if x == y else f'{x}-{y}' for x, y in zip(lo, hi)]
        return p[0] if p[0] == p[1] else f'{p[0]} to {p[1]}'
    nonzero = bool(va) and any(va)
    if func == 18:
        return a
    if func == 65:
        return f'{a}: {b}' if a and b else None
    if func == 66 and va:
        return a.replace('%d', vals(va)).replace('%%', '%')
    if func == 38 and va and vb and va != vb:
        return f'{a}{pairs(va, vb)}{b}'
    if func == 35 and va and vb:
        pair = f'{va[0]}-{vb[0]}' if (va[0], vb[0]) == (va[1], vb[1]) else f'{va[0]}-{vb[0]} to {va[1]}-{vb[1]}'
        return f'{a}: {pair}'
    if func == 59 and va and vb:
        return f'{b}{a}{pairs(va, vb)}'
    if not nonzero:
        return None
    return {2: lambda: f'{a}{vals(va, True)}{b}', 3: lambda: f'{a}{vals(va)}{b}', 38: lambda: f'{a}{vals(va)}{b}',
            4: lambda: f'{a}{vals(va, True)}', 5: lambda: f'{a}{vals(va)}',
            6: lambda: f'{vals(va, True)}{a}', 7: lambda: f'{vals(va)}{a}',
            20: lambda: f'{a}{vals(va, True)}%{b}', 21: lambda: f'{a}{vals(va)}%{b}',
            63: lambda: (f'{a}: ' if a else '') + f'{vals(va, True)}% {b}'}.get(func, lambda: None)()


# ---------- lignes de dégâts ----------
def damage_line(calc, func, skill, lo, hi, char, prefix):
    """Lignes de dégâts et de durée (formats de D2Client.dll, précédés des textes A et B de la ligne, prefix) :
    10 = « Fire Damage: 5-7 » (dégâts ÷ 256, rien s'ils sont nuls) ; 11 = « Poison Length: 2.4 seconds » (froid,
    poison) ; 14 = dégâts totaux sur la durée : « Poison Damage: 60-72 » au-dessus de « over 2.4 seconds » ;
    24 = texte A à la place du libellé de l'élément ; 26 / 27 = « Average … Damage: x-y per second »."""
    etype = calc.rec(skill).u8(SKILL_ELEM_TYPE)
    label = ELEMENT_LABELS.get(etype)
    pair = lambda a, b: str(a) if a == b else f'{a}-{b}'

    def rng(get):
        (a, b), (c, e) = get(lo), get(hi)
        return pair(a, b) if lo == hi else f'{pair(a, b)} to {pair(c, e)}'
    dmg = lambda lvl, which: M.elem_damage(calc, skill, lvl, char, which)
    if func == 10:
        if label is None or not any(dmg(lvl, w) >> 8 for lvl in (lo, hi) for w in ('min', 'max')):
            return None
        return prefix + calc.data.s(label) + rng(lambda lvl: (dmg(lvl, 'min') >> 8, dmg(lvl, 'max') >> 8))
    if func == 11:
        if etype not in LENGTH_LABELS:
            return None
        texts = [seconds(calc, M.elem_length(calc, skill, lvl, char)) for lvl in (lo, hi)]
        if texts[1] is None:
            return None
        return prefix + calc.data.s(LENGTH_LABELS[etype]) + (texts[0] if texts[0] == texts[1] else f'{texts[0]} to {texts[1]}')
    if func == 24 and label is not None:   # texte A à la place du libellé de l'élément
        if not any(dmg(lvl, w) >> 8 for lvl in (lo, hi) for w in ('min', 'max')):
            return None
        return prefix + rng(lambda lvl: (dmg(lvl, 'min') >> 8, dmg(lvl, 'max') >> 8))
    if func in (26, 27):   # dégâts par seconde : × 25 / 256 (26, élément de la compétence) ; × 75 / 256 (27, feu)
        k, lab = (25, label or ELEMENT_LABELS[1]) if func == 26 else (75, ELEMENT_LABELS[1])
        per = lambda lvl: ((dmg(lvl, 'min') * k) >> 8, (dmg(lvl, 'max') * k) >> 8)
        if not any(per(lvl)[0] or per(lvl)[1] for lvl in (lo, hi)):
            return None
        return prefix + calc.data.s(STR_AVERAGE) + calc.data.s(lab) + rng(per) + calc.data.s(STR_PER_SECOND)
    if func == 14 and label is not None:
        length = lambda lvl: M.elem_length(calc, skill, lvl, char)
        total = rng(lambda lvl: ((dmg(lvl, 'min') * length(lvl)) >> 8, (dmg(lvl, 'max') * length(lvl)) >> 8))
        texts = [seconds(calc, length(lvl)) for lvl in (lo, hi)]
        over = '' if texts[1] is None else calc.data.s(STR_OVER) + (texts[0] if texts[0] == texts[1] else f'{texts[0]} to {texts[1]}') + '\n'
        return prefix + over + calc.data.s(label) + total
    return None


def physical_line(calc, skill, lo, hi, char, prefix, ca, cb):
    """Ligne de format 9 (D2Client.dll 0x6fadd000) : textes A et B, « Physical Damage: », puis min et max des dégâts
    physiques ÷ 256, chacun + x × formule A / 100 + formule B ; « x-y », ou « +x » si x = y ; rien si nuls."""
    def pct(v, a):   # v × a / 100 comme le jeu (ordre des opérations choisi contre le débordement)
        if v > 0x100000:
            return int(v / 100) * a
        if a > 0x10000:
            return int(a / 100) * v
        return int(v * a / 100)
    texts = []
    for k, lvl in enumerate((lo, hi)):
        a = 0 if ca is None else ca[k]
        b = 0 if cb is None else cb[k]
        lo_v, hi_v = (M.physical_damage(calc, skill, lvl, char, w) >> 8 for w in ('min', 'max'))
        lo_v, hi_v = lo_v + pct(lo_v, a) + b, hi_v + pct(hi_v, a) + b
        if not lo_v and not hi_v:
            return None
        texts.append(f'{lo_v}-{hi_v}' if lo_v != hi_v else (f'+{lo_v}' if lo_v >= 0 else str(lo_v)))
    return prefix + calc.data.s(STR_PHYSICAL_DAMAGE) + (texts[0] if texts[0] == texts[1] else f'{texts[0]} to {texts[1]}')


# ---------- table des formats ----------
class Line:
    """Une ligne de l'explication à rendre : textes A / B (avec codes couleur), formules A / B évaluées à la demande
    (va / vb : [niveau bas, niveau haut], None sans formule)."""

    def __init__(self, calc, func, ta, tb, ca, cb, skill, lo, hi, char):
        self.calc, self.func, self.ca, self.cb = calc, func, ca, cb
        self.skill, self.lo, self.hi, self.char = skill, lo, hi, char
        self.a, self.b = text(calc, ta), text(calc, tb)

    def value(self, off):
        if off == NO_CALC:
            return None
        return [self.calc.run(self.calc.desc_code, off, self.skill, lvl, self.char) for lvl in (self.lo, self.hi)]

    @property
    def va(self):
        return self.value(self.ca)

    @property
    def vb(self):
        return self.value(self.cb)


def _text_format(L):   # formats de desc_line : textes et valeurs des formules A et B
    return desc_line(L.func, L.a, L.b, L.va, L.vb)


def _attack_rating(L):   # 8 : textes A et B, « To Attack Rating: +v% » (variable toht, D2Client.dll 0x6fadeef0)
    v = [M.to_hit(L.calc, L.skill, lvl, L.char) for lvl in (L.lo, L.hi)]
    return desc_line(2, L.a + L.b + L.calc.data.s(STR_TO_ATTACK_RATING), '%', v, None)


def _physical(L):   # 9 : dégâts physiques de la compétence, modifiés par les formules A (%) et B
    return physical_line(L.calc, L.skill, L.lo, L.hi, L.char, L.a + L.b, L.va, L.vb)


def _damage(L):   # 10, 11, 14, 26, 27 : dégâts et durée de l'effet élémentaire, après les textes A et B
    return damage_line(L.calc, L.func, L.skill, L.lo, L.hi, L.char, L.a + L.b)


def _damage_labelled(L):   # 24 : texte B, texte A (libellé), dégâts de l'élément
    return damage_line(L.calc, 24, L.skill, L.lo, L.hi, L.char, L.b + L.a)


def _duration(L):   # 12 : texte B, texte A, durée (formule A, en frames) : « Duration: 5 seconds »
    frames = L.va
    texts = [seconds(L.calc, v) for v in frames] if frames else [None, None]
    return None if texts[1] is None else L.b + L.a + (texts[0] if texts[0] == texts[1] else f'{texts[0]} to {texts[1]}')


def _radius(L):   # 19 : texte B, texte A, rayon (formule A) : « Radius: 4.6 yards »
    texts = [yards(L.calc, x) for x in (L.va or [0, 0])]
    return L.b + L.a + (texts[0] if texts[0] == texts[1] else f'{texts[0]} to {texts[1]}')


def _mana(L):   # 77 : coût en mana de Median XL (texte du coût de la fiche, skilldesc.bin @0x10)
    raw = desc_row(L.calc, L.skill)
    strmana = text(L.calc, Record(raw).u16(SKILLDESC_STRMANA)) if raw else ''
    return mana_line(L.calc, L.skill, L.lo, L.hi, L.char, strmana)


def _unlock(L):   # 76 (D2Sigma.dll 0x100a912f) : rien si débloquée (formule B non nulle), sinon texte A si la formule A
    # est positive, sinon texte B
    va, vb = L.va or [0, 0], L.vb or [0, 0]
    return None if vb[1] else (L.a if va[1] > 0 else L.b) or None


class Format:
    """Format de ligne : rendu (Line -> texte ou None) ; libellé de la ligne grise d'une valeur inconnue : 'element'
    (libellé de l'élément), 'length' (« Cold Length: »…), 'physical' (« Physical Damage: »), 'pair' (texte A + « : »),
    'colon' (texte A s'il finit par « : »), None (note à la place)."""

    def __init__(self, render, label=None):
        self.render, self.label = render, label


FORMATS = {
    2: Format(_text_format, 'colon'), 3: Format(_text_format, 'colon'), 4: Format(_text_format, 'colon'),
    5: Format(_text_format, 'colon'), 6: Format(_text_format), 7: Format(_text_format), 18: Format(_text_format),
    20: Format(_text_format, 'colon'), 21: Format(_text_format, 'colon'), 35: Format(_text_format, 'pair'),
    38: Format(_text_format, 'colon'), 59: Format(_text_format), 63: Format(_text_format), 65: Format(_text_format),
    66: Format(_text_format), 77: Format(_mana, 'mana'),   # 77 : coût en mana (Median XL ; avec charges : « (N Charges) »)
    8: Format(_attack_rating), 9: Format(_physical, 'physical'),
    10: Format(_damage, 'element'), 11: Format(_damage, 'length'), 14: Format(_damage, 'element'),
    26: Format(_damage, 'element'), 27: Format(_damage), 24: Format(_damage_labelled),
    12: Format(_duration, 'colon'), 19: Format(_radius, 'colon'), 76: Format(_unlock),
}


def render_line(calc, func, ta, tb, ca, cb, skill, lo, hi, char):
    """Texte d'une ligne de l'explication (format func, n° de textes A / B, formules A / B), ou None (format inconnu :
    comme le jeu, rendu des formats de texte, qui ne donne rien)."""
    fmt = FORMATS.get(func, Format(_text_format))
    return fmt.render(Line(calc, func, ta, tb, ca, cb, skill, lo, hi, char))


def placeholder(calc, func, a, skill, no_char=True):
    """Ligne de remplacement d'une valeur non calculée, en gris : « Fire Damage: varies by character » (sans
    personnage de référence) ou « Fire Damage: not calculated » (avec) ; libellé selon le format (FORMATS) ; None si
    le libellé est inconnu (la note en tient lieu)."""
    etype = calc.rec(skill).u8(SKILL_ELEM_TYPE)
    kind = FORMATS[func].label if func in FORMATS else None
    a = strip_colors(a)
    label = None
    if kind == 'element':
        label = ELEMENT_LABELS.get(etype)
        label = calc.data.s(label) if label else None
    elif kind == 'physical':
        label = a + calc.data.s(STR_PHYSICAL_DAMAGE)
    elif kind == 'length':
        label = calc.data.s(LENGTH_LABELS[etype]) if etype in LENGTH_LABELS else None
    elif kind == 'pair' and a.strip():
        label = a.strip() + ': '
    elif kind == 'mana':   # texte du coût de la fiche (« Mana Cost: »)
        raw = desc_row(calc, skill)
        label = text(calc, Record(raw).u16(SKILLDESC_STRMANA)) if raw else None
    elif kind == 'colon' and a.strip().endswith(':') and '\n' not in a and not a.strip().startswith('('):
        label = a   # pas de parenthèse laissée ouverte
    return Grey(label + tr('skill.varies' if no_char else 'skill.not_calculated')) if label else None


# ---------- vie / mana actuelles : taux de conversion ----------
def pool_rate_line(render, char, pool):
    """Ligne qui lit la vie ou la mana actuelle (pool : stat 6 ou 8), valeur qui varie en cours de partie : taux de
    conversion, en gris, si chaque nombre de la ligne leur est proportionnel (droite vérifiée sur les valeurs de
    POOL_SAMPLES) ; sinon None. Croissante : « Physical Damage: 7-10 per 100 Current Mana » (nombres nuls sans
    réserve), sinon valeur sans réserve + « (+1.2 per 100 Current Mana) » ; décroissante (mana manquante, Vizjerei
    Rage) : même chose depuis la réserve pleine avec « Missing Mana ». Les nombres fixes du texte restent tels quels."""
    number = re.compile(r'(?:(?<!\d)[+-])?\d+')   # « 25-30 » : deux nombres positifs ; « +225 », « -84 » : signés
    full = char.stat(pool + 1) // 256   # maximum (stats 7 / 9)
    per = tr('skill.per_100') + ' ' + tr('skill.current_life' if pool == 6 else 'skill.current_mana')
    per_missing = tr('skill.per_100') + ' ' + tr('skill.missing_life' if pool == 6 else 'skill.missing_mana')

    codes = []

    def sample(current):   # (forme du texte, nombres, nombres écrits avec « + ») ; None : ligne absente ou inconnue
        try:
            t = render(PoolProbe(char, {pool: current * 256}))
        except Unsupported:
            return None
        if t is None:
            return None
        codes[:] = re.findall('ÿc.', t)   # codes couleur (« ÿc3 » n'est pas un nombre), remis à la fin
        t = re.sub('ÿc.', '\x01', t)
        tokens = number.findall(t)
        return number.sub('#', t), [int(n) for n in tokens], [n.startswith('+') for n in tokens]
    points = [(v, sample(v)) for v in POOL_SAMPLES]
    points = [(v, p) for v, p in points if p is not None]
    if len(points) < 3 or len({p[0] for _, p in points}) != 1:
        return None
    shape, plus = points[0][1][0], points[0][1][2]
    xs = [v for v, _ in points]
    mean_x = sum(xs) / len(xs)
    fit = []   # (pente par point de réserve, ordonnée à 0) de chaque nombre, droite des moindres carrés
    for ys in zip(*(p[1] for _, p in points)):
        mean_y = sum(ys) / len(ys)
        slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / sum((x - mean_x) ** 2 for x in xs)
        if any(abs(y - (mean_y + slope * (x - mean_x))) > 2 for x, y in zip(xs, ys)):
            return None   # pas proportionnel (plafond, seuil…)
        fit.append((slope, mean_y - slope * mean_x))
    if not any(abs(s) * 100 >= 0.05 for s, _ in fit):
        # ligne qui ne dépend pas en fait de la vie / mana actuelles (lues par une formule annulée, ex. compétence
        # interne 1820 au niveau 0) : sa valeur, exacte
        try:
            return render(PoolProbe(char, {pool: full * 256}))
        except Unsupported:
            return None
    if all(s >= 0 for s, _ in fit):
        base, rates, suffix = [b for _, b in fit], [s * 100 for s, _ in fit], per
    elif all(s <= 0 for s, _ in fit):   # dépend de ce qui manque : depuis la réserve pleine
        base, rates, suffix = [b + s * full for s, b in fit], [-s * 100 for s, _ in fit], per_missing
    else:
        return None

    def fmt(v, rate, sign):   # valeurs du jeu : entières ; taux : une décimale en dessous de 10
        v = round(v, 1) if rate and abs(v) < 10 else round(v)
        txt = str(int(v)) if v == int(v) else str(v)
        return f'+{txt}' if sign and v >= 0 else txt
    changing = [abs(r) >= 0.05 for r in rates]
    restore = lambda t: re.sub('\x01', lambda m, it=iter(codes): next(it, ''), t)
    fill = lambda vals: re.sub('#', lambda m, it=iter(zip(*vals, plus)): fmt(*next(it)), shape)
    mentioned = ('current life' if pool == 6 else 'current mana') in shape.lower()
    if mentioned and changing.count(True) == 1 and all(abs(round(b)) < 1 for b, c in zip(base, changing) if c):
        # le texte du jeu donne déjà le taux (Balefire « Drains 10% of current life (…) per second ») : nombre retiré
        kept = iter([None if c else b for b, c in zip(base, changing)])
        txt = re.sub(r'\s*\(#\)|#', lambda m: '' if (v := next(kept)) is None else fmt(v, False, False), shape)
        return Grey(restore(re.sub(r' {2,}', ' ', txt)))
    if all(abs(round(b)) < 1 for b, c in zip(base, changing) if c):   # nul sans réserve : taux à la place
        return Grey(restore(f'{fill(([r if c else b for b, r, c in zip(base, rates, changing)], changing))} {suffix}'))
    steps = '-'.join(dict.fromkeys(fmt(r, True, False) for r, c in zip(rates, changing) if c))
    return Grey(restore(f'{fill((base, [False] * len(base)))} (+{steps} {suffix})'))


# ---------- explication complète ----------
MANA_FORMAT = 77   # ligne du coût en mana (Median XL)


def grouped_lines(calc, skill, lo, hi, char=None, reasons=None, colors=False, mana=True):
    """Lignes de l'explication sous « Current Skill Level » comme dans le jeu pour une compétence donnée par un objet
    (niveau lo, ou de lo à hi dans le catalogue) : lignes dsc2 puis lignes du niveau actuel, chaque groupe de la
    dernière à la première, puis le coût en mana : [('dsc2', textes), ('desc', textes)]. Textes bruts (codes de
    couleur compris, « \\n » pour les lignes multiples) ; une ligne dont une valeur n'est pas calculable est omise.
    Toute valeur non calculée est signalée, en gris (Grey) : une ligne dont la valeur dépend d'une donnée inconnue
    devient « <libellé>: varies by character » (sans personnage de référence, écran Library) ou « <libellé>: not
    calculated » (avec) si son libellé est connu (placeholder) ; sinon, comme pour un format de ligne pas encore
    reconnu, une note en tête : ('note', [« (values depend on character) » ou « (some values not calculated) »]).
    char : personnage (mxl_save.load_character, dict des mêmes champs, ou ses totaux mxl_char_stats) ou None.
    reasons : liste qui reçoit (n° de ligne, format, raison) de chaque ligne non calculée (diagnostic).
    colors : textes avec leurs codes couleur du jeu (ÿc), pour l'infobulle (mxl_skills) ; sinon sans.
    mana : False = sans la ligne du coût en mana (compétence lancée par une chance de lancer : jamais payée)."""
    if char is not None and not hasattr(char, 'skill_level'):
        from mxl_char_stats import character_stats
        char = character_stats(char, calc.data)
    raw = desc_row(calc, skill)
    if raw is None:
        return []
    x = Record(raw)
    funcs = raw[SKILLDESC_LINES:SKILLDESC_LINES + 17]
    ta, tb = x.u16s(SKILLDESC_TEXT_A, 17), x.u16s(SKILLDESC_TEXT_B, 17)
    ca, cb = x.u32s(SKILLDESC_CALC_A, 17), x.u32s(SKILLDESC_CALC_B, 17)
    out = {'note': [], 'dsc2': [], 'desc': []}
    note = Grey(tr('skill.values_note' if char is None else 'skill.some_not_calculated'))
    for k in list(reversed(DSC2_GROUP)) + list(reversed(DESC_GROUP)):
        if not funcs[k] or (not mana and funcs[k] == MANA_FORMAT):
            continue
        render = lambda ch, k=k: render_line(calc, funcs[k], ta[k], tb[k], ca[k], cb[k], skill, lo, hi, ch)
        try:
            line = render(char)
        except Unsupported as e:   # valeur inconnue : libellé + « varies by character » / « not calculated », sinon note
            # vie / mana actuelles : taux de conversion (« … per 100 Current Mana ») si la ligne leur est proportionnelle
            line = pool_rate_line(render, char, e.stat) if char and e.stat in POOL_STATS else None
            if line is None:
                line = placeholder(calc, funcs[k], text(calc, ta[k]), skill, char is None)
                if line is None:
                    out['note'] = [note]
                if reasons is not None:
                    reasons.append((k, funcs[k], e.kind))
        except (IndexError, struct.error) as e:   # lecture hors des tables
            line, out['note'] = None, [note]
            if reasons is not None:
                reasons.append((k, funcs[k], f'erreur {type(e).__name__}'))
        if funcs[k] not in FORMATS:   # format pas encore reconnu : signalé par la note
            out['note'] = [note]
            if reasons is not None:
                reasons.append((k, funcs[k], f'format {funcs[k]}'))
        if line is not None:
            out['dsc2' if k in DSC2_GROUP else 'desc'].append(line)
    plain = lambda t: Grey(strip_colors(t)) if isinstance(t, Grey) else strip_colors(t)
    return [(g, t if colors else [plain(x) for x in t]) for g, t in out.items() if t]
