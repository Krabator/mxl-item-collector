"""Fichiers de sauvegarde : coffre (.stash, coffre partagé) et cube d'un personnage (.d2s) — lecture, déplacement
d'objets, édition de valeurs, transfert d'un fichier à l'autre, sauvegarde .bak — et personnage (.d2s : classe,
niveau, attributs, objets). Un fichier d'objets se modifie par ItemFile, qui cache la différence entre un coffre
(sections par page) et un personnage (une liste d'objets, taille et somme de contrôle dans l'en-tête)."""
import struct, os
import stat_ids as S
import settings
import mxl_game
from i18n import tr
from mxl_format import BitReader, Character, FormatError, read_item_list, write_bits, expect
# dossier du programme (sources ou exécutable) : les coffres qui s'y trouvent (tests/fixtures) ne sont jamais modifiés
from paths import APP_DIR as PROJECT_DIR, BACKUP_DIR
from mxl_containers import STASH, SHARED_BOX, PANELS, HORADRIC_CUBE, character_containers, place, placed


def check_game_closed():
    """EditError si le jeu Median XL est ouvert : il garde le coffre en mémoire et le réécrirait à sa fermeture,
    écrasant les changements de l'éditeur (mxl_game)."""
    running = mxl_game.running_game(settings.get('game_dir'))
    if running:
        raise EditError(tr('err.game_running', exe=running))


def in_project(path):
    """Vrai si path est dans le dossier du programme (majuscules ignorées, autre lecteur = non)."""
    p, root = os.path.normcase(os.path.abspath(path)), os.path.normcase(PROJECT_DIR)
    try:
        return os.path.commonpath([p, root]) == root
    except ValueError:   # lecteurs différents
        return False


def parse_stash(path, data):
    """Lit toutes les pages du coffre. Chaque page = 'STASH' + n° de page (u32) + 'JM' + nb + objets.
    Les objets sont lus à la suite (longueur = nb de bits lus, arrondi à l'octet)."""
    return stash_items(read_file(path), data)


def stash_items(buf, data):
    """Objets d'un coffre lu en mémoire (voir parse_stash)."""
    items = []
    p = 8
    while p < len(buf):
        expect(buf, p, b'STASH')
        page = struct.unpack_from('<I', buf, p + 5)[0]
        expect(buf, p + 9, b'JM')
        count = struct.unpack_from('<H', buf, p + 11)[0]
        page_items, p = read_item_list(buf, p + 13, count, data)
        for it in page_items:
            for x in [it] + it['socketed']:
                x['page'] = page
        items += page_items
    return items


def is_character(path):
    """Vrai pour un fichier de personnage (.d2s), dont l'éditeur affiche et modifie le cube."""
    return path.lower().endswith('.d2s')


def stash_box(path):
    """Forme d'un coffre : coffre partagé (.shared : le cube Horadrim n'y va pas) ou coffre d'un personnage."""
    return SHARED_BOX if path.lower().endswith('.shared') else STASH


def read_items(path, data, where=None):
    """Objets du conteneur d'un fichier : ceux du coffre (avec leur page), ou ceux du cube d'un personnage (page 0 ;
    where = 'inventory' : ceux de son sac)."""
    return ItemFile(path, data, where=where).items


def last_page(path):
    """Dernière page du coffre affichée en jeu (en-tête : u32 @0x04, à partir de 0)."""
    with open(path, 'rb') as f:
        return struct.unpack('<II', f.read(8))[1]


class EditError(Exception):
    """Modification refusée (valeur hors plage, emplacement occupé, fichier changé…) : le fichier n'est pas modifié."""


def read_file(path):
    with open(path, 'rb') as f:
        return f.read()


def commit_file(path, content, verify, backup=True):
    """Écriture sûre : content est écrit dans <path>.tmp, relu et contrôlé par verify(chemin temporaire) (qui lève
    EditError si le résultat n'est pas celui attendu), puis sauvegarde make_backup si backup, et remplacement
    atomique du fichier (os.replace). En cas d'erreur ou de coupure, le fichier d'origine reste intact.
    Renvoie la sauvegarde ou None.
    Garde-fous (EditError) : aucune écriture dans un coffre situé dans le dossier du programme (copies de test), ni
    pendant que le jeu est ouvert (check_game_closed)."""
    if in_project(path):
        raise EditError(tr('err.protected', file=path))
    check_game_closed()
    tmp = path + '.tmp'
    try:
        with open(tmp, 'wb') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        verify(tmp)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    bak = make_backup(path) if backup else None
    os.replace(tmp, path)
    return bak


def make_backup(path):
    """Copie horodatée <nom du fichier>.bak-AAAAMMJJ-HHMMSS dans le dossier des sauvegardes de l'utilisateur
    (paths.BACKUP_DIR, dossier unique : décision du 08/10 ; avant : à côté du fichier), puis suppression des
    sauvegardes horodatées plus anciennes du même fichier : seule la dernière est conservée. Les sauvegardes nommées
    autrement (ex. « .bak-avant-shark ») ne sont jamais supprimées. Renvoie le chemin de la sauvegarde."""
    import shutil, time, re, glob
    os.makedirs(BACKUP_DIR, exist_ok=True)
    base = os.path.join(BACKUP_DIR, os.path.basename(path))
    bak = base + time.strftime('.bak-%Y%m%d-%H%M%S')
    n = 1
    while os.path.exists(bak):
        n += 1; bak = base + time.strftime('.bak-%Y%m%d-%H%M%S') + f'-{n}'
    shutil.copy2(path, bak)
    pat = re.compile(re.escape(os.path.basename(path)) + r'\.bak-\d{8}-\d{6}(-\d+)?$')
    for old in glob.glob(glob.escape(base) + '.bak-*'):
        if old != bak and pat.fullmatch(os.path.basename(old)):
            os.remove(old)
    return bak


STASH_COLS, STASH_ROWS, STASH_PAGES = STASH.cols, STASH.rows, STASH.pages   # grille et pages du coffre


def build_stash(header, pages):
    """Fichier .stash : en-tête (8 octets) puis une section par page NON VIDE, dans l'ordre des pages :
    'STASH' + n° de page (u32) + 'JM' + nombre d'objets (u16) + objets (sertis à la suite de leur porteur)."""
    out = bytearray(header)
    for p in sorted(pages):
        if pages[p]:
            out += b'STASH' + struct.pack('<I', p) + b'JM' + struct.pack('<H', len(pages[p])) + b''.join(pages[p])
    return bytes(out)


def placement_error(items, item, page, x, y, data, box=STASH):
    """Règle de placement d'un objet dans un conteneur (box, le coffre par défaut) : None s'il peut être posé en
    (x, y) de la page page (entièrement dans la grille, sans chevaucher un autre objet de cette page), sinon le
    message d'erreur. Utilisée par move_item (écriture) et par l'interface (surbrillance pendant le glisser-déposer)."""
    if box is None:   # objets portés : pas de grille (équiper un objet n'est pas encore possible)
        return tr('err.no_grid')
    if not box.holds_cube and item['code'] == HORADRIC_CUBE:   # ni dans lui-même, ni dans le coffre partagé
        return tr('err.cube_in_cube' if box.key == 'cube' else 'err.cube_shared')
    w, h = data.base(item['code']).size
    if not (0 <= page < box.pages and 0 <= x and 0 <= y and x + w <= box.cols and y + h <= box.rows):
        return tr('err.outside', x=x, y=y, w=w, h=h, cols=box.cols, rows=box.rows)
    for o in items:
        if o is not item and o['page'] == page:
            ow, oh = data.base(o['code']).size
            if x < o['x'] + ow and o['x'] < x + w and y < o['y'] + oh and o['y'] < y + h:
                return (tr('err.overlap', x=x, y=y, item=o['name'], ox=o['x'], oy=o['y']) if page == item.get('page') else
                        tr('err.overlap_page', x=x, y=y, page=page + 1, item=o['name'], ox=o['x'], oy=o['y']))
    return None


D2S_SIGNATURE = b'\x55\xAA\x55\xAA'   # signature des personnages D2
PANEL_OF = {where: n for n, where in PANELS.items()}   # conteneur -> champ « panneau » d'un objet rangé


WEAPON_SWITCH = 0x10   # en-tête du .d2s : jeu d'armes actif (u32, 0 = I, 1 = II ; ✅ Nekratall, 30/09)


def class_skills(cls, data):
    """Compétences de la classe cls dans l'ordre de skills.bin (95 par classe en Median XL)."""
    return sorted(sid for sid, c in data.skill_class.items() if c == cls)


def character_skills(b, items_at, cls, data):
    """Points investis dans chaque compétence de la classe : section 'if' du .d2s, un octet par compétence de la classe
    dans l'ordre de skills.bin, jusqu'à la liste d'objets (items_at). ✅ Nekratall, capture de l'arbre en jeu (30/09) :
    Blood Skeleton 12, Abyss Knight 6, Night Hawks 1, Embalming 1 (plus une compétence interne sans nom à 1, comme
    chez tous les personnages). Renvoie {n° de compétence: points} (compétences à 0 absentes)."""
    p = b.find(b'if', b.find(b'gf'))
    expect(b, p, b'if')
    ids = class_skills(cls, data)
    raw = b[p + 2:items_at]
    if len(raw) != len(ids):
        raise FormatError(tr('err.format', expected=f'{len(ids)} skills', pos=p))
    return {sid: n for sid, n in zip(ids, raw) if n}


def character_item_list(b, data):
    """Liste des objets du personnage dans un .d2s lu en mémoire : (octet de son 'JM', octet suivant la liste,
    objets). Elle suit la section 'if' : 'JM' + nombre (u16) + objets, objets sertis à la suite de leur porteur."""
    p = b.find(b'JM', b.find(b'if'))
    expect(b, p, b'JM')
    items, end = read_item_list(b, p + 4, struct.unpack_from('<H', b, p + 2)[0], data)
    return p, end, items


def character_checksum(b):
    """Somme de contrôle d'un .d2s (u32 @0x0C, comptée comme nulle) : pour chaque octet, somme = rotation à gauche
    d'un bit de la somme + octet (✅ 3 personnages, 30/09)."""
    total = 0
    for i, x in enumerate(b):
        total = (((total << 1) | (total >> 31)) + (0 if 12 <= i < 16 else x)) & 0xFFFFFFFF
    return total


def seal_character(content):
    """Contenu d'un .d2s avec sa taille (u32 @0x08) et sa somme de contrôle (u32 @0x0C) à jour."""
    b = bytearray(content)
    struct.pack_into('<I', b, 8, len(b))
    struct.pack_into('<I', b, 12, character_checksum(b))
    return bytes(b)


class ItemFile:
    """Fichier d'objets lu pour être modifié : coffre (.stash, coffre partagé) ou personnage (.d2s : son cube, son
    sac avec where = 'inventory', ses objets portés avec where = 'equipped', ceux de son mercenaire avec where =
    'mercenary' — ces deux derniers : édition sur place seulement).
    where : conteneur modifié ('stash', 'cube', 'inventory' ou 'equipped' ; par défaut le coffre,
    ou le cube d'un personnage) ; buf : octets lus ; items : objets du conteneur (page 0 pour le cube et le sac) ;
    box : sa forme ; entries : [(page, octets, objet)] de tous les objets de premier niveau du fichier, dans l'ordre
    (personnage : tous ceux de sa liste — ceux des autres rangements sont réécrits tels quels, à leur place)."""

    def __init__(self, path, data, character=None, where=None):
        self.data = data
        self.character = is_character(path) if character is None else character
        self.where = where or ('cube' if self.character else 'stash')
        self.buf = read_file(path)
        if self.character:
            expect(self.buf, 0, D2S_SIGNATURE)
            self.start, self.end, top = character_item_list(self.buf, data)
            if self.where == 'mercenary':   # objets du mercenaire : liste après celle du personnage (section 'jf')
                merc = character_extras(self.buf, self.end, data)['mercenary']
                self.items = merc['items'] if merc else []
            else:
                self.items = placed(top, self.where)
            for it in self.items:
                for x in [it] + it['socketed']:
                    x['page'] = 0
            self.box = character_containers(data).get(self.where)   # None : objets portés (pas de grille)
        else:
            top = self.items = stash_items(self.buf, data)
            self.box = stash_box(path)
        self.entries = [(it.get('page') or 0, item_blob(self.buf, it), it) for it in top]

    def build(self, entries):
        """Contenu du fichier avec ces objets de premier niveau [(page, octets, objet)] : coffre = une section par
        page non vide (build_stash, objets dans l'ordre donné) ; personnage = sa liste d'objets dans l'ordre donné,
        le reste du fichier inchangé, taille et somme de contrôle recalculées."""
        if self.character:
            return seal_character(self.buf[:self.start] + b'JM' + struct.pack('<H', len(entries)) +
                                  b''.join(e[1] for e in entries) + self.buf[self.end:])
        pages = {}
        for page, blob, _ in entries:
            pages.setdefault(page, []).append(blob)
        return build_stash(self.buf[:8], pages)

    def seal(self, content):
        """Contenu modifié sur place (tailles inchangées), prêt à écrire : somme de contrôle d'un personnage à jour."""
        return seal_character(content) if self.character else bytes(content)

    def check(self):
        """Garde-fou avant une reconstruction : le fichier reconstruit sans modification doit être identique à
        l'octet près (structure comprise, taille et somme de contrôle d'un personnage justes), sinon EditError."""
        if self.build(self.entries) != self.buf:
            raise EditError(tr('err.structure'))

    def reread(self, tmp, wheres=None):
        """Objets du conteneur dans le fichier écrit tmp (contrôle avant de remplacer l'original). Personnage : ses
        objets rangés ailleurs que dans les conteneurs wheres (par défaut : celui-ci) doivent être inchangés et ses
        sections suivantes (cadavre, mercenaire, golem) lisibles, sinon EditError."""
        after = ItemFile(tmp, self.data, self.character, self.where)
        if self.character:
            wheres = wheres or (self.where,)
            others = lambda f: [blob for _, blob, it in f.entries if place(it) not in wheres]
            try:
                character_extras(after.buf, after.end, self.data)
            except (FormatError, struct.error, IndexError):
                raise EditError(tr('err.verify'))
            if others(after) != others(self):
                raise EditError(tr('err.verify'))
            if self.where == 'mercenary':   # après la liste du personnage : seuls les octets de ses objets ont changé
                spans = [(i['_offset'], i['_offset'] + i['_size']) for m in self.items for i in [m] + m['socketed']]
                if len(after.buf) != len(self.buf) or any(
                        a != b and not 12 <= k < 16 and not any(s <= k < e for s, e in spans)
                        for k, (a, b) in enumerate(zip(after.buf, self.buf))):
                    raise EditError(tr('err.verify'))
            elif after.buf[after.end:] != self.buf[self.end:]:
                raise EditError(tr('err.verify'))
        return after.items


def move_item(path, item, x, y, data, page=None, backup=True, where=None):
    """Déplace un objet du coffre, du cube ou du sac (where : voir ItemFile) (et ses objets sertis) en (x, y) de la page page (par défaut sa page
    actuelle). Contrôles : position dans la grille, objet inchangé depuis la lecture, pas de chevauchement dans la
    page cible.
    - même page : x et y (4 bits chacun) réécrits sur place ;
    - autre page : octets de l'objet retirés de la section de sa page et ajoutés à la fin de celle de la page cible
      (créée si vide, supprimée si la page source devient vide) ; garde-fou : le fichier reconstruit sans
      modification doit être identique à l'octet près, sinon refus.
    Écriture sûre (commit_file : relecture de vérification avant de remplacer le fichier, sauvegarde si backup).
    Renvoie la sauvegarde ou None."""
    page = item['page'] if page is None else page
    f = ItemFile(path, data, where=where)
    items = f.items
    cur = next((i for i in items if i['_offset'] == item['_offset']), None)
    if cur is None or (cur['x'], cur['y'], cur['code'], cur['page']) != (item['x'], item['y'], item['code'], item['page']):
        raise EditError(tr('err.changed'))
    err = placement_error(items, cur, page, x, y, data, f.box)
    if err:
        raise EditError(err)
    if page == cur['page']:
        new = bytearray(f.buf)
        pos = (cur['_offset'] + 2) * 8 + cur['_pos_bit']
        write_bits(new, pos, 4, x)
        write_bits(new, pos + 4, 4, y)
        content = f.seal(new)
    else:
        f.check()
        blob = bytearray(item_blob(f.buf, cur))
        write_bits(blob, 2 * 8 + cur['_pos_bit'], 4, x)
        write_bits(blob, 2 * 8 + cur['_pos_bit'] + 4, 4, y)
        content = f.build([e for e in f.entries if e[2] is not cur] + [(page, bytes(blob), cur)])

    def verify(tmp):
        after = f.reread(tmp)
        moved = [i for i in after if i['page'] == page and (i['x'], i['y'], i['code']) == (x, y, cur['code'])]
        if not (len(after) == len(items) and moved and len(moved[0]['socketed']) == len(cur['socketed'])):
            raise EditError(tr('err.verify'))
    return commit_file(path, content, verify, backup)


def transfer_item(src, dst, item, page, x, y, data, backup_src=True, backup_dst=True, src_where=None, dst_where=None):
    """Déplace un objet (et ses objets sertis) du fichier src vers la place (page, x, y) du fichier dst (coffre d'un
    personnage, coffre partagé, cube ou sac d'un personnage : src_where, dst_where, voir ItemFile). Contrôles : jeu fermé, objet inchangé dans src depuis la
    lecture, place libre dans dst (edit_stash). Écritures : dst d'abord, puis src ; si l'écriture de src échoue, dst
    est remis tel qu'il était (une coupure entre les deux laisse au pire l'objet en double, jamais perdu). Renvoie
    (sauvegarde de src, de dst)."""
    if os.path.abspath(src) == os.path.abspath(dst):
        raise EditError(tr('err.changed'))
    check_game_closed()   # avant la première écriture (commit_file le vérifie aussi pour chacune)
    buf = read_file(src)
    cur = find_item(read_items(src, data, src_where), item['_offset'])
    if cur is None or (cur['x'], cur['y'], cur['code'], cur['page'], cur.get('id')) != \
            (item['x'], item['y'], item['code'], item['page'], item.get('id')):
        raise EditError(tr('err.changed'))
    before_dst = read_file(dst)
    bak_dst = edit_stash(dst, data, insert=[(page, x, y, item_blob(buf, cur))], backup=backup_dst, where=dst_where)
    try:
        bak_src = edit_stash(src, data, remove=[cur['_offset']], backup=backup_src, where=src_where)
    except BaseException:
        n = len(read_items(dst, data, dst_where)) - 1   # dst remis tel qu'il était : l'objet ajouté en moins

        def verify(tmp):
            if len(ItemFile(tmp, data, is_character(dst), dst_where).items) != n:
                raise EditError(tr('err.verify'))
        try:
            commit_file(dst, before_dst, verify, backup=False)
        except Exception:
            pass   # remise en état impossible (ex. jeu ouvert entre-temps) : objet en double, jamais perdu
        raise
    return bak_src, bak_dst


def move_between(path, item, src_where, dst_where, x, y, data, backup=True):
    """Déplace un objet (et ses objets sertis) d'un conteneur d'un personnage à un autre du même fichier (sac <-> cube),
    en une seule écriture : objet retiré de sa place dans la liste et ajouté à la fin, case et panneau réécrits.
    Contrôles : objet inchangé depuis la lecture, place libre (placement_error), fichier reconstruit à l'identique
    avant modification ; relecture : un objet de moins d'un côté, l'objet à sa place de l'autre, rien d'autre changé.
    Renvoie la sauvegarde ou None."""
    src, dst = ItemFile(path, data, where=src_where), ItemFile(path, data, where=dst_where)
    cur = next((i for i in src.items if i['_offset'] == item['_offset']), None)
    if cur is None or (cur['x'], cur['y'], cur['code']) != (item['x'], item['y'], item['code']):
        raise EditError(tr('err.changed'))
    err = placement_error(dst.items, cur, 0, x, y, data, dst.box)
    if err:
        raise EditError(err)
    src.check()
    blob = bytearray(item_blob(src.buf, cur))
    place_blob(blob, cur, x, y, dst_where)
    content = src.build([e for e in src.entries if e[2] is not cur] + [(0, bytes(blob), cur)])

    def verify(tmp):
        before = src.reread(tmp, (src_where, dst_where))
        after = ItemFile(tmp, data, True, dst_where).items
        moved = [i for i in after if (i['x'], i['y'], i['code']) == (x, y, cur['code'])]
        if not (len(before) == len(src.items) - 1 and len(after) == len(dst.items) + 1 and moved
                and len(moved[0]['socketed']) == len(cur['socketed'])):
            raise EditError(tr('err.verify'))
    return commit_file(path, content, verify, backup)


def place_blob(blob, it, x, y, where):
    """Réécrit dans les octets d'un objet (blob, bytearray) sa case (x, y) et son rangement : emplacement « rangé » et
    panneau du conteneur where. En-tête : emplacement 3 bits, équipé 4, x 4, y 4, panneau 3."""
    pos = 2 * 8 + it['_pos_bit']
    write_bits(blob, pos, 4, x)
    write_bits(blob, pos + 4, 4, y)
    write_bits(blob, pos - 7, 3, 0)
    write_bits(blob, pos + 8, 3, PANEL_OF[where])


def item_blob(buf, it):
    """Octets d'un objet de premier niveau du fichier et de ses objets sertis (enregistrés juste après lui)."""
    end = it['_offset'] + it['_size']
    for sub in it.get('socketed', []):
        end = sub['_offset'] + sub['_size']
    return bytes(buf[it['_offset']:end])


def blob_item(blob, data):
    """Objet (avec ses objets sertis) lu depuis ses octets (item_blob)."""
    items, _ = read_item_list(blob, 0, 1, data)
    return items[0]


def edit_stash(path, data, remove=(), insert=(), backup=True, where=None):
    """Retire des objets du coffre (ou du cube, du sac d'un personnage : where, voir ItemFile) et en ajoute, en une
    seule écriture :
    remove = offsets d'objets de premier niveau (leurs objets sertis partent avec eux) ;
    insert = [(page, x, y, octets d'un objet et de ses objets sertis)] : position réécrite dans l'objet (case,
    emplacement « rangé », panneau du conteneur : coffre ou cube), placement contrôlé (placement_error : grille,
    chevauchement avec les objets restants et ceux déjà insérés).
    Garde-fou : le fichier reconstruit sans modification doit être identique à l'octet près. Écriture sûre
    (commit_file) : relecture vérifiée (nombre d'objets, objets insérés à leur place). Renvoie la sauvegarde ou None."""
    return edit_containers(path, data, {where: (remove, insert)}, backup)


def edit_containers(path, data, changes, backup=True):
    """edit_stash sur plusieurs conteneurs d'un même fichier (sac et cube d'un personnage), en une seule écriture :
    changes = {where: (remove, insert)}. Relecture : objets des autres conteneurs inchangés, nombre d'objets et objets
    insérés vérifiés dans chacun. Renvoie la sauvegarde ou None."""
    files = {w: ItemFile(path, data, where=w) for w in changes}
    f = next(iter(files.values()))
    f.check()
    removed, added, expected = set(), [], {}
    for w, (remove, insert) in changes.items():
        items = files[w].items
        gone = set()
        for off in remove:
            if not any(i['_offset'] == off for i in items):
                raise EditError(tr('err.changed'))
            gone.add(off)
        removed |= gone
        kept = [i for i in items if i['_offset'] not in gone]
        for page, x, y, blob in insert:
            new = blob_item(blob, data)
            new['page'] = page
            err = placement_error(kept, new, page, x, y, data, files[w].box)
            if err:
                raise EditError(err)
            b = bytearray(blob)
            place_blob(b, new, x, y, files[w].where)
            added.append((page, bytes(b), new))
            new['x'], new['y'] = x, y
            kept.append(new)
        expected[w] = len(items) - len(gone) + len(insert)
    content = f.build([e for e in f.entries if e[2]['_offset'] not in removed] + added)

    def verify(tmp):
        f.reread(tmp, tuple(g.where for g in files.values()))
        for w, (_, insert) in changes.items():
            after = ItemFile(tmp, data, f.character, files[w].where).items
            if len(after) != expected[w] or not all(
                    any((i['page'], i['x'], i['y']) == (page, x, y) and i['code'] == blob_item(blob, data)['code']
                        for i in after) for page, x, y, blob in insert):
                raise EditError(tr('err.verify'))
    return commit_file(path, content, verify, backup)


def free_spot(items, it, data, pages=None, box=STASH):
    """Première place (page, x, y) où l'objet it peut être posé dans le conteneur box (placement_error), ou None ;
    pages : pages essayées, dans l'ordre (toutes par défaut)."""
    w, h = data.base(it['code']).size
    for page in range(box.pages) if pages is None else pages:
        for y in range(box.rows - h + 1):
            for x in range(box.cols - w + 1):
                if placement_error(items, it, page, x, y, data, box) is None:
                    return page, x, y
    return None


def find_item(items, offset):
    """Objet (ou objet serti) situé à cet offset du fichier."""
    for it in items:
        if it['_offset'] == offset:
            return it
        for sub in it.get('socketed', []):
            if sub['_offset'] == offset:
                return sub
    return None


def load_character(path, data):
    """Classe, niveau, Force / Dextérité (base + objets équipés) d'un personnage .d2s (format 1.13c).
    En-tête : classe u8 @0x28, niveau u8 @0x2B ; stats après 'gf' (id 9 bits + valeur, largeur
    = u8 @0x0A de itemstatcost) ; objets après 'JM' + nombre (u16), objets sertis à la suite."""
    b = read_file(path)
    expect(b, 0, D2S_SIGNATURE)
    ch = Character(name=b[0x14:0x24].split(b'\0')[0].decode('latin1'), cls=b[0x28], level=b[0x2B], path=path,
                   weapon_switch=struct.unpack_from('<I', b, WEAPON_SWITCH)[0] & 1)
    gf = b.find(b'gf')
    expect(b, gf, b'gf')
    br, base = BitReader(b[gf + 2:gf + 2 + 200]), {}
    for _ in range(16):   # les stats utiles (0 à GOLD = 14) sont en tête ; on s'arrête après l'or
        sid = br.read(9)
        if sid == 0x1FF or sid not in data.isc:
            break
        base[sid] = br.read(data.csv_bits.get(sid, 0))
        if sid == S.GOLD:
            break
    start, end, items = character_item_list(b, data)
    skills = character_skills(b, start, ch['cls'], data)
    for it in items:   # grilles d'un personnage (sac, cube) : une seule page, comme pour ItemFile
        if it['location'] == 0:
            for x in [it] + it['socketed']:
                x['page'] = 0
    worn = [i for i in items if i['location'] == 1]
    bonus = lambda sid: sum(s['value'] for i in worn for x in [i] + i['socketed']
                            for s in x.get('stats', []) + x.get('stats_runeword', []) if s['id'] == sid)
    attr = lambda sid: base.get(sid, 0) + bonus(sid)
    ch.update(strength=attr(S.STRENGTH), energy=attr(S.ENERGY), dexterity=attr(S.DEXTERITY), vitality=attr(S.VITALITY),
              base_stats=base, skills=skills, items=items, corpse=[], mercenary=None, golem=None, extra_error=None)
    try:   # sections suivantes : une erreur ici ne rend pas le personnage illisible (elle est gardée)
        ch.update(character_extras(b, end, data))
    except (FormatError, struct.error, IndexError) as e:
        ch['extra_error'] = str(e) or type(e).__name__
    return ch


MERC_HEADER = 0xB1   # mercenaire dans l'en-tête du .d2s : mort u16, identifiant u32 (0 = pas de mercenaire),
                     # n° de nom u16, type u16 (ligne de hireling.bin), expérience u32


def character_extras(b, p, data):
    """Sections du .d2s après les objets du personnage (octet p), format D2 1.13c : cadavre ('JM' + nombre u16 ; par
    cadavre 12 octets puis 'JM' + nombre + objets), mercenaire ('jf', puis 'JM' + nombre + objets s'il y a un
    mercenaire ; ✅ Nekratall, 6 objets portés), golem de fer ('kf' + u8 ; 1 = un objet suit). Cadavre non vide et
    golem : format standard, pas encore rencontrés."""
    def item_list(p):
        expect(b, p, b'JM')
        return read_item_list(b, p + 4, struct.unpack_from('<H', b, p + 2)[0], data)

    expect(b, p, b'JM')
    corpses, p, corpse = struct.unpack_from('<H', b, p + 2)[0], p + 4, []
    for _ in range(corpses):
        items, p = item_list(p + 12)
        corpse += items
    expect(b, p, b'jf')
    p += 2
    dead, ident, name_id, kind, experience = struct.unpack_from('<HIHHI', b, MERC_HEADER)
    merc = None
    if ident:
        items, p = item_list(p)
        merc = dict(type=kind, name_id=name_id, experience=experience, dead=bool(dead), items=items)
    expect(b, p, b'kf')
    golem = read_item_list(b, p + 3, 1, data)[0][0] if b[p + 2] else None
    return dict(corpse=corpse, mercenary=merc, golem=golem)


def character_for(stash_path, data):
    """Personnage associé à un coffre (même nom, extension .d2s), ou None s'il n'existe pas.
    Un fichier présent mais illisible lève l'erreur de lecture (à signaler à l'utilisateur)."""
    p = os.path.splitext(stash_path)[0] + '.d2s'
    return load_character(p, data) if os.path.exists(p) else None
