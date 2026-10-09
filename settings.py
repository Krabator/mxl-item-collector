"""Réglages de l'utilisateur, enregistrés dans settings.json (paths.SETTINGS_FILE : dossier unique de l'utilisateur,
« MXL Item Collector » dans le dossier des sauvegardes du jeu) : langue, dernier coffre ouvert,
dossier du jeu, priorités des stats (données de l'utilisateur, à ne pas perdre).

Écriture sûre : fichier temporaire puis remplacement (une coupure ne laisse jamais un fichier tronqué) ; copie de la
dernière version enregistrée dans settings.json.bak, relue si settings.json est illisible (abîmé hors de l'éditeur :
disque, modification à la main) ; un settings.json abîmé n'est jamais écrasé sans être gardé dans
settings.json.broken.
La variable d'environnement MXL_SETTINGS désigne un autre fichier (utilisé par les tests, pour ne pas modifier
les réglages de l'utilisateur).
"""
import json, os, shutil
from paths import SETTINGS_FILE

PATH = os.environ.get('MXL_SETTINGS') or SETTINGS_FILE


def _read(path):
    with open(path, encoding='utf-8') as f:
        s = json.load(f)
    if not isinstance(s, dict):
        raise ValueError('settings: not an object')
    return s


def load():
    """Tous les réglages : settings.json, sinon sa copie (settings.json.bak) s'il est illisible, sinon {}."""
    for path in (PATH, PATH + '.bak'):
        try:
            return _read(path)
        except (OSError, ValueError):
            continue
    return {}


def get(key, default=None):
    return load().get(key, default)


def put(key, value):
    """Enregistre un réglage (les autres sont conservés), par écriture sûre (voir le module)."""
    s = load()
    s[key] = value
    _save(s)


def rename(old, new):
    """Réglage renommé : valeur de old reprise sous new (si new n'existe pas encore), old retiré ; rien d'écrit si old
    est absent."""
    s = load()
    if old not in s:
        return
    value = s.pop(old)
    s.setdefault(new, value)
    _save(s)


def _save(s):
    """Écriture sûre de tous les réglages (voir le module)."""
    if os.path.exists(PATH):
        try:
            _read(PATH)
        except (OSError, ValueError):
            shutil.copy2(PATH, PATH + '.broken')   # fichier abîmé gardé pour examen, pas écrasé sans copie
    tmp = PATH + '.tmp'
    os.makedirs(os.path.dirname(os.path.abspath(PATH)), exist_ok=True)   # dossier de l'utilisateur (1er lancement)
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, PATH)
    shutil.copy2(PATH, PATH + '.bak')   # copie de la dernière version enregistrée
