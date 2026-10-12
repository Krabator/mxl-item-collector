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
import struct
import stat_ids as S
from mxl_containers import place, ACTIVE_HANDS, INACTIVE_HANDS
from mxl_rules import item_type_codes, set_row, mods_stats, ethereal_base
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
# résistances de la feuille : stat -> stat de résistance maximale ; plafond de base 75 % ; la pénalité de difficulté
# (difficultylevels.bin, 1re colonne : 0 / -30 / -70) touche aussi la Poison Length Reduction (stat 110 ; ✅ Kalidor en
# Hell : -70 % sur sa feuille, 11/10)
RESISTS = {39: 40, 41: 42, 43: 44, 45: 46}
RESIST_CAP, POISON_LENGTH = 75, 110
# plafonds appliqués aux dégâts subis (D2Game.dll 0x6fcfb3c0, joueurs et mercenaires seulement : D2Common 11104 ;
# invocations et monstres : aucun plafond ni pénalité) : élémentaires et magie (Magic Resist 37, maximum 38, sans
# pénalité de difficulté) : 75 % + maximum, au plus 90 % (95 dans D2Game, 90 écrit par D2Sigma en 0x6fcfb468 /
# 0x6fcfb46c) ; Physical Resist (36, sans maximum ni pénalité) : 50 %
PHYSICAL_RESIST, MAGIC_RESIST, MAX_MAGIC_RESIST = 36, 37, 38
SENT_PER_SOURCE = frozenset((333, 334, 335, 336))   # pierces : bornés par source sur la feuille (shown_stat)
RESIST_CAP_MAX, PHYSICAL_RESIST_CAP = 90, 50
BASE_ONLY = frozenset((4, 5, 12, 13, 14, 15))   # points d'attributs / de compétences à répartir, niveau, expérience, or
MAX_BLOCK = 213                 # « Maximum Block Chance » : relève le plafond de la chance de blocage
# plafond de la chance de blocage : 50 %, « can be increased up to 80% » (docs.median-xl.com/doc/concepts/defense)
BLOCK_CAP, BLOCK_CAP_MAX = 50, 80
BONUS_DEFENSE, STAT_TOTAL_DEFENSE_PCT = 171, 182   # % de la défense totale (D2Common.dll 10672)
WEAPON_ELEMENTS = (48, 49, 54, 55, 50, 51, 57, 58, 52, 53)   # dégâts élémentaires min / max (feu, froid, foudre, poison, magie)
WEAPON_PHYSICAL = 25   # « Weapon Physical Damage +x% » (W. Physical Damage de la feuille : tous les objets)
BARBARIAN = 4          # seule classe qui manie les épées à deux mains à une main


class CharacterStats:
    """Totaux du personnage char : stat(n°, param), skill_level(n° de compétence)."""

    def __init__(self, char, data, other_set=False):
        """other_set : avec l'autre jeu d'armes que celui du jeu (emplacements 11 et 12 à la place de 4 et 5)."""
        self.char, self.data = char, data
        self.hands = INACTIVE_HANDS if other_set else ACTIVE_HANDS   # emplacements des armes comptées
        # objets actifs : exigences évaluées sur les attributs totaux (objets compris), comme le jeu ; point fixe : tous
        # les objets possibles comptés, puis ceux dont les exigences ne sont plus remplies retirés, jusqu'à stabilité
        # (✅ Pala, 11/10 : 9 objets Sacred sur 12 ignorés avec la Force lue dans la sauvegarde, 136 au lieu de 2 287)
        self.items = self.active_items()
        for _ in range(10):
            self.compute()
            usable = self.usable(self.items)
            if len(usable) == len(self.items):
                break
            self.items = usable

    def compute(self):
        """Totaux des objets self.items, des bonus de set, des auras et des passives."""
        data = self.data
        self._passives = None
        self.totals = {}       # (stat, param) -> valeur propre des objets, des auras et des passifs (sans opérations)
        self.auras = {}        # aura donnée par les objets de ce porteur -> niveau (total de la stat 151)
        self.item_sources = []   # {(stat, param): valeur} de chaque objet et des bonus de set (sources de shown_stat)
        for it in self.items:
            self.item_sources.append(self.add(all_stats(it, data)))
        self.item_sources.append(self.add(self.set_bonuses()))
        # stats en unités du jeu données par les auras et les passives (vie, mana, endurance : en 256es, comme les
        # formules des compétences les écrivent ; ✅ aura d'Azurewrath de Pala, 11/10 : -230 × Vitalité 256es de vie)
        self.raw = {}
        # aura -> {(stat, param): valeur} : celles de ce porteur, puis celles du mercenaire (plus haut niveau gardé)
        self.aura_stats = self.item_aura_stats()
        self.aura_levels = dict(self.auras)
        self.mercenary = self.mercenary_stats()
        merc = set()
        if self.mercenary is not None:
            for sid, stats in self.mercenary.aura_stats.items():
                if self.mercenary.auras[sid] > self.aura_levels.get(sid, 0):
                    self.aura_stats[sid], self.aura_levels[sid] = stats, self.mercenary.auras[sid]
                    merc.add(sid)
        self.add_skill_stats(self.aura_stats.values())
        self.passives = self.passive_stats()   # compétence -> {(stat, param): valeur}
        self.add_skill_stats(self.passives.values())
        # 2e passage : formules des passives et des auras du porteur relues avec les stats complètes (le jeu les
        # calcule sur le personnage complet ; ✅ Grit de Kalidor, 11/10 : 15 % au 1er passage, 24 % en jeu avec Dragon's
        # Blessing ; aura d'Azurewrath de Pala : vie et dégâts de froid selon la Vitalité finale)
        again = self.passive_stats()
        auras = {sid: st for sid, st in self.item_aura_stats().items() if sid not in merc}
        self.add_skill_stats(self.passives.values(), -1)
        self.add_skill_stats([self.aura_stats[sid] for sid in auras], -1)
        self.add_skill_stats(again.values())
        self.add_skill_stats(auras.values())
        self.passives = again
        self.aura_stats.update(auras)

    def add_skill_stats(self, sources, sign=1):
        """Ajoute (sign 1) ou retire (-1) des stats d'auras ou de passives : vie, mana, endurance (ValShift) en
        unités du jeu dans raw, les autres dans totals."""
        for stats in sources:
            for key, v in stats.items():
                if key[1] is None and self.data.isc.get(key[0], {}).get('shift'):
                    self.raw[key[0]] = self.raw.get(key[0], 0) + sign * v
                else:
                    self.totals[key] = self.totals.get(key, 0) + sign * v

    # ---------- sources ----------
    def active_items(self):
        """Objets qui peuvent compter : portés (jeu d'armes actif) et charmes du sac (exigences : usable)."""
        out = []
        for it in self.char['items']:
            where = place(it)
            if where == 'equipped' and it['equipped'] in set(ACTIVE_HANDS + INACTIVE_HANDS) - set(self.hands):
                continue
            if where == 'inventory' and 'char' not in item_type_codes(it, self.data):
                continue
            if where in ('equipped', 'inventory'):
                out.append(it)
        return out

    def usable(self, items):
        """Objets dont les exigences sont remplies par les attributs totaux actuels (objets compris)."""
        char = dict(self.char, strength=self.attribute(S.STRENGTH), dexterity=self.attribute(S.DEXTERITY),
                    energy=self.attribute(S.ENERGY), vitality=self.attribute(S.VITALITY))
        return [it for it in items if not requirements_unmet(it, self.data, char)]

    def add(self, stats):
        """Ajoute des stats aux totaux ; renvoie leurs valeurs par (stat, param) (une source pour shown_stat)."""
        own = {}
        for s in stats:
            key = (s['id'], s.get('param'))
            if s['id'] == ITEM_AURA:   # niveau = total sur le porteur (D2Game.dll 0x6fcc37d0)
                self.auras[s['param']] = self.auras.get(s['param'], 0) + s['value']
                continue
            self.totals[key] = self.totals.get(key, 0) + s['value']
            own[key] = own.get(key, 0) + s['value']
        return own

    def mercenary_stats(self):
        """Statistiques du mercenaire vivant (MercenaryStats), ou None : seules ses auras touchent le personnage."""
        merc = self.char.get('mercenary')
        if not merc or merc.get('dead'):
            return None
        return MercenaryStats(merc, self.data, self.char.get('difficulty') or 0)

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
        return (self.char['base_stats'].get(sid, 0) + self.raw.get(sid, 0)
                + items * (1 << self.data.isc[sid]['shift'] if sid in self.data.isc else 1))

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

    def shown_stat(self, sid, param=None):
        """Valeur affichée par la feuille du jeu. Pierces élémentaires (SENT_PER_SOURCE) : chaque source (objet,
        bonus de set, aura, passive) bornée à sa largeur d'envoi (SendBits, itemstatcost @0x08, signée si drapeau 0x2 :
        9 bits, -256 à 255), puis additionnées (✅ pierce feu de Kalidor : Consecration -666 -> -256, + Sunstone 5 =
        -251 en jeu ; valeur réelle -661). Pas une règle générale : Mana on Melee Attack de Kalidor (6 bits) vaut 100 sur
        sa feuille, pas 63. Autres stats : stat()."""
        c = self.data.isc.get(sid)
        bits = c and c.get('send_bits')
        if sid not in SENT_PER_SOURCE or not bits or bits >= 32:
            return self.stat(sid, param)
        lo, hi = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if c['signed'] else (0, (1 << bits) - 1)
        sources = self.stat_sources()
        keys = [(sid, param)] if param is not None else [(sid, None), (sid, 0)]
        return sum(max(lo, min(hi, src.get(k, 0))) for src in sources for k in keys)

    def stat_sources(self):
        """Sources des stats, chacune {(stat, param): valeur} : objets, bonus de set, auras, passives."""
        return self.item_sources + list(self.aura_stats.values()) + list(self.passives.values())

    def difficulty_penalty(self):
        """Pénalité de résistance de la difficulté en cours du personnage (difficultylevels.bin : 0, -30, -70)."""
        rows = self.data._rows('difficultylevels')
        d = self.char.get('difficulty') or 0
        return struct.unpack_from('<i', rows[d], 0)[0] if 0 <= d < len(rows) else 0

    def resist_cap(self, sid):
        """Plafond d'une résistance (voir RESIST_CAP_MAX) : élémentaire ou magie : 75 % + résistance maximale, au plus
        90 % ; physique : 50 % ; autre stat : None."""
        if sid in RESISTS or sid == MAGIC_RESIST:
            return min(RESIST_CAP + self.stat(RESISTS.get(sid, MAX_MAGIC_RESIST)), RESIST_CAP_MAX)
        return PHYSICAL_RESIST_CAP if sid == PHYSICAL_RESIST else None

    def shown_resist(self, sid):
        """Résistance de la feuille du jeu : cumulée (stat) + pénalité de difficulté, plafonnée (resist_cap) ; magie et
        physique : sans pénalité, plafonnées ; Poison Length Reduction (stat 110) : + pénalité, sans plafond ; autres
        stats : stat."""
        if sid in RESISTS:
            return min(self.resist_cap(sid), self.stat(sid) + self.difficulty_penalty())
        if sid in (MAGIC_RESIST, PHYSICAL_RESIST):
            return min(self.resist_cap(sid), self.stat(sid))
        if sid == POISON_LENGTH:
            return self.stat(sid) + self.difficulty_penalty()
        return self.stat(sid)

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
        l'objet, comme son infobulle), défense plate des charmes actifs du sac (✅ Kalidor, 11/10 : Visions of Akarat
        +250, Horazon's Focus -50 ; sans eux, 320 de moins que sa feuille) + Dextérité / 4 (✅ Nekratall : 328 + 10 =
        338)."""
        total = self.base_defense()
        for it in self.items:   # objets portés (jeu d'armes actif) et charmes du sac, exigences remplies
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

    def base_defense(self):
        """Défense propre au porteur, hors objets : 0 (personnage)."""
        return 0

    def shield(self):
        """Bouclier porté (jeu d'armes actif) ou None. Un bouclier ordinaire a 0 % de blocage, un bouclier de classe
        1 % (documentation) : il permet quand même de bloquer (bonus de la classe et des objets)."""
        return next((it for it in self.items if place(it) == 'equipped' and it['equipped'] in self.hands
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
        return max(0, min(value, self.block_cap()))

    def weapon(self):
        """Arme du jeu d'armes actif (main droite, sinon main gauche), ou None."""
        hands = {it['equipped']: it for it in self.items if place(it) == 'equipped' and it['equipped'] in self.hands}
        return next((hands[n] for n in self.hands if n in hands and self.data.base(hands[n]['code']).damage), None)

    def damage_bonus(self, it=None):
        """(bonus de Force, bonus de Dextérité) en % de l'arme : attribut × coefficient de weapons.bin (u16 @0x106 /
        @0x108, en centièmes de % par point), arrondi vers le bas (✅ Kalidor, Faithshaker 0,18 : Force 2 770 -> 498 %)."""
        it = it or self.weapon()
        if it is None:
            return 0, 0
        sb, db = self.data.base(it['code']).dmg_bonus
        return self.attribute(S.STRENGTH) * sb // 100, self.attribute(S.DEXTERITY) * db // 100

    def sources(self, sid):
        """Sources d'une stat (sans param), dans l'ordre : [(genre, réf, valeur)] ; genre 'item' (réf : l'objet), 'set'
        (bonus de set), 'aura' / 'passive' (réf : n° de compétence), 'innate' (bonus inné du mercenaire), 'other' (reste
        du total : opérations par niveau…). Somme des valeurs = stat(sid)."""
        out = []
        for i, src in enumerate(self.item_sources):
            v = src.get((sid, None), 0) + src.get((sid, 0), 0)
            if v:
                out.append(('item', self.items[i], v) if i < len(self.items) else ('set', None, v))
        for kind, group in (('aura', self.aura_stats), ('passive', self.passives)):
            for skill, stats in group.items():
                v = stats.get((sid, None), 0)
                if v:
                    out.append((kind, skill, v))
        v = getattr(self, 'innate', {}).get(sid, 0)
        if v:
            out.append(('innate', None, v))
        rest = self.stat(sid) - sum(v for _, _, v in out)
        if rest:
            out.append(('other', None, rest))
        return out

    def weapons(self):
        """Armes du jeu d'armes compté, dans l'ordre de la feuille : main gauche puis main droite (une seule : [arme])."""
        hands = {it['equipped']: it for it in self.items if place(it) == 'equipped' and it['equipped'] in self.hands
                 and self.data.base(it['code']).damage}
        return [hands[n] for n in reversed(self.hands) if n in hands]

    def weapon_elemental(self, it):
        """Dégâts élémentaires d'une arme : {stat min / max: valeur} = ceux de l'arme + ceux des objets qui ne sont pas
        des armes portées (règle de Diablo II supposée pour deux armes : les dégâts propres d'une arme ne comptent que
        pour elle ; avec une seule arme : total du personnage)."""
        others = [w for w in self.weapons() if w is not it]
        out = {}
        for sid in WEAPON_ELEMENTS:
            out[sid] = self.stat(sid) - sum(s['value'] for w in others for s in all_stats(w, self.data) if s['id'] == sid)
        return out

    def element_detail(self, it, lo_id, hi_id):
        """Détail d'un élément d'une arme (« facture » de sa case) : dict added (dégâts ajoutés par les objets, bonus de
        set… : [(genre, réf, (min, max))], sans ceux des autres armes portées), added_total, innate (compétences
        cachées dont la formule est en % × attribut : [dict(skill, terms, total=(min, max))], terms = [(attribut, %,
        'innate' / 'synergy', valeur sans Innate Ele Damage, valeur)], result.
        Dégâts innés seulement si l'arme affiche un dégât inné (stat 415 : « Innate … Damage ») ; ses compétences en
        % × attribut : terme sur l'attribut de cette ligne « Weapon innate », sur un autre attribut « Weapon synergy »
        (rare : Azurewrath, 100 % de la Vitalité). Sinon, et pour les autres compétences (passive Ignis Fatuus, aura du
        mercenaire), dégâts ajoutés, sous leur nom. Termes : chaque attribut retiré tour à tour du calcul de la formule
        (✅ Azurewrath de Pala : 49 % Dex × 1,29 = 1 809 + 100 % Vit = 12 225 -> 14 534 - 14 784 comme en jeu)."""
        others = [w for w in self.weapons() if w is not it]
        inn = next((s['param'] for s in all_stats(it, self.data) if s['id'] == WEAPON_INNATE), None)
        innate_attr = None if inn is None else (inn or 0) >> 8   # param : élément + attribut × 256
        added, innate = {}, {}
        for k, sid in ((0, lo_id), (1, hi_id)):
            for kind, ref, v in self.sources(sid):
                if kind in ('aura', 'passive'):
                    innate.setdefault((kind, ref), [0, 0])[k] += v
                elif not any(ref is w for w in others):
                    key = (kind, id(ref) if kind == 'item' else ref)
                    added.setdefault(key, [kind, ref, [0, 0]])[2][k] += v
        added = [(kind, ref, tuple(v)) for kind, ref, v in added.values()]
        skills = []
        for (kind, sk), (lo, hi) in innate.items():
            own = kind == 'passive' or sk in self.auras
            terms = self.skill_terms(kind, sk, lo_id) if own and innate_attr is not None else []
            if terms:   # dégât inné de l'arme : % × attribut
                terms = [(a, pct, 'innate' if a == innate_attr else 'synergy', raw, part) for a, pct, raw, part in terms]
                skills.append(dict(skill=sk, kind=kind, terms=terms, total=(lo, hi)))
            else:       # compétence qui ajoute des dégâts fixes (passive Ignis Fatuus…) : avec les dégâts ajoutés
                added.append((kind, sk, (lo, hi)))
        total = (sum(v[0] for _, _, v in added), sum(v[1] for _, _, v in added))
        return dict(added=added, added_total=total, innate=skills,
                    result=(total[0] + sum(s['total'][0] for s in skills), total[1] + sum(s['total'][1] for s in skills)))

    def skill_terms(self, kind, sk, stat_id):
        """Termes « % × attribut (× (100 + Innate Ele Damage)) » de la formule d'une compétence cachée pour une stat :
        [(attribut, %, valeur sans Innate Ele Damage, valeur)]."""
        from mxl_skill_calc import skill_calc
        calc = skill_calc(self.data)
        r = calc.rec(sk)
        stats, calcs = ((r.u16s(SKILL_AURA_STATS, 6), r.u32s(SKILL_AURA_CALCS, 6)) if kind == 'aura'
                        else (r.u16s(SKILL_PASSIVE_STATS, 5), r.u32s(SKILL_PASSIVE_CALCS, 5)))
        off = next((o for st, o in zip(stats, calcs) if st == stat_id and o != NO_CALC), None)
        if off is None:
            return []
        lvl = self.aura_levels.get(sk, 1) if kind == 'aura' else self.passive_skills().get(sk, (1, 0))[0]

        def value(**hide):
            try:
                return calc.skill_calc(sk, off, lvl, _Masked(self, sk, **hide))
            except Unsupported:
                return None
        full, no_innate = value(), value(innate=True)
        if None in (full, no_innate):
            return []
        out = []
        for a in ATTRIBUTE_ORDER:
            part = full - (value(attr=a) or 0)
            if not part or not self.attribute(a):
                continue
            raw = no_innate - (value(attr=a, innate=True) or 0)
            out.append((a, round(raw * 100 / self.attribute(a), 1), raw, part))
        return out

    def weapon_damage_detail(self, it=None):
        """Détail des dégâts physiques de l'arme (« facture » de la feuille), ou None sans arme : dict weapon (l'objet),
        base (min, max de la table), ethereal (× 1,25, ou None), ed (Enhanced Damage de l'arme) et after_ed, weapon_flat
        (dégâts plats de l'arme), tooltip (= infobulle), flat (sources des dégâts plats hors arme : [(genre, réf, (min,
        max))]), damage (dégâts de l'arme + plats), percent (sources du multiplicateur : [(genre, réf, %)], genre
        'base' 100, sources de W. Physical Damage, 'strength' / 'dexterity' (réf : (attribut, coefficient))),
        multiplier (somme, en %), result (min, max). it : l'arme (par défaut celle de la main droite) ; dégâts plats des
        autres armes portées : locaux à elles, non comptés."""
        it = it or self.weapon()
        if it is None:
            return None
        others = [w for w in self.weapons() if w is not it]
        base = self.data.base(it['code'])
        two = base.two_handed and base.damage['two_hand'][1] and not (
            self.char.get('cls') == BARBARIAN and base.damage['one_hand'][1])
        lo, hi = base.damage['two_hand' if two else 'one_hand']
        fmin, fmax = (S.MIN_DAMAGE_2, S.MAX_DAMAGE_2) if two else (S.MIN_DAMAGE, S.MAX_DAMAGE)
        own = {}
        for s in all_stats(it, self.data):
            own[s['id']] = own.get(s['id'], 0) + s['value']
        ed = own.get(S.ENH_DAMAGE_MAX, 0)
        eth = (ethereal_base(lo, True), ethereal_base(hi, True)) if it.get('ethereal') else None
        elo, ehi = eth or (lo, hi)
        after = (elo * (100 + ed) // 100, ehi * (100 + ed) // 100)
        wflat = (own.get(fmin, 0), own.get(fmax, 0))
        flat = {}
        for k, stat in ((0, fmin), (1, fmax)):
            for kind, ref, v in self.sources(stat):
                if ref is it or any(ref is w for w in others):
                    continue
                key = (kind, id(ref) if kind == 'item' else ref)
                flat.setdefault(key, [kind, ref, [0, 0]])[2][k] += v
        flat = [(kind, ref, tuple(v)) for kind, ref, v in flat.values()]
        damage = (after[0] + wflat[0] + sum(v[0] for _, _, v in flat), after[1] + wflat[1] + sum(v[1] for _, _, v in flat))
        str_b, dex_b = self.damage_bonus(it)
        sb, db = base.dmg_bonus
        percent = [('base', None, 100)] + sorted(self.sources(WEAPON_PHYSICAL), key=lambda x: -x[2])
        if str_b:
            percent.append(('strength', (self.attribute(S.STRENGTH), sb), str_b))
        if dex_b:
            percent.append(('dexterity', (self.attribute(S.DEXTERITY), db), dex_b))
        pct = sum(v for _, _, v in percent)
        return dict(weapon=it, base=(lo, hi), ethereal=eth, ed=ed, after_ed=after, weapon_flat=wflat,
                    tooltip=(after[0] + wflat[0], after[1] + wflat[1]), flat=flat, damage=damage, percent=percent,
                    multiplier=pct, result=(damage[0] * pct // 100, damage[1] * pct // 100))

    def weapon_damage(self):
        """Dégâts physiques de l'arme (min, max), ou None sans arme : (dégâts de l'arme + dégâts plats de tous les
        objets) × (100 + W. Physical Damage + bonus de Force + bonus de Dextérité) / 100, arrondis vers le bas
        (détail : weapon_damage_detail).
        Dégâts de l'arme = base (× 1,25 éthérée) × (100 + son Enhanced Damage) / 100 ; deux mains (sauf épée d'un
        Barbare) : dégâts à deux mains et plats 23 / 24, sinon à une main et plats 21 / 22.
        ✅ Kalidor, Faithshaker éthérée 60-82, +240 % (infobulle 255-396), +50 max sur l'arme et +10 d'un autre objet,
        W. Physical 390 %, Force 498 % : 255 × 9,88 = 2 519, 406 × 9,88 = 4 011 ; sans un charme de +30 % : 2 442 - 3 889
        (Attack, page 1 de la feuille du jeu, 11/10)."""
        detail = self.weapon_damage_detail()
        return detail and detail['result']

    def block_cap(self):
        """Plafond de la chance de blocage : 50 % + « Maximum Block Chance », au plus 80 %."""
        return min(BLOCK_CAP + self.totals.get((MAX_BLOCK, None), 0), BLOCK_CAP_MAX)

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


# mercenaires (classe monstats -> acte) ; bonus innés écrits par D2Sigma.dll (0x10066900) à leur création
ROGUE, DESERT_GUARD, IRON_WOLF = 271, 338, 359
MERC_ACTS = {ROGUE: 1, DESERT_GUARD: 2, IRON_WOLF: 3, 560: 5, 561: 5}
FIGHTER_MAGES = (8, 11, 14)   # Desert Guard « Fighter Mage » (types de hireling.bin) : dégâts de sort feu et froid


def mercenary_bonuses(cls, mtype, level, strength, dexterity):
    """Bonus innés d'un mercenaire (D2Sigma.dll 0x10066900, Force et Dextérité de base) : {stat: valeur}. Tous :
    Poison Length Reduction 200, Experience Gain niveau × 10. Rogue : Physical Resist niveau / 4, % de dégâts
    physiques Dextérité / 2, Evade Dextérité / 40 (au plus 60), Énergie (niveau + 4) × 6, Slow Attacker niveau / 5
    + 25 ; les autres : Bonus to Defense 40 %, % de dégâts physiques Force / 2 ; Desert Guard : Énergie niveau × 4
    + 16, Crushing Blow niveau / 10 + 15, Physical Resist niveau / 5 + 25 (Fighter Mage : dégâts de sort feu et
    froid = niveau) ; Iron Wolf : Énergie (niveau + 9) × 20, Bonus to Defense (niveau + 60) × 5, Spell Focus (niveau
    + 50) × 5, dégâts de sort feu, foudre, froid = niveau ; Barbarian : Énergie niveau × 2 + 8, % de Force niveau / 4
    + 20, % de Dextérité niveau / 3 + 20, Grit 20. Niveau 100 et plus : résistances maximales + (niveau − 100) / 10
    (✅ Sharyn niveau 112 : 76 %)."""
    b = {POISON_LENGTH: 200, 85: level * 10}
    if cls == ROGUE:
        b.update({36: level // 4, 25: dexterity // 2, 338: min(dexterity // 40, 60), S.ENERGY: (level + 4) * 6,
                  363: level // 5 + 25})
    else:
        b.update({BONUS_DEFENSE: 40, 25: strength // 2})
        if cls == DESERT_GUARD:
            b.update({S.ENERGY: level * 4 + 16, 136: level // 10 + 15, 36: level // 5 + 25})
            if mtype in FIGHTER_MAGES:
                b.update({329: level, 331: level})
        elif cls == IRON_WOLF:
            b.update({S.ENERGY: (level + 9) * 20, BONUS_DEFENSE: (level + 60) * 5, 485: (level + 50) * 5,
                      329: level, 330: level, 331: level})
        else:
            b.update({S.ENERGY: level * 2 + 8, 359: level // 4 + 20, 360: level // 3 + 20, 184: 20})
    if level >= 100:
        b.update({m: (level - 100) // 10 for m in RESISTS.values()})
    return b


class MercenaryStats(CharacterStats):
    """Statistiques du mercenaire : niveau (expérience), Force, Dextérité, vie de hireling.bin (ligne de son type
    dont la tranche de niveau est atteinte, d = niveau − niveau de la ligne : Force = max(10, Str + StrPerLvl × d / 8),
    Dextérité de même, vie = max(40, Hp + HpPerLvl × d) : D2Game.dll 0x6fc68d9a), défense de base Defense +
    DefPerLvl × d et résistance élémentaire Resist + ResistPerLvl × d / 4 (D2Sigma.dll 0x10066c10), bonus innés
    (mercenary_bonuses, dans innate ; Énergie : de base), objets portés (sans contrôle des exigences : le jeu ne les
    lui laisse pas porter sinon) ; pas de classe (Vitalité sans effet : ✅ vie de Sharyn 5 628 en jeu), pas de
    compétences investies ni de mercenaire. difficulty : difficulté en cours du personnage (pénalité de résistance).
    ✅ Sharyn (Kalidor, Hell) et Debi (Nekratall, Normal), feuilles du jeu : attributs, vie, défense, résistances."""

    def __init__(self, merc, data, difficulty=0):
        self.merc = merc
        level = mercenary_level(merc, data)
        rows = [r for r in hireling_rows(merc, data) if r['level'] <= level] or hireling_rows(merc, data)[:1]
        self.row = r = rows[-1] if rows else None
        base, self.innate, self._base_defense = {12: level}, {}, 0
        if r:
            d = level - r['level']
            per8 = lambda v: int(v * d / 8)   # division entière vers zéro (D2Game : cdq / and 7 / sar 3)
            base[0] = max(10, r['strength'] + per8(r['strength_per_level']))
            base[2] = max(10, r['dexterity'] + per8(r['dexterity_per_level']))
            base[7] = base[6] = max(0x2800, (r['life'] << 8) + (r['life_per_level'] << 8) * d)
            self._base_defense = max(0, r['defense'] + r['defense_per_level'] * d)
            self.innate = mercenary_bonuses(r['cls'], merc['type'], level, base[0], base[2])
            base[S.ENERGY] = self.innate.pop(S.ENERGY, 0)
            res = r['resist'] + r['resist_per_level'] * d // 4
            for sid in RESISTS:
                self.innate[sid] = self.innate.get(sid, 0) + res
        char = dict(cls=None, level=level, skills={}, items=merc.get('items') or [], base_stats=base, mercenary=None,
                    strength=base.get(0, 0), dexterity=base.get(2, 0), energy=base.get(S.ENERGY, 0), vitality=0,
                    difficulty=difficulty)
        super().__init__(char, data)

    def active_items(self):
        return [it for it in self.char['items'] if place(it) == 'equipped' and it['equipped'] not in INACTIVE_HANDS]

    def usable(self, items):
        return items   # pas de contrôle des exigences : le jeu ne lui laisse pas porter un objet sinon

    def class_row(self):
        return bytes(0x100)   # pas de classe : aucune vie / mana / endurance par point d'attribut

    def stat(self, sid, param=None):
        """Total d'une stat, bonus innés compris."""
        value = super().stat(sid, param)
        return value + self.innate.get(sid, 0) if param is None and sid not in ATTRIBUTES else value

    def stat_sources(self):
        """Sources des stats, bonus innés compris (une source)."""
        return super().stat_sources() + [{(sid, None): v for sid, v in self.innate.items()}]

    def base_defense(self):
        """Défense de base du mercenaire (hireling.bin), avant objets, Dextérité et % (✅ Sharyn 4 589, Debi 594)."""
        return self._base_defense

    def act(self):
        """Acte du mercenaire (1, 2, 3, 5), ou None."""
        return MERC_ACTS.get(self.row['cls']) if self.row else None

    def subclass(self):
        """Sous-classe affichée par le jeu (chaîne « strhirespecialN » : Ranger, Priestess, Exemplar…), ou None."""
        k = f"strhirespecial{self.row['subclass']}" if self.row else None
        return self.data.key(k) if k and self.data.key_index(k) is not None else None

    def name(self):
        """Nom du mercenaire : chaîne du premier nom de la liste de son type + son numéro de nom (✅ Sharyn, Debi), ou
        None."""
        i = self.data.key_index(self.row['name_first']) if self.row else None
        return self.data.s(i + self.merc.get('name_id', 0)) if i is not None else None


WEAPON_INNATE = 415   # dégât inné affiché par l'arme (« Innate Fire Damage: x (y% of Strength) »)
ATTRIBUTE_ORDER = (S.STRENGTH, S.DEXTERITY, S.VITALITY, S.ENERGY)
INNATE_ELE = 484


class _Masked:
    """Personnage vu par une formule avec un attribut ou Innate Ele Damage à 0
    (décomposition des formules en termes : CharacterStats.skill_terms)."""

    def __init__(self, cs, skill, attr=None, innate=False):
        self.cs, self.skill, self.attr, self.innate = cs, skill, attr, innate

    def __getattr__(self, name):
        return getattr(self.cs, name)

    def stat(self, sid, param=None):
        if sid == self.attr or (self.innate and sid == INNATE_ELE):
            return 0
        return self.cs.stat(sid, param)

    def attribute(self, sid):
        return 0 if sid == self.attr else self.cs.attribute(sid)

    def base_stat(self, sid, param=None):
        return 0 if sid == self.attr else self.cs.base_stat(sid, param)


_CACHE = {}   # (personnage, données, autre jeu d'armes) -> (personnage, données, CharacterStats) ; un seul personnage


def character_stats(char, data, other_set=False):
    """CharacterStats du personnage char (gardé tant que c'est le même personnage lu ; les deux jeux d'armes)."""
    key = (id(char), id(data), other_set)
    if key not in _CACHE:
        if any(k[:2] != key[:2] for k in _CACHE):
            _CACHE.clear()
        _CACHE[key] = (char, data, CharacterStats(char, data, other_set))
    return _CACHE[key][2]
