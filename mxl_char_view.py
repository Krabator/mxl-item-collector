"""Panneau du personnage : son équipement et son sac, disposés comme l'écran d'inventaire du jeu (mêmes emplacements,
mêmes tailles en cases), resserrés et réunis dans un cadre, dans le style de l'éditeur. Affiché à gauche du
coffre, repliable.

En haut, un canevas avec le cadre de l'équipement (objets portés du .d2s, onglets I / II des deux jeux d'armes) ;
dessous, le sac (mxl_grid.ItemGrid, 15 × 10). Un clic sélectionne l'objet (host.select_worn, host.on_bag_click),
dont le détail s'affiche dans le panneau de droite ; les objets du sac se déplacent par glisser-déposer (host.on_drag,
host.on_release : dans le sac ou vers la grille de droite) ; les objets portés s'éditent par curseurs mais ne se déplacent pas. Sélecteur en haut : Personnage ou
Mercenaire (son équipement : édition par curseurs, pas de déplacement). host : la fenêtre (data, char, selected).
"""
import tkinter as tk
import ttkbootstrap as ttk

import settings
from i18n import tr

from mxl_containers import character_containers, place, placed, weapon_slots, ACTIVE_HANDS
from mxl_grid import ItemGrid
from mxl_gui_detail import item_color, LAYERS_SHOWN
from mxl_tooltip import requirements_unmet
from mxl_theme import BG, GRID_LINE, EMPTY, CELL_OK, CELL_KO, SELECTION, FONT, LABEL_DIM, blend

CELL = 37                 # taille d'une case en pixels (à 96 dpi) : celle du cube
# cadre de l'équipement, en pixels à 96 dpi : écart entre deux emplacements, hauteur des onglets I / II, marge
# intérieure du cadre
GAP, TABS_HEIGHT, PAD = 6, 18, 12
MERC_SLOTS = (1, 2, 3, 4, 5, 8, 9, 10)   # emplacements d'un mercenaire : pas d'anneaux (inventory.bin, ligne 13)


class CharacterView:
    def __init__(self, parent, host):
        self.host = host
        self.frame = ttk.Frame(parent, padding=(0, 0, 8, 0))
        # sélecteur : équipement et sac du personnage, ou équipement de son mercenaire (pas de sac)
        self.who = tk.StringVar(value=settings.get('panel_view') or 'character')
        row = ttk.Frame(self.frame)
        row.pack(side='top', fill='x', pady=(0, 4))
        self.btn_who = {}
        for who, key in (('character', 'btn.panel_character'), ('mercenary', 'btn.panel_mercenary')):
            b = ttk.Radiobutton(row, text=tr(key), value=who, variable=self.who, command=self.switch,
                                bootstyle='info-outline-toolbutton')
            b.pack(side='left')
            self.btn_who[who] = b
        box = character_containers(host.data)['inventory']
        self.bag = ItemGrid(self.frame, host, box, cell=CELL)
        self.cell = self.bag.cell
        c, scale = self.cell, self.cell / CELL
        g, tab, pad = (round(v * scale) for v in (GAP, TABS_HEIGHT, PAD))
        width = box.cols * c + 1
        # cinq colonnes (arme et gants, anneau, tête / armure / ceinture, amulette et anneau, arme et bottes), bas
        # alignés ; groupe centré dans le cadre
        height = tab + 4 * c + g + 2 * c
        xs = [(width - (8 * c + 4 * g)) // 2]
        for w in (2, 1, 2, 1):
            xs.append(xs[-1] + w * c + g)
        top = pad
        belt = top + height - c
        armor = belt - g - 3 * c
        spots = {4: (xs[0], top + tab, 2, 4), 10: (xs[0], top + tab + 4 * c + g, 2, 2),
                 5: (xs[4], top + tab, 2, 4), 9: (xs[4], top + tab + 4 * c + g, 2, 2),
                 1: (xs[2], armor - g - 2 * c, 2, 2), 3: (xs[2], armor, 2, 3), 8: (xs[2], belt, 2, 1),
                 6: (xs[1], belt - g - c, 1, 1), 7: (xs[3], belt - g - c, 1, 1), 2: (xs[3], armor, 1, 1)}
        # emplacement (champ « equipped » des objets) -> rectangle (x0, y0, x1, y1) du canevas
        self.slots = {n: (x, y, x + w * c, y + h * c) for n, (x, y, w, h) in spots.items()}
        self.tabs = {}   # (emplacement d'arme, jeu d'armes) -> rectangle de son onglet
        for n in ACTIVE_HANDS:
            x0, y0, x1, _ = self.slots[n]
            mid = (x0 + x1) // 2
            self.tabs[n, 1], self.tabs[n, 2] = (x0, y0 - tab, mid, y0 - 2), (mid, y0 - tab, x1, y0 - 2)
        self.weapon_set = 1        # onglet I / II affiché (celui du jeu actif à chaque nouvelle lecture du personnage)
        self.shown_char = None     # (fichier, jeu actif) du personnage dont l'onglet a été choisi
        self.worn = {}   # emplacement dessiné -> objet porté
        self.canvas = tk.Canvas(self.frame, width=width, height=top + height + pad,
                                bg=ttk.Style().lookup('TFrame', 'background') or BG, highlightthickness=0)
        self.canvas.pack(side='top')
        self.bag.canvas.pack(side='top', pady=(round(GAP * scale), 0))
        self.canvas.bind('<Button-1>', self.on_click)
        self.canvas.bind('<Motion>', lambda e: host.hover_worn(self.item_at(e)))
        self.bag.canvas.bind('<Button-1>', host.on_bag_click)
        self.bag.canvas.bind('<B1-Motion>', host.on_drag)
        self.bag.canvas.bind('<ButtonRelease-1>', host.on_release)
        self.bag.canvas.bind('<Motion>', lambda e: host.hover_worn(self.bag.item_at(e)))
        for c in (self.canvas, self.bag.canvas):
            c.bind('<Leave>', lambda e: host.hover_worn(None))
        # menu de l'objet (module mxl_editor : duplication) ; objet en main : annulé
        self.canvas.bind('<Button-3>', lambda e: host.on_item_menu(e, self.item_at(e)))
        self.bag.canvas.bind('<Button-3>', lambda e: host.on_item_menu(e, self.bag.item_at(e)))

    def mercenary(self):
        """Vrai si le panneau affiche le mercenaire (choisi, et le personnage en a un)."""
        ch = self.host.char
        return self.who.get() == 'mercenary' and bool(ch and ch['mercenary'])

    def switch(self):
        """Changement Personnage / Mercenaire : choix retenu, sélection du panneau abandonnée."""
        settings.put('panel_view', self.who.get())
        if self.host.in_character(self.host.selected):
            self.host.select_worn(None)
        else:
            self.draw()

    def retranslate(self):
        for who, key in (('character', 'btn.panel_character'), ('mercenary', 'btn.panel_mercenary')):
            self.btn_who[who].configure(text=tr(key))

    def items(self):
        """Objets affichés dans le panneau : portés et dans le sac (personnage), ou portés (mercenaire)."""
        ch = self.host.char
        if not ch:
            return []
        if self.mercenary():
            return list(ch['mercenary']['items'])
        return [it for it in ch['items'] if place(it) in ('equipped', 'inventory')]

    def find(self, old):
        """Objet du panneau au même endroit qu'un objet lu avant une relecture du personnage, ou None."""
        key = lambda it: (it['location'], it['equipped'] if it['location'] == 1 else (it['panel'], it['x'], it['y']), it['code'])
        return next((it for it in self.items() if key(it) == key(old)), None)

    def draw(self):
        """Dessine l'équipement et le sac du personnage de la fenêtre (rien si elle n'en a pas), ou l'équipement de son
        mercenaire (sans anneaux ni second jeu d'armes, sac masqué, exigences non évaluées : ses attributs ne sont pas
        dans le fichier)."""
        ch, c, data = self.host.char, self.canvas, self.host.data
        selected = self.host.selected
        has_merc = bool(ch and ch['mercenary'])
        self.btn_who['mercenary'].state(['!disabled' if has_merc else 'disabled'])
        if not has_merc and self.who.get() == 'mercenary':
            self.who.set('character')
        merc = self.mercenary()
        items = ch['items'] if ch else []
        if merc:
            self.bag.canvas.pack_forget()
            self.bag.items = []
        else:
            if not self.bag.canvas.winfo_manager():
                self.bag.canvas.pack(side='top', pady=(round(GAP * self.cell / CELL), 0))
            self.bag.draw(placed(items, 'inventory'), selected)
        worn_items = ch['mercenary']['items'] if merc else placed(items, 'equipped')
        by_slot = {it['equipped']: it for it in worn_items}
        key = (ch['path'], ch['weapon_switch']) if ch else None
        if ch is not None and key != self.shown_char:   # autre personnage ou jeu actif changé : onglet du jeu actif
            self.shown_char, self.weapon_set = key, 2 if ch['weapon_switch'] else 1
        sets = weapon_slots(0, 1) if merc else weapon_slots(ch['weapon_switch'] if ch else 0, self.weapon_set)
        slots = {n: r for n, r in self.slots.items() if not merc or n in MERC_SLOTS}
        self.worn = {n: by_slot[sets.get(n, n)] for n in slots if sets.get(n, n) in by_slot}
        req_char = None if merc else ch
        c.delete('all')
        # cadre de l'équipement : fond des cases d'une grille ; emplacements vides en creux
        c.create_rectangle(0, 0, int(c.cget('width')) - 1, int(c.cget('height')) - 1, fill=EMPTY, outline=GRID_LINE)
        for (n, k), (x0, y0, x1, y1) in ({} if merc else self.tabs).items():   # onglets des deux jeux d'armes
            on = k == self.weapon_set
            c.create_rectangle(x0, y0, x1, y1, fill=CELL_OK if on else BG, outline=GRID_LINE)
            c.create_text((x0 + x1) // 2, (y0 + y1) // 2, text='I' * k, fill=LABEL_DIM if on else GRID_LINE, font=(FONT, 8, 'bold'))
        for n, (x0, y0, x1, y1) in slots.items():
            it = self.worn.get(n)
            c.create_rectangle(x0, y0, x1, y1, fill=BG, outline=GRID_LINE)
            if it is None:
                continue
            sel = it is selected
            bg = CELL_KO if requirements_unmet(it, data, req_char) else CELL_OK
            fill = blend(SELECTION, bg, 0.12) if sel else bg
            c.create_rectangle(x0 + 1, y0 + 1, x1, y1, fill=fill, outline='', width=0)
            # image de la taille de l'objet (intérieur de ses cases, comme dans une grille), centrée dans l'intérieur
            # de l'emplacement (x0 + 1 à x1 - 1) : pile au centre si l'objet a la taille de l'emplacement
            w, h = self.bag.size(it)
            imgs = self.bag.icon(it, fill, (w * self.cell - 1, h * self.cell - 1))
            if imgs:
                ix = x0 + 1 + (x1 - x0 - 1 - imgs[1].width()) // 2
                iy = y0 + 1 + (y1 - y0 - 1 - imgs[1].height()) // 2
                for k in (1, 2, 3):
                    if imgs[k] is not None and k in LAYERS_SHOWN:
                        c.create_image(ix, iy, image=imgs[k], anchor='nw', tags=(f'calque{k}',))
            if sel:   # cadre de sélection par-dessus l'image (elle en cachait une partie sur les côtés) : 1 pixel partout
                c.create_rectangle(x0, y0, x1, y1, outline=item_color(it, data))

    def item_at(self, ev):
        """Objet porté sous la souris, ou None."""
        return next((self.worn.get(n) for n, (x0, y0, x1, y1) in self.slots.items()
                     if x0 <= ev.x < x1 and y0 <= ev.y < y1), None)

    def on_click(self, ev):
        if self.host.carry:   # objet en main : pas de dépôt sur un emplacement porté
            return 'break'
        for (_, k), (x0, y0, x1, y1) in self.tabs.items():   # onglet I / II : autre jeu d'armes affiché
            if x0 <= ev.x < x1 and y0 <= ev.y < y1 and not self.mercenary():
                self.weapon_set = k
                self.draw()
                return
        self.host.select_worn(self.item_at(ev))
