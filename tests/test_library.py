"""Tests : bibliothèque — catalogue, infobulles du catalogue (alignées sur la documentation du jeu), reconnaissance
des objets, découvertes, protections du fichier library.json."""
import os
from common import case, STASH2
from mxl_save import parse_stash
from mxl_library import catalog, entry_key, disabled, quest_item, Library, LibraryError, plan_transfer, apply_transfer
from mxl_catalog_tooltip import catalog_tooltip

_catalog = {}


def cat(data):
    """Catalogue calculé une fois pour tous les cas."""
    if 'entries' not in _catalog:
        _catalog['entries'] = catalog(data)
    return _catalog['entries']


def entry(data, key=None, name=None):
    return next(e for e in cat(data) if e['key'] == key or e['name'] == name)


def texts(lines):
    return [''.join(t for _, t in line) for line in lines]


@case('Bibliothèque', 'catalogue : 1 720 uniques (90 reliques vides et 9 objets de quête écartés), 198 objets de set')
def catalog_counts(ctx):
    ctx.expect('entrées', {k: sum(1 for e in cat(ctx.data) if e['kind'] == k) for k in ('unique', 'set')},
               {'unique': 1720, 'set': 198})


@case('Bibliothèque', "objets de quête (Cannot be Disenchanted, Akara's Robe de la quête) : ni au catalogue, ni reconnus")
def quest_rows(ctx):
    data = ctx.data
    off = [f'unique:{k}' for k, r in enumerate(data.uniques) if r['code'] in data.bases and quest_item(r, data)]
    ctx.expect('lignes', off, [f'unique:{n}' for n in (0, 1, 2, 3, 4, 5, 69, 70, 71)])
    ctx.check(not any(e['key'] in off for e in cat(data)), 'objet de quête au catalogue')
    ctx.expect('reconnaissance', [entry_key(dict(code=data.uniques[n]['code'], quality='unique', set_unique_id=n), data)
                                  for n in (0, 69, 71)], [None] * 3)
    ctx.expect("aucune Akara's Robe au catalogue", [e['key'] for e in cat(data) if "Akara's Robe" in e['name']], [])


@case('Bibliothèque', "lignes désactivées (set 25 « Orphan's Call ») : ni au catalogue, ni reconnues")
def disabled_rows(ctx):
    data = ctx.data
    off = [f'set:{k}' for k, r in enumerate(data.set_items) if r['code'] in data.bases and disabled(r)]
    ctx.expect('lignes', off, ['set:315', 'set:316', 'set:317', 'set:318', 'set:319'])
    ctx.check(not any(e['key'] in off for e in cat(data)), 'ligne désactivée au catalogue')
    ctx.expect('reconnaissance', entry_key(dict(code=data.set_items[316]['code'], quality='set', set_unique_id=316), data), None)


@case('Bibliothèque', "infobulle du catalogue : Jared's Fragmentor (unique)")
def tooltip_jared(ctx):
    ctx.expect('lignes', texts(catalog_tooltip(entry(ctx.data, 'unique:375'), ctx.data)), [
        "Jared's Fragmentor", 'Claymore (1)', 'One-Hand Damage: (7 - 8) to (12 - 15)', 'Two-Hand Damage: (9 - 11) to (15 - 18)',
        'Required Level: 2', 'Required Strength: 41', 'Item Level: 10', 'Strength Damage Bonus: (0.16 per Strength)%',
        '5% Chance to cast level 4 Spike Nova on Melee Attack', '+(41 to 60)% Enhanced Damage',
        '+(2 to 3)% Chance of Crushing Blow', '+(4 to 6) to Maximum Damage', '+(21 to 30) Life on Melee Attack',
        'Socketed (2)'])


@case('Bibliothèque', "infobulle du catalogue : Celestia's Charge (objet de set)")
def tooltip_set(ctx):
    ctx.expect('lignes', texts(catalog_tooltip(entry(ctx.data, 'set:127'), ctx.data)), [
        "Celestia's Charge", 'Light Plated Boots (Sacred)', 'Defense: (1881 - 2116) to (2083 - 2343)', 'Required Level: 90',
        'Required Strength: 468', 'Item Level: 1', '+(20 to 50)% Movement Speed', '2% Chance to cast level 6 Celerity on Kill',
        '+20% Hit Recovery', '+(140 to 170)% Enhanced Defense', '+(31 to 50) to Strength', '+(11 to 15)% to Dexterity',
        '+(11 to 15)% Bonus to Defense', 'Requirements -25%', 'Socketed (4)'])


# infobulles alignées sur la documentation du jeu : (couleur du dernier segment, texte) de chaque ligne
DOC_TOOLTIPS = {
    # Crown : défense avec défense plate, exigence réduite en bleu, « +x to <compétence> », réanimation sur une plage
    "Aidan's Lament": [
        ('4', "Aidan's Lament"), ('4', 'Crown (Sacred)'), ('3', 'Defense: (3753 - 4493) to (5603 - 6422)'), ('0', 'Required Level: 100'),
        ('3', 'Required Strength: 337'), ('0', 'Item Level: 105'), ('3', '+(90 to 120)% Damage to Demons'),
        ('3', '+(90 to 120)% Damage to Undead'), ('3', '+(10 to 19) to Charged Strike'), ('3', '+(120 to 170)% Enhanced Defense'),
        ('3', '+(500 to 2000) Defense'), ('3', 'Maximum Elemental Resists +1%'), ('3', 'Physical Resist +(4 to 8)%'),
        ('3', '5% Reanimate as: Random Monster'), ('3', 'Requirements -50%'), ('3', 'Socketed (4)')],
    # texte du jeu n° param en orange, texte seul en vert
    'Undead Crown': [
        ('4', 'Undead Crown'), ('4', 'Crown (Sacred)'), ('3', 'Defense: 4437 to 4914'), ('0', 'Required Level: 110'),
        ('0', 'Required Strength: 675'), ('0', 'Item Level: 120'), ('8', '10% of Minion Damage Increases Added as Deadly Strike'),
        ('8', '65% of Minion Life Increases Added as Bonus to Defense'), ('8', 'Deal No Crushing Blows'),
        (':', 'Orb Effects Applied to this Item are Doubled'), ('3', '+50% Attack Speed'), ('3', '+200% Enhanced Defense'),
        ('3', 'Socketed (4)')],
    # Raptor Scythe : éthéré, classe en rouge, auto-affixe de la base, couleur qui persiste
    'Iron Shard': [
        ('4', 'Iron Shard'), ('4', 'Raptor Scythe (Sacred)'), ('3', 'Two-Hand Damage: (297 - 360) to (335 - 390)'), ('1', '(Necromancer Only)'),
        ('0', 'Required Level: 100'), ('3', 'Required Strength: 1439'), ('0', 'Item Level: 105'),
        ('0', 'Dexterity Damage Bonus: (0.14 per Dexterity)%'), ('0', 'Strength Damage Bonus: (0.14 per Strength)%'),
        ('5', 'Ethereal'), ('8', 'Mega Impact'), ('8', 'When Iron Golem Consumes This Item:'), ('5', '+20% Deadly Strike'),
        ('5', '+20% Crushing Blow'), ('5', '+160% to Iron Golem Damage'), ('3', '10% Chance to cast level 10 Spike Rush on Melee Attack'),
        ('3', 'Adds (105 to 130)-(135 to 150) Damage'), ('3', '+(101 to 150)% Bonus to Attack Rating'),
        ('3', '+(100 to 140)% Enhanced Damage'), ('3', '+(1001 to 5000) Defense'), ('3', 'Maximum Life -20%'),
        ('3', '5% Reanimate as: Random Monster'), ('3', 'Requirements +250%'), ('3', 'Socketed (6)')],
    # Bonesplitter : stat proportionnelle à la Force (sans personnage : par point)
    "Reaper's Hand": [
        ('4', "Reaper's Hand"), ('4', 'Bonesplitter (Sacred)'), ('3', 'Two-Hand Damage: (258 - 396) to (353 - 442)'), ('1', '(Necromancer Only)'),
        ('0', 'Required Level: 100'), ('0', 'Required Strength: 512'), ('0', 'Item Level: 105'),
        ('0', 'Dexterity Damage Bonus: (0.14 per Dexterity)%'), ('0', 'Strength Damage Bonus: (0.14 per Strength)%'),
        ('8', 'Mega Impact'), ('3', '20% Chance to cast level 1 Raid on Melee Attack'),
        ('3', 'Additional Strength Damage Bonus: 0.046875%'), ('3', 'Adds (70 to 150)-(160 to 190) Damage'),
        ('3', '+(150 to 250)% Bonus to Attack Rating'), ('3', '+(5 to 10)% Life stolen per Hit'),
        ('3', '+(130 to 200)% Enhanced Damage'), ('3', 'Freezes Target +1'), ('3', 'Socketed (6)')],
    # Marrow Staff : classe de l'objet, plage qui change de signe
    "Karybdus' Descent": [
        ('4', "Karybdus' Descent"), ('4', 'Marrow Staff (Sacred)'), ('0', 'Two-Hand Damage: 45 to 49'), ('1', '(Necromancer Only)'),
        ('0', 'Required Level: 100'), ('0', 'Required Strength: 275'), ('0', 'Item Level: 105'),
        ('0', 'Strength Damage Bonus: (0.06 per Strength)%'), ('8', 'Bane: +100% Duration'), ('8', 'Enhances Death Ripple'),
        ('3', '+(8 to 11) to Necromancer Skill Levels'), ('3', '2% Chance to cast level 50 Blood Skeleton on Death Blow'),
        ('3', '-25% Cast Speed'), ('3', 'Maximum Elemental Resists (-1 to 1)%'), ('3', 'Physical Resist +(5 to 10)%'),
        ('3', 'Socketed (6)')],
    # temps de recharge en secondes, texte de la stat 377 en bleu
    'The Worshipper': [
        ('4', 'The Worshipper'), ('4', 'Marrow Staff (Sacred)'), ('0', 'Two-Hand Damage: 45 to 49'), ('1', '(Necromancer Only)'),
        ('0', 'Required Level: 120'), ('0', 'Required Strength: 275'), ('0', 'Item Level: 130'),
        ('0', 'Strength Damage Bonus: (0.06 per Strength)%'), ('8', '+1 Extra Totems'),
        ('3', '+(8 to 11) to Necromancer Skill Levels'), ('3', 'Bend the Shadows Cooldown Reduced by 1 seconds'),
        ('3', '-50% to Enemy Fire Resistance'), ('3', '-50% to Enemy Lightning Resistance'), ('3', '-50% to Enemy Cold Resistance'),
        ('3', '+(501 to 1000) to Life'), ('3', '+(251 to 500) to Mana'), ('3', '+(51 to 100)% Magic Find'),
        ('3', 'Slain Monsters Rest in Peace'), ('3', 'Socketed (6)')],
    # Kriss : couleurs du texte n° param, compétence sans nom absente
    'Black Razor': [
        ('4', 'Black Razor'), ('4', 'Kriss (Sacred)'), ('0', 'One-Hand Damage: 39 to 40'), ('0', 'Required Level: 120'),
        ('0', 'Required Dexterity: 454'), ('0', 'Item Level: 120'), ('0', 'Dexterity Damage Bonus: (0.11 per Dexterity)%'),
        ('8', 'Cast a random Deadly Curse on attack'), ('1', 'It also applies to you'), ('3', '-200 Life on Melee Attack'),
        ('3', "Ignore Target's Defense"), ('3', '+666 to Life'), ('3', 'Maximum Elemental Resists +(1 to 2)%'),
        ('3', 'Curse Length Reduction -50%'), ('3', 'Socketed (3)')],
    # Einherjar Helm : deux « +x to <compétence> » (même stat 97, compétences différentes), texte du jeu en orange
    # puis en gris (« + » gardé sur les stats où la documentation l'omet)
    'Jeweled Crown': [
        ('4', 'Jeweled Crown'), ('4', 'Einherjar Helm (Sacred)'), ('3', 'Defense: (1762 - 2447) to (1895 - 2632)'),
        ('1', '(Amazon Only)'), ('0', 'Required Level: 100'), ('3', 'Required Dexterity: 267'), ('0', 'Item Level: 105'),
        ('8', '1% of total Vitality added as Energy for each Jewel in your gear'),
        ('5', '(Doubled for Jewels socketed in the Crown itself)'), ('3', '+2 to Amazon Skill Levels'),
        ('3', '+(5 to 13) to Psicrown'), ('3', '+(5 to 21) to Psionic Storm'), ('3', '+(80 to 150)% Enhanced Defense'),
        ('3', 'Regenerate Mana +(30 to 50)%'), ('3', '+(5 to 8)% to Experience Gained'), ('3', 'Requirements -50%'),
        ('3', 'Socketed (4)')],
    # Spangenhelm : dégâts plats d'un objet qui n'est pas une arme à deux mains = version une main, en tête
    'Helepolis': [
        ('4', 'Helepolis'), ('4', 'Spangenhelm (Sacred)'), ('3', 'Defense: (2894 - 3192) to (3206 - 3537)'),
        ('1', '(Amazon Only)'), ('0', 'Required Level: 100'), ('0', 'Required Strength: 675'), ('0', 'Item Level: 105'),
        ('3', '+38 to Maximum Damage'), ('3', '+(14 to 24) to Guard Tower'), ('3', '+10% Chance of Crushing Blow'),
        ('3', '+(172 to 200)% Enhanced Defense'), ('3', '+(21 to 30)% to Strength'), ('3', 'Physical Resist +20%'),
        ('3', '+(31 to 50)% Bonus to Defense'), ('3', 'Socketed (4)')],
    # épées (documentation du jeu) : dégâts plats aussi en deux mains, classe des Skill Levels lue dans la propriété (Barbare)
    'Durandal the Blazing Sword': [
        ('4', 'Durandal the Blazing Sword'),
        ('4', 'Claymore (Sacred)'),
        ('3', 'One-Hand Damage: (268 - 280) to (301 - 313)'),
        ('3', 'Two-Hand Damage: (323 - 340) to (355 - 373)'),
        ('0', 'Required Level: 100'),
        ('0', 'Required Strength: 450'),
        ('0', 'Item Level: 105'),
        ('0', 'Strength Damage Bonus: (0.16 per Strength)%'),
        ('3', '+(2 to 3) to Barbarian Skill Levels'),
        ('3', '15% Chance to cast level 13 Shockwave on Melee Attack'),
        ('3', '+25% Attack Speed'),
        ('3', 'Adds 160-190 Damage'),
        ('3', '+(100 to 150)% Bonus to Attack Rating'),
        ('3', '+(172 to 200)% Enhanced Damage'),
        ('3', '+100 to Strength'),
        ('3', '-40% Mana Cost of Skills'),
        ('3', '+(50 to 100)% Bonus to Defense'),
        ('3', 'Socketed (4)'),
    ],
    # épées (documentation du jeu) : auto-affixe du second type de base (Crystal Sword), « +x to <compétence> (<classe> Only) », ordre à stat égale
    'Shadowsabre': [
        ('4', 'Shadowsabre'),
        ('4', 'Crystal Sword (Sacred)'),
        ('0', 'Required Level: 100'),
        ('0', 'Required Dexterity: 510'),
        ('0', 'Item Level: 105'),
        ('0', 'Innate Cold Damage: (49.0% of Dexterity)'),
        ('8', 'Crucify: total number of projectiles increased by 25%'),
        ('3', '+50% Attack Speed'),
        ('3', 'Adds 160-250 Cold Damage'),
        ('3', '-20% to Enemy Elemental Resistances'),
        ('3', '+15 to Way of the Raven (Assassin Only)'),
        ('3', '+15 to Way of the Gryphon (Assassin Only)'),
        ('3', '+15 to Way of the Phoenix (Assassin Only)'),
        ('3', '+(15 to 25) to Crucify (Assassin Only)'),
        ('3', 'Fire Absorb +5%'),
        ('3', 'Lightning Absorb +5%'),
        ('3', 'Cold Absorb +5%'),
        ('3', '+4 Life on Striking'),
        ('3', 'Socketed (6)'),
    ],
    # épées (documentation du jeu) : classe imposée par la stat 463, réanimation (param = monstre, valeur = chance)
    'Shadowfang': [
        ('4', 'Shadowfang'),
        ('4', 'Bastard Sword (Sacred)'),
        ('0', 'One-Hand Damage: 44 to 47'),
        ('0', 'Two-Hand Damage: 70 to 72'),
        ('1', '(Necromancer Only)'),
        ('0', 'Required Level: 100'),
        ('0', 'Required Strength: 535'),
        ('0', 'Item Level: 120'),
        ('0', 'Strength Damage Bonus: (0.16 per Strength)%'),
        ('8', 'Pestilence: duration reduced by 50%'),
        ('8', 'Pestilence: regenerates 4% of Maximum Life per Second'),
        ('3', '50% Chance to cast level 50 Veil King Plague Grasp on Melee Attack'),
        ('3', '+200% Bonus to Attack Rating'),
        ('3', '+100% to Poison Spell Damage'),
        ('3', '+60 to Stormlord'),
        ('3', 'Slow Target +25%'),
        ('3', '+200 Life after each Kill'),
        ('3', '2% Reanimate as: Veil Terror'),
        ('3', 'Socketed (4)'),
    ],
    # épées (documentation du jeu) : chances de lancer de même stat : ordre inverse des affixes
    'Astral Blade': [
        ('4', 'Astral Blade'),
        ('4', 'Long Sword (Sacred)'),
        ('0', 'One-Hand Damage: 45 to 48'),
        ('0', 'Required Level: 100'),
        ('0', 'Required Strength: 540'),
        ('0', 'Item Level: 120'),
        ('0', 'Strength Damage Bonus: (0.11 per Strength)%'),
        ('3', '+1 Hunting Banshee/Ember Spirit Projectile'),   # descfunc 31, valeur 4 -> bleu (D2Sigma.dll 0x10077720)
        ('3', '8% Chance to cast level 13 Mythal on Melee Attack'),
        ('3', '15% Chance to cast level 60 Ember Spirit on Melee Attack'),
        ('3', '15% Chance to cast level 60 Hunting Banshee on Melee Attack'),
        ('3', '+(100 to 125) Spell Focus'),
        ('3', '+100% Attack Speed'),
        ('3', '+(20 to 25)% to Fire Spell Damage'),
        ('3', '-(15 to 20)% to Enemy Fire Resistance'),
        ('3', '+(20 to 25)% to Cold Spell Damage'),
        ('3', '-(15 to 20)% to Enemy Cold Resistance'),
        ('3', 'Socketed (6)'),
    ],
    # épées (documentation du jeu) : Enhanced Damage entre la pénétration foudre (135) et froid (133)
    "Kraken's Cutlass": [
        ('4', "Kraken's Cutlass"),
        ('4', 'Scimitar (Sacred)'),
        ('3', 'One-Hand Damage: (103 - 185) to (186 - 228)'),
        ('0', 'Required Level: 100'),
        ('0', 'Required Strength: 421'),
        ('0', 'Item Level: 105'),
        ('0', 'Strength Damage Bonus: (0.11 per Strength)%'),
        ('8', 'Mana Pulse: +50% Duration'),
        ('3', '+75% Attack Speed'),
        ('3', 'Adds (10 to 80)-(90 to 120) Damage'),
        ('3', 'Adds 200-300 Cold Damage'),
        ('3', '+(140 to 170)% Enhanced Damage'),
        ('3', '-(20 to 25)% to Enemy Cold Resistance'),
        ('3', 'Slow Target +10%'),
        ('3', 'Maximum Cold Resist +1%'),
        ('3', '-20% Mana Cost of Skills'),
        ('3', 'Socketed (3)'),
    ],
    # épées (documentation du jeu) : stat par niveau sans personnage : valeur par niveau
    'The Xiphos': [
        ('4', 'The Xiphos'),
        ('4', 'Short Sword (Sacred)'),
        ('3', 'One-Hand Damage: (60 - 114) to (102 - 136)'),
        ('0', 'Required Level: 60'),
        ('0', 'Required Strength: 376'),
        ('0', 'Item Level: 105'),
        ('0', 'Strength Damage Bonus: (0.11 per Strength)%'),
        (':', 'Orb Effects Applied to this Item are Doubled'),
        ('3', '2% Chance to cast level 5 Shatterblade on Striking'),
        ('3', '+(5 to 50)% Attack Speed'),
        ('3', 'Adds (5 to 40)-(45 to 60) Damage'),
        ('3', '+(50 to 100)% Enhanced Damage'),
        ('3', '0.125% Chance of Crushing Blow (Based on Character Level)'),
        ('3', 'Physical Resist +5%'),
        ('3', 'Socketed (3)'),
    ],
    # épées (documentation du jeu) : classe imposée par la stat 463 (Druide)
    "Azgar's Crystal": [
        ('4', "Azgar's Crystal"),
        ('4', 'Giant Sword (Sacred)'),
        ('0', 'One-Hand Damage: 42 to 45'),
        ('0', 'Two-Hand Damage: 65 to 67'),
        ('1', '(Druid Only)'),
        ('0', 'Required Level: 100'),
        ('0', 'Required Strength: 480'),
        ('0', 'Item Level: 130'),
        ('0', 'Strength Damage Bonus: (0.16 per Strength)%'),
        ('8', 'While in Werewolf Form:'),
        ('8', 'Adds 50% of Current Mana as Cold Damage'),
        ('8', '10% Grit'),
        ('3', '+100% Attack Speed'),
        ('3', '+150% Bonus to Attack Rating'),
        ('3', '-100% to Enemy Cold Resistance'),
        ('3', 'Maximum Cold Resist +(2 to 5)%'),
        ('3', 'Cannot Be Frozen'),
        ('3', 'Socketed (4)'),
    ],
    # épées (documentation du jeu) : auto-affixe du second type ajouté aux dégâts de froid ; « on Kill » (stat 196) avant « on Striking » (198)
    'Cold Blood': [
        ('4', 'Cold Blood'),
        ('4', 'Crystal Sword (Sacred)'),
        ('0', 'Required Level: 100'),
        ('3', 'Required Dexterity: 1020'),
        ('0', 'Item Level: 120'),
        ('0', 'Innate Cold Damage: (49.0% of Dexterity)'),
        ('8', 'Regens 15% Life Over 5 Seconds Upon Taking Weapon Damage'),
        ('3', '100% Chance to cast level 50 Shatter the Flesh on Kill'),
        ('3', '1% Chance to cast level 63 Blizzard on Striking'),
        ('3', '+25% Attack Speed'),
        ('3', 'Adds (460 to 660)-(750 to 950) Cold Damage'),
        ('3', '+150% to Cold Spell Damage'),
        ('3', '-(20 to 30)% to Enemy Cold Resistance'),
        ('3', 'Maximum Mana -50%'),
        ('3', 'Requirements +100%'),
        ('3', 'Socketed (6)'),
    ],
    # dégâts innés du catalogue : élément, pourcentage et attribut, sans valeur calculée
    'Shard of Refraction': [
        ('4', 'Shard of Refraction'), ('4', 'Kriss (Sacred)'), ('0', 'One-Hand Damage: 39 to 40'), ('0', 'Required Level: 100'),
        ('0', 'Required Dexterity: 454'), ('0', 'Item Level: 130'), ('0', 'Dexterity Damage Bonus: (0.11 per Dexterity)%'),
        ('0', 'Innate Tri-Elemental Damage: (54.0% of Dexterity)'), ('3', '10% Chance to cast level 25 Trinity Arrow on Melee Attack'),
        ('3', 'Adds 500-700 Magic Damage'), ('3', '+1 to Tracking'), ('3', '+(80 to 100) to Dexterity'),
        ('3', '+7% Chance to Avoid Damage'), ('3', '+1 Life on Striking'), ('3', 'Socketed (3)')],
}

for _name, _want in DOC_TOOLTIPS.items():
    case('Bibliothèque', f'infobulle du catalogue (documentation du jeu) : {_name}')(
        lambda ctx, name=_name, want=_want: ctx.expect(
            'lignes', [(line[-1][0], ''.join(t for _, t in line)) for line in catalog_tooltip(entry(ctx.data, name=name), ctx.data)],
            want))


@case('Bibliothèque', 'infobulle du catalogue : couleurs des dégâts, de la défense et des exigences')
def tooltip_colors(ctx):
    """Valeurs de dégâts / défense en bleu avec Enhanced Damage / Defense ; exigence annulée absente."""
    summary = {}
    for name in ("Jared's Fragmentor", 'Gaze of the Dead', 'Black Masquerade'):
        lines = [line for line in catalog_tooltip(entry(ctx.data, name=name), ctx.data)
                 if line[0][1].startswith(('Defense', 'Two-Hand', 'Required Str'))]
        summary[name] = [(line[0][1].split(':')[0], line[-1][0]) for line in lines]
    ctx.expect('couleurs', summary, {"Jared's Fragmentor": [('Two-Hand Damage', '3'), ('Required Strength', '0')],
                                     'Gaze of the Dead': [('Defense', '0'), ('Required Strength', '0')],
                                     'Black Masquerade': [('Defense', '3')]})


@case('Bibliothèque', 'infobulle du catalogue : aucun texte mal formé (1 927 entrées)')
def tooltip_well_formed(ctx):
    bad = [e['key'] for e in cat(ctx.data) for line in catalog_tooltip(e, ctx.data)
           if any(m in ''.join(t for _, t in line) for m in ('%s', '%d', '%.', 'BUFFALO'))]
    ctx.expect('entrées mal formées', bad[:5], [])


@case('Bibliothèque', "reconnaissance : Jared's Fragmentor = unique:375, Horadric Malus de quête hors catalogue")
def recognition(ctx):
    items = parse_stash(STASH2, ctx.data)
    ctx.expect('clés', {i['code']: entry_key(i, ctx.data) for i in items if i['code'] in ('108 ', 'hdm ')},
               {'108 ': 'unique:375', 'hdm ': None})


@case('Bibliothèque', 'découvertes : enregistrées une seule fois (date, coffre, exemplaire), relues')
def found_recorded(ctx):
    items = parse_stash(STASH2, ctx.data)
    lp = os.path.join(ctx.tmp, 'library.json')
    lib = Library(lp)
    ctx.expect('1re ouverture', lib.record_found(items, ctx.data, 'test.stash'), ['unique:375'])
    ctx.expect('2e ouverture', lib.record_found(items, ctx.data, 'test.stash'), [])
    reread = Library(lp).found
    ctx.expect('fichier relu', (list(reread), reread['unique:375']['source'], len(reread['unique:375']['instances'])),
               (['unique:375'], 'test.stash', 1))


@case('Bibliothèque', 'protection : version précédente gardée dans library.json.bak')
def library_backup(ctx):
    lp = os.path.join(ctx.tmp, 'library.json')
    lib = Library(lp)
    lib.record_found(parse_stash(STASH2, ctx.data), ctx.data, 'test.stash')
    v1 = open(lp, 'rb').read()
    lib.save()
    ctx.check(open(lp + '.bak', 'rb').read() == v1, 'version précédente non copiée')


@case('Bibliothèque', 'protection : verrou (deuxième éditeur en lecture seule, verrou libéré)')
def library_lock(ctx):
    lp = os.path.join(ctx.tmp, 'library.json')
    Library(lp).save()
    a, b = Library(lp, lock=True), Library(lp, lock=True)
    ctx.expect('lecture seule', (bool(a.readonly), bool(b.readonly)), (False, True))
    a.release()
    c = Library(lp, lock=True)
    ctx.check(not c.readonly, 'verrou non libéré')
    c.release()


@case('Bibliothèque', 'protection : fichier illisible jamais écrasé (lecture seule, coffre intact)')
def library_broken(ctx):
    data = ctx.data
    lp = os.path.join(ctx.tmp, 'library.json')
    with open(lp, 'w', encoding='utf-8') as f:
        f.write('{"found": {"unique:375"')
    broken = open(lp, 'rb').read()
    bad = Library(lp)
    stash = ctx.copy(STASH2, 's.stash')
    before = open(stash, 'rb').read()
    items = parse_stash(stash, data)
    ctx.raises(LibraryError, 'enregistrement', lambda: bad.record_found(items, data, 'x'))
    ctx.raises(LibraryError, 'transfert', lambda: apply_transfer(stash, data, bad, plan_transfer(items, bad, data, {}),
                                                                  backup=False))
    ctx.check(bad.readonly and open(lp, 'rb').read() == broken and open(stash, 'rb').read() == before,
              'fichier illisible écrasé ou coffre modifié')


@case('Bibliothèque', "recherche : texte complet, mots exigés, « \"…\" », classe des compétences, bonus de set")
def full_text_search(ctx):
    """Recherche de l'écran Library (mxl_library_search) sur tout le catalogue : « magic find » = tous les mots,
    « "fire resist" » = expression exacte ; « paladin » trouve aussi un objet qui donne une compétence de Paladin sans
    le mot « Paladin » ; « trinity nova » (bonus du set complet Pantheon) trouve le set, pas ses pièces (leur propre
    texte ne le contient pas) ; « earth » trouve la pièce Earth par son nom."""
    from mxl_library_search import parse_query, build_index, search, line_matches, skill_classes
    data = ctx.data
    entries = {e['key']: e for e in cat(data)}
    index = build_index(entries, data)
    items = lambda q: search(index, parse_query(q))[0]
    sets = lambda q: search(index, parse_query(q))[1]
    ctx.expect('termes', parse_query('Paladin "Fire  Resist" magic'), ['fire  resist', 'paladin', 'magic'])
    mf, words = items('magic find'), items('find magic')
    ctx.check(mf == words and len(mf) > 100, f'mots dans le désordre : {len(mf)} / {len(words)}')
    ctx.check(items('"fire resist"') < items('fire resist'), 'expression exacte pas plus stricte que les mots séparés')
    visible = lambda k: '\n'.join(t for t, _ in index['items'][k]).lower()
    hidden = [k for k in items('paladin') if 'paladin' not in visible(k)]
    ctx.check(hidden, 'aucun objet trouvé par la classe cachée de ses compétences')
    classes = skill_classes(data)
    line = next(t for t, _ in index['items'][hidden[0]] if line_matches(t, ['paladin'], classes))
    ctx.check(' to ' in line, f'ligne surlignée pour la classe cachée : {line}')
    pantheon = index['set_of'][next(k for k, e in entries.items() if e['kind'] == 'set' and e['name'] == 'Earth')]
    ctx.expect('bonus du set Pantheon', (pantheon in sets('trinity nova'),
                                        {entries[k]['name'] for k in items('trinity nova') if entries[k]['kind'] == 'set'}),
               (True, set()))
    ctx.check(any(entries[k]['name'] == 'Earth' for k in items('earth')), 'pièce de set trouvée par son nom')
    ctx.check(items('paladin magic find') <= items('paladin') & mf, 'tous les mots exigés')
    # préparation par étapes (écran Library) : interrompue puis terminée = même texte que la préparation en une fois
    from mxl_library_search import index_steps
    partial = {}
    job = index_steps(entries, data, partial)
    for _ in range(300):
        next(job)
    ctx.check(0 < len(partial['items']) < len(entries), f"étapes : {len(partial['items'])} entrées après 300 étapes")
    for _ in job:
        pass
    ctx.check(partial == index, 'texte préparé par étapes différent du texte préparé en une fois')


@case('Bibliothèque', "compétences d'un objet : repérage (niveau donné), explication, icône")
def skill_references(ctx):
    """Auto Da Fe : « +(1 to 2) to Ignis Fatuus » et « +(3 to 4) to Flamefront » ; explication au format du jeu (nom,
    description, « Current Skill Level ») ; icône = image n° 92 / 282 du fichier commun (✅ captures en jeu) ; chance
    de lancer : niveau de la compétence lancée ; compétence sans nom (effet interne) : ignorée."""
    from mxl_catalog_tooltip import CatalogContext
    from mxl_skills import skill_refs, skill_tooltip
    from mxl_gfx import skill_icon_file
    data = ctx.data
    ctx_ = CatalogContext(entry(data, name='Auto Da Fe'), data)
    refs = skill_refs(ctx_.lo, ctx_.hi, data)
    ctx.expect('compétences', refs, {'Ignis Fatuus': (470, 1, 2), 'Flamefront': (523, 3, 4)})
    ctx.expect('explication', [t for _, t in skill_tooltip(523, 3, 4, data)],
               ['Flamefront', 'spell - casts a wave of exploding firebolts in front of you', '', 'Current Skill Level: 3 to 4',
                'Firebolts: varies by character', 'Fire Damage: varies by character', 'Mana Cost: 8'])
    ctx.expect('niveau fixe', skill_tooltip(470, 2, 2, data)[3][1], 'Current Skill Level: 2')
    ctx.expect('icônes', (skill_icon_file(523, data), skill_icon_file(470, data), skill_icon_file(1478, data)),
               ('shared_92', 'shared_282', 'pal_86'))
    jared = CatalogContext(entry(data, 'unique:375'), data)   # 5% Chance to cast level 4 Spike Nova on Melee Attack
    ctx.expect('chance de lancer', {k: v[1:] for k, v in skill_refs(jared.lo, jared.hi, data).items()}, {'Spike Nova': (4, 4)})
    ctx.check(all(data.skill_names.get(v[0]) for e in cat(data)[:300]
                  for v in skill_refs(*(lambda c: (c.lo, c.hi))(CatalogContext(e, data)), data).values()), 'compétence sans nom repérée')
    # compétences modifiées sans niveau donné (mentions) : temps de recharge (309), stat cachée d'un texte d'effet
    # (383 : Vision of the Furies), stat propre à une compétence (« Bonus Elemental Damage to Bloodlust » : 381 -> 500)
    vision = CatalogContext(entry(data, name='Vision of the Furies'), data)
    ctx.expect('mentions', skill_refs(vision.lo, vision.hi, data, mentions=True),
               {'Fire Elementals': (1042, None, None), 'Bloodlust': (500, None, None)})
    ctx.expect('sans mentions', skill_refs(vision.lo, vision.hi, data), {})
    winter = CatalogContext(entry(data, name='Beastfur Pelt'), data)
    ctx.expect('temps de recharge', skill_refs(winter.lo, winter.hi, data, mentions=True).get('Winter Avatar', (0,))[1:],
               (None, None))


@case('Bibliothèque', "explication d'une compétence : nombres du jeu (valeurs qui ne dépendent que du niveau)")
def skill_numbers(ctx):
    """Formules des compétences interprétées (mxl_skill_calc), comparées aux captures en jeu du 30/09 : Ignis Fatuus
    niveau 2 et Flamefront niveau 4 (personnage nécromancien : Incineration, compétence citée par la formule des
    Firebolts, sans point, vaut 0). Lignes dans l'ordre du jeu, « item granted passive skill » en bleu ; dégâts de feu de
    Flamefront (synergie sur l'Énergie : dépend du personnage) non affichés ; plages dans le catalogue."""
    from mxl_skills import skill_tooltip
    from mxl_skill_calc import skill_calc, desc_line
    from mxl_theme import WHITE, BLUE
    data = ctx.data
    necro = dict(cls=2, level=24, skills={}, items=[], base_stats={})   # personnage de référence minimal (classe, niveau, points)
    ctx.expect('Ignis Fatuus niveau 2', skill_tooltip(470, 2, 2, data, necro)[4:],
               [(BLUE, 'item granted passive skill'), (WHITE, ''), (WHITE, '+10 Spell Focus'), (WHITE, 'Fire Resist -3%'),
                (WHITE, 'Fire Damage to Weapon: 28-44')])
    ctx.expect('Flamefront niveau 4 (nécromancien niveau 24 sans objet)', [t for _, t in skill_tooltip(523, 4, 4, data, necro)[4:]],
               ['Firebolts: 3', 'Fire Damage: 12-15', 'Mana Cost: 8'])
    calc = skill_calc(data)
    sorc = dict(cls=1, level=24, skills={1599: 5}, items=[], base_stats={})   # 5 points dans Incineration : terme de mana actuelle annulé (valeur exacte)
    ctx.expect('Flamefront : sorcière avec / sans points dans Incineration, sans personnage',
               (calc.lines(523, 4, 4, sorc), calc.lines(523, 4, 4, dict(sorc, skills={})), calc.lines(523, 4, 4)),
               (['Firebolts: 3', 'Fire Damage: 12-15', 'Mana Cost: 8'], ['Firebolts: 3', 'Fire Damage: 12-15', 'Mana Cost: 8'],
                ['Firebolts: varies by character', 'Fire Damage: varies by character', 'Mana Cost: 8']))
    ctx.expect('plages (catalogue)', calc.lines(470, 1, 2),
               ['\nitem granted passive skill', '+5 to +10 Spell Focus', 'Fire Resist -1 to -3%', 'Fire Damage to Weapon: 14-22 to 28-44'])
    ctx.expect('formats', [desc_line(2, 'Speed: ', '%', [20, 30], None), desc_line(7, ' bolts', '', [5, 5], None),
                           desc_line(66, 'Converts %d%% to Fire', '', [75, 75], None), desc_line(99, 'x', '', [1, 1], None)],
               ['Speed: +20 to +30%', '5 bolts', 'Converts 75% to Fire', None])
    # constantes signées : un octet 246 vaut -10 (Venomous Spirit : « Enemy Movement Speed: -10% »)
    vs = next(k for k, v in data.skill_names.items() if v == 'Venomous Spirit')
    ctx.check('Enemy Movement Speed: -10%' in calc.lines(vs, 1, 1), f'constante signée : {calc.lines(vs, 1, 1)}')
    # toutes les compétences données par des objets : aucune erreur, aucune ligne avec une formule absente
    from mxl_library import catalog
    from mxl_catalog_tooltip import CatalogContext
    from mxl_skills import skill_refs
    n = 0
    for e in catalog(data):
        c = CatalogContext(e, data)
        for sid, lo, hi in skill_refs(c.lo, c.hi, data).values():
            n += len(skill_tooltip(sid, lo, hi, data))
    ctx.check(n > 3000, f'explications calculées : {n} lignes')


@case('Bibliothèque', "explication d'une compétence : améliorations données par les objets (syn1 à syn6)")
def skill_modifiers(ctx):
    """syn1 = stat cachée 383 du personnage, param = n° de la compétence (D2Sigma.dll) : Magic Missiles tire
    min(6 + niveau / 5, 15) + syn1 projectiles ; sans amélioration 0, avec une amélioration (+1) un projectile de plus ;
    sans personnage de référence : ligne masquée."""
    from mxl_skill_calc import skill_calc
    from mxl_char_stats import CharacterStats
    data = ctx.data
    calc = skill_calc(data)
    mm = next(k for k, v in data.skill_names.items() if v == 'Magic Missiles')
    cs = CharacterStats(dict(cls=1, level=30, skills={}, items=[], base_stats={}), data)
    bolts = lambda: [l for l in calc.lines(mm, 5, 5, cs) if 'bolts' in l]
    before = bolts()
    cs.totals[(383, mm)] = 1
    after = bolts()
    ctx.expect('projectiles sans / avec amélioration', (before, after), (['7 bolts'], ['8 bolts']))
    ctx.check(not [l for l in calc.lines(mm, 5, 5) if 'bolts' in l], 'ligne affichée sans personnage de référence')


@case('Bibliothèque', "explication d'une compétence : dégâts élémentaires (capture de Flamefront avec Kalidor)")
def skill_damage(ctx):
    """Kalidor au 30/09 (paladin niveau 4, Énergie 21, Auto Da Fe porté : Spell Focus 25 + 10 d'Ignis Fatuus, +4 % dégâts
    de sort de feu) : Flamefront niveau 4 = « Firebolts: 3 », « Fire Damage: 5-7 », « Mana Cost: 8 » comme en jeu ;
    paliers de niveau et formules du bonus automatique (D2Sigma.dll)."""
    import os
    from common import FIXTURES
    from mxl_save import load_character
    from mxl_skill_calc import skill_calc, level_brackets, energy_bonus
    from mxl_char_stats import CharacterStats
    data = ctx.data
    kalidor = load_character(os.path.join(FIXTURES, 'kalidor', 'Kalidor.d2s'), data)
    calc = skill_calc(data)
    ctx.expect('Flamefront niveau 4 (Kalidor)', calc.lines(523, 4, 4, kalidor), ['Firebolts: 3', 'Fire Damage: 5-7', 'Mana Cost: 8'])
    # 2e capture en jeu (Flamefront d'Auto Da Fe édité au niveau 3 dans l'éditeur, même personnage)
    ctx.expect('Flamefront niveau 3 (Kalidor)', calc.lines(523, 3, 3, kalidor), ['Firebolts: 3', 'Fire Damage: 4-5', 'Mana Cost: 8'])
    ctx.expect('dégâts en 256es', (calc.elem_damage(523, 4, CharacterStats(kalidor, data), 'min'),
                                   calc.elem_damage(523, 4, CharacterStats(kalidor, data), 'max')), (1409, 1827))
    ctx.expect('paliers (niveaux 1, 4, 8, 9, 17, 30)', [level_brackets([1, 10, 100, 1000, 10000], n) for n in (1, 4, 8, 9, 17, 30)],
               [0, 3, 7, 17, 187, 26687])
    ctx.expect('bonus automatique (Kalidor)', energy_bonus(CharacterStats(kalidor, data)), -19)
    ctx.expect('sans personnage de référence', [l for l in calc.lines(523, 4, 4) if 'Damage' in l],
               ['Fire Damage: varies by character'])
    # variables des formules (D2Common.dll, remplacées par D2Sigma.dll) : edmn / edmx sans « % dégâts de sort » de
    # l'élément, enma / exma avec, edns / enms… en 256es
    cs = CharacterStats(kalidor, data)
    ref = lambda name: calc.ref(calc.refs.index(name), 523, 4, cs)
    ctx.expect('edmn, edmx, enma, exma, edns, enms', [ref(n) for n in ('edmn', 'edmx', 'enma', 'exma', 'edns', 'enms')],
               [1355 >> 8, 1757 >> 8, 1409 >> 8, 1827 >> 8, 1355, 1409])


@case('Bibliothèque', "explication d'une compétence : durées et poison (formats 11, 12, 14 de D2Client.dll)")
def skill_durations(ctx):
    """Durées en frames (25 par seconde) affichées comme le jeu : entier ou une décimale tronquée, « second » au
    singulier seulement pour 1 ; durée des effets (edln) sur 3 paliers de niveau ; poison (format 14) : dégâts × durée /
    256 au-dessus de « over … seconds » (texte multiple, affiché de bas en haut)."""
    import os
    from common import FIXTURES
    from mxl_save import load_character
    from mxl_skill_calc import skill_calc, level_brackets
    from mxl_char_stats import CharacterStats
    data = ctx.data
    calc = skill_calc(data)
    ctx.expect('secondes (0, 1, 3, 25, 50, 60, 70 frames)', [calc.seconds(n) for n in (0, 1, 3, 25, 50, 60, 70)],
               [None, None, '0.1 seconds', '1 second', '2 seconds', '2.4 seconds', '2.8 seconds'])
    ctx.expect('paliers des durées (niveaux 1, 8, 9, 16, 17, 30)',
               [level_brackets([1, 10, 100, 100, 100], n, (8, 16, 10 ** 9)) for n in (1, 8, 9, 16, 17, 30)],
               [0, 7, 17, 87, 187, 1487])
    ch = CharacterStats(load_character(os.path.join(FIXTURES, 'character_sheet', 'Nekratall.d2s'), data), data)
    hive = next(k for k, v in data.skill_names.items() if v == 'Hive')
    line = next(l for l in calc.lines(hive, 5, 5, ch) if 'Poison Damage' in l)
    over, dmg = line.split('\n')
    n = calc.elem_length(hive, 5, ch)
    lo, hi = ((calc.elem_damage(hive, 5, ch, w) * n) >> 8 for w in ('min', 'max'))
    ctx.expect('poison sur la durée', (over, dmg), (f'over {calc.seconds(n)}', f'Poison Damage: {lo}-{hi}'))


@case('Bibliothèque', "explication d'une compétence sans personnage de référence : « varies by character »")
def skill_varies(ctx):
    """Écran Library : une valeur qui dépend du personnage est remplacée par « <libellé>: varies by character » (libellé
    connu), sinon une note grise « (values depend on character) » sous « Current Skill Level » ; les valeurs qui ne
    dépendent que du niveau restent affichées."""
    from mxl_skills import skill_tooltip
    from mxl_theme import GREY
    data = ctx.data
    ctx.expect('Flamefront (Auto Da Fe)', [t for _, t in skill_tooltip(523, 3, 4, data)][3:],
               ['Current Skill Level: 3 to 4', 'Firebolts: varies by character', 'Fire Damage: varies by character',
                'Mana Cost: 8'])
    ctx.check(not [t for _, t in skill_tooltip(470, 1, 2, data) if 'character' in t], 'Ignis Fatuus : rien ne dépend du personnage')
    tips = [skill_tooltip(s, 1, 1, data) for s in data.skill_names if data.skill_names[s]][:400]
    noted = [t for t in tips if (GREY, '(values depend on character)') in t]
    ctx.check(noted and all(t[t.index((GREY, '(values depend on character)')) - 1][1].startswith('Current Skill Level')
                            for t in noted), 'note absente ou mal placée')
    ctx.check(not [l for t in tips for _, l in t if l.startswith('(') and 'varies by character' in l], 'parenthèse ouverte')


@case('Bibliothèque', "explication d'une compétence : « % Weapon Damage » (variable wdm)")
def skill_weapon_damage(ctx):
    """wdm = part des dégâts de l'arme (skills.bin u8 @0x1A5, en 128es) × 100 / 128 (D2Sigma.dll) : Spike Nova de
    Jared's Fragmentor = 100 % (128 / 128), avec ou sans personnage de référence."""
    from mxl_skill_calc import skill_calc
    calc = skill_calc(ctx.data)
    nova = next(k for k, v in ctx.data.skill_names.items() if v == 'Spike Nova')
    ctx.expect('Spike Nova niveau 4', calc.lines(nova, 4, 4), ['\nitem granted skill', '100% Weapon Damage'])


@case('Bibliothèque', "explication d'une compétence : toute valeur non calculée signalée en gris (coffre et Library)")
def skill_not_calculated(ctx):
    """Valeur inconnue : ligne grise « <libellé>: varies by character » (sans personnage de référence) ou « <libellé>:
    not calculated » (avec) ; libellé inconnu ou format de ligne pas encore reconnu : note grise sous « Current Skill
    Level » (« (values depend on character) » / « (some values not calculated) »)."""
    import os
    from common import FIXTURES
    from mxl_save import load_character
    from mxl_skills import skill_tooltip
    from mxl_theme import GREY, WHITE
    data = ctx.data
    ch = load_character(os.path.join(FIXTURES, 'character_sheet', 'Nekratall.d2s'), data)
    ctx.expect('Flamefront sans personnage', skill_tooltip(523, 3, 4, data)[4:],
               [(GREY, 'Firebolts: varies by character'), (GREY, 'Fire Damage: varies by character'), (WHITE, 'Mana Cost: 8')])
    names = [s for s in data.skill_names if data.skill_names[s]][:500]
    with_char = [skill_tooltip(s, 5, 5, data, ch) for s in names]
    grey = {t for tip in with_char for c, t in tip if c == GREY}
    ctx.check(any(t.endswith(': not calculated') for t in grey), 'aucune ligne « not calculated » avec un personnage')
    ctx.check('(some values not calculated)' in grey, 'aucune note avec un personnage')
    ctx.check(not any('varies by character' in t or t == '(values depend on character)' for t in grey),
              'texte « sans personnage » affiché avec un personnage')
    for tip in with_char:   # note juste sous « Current Skill Level »
        if (GREY, '(some values not calculated)') in tip:
            i = tip.index((GREY, '(some values not calculated)'))
            ctx.check(tip[i - 1][1].startswith('Current Skill Level'), f'note mal placée : {tip[:i + 1]}')


@case('Bibliothèque', "explication d'une compétence sans fiche dans le jeu, non décrite (Stampede Nova)")
def skill_without_details(ctx):
    """73 compétences lancées par chance n'ont pas de fiche : texte vide (« FLYING POLAR BUFFALO ERROR » dans le jeu),
    icône n° 0 du fichier commun (« ? ») : ni texte d'erreur, ni icône ; part des dégâts de l'arme si elle n'est pas nulle,
    puis note grise « (no description in game data) »."""
    from mxl_skills import skill_tooltip
    from mxl_gfx import skill_icon_file
    from mxl_theme import GREY
    data = ctx.data
    # cas général (compétence ni décrite par le jeu, ni par les mécanismes vérifiés une à une) : Stampede Nova (1214,
    # hors du catalogue ; Thunder Wave d'Akarat's Trek, l'exemple d'origine, est décrite depuis le 02/10)
    wave = 1214
    ctx.expect('Stampede Nova (part des dégâts de l arme : 144 / 128 = 112 %)', [t for _, t in skill_tooltip(wave, 30, 30, data)],
               ['Stampede Nova', '', 'Current Skill Level: 30', '112% Weapon Damage', '(no description in game data)'])
    ctx.expect('note grise', skill_tooltip(wave, 30, 30, data)[-1][0], GREY)
    ctx.expect('pas d icône « ? »', skill_icon_file(wave, data), None)
    ctx.check(not [s for s, t in data.skill_desc.items() if 'BUFFALO' in t], 'texte « BUFFALO » restant')
    ctx.expect('icône ordinaire gardée (Flamefront)', skill_icon_file(523, data), 'shared_92')
    nova = next(k for k, v in data.skill_names.items() if v == 'Thunder Hammer Nova')
    ctx.expect('compétence décrite : icône « ? » du jeu gardée (Thunder Hammer Nova)', skill_icon_file(nova, data), 'shared_0')


@case('Bibliothèque', "explication d'une compétence : temps de recharge (variable skcd)")
def skill_cooldown(ctx):
    """skcd = formule de recharge de la compétence (skills.bin @0x190, frames) − stat 309 du personnage (« Cooldown
    Reduced by », param = compétence), D2Sigma.dll 0x100b0ed0 : Telekinesis 25 frames = « Cooldown: 1 second » ;
    réduction de 5 frames = 0.8 seconde ; sans personnage de référence : « varies by character »."""
    from mxl_skill_calc import skill_calc
    from mxl_char_stats import CharacterStats
    data = ctx.data
    calc = skill_calc(data)
    tk = next(k for k, v in data.skill_names.items() if v == 'Telekinesis')
    cs = CharacterStats(dict(cls=1, level=30, skills={}, items=[], base_stats={}), data)
    cooldown = lambda char: [l for l in calc.lines(tk, 1, 1, char) if 'Cooldown' in l]
    ctx.expect('sans réduction', cooldown(cs), ['Cooldown: 1 second'])
    cs.totals[(309, tk)] = 5
    ctx.expect('réduction de 5 frames', cooldown(cs), ['Cooldown: 0.8 seconds'])
    ctx.expect('sans personnage', cooldown(None), ['Cooldown: varies by character'])


@case('Bibliothèque', "explication d'une compétence : nombre maximal d'invocations (pets) et stat cachée 211")
def skill_pets(ctx):
    """pets = formule de skills.bin @0xC0 (D2Common.dll, variable 71 ; pas de formule = 0). Blood Skeleton lit la stat
    cachée 211 (posée par les passifs de spécialisation et les auras de transformation, qui désactivent les
    invocations) : prise avec sa valeur au repos (objets + passifs), 0 sans spécialisation ; 1 = 0 invocation : ligne masquée (valeur nulle, D2Client.dll)."""
    from mxl_skill_calc import skill_calc
    from mxl_char_stats import CharacterStats
    data = ctx.data
    calc = skill_calc(data)
    sid = lambda name: next(k for k, v in data.skill_names.items() if v == name)
    cs = CharacterStats(dict(cls=4, level=30, skills={}, items=[], base_stats={}), data)
    count = lambda name, label, char: [l for l in calc.lines(sid(name), 13, 13, char) if l.startswith(label)]
    ctx.expect('Summon Edyrem', count('Summon Edyrem', 'Edyrems:', cs), ['Edyrems: 10'])
    ctx.expect('Blood Skeleton', count('Blood Skeleton', 'Skeletons:', cs), ['Skeletons: 2'])
    cs.totals[(211, None)] = 1
    ctx.expect('Blood Skeleton spécialisé', count('Blood Skeleton', 'Skeletons:', cs), [])
    ctx.expect('stat 379 (réduction des bonus d invocation) : 0 au repos', count('Summon Darklings', 'Damage:', cs),
               ['Damage: 18-28'])


@case('Bibliothèque', "explication d'une compétence : vie et Attack Rating des invocations (mnhp, mnar)")
def skill_minion_life(ctx):
    """mnhp (D2Sigma.dll 0x10067c60) = (vie skills.bin @0x150 + (niveau − 1) × @0x154) × (100 + formule @0x138) ×
    (100 + niveau du personnage / 2) / 3333 ; mnar (0x10067bd0) = (niveau − 1) × @0x158 × (100 + stat 500) / 100.
    Blood Skeleton niveau 13, personnage niveau 30 : 520 × 100 × 115 / 3333 = 1794 ; la formule de vie lit la stat 444
    (« Summon Life ») réduite de la stat cachée 379 (0 au repos)."""
    from mxl_skill_calc import skill_calc
    from mxl_char_stats import CharacterStats
    data = ctx.data
    calc = skill_calc(data)
    bs = next(k for k, v in data.skill_names.items() if v == 'Blood Skeleton')
    cs = CharacterStats(dict(cls=4, level=30, skills={}, items=[], base_stats={}), data)
    lines = lambda char: [l for l in calc.lines(bs, 13, 13, char) if l.startswith(('Life', 'Attack Rating'))]
    ctx.expect('sans bonus', lines(cs), ['Life: 1794 hit points', 'Attack Rating: 1400'])
    cs.totals[(444, None)] = 50
    cs.totals[(500, None)] = 50
    ctx.expect('+50% Summon Life / Attack Rating', lines(cs), ['Life: 2763 hit points', 'Attack Rating: 2000'])
    ctx.expect('sans personnage', lines(None), ['Life: varies by character', 'Attack Rating: varies by character'])


@case('Bibliothèque', "explication d'une compétence : formats relus dans D2Client.dll / D2Sigma.dll, opérations de Fog.dll")
def skill_formats_game(ctx):
    """Formats de ligne d'après le code du jeu : 19 = rayon (v × 20 / 3 dixièmes de yard, Jitan's Gate 25 -> 16.6) ;
    9 = dégâts physiques de la compétence (Singularity niveau 5 : (48 + 4 × 8) × 217 % → 173 × 32 / 256 = 21, max 32) ;
    8 = « To Attack Rating: +v% » (toht) ; 26 = dégâts × 25 / 256 « per second » ; 76 = texte de déblocage tant que la
    stat de déblocage est nulle ; opération 9 = constante i32 (Summon Edyrem « Damage: 12-12 », format 35) ;
    stat(n, 1) = valeur de base (ATMG Sentry : rayon selon la Dextérité de base, pas celle des objets)."""
    from mxl_skill_calc import skill_calc, desc_line
    from mxl_char_stats import CharacterStats
    data = ctx.data
    calc = skill_calc(data)
    sid = lambda name: next(k for k, v in data.skill_names.items() if v == name)
    cs = CharacterStats(dict(cls=1, level=30, skills={}, items=[], base_stats={2: 40}), data)
    pick = lambda name, lvl, start: [l for l in calc.lines(sid(name), lvl, lvl, cs) if l.startswith(start)]
    ctx.expect('format 19', pick("Jitan's Gate", 1, 'Range'), ['Range: 16.6 yards'])
    ctx.expect('format 9', pick('Singularity', 5, 'Physical'), ['Physical Damage: 21-32'])
    ctx.expect('format 8', pick('Heartseeker', 5, 'Attack'), ['Attack Rating: +10%'])
    ctx.expect('format 26', pick('Ember Spirit', 5, 'Average'), ['Average Fire Damage: 176-237 per second'])
    ctx.expect('format 76', pick('Force Blast', 5, '\n\n'), ['\n\nDefeat Buyard Cholik in Bramwell\nUnlockable Skill\n'])
    ctx.expect('opération 9', pick('Summon Edyrem', 10, 'Damage'), ['Damage: 12-12'])
    ctx.expect('Dextérité de base 40', pick('ATMG Sentry', 5, 'Radius'), ['Radius: 12 yards'])
    cs.totals[(2, None)] = 900
    ctx.expect('Dextérité des objets 900 (sans effet)', pick('ATMG Sentry', 5, 'Radius'), ['Radius: 12 yards'])
    cs.char['base_stats'][2] = 900
    ctx.expect('Dextérité de base 900', pick('ATMG Sentry', 5, 'Radius'), ['Radius: 22 yards'])
    ctx.expect('valeurs nulles masquées, signes', [desc_line(3, 'Hits: ', '', [0, 0], None), desc_line(4, 'Bonus: ', '', [5, 5], None),
                                                   desc_line(38, 'Damage: ', '', [7, 7], [7, 7]), desc_line(63, 'Party', 'Bonus', [3, 3], None)],
               [None, 'Bonus: +5', 'Damage: 7', 'Party: +3% Bonus'])


@case('Bibliothèque', "explication d'une compétence : taux de conversion de la vie / mana actuelles")
def skill_pool_rate(ctx):
    """Vie / mana actuelles (stats 6 / 8) : varient en cours de partie ; la ligne est recalculée pour 0, 200, 400 et 600
    points et, si chaque nombre y est proportionnel, affichée en gris avec son taux (Arcane Torrent : dégâts nuls sans
    mana, « 7-10 per 100 Current Mana » ; Dragon Jaws : valeur sans mana + taux ; Vizjerei Rage : mana manquante ; Balefire : texte qui donne déjà le taux, nombre retiré)."""
    from mxl_skill_calc import skill_calc, Grey
    from mxl_save import load_character
    data = ctx.data
    calc = skill_calc(data)
    char = load_character(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'character_sheet', 'Nekratall.d2s'), data)
    sid = lambda name: next(k for k, v in data.skill_names.items() if v == name)
    pick = lambda name: [l for l in calc.lines(sid(name), 5, 5, char) if l.startswith('Physical')]
    ctx.expect('Arcane Torrent', pick('Arcane Torrent'), ['Physical Damage: 7-10 per 100 Current Mana'])
    ctx.expect('Dragon Jaws', pick('Dragon Jaws'), ['Physical Damage: 25-30 (+0.8 per 100 Current Mana)'])
    ctx.expect('Vizjerei Rage', pick('Vizjerei Rage'), ['Physical Damage: +62 per 100 Missing Mana'])
    ctx.expect('en gris', all(isinstance(l, Grey) for l in pick('Arcane Torrent') + pick('Vizjerei Rage')), True)
    drain = [l for l in calc.lines(sid('Balefire'), 5, 5, char) if l.startswith('Drains')]
    ctx.expect('Balefire : taux déjà dans le texte du jeu, nombre retiré', drain, ['Drains 10% of current life per second'])


@case('Bibliothèque', "explication d'une compétence : projectiles (miss), stat 88, rendement décroissant")
def skill_missile_values(ctx):
    """miss(projectile, variable) lit missiles.bin (D2Common.dll 0x6fdba790) : Widowmaker « Converts 70% Physical Damage
    to Magic » (dpa1 du projectile 1156) ; stat 88 = marque des unités invoquées (D2Sigma.dll 0x1004b4b0), 0 pour un
    personnage (Jerhyn's Tawiz calculé) ; rendement décroissant du jeu (D2Common.dll 0x6fd9dc30) : arrondis successifs,
    plafonné au maximum."""
    from mxl_skill_calc import skill_calc, diminishing
    from mxl_char_stats import CharacterStats
    data = ctx.data
    calc = skill_calc(data)
    sid = lambda name: next(k for k, v in data.skill_names.items() if v == name)
    ctx.expect('Widowmaker sans personnage', [l for l in calc.lines(sid('Widowmaker'), 1, 1) if l.startswith('Converts')],
               ['Converts 70% Physical Damage to Magic'])
    cs = CharacterStats(dict(cls=1, level=30, skills={}, items=[], base_stats={}), data)
    ctx.expect("Jerhyn's Tawiz", any('not calculated' in l for l in calc.lines(sid("Jerhyn's Tawiz"), 1, 1, cs)), False)
    ctx.expect('rendement décroissant', [diminishing(0, 10, 100), diminishing(1, 10, 100), diminishing(20, 10, 100),
                                         diminishing(10 ** 6, 10, 100)], [0, 23, 85, 100])


@case('Bibliothèque', "explication d'une compétence : couleurs des codes du jeu (ÿc), comme D2Win.dll")
def skill_text_colors(ctx):
    """Couleurs des lignes chiffrées : uniquement celles des codes ÿc de leurs textes ; le tampon se dessine de bas en
    haut et la couleur continue sur les lignes au-dessus (D2Win.dll 0x6f8f2940). ✅ captures : Ignis Fatuus « item
    granted passive skill » en bleu ; Blood Skeleton, lignes dsc2 sans code (« Area Effect Attack ») en blanc. Une
    ligne peut changer de couleur (Cascade : « Steady Aim » en vert foncé)."""
    from mxl_skills import skill_tooltip, game_colors
    from mxl_theme import WHITE, BLUE, GREY, DARK_GREEN, YELLOW
    data = ctx.data
    sid = lambda name: next(k for k, v in data.skill_names.items() if v == name)
    char = dict(cls=4, level=30, skills={}, items=[], base_stats={})
    bs = [line for line in skill_tooltip(sid('Blood Skeleton'), 13, 13, data, char) if line[1].startswith(('Area', 'Cooldown'))]
    ctx.expect('Blood Skeleton : dsc2 sans code en blanc', bs, [(WHITE, 'Area Effect Attack'), (WHITE, 'Cooldown: 2.4 seconds')])
    cascade = [line for line in skill_tooltip(sid('Cascade'), 5, 5, data, char, segments=True) if 'Steady Aim' in ''.join(t for _, t in line)]
    ctx.expect('Cascade : couleurs dans la ligne', cascade, [[(WHITE, 'Consumes all'), (DARK_GREEN, ' Steady Aim '), (WHITE, 'charges')]])
    ctx.expect('couleur qui continue vers le haut, gris conservé',
               game_colors(['haut', 'ÿc9milieu', 'bas'], grey={0}),
               [[(GREY, 'haut')], [(YELLOW, 'milieu')], [(WHITE, 'bas')]])
    ctx.expect('ligne multiple : de bas en haut', game_colors(['un' + chr(10) + 'ÿc3deux']), [[(BLUE, 'deux')], [(WHITE, 'un')]])
    # description de plusieurs lignes : stockée de bas en haut (« to shock nearby enemies\ncreates an expanding ring »)
    ctx.expect('description de Nova dans l ordre du jeu', [t for _, t in skill_tooltip(sid('Nova'), 1, 1, data)][1:3],
               ['creates an expanding ring of lightning', 'to shock nearby enemies'])


def skill_lines_text(data, char):
    """Toutes les explications de compétences du catalogue (infobulle complète, couleurs comprises), une ligne de texte
    par ligne d'infobulle : « compétence #n° | personnage | <couleur>texte… »."""
    from mxl_skills import skill_refs, skill_tooltip
    from mxl_catalog_tooltip import CatalogContext
    refs = {}
    for e in catalog(data):
        ctx_ = CatalogContext(e, data)
        for sid, lo, hi in skill_refs(ctx_.lo, ctx_.hi, data).values():
            a, b = refs.get(sid, (lo, hi))
            refs[sid] = (min(a, lo), max(b, hi))
    out = []
    for sid in sorted(refs):
        lo, hi = refs[sid]
        for who, ch in (('Nekratall', char), ('Library', None)):
            for line in skill_tooltip(sid, lo, hi, data, ch, segments=True):
                out.append(f'{data.skill_names.get(sid)} #{sid} | {who} | ' + ''.join(f'<{c}>{t}' for c, t in line))
    return '\n'.join(out) + '\n'


@case('Bibliothèque', "explication des compétences : photo de tout le catalogue (tests/reference/skill_lines.txt)")
def skill_lines_snapshot(ctx):
    """Les explications des 417 compétences données par les objets du catalogue, avec Nekratall et sans personnage
    (écran Library), lignes et couleurs, comparées à la référence : tout changement, même d'une seule ligne, est
    signalé. Changement voulu (vérifié) : python tests/run_tests.py --update -k photo."""
    from mxl_save import load_character
    char = load_character(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'character_sheet',
                                       'Nekratall.d2s'), ctx.data)
    ctx.compare('skill_lines.txt', skill_lines_text(ctx.data, char))


@case('Bibliothèque', "familles du catalogue (filtre Type) : uniques à tiers, Sacred / SSU / SSSU, autres, sets")
def catalog_families(ctx):
    """Famille de chaque entrée : base « (1) » à « (4) » = Tiered ; base « (Sacred) » qui peut tomber, par niveau
    d'objet (page officielle « Sacred Uniques » : SU 105, SSU 120, SSSU 130) ; Sacred qui ne tombe pas, bijoux… =
    autres. Exemples relevés sur le site : Witherfang 130 (SSSU, placé au centre de son tableau mais niveau 130),
    Herald of Pestilence 120 (SSU), The Xiphos 105 (SU). Anneaux, amulettes, joyaux et carquois sacrés (niveau 105 ou
    plus, qui tombent) : mêmes seuils (✅ game feed du Discord de Median XL, 09/10 : Signet of the Gladiator « SSU »,
    Jewel of Luck et Arkenstone « SSSU ») ; plus bas (Witchmoon 100), charmes de boss : autres."""
    from collections import Counter
    from mxl_library import FAMILIES
    cat = catalog(ctx.data)
    fam = lambda name, base: next(e['family'] for e in cat if e['name'] == name and e['base'] == base)
    ctx.expect('exemples', [fam('The Xiphos', 'Short Sword (Sacred)'), fam('Herald of Pestilence', 'Angel Star (Sacred)'),
                            fam('Witherfang', 'Flail (Sacred)'), fam('Void-Infused', 'Maple Bow (Sacred)'),
                            fam("Jared's Fragmentor", 'Claymore (3)')],
               ['sacred', 'ssu', 'sssu', 'other', 'tiered'])
    ctx.expect('bijoux, joyaux, carquois', [fam('Signet of the Gladiator', 'Ring'), fam('Jewel of Luck', 'Jewel'),
                                            fam('Arkenstone', 'Jewel'), fam('Earth Rouser', 'Ring'),
                                            fam('Bag of Tricks', 'Arrow Quiver'), fam('Witchmoon', 'Amulet'),
                                            fam("Skinrender's Ear", "Skinrender's Ear")],
               ['ssu', 'sssu', 'sssu', 'sacred', 'ssu', 'other', 'other'])
    counts = Counter(e['family'] for e in cat)
    ctx.expect('toutes les familles présentes', sorted(counts) == sorted(FAMILIES), True)
    ctx.expect('Sacred par niveau', (counts['sacred'], counts['ssu'], counts['sssu']), (212, 198, 27))


@case('Bibliothèque', "explication d'une compétence : coût en mana de Median XL (format 77, Mana Cost of Skills)")
def skill_mana_cost(ctx):
    """Coût en mana (D2Sigma.dll 0x100a8cf0, ligne de format 77) : formules de skills2.bin (mana de base @0x36, mana par
    niveau @0x3A × (100 + stat 228 « Mana Cost of Skills ») / 100), décalées de manashift, au moins le minimum ; écrit en
    entier ou avec une décimale tronquée. Nova : niveau 1 « 16.5 », niveau 20
    « 21.2 », avec -50 % « 18.8 » (seule la part par niveau est réduite). ✅ Flamefront de Kalidor : 8 ; Blood Skeleton
    : 1 en ville (skill(1819, clc2)), 49 hors de la ville (convention de l'application)."""
    from mxl_skill_calc import skill_calc
    from mxl_skill_lines import mana_text
    from mxl_char_stats import CharacterStats
    data = ctx.data
    calc = skill_calc(data)
    nova = next(k for k, v in data.skill_names.items() if v == 'Nova')
    cs = CharacterStats(dict(cls=1, level=30, skills={}, items=[], base_stats={}), data)
    cost = lambda lvl: [l for l in calc.lines(nova, lvl, lvl, cs) if l.startswith('Mana Cost')]
    ctx.expect('Nova niveaux 1 et 20', (cost(1), cost(20)), (['Mana Cost: 16.5'], ['Mana Cost: 21.2']))
    cs.totals[(228, None)] = -50
    ctx.expect('Mana Cost of Skills -50%', cost(20), ['Mana Cost: 18.8'])
    ctx.expect('écriture', [mana_text(2240), mana_text(2240, decimal=False), mana_text(0)], ['8.7', '8', None])


@case('Bibliothèque', "explication des compétences : invocations de Nekratall hors de la ville (captures du jeu)")
def skill_summons_outside_town(ctx):
    """✅ Captures du jeu (02/10/2026), Nekratall hors de la ville : Blood Skeleton niveau 13, Abyss Knight niveau 7 et
    Night Hawks niveau 2, toutes les lignes (couleurs comprises) ; le coût en mana dépend de la zone (1 en ville)."""
    from mxl_save import load_character
    from mxl_skills import skill_tooltip
    data = ctx.data
    char = load_character(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'character_sheet',
                                       'Nekratall.d2s'), data)
    sid = lambda name: next(k for k, v in data.skill_names.items() if v == name)   # la première (noms en double)
    tip = lambda name, lvl: [(int(c), t) for c, t in skill_tooltip(sid(name), lvl, lvl, data, char)[4:]]
    ctx.expect('Blood Skeleton 13', tip('Blood Skeleton', 13), [
        (0, 'Area Effect Attack'), (0, 'Cooldown: 6 seconds'), (0, 'Skeletons: 5'), (0, 'Life: 2725 hit points'),
        (0, 'Damage: 28-38'), (0, 'Attack Rating: 1400'), (0, 'Mana Cost: 49')])
    ctx.expect('Abyss Knight 7', tip('Abyss Knight', 7), [
        (0, '5% chance to cast Chaos Nova on Kill'), (0, 'Cooldown: 2.4 seconds'), (0, 'Knights: 2'),
        (0, 'Life: 2112 hit points'), (0, 'Magic Damage: 72-72'), (0, 'Always Hits'), (0, 'Mana Cost: 19')])
    ctx.expect('Night Hawks 2', tip('Night Hawks', 2), [
        (8, 'Inherits Grim Vision Aura'), (0, ''), (0, 'Hits Multiple Times'), (0, 'Max Hawks: 5'),
        (0, 'Cooldown: 2 seconds'), (0, 'Damage: 37-45'), (0, 'Attack Rating: 950'), (0, 'Mana Cost: 19')])


@case('Bibliothèque', "régénération de vie affichée comme le jeu (descfunc 32 : ÷ 10 tronqué, au moins 1)")
def regen_display(ctx):
    """D2Sigma.dll 0x10077800 : valeur stockée / 10 tronquée vers zéro, au moins 1 si positive, au plus −1 si négative.
    Athulua's Blessing : 1125 -> 112 (le site arrondit à 113)."""
    from mxl_stat_text import regen_shown
    ctx.expect('valeurs', [regen_shown(v) for v in (1125, 750, 16, 5, 0, -5, -1125)], [112, 75, 1, 1, 0, -1, -112])


@case('Bibliothèque', "objet non trouvé affiché dans le contexte du personnage sélectionné (Nekratall)")
def catalog_with_character(ctx):
    """Avec un personnage : exigences en rouge s'il ne les remplit pas même à la valeur la plus favorable, stats par
    niveau à son niveau, bonus de dégâts par Force, « One-Hand Damage » d'une arme à deux mains pour un Barbare
    seulement ; sans personnage : inchangé (documentation du jeu). Attributs du personnage : ses totaux (Force 42 de la
    feuille en jeu, 39 avec la seule lecture de la sauvegarde)."""
    from mxl_save import load_character
    from mxl_catalog_tooltip import catalog_tooltip, set_bonus_lines
    from mxl_char_stats import with_total_attributes
    from mxl_theme import RED
    data = ctx.data
    char = load_character(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'character_sheet',
                                       'Nekratall.d2s'), data)
    ctx.expect('Force lue dans la sauvegarde', char['strength'], 39)
    with_total_attributes(char, data)
    ctx.expect('attributs totaux', (char['strength'], char['dexterity']), (42, 42))
    lines = lambda name, ch: [(l[0][0], ''.join(t for _, t in l)) for l in catalog_tooltip(entry(data, name=name), data, char=ch)]
    athulua = lines("Athulua's Blessing", char)
    ctx.expect('exigences non remplies en rouge', [t for c, t in athulua if c == RED],
               ['(Amazon Only)', 'Required Level: 100', 'Required Strength: 525'])
    jared = [t for _, t in lines("Jared's Fragmentor", char)]
    ctx.expect('Jared : Force 41 remplie (42), pas de « One-Hand Damage » pour un Nécromancien, bonus de Force',
               ([t for c, t in lines("Jared's Fragmentor", char) if c == RED], any('One-Hand' in t for t in jared),
                'Strength Damage Bonus: 6%' in jared), ([], False, True))
    ctx.expect('stat par niveau au niveau 24', '3% Chance of Crushing Blow (Based on Character Level)' in
               [t for _, t in lines('The Xiphos', char)], True)
    ctx.expect('sans personnage : inchangé', [t for _, t in lines("Jared's Fragmentor", None)][2:4],
               ['One-Hand Damage: (7 - 8) to (12 - 15)', 'Two-Hand Damage: (9 - 11) to (15 - 18)'])
    with_char = set_bonus_lines(0, data, char)
    ctx.check(bool(with_char) and len(with_char) == len(set_bonus_lines(0, data)), 'bonus du set avec le personnage')


@case('Bibliothèque', "compétence d'une chance de lancer ou de charges : explication sans coût en mana (jamais payé en jeu)")
def cast_only_no_mana(ctx):
    """D2Game.dll : une chance de lancer passe par 0x6fd114f0, qui appelle 0x6fcbfd00 avec son dernier paramètre à 1
    (sans contrôle ni retrait de mana). Jared's Fragmentor : Spike Nova (chance de lancer seule) sans « Mana Cost » ;
    Auto Da Fe : Flamefront (« +x to ») avec ; une compétence aussi donnée autrement garde son coût."""
    from mxl_catalog_tooltip import CatalogContext
    from mxl_skills import cast_only_skills, skill_tooltip
    import stat_ids as S
    data = ctx.data
    jared = CatalogContext(entry(data, 'unique:375'), data)
    ctx.expect('chance de lancer seule', cast_only_skills(jared.lo, data), {'Spike Nova'})
    ada = CatalogContext(entry(data, name='Auto Da Fe'), data)
    ctx.expect('« +x to » : pas concerné', cast_only_skills(ada.lo, data), set())
    nova = next(s for s in jared.lo if s['id'] in S.CHANCE_TO_CAST)
    both = [nova, {'id': S.SINGLE_SKILL, 'param': nova['param'] >> 6, 'value': 1}]
    ctx.expect('aussi donnée par « +x to » : coût gardé', cast_only_skills(both, data), set())
    texts = lambda mana: [t for _, t in skill_tooltip(523, 3, 4, data, mana=mana)]
    ctx.expect('ligne du coût retirée', (texts(True)[-1], any('Mana' in t for t in texts(False))), ('Mana Cost: 8', False))
    # charges : une charge retirée au lieu de la mana (D2Sigma.dll 0x100a1c20 -> D2Game.dll 0x6fcbf4a0)
    staff = CatalogContext(entry(data, name='Malus Domestica'), data)
    ctx.expect('charges seules', cast_only_skills(staff.lo, data), {'Inner Fire'})
    charge = next(s for s in staff.lo if s['id'] == S.CHARGES)
    ctx.expect('charges et « +x to » : coût gardé',
               cast_only_skills([charge, {'id': S.SINGLE_SKILL, 'param': charge['param'] >> 6, 'value': 1}], data), set())


@case('Bibliothèque', "compétences sans fiche dans le jeu : tir de projectiles d'Arrow, Knife Throw, Thunder Hammer et Javelin (srvdo 8)")
def arrow_shot(ctx):
    """Arrow (609, chances de lancer de 16 objets) : srvdo 8 = tir de projectiles (D2Game.dll 0x6fc6d420), clc1 = 1
    flèche, srvmissileA = projectile 0 « arrow », part des dégâts de l'arme 128 / 128 (missiles.bin @0x12D) ; niveau
    sans effet. Thunder Wave (pas encore vérifiée) : inchangée."""
    from mxl_skills import skill_tooltip
    data = ctx.data
    texts = lambda sid, lo, hi: [t for _, t in skill_tooltip(sid, lo, hi, data)][3:]
    ctx.expect('Arrow niveaux 1 à 50', texts(609, 1, 50),
               ['Fires 1 Arrow', '100% Weapon Damage', '(no description in game data)'])
    ctx.expect('Thunder Wave (décrite depuis : test thunder_wave)', texts(606, 30, 30)[0], 'Throws 31 Hammers')
    # Knife Throw (591, 6 objets) : même tir, projectile 36 à 128 / 128 des dégâts de l'arme
    ctx.expect('Knife Throw niveaux 1 à 35', texts(591, 1, 35),
               ['Throws 1 Knife', '100% Weapon Damage', '(no description in game data)'])
    # Thunder Hammer (605, 6 objets) : 1 projectile 774 (explosion 328 visuelle), dégâts physiques de la compétence ;
    # part de l'arme : celle de la compétence (78 / 128 = 60 %) avant celle du projectile (48), D2Sigma.dll 0x1008a696
    # Javelin (588, 4 objets) : même tir, projectile 1 à 128 / 128 des dégâts de l'arme
    ctx.expect('Javelin niveaux 1 à 5', texts(588, 1, 5),
               ['Throws 1 Javelin', '100% Weapon Damage', '(no description in game data)'])
    ctx.expect('Thunder Hammer sans personnage', texts(605, 10, 50),
               ['Throws 1 Hammer', 'Physical Damage: varies by character', '60% Weapon Damage', '(no description in game data)'])
    from mxl_save import load_character
    nek = load_character(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'character_sheet',
                                      'Nekratall.d2s'), data)
    ctx.expect('Thunder Hammer avec Nekratall', [t for _, t in skill_tooltip(605, 10, 50, data, nek)][3:5],
               ['Throws 1 Hammer', 'Physical Damage: 9-14 to 30-46'])


@case('Bibliothèque', "compétence sans fiche dans le jeu : bonus temporaire de Celerity (srvdo 25)")
def celerity_buff(ctx):
    """Celerity (701, 4 objets) : srvdo 25 (D2Game.dll 0x6fc62570) pose l'état 219 avec les stats d'aura : Movement Speed
    min(ln34, 75) = 25 + 5 par niveau au-delà du 1er, au plus 75 ; Cannot Be Frozen ; durée ln12 × (100 + stat 409 « Skill
    Duration ») / 100 = 250 images (10 s) sans bonus."""
    from mxl_skills import skill_tooltip
    from mxl_save import load_character
    data = ctx.data
    nek = load_character(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'character_sheet',
                                      'Nekratall.d2s'), data)
    texts = lambda lo, hi, ch: [t for _, t in skill_tooltip(701, lo, hi, data, ch)][3:]
    ctx.expect('niveaux 2 à 20, sans personnage', texts(2, 20, None),
               ['+(30 to 75)% Movement Speed', 'Cannot Be Frozen', 'Duration: varies by character',
                '(no description in game data)'])
    ctx.expect('niveau 1, Nekratall', texts(1, 1, nek),
               ['+25% Movement Speed', 'Cannot Be Frozen', 'Duration: 10 seconds', '(no description in game data)'])


@case('Bibliothèque', "compétence sans fiche dans le jeu : soin instantané de Life Spark (srvdo 18)")
def life_spark_heal(ctx):
    """Life Spark (579, 4 objets) : srvdo 18 (D2Game.dll 0x6fc628f0) pose l'état 444 pendant 1 image avec Life
    Regenerated (stat 74, 256es de vie par image) = vie max × niveau / 100 × clc1(2908) / 100 (100 au repos) : rend
    niveau % de la vie maximale. Nekratall, 874 de vie : 26 au niveau 3, 87 au niveau 10."""
    from mxl_skills import skill_tooltip
    from mxl_save import load_character
    data = ctx.data
    nek = load_character(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'character_sheet',
                                      'Nekratall.d2s'), data)
    texts = lambda ch: [t for _, t in skill_tooltip(579, 3, 10, data, ch)][3:]
    ctx.expect('sans personnage', texts(None), ['Heals (3 to 10)% of Maximum Life', '(no description in game data)'])
    ctx.expect('Nekratall', texts(nek), ['Heals 26 to 87 Life (3 to 10% of Maximum Life)', '(no description in game data)'])


@case('Bibliothèque', "compétence sans fiche dans le jeu : projectile tournant de Flurry of Javelins (srvdo 28, srvmove 15)")
def flurry_spin(ctx):
    """Flurry of Javelins (490, 3 objets) : srvdo 28 lance le projectile 840 (D2Game.dll 0x6fc62d90) ; son déplacement
    15 (0x6fc60ca0) libère un javelot 931 toutes les 3 images (param1), direction + 19/64, pendant 20 + 3 × niveau
    images (0x6fc8fc85) ; javelot à 128 / 128 des dégâts de l'arme, explosion 966 visuelle ; un javelot dès l'image 0
    (déduit de Corrupted Vines) : 32 / 3 -> 11 au niveau 4, 92 / 3 -> 31 au niveau 24."""
    from mxl_skills import skill_tooltip
    data = ctx.data
    ctx.expect('niveaux 4 à 24', [t for _, t in skill_tooltip(490, 4, 24, data)][3:],
               ['Throws 1 Javelin every 0.12 seconds, in a spiral (11 to 31 Javelins)', 'Duration: 1.2 to 3.6 seconds',
                '100% Weapon Damage',
                '(no description in game data)'])


@case('Bibliothèque', "compétence sans fiche dans le jeu : nova de Javelin Nova (srvdo 22)")
def javelin_nova(ctx):
    """Javelin Nova (625, 3 objets) : srvdo 22 (D2Game.dll 0x6fc63aa0 -> 0x6fcc2800) lance 64 projectiles 1701, un par
    direction ; vitesse 30 et portée 25 fixes (le niveau ne change que la vitesse, ici sans bonus) ; part de l'arme du
    projectile, 96 / 128 = 75 %."""
    from mxl_skills import skill_tooltip
    ctx.expect('niveaux 1 à 13', [t for _, t in skill_tooltip(625, 1, 13, ctx.data)][3:],
               ['Throws 64 Javelins in a ring', '75% Weapon Damage', '(no description in game data)'])


@case('Bibliothèque', "compétences sans fiche dans le jeu : malédictions Rust Storm et Amplify Damage (srvdo 30)")
def curses(ctx):
    """srvdo 30 (D2Game.dll 0x6fc705d0) : état @0x82 sur les ennemis dans le rayon @0x64 (yards du format 19), durée @0x60
    avec Skill Duration, stats aurastat. Rust Storm : rayon 20 (13.3 yards), −40 % de défense totale (stat 182 : %
    de la défense totale appliqué en dernier, D2Common.dll 10672),
    −8 % de résistance physique ; Amplify Damage : rayon 4 (2.6 yards), −20 % ; 200 images (8 s)."""
    from mxl_skills import skill_tooltip
    from mxl_save import load_character
    data = ctx.data
    nek = load_character(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'character_sheet',
                                      'Nekratall.d2s'), data)
    texts = lambda sid, lo, hi, ch: [t for _, t in skill_tooltip(sid, lo, hi, data, ch)][3:]
    ctx.expect('Rust Storm, Nekratall', texts(638, 6, 10, nek),
               ['Curses enemies within 13.3 yards', 'Total Defense -40%', 'Physical Resist -8%', 'Duration: 8 seconds',
                '(no description in game data)'])
    ctx.expect('Amplify Damage sans personnage', texts(66, 15, 15, None),
               ['Curses enemies within 2.6 yards', 'Physical Resist -20%', 'Duration: varies by character',
                '(no description in game data)'])


@case('Bibliothèque', "compétence sans fiche dans le jeu : chaîne d'anneaux de Corrupted Vines (srvdo 28, impacts 29)")
def corrupted_vines(ctx):
    """Corrupted Vines (567, 2 objets) : srvdo 28 pose 3687 à la cible ; 3687 -> 3688 -> 3689 -> 3690 (déplacement 15 :
    successeur à l'image 0), chacun finissant par l'impact 29 (hitpar1 5, 7, 10, 12) : anneaux de 13, 10, 7 et 6 lianes
    3691 ; part de l'arme de la compétence 255 / 128 = 199 %."""
    from mxl_skills import skill_tooltip
    ctx.expect('niveau 1', [t for _, t in skill_tooltip(567, 1, 1, ctx.data)][3:],
               ['Releases 4 rings of Vines on the target: 13, 10, 7 and 6 (36 in all)', '199% Weapon Damage',
                '(no description in game data)'])


@case('Bibliothèque', "compétence sans fiche dans le jeu : tourniquets d'Athulua's Wrath (srvmissile, impacts 29 / 36)")
def athulua_wrath(ctx):
    """Athulua's Wrath (754, Valkyrie's Prime) : pas de srvdo, srvmissile 2132 sur le personnage (D2Game.dll
    0x6fcc1b3a) ; 2132 -> 2124 (impact 29, hitpar1 64 : 1) -> 2125 -> 2126 -> 2130 (impact 36 : relais en fin de vie) ;
    tourniquets 2127, 2128, 2129 (créés une fois, déplacement 15 de param1 99) et 2130 : un projectile 2131 par image
    pendant 300 + 3 × niveau images ; 60 % des dégâts de l'arme (part de la compétence)."""
    from mxl_skills import skill_tooltip
    ctx.expect('niveau 1', [t for _, t in skill_tooltip(754, 1, 1, ctx.data)][3:],
               ['Places 4 spinning turrets where you stand',
                'Each fires 1 projectile every 0.04 seconds for 12.1 seconds (1212 in all)', '60% Weapon Damage',
                '(no description in game data)'])


@case('Bibliothèque', "compétence sans fiche dans le jeu : anneau à retardement de Devastation (srvdo 8, impact 29)")
def devastation(ctx):
    """Devastation (612, Giyua's Grace) : tir de 1951 (immobile, sur le personnage) qui crée 1955 ; 1955 vit 93 images
    puis l'impact 29 (hitpar1 1) libère 64 projectiles de feu 1954 (collision 3, 128 / 128 des dégâts de l'arme,
    fonction de dégâts 1 : formule 100 -> 100 % du physique en feu) ; 1952 -> 16 projectiles 1953 sans collision."""
    from mxl_skills import skill_tooltip
    ctx.expect('niveau 1', [t for _, t in skill_tooltip(612, 1, 1, ctx.data)][3:],
               ['After 3.7 seconds, releases 64 projectiles in a ring where you stood', '100% Weapon Damage',
                '100% of Physical Damage converted to Fire', '(no description in game data)'])


@case('Bibliothèque', "compétence sans fiche dans le jeu : sol embrasé de Fire Splash (srvdo 28, impact 9)")
def fire_splash(ctx):
    """Fire Splash (489, Hell Forge Hammer) : srvdo 28 pose 717 à la cible ; impact 9 (D2Game.dll 0x6fc5e0b0) : une case
    de feu 716 par sous-case du disque de rayon hitpar1 5 (3.3 yards, 0x6fc5d450), durée = formule d'impact (25 images) ;
    dégâts de feu de la compétence par image (hitshift 0) : « par seconde » comme un mur de feu (format 26).
    Nekratall, niveau 2 : 54-109 / 256 par image -> 5-10 par seconde."""
    from mxl_skills import skill_tooltip
    from mxl_save import load_character
    data = ctx.data
    nek = load_character(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'character_sheet',
                                      'Nekratall.d2s'), data)
    texts = lambda ch: [t for _, t in skill_tooltip(489, 2, 2, data, ch)][3:]
    ctx.expect('Nekratall', texts(nek), ['Sets the ground ablaze within 3.3 yards of the target for 1 second',
                                         'Average Fire Damage: 5-10 per second', '(no description in game data)'])
    ctx.expect('sans personnage', texts(None)[1], 'Average Fire Damage: varies by character')


@case('Bibliothèque', "compétence sans fiche dans le jeu : bonus offert de Gift of Celerity (srvdo 68 de Median XL)")
def gift_of_celerity(ctx):
    """Gift of Celerity (704, Celestial Sigil) : srvdo 68 (D2Sigma.dll 0x100a9f50) pose l'état 219 de Celerity sur le
    lanceur (0x100ae9b0) et lance le projectile 817, dont l'impact 18 (D2Game.dll 0x6fc5ea60) pose le même état sur un
    allié touché (test d'alliance 0x6fd00570) ; niveau 5 : Movement Speed min(25 + 4 × 5, 75) = 45."""
    from mxl_skills import skill_tooltip
    ctx.expect('niveau 5', [t for _, t in skill_tooltip(704, 5, 5, ctx.data)][3:],
               ['On you, and on an ally hit by the projectile sent at the target:', '+45% Movement Speed',
                'Cannot Be Frozen', 'Duration: varies by character', '(no description in game data)'])


@case('Bibliothèque', "compétence sans fiche dans le jeu : soin offert de Gift of Inner Fire (srvdo 68 de Median XL)")
def gift_of_inner_fire(ctx):
    """Gift of Inner Fire (705, Berserrker) : même fonction que Gift of Celerity (lanceur et allié touché) ; état 193,
    durée (50 − dm12) × (100 + Skill Duration) / 100 images, Life Regenerated = vie max / (50 − dm12) : toute la vie
    maximale sur la durée de base (niveau 2 : dm12 = 12, 38 images = 1.5 s). Nekratall : 874 de vie."""
    from mxl_skills import skill_tooltip
    from mxl_save import load_character
    data = ctx.data
    nek = load_character(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'character_sheet',
                                      'Nekratall.d2s'), data)
    texts = lambda ch: [t for _, t in skill_tooltip(705, 2, 2, data, ch)][3:]
    ctx.expect('sans personnage', texts(None)[1], 'Heals 100% of Maximum Life over 1.5 seconds')
    ctx.expect('Nekratall', texts(nek)[1], 'Heals 874 Life (100% of Maximum Life) over 1.5 seconds')


@case('Bibliothèque', "compétence sans fiche dans le jeu : tourniquet de Punisher Barrage (tir srvdo 8)")
def punisher_barrage(ctx):
    """Punisher Barrage (448, Warshrike) : tir srvdo 8 de clc1 = 1 projectile 2880 immobile (sur le personnage), tourniquet
    (déplacement 15, param1 1, param2 19) qui tire un projectile 2881 par image pendant 75 images ; 2881 lent, collision
    3, explosion 964 visuelle ; part de l'arme 0 pour la compétence et le projectile : 100 % ; niveau sans effet."""
    from mxl_skills import skill_tooltip
    ctx.expect('niveau 40', [t for _, t in skill_tooltip(448, 40, 40, ctx.data)][3:],
               ['Places a spinning turret where you stand',
                'It fires 1 projectile every 0.04 seconds for 3 seconds (75 in all)', '100% Weapon Damage',
                '(no description in game data)'])


@case('Bibliothèque', "compétence sans fiche dans le jeu : lame qui éclate de Shatterblade (tir srvdo 8, impact 20)")
def shatterblade(ctx):
    """Shatterblade (462, The Xiphos) : tir srvdo 8 d'une lame 2182 sans collision (vitesse 10, 50 images) ; en fin de
    vie, l'impact 20 (D2Game.dll 0x6fc5dd60) cherche les ennemis dans un rayon hitpar1 = 30 (20 yards) et envoie vers
    eux jusqu'à hitpar2 = 1 éclat 2183 (0x6fc5cd00) ; éclat à 48 / 128 = 37 % des dégâts de l'arme."""
    from mxl_skills import skill_tooltip
    ctx.expect('niveau 5', [t for _, t in skill_tooltip(462, 5, 5, ctx.data)][3:],
               ['Throws a blade that shatters after 2 seconds, sending 1 shard at an enemy within 20 yards',
                '37% Weapon Damage', '(no description in game data)'])


@case('Bibliothèque', "compétence sans fiche dans le jeu : anneaux de Spike Rush (srvdo 17, relais 29 / 15)")
def spike_rush(ctx):
    """Spike Rush (378, Iron Shard) : srvdo 17 (D2Game.dll 0x6fc63b60) pose 3259 sur le personnage ; 13 images puis
    impact 29 (hitpar1 64 : 1) -> tourniquet 3260 (param1 1, 2 images : 2 relais 3261) -> impact 29 (hitpar1 1) : 2
    anneaux de 64 pointes 3258 (images 14 et 15) ; part de l'arme de la compétence 192 / 128 = 150 %."""
    from mxl_skills import skill_tooltip
    ctx.expect('niveau 10', [t for _, t in skill_tooltip(378, 10, 10, ctx.data)][3:],
               ['After 0.5 seconds, releases 2 rings of 64 projectiles around you (128 in all)', '150% Weapon Damage',
                '(no description in game data)'])


@case('Bibliothèque', "compétence sans fiche dans le jeu : marteaux de Thunder Wave (srvdo 8)")
def thunder_wave(ctx):
    """Thunder Wave (606, Akarat's Trek) : comme Thunder Hammer (tir srvdo 8, projectile 774, dégâts physiques de la
    compétence), mais clc1 = 1 + niveau marteaux (31 au niveau 30) et 144 / 128 = 112 % des dégâts de l'arme."""
    from mxl_skills import skill_tooltip
    ctx.expect('niveau 30', [t for _, t in skill_tooltip(606, 30, 30, ctx.data)][3:],
               ['Throws 31 Hammers', 'Physical Damage: varies by character', '112% Weapon Damage',
                '(no description in game data)'])


@case('Bibliothèque', "réanimation (propriété de fonction 12) : chance fixe, pas de plage ni de curseur")
def reanimate_fixed_chance(ctx):
    """Propriété « Reanimate as » (fonction 12) : param du mod = chance (fixe), min / max = monstres possibles (tirés au
    hasard). ✅ Bonefiend : 2 %, monstres 3374 à 3381 ; la plage de la valeur n'est pas 3374-3381 (qualité -7991 %)."""
    from mxl_rules import mod_ranges
    data = ctx.data
    prop = next(m['prop'] for m in __import__('mxl_rules').table_row(entry(data, name='Bonefiend')['key'], data)['mods']
                if data.prop_func[m['prop']] == 12)
    ctx.expect('valeur fixe', list(mod_ranges(data, prop, 2, 3374, 3381).values()), [(2, 2)])


@case('Bibliothèque', "curseur de stats liées sur plusieurs lignes : titre complet (Athame, pénétrations feu et poison)")
def linked_stats_heading(ctx):
    """Une propriété qui donne plusieurs stats avec un seul tirage (Athame : propriété 197, stats 333 et 336) : un seul
    curseur pour les deux ; son titre nomme toutes les lignes de l'infobulle qu'il modifie."""
    from mxl_edit import _heading
    data = ctx.data
    it = dict(code='144 ', quality='unique', stats=[{'id': 333, 'param': None, 'value': 8},
                                                   {'id': 336, 'param': None, 'value': 8}])
    ctx.expect('titre', _heading(it, (333, 336), data, None),
               '-8% to Enemy Fire Resistance\n-8% to Enemy Poison Resistance')


@case('Bibliothèque', "classes de trésor lues, montée de palier, plages de chute (monstres ordinaires et élites)")
def drop_ranges(ctx):
    from mxl_drop import entry_drop_lines, item_drop_lines, reach, _upgrade
    from common import CONTAINERS
    data = ctx.data
    tcs = data.treasure_classes
    index = {t['name']: k for k, t in enumerate(tcs)}
    h = tcs[index['H Equip 1']]
    ctx.expect('« H Equip 1 »', (h['level'], h['group'], h['items'][:4]),
               (93, 1, [('weap93', 19), ('armo93', 19), ('weap90', 76), ('armo90', 76)]))
    ctx.expect('montée de palier (« Normal » au niveau 85, 92, 120)',
               [tcs[_upgrade(tcs, index['Normal'], lvl)]['name'] for lvl in (85, 92, 120)],
               ['NM Normal 4', 'NM Normal 5', 'H Normal 1'])
    ctx.expect('groupes atteignables', [reach(data)[0].get(g) for g in ('weap12', 'weap33', 'weap51', 'weap78')],
               [(10, 50), (31, 76), (51, 89), (77, 150)])
    lines = lambda k: entry_drop_lines(entry(data, k), data)
    ctx.expect("Jared's Fragmentor (1) à (4), Durandal (sacré)",
               [lines(k) for k in ('unique:375', 'unique:376', 'unique:377', 'unique:378', 'unique:1473')],
               [['Drops from area level 10 to 50'], ['Drops from area level 31 to 76'],
                ['Drops from area level 51 to 89'], ['Drops from area level 77+'],
                ['Drops from area level 105+ (Hell only)']])
    ctx.expect('minimum relevé par le groupe de bases (Queen of Glass (1) : unique 29, groupe dès 31)',
               lines(entry(data, name='Queen of Glass')['key']), ['Drops from area level 31 to 50'])
    ctx.expect('aucune classe de trésor, sources spéciales, bijou',
               [lines(entry(data, name=n)['key'])[:1] for n in ("Valkyrie's Prime", "Lylia's Curse", 'Fren Slairea')],
               [['Does not drop from monsters'], ['Only from special monsters or areas'], ['Drops from area level 40+']])
    relic = next(e for e in cat(data) if e['category'] == 'relic')
    ctx.expect('relique : seulement par « World Drops »', lines(relic['key'])[:1],
               ['Drops from area level 1+ (world drop, extremely rare)'])
    items = parse_stash(CONTAINERS, data)
    sup = next(i for i in items if i.get('quality') == 'superior' and i['code'] == '277 ')
    magic = next(i for i in items if i.get('quality') == 'magic')
    ctx.expect('supérieur Pike (2) (base de niveau 36 : groupe weap36), magique (rien)',
               (item_drop_lines(sup, data), item_drop_lines(magic, data)), (['Drops from area level 36 to 76'], []))


@case('Bibliothèque', "unique sur une base partagée : part parmi les uniques de sa base, par tranche (rareté)")
def drop_unique_shares(ctx):
    from mxl_drop import entry_drop_lines
    data = ctx.data
    share = lambda n: entry_drop_lines(entry(data, name=n), data)[1:]
    ctx.expect('Ancient Armor (Sacred) : SU 250, SSU 49, SSSU 1',
               [share(n) for n in ('Silks of the Victor', 'Khazra Plate', "Tyrael's Might")],
               [['Share among uniques of this base: 100% (105-119) · 83.6% (120-129) · 83.3% (130+)'],
                ['Share among uniques of this base: 16.4% (120-129) · 16.3% (130+)'],
                ['Share among uniques of this base: 0.3% (area level 130+)']])
    ctx.expect('deux SSU de même niveau (Angel Star (Sacred))', share('The Angiris Star'),
               ['Share among uniques of this base: 15% (area level 120+)'])
    ctx.expect('toutes les bases partagées : fusion des tranches au même pourcentage affiché, abréviation',
               [share(n) for n in ('The Tesseract', 'Wishmaster', 'Hangman', 'The Seal of Kharos')],
               [['Share among uniques of this base: 2.8% (105-119) · 2.6% (120+)'],
                ['Share among uniques of this base: 0.6% (1-19) · 0.5% (20-39) · 0.4% (40+)'],
                ['Share among uniques of this base: 78.9% (1-9) · 65.9% (10-39) · 32.8% (40-59) · … · 15.8% (120+)'],
                ['Share among uniques of this base: 2.7% (80-104) · 2.4% (105-119) · 2.2% (120+)']])
    ctx.expect('sources spéciales : niveau d\'objet', share("Lylia's Curse"),
               ['Share among uniques of this base: 25% (item level 1+)'])
    ctx.expect('ne tombe jamais : pas de part', share("Valkyrie's Prime"), [])
    alone = next(e for e in cat(data) if e['kind'] == 'unique' and e['base'].endswith('(Sacred)') and e['droppable']
                 and sum(1 for u in data.uniques if u.get('code') == e['code'] and u.get('rarity', 0) > 0) == 1)
    ctx.expect('seul sur sa base, tiers 4 : pas de part', (share(alone['name']) if alone['name'] else None,
                                                          entry_drop_lines(entry(data, 'unique:378'), data)[1:]), ([], []))
