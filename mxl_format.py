"""Format binaire des objets D2 1.13c / Median XL (bits de poids faible en premier) : lecture et écriture de
champs de bits, fiches Item / Character, lecture d'un objet et de ses listes de stats."""
import stat_ids as S
from i18n import tr


class FormatError(Exception):
    """Fichier de sauvegarde dont la structure n'est pas celle attendue (lecture refusée)."""


def expect(buf, pos, marker):
    """Vérifie que buf contient marker (octets) à l'octet pos, sinon FormatError."""
    if bytes(buf[pos:pos + len(marker)]) != marker:
        shown = marker.decode('latin1') if marker.isalpha() else marker.hex(' ').upper()   # « JM » ou « 55 AA 55 AA »
        raise FormatError(tr('err.format', expected=shown, pos=pos))


# Stats enregistrées en groupe dans le fichier : lire la première implique de lire les suivantes
STAT_GROUPS = {S.ENH_DAMAGE_MAX: [S.ENH_DAMAGE_MIN], S.FIRE_MIN: [S.FIRE_MAX], S.LIGHTNING_MIN: [S.LIGHTNING_MAX],
               S.MAGIC_MIN: [S.MAGIC_MAX], S.COLD_MIN: [S.COLD_MAX, S.COLD_LENGTH],
               S.POISON_MIN: [S.POISON_MAX, S.POISON_LENGTH]}


class Record(dict):
    """Dictionnaire à champs déclarés (FIELDS) : lire, écrire ou tester un champ non déclaré lève une erreur,
    au lieu de renvoyer None en silence (ex. faute de frappe « it.get('sokets') »). Un champ déclaré mais
    absent se comporte comme dans un dictionnaire (it.get(champ) -> None, it[champ] -> KeyError)."""
    FIELDS = frozenset()

    def _check(self, key):
        if key not in self.FIELDS:
            raise KeyError(f"{type(self).__name__} : champ inconnu {key!r}")

    def __init__(self, *args, **kw):
        super().__init__()
        self.update(*args, **kw)

    def update(self, *args, **kw):
        for k, v in dict(*args, **kw).items():
            self[k] = v

    def __setitem__(self, key, value):
        self._check(key)
        super().__setitem__(key, value)

    def __getitem__(self, key):
        self._check(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self._check(key)
        return super().get(key, default)

    def __contains__(self, key):
        self._check(key)
        return super().__contains__(key)


class Item(Record):
    """Objet lu dans un fichier de sauvegarde (parse_item). Champs, dans l'ordre du format D2 1.13c :
    - en-tête : identified, has_sockets (a des sockets), ethereal, version, location (0 rangé, 1 porté,
      2 ceinture), equipped, x, y, panel, code, name (nom de base), socketed_count (objets sertis) ;
    - objet non simple : id, ilvl, quality ('low', 'normal', 'superior', 'magic', 'set', 'rare', 'unique',
      'crafted', 'honorific' ; 'unknown' si code inconnu), image (variante d'icône), auto_affix, subquality, prefix, suffix, set_unique_id, rare_names,
      rare_affixes, runeword, personalized_name ;
    - données de type : defense (armures), max_durability, durability, quantity (empilables), sockets ;
    - listes de stats : stats, set_stats_0 à set_stats_4, stats_runeword ;
    - position dans le fichier : page, _offset (octet de 'JM'), _size, _pos_bit (bit de x), _def_bit (bit de la
      défense), _auto_bit (bit du n° d'auto-affixe), _id_bit (bit du n° propre), _dur_bit (durabilité max, suivie de
      la durabilité courante), _sock_bit (nombre de sockets) ; socketed = objets sertis (liste d'Item) ;
    - _src : (fichier, conteneur) d'un objet lu pour un transfert de plusieurs conteneurs (mxl_library.transfer_items)."""
    FIELDS = frozenset("""identified has_sockets ethereal version location equipped x y panel code name stats
        socketed_count id ilvl quality image auto_affix subquality prefix suffix set_unique_id rare_names
        rare_affixes runeword personalized_name defense max_durability durability quantity sockets
        set_stats_0 set_stats_1 set_stats_2 set_stats_3 set_stats_4 stats_runeword
        page socketed _offset _size _pos_bit _def_bit _auto_bit _id_bit _dur_bit _sock_bit _src""".split())


class Character(Record):
    """Personnage (.d2s, mxl_save.load_character) : name, cls (0 Amazon … 6 Assassin), level, path, weapon_switch (jeu
    d'armes actif : 0 = I, 1 = II ; voir mxl_containers.weapon_slots),
    strength, energy, dexterity, vitality (base + objets portés), base_stats (stats de la section 'gf' : {n°: valeur},
    points répartis compris), skills (points investis : {n° de compétence: points},
    compétences à 0 absentes), items (objets du personnage, liste d'Item :
    portés, ceinture, inventaire, cube ; rangement de chacun : mxl_containers.place), corpse (objets restés sur le
    cadavre), mercenary (None ou dict : type, name_id, experience, dead, items), golem (objet du golem de fer ou
    None), extra_error (erreur de lecture du cadavre / mercenaire / golem, ou None)."""
    FIELDS = frozenset('name cls level path weapon_switch strength energy dexterity vitality base_stats skills items corpse mercenary golem '
                       'extra_error'.split())


class BitReader:
    """Lecture de champs de bits, bits de poids faible en premier (format D2). data : octets (bytes,
    bytearray ou memoryview, sans copie). Au-delà de la fin des données, les bits manquants valent 0."""
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def read(self, n):
        if n <= 0:
            return 0
        chunk = int.from_bytes(self.data[self.pos >> 3:(self.pos + n + 7) >> 3], 'little')
        self.pos += n
        return (chunk >> ((self.pos - n) & 7)) & ((1 << n) - 1)


QUALITY = {1: 'low', 2: 'normal', 3: 'superior', 4: 'magic', 5: 'set',
           6: 'rare', 7: 'unique', 8: 'crafted',
           # Median XL : objets honorifiques (✅ Soul Track, bottes d'un personnage de test, 07/10) : nom en deux mots
           # comme un rare (2 × 8 bits, rareprefix / raresuffix), sans ses 6 affixes ; stats dans la liste de l'objet
           9: 'honorific'}


def read_stats(br, data):
    """Liste de stats (id 9 bits + param + valeur, terminée par 0x1FF) : [{id, param, value, pos, desc, bits, add}].
    Largeurs lues dans itemstatcost : une stat absente des tables (data/ plus ancien que le jeu) lève FormatError."""
    stats = []
    while True:
        sid = br.read(9)
        if sid == 0x1FF:
            return stats
        if br.pos > len(br.data) * 8:   # fin des données sans marqueur de fin : lecture décalée (sinon boucle sans fin)
            raise FormatError(tr('err.truncated'))
        for s in [sid] + STAT_GROUPS.get(sid, []):
            if s not in data.isc:
                raise FormatError(tr('err.unknown_stat', stat=s))
            c = data.isc[s]
            param = br.read(c['param']) if c['param'] else None
            pos = br.pos   # position (en bits, après 'JM') de la valeur : sert à l'édition
            raw = br.read(c['bits'])
            stats.append(dict(id=s, param=param, value=raw - c['add'], pos=pos,
                              desc=c['desc'], bits=c['bits'], add=c['add']))


SET_UNIQUE_ID_BITS = 15   # numéro de set / d'unique (12 bits dans D2 1.13c, élargi par Median XL)
CODE_BIT = 60   # position (bits après 'JM') du code de l'objet : drapeaux 32, version 10, emplacement 3, équipé 4, x 4, y 4, panneau 3


def item_code(blob):
    """Code de l'objet (4 caractères) d'un blob commençant par 'JM', sans lire le reste."""
    br = BitReader(blob[2:])
    br.read(CODE_BIT)
    return ''.join(chr(br.read(8)) for _ in range(4))


def parse_item(blob, data):
    """blob commence par 'JM'."""
    expect(blob, 0, b'JM')
    br = BitReader(blob[2:])
    it = Item()
    flags = br.read(32)
    it['identified'] = bool(flags >> 4 & 1)
    it['has_sockets'] = bool(flags >> 11 & 1)
    simple = bool(flags >> 21 & 1)
    it['ethereal'] = bool(flags >> 22 & 1)
    personalized = flags >> 24 & 1
    runeword = flags >> 26 & 1
    it['version'] = br.read(10)
    it['location'] = br.read(3)
    it['equipped'] = br.read(4)
    it['_pos_bit'] = br.pos   # position (en bits, après 'JM') de x (4 bits) puis y (4 bits) : sert au déplacement
    it['x'] = br.read(4)
    it['y'] = br.read(4)
    it['panel'] = br.read(3)
    code = ''.join(chr(br.read(8)) for _ in range(4))
    it['code'] = code
    base = data.base(code)
    kind, name = base.kind, base.name
    it['name'] = name
    it['stats'] = []
    if simple:
        it['socketed_count'] = br.read(1)
        return it, br
    it['socketed_count'] = br.read(3)
    it['_id_bit'] = br.pos   # position (bits après 'JM') du n° propre : réécrit par une copie (mxl_library.copy_out)
    it['id'] = br.read(32)
    it['ilvl'] = br.read(7)
    q = QUALITY.get(br.read(4), 'unknown')
    it['quality'] = q
    if br.read(1):
        it['image'] = br.read(3)
    if br.read(1):
        it['_auto_bit'] = br.pos   # position (bits après 'JM') du n° d'auto-affixe : sert au changement de palier
        it['auto_affix'] = br.read(11)
    if q in ('low', 'superior'):
        it['subquality'] = br.read(3)
    elif q == 'magic':
        it['prefix'] = br.read(11); it['suffix'] = br.read(11)
    elif q in ('set', 'unique'):
        # Median XL : 15 bits (12 dans D2 1.13c) ✅ Horadric Malus, unique de quête : 15 bits à 1 (32767 = aucune ligne)
        it['set_unique_id'] = br.read(SET_UNIQUE_ID_BITS)
    elif q == 'honorific':   # nom seul (« Soul » + « Track ») : 16 bits, puis la suite habituelle
        it['rare_names'] = (br.read(8), br.read(8))
    elif q in ('rare', 'crafted'):
        it['rare_names'] = (br.read(8), br.read(8))
        it['rare_affixes'] = [br.read(11) if br.read(1) else None for _ in range(6)]
    if runeword:
        it['runeword'] = br.read(12); br.read(4)
    if personalized:
        s = ''
        while True:
            c = br.read(7)
            if not c: break
            s += chr(c)
        it['personalized_name'] = s
    if code in ('tbk ', 'ibk '):
        br.read(5)
    br.read(1)  # drapeau « timestamp »
    if kind == 'armor':
        it['_def_bit'] = br.pos   # position (bits après 'JM') de la défense de base : sert à l'édition
        c = data.isc[S.DEFENSE]; it['defense'] = br.read(c['bits']) - c['add']
    if kind in ('armor', 'weapons'):
        it['_dur_bit'] = br.pos   # durabilité max puis courante : réécrites par la bascule éthérée
        maxd = br.read(data.isc[S.MAX_DURABILITY]['bits'])
        it['max_durability'] = maxd
        if maxd != data.isc[S.MAX_DURABILITY]['add']:   # valeur réelle = brut - add ; 0 = indestructible, pas de durabilité courante
            it['durability'] = br.read(data.isc[S.DURABILITY]['bits'])
    if data.base(code).stack_max is not None:
        it['quantity'] = br.read(9)
    if it['has_sockets']:
        it['_sock_bit'] = br.pos   # nombre de sockets : réécrit par « Max sockets »
        it['sockets'] = br.read(4)
    set_lists = br.read(5) if q == 'set' else 0
    it['stats'] = read_stats(br, data)
    for i in range(5):
        if set_lists >> i & 1:
            it['set_stats_%d' % i] = read_stats(br, data)
    if runeword:
        it['stats_runeword'] = read_stats(br, data)
    return it, br


def read_item_list(buf, p, count, data):
    """Lit count objets à partir de l'octet p de buf, chacun suivi de ses objets sertis (enregistrés juste après
    lui, non comptés dans count). Chaque objet reçoit _offset (octet de 'JM') et _size (octets) ; les objets de
    la liste reçoivent socketed (liste de leurs objets sertis). Renvoie (objets, octet suivant la liste).
    Format commun au coffre (.stash) et au personnage (.d2s)."""
    view = memoryview(buf)   # tranches sans copie

    def one(p):
        expect(buf, p, b'JM')
        try:
            it, br = parse_item(view[p:], data)
        except FormatError as e:   # message complété par l'objet en cause (code, position)
            raise FormatError(tr('err.in_item', code=item_code(view[p:]).strip(), pos=p, error=e)) from e
        it['_offset'], it['_size'] = p, 2 + (br.pos + 7) // 8
        return it, p + it['_size']
    items = []
    for _ in range(count):
        it, p = one(p)
        it['socketed'] = []
        for _ in range(it.get('socketed_count', 0) if it['has_sockets'] else 0):
            sub, p = one(p)
            it['socketed'].append(sub)
        items.append(it)
    return items, p


def write_bits(buf, bitpos, nbits, value):
    """Écrit value sur nbits à partir de bitpos (bits LSB en premier), en place."""
    for i in range(nbits):
        byte, bit = divmod(bitpos + i, 8)
        if value >> i & 1:
            buf[byte] |= 1 << bit
        else:
            buf[byte] &= ~(1 << bit) & 0xFF
