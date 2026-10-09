"""Outils des tests : chemins, enregistrement des cas (@case) et contexte d'un cas (Ctx).

Chaque cas est une fonction indépendante qui reçoit un Ctx : tables du jeu (lecture seule), dossier temporaire à lui
(supprimé à la fin), vérifications (expect, check, raises) et comparaison à une référence (compare). Un cas qui
échoue ou plante n'empêche pas les autres de tourner.
"""
import os, sys, shutil, subprocess, tempfile, traceback
# dossier de l'utilisateur des tests (réglages, sauvegardes .bak) : temporaire, jamais celui de l'utilisateur
os.environ.setdefault('MXL_HOME', tempfile.mkdtemp(prefix='mxl_tests_home_'))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
FIXTURES = os.path.join(HERE, 'fixtures')
REF = os.path.join(HERE, 'reference')
STASH = os.path.join(FIXTURES, 'Nekratall.stash')
# 2e coffre (26/09) : 84 objets dont 2 uniques : Horadric Malus (quête, n° 32767) et Jared's Fragmentor (n° 375),
# Heavy Boots au palier de vitesse 20 %, runeword Lumen Arcana (stat à total nul : RW -3 % + rune +3 %)
STASH2 = os.path.join(FIXTURES, 'stash2', 'Nekratall.stash')
# coffre partagé de test (06/10) : Containers, Clusters et Shrine Vessels (stat Quantity 501)
CONTAINERS = os.path.join(FIXTURES, 'containers', '_sharedstash.shared')
LANGUAGES = ('en',)   # instantanés d'affichage : une par langue livrée (lang/)


def _game_dir():
    """Installation du jeu (lecture seule) : MXL_GAME_DIR, sinon le réglage game_dir de l'utilisateur (lu directement :
    paths pointe vers le dossier temporaire des tests) ; '' si aucun (cas qui en ont besoin : « non testé »)."""
    if os.environ.get('MXL_GAME_DIR'):
        return os.environ['MXL_GAME_DIR']
    import json
    save = os.environ.get('MXL_SAVE_DIR') or os.path.expandvars(r'%APPDATA%\MedianXL\save')
    try:
        with open(os.path.join(save, 'MXL Item Collector', 'settings.json'), encoding='utf-8') as f:
            return json.load(f).get('game_dir') or ''
    except (OSError, ValueError, AttributeError):
        return ''


GAME_DIR = _game_dir()

CASES = []   # (groupe, titre, fonction, lent) dans l'ordre d'enregistrement
GUI_GROUPS = ('Interface', 'Éditeur : interface')   # tests d'interface (sauf --no-gui)

# jeu considéré fermé pendant les tests (sinon toute écriture serait refusée si Median XL est ouvert pendant la
# campagne) ; les cas du jeu ouvert simulent leurs processus (test_display_writes)
import mxl_game
mxl_game.running_processes = lambda: []


def case(group, title, slow=False):
    """Enregistre une fonction de test (elle reçoit un Ctx) dans le groupe donné ; slow : cas long, lancé seulement
    avec --slow (sinon signalé « non lancé »)."""
    def deco(fn):
        CASES.append((group, title, fn, slow))
        return fn
    return deco


def gui_case(test):
    """Test d'interface dans son propre processus (fenêtres fermées même en cas d'échec : voir gui_tests.py) ; base
    seule (MXL_NO_EDITOR) transmise au processus."""
    def run(ctx):
        r = subprocess.run([sys.executable, os.path.join(HERE, 'gui_tests.py'), test],
                           capture_output=True, text=True, encoding='utf-8', timeout=300,
                           env=dict(os.environ, PYTHONIOENCODING='utf-8'))   # messages accentués lisibles
        if r.returncode != 0:
            ctx.failures.append('\n    ' + (r.stdout + r.stderr).strip().replace('\n', '\n    '))
    return run


def set_raw_stat(buf, it, stat_id, value, data):
    """Fabrique d'exemplaires des tests : valeur d'une stat (et des stats liées au même mod : 17/18…) posée
    directement dans buf, sans contrôle de plage (l'écriture contrôlée des valeurs est dans le module mxl_editor)."""
    from mxl_format import write_bits
    from mxl_rules import linked_stats
    for sid in linked_stats(it, stat_id, data, 'stats'):
        st = next(s for s in it['stats'] if s['id'] == sid)
        write_bits(buf, (it['_offset'] + 2) * 8 + st['pos'], st['bits'], value + st['add'])


class Ctx:
    """Contexte d'un cas : data (tables du jeu, à ne pas modifier durablement), update (--update : références
    réécrites), dossier temporaire tmp, échecs relevés (failures), notes affichées après le résultat."""

    def __init__(self, data, update=False):
        self.data, self.update = data, update
        self.failures, self.notes = [], []
        self._tmp = None

    @property
    def tmp(self):
        if self._tmp is None:
            self._tmp = tempfile.mkdtemp(prefix='mxl_tests_')
        return self._tmp

    def copy(self, src, name=None):
        """Copie d'un fichier de test dans le dossier temporaire (les fichiers de référence ne sont jamais modifiés)."""
        dst = os.path.join(self.tmp, name or os.path.basename(src))
        shutil.copy2(src, dst)
        return dst

    def expect(self, what, got, want):
        if got != want:
            self.failures.append(f'{what} : {got!r} au lieu de {want!r}')

    def check(self, cond, msg):
        if not cond:
            self.failures.append(msg)

    def raises(self, exc, what, f):
        """f doit lever exc ; renvoie l'exception levée (ou None)."""
        try:
            f()
        except exc as e:
            return e
        self.failures.append(f'{what} : {exc.__name__} attendue, rien levé')
        return None

    def compare(self, ref_file, text):
        """Compare text à la référence tests/reference/<ref_file> (chemin absolu : référence ailleurs, celles du
        module mxl_editor) ; créée si absente, réécrite avec --update."""
        path = os.path.join(REF, ref_file)   # chemin absolu gardé tel quel
        if self.update or not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(text)
            self.notes.append(f'référence {"mise à jour" if self.update else "créée"} ({ref_file})')
            return
        ref = open(path, encoding='utf-8').read()
        if ref != text:
            diff = [f'    - {a}\n    + {b}' for a, b in zip(ref.splitlines(), text.splitlines()) if a != b][:5]
            self.failures.append(f'DIFFÉRENT de {ref_file}\n' + '\n'.join(diff))

    def cleanup(self):
        if self._tmp:
            shutil.rmtree(self._tmp, ignore_errors=True)


def run_case(title, fn, data, update=False):
    """Exécute un cas ; renvoie ses échecs (exception = échec, avec la trace)."""
    ctx = Ctx(data, update)
    try:
        fn(ctx)
    except Exception:
        ctx.failures.append('exception :\n' + traceback.format_exc())
    finally:
        ctx.cleanup()
    status = 'ÉCHEC' if ctx.failures else 'OK'
    print(f'  {title} : {status}' + ''.join(f' ({n})' for n in ctx.notes))
    return [f'{title} : {f}' for f in ctx.failures]
