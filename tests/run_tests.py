"""Tests de non-régression de l'éditeur : à lancer après chaque modification du code.

Usage : python tests/run_tests.py [--base] [--no-gui] [--slow] [--update] [--refresh-docs] [-k texte]
Deux campagnes : sans option, base + module mxl_editor (s'il est présent : ses cas sont dans mxl_editor/tests/,
groupes « Éditeur : … ») ; --base : base seule, module ignoré même présent (MXL_NO_EDITOR), comme la version publique.
Chaque cas est indépendant (dossier temporaire à lui ; un échec ou un plantage n'arrête pas les autres), classé par
groupe, un fichier par thème :
- test_display_writes.py : affichage (ligne de commande, infobulle, section Édition, icône et fond rouge de chaque
  objet des deux coffres de référence, en anglais et en français, comparés à tests/reference/snapshot*.txt),
  scénario d'écriture (empreinte après chaque opération, tests/reference/writes.txt), écriture sûre, fichiers abîmés ;
- test_character.py : lecture complète d'un personnage (.d2s) : rangements, mercenaire, grilles ;
- test_quality_install.py : qualité pondérée, priorités, contrôle / réparation / version d'extraction de data/ ;
- test_library.py : catalogue, infobulles du catalogue, reconnaissance, découvertes, protections de library.json,
  explications des compétences (photo de tout le catalogue : tests/reference/skill_lines.txt) ;
- test_collection.py : panneau de la collection sans interface, transfert, éthéré, départage, panne ;
- test_documentation.py : infobulles du catalogue comparées à une page entière de la documentation officielle
  (prise sur Internet, en cache par version du jeu ; --refresh-docs : retéléchargée), hors différences connues ;
- test_settings_rebuild.py : écriture sûre des réglages ; reconstruction complète de data/ depuis le jeu (lente :
  seulement avec --slow, à lancer quand l'extraction change : mxl_install, mxl_gfx, extract_data) ;
- gui_tests.py (sauf --no-gui) : interface, un processus par test (ouverture, glisser-déposer, écran Library,
  transfert…) ;
- mxl_editor/tests/ (module, sans --base) : test_editor.py (écriture des valeurs, copie, recettes bonus, droits) et
  gui_editor_tests.py (curseurs, quantité, Ethereal / Max sockets, fenêtre de copie : lancés par gui_tests.py) ;
- data/ (tables extraites du jeu) : empreinte comparée à tests/reference/data_hash.txt ; data/ ne doit jamais être
  modifié par le code.
--update réécrit les références d'affichage et d'écriture : seulement après un changement VOULU, vérifié à l'écran.
-k texte : seulement les cas dont le titre ou le groupe contient ce texte. --slow : cas lents compris.
Les fichiers de référence ne sont jamais modifiés (copies dans un dossier temporaire).
"""
import sys, os, hashlib
if '--base' in sys.argv:   # base seule : module mxl_editor ignoré (aussi par les tests d'interface, même variable)
    os.environ['MXL_NO_EDITOR'] = '1'
from common import case, gui_case, run_case, CASES, GUI_GROUPS, ROOT
import importlib
from mxl_data import Data
from mxl_ext import editor

for _module in ('test_display_writes', 'test_character', 'test_quality_install', 'test_settings_rebuild', 'test_library',
                'test_collection', 'test_documentation'):
    importlib.import_module(_module)   # chaque fichier enregistre ses cas (@case)
GUI_TESTS = ('smoke', 'drag', 'library', 'transfer', 'shared', 'xfer', 'cube', 'inventory', 'bag', 'nocube')
for _test in GUI_TESTS:
    case('Interface', _test)(gui_case(_test))
EDITOR_TESTS = os.path.join(ROOT, 'mxl_editor', 'tests')
if editor() is not None and os.path.isdir(EDITOR_TESTS):   # module présent et pris en compte : ses cas après
    sys.path.insert(0, EDITOR_TESTS)
    importlib.import_module('test_editor')


def data_hash():
    """Empreinte de chaque fichier de data/ : « md5  chemin » par ligne, triée par chemin."""
    base = os.path.join(ROOT, 'data')
    lines = []
    for d, _, files in os.walk(base):
        for f in files:
            if d == base and f == 'install.json':   # empreinte de l'installation : écrite par une reconstruction
                continue
            full = os.path.join(d, f)
            rel = os.path.relpath(full, base).replace(os.sep, '/')
            lines.append(f"{hashlib.md5(open(full, 'rb').read()).hexdigest()}  {rel}")
    return '\n'.join(sorted(lines, key=lambda l: l.split('  ', 1)[1])) + '\n'


@case('data/', 'data/ (ne doit jamais changer)')
def data_unchanged(ctx):
    ctx.update = False   # jamais réécrite par --update : seulement après une reconstruction acceptée
    ctx.compare('data_hash.txt', data_hash())


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    args = sys.argv[1:]
    update, gui, slow = '--update' in args, '--no-gui' not in args, '--slow' in args
    if '--refresh-docs' in args:   # pages de la documentation retéléchargées (test_documentation)
        os.environ['MXL_REFRESH_DOCS'] = '1'
    only = args[args.index('-k') + 1].lower() if '-k' in args and args.index('-k') + 1 < len(args) else None
    data = Data(os.path.join(ROOT, 'data'))
    failures, group, n = [], None, 0
    for g, title, fn, is_slow in CASES:
        if (g in GUI_GROUPS and not gui) or (only and only not in f'{g} {title}'.lower()):
            continue
        if g != group:
            print(g)
            group = g
        if is_slow and not slow:
            print(f'  {title} : non lancé (--slow)')
            continue
        failures += run_case(title, fn, data, update)
        n += 1
    print()
    if failures:
        print('ÉCHECS :\n' + '\n'.join(failures))
        sys.exit(1)
    print(f"TOUT EST OK ({n} cas, {'base seule' if os.environ.get('MXL_NO_EDITOR') else 'base + module' if editor() else 'base (module absent)'})")


if __name__ == '__main__':
    main()
