"""Grille d'objets affichée dans un canevas Tk : cases, icônes du jeu (3 calques), objet sélectionné, surbrillance
de dépôt pendant un glisser-déposer. Forme de la grille : un conteneur (mxl_containers.Container).

Le canevas garde la taille du premier conteneur ; un conteneur plus large (set_box) est affiché avec des cases plus
petites, pour que la fenêtre ne change pas de taille ; ses colonnes occupent alors toute la largeur du canevas (bord
droit aligné sur celui du coffre), certaines ayant un pixel de plus que les autres (self.xs). La grille ne connaît ni les fichiers ni les pages : la fenêtre lui donne les objets à dessiner (draw) et branche ses
propres réactions sur le canevas (self.canvas). host : objet portant data (tables du jeu) et char (personnage de
référence, pour le fond rouge des exigences non remplies).
"""
import bisect
import tkinter as tk
from tkinter import font as tkfont
import ttkbootstrap as ttk
from PIL import Image, ImageTk

from mxl_gfx import icon_layers, icon_name
from mxl_gui_detail import item_color, LAYERS_SHOWN
from mxl_tooltip import requirements_unmet
from mxl_theme import BG, GRID_LINE, EMPTY, CELL_OK, CELL_KO, SELECTION, DROP_OK, DROP_KO, FONT, blend
from paths import ICONS_DIR

CELL = 40             # taille d'une case en pixels (à 96 dpi)


def short_name(it):
    n = it['name']
    return n[:-4] if n.endswith(' (1)') else n   # le « (1) » des noms MXL n'aide pas dans la grille


def fit_lines(text, font, width, max_lines):
    """Découpe text en lignes tenant dans width pixels (dernière ligne tronquée avec « … »)."""
    lines, cur = [], ''
    for w in text.split():
        t = f'{cur} {w}'.strip()
        if font.measure(t) <= width or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] += '…'
    for i, l in enumerate(lines):
        while font.measure(l) > width and len(l) > 1:
            l = l[:-2] + '…'
        lines[i] = l
    return lines


class ItemGrid:
    def __init__(self, parent, host, box, cell=CELL):
        """cell : taille d'une case en pixels à 96 dpi."""
        self.host, self.box = host, box
        self.base_cell = self.cell = round(cell * parent.winfo_fpixels('1i') / 96)   # case d'origine, case affichée
        self.font = tkfont.Font(family=FONT, size=7)
        self.icons = {}   # (contenu de l'objet, fond, taille) -> calques PhotoImage (références gardées pour Tk)
        self.items = []   # objets dessinés (ceux de la page affichée)
        # fond = celui de la fenêtre : la place laissée libre par une grille plus petite ne se voit pas
        self.canvas = tk.Canvas(parent, width=box.cols * self.cell + 1, height=box.rows * self.cell + 1,
                                bg=ttk.Style().lookup('TFrame', 'background') or BG,
                                highlightthickness=0)
        self.set_box(box)

    def set_box(self, box):
        """Change de conteneur : cases réduites si sa grille est plus large que le canevas."""
        self.box = box
        width = int(self.canvas.cget('width')) - 1
        self.cell = min(self.base_cell, width // box.cols)
        # bord gauche de chaque colonne (et bord droit de la dernière) : la largeur du canevas répartie entre les
        # colonnes quand les cases sont réduites, sinon des cases de self.cell pixels
        span = width if self.cell < self.base_cell else box.cols * self.cell
        self.xs = [round(i * span / box.cols) for i in range(box.cols + 1)]

    def left(self, col):
        """Abscisse du bord gauche de la colonne col (prolongée hors de la grille, pour un dépôt qui déborde)."""
        return self.xs[col] if 0 <= col <= self.box.cols else col * self.cell

    def size(self, it):
        return self.host.data.base(it['code']).size

    def draw(self, items, selected=None):
        """Dessine les cases et les objets items (positions x, y en cases) ; selected : objet encadré."""
        c, s, data = self.canvas, self.cell, self.host.data
        self.items = list(items)
        c.delete('all')
        for x in range(self.box.cols):
            for y in range(self.box.rows):
                c.create_rectangle(self.xs[x], y * s, self.xs[x + 1], (y + 1) * s, fill=EMPTY, outline=GRID_LINE)
        for it in self.items:
            w, h = self.size(it)
            x0, y0 = self.left(it['x']), it['y'] * s
            x1, y1 = self.left(it['x'] + w), y0 + h * s
            col = item_color(it, data)
            sel = it is selected
            bg = CELL_KO if requirements_unmet(it, data, self.host.char) else CELL_OK
            fill = blend(SELECTION, bg, 0.12) if sel else bg
            # intérieur des cases de l'objet : entre les traits de la grille (pixels x0 et x1 : trait d'un pixel,
            # remplissage de x0 à x1 - 1), soit x0 + 1 à x1 - 1 ; fond et image l'occupent exactement (centrés)
            c.create_rectangle(x0 + 1, y0 + 1, x1, y1, fill=fill, outline='')
            imgs = self.icon(it, fill, (x1 - x0 - 1, y1 - y0 - 1))
            if imgs:
                for k in (1, 2, 3):   # un élément de canevas par calque, dans l'ordre (tags calque1…calque3)
                    if imgs[k] is not None and k in LAYERS_SHOWN:
                        c.create_image(x0 + 1, y0 + 1, image=imgs[k], anchor='nw', tags=(f'calque{k}',))
            else:   # icône absente : nom de l'objet (dossier data/items/ non extrait)
                lines = fit_lines(short_name(it), self.font, w * s - 6, max(1, (h * s - 4) // 12))
                c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text='\n'.join(lines), fill=col,
                              font=self.font, justify='center', width=w * s - 4)
            if sel:   # cadre de sélection par-dessus l'image, sur le pourtour de l'objet (traits de la grille)
                c.create_rectangle(x0, y0, x1, y1, outline=col)

    def icon(self, it, bg, size=None):
        """Les 3 calques de l'image de l'objet (mxl_gfx.icon_layers, icônes extraites par extract_data.py) mis à la
        taille size (largeur, hauteur en pixels ; par défaut : intérieur de ses cases dans la grille, traits exclus) :
        {1: PhotoImage, 2: PhotoImage ou None, 3: PhotoImage ou None}, ou None."""
        data = self.host.data
        if size is None:
            w, h = self.size(it)
            size = (w * self.cell - 1, h * self.cell - 1)
        key = (it['code'], icon_name(it, data), it.get('image'), it.get('ethereal'), it.get('sockets'),
               tuple(icon_name(s, data) for s in it.get('socketed', [])), bg, size)
        if key not in self.icons:
            layers = icon_layers(it, data, bg, ICONS_DIR)
            if layers is not None:
                size = (max(1, size[0]), max(1, size[1]))
                layers = {k: ImageTk.PhotoImage(im.resize(size, Image.LANCZOS)) if im is not None else None
                          for k, im in layers.items()}
            self.icons[key] = layers
        return self.icons[key]

    def cell_at(self, ev):
        """Case (colonne, ligne) sous la souris (peut être hors de la grille : voir inside)."""
        col = bisect.bisect_right(self.xs, ev.x) - 1 if 0 <= ev.x < self.xs[-1] else ev.x // self.cell
        return col, ev.y // self.cell

    def inside(self, ev):
        """Vrai si la souris est sur la grille."""
        return 0 <= ev.x < self.xs[-1] and 0 <= ev.y < self.box.rows * self.cell

    def item_at(self, ev):
        """Objet dessiné sous la souris, ou None."""
        cx, cy = self.cell_at(ev)
        for it in self.items:
            w, h = self.size(it)
            if it['x'] <= cx < it['x'] + w and it['y'] <= cy < it['y'] + h:
                return it
        return None

    def show_drop(self, it, x, y, ok):
        """Surbrillance légère des cases où l'objet it serait déposé en (x, y) (rouge si ok est faux), limitée à la
        grille."""
        c, s = self.canvas, self.cell
        self.clear_drop()
        w, h = self.size(it)
        x0, x1 = self.left(max(x, 0)), self.left(max(min(x + w, self.box.cols), 0))
        y0, y1 = max(y, 0) * s, min(y + h, self.box.rows) * s
        if x1 > x0 and y1 > y0:
            rgba, outline = DROP_OK if ok else DROP_KO
            img = ImageTk.PhotoImage(Image.new('RGBA', (x1 - x0, y1 - y0), rgba))
            self._drop_img = img   # référence gardée pour Tk
            c.create_image(x0, y0, image=img, anchor='nw', tags=('depot',))
            c.create_rectangle(x0, y0, x1, y1, outline=outline, width=1, tags=('depot',))

    def clear_drop(self):
        self.canvas.delete('depot')


class FloatingIcon:
    """Image d'un objet qui suit la souris (glisser-déposer, objet « en main ») : petite fenêtre sans bord, au-dessus
    de tout, que la souris traverse (Windows : WS_EX_TRANSPARENT) pour que la grille dessous reçoive les mouvements et
    les clics (10/10). offset : point de l'image placé sous la souris (pixels depuis son coin haut gauche)."""
    ALPHA = 0.85

    def __init__(self, root):
        self.root, self.win, self.offset = root, None, (0, 0)
        # calques affichés : références propres (la réserve de la grille est vidée à chaque changement de coffre, ce
        # qui effaçait l'image de l'objet en main, 10/10)
        self.images = None

    def show(self, grid, it, x_root, y_root, offset):
        """Image de it (calques de la grille grid, fond d'une case) avec offset sous la souris."""
        self.hide()
        w, h = grid.size(it)
        pw, ph = w * grid.cell - 1, h * grid.cell - 1
        self.win = win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes('-topmost', True)
        win.attributes('-alpha', self.ALPHA)
        c = tk.Canvas(win, width=pw, height=ph, bg=CELL_OK, highlightthickness=0, bd=0)
        c.pack()
        imgs = self.images = grid.icon(it, CELL_OK, (pw, ph))
        if imgs:
            for k in (1, 2, 3):
                if imgs[k] is not None and k in LAYERS_SHOWN:
                    c.create_image(0, 0, image=imgs[k], anchor='nw')
        else:
            c.create_text(pw / 2, ph / 2, text=short_name(it), fill=item_color(it, grid.host.data), font=grid.font,
                          width=pw - 4, justify='center')
        self.offset = offset
        self.move(x_root, y_root)
        win.update_idletasks()
        self._click_through(win)

    @staticmethod
    def _click_through(win):
        """La souris traverse la fenêtre (Windows) ; ailleurs, rien (l'image reste sous la souris)."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
            style = user32.GetWindowLongW(hwnd, -20)   # GWL_EXSTYLE
            user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20)   # WS_EX_LAYERED | WS_EX_TRANSPARENT
        except (AttributeError, OSError):
            pass

    def move(self, x_root, y_root):
        if self.win is not None:
            self.win.geometry(f'+{x_root - self.offset[0]}+{y_root - self.offset[1]}')

    def hide(self):
        if self.win is not None:
            self.win.destroy()
            self.win = None
        self.images = None
