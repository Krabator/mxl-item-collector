"""Bibliothèque d'objets : catalogue des uniques et des objets de set du jeu, à compléter au fil des découvertes.

- Catalogue (catalog) : une entrée par ligne de uniqueitems.bin et de setitems.bin ayant un objet de base connu
  (1 819 uniques et 198 objets de set en Median XL 2.14.4 ; lignes désactivées exclues : disabled), identifiée par
  sa clé : 'unique:<n° de ligne>' ou
  'set:<n° de ligne>'. Les runewords n'y sont pas (même runeword sur des bases différentes : pas comparables).
- Reconnaissance (entry_key) : clé de l'entrée du catalogue d'un objet lu dans un coffre, ou None.
- Découvertes (Library) : fichier library.json ; une entrée est « trouvée » dès qu'un exemplaire est vu dans un
  coffre ouvert par l'éditeur : date et coffre de la première découverte, exemplaires distincts vus (n° propre
  de chaque objet, enregistré dans l'objet). Écriture sûre (fichier temporaire puis remplacement).
- Collection : au plus un exemplaire par entrée, toujours le meilleur (rank : qualité avec les priorités du profil,
  puis somme des valeurs les plus prioritaires ; égalité = l'exemplaire déjà rangé est gardé). Transfert
  (plan_transfer, apply_transfer) : les objets rangés sortent du coffre ; l'ancien exemplaire remplacé est rapatrié
  à la place du nouveau (même objet de base, même taille) ou détruit ; un exemplaire moins bon que celui rangé est
  gardé dans le coffre ou détruit. Objets détruits : journal de la dernière opération, restaurable
  (restore_destroyed). Sortie d'un objet de la collection vers le coffre (take_out). Jamais de perte : transfert =
  bibliothèque écrite d'abord, puis le coffre (en cas d'échec du coffre, bibliothèque remise dans son état d'avant) ;
  restauration et sortie = coffre d'abord, puis bibliothèque (au pire un objet en double, jamais perdu).
- Protection du fichier (il contient de vrais objets) : un fichier présent mais illisible n'est jamais écrasé (la
  bibliothèque passe en lecture seule) ; chaque écriture garde la version précédente dans library.json.bak ; un
  éditeur ouvert réserve la bibliothèque (verrou du système, libéré même si l'éditeur plante) : un deuxième
  éditeur la passe en lecture seule. Lecture seule = toute écriture refusée (LibraryError) avant de toucher au coffre.
"""
import base64, copy, json, os, re, shutil, time
from i18n import tr
from mxl_rules import unique_row, set_row, table_row, item_type_codes, indestructible_base, row_always_ethereal
from mxl_save import (check_game_closed, read_file, read_items, ItemFile, item_blob, blob_item, edit_stash, free_spot,
                      edit_containers, placement_error, EditError)

CATEGORIES = ('weapons', 'armor', 'jewelry', 'charm', 'jewel', 'relic', 'other')   # ordre d'affichage
# familles (filtre « Type » de l'écran Library) : uniques à tiers (base « (1) » à « (4) »), uniques Sacred par niveau
# d'objet (un unique ne tombe que d'un niveau de zone / monstre au moins égal) : SU 105 (zones 104+), SSU 120 (119+),
# SSSU 130 (130+) d'après la page officielle « Sacred Uniques » (✅ niveaux identiques au site pour 380 uniques) ;
# anneaux, amulettes, joyaux et carquois sacrés classés de même par niveau d'objet (09/10 : ✅ game feed du Discord de
# Median XL, Signet of the Gladiator 120 « SSU », Jewel of Luck et Arkenstone 130 « SSSU ») ; autres uniques (charmes,
# reliques, quêtes, bijoux ordinaires, Sacred qui ne tombent pas) ; objets de set
FAMILIES = ('tiered', 'sacred', 'ssu', 'sssu', 'other', 'set')
SU_LEVEL, SSU_LEVEL, SSSU_LEVEL = 105, 120, 130
# types d'objet des bijoux, joyaux et carquois sacrés (« The best rings, amulets, jewels and quivers are also marked as
# sacred uniques », page officielle) : uniques qui peuvent tomber, de niveau d'objet SU_LEVEL ou plus
SACRED_JEWELRY_TYPES = frozenset(('ring', 'amul', 'jewl', 'bowq', 'xboq'))


def _category(code, name, data):
    """Catégorie d'une entrée : armes, armures, bijoux (bagues, amulettes), charmes, joyaux, reliques, autres."""
    kind = data.base(code).kind
    if kind in ('weapons', 'armor'):
        return kind
    types = item_type_codes(dict(code=code), data)
    if name == 'Relic':
        return 'relic'
    if types & {'ring', 'amul'}:
        return 'jewelry'
    if 'char' in types:
        return 'charm'
    if 'jewl' in types:
        return 'jewel'
    return 'other'


DISABLED_LEVEL = 250   # niveau d'objet inatteignable : ligne désactivée par Median XL (voir disabled)


def disabled(r):
    """Ligne de table désactivée, jamais obtenable, pas au catalogue : aucun affixe et
    - niveau d'objet DISABLED_LEVEL (✅ set 25 « Orphan's Call » de Diablo II, remplacé par 5 lignes vides VD_Catalyst,
      VD_Darkness, VD_Hunger, VD_Judgment, The Presence) ;
    - ou niveau d'objet 0 et rareté 0 (ne tombe pas) : emplacement vide (✅ 90 uniques « Relic » de Median XL, infobulle
      réduite à « Relic » ; les autres entrées sans affixe, ex. Golden Cycle, Ring of Pride, ont un niveau)."""
    if r.get('mods'):
        return False
    level = r.get('level') or 0
    return level >= DISABLED_LEVEL or (level == 0 and r.get('rarity', 1) == 0)


NO_DISENCHANT = 276   # stat « Cannot be Disenchanted » (propriété 236)


def quest_item(r, data):
    """Objet de quête, pas au catalogue (ni découvertes, ni transferts) :
    - stat NO_DISENCHANT (✅ objets de quête de Diablo II : Amulet of the Viper, Staff of Kings, Horadric Staff, Hell
      Forge Hammer, Khalim's Flail, Khalim's Will) ;
    - ou ne tombe pas (rareté 0) et niveau d'objet DISABLED_LEVEL ou plus (✅ les 3 Akara's Robe données par la quête,
      « Cannot be Upgraded » sur les deux premières)."""
    if any(NO_DISENCHANT in data.props[m['prop']] for m in r.get('mods', [])):
        return True
    return r.get('rarity', 1) == 0 and (r.get('level') or 0) >= DISABLED_LEVEL


def catalog(data):
    """Entrées du catalogue, dans l'ordre des tables (uniques puis sets) :
    [{key, kind ('unique' / 'set'), row, name (nom affiché, lignes séparées par « / »), code, base (nom de l'objet
    de base), category, droppable (peut tomber : rareté > 0 pour les uniques ; toujours vrai pour les sets),
    level, level_req, family (FAMILIES)}]."""
    out = []
    for kind, rows in (('unique', data.uniques), ('set', data.set_items)):
        for row, r in enumerate(rows):
            # ligne inutilisée (code vide ou inconnu), désactivée, ou objet de quête
            if r['code'] not in data.bases or disabled(r) or quest_item(r, data):
                continue
            name = data.key(r['name']).replace('\n', ' / ')
            base, droppable = data.base(r['code']).name, r.get('rarity', 1) > 0
            out.append(dict(key=f'{kind}:{row}', kind=kind, row=row, name=name, code=r['code'],
                            base=base, category=_category(r['code'], data.key(r['name']), data),
                            droppable=droppable, level=r.get('level'),
                            # niveau requis : le plus grand de l'unique / objet de set et de son objet de base, comme le
                            # jeu (D2Common.dll 0x6fd7652d ; ✅ Mendeln's Companion T1 : 4 et Spirit Edge (1) 5 -> 5)
                            level_req=max(r.get('level_req') or 0, data.base(r['code']).level_req),
                            family=family(kind, base, r.get('level'), droppable,
                                          item_type_codes(dict(code=r['code']), data))))
    return out


TIERS = ('1', '2', '3', '4', 'sacred')   # tiers d'un objet de base : « (1) » à « (4) », « (Sacred) » en fin de nom


def base_tier(base_name):
    """Tiers d'un objet de base d'après la fin de son nom (TIERS), ou None (objet sans tiers)."""
    m = re.search(r'\((1|2|3|4|Sacred)\)$', base_name or '')
    return m.group(1).lower() if m else None


def family(kind, base, level, droppable, types=()):
    """Famille d'une entrée (FAMILIES) : 'set' ; unique 'tiered' (objet de base à tiers « (1) » à « (4) ») ; unique
    Sacred qui peut tomber : 'sssu' (niveau d'objet 130 et plus), 'ssu' (120 et plus), sinon 'sacred' (SU : 105, et
    les rares 80 à 110) ; anneau, amulette, joyau ou carquois unique (types : types de l'objet de base,
    SACRED_JEWELRY_TYPES) qui peut tomber, de niveau 105 ou plus : mêmes seuils ; autres uniques : 'other' (charmes,
    reliques, quêtes, bijoux de niveau plus bas, Sacred qui ne tombent pas)."""
    if kind == 'set':
        return 'set'
    if re.search(r'\([1-4]\)$', base):
        return 'tiered'
    level = level or 0
    if droppable and (base.endswith('(Sacred)') or (SACRED_JEWELRY_TYPES & set(types) and level >= SU_LEVEL)):
        return 'sssu' if level >= SSSU_LEVEL else 'ssu' if level >= SSU_LEVEL else 'sacred'
    return 'other'


def entry_key(it, data):
    """Clé de l'entrée du catalogue d'un objet ('unique:<n°>' ou 'set:<n°>'), ou None (pas au catalogue)."""
    for kind, row in (('unique', unique_row(it, data)), ('set', set_row(it, data))):
        if row and not disabled(row) and not quest_item(row, data):
            return f"{kind}:{it['set_unique_id']}"
    return None


ETHEREAL = ':eth'   # suffixe de la place de l'exemplaire éthéré d'une entrée dans la collection ('unique:375:eth')


def always_ethereal(key, data):
    """Entrée toujours éthérée (propriété « ethereal » dans sa ligne de table, ✅ Iron Shard) : une seule place."""
    return row_always_ethereal(table_row(key, data), data)


def no_ethereal(code, data):
    """Vrai pour un objet de base dont la collection ne range pas d'exemplaire éthéré : base sans durabilité (arcs,
    arbalètes et 10 autres bases ; mxl_rules.indestructible_base ; décision du 07/10 : option (a))."""
    return indestructible_base(code, data)


def two_variants(key, data):
    """L'objet de cette entrée a une place normale et une place éthérée dans la collection : arme ou armure (les seules
    qui peuvent être éthérées), sauf entrée toujours éthérée et base sans durabilité (no_ethereal)."""
    code = table_row(key, data)['code']
    return data.base(code).kind in ('weapons', 'armor') and not always_ethereal(key, data) and not no_ethereal(code, data)


STORAGE = 'superior'   # préfixe des places du stockage des supérieurs ('superior:<code>:s<sockets>[:eth]')
PHYSICAL_RESIST = 36   # stat « Physical Resist » : +1 % au plus sur une armure supérieure (règle du 06/10)
ENHANCED_DAMAGE = 17   # stat « Enhanced Damage » (max ; 18 = min, liée)
MOVEMENT_SPEED = 96    # stat « Movement Speed » : bottes supérieures, gardées sur elle d'abord (règle du 06/10)


def storage_key(it, data):
    """Place de l'objet dans le stockage des supérieurs (hors collection : ni découverte, ni avancement), ou None :
    supérieur, arme ou armure, au moins un socket, aucun objet serti (objets runiques exclus) ; une place par objet de
    base et nombre de sockets, plus ETHEREAL pour un exemplaire éthéré (décisions du 06/10)."""
    if it.get('quality') != 'superior' or data.base(it['code']).kind not in ('weapons', 'armor'):
        return None
    if not it.get('sockets') or it.get('socketed') or (it.get('ethereal') and no_ethereal(it['code'], data)):
        return None
    key = f"{STORAGE}:{it['code'].strip()}:s{it['sockets']}"
    return key + ETHEREAL if it.get('ethereal') else key


def is_storage(slot):
    """Vrai pour une place du stockage des supérieurs (storage_key)."""
    return slot.startswith(STORAGE + ':')


def storage_parts(slot):
    """(code de l'objet de base, nombre de sockets, éthéré) d'une place du stockage."""
    _, code, sockets = entry_of(slot).split(':')
    return code, int(sockets[1:]), slot.endswith(ETHEREAL)


def slot_key(it, data):
    """Place de l'objet dans la collection : clé de l'entrée, suivie de ETHEREAL pour un exemplaire éthéré (rangé à
    part : un exemplaire normal et un éthéré par entrée), sauf entrée toujours éthérée ; sinon sa place dans le
    stockage des supérieurs (storage_key) ; None si ni l'un ni l'autre."""
    key = entry_key(it, data)
    if key and it.get('ethereal') and not always_ethereal(key, data):
        return None if no_ethereal(it['code'], data) else key + ETHEREAL
    return key or storage_key(it, data)


def entry_of(slot):
    """Clé de l'entrée du catalogue d'une place de la collection."""
    return slot[:-len(ETHEREAL)] if slot.endswith(ETHEREAL) else slot


class LibraryError(Exception):
    """Bibliothèque en lecture seule (fichier illisible ou déjà ouvert par un autre éditeur) : rien n'est écrit."""


class Library:
    """Bibliothèque enregistrée dans un fichier JSON : découvertes {'found': {clé: {'date': 'AAAA-MM-JJ HH:MM',
    'source': coffre, 'instances': [n° propres des exemplaires vus]}}}, collection, journal.
    readonly : message (traduit) expliquant pourquoi rien ne peut être écrit, ou None. lock=True (éditeur) : verrou."""

    def __init__(self, path, lock=False):
        self.path = path
        self.readonly = None
        self._lock = None
        self.state = {}
        if os.path.exists(path):
            try:
                with open(path, encoding='utf-8') as f:
                    self.state = json.load(f)
                if not isinstance(self.state, dict):
                    raise ValueError('not a JSON object')
            except (OSError, ValueError) as e:   # jamais écrasé : lecture seule, fichier conservé tel quel
                self.state = {}
                self.readonly = tr('library.unreadable', file=path, error=f'{type(e).__name__}: {e}')
        if lock and not self.readonly:
            self._acquire_lock()
        self.state.setdefault('found', {})

    def _acquire_lock(self):
        """Verrou exclusif sur <fichier>.lock tant que l'éditeur est ouvert (libéré par le système à sa fermeture,
        même en cas de plantage) ; déjà pris par un autre éditeur : lecture seule."""
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        fh = open(self.path + '.lock', 'a+')
        try:
            fh.seek(0)
            try:
                import msvcrt
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            except ImportError:   # hors Windows
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock = fh
        except OSError:
            fh.close()
            self.readonly = tr('library.locked', file=self.path)

    def release(self):
        """Libère le verrou (fermeture de l'éditeur)."""
        if self._lock:
            self._lock.close()
            self._lock = None

    def check_writable(self):
        """LibraryError si la bibliothèque est en lecture seule (à appeler avant toute modification du coffre)."""
        if self.readonly:
            raise LibraryError(self.readonly)

    @property
    def found(self):
        return self.state['found']

    @property
    def collection(self):
        """Collection : {place (slot_key : clé du catalogue, + ETHEREAL pour l'exemplaire éthéré): {'blob': octets de
        l'objet (base64), 'date', 'source', 'id'}}."""
        return self.state.setdefault('collection', {})

    @property
    def storage(self):
        """Stockage des supérieurs : {place (storage_key): même forme que collection} ; hors collection (ni compté dans
        l'avancement, ni découvertes)."""
        return self.state.setdefault('storage', {})

    def slots(self, key):
        """Section de la bibliothèque qui range cette place : storage (supérieurs) ou collection."""
        return self.storage if is_storage(key) else self.collection

    @property
    def journal(self):
        """Objets détruits lors de la dernière opération de transfert, restaurables :
        {'date', 'source', 'items': [{'key', 'blob', 'page', 'x', 'y', 'file', 'where'}]} (file, where : fichier et
        conteneur d'origine ; absents des journaux plus anciens)."""
        return self.state.setdefault('journal', dict(date=None, source=None, items=[]))

    def stored_item(self, key, data):
        """Exemplaire rangé à cette place (slot_key : collection ou stockage), objet lu depuis ses octets, ou None."""
        e = self.slots(key).get(key)
        return blob_item(base64.b64decode(e['blob']), data) if e else None

    def record_found(self, items, data, source):
        """Enregistre les objets du catalogue présents dans items (objets sertis compris) ; source = nom du coffre.
        Renvoie les clés des entrées trouvées pour la première fois. Le fichier n'est écrit que s'il y a du nouveau."""
        new, changed = [], False
        now = time.strftime('%Y-%m-%d %H:%M')
        for it in items:
            for x in [it] + it.get('socketed', []):
                key = entry_key(x, data)
                if key is None:
                    continue
                entry = self.found.get(key)
                if entry is None:
                    entry = self.found[key] = dict(date=now, source=source, instances=[])
                    new.append(key)
                if x.get('id') is not None and x['id'] not in entry['instances']:
                    entry['instances'].append(x['id'])
                    changed = True
        if new or changed:
            self.save()
        return new

    def save(self):
        """Écriture sûre : fichier temporaire, copie de la version précédente dans <fichier>.bak, puis remplacement
        (dossier créé au besoin). LibraryError en lecture seule."""
        self.check_writable()
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        if os.path.exists(self.path):
            shutil.copy2(self.path, self.path + '.bak')
        tmp = self.path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)


# ---------------------------------------------------------------- collection

def rank(it, data, priorities):
    """Classement d'un exemplaire : (critère d'abord, qualité, départage), le plus grand est le meilleur. Critère :
    supérieur du stockage = armure avec Physical Resist (1) avant sans (0), bottes = (Movement Speed, Physical Resist),
    arme = Enhanced Damage brut (décisions du 06/10) ; 0 pour les uniques et sets. Qualité = item_quality avec les priorités du profil de l'objet
    (priority_profile ; priorities = {profil: {stat: priorité}}) ; départage = top_priority_sum."""
    from mxl_edit import edit_groups, item_quality, top_priority_sum, priority_profile
    groups = edit_groups(it, data)
    prio = priorities.get(priority_profile(it, data)[0], {})
    q = item_quality(groups, prio)
    first = 0
    if storage_key(it, data):
        value = lambda sid: next((s['value'] for s in it['stats'] if s['id'] == sid), 0)
        if data.base(it['code']).kind != 'armor':
            first = value(ENHANCED_DAMAGE)
        elif 'boot' in item_type_codes(it, data):
            first = (value(MOVEMENT_SPEED), int(value(PHYSICAL_RESIST) > 0))
        else:
            first = int(value(PHYSICAL_RESIST) > 0)
    return (first, q if q is not None else 0.0, top_priority_sum(groups, prio))


def transfer_items(sources, data, bag_charms=True):
    """Objets de premier niveau de plusieurs conteneurs [(fichier, conteneur)] (read_items), chacun marqué de sa
    source (_src) : les offsets ne sont uniques que dans un fichier. bag_charms=False : charmes du sac écartés (ils
    donnent leurs bonus au personnage ; transfert du personnage entier)."""
    items = []
    for path, where in sources:
        for it in read_items(path, data, where):
            if not bag_charms and where == 'inventory' and 'char' in item_type_codes(it, data):
                continue
            it['_src'] = (path, where)
            items.append(it)
    return items


def item_ref(it):
    """Identifiant d'un objet d'un plan de transfert (clé de choices) : (source, offset), source = _src ou None."""
    return it.get('_src'), it['_offset']


def plan_transfer(items, library, data, priorities, only=None):
    """Plan du transfert des objets (premier niveau, d'un ou plusieurs conteneurs : transfer_items ; only = offsets à
    traiter, par défaut tous) : [{kind, key, item, rank, old}] (key = place, slot_key : exemplaires normaux et éthérés
    comparés séparément ; exemplaires de tous les conteneurs comparés ensemble) avec kind =
    - 'store' : entrée sans exemplaire rangé, meilleur exemplaire rangé ;
    - 'upgrade' : exemplaire meilleur que celui rangé (old = rang de celui-ci), qui sera rapatrié ou détruit ;
    - 'worse' : exemplaire moins bon que la référence (old : exemplaire rangé ou meilleur exemplaire),
      gardé à sa place ou détruit."""
    by_key = {}
    for it in items:
        key = slot_key(it, data)
        if key and (only is None or it['_offset'] in only):
            by_key.setdefault(key, []).append(it)
    actions = []
    for key, cands in by_key.items():
        ranked = sorted(((rank(it, data, priorities), it) for it in cands), key=lambda r: r[0], reverse=True)
        stored = library.stored_item(key, data)
        ref = rank(stored, data, priorities) if stored else None
        (best_rank, best), rest = ranked[0], ranked[1:]
        if ref is None or best_rank > ref:
            actions.append(dict(kind='store' if ref is None else 'upgrade', key=key, item=best, rank=best_rank, old=ref))
            ref = best_rank
        else:
            rest = ranked
        actions += [dict(kind='worse', key=key, item=it, rank=r, old=ref) for r, it in rest]
    return actions


def apply_transfer(path, data, library, actions, choices=None, source='', backup=True, where=None):
    """Applique un plan de transfert. Objets d'un conteneur (path, where), ou de plusieurs (source de chaque objet :
    _src, transfer_items). choices = {item_ref de l'objet: 'exchange' | 'destroy'} pour 'upgrade' (ancien exemplaire
    rapatrié à la place du nouveau ou détruit ; défaut 'exchange') et 'keep' | 'destroy' pour 'worse' (défaut 'keep').
    Contrôle que les objets n'ont pas changé depuis le plan. Le journal des objets détruits est remplacé.
    source : nom de la provenance (défaut : nom du fichier de l'objet) ; backup : booléen ou fonction(fichier).
    Écritures : bibliothèque d'abord, puis chaque fichier en une fois (sac et cube d'un personnage ensemble) ; si un
    fichier ne peut être écrit, la bibliothèque est remise en état pour les objets de ce fichier et des suivants
    (au pire un objet en double, jamais perdu). Renvoie {fichier écrit: sauvegarde ou None}."""
    library.check_writable()
    check_game_closed()   # avant d'écrire la bibliothèque (les fichiers sont écrits ensuite)
    choices = choices or {}
    groups = {}   # fichier -> conteneur -> actions
    for a in actions:
        f, w = a['item'].get('_src') or (path, where)
        groups.setdefault(f, {}).setdefault(w, []).append(a)
    before = copy.deepcopy(library.state)
    now = time.strftime('%Y-%m-%d %H:%M')
    changes, destroyed, keys = {}, [], {}

    def b64(b):
        return base64.b64encode(b).decode('ascii')
    for f, by_where in groups.items():
        buf = read_file(f)
        name = source or os.path.basename(f)
        changes[f], keys[f] = {}, []
        for w, acts in by_where.items():
            by_off = {i['_offset']: i for i in read_items(f, data, w)}
            for a in acts:
                cur = by_off.get(a['item']['_offset'])
                if cur is None or (cur['code'], cur.get('id')) != (a['item']['code'], a['item'].get('id')):
                    raise EditError(tr('err.changed'))
            remove, insert = [], []
            for a in acts:
                it = by_off[a['item']['_offset']]
                ref = item_ref(a['item'])
                blob, place = item_blob(buf, it), (it['page'], it['x'], it['y'])
                lost = lambda key, b: destroyed.append(dict(key=key, blob=b64(b), page=place[0], x=place[1], y=place[2],
                                                            file=f, where=w))
                if a['kind'] in ('store', 'upgrade'):
                    if a['kind'] == 'upgrade':   # ancien exemplaire : à la place du nouveau (même taille) ou détruit
                        old = base64.b64decode(library.slots(a['key'])[a['key']]['blob'])
                        if choices.get(ref, 'exchange') == 'exchange':
                            insert.append((*place, old))
                        else:
                            lost(a['key'], old)
                    library.slots(a['key'])[a['key']] = dict(blob=b64(blob), date=now, source=name, id=it.get('id'))
                    keys[f].append(a['key'])
                    remove.append(it['_offset'])
                elif choices.get(ref, 'keep') == 'destroy':
                    lost(a['key'], blob)
                    remove.append(it['_offset'])
            if remove or insert:
                changes[f][w] = (remove, insert)
    names = sorted({source or os.path.basename(f) for f in groups})
    library.state['journal'] = dict(date=now, source=', '.join(names), items=destroyed)
    library.save()   # bibliothèque d'abord : une coupure ensuite laisse au pire un objet en double, jamais perdu
    baks, todo = {}, [f for f in changes if changes[f]]
    for k, f in enumerate(todo):
        try:
            baks[f] = edit_containers(f, data, changes[f], backup(f) if callable(backup) else backup)
        except BaseException:   # fichiers non écrits : leurs objets rendus à la bibliothèque d'avant
            undone = set(todo[k:])
            for g in undone:
                for key in keys[g]:
                    section = 'storage' if is_storage(key) else 'collection'
                    if key in before.get(section, {}):
                        library.slots(key)[key] = before[section][key]
                    else:
                        library.slots(key).pop(key, None)
            library.journal['items'] = [e for e in destroyed if e['file'] not in undone]
            if not baks:
                library.state = before
            library.save()
            raise
    return baks


def restore_destroyed(path, data, library, backup=True):
    """Remet les objets détruits lors de la dernière opération dans leur fichier et leur conteneur d'origine (path :
    coffre des entrées d'un journal plus ancien, sans fichier noté) : à leur place d'origine si elle est libre, sinon à
    la première place libre ; ceux qui ne rentrent pas restent dans le journal. Chaque fichier est écrit d'abord, puis
    le journal. backup : booléen ou fonction(fichier). Renvoie ({fichier écrit: sauvegarde ou None}, objets restaurés,
    objets restés dans le journal)."""
    library.check_writable()
    groups = {}
    for e in library.journal['items']:
        groups.setdefault((e.get('file') or path, e.get('where')), []).append(e)
    baks, done = {}, 0
    for (f, w), entries in groups.items():
        if not f:
            continue
        items = ItemFile(f, data, where=w)
        placed = items.items
        inserts, back = [], []
        for e in entries:
            blob = base64.b64decode(e['blob'])
            it = blob_item(blob, data)
            spot = (e['page'], e['x'], e['y'])
            if placement_error(placed, it, *spot, data, items.box) is not None:
                spot = free_spot(placed, it, data, box=items.box)
            if spot is None:
                continue
            inserts.append((*spot, blob))
            back.append(e)
            it['page'], it['x'], it['y'] = spot
            placed.append(it)
        if inserts:
            baks[f] = edit_stash(f, data, insert=inserts, backup=backup(f) if callable(backup) else backup, where=w)
            library.journal['items'] = [e for e in library.journal['items'] if not any(e is b for b in back)]
            library.save()
            done += len(inserts)
    return baks, done, len(library.journal['items'])


def take_out(path, data, library, key, backup=True):
    """Sort de la collection l'exemplaire rangé à cette place (slot_key) et le pose dans le coffre, à la première place
    libre (EditError si le coffre est plein). Coffre écrit d'abord, puis la bibliothèque. Renvoie (sauvegarde ou None,
    (page, x, y))."""
    library.check_writable()
    e = library.slots(key).get(key)
    if e is None:
        raise EditError(tr('library.not_stored'))
    blob = base64.b64decode(e['blob'])
    f = ItemFile(path, data)
    spot = free_spot(f.items, blob_item(blob, data), data, box=f.box)
    if spot is None:
        raise EditError(tr('library.no_space'))
    bak = edit_stash(path, data, insert=[(*spot, blob)], backup=backup)
    del library.slots(key)[key]
    library.save()
    return bak, spot
