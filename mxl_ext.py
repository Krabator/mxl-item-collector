"""Module complémentaire de l'éditeur : mxl_editor (privé : édition des valeurs, duplication), chargé s'il est présent.

L'application de base lit, compare, range et déplace les objets ; elle ne modifie jamais leurs valeurs et ne les
copie pas. Le module mxl_editor (dossier à côté du programme, ou inclus dans l'exécutable privé) s'y branche par des
points d'accroche (fonctions qu'il définit, appelées par la base si elles existent) :
- library_buttons(window, parent) : boutons ajoutés sous l'infobulle de l'écran Library (« Copy to the stash »),
  [bouton] ;
- panel_editor(panel) : partie active de la section Editing d'un panneau de détail (titre, Ethereal / Max sockets,
  quantité, curseurs actifs) ;
- commit_edit(app, it, edit) : écriture d'une modification (contrôles, sauvegarde, relecture).
Droits (edition_enabled, duplication_enabled de settings.json) : sans le module, toujours désactivés ; avec lui,
activés par défaut, désactivables par « false » dans settings.json (décision du 08/10).
MXL_NO_EDITOR (variable d'environnement) : module ignoré même présent (tests de la base seule).
"""
import importlib
import os

EDITOR_MODULE = 'mxl_editor'
_editor = False   # pas encore cherché


def editor():
    """Le module mxl_editor s'il est présent (et non ignoré par MXL_NO_EDITOR), sinon None ; cherché une fois."""
    global _editor
    if _editor is False:
        _editor = None
        if not os.environ.get('MXL_NO_EDITOR'):
            try:
                _editor = importlib.import_module(EDITOR_MODULE)
            except ModuleNotFoundError as e:
                if e.name != EDITOR_MODULE:   # module présent mais cassé : erreur visible, pas d'absence silencieuse
                    raise
    return _editor


def editor_error():
    """Erreur du module s'il est présent mais ne se charge pas (« Type: message »), sinon None : vérifié au lancement
    pour l'afficher à l'écran (l'exécutable n'a pas de console ; audit du 09/10)."""
    try:
        editor()
    except Exception as e:
        return f'{type(e).__name__}: {e}'
    return None


def hook(name):
    """Point d'accroche name du module (fonction), ou None si le module est absent ou ne le définit pas."""
    ed = editor()
    return getattr(ed, name, None) if ed else None
