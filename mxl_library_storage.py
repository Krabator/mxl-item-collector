"""Écran Library, onglet « Storage » : supérieurs du stockage (mxl_library.storage_key, hors collection) ; filtres
(tiers, arme / armure), tableau des exemplaires stockés (objet de base, catégorie, sockets, éthéré, qualité, date) trié
par colonne, panneau de détail (même panneau que le coffre).

StorageTab est une classe mixte de mxl_library_gui.LibraryWindow : elle en utilise app, search, combo, detail, panel,
detail_sig, views, detail_image, count_label, stored_quality, quality_cache, refresh_actions, set_out_buttons,
show_detail, draw_image et place_image.
"""
import ttkbootstrap as ttk
from i18n import tr
from mxl_library import TIERS, base_tier, storage_parts, storage_double
from mxl_theme import STORED_COLOR, CELL_KO, CELL_OK
from mxl_tooltip import requirements_unmet, item_tooltip
from mxl_widgets import AutoScrollbar

# onglet Storage : colonnes du tableau des supérieurs stockés, dans l'ordre, et largeurs
STORAGE_COLUMNS = ('base', 'category', 'sockets', 'double', 'ethereal', 'quality', 'date')   # provenance : panneau de détail seulement
STORAGE_WIDTHS = dict(base=220, category=85, sockets=70, double=110, ethereal=80, quality=80, date=130)


class StorageTab:
    """Onglet Storage de l'écran Library (classe mixte de LibraryWindow)."""

    def build_storage_filters(self, filters):
        """Filtres de l'onglet (affichés par LibraryWindow.switch_mode) : tiers, arme / armure."""
        self.stor_filters = ttk.Frame(filters)   # filtres de l'onglet Storage : tiers, arme / armure
        self.stor_tiers = [('all', tr('library.all'))] + [(t, tr('library.tier.' + t)) for t in TIERS]
        self.stor_tier_box = self.combo(self.stor_filters, 'library.kind', self.stor_tiers)
        self.stor_categories = [('all', tr('library.all'))] + [(c, tr('library.cat.' + c)) for c in ('weapons', 'armor')]
        self.stor_category_box = self.combo(self.stor_filters, 'library.category', self.stor_categories)
        self.ssort = ('base', False)   # tri du tableau Storage

    def build_storage_table(self, body):
        """Tableau des supérieurs stockés (affiché par LibraryWindow.switch_mode)."""
        stor_box = self.stor_box = ttk.Frame(body)   # tableau des supérieurs stockés (onglet Storage)
        self.stree = ttk.Treeview(stor_box, columns=STORAGE_COLUMNS, show='headings', selectmode='browse')
        self.stree.bind('<<TreeviewSelect>>', lambda e: self.show_detail())
        for c in STORAGE_COLUMNS:
            self.stree.heading(c, text=tr('library.scol.' + c), command=lambda c=c: self.storage_sort_by(c))
            self.stree.column(c, width=STORAGE_WIDTHS[c], anchor='w' if c in ('base', 'category') else 'center')
        self.stree.tag_configure('stored', foreground=STORED_COLOR)
        ssb = AutoScrollbar(stor_box, command=self.stree.yview, bootstyle='round')
        self.stree.configure(yscrollcommand=ssb.set)
        ssb.pack(side='right', fill='y')
        self.stree.pack(side='left', fill='both', expand=True)

    def storage_slot(self):
        """Place du supérieur sélectionné dans le tableau Storage, ou None."""
        sel = self.stree.selection()
        return sel[0] if sel and sel[0] in self.app.library.storage else None

    def show_storage_detail(self):
        """Onglet Storage : supérieur stocké sélectionné = même panneau que le coffre, date et provenance ; aucun : invite.
        Pas de bascule Normal / Ethereal (place éthérée = ligne à part). Contenu inchangé : panneau gardé (detail_signature)."""
        lib, data, t = self.app.library, self.app.data, self.detail
        slot = self.storage_slot()
        self.views.pack_forget()
        it = lib.stored_item(slot, data) if slot else None
        sig = ('storage', slot, dict(lib.storage[slot]) if slot else None,
               repr(item_tooltip(it, data, self.panel.host.char_for(it))) if it else None,
               requirements_unmet(it, data, self.app.char) if it else None)
        state = 'normal' if it is not None and self.app.stash_path else 'disabled'
        if sig == self.detail_sig:
            self.set_out_buttons(state)
            return
        self.detail_sig = sig
        self.detail_image.delete('all')
        self.panel.show(it)
        if it is not None:
            e = lib.storage[slot]
            t.configure(state='normal')
            t.insert('end', '\n' + tr('library.detail_stored', date=e['date'], source=e['source']) + '\n', 'dim')
            t.configure(state='disabled')
        self.set_out_buttons(state)
        t.update_idletasks()
        t.yview_moveto(0)
        self.panel.hover.place()
        if it is not None:
            self.draw_image(it, CELL_KO if requirements_unmet(it, data, self.app.char) else CELL_OK)
        self.place_image()

    def storage_rows(self):
        """Supérieurs stockés selon la recherche (objet de base), le tiers et la catégorie : [(place, valeurs des colonnes)],
        triés."""
        lib, data = self.app.library, self.app.data
        cat = dict((v, k) for k, v in self.stor_categories)[self.stor_category_box.get()]
        tier = dict((v, k) for k, v in self.stor_tiers)[self.stor_tier_box.get()]
        words = self.search.get().lower().split()
        rows = []
        for slot, e in lib.storage.items():
            code, sockets, eth = storage_parts(slot)
            base = data.base(code.ljust(4))
            if cat != 'all' and base.kind != cat:
                continue
            if tier != 'all' and base_tier(base.name) != tier:
                continue
            if any(w not in base.name.lower() for w in words):
                continue
            q = self.stored_quality(slot)
            rows.append((slot, dict(base=base.name, category=tr('library.cat.' + base.kind), sockets=sockets,
                                    double=tr('library.storage_double') if storage_double(slot) else '',
                                    ethereal=tr('library.view.ethereal') if eth else '',
                                    quality=q, date=e['date'])))
        col, desc = self.ssort
        rows.sort(key=lambda r: (r[1][col] is None, r[1][col] if r[1][col] is not None else 0, r[1]['base']), reverse=desc)
        return rows

    def refresh_storage(self):
        """Onglet Storage : tableau des supérieurs stockés, nombre affiché, sélection gardée, panneau de détail."""
        self.refresh_actions()
        self.quality_cache = {}
        keep = self.storage_slot()
        self.stree.delete(*self.stree.get_children())
        rows = self.storage_rows()
        for slot, v in rows:
            self.stree.insert('', 'end', iid=slot, tags=('stored',), values=[
                f"{v[c]:.0f} %" if c == 'quality' and v[c] is not None else v[c] for c in STORAGE_COLUMNS])
        self.count_label.configure(text=tr('library.storage_count', n=len(rows), total=len(self.app.library.storage)))
        if keep and self.stree.exists(keep):
            self.stree.selection_set(keep)
        for c in STORAGE_COLUMNS:   # flèche de tri sur la colonne active
            arrow = (' ▼' if self.ssort[1] else ' ▲') if c == self.ssort[0] else ''
            self.stree.heading(c, text=tr('library.scol.' + c) + arrow)
        self.show_detail()

    def storage_sort_by(self, col):
        """Clic sur un en-tête du tableau Storage : tri par cette colonne (second clic : ordre inverse)."""
        self.ssort = (col, not self.ssort[1] if self.ssort[0] == col else False)
        self.refresh_storage()
