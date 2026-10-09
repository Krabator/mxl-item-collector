"""Explication d'une compétence (infobulle du jeu) : point d'entrée, sans interface (testable seul).

Façade des modules de l'explication, qui s'appellent dans un seul sens :
  mxl_skill_lines      mise en forme des lignes : table des formats (FORMATS), lignes grises, taux de conversion ;
  mxl_skill_formula    interpréteur des formules du jeu : tables des variables (VARIABLES) et des fonctions ;
  mxl_skill_mechanics  mécaniques du jeu (dégâts, durées, mana, recharge, invocations, projectiles) et interface du
                       personnage de référence ;
  mxl_skill_data       champs des tables, n° de textes et de stats, Record, Grey, Unsupported, calculs entiers.
skill_calc(data) : le calculateur (SkillCalc) de ces données. Relevé des lignes non calculées : mxl_skill_report.

Personnage de référence (mxl_save.load_character, ou None : écran Library ; ses totaux : mxl_char_stats). Une valeur
inconnue (Unsupported) devient une ligne grise « … varies by character » / « … not calculated », ou une note ; vie /
mana actuelles : taux de conversion en gris. Adresses du jeu : docs/format-stash-mxl-2.14.5.md.
✅ Captures en jeu : Ignis Fatuus, Flamefront (Kalidor), Blood Skeleton (Nekratall). Relevé sur tout le catalogue :
python mxl_skill_report.py [personnage.d2s] ; photo de toutes les explications : tests/reference/skill_lines.txt
(test « photo de tout le catalogue » ; changement voulu : python tests/run_tests.py --update -k photo).
"""
import mxl_skill_lines as L
import mxl_skill_mechanics as M
from mxl_skill_formula import FormulaEngine
# noms publics gardés à leur adresse d'origine (application et tests)
from mxl_skill_data import Grey, Unsupported, level_brackets, diminishing, muldiv
from mxl_skill_mechanics import energy_bonus
from mxl_skill_lines import desc_line, values, mana_text, PoolProbe, FORMATS

__all__ = ['SkillCalc', 'skill_calc', 'KNOWN_FORMATS', 'Grey', 'Unsupported', 'level_brackets',
           'diminishing', 'muldiv', 'energy_bonus', 'desc_line', 'values', 'mana_text', 'PoolProbe', 'FORMATS']

KNOWN_FORMATS = frozenset(FORMATS)


class SkillCalc(FormulaEngine):
    """Tables des compétences et de leurs formules (lues une fois par dossier de données), avec les lignes de leur
    explication et les mécaniques du jeu appelées par l'application et les tests."""

    def grouped_lines(self, skill, lo, hi, char=None, reasons=None, colors=False, mana=True):
        return L.grouped_lines(self, skill, lo, hi, char, reasons, colors, mana)

    def lines(self, skill, lo, hi, char=None):
        """Textes des lignes chiffrées, dans l'ordre (voir mxl_skill_lines.grouped_lines)."""
        return [t for _, texts in self.grouped_lines(skill, lo, hi, char) for t in texts]

    def weapon_damage(self, skill):
        return L.weapon_damage(self, skill)

    def shot_lines(self, skill, lo, hi, char=None):
        return L.shot_lines(self, skill, lo, hi, char)

    def buff_lines(self, skill, lo, hi, char=None):
        return L.buff_lines(self, skill, lo, hi, char)

    def heal_lines(self, skill, lo, hi, char=None):
        return L.heal_lines(self, skill, lo, hi, char)

    def spin_lines(self, skill, lo, hi, char=None):
        return L.spin_lines(self, skill, lo, hi, char)

    def nova_lines(self, skill, lo, hi, char=None):
        return L.nova_lines(self, skill, lo, hi, char)

    def curse_lines(self, skill, lo, hi, char=None):
        return L.curse_lines(self, skill, lo, hi, char)

    def ring_chain_lines(self, skill, lo, hi, char=None):
        return L.ring_chain_lines(self, skill, lo, hi, char)

    def turret_lines(self, skill, lo, hi, char=None):
        return L.turret_lines(self, skill, lo, hi, char)

    def delayed_ring_lines(self, skill, lo, hi, char=None):
        return L.delayed_ring_lines(self, skill, lo, hi, char)

    def fire_ground_lines(self, skill, lo, hi, char=None):
        return L.fire_ground_lines(self, skill, lo, hi, char)

    def shatter_lines(self, skill, lo, hi, char=None):
        return L.shatter_lines(self, skill, lo, hi, char)

    def ring_burst_lines(self, skill, lo, hi, char=None):
        return L.ring_burst_lines(self, skill, lo, hi, char)

    def seconds(self, frames):
        return L.seconds(self, frames)

    def elem_damage(self, skill, lvl, char, which, spell=True):
        return M.elem_damage(self, skill, lvl, char, which, spell)

    def elem_length(self, skill, lvl, char):
        return M.elem_length(self, skill, lvl, char)


_CACHE = {}


def skill_calc(data):
    """SkillCalc de ces données (un par objet Data)."""
    if id(data) not in _CACHE:
        _CACHE.clear()
        _CACHE[id(data)] = (data, SkillCalc(data))
    return _CACHE[id(data)][1]
