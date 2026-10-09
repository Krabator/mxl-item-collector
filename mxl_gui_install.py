"""Installation du jeu vue par l'interface (GameInstall, utilisé par mxl_gui.App) : dossier de Median XL (réglage
game_dir), version des données, contrôle de data/ au lancement et sur demande, réparation fichier par fichier ou
reconstruction complète avec fenêtre de progression (mxl_install).
"""
import json, os
import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
import settings
from i18n import tr
from mxl_install import is_game_dir, data_state, fingerprint, installed, rebuild_data, repair_data, check_data


class GameInstall:
    """Dossier du jeu et données extraites (data/). Ne connaît de l'application que sa fenêtre root (dialogues), le
    dossier data_dir, l'étiquette de version (label, attach_label) et on_rebuilt : appelé quand data/ a été reconstruit
    ou réparé à la demande (bouton « Game folder… »), pour relire les tables."""

    def __init__(self, root, data_dir, on_rebuilt=None):
        self.root, self.data_dir, self.on_rebuilt = root, data_dir, on_rebuilt
        self.game_dir = settings.get('game_dir')   # dossier d'installation de Median XL
        self.label = None

    def start(self):
        """Au lancement : dossier du jeu demandé s'il n'est pas connu, puis contrôle rapide de data/ (reconstruction
        ou réparation proposée si besoin)."""
        if not is_game_dir(self.game_dir):
            self.game_dir = self.ask_game_dir(first=True)
        self.check_data(startup=True)

    def attach_label(self, label):
        """Étiquette de la fenêtre qui affiche la version des données."""
        self.label = label
        self.show_game()

    def show_game(self):
        """Version de Median XL dont les données sont extraites (data/install.json)."""
        fp = installed(self.data_dir)
        if self.label is not None:
            self.label.configure(text=tr('label.game', version=(fp or {}).get('version') or '?'))

    def ask_game_dir(self, first=False):
        """Choix du dossier d'installation de Median XL (réglage game_dir) ; renvoie le dossier, ou None si annulé."""
        if first:
            messagebox.showinfo(tr('dlg.game_dir.title'), tr('dlg.game_dir.first'))
        while True:
            p = filedialog.askdirectory(title=tr('dlg.game_dir.title'), mustexist=True,
                                        initialdir=self.game_dir if is_game_dir(self.game_dir) else None)
            if not p:
                return None
            p = os.path.normpath(p)
            if is_game_dir(p):
                settings.put('game_dir', p)
                return p
            messagebox.showerror(tr('dlg.game_dir.title'), tr('err.not_game_dir', path=p))

    def change_game_dir(self):
        """Bouton « Game folder… » : choix du dossier, puis reconstruction de data/ si besoin (ou sur demande)."""
        p = self.ask_game_dir()
        if not p:
            return
        self.game_dir = p
        if self.check_data(startup=False):   # data/ reconstruit : tables, icônes et coffre relus par l'application
            self.show_game()
            if self.on_rebuilt:
                self.on_rebuilt()

    def check_data(self, startup):
        """data/ correspond-il à l'installation du jeu ? Sinon (absent, sans empreinte, version différente), propose de
        le reconstruire ; à jour : reconstruction proposée seulement sur demande (pas au lancement). Un refus est
        retenu pour cette installation (pas de nouvelle question au lancement avant un changement du jeu).
        Fichiers absents ou abîmés d'une installation inchangée : réparation de ces seuls fichiers (repair).
        Renvoie True si data/ a été reconstruit ou réparé."""
        if not is_game_dir(self.game_dir):
            return False
        # au lancement : contrôle rapide (présence et taille des fichiers) ; sur demande : contenu complet
        state = data_state(self.data_dir, self.game_dir, full=not startup)
        fp = fingerprint(self.game_dir)
        key = json.dumps(fp, sort_keys=True)
        # refus retenu seulement pour une version du jeu (unknown / outdated) ; données abîmées : question à chaque fois
        if state == 'ok' and startup or state in ('unknown', 'outdated') and startup and settings.get('data_declined') == key:
            return False
        bad = check_data(self.data_dir, full=not startup) if state == 'damaged' else []
        n_files = len((installed(self.data_dir) or {}).get('manifest') or {})
        if not messagebox.askyesno(tr('dlg.rebuild.title'), tr(
                ('ask.repair' if state == 'damaged' else 'ask.rebuild.' + state), version=fp['version'] or '?',
                path=self.game_dir, files=n_files,
                n=len(bad), examples=', '.join(bad[:5]) + (' …' if len(bad) > 5 else ''))):
            if state in ('unknown', 'outdated'):
                settings.put('data_declined', key)
            return False
        return self.repair(bad) if state == 'damaged' else self.rebuild()

    def progress_window(self):
        """Fenêtre de progression (reconstruction / réparation de data/) : (fenêtre, progress(étape, fait, total))."""
        win = tk.Toplevel(self.root)
        win.title(tr('dlg.rebuild.title'))
        win.resizable(False, False)
        win.transient(self.root)
        label = ttk.Label(win, text=tr('rebuild.start'), width=48)
        label.pack(padx=16, pady=(14, 6))
        bar = ttk.Progressbar(win, length=380, maximum=1.0)
        bar.pack(padx=16, pady=(0, 14))
        win.grab_set()
        win.update()

        def progress(step, done, total):
            label.configure(text=tr('rebuild.' + step, done=done, total=total))
            bar['value'] = done / total
            win.update()
        return win, progress

    def repair(self, files):
        """Réparation des seuls fichiers absents ou abîmés (mxl_install.repair_data), vérifiés un par un ; si elle
        est impossible, reconstruction complète. True si data/ est réparé."""
        win, progress = self.progress_window()
        try:
            n = repair_data(self.game_dir, self.data_dir, files, progress)
        except Exception as e:   # fichiers sains intacts ; passage à la reconstruction complète
            win.destroy()
            messagebox.showinfo(tr('dlg.rebuild.title'), tr('repair.failed', error=f'{type(e).__name__}: {e}'))
            return self.rebuild()
        win.destroy()
        messagebox.showinfo(tr('dlg.rebuild.title'), tr('repair.done', n=n))
        return True

    def rebuild(self):
        """Reconstruction de data/ (mxl_install.rebuild_data) avec une fenêtre de progression. True si réussie."""
        win, progress = self.progress_window()
        try:
            ok, missing = rebuild_data(self.game_dir, self.data_dir, progress)
        except Exception as e:   # data/ intact (mxl_install) : l'erreur est affichée
            win.destroy()
            messagebox.showerror(tr('dlg.rebuild.title'), tr('err.rebuild', error=f'{type(e).__name__}: {e}'))
            return False
        win.destroy()
        messagebox.showinfo(tr('dlg.rebuild.title'), tr('rebuild.done', version=(installed(self.data_dir) or {}).get('version') or '?',
                                                        n=ok, missing=len(missing)))
        return True
