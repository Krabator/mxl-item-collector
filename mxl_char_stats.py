"""Statistiques totales d'un personnage (étape 2), sans interface (testable seul) : ce que le jeu additionne pour
lui, à partir de son fichier .d2s (mxl_save.load_character).

Sources prises en compte :
- attributs de base (Force, Dextérité, Vitalité, Énergie répartis : section 'gf') ;
- objets portés (jeu d'armes actif : toujours enregistré en 4 et 5, l'autre en 11 et 12), avec leur runeword
  et leurs objets sertis (mxl_tooltip.all_stats) ; objets dont le personnage ne remplit pas les exigences : ignorés ;
- charmes du sac (types « char » : « Keep in Inventory to Gain Bonus ») ;
- bonus de set : listes de l'objet (set_stats_n, actives à partir de n + 2 pièces portées) et bonus du set (sets.bin :
  partiels à 2 à 5 pièces, complet) — pas encore vérifié en jeu (aucun set porté) ;
- opérations de itemstatcost (op, op stat1-3), lues dans le jeu (D2Common.dll 0x6fd89530) : une stat source ajoute
  à sa stat cible (source × base) >> op_param (op 2 / 4 : par niveau, par point d'attribut ; vie / mana / résistances /
  Magic Find / dégâts de sort par niveau…), la valeur propre de la cible × source / 100 (op 11 : % de vie, de mana,
  des attributs, de Spell Focus) ou les points d'attribut venus des objets × vie / mana par point (op 8 / 9) ;
- auras données par les objets (stat 151, « Level x … Aura When Equipped » : toujours actives) : niveau = total de la
  stat 151 sur le porteur (les objets qui donnent la même aura s'additionnent ; +compétences sans effet : D2Game.dll
  0x6fcc37d0), stats d'aura (skills.bin aurastat1-6) évaluées avec les stats du porteur, et état d'aura ; aussi celles
  des objets portés par le mercenaire vivant (une aura touche les alliés à portée : personnage supposé près de lui),
  évaluées avec les stats du mercenaire (MercenaryStats) ; même aura des deux côtés : celle de plus haut niveau (règle confirmée en jeu) ;
  les auras de la classe (à choisir en jeu) ne comptent pas ; les mercenaires de Median XL n'ont pas d'aura à eux
  (aucune compétence de hireling.bin n'a le drapeau aura, bit 5 de skills.bin @0x04 : Dark Power, Lionheart… sont
  des sorts lancés) ;
- compétences passives (état passif défini dans skills.bin) du personnage et données par ses objets : stats passives
  (pst1-5) à leur niveau.
Niveau d'une compétence : points investis + « +x à toutes les compétences », « +x aux compétences de la classe »,
« +x à la compétence » (si au moins un point) + compétence donnée par un objet.

✅ Feuille de personnage de Nekratall en jeu (30/09) : attributs, résistances, vitesses, Magic / Gold Find, Spell
Focus, dégâts de sort, pénétrations, régénération de mana et % de vie (Embalming), vie des invocations.
Vie, mana, endurance maximales et défense (formules de classe, charstats.bin) : voir max_life, max_mana, max_stamina,
defense (✅ Nekratall : 874, 364, 50, 338) ; chance de blocage (block_chance, ✅ 1 %, formule et plafond de la documentation officielle).
"""
import stat_ids as S
from mxl_containers import place, INACTIVE_HANDS
from mxl_rules import item_type_codes, set_row, mods_stats
from mxl_tooltip import all_stats, requirements_unmet

ATTRIBUTES = (S.STRENGTH, S.ENERGY, S.DEXTERITY, S.VITALITY)
ALL_SKILLS, CLASS_SKILLS, SINGLE_SKILL, NONCLASS_SKILL = 127, 83, 107, 97   # +x aux compétences (itemstatcost)
from mxl_skill_data import (Unsupported, SKILL_PASSIVE_STATE, SKILL_PASSIVE_STATS, SKILL_PASSIVE_CALCS, NO_STATE,
                            NO_STAT, NO_CALC, SKILL_AURA_STATS, SKILL_AURA_CALCS, SKILL_STATE_FIELDS, muldiv)
# skills.bin : état passif u16, stats 5 × u16, formules 5 × u32 ; aura : stats 6 × u16 (@0x54), formules 6 × u32, état
SKILL_AURA_STATE = SKILL_STATE_FIELDS[90]
ITEM_AURA = 151        # « Level x <aura> Aura When Equipped » : param = compétence, valeur = niveau
# opérations (itemstatcost op) évaluées sur le personnage ; les autres agissent sur l'objet lui-même (1, 3, 5, 13 :
# défense, dégâts, durabilité de l'objet : defense()) ou dans le temps (6, 7)
PER_BASE_OPS, ATTRIBUTE_OPS, PERCENT_OP = (2, 4), (8, 9), 11
ITEM_TARGETS = frozenset((21, 22, 23, 24, 31, 159, 160))   # dégâts et défense de l'objet (op 4 sur l'objet)
DEF_PER_LEVEL, ED_PER_LEVEL = 214, 215                    # défense, % de défense par niveau (op 4 / 5 sur l'objet)
# charstats.bin (une ligne par classe) : vie par point de Vitalité, endurance par Vitalité, mana par point d'Énergie
# (u8, en quarts)
CHARSTATS_LIFE_PER_VIT, CHARSTATS_STAMINA_PER_VIT, CHARSTATS_MANA_PER_ENERGY = 0x46, 0x47, 0x48
LIFE, MAX_LIFE, MANA, MAX_MANA, STAMINA, MAX_STAMINA = 6, 7, 8, 9, 10, 11   # enregistrées en 256es
MAX_LIFE_PCT, MAX_MANA_PCT = 76, 77
BASE_ONLY = frozenset((4, 5, 12, 13, 14, 15))   # points d'attributs / de compétences à répartir, niveau, expérience, or
MAX_BLOCK = 213                 # « Maximum Block Chance » : relève le plafond de la chance de blocage
# plafond de la chance de blocage : 50 %, « can be increased up to 80% » (docs.median-xl.com/doc/concepts/defense)
BLOCK_CAP, BLOCK_CAP_MAX = 50, 80
BONUS_DEFENSE, STAT_TOTAL_DEFENSE_PCT = 171, 182   # % de la défense totale (D2Common.dll 10672)


class CharacterStats:
    """Totaux du personnage char : stat(n°, param), skill_level(n° de compétence)."""

    def __init__(self, char, data):
        self.char, self.data = char, data
        self.items = self.active_items()
        self.totals = {}       # (stat, param) -> valeur propre des objets, des auras et des passifs (sans opérations)
        self.auras = {}        # aura donnée par les objets de ce porteur -> niveau (total de la stat 151)
        for it in self.items:
            self.add(all_stats(it, data))
        self.add(self.set_bonuses())
        # aura -> {(stat, param): valeur} : celles de ce porteur, puis celles du mercenaire (plus haut niveau gardé)
        self.aura_stats = self.item_aura_stats()
        self.aura_levels = dict(self.auras)
        self.mercenary = self.mercenary_stats()
        if self.mercenary is not None:
            for sid, stats in self.mercenary.aura_stats.items():
                if self.mercenary.auras[sid] > self.aura_levels.get(sid, 0):
                    self.aura_stats[sid], self.aura_levels[sid] = stats, self.mercenary.auras[sid]
        for stats in self.aura_stats.values():
            for key, v in stats.items():
                self.totals[key] = self.totals.get(key, 0) + v
        self.passives = self.passive_stats()   # compétence -> {(stat, param): valeur}
        for stats in self.passives.values():
            for key, v in stats.items():
                self.totals[key] = self.totals.get(key, 0) + v

    # ---------- sources ----------
    def active_items(self):
        """Objets qui comptent : portés (jeu d'armes actif) et charmes du sac, exigences remplies."""
        out = []
        for it in self.char['items']:
            where = place(it)
            if where == 'equipped' and it['equipped'] in INACTIVE_HANDS:
                continue
            if where == 'inventory' and 'char' not in item_type_codes(it, self.data):
                continue
            if where in ('equipped', 'inventory') and not requirements_unmet(it, self.data, self.char):
                out.append(it)
        return out

    def add(self, stats):
        for s in stats:
            key = (s['id'], s.get('param'))
            if s['id'] == ITEM_AURA:   # niveau = total sur le porteur (D2Game.dll 0x6fcc37d0)
                self.auras[s['param']] = self.auras.get(s['param'], 0) + s['value']
                continue
            self.totals[key] = self.totals.get(key, 0) + s['value']

    def mercenary_stats(self):
        """Statistiques du mercenaire vivant (MercenaryStats), ou None : seules ses auras touchent le personnage."""
        merc = self.char.get('mercenary')
        if not merc or merc.get('dead'):
            return None
        return MercenaryStats(merc, self.data)

    def set_bonuses(self):
        """Stats des bonus de set : listes propres aux objets portés (set_stats_n à partir de n + 2 pièces) et bonus
        du set (partiels selon le nombre de pièces, complet si toutes les pièces sont portées)."""
        worn = [it for it in self.items if place(it) == 'equipped']
        by_set = {}
        for it in worn:
            row = set_row(it, self.data)
            if row is not None:
                by_set.setdefault(row['set_id'], []).append(it)
        out = []
        for set_id, pieces in by_set.items():
            n = len({(it['code'], it.get('set_unique_id')) for it in pieces})
            for it in pieces:
                for k in range(5):
                    if n >= k + 2:
                        out += it.get(f'set_stats_{k}') or []
            if 0 <= set_id < len(self.data.sets):
                s = self.data.sets[set_id]
                mods = [m for count, ms in s['partial'].items() if n >= count for m in ms]
                total = sum(1 for r in self.data.set_items if r['set_id'] == set_id)
                if n >= total:
                    mods += s['full']
                out += mods_stats([(m['prop'], m['param'], m['min'], m['max']) for m in mods], self.data, 'min')
        return out

    def item_aura_stats(self):
        """Stats des auras données par les objets (toujours actives : aurastat1-6 de skills.bin à leur niveau) :
        {aura: {(stat, None): valeur}} ; une stat dont la formule dépend d'une valeur inconnue est omise."""
        from mxl_skill_calc import skill_calc
        calc = skill_calc(self.data)
        out = {}
        for sid, lvl in self.auras.items():
            if not 0 <= sid < len(calc.skills) or lvl <= 0:
                continue
            r = calc.rec(sid)
            stats = {}
            for stat, off in zip(r.u16s(SKILL_AURA_STATS, 6), r.u32s(SKILL_AURA_CALCS, 6)):
                if stat == NO_STAT or off == NO_CALC:
                    continue
                try:
                    stats[(stat, None)] = stats.get((stat, None), 0) + calc.skill_calc(sid, off, lvl, self)
                except Unsupported:
                    pass
            out[sid] = stats
        return out

    # ---------- opérations de itemstatcost (D2Common.dll 0x6fd89530) ----------
    def own(self, sid):
        """Valeur propre d'une stat, en unités du jeu (× 2^ValShift : vie, mana en 256es) : valeur enregistrée dans la
        sauvegarde (section 'gf') + valeurs des objets, auras et passifs, sans les opérations."""
        items = self.totals.get((sid, None), 0) + self.totals.get((sid, 0), 0)
        return self.char['base_stats'].get(sid, 0) + items * (1 << self.data.isc[sid]['shift'] if sid in self.data.isc else 1)

    def op_bonus(self, target, own):
        """Part ajoutée à la stat target (de valeur propre own, en unités du jeu) par les stats qui la visent :
        op 2 / 4 : (source × base) >> op_param, base = niveau, attribut ou autre stat (> 0) ; op 8 / 9 : points d'attribut
        au-delà de ceux enregistrés × mana (Énergie) ou vie / endurance (Vitalité) par point de la classe, en quarts
        (<< 6 : 256es) ; op 11 : own × source / 100. Sources en unités du jeu (valeur << ValShift)."""
        if target in ITEM_TARGETS:
            return 0
        isc, total = self.data.isc, 0
        for src in self.data.op_sources.get(target, ()):
            c = isc[src]
            if c['op'] in ATTRIBUTE_OPS:   # 8 : Énergie -> mana ; 9 : Vitalité -> vie (endurance : 2e colonne)
                gained = self.attribute(src) - self.char['base_stats'].get(src, 0)
                col = (CHARSTATS_MANA_PER_ENERGY if c['op'] == 8 else
                       CHARSTATS_STAMINA_PER_VIT if target == MAX_STAMINA else CHARSTATS_LIFE_PER_VIT)
                total += gained * self.class_row()[col] << 6
                continue
            value = self.totals.get((src, None), 0) << c['shift']
            if not value:
                continue
            if c['op'] in PER_BASE_OPS:
                base = self.char['level'] if c['op_base'] == S.LEVEL else self.base_value(c['op_base'])
                if base > 0:
                    total += (value * base) >> c['op_param']
            elif c['op'] == PERCENT_OP and own:
                total += muldiv(own, value, 100)
        return total

    def base_value(self, sid):
        """Base d'une opération par point (op 2 / 4) : valeur propre de la stat (attribut : base + objets)."""
        return self.own(sid) >> self.data.isc[sid]['shift'] if sid in self.data.isc else 0

    def total(self, sid):
        """Valeur d'une stat avec ses opérations, en unités du jeu."""
        own = self.own(sid)
        return own + self.op_bonus(sid, own)

    def passive_skills(self):
        """Compétences passives actives (état passif défini, niveau > 0) du personnage et de ses objets :
        {compétence: (niveau, état passif)}."""
        if getattr(self, '_passives', None) is None:
            from mxl_skill_calc import skill_calc
            calc = skill_calc(self.data)
            out = {}
            candidates = set(self.char['skills']) | {p for (sid, p) in self.totals if sid == NONCLASS_SKILL and p is not None}
            for sid in sorted(candidates):
                if sid >= len(calc.skills):
                    continue
                state = calc.rec(sid).u16(SKILL_PASSIVE_STATE)
                lvl = self.skill_level(sid) if state != NO_STATE else 0
                if lvl > 0:
                    out[sid] = (lvl, state)
            self._passives = out
        return self._passives

    def has_state(self, state):
        """État actif au repos : états passifs des compétences et états des auras données par les objets (aucune aura
        de la classe ni effet temporaire)."""
        if any(st == state for _, st in self.passive_skills().values()):
            return True
        auras = getattr(self, 'aura_levels', None) or getattr(self, 'auras', None)
        if not auras:
            return False
        from mxl_skill_calc import skill_calc
        calc = skill_calc(self.data)
        return any(0 <= sid < len(calc.skills) and calc.rec(sid).u16(SKILL_AURA_STATE) == state for sid in auras)

    def base_stat(self, sid, param=None):
        """Valeur de base d'une stat (sans les objets : section 'gf' de la sauvegarde ; D2Common.dll 10587)."""
        return self.char['base_stats'].get(sid, 0) if param in (None, 0) else 0

    def passive_stats(self):
        """Stats données par les compétences passives (état passif défini) du personnage et celles données par ses
        objets, à leur niveau : {compétence: {(stat, param): valeur}} ; une stat dont la formule dépend d'une valeur
        inconnue est omise."""
        from mxl_skill_calc import skill_calc
        calc = skill_calc(self.data)
        out = {}
        for sid, (lvl, _) in self.passive_skills().items():
            r = calc.rec(sid)
            stats = {}
            for stat, off in zip(r.u16s(SKILL_PASSIVE_STATS, 5), r.u32s(SKILL_PASSIVE_CALCS, 5)):
                if stat == NO_STAT or off == NO_CALC:
                    continue
                try:
                    stats[(stat, None)] = calc.skill_calc(sid, off, lvl, self)
                except Unsupported:
                    pass
            out[sid] = stats
        return out

    # ---------- lecture ----------
    def stat(self, sid, param=None):
        """Total d'une stat (0 si aucune source). Vie, mana, endurance (actuelles = maximales) : en 256es, comme le jeu
        les enregistre (les formules divisent par 256) ; défense (31) : défense totale."""
        if sid in (LIFE, MAX_LIFE, MANA, MAX_MANA, STAMINA, MAX_STAMINA):
            value = {LIFE: self.max_life, MAX_LIFE: self.max_life, MANA: self.max_mana, MAX_MANA: self.max_mana,
                     STAMINA: self.max_stamina, MAX_STAMINA: self.max_stamina}[sid]()
            return int(value * 256)
        if sid == S.DEFENSE:
            return self.defense()
        if sid in ATTRIBUTES:
            return self.attribute(sid)
        if sid in BASE_ONLY:   # stats de la section 'gf' : points à répartir, niveau, expérience, or
            return self.char['base_stats'].get(sid, 0)
        if param is not None:
            return self.totals.get((sid, param), 0)
        value = self.totals.get((sid, None), 0) + self.totals.get((sid, 0), 0)
        if sid in self.data.op_sources and sid in self.data.isc:   # opérations (par niveau, %…)
            shift = self.data.isc[sid]['shift']
            value += self.op_bonus(sid, value << shift) >> shift
        return value

    def attribute(self, sid):
        """Attribut total : base (points répartis) + objets + opérations (« +x% to Strength » : op 11, % de la valeur
        propre ; « +x to Energy (Based on Character Level) » : op 2)."""
        return self.total(sid)

    # ---------- formules de classe ----------
    def class_row(self):
        return self.data._rows('charstats')[self.char['cls']]

    def base(self, sid):
        """Valeur enregistrée dans le fichier (section 'gf') : vie, mana, endurance de base en 256es."""
        return self.char['base_stats'].get(sid, 0)

    def max_life(self):
        """Vie maximale (opérations du jeu, en 256es) : valeur propre (base enregistrée : niveau et Vitalité répartie, +
        vie des objets) + % de vie de la valeur propre (op 11) + vie par niveau (op 2 : valeur × niveau / 32) +
        Vitalité au-delà de celle enregistrée × vie par Vitalité de la classe (op 9) (✅ Nekratall : 731,25 + 14 % + 27 ×
        1,5 = 874)."""
        return self.total(MAX_LIFE) / 256

    def max_mana(self):
        """Mana maximale : comme la vie, avec le % de mana, la mana par niveau et l'Énergie au-delà de celle enregistrée
        × mana par Énergie de la classe (op 8) (✅ Nekratall : 255 + 58 + 17 × 3 = 364)."""
        return self.total(MAX_MANA) / 256

    def max_stamina(self):
        """Endurance maximale : valeur propre + Vitalité au-delà de celle enregistrée × endurance par Vitalité (op 9)."""
        return self.total(MAX_STAMINA) / 256

    def defense(self):
        """Défense totale : défense de chaque objet porté (stockée × (100 + ED de l'objet) / 100 + défense plate de
        l'objet, comme son infobulle) + Dextérité / 4 (✅ Nekratall : 328 + 10 = 338)."""
        total = 0
        for it in self.items:
            if place(it) != 'equipped':
                continue
            ids = {}
            for s in all_stats(it, self.data):
                ids[s['id']] = ids.get(s['id'], 0) + s['value']
            # défense et % de défense par niveau (op 4 / 5 sur l'objet : (valeur × niveau) >> op_param)
            lvl = self.char['level']
            per = {sid: (ids.get(sid, 0) * lvl) >> self.data.isc[sid]['op_param'] for sid in (DEF_PER_LEVEL, ED_PER_LEVEL)}
            if 'defense' in it:
                total += it['defense'] * (100 + ids.get(S.ENH_DEFENSE, 0) + per[ED_PER_LEVEL]) // 100
            total += ids.get(S.DEFENSE, 0) + per[DEF_PER_LEVEL]
        total += self.attribute(S.DEXTERITY) // 4
        # % de la défense totale (D2Common.dll 10672) : « Bonus to Defense » (stat 171 : objets, compétences, ✅ Kalidor,
        # Lionheart +186 % : 848 -> 2425 comme sa feuille en jeu), puis stat 182 en dernier (Rust Storm)
        total += muldiv(total, self.stat(BONUS_DEFENSE), 100)   # division vers zéro, comme le jeu
        return total + muldiv(total, self.stat(STAT_TOTAL_DEFENSE_PCT), 100)

    def shield(self):
        """Bouclier porté (jeu d'armes actif) ou None. Un bouclier ordinaire a 0 % de blocage, un bouclier de classe
        1 % (documentation) : il permet quand même de bloquer (bonus de la classe et des objets)."""
        return next((it for it in self.items if place(it) == 'equipped' and it['equipped'] in (4, 5)
                     and 'shld' in item_type_codes(it, self.data)), None)

    def base_block_chance(self):
        """« Base Block Chance » de la feuille de personnage : blocage du bouclier + « Base Block Chance » des objets
        (stat 20) ; 0 sans bouclier (✅ Nekratall : 1 %)."""
        sh = self.shield()
        return self.data.base(sh['code']).block + self.totals.get((S.BASE_BLOCK, None), 0) if sh else 0

    def block_chance(self):
        """Chance de blocage (docs.median-xl.com/doc/concepts/defense, formule de Diablo II) : (base + bonus de blocage
        de la classe : 3 % Amazone, Assassin, Druide, Sorcière, 1 % Nécromancien, Paladin, 0 % Barbare) × (Dextérité −
        15) / (2 × niveau), arrondie vers le bas, entre 0 et le plafond (50 % + « Maximum Block Chance », au plus 80 %) ;
        0 sans bouclier. ✅ Nekratall niveau 24, Dextérité 42, Gargoyle Head (1) + nécromancien (1) : 2 × 27 / 48 = 1 %."""
        if self.shield() is None:
            return 0
        blocking = self.base_block_chance() + self.data.block_factor[self.char['cls']]
        value = blocking * (self.attribute(S.DEXTERITY) - 15) // (2 * max(self.char['level'], 1))
        cap = min(BLOCK_CAP + self.totals.get((MAX_BLOCK, None), 0), BLOCK_CAP_MAX)
        return max(0, min(value, cap))

    def skill_level(self, sid):
        """Niveau actuel d'une compétence : points investis et bonus des objets s'il y a au moins un point (règle du jeu),
        plus le niveau donné directement par un objet (compétence d'une autre classe ou sans classe)."""
        pts = self.char['skills'].get(sid, 0)
        lvl = pts
        if pts:
            lvl += (self.totals.get((ALL_SKILLS, None), 0) + self.totals.get((CLASS_SKILLS, self.char['cls']), 0)
                    + self.totals.get((SINGLE_SKILL, sid), 0))
        return lvl + self.totals.get((NONCLASS_SKILL, sid), 0)


def with_total_attributes(char, data):
    """Attributs du personnage (char['strength'], 'dexterity', 'energy', 'vitality', lus par les exigences) remplacés
    par ses totaux (CharacterStats : objets portés, charmes, passifs, %), au lieu de base + objets portés de la lecture
    de la sauvegarde (✅ Nekratall : Force 39 -> 42, celle de sa feuille en jeu). Renvoie char (modifié sur place)."""
    cs = character_stats(char, data)
    for key, sid in (('strength', S.STRENGTH), ('dexterity', S.DEXTERITY), ('energy', S.ENERGY),
                     ('vitality', S.VITALITY)):
        char[key] = cs.attribute(sid)
    return char


def hireling_rows(merc, data):
    """Lignes de hireling.bin du type du mercenaire (Id enregistré dans la sauvegarde), par niveau croissant."""
    return sorted((r for r in data.hirelings if r['id'] == merc['type']), key=lambda r: r['level'])


def mercenary_level(merc, data):
    """Niveau du mercenaire d'après son expérience : le plus haut L tel que ExpPerLvl × L² × (L + 1) <= expérience
    (D2Common.dll 10448 ; ✅ mercenaire de Nekratall : 14 414 -> 24)."""
    rows = hireling_rows(merc, data)
    per = rows[0]['exp_per_level'] if rows else 0
    if per <= 0:
        return 1
    level = 1
    while per * (level + 1) ** 2 * (level + 2) <= merc.get('experience', 0) and level < 999:
        level += 1
    return level


class MercenaryStats(CharacterStats):
    """Statistiques du mercenaire : niveau (expérience), Force, Dextérité, vie de hireling.bin (ligne de son type
    dont la tranche de niveau est atteinte, d = niveau − niveau de la ligne : Force = max(10, Str + StrPerLvl × d / 8),
    Dextérité de même, vie = max(40, Hp + HpPerLvl × d) : D2Game.dll 0x6fc68d9a), objets portés (sans contrôle des
    exigences : le jeu ne les lui laisse pas porter sinon) ; pas de classe (aucun attribut -> vie / mana), pas de
    compétences investies ni de mercenaire."""

    def __init__(self, merc, data):
        level = mercenary_level(merc, data)
        rows = [r for r in hireling_rows(merc, data) if r['level'] <= level] or hireling_rows(merc, data)[:1]
        base = {12: level}
        if rows:
            r, d = rows[-1], level - rows[-1]['level']
            per8 = lambda v: int(v * d / 8)   # division entière vers zéro (D2Game : cdq / and 7 / sar 3)
            base[0] = max(10, r['strength'] + per8(r['strength_per_level']))
            base[2] = max(10, r['dexterity'] + per8(r['dexterity_per_level']))
            base[7] = base[6] = max(0x2800, (r['life'] << 8) + (r['life_per_level'] << 8) * d)
        char = dict(cls=None, level=level, skills={}, items=merc.get('items') or [], base_stats=base, mercenary=None,
                    strength=base.get(0, 0), dexterity=base.get(2, 0), energy=0, vitality=0)
        super().__init__(char, data)

    def active_items(self):
        return [it for it in self.char['items'] if place(it) == 'equipped' and it['equipped'] not in INACTIVE_HANDS]

    def class_row(self):
        return bytes(0x100)   # pas de classe : aucune vie / mana / endurance par point d'attribut


_CACHE = {}


def character_stats(char, data):
    """CharacterStats du personnage char (gardé tant que c'est le même personnage lu)."""
    key = (id(char), id(data))
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = (char, data, CharacterStats(char, data))
    return _CACHE[key][2]
