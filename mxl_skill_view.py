"""Compétences d'une infobulle affichée dans une zone de texte Tk : nom souligné en pointillé (de la couleur du texte)
et explication au survol, avec l'icône de la compétence à gauche (coffre et écran Library). Même mécanisme pour les
Mystic Orbs appliqués à l'objet (attach_orbs) : icône de l'orbe au-dessus, puis ses lignes (mxl_orbs.orb_tooltip).

Contenu : mxl_skills (compétences citées par l'objet, lignes de l'explication). Tk ne sait pas souligner en pointillé
dans une zone de texte : le pointillé est un petit canevas d'un pixel de haut posé sous le nom, replacé quand le texte
défile (place, appelé par la fenêtre dans sa commande de défilement).
"""
import os
import tkinter as tk
from PIL import Image, ImageTk
from mxl_gfx import skill_icon_file
from mxl_skills import skill_tooltip
from mxl_orbs import orb_tooltip, orb_icon
from mxl_theme import GAME_COLORS, TIP_BG, FONT
from paths import ICONS_DIR
from mxl_widgets import screen_area

POPUP_BORDER = '#6a6a6a'     # liseré de l'explication
POPUP_OFFSET = (18, 18)      # décalage de l'explication par rapport à la souris (px)
ORB_ICON_SCALE = 1.5          # icône d'un Mystic Orb dans son explication (comme la capture de Crystal of Tears)
DOT_STEP = 3                 # pointillé : un point tous les DOT_STEP pixels


class SkillHover:
    """Noms de compétences d'une infobulle : soulignés en pointillé, explication au survol."""

    def __init__(self, text, icons_dir):
        self.text, self.icons_dir = text, icons_dir
        self.items = []      # [{tag, start, end (marques), line (canevas du pointillé), skill, lo, hi}]
        self.popup = None
        self.images = {}     # fichier d'icône -> image Tk (référence gardée)
        self.data = None
        self.char = None

    # ---------- repérage ----------
    def clear(self, kind=None):
        """Retire les soulignements et l'explication (panneau vidé ou réécrit) ; kind : seulement ceux de ce genre
        ('skill' : compétences, réécrites après une édition ; 'orb' : Mystic Orbs)."""
        self.hide()
        for it in self.items:
            if kind is None or it['kind'] == kind:
                self.text.tag_delete(it['tag'])
                it['line'].destroy()
                for mark in (it['start'], it['end']):
                    self.text.mark_unset(mark)
        self.items = [it for it in self.items if kind is not None and it['kind'] != kind]

    def _add(self, item, start, end):
        """Soulignement et survol de item entre les positions start et end du texte."""
        t = self.text
        t.mark_set(item['start'], start)
        t.mark_set(item['end'], end)
        t.mark_gravity(item['start'], 'left')
        t.tag_add(item['tag'], item['start'], item['end'])
        for widget_bind in (lambda seq, f, tag=item['tag']: t.tag_bind(tag, seq, f), item['line'].bind):
            widget_bind('<Enter>', lambda e, item=item: self.show(item, e))
            widget_bind('<Leave>', lambda e: self.hide())
            widget_bind('<Motion>', lambda e: self.move(e))
        self.items.append(item)

    def attach_orbs(self, spans, data):
        """Noms des Mystic Orbs appliqués (sous l'infobulle) : spans = [(début, fin, ligne de mysticorbs.bin)] ;
        soulignés, explication de l'orbe au survol (mxl_orbs.orb_tooltip). Les compétences ne sont pas touchées."""
        self.clear('orb')
        self.data = data
        for start, end, k in spans:
            n = len(self.items)
            name = f'orb{n}_{k}'
            self._add(dict(kind='orb', orb=k, tag=name, start=name + 'a', end=name + 'b', width=0,
                           line=tk.Canvas(self.text, height=1, highlightthickness=0, bd=0)), start, end)
        self.text.after_idle(self.place)

    def attach(self, refs, data, char=None, heading=(), cast_only=()):
        """refs = mxl_skills.skill_refs(…) : chaque nom de compétence trouvé dans les lignes de l'infobulle (zone 'tip')
        est souligné et réagit au survol ; noms les plus longs d'abord, une occurrence par ligne. char : personnage de
        référence (niveau, classe et points investis : lignes chiffrées de l'explication), ou None. heading : lignes
        de titre de l'infobulle ([(couleur, texte)…], nom de l'objet, de son type, des pièces d'un set) : jamais
        soulignées (« Jerhyn's Tawiz », « Arrow Quiver » ne sont pas les compétences du même nom). cast_only : noms des
        compétences données seulement par une chance de lancer (mxl_skills.cast_only_skills) : explication sans coût
        en mana (jamais payé)."""
        self.clear('skill')
        self.data, self.char = data, char
        t = self.text
        names = sorted(refs, key=len, reverse=True)
        titles = {part for line in heading for part in ''.join(x for _, x in line).split('\n')}
        for n in range(1, int(t.index('end').split('.')[0])) if names else ():
            if 'tip' not in t.tag_names(f'{n}.0'):
                continue
            content, taken = t.get(f'{n}.0', f'{n}.end'), []
            if content in titles:
                continue
            for name in names:
                i = content.find(name)
                if i < 0 or any(a < i + len(name) and i < b for a, b in taken):
                    continue
                taken.append((i, i + len(name)))
                k = len(self.items)
                item = dict(kind='skill', tag=f'skill{k}', start=f'skill{k}a', end=f'skill{k}b', skill=refs[name][0],
                            mana=name not in cast_only,
                            lo=refs[name][1], hi=refs[name][2], width=0,
                            line=tk.Canvas(t, height=1, highlightthickness=0, bd=0))
                self._add(item, f'{n}.{i}', f'{n}.{i + len(name)}')
        t.after_idle(self.place)

    def place(self):
        """Pose (ou replace après un défilement) le pointillé sous chaque nom visible ; nom hors de la vue : masqué."""
        t = self.text
        for it in self.items:
            a, b = t.bbox(it['start']), t.bbox(f"{it['end']} - 1 chars")
            if not a or not b or a[1] != b[1]:
                it['line'].place_forget()
                continue
            x, width = a[0], b[0] + b[2] - a[0]
            color = next((t.tag_cget(g, 'foreground') for g in reversed(t.tag_names(it['start']))
                          if g.startswith('g') and t.tag_cget(g, 'foreground')), GAME_COLORS['3'])
            # fond : celui de l'infobulle (zone 'tip'), sinon celui du panneau (orbes, sous l'infobulle)
            bg = next((t.tag_cget(g, 'background') for g in reversed(t.tag_names(it['start']))
                       if t.tag_cget(g, 'background')), TIP_BG if 'tip' in t.tag_names(it['start']) else t.cget('bg'))
            if (width, color, bg) != it.get('drawn'):
                c = it['line']
                c.configure(bg=bg)
                c.delete('all')
                for px in range(0, width, DOT_STEP):
                    c.create_line(px, 0, px + 1, 0, fill=color)
                it['drawn'] = (width, color, bg)
            # les éléments posés dans la zone de texte sont décalés de sa marge intérieure (padx, pady), pas bbox
            it['line'].place(x=x - int(t.cget('padx')), y=a[1] + a[3] - 2 - int(t.cget('pady')), width=width, height=1)

    # ---------- explication ----------
    def icon(self, skill):
        """Icône de la compétence (data/skills), ou None si elle n'est pas extraite."""
        name = skill_icon_file(skill, self.data)
        path = os.path.join(self.icons_dir, f'{name}.png') if name else None
        if not path or not os.path.exists(path):
            return None
        if name not in self.images:
            scale = self.text.winfo_fpixels('1i') / 96
            img = Image.open(path)
            self.images[name] = ImageTk.PhotoImage(img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS))
        return self.images[name]

    def orb_image(self, k):
        """Icône d'un Mystic Orb (data/items), à l'échelle de l'écran, ou None si elle n'est pas extraite."""
        name = orb_icon(k, self.data)
        path = os.path.join(ICONS_DIR, f'{name}.png')
        if not os.path.exists(path):
            return None
        key = 'item:' + name
        if key not in self.images:
            scale = ORB_ICON_SCALE * self.text.winfo_fpixels('1i') / 96   # icône du jeu (28 px) agrandie
            img = Image.open(path)
            self.images[key] = ImageTk.PhotoImage(img.resize((round(img.width * scale), round(img.height * scale)),
                                                             Image.LANCZOS))
        return self.images[key]

    def show_orb(self, item, event):
        """Explication d'un Mystic Orb près de la souris, comme son infobulle en jeu : icône centrée en haut (sans
        cadre, choix retenu), puis ses lignes centrées (mxl_orbs.orb_tooltip)."""
        self.popup = win = tk.Toplevel(self.text)
        win.overrideredirect(True)
        win.attributes('-topmost', True)
        box = tk.Frame(win, bg=TIP_BG, highlightbackground=POPUP_BORDER, highlightthickness=1)
        box.pack()
        icon = self.orb_image(item['orb'])
        if icon is not None:
            tk.Label(box, image=icon, bg=TIP_BG, bd=0, highlightthickness=0).pack(side='top', pady=(10, 4))   # sans cadre
        lines = tk.Frame(box, bg=TIP_BG)
        lines.pack(side='top', padx=14, pady=(2, 8))
        for line in orb_tooltip(item['orb'], self.data):
            row = tk.Frame(lines, bg=TIP_BG)
            row.pack()
            for color, text in line:
                tk.Label(row, text=text, fg=GAME_COLORS[color], bg=TIP_BG, font=(FONT, 11), bd=0, pady=0,
                         padx=0).pack(side='left')
        self.move(event)

    def show(self, item, event):
        """Explication de la compétence près de la souris : icône à gauche, texte centré comme l'infobulle du jeu
        (Mystic Orb : show_orb)."""
        self.hide()
        if item['kind'] == 'orb':
            self.show_orb(item, event)
            return
        self.popup = win = tk.Toplevel(self.text)
        win.overrideredirect(True)
        win.attributes('-topmost', True)
        box = tk.Frame(win, bg=TIP_BG, highlightbackground=POPUP_BORDER, highlightthickness=1)
        box.pack()
        icon = self.icon(item['skill'])
        if icon is not None:
            # icône centrée verticalement sur la hauteur de l'explication
            tk.Label(box, image=icon, bg=TIP_BG, bd=0).pack(side='left', anchor='center', padx=(8, 0), pady=8)
        lines = tk.Frame(box, bg=TIP_BG)
        lines.pack(side='left', padx=10, pady=6)
        lo, hi = item['lo'], item['hi']
        if lo is None:   # compétence modifiée par l'objet sans niveau donné : celui du personnage, au moins 1
            from mxl_char_stats import character_stats
            lo = hi = max(1, character_stats(self.char, self.data).skill_level(item['skill'])) if self.char else 1
        for line in skill_tooltip(item['skill'], lo, hi, self.data, self.char, segments=True,
                                  mana=item.get('mana', True)):
            row = tk.Frame(lines, bg=TIP_BG)   # une ligne peut changer de couleur (codes du jeu) : morceaux côte à côte
            row.pack()
            for color, text in line:
                tk.Label(row, text=text, fg=GAME_COLORS[color], bg=TIP_BG, font=(FONT, 11), bd=0, pady=0,
                         padx=0).pack(side='left')
        self.move(event)

    def move(self, event):
        """Explication placée près de la souris, sans sortir de l'écran où se trouve la souris (plusieurs écrans :
        mxl_widgets.screen_area ; avant le 08/10, l'écran principal seul : sur un écran à gauche de lui, l'explication
        partait sur l'écran principal)."""
        win = self.popup
        if win is None:
            return
        win.update_idletasks()
        left, top, right, bottom = screen_area(win, event.x_root, event.y_root)
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        x, y = event.x_root + POPUP_OFFSET[0], event.y_root + POPUP_OFFSET[1]
        x = min(x, right - w - 4)
        if y + h > bottom - 4:
            y = event.y_root - POPUP_OFFSET[1] - h
        win.geometry(f'+{max(left, x)}+{max(top, y)}')

    def hide(self):
        if self.popup is not None:
            self.popup.destroy()
            self.popup = None
