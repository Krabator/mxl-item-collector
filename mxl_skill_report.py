"""Relevé des lignes non calculées des explications de compétences, sur toutes les compétences données par les objets
du catalogue (suivi : docs/explications-competences.md). Outil de suivi lancé à la main, pas utilisé par l'application :
python mxl_skill_report.py [personnage.d2s]. Hors de mxl_skill_calc, qui ne dépend ainsi plus de mxl_skills (audit
du 07/10 : dépendance circulaire retirée).
"""
from mxl_skill_calc import skill_calc
from mxl_library import catalog
from mxl_catalog_tooltip import CatalogContext
from mxl_skills import skill_refs


def catalog_report(data, char=None):
    """Relevé des lignes non calculées sur toutes les compétences données par les objets du catalogue (suivi :
    docs/explications-competences.md) : {raison: (nombre de lignes, compétences, exemple)}, triée par nombre de lignes.
    Usage : python mxl_skill_report.py [personnage.d2s]."""
    calc, refs = skill_calc(data), {}
    for e in catalog(data):
        ctx = CatalogContext(e, data)
        for sid, lo, hi in skill_refs(ctx.lo, ctx.hi, data).values():
            a, b = refs.get(sid, (lo, hi))
            refs[sid] = (min(a, lo), max(b, hi))
    out = {}
    for sid, (lo, hi) in refs.items():
        reasons = []
        calc.grouped_lines(sid, lo, hi, char, reasons)
        for _, _, why in reasons:
            n, skills, example = out.get(why, (0, set(), data.skill_names.get(sid)))
            out[why] = (n + 1, skills | {sid}, example)
    return dict(sorted(out.items(), key=lambda kv: -kv[1][0]))


if __name__ == '__main__':
    import sys
    from mxl_data import Data
    from paths import DATA_DIR
    data = Data(DATA_DIR)
    who = None
    if len(sys.argv) > 1:
        from mxl_save import load_character
        who = load_character(sys.argv[1], data)
    report = catalog_report(data, who)
    print(f'{sum(n for n, _, _ in report.values())} lignes non calculées')
    for why, (n, skills, example) in report.items():
        print(f'{n:5d} lignes  {len(skills):4d} compétences  {why}  (ex. {example})')
