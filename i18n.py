"""Traduction de l'application : un fichier JSON par langue dans lang/ (<code>.json, ex. en.json, de.json) ; exécutable :
langues livrées, plus celles du dossier lang/ du dossier de l'utilisateur (paths.LANG_DIRS : un fichier de même nom y
remplace celui livré).

- lang/en.json est la référence : il contient toutes les clés, en anglais (langue par défaut).
- Une clé absente d'une autre langue retombe sur l'anglais, puis sur la clé elle-même : une traduction
  partielle ne casse rien.
- Chaque fichier contient "_language" (nom de la langue, dans cette langue) ; les clés commençant par "_"
  ne sont pas des textes.
- Les textes peuvent contenir des champs {nom} remplacés à l'affichage (str.format).
- La langue choisie est enregistrée dans les réglages (settings.py, fichier settings.json).
Pour ajouter une langue : copier lang/en.json en lang/<code>.json et traduire les valeurs (pas les clés).
"""
import json, os
import settings

from paths import LANG_DIRS
DEFAULT = 'en'

_texts = {}      # langue courante
_fallback = {}   # anglais
_current = DEFAULT


def _load(code):
    """Textes de la langue code : fichier du dernier dossier de LANG_DIRS qui l'a et qui se lit ({} sinon)."""
    for d in reversed(LANG_DIRS):
        try:
            with open(os.path.join(d, f'{code}.json'), encoding='utf-8') as f:
                texts = json.load(f)
            if isinstance(texts, dict):
                return texts
        except (OSError, ValueError):
            continue
    return {}


def available():
    """[(code, nom de la langue)] des fichiers présents dans les dossiers de langues, triés par nom."""
    codes = {fn[:-5] for d in LANG_DIRS if os.path.isdir(d) for fn in os.listdir(d) if fn.endswith('.json')}
    return sorted(((code, _load(code).get('_language', code)) for code in codes), key=lambda x: x[1].lower())


def set_language(code, save=True):
    """Active une langue (retombe sur l'anglais si le fichier est absent) ; l'enregistre si save."""
    global _texts, _fallback, _current
    _fallback = _load(DEFAULT)
    _texts = _load(code) if code != DEFAULT else _fallback
    _current = code if _texts else DEFAULT
    if save:
        settings.put('language', _current)


def current():
    return _current


def tr(key, **fields):
    """Texte traduit de la clé, champs {nom} remplacés."""
    txt = _texts.get(key) or _fallback.get(key) or key
    try:
        return txt.format(**fields) if fields else txt
    except (KeyError, IndexError, ValueError):
        return txt


set_language(settings.get('language', DEFAULT), save=False)
