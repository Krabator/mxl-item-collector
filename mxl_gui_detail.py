"""Panneau de détail d'un objet (DetailPanel), affiché dans la fenêtre du coffre et dans l'écran Library : infobulle
(mise à jour localisée après une édition), bouton de transfert vers la bibliothèque, section Édition (curseurs,
qualité, étoiles de priorité), détails techniques (masqués par défaut, SHOW_TECHNICAL_DETAILS).

Le panneau ne connaît sa fenêtre qu'à travers DetailHost (données, personnage, priorités, édition permise, transfert,
enregistrement d'une édition, priorité changée) : fenêtre du coffre (mxl_gui.App) et écran Library
(mxl_library_gui.CollectionHost) l'implémentent chacune.
"""
import tkinter as tk
import ttkbootstrap as ttk
import stat_ids as S
from i18n import tr
from mxl_rules import (stat_label, stat_range, special_name, base_props, stat_hidden, text_missing, is_rune, mods_stats,
                       gem_group, GEM_GROUPS)
from mxl_edit import edit_groups, item_quality, priority_profile, DEFAULT_PRIORITY
from mxl_ext import hook
from mxl_skills import skill_refs, cast_only_skills
from mxl_skill_view import SkillHover
from paths import SKILL_ICONS_DIR
from mxl_stat_text import stat_lines
from mxl_drop import item_drop_lines
from mxl_orbs import orb_lines, orb_mismatch
from mxl_tooltip import item_tooltip, name_color, all_stats, section_name, TooltipContext
from mxl_theme import GAME_COLORS, DETAIL_BG, DETAIL_DIM, SECTION, BAD, HIDDEN, FONT, TIP_BG
import mxl_tooltip_view as tooltip_view

# affichage des « Technical details » sous l'infobulle (plages, n° de stat…) : réglage du code uniquement,
# non modifiable depuis l'interface ; masqués par défaut
SHOW_TECHNICAL_DETAILS = False
# calques de l'image d'un objet affichés (grille, image de la collection) : réglage du code uniquement (docs/ihm.md)
LAYERS_SHOWN = (1, 2, 3)
# ligne de curseur : longueur du curseur (px) et largeur des bornes (caractères) de part et d'autre, fixes : curseurs
# et étoiles alignés d'une ligne à l'autre, ligne dans la largeur du panneau
SLIDER_LENGTH, BOUND_WIDTH = 200, 6


def forward_wheel(widget, text):
    """Molette au-dessus de widget (et de ses enfants) : défilement de la zone de texte text, du même pas que la molette
    au-dessus du texte (liaison de la classe Text de Tk : -delta / 3 pixels). Sous Windows, la molette va au widget
    sous la souris : un curseur, une étiquette ou une image insérés dans le panneau la gardaient sans rien faire."""
    def scroll(e):
        text.yview_scroll(-e.delta // 3 if e.delta >= 0 else (2 - e.delta) // 3, 'pixels')
        return 'break'
    todo = [widget]
    while todo:
        w = todo.pop()
        w.bind('<MouseWheel>', scroll, add='+')
        todo += w.winfo_children()


def setup_detail_tags(t):
    """Styles d'un panneau de détail (coffre et écran Library : rendu identique) : titres, textes atténués, sections,
    valeurs hors plage, stats cachées, objets sertis, infobulle, titres de la section Édition."""
    t.tag_configure('title', font=(FONT, 13, 'bold'), spacing1=2, spacing3=2)
    # « Item quality » (texte orange inséré dans le panneau) : fond du panneau, pas celui du thème (bande plus claire)
    st = ttk.Style()
    st.configure('DetailWarning.TLabel', background=DETAIL_BG, foreground=st.colors.warning)
    t.tag_configure('sub', font=(FONT, 10, 'bold'))
    t.tag_configure('dim', foreground=DETAIL_DIM)
    t.tag_configure('section', foreground=SECTION, font=(FONT, 9, 'bold'), spacing1=10, spacing3=2)
    # titres des sections Édition et Mystic Orbs : plus grands, non gras, aérés (décisions du 07/10 et 08/10)
    t.tag_configure('edittitle', foreground=SECTION, font=(FONT, 12), spacing1=4, spacing3=10)
    # bloc des Mystic Orbs : fond noir de l'infobulle, juste dessous, séparé d'elle par un mince filet du fond du
    # panneau (orbgap) ; contenu aligné à gauche avec une marge (décision sur maquette, 08/10)
    t.tag_configure('orbgap', font=(FONT, 4))
    t.tag_configure('orbbox', background=TIP_BG, lmargin1=14, lmargin2=14)
    t.tag_configure('orbtitle', foreground=SECTION, font=(FONT, 12), spacing1=6, spacing3=6)   # taille du titre Editing
    t.tag_configure('orbline', foreground=GAME_COLORS['3'], font=(FONT, 10), spacing1=3, spacing3=1)
    t.tag_configure('orbnote', foreground=DETAIL_DIM, font=(FONT, 9), spacing1=6, spacing3=6)
    t.tag_configure('rowgap', spacing3=8)   # espace sous une ligne de contrôles (Ethereal / Max sockets, Quantity)
    t.tag_configure('bad', foreground=BAD)
    t.tag_configure('hidden', foreground=HIDDEN)
    t.tag_configure('socket', lmargin1=18, lmargin2=18)
    tooltip_view.setup_tags(t)
    t.tag_configure('edithead', foreground=GAME_COLORS['3'], font=(FONT, 10), spacing1=6)


def item_color(it, data):
    return GAME_COLORS[name_color(it, data)]


def main_line(name):
    """Ligne principale d'un nom du jeu sur plusieurs lignes : celle du haut en jeu, qui affiche ces textes de bas en
    haut, donc la dernière (« Cube Reagent\nArcane Crystal » -> « Arcane Crystal », « Mystic Orb\nCrystal of Tears »
    -> « Crystal of Tears ») ; les autres restent dans l'infobulle."""
    parts = [p.strip() for p in (name or '').split('\n') if p.strip()]
    return parts[-1] if parts else ''


def full_name(it, data):
    """Nom complet d'un objet pour la barre du bas, sur une ligne : nom propre (unique, set, rare, runeword) — nom de
    base, chacun réduit à sa ligne principale (main_line, décision du 08/10)."""
    special = special_name(it, data)
    base = main_line(it['name'])
    return f"{main_line(special)} — {base}" if special else base


class DetailHost:
    """Ce que le panneau de détail demande à la fenêtre qui l'affiche. Valeurs par défaut : lecture seule (curseurs
    grisés, pas de transfert), priorités non propagées. data, char et saved_priorities sont fournis par la fenêtre."""
    editing = False   # édition des valeurs permise (curseurs actifs, écriture au relâchement)

    def size(self, it):
        """Taille de l'objet en cases (w, h)."""
        return self.data.base(it['code']).size

    def char_for(self, it):
        """Personnage de référence de l'objet it (exigences, bonus) : celui de la fenêtre."""
        return self.char

    def can_transfer(self, it):
        """Bouton de transfert vers la collection sous l'infobulle ?"""
        return False

    def transfer(self, it):
        """Clic sur le bouton de transfert."""

    def commit_edit(self, it, edit):
        """Écrit l'édition (dict de mxl_edit, avec 'value') dans le fichier de l'objet et le relit : (True, objet relu
        ou None) si c'est fait, (False, None) si c'est refusé (erreur déjà signalée)."""
        return False, None

    def edit_done(self, it, line, value):
        """Édition enregistrée : ligne de l'infobulle concernée (à jour) et valeur écrite, pour l'annoncer."""

    def priorities_changed(self, priorities, key):
        """Priorité d'une stat changée dans ce panneau (dict des priorités du profil, clé de la stat) : autres vues à
        mettre à jour (tableau de la collection, autre panneau)."""


class DetailPanel:
    """Panneau de détail : zone de texte text, fenêtre host (DetailHost). show(it) affiche un objet (None : invite)."""

    def __init__(self, text, host):
        self.detail, self.host = text, host
        self.item = None           # objet affiché (relu après une édition)
        self.edit_widgets = []     # widgets posés dans le texte (bouton de transfert, qualité, lignes de curseurs)
        self.edit_scales = []      # curseurs de la section Édition
        self.edit_heads = []       # (marque du titre, champs) pour les mises à jour localisées
        self.head_lines = {}       # marque du titre -> nombre de lignes du titre
        self.edit_groups_shown = []
        self.stars = {}            # clé de priorité -> [[3 étoiles] par curseur de cette stat]
        self.priorities = {}       # priorités du profil de l'objet affiché (dict partagé si le profil est conservé)
        self.quality_label = None
        self.tip_lines = []
        # compétences de l'infobulle : nom souligné en pointillé, explication au survol (mxl_skill_view)
        self.hover = SkillHover(text, SKILL_ICONS_DIR)
        # partie active de la section Editing (module mxl_editor, point d'accroche panel_editor) ; None sans le module
        make = hook('panel_editor')
        self.editor = make(self) if make else None

    data = property(lambda self: self.host.data)
    char = property(lambda self: self.host.char_for(self.item))   # personnage de référence de l'objet affiché

    def show(self, it):
        t = self.detail
        self.item = it
        self.hover.clear()
        for w in self.edit_widgets:   # curseurs de la section Édition précédente
            w.destroy()
        self.edit_widgets = []
        self.stars = {}   # étoiles du panneau précédent détruites : plus de mise à jour sur place
        self.edit_scales = []   # curseurs du panneau précédent (détruits)
        t.configure(state='normal')
        t.delete('1.0', 'end')
        if it is None:
            t.insert('end', tr('detail.click'), 'dim')
        else:
            self.write_tooltip(it)
            self.write_orbs(it)   # juste sous l'infobulle (bloc noir)
            self.write_drop(it)
            self.write_transfer(it)
            self.write_edit(it)
            if SHOW_TECHNICAL_DETAILS:
                t.insert('end', '\n' + tr('detail.tech') + '\n', 'section')
                self.write_item(it)
        t.configure(state='disabled')

    def embed(self, widget):
        """Insère widget (bouton, étiquette, ligne de curseur) à la fin du panneau ; molette renvoyée au panneau."""
        self.detail.window_create('end', window=widget, padx=12)
        forward_wheel(widget, self.detail)
        self.edit_widgets.append(widget)

    def end_row(self):
        """Fin d'une ligne de contrôles de la section Édition (Ethereal / Max sockets, Quantity) : saut de ligne et
        espace en dessous (tag 'rowgap', posé sur la ligne du widget)."""
        t = self.detail
        t.insert('end', '\n')
        t.tag_add('rowgap', 'end - 2 lines linestart', 'end - 1 lines')

    def write_orbs(self, it):
        """Juste sous l'infobulle, seulement si l'objet a reçu au moins un orbe : bloc noir des Mystic Orbs appliqués
        (mxl_orbs.orb_lines) : titre, une ligne par orbe (nom souligné en pointillé, explication au survol :
        self.hover.attach_orbs, comme les compétences), note « Base in red… » en bas s'il y a un écart."""
        found = orb_lines(it, self.data)
        if not found:
            return
        title, lines = found
        t = self.detail
        t.insert('end', ' \n', 'orbgap')   # mince séparation avec l'infobulle
        t.insert('end', title + '\n', ('orbbox', 'orbtitle'))
        spans = []
        for rows, text, names in lines:
            line = int(t.index('end - 1 chars').split('.')[0])
            t.insert('end', '   ' + text + '\n', ('orbbox', 'orbline', 'orb'))
            spans += [(f'{line}.{3 + a}', f'{line}.{3 + b}', k) for k, a, b in names]
        self.hover.attach_orbs(spans, self.data)
        if orb_mismatch(it, self.data):   # « B » rouge dans l'infobulle : explication (décision du 08/10)
            key = 'orbs.mismatch_honorific' if it.get('quality') == 'honorific' else 'orbs.mismatch'
            t.insert('end', tr(key) + '\n', ('orbbox', 'orbnote'))
        else:
            t.insert('end', ' \n', ('orbbox', 'orbnote'))   # marge du bas du bloc

    def write_drop(self, it):
        """Sous l'infobulle : où l'objet tombe (plage de niveaux de zone, sources spéciales) et, pour un unique sacré,
        sa part parmi les uniques de sa base (mxl_drop), s'ils sont connus."""
        lines = item_drop_lines(it, self.data)
        if lines:
            self.detail.insert('end', '\n' + '\n'.join(lines) + '\n', 'dim')

    def write_transfer(self, it):
        """Sous l'infobulle : bouton de transfert vers la collection, si la fenêtre le permet (host.can_transfer)."""
        if not self.host.can_transfer(it):
            return
        btn = ttk.Button(self.detail, text=tr('library.transfer_one'), bootstyle='warning-outline',
                         command=lambda: self.host.transfer(it))
        self.detail.insert('end', '\n')
        self.embed(btn)
        self.detail.insert('end', '\n')

    def write_edit(self, it):
        """Section qualité / édition : une ligne de titre par ligne de l'infobulle ayant de la variance, puis un curseur
        par élément variable (source B / RW / J, min / max) et les étoiles de priorité ; note de qualité en tête. Base :
        sans titre (la note en tient lieu), curseurs grisés (position de chaque valeur dans sa plage). Module mxl_editor avec le
        droit d'édition (host.editing) : titre « Editing », lignes Ethereal / Max sockets et Quantity, curseurs actifs
        (self.editor : write_head, edit_preview, edit_commit)."""
        t = self.detail
        groups = edit_groups(it, self.data, self.char)
        self.edit_heads = []   # (marque du titre, champs) pour les mises à jour localisées
        self.head_lines = {}   # marque du titre -> nombre de lignes du titre
        self.quality_label = None   # widget du panneau précédent détruit
        if self.editor:
            self.editor.reset()
        editing = self.editor is not None and self.host.editing
        if editing:
            if not self.editor.write_head(it, groups):   # rien de modifiable (message affiché par le module)
                return
        elif groups:   # lecture : pas de titre, la note « Item quality: x% » en tient lieu (décision du 08/10)
            t.insert('end', '\n', 'section')   # ligne d'espace : petite
        if not groups:
            return
        # qualité de l'objet (curseurs pondérés par les priorités), mise à jour sur place (étiquette)
        profile, kept = priority_profile(it, self.data)
        # objet sans profil conservé (magique, rare, runeword, objet serti…) : poids par défaut, pas d'étoiles
        self.priorities = self.host.saved_priorities.setdefault(profile, {}) if kept else {}
        self.edit_groups_shown = groups
        self.edit_scales = []
        self.stars = {}   # clé de priorité -> [[3 étoiles] par curseur de cette stat]
        self.quality_label = ttk.Label(t, text='', font=(FONT, 11, 'bold'), style='DetailWarning.TLabel')
        self.embed(self.quality_label)
        t.insert('end', ('  ' + tr('edit.priorities_kept') if kept else '') + '\n', 'dim')
        self.show_quality()
        for k, g in enumerate(groups):
            mark = f'edh{k}'
            t.mark_set(mark, 'end - 1 chars')
            t.mark_gravity(mark, 'left')
            self.edit_heads.append((mark, g['fields']))
            self.head_lines[mark] = g['heading'].count('\n') + 1
            t.insert('end', g['heading'] + '\n', ('edithead',))
            for f in g['fields']:
                row = ttk.Frame(t)
                ttk.Label(row, text=f['label'], width=9, bootstyle='secondary').pack(side='left')
                var = tk.DoubleVar(value=f['value'])
                # bornes (valeurs de l'infobulle) de part et d'autre du curseur, largeur fixe : curseurs et étoiles
                # alignés d'une ligne à l'autre ; moins bonne à gauche, meilleure à droite
                low = ttk.Label(row, text=f['shown'](f['lo']), width=BOUND_WIDTH, anchor='e', bootstyle='secondary')
                high = ttk.Label(row, text=f['shown'](f['hi']), width=BOUND_WIDTH, anchor='w', bootstyle='secondary')
                scale = ttk.Scale(row, from_=f['lo'], to=f['hi'], variable=var, length=SLIDER_LENGTH)
                if editing:   # module : aperçu pendant le glissement, écriture au relâchement
                    scale.configure(command=lambda v, var=var, f=f: self.editor.edit_preview(var, f, self.item or it))
                    scale.bind('<ButtonRelease-1>',
                               lambda e, var=var, f=f, g=g: self.editor.edit_commit(self.item or it, g, f, var))
                else:   # lecture : curseur grisé et immobile (position de la valeur dans sa plage)
                    scale.state(['disabled'])
                self.edit_scales.append(scale)
                low.pack(side='left')
                scale.pack(side='left', padx=4)
                high.pack(side='left')   # valeur : dans le titre au-dessus (en bleu), pas répétée ici
                stars = []   # priorité : 1 à 3 étoiles, clic = nouvelle priorité (profil conservé seulement)
                for n in ((1, 2, 3) if kept else ()):
                    s_ = ttk.Label(row, text='', cursor='hand2', font=(FONT, 12), bootstyle='warning')
                    s_.pack(side='left', padx=(8 if n == 1 else 0, 0))
                    s_.bind('<Button-1>', lambda e, key=f['priority_key'], n=n: self.set_priority(key, n))
                    stars.append(s_)
                if stars:
                    self.stars.setdefault(f['priority_key'], []).append(stars)
                    self.show_stars(f['priority_key'])
                self.embed(row)
                t.insert('end', '\n')

    def _pixels(self, a, b):
        """Hauteur en pixels du texte du panneau entre deux positions (lignes hors de la vue comprises)."""
        r = self.detail.count(a, b, 'update', 'ypixels')
        return (r[0] if isinstance(r, tuple) else r) or 0

    def edit_title_offset(self):
        """Distance (pixels) entre le haut de la vue et le titre de la section Édition, ou None sans titre."""
        t = self.detail
        ranges = t.tag_ranges('edittitle')
        if not ranges:
            return None
        return self._pixels('1.0', ranges[0]) - t.yview()[0] * self._pixels('1.0', 'end')

    def keep_edit_title(self, offset):
        """Après une reconstruction du panneau : défilement tel que le titre de la section Édition soit à la même
        distance du haut de la vue qu'avant (edit_title_offset) ; l'infobulle a pu gagner ou perdre des lignes."""
        t = self.detail
        t.update_idletasks()
        ranges = t.tag_ranges('edittitle')
        if offset is None or not ranges:
            return
        total = self._pixels('1.0', 'end')
        if total:
            t.yview_moveto(max(0.0, (self._pixels('1.0', ranges[0]) - offset) / total))

    def show_quality(self):
        """Qualité de l'objet affiché (item_quality), en tête de la section Édition."""
        q = item_quality(self.edit_groups_shown, self.priorities)
        self.quality_label.configure(text=tr('edit.quality', q=round(q)) if q is not None else '')

    def show_stars(self, key):
        """Étoiles pleines / vides des curseurs de cette clé de priorité."""
        n = self.priorities.get(key, DEFAULT_PRIORITY)
        for stars in self.stars.get(key, []):
            for k, s_ in enumerate(stars):
                s_.configure(text='★' if k < n else '☆')

    def set_priority(self, key, n):
        """Clic sur une étoile : priorité de cette stat (1 Low, 2 Medium, 3 High) dans le profil de l'objet affiché
        (enregistrée à la fermeture si le profil est conservé)."""
        if n == DEFAULT_PRIORITY:
            self.priorities.pop(key, None)   # valeur par défaut : rien à retenir
        else:
            self.priorities[key] = n
        self.show_stars(key)
        self.show_quality()
        self.host.priorities_changed(self.priorities, key)   # autres vues mises à jour sur place

    def priorities_updated(self, priorities, key):
        """Priorités changées ailleurs (autre panneau) : étoiles et qualité mises à jour sur place, sans reconstruire
        le panneau (ni clignotement ni défilement), si ce panneau affiche le même profil."""
        if self.stars and self.priorities is priorities:
            self.show_stars(key)
            self.show_quality()

    def head_span(self, mark):
        """Début et fin du titre d'un groupe de curseurs (plusieurs lignes pour des stats liées, ✅ Athame)."""
        n = self.head_lines.get(mark, 1)
        return f'{mark} linestart', f'{mark} + {n - 1} lines lineend'

    def head_text(self, mark):
        return self.detail.get(*self.head_span(mark))

    def set_head(self, mark, text):
        """Remplace le titre d'un groupe de curseurs."""
        self.detail.delete(*self.head_span(mark))
        self.detail.insert(f'{mark} linestart', text, ('edithead',))
        self.head_lines[mark] = text.count('\n') + 1

    def write_tooltip(self, it):
        """Description comme l'infobulle du jeu (mxl_tooltip.item_tooltip)."""
        self.tip_lines = item_tooltip(it, self.data, self.char)
        # marque « tip0 » au début de la 1re ligne : mises à jour localisées après une édition (refresh_detail)
        tooltip_view.write_tooltip(self.detail, self.tip_lines, mark='tip0')
        self.attach_skills(it)

    def attach_skills(self, it):
        """Compétences données par l'objet (stats de l'objet, du runeword et des objets sertis) : survol actif."""
        stats = all_stats(it, self.data)
        heading = section_name(TooltipContext(it, self.data, self.char))
        self.hover.attach(skill_refs(stats, stats, self.data, mentions=True), self.data, self.char, heading,
                          cast_only_skills(stats, self.data))

    def refresh_detail(self, it):
        """Après une édition : ne réécrit que les lignes de l'infobulle et les titres de la section Édition dont le
        texte a changé ; les curseurs et le reste du panneau ne bougent pas (pas de clignotement)."""
        t = self.detail
        t.configure(state='normal')
        new = item_tooltip(it, self.data, self.char)
        old = self.tip_lines
        if len(new) != len(old):   # nombre de lignes changé : bloc de l'infobulle réécrit (curseurs intacts)
            t.delete('tip0', f'tip0 + {len(old)} lines')
            for k, segs in enumerate(new):
                tooltip_view.insert_line(t, f'tip0 + {k} lines', segs)
                t.insert(f'tip0 + {k} lines lineend', '\n', 'tip')
        else:
            for k, (a, b) in enumerate(zip(old, new)):
                if a != b:
                    line = f'tip0 + {k} lines'
                    t.delete(f'{line} linestart', f'{line} lineend')
                    tooltip_view.insert_line(t, f'{line} linestart', b)
        self.tip_lines = new
        # titres de la section Édition et valeurs de référence des curseurs
        for (mark, fields), g in zip(self.edit_heads, edit_groups(it, self.data, self.char)):
            if self.head_text(mark) != g['heading']:
                self.set_head(mark, g['heading'])
            for f, nf in zip(fields, g['fields']):
                f['value'], f['edit'] = nf['value'], nf['edit']
        if self.quality_label:   # pas de qualité : objet sans curseur (quantité seule)
            self.show_quality()   # les champs de edit_groups_shown sont ceux mis à jour ci-dessus
        self.attach_skills(it)   # lignes réécrites : soulignements des compétences reposés
        t.configure(state='disabled')

    def color_tag(self, col):
        tag = 'c' + col[1:]
        self.detail.tag_configure(tag, foreground=col)
        return tag

    def write_item(self, it, socketed=False, parent=None):
        t, d = self.detail, self.data
        extra = ('socket',) if socketed else ()
        col = self.color_tag(item_color(it, d))
        if socketed:
            t.insert('end', '◆ ' + it['name'] + '\n', ('sub', col) + extra)
        w, h = self.host.size(it)
        q = it.get('quality')
        info = [tr('quality.' + q) if q else tr('detail.rune' if is_rune(it, d) else 'detail.simple')]
        if 'runeword' in it: info.append(tr('detail.runeword'))
        if 'ilvl' in it: info.append(f"ilvl {it['ilvl']}")
        info.append(f"code {it['code'].strip()}")
        if not socketed: info.append(tr('detail.cell', x=it['x'], y=it['y'], w=w, h=h))
        t.insert('end', ' · '.join(info) + '\n', ('dim',) + extra)
        for b in base_props(it, d):
            t.insert('end', b + '\n', extra)
        groups = d.gems.get(it['code'])
        if socketed and groups and parent is not None:
            # gemme / rune sertie : bonus non stockés dans l'objet, tirés de gems.bin selon le type du porteur
            g = gem_group(parent, d)
            t.insert('end', tr('detail.gem_bonus', group=d.key(GEM_GROUPS[g]).rstrip(':')) + '\n',
                     ('dim',) + extra)
            for _, txt, _, _ in stat_lines(mods_stats(groups[g], d), d, self.char):
                t.insert('end', f"   {txt}\n", extra)
        self.write_stats(it, 'stats', None, extra)
        if it.get('stats_runeword'):
            self.write_stats(it, 'stats_runeword', tr('detail.rw_stats'), extra)
        if it.get('socketed'):
            t.insert('end', tr('detail.socketed_one' if len(it['socketed']) == 1 else 'detail.socketed_many') + '\n',
                     'section')
        for sub in it.get('socketed', []):
            self.write_item(sub, socketed=True, parent=it)

    def write_stats(self, it, stat_list, title, extra):
        t, d = self.detail, self.data
        stats = it.get(stat_list) or []
        if title:
            t.insert('end', title + '\n', ('section',) + extra)
        elif stats:
            t.insert('end', tr('detail.stats') + '\n', ('section',) + extra)
        for s in stats:
            hidden = stat_hidden(s['id'], d, s['value'])
            rng = stat_range(it, s['id'], d, stat_list, s.get('param'))
            style = ('hidden',) + extra if hidden else extra
            t.insert('end', f"{s['value']:>5}  ", style)
            label = stat_label(s, d)
            t.insert('end', f"{tr('detail.hidden')} {'' if text_missing(label) else label}".rstrip() if hidden else label,
                     style)
            if rng:
                out = not rng[0] <= s['value'] <= rng[1]
                t.insert('end', f"   [{rng[0]}–{rng[1]}]", ('bad' if out else 'dim',) + extra)
            if s['id'] == S.LIFE_REGEN:
                t.insert('end', '   ' + tr('detail.regen_note'), ('dim',) + extra)
            if s['id'] == S.POISON_MIN:   # poison : 1/256 par frame pendant la durée (frames de 1/25 s)
                dur = next((x['value'] for x in stats if x['id'] == S.POISON_LENGTH), 0)
                if dur:
                    t.insert('end', '   ' + tr('detail.poison_note', dmg=round(s['value'] * dur / 256), sec=f'{dur / 25:g}'),
                             ('dim',) + extra)
            t.insert('end', f"   #{s['id']}\n", ('hidden',) + extra)
