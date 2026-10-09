"""Recherche de l'écran Library dans le texte complet des entrées du catalogue, sans interface (testable seul).

Texte (build_index) : pour chaque entrée, son infobulle du catalogue (nom, objet de base, exigences, classe imposée,
affixes, textes du jeu) ; pour chaque set, son nom et ses bonus (utile pour composer un build) ; en mots cachés, la
classe de chaque compétence donnée par une ligne « +x to <compétence> » (« paladin » trouve « +3 to Holy Fire »,
compétence utilisable par toutes les classes mais de Paladin).
Requête (parse_query) : mots exigés tous, n'importe où, sans tenir compte des majuscules ; « "fire resist" » entre
guillemets = expression exacte.
Résultat (search) : entrées trouvées par leur propre texte, et sets trouvés par leur nom ou leurs bonus (ou par le
texte d'une pièce et celui du set réunis, quand aucun des deux ne suffit seul). Lignes trouvées (line_matches) :
surlignées dans le panneau de détail.
"""
import re
from mxl_rules import CLASSES, table_row
from mxl_catalog_tooltip import catalog_tooltip, set_bonus_lines, set_name


def parse_query(text):
    """Termes de la recherche, en minuscules : expressions entre guillemets gardées entières, puis mots."""
    text = text.lower()
    phrases = [p.strip() for p in re.findall(r'"([^"]*)"', text) if p.strip()]
    words = re.sub(r'"[^"]*"?', ' ', text).split()
    return phrases + words


def skill_classes(data):
    """{nom de compétence en minuscules: {classes}} des compétences de classe (Amazon… Assassin)."""
    out = {}
    for sid, name in data.skill_names.items():
        cls = data.skill_class.get(sid, 255)
        if name and cls < len(CLASSES):
            out.setdefault(name.lower(), set()).add(CLASSES[cls].lower())
    return out


def line_keywords(line, classes):
    """Mots cachés d'une ligne : classes de la compétence d'une ligne « +x to <compétence> [(<classe> Only)] »."""
    if ' to ' not in line:
        return ''
    skill = re.sub(r' \(\w+ only\)$', '', line.lower().rsplit(' to ', 1)[1]).strip()
    return ' '.join(sorted(classes.get(skill, ())))


def searchable(lines, classes):
    """[(texte affiché, texte cherché = texte + mots cachés, en minuscules)]."""
    return [(t, (t + ' ' + line_keywords(t, classes)).lower()) for t in lines]


def index_steps(catalog, data, index):
    """Construit le texte de recherche dans index, par étapes (générateur : une entrée par étape, pour ne pas figer
    l'écran ; environ 0,5 s au total) : {'items': {clé: lignes de l'infobulle}, 'sets': {n° du set: lignes du nom et
    des bonus}, 'set_of': {clé d'un objet de set: n° de son set}} ; lignes au format de searchable. Les sets d'abord,
    puis les entrées : complet seulement quand le générateur est épuisé."""
    classes = skill_classes(data)
    set_of = {key: table_row(key, data)['set_id'] for key, e in catalog.items() if e['kind'] == 'set'}
    index.update(items={}, sets={}, set_of=set_of)
    for sid in set(set_of.values()):
        lines = [' '.join(p for p in set_name(sid, data) if p)]
        for title, bonus in set_bonus_lines(sid, data):
            lines += [title] + [t for _, t in bonus]
        index['sets'][sid] = searchable(lines, classes)
        yield
    for key, e in catalog.items():
        index['items'][key] = searchable([''.join(t for _, t in line) for line in catalog_tooltip(e, data)], classes)
        yield


def build_index(catalog, data):
    """Texte de recherche complet (index_steps, en une fois)."""
    index = {}
    for _ in index_steps(catalog, data, index):
        pass
    return index


def matches(lines, terms):
    """Vrai si chaque terme est présent dans au moins une des lignes cherchées."""
    text = '\n'.join(s for _, s in lines)
    return all(term in text for term in terms)


def search(index, terms):
    """(entrées trouvées par leur propre texte, sets trouvés par leur nom / leurs bonus, ou par le texte d'une pièce et
    celui du set réunis)."""
    items = {k for k, lines in index['items'].items() if matches(lines, terms)}
    sets = {sid for sid, lines in index['sets'].items() if matches(lines, terms)}
    sets |= {sid for k, sid in index['set_of'].items()
             if k not in items and sid not in sets and matches(index['items'][k] + index['sets'][sid], terms)}
    return items, sets


def line_matches(line, terms, classes):
    """Vrai si une ligne affichée (panneau de détail) contient un des termes (mots cachés compris) : à surligner."""
    text = (line + ' ' + line_keywords(line, classes)).lower()
    return any(term in text for term in terms)
