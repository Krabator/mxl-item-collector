"""Tests : infobulles du catalogue comparées à toutes celles d'une page de la documentation officielle. Toute
différence fait échouer le test, sauf les différences connues (KNOWN) : différences du site par rapport au jeu
(gardées volontairement) et points à éclaircir (capture en jeu nécessaire).

La page est prise sur Internet et gardée en cache (tests/cache/docs/, hors du dépôt) avec la version du jeu de data/ :
retéléchargée quand la version change (nouvelle version du mod : le site est comparé aux nouvelles tables),
ou à la demande (MXL_REFRESH_DOCS, option --refresh-docs de run_tests.py) ; sans connexion : copie en cache, sinon
test non lancé."""
import os, re, json, time, urllib.request
from common import case, HERE, ROOT
from doc_pages import Page, compare
from mxl_install import installed
from mxl_library import catalog
from mxl_catalog_tooltip import catalog_tooltip, catalog_name, CatalogContext


def title(e, data):
    """Nombre de lignes du titre de l'infobulle d'une entrée (nom propre et objet de base, sans répétition)."""
    return len(catalog_name(CatalogContext(e, data)))

# (raison, catégorie, motif du détail, objets concernés ou None pour tous)
SEPARATE = "site : auto-affixe de la base et affixe de l'unique sur deux lignes (le jeu les additionne)"
CAPTURE = "à éclaircir : capture en jeu nécessaire"
KNOWN = [
    ("site : « Chance to Block: Class % » (blocage selon la classe du personnage)", 'manquante', r'Class %', None),
    ("site : poison en « a-b » sans plages", 'manquante', r'Poison Damage over', None),
    ("site : poison en « a-b » sans plages", 'en trop', r'Poison Damage over', None),
    ("site : régénération par niveau arrondie", 'valeur', r'Life Regenerated per Second \(Based on', None),
    (SEPARATE, 'valeur', r'(Fire|Lightning) Damage', ["Compass of Souls", "Ord Rekar's Testament"]),
    (SEPARATE, 'manquante', r'(Fire|Lightning) Damage', ["Compass of Souls", "Ord Rekar's Testament"]),
    ("site : « (1/2 chance to appear) »", 'manquante', r'\(1/2 chance to appear\)', None),
    ("site : « (1/2 chance to appear) »", 'en trop', r'^Cannot Be Frozen$', ["Candlewake"]),
    ("site : variantes (une par élément) réunies en une", 'manquante', r'\[Random Elemental\]', ["Zann Esu's Stone"]),
    ("site : variantes (une par élément) réunies en une", 'en trop', r'Maximum \w+ Resist', ["Zann Esu's Stone"]),
    ("site : aucune des versions du jeu (page pas à jour)", r'.*', r'', ["Darkfeast"]),
    ("site : « Reduced by 0 seconds »", r'manquante|en trop', r'Colosseum Cooldown', ["Signet of the Gladiator"]),
    ("site : régénération 112,5 arrondie à 113 ; le jeu tronque (D2Sigma.dll 0x10077800 : valeur / 10 vers zéro, au "
     "moins 1) : 112", 'valeur', r'Life Regenerated', ["Athulua's Blessing"]),
    ("site : textes différents selon le signe réunis en une plage", r'manquante|en trop', r'Stamina Drain', ["Hellrush"]),
    ("site : niveau requis de l'unique seul ; le jeu prend le plus grand avec celui de l'objet de base (D2Common.dll "
     "0x6fd7652d)", 'valeur', r'Required Level', ["Mendeln's Companion"]),
    ("site : couleur d'un texte de descfunc 31 différente du jeu (D2Sigma.dll 0x10077720 : couleur = valeur − 1 ; "
     "King of Ents valeur 2 -> rouge, Void-Touched valeur 6 -> gris)", 'couleur', r'', ["The King of Ents", "Void-Touched"]),
]
# différences propres à une page : (raison, catégorie, motif, objets concernés ou None), comme KNOWN
FUNC17 = "site : propriété de fonction 17 (« param seul » dans Diablo II) lue dans min / max au lieu de param"
KNOWN_SETS = [
    (FUNC17, 'valeur', r'Additional Strength Damage Bonus', ["Nature's Wrath"]),
]
# bonus des sets (cellules de résumé de la page des sets), comparés par set
KNOWN_SET_BONUS = [
    (FUNC17, r'manquante|en trop', r'Chance of Crushing Blow', ["Curse of the Zakarum"]),
]
# site : « +x to Maximum Damage » placé avant l'Enhanced Damage ; en jeu, après Crushing Blow (✅ capture de la
# Jared's Fragmentor) : place non comparée
ORDER_IGNORE = r'to (Maximum|Minimum) Damage$'
_catalog = {}
DOCS_URL = 'https://docs.median-xl.com/doc/items/'
CACHE = os.path.join(HERE, 'cache', 'docs')


def page_html(ctx, name):
    """HTML de la page docs.median-xl.com/doc/items/<name> : copie en cache si elle a été téléchargée pour la version du
    jeu de data/, sinon téléchargée (et mise en cache) ; None si ni réseau ni copie (le test n'est pas lancé)."""
    version = (installed(os.path.join(ROOT, 'data')) or {}).get('version')
    path, meta_path = os.path.join(CACHE, name + '.html'), os.path.join(CACHE, name + '.json')
    meta = json.load(open(meta_path, encoding='utf-8')) if os.path.exists(meta_path) else {}
    fresh = os.path.exists(path) and meta.get('version') == version and not os.environ.get('MXL_REFRESH_DOCS')
    if not fresh:
        try:
            req = urllib.request.Request(DOCS_URL + name, headers={'User-Agent': 'MXL item editor tests'})
            html = urllib.request.urlopen(req, timeout=30).read().decode('utf-8')
            os.makedirs(CACHE, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html)
            meta = dict(version=version, date=time.strftime('%Y-%m-%d %H:%M'))
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f)
            ctx.notes.append(f"page téléchargée pour Median XL {version}")
        except OSError as e:
            if not os.path.exists(path):
                ctx.notes.append(f'non lancé : page inaccessible ({e})')
                return None
            ctx.notes.append(f"téléchargement impossible, copie du {meta.get('date')} (Median XL {meta.get('version')})")
    return open(path, encoding='utf-8').read()


REVERSED = "choix du 30/09 : plage écrite de la moins bonne à la meilleure valeur (site : du plus petit au plus grand)"


def reversed_range(detail):
    """Vrai si un écart de valeur n'est qu'une plage écrite dans l'autre sens : « -(1 to 10) » / « -(10 to 1) »."""
    m = re.fullmatch(r'page « (.*) » / éditeur « (.*) »', detail)
    if not m:
        return False
    canon = lambda t: re.sub(r'\((-?[\d.]+) to (-?[\d.]+)\)',
                             lambda r: '(' + ' to '.join(sorted((r.group(1), r.group(2)), key=float)) + ')', t)
    return m.group(1) != m.group(2) and canon(m.group(1)) == canon(m.group(2))


def known(name, category, detail, page_known=()):
    if category == 'valeur' and reversed_range(detail):
        return REVERSED
    return next((reason for reason, cat, pattern, names in KNOWN + list(page_known)
                 if re.fullmatch(cat, category) and re.search(pattern, detail) and (names is None or name in names)), None)


def check_page(ctx, name, family, page_known=()):
    """Tous les blocs de la page retrouvés dans le catalogue et identiques, hors différences connues (leur nombre dépend
    de la version du jeu : indiqué, pas imposé). Bloc : entrée de même nom (et même objet de base / tier si la page les
    donne) ; plusieurs possibles (versions d'un même objet) : la plus proche du bloc, pas déjà prise.
    family(entrée) : entrées du catalogue que la page devrait montrer ; celles qui n'y sont pas sont indiquées en
    information (sans échec : objet hors des tirages, site en retard). page_known : différences connues propres à la
    page (même forme que KNOWN)."""
    html = page_html(ctx, name)
    if html is None:
        return
    data = ctx.data
    if 'by_name' not in _catalog:
        _catalog['by_name'] = {}
        for e in catalog(data):
            _catalog['by_name'].setdefault(e['name'], []).append(e)
    page = Page(html)
    ctx.check(page.blocks, 'aucune infobulle lue sur la page (structure du site changée ?)')
    unexpected, missing, n_known, seen = [], [], 0, set()
    for b in page.blocks:
        tier = f" T{b['tier']}" if b['tier'] else ''
        found = _catalog['by_name'].get(b['name'], [])
        if b['tier']:
            found = [e for e in found if e['base'] == f"{b['base']} ({b['tier']})"]
        elif b['base']:
            found = [e for e in found if e['base'] == b['base'] or e['base'].startswith(b['base'] + ' (')] or found
        tips = [(e, [(line[-1][0], ''.join(t for _, t in line)) for line in catalog_tooltip(e, data)][title(e, data):])
                for e in found if e['key'] not in seen]   # sans les lignes du titre (nom, objet de base)
        if not tips:
            missing.append(f"{b['name']} ({b['base']}){tier}")
            continue
        diffs = [(compare(b['lines'], ours, ORDER_IGNORE), e) for e, ours in tips]
        diff, e = min(diffs, key=lambda x: len(x[0]))
        seen.add(e['key'])
        for category, detail in diff:
            if known(b['name'], category, detail, page_known):
                n_known += 1
            else:
                unexpected.append(f"{b['name']}{tier} [{category}] {detail}")
    ctx.expect('objets absents du catalogue', missing[:5], [])
    ctx.check(not unexpected, f'{len(unexpected)} différence(s) inattendue(s) :\n    ' + '\n    '.join(unexpected[:10]))
    ctx.notes.append(f'{len(page.blocks)} infobulles comparées, {n_known} différences connues ignorées')
    absent = [f"{e['name']} ({e['base']}{'' if e['droppable'] else ', ne tombe pas'})"
              for es in _catalog['by_name'].values() for e in es if family(e) and e['key'] not in seen]
    if absent:
        ctx.notes.append(f'information : {len(absent)} dans le jeu mais pas sur le site : ' + ', '.join(absent))


@case('Documentation', 'page « Tiered Uniques » : infobulles identiques au site (tous les uniques, tiers 1 à 4)')
def tiered_uniques(ctx):
    check_page(ctx, 'tiereduniques', lambda e: e['kind'] == 'unique' and e['family'] == 'tiered')


@case('Documentation', 'page « Sacred Uniques » : infobulles identiques au site (tous les uniques Sacred)')
def sacred_uniques(ctx):
    check_page(ctx, 'sacreduniques', lambda e: e['kind'] == 'unique' and (e['base'].endswith('(Sacred)')
                                                                          or e['family'] in ('sacred', 'ssu', 'sssu')))


@case('Documentation', 'page « Sets » : infobulles identiques au site (tous les objets de set)')
def sets(ctx):
    check_page(ctx, 'sets', lambda e: e['kind'] == 'set', KNOWN_SETS)


@case('Documentation', 'page « Sets » : bonus de chaque set identiques au site (par nombre de pièces, set complet)')
def set_bonuses(ctx):
    """Cellule de résumé de chaque set (nom, pièces, « Set Bonus with n or more set items: », « … complete set: »)
    comparée aux bonus lus dans sets.bin (mxl_catalog_tooltip.set_bonus_lines), titres compris."""
    from mxl_catalog_tooltip import set_bonus_lines, set_name
    from mxl_stat_text import segments
    html = page_html(ctx, 'sets')
    if html is None:
        return
    data = ctx.data
    ids = {set_name(i, data)[0]: i for i in range(len(data.sets))}
    page = Page(html)
    ctx.check(page.sets, 'aucun résumé de set lu sur la page (structure du site changée ?)')
    unexpected, n_known = [], 0
    for s in page.sets:
        name = s['lines'][0][1]
        if name not in ids:
            unexpected.append(f'{name} : set absent de sets.bin')
            continue
        k = next((j for j, (_, t) in enumerate(s['lines']) if t.startswith('Set Bonus')), len(s['lines']))
        ours = []
        for title, lines in set_bonus_lines(ids[name], data):
            # couleur comparée : celle du dernier morceau de la ligne, comme pour les infobulles (check_page)
            ours += [('4', title)] + [(segments(c, t)[-1][0], str(t)) for c, t in lines]
        for category, detail in compare(s['lines'][k:], ours):
            if known(name, category, detail, KNOWN_SET_BONUS):
                n_known += 1
            else:
                unexpected.append(f'{name} [{category}] {detail}')
    ctx.check(not unexpected, f'{len(unexpected)} différence(s) inattendue(s) :\n    ' + '\n    '.join(unexpected[:10]))
    ctx.notes.append(f'{len(page.sets)} sets comparés, {n_known} différences connues ignorées')
