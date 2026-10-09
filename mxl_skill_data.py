"""Explication des compétences : données de base, sans dépendance (mxl_skill_calc et ses modules s'appuient dessus).

Champs des tables du jeu (skills.bin, skills2.bin, skilldesc.bin, missiles.bin), n° de textes et de stats, lecture d'un
enregistrement (Record), types communs (Grey, Unsupported) et petits calculs entiers du jeu (paliers de niveau,
rendement décroissant, multiplication-division arrondie vers zéro). Adresses du jeu : docs/format-stash-mxl-2.14.5.md.
"""
import struct

# ---------- skilldesc.bin (ligne de l'explication) ----------
SKILLDESC_LINES, SKILLDESC_TEXT_A, SKILLDESC_TEXT_B = 0x42, 0x54, 0x76   # 17 formats u8, 17 + 17 textes u16
SKILLDESC_CALC_A, SKILLDESC_CALC_B, SKILLDESC_STRMANA = 0x98, 0xDC, 0x10  # 17 + 17 formules u32, texte du coût
DESC_GROUP, DSC2_GROUP = range(0, 6), range(6, 10)   # lignes du niveau actuel ; lignes affichées au-dessus (dsc2)

# ---------- skills.bin (enregistrement de 572 octets) ----------
SKILL_DESC = 0x194                                                        # ligne de skilldesc (u16)
SKILL_CALCS, SKILL_PARAMS, SKILL_PASSIVE_CALCS = 0x138, 0x148, 0xA4       # clc1-4, par1-8 (i32), pst1-5 (u32)
SKILL_AURA_CALCS, SKILL_AURA_LEN, SKILL_AURA_RANGE = 0x68, 0x60, 0x64     # ast1-6, len, rng (u32)
SKILL_PASSIVE_STATE = 0x94                                                # état passif (u16 ; NO_STATE : aucun)
SKILL_PASSIVE_STATS, SKILL_AURA_STATS = 0x98, 0x54                        # 5 / 6 × u16 : stats passives / d'aura
SKILL_MIN_MANA, SKILL_MANA_SHIFT, SKILL_MANA, SKILL_LVL_MANA = 0x186, 0x188, 0x18A, 0x18C
# Attack Rating de la compétence (variable toht) : i32 + i32 par niveau au-delà du 1er, ou formule u32 si elle existe
SKILL_TOHIT, SKILL_LVL_TOHIT, SKILL_TOHIT_CALC = 0x198, 0x19C, 0x1A0
# dégâts élémentaires : type u8, décalage u8, min / max i32, incréments par palier 5 × i32 (min, max), formule de
# synergie u32 ; skills2.bin (Median XL, 66 octets par compétence) : bonus Énergie / Spell Focus automatique, pas de
# « % dégâts de sort » de l'élément (u8)
SKILL_ELEM_TYPE, SKILL_HIT_SHIFT, SKILL_EMIN, SKILL_EMAX = 0x1DC, 0x1A4, 0x1E0, 0x1E4
SKILL_EMIN_LEV, SKILL_EMAX_LEV, SKILL_EDMG_SYM = 0x1E8, 0x1FC, 0x210
SKILLS2_ENERGY_BONUS, SKILLS2_NO_SPELL_DAMAGE = 0x2D, 0x2E
# coût en mana de Median XL (champs de skills.bin à zéro) : formules u32 de skills2.bin (code : skills2code.bin) : mana
# de base @0x36, mana par niveau @0x3A (× (100 + stat 228 « Mana Cost of Skills ») / 100) ; D2Sigma.dll 0x100a7620,
# 0x100a1dc0, ligne de format 77 (0x100a8f66)
SKILLS2_MANA_CALC, SKILLS2_LVL_MANA_CALC, MANA_COST_REDUCTION = 0x36, 0x3A, 228
SKILLS2_SIZE = 66
# dégâts physiques de la compétence (D2Sigma.dll 0x100a6020 / 0x100a5ec0, exports 10567 / 10297 de D2Common.dll
# remplacés) : min / max i32, incréments par palier 5 × i32 (min, max), formule de synergie u32 ; drapeau u32 @0x04
# 0x200 : autre calcul (non étudié) ; « % dégâts de sort » : stat 357 (magique)
SKILL_FLAGS, SKILL_OTHER_DAMAGE = 0x04, 0x200
SKILL_MIN_DAM, SKILL_MAX_DAM, SKILL_MIN_DAM_LEV, SKILL_MAX_DAM_LEV, SKILL_DMG_SYM = 0x1A8, 0x1AC, 0x1B0, 0x1C4, 0x1D8
PHYSICAL_SPELL_DAMAGE = 357
# temps de recharge (variable skcd, D2Sigma.dll 0x100b0ed0) : formule u32 (en frames ; pas de formule = 0) moins la
# stat 309 du personnage (« %s Cooldown Reduced by », param = compétence)
SKILL_COOLDOWN_CALC, COOLDOWN_REDUCTION = 0x190, 309
# nombre maximal d'invocations (pets) et formule skpt : formules u32 (D2Common.dll, variables 71 et 72 ; absente = 0)
SKILL_PET_MAX_CALC, SKILL_SKPT_CALC = 0xC0, 0x170
# vie et Attack Rating des invocations (variables mnhp / mnar, D2Sigma.dll 0x10067c60 / 0x10067bd0) : vie de base i32
# @0x150 + (niveau - 1) x i32 @0x154, formule de bonus de vie u32 @0x138 (en %) ; Attack Rating par niveau i32 @0x158,
# majoré de la stat 500 du personnage (« to Summon Attack Rating »)
SKILL_MINION_LIFE, SKILL_MINION_LIFE_LEV, SKILL_MINION_LIFE_CALC, SKILL_MINION_AR_LEV = 0x150, 0x154, 0x138, 0x158
SUMMON_ATTACK_RATING = 500
SKILL_STATE_FIELDS = {90: 0x80, 91: 0x94, 101: 0x82}   # variables aura, pass, aura (2e) : état u16 de skills.bin
# fonction serveur de la compétence (srvdo, u16) et projectiles (srvmissile, srvmissileA-C, u16), format D2 1.13c ;
# tir de projectiles (srvdo 8, D2Game.dll 0x6fc6d420) : nombre = clc1, projectile = srvmissileA (srvmissileB dans un
# cas particulier)
SKILL_SRV_DO, SKILL_SRV_MISSILE_A, SRV_DO_SHOOT = 0x2E, 0x48, 8
# bonus temporaire (srvdo 25, D2Game.dll 0x6fc62570) : état aurastate (@0x80) posé pour la durée de la formule @0x60,
# avec les stats aurastat1-6 (@0x54) et leurs formules (@0x68)
SRV_DO_BUFF = 25
# bonus offert (srvdo 68 de Median XL, D2Sigma.dll 0x100a9f50) : même état et mêmes stats sur le lanceur (0x100ae9b0),
# plus un projectile vers la cible dont l'impact 18 (D2Game.dll 0x6fc5ea60) les pose sur l'allié touché (test
# d'alliance 0x6fd00570 : même unité, maître d'une créature, même groupe)
SRV_DO_GIFT = 68
SRV_DO_PULSE = 18   # état posé (D2Game.dll 0x6fc628f0) : aurastate pour la durée @0x60, stats aurastat1-6
# lanceur (srvdo 28, D2Game.dll 0x6fc62d90) : un projectile srvmissileA vers la cible ; s'il tourne sur lui-même
# (déplacement srvmove 15, D2Game.dll 0x6fc60ca0), il libère toutes les param1 images son sous-projectile subm1, dans sa
# direction + param2 (sur 64), pendant sa durée de vie : portée + portée par niveau × niveau (D2Game.dll 0x6fc8fc85)
SRV_DO_LAUNCH, MISSILE_SRV_MOVE, SRV_MOVE_SPIN, MISSILE_SUBMISSILE, MISSILE_PARAM1 = 28, 0x0C, 15, 0x18, 0x38
# nova (srvdo 22, D2Game.dll 0x6fc63aa0 -> 0x6fcc2800) : 64 projectiles, un par direction (tables 0x6fd1b770 /
# 0x6fd1b870) ; le niveau ne change que leur vitesse (vel @0x9A + vel par niveau @0x9B × niveau / 8, + clc1)
SRV_DO_NOVA, NOVA_COUNT = 22, 64
# malédiction (srvdo 30, D2Game.dll 0x6fc705d0) : état @0x82 posé sur les ennemis (filtre @0x50) dans le rayon de la
# formule @0x64, pour la durée de la formule @0x60, avec les stats aurastat1-6 (@0x54, formules @0x68)
SRV_DO_CURSE, SKILL_TARGET_STATE, SKILL_AURA_RANGE_CALC = 30, 0x82, 0x64
# impact en anneau (fonction d'impact 29, D2Game.dll 0x6fc5c850 ; aussi à la fin de la durée de vie) : sous-projectile
# d'impact hitsub1 (@0x24) dans une direction sur hitpar1 (@0x4C) parmi 64
MISSILE_SRV_HIT, SRV_HIT_RING, MISSILE_HIT_SUBMISSILE, MISSILE_HIT_PARAM1, DIRECTIONS = 0x0E, 29, 0x24, 0x4C, 64
# impact de relais (fonction d'impact 36, D2Game.dll 0x6fc5ab30) : en fin de vie seulement (sans cible), un seul
# sous-projectile d'impact au même endroit, même direction ; projectile de la compétence sans srvdo : srvmissile
# (@0x46), créé sur le lanceur vers la cible (D2Game.dll 0x6fcc1b3a -> 0x6fcc28f0, drapeau 0x20)
SRV_HIT_RELAY, SKILL_SRV_MISSILE = 36, 0x46
# collision (missiles.bin u8 @0x183, colonne CollideType : 0 = ne touche personne) ; fonction de dégâts (@0x10) n° 1
# (D2Game.dll 0x6fc59ce0) : la formule de dégâts (@0x90, misscode.bin) % des dégâts physiques, au plus 100, passent à
# l'élément du projectile (@0xE4 : 1 feu, 2 foudre, 3 magie, 4 froid, 5 poison)
MISSILE_COLLIDE, MISSILE_SRV_DMG, SRV_DMG_CONVERT, MISSILE_DMG_CALC, MISSILE_ELEM = 0x183, 0x10, 1, 0x90, 0xE4
# impact en zone (fonction d'impact 9, D2Game.dll 0x6fc5e0b0) : dégâts de zone de rayon hitpar2 (sinon clc2), puis un
# sous-projectile d'impact sur chaque case du disque de rayon hitpar1 (sinon clc1 ; 0x6fc5d450 : x² + y² <= rayon²),
# avec pour durée de vie la formule d'impact @0x88 (misscode.bin)
SRV_HIT_AREA, MISSILE_HIT_CALC = 9, 0x88
# impact chercheur (fonction d'impact 20, D2Game.dll 0x6fc5dd60) : unités du filtre de la compétence (@0x50, sinon
# ennemis) dans le rayon hitpar1 (sinon formule @0x64) ; vers chacune, jusqu'à hitpar2 (sinon clc1), un sous-projectile
# d'impact parti de l'endroit du projectile (0x6fc5cd00)
SRV_HIT_SEEK = 20
# projectiles sur le lanceur (srvdo 17, D2Game.dll 0x6fc63b60) : clc1 projectiles srvmissileA posés sur le lanceur
# (drapeau 0x21), visés vers la cible
SRV_DO_PLACE = 17
# « Total Defense = 0 » dans le jeu (texte sans valeur, écrit pour −100) : % de la défense totale, appliqué en dernier
# (✅ D2Common.dll 10672 : défense = (défense + Dextérité / 4) × (100 + stats 171 + 16…) / 100, puis × (100 + stat 182) / 100)
STAT_TOTAL_DEFENSE_PCT = 182
STAT_LIFE_REGEN = 74   # régénération de vie : 256es de vie par image (affichée ≈ ÷ 10 par seconde)
MISSILE_SRC_DAMAGE = 0x12D   # missiles.bin : part des dégâts de l'arme (u8, en 128es ; 128 = 100 %)
SKILL_SRC_DAMAGE = 0x1A5   # part des dégâts de l'arme (u8, en 128es) : variable wdm = × 100 / 128 (D2Sigma.dll 0x100a6532)
# durée des effets élémentaires : durée i32, incréments 3 × i32 (niveaux 2-8, 9-16, 17+), formule u32
SKILL_ELEN, SKILL_ELEV_LEN, SKILL_ELEN_SYM = 0x214, 0x218, 0x224
NO_CALC = 0xFFFFFFFF   # pas de formule
NO_STATE, NO_STAT = 0xFFFF, 0xFFFF   # pas d'état / pas de stat

# ---------- missiles.bin (variables de misscalc.bin) ----------
# par1-5, cpa1-5, hpa1-3, chp1-3, dpa1-2 (i32) ; paires (a, b) de sl12 / sd12, sl34, cl12, cl34, shl1, chl1, dl12
MISSILE_FIELDS = (0x38, 0x3C, 0x40, 0x44, 0x48, 0x58, 0x5C, 0x60, 0x64, 0x68, 0x4C, 0x50, 0x54, 0x6C, 0x70, 0x74, 0x78, 0x7C)
MISSILE_PAIRS = ((0x38, 0x3C), (0x40, 0x44), (0x58, 0x5C), (0x60, 0x64), (0x4C, 0x50), (0x6C, 0x70), (0x78, 0x7C))
MISSILE_RANGE, MISSILE_RANGE_LEV = 0x96, 0x98   # rang = i16 + niveau × i16

# ---------- stats du personnage ----------
CURRENT_POOLS = frozenset((6, 8, 10))   # vie, mana, endurance actuelles : varient en cours de jeu, inconnues
POOL_STATS = frozenset((6, 8))          # vie / mana actuelles : affichées en taux de conversion
POOL_SAMPLES = (0, 200, 400, 600)       # valeurs essayées pour le taux
# stats cachées que le jeu ne donne jamais à un personnage (0 pour lui) : 379 = réduction en % des bonus d'invocation
# (formules : stat 444 ou 470 × (100 − stat 379) / 100 ; aucune source dans les .bin ni les DLL) ; 88 = marque posée par
# Median XL sur une unité invoquée (D2Sigma.dll 0x1004b4b0, branché sur la création d'unité de D2Game.dll : param 0x2004
# = 1, 0x200D = propriétaire), lue par Jerhyn's Tawiz
NOT_ON_PLAYER = frozenset((379, 88))
STAT_ATTACK_RATING = 19   # stat(19) : Attack Rating total, calcul dédié du jeu (D2Common.dll 10621), inconnu
STAT_ENERGY, STAT_SPELL_FOCUS = 1, 485
# élément -> « % dégâts de sort » de l'élément (D2Sigma.dll 0x100a6d60)
ELEMENTS = {1: 329, 2: 330, 3: 357, 4: 331, 5: 332}
# syn1-syn6 : stat cachée du personnage dont le param est le n° de la compétence (améliorations de compétences données
# par des objets : Sharp Beak -> Raid…) ; trouvé dans D2Sigma.dll (évaluateur des variables 73 à 110, 0x100a6340)
SYN_STATS = {'syn1': 383, 'syn2': 393, 'syn3': 396, 'syn4': 397, 'syn5': 399, 'syn6': 400}

# ---------- textes (n° de chaîne) ----------
# textes de l'élément dans les lignes de dégâts (D2Client.dll 0x6fadc870) ; durée (froid, poison)
ELEMENT_LABELS = {1: 4257, 2: 4259, 3: 4291, 4: 4258, 5: 4260, 6: 3524}
LENGTH_LABELS = {4: 4265, 5: 4266}          # « Cold Length: », « Poison Length: »
STR_SECOND, STR_SECONDS, STR_OVER = 4267, 4268, 11022   # « second », « seconds », « over »
STR_YARD, STR_YARDS = 4288, 4278   # « yard », « yards »
STR_WEAPON_DAMAGE = 25041   # « % Weapon Damage »
STR_PHYSICAL_DAMAGE = 4256   # « Physical Damage: »
STR_TO_ATTACK_RATING, STR_AVERAGE, STR_PER_SECOND = 4262, 4322, 4286   # « To Attack Rating: », « Average », « per second »
FRAMES_PER_SECOND = 25


class Grey(str):
    """Texte de l'explication à afficher en gris : valeur non calculée (« Fire Damage: varies by character ») ou note
    (« (some values not calculated) »)."""


class Unsupported(Exception):
    """Valeur inconnue (dépend du personnage, ou mécanisme non reproduit) : ligne grise ou note à la place.
    Le message est un libellé pour les humains (relevé du catalogue) ; le code lit les attributs, jamais le message :
    stat = n° de la stat du personnage en cause (stat / lstat), kind = raison regroupée dans le relevé (sinon message)."""

    def __init__(self, message, stat=None, kind=None):
        super().__init__(message)
        self.stat, self.kind = stat, kind or message


class PoolProbe:
    """Personnage dont la vie / mana actuelles valent pools ({stat: valeur en 256es}) ; le reste est celui de base."""

    def __init__(self, base, pools):
        self.base, self.pools = base, pools

    def __getattr__(self, name):
        return getattr(self.base, name)


class Record:
    """Lecture des champs d'un enregistrement binaire (petit-boutiste) : rec.i32(0x148), rec.u32(off)…"""
    __slots__ = ('raw',)

    def __init__(self, raw):
        self.raw = raw

    def i32(self, o):
        return struct.unpack_from('<i', self.raw, o)[0]

    def u32(self, o):
        return struct.unpack_from('<I', self.raw, o)[0]

    def i16(self, o):
        return struct.unpack_from('<h', self.raw, o)[0]

    def u16(self, o):
        return struct.unpack_from('<H', self.raw, o)[0]

    def u8(self, o):
        return self.raw[o]

    def i32s(self, o, n):
        return list(struct.unpack_from(f'<{n}i', self.raw, o))

    def u16s(self, o, n):
        return list(struct.unpack_from(f'<{n}H', self.raw, o))

    def u32s(self, o, n):
        return list(struct.unpack_from(f'<{n}I', self.raw, o))


def level_brackets(increments, lvl, tops=(8, 16, 22, 28, 10 ** 9)):
    """Somme des incréments par niveau au-delà du 1er, par paliers (D2Sigma.dll 0x100a6be0) : niveaux 2 à 8 :
    incrément 1, 9 à 16 : 2, 17 à 22 : 3, 23 à 28 : 4, 29 et plus : 5 (durées : 3 paliers, tops 8, 16, sans fin)."""
    total, prev = 0, 1
    for inc, top in zip(increments, tops):
        if lvl <= prev:
            break
        total += (min(lvl, top) - prev) * inc
        prev = top
    return total


def diminishing(lvl, lo, hi):
    """Rendement décroissant de lo vers hi (D2Common.dll 0x6fd9dc30) : lo + ⌊⌊110 × niveau / (niveau + 6)⌋ × (hi − lo)
    / 100⌋, au plus hi ; 0 si le niveau est nul."""
    if lvl <= 0:
        return 0
    v = lo + int(int(110 * lvl / (lvl + 6)) * (hi - lo) / 100)
    return min(v, hi)


def muldiv(a, b, c):
    """a × b / c en entiers, arrondi vers zéro (comme le C)."""
    q = abs(a * b) // c
    return q if (a * b) >= 0 else -q
