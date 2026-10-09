"""Affichage d'une infobulle dans une zone de texte Tk (fenêtre principale, écran Library).

Une infobulle est une liste de lignes ; une ligne est une liste de segments (code couleur du jeu, texte), le code
suivi de « * » demande du gras (voir mxl_tooltip). Le contenu vient d'ailleurs (mxl_tooltip.item_tooltip pour un
objet réel ; plus tard, une infobulle construite depuis les tables pour une entrée du catalogue) : ce module ne
fait que l'affichage, identique partout.
"""
from mxl_theme import GAME_COLORS, TIP_BG, FONT


def setup_tags(text):
    """Styles de l'infobulle dans la zone de texte : fond et centrage ('tip'), couleurs du jeu ('g<code>'), gras."""
    text.tag_configure('tip', justify='center', background=TIP_BG, font=(FONT, 11), spacing1=1, spacing3=1,
                       lmargin1=0, rmargin=0)
    for code, col in GAME_COLORS.items():
        text.tag_configure('g' + code, foreground=col)
    text.tag_configure('bold', font=(FONT, 11, 'bold'))


def insert_line(text, index, segs):
    """Insère une ligne de l'infobulle (segments couleur / texte) à index (sans le saut de ligne)."""
    text.mark_set('ins', index)
    text.mark_gravity('ins', 'right')
    for code, txt in segs:
        tags = ('tip', 'g' + code.rstrip('*')) + (('bold',) if code.endswith('*') else ())
        text.insert('ins', txt, tags)


def write_tooltip(text, lines, mark=None):
    """Écrit l'infobulle à la fin de la zone de texte, avec une ligne vide de marge avant et après.
    mark : nom d'une marque posée au début de la première ligne (mises à jour localisées d'une ligne)."""
    text.insert('end', ' \n', 'tip')
    if mark:
        text.mark_set(mark, 'end - 1 chars')
        text.mark_gravity(mark, 'left')
    for segs in lines:
        insert_line(text, 'end', segs)
        text.insert('end', '\n', 'tip')
    text.insert('end', ' \n', 'tip')
