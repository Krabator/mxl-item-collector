"""Explication des compétences : interpréteur des formules du jeu (skillscode.bin, skilldesccode.bin).

Une formule est une suite d'opérations sur une pile (Fog.dll 10253, table 0x6ff6a440) :
- 0 fin ; 4 / 5 / 6 n : variable n de skillcalc.bin (index u8 / i16 / i32 : lvl, par1…par8, ln12, clc1, pst1…) ;
  7 / 8 / 9 : constante signée de 8 / 16 / 32 bits ;
- 1 n : fonction n (min, max, rand, skill, miss, stat, sklvl, state, class, …, lstat) ;
- 10 à 15 : < > <= >= == != ; 16 + ; 17 - ; 18 * ; 19 / (entière, ÷ 0 = 0) ; 20 puissance ; 21 opposé ;
  22 condition ? a : b.
Variables : table VARIABLES (nom de skillcalc.bin -> fonction) ; fonctions : table FUNCTIONS (nom -> fonction).
Ajouter une variable ou une fonction = une entrée dans sa table. Une valeur inconnue lève Unsupported.
"""
import os, struct
from mxl_skill_data import (Unsupported, Record, PoolProbe, NO_CALC, diminishing, SKILL_CALCS, SKILL_PARAMS,
                            SKILL_PASSIVE_CALCS, SKILL_AURA_CALCS, SKILL_AURA_LEN, SKILL_AURA_RANGE, SKILL_PET_MAX_CALC,
                            SKILL_SKPT_CALC, SKILL_STATE_FIELDS, SKILL_PASSIVE_STATS, SKILL_AURA_STATS, SKILLS2_SIZE,
                            SYN_STATS, STAT_ATTACK_RATING, NOT_ON_PLAYER, CURRENT_POOLS)
import mxl_skill_mechanics as M

# situation « au repos » supposée par les explications : hors de la ville, debout (en ville, le coût en mana de
# certaines invocations tombe à 1)
REST_AREA = 2   # zone : Blood Moor (acte I, hors de la ville ; camp des Rogues = 1)
REST_MODE = 1   # action : debout hors de la ville (mode NU ; en ville : TN = 5)
# fonctions des formules, dans l'ordre de leur n° (table de D2Common.dll 0x6fde9e24 complétée par D2Sigma.dll 0x101df3a8)
FUNCS = ('min', 'max', 'rand', 'skill', 'miss', 'stat', 'sklvl', 'state', 'class', 'prob', 'sktree', 'lstat',
         'sumcount', 'istat')
# variables des dégâts élémentaires (D2Common.dll, ordinal 10147, remplacées au lancement par D2Sigma.dll 0x100a5d60 /
# 0x100a5c80) : (min ou max, « % dégâts de sort » de l'élément compris, divisé par 256)
ELEM_REFS = {'edmn': ('min', False, True), 'edmx': ('max', False, True), 'edns': ('min', False, False),
             'edxs': ('max', False, False), 'enma': ('min', True, True), 'exma': ('max', True, True),
             'enms': ('min', True, False), 'exms': ('max', True, False)}


class FormulaEngine:
    """Tables des compétences et de leurs formules (lues une fois par dossier de données) et interpréteur."""

    def __init__(self, data):
        self.data = data
        self.skills, self.descs = data._rows('skills'), data._rows('skilldesc')
        read = lambda name: open(os.path.join(data.folder, name + '.bin'), 'rb').read()
        self.desc_code, self.skill_code = read('skilldesccode'), read('skillscode')
        self.skills2_code = read('skills2code')   # formules de skills2.bin (coût en mana de Median XL)
        self.skills2 = data._rows('skills2')
        self.missiles = data._rows('missiles')
        refs = read('skillcalc')
        self.refs = [refs[4 + i * 4:8 + i * 4].decode('latin1').strip() for i in range(struct.unpack_from('<I', refs)[0])]
        self._sourced = None

    # ---------- enregistrements ----------
    def rec(self, skill):
        """Enregistrement de skills.bin de la compétence."""
        return Record(self.skills[skill])

    def rec2(self, skill):
        """Enregistrement de skills2.bin (Median XL) de la compétence ; vide s'il n'existe pas."""
        return Record(self.skills2[skill] if skill < len(self.skills2) else bytes(SKILLS2_SIZE))

    def missile_rec(self, missile):
        return Record(self.missiles[missile])

    # ---------- interpréteur ----------
    def run(self, code, off, skill, lvl, char):
        """Valeur de la formule à l'octet off de code, pour la compétence skill au niveau lvl."""
        stack, i = [], off
        pop = lambda n: [stack.pop() for _ in range(n)][::-1]
        while True:
            op = code[i]
            if op == 0:
                if len(stack) != 1:
                    raise Unsupported('pile')
                return stack[0]
            if op in (7, 8, 9):   # constante i8 / i16 / i32
                fmt, size = {7: ('<b', 1), 8: ('<h', 2), 9: ('<i', 4)}[op]
                stack.append(struct.unpack_from(fmt, code, i + 1)[0])
                i += 1 + size
            elif op in (4, 5, 6):   # variable (index u8 / i16 / i32)
                fmt, size = {4: ('<B', 1), 5: ('<h', 2), 6: ('<i', 4)}[op]
                stack.append(self.ref(struct.unpack_from(fmt, code, i + 1)[0], skill, lvl, char))
                i += 1 + size
            elif op == 20:   # a puissance b (1 si b <= 0), en entiers 32 bits signés
                a, b = pop(2)
                v = 1
                for _ in range(b):
                    v = (v * a + 2 ** 31) % 2 ** 32 - 2 ** 31
                stack.append(v)
                i += 1
            elif op == 1:
                stack.append(self.func(code[i + 1], pop, skill, lvl, char))
                i += 2
            elif 10 <= op <= 19:
                a, b = pop(2)
                stack.append({10: lambda: int(a < b), 11: lambda: int(a > b), 12: lambda: int(a <= b),
                              13: lambda: int(a >= b), 14: lambda: int(a == b), 15: lambda: int(a != b),
                              16: lambda: a + b, 17: lambda: a - b, 18: lambda: a * b,
                              19: lambda: int(a / b) if b else 0}[op]())
                i += 1
            elif op == 21:
                stack.append(-stack.pop())
                i += 1
            elif op == 22:
                c, a, b = pop(3)
                stack.append(a if c else b)
                i += 1
            else:
                raise Unsupported(f'opération {op}')

    def skill_calc(self, skill, off, lvl, char):
        """Formule de skillscode.bin (champ u32 de la compétence). Pas de formule (NO_CALC) : 0, comme le jeu
        (D2Common.dll 0x6fda1741 : décalage hors du code des formules)."""
        if off == NO_CALC:
            return 0
        return self.run(self.skill_code, off, skill, lvl, char)

    def ref(self, n, skill, lvl, char):
        """Valeur de la variable n de skillcalc.bin (table VARIABLES)."""
        name = self.refs[n] if n < len(self.refs) else ''
        handler = VARIABLES.get(name)
        if handler is None:
            raise Unsupported(name or f'variable {n}')
        return handler(self, n, skill, lvl, char)

    def func(self, n, pop, skill, lvl, char):
        """Valeur de la fonction n des formules (table FUNCTIONS), ses arguments pris sur la pile (pop)."""
        name = FUNCS[n] if n < len(FUNCS) else ''
        handler = FUNCTIONS.get(name)
        if handler is None:
            raise Unsupported(name or f'fonction {n}')
        return handler(self, name, pop, skill, lvl, char)

    def sourced_stats(self):
        """Stats qu'un calcul hors du jeu peut connaître : stats nommées, stats de base du personnage (0 à 15), et stats
        cachées écrites par une propriété d'objet, une stat passive ou une aura de compétence (au repos : sans aura
        active, la part des auras vaut 0)."""
        if self._sourced is None:
            named = {s for s, c in self.data.isc.items() if c.get('desc') and 'BUFFALO' not in c['desc']}
            items = {x for st in self.data.props for x in st if x is not None and x >= 0}
            skills = set()
            for raw in self.skills:
                r = Record(raw)
                skills |= set(r.u16s(SKILL_PASSIVE_STATS, 5)) | set(r.u16s(SKILL_AURA_STATS, 6))
            self._sourced = (named | items | skills | set(range(16)) | NOT_ON_PLAYER) - CURRENT_POOLS
        return self._sourced


# ---------- variables (skillcalc.bin) ----------
def _par(calc, skill, k):
    return calc.rec(skill).i32(SKILL_PARAMS + 4 * (k - 1))


def _needs_char(name, fn):
    """Variable qui demande un personnage de référence : sans lui, Unsupported(name)."""
    def handler(calc, n, skill, lvl, char):
        if not char:
            raise Unsupported(name)
        return fn(calc, n, skill, lvl, char)
    return handler


def _calc_field(off):
    """Variable = formule u32 de la compétence au champ off (absente : 0)."""
    return lambda calc, n, skill, lvl, char: calc.skill_calc(skill, calc.rec(skill).u32(off), lvl, char)


def _elem(which, spell, shift):
    def handler(calc, n, skill, lvl, char):   # dégâts élémentaires de la compétence (en 256es ou divisés par 256)
        v = M.elem_damage(calc, skill, lvl, char, which, spell)
        return v >> 8 if shift else v
    return handler


def _state(calc, n, skill, lvl, char):
    """État de l'aura (variable 90 : @0x80 ; 101 : @0x82) ou état passif (91 : @0x94) actif (D2Sigma.dll 0x100a657f…) ;
    au repos : états passifs seulement."""
    state = calc.rec(skill).u16(SKILL_STATE_FIELDS[n])
    return int(bool(state) and char.has_state(state))


VARIABLES = {
    'lvl': lambda calc, n, skill, lvl, char: lvl,
    'mana': lambda calc, n, skill, lvl, char: M.mana_raw(calc, skill, lvl),
    'len': _calc_field(SKILL_AURA_LEN),
    'rng': _calc_field(SKILL_AURA_RANGE),   # rayon de l'aura (D2Common.dll, variable 59)
    'pets': _calc_field(SKILL_PET_MAX_CALC),   # nombre maximal d'invocations
    'skpt': _calc_field(SKILL_SKPT_CALC),
    'toht': lambda calc, n, skill, lvl, char: M.to_hit(calc, skill, lvl, char),
    'skcd': lambda calc, n, skill, lvl, char: M.cooldown(calc, skill, lvl, char),
    'mnhp': lambda calc, n, skill, lvl, char: M.minion_life(calc, skill, lvl, char),
    'mnar': lambda calc, n, skill, lvl, char: M.minion_attack_rating(calc, skill, lvl, char),
    'wdm': lambda calc, n, skill, lvl, char: M.weapon_damage_pct(calc, skill),   # « % Weapon Damage »
    'edln': lambda calc, n, skill, lvl, char: M.elem_length(calc, skill, lvl, char),   # durée de l'effet (frames)
    'edma': lambda calc, n, skill, lvl, char: M.elem_length(calc, skill, lvl, char),
    'ulvl': _needs_char('ulvl', lambda calc, n, skill, lvl, char: M.char_level(char)),
    'blvl': _needs_char('blvl', lambda calc, n, skill, lvl, char: M.invested_points(char, skill)),
    'aura': _needs_char('aura', _state),
    # zone où se trouve le personnage (Median XL, variable 106) : au repos, hors de la ville ; ✅ captures de Blood
    # Skeleton (« Mana Cost: 1 » en ville, « 49 » dehors), Abyss Knight et Night Hawks hors de la ville
    'area': lambda calc, n, skill, lvl, char: REST_AREA,
    # action du personnage (unité +0x10, variable 109) : au repos, debout hors de la ville
    'mode': lambda calc, n, skill, lvl, char: REST_MODE,
    'pass': _needs_char('pass', _state),
}
for _k in range(1, 9):
    VARIABLES[f'par{_k}'] = lambda calc, n, skill, lvl, char, k=_k: _par(calc, skill, k)
def _points(k, diminish, at_zero):
    """Variables par points investis (D2Sigma.dll 0x100a5c40 / 0x100a5be0) : points > 0 : par(k) + (points − 1) ×
    par(k + 1), ou rendement décroissant de par(k) vers par(k + 1) sans plafond ; aucun point : 0 (bl12, bd12…) ou
    par(k) (blz1, bdz1… : at_zero)."""
    def handler(calc, n, skill, lvl, char):
        a, b, pts = _par(calc, skill, k), _par(calc, skill, k + 1), M.invested_points(char, skill)
        if pts <= 0:
            return a if at_zero else 0
        if diminish:
            return a + int(int(110 * pts / (pts + 6)) * (b - a) / 100)
        return a + (pts - 1) * b
    return handler


for _k in (1, 3, 5, 7):
    # ln12… : par(k) + (niveau − 1) × par(k + 1), 0 au niveau 0 (D2Common.dll 0x6fd51670 : skill() d'une compétence que
    # le personnage n'a pas) ; dm12… : rendement décroissant de par(k) vers par(k + 1)
    VARIABLES[f'ln{_k}{_k + 1}'] = lambda calc, n, skill, lvl, char, k=_k: (
        _par(calc, skill, k) + (lvl - 1) * _par(calc, skill, k + 1) if lvl > 0 else 0)
    VARIABLES[f'dm{_k}{_k + 1}'] = lambda calc, n, skill, lvl, char, k=_k: diminishing(lvl, _par(calc, skill, k), _par(calc, skill, k + 1))
    for _name, _dim, _zero in ((f'bl{_k}{_k + 1}', False, False), (f'bd{_k}{_k + 1}', True, False),
                               (f'blz{_k}', False, True), (f'bdz{_k}', True, True)):
        VARIABLES[_name] = _needs_char(_name, _points(_k, _dim, _zero))
for _k in range(1, 5):
    VARIABLES[f'clc{_k}'] = _calc_field(SKILL_CALCS + 4 * (_k - 1))
for _k in range(1, 6):
    VARIABLES[f'pst{_k}'] = _calc_field(SKILL_PASSIVE_CALCS + 4 * (_k - 1))
for _k in range(1, 7):
    VARIABLES[f'ast{_k}'] = _calc_field(SKILL_AURA_CALCS + 4 * (_k - 1))
for _name, (_which, _spell, _shift) in ELEM_REFS.items():
    VARIABLES[_name] = _elem(_which, _spell, _shift)
for _name, _sid in SYN_STATS.items():   # amélioration de la compétence par les objets du personnage (0 sans)
    VARIABLES[_name] = _needs_char(_name, lambda calc, n, skill, lvl, char, sid=_sid: char.stat(sid, skill))


# ---------- fonctions des formules ----------
def _min_max(calc, name, pop, skill, lvl, char):
    a, b = pop(2)
    return min(a, b) if name == 'min' else max(a, b)


def _skill(calc, name, pop, skill, lvl, char):
    """skill(compétence, variable) : variable d'une autre compétence à son niveau actuel chez le personnage (points et
    bonus des objets), évaluée même au niveau 0 si le personnage ne l'a pas (D2Common.dll 0x6fda1af0 : niveau 0 puis
    évaluateur des variables ; ✅ Blood Skeleton, coût en mana : skill(1819, clc2) = 1 en ville, 49 dehors) ; la compétence
    elle-même : à son niveau."""
    other, ref = pop(2)
    if other == skill:
        return calc.ref(ref, skill, lvl, char)
    if char is None:
        raise Unsupported(f'skill({other})', kind='skill(compétence avec points)')
    if not getattr(char, 'pools', None):
        # autre compétence (souvent une compétence interne de calcul, ex. 1820) : vie / mana actuelles au repos, pleines
        # (une lecture directe par la ligne elle-même reste un taux de conversion : mxl_skill_lines.pool_rate_line)
        char = PoolProbe(char, {6: char.stat(7), 8: char.stat(9)})
    return calc.ref(ref, other, char.skill_level(other), char)


def _stat(calc, name, pop, skill, lvl, char):
    """stat(n°, mode), lstat(n°, mode, param) (D2Common.dll 0x6fda0c30, D2Sigma.dll 0x100a6970) : mode 1 = valeur de
    base (sans les objets, D2Common.dll 10587), sinon total (10973) ; stat 19 (Attack Rating) : calcul dédié du jeu
    (D2Common.dll 10621), inconnu. Stat cachée : valeur au repos (objets + passifs, aucune aura ni effet temporaire
    actif), connue si le jeu lui connaît une source (sourced_stats)."""
    sid, mode, param = pop(2) + [None] if name == 'stat' else pop(3)
    if sid in getattr(char, 'pools', {}):   # vie / mana actuelles imposées (taux de conversion, PoolProbe)
        return char.pools[sid]
    if sid == STAT_ATTACK_RATING or sid not in calc.data.isc or sid not in calc.sourced_stats():
        raise Unsupported(f'{name}({sid})', stat=sid)
    try:
        return char.base_stat(sid, param) if mode == 1 else char.stat(sid, param)
    except KeyError:
        raise Unsupported(f'{name}({sid})', stat=sid)


def _miss(calc, name, pop, skill, lvl, char):
    """miss(projectile, variable de misscalc.bin) : missiles.bin (D2Common.dll 0x6fdba790)."""
    missile, var = pop(2)
    return M.missile_value(calc, missile, var, lvl)


def _state_func(calc, name, pop, skill, lvl, char):
    """state(état) : état actif (D2Sigma.dll 0x100a6aa0) ; au repos, états passifs seulement."""
    return int(char.has_state(pop(1)[0]))


def _with_char(fn):
    """Fonction qui demande un personnage de référence : sans lui, Unsupported(nom de la fonction)."""
    def handler(calc, name, pop, skill, lvl, char):
        if not char:
            raise Unsupported(name)
        return fn(calc, name, pop, skill, lvl, char)
    return handler


FUNCTIONS = {'min': _min_max, 'max': _min_max, 'skill': _skill, 'miss': _miss,
             'stat': _with_char(_stat), 'lstat': _with_char(_stat), 'state': _with_char(_state_func)}
