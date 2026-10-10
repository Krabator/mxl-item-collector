"""Écran « Library » : catalogue des uniques et objets de set (mxl_library), avancement, recherche et filtres.

Fenêtre séparée de la fenêtre principale (une seule ouverte à la fois), mise à jour quand un coffre ouvert apporte
de nouvelles découvertes. Chaque ligne affiche le nom de l'entrée ET son objet de base : les tiers d'un même unique
(ex. Jared's Fragmentor sur Claymore (1) à (4)) sont des entrées distinctes.
Recherche (mxl_library_search) : texte complet de chaque entrée (infobulle, bonus de son set, classe des compétences
données), préparé en arrière-plan à l'ouverture de l'écran ; tous les mots exigés, « "…" » = expression exacte ;
lignes trouvées surlignées dans le panneau de détail.
Case « Group by set » (cochée par défaut, retenue dans les réglages) : objets de set regroupés sous une ligne par set
(progression sur les pièces trouvées, pièces rangées en information), sets par ordre alphabétique après les uniques ;
ligne d'un set sélectionnée : pièces et bonus du set (sets.bin) dans le panneau de détail.
Onglet « Storage » : mxl_library_storage.StorageTab ; image de l'objet : mxl_library_image.DetailImage (classes
mixtes) ; fenêtre de transfert : mxl_library_transfer ; lien avec la fenêtre principale : mxl_library_ui.LibraryUI.
"""
import os
import time
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from i18n import tr
from mxl_gui_detail import DetailHost, DetailPanel, setup_detail_tags, forward_wheel
from mxl_library_view import DetailSelection, slot_name
from mxl_rules import table_row, mods_stats
from mxl_tooltip import requirements_unmet, item_tooltip
from mxl_drop import entry_drop_lines
from mxl_catalog_tooltip import catalog_tooltip, catalog_name, set_bonus_lines, set_name, CatalogContext
from mxl_skills import skill_refs, cast_only_skills
from mxl_stat_text import segments
from mxl_library_search import index_steps, parse_query, search, line_matches, skill_classes
import settings
from mxl_library import (CATEGORIES, FAMILIES, JEWELRY_TIER, entry_tier, ETHEREAL, two_variants, rank, restore_destroyed, take_out, LibraryError)
from mxl_save import EditError
from mxl_widgets import AutoScrollbar
from mxl_format import FormatError
from mxl_theme import (DETAIL_BG, DETAIL_FG, DETAIL_WIDTH, DETAIL_PADX, FOUND_COLOR, MISSING_COLOR, STORED_COLOR,
                       SET_GROUP_COLOR, CELL_OK, CELL_KO, FONT, SEARCH_HIT)
import mxl_tooltip_view as tooltip_view
from mxl_library_storage import StorageTab
from mxl_library_image import DetailImage, IMAGE_PAD
from mxl_ext import hook

ETHEREAL_IMAGE_OPACITY = 0.5   # opacité de l'image d'une entrée non rangée en vue Ethereal (normale : 100 %)
# colonnes du tableau, dans l'ordre ; stored / ethereal : qualité de l'exemplaire rangé normal / éthéré
# (coffre de la découverte : panneau de détail seulement, plus de colonne « Found in » depuis le 27/09)
COLUMNS = ('name', 'base', 'category', 'level_req', 'stored', 'ethereal', 'date')
ZWSP = '\u200b'   # caractère invisible de tête des lignes surlignées (voir LibraryWindow.highlight)
INDEX_DELAY_MS, INDEX_SLICE_MS = 50, 12   # texte de recherche : délai après l'ouverture, durée d'une tranche de calcul
SET_ROW = 'setgroup:'   # identifiant des lignes de set du tableau (« setgroup:<n° du set> »), parents de leurs pièces
WIDTHS = dict(name=220, base=180, category=85, level_req=70, stored=115, ethereal=115, date=120)


class LibraryWindow(StorageTab, DetailImage):
    """Écran « Library » : onglets Collection (catalogue, avancement, filtres, recherche) et Storage (StorageTab),
    panneau de détail (DetailPanel, image : DetailImage), sortie et copie vers le coffre, restauration."""

    def __init__(self, app):
        self.app = app
        self.sort = ('name', False)   # colonne de tri, ordre décroissant ?
        # n° du set de chaque objet de set du catalogue ; lignes de set dépliées (retenues dans les réglages)
        self.set_ids = {k: table_row(k, app.data)['set_id'] for k, e in app.catalog.items() if e['kind'] == 'set'}
        self.open_sets = set(settings.get('library_open_sets', []))
        # texte de recherche de chaque entrée (environ 0,5 s de calcul) : préparé par petites étapes entre deux
        # rafraîchissements de l'écran, après l'ouverture de la fenêtre (index_tick) ; terminé d'un coup si une
        # recherche est tapée avant la fin (finish_index). Pas de fil d'arrière-plan : en Python, il bloque l'interface
        # pendant le calcul (ouverture mesurée à 1,35 s au lieu de 0,25 s).
        self.index, self.classes = {}, skill_classes(app.data)
        self.index_job, self.index_after = index_steps(app.catalog, app.data, self.index), None
        self.win = ttk.Toplevel(master=app.root, title=tr('library.title'))   # fenêtre au thème de l'application
        self.win.geometry('1600x700')   # tableau + panneau de détail de la largeur de celui du coffre
        self.win.protocol('WM_DELETE_WINDOW', self.close)
        self.build()
        self.refresh()
        self.index_after = self.win.after(INDEX_DELAY_MS, self.index_tick)

    def index_tick(self):
        """Quelques étapes du texte de recherche (INDEX_SLICE_MS au plus), puis la main est rendue à l'interface."""
        self.index_after = None
        end = time.perf_counter() + INDEX_SLICE_MS / 1000
        for _ in self.index_job or ():
            if time.perf_counter() >= end:
                self.index_after = self.win.after(1, self.index_tick)
                return
        self.index_job = None   # terminé

    def finish_index(self):
        """Termine tout de suite le texte de recherche (recherche tapée avant la fin de la préparation)."""
        for _ in self.index_job or ():
            pass
        self.index_job = None

    # ---------- construction ----------
    def build(self):
        top = ttk.Frame(self.win, padding=10)
        top.pack(side='top', fill='x')
        # onglets : Collection (uniques et sets, avancement) / Storage (supérieurs stockés, hors collection)
        self.mode = tk.StringVar(value='collection')
        tabs = ttk.Frame(top)
        tabs.pack(side='top', fill='x', pady=(0, 8))
        self.btn_modes = {}
        for m in ('collection', 'storage'):
            self.btn_modes[m] = ttk.Radiobutton(tabs, text=tr('library.tab.' + m), value=m, variable=self.mode,
                                                bootstyle='warning-toolbutton', command=self.switch_mode)
            self.btn_modes[m].pack(side='left', padx=(0, 4))
        self.progress_box = ttk.Frame(top)   # avancement de la collection (pas dans l'onglet Storage)
        self.progress_box.pack(side='top', fill='x')
        self.progress_label = ttk.Label(self.progress_box, text='', font=(FONT, 12, 'bold'), bootstyle='warning')
        self.progress_label.pack(side='top', anchor='w')
        self.progress = ttk.Progressbar(self.progress_box, maximum=1.0, bootstyle='warning')
        self.progress.pack(side='top', fill='x', pady=(4, 8))
        # remise à zéro des découvertes : volontairement discrète (clic droit sur l'avancement, aucun bouton visible ;
        # 10/10), avec confirmation (reset_found)
        self.reset_menu = tk.Menu(self.win, tearoff=False)
        self.reset_menu.add_command(label=tr('library.reset_found'), command=self.reset_found)
        for w in (self.progress_label, self.progress):
            w.bind('<Button-3>', lambda e: self.reset_menu.tk_popup(e.x_root, e.y_root))
        # collection : transfert depuis le coffre ouvert, restauration des objets détruits (dernière opération)
        actions = self.actions = ttk.Frame(top)
        actions.pack(side='top', fill='x', pady=(0, 8))
        self.btn_transfer = ttk.Button(actions, text=tr('library.transfer_all'), bootstyle='warning',
                                       command=lambda: self.app.library_ui.open_transfer(parent=self.win))
        self.btn_transfer.pack(side='left')
        self.btn_restore = ttk.Button(actions, text='', bootstyle='secondary', command=self.restore)
        self.btn_restore.pack(side='left', padx=8)

        filters = ttk.Frame(top)
        filters.pack(side='top', fill='x')
        ttk.Label(filters, text=tr('library.search'), bootstyle='secondary').pack(side='left')
        self.search = tk.StringVar()
        self.search.trace_add('write', lambda *a: self.refresh())
        ttk.Entry(filters, textvariable=self.search, width=28).pack(side='left', padx=(6, 18))
        coll_filters = self.coll_filters = ttk.Frame(filters)   # filtres de la collection
        coll_filters.pack(side='left')
        self.build_storage_filters(filters)
        # filtres : état (trouvé / manquant), type (famille : uniques à tiers, SU / SSU / SSSU, autres uniques, sets),
        # catégorie ; valeurs = (clé, libellé traduit)
        self.states = [('all', tr('library.all')), ('found', tr('library.found')), ('stored', tr('library.stored')),
                       ('missing', tr('library.missing'))]
        # uniques à tiers déclinés par tiers (« tiered:1 » à « tiered:4 » : fin du nom de l'objet de base), puis
        # bijoux, joyaux et carquois à tiers (« tiered:jewelry », sans tier)
        tiers = [f'tiered:{t}' for t in (*'1234', JEWELRY_TIER)]
        self.kinds = [('all', tr('library.all'))] + [(k, tr('library.kind.' + k.replace(':', ''))) for f in FAMILIES
                                                     for k in (tiers if f == 'tiered' else [f])]
        self.categories = [('all', tr('library.all'))] + [(c, tr('library.cat.' + c)) for c in CATEGORIES]
        self.state_box = self.combo(coll_filters, 'library.state', self.states)
        self.kind_box = self.combo(coll_filters, 'library.kind', self.kinds)
        self.category_box = self.combo(coll_filters, 'library.category', self.categories)
        self.group_sets = tk.BooleanVar(value=settings.get('library_group_sets', True))
        ttk.Checkbutton(coll_filters, text=tr('library.group_sets'), variable=self.group_sets, bootstyle='warning',
                        command=lambda: (settings.put('library_group_sets', self.group_sets.get()), self.refresh())
                        ).pack(side='left')

        body = ttk.Frame(self.win, padding=(10, 0, 10, 10))
        body.pack(fill='both', expand=True)
        self.build_detail(body)
        coll_box = self.coll_box = ttk.Frame(body)   # tableau de la collection (onglet Collection)
        coll_box.pack(side='left', fill='both', expand=True)
        self.tree = ttk.Treeview(coll_box, columns=COLUMNS, show='headings', selectmode='browse')
        self.tree.column('#0', width=28, minwidth=28, stretch=False)   # flèche des lignes de set (regroupement)
        self.tree.bind('<<TreeviewSelect>>', lambda e: (setattr(self, 'selected', (self.tree.selection() or [None])[0]),
                                                      self.show_detail()))
        self.tree.bind('<<TreeviewOpen>>', lambda e: self.remember_open(True))
        self.tree.bind('<<TreeviewClose>>', lambda e: self.remember_open(False))
        for c in COLUMNS:
            self.tree.heading(c, text=tr('library.col.' + c), command=lambda c=c: self.sort_by(c))
            self.tree.column(c, width=WIDTHS[c], anchor='w' if c in ('name', 'base', 'category') else 'center')
        self.tree.tag_configure('found', foreground=FOUND_COLOR)
        self.tree.tag_configure('missing', foreground=MISSING_COLOR)
        self.tree.tag_configure('stored', foreground=STORED_COLOR)
        self.tree.tag_configure('setgroup', font=(FONT, 10, 'bold'))
        self.tree.tag_configure('setpending', foreground=SET_GROUP_COLOR)   # set pas encore complet (complet : or)
        sb = AutoScrollbar(coll_box, command=self.tree.yview, bootstyle='round')
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)
        self.build_storage_table(body)
        self.count_label = ttk.Label(self.win, text='', bootstyle='secondary', padding=(10, 0, 10, 8))
        self.count_label.pack(side='bottom', anchor='w')

    def build_detail(self, parent):
        """Panneau de droite : exemplaire rangé = même panneau que le coffre (DetailPanel, hôte CollectionHost : infobulle, qualité,
        étoiles, curseurs) ; sinon infobulle du catalogue ; bouton de sortie vers le coffre."""
        self.detail_sig = None   # empreinte du contenu affiché (detail_signature)
        side = ttk.Frame(parent, padding=(10, 0, 0, 0))
        side.pack(side='right', fill='y')
        # boutons sous l'infobulle, sur une ligne de sa largeur : ceux du module mxl_editor (« Copy to the stash »,
        # point d'accroche library_buttons, avec le droit duplication_enabled) puis « Take out », côte à côte, de même
        # largeur ; seul, « Take out » prend toute la largeur
        self.out_row = ttk.Frame(side)
        self.out_row.pack(side='bottom', fill='x', pady=(8, 0))
        extra = hook('library_buttons')
        buttons = list(extra(self, self.out_row)) if extra else []
        self.btn_take = ttk.Button(self.out_row, text=tr('library.take_out'), bootstyle='warning-outline',
                                   command=self.take_out, state='disabled')
        buttons.append(self.btn_take)
        self.out_buttons = buttons   # actifs ou non ensemble (set_out_buttons)
        for c, b in enumerate(buttons):
            self.out_row.columnconfigure(c, weight=1, uniform='out')
            b.grid(row=0, column=c, sticky='ew', padx=(0 if c == 0 else 2, 0 if c == len(buttons) - 1 else 2))
        # exemplaire affiché : normal ou éthéré (rangés à des places séparées de la collection)
        self.view = tk.StringVar(value='normal')
        # affichée seulement si l'objet existe en jeu dans les deux variantes (show_detail)
        self.views = views = ttk.Frame(side)
        self.btn_views = {}
        for v in ('normal', 'ethereal'):
            self.btn_views[v] = ttk.Radiobutton(views, text=tr('library.view.' + v), value=v, variable=self.view,
                                                bootstyle='warning-toolbutton', command=self.choose_view)
            self.btn_views[v].pack(side='left', padx=(0, 4))
        self.detail_box = box = ttk.Frame(side)
        box.pack(side='top', fill='both', expand=True)
        # même largeur, mêmes styles que le panneau de détail de la fenêtre principale (rendu identique)
        self.detail = tk.Text(box, width=DETAIL_WIDTH, wrap='word', bg=DETAIL_BG, fg=DETAIL_FG, bd=0, padx=DETAIL_PADX, pady=8,
                              font=(FONT, 10), cursor='arrow', insertwidth=0, highlightthickness=0, state='disabled')
        sb = AutoScrollbar(box, command=self.detail.yview, bootstyle='round')
        # défilement : l'image de l'objet suit l'infobulle
        self.detail.configure(yscrollcommand=lambda a, b: (sb.set(a, b), self.place_image(),
                                                            hasattr(self, 'panel') and self.panel.hover.place()))
        # image de l'objet : colonne à gauche, en plus de la largeur du panneau (infobulle aussi large que dans le coffre)
        self.detail_image = tk.Canvas(box, width=2 * self.app.grid.base_cell + IMAGE_PAD, bg=DETAIL_BG, highlightthickness=0)
        self.detail_image.pack(side='left', fill='y')
        forward_wheel(self.detail_image, self.detail)   # molette sur l'image : l'infobulle défile
        self.image_y = 0   # ordonnée actuelle du centre de l'image dans le canevas
        self.catalog_images = {}   # (clé de l'entrée, taille, opacité) -> image d'une entrée non rangée (référence gardée)
        self.detail.pack(side='left', fill='y')   # largeur fixe (DETAIL_WIDTH), comme dans le coffre
        sb.pack(side='left', fill='y')
        setup_detail_tags(self.detail)
        self.detail.tag_configure('hit', background=SEARCH_HIT)   # lignes trouvées par la recherche
        self.panel = DetailPanel(self.detail, CollectionHost(self.app, self))   # même panneau que le coffre
        self.selection = DetailSelection()   # vue choisie, place affichée (mxl_library_view)

    def show_detail(self):
        """Entrée sélectionnée : exemplaire rangé = même panneau que le coffre (infobulle, qualité, étoiles, curseurs
        grisés, sans bouton de transfert), date et coffre d'origine ; sinon infobulle du catalogue (mxl_catalog_tooltip.catalog_tooltip : plages des affixes) et date de découverte."""
        if self.mode.get() == 'storage':
            self.show_storage_detail()
            return
        sel = self.tree.selection()
        key = sel[0] if sel else None
        if key and key.startswith(SET_ROW):   # ligne d'un set : ses pièces et ses bonus
            self.show_set(int(key[len(SET_ROW):]))
            return
        lib, data, t = self.app.library, self.app.data, self.detail
        s = self.selection.update(key, lib.collection, lib.found, key is not None and two_variants(key, data))
        self.view.set(s.view)
        if s.toggle:   # bascule Normal / Ethereal : seulement si l'objet existe en jeu dans les deux variantes
            if not self.views.winfo_ismapped():
                self.views.pack(side='top', fill='x', pady=(0, 6), before=self.detail_box)
        else:
            self.views.pack_forget()
        top = t.yview()[0] if s.same_slot else 0   # même place (clic sur une étoile) : défilement gardé
        it = lib.stored_item(s.slot, data) if s.stored else None
        # contenu inchangé (relecture après une copie vers le coffre, surveillance des fichiers…) : panneau gardé tel
        # quel, seuls les boutons sont mis à jour ; reconstruit, il clignotait (curseurs recréés, image redessinée)
        sig = self.detail_signature(key, s, it)
        if sig == self.detail_sig:
            self.set_out_buttons('normal' if s.stored and self.app.stash_path else 'disabled')
            return
        self.detail_sig = sig
        self.detail_image.delete('all')   # image dessinée à la fin, une fois l'infobulle affichée (sans saut)
        self.panel.show(it)   # exemplaire rangé : même rendu que le coffre ; sinon panneau vidé
        t.configure(state='normal')
        if it is None:
            t.delete('1.0', 'end')
            if key:   # pas d'exemplaire rangé : infobulle construite depuis les tables (plages des affixes)
                # dans le contexte du personnage sélectionné : exigences en rouge, stats par niveau, explications…
                tooltip_view.write_tooltip(t, catalog_tooltip(self.app.catalog[key], data, ethereal=s.view == 'ethereal',
                                                              char=self.app.char))
                drop = entry_drop_lines(self.app.catalog[key], data)   # où l'entrée tombe (mxl_drop)
                if drop:
                    t.insert('end', '\n' + '\n'.join(drop) + '\n', 'dim')
                ctx = CatalogContext(self.app.catalog[key], data)   # compétences données par l'entrée : survol
                self.panel.hover.attach(skill_refs(ctx.lo, ctx.hi, data, mentions=True), data, self.app.char,
                                        heading=catalog_name(ctx), cast_only=cast_only_skills(ctx.lo, data))
        f = lib.found.get(key) if key else None
        found_on = tr('library.detail_found_on', date=f['date'], source=f['source']) if f else ''
        if s.footer == 'stored':   # date de la première découverte (jamais modifiée), puis rangement de cet exemplaire
            e = lib.collection[s.slot]
            t.insert('end', '\n' + (found_on + '\n' if f else '')
                     + tr('library.detail_stored', date=e['date'], source=e['source']) + '\n', 'dim')
        elif s.footer == 'no_ethereal':   # vue Ethereal, seul l'exemplaire normal est rangé
            t.insert('end', '\n' + found_on + '\n' + tr('library.detail_no_ethereal'), 'dim')
        elif s.footer == 'found':
            t.insert('end', '\n' + tr('library.detail_found', date=f['date'], source=f['source']), 'dim')
        elif s.footer == 'missing':
            t.insert('end', '\n' + tr('library.detail_missing'), 'dim')
        t.configure(state='disabled')
        self.set_out_buttons('normal' if s.stored and self.app.stash_path else 'disabled')
        t.update_idletasks()
        t.yview_moveto(top)
        # image dessinée seulement maintenant, et placée avant tout affichage : elle apparaît directement centrée sur
        # l'infobulle (dessinée avant, elle était affichée en haut pendant update_idletasks puis déplacée : clignotement)
        self.highlight()
        self.panel.hover.place()   # après le surlignage (caractère ajouté en tête de ligne, fond changé)
        if it is not None:   # image de l'exemplaire (fond rouge si exigences non remplies, comme dans la grille)
            self.draw_image(it, CELL_KO if requirements_unmet(it, self.app.data, self.app.char) else CELL_OK)
        elif key:   # pas d'exemplaire : image de l'objet de base sur fond noir, estompée (50 %) en vue Ethereal
            self.draw_catalog_image(self.app.catalog[key], ETHEREAL_IMAGE_OPACITY if s.view == 'ethereal' else 1.0)
        self.place_image()

    def set_members(self, sid):
        """Pièces du set sid (entrées du catalogue), dans l'ordre de la table du jeu."""
        return sorted((e for k, e in self.app.catalog.items() if self.set_ids.get(k) == sid), key=lambda e: e['row'])

    def set_progress(self, sid):
        """(pièces trouvées, pièces du set, pièces rangées : exemplaire normal ou éthéré dans la collection)."""
        lib, members = self.app.library, self.set_members(sid)
        found = sum(1 for e in members if e['key'] in lib.found)
        stored = sum(1 for e in members if e['key'] in lib.collection or e['key'] + ETHEREAL in lib.collection)
        return found, len(members), stored

    def detail_signature(self, key, s, it):
        """Empreinte de ce qu'affiche le panneau d'une entrée : entrée, vue, pied de page, exemplaire rangé (octets),
        infobulle (dépend du personnage), fond de l'image, découverte et recherche (surlignage)."""
        lib, data, char = self.app.library, self.app.data, self.app.char
        found = lib.found.get(key) if key else None   # date et coffre seulement (n° des exemplaires : pas affichés)
        if it is not None:
            tip = item_tooltip(it, data, self.panel.host.char_for(it))
            back = requirements_unmet(it, data, char)
        else:
            tip = catalog_tooltip(self.app.catalog[key], data, ethereal=s.view == 'ethereal', char=char) if key else None
            back = None
        return (key, s.slot, s.view, s.toggle, s.footer, dict(lib.collection[s.slot]) if s.stored else None,
                repr(tip), back, found and (found['date'], found['source']), self.search.get())

    def show_set(self, sid):
        """Ligne d'un set sélectionnée : nom, pièces (vertes si trouvées, grises sinon), bonus par nombre de pièces
        portées puis du set complet (set_bonus_lines, comme la documentation du jeu), progression en dessous."""
        data, t = self.app.data, self.detail
        self.detail_sig = None   # panneau d'un set : l'entrée suivante sera reconstruite
        self.selection.update(None, self.app.library.collection, self.app.library.found, False)
        self.views.pack_forget()
        self.detail_image.delete('all')
        self.panel.show(None)
        name, sub = set_name(sid, data)
        lines = [[('2', name)]] + ([[('2', sub)]] if sub else []) + [[]]
        lines += [[('2' if e['key'] in self.app.library.found else '5', e['name'])] for e in self.set_members(sid)]
        for title, bonus in set_bonus_lines(sid, data, self.app.char):
            lines += [[], [('4', title)]] + [segments(c, t) for c, t in bonus]   # textes à plusieurs couleurs
        t.configure(state='normal')
        t.delete('1.0', 'end')
        tooltip_view.write_tooltip(t, lines)
        # compétences données par les bonus du set : survol
        mods = [(m['prop'], m['param'], m['min'], m['max']) for ms in list(data.sets[sid]['partial'].values()) +
                [data.sets[sid]['full']] for m in ms]
        heading = [[('2', name)], [('2', sub or '')]] + [[('0', e['name'])] for e in self.set_members(sid)]
        low = mods_stats(mods, data, 'min')
        self.panel.hover.attach(skill_refs(low, mods_stats(mods, data, 'max'), data, mentions=True), data,
                                self.app.char, heading=heading, cast_only=cast_only_skills(low, data))
        found, total, stored = self.set_progress(sid)
        t.insert('end', '\n' + tr('library.set_progress', found=found, total=total, stored=stored), 'dim')
        t.configure(state='disabled')
        self.set_out_buttons('disabled')
        self.highlight()
        t.yview_moveto(0)

    def highlight(self):
        """Lignes de l'infobulle affichée qui contiennent un terme de la recherche (mots cachés compris) : surlignées
        du premier au dernier caractère. Ligne centrée : Tk peint la marge de centrage avec le fond du 1er caractère ;
        un caractère invisible sans surlignage (ZWSP) en tête de la ligne garde cette marge au fond de l'infobulle."""
        t = self.detail
        t.tag_remove('hit', '1.0', 'end')
        terms = parse_query(self.search.get())
        if not terms:
            return
        state = t.cget('state')
        t.configure(state='normal')
        for n in range(1, int(t.index('end').split('.')[0])):
            line = t.get(f'{n}.0', f'{n}.end')
            if 'tip' not in t.tag_names(f'{n}.0') or not line_matches(line.replace(ZWSP, '').strip(), terms, self.classes):
                continue
            if not line.startswith(ZWSP):
                t.insert(f'{n}.0', ZWSP, tuple(x for x in t.tag_names(f'{n}.0') if x != 'hit'))
            t.tag_add('hit', f'{n}.1', f'{n}.end')
        t.configure(state=state)
        t.tag_raise('hit')

    def remember_open(self, opened):
        """Ligne de set dépliée ou repliée à la main : état retenu (réglages) pour les prochains affichages."""
        iid = self.tree.focus()
        if not iid.startswith(SET_ROW):
            return
        (self.open_sets.add if opened else self.open_sets.discard)(iid)
        settings.put('library_open_sets', sorted(self.open_sets))

    def item_iids(self):
        """Lignes des entrées du catalogue affichées (hors lignes de set), dans l'ordre du tableau."""
        out = []
        for iid in self.tree.get_children():
            out += list(self.tree.get_children(iid)) if iid.startswith(SET_ROW) else [iid]
        return out

    def choose_view(self):
        """Clic sur la bascule Normal / Ethereal : vue gardée (DetailSelection), panneau réaffiché."""
        self.selection.choose_view(self.view.get())
        self.show_detail()

    def set_out_buttons(self, state):
        """Boutons sous l'infobulle (« Take out », ceux du module) : actifs si un exemplaire rangé est affiché et qu'un
        conteneur modifiable est ouvert."""
        for b in self.out_buttons:
            b.configure(state=state)

    def out_slot(self):
        """Place de l'exemplaire affiché, pour Take out / Copy : supérieur sélectionné (onglet Storage) ou exemplaire
        affiché de l'entrée sélectionnée (normal ou éthéré)."""
        if self.mode.get() == 'storage':
            return self.storage_slot()
        return self.selection.slot if self.selection.key else None

    def reset_found(self):
        """Menu du clic droit sur l'avancement : oublie les découvertes des entrées non rangées (Library.reset_found),
        après confirmation (non par défaut) ; les entrées rangées gardent leur date."""
        lib = self.app.library
        forget, kept = lib.found_reset_counts()
        if not forget:
            messagebox.showinfo(tr('library.reset_found_title'), tr('library.reset_found_none'), parent=self.win)
            return
        if not messagebox.askyesno(tr('library.reset_found_title'), tr('library.reset_found_confirm', n=forget, kept=kept),
                                   icon='warning', default='no', parent=self.win):
            return
        try:
            forgotten, kept = lib.reset_found()
        except (OSError, LibraryError) as e:
            messagebox.showerror(tr('library.reset_found_title'), str(e), parent=self.win)
            return
        self.refresh()
        self.app.status.configure(text=tr('library.reset_found_done', n=forgotten, kept=kept))

    def take_out(self):
        """Bouton « Take out » : l'exemplaire rangé de l'entrée sélectionnée retourne dans le coffre ouvert."""
        slot = self.out_slot()
        if not slot or not self.app.stash_path:
            return
        key = slot
        name = slot_name(self.app.catalog, slot, self.app.data)
        if not messagebox.askyesno(tr('library.take_out_title'), tr('library.take_out_confirm', name=name,
                                   file=os.path.basename(self.app.stash_path)), parent=self.win):
            return
        try:
            bak, (page, x, y) = take_out(self.app.stash_path, self.app.data, self.app.library, key,
                                         backup=self.app.needs_backup(self.app.stash_path))
        except (EditError, FormatError, OSError, LibraryError) as e:
            messagebox.showerror(tr('library.take_out_title'), str(e), parent=self.win)
            return
        self.app.library_ui.after_change({self.app.stash_path: bak}, tr('library.taken_out', name=name, page=page + 1, x=x, y=y))

    def combo(self, parent, label_key, values):
        """Liste déroulante de filtre (libellés traduits), sur « tous » par défaut."""
        ttk.Label(parent, text=tr(label_key), bootstyle='secondary').pack(side='left')
        # largeur : celle du plus long libellé (« Tiered jewelry & quivers »), au moins 14 caractères
        box = ttk.Combobox(parent, state='readonly', width=max(14, max(len(v) for _, v in values) + 1),
                           values=[v for _, v in values])
        box.current(0)
        box.bind('<<ComboboxSelected>>', lambda e: (box.selection_clear(), self.refresh()))
        box.pack(side='left', padx=(6, 18))
        return box

    # ---------- contenu ----------
    def entries(self):
        """Entrées du catalogue qui passent les filtres, triées : [(entrée, découverte ou None)]."""
        found, stored = self.app.library.found, self.app.library.collection
        terms = parse_query(self.search.get())
        self.hit_items = self.hit_sets = None   # recherche : entrées trouvées par leur texte, sets par leur nom / bonus
        if terms:
            self.finish_index()   # texte de recherche complet (préparé par étapes depuis l'ouverture de l'écran)
            self.hit_items, self.hit_sets = search(self.index, terms)
        state = self.states[self.state_box.current()][0]
        kind = self.kinds[self.kind_box.current()][0]
        category = self.categories[self.category_box.current()][0]
        rows = []
        for e in self.app.catalog.values():
            f = found.get(e['key'])
            if (state == 'found' and not f) or (state == 'missing' and f) or (state == 'stored' and e['key'] not in stored and e['key'] + ETHEREAL not in stored) \
                    or kind not in ('all', e['family'], f"{e['family']}:{entry_tier(e)}") \
                    or category not in ('all', e['category']) \
                    or terms and e['key'] not in self.hit_items and self.set_ids.get(e['key']) not in self.hit_sets:
                continue
            rows.append((e, f))
        col, desc = self.sort
        key = {'name': lambda r: (r[0]['name'].lower(), r[0]['level_req'] or 0),
               'base': lambda r: r[0]['base'].lower(),
               'category': lambda r: (CATEGORIES.index(r[0]['category']), r[0]['name'].lower()),
               'level_req': lambda r: (r[0]['level_req'] or 0, r[0]['name'].lower()),
               'stored': lambda r: (self.stored_quality(r[0]['key']) or -1, r[0]['name'].lower()),
               'ethereal': lambda r: (self.stored_quality(r[0]['key'] + ETHEREAL) or -1, r[0]['name'].lower()),
               'date': lambda r: (r[1]['date'] if r[1] else '', r[0]['name'].lower())}[col]
        return sorted(rows, key=key, reverse=desc)

    def switch_mode(self):
        """Onglet Collection / Storage : en-tête, filtres et tableau de l'onglet ; panneau de détail reconstruit."""
        storage = self.mode.get() == 'storage'
        for frame, shown, opts in ((self.progress_box, not storage, dict(side='top', fill='x', before=self.actions)),
                                   (self.coll_filters, not storage, dict(side='left')),
                                   (self.stor_filters, storage, dict(side='left')),
                                   (self.coll_box, not storage, dict(side='left', fill='both', expand=True)),
                                   (self.stor_box, storage, dict(side='left', fill='both', expand=True))):
            if shown and not frame.winfo_manager():
                frame.pack(**opts)
            elif not shown:
                frame.pack_forget()
        self.detail_sig = None
        self.refresh()

    def refresh_actions(self):
        """Boutons de transfert et de restauration (communs aux deux onglets)."""
        n_destroyed = len(self.app.library.journal['items'])
        self.btn_restore.configure(text=tr('library.restore', n=n_destroyed), state='normal' if n_destroyed else 'disabled')
        self.btn_transfer.configure(state='normal' if self.app.transfer_sources() else 'disabled')

    def refresh(self):
        """Avancement et tableau selon les filtres (appelé aussi après de nouvelles découvertes)."""
        if self.mode.get() == 'storage':
            self.refresh_storage()
            return
        found = self.app.library.found
        total = len(self.app.catalog)
        n = sum(1 for k in self.app.catalog if k in found)
        by_kind = {k: (sum(1 for e in self.app.catalog.values() if e['kind'] == k and e['key'] in found),
                       sum(1 for e in self.app.catalog.values() if e['kind'] == k)) for k in ('unique', 'set')}
        self.progress_label.configure(text=tr('library.progress', found=n, total=total, pct=f'{100 * n / total:.1f}',
                                              uf=by_kind['unique'][0], ut=by_kind['unique'][1],
                                              sf=by_kind['set'][0], st=by_kind['set'][1]))
        self.progress['value'] = n / total if total else 0
        self.tree.delete(*self.tree.get_children())
        self.quality_cache = {}
        rows = self.entries()
        grouping = self.group_sets.get()
        self.tree.configure(show='tree headings' if grouping else 'headings')

        def insert(parent, e, f):
            q, qe = self.stored_quality(e['key']), self.stored_quality(e['key'] + ETHEREAL)
            stored = q is not None or qe is not None
            self.tree.insert(parent, 'end', iid=e['key'], tags=('stored' if stored else 'found' if f else 'missing',), values=(
                e['name'], e['base'], tr('library.cat.' + e['category']), e['level_req'] or '',
                f'{q:.0f} %' if q is not None else '', f'{qe:.0f} %' if qe is not None else '',
                f['date'] if f else ''))
        groups = {}   # regroupement : n° du set -> ses pièces affichées, dans l'ordre du tri choisi
        searching = self.hit_items is not None
        for e, f in rows:
            # recherche : pièce trouvée par son propre texte = affichée seule, hors de son set ; set trouvé par son nom
            # ou ses bonus = ligne du set (repliée), avec ses autres pièces
            if grouping and e['kind'] == 'set' and not (searching and e['key'] in self.hit_items):
                groups.setdefault(self.set_ids[e['key']], []).append((e, f))
            else:
                insert('', e, f)
        # sets par ordre alphabétique, après les uniques ; dépliés si un filtre (état, catégorie) est actif, repliés
        # pendant une recherche (set trouvé par ses bonus : ses pièces ne contiennent pas forcément le texte),
        # sinon selon le dernier choix (repliés par défaut)
        filtering = not searching and (self.state_box.current() or self.category_box.current())
        for sid in sorted(groups, key=lambda s: set_name(s, self.app.data)[0].lower()):
            iid = f'{SET_ROW}{sid}'
            found, total, stored = self.set_progress(sid)
            self.tree.insert('', 'end', iid=iid, open=bool(filtering) or (not searching and iid in self.open_sets),
                             tags=('setgroup',) + (('found',) if found == total else ('setpending',)),
                             values=(set_name(sid, self.app.data)[0],
                                     tr('library.set_progress', found=found, total=total, stored=stored), '', '', '', '', ''))
            for e, f in groups[sid]:
                insert(iid, e, f)
        self.refresh_actions()
        self.count_label.configure(text=tr('library.count', n=len(rows)))
        if getattr(self, 'selected', None) and self.tree.exists(self.selected):   # sélection gardée après une mise à jour
            self.tree.selection_set(self.selected)
        self.show_detail()
        for c in COLUMNS:   # flèche de tri sur la colonne active
            arrow = (' ▼' if self.sort[1] else ' ▲') if c == self.sort[0] else ''
            self.tree.heading(c, text=tr('library.col.' + c) + arrow)

    def priorities_changed(self, priorities, key):
        """Priorité changée (étoile, ici ou dans le coffre) : colonne « Stored » et panneau de détail mis à jour sur
        place, sans reconstruire le tableau ni le panneau (pas de clignotement, défilement et sélection gardés)."""
        self.quality_cache = {}
        for iid in self.item_iids():
            for col, slot in (('stored', iid), ('ethereal', iid + ETHEREAL)):
                q = self.stored_quality(slot)
                if q is not None:
                    self.tree.set(iid, col, f'{q:.0f} %')
        for slot in self.stree.get_children():   # onglet Storage
            q = self.stored_quality(slot)
            if q is not None:
                self.stree.set(slot, 'quality', f'{q:.0f} %')
        self.panel.priorities_updated(priorities, key)

    def stored_quality(self, key):
        """Qualité (%) de l'exemplaire rangé à cette place (slot_key), ou None (mise en cache par refresh)."""
        if not hasattr(self, 'quality_cache'):
            self.quality_cache = {}
        if key not in self.quality_cache:
            it = self.app.library.stored_item(key, self.app.data)
            self.quality_cache[key] = rank(it, self.app.data, self.app.saved_priorities)[1] if it else None
        return self.quality_cache[key]

    def restore(self):
        """Bouton « Restore destroyed » : objets détruits lors de la dernière opération remis dans leur fichier et
        leur conteneur d'origine (entrées d'un journal plus ancien, sans fichier noté : dans le coffre ouvert)."""
        app = self.app
        items = app.library.journal['items']
        files = sorted({os.path.basename(e.get('file') or app.stash_path or '') for e in items} - {''})
        if not items or not files or not messagebox.askyesno(
                tr('library.restore_title'), tr('library.restore_confirm', n=len(items), file=', '.join(files)),
                parent=self.win):
            return
        try:
            baks, done, left = restore_destroyed(app.stash_path, app.data, app.library, backup=app.needs_backup)
        except (EditError, FormatError, OSError, LibraryError) as e:
            messagebox.showerror(tr('library.restore_title'), str(e), parent=self.win)
            return
        app.library_ui.after_change(baks, tr('library.restored', n=done, left=left))

    def sort_by(self, col):
        """Clic sur un en-tête : tri par cette colonne (second clic : ordre inverse)."""
        self.sort = (col, not self.sort[1] if self.sort[0] == col else False)
        self.refresh()

    def close(self):
        if self.index_after:
            self.win.after_cancel(self.index_after)
        self.win.destroy()
        self.app.library_ui.close()


class CollectionHost(DetailHost):
    """Hôte du panneau de détail de l'écran Library (exemplaire rangé) : même panneau que le coffre (DetailPanel :
    infobulle, qualité, étoiles de priorité, curseurs), donc même rendu. Valeurs de DetailHost : lecture seule (curseurs
    grisés : modifier un objet rangé n'est pas géré), pas de bouton de transfert (l'objet n'est pas dans le coffre).
    Les étoiles modifient les priorités partagées de l'éditeur (mêmes profils que dans le coffre)."""

    def __init__(self, app, window):
        self.app, self.window = app, window

    data = property(lambda self: self.app.data)
    char = property(lambda self: self.app.char)
    saved_priorities = property(lambda self: self.app.saved_priorities)

    def priorities_changed(self, priorities, key):
        """Étoile cliquée dans l'écran Library : tableau de la collection et panneau du coffre mis à jour (sur place)."""
        self.window.priorities_changed(priorities, key)
        self.app.panel.priorities_updated(priorities, key)
