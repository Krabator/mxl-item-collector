"""Tests : affichage (instantanés des deux coffres de référence, dans chaque langue livrée), scénario de déplacements,
écriture sûre et erreurs de format."""
import io, json, os, hashlib, contextlib
from common import case, STASH, STASH2, FIXTURES, LANGUAGES
import i18n
from mxl_save import parse_stash, character_for, move_item, commit_file, EditError
from mxl_format import FormatError
from mxl_items import show
from mxl_tooltip import item_tooltip, requirements_unmet
from mxl_edit import edit_groups, item_quality, priority_profile
from mxl_gfx import icon_name


def snapshot(data, lang, stash=STASH):
    """Texte décrivant tout ce que l'éditeur affiche pour chaque objet d'un coffre de référence, dans cette langue :
    ligne de commande, infobulle, section Édition, icône et fond rouge, qualité et profil de priorités."""
    i18n.set_language(lang, save=False)
    try:
        items, ch = parse_stash(stash, data), character_for(stash, data)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            for it in items:
                show(it, data)
        out = [buf.getvalue()]
        for it in items:
            out.append(json.dumps(item_tooltip(it, data, ch), ensure_ascii=False))
            out.append(json.dumps([(g['heading'], [(f['label'], f['lo'], f['hi'], f['value'], f['fmt'](f['value']))
                                                   for f in g['fields']]) for g in edit_groups(it, data, ch)],
                                  ensure_ascii=False))
            q = item_quality(edit_groups(it, data, ch))
            profile, kept = priority_profile(it, data)
            out.append(f"{icon_name(it, data)} {requirements_unmet(it, data, ch)}" + (f' qualité {q:.2f}' if q is not None else '')
                       + (f' profil {profile}' if kept else ''))
        return '\n'.join(out)
    finally:
        i18n.set_language('en', save=False)


for _lang in LANGUAGES:
    for _label, _stash, _ref in (('coffre 1', STASH, f'snapshot_{_lang}.txt'), ('coffre 2', STASH2, f'snapshot2_{_lang}.txt')):
        case('Affichage', f'affichage {_label} {_lang}')(
            lambda ctx, lang=_lang, stash=_stash, ref=_ref: ctx.compare(ref, snapshot(ctx.data, lang, stash)))


@case('Écriture', 'scénario de déplacements (acceptés / refusés)')
def move_scenario(ctx):
    """Une ligne par déplacement sur une copie du coffre : empreinte du fichier ou refus, comparées à moves.txt (début
    du scénario d'écriture du module mxl_editor : writes.txt)."""
    data = ctx.data
    i18n.set_language('en', save=False)
    p = ctx.copy(STASH, 'ops_test.stash')
    find = lambda code: next(i for i in parse_stash(p, data) if i['code'] == code)
    move = lambda it, page, x, y: move_item(p, it, x, y, data, page=page, backup=False)
    res = []

    def step(name, f):
        try:
            f()
            res.append(f'{name}: {hashlib.md5(open(p, "rb").read()).hexdigest()[:10]}')
        except Exception as e:
            res.append(f'{name}: REFUS {type(e).__name__} {e}')
    step('déplacement même page', lambda: move(find('160 '), find('160 ')['page'], 9, 9))
    step('déplacement page vide', lambda: move(find('160 '), 7, 2, 3))
    step('retour page 1', lambda: move(find('160 '), 0, 9, 4))
    step('chevauchement', lambda: move(find('160 '), 0, 0, 0))
    step('hors grille', lambda: move(find('160 '), 0, 13, 13))
    ctx.compare('moves.txt', '\n'.join(res) + '\n')


@case('Écriture', 'écriture sûre : vérification échouée = fichier intact, ni .tmp ni .bak')
def safe_commit(ctx):
    p = ctx.copy(STASH, 'safety.stash')
    before = open(p, 'rb').read()

    def refuse(_):
        raise EditError('test')
    ctx.raises(EditError, 'vérification échouée', lambda: commit_file(p, b'garbage', refuse, backup=True))
    ctx.expect('fichier et dossier', (open(p, 'rb').read() == before, sorted(os.listdir(ctx.tmp))), (True, ['safety.stash']))


@case('Écriture', "transfert entre deux coffres (personnage -> partagé) : objet et sertis déplacés, échec = rien perdu")
def stash_transfer(ctx):
    """Objet à sockets remplis du coffre 1 posé dans une place libre du coffre partagé (copie du coffre 2) : octets
    identiques à l'arrivée, retiré du départ, autres objets intacts ; objet changé : refus ; échec de l'écriture du
    départ : arrivée remise telle qu'elle était, départ intact."""
    import mxl_save
    from mxl_save import transfer_item, free_spot, read_file, item_blob
    data = ctx.data
    src, dst = ctx.copy(STASH, 'Nekratall.stash'), ctx.copy(STASH2, '_sharedstash.shared')
    blobs = lambda p: sorted(item_blob(read_file(p), i) for i in parse_stash(p, data))
    it = next(i for i in parse_stash(src, data) if i['socketed'])
    page, x, y = free_spot(parse_stash(dst, data), it, data)
    blob, src_before, dst_before = item_blob(read_file(src), it), blobs(src), blobs(dst)
    raw_src, raw_dst = read_file(src), read_file(dst)
    # échec de l'écriture du départ : arrivée remise en état, rien perdu ni en double
    edit_stash = mxl_save.edit_stash

    def fail_on_src(path, *a, **k):
        if path == src:
            raise EditError('test')
        return edit_stash(path, *a, **k)
    mxl_save.edit_stash = fail_on_src
    try:
        ctx.raises(EditError, 'échec au départ', lambda: transfer_item(src, dst, it, page, x, y, data, False, False))
    finally:
        mxl_save.edit_stash = edit_stash
    ctx.expect('fichiers après échec', (read_file(src) == raw_src, read_file(dst) == raw_dst), (True, True))
    # transfert
    transfer_item(src, dst, it, page, x, y, data, backup_src=False, backup_dst=False)
    moved = next((i for i in parse_stash(dst, data) if (i['page'], i['x'], i['y']) == (page, x, y)), None)
    ctx.check(moved and len(moved['socketed']) == len(it['socketed']), "objet et sertis absents de l'arrivée")
    ctx.expect('arrivée', blobs(dst), sorted(dst_before + [item_blob(read_file(dst), moved)]))
    ctx.expect('départ', blobs(src), sorted(b for b in src_before if b != blob))
    ctx.check(item_blob(read_file(dst), moved)[:4] == blob[:4], "octets de l'objet changés (hors position)")
    # objet déjà parti (lecture périmée) : refus, fichiers inchangés
    raw_src, raw_dst = read_file(src), read_file(dst)
    ctx.raises(EditError, 'objet changé', lambda: transfer_item(src, dst, it, page, x, y, data, False, False))
    ctx.expect('fichiers après refus', (read_file(src) == raw_src, read_file(dst) == raw_dst), (True, True))


@case('Affichage', "objet éthéré : « Ethereal » en gris après les exigences, avant les stats (capture Glyph Basher)")
def ethereal_line_position(ctx):
    """Capture en jeu de Glyph Basher (Totem Shield éthéré, coffre partagé) : ... Required Dexterity: 34 / Ethereal /
    Prefixes: 3 / ... ; objet d'un coffre de test rendu éthéré : même place, en gris, jamais en fin d'infobulle."""
    data = ctx.data
    it = next(i for i in parse_stash(STASH, data) if 'defense' in i and i.get('quality') == 'rare')
    it = dict(it, ethereal=True)
    lines = [(line[0][0], ''.join(t for _, t in line)) for line in item_tooltip(it, data)]
    texts = [t for _, t in lines]
    k = texts.index('Ethereal')
    last_req = max(i for i, t in enumerate(texts) if t.startswith('Required '))
    ctx.expect('place et couleur', (k == last_req + 1, lines[k][0], texts[k + 1].startswith('Prefixes')), (True, '5', True))


@case('Affichage', "objet éthéré : défense et dégâts de base × 1,25 arrondis vers le bas (plage, limites d'édition)")
def ethereal_base_values(ctx):
    """Règle retenue : Totem Shield [42-82] -> [52-102] éthéré (plage grise de la défense de base, curseur d'édition) ;
    arme éthérée : dégâts de base × 1,25 comme la collection (documentation : Iron Shard)."""
    from mxl_rules import ethereal_base, defense_range
    data = ctx.data
    ctx.expect('règle', [ethereal_base(v, True) for v in (42, 82)] + [ethereal_base(82, False)], [52, 102, 82])
    items = parse_stash(STASH, data)
    armor = next(i for i in items if 'defense' in i and data.base(i['code']).def_range[0] != data.base(i['code']).def_range[1]
                 and defense_range(i, data))
    lo, hi = data.base(armor['code']).def_range
    eth = dict(armor, ethereal=True)
    base_line = next(''.join(t for _, t in l) for l in item_tooltip(eth, data) if l[0][1].startswith('Base Defense'))
    ctx.expect('plage éthérée', (base_line.endswith(f'[{lo * 5 // 4}-{hi * 5 // 4}]'), defense_range(eth, data)),
               (True, (lo * 5 // 4, hi * 5 // 4)))
    weapon = next(i for i in items if data.base(i['code']).damage and data.base(i['code']).damage['one_hand'][1]
                  and not data.base(i['code']).two_handed)
    a, b = data.base(weapon['code']).damage['one_hand']
    base = [''.join(t for _, t in l) for l in item_tooltip(dict(weapon, ethereal=True), data)
            if ''.join(t for _, t in l).startswith('One-Hand Base Damage')]
    ctx.expect('dégâts de base éthérés', base, [f'One-Hand Base Damage: {a * 5 // 4} to {b * 5 // 4}'])


@case('Écriture', 'stat absente des tables : erreur explicite (stat et objet)')
def unknown_stat(ctx):
    removed = ctx.data.isc.pop(49)   # data/ plus ancien que le jeu
    try:
        e = ctx.raises(FormatError, 'lecture', lambda: parse_stash(STASH, ctx.data))
        ctx.check(e is None or ('49' in str(e) and '7@5' in str(e)), f'message sans la stat ou l\'objet : {e}')
    finally:
        ctx.data.isc[49] = removed


@case('Écriture', 'lecture décalée (ancienne largeur du n° d\'unique) : erreur, pas de boucle sans fin')
def shifted_read(ctx):
    import mxl_format
    mxl_format.SET_UNIQUE_ID_BITS = 12
    try:
        ctx.raises(FormatError, 'lecture décalée', lambda: parse_stash(STASH2, ctx.data))
    finally:
        mxl_format.SET_UNIQUE_ID_BITS = 15


@case('Écriture', 'garde-fou : coffre du dossier du programme jamais modifié')
def program_folder_guard(ctx):
    data = ctx.data
    before = open(STASH, 'rb').read()
    it = next(i for i in parse_stash(STASH, data) if i['code'] == '7@5 ')
    ctx.raises(EditError, 'déplacement', lambda: move_item(STASH, it, 0, 12, data))
    ctx.check(open(STASH, 'rb').read() == before and not any('.bak' in f or f.endswith('.tmp') for f in os.listdir(FIXTURES)),
              'coffre de test modifié ou fichier laissé')


@case('Écriture', 'fichier abîmé (en-tête de page) refusé')
def damaged_file(ctx):
    p = ctx.copy(STASH, 'damaged.stash')
    with open(p, 'r+b') as f:
        f.seek(8)
        f.write(b'X')
    ctx.raises(FormatError, 'fichier abîmé', lambda: parse_stash(p, ctx.data))


# ---------------------------------------------------------------- jeu ouvert : écriture refusée

class GameOpen:
    """Jeu simulé : processus [(nom, n°)] et chemins {n°: chemin}, réglage game_dir dans un fichier du cas."""

    def __init__(self, ctx, procs, paths, game_dir=r'D:\Games\median-xl'):
        import settings
        self.ctx, self.procs, self.paths, self.settings = ctx, procs, paths, settings
        self.settings_file = os.path.join(ctx.tmp, 'settings.json')
        with open(self.settings_file, 'w', encoding='utf-8') as f:
            json.dump({'game_dir': game_dir}, f)

    def __enter__(self):
        import mxl_game
        self.saved = mxl_game.running_processes, mxl_game.process_path, self.settings.PATH
        mxl_game.running_processes = lambda: self.procs
        mxl_game.process_path = lambda pid: self.paths.get(pid)
        self.settings.PATH = self.settings_file

    def __exit__(self, *exc):
        import mxl_game
        mxl_game.running_processes, mxl_game.process_path, self.settings.PATH = self.saved


def write_copy(ctx):
    """Copie du coffre et déplacement d'un objet (Body Armor 7@5 vers une page vide) : (chemin, fonction d'écriture)."""
    p = ctx.copy(STASH, 'game.stash')
    it = next(i for i in parse_stash(p, ctx.data) if i['code'] == '7@5 ')
    return p, lambda: move_item(p, it, 2, 3, ctx.data, page=7, backup=False)


@case('Écriture', 'jeu ouvert (Game.exe du dossier de Median XL) : écriture refusée, coffre intact')
def game_open_refused(ctx):
    p, write = write_copy(ctx)
    before = open(p, 'rb').read()
    with GameOpen(ctx, [('explorer.exe', 1), ('Game.exe', 2)], {2: r'D:\Games\median-xl\Game.exe'}):
        e = ctx.raises(EditError, 'écriture', write)
    ctx.check(e is not None and 'Game.exe' in str(e), f'message sans le jeu : {e}')
    ctx.check(open(p, 'rb').read() == before and sorted(os.listdir(ctx.tmp)) == ['game.stash', 'settings.json'],
              'coffre modifié ou fichier laissé')


@case('Écriture', "Game.exe d'un autre jeu : écriture permise ; chemin illisible : refusée (prudence)")
def game_other_or_unknown(ctx):
    p, write = write_copy(ctx)
    with GameOpen(ctx, [('Game.exe', 2)], {2: r'C:\Other Game\Game.exe'}):
        write()   # autre dossier : pas de blocage
    ctx.check(open(p, 'rb').read() != open(STASH, 'rb').read(), 'écriture non faite avec le Game.exe d\'un autre jeu')
    with GameOpen(ctx, [('GAME.EXE', 3)], {}):
        ctx.raises(EditError, 'chemin illisible', write)


@case('Écriture', 'jeu ouvert : transfert refusé avant toute écriture (bibliothèque et coffre intacts)')
def game_open_transfer(ctx):
    from mxl_library import Library, plan_transfer, apply_transfer
    data = ctx.data
    p = ctx.copy(STASH2, 't.stash')
    lib = Library(os.path.join(ctx.tmp, 'library.json'))
    plan = plan_transfer(parse_stash(p, data), lib, data, {})
    before = open(p, 'rb').read()
    with GameOpen(ctx, [('Game.exe', 2)], {2: r'D:\Games\median-xl\Game.exe'}):
        ctx.raises(EditError, 'transfert', lambda: apply_transfer(p, data, lib, plan, backup=False))
    ctx.check(open(p, 'rb').read() == before and not os.path.exists(lib.path), 'coffre ou bibliothèque écrits')


@case('Écriture', 'liste réelle des processus lue (API Windows), éditeur compris')
def real_processes(ctx):
    import importlib
    import mxl_game
    real = importlib.reload(mxl_game)   # vraie fonction (celle des tests simule « jeu fermé »)
    try:
        procs = real.running_processes()
        ctx.check(procs and any(pid == os.getpid() for _, pid in procs), f'processus : {procs and len(procs)}')
        ctx.check((real.process_path(os.getpid()) or '').lower().endswith('.exe'), 'chemin de l\'éditeur illisible')
    finally:
        mxl_game.running_processes = lambda: []
