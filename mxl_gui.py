"""Interface graphique de l'éditeur d'objets Median XL 2.14.5 : coffre en grille avec les icônes du jeu,
infobulle, déplacement des objets par glisser-déposer, édition des valeurs à variance par curseurs.

Fenêtre principale (App) : construction, fichiers, pages et glisser-déposer ; le reste est confié à des objets :
grille d'objets (mxl_grid.ItemGrid, self.grid ; forme : conteneur mxl_containers.STASH), installation du jeu (mxl_gui_install.GameInstall, self.install), bibliothèque (mxl_library_ui.LibraryUI,
self.library_ui), panneau de détail (mxl_gui_detail.DetailPanel, self.panel, dont App est l'hôte : DetailHost).

Point d'entrée : choix d'un personnage sauvegardé (liste des .d2s du dossier de sauvegarde), dont le coffre s'ouvre ;
bascule vers le coffre partagé (SHARED_STASH), affiché pour le même personnage (exigences, bonus Force/Dex), ou vers
son cube (objets du .d2s rangés dans le cube) : un coffre sans page, modifiable comme un coffre (mxl_save.ItemFile).
À gauche, panneau repliable du personnage (mxl_char_view.CharacterView, self.char_view) : équipement (édition par
curseurs, pas de déplacement) et sac (modifiable : glisser-déposer dans le sac et vers la grille de droite, édition) ; la sélection (self.selected) est
commune au panneau et à la grille.
Personnage et coffre (du personnage / partagé) retenus dans les réglages (settings.py) et rouverts au lancement.

Usage : python mxl_gui.py [fichier.stash] — ouvre ce fichier (personnage du même nom), sinon le dernier choix.
"""
import os, sys, glob
from types import SimpleNamespace
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk

from mxl_data import Data
from mxl_rules import CLASSES
from mxl_format import FormatError
from mxl_save import (read_items, stash_box, parse_stash, is_character, last_page, move_item, move_between, transfer_item, placement_error, EditError,
                      load_character, edit_stash, blob_item)
from dataclasses import replace
from mxl_containers import STASH, character_containers, place, cube_status
from mxl_grid import ItemGrid, FloatingIcon
from mxl_widgets import AutoScrollbar, OneLineLabel
from mxl_char_view import CharacterView
from mxl_edit import global_priorities
import i18n
import settings
from mxl_library import Library, catalog, slot_key
from paths import DATA_DIR, SAVE_DIR, LIBRARY_FILE as PATHS_LIBRARY_FILE
from mxl_home import migrate
from mxl_ext import editor, editor_error, hook
from version import VERSION
from i18n import tr
from mxl_theme import DETAIL_BG, DETAIL_FG, FONT, DETAIL_WIDTH, DETAIL_PADX, LABEL_DIM
from mxl_gui_install import GameInstall
from mxl_gui_detail import DetailHost, DetailPanel, full_name, setup_detail_tags
from mxl_library_ui import LibraryUI
from mxl_char_stats import with_total_attributes

SHARED_STASH = '_sharedstash.shared'   # coffre partagé entre les personnages (même format qu'un .stash)
# vues proposées : (vue, texte du bouton), de droite à gauche sur la ligne des onglets
VIEWS = (('cube', 'btn.cube'), ('shared', 'btn.stash_shared'), ('character', 'btn.stash_character'))
# bibliothèque d'objets (mxl_library) : découvertes, collection (vrais objets) et journal, dans le dossier unique de
# l'utilisateur (paths.HOME_DIR) ; MXL_LIBRARY = autre fichier (tests)
LIBRARY_FILE = os.environ.get('MXL_LIBRARY') or PATHS_LIBRARY_FILE
TAB_HOVER_MS = 600    # glisser-déposer : temps de survol d'un onglet avant de basculer sur sa page
WATCH_MS = 1000       # surveillance du coffre ouvert et du personnage de référence (relus s'ils changent sur le disque)


def file_signature(path):
    """(date de modification, taille) d'un fichier, ou None s'il n'existe pas (ou pas de fichier)."""
    try:
        st = os.stat(path)
        return st.st_mtime_ns, st.st_size
    except (OSError, TypeError):
        return None


class App(DetailHost):
    def __init__(self, root, path=None):
        self.root = root
        # boutons, bascules, cases à cocher et onglets : pas de focus au clic, donc pas de cadre en pointillés dessiné
        # dessus (toutes les fenêtres de l'application : base d'options de Tk) ; ils ne sont plus atteints par Tab
        for cls in ('TButton', 'TRadiobutton', 'TCheckbutton', 'TNotebook'):
            root.option_add(f'*{cls}.takeFocus', '0')
        self.path = None          # fichier affiché : coffre (.stash, coffre partagé) ou personnage (.d2s : son cube)
        self.box = STASH          # conteneur affiché (forme de la grille, pages, écriture permise)
        self.cube_state = 'none'  # cube du personnage : 'ok', 'readonly' (pas de cube Horadrim, contenu non vide), 'none'
        self.items = []
        self.selected = None
        self.char = None
        self.char_file = None     # .d2s du personnage de référence (exigences, bonus) : celui du coffre ou celui choisi
        self.files_seen = None    # signatures (coffre, personnage) à la dernière lecture : voir watch_files
        self.save_dir = os.path.dirname(os.path.abspath(path)) if path else SAVE_DIR   # personnages proposés
        self.char_error = None    # erreur de lecture du personnage (.d2s présent mais illisible), affichée en bas
        self.drag = None          # glisser-déposer en cours : objet, case saisie dans l'objet, case visée
        self.tab_hover = None     # (onglet survolé, id du minuteur) pendant un glisser-déposer
        # objet « en main » (posé par un clic, sans bouton enfoncé ; start_carry) : objet, octets, case tenue, suivant
        self.carry = None
        self.floating = FloatingIcon(root)   # image de l'objet sous la souris (glisser-déposer, objet en main)
        self.backups_done = set()   # fichiers déjà sauvegardés (.bak) pendant cette session : voir needs_backup
        self.last_edit_backup = None   # sauvegarde faite par la dernière édition (annoncée dans la barre du bas)
        # priorités des stats (étoiles) par profil d'objet, communes à tous les personnages : {profil: {stat: n}} ;
        # seulement pour les profils conservés (uniques, sets, Superior gris sans objet serti), enregistrés à la
        # fermeture ; autres objets : pas d'étoiles, qualité avec les poids par défaut (ancien format par
        # personnage converti)
        self.saved_priorities = global_priorities(settings.get('item_priorities', {}))
        # droits de settings.json (jamais écrits par l'éditeur) : « edition_enabled » = édition des valeurs (curseurs,
        # quantité, Ethereal, Max sockets ; ancien nom « editing_enabled », repris) ; « duplication_enabled » = copie
        # d'un objet de la collection vers le coffre. Sans le module mxl_editor : toujours inactifs ; avec lui :
        # actifs sans ligne, « false » respecté (décision du 08/10)
        settings.rename('editing_enabled', 'edition_enabled')
        self.editing_setting = self.right('edition_enabled')
        self.duplication_setting = self.right('duplication_enabled')
        root.protocol('WM_DELETE_WINDOW', self.on_close)
        root.title(tr('app.title', version=VERSION))
        # dossier d'installation de Median XL (réglage game_dir, demandé au premier lancement) ; data/ reconstruit
        # (avec accord) s'il manque ou si le mod a changé de version
        self.install = GameInstall(root, DATA_DIR, on_rebuilt=self.reload_data)
        self.install.start()
        try:
            self.data = Data(DATA_DIR)
        except FileNotFoundError as e:
            messagebox.showerror(tr('err.data_missing.title'), tr('err.data_missing.body', file=e.filename))
            root.destroy()
            raise SystemExit(1)
        self.library = Library(LIBRARY_FILE, lock=True)
        if self.library.readonly:   # fichier illisible ou bibliothèque déjà ouverte : rien ne sera écrit
            messagebox.showwarning(tr('library.readonly_title'), self.library.readonly)
        elif self.library.rekey_storage(self.data):   # places du stockage selon la règle actuelle (Physical Resist)
            self.library.save()
        self.catalog = {e['key']: e for e in catalog(self.data)}   # entrées du catalogue par clé
        self.library_ui = LibraryUI(self)   # écran « Library », bouton, découvertes, transfert
        self._build()
        # libellés secondaires plus clairs (fenêtre principale et écran Library : même style) ; après _build, le style
        # « secondary.TLabel » est créé par ttkbootstrap à la première étiquette qui l'utilise
        root.style.configure('secondary.TLabel', foreground=LABEL_DIM)
        if path:   # fichier donné (ligne de commande, tests) : son personnage et sa vue sélectionnés
            shared = os.path.basename(path) == SHARED_STASH
            name = settings.get('last_character') if shared else os.path.splitext(os.path.basename(path))[0]
            self.select_character(name, 'shared' if shared else 'character')
            self.load(path, char_file=self.character_file())
        else:   # dernier personnage et dernière vue choisis (ancien réglage : nom du dernier coffre ouvert)
            last = settings.get('last_stash')
            name = settings.get('last_character') or (os.path.splitext(os.path.basename(last))[0] if last else None)
            self.select_character(name, settings.get('last_view') or 'character')
            self.open_view()
        self.root.after(WATCH_MS, self.watch_files)

    @staticmethod
    def right(key):
        """Droit de settings.json : toujours faux sans le module mxl_editor (mxl_ext) ; avec lui, la valeur du réglage,
        vrai s'il est absent (décision du 08/10) ; rien n'est écrit."""
        return editor() is not None and bool(settings.get(key, True))

    @property
    def editing(self):
        """Édition par curseurs : permise par le réglage, dans un conteneur où l'éditeur écrit (panneau du personnage :
        objets du sac et objets portés)."""
        if self.in_mercenary(self.selected):   # mercenaire : édition, pas de déplacement
            return self.editing_setting
        if self.in_character(self.selected):
            return self.editing_setting and place(self.selected) in ('inventory', 'equipped')
        return self.editing_setting and self.box.writable

    @property
    def stash_path(self):
        """Fichier ouvert où l'éditeur peut écrire (coffre, cube), ou None : aucun fichier, conteneur en lecture seule."""
        return self.path if self.box.writable else None

    def save_priorities(self):
        """Enregistre les priorités des profils conservés (hors valeurs par défaut) dans les réglages."""
        settings.put('item_priorities', {p: v for p, v in self.saved_priorities.items() if v})

    def on_close(self):
        """Fermeture de la fenêtre : priorités enregistrées, puis fin de l'application."""
        try:
            self.save_priorities()
        finally:
            self.library.release()
            self.root.destroy()

    # ---------- construction de la fenêtre ----------
    def _build(self):
        top = ttk.Frame(self.root, padding=6)
        top.pack(side='top', fill='x')
        # point d'entrée : personnage sauvegardé, puis son coffre ou le coffre partagé (affiché pour ce personnage)
        self.char_title = ttk.Label(top, text=tr('label.character'), bootstyle='secondary')
        self.char_title.pack(side='left')
        # liste relue à chaque ouverture (personnage créé pendant que l'éditeur est ouvert)
        self.char_combo = ttk.Combobox(top, state='readonly', width=18,
                                       postcommand=lambda: self.char_combo.configure(values=self.characters()))
        self.char_combo.bind('<<ComboboxSelected>>', lambda e: (self.char_combo.selection_clear(), self.root.focus_set(),
                                                                self.open_view()))
        self.char_combo.bind('<FocusIn>', lambda e: self.char_combo.selection_clear())
        self.char_combo.pack(side='left', padx=(6, 6))
        self.btn_library = ttk.Button(top, text=tr('btn.library'), command=self.library_ui.open, bootstyle='warning-outline')
        self.btn_library.pack(side='left', padx=6)
        self.library_ui.attach_button(self.btn_library)
        # panneau du personnage (équipement et sac) à gauche du coffre : toujours replié à l'ouverture (l'application
        # gère des objets : le personnage n'est pas mis en avant), affiché à la demande
        self.show_char = tk.BooleanVar(value=False)
        self.btn_char = ttk.Checkbutton(top, text=tr('btn.equipment'), variable=self.show_char,
                                        command=self.toggle_character, bootstyle='info-outline-toolbutton')
        self.btn_char.pack(side='left', padx=6)
        # langue de l'interface : un fichier par langue dans lang/ (voir i18n.py), choix enregistré dans settings.json
        self.languages = i18n.available()
        self.lang_combo = ttk.Combobox(top, state='readonly', width=14, values=[n for _, n in self.languages])
        codes = [c for c, _ in self.languages]
        if i18n.current() in codes:
            self.lang_combo.current(codes.index(i18n.current()))
        self.lang_combo.bind('<<ComboboxSelected>>', self.change_language)
        # pas de surlignage du texte choisi (effet « mot sélectionné ») : on l'efface et on rend le focus à la fenêtre
        self.lang_combo.bind('<FocusIn>', lambda e: self.lang_combo.selection_clear())
        self.lang_combo.pack(side='right')
        self.lang_label = ttk.Label(top, text=tr('label.language'), bootstyle='secondary')
        self.lang_label.pack(side='right', padx=6)
        # installation du jeu : version des données extraites, choix du dossier (et reconstruction de data/)
        self.btn_game = ttk.Button(top, text=tr('btn.game_dir'), command=self.install.change_game_dir, bootstyle='secondary')
        self.btn_game.pack(side='right', padx=(6, 18))
        self.game_label = ttk.Label(top, text='', bootstyle='secondary')
        self.game_label.pack(side='right')
        self.install.attach_label(self.game_label)

        # barre du bas : nombres d'objets (coffre, page affichée) bien visibles, personnage, puis message courant
        bottom = ttk.Frame(self.root, padding=(8, 4))
        bottom.pack(side='bottom', fill='x')
        self.count_total = ttk.Label(bottom, text='', font=(FONT, 10, 'bold'), bootstyle='info')
        self.count_total.pack(side='left')
        self.count_page = ttk.Label(bottom, text='', font=(FONT, 10, 'bold'), bootstyle='info')
        self.count_page.pack(side='left', padx=(18, 0))
        self.char_label = ttk.Label(bottom, text='', bootstyle='secondary')
        self.char_label.pack(side='left', padx=(18, 0))
        # message courant : occupe la place restante sans jamais imposer sa largeur à la fenêtre (width=1) ;
        # un message long est coupé au lieu d'élargir la fenêtre (sinon le panneau de détail « bougeait ») ;
        # toujours sur une ligne (OneLineLabel) : un texte de plusieurs lignes n'agrandit pas la fenêtre
        self.status = OneLineLabel(bottom, text='', bootstyle='secondary', anchor='e', width=1)
        self.status.pack(side='right', fill='x', expand=True, padx=(18, 0))

        body = ttk.Frame(self.root, padding=(6, 0, 6, 6))
        body.pack(fill='both', expand=True)

        self.char_view = CharacterView(body, self)
        # hauteur de la fenêtre identique panneau affiché ou replié : cale invisible de la hauteur du panneau
        self.char_view.frame.update_idletasks()
        tk.Frame(body, width=1, height=self.char_view.frame.winfo_reqheight(),
                 bg=ttk.Style().lookup('TFrame', 'background')).pack(side='right')
        self.stash_col = left = ttk.Frame(body)
        left.pack(side='left', fill='y')
        if self.show_char.get():
            self.char_view.frame.pack(side='left', fill='y', before=left)
        # ligne des onglets : pages 1 à 10, puis coffre du personnage / coffre partagé / cube ; pendant un
        # glisser-déposer, le survol d'un bouton de coffre l'affiche, comme celui d'un onglet affiche sa page (watch_tab)
        self.tabs_row = tabs = ttk.Frame(left)
        tabs.pack(side='top', fill='x')
        self.notebook = ttk.Notebook(tabs)
        self.notebook.pack(side='left', fill='x', expand=True)
        self.view = tk.StringVar(value='character')
        self.btn_views = {}
        for view, key in VIEWS:
            b = ttk.Radiobutton(tabs, text=tr(key), value=view, variable=self.view, command=self.open_view,
                                bootstyle='info-outline-toolbutton')
            # bouton de droite : un pixel de marge, son bord tombe sur la dernière colonne de cases (le trait qui
            # ferme la grille, presque de la couleur du fond, occupe le dernier pixel)
            b.pack(side='right', anchor='n', padx=(0, 0 if self.btn_views else 1))
            self.btn_views[view] = b
        # bouton « Cube » grisé (personnage sans cube Horadrim) : la raison dans la barre du bas au survol
        self.btn_views['cube'].bind('<Enter>', lambda e: self.btn_views['cube'].instate(['disabled']) and
                                    self.status.configure(text=tr('status.no_cube')))
        self.btn_views['cube'].bind('<Leave>', lambda e: self.show_status())
        for i in range(STASH.pages):   # numéro de page seul ; les nombres d'objets sont dans la barre du bas
            self.notebook.add(ttk.Frame(self.notebook), text=f' {i + 1} ')
        self.notebook.bind('<<NotebookTabChanged>>', lambda e: (self.draw_grid(), self.show_status()))

        self.grid = ItemGrid(left, self, STASH)   # grille de la page affichée
        canvas = self.grid.canvas
        canvas.pack(side='top', pady=(4, 0))
        canvas.bind('<Button-1>', self.on_click)
        canvas.bind('<B1-Motion>', self.on_drag)            # glisser-déposer d'un objet dans la page
        canvas.bind('<ButtonRelease-1>', self.on_release)
        canvas.bind('<Motion>', self.on_motion)
        canvas.bind('<Leave>', lambda e: self.show_status())
        canvas.bind('<Button-3>', lambda e: self.on_item_menu(e, self.item_at(e)))   # menu de l'objet (module)

        right = ttk.Frame(body, padding=(8, 0, 0, 0))
        right.pack(side='left', fill='both', expand=True)
        self.detail = tk.Text(right, width=DETAIL_WIDTH, wrap='word', bg=DETAIL_BG, fg=DETAIL_FG, bd=0,
                              padx=DETAIL_PADX, pady=8, font=(FONT, 10), cursor='arrow',
                              insertwidth=0, highlightthickness=0)
        # ascenseur affiché seulement si le détail dépasse (mxl_widgets.AutoScrollbar)
        self.detail_scroll = sb = AutoScrollbar(right, command=self.detail.yview, bootstyle='round')
        # défilement : les pointillés des compétences suivent le texte
        self.detail.configure(yscrollcommand=lambda a, b: (sb.set(a, b), hasattr(self, 'panel') and self.panel.hover.place()))
        # largeur fixe (DETAIL_WIDTH), pas étirée avec la fenêtre : infobulle de même largeur que dans la collection
        self.detail.pack(side='left', fill='y')
        sb.pack(side='left', fill='y')
        self.detail.bind('<Key>', lambda e: None if e.state & 4 else 'break')   # lecture seule, copie permise
        setup_detail_tags(self.detail)
        self.panel = DetailPanel(self.detail, self)
        self.set_detail(None)
        self.fit_window()

    def change_language(self, _ev=None):
        """Applique la langue choisie (et l'enregistre) sans redémarrer : textes fixes, titre, détail, état."""
        self.lang_combo.selection_clear()
        self.root.focus_set()
        code = self.languages[self.lang_combo.current()][0]
        i18n.set_language(code)
        self.char_title.configure(text=tr('label.character'))
        self.btn_char.configure(text=tr('btn.equipment'))
        self.char_view.retranslate()
        self.char_view.draw()
        for view, key in VIEWS:
            self.btn_views[view].configure(text=tr(key))
        self.library_ui.show_button()
        if self.library_ui.window:   # textes de l'écran « Library » : fenêtre reconstruite dans la nouvelle langue
            self.library_ui.window.close()
            self.library_ui.open()
        self.lang_label.configure(text=tr('label.language'))
        self.btn_game.configure(text=tr('btn.game_dir'))
        self.install.show_game()
        if self.path:
            self.root.title(tr('app.title_file', version=VERSION, file=os.path.basename(self.path)))
        else:
            self.root.title(tr('app.title', version=VERSION))
        self.set_detail(self.selected)
        self.show_status()


    # ---------- panneau du personnage ----------
    def fit_window(self):
        """Hauteur minimale de la fenêtre : celle de son contenu (l'équipement et le sac tiennent en entier, que le
        panneau du personnage soit affiché ou replié)."""
        self.root.update_idletasks()
        self.root.minsize(1, self.root.winfo_reqheight())

    def toggle_character(self):
        """Affiche ou replie le panneau du personnage ; la fenêtre reprend la taille de son contenu."""
        shown = self.show_char.get()
        if shown:
            self.char_view.frame.pack(side='left', fill='y', before=self.stash_col)
            self.char_view.draw()
        else:
            self.char_view.frame.pack_forget()
            if self.in_character(self.selected):   # objet sélectionné dans le panneau replié : plus de sélection
                self.selected = None
                self.set_detail(None)
        self.root.minsize(1, 1)
        self.root.geometry('')
        self.fit_window()

    def in_character(self, it):
        """Vrai si it est un objet du panneau du personnage (porté, dans le sac, ou porté par son mercenaire), pas de
        la grille du coffre."""
        return it is not None and self.char is not None and (any(it is x for x in self.char['items'])
                                                             or self.in_mercenary(it))

    def in_mercenary(self, it):
        """Vrai si it est un objet porté par le mercenaire du personnage (édition seulement)."""
        merc = self.char and self.char['mercenary']
        return it is not None and bool(merc) and any(it is x for x in merc['items'])

    def char_for(self, it):
        """Personnage de référence d'un objet : aucun pour un objet du mercenaire (ses attributs ne sont pas dans le
        fichier : exigences non évaluées), sinon le personnage choisi."""
        return None if self.in_mercenary(it) else self.char

    def select_worn(self, it):
        """Clic dans le panneau du personnage : objet sélectionné (None : aucun), détail affiché."""
        self.selected = it
        self.draw_grid()
        self.char_view.draw()
        self.set_detail(it)

    def hover_worn(self, it):
        """Survol du panneau du personnage : nom de l'objet dans la barre du bas."""
        if self.drag or self.carry:
            return
        if it:
            self.status.configure(text=self.full_name(it))
        else:
            self.show_status()

    def read_character(self, char_file):
        """Personnage de référence lu (exigences en rouge, bonus Force/Dex, panneau du personnage) ; illisible :
        l'éditeur reste utilisable, l'erreur est affichée en bas."""
        try:
            self.char, self.char_error = (load_character(char_file, self.data) if os.path.exists(char_file) else None), None
            if self.char:   # exigences (cases rouges, infobulles) : attributs totaux, comme la feuille du jeu
                with_total_attributes(self.char, self.data)
        except Exception as e:
            self.char, self.char_error = None, str(e) if isinstance(e, (FormatError, OSError)) else f'{type(e).__name__}: {e}'
        self.cube_state = self.character_cube(self.char)
        self.btn_views['cube'].state(['disabled' if self.cube_state == 'none' else '!disabled'])
        lib = getattr(self, 'library_ui', None)
        if lib and lib.window:   # écran « Library » ouvert : objet affiché recalculé pour ce personnage
            lib.window.show_detail()

    def character_cube(self, char):
        """État du cube du personnage char (mxl_containers.cube_status) : cube Horadrim cherché dans son sac et dans
        son coffre (<nom>.stash, déjà lu s'il est affiché)."""
        if char is None:
            return 'none'
        stash = os.path.splitext(char['path'])[0] + '.stash'
        try:
            items = self.items if self.path == stash else parse_stash(stash, self.data) if os.path.exists(stash) else []
        except Exception:   # coffre illisible (en cours d'écriture) : cube cherché dans le sac seulement
            items = []
        return cube_status(char['items'], items)

    # ---------- personnage et coffre ----------
    def characters(self):
        """Noms des personnages sauvegardés (<nom>.d2s du dossier de sauvegarde), par ordre alphabétique."""
        return sorted((os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(self.save_dir, '*.d2s'))),
                      key=str.lower)

    def select_character(self, name, view):
        """Liste des personnages à jour, name choisi (s'il existe, sinon le premier) et vue choisie, sans rien ouvrir."""
        names = self.characters()
        self.char_combo.configure(values=names)
        if names:
            self.char_combo.current(names.index(name) if name in names else 0)
        else:
            self.char_combo.set('')
        self.view.set(view)

    def character_file(self):
        """<nom>.d2s du personnage choisi, ou None s'il n'y a aucun personnage."""
        name = self.char_combo.get()
        return os.path.join(self.save_dir, name + '.d2s') if name else None

    def shared_stash_path(self):
        """Coffre partagé du dossier des sauvegardes (qu'il soit affiché ou non)."""
        return os.path.join(self.save_dir, SHARED_STASH) if self.save_dir else None

    def side_stashes(self):
        """Coffres associés au personnage sélectionné, existants et non affichés : son coffre (<nom>.stash) et le
        coffre partagé (découvertes enregistrées sans les ouvrir ; son .d2s est lu avec le personnage)."""
        name = self.char_combo.get()
        paths = ([os.path.join(self.save_dir, name + '.stash')] if name else []) + [self.shared_stash_path()]
        shown = os.path.abspath(self.path) if self.path else None
        return [p for p in paths if p and os.path.exists(p) and os.path.abspath(p) != shown]

    def transfer_sources(self):
        """Conteneurs du transfert vers la collection (« Transfer from character… ») : coffre du personnage lu
        (<nom>.stash, s'il existe), son sac, et son cube s'il a un cube Horadrim ; jamais ses objets portés, ceux de son
        mercenaire ni le coffre partagé, quelle que soit la vue affichée. Aucun personnage lu : []."""
        if not self.char:
            return []
        d2s = self.char['path']
        stash = os.path.splitext(d2s)[0] + '.stash'
        return (([(stash, None)] if os.path.exists(stash) else []) + [(d2s, 'inventory')]
                + ([(d2s, 'cube')] if self.cube_state == 'ok' else []))

    def view_path(self):
        """Fichier de la vue choisie : <personnage>.stash, le coffre partagé, ou <personnage>.d2s (cube)."""
        name, view = self.char_combo.get(), self.view.get()
        return os.path.join(self.save_dir, SHARED_STASH if view == 'shared' else name + ('.d2s' if view == 'cube' else '.stash'))

    def open_view(self, keep_page=False):
        """Ouvre le coffre de la vue choisie : celui du personnage choisi, ou le coffre partagé affiché pour ce
        personnage ; coffre absent (personnage sans coffre, coffre partagé jamais créé par le jeu) : grille vide et
        message. Choix retenus dans les réglages. keep_page : page affichée gardée (sinon dernière page du jeu)."""
        char_file = self.character_file()
        if not char_file:
            return
        if self.view.get() == 'cube':   # personnage sans cube Horadrim ni objets dans son cube : son coffre
            try:
                char = load_character(char_file, self.data)
            except Exception:
                char = None
            if self.character_cube(char) == 'none':
                self.view.set('character')
        settings.put('last_character', self.char_combo.get())
        settings.put('last_view', self.view.get())
        path = self.view_path()
        if not os.path.exists(path):
            self.grid.icons.clear()
            self.set_box(stash_box(path))
            self.path, self.items, self.selected, self.char_file, self.files_seen = None, [], None, None, None
            self.read_character(char_file)   # personnage sans coffre : son équipement et son sac restent affichés
            self.char_view.draw()
            self.root.title(tr('app.title', version=VERSION))
            self.draw_grid()
            self.set_detail(None)
            self.show_status()
            return
        if keep_page:
            self.selected = None   # pas de sélection reprise d'un autre coffre
        self.load(path, char_file=char_file, keep_selection=keep_page)

    # ---------- fichier ----------
    def reload(self, quiet=False):
        if self.path:
            self.load(self.path, keep_selection=True, quiet=quiet)

    def watch_files(self):
        """Toutes les WATCH_MS : coffre ouvert ou personnage de référence modifié sur le disque (partie jouée, sauvegarde
        du jeu) : coffre relu, sélection gardée ; coffre attendu apparu (coffre partagé créé par le jeu) : ouvert.
        Pas pendant un glisser-déposer. Les écritures de l'éditeur relisent déjà le coffre (signatures à jour)."""
        try:
            if self.drag is None:
                if self.path:
                    before = self.files_seen
                    if (file_signature(self.path), file_signature(self.char_file)) != before:
                        self.reload(quiet=True)
                        if self.files_seen != before:   # relu (pas illisible en cours d'écriture)
                            self.status.configure(text=tr('status.reloaded'))
                elif self.char_combo.get() and os.path.exists(self.view_path()):
                    self.open_view()
                # coffre du personnage ou coffre partagé modifié alors qu'il n'est pas affiché : découvertes enregistrées
                # quand même (première fois : à l'ouverture d'un coffre, déjà faite par load)
                sigs = {p: file_signature(p) for p in self.side_stashes()}
                if sigs != getattr(self, 'side_seen', sigs):
                    self.library_ui.record_found()
                self.side_seen = sigs
        finally:
            self.root.after(WATCH_MS, self.watch_files)

    def load(self, path, keep_selection=False, char_file=None, quiet=False):
        """Lit le coffre path (ou, pour un personnage .d2s, son cube : un coffre sans page) ;
        personnage de référence : char_file, sinon celui du coffre déjà ouvert (rechargement),
        sinon <même nom>.d2s à côté du coffre. quiet (relecture automatique) : fichier illisible (en cours d'écriture
        par le jeu) sans message, nouvel essai à la surveillance suivante."""
        seen = (file_signature(path), None)
        cube = is_character(path)
        try:
            items = read_items(path, self.data)
        except Exception as e:
            if not quiet:
                messagebox.showerror(tr('err.read.title'), f'{path}\n\n{type(e).__name__}: {e}')
            return
        settings.put('last_stash', os.path.abspath(path))   # rouvert au prochain lancement
        if char_file is None:
            char_file = self.char_file if path == self.path and self.char_file else os.path.splitext(path)[0] + '.d2s'
        old = self.selected
        old_worn = old if self.in_character(old) else None   # sélection dans le panneau du personnage
        self.set_box(character_containers(self.data)['cube'] if cube else stash_box(path))
        self.grid.icons.clear()
        self.path, self.items, self.selected, self.char_file = path, items, None, char_file
        self.files_seen = (seen[0], file_signature(char_file))
        self.read_character(char_file)
        if cube:   # cube modifiable seulement si le personnage a un cube Horadrim
            self.set_box(replace(self.box, writable=self.cube_state == 'ok'))
        if keep_selection and old_worn:
            self.selected = self.char_view.find(old_worn)
        elif keep_selection and old:
            self.selected = next((i for i in items if (i['page'], i['x'], i['y']) ==
                                  (old['page'], old['x'], old['y'])), None)
        if not keep_selection and not cube:   # ouverture sur la dernière page affichée en jeu
            last = last_page(path)
            if last < STASH.pages:
                self.notebook.select(last)
        self.root.title(tr('app.title_file', version=VERSION, file=os.path.basename(path)))
        self.draw_grid()
        self.char_view.draw()
        self.set_detail(self.selected)
        self.show_status()
        self.library_ui.record_found()


    # ---------- grille ----------
    def page(self):
        return self.notebook.index('current') if self.box.pages > 1 else 0

    def set_box(self, box):
        """Conteneur affiché : forme de la grille ; onglets des pages masqués pour un conteneur sans page."""
        if box == self.box:
            return
        self.box = box
        self.grid.set_box(box)
        row = self.tabs_row
        if box.pages > 1:
            self.notebook.pack(side='left', fill='x', expand=True)
            row.pack_propagate(True)
        else:   # la ligne garde sa hauteur sans les onglets : la grille ne remonte pas
            row.update_idletasks()
            row.configure(height=row.winfo_reqheight())
            row.pack_propagate(False)
            self.notebook.pack_forget()

    def reload_data(self):
        """data/ reconstruit ou réparé (GameInstall) : tables relues, icônes et coffre ouvert réaffichés."""
        self.data = Data(DATA_DIR)
        self.grid.icons.clear()
        if self.path:
            self.load(self.path, keep_selection=True)

    # ---------- panneau de détail (DetailPanel) : App en est l'hôte (DetailHost) ----------
    def set_detail(self, it):
        self.panel.show(it)

    def needs_backup(self, path):
        """Vrai si le fichier n'a pas encore été sauvegardé (.bak) pendant cette session (une sauvegarde par fichier)."""
        return os.path.abspath(path) not in self.backups_done

    def backup_made(self, path, bak):
        if bak:
            self.backups_done.add(os.path.abspath(path))

    def full_name(self, it):
        return full_name(it, self.data)

    def can_transfer(self, it):
        """Unique ou objet de set du coffre (ou cube) ouvert ou du sac : bouton de transfert vers la collection."""
        if slot_key(it, self.data) is None:   # ni au catalogue, ni supérieur admis au stockage
            return False
        if self.in_character(it):
            return place(it) == 'inventory' and not self.in_mercenary(it)
        return bool(self.stash_path) and it in self.items

    def transfer(self, it):
        source = (self.char_file, 'inventory') if self.in_character(it) else (self.stash_path, self.box.key)
        self.library_ui.open_transfer(only={it['_offset']}, source=source)

    def commit_edit(self, it, edit):
        """Écrit l'édition dans le fichier de l'objet : module mxl_editor (point d'accroche commit_edit : contrôles,
        sauvegarde, relecture) ; sans lui, refusée (la base n'écrit jamais de valeur). (True, objet relu) / (False, None)."""
        write = hook('commit_edit')
        return write(self, it, edit) if write and self.editing_setting else (False, None)

    def edit_done(self, it, line, value):
        bak = self.last_edit_backup
        self.status.configure(text=tr('status.edited', item=self.full_name(it), line=line, value=value)
                              + (tr('status.backup', file=os.path.basename(bak)) if bak else ''))

    def priorities_changed(self, priorities, key):
        if self.library_ui.window:   # qualité des exemplaires rangés et panneau de la collection (sur place)
            self.library_ui.window.priorities_changed(priorities, key)

    def size(self, it):
        return self.data.base(it['code']).size

    def draw_grid(self):
        """Objets de la page affichée dessinés dans la grille."""
        self.grid.draw([i for i in self.items if i['page'] == self.page()], self.selected)

    def item_at(self, ev):
        return self.grid.item_at(ev)

    def on_click(self, ev):
        """Clic dans la grille de droite : objet sélectionné, début d'un éventuel glisser-déposer ; objet en main :
        posé ici (carry_drop)."""
        if self.carry:
            self.carry_drop(ev)
            return 'break'
        self.selected = self.item_at(ev)
        self.draw_grid()
        self.char_view.draw()
        self.set_detail(self.selected)
        self.start_drag(ev, 'main', self.selected)

    def on_bag_click(self, ev):
        """Clic dans le sac du personnage : objet sélectionné, début d'un éventuel glisser-déposer ; objet en main :
        posé ici."""
        if self.carry:
            self.carry_drop(ev)
            return 'break'
        it = self.char_view.bag.item_at(ev)
        self.select_worn(it)
        self.start_drag(ev, 'bag', it)

    def start_drag(self, ev, src, it):
        """Retient l'objet saisi dans la grille src ('main' ou 'bag'), la case de l'objet sous la souris, son fichier et
        son conteneur (pas dans un conteneur en lecture seule)."""
        zone = self.zones().get(src)
        if it is None or zone is None or not zone[0].box.writable:
            self.drag = None
            return
        grid, path, where = zone[:3]
        cx, cy = grid.cell_at(ev)
        self.drag = dict(item=it, dx=cx - it['x'], dy=cy - it['y'], target=None, src=src, path=path, where=where,
                         view=self.view.get(), grid=grid)

    def zones(self):
        """Grilles où un objet peut être pris ou déposé : {nom: (grille, fichier, conteneur, page, objets)} — 'main' :
        coffre ou cube affiché à droite ; 'bag' : sac du personnage (panneau affiché)."""
        out = {}
        if self.path:
            out['main'] = (self.grid, self.path, self.box.key, self.page(), self.items)
        if self.char and self.show_char.get() and not self.char_view.mercenary():
            out['bag'] = (self.char_view.bag, self.char_file, 'inventory', 0, self.char_view.bag.items)
        return out

    def drop_target(self, ev, d):
        """Dépôt de l'objet du glisser-déposer d à la position de la souris (ev : événement d'une grille quelconque,
        repéré par ses coordonnées d'écran) : (grille visée ou None, x, y, dépôt possible). Possible = dans la grille,
        sans chevaucher un autre objet de la page (placement_error : forme et règles du conteneur)."""
        for name, (grid, path, where, page, items) in self.zones().items():
            c = grid.canvas
            e = SimpleNamespace(x=ev.x_root - c.winfo_rootx(), y=ev.y_root - c.winfo_rooty())
            if not grid.inside(e):
                continue
            cx, cy = grid.cell_at(e)
            x, y = cx - d['dx'], cy - d['dy']
            if path == d['path']:   # même fichier : l'objet déplacé (éventuellement relu entre-temps) ne se gêne pas
                items = [o for o in items if o['_offset'] != d['item']['_offset']]
            return name, x, y, grid.box.writable and placement_error(items, d['item'], page, x, y, self.data,
                                                                      grid.box) is None
        return None, None, None, False

    def tab_under(self, ev):
        """Onglet sous la souris (indice) pendant un glissement, ou None."""
        nb = self.notebook
        nx, ny = ev.x_root - nb.winfo_rootx(), ev.y_root - nb.winfo_rooty()
        if not (0 <= nx < nb.winfo_width() and 0 <= ny < nb.winfo_height()) or not nb.identify(nx, ny):
            return None
        try:
            return nb.index(f'@{nx},{ny}')
        except tk.TclError:
            return None

    def view_under(self, ev):
        """Bouton de coffre (vue 'character' / 'shared' / 'cube') sous la souris pendant un glissement, ou None."""
        for view, b in self.btn_views.items():
            bx, by = ev.x_root - b.winfo_rootx(), ev.y_root - b.winfo_rooty()
            if 0 <= bx < b.winfo_width() and 0 <= by < b.winfo_height():
                return view
        return None

    def watch_tab(self, ev):
        """Survol d'un onglet ou d'un bouton de coffre pendant un glissement : après TAB_HOVER_MS, bascule sur sa page
        ou sur ce coffre (sans limite tant que le bouton de la souris n'est pas relâché). Renvoie ce qui est survolé
        (('tab', n°) ou ('view', vue)) ou None."""
        tab, view = self.tab_under(ev), self.view_under(ev)
        target = ('tab', tab) if tab is not None else ('view', view) if view else None
        if self.tab_hover and self.tab_hover[0] == target:
            return target
        if self.tab_hover:
            self.root.after_cancel(self.tab_hover[1])
            self.tab_hover = None
        if tab is not None and tab != self.page():
            self.tab_hover = (target, self.root.after(TAB_HOVER_MS, lambda: self.switch_tab(tab)))
        elif view and view != self.view.get() and not self.btn_views[view].instate(['disabled']):
            self.tab_hover = (target, self.root.after(TAB_HOVER_MS, lambda: self.switch_view(view)))
        return target

    def switch_tab(self, tab):
        """Survol d'un onglet pendant un glissement ou avec un objet en main : page affichée."""
        self.tab_hover = None
        d = self.drag or self.carry
        if d:
            d['target'] = None
            self.notebook.select(tab)
            name = d.get('name') or self.full_name(d['item'])
            self.root.after(50, lambda: self.status.configure(text=tr('status.drop_here', page=tab + 1, item=name)))

    def switch_view(self, view):
        """Pendant un glissement ou avec un objet en main (10/10 : survol des boutons aussi en main) : affiche l'autre
        coffre ou le cube (même page si elle existe), l'objet reste « en main » ; déposé, il y sera transféré
        (on_release) ou écrit (carry_drop)."""
        self.tab_hover = None
        d = self.drag or self.carry
        if d:
            d['target'] = None
            self.view.set(view)
            self.open_view(keep_page=True)
            name = d.get('name') or self.full_name(d['item'])
            self.root.after(50, lambda: self.status.configure(
                text=tr('status.drop_here_stash', stash=self.stash_name(view), item=name)))

    def stash_name(self, view):
        return tr(dict(VIEWS)[view])

    def on_drag(self, ev):
        """Pendant le glissement : surbrillance légère des cases où l'objet serait déposé (rouge si impossible), dans la
        grille sous la souris (coffre ou cube à droite, sac à gauche) ; survol d'un onglet ou d'un bouton de coffre =
        changement de page ou de coffre après un court délai."""
        if not self.drag:
            return
        d = self.drag
        if self.floating.win is None:   # image de l'objet sous la souris, à la case saisie (10/10)
            g = d['grid']
            self.floating.show(g, d['item'], ev.x_root, ev.y_root, (d['dx'] * g.cell + g.cell // 2,
                                                                     d['dy'] * g.cell + g.cell // 2))
        self.floating.move(ev.x_root, ev.y_root)
        self.show_drop_target(ev, d)

    def show_drop_target(self, ev, d):
        """Glisser-déposer ou objet en main d : cases visées éclairées (rouge si impossible), survol d'un onglet ou
        d'un bouton de coffre = changement de page ou de coffre après un court délai ; message dans la barre."""
        grids = [z[0] for z in self.zones().values()]
        if self.watch_tab(ev) is not None:   # souris sur les onglets : pas de dépôt possible
            for g in grids:
                g.clear_drop()
            d['target'] = None
            return
        zone, x, y, ok = self.drop_target(ev, d)
        if d['target'] == (zone, x, y):
            return
        d['target'] = (zone, x, y) if zone else None
        for g in grids:
            g.clear_drop()
        it = d['item']
        if zone is None:
            self.show_status()
            return
        self.zones()[zone][0].show_drop(it, x, y, ok)
        self.status.configure(text=tr('status.carry_to' if d is self.carry else 'status.move_to',
                                      item=d.get('name') or self.full_name(it), x=x, y=y) if ok
                              else tr('status.drop_invalid', x=x, y=y))

    def on_release(self, ev):
        """Fin du glissement : l'objet est déplacé si la case visée est valide et différente — dans sa grille
        (move_item), entre le sac et le cube du même personnage (move_between, une écriture) ou d'un fichier à l'autre
        (transfer_item : coffre, coffre partagé, cube, sac)."""
        d, self.drag = self.drag, None
        if not self.carry:   # (un clic qui pose un objet en main en reprend un autre avec Ctrl : image gardée)
            self.floating.hide()
        if self.tab_hover:
            self.root.after_cancel(self.tab_hover[1])
            self.tab_hover = None
        for z in self.zones().values():
            z[0].clear_drop()
        # objet pris dans la grille de droite, qui a changé de coffre pendant le glissement (survol d'un bouton)
        switched = d and d['src'] == 'main' and d['path'] != self.path
        zone, x, y, ok = self.drop_target(ev, d) if d else (None, None, None, False)
        if not d or d['target'] is None or zone is None:
            if switched:   # relâché hors d'une grille : retour au coffre d'origine (rien n'a bougé)
                self.view.set(d['view'])
                self.open_view(keep_page=True)
            self.draw_grid()
            return
        it, spath, swhere = d['item'], d['path'], d['where']
        _, dpath, dwhere, page, _ = self.zones()[zone]
        same = spath == dpath and swhere == dwhere
        if not ok or (same and (page, x, y) == (it.get('page') or 0, it['x'], it['y'])):
            self.show_status()
            return
        name = self.full_name(it)
        try:
            if same:
                baks = {dpath: move_item(dpath, it, x, y, self.data, page=page, backup=self.needs_backup(dpath),
                                         where=dwhere)}
            elif spath == dpath:
                baks = {dpath: move_between(dpath, it, swhere, dwhere, x, y, self.data, backup=self.needs_backup(dpath))}
            else:
                b_src, b_dst = transfer_item(spath, dpath, it, page, x, y, self.data, backup_src=self.needs_backup(spath),
                                             backup_dst=self.needs_backup(dpath), src_where=swhere, dst_where=dwhere)
                baks = {dpath: b_dst, spath: b_src}
        except (EditError, FormatError, OSError) as e:
            messagebox.showerror(tr('err.move.title'), str(e))
            self.refresh_files()
            return
        for p, bak in baks.items():
            self.backup_made(p, bak)
        self.refresh_files()
        if zone == 'bag':
            self.selected = next((i for i in self.char_view.bag.items if (i['x'], i['y']) == (x, y)), None)
            text = tr('status.moved_bag', item=name, x=x, y=y)
        else:
            self.selected = next((i for i in self.items if (i['page'], i['x'], i['y']) == (page, x, y)), None)
            if self.box.pages == 1:
                text = tr('status.moved_cube' if same else 'status.moved_to_cube', item=name, x=x, y=y)
            elif same:
                text = tr('status.moved', item=name, page=page + 1, x=x, y=y)
            else:
                text = tr('status.moved_stash', item=name, stash=self.stash_name(self.view.get()), page=page + 1, x=x, y=y)
        self.draw_grid()
        self.char_view.draw()
        self.set_detail(self.selected)
        self.show_status()   # nombres d'objets du coffre et de la page
        names = ', '.join(os.path.basename(b) for b in baks.values() if b)
        self.status.configure(text=text + (tr('status.backup', file=names) if names else ''))

    def refresh_files(self):
        """Relit le coffre (ou cube) affiché et le personnage après une écriture ; sélection gardée si possible."""
        if self.path:
            self.load(self.path, keep_selection=True)
        else:
            self.read_character(self.char_file)
            self.char_view.draw()

    # ---------------------------------------------------------------- objet en main, menu de l'objet
    def source_of(self, it):
        """(fichier, conteneur) d'un objet affiché : coffre ou cube de droite, sac, objet porté, objet du mercenaire."""
        if self.in_mercenary(it):
            return self.char_file, 'mercenary'
        if self.in_character(it):
            return self.char_file, place(it)
        return self.path, self.box.key

    def on_item_menu(self, ev, it):
        """Clic droit sur un objet (coffre, coffre partagé, cube, sac, objet porté) : menu des actions du module
        mxl_editor (point d'accroche item_menu : [(libellé, fonction)]) ; sans le module ou sans action : rien. Objet en
        main : annulé."""
        if self.carry:
            self.cancel_carry()
            return 'break'
        make = hook('item_menu')
        actions = make(self, it) if make and it is not None and not self.drag else None
        if not actions:
            return None
        self.selected = it
        self.draw_grid()
        self.char_view.draw()
        self.set_detail(it)
        menu = tk.Menu(self.root, tearoff=False)
        for label, action in actions:
            menu.add_command(label=label, command=action)
        menu.tk_popup(ev.x_root, ev.y_root)
        return 'break'

    def start_carry(self, it, blob, name, next_copy=None):
        """Objet « en main » (10/10, duplication du module) : it (objet lu des octets blob, sans fichier) suit la
        souris ; clic gauche sur une place libre d'une grille (coffre, coffre partagé, cube, sac ; page ou coffre
        changés au survol des onglets et des boutons) : posé là (carry_drop) ; Ctrl + clic : posé, et next_copy()
        (nouveaux octets) reste en main ; Échap ou clic droit : annulé, rien d'écrit."""
        g = self.grid
        w, h = g.size(it)
        self.carry = dict(item=it, blob=blob, name=name, next_copy=next_copy, dx=w // 2, dy=h // 2, target=None,
                          path=None, where=None)
        px, py = self.root.winfo_pointerxy()
        # image tenue par la case (dx, dy), comme les cases éclairées sous la souris
        self.floating.show(g, it, px, py, ((w // 2) * g.cell + g.cell // 2, (h // 2) * g.cell + g.cell // 2))
        self.root.bind_all('<Motion>', self.carry_motion)
        self.root.bind_all('<Escape>', lambda e: self.cancel_carry())
        self.status.configure(text=tr('status.carry', item=name))

    def carry_motion(self, ev):
        """Objet en main : image sous la souris, cases visées éclairées (comme un glisser-déposer)."""
        if not self.carry:
            return
        self.floating.move(ev.x_root, ev.y_root)
        self.show_drop_target(ev, self.carry)

    def end_carry(self):
        """Fin de l'objet en main : image, surbrillance et liaisons retirées."""
        self.carry = None
        self.floating.hide()
        self.root.unbind_all('<Motion>')
        self.root.unbind_all('<Escape>')
        if self.tab_hover:
            self.root.after_cancel(self.tab_hover[1])
            self.tab_hover = None
        for z in self.zones().values():
            z[0].clear_drop()

    def cancel_carry(self):
        """Échap ou clic droit : l'objet en main est abandonné, rien n'est écrit."""
        name = self.carry['name'] if self.carry else ''
        self.end_carry()
        self.draw_grid()
        self.show_status()
        self.status.configure(text=tr('status.carry_cancelled', item=name))

    def carry_drop(self, ev):
        """Clic avec un objet en main : posé à la place visée si elle est libre (edit_stash : insertion contrôlée,
        sauvegarde, relecture ; refus si le jeu est ouvert : message et objet abandonné) ; Ctrl + clic : un nouvel
        exemplaire (next_copy) reste en main."""
        d = self.carry
        zone, x, y, ok = self.drop_target(ev, d)
        if zone is None or not ok:
            if zone is not None:
                self.status.configure(text=tr('status.drop_invalid', x=x, y=y))
            return
        _, path, where, page, _ = self.zones()[zone]
        try:
            bak = edit_stash(path, self.data, insert=[(page, x, y, d['blob'])], backup=self.needs_backup(path),
                             where=where)
        except (EditError, FormatError, OSError) as e:
            self.end_carry()
            messagebox.showerror(tr('err.carry.title'), str(e))
            self.refresh_files()
            return
        self.backup_made(path, bak)
        if zone == 'bag':
            place_text = tr('status.place_bag', x=x, y=y)
        elif self.box.pages == 1:
            place_text = tr('status.place_cube', x=x, y=y)
        else:
            place_text = tr('status.place_stash', stash=self.stash_name(self.view.get()), page=page + 1, x=x, y=y)
        nxt = None
        if getattr(ev, 'state', 0) & 0x0004 and d['next_copy']:   # Ctrl + clic : un autre exemplaire en main
            try:
                nxt = d['next_copy']()
            except EditError as e:
                messagebox.showerror(tr('err.carry.title'), str(e))
        self.end_carry()
        self.refresh_files()
        self.draw_grid()
        self.char_view.draw()
        text = tr('status.dropped', item=d['name'], place=place_text) + (
            tr('status.backup', file=os.path.basename(bak)) if bak else '')
        if nxt is not None:
            self.start_carry(blob_item(nxt, self.data), nxt, d['name'], d['next_copy'])
        self.status.configure(text=text)

    def on_motion(self, ev):
        if self.drag or self.carry:
            return
        it = self.item_at(ev)
        if it:
            w, h = self.size(it)
            self.status.configure(text=tr('status.hover', item=self.full_name(it), x=it['x'], y=it['y'], w=w, h=h))
        else:
            self.show_status()

    def show_status(self):
        """Barre du bas : nombre d'objets du coffre et de la page affichée, personnage, rappel d'usage."""
        if not self.path:
            for lab in (self.count_total, self.count_page, self.char_label):
                lab.configure(text='')
            # coffre du choix absent (personnage sans coffre, coffre partagé pas encore créé), sinon aucun personnage
            self.status.configure(text=tr('status.no_stash', file=os.path.basename(self.view_path()))
                                  if self.char_combo.get() else tr('status.open_file'))
            return
        n = sum(1 for i in self.items if i['page'] == self.page())
        cube = self.box.pages == 1
        self.count_total.configure(text=tr('count.cube' if cube else 'count.stash', n=len(self.items)))
        self.count_page.configure(text='' if cube else tr('count.page', page=self.page() + 1, n=n))
        ch = self.char
        self.char_label.configure(text=tr('status.char', name=ch['name'], cls=CLASSES[ch['cls']], level=ch['level'],
                                          str=ch['strength'], dex=ch['dexterity']) if ch else
                                  tr('status.char_error', error=self.char_error) if self.char_error else tr('status.no_char'))
        self.status.configure(text=tr('status.hint' if self.box.writable else
                                      'status.cube_readonly' if self.box.key == 'cube' else 'status.hint_readonly'))


def main():
    try:   # netteté sur les écrans à mise à l'échelle Windows
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    # fichiers des versions précédentes repris dans le dossier unique de l'utilisateur (mxl_home), puis langue relue
    # dans les réglages repris (lue à l'import d'i18n, avant la reprise)
    if migrate():
        i18n.set_language(settings.get('language', i18n.DEFAULT), save=False)
    root = ttk.Window(themename='darkly')
    error = editor_error()
    if error:   # module complémentaire présent mais cassé : message à l'écran plutôt qu'une fermeture muette
        root.withdraw()
        messagebox.showerror(tr('err.editor.title'), tr('err.editor', error=error), parent=root)
        root.destroy()
        sys.exit(1)
    app = App(root, sys.argv[1] if len(sys.argv) > 1 else None)
    if os.environ.get('MXL_EXIT_AFTER'):   # essai de l'exécutable (build_exe.py) : fermeture normale après n ms
        root.after(int(os.environ['MXL_EXIT_AFTER']), app.on_close)
    root.mainloop()


if __name__ == '__main__':
    main()
