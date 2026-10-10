"""Tests : collection — panneau de l'écran Library sans interface (mxl_library_view), transfert (rangement, échange,
destruction, restauration, sortie), exemplaire éthéré, départage, panne pendant l'écriture."""
import os
from PIL import Image
from common import case, set_raw_stat, ROOT, STASH2, FIXTURES, CONTAINERS
import mxl_library
from mxl_library import (Library, plan_transfer, apply_transfer, restore_destroyed, take_out, slot_key, always_ethereal,
                         transfer_items, item_ref, is_storage, storage_key, rank,
                         entry_key, two_variants, catalog)
from mxl_rules import item_type_codes
from mxl_library_view import DetailSelection
from mxl_save import (parse_stash, read_file, read_items, item_blob, blob_item, edit_stash, free_spot, 
                      EditError, ItemFile)
from mxl_edit import top_priority_sum
from mxl_gfx import icon_layers, ETHEREAL_OPACITY
from mxl_containers import SHARED_BOX as SHARED

K, E = 'unique:375', 'unique:375:eth'


# ---------------------------------------------------------------- panneau de la collection, sans interface

def expect_shown(ctx, what, shown, **want):
    ctx.expect(what, {n: getattr(shown, n) for n in want}, want)


@case('Collection', 'panneau : vue par défaut, même place, ligne sous l\'infobulle')
def view_default(ctx):
    sel = DetailSelection()
    expect_shown(ctx, 'rien de rangé', sel.update(K, {}, {}, True), view='normal', slot=K, stored=False, toggle=True,
                 same_slot=False, footer='missing')
    expect_shown(ctx, 'même place', sel.update(K, {}, {K: 1}, True), same_slot=True, footer='found')
    expect_shown(ctx, "seul l'éthéré rangé : vue Ethereal", DetailSelection().update(K, {E: 1}, {K: 1}, True),
                 view='ethereal', slot=E, stored=True, footer='stored')


@case('Collection', 'panneau : vue Ethereal choisie gardée, bascule quand les exemplaires changent')
def view_kept(ctx):
    sel = DetailSelection()
    sel.update(K, {K: 1}, {K: 1}, True)
    sel.choose_view('ethereal')   # exemplaire normal rangé, vue Ethereal choisie : catalogue éthéré
    expect_shown(ctx, 'vue Ethereal choisie', sel.update(K, {K: 1}, {K: 1}, True), view='ethereal', stored=False,
                 footer='no_ethereal')
    expect_shown(ctx, 'vue gardée après une mise à jour', sel.update(K, {K: 1}, {K: 1}, True), view='ethereal')
    expect_shown(ctx, 'éthéré rangé', sel.update(K, {K: 1, E: 1}, {K: 1}, True), view='ethereal', stored=True,
                 footer='stored')
    expect_shown(ctx, 'éthéré sorti, normal rangé : bascule', sel.update(K, {K: 1}, {K: 1}, True), view='normal',
                 stored=True)


@case('Collection', "panneau : seul l'éthéré vient d'être rangé, puis sorti")
def view_ethereal_only(ctx):
    sel = DetailSelection()
    sel.update(K, {}, {K: 1}, True)
    expect_shown(ctx, 'rangé : bascule', sel.update(K, {E: 1}, {K: 1}, True), view='ethereal', stored=True)
    expect_shown(ctx, 'sorti, rien de rangé : vue gardée', sel.update(K, {}, {K: 1}, True), view='ethereal',
                 stored=False, footer='found')


@case('Collection', 'panneau : une seule variante en jeu, aucune entrée')
def view_single(ctx):
    sel = DetailSelection()
    sel.choose_view('ethereal')
    expect_shown(ctx, 'une seule variante', sel.update('unique:153', {}, {}, False), view='normal', toggle=False)
    expect_shown(ctx, 'aucune entrée', sel.update(None, {}, {}, False), slot=None, stored=False, toggle=False, footer=None)


# ---------------------------------------------------------------- transfert

class Setup:
    """Copie du 2e coffre (Jared's Fragmentor ED 57) et bibliothèque vide dans le dossier du cas ; exemplaires
    fabriqués à partir des octets de la Jared's Fragmentor."""

    def __init__(self, ctx):
        self.ctx, self.data = ctx, ctx.data
        self.p = ctx.copy(STASH2, 'c.stash')
        self.lib = Library(os.path.join(ctx.tmp, 'library.json'))
        jared = next(i for i in parse_stash(self.p, self.data) if i['code'] == '108 ')
        self.blob = item_blob(read_file(self.p), jared)

    @staticmethod
    def ed(it):
        return next(s['value'] for s in it['stats'] if s['id'] == 17)

    def claymores(self):
        return sorted(self.ed(i) for i in parse_stash(self.p, self.data) if i['code'] == '108 ')

    def variant(self, value, ethereal=False):
        """Même objet, Enhanced Damage modifié ; éthéré : drapeau bit 22 = octet 4, bit 6."""
        b = bytearray(self.blob)
        set_raw_stat(b, blob_item(self.blob, self.data), 17, value, self.data)
        if ethereal:
            b[4] |= 0x40
        return bytes(b)

    def insert(self, *blobs):
        """Pose ces objets dans le coffre, chacun à la première place libre ; renvoie leurs places."""
        items, spots = parse_stash(self.p, self.data), []
        for b in blobs:
            spot = free_spot(items, blob_item(b, self.data), self.data)
            items.append(dict(blob_item(b, self.data), page=spot[0], x=spot[1], y=spot[2]))
            spots.append(spot)
        edit_stash(self.p, self.data, insert=[(*s, b) for s, b in zip(spots, blobs)], backup=False)
        return spots

    def plan(self):
        """Plan du coffre, sans les supérieurs du coffre de test (stockage : cas à part)."""
        return [a for a in plan_transfer(parse_stash(self.p, self.data), self.lib, self.data, {})
                if not is_storage(a['key'])]


@case('Collection', 'transfert : rangement, échange, destruction, restauration, sortie (scénario)')
def transfer_story(ctx):
    s, data = Setup(ctx), ctx.data
    plan = s.plan()
    ctx.expect('1er plan', [(a['kind'], a['key']) for a in plan], [('store', K)])
    apply_transfer(s.p, data, s.lib, plan, backup=False)
    ctx.expect('rangement', (s.claymores(), s.ed(s.lib.stored_item(K, data))), ([], 57))
    s1, _ = s.insert(s.variant(60), s.variant(41))
    plan = s.plan()
    ctx.expect('2e plan', [(a['kind'], s.ed(a['item'])) for a in plan], [('upgrade', 60), ('worse', 41)])
    choices = {item_ref(a['item']): 'exchange' if a['kind'] == 'upgrade' else 'destroy' for a in plan}
    apply_transfer(s.p, data, s.lib, plan, choices, backup=False)
    at = [(i['page'], i['x'], i['y']) for i in parse_stash(s.p, data) if i['code'] == '108 ']
    ctx.expect('échange et destruction', (s.claymores(), at, s.ed(s.lib.stored_item(K, data)), len(s.lib.journal['items'])),
               ([57], [s1], 60, 1))
    ctx.expect('restauration', (restore_destroyed(s.p, data, s.lib, backup=False)[1:], s.claymores(), s.lib.journal['items']),
               ((1, 0), [41, 57], []))
    take_out(s.p, data, s.lib, K, backup=False)   # sortie de la collection vers le coffre
    ctx.expect('sortie', (s.claymores(), K in s.lib.collection), ([41, 57, 60], False))
    ctx.raises(EditError, 'sortie d\'une entrée vide', lambda: take_out(s.p, data, s.lib, K, backup=False))


@case('Collection', 'éthéré : place séparée, comparé à part des exemplaires normaux')
def transfer_ethereal(ctx):
    s, data = Setup(ctx), ctx.data
    s.insert(s.variant(50, ethereal=True))
    plan = s.plan()
    ctx.expect('plan', sorted((a['kind'], a['key'], s.ed(a['item'])) for a in plan), [('store', K, 57), ('store', E, 50)])
    apply_transfer(s.p, data, s.lib, plan, backup=False)
    ctx.expect('deux places', (s.ed(s.lib.stored_item(K, data)), s.ed(s.lib.stored_item(E, data)),
                               s.lib.stored_item(E, data)['ethereal'], s.claymores()), (57, 50, True, []))


@case('Collection', 'éthéré : drapeau lu, place éthérée, entrée toujours éthérée (Iron Shard)')
def ethereal_flag(ctx):
    s = Setup(ctx)
    eth = blob_item(s.variant(50, ethereal=True), ctx.data)
    ctx.expect('drapeau et place', (eth['ethereal'], slot_key(eth, ctx.data)), (True, E))
    ctx.expect('toujours éthéré', (always_ethereal('unique:1653', ctx.data), always_ethereal(K, ctx.data)), (True, False))


@case('Collection', 'base sans durabilité (arcs, arbalètes, 10 autres) : pas de place éthérée, ni collection ni stockage')
def bow_not_ethereal(ctx):
    data = ctx.data
    bow = dict(quality='unique', set_unique_id=887, code='160 ')   # The Rift Bow
    ctx.expect('collection', (two_variants('unique:887', data), slot_key(dict(bow, ethereal=True), data),
                              slot_key(bow, data)), (False, None, 'unique:887'))
    sup = dict(quality='superior', code='160 ', sockets=2)
    ctx.expect('stockage', (storage_key(dict(sup, ethereal=True), data), storage_key(sup, data)), (None, 'superior:160:s2'))
    two = [e for e in catalog(data) if data.base(e['code']).kind in ('weapons', 'armor') and two_variants(e['key'], data)]
    ctx.expect('aucune entrée à deux places sur une base sans durabilité',
               [e['name'] for e in two if data.base(e['code']).durability == 0], [])
    ctx.check(not any(item_type_codes({'code': e['code']}, data) & {'bow', 'xbow'} for e in two), 'arc à deux places')
    # bases indestructibles hors arcs : Despondence (Voidforged Staff), set de Horazon (Mage's Plate…)
    ctx.expect("Despondence, Horazon's Guard",(two_variants('unique:80', data), two_variants('set:281', data)), (False, False))


@case('Collection', 'éthéré : image = image normale à 50 % sur le fond de la case')
def ethereal_image(ctx):
    s = Setup(ctx)
    folder = os.path.join(ROOT, 'data', 'items')
    n1 = icon_layers(blob_item(s.blob, ctx.data), ctx.data, '#123456', folder)[1]
    e1 = icon_layers(blob_item(s.variant(57, ethereal=True), ctx.data), ctx.data, '#123456', folder)[1]
    ctx.check(e1.tobytes() == Image.blend(Image.new('RGBA', n1.size, '#123456'), n1, ETHEREAL_OPACITY).tobytes(),
              'image éthérée différente de l\'image normale à 50 %')


@case('Collection', 'départage à qualité égale : somme des valeurs les plus prioritaires')
def tie_break(ctx):
    g = [dict(fields=[dict(priority_key='a', value=5), dict(priority_key='b', value=7), dict(priority_key='c', value=2)])]
    ctx.expect('départage', (top_priority_sum(g, {'a': 3, 'c': 3}), top_priority_sum(g, {})), (7, 14))


@case('Collection', "panne pendant l'écriture du coffre : bibliothèque et coffre intacts")
def transfer_failure(ctx):
    s, data = Setup(ctx), ctx.data
    plan = s.plan()   # calculé d'abord : sections vides de la bibliothèque créées avant l'état de référence
    s.lib.save()
    state, stash = read_file(s.lib.path), read_file(s.p)
    real = mxl_library.edit_containers
    mxl_library.edit_containers = lambda *a, **k: (_ for _ in ()).throw(OSError('panne simulée'))
    try:
        ctx.raises(OSError, 'panne', lambda: apply_transfer(s.p, data, s.lib, plan, backup=False))
    finally:
        mxl_library.edit_containers = real
    ctx.expect('bibliothèque et coffre intacts', (read_file(s.lib.path) == state, read_file(s.p) == stash), (True, True))


# ---------------------------------------------------------------- transfert depuis le personnage

class CharSetup(Setup):
    """Setup + personnage du 2e coffre (c.d2s : cube Horadrim dans le sac, cube vide) : Jared's Fragmentor ED 60
    posée dans son sac, ED 41 dans son cube ; sources du transfert : coffre, sac, cube."""

    def __init__(self, ctx):
        super().__init__(ctx)
        self.d2s = ctx.copy(os.path.join(FIXTURES, 'stash2', 'Nekratall.d2s'), 'c.d2s')
        for where, value in (('inventory', 60), ('cube', 41)):
            f = ItemFile(self.d2s, self.data, where=where)
            spot = free_spot(f.items, blob_item(self.blob, self.data), self.data, box=f.box)
            edit_stash(self.d2s, self.data, insert=[(*spot, self.variant(value))], backup=False, where=where)
        self.sources = [(self.p, None), (self.d2s, 'inventory'), (self.d2s, 'cube')]

    def eds(self, where):
        return sorted(self.ed(i) for i in read_items(self.d2s, self.data, where) if i['code'] == '108 ')

    def plan(self):
        return [a for a in plan_transfer(transfer_items(self.sources, self.data), self.lib, self.data, {})
                if a['key'] == K]


@case('Collection', 'transfert depuis le personnage : coffre, sac et cube comparés ensemble, restauration')
def transfer_character(ctx):
    s, data = CharSetup(ctx), ctx.data
    items = transfer_items(s.sources, data)
    ctx.expect('conteneurs lus', sorted({(os.path.basename(i['_src'][0]), i['_src'][1]) for i in items}, key=str),
               [('c.d2s', 'cube'), ('c.d2s', 'inventory'), ('c.stash', None)])
    plan = s.plan()
    ctx.expect('plan', [(a['kind'], s.ed(a['item']), a['item']['_src'][1]) for a in plan],
               [('store', 60, 'inventory'), ('worse', 57, None), ('worse', 41, 'cube')])
    calls = []
    real = mxl_library.edit_containers
    mxl_library.edit_containers = lambda path, d, changes, backup: calls.append(sorted(changes, key=str)) or real(
        path, d, changes, backup)
    try:
        choices = {item_ref(a['item']): 'destroy' for a in plan if s.ed(a['item']) == 41}
        baks = apply_transfer(None, data, s.lib, plan, choices, backup=False)
    finally:
        mxl_library.edit_containers = real
    ctx.expect('fichiers écrits (sac et cube en une écriture, coffre inchangé)', (list(baks), calls),
               ([s.d2s], [['cube', 'inventory']]))
    ctx.expect('après transfert', (s.eds('inventory'), s.eds('cube'), s.claymores(), s.ed(s.lib.stored_item(K, data)),
                                   s.lib.collection[K]['source']), ([], [], [57], 60, 'c.d2s'))
    ctx.expect('journal', [(e['file'], e['where']) for e in s.lib.journal['items']], [(s.d2s, 'cube')])
    ctx.expect('restauration dans le cube', (restore_destroyed(None, data, s.lib, backup=False)[1:], s.eds('cube'),
                                             s.claymores()), ((1, 0), [41], [57]))


@case('Collection', 'transfert depuis le personnage : échange rapatrié dans le conteneur du nouvel exemplaire')
def transfer_character_exchange(ctx):
    s, data = CharSetup(ctx), ctx.data
    apply_transfer(s.p, data, s.lib, plan_transfer(parse_stash(s.p, data), s.lib, data, {}), backup=False)   # 57 rangé
    plan = s.plan()
    ctx.expect('plan', [(a['kind'], s.ed(a['item']), a['item']['_src'][1]) for a in plan],
               [('upgrade', 60, 'inventory'), ('worse', 41, 'cube')])
    apply_transfer(None, data, s.lib, plan, backup=False)
    ctx.expect('ancien exemplaire dans le sac', (s.eds('inventory'), s.eds('cube'), s.ed(s.lib.stored_item(K, data))),
               ([57], [41], 60))


@case('Collection', 'transfert depuis le personnage : panne au 2e fichier, objets du 1er rangés, aucun perdu')
def transfer_character_failure(ctx):
    s, data = CharSetup(ctx), ctx.data
    plan = s.plan()   # store 60 (sac : .d2s écrit en premier), 57 détruit (coffre : écriture en panne)
    stash = read_file(s.p)
    real = mxl_library.edit_containers

    def fake(path, *a, **k):
        if path == s.p:
            raise OSError('panne simulée')
        return real(path, *a, **k)
    mxl_library.edit_containers = fake
    try:
        choices = {item_ref(a['item']): 'destroy' for a in plan if a['kind'] == 'worse'}
        ctx.raises(OSError, 'panne', lambda: apply_transfer(None, data, s.lib, plan, choices, backup=False))
    finally:
        mxl_library.edit_containers = real
    ctx.expect('sac et cube écrits, coffre intact, rien perdu',
               (s.eds('inventory'), s.eds('cube'), read_file(s.p) == stash, s.ed(s.lib.stored_item(K, data)),
                [(e['where'], e['file'] == s.d2s) for e in s.lib.journal['items']]),
               ([], [], True, 60, [('cube', True)]))
    reread = Library(s.lib.path)
    ctx.expect('bibliothèque enregistrée', (s.ed(reread.stored_item(K, data)), len(reread.journal['items'])), (60, 1))


@case('Collection', 'transfert depuis le personnage : charmes du sac écartés (bonus), pas ceux du coffre ni du cube')
def transfer_character_charms(ctx):
    s, data = CharSetup(ctx), ctx.data
    real = mxl_library.item_type_codes   # Jared's Fragmentor (sac 60, coffre 57, cube 41) traitée comme un charme
    mxl_library.item_type_codes = lambda it, d: {'char'} if it['code'] == '108 ' else real(it, d)
    try:
        eds = lambda **k: sorted((s.ed(i), i['_src'][1] or 'stash') for i in transfer_items(s.sources, data, **k)
                                 if i['code'] == '108 ')
        ctx.expect('personnage entier', eds(bag_charms=False), [(41, 'cube'), (57, 'stash')])
        ctx.expect('objet choisi (sac)', eds(), [(41, 'cube'), (57, 'stash'), (60, 'inventory')])
    finally:
        mxl_library.item_type_codes = real


# ---------------------------------------------------------------- stockage des supérieurs

@case('Collection', 'stockage des supérieurs : places, hors collection et découvertes, classement, sortie')
def superior_storage(ctx, copy=None):
    """copy(p, lib, key) : appelé avant la sortie de l'arme stockée (module mxl_editor : copie vers le coffre)."""
    data = ctx.data
    p = ctx.copy(CONTAINERS, 's.shared')
    lib = Library(os.path.join(ctx.tmp, 'library.json'))
    items = parse_stash(p, data)
    sup = lambda code: next(i for i in items if i['code'] == code and i.get('quality') == 'superior')
    ctx.expect('places', [storage_key(sup(c), data) for c in ('277 ', '607 ')], ['superior:277:s4:db', 'superior:607:s1:db:eth'])
    runic = dict(sup('277 '), socketed=[dict(code='r01 ')])   # objet serti : supérieur runique
    ctx.expect('exclus : runique, sans socket ; jamais au catalogue',
               (storage_key(runic, data), storage_key(dict(quality='superior', code='277 ', sockets=0), data),
                entry_key(sup('277 '), data)), (None, None, None))
    # 1er critère : armure avec Physical Resist (1) / sans (0) ; arme : Enhanced Damage brut
    ctx.expect('1er critère', [rank(sup(c), data, {})[0] for c in ('2@J ', '706 ', '277 ', '730 ')], [1, 0, 40, (25, 1)])

    def variants(code, *values):
        """Exemplaires du supérieur code posés dans le coffre, valeurs modifiées : [(stat, valeur)…] par exemplaire."""
        it = next(i for i in parse_stash(p, data) if i['code'] == code and i.get('quality') == 'superior')   # fichier à jour
        blob, out = item_blob(read_file(p), it), []
        for vals in values:
            b = bytes(blob)
            for sid, v in vals:
                bb = bytearray(b)
                set_raw_stat(bb, blob_item(b, data), sid, v, data)
                b = bytes(bb)
            out.append(b)
        placed = parse_stash(p, data)
        spots = []
        for b in out:
            spot = free_spot(placed, blob_item(b, data), data, box=SHARED)
            placed.append(dict(blob_item(b, data), page=spot[0], x=spot[1], y=spot[2]))
            spots.append(spot)
        edit_stash(p, data, insert=[(*sp, b) for sp, b in zip(spots, out)], backup=False)
        return storage_key(it, data)
    # arme : ED 50 / AR 50 (qualité 50 %) devant ED 45 / AR 100 (qualité 83 %) : Enhanced Damage d'abord
    wkey = variants('277 ', [(17, 50), (119, 50)], [(17, 45), (119, 100)])
    # armure (Physical Resist sur les deux) : qualité ensuite, défense améliorée 50 devant 36
    akey = variants('2@J ', [(16, 50)])
    # bottes : Movement Speed d'abord (40, défense améliorée au minimum, devant 25 et défense 47)
    bkey = variants('730 ', [(96, 40), (16, 35)])
    stash = parse_stash(p, data)
    plan = [a for a in plan_transfer(stash, lib, data, {}) if a['key'] in (wkey, akey, bkey)]
    best = {a['key']: a['item'] for a in plan if a['kind'] == 'store'}
    value = lambda it, sid: next(x['value'] for x in it['stats'] if x['id'] == sid)
    ctx.expect('meilleurs', ((value(best[wkey], 17), value(best[wkey], 119)), value(best[akey], 16),
                             (value(best[bkey], 96), value(best[bkey], 16))), ((50, 50), 50, (40, 35)))
    apply_transfer(p, data, lib, plan, backup=False)
    lib.record_found(parse_stash(p, data), data, 's.shared')
    ctx.expect('stockage seul (ni collection, ni découvertes)',
               (sorted(lib.storage), [k for k in lib.collection if is_storage(k)], [k for k in lib.found if is_storage(k)]),
               (sorted([wkey, akey, bkey]), [], []))
    if copy:
        copy(p, lib, wkey)
    n = lambda: sum(1 for i in parse_stash(p, data) if i['code'] == '277 ')
    before = n()
    take_out(p, data, lib, wkey, backup=False)
    ctx.expect('sortie', (n(), wkey in lib.storage, akey in lib.storage), (before + 1, False, True))


@case('Collection', 'stockage des supérieurs : double bonus à part (armure : Physical Resist + ED ; arme : AR + ED), places reprises')
def superior_double(ctx):
    """Même objet de base, mêmes sockets : double bonus et bonus simple gardés tous les deux (10/10) ; Heavy Boots
    2 sockets avec et sans +1 % Physical Resist, arme (277) avec et sans % Bonus to Attack Rating ; ancienne place d'un
    double bonus : reprise par rekey_storage, une seule fois, rien de perdu."""
    import base64
    from mxl_library import DOUBLE, storage_double
    data = ctx.data
    p = ctx.copy(CONTAINERS, 'r.shared')
    lib = Library(os.path.join(ctx.tmp, 'library.json'))
    keys = []
    for code, stat in (('730 ', 36), ('277 ', 119)):
        it = next(i for i in parse_stash(p, data) if i['code'] == code and i.get('quality') == 'superior')
        blob = bytearray(item_blob(read_file(p), it))
        set_raw_stat(blob, blob_item(bytes(blob), data), stat, 0, data)   # même objet, bonus simple
        spot = free_spot(parse_stash(p, data), it, data, box=SHARED)
        edit_stash(p, data, insert=[(*spot, bytes(blob))], backup=False)
        keys += sorted(storage_key(i, data) for i in parse_stash(p, data) if i['code'] == code and i.get('quality') == 'superior')
    ctx.expect('places', keys, ['superior:730:s2', 'superior:730:s2' + DOUBLE, 'superior:277:s4', 'superior:277:s4' + DOUBLE])
    plan = [a for a in plan_transfer(parse_stash(p, data), lib, data, {}) if a['key'] in keys]
    ctx.expect('tous stockés', sorted((a['kind'], a['key']) for a in plan), sorted(('store', k) for k in keys))
    apply_transfer(p, data, lib, plan, backup=False)
    ctx.expect('stockage', (sorted(k for k in lib.storage if k in keys) == sorted(keys), [storage_double(k) for k in keys]),
               (True, [False, True, False, True]))
    # bibliothèque plus ancienne : double bonus rangé sans DOUBLE (ou avec l'ancien suffixe :pr), repris à sa place
    old = Library(os.path.join(ctx.tmp, 'old.json'))
    old.storage['superior:730:s2'] = dict(lib.storage[keys[1]])
    old.storage['superior:277:s4:pr'] = dict(lib.storage[keys[3]])
    ctx.expect('reprise', (old.rekey_storage(data), sorted(old.storage), old.rekey_storage(data)),
               (2, sorted([keys[1], keys[3]]), 0))
    ctx.check(base64.b64decode(old.storage[keys[1]]['blob']) == base64.b64decode(lib.storage[keys[1]]['blob']),
              'objet changé par la reprise')


@case('Collection', 'remise à zéro des découvertes : entrées non rangées oubliées, entrées rangées gardées avec leur date')
def reset_found(ctx):
    s, data = Setup(ctx), ctx.data
    s.lib.record_found(parse_stash(s.p, data), data, 'c.stash')
    apply_transfer(s.p, data, s.lib, s.plan(), backup=False)   # Jared's Fragmentor rangée
    stored = {k for k in s.lib.found if k == K}
    date = s.lib.found[K]['date']
    n = len(s.lib.found)
    ctx.expect('comptes', s.lib.found_reset_counts(), (n - 1, 1))
    ctx.expect('remise à zéro', (s.lib.reset_found(), set(s.lib.found), s.lib.found[K]['date']), ((n - 1, 1), stored, date))
    again = Library(s.lib.path)   # écrit sur le disque
    ctx.expect('relue', (set(again.found), again.reset_found()), (stored, (0, 1)))
