"""Conteneurs d'objets : les endroits où un objet peut être rangé (coffre, et plus tard inventaire, cube…), sans
interface (testable seul).

Un conteneur décrit la forme de la grille (colonnes, lignes, pages) et si l'éditeur peut y écrire ; les règles de
placement (mxl_save.placement_error, free_spot) et la grille affichée (mxl_grid.ItemGrid) s'appuient dessus.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Container:
    key: str             # nom interne ('stash')
    cols: int            # colonnes de la grille
    rows: int            # lignes de la grille
    pages: int = 1       # nombre de pages (1 = pas d'onglets)
    writable: bool = True   # l'éditeur peut y déplacer et y modifier des objets
    holds_cube: bool = True   # le cube Horadrim peut y être rangé


# coffre du personnage et coffre partagé : 10 pages (limite du jeu) de 14 × 14 cases (confirmée en jeu)
STASH = Container('stash', 14, 14, 10)
# coffre partagé : même forme, mais le cube Horadrim ne peut pas y être rangé (règle du jeu)
SHARED_BOX = Container('stash', 14, 14, 10, holds_cube=False)

# emplacements des objets portés (champ « equipped » d'un objet, personnage et mercenaire) ; ✅ Nekratall, 1 à 10
SLOTS = {1: 'head', 2: 'amulet', 3: 'body', 4: 'right_hand', 5: 'left_hand', 6: 'right_ring', 7: 'left_ring',
         8: 'belt', 9: 'boots', 10: 'gloves', 11: 'right_hand_alt', 12: 'left_hand_alt'}
# jeu d'armes : le jeu échange les armes dans le fichier ; les emplacements 4 et 5 portent toujours le jeu ACTIF, 11 et
# 12 l'autre (✅ Nekratall, 30/09 : armes mises dans l'onglet II, onglet II actif -> rangées en 4 et 5)
ACTIVE_HANDS, INACTIVE_HANDS = (4, 5), (11, 12)


def weapon_slots(weapon_switch, tab):
    """Emplacements enregistrés des armes de l'onglet tab (1 = I, 2 = II) : {main droite (4): n°, main gauche (5): n°},
    selon le jeu actif (weapon_switch : 0 = I, 1 = II)."""
    active = (tab == 2) == bool(weapon_switch)
    return dict(zip(ACTIVE_HANDS, ACTIVE_HANDS if active else INACTIVE_HANDS))


PANELS = {1: 'inventory', 4: 'cube', 5: 'stash'}   # champ « panel » d'un objet rangé
HORADRIC_CUBE = 'box '   # code du cube Horadrim : il ne peut pas être rangé dans lui-même


def character_containers(data):
    """Grilles d'un personnage {nom: Container} : inventaire et cube, dimensions lues dans les tables du jeu
    (Data.grids), modifiables (mxl_save.ItemFile) ; le cube Horadrim ne se range pas dans lui-même."""
    return {key: Container(key, *data.grids[key], holds_cube=key != 'cube') for key in ('inventory', 'cube')}


def cube_status(char_items, stash_items):
    """État du cube d'un personnage : 'ok' s'il a un cube Horadrim (dans son sac ou dans son coffre, stash_items),
    sinon 'readonly' si son cube contient encore des objets (visibles, pas modifiables), sinon 'none' (pas de cube)."""
    if any(it['code'] == HORADRIC_CUBE for it in placed(char_items, 'inventory') + list(stash_items)):
        return 'ok'
    return 'readonly' if placed(char_items, 'cube') else 'none'


def place(it):
    """Rangement d'un objet lu dans un .d2s : 'equipped' (porté, emplacement SLOTS[it['equipped']]), 'belt'
    (ceinture : case x), 'inventory', 'cube' ou 'stash' (grille : cases x, y), sinon None (objet en main, inconnu)."""
    if it['location'] == 1:
        return 'equipped'
    if it['location'] == 2:
        return 'belt'
    return PANELS.get(it['panel']) if it['location'] == 0 else None


def placed(items, where):
    """Objets de la liste rangés dans where ('equipped', 'belt', 'inventory', 'cube')."""
    return [it for it in items if place(it) == where]
