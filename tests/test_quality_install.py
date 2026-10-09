"""Tests : qualité pondérée et priorités ; contrôle, réparation et version d'extraction de data/, icônes propres."""
import json, os, shutil
from common import case, ROOT, STASH2, GAME_DIR
from mxl_data import Data
from mxl_save import parse_stash, character_for
from mxl_edit import edit_groups, item_quality, global_priorities
from mxl_install import manifest, check_data, data_state, INSTALL_FILE, EXTRACT_VERSION, is_game_dir, fingerprint, repair_data
from mxl_gfx import icon_name, icon_names, icon_layers


@case('Qualité', "qualité pondérée (Jared's Fragmentor : défaut, ED en High, ED en Low)")
def weighted_quality(ctx):
    """ED 57 dans 41-60, Max Damage 5 dans 4-6, Crushing Blow 3 dans 2-3, Life on Melee Attack 22 dans 21-30 :
    61,3 % par défaut ; ED en High (3 étoiles) -> 63,9 %, en Low (1 étoile) -> 58,1 % (ED au-dessus de la moyenne)."""
    data = ctx.data
    it = next(i for i in parse_stash(STASH2, data) if i['code'] == '108 ')
    groups = edit_groups(it, data, character_for(STASH2, data))
    ctx.expect('qualité', [round(item_quality(groups, p), 1) for p in ({}, {'stat:17': 3}, {'stat:17': 1})],
               [61.3, 63.9, 58.1])


@case('Qualité', 'deux « +x to <compétence> » (Auto Da Fe) : plage et élément propres à chaque compétence')
def two_skill_stats(ctx):
    """Stat 97 deux fois, params différents (Ignis Fatuus 470 : 1-2, Flamefront 523 : 3-4) : chaque ligne a sa plage
    (pas [4-6], somme des deux), chaque compétence un élément du panneau de qualité."""
    from mxl_tooltip import item_tooltip
    data = ctx.data
    stat = lambda sid, param, value, pos: dict(id=sid, param=param, value=value, pos=pos, bits=7, add=1)
    it = dict(code='8@8 ', quality='unique', set_unique_id=291, identified=True, _offset=0, ethereal=False,
              stats=[stat(97, 470, 2, 0), stat(97, 523, 3, 16)])
    lines = [''.join(t for _, t in line) for line in item_tooltip(it, data)]
    ctx.expect('lignes', [x for x in lines if ' to ' in x and '[' in x], ['+3 to Flamefront [3-4]', '+2 to Ignis Fatuus [1-2]'])
    fields = [f for g in edit_groups(it, data) for f in g['fields']]
    ctx.expect('éléments', [(f['lo'], f['hi'], f['value'], f['edit']['param']) for f in fields], [(1, 2, 2, 470), (3, 4, 3, 523)])
    # même règle pour toutes les stats à param : « +x to <classe> Skill Levels » (param = classe, valeur de la
    # propriété), Eternal Bone Pile : (1 to 2) par classe, pas la somme des 7 classes (7 to 14)
    from mxl_library import catalog
    from mxl_rules import stat_range
    e = next(e for e in catalog(data) if e['name'] == 'Eternal Bone Pile')
    bone = dict(code=e['code'], quality='unique', set_unique_id=e['row'],
                stats=[dict(id=83, param=cls, value=1) for cls in range(7)])
    ctx.expect('Skill Levels par classe', {stat_range(bone, 83, data, param=cls) for cls in range(7)}, {(1, 2)})


@case('Qualité', "sens des curseurs : de la moins bonne à la meilleure valeur (Requirements : -30 % meilleur que -21 %)")
def slider_direction(ctx):
    """Unique à « Requirements -(21 to 30)% » : curseur de -21 (moins bon, à gauche) à -30 (meilleur, à droite), qualité
    100 % à -30 ; pénétration « -(4 to 5)% to Enemy … Resistance » enregistrée en positif : 4 -> 5 ; malus Attack Speed
    -(5 to 1)% : -5 -> -1 (décision du 30/09)."""
    from mxl_library import catalog
    from mxl_rules import table_row, worst_best
    data = ctx.data
    e = next(e for e in catalog(data) if e['kind'] == 'unique' and any(
        m['prop'] and 91 in data.props[m['prop']] and m['min'] != m['max'] and max(m['min'], m['max']) < 0
        for m in table_row(e['key'], data).get('mods', [])))
    m = next(m for m in table_row(e['key'], data)['mods'] if 91 in data.props[m['prop']])
    best, worst = min(m['min'], m['max']), max(m['min'], m['max'])
    stat = dict(id=91, param=None, value=best, pos=0, bits=8, add=100)
    it = dict(code=e['code'], quality='unique', set_unique_id=e['row'], identified=True, _offset=0, ethereal=False,
              stats=[stat])
    f = next(f for g in edit_groups(it, data) for f in g['fields'] if f['edit']['stat'] == 91)
    ctx.expect('curseur Requirements', (f['lo'], f['hi'], round(item_quality(edit_groups(it, data)))), (worst, best, 100))
    ctx.expect('pénétration, malus', (worst_best(333, 4, 5, data), worst_best(93, -5, -1, data)), ((4, 5), (-5, -1)))


@case('Qualité', 'priorités : ancien format par personnage converti (fusion des personnages)')
def priorities_conversion(ctx):
    old = {'Nekratall': {'unique:375': {'stat:17': 3}}, 'Krom': {'unique:375': {'stat:210': 1}, 'superior:638': {'stat:96': 3}}}
    conv = global_priorities(old)
    ctx.expect('conversion', conv, {'unique:375': {'stat:17': 3, 'stat:210': 1}, 'superior:638': {'stat:96': 3}})
    ctx.expect('déjà converti', global_priorities(conv), conv)


def data_copy(ctx, extract_version=EXTRACT_VERSION, files=None):
    """Copie saine de data/ dans le dossier du cas, avec son install.json : (dossier, liste de référence)."""
    d = os.path.join(ctx.tmp, 'data')
    shutil.copytree(os.path.join(ROOT, 'data'), d, ignore=shutil.ignore_patterns(INSTALL_FILE))
    ref = manifest(d)
    fp = dict(version='test', files={}, manifest=ref) if files is None else dict(files, manifest=ref)
    if extract_version is not None:
        fp['extract_version'] = extract_version
    with open(os.path.join(d, INSTALL_FILE), 'w', encoding='utf-8') as f:
        json.dump(fp, f)
    return d, ref


@case('Installation', "version d'extraction antérieure : reconstruction proposée")
def extract_version(ctx):
    d, _ = data_copy(ctx, extract_version=None)
    ctx.expect('extrait par une ancienne version', data_state(d, ctx.tmp), 'unknown')
    d2 = os.path.join(ctx.tmp, 'data')
    with open(os.path.join(d2, INSTALL_FILE), encoding='utf-8') as f:
        fp = json.load(f)
    fp['extract_version'] = EXTRACT_VERSION
    with open(os.path.join(d2, INSTALL_FILE), 'w', encoding='utf-8') as f:
        json.dump(fp, f)
    ctx.expect('version actuelle', data_state(d2, ctx.tmp), 'ok')


@case('Installation', "icône propre d'un unique : extraite, affichée en priorité, sinon icône de base")
def own_icons(ctx):
    """Table @0x5A, ✅ Griswold's Heart ligne 69 « invxtuu » ; pas encore extraite (data/ d'avant) : icône de base."""
    data = ctx.data
    gris = dict(code=data.uniques[69]['code'], quality='unique', set_unique_id=69)
    ctx.expect('icône propre', (icon_name(gris, data), 'invxtuu' in icon_names(data), icon_name(dict(code='108 '), data)),
               ('invxtuu', True, data.base('108 ').inv_file))
    only_base = os.path.join(ctx.tmp, 'only_base')
    os.makedirs(only_base)
    shutil.copy2(os.path.join(ROOT, 'data', 'items', data.base(gris['code']).inv_file + '.png'), only_base)
    ctx.check(icon_layers(gris, data, '#000000', only_base) is not None, 'icône propre absente : pas d\'icône de base')


@case('Installation', 'contrôle de data/ : intact, octet modifié (complet seulement), fichiers supprimés')
def data_check(ctx):
    d, _ = data_copy(ctx)
    icon = next(n for n in sorted(os.listdir(os.path.join(d, 'items'))) if n.endswith('.png'))
    ctx.expect('intact, rapide', check_data(d), [])
    ctx.expect('intact, complet', check_data(d, full=True), [])
    with open(os.path.join(d, 'items', icon), 'r+b') as f:   # octet modifié, même taille
        b = f.read(1)
        f.seek(0)
        f.write(bytes([b[0] ^ 1]))
    ctx.expect('octet modifié, rapide', check_data(d), [])
    ctx.expect('octet modifié, complet', check_data(d, full=True), [f'items/{icon}'])
    os.remove(os.path.join(d, 'uniqueitems.bin'))
    os.remove(os.path.join(d, 'items', icon))
    ctx.expect('fichiers supprimés, rapide', check_data(d), ['items/' + icon, 'uniqueitems.bin'])
    ctx.expect('état', data_state(d, ctx.tmp), 'damaged')


@case('Installation', 'réparation de data/ fichier par fichier depuis le jeu (vérifiée par md5)')
def data_repair(ctx):
    if not is_game_dir(GAME_DIR):
        ctx.notes.append(f'non testée : jeu introuvable dans {GAME_DIR}')
        return
    d, _ = data_copy(ctx, files=fingerprint(GAME_DIR))   # même installation que le jeu
    icon = next(n for n in sorted(os.listdir(os.path.join(d, 'items'))) if n.endswith('.png'))
    os.remove(os.path.join(d, 'uniqueitems.bin'))
    os.remove(os.path.join(d, 'items', icon))
    bad = check_data(d, full=True)
    ctx.expect('réparation', repair_data(GAME_DIR, d, bad), 2)
    ctx.expect('après réparation, complet', check_data(d, full=True), [])
    ctx.check(Data(d).uniques, 'tables illisibles après réparation')
