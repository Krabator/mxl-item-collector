"""Tables du jeu Median XL 2.14.5 lues dans data/ (extraites par extract_data.py) : Data, ItemBase."""
import struct, os
from dataclasses import dataclass
from tbl import all_strings
from i18n import tr


def strip_colors(txt):
    """Texte sans ses codes couleur du jeu (ÿc + 1 caractère)."""
    while 'ÿc' in txt:
        i = txt.index('ÿc')
        txt = txt[:i] + txt[i + 3:]
    return txt


@dataclass(frozen=True)
class ItemBase:
    """Objet de base (une ligne de weapons / armor / misc.bin), commun à tous les exemplaires de ce code."""
    code: str
    kind: str = '?'              # 'weapons', 'armor', 'misc' ('?' : code inconnu)
    name: str = '?'              # nom affiché (codes couleur retirés), u16 @0xF4 = index de chaîne
    name_raw: str = ''           # nom brut (codes couleur ÿc, sauts de ligne)
    type: int = -1               # index itemtypes : u16 @0x11E
    type2: int = -1              # second type (i16 @0x120 ; ✅ Crystal Sword 272 : son auto-affixe en dépend)
    size: tuple = (1, 1)         # (largeur, hauteur) en cases : u8 @0x10F / @0x110
    level_req: int = 0           # niveau requis de base : u8 @0x13F
    qlvl: int = 0                # niveau de l'objet de base (qlvl, niveau d'objet minimum pour qu'il tombe) : u8 @0xFD
                                 # (✅ Claymore (1) à (4), Sacred = 10, 31, 51, 77, 90)
    req_str_dex: tuple = (0, 0)  # Force, Dextérité requises : u16 @0x10A / @0x10C
    block: int = 0               # chance de blocage de base (boucliers) : u8 @0x111
    inv_file: str = ''           # fichier d'icône d'inventaire (DC6) : texte @0x20
    spell: int = 0               # u32 @0x94 (13 = « Right Click to Read »)
    stack_max: int = None        # quantité max si empilable (u8 @0x132 ≠ 0) : u16 @0xE4 ; None sinon
    def_range: tuple = (0, 0)    # armures : défense de base min, max : i32 @0xCC / @0xD0
    two_handed: int = 0          # armes : 1 si à deux mains (u8 @0x11C)
    dmg_bonus: tuple = (0, 0)    # armes : bonus de dégâts par Force / Dextérité : u16 @0x106 / @0x108
    wclass: str = ''             # armes : catégorie d'animation (1hs, stf, 2ht, bow…) : 4 car. @0xC0
    wsm: int = 0                 # armes : vitesse de base (WSM, négatif = rapide) : i32 @0xD8
    damage: dict = None          # armes : dégâts de base (min, max) one_hand, throw, two_hand : u8 @0xFE…@0x103
    auto_group: int = 0          # groupe d'automagic de l'auto-affixe de la base (« auto prefix ») : u16 @0xF8
                                 # (✅ Claymore (1) = 411, auto-affixe 49 de la Jared's Fragmentor réelle)
    max_sockets: int = 0         # nombre maximum de sockets (colonne gemsockets) : u8 @0x138 ; dépend du tier
    durability: int = 0          # durabilité de base : u8 @0x112 (✅ = durabilité max des 212 objets normaux du
                                 # corpus, 07/10) ; 0 = indestructible (119 arcs et arbalètes, 10 autres bases)
    quest: int = 0               # n° de quête (objet de quête) : u8 @0x12A (✅ Amulet of the Viper 10, Horadric Cube,
                                 # Khalim's Eye… ; 0 : objet ordinaire ; 255 : reliques de Median XL)
                                 # (✅ Claymore (1) à (4) : 2, 3, 4, 4 ; aucun objet socketé des coffres au-delà)


class Data:
    def __init__(self, folder='data'):
        """Lit les tables extraites du jeu dans folder (data/) : une méthode par groupe de tables, dans l'ordre de
        leurs dépendances (textes d'abord ; propriétés avant affixes ; objets de base avant gemmes)."""
        self.folder = folder
        self.strings = all_strings(folder)
        self._load_stats()
        self._load_properties()
        self._load_affixes()
        self._load_uniques_and_sets()
        self._load_runewords()
        self._load_item_types()
        self._load_skills()
        self._load_bases()
        self._load_gems()
        self._load_hirelings()
        self._load_areas()
        self._load_mystic_orbs()
        self._load_treasure_classes()
        # monstres : monstats.bin, nom (index de chaîne) u16 @0x06 ✅ 3374 « Returned Warrior » (réanimation)
        self.monster_names = [self.s(struct.unpack_from('<H', r, 0x06)[0]) for r in self._rows('monstats')]
        # mêmes noms avec leurs codes couleur (« Reanimate as: Edyrem », Edyrem en jaune)
        self.monster_names_raw = [(self.strings.get(struct.unpack_from('<H', r, 0x06)[0]) or (None, ''))[1]
                                  for r in self._rows('monstats')]
        self.anim = self._animdata()

    def _load_stats(self):
        """itemstatcost.bin : description de chaque stat (isc) et largeur des stats du personnage (csv_bits)."""
        self.isc = {}
        self.csv_bits = {}
        for r in self._rows('itemstatcost'):
            sid = struct.unpack_from('<H', r, 0x00)[0]
            pos, neg, str2, dgrp = struct.unpack_from('<4H', r, 0x38)
            gpos, gneg, gstr2 = struct.unpack_from('<3H', r, 0x42)
            self.isc[sid] = dict(
                bits=r[0x19], add=struct.unpack_from('<i', r, 0x1C)[0],
                param=struct.unpack_from('<i', r, 0x24)[0],
                desc=self.s(pos),
                # affichage en jeu : priorité @0x34, descfunc @0x36, descval @0x37, textes @0x38/0x3A/0x3C ;
                # groupe (ex. 0-3 « to all Attributes ») : dgrp @0x3E, dgrpfunc @0x40, dgrpval @0x41, textes @0x42/0x44/0x46
                prio=struct.unpack_from('<H', r, 0x34)[0], func=r[0x36], val=r[0x37],
                pos=self.s(pos), neg=self.s(neg), str2=self.s(str2),
                dgrp=dgrp, gfunc=r[0x40], gval=r[0x41], gpos=self.s(gpos), gneg=self.s(gneg), gstr2=self.s(gstr2),
                color=self.color(pos),
                # stats « par niveau » : valeur affichée = (valeur × stat op_base) >> op_param (op @0x54, param @0x55, base u16 @0x56)
                op=r[0x54], op_param=r[0x55], op_base=struct.unpack_from('<H', r, 0x56)[0],
                # stats cibles de l'opération (op stat1-3, u16 @0x58) ; décalage de la valeur en mémoire (ValShift @0x18 :
                # vie, mana = 8, en 256es)
                op_stats=tuple(s for s in struct.unpack_from('<3H', r, 0x58) if s != 0xFFFF), shift=r[0x18])
            self.csv_bits[sid] = r[0x0A]   # largeur des stats du personnage dans le .d2s (Force = 11 bits en MXL)
        # stats de chaque groupe d'affichage (dgrp), dans l'ordre de la table : calculées une fois (chaque infobulle les
        # demande pour chacune de ses stats : les recalculer coûtait les deux tiers du temps de la recherche)
        groups = {}
        for sid, c in self.isc.items():
            if c['dgrp']:
                groups.setdefault(c['dgrp'], []).append(sid)
        self.stat_group = {sid: groups.get(c['dgrp'], []) for sid, c in self.isc.items()}
        # stats qui modifient chaque stat cible par une opération (D2Common.dll 0x6fd89530) : cible -> [source]
        self.op_sources = {}
        for sid, c in self.isc.items():
            if c['op']:
                for target in c['op_stats']:
                    self.op_sources.setdefault(target, []).append(sid)

    def _load_properties(self):
        """properties.bin : stats et fonctions de chaque propriété."""
        # properties.bin : propriété -> stats (jusqu'à 7, i16 @0x20) et fonction de chaque stat (u8 @0x18)
        prop_rows = self._rows('properties')
        self.props = [struct.unpack_from('<7h', r, 0x20) for r in prop_rows]
        self.prop_func = [r[0x18] for r in prop_rows]              # 1re fonction de la propriété
        self.prop_funcs = [list(r[0x18:0x1F]) for r in prop_rows]  # fonction de chaque stat
        # valeur fixe de chaque stat (i16 @0x0A) : ex. classe des « +x to <classe> Skill Levels » (✅ prop 126 = 4 Barbare)
        self.prop_vals = [struct.unpack_from('<7h', r, 0x0A) for r in prop_rows]

    def _load_affixes(self):
        """Basse qualité, supérieurs, affixes magiques et automagiques, noms des rares."""
        # objets de basse qualité : lowqualityitems.bin, nom ASCII @0x00 = clé tbl ; ligne = sous-qualité
        self.low_quality = [r[:0x20].split(b'\0')[0].decode('latin1') for r in self._rows('lowqualityitems')]
        # objets supérieurs : qualityitems.bin, 2 mods × (prop, param, min, max) @0x0C ; ligne = sous-qualité
        self.quality_mods = [[dict(zip(('prop', 'param', 'min', 'max'), m))
                              for m in struct.iter_unpack('<4i', r[0x0C:0x2C]) if m[0] >= 0]
                             for r in self._rows('qualityitems')]
        # affixes magiques : id dans la sauvegarde = n° de ligne + 1
        self.affixes = {}
        for kind in ('magicprefix', 'magicsuffix', 'automagic'):
            lst = []
            for r in self._rows(kind):
                mods = [struct.unpack_from('<iiii', r, 0x24 + 16 * k) for k in range(3)]
                lst.append(dict(mods=[dict(prop=m[0], param=m[1], min=m[2], max=m[3],
                                           stats=[x for x in self.props[m[0]] if x >= 0])
                                      for m in mods if m[0] >= 0],
                                level=struct.unpack_from('<I', r, 0x58)[0], level_req=r[0x65],
                                # sélection : apparition u16 @0x54, groupe u32 @0x5C, niveau max u32 @0x60 (0 = aucun),
                                # types autorisés 7 × i16 @0x6A, exclus 5 × i16 @0x78 (itemtypes)
                                spawnable=struct.unpack_from('<H', r, 0x54)[0], group=struct.unpack_from('<I', r, 0x5C)[0],
                                maxlevel=struct.unpack_from('<I', r, 0x60)[0],
                                itypes={t for t in struct.unpack_from('<7h', r, 0x6A) if t > 0},
                                etypes={t for t in struct.unpack_from('<5h', r, 0x78) if t > 0}))
            self.affixes[kind] = lst
        # noms des rares : texte ASCII à 0x26 ; id enregistré = n° de ligne + 1
        # (1er nom : table combinée suffixes puis préfixes → préfixe = id - 1 - nb_suffixes)
        self.rare_prefix = [r[0x26:0x40].split(b'\0')[0].decode('latin1') for r in self._rows('rareprefix')]
        self.rare_suffix = [r[0x26:0x40].split(b'\0')[0].decode('latin1') for r in self._rows('raresuffix')]

    def _load_uniques_and_sets(self):
        """uniqueitems.bin et setitems.bin : une fiche par ligne (nom, objet de base, niveaux, icône propre, mods)."""
        # uniques : uniqueitems.bin, 332 octets ; n° d'unique enregistré dans l'objet = n° de ligne.
        # Nom (clé tbl) @0x02, code de l'objet de base @0x28 (vide : ligne inutilisée), rareté u32 @0x30 (0 : ne tombe
        # pas : quêtes, événements, Item Design), niveau u16 @0x34, niveau requis u16 @0x36, icône propre (fichier
        # DC6, vide : icône de l'objet de base) @0x5A (32 octets ; 67 uniques, ex. Griswold's Heart « invxtuu »),
        # 12 mods (propriété, param, min, max) en i32 @0x8C. ✅ Jared's Fragmentor (ligne 375, Claymore)
        self.uniques = [dict(name=r[0x02:0x22].split(b'\0')[0].decode('latin1'), code=r[0x28:0x2C].decode('latin1'),
                             rarity=struct.unpack_from('<I', r, 0x30)[0], level=struct.unpack_from('<H', r, 0x34)[0],
                             level_req=struct.unpack_from('<H', r, 0x36)[0],
                             inv_file=r[0x5A:0x7A].split(b'\0')[0].decode('latin1'),
                             mods=[dict(zip(('prop', 'param', 'min', 'max'), m))
                                   for m in struct.iter_unpack('<4i', r[0x8C:0x14C]) if m[0] >= 0])
                        for r in self._rows('uniqueitems')]
        # objets de set : setitems.bin, 440 octets ; n° enregistré dans l'objet = n° de ligne (supposé comme pour les
        # uniques, à vérifier sur un objet de set). Nom (clé tbl) @0x02, code de l'objet de base @0x28 (vide pour les
        # 127 sets de Diablo II retirés par Median XL), n° du set i16 @0x2C, niveau u16 @0x30, niveau requis u16 @0x32,
        # icône propre @0x62 (32 octets ; 24 objets de set, ex. « invamuset »),
        # 9 affixes propres (propriété, param, min, max) en i32 @0x88 (puis 10 bonus partiels @0x118, vides en Median
        # XL). ✅ Celestia's Charge (ligne 127) : ED 140-170, Force 31-50, niveau requis 90
        self.set_items = [dict(name=r[0x02:0x22].split(b'\0')[0].decode('latin1'), code=r[0x28:0x2C].decode('latin1'),
                               set_id=struct.unpack_from('<h', r, 0x2C)[0], level=struct.unpack_from('<H', r, 0x30)[0],
                               level_req=struct.unpack_from('<H', r, 0x32)[0],
                               inv_file=r[0x62:0x82].split(b'\0')[0].decode('latin1'),
                               mods=[dict(zip(('prop', 'param', 'min', 'max'), m))
                                     for m in struct.iter_unpack('<4i', r[0x88:0x118]) if m[0] >= 0])
                          for r in self._rows('setitems')]
        # sets : sets.bin, 296 octets, ligne = n° du set (set_id des objets) ; nom (n° de texte u16 @0x02, deux lignes
        # affichées de bas en haut : « (Amazon Bow Set)\nPantheon ») ; 8 bonus partiels (propriété, param, min, max en
        # i32) @0x10 par paires : avec 2, 3, 4, 5 pièces ; 8 bonus du set complet @0x90.
        # ✅ documentation, page Sets : Pantheon, 2 pièces « 50% Attack Speed » et « Elemental Resists +50% »
        mods = lambda r, off: [dict(zip(('prop', 'param', 'min', 'max'), m))
                               for m in struct.iter_unpack('<4i', r[off:off + 128])]
        keep = lambda ms: [m for m in ms if m['prop'] >= 0]
        self.sets = [dict(name=self.s(struct.unpack_from('<H', r, 0x02)[0]),
                          partial={n: keep(mods(r, 0x10)[2 * (n - 2):2 * (n - 1)]) for n in (2, 3, 4, 5)},
                          full=keep(mods(r, 0x90)))
                     for r in self._rows('sets')]

    def _load_runewords(self):
        """runes.bin : runewords (nom, runes, types autorisés et exclus) et leurs mods."""
        # runewords : nom (clé tbl) @0x00, runes = 6 × i32 @0x98 (index dans armes+armures+misc)
        self.runewords = []
        self.runeword_mods = []
        for r in self._rows('runes'):
            runes = [x for x in struct.unpack_from('<6i', r, 0x98) if x >= 0]
            it_ok = [x for x in struct.unpack_from('<6h', r, 0x86) if x > 0]
            it_ex = [x for x in struct.unpack_from('<3h', r, 0x92) if x > 0]
            self.runewords.append((r[0x40:0x80].split(b'\0')[0].decode('latin1'), runes, it_ok, it_ex))
            self.runeword_mods.append([dict(zip(('prop', 'param', 'min', 'max'), m))
                                       for m in struct.iter_unpack('<4i', r[0xC0:0x130]) if m[0] >= 0])

    def _load_item_types(self):
        """itemtypes.bin (parents, classe imposée, variantes d'icône) et charstats.bin (bonus de blocage)."""
        # types d'objets : code @0x00, parents (equiv1, equiv2) @0x04 / @0x06
        itype_rows = self._rows('itemtypes')
        self.itypes = [(r[:4].decode('latin1').strip('\0 '), struct.unpack_from('<hh', r, 0x04)) for r in itype_rows]
        self.itype_class = [r[0x21] for r in itype_rows]   # 0-6 = classe imposée, 255 = aucune
        # variantes d'icône du type (bagues, amulettes, joyaux, charmes…) : nombre u8 @0x23, 6 noms de 32 octets @0x24
        self.itype_gfx = [[r[0x24 + 32 * k:0x44 + 32 * k].split(b'\0')[0].decode('latin1') for k in range(r[0x23])]
                          for r in itype_rows]
        self.block_factor = [r[0x49] for r in self._rows('charstats')]  # bonus de blocage par classe (MXL : Nécro 1)

    def _load_skills(self):
        """Noms des compétences."""
        # noms des compétences : skills.bin (u16 @0x194 = ligne de skilldesc), skilldesc.bin (nom u16 @0x08)
        sd_rows = self._rows('skilldesc')
        self.skill_names = {}
        self.skill_names_raw = {}   # noms avec leurs codes couleur (« ÿc4Ranged Egg Trap ») : lignes « +x to <compétence> »
        # compétences jamais citées dans l'infobulle d'un objet : skills2.bin (Median XL, 66 octets) u8 @0x31 non nul
        # (D2Sigma.dll 0x100af880, testé par les descfunc 15, 24, 27, 28, 33, 37 : ligne absente ; ex. « Gematria » des
        # uniques, Jerhyn's Tawiz, Slayer de Staff of Shadows)
        self.skill_hidden = frozenset(i for i, r in enumerate(self._rows('skills2')) if len(r) > 0x31 and r[0x31])
        self.skill_class = {}   # classe de la compétence (u8 @0x0C : 0-6, 255 = aucune ; ✅ Crucify, Way of the Phoenix = 6)
        # niveau requis de la compétence (i16 @0x174 ; ✅ documentation : Holy Fire 20, Grim Fang ; négatif : aucun)
        self.skill_req = {}
        # description de la compétence (skilldesc.bin : texte long u16 @0x0C, ex. « spell - casts a wave of exploding
        # firebolts in front of you ») et n° de son icône (u16 @0x16 : image du fichier d'icônes de sa classe,
        # mxl_gfx.skill_icon_file ; ✅ captures en jeu : Flamefront 92, Ignis Fatuus 282)
        self.skill_desc, self.skill_icon = {}, {}
        for sid, r in enumerate(self._rows('skills')):
            self.skill_class[sid] = r[0x0C]
            self.skill_req[sid] = struct.unpack_from('<h', r, 0x174)[0]
            sd = struct.unpack_from('<H', r, 0x194)[0]
            if 0 < sd < len(sd_rows):
                name_id = struct.unpack_from('<H', sd_rows[sd], 0x08)[0]
                self.skill_names[sid] = self.s(name_id)
                self.skill_names_raw[sid] = (self.strings.get(name_id) or (None, ''))[1]
                # texte absent : le jeu pointe vers une chaîne vide affichée « FLYING POLAR BUFFALO ERROR » (73 compétences
                # lancées par chance : Thunder Wave, Charged Bolt…) -> pas de description
                desc = self.s(struct.unpack_from('<H', sd_rows[sd], 0x0C)[0]) or ''
                self.skill_desc[sid] = '' if 'BUFFALO' in desc else desc
                self.skill_icon[sid] = struct.unpack_from('<H', sd_rows[sd], 0x16)[0]
        # grilles de rangement (inventory.bin, 240 octets par ligne : colonnes u8 @0x10, lignes u8 @0x11) : ligne 0 =
        # inventaire (identique pour les 7 classes), 8 = coffre, 9 = cube ; ✅ coffre 14 × 14 confirmé en jeu
        inv = self._rows('inventory')
        self.grids = {name: (inv[row][0x10], inv[row][0x11]) for name, row in (('inventory', 0), ('stash', 8), ('cube', 9))}

    def _load_bases(self):
        """weapons / armor / misc.bin : une fiche ItemBase par code, et l'ordre global des objets (item_index)."""
        # objets de base : une fiche ItemBase par code (weapons / armor / misc.bin, 424 octets par ligne)
        self.bases = {}
        self.item_index = []   # ordre armes + armures + misc (index utilisé par runes.bin et gems.bin)
        for kind in ('weapons', 'armor', 'misc'):
            for r in self._rows(kind):
                code = r[0x80:0x84].decode('latin1')
                self.item_index.append(code)
                if code in self.bases:
                    continue
                name_idx = struct.unpack_from('<H', r, 0xF4)[0]
                weapon = kind == 'weapons'
                self.bases[code] = ItemBase(
                    code=code, kind=kind, name=self.s(name_idx), name_raw=(self.strings.get(name_idx) or ('', ''))[1],
                    type=struct.unpack_from('<h', r, 0x11E)[0], type2=struct.unpack_from('<h', r, 0x120)[0], size=(r[0x10F] or 1, r[0x110] or 1),
                    level_req=r[0x13F], qlvl=r[0xFD], req_str_dex=struct.unpack_from('<HH', r, 0x10A), block=r[0x111],
                    inv_file=r[0x20:0x40].split(b'\0')[0].decode('latin1'), spell=struct.unpack_from('<I', r, 0x94)[0],
                    stack_max=struct.unpack_from('<H', r, 0xE4)[0] if r[0x132] else None,
                    def_range=struct.unpack_from('<ii', r, 0xCC) if kind == 'armor' else (0, 0),
                    two_handed=r[0x11C] if weapon else 0, max_sockets=r[0x138], quest=r[0x12A], durability=r[0x112],
                    auto_group=struct.unpack_from('<H', r, 0xF8)[0] if kind != 'misc' else 0,
                    dmg_bonus=struct.unpack_from('<HH', r, 0x106) if weapon else (0, 0),
                    wclass=r[0xC0:0xC4].decode('latin1').strip('\0 ') if weapon else '',
                    wsm=struct.unpack_from('<i', r, 0xD8)[0] if weapon else 0,
                    damage=dict(one_hand=(r[0xFE], r[0xFF]), throw=(r[0x100], r[0x101]),
                                two_hand=(r[0x102], r[0x103])) if weapon else None)

    def _load_mystic_orbs(self):
        """mysticorbs.bin (Median XL, 101 lignes de 143 octets, 08/10) : Mystic Orbs, n° = ligne (param de la stat 290 d'un
        objet, mxl_orbs) ; nom @0x00 (32 octets : « MO - Strength », « Idol of Stars »…), niveau requis ajouté u8 @0x20,
        texte de restriction u16 @0x21 (n° de texte du jeu : « (Armor Only) », « (Weapon Only) », « (Ring, Amulet or
        Quiver Only) », « (Any Equippable Item) », « (Shield Only) », « (Body Armor Only) » ; 0 : aucun), limite par objet
        u8 @0x2B (✅ wiki officiel « Unique Mystic Orbs » : +10 / limite 2, Imperfect Sphere +9 / 1, Apple of Discord
        +12 / 2, Weight of Talent +15 / 1, Solitude +20 / 1), 6 mods × (propriété, param, min, max) en i32 @0x2D
        (fin = -1) ; mods de propriété 403 (compteur d'un autre orbe) = verrous. Table absente (data/ d'une version
        antérieure de l'éditeur) : aucun orbe."""
        self.mystic_orbs = []
        try:
            rows = self._rows('mysticorbs')
        except OSError:
            return
        for r in rows:
            mods = [m for m in struct.iter_unpack('<4i', r[0x2D:0x2D + 96]) if m[0] >= 0]
            self.mystic_orbs.append(dict(
                name=r[:32].split(b'\0')[0].decode('latin1'), req_level=r[0x20], only=struct.unpack_from('<H', r, 0x21)[0], limit=r[0x2B],
                mods=[dict(zip(('prop', 'param', 'min', 'max'), m)) for m in mods if m[0] != 403],
                locks=[(m[1], m[2]) for m in mods if m[0] == 403]))

    def _load_areas(self):
        """levels.bin (544 octets par ligne) : zones {nom: (Normal, Nightmare, Hell)}, niveau des monstres de la zone
        (« area level ») u16 ×3 @0x16 (✅ Blood Moor 1 / 51 / 100, The Worldstone Chamber 50 / 100 / 125) ; nom @0xF5 ;
        villes (niveaux à 0) écartées."""
        self.areas = {}
        for r in self._rows('levels'):
            levels = struct.unpack_from('<3H', r, 0x16)
            name = r[0xF5:0xF5 + 40].split(b'\0')[0].decode('latin1')
            if name and any(levels):
                self.areas.setdefault(name, levels)

    def _load_treasure_classes(self):
        """treasureclassex.bin (Median XL : texte conservé, 736 octets par ligne) : classes de trésor, dans l'ordre de la
        table (numéro dans monstats = ligne + 513, les groupes de bases fabriqués par le jeu passant avant) :
        nom @0 (32 octets), tirages i32 @0x20, groupe u16 @0x24 et niveau u16 @0x26 (montée de palier, D2Common
        ordinal 10634), part de « rien » i32 @0x34, 10 éléments (64 octets) @0x38 et leurs poids i32 @0x2B8
        (✅ « H Equip 1 » : niveau 93, groupe 1, weap93 / armo93 19, weap90 / armo90 76…)."""
        self.treasure_classes = []
        for r in self._rows('treasureclassex'):
            items = [r[0x38 + 64 * i:0x38 + 64 * (i + 1)].split(b'\0')[0].decode('latin1') for i in range(10)]
            probs = struct.unpack_from('<10i', r, 0x2B8)
            self.treasure_classes.append(dict(
                name=r[:32].split(b'\0')[0].decode('latin1'), picks=struct.unpack_from('<i', r, 0x20)[0],
                group=struct.unpack_from('<H', r, 0x24)[0], level=struct.unpack_from('<H', r, 0x26)[0],
                nodrop=struct.unpack_from('<i', r, 0x34)[0],
                items=[(it, p) for it, p in zip(items, probs) if it]))

    def _load_hirelings(self):
        """hireling.bin (format D2 1.13c, 0x118 octets par ligne) : une ligne par type de mercenaire (Id u32 @0x04, celui
        de la sauvegarde) et tranche de niveau (Level u32 @0x1C) ; expérience par niveau @0x20 ; vie @0x24 / par niveau
        @0x28, défense @0x2C / @0x30, Force @0x34 / @0x38, Dextérité @0x3C / @0x40 (D2Game.dll 0x6fc68d9a)."""
        self.hirelings = []
        for r in self._rows('hireling'):
            (ident, level, exp, hp, hp_lvl, df, df_lvl, st, st_lvl, dx, dx_lvl) = (
                struct.unpack_from('<I', r, 0x04)[0], *struct.unpack_from('<10i', r, 0x1C))
            self.hirelings.append(dict(id=ident, level=level, exp_per_level=exp, life=hp, life_per_level=hp_lvl,
                                       defense=df, defense_per_level=df_lvl, strength=st, strength_per_level=st_lvl,
                                       dexterity=dx, dexterity_per_level=dx_lvl))

    def _load_gems(self):
        """gems.bin : bonus des gemmes et runes par groupe de types d'objets (armes, casques / armures, boucliers)."""
        # gemmes et runes : gems.bin, 192 octets ; objet = index global u32 @0x28 ;
        # 3 groupes (armes, casques/armures, boucliers) de 3 mods (propriété, param, min, max) en i32 @0x30
        self.gems = {}
        for r in self._rows('gems'):
            idx = struct.unpack_from('<I', r, 0x28)[0]
            if idx < len(self.item_index):
                self.gems[self.item_index[idx]] = [
                    [m for m in struct.iter_unpack('<4i', r[0x30 + 48 * g:0x60 + 48 * g]) if m[0] >= 0]
                    for g in range(3)]

    def base(self, code):
        """Fiche ItemBase d'un code d'objet (fiche par défaut, kind '?', si le code est inconnu)."""
        return self.bases.get(code) or ItemBase(code)

    def _animdata(self):
        """animdata.d2 (extrait de medianxl-YW5pbWRhdGE.mpq) : {cof: (images par direction, vitesse)}.
        256 blocs [nombre u32][nombre × 160 octets : nom COF 8 octets, images u32, vitesse u32, …]."""
        path = os.path.join(self.folder, 'animdata.d2')
        if not os.path.exists(path):
            return {}
        with open(path, 'rb') as f:
            d, p, recs = f.read(), 0, {}
        for _ in range(256):
            n = struct.unpack_from('<I', d, p)[0]; p += 4
            for _ in range(n):
                recs[d[p:p + 8].split(b'\0')[0].decode('latin1')] = struct.unpack_from('<II', d, p + 8)
                p += 160
        return recs

    def _rows(self, name):
        with open(os.path.join(self.folder, name + '.bin'), 'rb') as f:
            d = f.read()
        n = struct.unpack_from('<I', d)[0]
        rs = (len(d) - 4) // n
        return [d[4 + i * rs:4 + (i + 1) * rs] for i in range(n)]

    def type_ancestors(self, t):
        """Ensemble des types d'objet dont t hérite (lui compris)."""
        seen, todo = set(), [t]
        while todo:
            x = todo.pop()
            if x <= 0 or x in seen or x >= len(self.itypes):
                continue
            seen.add(x)
            todo.extend(self.itypes[x][1])
        return seen

    def skill(self, sid):
        """Nom d'une compétence (skilldesc, sinon clé « skillnameN », sinon numéro)."""
        n = self.skill_names.get(sid)
        if not n:
            n = self.key(f'skillname{sid}')
            if n == f'skillname{sid}':
                n = tr('skill.unknown', id=sid)
        return n

    def key(self, k):
        """Texte affiché pour une clé de string.tbl (la clé elle-même si absente)."""
        if not hasattr(self, '_bykey'):
            self._bykey = {}
            rank = lambda i: 0 if 10000 <= i < 20000 else 1 if i >= 20000 else 2
            for i, (kk, _) in sorted(self.strings.items(), key=lambda x: (rank(x[0]), x[0])):
                self._bykey.setdefault(kk, i)
        i = self._bykey.get(k)
        return self.s(i) if i is not None else k

    def color(self, idx):
        """Code couleur (caractère après ÿc) au début d'une chaîne, ou None."""
        v = self.strings.get(idx)
        txt = v[1] if v else ''
        return txt[2] if txt.startswith('ÿc') and len(txt) > 2 else None

    def s(self, idx):
        v = self.strings.get(idx)
        if not v:
            return ''
        return strip_colors(v[1])
