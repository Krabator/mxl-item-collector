"""Fenêtre de transfert vers la collection (et le stockage des supérieurs) : aperçu du plan (mxl_library.plan_transfer),
options pour les exemplaires remplacés et pour les nouveaux exemplaires moins bons, choix ligne par ligne, écriture à
la validation (mxl_library.apply_transfer). Ouverte par mxl_library_ui.LibraryUI.open_transfer.
"""
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from i18n import tr
from mxl_library import transfer_items, item_ref, plan_transfer, apply_transfer, LibraryError
from mxl_library_view import slot_name, slot_base
from mxl_save import EditError
from mxl_format import FormatError
from mxl_widgets import AutoScrollbar
from mxl_theme import FONT, DESTROY_COLOR


class TransferDialog:
    """Transfert vers la collection : aperçu du plan (plan_transfer), options pour les anciens exemplaires remplacés
    (A rapatrier / B détruire / C au choix) et pour les exemplaires moins bons (A garder / B détruire / C au choix),
    choix ligne par ligne (double-clic) en option C ; rien n'est écrit avant « Validate »."""
    GROUPS = (('upgrade', ('exchange', 'destroy', 'choose')), ('worse', ('keep', 'destroy', 'choose')))

    def __init__(self, app, only=None, parent=None, source=None):
        """parent : fenêtre d'où le transfert est lancé (écran Library ou fenêtre du coffre, par défaut), qui reprend
        le focus à la fermeture. source : (fichier, conteneur) des objets (transfert d'un objet : only = son offset) ;
        par défaut, les conteneurs du personnage (App.transfer_sources : son coffre, son sac sans ses charmes, son
        cube)."""
        self.app = app
        self.parent = parent or app.root
        # personnage entier : charmes du sac écartés (bonus du personnage) ; un objet choisi : toujours transférable
        items = transfer_items([source] if source else app.transfer_sources(), app.data, bag_charms=bool(source))
        self.plan = plan_transfer(items, app.library, app.data, app.saved_priorities, only)
        if not self.plan:
            messagebox.showinfo(tr('library.transfer_title'), tr('library.transfer_nothing'), parent=self.parent)
            return
        self.choices = {}   # item_ref -> choix ligne par ligne (option C)
        self.win = ttk.Toplevel(master=app.root, title=tr('library.transfer_title'))
        self.win.geometry('980x600')
        self.win.transient(self.parent)
        self.win.protocol('WM_DELETE_WINDOW', self.close)
        self.build()
        self.refresh()
        self.win.grab_set()

    def build(self):
        top = ttk.Frame(self.win, padding=10)
        top.pack(side='top', fill='x')
        self.summary = ttk.Label(top, text='', font=(FONT, 11, 'bold'), bootstyle='warning')
        self.summary.pack(anchor='w')
        ttk.Label(top, text=tr('library.game_closed'), bootstyle='secondary').pack(anchor='w', pady=(2, 8))
        self.options = {}
        grid = self.option_grid = ttk.Frame(top)   # une grille pour les deux groupes : libellés entiers, boutons alignés en colonnes
        grid.pack(anchor='w')
        for kind, values in self.GROUPS:   # options affichées seulement si le plan a des lignes de ce type
            if not any(a['kind'] == kind for a in self.plan):
                continue
            r = len(self.options)
            ttk.Label(grid, text=tr('library.option.' + kind)).grid(row=r, column=0, sticky='w', pady=2)
            var = tk.StringVar(value=values[0])
            for c, v in enumerate(values, 1):
                ttk.Radiobutton(grid, text=tr('library.choice.' + v), value=v, variable=var,
                                command=self.refresh).grid(row=r, column=c, sticky='w', padx=8, pady=2)
            self.options[kind] = var
        body = ttk.Frame(self.win, padding=(10, 0))
        body.pack(fill='both', expand=True)
        cols = ('name', 'base', 'source', 'action', 'new', 'old', 'choice')
        self.tree = ttk.Treeview(body, columns=cols, show='headings', selectmode='browse')
        for c, w in zip(cols, (200, 160, 70, 160, 70, 70, 160)):
            self.tree.heading(c, text=tr('library.tcol.' + c))
            self.tree.column(c, width=w, anchor='w' if c in ('name', 'base', 'action', 'choice') else 'center')
        self.tree.tag_configure('destroy', foreground=DESTROY_COLOR)
        self.tree.bind('<Double-1>', self.toggle)
        sb = AutoScrollbar(body, command=self.tree.yview, bootstyle='round')
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)
        bottom = ttk.Frame(self.win, padding=10)
        bottom.pack(side='bottom', fill='x')
        ttk.Button(bottom, text=tr('library.validate'), bootstyle='warning', command=self.validate).pack(side='right')
        ttk.Button(bottom, text=tr('library.cancel'), bootstyle='secondary', command=self.close).pack(side='right', padx=8)
        self.hint = ttk.Label(bottom, text='', bootstyle='secondary')
        self.hint.pack(side='left')

    def choice(self, a):
        """Choix effectif d'une ligne : option du groupe, ou choix de la ligne (option C, défaut = 1re option)."""
        if a['kind'] not in self.options:
            return None
        opt = self.options[a['kind']].get()
        if opt != 'choose':
            return opt
        return self.choices.get(item_ref(a['item']), dict(self.GROUPS)[a['kind']][0])

    @staticmethod
    def source_name(it):
        """Conteneur d'origine d'un objet du plan : Stash, Shared, Bag ou Cube."""
        path, where = it['_src']
        kind = where if where in ('inventory', 'cube') else 'shared' if path.lower().endswith('.shared') else 'stash'
        return tr('library.src.' + kind)

    def refresh(self):
        name = lambda a: slot_name(self.app.catalog, a['key'], self.app.data)
        self.tree.delete(*self.tree.get_children())
        for k, a in enumerate(self.plan):
            c = self.choice(a)
            self.tree.insert('', 'end', iid=str(k), tags=('destroy',) if c == 'destroy' else (), values=(
                name(a), slot_base(self.app.catalog, a['key'], self.app.data), self.source_name(a['item']),
                tr('library.action.' + a['kind']),
                f"{a['rank'][1]:.0f} %", f"{a['old'][1]:.0f} %" if a['old'] else '',
                tr('library.choice.' + c) if c else ''))
        count = lambda kind: sum(1 for a in self.plan if a['kind'] == kind)
        self.destroyed = sum(1 for a in self.plan if self.choice(a) == 'destroy')
        self.summary.configure(text=tr('library.summary', store=count('store'), upgrade=count('upgrade'),
                                       worse=count('worse'), destroy=self.destroyed))
        choose = any(v.get() == 'choose' for v in self.options.values())
        self.hint.configure(text=tr('library.choose_hint') if choose else '')

    def toggle(self, ev):
        """Double-clic sur une ligne (option C de son groupe) : bascule entre les deux choix."""
        row = self.tree.identify_row(ev.y)
        if not row:
            return
        a = self.plan[int(row)]
        if a['kind'] in self.options and self.options[a['kind']].get() == 'choose':
            first, second, _ = dict(self.GROUPS)[a['kind']]
            self.choices[item_ref(a['item'])] = second if self.choice(a) == first else first
            self.refresh()

    def validate(self):
        if self.destroyed and not messagebox.askyesno(tr('library.transfer_title'),
                                                      tr('library.destroy_confirm', n=self.destroyed), parent=self.win):
            return
        choices = {item_ref(a['item']): self.choice(a) for a in self.plan if self.choice(a)}
        app = self.app
        try:
            baks = apply_transfer(None, app.data, app.library, self.plan, choices, backup=app.needs_backup)
        except (EditError, FormatError, OSError, LibraryError) as e:
            messagebox.showerror(tr('library.transfer_title'), str(e), parent=self.win)
            return
        self.win.destroy()
        moved = sum(1 for a in self.plan if a['kind'] in ('store', 'upgrade'))
        app.library_ui.after_change(baks, tr('library.transferred', n=moved, destroyed=self.destroyed))
        self.give_back_focus()

    def close(self):
        """Annulation (bouton ou fermeture de la fenêtre) : rien n'est écrit, focus rendu à la fenêtre de départ."""
        self.win.destroy()
        self.give_back_focus()

    def give_back_focus(self):
        """Fenêtre de départ (écran Library ou coffre) au premier plan avec le focus : sans cela, Windows le rend à la
        fenêtre principale (propriétaire des fenêtres de l'application)."""
        if self.parent.winfo_exists():
            self.parent.lift()
            self.parent.focus_force()
