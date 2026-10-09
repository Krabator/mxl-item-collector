"""Tests : écriture sûre des réglages (settings.py) ; reconstruction complète de data/ depuis le jeu (cas lent)."""
import json, os
from common import case, ROOT, GAME_DIR
import settings
from mxl_data import Data
from mxl_install import is_game_dir, rebuild_data, check_data, installed, manifest, EXTRACT_VERSION


class SettingsFile:
    """settings.PATH dirigé vers un fichier du dossier du cas le temps du test."""

    def __init__(self, ctx):
        self.path = os.path.join(ctx.tmp, 'settings.json')

    def __enter__(self):
        self.old, settings.PATH = settings.PATH, self.path
        return self.path

    def __exit__(self, *exc):
        settings.PATH = self.old


@case('Réglages', 'écriture sûre : réglages conservés, copie de la dernière version, pas de fichier temporaire laissé')
def settings_safe_write(ctx):
    with SettingsFile(ctx) as p:
        settings.put('game_dir', r'D:\jeu')
        settings.put('item_priorities', {'unique:375': {'stat:17': 3}})
        want = {'game_dir': r'D:\jeu', 'item_priorities': {'unique:375': {'stat:17': 3}}}
        ctx.expect('réglages', settings.load(), want)
        with open(p + '.bak', encoding='utf-8') as f:
            ctx.expect('copie', json.load(f), want)
        ctx.expect('fichiers', sorted(os.listdir(ctx.tmp)), ['settings.json', 'settings.json.bak'])


@case('Réglages', 'fichier abîmé : relu depuis sa copie, rien perdu, fichier abîmé gardé à part')
def settings_damaged(ctx):
    with SettingsFile(ctx) as p:
        settings.put('game_dir', r'D:\jeu')
        settings.put('item_priorities', {'unique:375': {'stat:17': 3}})
        with open(p, 'w', encoding='utf-8') as f:   # fichier tronqué (disque, modification à la main)
            f.write('{"item_priorities": {"uniq')
        broken = open(p, 'rb').read()
        ctx.expect('relu depuis la copie', settings.get('item_priorities'), {'unique:375': {'stat:17': 3}})
        settings.put('language', 'fr')   # écriture suivante : aucun réglage perdu, fichier abîmé gardé
        ctx.expect('après écriture', settings.load(), {'game_dir': r'D:\jeu', 'language': 'fr',
                                                       'item_priorities': {'unique:375': {'stat:17': 3}}})
        ctx.check(open(p + '.broken', 'rb').read() == broken, 'fichier abîmé non gardé dans settings.json.broken')


@case('Réglages', 'fichier absent : réglages vides, créés à la première écriture')
def settings_missing(ctx):
    with SettingsFile(ctx):
        ctx.expect('absent', settings.load(), {})
        settings.put('language', 'en')
        ctx.expect('créé', settings.load(), {'language': 'en'})


@case('Réglages', 'réglage renommé (editing_enabled -> edition_enabled) : valeur reprise, ancien nom retiré')
def settings_rename(ctx):
    with SettingsFile(ctx):
        settings.put('editing_enabled', True)
        settings.put('language', 'fr')
        settings.rename('editing_enabled', 'edition_enabled')
        ctx.expect('repris', settings.load(), {'edition_enabled': True, 'language': 'fr'})
        settings.put('editing_enabled', False)   # nouveau nom déjà présent : gardé, ancien retiré
        settings.rename('editing_enabled', 'edition_enabled')
        ctx.expect('nouveau gardé', settings.load(), {'edition_enabled': True, 'language': 'fr'})
        settings.rename('editing_enabled', 'edition_enabled')   # ancien absent : rien
        ctx.expect('rien à faire', settings.load(), {'edition_enabled': True, 'language': 'fr'})


@case('Réglages', 'droits : toujours inactifs sans le module mxl_editor (réglage à true compris), rien écrit')
def settings_rights(ctx):
    import mxl_ext
    from mxl_gui import App
    with SettingsFile(ctx):
        settings.put('language', 'en')
        settings.put('edition_enabled', True)
        saved = mxl_ext._editor
        try:
            mxl_ext._editor = None   # base seule
            ctx.expect('sans le module', (App.right('edition_enabled'), App.right('duplication_enabled')), (False, False))
        finally:
            mxl_ext._editor = saved
        ctx.expect('rien écrit ni retiré', settings.load(), {'language': 'en', 'edition_enabled': True})


@case('Réglages', 'module complémentaire cassé : erreur lisible pour le message au lancement ; absent : aucune (audit du 09/10)')
def editor_broken(ctx):
    import sys
    import mxl_ext
    pkg = os.path.join(ctx.tmp, 'mxl_broken_editor')
    os.makedirs(pkg)
    with open(os.path.join(pkg, '__init__.py'), 'w', encoding='utf-8') as f:
        f.write('import mxl_module_qui_n_existe_pas\n')
    saved = mxl_ext.EDITOR_MODULE, mxl_ext._editor
    no_editor = os.environ.pop('MXL_NO_EDITOR', None)   # campagne --base : module de test chargé quand même
    sys.path.insert(0, ctx.tmp)
    try:
        mxl_ext.EDITOR_MODULE, mxl_ext._editor = 'mxl_broken_editor', False
        ctx.expect('module cassé', mxl_ext.editor_error(),
                   "ModuleNotFoundError: No module named 'mxl_module_qui_n_existe_pas'")
        mxl_ext.EDITOR_MODULE, mxl_ext._editor = 'mxl_module_absent', False
        ctx.expect('module absent', (mxl_ext.editor_error(), mxl_ext.editor()), (None, None))
    finally:
        sys.path.remove(ctx.tmp)
        sys.modules.pop('mxl_broken_editor', None)
        mxl_ext.EDITOR_MODULE, mxl_ext._editor = saved
        if no_editor is not None:
            os.environ['MXL_NO_EDITOR'] = no_editor


@case('Réglages', "traductions : langues livrées + dossier lang/ de l'utilisateur (ajout, remplacement)")
def extra_languages(ctx):
    """Dossier livré (en, fr) et dossier à côté de l'exécutable (fr corrigé, nouvelle langue « xx », fichier abîmé) :
    langues réunies, fichier d'à côté prioritaire, fichier illisible ignoré (version livrée gardée)."""
    import i18n
    shipped, beside = os.path.join(ctx.tmp, 'shipped'), os.path.join(ctx.tmp, 'beside')
    for d, files in ((shipped, {'en': {'_language': 'English', 'k': 'key'}, 'fr': {'_language': 'Français', 'k': 'clé'},
                                'de': {'_language': 'Deutsch', 'k': 'Schlüssel'}}),
                     (beside, {'fr': {'_language': 'Français', 'k': 'clé corrigée'}, 'xx': {'_language': 'Xx', 'k': 'x'}})):
        os.makedirs(d)
        for code, texts in files.items():
            json.dump(texts, open(os.path.join(d, code + '.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    open(os.path.join(beside, 'de.json'), 'w').write('{abîmé')
    saved = i18n.LANG_DIRS, i18n.current()
    i18n.LANG_DIRS = [shipped, beside]
    try:
        ctx.expect('langues', i18n.available(), [('de', 'Deutsch'), ('en', 'English'), ('fr', 'Français'), ('xx', 'Xx')])
        got = []
        for code in ('fr', 'xx', 'de'):
            i18n.set_language(code, save=False)
            got.append(i18n.tr('k'))
        ctx.expect('textes', got, ['clé corrigée', 'x', 'Schlüssel'])
    finally:
        i18n.LANG_DIRS = saved[0]
        i18n.set_language(saved[1], save=False)


@case('Installation', "exécutable Windows public (build_exe.py) : sans le module, lancé, coffre ouvert, fermeture normale", slow=True)
def windows_exe(ctx):
    import importlib.util
    if importlib.util.find_spec('PyInstaller') is None:
        ctx.notes.append('non lancé : PyInstaller absent (pip install pyinstaller)')
        return
    import subprocess, sys
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'build_exe.py'), '--check'], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=900, env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    ctx.check(r.returncode == 0, 'construction ou essai échoués :\n    ' + (r.stdout + r.stderr)[-1500:].replace('\n', '\n    '))
    exe_dir = os.path.join(ROOT, 'dist', 'MXL Item Collector')
    ctx.check(os.path.exists(os.path.join(exe_dir, '_internal', 'lang', 'en.json')), "traductions absentes de l'exécutable")


@case('Installation', 'reconstruction complète de data/ depuis le jeu : même contenu que data/, contrôlé', slow=True)
def full_rebuild(ctx):
    """Extraction complète dans un dossier du cas (le jeu est seulement lu) : tables lisibles, icônes extraites,
    contrôle complet sans écart, version d'extraction, et mêmes fichiers (md5) que data/ pour la même installation."""
    if not is_game_dir(GAME_DIR):
        ctx.notes.append(f'non testée : jeu introuvable dans {GAME_DIR}')
        return
    d = os.path.join(ctx.tmp, 'data')
    ok, missing = rebuild_data(GAME_DIR, d)
    ctx.check(ok > 800 and not missing, f'icônes extraites : {ok}, introuvables : {missing[:5]}')
    ctx.expect('contrôle complet', check_data(d, full=True), [])
    ctx.expect("version d'extraction", (installed(d) or {}).get('extract_version'), EXTRACT_VERSION)
    ctx.check(Data(d).uniques, 'tables illisibles')
    # même installation que data/ : mêmes fichiers, même contenu (noms comparés sans la casse : Windows)
    norm = lambda m: {k.lower(): v for k, v in m.items()}
    ref, new = norm(manifest(os.path.join(ROOT, 'data'))), norm(manifest(d))
    ctx.expect('fichiers différents de data/', sorted(k for k in ref.keys() | new.keys() if ref.get(k) != new.get(k))[:5], [])


@case('Réglages', "dossier unique : réglages, bibliothèque et sauvegardes des versions précédentes repris, rien d'écrasé")
def home_migration(ctx):
    import subprocess, sys
    save, user = os.path.join(ctx.tmp, 'save'), os.path.join(ctx.tmp, 'user')
    home = os.path.join(save, 'MXL Item Collector')
    os.makedirs(save)
    os.makedirs(user)
    files = {os.path.join(user, 'settings.json'): b'{"language": "en"}', os.path.join(user, 'settings.json.bak'): b'{}',
             os.path.join(save, 'Kalidor.stash'): b'coffre', os.path.join(save, 'Kalidor.stash.bak-20261008-101010'): b'v1',
             os.path.join(save, 'Kalidor.stash.bak-avant-test'): b'named'}
    for f, content in files.items():
        open(f, 'wb').write(content)
    env = dict(os.environ, MXL_SAVE_DIR=save, MXL_USER_DIR=user)
    for k in ('MXL_HOME', 'MXL_SETTINGS', 'MXL_LIBRARY'):
        env.pop(k, None)
    run = lambda: subprocess.run([sys.executable, '-c', 'import mxl_home; print(mxl_home.migrate())'], cwd=ROOT, env=env,
                                 capture_output=True, text=True).stdout.strip()
    ctx.expect('fichiers repris', run(), '3')
    listing = lambda d: sorted(os.listdir(d)) if os.path.isdir(d) else []
    ctx.expect('dossier unique', (listing(home), listing(os.path.join(home, 'backups'))),
               (['backups', 'settings.json', 'settings.json.bak'], ['Kalidor.stash.bak-20261008-101010']))
    ctx.expect('restés en place : jeu, sauvegarde nommée ; anciens réglages retirés', (listing(save), listing(user)),
               (['Kalidor.stash', 'Kalidor.stash.bak-avant-test', 'MXL Item Collector'], []))
    ctx.expect('contenu', open(os.path.join(home, 'settings.json'), 'rb').read(), b'{"language": "en"}')
    open(os.path.join(user, 'settings.json'), 'wb').write(b'{"language": "fr"}')   # déjà repris : jamais écrasé
    ctx.expect('rien d\'écrasé', (run(), open(os.path.join(home, 'settings.json'), 'rb').read()), ('0', b'{"language": "en"}'))
