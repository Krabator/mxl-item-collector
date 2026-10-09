"""Explication des compétences : mécaniques du jeu reproduites d'après son code (adresses citées dans chaque fonction).

Fonctions sans état qui reçoivent le calculateur (calc : mxl_skill_formula.FormulaEngine, pour les tables et les
formules : calc.rec, calc.rec2, calc.skill_calc, calc.missiles) et le personnage de référence (char, ou None : écran
Library). Ce module n'importe pas l'interpréteur des formules : il se contente d'appeler calc.skill_calc.

Interface du personnage (mxl_char_stats.CharacterStats, ou PoolProbe pour la vie / mana imposées) — seuls accès faits
par l'explication des compétences :
  char_level(char), invested_points(char, skill)  niveau, points investis (champs du personnage lu) ;
  char.stat(n°, param), char.base_stat(n°, param)  total / valeur de base d'une stat ;
  char.skill_level(compétence)                    niveau actuel d'une autre compétence (points + objets) ;
  char.has_state(état)                            état actif au repos (états passifs) ;
  char.pools                                      vie / mana actuelles imposées (taux de conversion).
"""
from mxl_skill_data import (Unsupported, NO_CALC, level_brackets, diminishing, muldiv, SKILL_ELEM_TYPE, SKILL_HIT_SHIFT,
                            SKILL_EMIN, SKILL_EMAX, SKILL_EMIN_LEV, SKILL_EMAX_LEV, SKILL_EDMG_SYM, SKILLS2_ENERGY_BONUS,
                            SKILLS2_NO_SPELL_DAMAGE, SKILL_FLAGS, SKILL_OTHER_DAMAGE, SKILL_MIN_DAM, SKILL_MAX_DAM,
                            SKILL_MIN_DAM_LEV, SKILL_MAX_DAM_LEV, SKILL_DMG_SYM, PHYSICAL_SPELL_DAMAGE, ELEMENTS,
                            SKILL_ELEN, SKILL_ELEV_LEN, SKILL_ELEN_SYM, SKILL_MIN_MANA, SKILL_MANA_SHIFT, SKILL_MANA,
                            SKILL_LVL_MANA, SKILLS2_MANA_CALC, SKILLS2_LVL_MANA_CALC, MANA_COST_REDUCTION, SKILL_TOHIT, SKILL_LVL_TOHIT, SKILL_TOHIT_CALC, SKILL_COOLDOWN_CALC,
                            COOLDOWN_REDUCTION, SKILL_MINION_LIFE, SKILL_MINION_LIFE_LEV, SKILL_MINION_LIFE_CALC,
                            SKILL_MINION_AR_LEV, SUMMON_ATTACK_RATING, SKILL_SRC_DAMAGE, MISSILE_FIELDS, MISSILE_PAIRS,
                            MISSILE_RANGE, MISSILE_RANGE_LEV, STAT_ENERGY, STAT_SPELL_FOCUS)


# ---------- interface du personnage ----------
def char_level(char):
    """Niveau du personnage."""
    return char.char['level']


def invested_points(char, skill):
    """Points investis dans la compétence (0 : compétence donnée par un objet)."""
    return char.char['skills'].get(skill, 0)


# ---------- dégâts ----------
def energy_bonus(char):
    """Bonus automatique Énergie / Spell Focus / niveau du personnage (D2Sigma.dll 0x100a6c70), en % :
    (50 + 130 × (Énergie + 20) / (Énergie + 500) + min(Spell Focus / 10, 100)) × (min(niveau, 120) + 5) × 10 / 100 − 75."""
    energy, focus, level = char.stat(STAT_ENERGY), char.stat(STAT_SPELL_FOCUS), char_level(char)
    part = 50 + (energy + 20) * 130 // (energy + 500) + min(focus // 10, 100)
    return part * (min(level, 120) + 5) * 10 // 100 - 75


def elem_damage(calc, skill, lvl, char, which, spell=True):
    """Dégâts élémentaires minimum (which = 'min') ou maximum de la compétence au niveau lvl, en 256es, comme le jeu :
    base (min / max + incréments des paliers de niveau) décalée de HitShift ; + base × (formule de synergie de la
    compétence + bonus Énergie / Spell Focus automatique) / 100 ; + base × « % dégâts de sort » de l'élément / 100 (si
    spell : ligne de dégâts, variables enma / exma ; pas pour edmn / edmx).
    ✅ Flamefront, Kalidor (niveau 4, Énergie 21, Spell Focus 35, +4 % feu) : niveau 4 = 1409-1827 -> 5-7, niveau 3 =
    1146-1476 -> 4-5 (deux captures en jeu)."""
    if char is None:
        raise Unsupported('dégâts élémentaires sans personnage')
    if lvl <= 0:   # compétence que le personnage n'a pas (skill() au niveau 0) : 0 (D2Sigma.dll 0x100a5d60)
        return 0
    r, r2 = calc.rec(skill), calc.rec2(skill)
    levels = r.i32s(SKILL_EMIN_LEV if which == 'min' else SKILL_EMAX_LEV, 5)
    base = (r.i32(SKILL_EMIN if which == 'min' else SKILL_EMAX) + level_brackets(levels, lvl)) << r.u8(SKILL_HIT_SHIFT)
    bonus = calc.skill_calc(skill, r.u32(SKILL_EDMG_SYM), lvl, char)
    if r2.u8(SKILLS2_ENERGY_BONUS):
        bonus += energy_bonus(char)
    if bonus:
        base += muldiv(base, bonus, 100)
    element = ELEMENTS.get(r.u8(SKILL_ELEM_TYPE))
    if spell and element and not r2.u8(SKILLS2_NO_SPELL_DAMAGE):
        pct = char.stat(element)
        if pct:
            base += muldiv(base, pct, 100)
    return base


def physical_damage(calc, skill, lvl, char, which):
    """Dégâts physiques propres de la compétence (sans la part de l'arme, que la ligne de format 9 ne demande pas),
    en 256es (D2Sigma.dll 0x100a6020 / 0x100a5ec0) : base (min / max + incréments des paliers de niveau) ; + base ×
    (formule de synergie + bonus Énergie / Spell Focus automatique) / 100 ; + base × stat 357 / 100 (sauf
    skills2.bin @0x2E) ; décalée de HitShift à la fin."""
    if char is None:
        raise Unsupported('dégâts physiques sans personnage')
    r, r2 = calc.rec(skill), calc.rec2(skill)
    if r.u32(SKILL_FLAGS) & SKILL_OTHER_DAMAGE:
        raise Unsupported('dégâts physiques (autre calcul)')
    levels = r.i32s(SKILL_MIN_DAM_LEV if which == 'min' else SKILL_MAX_DAM_LEV, 5)
    base = r.i32(SKILL_MIN_DAM if which == 'min' else SKILL_MAX_DAM) + level_brackets(levels, lvl)
    bonus = (energy_bonus(char) if r2.u8(SKILLS2_ENERGY_BONUS) else 0) + calc.skill_calc(skill, r.u32(SKILL_DMG_SYM), lvl, char)
    if bonus:
        base += muldiv(base, bonus, 100)
    if not r2.u8(SKILLS2_NO_SPELL_DAMAGE):
        pct = char.stat(PHYSICAL_SPELL_DAMAGE)
        if pct:
            base += muldiv(base, pct, 100)
    return base << r.u8(SKILL_HIT_SHIFT)


def weapon_damage_pct(calc, skill):
    """Part des dégâts de l'arme, en % (variable wdm : u8 en 128es × 100 / 128, D2Sigma.dll 0x100a6532)."""
    return muldiv(calc.rec(skill).u8(SKILL_SRC_DAMAGE), 100, 128)


# ---------- durées, coût, recharge, précision ----------
def elem_length(calc, skill, lvl, char):
    """Durée de l'effet élémentaire (froid, poison…) en frames (25 par seconde), comme D2Common.dll (fonction de
    l'ordinal 10147, variable edln ; non remplacée par Median XL) : durée + incréments par palier (niveaux 2-8,
    9-16, 17+) ; + durée × formule de synergie de durée / 100."""
    if lvl <= 0:   # niveau 0 : 0 (D2Common.dll 0x6fd9e900)
        return 0
    r = calc.rec(skill)
    incs = r.i32s(SKILL_ELEV_LEN, 3)
    n = r.i32(SKILL_ELEN) + level_brackets(incs + [incs[2]] * 2, lvl, (8, 16, 10 ** 9))
    off = r.u32(SKILL_ELEN_SYM)
    if off != NO_CALC:
        pct = calc.skill_calc(skill, off, lvl, char)
        if pct:
            n += muldiv(n, pct, 100)
    return n


def mana_raw(calc, skill, lvl):
    """Variable mana des formules (D2Common.dll 0x6fda1264) : (mana + (niveau − 1) × mana par niveau de skills.bin)
    décalé de manashift, ÷ 256 ; 0 si le niveau est nul. Champs à zéro dans Median XL (coût : mana)."""
    if lvl <= 0:
        return 0
    r = calc.rec(skill)
    return ((r.i16(SKILL_MANA) + (lvl - 1) * r.i16(SKILL_LVL_MANA)) << r.u8(SKILL_MANA_SHIFT)) >> 8


def skills2_formula(calc, skill, field, lvl, char):
    """Formule de skills2.bin au champ field (D2Sigma.dll 0x100a7620 : décalage hors du code = 0)."""
    off = calc.rec2(skill).u32(field)
    return calc.run(calc.skills2_code, off, skill, lvl, char) if off < len(calc.skills2_code) else 0


def mana_parts(calc, skill, lvl, char):
    """(mana de base, mana par niveau) de Median XL, en unités avant décalage : formule de skills2.bin @0x36 ; formule
    @0x3A × (100 + stat 228 « Mana Cost of Skills ») / 100, arrondi vers zéro (D2Sigma.dll 0x100a1dc0 ; sans
    personnage : stat 228 = 0)."""
    base = skills2_formula(calc, skill, SKILLS2_MANA_CALC, lvl, char)
    per = skills2_formula(calc, skill, SKILLS2_LVL_MANA_CALC, lvl, char)
    reduction = char.stat(MANA_COST_REDUCTION) if char else 0
    return base, int(per * (100 + reduction) / 100)


def mana(calc, skill, lvl, char=None):
    """Coût en mana de Median XL, en 256es (D2Sigma.dll, ligne de format 77 0x100a8f66 et dépense 0x100a1cd0) :
    ((niveau − 1) × mana par niveau + mana de base) décalé de manashift, au moins le minimum × 256 (mana_parts ; ✅
    Flamefront niveau 4 : (3 × 16 + 22) × 32 = 2240 -> « 8 », capture de Kalidor)."""
    r = calc.rec(skill)
    base, per = mana_parts(calc, skill, lvl, char)
    cost = (max(lvl - 1, 0) * per + base) << r.u8(SKILL_MANA_SHIFT)
    return max(r.u16(SKILL_MIN_MANA) << 8, cost)


def cooldown(calc, skill, lvl, char):
    """Temps de recharge en frames (skcd, D2Sigma.dll 0x100b0ed0) : formule de la compétence − stat 309 du personnage
    (« Cooldown Reduced by », param = compétence)."""
    if not char:
        raise Unsupported('skcd')
    return calc.skill_calc(skill, calc.rec(skill).u32(SKILL_COOLDOWN_CALC), lvl, char) - char.stat(COOLDOWN_REDUCTION, skill)


def to_hit(calc, skill, lvl, char):
    """Attack Rating de la compétence (toht, D2Common.dll 0x6fd9ea50) : formule @0x1A0 si elle existe, sinon
    @0x198 + (niveau − 1) × @0x19C."""
    if lvl <= 0:   # niveau 0 : 0 (D2Common.dll 0x6fd9ea80)
        return 0
    r = calc.rec(skill)
    off = r.u32(SKILL_TOHIT_CALC)
    if off != NO_CALC:
        return calc.skill_calc(skill, off, lvl, char)
    return r.i32(SKILL_TOHIT) + (lvl - 1) * r.i32(SKILL_LVL_TOHIT)


# ---------- invocations ----------
def minion_life(calc, skill, lvl, char):
    """Vie d'une invocation (mnhp, D2Sigma.dll 0x10067c60) : vie de base de la compétence × (100 + formule de bonus
    @0x138) × (100 + niveau du personnage / 2) / 3333 (en entiers 64 bits, plafonnée comme dans le jeu)."""
    if not char:
        raise Unsupported('mnhp')
    if lvl <= 0:   # niveau 0 : vie de base 0 (D2Sigma.dll 0x100a5e84)
        return 0
    r = calc.rec(skill)
    base = r.i32(SKILL_MINION_LIFE) + (lvl - 1) * r.i32(SKILL_MINION_LIFE_LEV)
    bonus = calc.skill_calc(skill, r.u32(SKILL_MINION_LIFE_CALC), lvl, char)
    life = (char_level(char) // 2 + 100) * (bonus + 100) * base // 3333
    return min(life, 0x7FFFFFFF >> 8)


def minion_attack_rating(calc, skill, lvl, char):
    """Attack Rating des invocations (mnar, D2Sigma.dll 0x10067bd0) : (niveau − 1) × @0x158, majoré de la stat 500 du
    personnage (« to Summon Attack Rating ») ; 0 au niveau 1."""
    n = (lvl - 1) * calc.rec(skill).i32(SKILL_MINION_AR_LEV)
    if n and not char:
        raise Unsupported('mnar')
    return n + muldiv(n, char.stat(SUMMON_ATTACK_RATING), 100) if n else 0


# ---------- projectiles ----------
def missile_value(calc, missile, var, lvl):
    """Variable var de misscalc.bin pour le projectile missile (enregistrement de 420 octets de missiles.bin) au
    niveau lvl (D2Common.dll 0x6fdba790, table 0x6fdbaa70) : par1-5, cpa1-5, hpa1-3, chp1-3, dpa1-2 = champs i32 ;
    lvl ; rang = i16 @0x96 + niveau × i16 @0x98 ; sl12, cl12… = a + (niveau − 1) × b ; sd12, cd12… = rendement
    décroissant de a vers b. Dégâts du projectile (edmn… dmxs, 19 à 27) : non étudiés."""
    if not 0 <= missile < len(calc.missiles):
        return 0
    r = calc.missile_rec(missile)
    if var < len(MISSILE_FIELDS):
        return r.i32(MISSILE_FIELDS[var])
    if var == 18:
        return lvl
    if var == 28:
        return r.i16(MISSILE_RANGE) + lvl * r.i16(MISSILE_RANGE_LEV)
    if 29 <= var <= 42:
        a, b = MISSILE_PAIRS[(var - 29) // 2]
        return r.i32(a) + (lvl - 1) * r.i32(b) if var % 2 else diminishing(lvl, r.i32(a), r.i32(b))
    raise Unsupported(f'miss(variable {var})')
