"""Construit l'exécutable Windows de l'éditeur (PyInstaller).

Usage : python build_exe.py [--with-editor] [--check]
- sans option : version publique, base seule (module mxl_editor exclu même présent) :
  dist/MXL Item Collector/MXL Item Collector.exe ;
- --with-editor : version privée, avec le module mxl_editor (édition des valeurs, copie vers le coffre) :
  dist/editor/MXL Item Collector/MXL Item Collector.exe (même nom de programme, dossier à part) ;
- exécutable en dossier (démarrage rapide, moins de fausses alertes des antivirus qu'un fichier unique), sans console ;
- icône : Horadric Cube du jeu (data/items/invbox.png, converti en .ico ; sans data/ : icône par défaut) ;
- traductions livrées dans l'exécutable ; une langue ajoutée (ou remplacée) se met dans lang/ du dossier de
  l'utilisateur, « MXL Item Collector » dans le dossier des sauvegardes du jeu (voir i18n.py, paths.py) ;
- data/ (tables et icônes extraites du jeu) n'est pas livré : extrait de l'installation de Median XL de l'utilisateur
  au premier lancement, dans %LOCALAPPDATA%\\MXL Item Collector (avec les réglages).
--check : contrôle que le module est embarqué (ou non) comme demandé, puis lance l'exécutable construit avec des dossiers temporaires (réglages, collection, sauvegardes, data/
copié) et vérifie qu'il s'ouvre, ouvre le coffre du personnage (retenu dans ses réglages) et se ferme normalement.
Prérequis : pip install pyinstaller.
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
NAME = 'MXL Item Collector'
EDITOR_MODULE = 'mxl_editor'   # module complémentaire (privé), chargé dynamiquement par mxl_ext
WITH_EDITOR = '--with-editor' in sys.argv[1:]
# seul résultat gardé : fichiers de travail de PyInstaller dans un dossier temporaire (sinon un exécutable
# intermédiaire, sans son dossier _internal, restait dans build/ et ne se lançait pas) ; version privée à part
DIST = os.path.join(ROOT, 'dist', 'editor') if WITH_EDITOR else os.path.join(ROOT, 'dist')
EXE_DIR = os.path.join(DIST, NAME)
EXE = os.path.join(EXE_DIR, NAME + '.exe')
ICON_PNG = os.path.join(ROOT, 'data', 'items', 'invbox.png')
# modules embarqués par PyInstaller mais jamais utilisés : numpy (42 Mo sur 75) et cffi ne sont que des imports
# facultatifs de Pillow (annotations de type, PyPy), yaml un reste d'analyse (07/10 : exécutable de 75 à ~30 Mo)
EXCLUDED = ('numpy', 'cffi', 'yaml')


def make_icon(work):
    """Icône .ico (plusieurs tailles) dans work depuis l'image du Horadric Cube, ou None si data/ est absent."""
    if not os.path.exists(ICON_PNG):
        return None
    from PIL import Image
    ico = os.path.join(work, 'icon.ico')
    img = Image.open(ICON_PNG).convert('RGBA')
    side = max(img.size)   # image carrée, objet centré sur fond transparent
    square = Image.new('RGBA', (side, side))
    square.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    square.resize((256, 256), Image.LANCZOS).save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                                                               (128, 128), (256, 256)])
    return ico


def build():
    import PyInstaller.__main__
    work = tempfile.mkdtemp(prefix='mxl_build_')
    try:
        ico = make_icon(work)
        args = [os.path.join(ROOT, 'mxl_gui.py'), '--name', NAME, '--onedir', '--windowed', '--noconfirm', '--clean',
                '--distpath', DIST, '--workpath', work, '--specpath', work,
                '--add-data', f"{os.path.join(ROOT, 'lang')}{os.pathsep}lang",
                '--collect-data', 'ttkbootstrap']
        for m in EXCLUDED:
            args += ['--exclude-module', m]
        if WITH_EDITOR:   # importé dynamiquement (mxl_ext) : à demander explicitement
            if not os.path.isdir(os.path.join(ROOT, EDITOR_MODULE)):
                sys.exit(f'--with-editor : dossier {EDITOR_MODULE}/ absent')
            args += ['--collect-submodules', EDITOR_MODULE]
        else:   # version publique : jamais le module, même présent dans le dossier
            args += ['--exclude-module', EDITOR_MODULE]
        if ico:
            args += ['--icon', ico]
        PyInstaller.__main__.run(args)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    old = os.path.join(ROOT, 'build')   # ancien dossier de travail (versions précédentes de ce script) : supprimé
    if os.path.isdir(os.path.join(old, NAME)):
        shutil.rmtree(old, ignore_errors=True)
    beside = os.path.join(EXE_DIR, 'lang')   # ancien dossier lang/ à côté de l'exécutable (avant le 08/10) : retiré
    shutil.rmtree(beside, ignore_errors=True)
    print(f"Exécutable ({'privé, avec' if WITH_EDITOR else 'public, sans'} {EDITOR_MODULE}) : {EXE}")


def embedded_modules():
    """Noms des modules Python embarqués dans l'exécutable (archive PYZ de PyInstaller)."""
    from PyInstaller.archive.readers import CArchiveReader
    exe = CArchiveReader(EXE)
    pyz = next(n for n in exe.toc if n.endswith('.pyz'))
    return set(exe.open_embedded_archive(pyz).toc)


def check_module():
    """Vrai si le module mxl_editor est embarqué exactement quand il est demandé (--with-editor)."""
    found = sorted(m for m in embedded_modules() if m.split('.')[0] == EDITOR_MODULE)
    ok = bool(found) == WITH_EDITOR and (not WITH_EDITOR or f'{EDITOR_MODULE}.panel' in found)
    print(f'Module {EDITOR_MODULE} :', 'OK' if ok else 'ÉCHEC', f'({len(found)} fichiers embarqués)')
    return ok


def find_game_dir():
    """Dossier d'installation de Median XL pour l'essai de l'exécutable : réglage game_dir du dossier unique de
    l'utilisateur, sinon des réglages d'avant le 08/10 (à côté du programme : pas encore repris si l'éditeur n'a pas
    été relancé), sinon MXL_GAME_DIR ; None si aucun n'est un dossier du jeu (sinon l'exécutable de l'essai le
    demanderait à l'écran, ✅ 08/10)."""
    import json
    from paths import SETTINGS_FILE, OLD_SETTINGS_FILE
    from mxl_install import is_game_dir
    candidates = []
    for path in (os.environ.get('MXL_SETTINGS'), SETTINGS_FILE, OLD_SETTINGS_FILE):
        try:
            with open(path, encoding='utf-8') as f:
                candidates.append(json.load(f).get('game_dir'))
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    candidates.append(os.environ.get('MXL_GAME_DIR'))
    return next((d for d in candidates if d and is_game_dir(d)), None)


def check():
    """Lance l'exécutable avec des dossiers temporaires ; vrai s'il s'ouvre puis se ferme normalement."""
    tmp = tempfile.mkdtemp(prefix='mxl_exe_check_')
    try:
        user, saves = os.path.join(tmp, 'user'), os.path.join(tmp, 'save')
        shutil.copytree(os.path.join(ROOT, 'data'), os.path.join(user, 'data'))   # pas de reconstruction demandée
        os.makedirs(saves)
        for ext in ('.stash', '.d2s'):
            shutil.copy2(os.path.join(ROOT, 'tests', 'fixtures', 'Nekratall' + ext), saves)
        game_dir = find_game_dir()
        if game_dir is None:   # sans dossier du jeu, l'exécutable le demanderait : essai impossible sans intervention
            print("Essai de l'exécutable : ÉCHEC (dossier du jeu introuvable : réglage game_dir ou MXL_GAME_DIR)")
            return False
        import json
        os.makedirs(user, exist_ok=True)
        with open(os.path.join(user, 'settings.json'), 'w', encoding='utf-8') as f:
            json.dump({'game_dir': game_dir, 'language': 'en'}, f)
        env = dict(os.environ, MXL_USER_DIR=user, MXL_HOME=user, MXL_SAVE_DIR=saves, MXL_EXIT_AFTER='4000',
                   MXL_LIBRARY=os.path.join(tmp, 'library.json'))
        env.pop('MXL_SETTINGS', None)
        r = subprocess.run([EXE], env=env, timeout=120)
        # coffre ouvert : personnage retenu dans les réglages du dossier de l'utilisateur (écrits par l'exécutable)
        with open(os.path.join(user, 'settings.json'), encoding='utf-8') as f:
            opened = json.load(f).get('last_character') == 'Nekratall'
        ok = r.returncode == 0 and opened
        print('Essai de l\'exécutable :', 'OK' if ok else f'ÉCHEC (code {r.returncode})')
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    build()
    if '--check' in sys.argv[1:] and not (check_module() and check()):
        sys.exit(1)
