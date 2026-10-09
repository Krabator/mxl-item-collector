"""Thème de l'interface : couleurs du jeu (codes ÿc), fonds, couleurs de l'écran Library, police.

Seul endroit où ces valeurs sont définies (fenêtre principale, écran Library, rendu des infobulles).
"""
FONT = 'Segoe UI'

BG, GRID_LINE, EMPTY = '#0a0a0a', '#2b2b2b', '#121212'   # grille du coffre : fond, lignes, case vide
# fond des cases occupées, comme dans le coffre du jeu (relevé sur capture) : bleu, rouge si exigences non remplies
CELL_OK, CELL_KO = '#0e212f', '#380e0e'
# couleurs du jeu (code ÿc + caractère), relevées sur captures en jeu quand c'est indiqué
GAME_COLORS = {'0': '#efefef',   # blanc (capture)
               '1': '#ef7676',   # rouge : exigence non remplie (capture)
               '2': '#50e050',   # vert (objets de set)
               '3': '#9696f0',   # bleu magique (capture)
               '4': '#dbc785',   # or : unique, runeword, titres « Weapons: » (capture)
               '5': '#979797',   # gris : objets à sockets / supérieurs (capture)
               '6': '#505050', '7': '#dbc785',
               '8': '#f2db04',   # or vif : « Mega Impact » (capture)
               '9': '#f0f090',   # jaune : rares, « Prefixes: » (capture)
               ':': '#2f8f2f',
               ';': '#db00ef',   # violet : runes (capture)
               'o': '#dc8617'}   # orange : nom d'un Mystic Orb (capture de Crystal of Tears, 08/10) ; pas un
                                 # code du jeu (son ÿc8 est rendu en or vif ici, voir '8')
# noms des codes couleur du jeu (clés de GAME_COLORS), utilisés par le code des infobulles
WHITE, RED, GREEN, BLUE, GOLD, GREY, BRIGHT_GOLD, YELLOW, DARK_GREEN, PURPLE = '0', '1', '2', '3', '4', '5', '8', '9', ':', ';'
TIP_BG = '#0b0b0b'       # fond de l'infobulle
DETAIL_BG = '#161616'    # fond du panneau de détail
DETAIL_FG = '#d0d0d0'    # texte du panneau de détail
DETAIL_WIDTH, DETAIL_PADX = 74, 10   # panneau de détail (infobulle) : largeur en caractères, marge ; coffre et Library
DIM = '#8a8a8a'          # texte secondaire
QUALITY = '#f0ad4e'      # qualité de l'objet
# écran Library : entrée trouvée (or, comme les uniques) / manquante (gris) / rangée dans la collection (vert)
FOUND_COLOR, MISSING_COLOR, STORED_COLOR = '#dbc785', '#8a8a8a', '#50e050'
# ligne d'un set (regroupement, en gras) pas encore complet : gris clair, un peu plus clair que ses pièces manquantes
# (pas le blanc par défaut du thème, trop vif)
SET_GROUP_COLOR = '#b4b4b4'
SEARCH_HIT = '#4a4318'   # fond des lignes de l'infobulle qui correspondent à la recherche (écran Library)
DESTROY_COLOR = '#ef7676'   # objet à détruire (aperçu du transfert)
# panneau de détail : texte atténué, titres de section, valeur hors plage, stat cachée (détails techniques)
DETAIL_DIM, SECTION, BAD, HIDDEN = '#7a7a7a', '#b0b0b0', '#ff5555', '#666666'
# libellés secondaires (style « secondary » des étiquettes : Personnage, version, barre du bas, écran Library…) :
# #444444 dans le thème darkly, trop proche du fond (#222222) ; gris clair, pas blanc (texte normal : #d0d0d0 à #ffffff)
LABEL_DIM = '#9a9a9a'
SELECTION = '#ffffff'   # objet sélectionné : fond éclairci vers le blanc
# glisser-déposer : surbrillance des cases visées (RGBA) et contour, dépôt possible / impossible
DROP_OK, DROP_KO = ((255, 255, 255, 55), '#ffffff'), ((255, 60, 60, 70), '#ff5050')


def blend(c1, c2, t):
    """Mélange deux couleurs #rrggbb (t = part de c1)."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(x * t + y * (1 - t)):02x}' for x, y in zip(a, b))
