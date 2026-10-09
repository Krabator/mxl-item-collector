"""Pages de la documentation officielle (docs.median-xl.com) : lecture des infobulles d'une page (prise sur Internet,
cache dans tests/cache/docs/ : voir test_documentation.py) et comparaison avec les infobulles du catalogue de l'éditeur.

Deux formes de tableau class="uniques" :
- titre « Nom (Objet de base) », puis une cellule par tier (« Tier 1 » à « Tier 4 ») ;
- titre « Objet de base » (ou pas de titre : amulettes, anneaux…), puis une cellule par objet commençant par son nom
  (segment de classe margin_bottom) ;
- page des sets (tableau class="sets") : cellule de résumé du set (sans image, ignorée), puis une cellule par objet
  (image de l'objet de base) : nom, objet de base, infobulle.
Une ligne se termine par <br>, sa couleur est la classe CSS de son dernier segment.
Les « + » sont ignorés (l'éditeur les garde comme le jeu, le site en omet), ainsi que les guillemets '' / ".
"""
import re
from html.parser import HTMLParser

COLORS = {'item-basic': '0', 'item-magic': '3', 'item-red': '1', 'item-unique': '4', 'item-orange': '8',
          'item-yellow': '9', 'item-set': '2', 'item-grey': '5', 'item-gray': '5', 'item-runeword': '5',
          'item-green': ':', 'item-darkgreen': ':', 'item-tan': '7'}


class Page(HTMLParser):
    """blocks : [{name, base ('' si inconnu), tier (None hors tiers), lines [(couleur, texte)]}], un par cellule ;
    sets (page des sets) : [{lines [(couleur, texte)]}], une par cellule de résumé d'un set (nom, pièces, bonus)."""

    def __init__(self, html):
        super().__init__()
        self.blocks, self.title, self.in_th, self.in_td = [], None, False, False
        self.stack, self.line, self.block = [], [], None
        self.table_class, self.framed, self.want_base = '', False, False   # page des sets : voir flush
        self.sets, self.summary = [], []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.title, self.table_class = '', dict(attrs).get('class') or ''
        elif tag == 'th':
            self.in_th, self.title = True, ''
        elif tag == 'td':
            self.in_td, self.block, self.line, self.framed, self.want_base = True, None, [], False, False
        elif tag == 'img' and self.in_td and 'frame' in (dict(attrs).get('class') or '').split():
            self.framed = True   # cellule d'un objet (image de l'objet de base) ; sans image : résumé du set
        elif tag == 'span':
            self.stack.append((dict(attrs).get('class') or '').split())
        elif tag == 'br' and self.in_td:
            self.flush()

    def handle_endtag(self, tag):
        if tag == 'th':
            self.in_th = False
        elif tag == 'td':
            self.flush()
            if self.block:
                self.blocks.append(self.block)
            elif self.summary:
                self.sets.append(dict(lines=self.summary))
            self.summary = []
            self.in_td, self.block = False, None
        elif tag == 'span' and self.stack:
            self.stack.pop()

    def handle_data(self, data):
        if self.in_th:
            self.title += data
        elif self.in_td:
            t = re.sub(r'\s+', ' ', data)
            if t.strip():
                col = next((COLORS[c] for cs in reversed(self.stack) for c in cs if c in COLORS), '0')
                self.line.append((col, t, any('margin_bottom' in cs for cs in self.stack)))

    def flush(self):
        text = re.sub(r'\s+', ' ', ''.join(x[1] for x in self.line)).strip()
        if text:
            m = re.fullmatch(r'Tier (\d)', text)
            title = re.sub(r'\s+', ' ', self.title).strip()
            if m and self.block is None:
                t = re.fullmatch(r'(.*) \((.*)\)', title)
                name, base = (t.group(1), t.group(2)) if t else (title, '')
                self.block = dict(name=name, base=base, tier=int(m.group(1)), lines=[])
            elif self.block is None and self.line[0][2]:
                self.block = dict(name=text, base=title, tier=None, lines=[])
            elif self.block is None and self.table_class == 'sets' and self.framed:
                # page des sets : nom de l'objet, puis objet de base sur la ligne suivante
                self.block, self.want_base = dict(name=text, base='', tier=None, lines=[]), True
            elif self.want_base:
                self.block['base'], self.want_base = text, False
            elif self.block is not None:
                self.block['lines'].append((self.line[-1][0], re.sub(r'\s+', ' ', text)))
            elif self.table_class == 'sets' and not self.framed:   # résumé d'un set : nom, pièces, bonus
                self.summary.append((self.line[-1][0], text))
        self.line = []


def norm(t):
    return re.sub(r'\s+', ' ', t.replace('+', '').replace("''", '"')).strip()


def shape(t):
    return re.sub(r'-?\d+(\.\d+)?', '#', norm(t))


def compare(doc, ours, order_ignore=None):
    """Écarts entre deux infobulles [(couleur, texte)] : [(catégorie, détail)] ; catégories : 'manquante' (ligne de
    la page absente de l'éditeur), 'en trop', 'valeur' (même ligne, nombres différents), 'couleur', 'ordre'.
    order_ignore : motif des lignes dont la place n'est pas comparée."""
    d = [(c, norm(t)) for c, t in doc]
    o = [(c, norm(t)) for c, t in ours]
    dt, ot = [t for _, t in d], [t for _, t in o]
    out = []
    for c, t in d:
        if t in ot and o[ot.index(t)][0] != c:
            out.append(('couleur', f'{t} : page {c}, éditeur {o[ot.index(t)][0]}'))
    rest_d = [x for x in d if x[1] not in ot]
    rest_o = [x for x in o if x[1] not in dt]
    for c, t in list(rest_d):
        m = next((x for x in rest_o if shape(x[1]) == shape(t)), None)
        if m:
            out.append(('valeur', f'page « {t} » / éditeur « {m[1]} »'))
            rest_d.remove((c, t))
            rest_o.remove(m)
    out += [('manquante', t) for _, t in rest_d] + [('en trop', t) for _, t in rest_o]
    keep = (lambda t: not re.search(order_ignore, t)) if order_ignore else (lambda t: True)
    common_d = [t for t in dt if t in ot and keep(t)]
    common_o = [t for t in ot if t in dt and keep(t)]
    if common_d != common_o:
        out.append(('ordre', ' | '.join(common_d)))
    return out
