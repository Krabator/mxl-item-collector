"""Écran Library : ce qu'affiche le panneau de détail pour l'entrée sélectionnée, sans interface (testable seul).

DetailSelection garde la vue choisie (exemplaire normal ou éthéré) d'un affichage à l'autre et décide, à chaque mise
à jour de l'écran, de la place de la collection affichée, de l'affichage de la bascule Normal / Ethereal et de la
ligne sous l'infobulle. L'écran (mxl_library_gui.LibraryWindow.show_detail) ne fait qu'afficher le résultat.
Noms des places (slot_name, slot_base) : écran Library et fenêtre de transfert.
"""
from dataclasses import dataclass
from i18n import tr
from mxl_library import ETHEREAL, entry_of, is_storage, storage_parts


@dataclass
class Shown:
    """Contenu du panneau de détail pour l'entrée sélectionnée."""
    key: str = None          # entrée sélectionnée (None : aucune)
    view: str = 'normal'     # 'normal' ou 'ethereal'
    slot: str = None         # place de la collection affichée : clé, suivie de ETHEREAL en vue Ethereal
    stored: bool = False     # un exemplaire est rangé à cette place (sinon : infobulle du catalogue)
    toggle: bool = False     # bascule Normal / Ethereal affichée (l'objet existe en jeu dans les deux variantes)
    same_slot: bool = False  # même place que l'affichage précédent (position de défilement gardée)
    footer: str = None       # ligne sous l'infobulle : 'stored' (dates), 'no_ethereal' (pas d'exemplaire éthéré,
                             # le normal est rangé), 'found' (trouvé, pas rangé), 'missing' (pas encore trouvé)


class DetailSelection:
    """Vue choisie et dernier affichage du panneau de détail (voir le module)."""

    def __init__(self):
        self.key = None           # entrée du dernier affichage
        self.view = 'normal'      # vue actuelle
        self.slot = None          # place du dernier affichage
        self.stored_pair = None   # (exemplaire normal rangé, exemplaire éthéré rangé) de l'entrée au dernier affichage

    def choose_view(self, view):
        """Clic sur la bascule : vue gardée tant que l'entrée et ses exemplaires rangés ne changent pas."""
        self.view = view

    def update(self, key, collection, found, two_variants):
        """Affichage de l'entrée key (None : aucune). collection : places rangées ; found : entrées trouvées ;
        two_variants : l'objet existe en jeu en version normale et éthérée (mxl_library.two_variants).
        - autre entrée : exemplaire normal s'il est rangé, sinon l'éthéré ;
        - même entrée, exemplaires rangés changés (l'un vient d'être rangé, ou celui affiché sorti) et vue sans
          exemplaire : bascule sur l'exemplaire rangé ; sinon la vue choisie est gardée (ex. vue Ethereal du
          catalogue alors que l'exemplaire normal est rangé, même après une recherche ou un tri) ;
        - une seule variante en jeu : vue normale, sans bascule."""
        normal = key is not None and key in collection
        eth = key is not None and key + ETHEREAL in collection
        if key != self.key:
            self.view = 'ethereal' if eth and not normal else 'normal'
        elif (normal, eth) != self.stored_pair:
            shown, other = (eth, normal) if self.view == 'ethereal' else (normal, eth)
            if not shown and other:
                self.view = 'normal' if self.view == 'ethereal' else 'ethereal'
        self.stored_pair = (normal, eth)
        if not two_variants:
            self.view = 'normal'
        slot = key + ETHEREAL if key is not None and self.view == 'ethereal' else key
        stored = eth if self.view == 'ethereal' else normal
        if key is None:
            footer = None
        elif stored:
            footer = 'stored'
        elif self.view == 'ethereal' and normal:
            footer = 'no_ethereal'
        else:
            footer = 'found' if key in found else 'missing'
        shown = Shown(key=key, view=self.view, slot=slot, stored=stored, toggle=key is not None and two_variants,
                      same_slot=slot == self.slot, footer=footer)
        self.key, self.slot = key, slot
        return shown


def slot_name(catalog, slot, data=None):
    """Nom d'une place de la collection : nom de l'entrée, suivi de « (Ethereal) » pour l'exemplaire éthéré ; place du
    stockage des supérieurs (data requis) : objet de base et nombre de sockets."""
    if is_storage(slot):
        code, sockets, _ = storage_parts(slot)
        name = tr('library.storage_name', base=data.base(code.ljust(4)).name, n=sockets)
    else:
        name = catalog[entry_of(slot)]['name']
    return name + tr('library.ethereal_suffix') if slot.endswith(ETHEREAL) else name


def slot_base(catalog, slot, data):
    """Objet de base d'une place (collection ou stockage des supérieurs)."""
    return data.base(storage_parts(slot)[0].ljust(4)).name if is_storage(slot) else catalog[entry_of(slot)]['base']
