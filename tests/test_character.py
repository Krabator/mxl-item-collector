"""Tests : lecture complète d'un personnage (.d2s) : rangement des objets, mercenaire, cadavre, golem, grilles."""
import os, re, struct
from common import case, FIXTURES, STASH as STASH_FILE
from mxl_save import (load_character, read_items, parse_stash, move_item, transfer_item, edit_stash,
                      free_spot, move_between, placement_error, ItemFile, character_checksum, EditError)
from mxl_containers import STASH, SLOTS, character_containers, place, placed
from mxl_tooltip import item_tooltip

# Nekratall au 30/09 : 10 objets portés, 6 potions à la ceinture, 2 objets en inventaire, 2 dans le cube,
# mercenaire avec 6 objets portés, pas de cadavre ni de golem
CHARACTER = os.path.join(FIXTURES, 'character', 'Nekratall.d2s')


@case('Personnage', 'grilles lues dans les tables du jeu (inventaire, cube, coffre)')
def grids(ctx):
    boxes = character_containers(ctx.data)
    ctx.expect('inventaire', (boxes['inventory'].cols, boxes['inventory'].rows), (15, 10))
    ctx.expect('cube', (boxes['cube'].cols, boxes['cube'].rows), (15, 10))
    ctx.expect('coffre (table du jeu = conteneur STASH)', ctx.data.grids['stash'], (STASH.cols, STASH.rows))
    ctx.check(boxes['inventory'].writable and boxes['cube'].writable, 'inventaire et cube modifiables')


@case('Personnage', 'rangement de chaque objet (portés, ceinture, inventaire, cube)')
def places(ctx):
    ch = load_character(CHARACTER, ctx.data)
    ctx.expect('erreur des sections suivantes', ch['extra_error'], None)
    ctx.expect('objets par rangement', {w: len(placed(ch['items'], w)) for w in ('equipped', 'belt', 'inventory', 'cube')},
               dict(equipped=10, belt=6, inventory=2, cube=2))
    ctx.check(all(place(it) for it in ch['items']), 'aucun objet sans rangement')
    # points investis (section 'if', ✅ arbre de compétences en jeu) : Blood Skeleton, Embalming, Abyss Knight, Night
    # Hawks, et la compétence interne sans nom à 1 point de tous les personnages
    ctx.expect('points de compétences', {ctx.data.skill_names.get(k) or k: v for k, v in ch['skills'].items()},
               {'Blood Skeleton': 12, 'Embalming': 1, 'Abyss Knight': 6, 'Night Hawks': 1, 1456: 1})
    ctx.expect('emplacements portés', sorted(SLOTS[it['equipped']] for it in placed(ch['items'], 'equipped')),
               sorted(SLOTS[n] for n in range(1, 11)))
    ctx.expect('objets du cube (code, x, y)', sorted((it['code'].strip(), it['x'], it['y']) for it in placed(ch['items'], 'cube')),
               [('618', 10, 3), ('7@5', 0, 0)])
    for key, box in character_containers(ctx.data).items():   # chaque objet tient dans sa grille, sans chevauchement
        cells = [(it['x'] + dx, it['y'] + dy) for it in placed(ch['items'], key)
                 for dx in range(ctx.data.base(it['code']).size[0]) for dy in range(ctx.data.base(it['code']).size[1])]
        ctx.check(all(0 <= x < box.cols and 0 <= y < box.rows for x, y in cells), f'{key} : objets dans la grille')
        ctx.expect(f'{key} : cases occupées une seule fois', len(cells), len(set(cells)))


@case('Personnage', 'mercenaire, cadavre et golem')
def extras(ctx):
    ch = load_character(CHARACTER, ctx.data)
    merc = ch['mercenary']
    ctx.expect('mercenaire (type, mort, objets)', (merc['type'], merc['dead'], len(merc['items'])), (1, False, 6))
    ctx.check(all(place(it) == 'equipped' for it in merc['items']), 'objets du mercenaire : tous portés')
    ctx.expect('emplacements du mercenaire', sorted(it['equipped'] for it in merc['items']), [1, 2, 3, 8, 9, 10])
    ctx.expect('cadavre et golem', (ch['corpse'], ch['golem']), ([], None))
    for it in ch['items'] + merc['items']:   # infobulle de chaque objet sans erreur
        ctx.check(item_tooltip(it, ctx.data, ch), f"infobulle de {it['name']}")
    # personnage sans mercenaire (coffre de référence n° 2, 27/09)
    old = load_character(os.path.join(FIXTURES, 'stash2', 'Nekratall.d2s'), ctx.data)
    ctx.expect('ancien fichier : erreur', old['extra_error'], None)


@case('Personnage', 'section illisible après les objets : personnage lu quand même, erreur gardée')
def damaged_extras(ctx):
    p = ctx.copy(CHARACTER)
    b = bytearray(open(p, 'rb').read())
    b[b.rfind(b'kf')] = ord('x')   # marqueur du golem abîmé
    open(p, 'wb').write(b)
    ch = load_character(p, ctx.data)
    ctx.check(ch['extra_error'], 'erreur gardée')
    ctx.expect('objets du personnage', len(ch['items']), 20)


def sound(ctx, path, what):
    """Personnage encore valide après une écriture : taille et somme de contrôle justes, sections lisibles, objets
    hors du cube inchangés (10 portés, 6 à la ceinture, 2 en inventaire, mercenaire à 6 objets)."""
    b = open(path, 'rb').read()
    ctx.expect(f"{what} : taille dans l'en-tête", struct.unpack_from('<I', b, 8)[0], len(b))
    ctx.expect(f'{what} : somme de contrôle', struct.unpack_from('<I', b, 12)[0], character_checksum(b))
    ch = load_character(path, ctx.data)
    ctx.expect(f'{what} : sections suivantes', ch['extra_error'], None)
    ctx.expect(f'{what} : autres objets', ([len(placed(ch['items'], w)) for w in ('equipped', 'belt', 'inventory')],
                                          len(ch['mercenary']['items'])), ([10, 6, 2], 6))
    return placed(ch['items'], 'cube')


@case('Personnage', "cube : fichier reconstruit à l'identique ; déplacement écrit, personnage valide")
def cube_move_edit(ctx):
    data = ctx.data
    p = ctx.copy(CHARACTER)
    ItemFile(p, data).check()   # reconstruction sans modification = fichier d'origine (somme de contrôle comprise)
    helm = next(i for i in read_items(p, data) if i['code'] == '618 ')
    ctx.expect('objet du cube lu', (helm['page'], helm['x'], helm['y']), (0, 10, 3))
    move_item(p, helm, 13, 8, data, backup=False)   # dernière case possible d'un objet 2 × 2 dans 15 × 10
    cube = sound(ctx, p, 'déplacement')
    ctx.expect('déplacé', sorted((i['code'], i['x'], i['y']) for i in cube), [('618 ', 13, 8), ('7@5 ', 0, 0)])
    helm = next(i for i in read_items(p, data) if i['code'] == '618 ')
    ctx.raises(EditError, 'hors de la grille', lambda: move_item(p, helm, 14, 8, data, backup=False))
    ctx.raises(EditError, 'chevauchement', lambda: move_item(p, helm, 0, 1, data, backup=False))


@case('Personnage', "cube <-> coffre : transfert dans les deux sens, panneau de l'objet réécrit, personnage valide")
def cube_transfer(ctx):
    data = ctx.data
    p, stash = ctx.copy(CHARACTER), ctx.copy(STASH_FILE)
    n_stash = len(parse_stash(stash, data))
    helm = next(i for i in read_items(p, data) if i['code'] == '618 ')
    page, x, y = free_spot(parse_stash(stash, data), helm, data)
    transfer_item(p, stash, helm, page, x, y, data, backup_src=False, backup_dst=False)
    ctx.expect('cube après le départ', [i['code'] for i in sound(ctx, p, 'cube -> coffre')], ['7@5 '])
    got = next(i for i in parse_stash(stash, data) if (i['page'], i['x'], i['y']) == (page, x, y))
    ctx.expect('objet dans le coffre (code, emplacement, panneau)', (got['code'], got['location'], got['panel']), ('618 ', 0, 5))
    ctx.expect('stats conservées', got['stats'] and [(s['id'], s['value']) for s in got['stats']],
               [(s['id'], s['value']) for s in helm['stats']])
    # un objet du coffre avec objets sertis vers le cube
    f = ItemFile(p, data)
    src = next(i for i in parse_stash(stash, data) if i['socketed'] and free_spot(f.items, i, data, box=f.box))
    _, cx, cy = free_spot(f.items, src, data, box=f.box)
    transfer_item(stash, p, src, 0, cx, cy, data, backup_src=False, backup_dst=False)
    cube = sound(ctx, p, 'coffre -> cube')
    got = next(i for i in cube if (i['x'], i['y']) == (cx, cy))
    ctx.expect('objet dans le cube (code, emplacement, panneau, sertis)',
               (got['code'], got['location'], got['panel'], len(got['socketed'])), (src['code'], 0, 4, len(src['socketed'])))
    ctx.expect("nombre d'objets du coffre", len(parse_stash(stash, data)), n_stash)
    ctx.raises(EditError, 'place occupée dans le cube', lambda: edit_stash(
        p, data, insert=[(0, cx, cy, ItemFile(stash, data).entries[0][1])], backup=False))


@case('Personnage', 'cube : somme de contrôle fausse dans le fichier = reconstruction refusée')
def cube_bad_checksum(ctx):
    p = ctx.copy(CHARACTER)
    b = bytearray(open(p, 'rb').read())
    b[12] ^= 1
    open(p, 'wb').write(b)
    helm = next(i for i in read_items(p, ctx.data) if i['code'] == '618 ')
    ctx.raises(EditError, 'retrait refusé', lambda: edit_stash(p, ctx.data, remove=[helm['_offset']], backup=False))
    ctx.expect('fichier inchangé', open(p, 'rb').read(), bytes(b))


def sound_bag(ctx, path, what, bag, cube):
    """Personnage valide après une écriture dans le sac : taille, somme de contrôle, sections suivantes, objets portés
    et ceinture inchangés ; bag, cube = nombres d'objets attendus."""
    b = open(path, 'rb').read()
    ctx.expect(f'{what} : somme de contrôle', (struct.unpack_from('<II', b, 8)), (len(b), character_checksum(b)))
    ch = load_character(path, ctx.data)
    ctx.expect(f'{what} : rangements', (ch['extra_error'], [len(placed(ch['items'], w)) for w in ('equipped', 'belt', 'inventory', 'cube')]),
               (None, [10, 6, bag, cube]))
    return ch


@case('Personnage', 'sac : déplacement, sac <-> cube (une écriture), sac <-> coffre ; cube Horadrim jamais dans le cube')
def bag_writes(ctx):
    data = ctx.data
    p, stash = ctx.copy(CHARACTER), ctx.copy(STASH_FILE)
    bag = ItemFile(p, data, where='inventory')
    ctx.expect('sac lu (codes)', sorted(i['code'] for i in bag.items), ['3o[ ', 'box '])
    cube_item = next(i for i in bag.items if i['code'] == 'box ')
    other = next(i for i in bag.items if i['code'] != 'box ')
    # le cube Horadrim ne va pas dans le cube (refus du placement, de l'écriture directe et du transfert)
    cube_box = character_containers(data)['cube']
    ctx.check(placement_error([], cube_item, 0, 5, 5, data, cube_box), 'cube Horadrim accepté dans le cube')
    ctx.raises(EditError, 'cube Horadrim écrit dans le cube', lambda: move_between(p, cube_item, 'inventory', 'cube', 5, 5, data, backup=False))
    before = open(p, 'rb').read()
    ctx.raises(EditError, 'cube Horadrim transféré dans le cube', lambda: edit_stash(
        p, data, insert=[(0, 5, 5, ItemFile(p, data, where='inventory').entries[0][1])], backup=False, where='cube'))
    ctx.expect('fichier inchangé après les refus', open(p, 'rb').read(), before)
    # déplacement dans le sac
    move_item(p, cube_item, 10, 5, data, backup=False, where='inventory')
    sound_bag(ctx, p, 'déplacement dans le sac', 2, 2)
    got = next(i for i in read_items(p, data, 'inventory') if i['code'] == 'box ')
    ctx.expect('cube Horadrim déplacé', (got['x'], got['y'], got['panel']), (10, 5, 1))
    # sac -> cube puis cube -> sac (même fichier, une écriture)
    move_between(p, other, 'inventory', 'cube', 5, 5, data, backup=False)
    sound_bag(ctx, p, 'sac -> cube', 1, 3)
    moved = next(i for i in read_items(p, data, 'cube') if (i['x'], i['y']) == (5, 5))
    ctx.expect('objet dans le cube', (moved['code'], moved['panel']), (other['code'], 4))
    helm = next(i for i in read_items(p, data, 'cube') if i['code'] == '618 ')
    move_between(p, helm, 'cube', 'inventory', 0, 0, data, backup=False)
    sound_bag(ctx, p, 'cube -> sac', 2, 2)
    helm = next(i for i in read_items(p, data, 'inventory') if i['code'] == '618 ')
    ctx.expect('casque dans le sac', (helm['x'], helm['y'], helm['panel']), (0, 0, 1))
    # sac -> coffre, coffre -> sac
    helm = next(i for i in read_items(p, data, 'inventory') if i['code'] == '618 ')
    n_stash = len(parse_stash(stash, data))
    page, x, y = free_spot(parse_stash(stash, data), helm, data)
    transfer_item(p, stash, helm, page, x, y, data, backup_src=False, backup_dst=False, src_where='inventory')
    sound_bag(ctx, p, 'sac -> coffre', 1, 2)
    got = next(i for i in parse_stash(stash, data) if (i['page'], i['x'], i['y']) == (page, x, y))
    ctx.expect('casque dans le coffre', (got['code'], got['panel'], len(parse_stash(stash, data))), ('618 ', 5, n_stash + 1))
    f = ItemFile(p, data, where='inventory')
    _, bx, by = free_spot(f.items, got, data, box=f.box)
    transfer_item(stash, p, got, page, bx, by, data, backup_src=False, backup_dst=False, dst_where='inventory')
    sound_bag(ctx, p, 'coffre -> sac', 2, 2)
    got = next(i for i in read_items(p, data, 'inventory') if (i['x'], i['y']) == (bx, by))
    ctx.expect('casque revenu dans le sac', (got['code'], got['panel']), ('618 ', 1))


@case('Personnage', 'cube Horadrim : refusé dans le coffre partagé ; état du cube du personnage (possédé, lecture seule, absent)')
def horadric_cube(ctx):
    from mxl_containers import SHARED_BOX, cube_status
    data = ctx.data
    p = ctx.copy(CHARACTER)
    shared = ctx.copy(os.path.join(FIXTURES, 'stash2', 'Nekratall.stash'), '_sharedstash.shared')
    box = next(i for i in read_items(p, data, 'inventory') if i['code'] == 'box ')
    ctx.check(placement_error([], box, 0, 0, 0, data, SHARED_BOX), 'cube Horadrim accepté dans le coffre partagé')
    ctx.check(placement_error([], box, 0, 0, 0, data, STASH) is None, 'cube Horadrim refusé dans le coffre du personnage')
    ctx.expect('forme du coffre partagé', ItemFile(shared, data).box, SHARED_BOX)
    before = open(shared, 'rb').read(), open(p, 'rb').read()
    page, x, y = free_spot(parse_stash(shared, data), box, data)
    ctx.raises(EditError, 'cube Horadrim transféré dans le coffre partagé', lambda: transfer_item(
        p, shared, box, page, x, y, data, backup_src=False, backup_dst=False, src_where='inventory'))
    ctx.expect('fichiers inchangés', (open(shared, 'rb').read(), open(p, 'rb').read()), before)
    ch = load_character(p, data)
    others = [i for i in ch['items'] if i['code'] != 'box ']
    ctx.expect('états du cube', [cube_status(ch['items'], []), cube_status(others, []), cube_status(others, [box]),
                                 cube_status(placed(others, 'inventory'), [])], ['ok', 'readonly', 'ok', 'none'])


@case('Personnage', 'objets portés et mercenaire : lus sur place, pas de déplacement')
def worn_no_move(ctx):
    data = ctx.data
    p = ctx.copy(CHARACTER)
    worn, merc = ItemFile(p, data, where='equipped'), ItemFile(p, data, where='mercenary')
    ctx.expect('objets lus', (len(worn.items), len(merc.items)), (10, 6))
    armor = next(i for i in worn.items if i['equipped'] == 3)
    circlet = next(i for i in merc.items if i['equipped'] == 1)
    before = open(p, 'rb').read()
    ctx.raises(EditError, 'objet porté déplacé', lambda: move_item(p, armor, 0, 0, data, backup=False, where='equipped'))
    ctx.raises(EditError, 'objet du mercenaire déplacé',
               lambda: move_item(p, circlet, 0, 0, data, backup=False, where='mercenary'))
    ctx.check(open(p, 'rb').read() == before, 'personnage modifié')


@case('Personnage', 'statistiques totales comparées à la feuille de personnage de Nekratall en jeu')
def character_sheet(ctx):
    """Nekratall au 30/09 (captures de ses trois pages de statistiques en jeu, fichier copié juste après) : objets
    portés, charmes, compétences passives (Embalming : régénération de mana, % de vie, vie des invocations ; compétence
    interne : Grit)."""
    from mxl_char_stats import CharacterStats
    data = ctx.data
    ch = load_character(os.path.join(FIXTURES, 'character_sheet', 'Nekratall.d2s'), data)
    cs = CharacterStats(ch, data)
    sheet = {'Strength': (0, 42), 'Dexterity': (2, 42), 'Vitality': (3, 47), 'Energy': (1, 42), 'All Skill Levels': (127, 1),
             'Fire Resistance': (39, 44), 'Cold Resistance': (43, 40), 'Lightning Resistance': (41, 15),
             'Poison Resistance': (45, 0), 'Physical Resistance': (36, 1), 'Magic Resistance': (37, 0),
             'Magic Find': (80, 44), 'Gold Find': (79, 5), 'Experience Gain': (85, 1), 'Light Radius': (89, 6),
             'Attack Speed': (93, 10), 'Cast Speed': (105, 25), 'Block Speed': (102, 10), 'Hit Recovery': (99, 10),
             'Movement': (96, 10), 'Attack Rating %': (119, 20), 'Spell Focus': (485, 19), 'Fire Spell Damage': (329, 7),
             'Cold Pierce': (335, 4), 'Poison Pierce': (336, 4), 'Life Leech': (60, 2), 'Mana After Each Kill': (138, 2),
             'Mana on Melee Attack': (295, 4), 'Life Regeneration (x10)': (74, 75), 'Mana Regeneration %': (27, 7),
             'Summon Life %': (444, 53), 'Life % bonus': (76, 14), 'Grit %': (184, 4)}
    ctx.expect('feuille de personnage', {k: cs.stat(sid) for k, (sid, _) in sheet.items()},
               {k: v for k, (_, v) in sheet.items()})
    ctx.expect('niveaux des compétences (points + 1 à toutes)', {data.skill_names.get(k) or k: cs.skill_level(k) for k in ch['skills']},
               {'Blood Skeleton': 13, 'Embalming': 2, 'Abyss Knight': 7, 'Night Hawks': 2, 1456: 2})
    ctx.expect('compétence sans point', cs.skill_level(1599), 0)
    # formules de classe : vie, mana, endurance (feuille : total / base), défense ; en 256es pour les formules
    ctx.expect('vie, mana, endurance, défense', (int(cs.max_life()), int(cs.max_mana()), int(cs.max_stamina()), cs.defense()),
               (874, 364, 50, 338))
    ctx.expect('stats lues par les formules (256es)', (cs.stat(7) // 256, cs.stat(8) // 256, cs.stat(31)), (874, 364, 338))
    # « Bonus to Defense » (stat 171) puis stat 182 : % de la défense totale (D2Common.dll 10672 ; ✅ Kalidor avec
    # Lionheart +186 % : 848 -> 2425 sur sa feuille en jeu)
    saved = dict(cs.totals)
    cs.totals[(171, None)] = 186
    cs.totals[(182, None)] = -40
    ctx.expect('défense avec bonus de défense (338 × 2,86 = 966, puis -40 % = 580)', cs.defense(), 580)
    cs.totals = saved
    ctx.expect('blocage (total, base, bonus au plafond)', (cs.block_chance(), cs.base_block_chance(), cs.stat(213)), (1, 1, 0))
    # plafond (documentation officielle) : 50 %, relevé par « Maximum Block Chance » jusqu'à 80 %
    cs.attribute = lambda sid: 10000   # Dextérité énorme : la formule dépasse le plafond
    caps = []
    for bonus in (0, 10, 100):
        cs.totals[(213, None)] = bonus
        caps.append(cs.block_chance())
    ctx.expect('plafonds (bonus 0, 10, 100)', caps, [50, 60, 80])


@case('Personnage', "opérations de itemstatcost (par niveau, % d'attribut, % de vie) et auras données par les objets")
def character_stat_ops(ctx):
    """Règles du jeu (D2Common.dll 0x6fd89530), calculées à la main : personnage niveau 40 (vie / mana enregistrées
    100 / 50, Vitalité 25, Énergie 20) ; objets : +20 vie, +10 % vie (op 11 sur la valeur propre 120), +8 vie par niveau
    (216 : 8 × 256 × 40 >> 5 = 10 vie), +5 Vitalité, +20 % Vitalité (op 11 : 30 × 20 % = 6 -> 36), +10 % Énergie (2) et
    +16 Énergie par niveau (499 : 16 × 40 >> 5 = 20 -> 42), +16 résistance au feu par niveau (231 -> 20), +8 dégâts de
    sort de feu par niveau (404, op 4 -> 10), +10 mana par niveau (217 : 12,5 mana). Aura Demon Blood niveau 1 (stat
    151) : +6 % de vie, état d'aura actif."""
    from mxl_char_stats import CharacterStats
    data = ctx.data
    ch = dict(cls=4, level=40, skills={}, items=[],
              base_stats={7: 100 * 256, 9: 50 * 256, 11: 80 * 256, 1: 20, 3: 25})
    cs = CharacterStats(ch, data)
    cs.add([{'id': i, 'param': None, 'value': v} for i, v in
            ((7, 20), (76, 10), (216, 8), (3, 5), (362, 20), (361, 10), (499, 16), (231, 16), (404, 8), (217, 10))])
    row = cs.class_row()
    per_vit, per_energy = row[0x46] / 4, row[0x48] / 4
    ctx.expect('attributs (Vitalité, Énergie)', (cs.attribute(3), cs.attribute(1), cs.stat(3), cs.stat(1)), (36, 42, 36, 42))
    ctx.expect('vie : 120 + 12 + 10 + 11 Vitalité', cs.max_life(), 120 + 12 + 10 + 11 * per_vit)
    ctx.expect('mana : 50 + 12,5 + 22 Énergie', cs.max_mana(), 50 + 12.5 + 22 * per_energy)
    ctx.expect('stat 7 lue par les formules (256es)', cs.stat(7), int((120 + 12 + 10 + 11 * per_vit) * 256))
    ctx.expect('résistance et dégâts de sort par niveau', (cs.stat(39), cs.stat(329)), (20, 10))
    # aura donnée par un objet : stats de l'aura à son niveau, état actif
    demon_blood = 1900
    cs.add([{'id': 151, 'param': demon_blood, 'value': 1}])
    for key, v in cs.item_aura_stats()[demon_blood].items():
        cs.totals[key] = cs.totals.get(key, 0) + v
    ctx.expect('% de vie avec Demon Blood (16 % en 256es : 4915 / 256)', cs.max_life(), 120 + 4915 / 256 + 10 + 11 * per_vit)
    from mxl_skill_calc import skill_calc
    state = skill_calc(data).rec(demon_blood).u16(0x80)
    ctx.expect("état de l'aura actif", (cs.has_state(state), cs.auras), (True, {demon_blood: 1}))
    ctx.expect('aura absente des stats', cs.stat(151, demon_blood), 0)
    # même aura sur deux objets d'un même porteur : niveaux additionnés (total de la stat 151, D2Game.dll 0x6fcc37d0)
    cs.add([{'id': 151, 'param': demon_blood, 'value': 2}])
    ctx.expect('niveaux additionnés (1 + 2)', cs.auras, {demon_blood: 3})
    # valeurs de l'aura évaluées avec les stats du porteur : dégâts de sort de Demon Blood = stat(432) + syn1 (stat 383
    # de la compétence : Relic « +15% Elemental Spell Damage to Demon Blood Aura ») ; Relic dans le sac du personnage
    relic = {'id': 383, 'param': demon_blood, 'value': 15}
    cs.add([relic])
    ctx.expect('aura portée par le personnage : syn1 = 15', cs.item_aura_stats()[demon_blood][(329, None)], 15)
    # aura portée par le mercenaire (Rogue de Nekratall : type 1, 14 414 points d'expérience -> niveau 24) : comptée
    # pour le personnage, évaluée avec les stats du mercenaire (sans la Relic : 0) ; ses autres stats : pour lui seul
    from mxl_char_stats import mercenary_level
    import mxl_char_stats
    aura_items = [dict(location=1, equipped=e, stats=[{'id': 151, 'param': demon_blood, 'value': v}, {'id': 0, 'value': 50}])
                  for e, v in ((3, 3), (4, 2))]
    real = mxl_char_stats.all_stats
    mxl_char_stats.all_stats = lambda it, d: it.get('stats', []) if 'stats' in it and 'code' not in it else real(it, d)
    try:
        merc = dict(type=1, experience=14414, dead=False, items=aura_items)
        ctx.expect('niveau du mercenaire', mercenary_level(merc, data), 24)
        cs2 = CharacterStats(dict(ch, mercenary=merc), data)
        cs2.add([relic])
        m = cs2.mercenary
        ctx.expect('stats du mercenaire (Force 108 + 2 × 50, Dextérité 218, vie 634 + 6 % de sa propre aura)',
                   (m.attribute(0), m.attribute(2), m.max_life()), (208, 218, (162304 + 162304 * 6 // 100) / 256))
        ctx.expect('aura du mercenaire : niveaux additionnés (3 + 2), Force du mercenaire pas au personnage',
                   (cs2.aura_levels, cs2.auras, cs2.attribute(0)), ({demon_blood: 5}, {}, 0))
        ctx.expect('aura du mercenaire évaluée avec ses stats (syn1 = 0), % de vie au personnage',
                   (cs2.aura_stats[demon_blood][(329, None)], cs2.stat(76)), (0, 6))
        ctx.expect('mercenaire mort : aucune aura',
                   CharacterStats(dict(ch, mercenary=dict(merc, dead=True)), data).aura_levels, {})
    finally:
        mxl_char_stats.all_stats = real

@case('Personnage', "jeu d'armes : le jeu actif est toujours enregistré en 4 et 5, l'onglet actif dans l'en-tête")
def weapon_swap(ctx):
    """Nekratall au 30/09 : armes ajoutées dans l'onglet II, onglet II actif ; le jeu les a rangées en 4 et 5 (Grim Wand,
    Preserved Head) et a déplacé celles de l'onglet I en 11 et 12 (Yew Wand, Gargoyle Head)."""
    from mxl_containers import weapon_slots
    from mxl_char_stats import CharacterStats
    data = ctx.data
    ch = load_character(os.path.join(FIXTURES, 'weapon_swap', 'Nekratall.d2s'), data)
    ctx.expect('onglet actif', ch['weapon_switch'], 1)
    worn = {it['equipped']: it['code'].strip() for it in placed(ch['items'], 'equipped')}
    tab = lambda n: {slot: worn.get(stored) for slot, stored in weapon_slots(ch['weapon_switch'], n).items()}
    ctx.expect('onglet I', tab(1), {4: 'l11', 5: 'w28'})
    ctx.expect('onglet II', tab(2), {4: 'l13', 5: 'w25'})
    ctx.expect('onglet I sans échange', weapon_slots(0, 1), {4: 4, 5: 5})
    active = {it['code'].strip() for it in CharacterStats(ch, data).items if it['equipped'] in (4, 5, 11, 12)}
    ctx.expect("armes comptées dans les statistiques (jeu actif)", active, {'l13', 'w25'})
    ctx.expect('ancien fichier : onglet I', load_character(CHARACTER, data)['weapon_switch'], 0)


# Pala (personnage de test transmis le 07/10) : bottes honorifiques « Soul Track » portées (qualité 9)
HONORIFIC = os.path.join(FIXTURES, 'honorific', 'Pala.d2s')


@case('Personnage', 'objet honorifique (qualité 9, Soul Track) : nom en deux mots, suite lue juste, comme en jeu')
def honorific(ctx):
    data = ctx.data
    boots = next(i for i in load_character(HONORIFIC, data)['items'] if i['code'] == '867 ')
    # lignes sans la ventilation de l'éditeur (« (B:10 + O:130) », absente du jeu)
    lines = [re.sub(r' \([A-Z]+:.*\)$', '', ''.join(t for _, t in line)) for line in item_tooltip(boots, data, None)]
    ctx.expect('qualité, défense, sockets', (boots['quality'], boots['defense'], boots['sockets']), ('honorific', 294, 4))
    ctx.expect('nom (vert, comme en jeu)', [(line[0][0], ''.join(t for _, t in line)) for line in item_tooltip(boots, data, None)[:2]],
               [('2', 'Soul Track'), ('2', 'Boots (4)')])
    # lignes de la capture en jeu (ordre à part : voir « Minimum Damage » dans la roadmap)
    game = ['Required Level: 149', 'Required Strength: 525', 'Orb Effects Applied to this Item are Doubled',
            '+10% Attack Speed', '+20% Bonus to Attack Rating', '+6 to Minimum Damage', '+140 to Strength',
            '+160 to Dexterity', '+4% to Dexterity', '+50 to Vitality', '+100 to Energy',
            '+100 Life Regenerated per Second', 'Requirements +50%', '+128 Required Level', 'Socketed (4)']
    ctx.expect('lignes de la capture en jeu', [g for g in game if g not in lines], [])
    ctx.check(any(x.startswith('+30% Movement Speed') for x in lines) and any(x.startswith('+56% to Vitality') for x in lines),
              f'Movement Speed / Vitality : {lines}')


@case('Personnage', 'Mystic Orbs appliqués (stat 290) : Soul Track, verrous des Imperfect Spheres, paire Apple of Discord')
def mystic_orbs(ctx):
    from mxl_orbs import orb_lines, applied_orbs
    data = ctx.data
    boots = next(i for i in load_character(HONORIFIC, data)['items'] if i['code'] == '867 ')
    title, lines = orb_lines(boots, data)
    ctx.expect('Soul Track', (title, [(rows, text) for rows, text, _ in lines]),
               ('Mystic Orbs applied (effects doubled) — 18 orbs',
                [((58,), '5 × Idol of Stars'), ((74,), '5 × Periapt of Life'), ((3,), '5 × Vitality Orb'),
                 ((1,), '2 × Dex Orb'), ((53,), "1 × Marksman's Eye")]))
    ctx.expect('positions des noms (survol)', [[text[a:b] for _, a, b in spans] for _, text, spans in lines],
               [['Idol of Stars'], ['Periapt of Life'], ['Vitality Orb'], ['Dex Orb'], ["Marksman's Eye"]])
    counters = lambda c: {'stats': [{'id': 290, 'param': p, 'value': v} for p, v in c.items()]}
    # une Imperfect Sphere ajoute 2 au compteur des deux autres (verrou) : une seule appliquée
    ctx.expect('sphère et verrous', applied_orbs(counters({94: 1, 95: 2, 96: 2}), data), ([((94,), 1)], 1))
    ctx.expect('verrous seuls comptés à part', applied_orbs(counters({0: 3, 94: 2, 95: 1, 96: 2}), data),
               ([((0,), 3), ((95,), 1)], 1))
    # Apple of Discord et sa version 2 se verrouillent l'une l'autre de 1 : indiscernables, données ensemble
    _, pair = orb_lines(counters({57: 1, 99: 1}), data)
    ctx.expect('paire Apple of Discord', [(rows, text, [text[a:b] for _, a, b in spans]) for rows, text, spans in pair],
               [((57, 99), '1 × Apple of Discord / Apple of Discord 2', ['Apple of Discord', 'Apple of Discord 2'])])
    ctx.expect('Imperfect Spheres : variante (même nom d\'objet)', orb_lines(counters({94: 1, 95: 2, 96: 2}), data)[1][0][1],
               '1 × Imperfect Sphere (no cold)')
    ctx.expect('objet sans orbe', orb_lines({'stats': []}, data), None)
    # multiplicateur de l'objet (stat 289) : absent = orbes posés une fois, 4 = Natalya's Deception
    ctx.expect('objet ordinaire', orb_lines(counters({3: 2, 18: 1}), data)[0], 'Mystic Orbs applied \u2014 3 orbs')
    quad = counters({3: 1})
    quad['stats'].append({'id': 289, 'param': None, 'value': 4})
    # compteurs anormaux (fichier abîmé) : groupe verrouillé donné ensemble, sans gel (audit du 09/10)
    import time
    start = time.perf_counter()
    found = applied_orbs(counters({94: 500, 95: 500, 96: 500}), data)
    ctx.expect('compteurs anormaux', (found, time.perf_counter() - start < 1), (([((94, 95, 96), 500)], 1), True))
    ctx.expect('quadruplé', orb_lines(quad, data)[0],'Mystic Orbs applied (effects quadrupled) \u2014 1 orbs')


@case('Personnage', 'Mystic Orb au survol : comme son infobulle en jeu (Crystal of Tears), wiki officiel (orbes uniques)')
def mystic_orb_tooltip(ctx):
    from mxl_orbs import orb_tooltip, orb_icon, orb_name, orb_item, NAMED_ROWS
    data = ctx.data
    text = lambda k: [''.join(t for _, t in line) for line in orb_tooltip(k, data)]
    # capture en jeu de Crystal of Tears (08/10) : noms orange, effets bleus
    # « Right-Click to Apply » retiré, restriction ajoutée (capture chez un vendeur : « (Armor Only) », 08/10)
    ctx.expect('Crystal of Tears', text(72), ['Crystal of Tears', 'Mystic Orb', '(Armor Only)', 'Adds 3-6 Damage',
                                             '+10 Required Level', 'Limit per item: 2', '(current orb values)'])
    ctx.expect('couleurs', [line[0][0] for line in orb_tooltip(72, data)[:5]], ['o', 'o', '5', '3', '3'])
    ctx.expect('capture chez le vendeur (Vitality)', text(3)[:5],
               ['Mystic Orb', '(Armor Only)', '+5 to Vitality', '+4 Required Level', 'Limit per item: 5'])
    ctx.expect('restrictions', [text(k)[1 if k < 48 else 2] for k in (29, 48, 53, 93, 100)],
               ['(Weapon Only)', '(Ring, Amulet or Quiver Only)', '(Any Equippable Item)', '(Body Armor Only)',
                '(Shield Only)'])
    ctx.check('Right-Click to Apply' not in sum((text(k) for k in range(len(data.mystic_orbs))), []),
              'Right-Click to Apply encore affiché')
    # wiki « Unique Mystic Orbs » : niveau requis et limite
    ctx.expect('niveau requis et limite (wiki)',
               [(text(k)[-3], text(k)[-2]) for k in (94, 57, 93, 62, 78)],
               [('+9 Required Level', 'Limit per item: 1'), ('+12 Required Level', 'Limit per item: 2'),
                ('+15 Required Level', 'Limit per item: 1'), ('+20 Required Level', 'Limit per item: 1'),
                ('+10 Required Level', 'Limit per item: 1')])
    ctx.check('+10% Enhanced Damage' in text(63), f"Larzuk's Round Shot : {text(63)}")
    ctx.expect('Soulforged', text(79)[:4], ['Soulforged Mystic Orb', 'Rare items only', '(Armor Only)', 'Physical Resist +1%'])
    ctx.check('(helm only)' in text(62) and len([x for x in text(62) if 'Only)' in x]) == 0, f'Solitude : {text(62)}')
    # noms d'objet (wiki) : Hand of Yaerius (ligne « Relic of Yaerius »), Lodestone, Explorer's Globe
    ctx.expect('noms des objets', [orb_name(k, data) for k in (51, 75, 76)], ['Hand of Yaerius', 'Lodestone', "Explorer's Globe"])
    ctx.check(all(orb_item(k, data) for k in NAMED_ROWS), 'orbe nommé sans objet')
    ctx.expect('icônes', [orb_icon(k, data) for k in (63, 3, 48, 96)], ['orb_weap', 'orb_armo', 'orb_misc', 'orb_misc_imperfect'])


@case('Personnage', 'ventilation O: des Mystic Orbs ; B impossible en rouge (valeurs des orbes changées), Requirements à part')
def mystic_orb_breakdown(ctx):
    import copy
    from mxl_orbs import orb_mismatch
    data = ctx.data
    boots = next(i for i in load_character(HONORIFIC, data)['items'] if i['code'] == '867 ')
    lines = {''.join(t for _, t in l).split(' (')[0]: l for l in item_tooltip(boots, data, None)}
    text = lambda k: ''.join(t for _, t in lines[k])
    red = lambda k: [t for c, t in lines[k] if c == '1']
    ctx.expect('lignes ventilées', [text(k) for k in ('+10% Attack Speed', '+140 to Strength', '+160 to Dexterity',
                                                      '+50 to Vitality', '+56% to Vitality',
                                                      '+100 Life Regenerated per Second')],
               ['+10% Attack Speed (O:10%)', '+140 to Strength (B:10 + O:130)', '+160 to Dexterity (B:10 + O:130 + O:20)',
                '+50 to Vitality (O:50)', '+56% to Vitality (O:40% + G:4% + G:4% + G:4% + G:4%)',
                '+100 Life Regenerated per Second (B:-300 + O:400)'])
    ctx.expect('B en rouge (objet honorifique : B attendu 0)',
               [red(k) for k in ('+140 to Strength', '+160 to Dexterity', '+100 Life Regenerated per Second',
                                 '+50 to Vitality')], [['10'], ['10'], ['-300'], []])
    ctx.expect('sans orbe : pas de ventilation (Requirements des bases honorifiques)', text('Requirements +50%'),
               'Requirements +50%')
    ctx.check(orb_mismatch(boots, data), 'écart non détecté')
    # mêmes bottes aux valeurs actuelles des orbes : tout s'explique, rien en rouge
    fixed = copy.deepcopy(boots)
    for st in fixed['stats']:
        st['value'] = {0: 130, 2: 150, 74: 4000}.get(st['id'], st['value'])
    ctx.check(not orb_mismatch(fixed, data), 'écart signalé à tort')
    tip = {''.join(t for _, t in l) for l in item_tooltip(fixed, data, None)}
    ctx.check('+130 to Strength (O:130)' in tip and '+150 to Dexterity (O:130 + O:20)' in tip, f'valeurs actuelles : {tip}')
