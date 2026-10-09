"""Éléments éditables d'un objet (valeurs à variance), regroupés par ligne de l'infobulle.

Seules les valeurs dont la plage n'est pas fixe (min ≠ max) sont éditables :
- défense de base d'une armure, dans [min, max] de armor.bin (pas si elle vaut max + 1 : Enhanced Defense) ;
- stats de l'objet issues de ses affixes ou de la sous-qualité « Superior » (source B) ;
- stats du runeword (source RW) ;
- stats des joyaux sertis, dans la plage de leurs propres affixes (source J).
Les gemmes et runes serties (bonus fixes) ne sont pas éditables. Les stats liées (ex. 17/18, attributs 0 à 3)
forment un seul élément ; les couples min / max (dégâts élémentaires…) donnent deux éléments indépendants.

Qualité de l'objet (item_quality) : 0 % = tous les curseurs au minimum, 100 % = tous au maximum, moyenne pondérée
par la priorité de chaque stat (1 étoile Low = 0,5 ; 2 étoiles Medium = 1, par défaut ; 3 étoiles High = 1,5).
Les priorités sont rangées par profil d'objet (priority_profile), communes à tous les personnages : les objets
identiques (uniques, sets, Superior gris sans objet serti) partagent un profil conservé d'une session à l'autre ; les
autres objets ont des combinaisons d'affixes trop variées : pas de priorités, poids par défaut.
"""
import copy
from i18n import tr
import stat_ids as S
from mxl_rules import stat_range, linked_stats, defense_range, stat_hidden, MIN_MAX_PAIRS, auto_tiers, worst_best
from mxl_stat_text import stat_lines, shown_value, is_percent, socket_contents
from mxl_tooltip import all_stats, name_color
from mxl_rules import unique_row

PAIR_OF = {s: p for p in MIN_MAX_PAIRS for s in p}   # stat -> couple (min, max) auquel elle appartient
PRIORITY_WEIGHTS = {1: 0.5, 2: 1.0, 3: 1.5}   # priorité (nombre d'étoiles : Low, Medium, High) -> poids
DEFAULT_PRIORITY = 2                           # Medium


def priority_profile(it, data):
    """(clé du profil de priorités, conservé ?) : 'unique:<n°>' (ligne de uniqueitems), 'set:<n°>', 'superior:<code>'
    (Superior au nom gris, c.-à-d. à sockets ou éthéré, sans objet serti) = conservés ; sinon 'item:<id>' (n° propre
    à l'exemplaire, enregistré dans l'objet) = session seulement."""
    q = it.get('quality')
    if unique_row(it, data):
        return f"unique:{it['set_unique_id']}", True
    if q == 'set' and it.get('set_unique_id') is not None:
        return f"set:{it['set_unique_id']}", True
    if q == 'superior' and name_color(it, data) == '5' and not it.get('socketed'):
        return f"superior:{it['code'].strip()}", True
    return f"item:{it.get('id', it['_offset'])}", False


def global_priorities(saved):
    """Priorités enregistrées {profil: {stat: priorité}}. L'ancien format par personnage (26/09 au 27/09 :
    {personnage: {profil: {stat: priorité}}}) est converti en fusionnant les personnages (clés de profil : 'unique:…',
    'set:…', 'superior:…', toujours avec « : » ; noms de personnage : jamais)."""
    out = {}
    for key, value in (saved or {}).items():
        for profile, stats in (value.items() if ':' not in key else [(key, value)]):
            out.setdefault(profile, {}).update(stats)
    return out


def item_quality(groups, priorities=None):
    """Qualité de l'objet en % (0 à 100), ou None s'il n'a aucun élément éditable : moyenne des positions des
    curseurs, (valeur - min) / (max - min), pondérée par la priorité de chaque élément.
    priorities = {clé de priorité (champ 'priority_key'): 1, 2 ou 3} ; clé absente = DEFAULT_PRIORITY."""
    priorities = priorities or {}
    total = weight = 0.0
    for g in groups:
        for f in g['fields']:
            w = PRIORITY_WEIGHTS[priorities.get(f['priority_key'], DEFAULT_PRIORITY)]
            total += w * (f['value'] - f['lo']) / (f['hi'] - f['lo'])
            weight += w
    return 100 * total / weight if weight else None


def top_priority_sum(groups, priorities=None):
    """Départage de deux exemplaires de même qualité : somme des valeurs des éléments qui ont la plus haute priorité
    de l'objet (ex. tous les ★★★ ; s'il n'y en a pas, les ★★☆…). 0 sans élément éditable."""
    priorities = priorities or {}
    fields = [(priorities.get(f['priority_key'], DEFAULT_PRIORITY), f['value']) for g in groups for f in g['fields']]
    top = max((p for p, _ in fields), default=None)
    return sum(v for p, v in fields if p == top)


def _heading(it, sids, data, char, param=None):
    """Texte de la ligne d'infobulle correspondant à un groupe de stats (valeurs totales de l'objet) ; param : celui
    de la stat (une des deux « +x to <compétence> »)."""
    if S.ENH_DAMAGE_MAX in sids or S.ENH_DAMAGE_MIN in sids:
        v = sum(s['value'] for s in all_stats(it, data) if s['id'] == S.ENH_DAMAGE_MAX)
        return tr('edit.enhanced_damage', v=v)
    stats = [s for s in all_stats(it, data) if s['id'] in sids and (param is None or s.get('param') == param)]
    lines = stat_lines(stats, data, char)
    # stats liées affichées sur plusieurs lignes (un seul tirage pour plusieurs stats, ✅ Athame : pénétrations feu et
    # poison) : toutes les lignes dans le titre, l'une sous l'autre ; le curseur les modifie ensemble
    return '\n'.join(l[1] for l in lines) if lines else ' / '.join(data.isc[s]['desc'] for s in sids)


def edit_groups(it, data, char=None):
    """[{heading, prio, fields: [{label, lo, hi, value, fmt, shown, choices, priority_key, edit}]}] ; lo / hi = moins bonne /
    meilleure valeur ; fmt = valeur affichée (+ valeur stockée si elle diffère) ; shown = valeur de l'infobulle ; edit = paramètres de
    mxl_save.apply_edits ; choices = valeurs permises (paliers d'un auto-affixe) ou None (toute la plage) ;
    priority_key = clé de la priorité de l'élément (même stat = même priorité sur tous les objets)."""
    groups = {}

    def group(key, heading, prio):
        return groups.setdefault(key, dict(heading=heading, prio=prio, fields=[]))

    rng = defense_range(it, data)
    if rng:
        # titre avec la valeur, comme les autres lignes (« 8 Base Defense »), mis à jour après une modification
        g = group('defense', tr('edit.base_defense', v=it['defense']), 10 ** 6)
        # source B (objet de base), comme les stats de l'objet
        g['fields'].append(dict(label='B', lo=rng[0], hi=rng[1], value=it['defense'], fmt=str, shown=str, choices=None,
                                priority_key='defense',
                                edit=dict(offset=it['_offset'], code=it['code'], kind='defense')))
    at = auto_tiers(it, data)
    owners = [(it, 'stats', 'B'), (it, 'stats_runeword', 'RW')]
    owners += [(sub, 'stats', 'J') for sub, src, _ in socket_contents(it, data) if src == 'J']
    for owner, stat_list, src in owners:
        seen = set()
        for s in owner.get(stat_list, []):
            sid, param = s['id'], s.get('param')   # stat identifiée par (n°, param) : deux « +x to <compétence> »
            if (sid, param) in seen:
                continue
            if stat_hidden(sid, data):
                continue   # stat cachée (compteurs, marqueurs MXL) : absente de l'infobulle, non éditable
            r = stat_range(owner, sid, data, stat_list, param)
            if not r or r[0] == r[1]:
                continue
            linked = tuple(sorted(linked_stats(owner, sid, data, stat_list)))
            seen.update((x, param) for x in linked)
            key = PAIR_OF.get(sid) or linked
            heading = _heading(it, key, data, char, param)
            g = group(key if param is None else key + (('param', param),), heading, data.isc[key[0]]['prio'])
            label = src
            if sid in PAIR_OF:
                label += ' · ' + tr('edit.min' if PAIR_OF[sid][0] == sid else 'edit.max')
            pct = '%' if is_percent(sid, data) or sid in (S.ENH_DEFENSE, S.ENH_DAMAGE_MAX, S.ENH_DAMAGE_MIN) else ''
            show = (lambda v, sid=sid: shown_value(sid, v, data, char))
            # valeur telle qu'affichée en jeu ; valeur stockée entre parenthèses si elle diffère (ex. régénération ×10)
            fmt = (lambda v, show=show, pct=pct: f"{show(v)}{pct}" + (f" ({v})" if show(v) != v else ''))
            # auto-affixe à paliers : seules les valeurs des paliers possibles (curseur aimanté)
            choices = sorted(t[1][sid] for t in at['tiers']) if at and owner is it and stat_list == 'stats' \
                and sid in at['stats'] else None
            # curseur de la moins bonne (à gauche) à la meilleure valeur (à droite) : lo > hi pour une stat dont la valeur
            # enregistrée la plus basse est la meilleure (Requirements, Mana Cost) ; qualité mesurée dans le même sens
            lo, hi = worst_best(sid, r[0], r[1], data)
            # bornes du curseur : valeurs telles qu'affichées dans l'infobulle (sans la valeur stockée)
            shown = (lambda v, show=show, pct=pct: f"{show(v)}{pct}")
            g['fields'].append(dict(label=label, lo=lo, hi=hi, value=s['value'], fmt=fmt, shown=shown, choices=choices,
                                    priority_key=f'stat:{sid}' if param is None else f'stat:{sid}:{param}',
                                    edit=dict(offset=owner['_offset'], code=owner['code'], kind='stat',
                                              stat_list=stat_list, stat=sid, param=param)))
    return sorted(groups.values(), key=lambda g: -g['prio'])


def preview_heading(it, field, value, data, char=None):
    """Titre de la ligne d'infobulle d'un élément si sa valeur était value, sans rien écrire (curseur en cours de
    glissement) : copie de l'objet avec la valeur changée (stats liées comprises), titre recalculé comme après
    l'enregistrement (edit_groups)."""
    e = field['edit']
    it = copy.deepcopy(it)
    owner = it if e['offset'] == it['_offset'] else next(s for s in it.get('socketed', []) if s['_offset'] == e['offset'])
    if e['kind'] == 'defense':
        owner['defense'] = value
    else:
        linked = set(linked_stats(owner, e['stat'], data, e['stat_list']))
        for s in owner[e['stat_list']]:
            if s['id'] == e['stat'] and s.get('param') == e.get('param') or s['id'] in linked - {e['stat']}:
                s['value'] = value
    same = lambda f: all(f['edit'].get(k) == e.get(k) for k in ('offset', 'kind', 'stat_list', 'stat', 'param'))
    return next((g['heading'] for g in edit_groups(it, data, char) if any(same(f) for f in g['fields'])), None)
