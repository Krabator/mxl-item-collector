"""Petits composants d'interface communs aux fenêtres de l'éditeur."""
import ttkbootstrap as ttk


def screen_area(win, px, py):
    """(gauche, haut, droite, bas) de la zone de travail de l'écran qui contient le point (px, py) : Windows
    (MonitorFromPoint, GetMonitorInfoW ; écrans à gauche de l'écran principal : coordonnées négatives) ; ailleurs, ou
    en cas d'échec, l'écran principal de Tk."""
    try:
        import ctypes
        from ctypes import wintypes

        class MONITORINFO(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT), ('rcWork', wintypes.RECT),
                        ('dwFlags', wintypes.DWORD)]
        user32 = ctypes.windll.user32
        user32.MonitorFromPoint.restype = wintypes.HMONITOR
        user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        monitor = user32.MonitorFromPoint(wintypes.POINT(px, py), 2)   # MONITOR_DEFAULTTONEAREST
        info = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
        if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            r = info.rcWork
            return r.left, r.top, r.right, r.bottom
    except (AttributeError, OSError):
        pass
    return 0, 0, win.winfo_screenwidth(), win.winfo_screenheight()


def one_line(text):
    """Texte ramené à une ligne : retours à la ligne remplacés par « / » (lignes vides retirées)."""
    return ' / '.join(part.strip() for part in str(text).split('\n') if part.strip())


class OneLineLabel(ttk.Label):
    """Étiquette qui n'affiche jamais qu'une ligne (one_line) : barre du bas, dont la hauteur ne doit pas changer
    (un texte sur plusieurs lignes agrandissait la fenêtre, ✅ Arcane Crystal au survol, 08/10)."""

    def __init__(self, parent, **kw):
        if 'text' in kw:
            kw['text'] = one_line(kw['text'])
        super().__init__(parent, **kw)

    def configure(self, cnf=None, **kw):
        if 'text' in kw:
            kw['text'] = one_line(kw['text'])
        return super().configure(cnf, **kw)

    config = configure


class AutoScrollbar(ttk.Scrollbar):
    """Ascenseur affiché seulement quand il y a quelque chose à faire défiler. Sa place reste réservée (cadre de sa
    largeur) : le contenu voisin ne bouge pas quand il apparaît ou disparaît. S'emploie comme ttk.Scrollbar
    (command, set, pack)."""

    def __init__(self, parent, **kw):
        self.holder = ttk.Frame(parent)
        super().__init__(self.holder, **kw)
        self.holder.configure(width=self.winfo_reqwidth())
        self.holder.pack_propagate(False)

    def pack(self, **kw):
        self.holder.pack(**kw)

    def set(self, first, last):
        super().set(first, last)
        if float(first) <= 0 and float(last) >= 1:
            self.pack_forget()
        elif not self.winfo_manager():
            ttk.Scrollbar.pack(self, fill='y', expand=True)
