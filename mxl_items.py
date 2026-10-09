"""Ligne de commande de l'éditeur d'objets Median XL 2.14.5 : affichage du coffre (édition d'une stat : module
mxl_editor, python -m mxl_editor.cli).

Usage : python mxl_items.py <fichier.stash> [--data DOSSIER]
Le dossier data/ (tables extraites du jeu) se crée avec extract_data.py.
"""
import stat_ids as S
from i18n import tr
from mxl_data import Data
from paths import DATA_DIR
from mxl_rules import stat_range, rare_name, unique_name, runeword_name, stat_label, base_props
from mxl_save import parse_stash


def show(it, data=None):
    head = f"p{it.get('page', 0) + 1} ({it['x']},{it['y']}) {it['name']} [{it['code'].strip()}]"
    if 'quality' in it:
        head += f" — {tr('quality.' + it['quality'])}, ilvl {it['ilvl']}"
    if data and rare_name(it, data):
        head += f" « {rare_name(it, data)} »"
    if data and unique_name(it, data):
        head += f" « {unique_name(it, data)} »"
    if data and runeword_name(it, data):
        head += f" — runeword « {runeword_name(it, data)} »"
    print(head)
    base = base_props(it, data)
    if base: print('    ' + ', '.join(base))
    for s in it['stats']:
        p = f" param={s['param']}" if s['param'] is not None else ''
        rng = stat_range(it, s['id'], data, param=s.get('param')) if data else None
        r = ' ' + tr('cli.range', lo=rng[0], hi=rng[1]) if rng else ''
        note = '  ' + tr('detail.regen_note') if s['id'] == S.LIFE_REGEN else ''
        print(f"    stat {s['id']:>3} {stat_label(s, data):<28} {tr('cli.value')}={s['value']}{p}{r}{note}")
    if it.get('stats_runeword'):
        print(f"    -- {tr('detail.rw_stats')} --")
        for s in it['stats_runeword']:
            p = f" param={s['param']}" if s['param'] is not None else ''
            rng = stat_range(it, s['id'], data, 'stats_runeword', s.get('param')) if data else None
            r = ' ' + tr('cli.range', lo=rng[0], hi=rng[1]) if rng else ''
            print(f"    stat {s['id']:>3} {stat_label(s, data):<28} {tr('cli.value')}={s['value']}{p}{r}")
    for sub in it.get('socketed', []):
        print(f"    {tr('detail.socketed_one')}: ", end=''); show(sub, data)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=tr('cli.description'))
    ap.add_argument('fichier', metavar='FILE')
    ap.add_argument('--data', default=DATA_DIR)
    a = ap.parse_args()
    data = Data(a.data)
    for it in parse_stash(a.fichier, data):
        show(it, data)
