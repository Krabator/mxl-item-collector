"""Bibliothèque vue par la fenêtre principale (mxl_gui.App.library_ui) : découvertes, bouton « Library », écran
(mxl_library_gui.LibraryWindow), transfert (mxl_library_transfer.TransferDialog), mises à jour après une modification
de la collection.
"""
import os
from i18n import tr
from mxl_save import read_items
from mxl_library_gui import LibraryWindow
from mxl_library_transfer import TransferDialog


class LibraryUI:
    """Bibliothèque vue par l'interface : découvertes à l'ouverture d'un coffre, bouton « Library » (avec les
    nouveautés), écran (window : LibraryWindow ouverte ou None), transfert, mises à jour après une modification de la
    collection. Utilise de l'application (app) : library, catalog, data, coffre ouvert (path, items, load, needs_backup)
    et barre du bas (status) ; le bouton lui est confié par attach_button."""

    def __init__(self, app):
        self.app = app
        self.window = None   # écran « Library » ouvert (LibraryWindow) ou None
        self.new = []        # découvertes pas encore vues dans l'écran (affichées sur le bouton)
        self.button = None

    def attach_button(self, button):
        """Bouton « Library » de la fenêtre principale."""
        self.button = button
        self.show_button()

    def record_found(self):
        """Objets du catalogue du coffre ouvert enregistrés comme trouvés ; nouveautés dans la barre du bas. Une
        erreur d'écriture est signalée sans bloquer l'éditeur."""
        app = self.app
        if app.library.readonly:
            return
        try:
            new = app.library.record_found(app.items, app.data, os.path.basename(app.path)) if app.path else []
            if app.char:   # objets du personnage (portés, sac, cube, ceinture) et du mercenaire : trouvés eux aussi
                merc = app.char['mercenary']['items'] if app.char['mercenary'] else []
                new += app.library.record_found(app.char['items'] + merc, app.data, os.path.basename(app.char['path']))
            # coffres du personnage sélectionné non affichés (son coffre, le coffre partagé) : leurs objets sont trouvés
            # eux aussi ; les autres personnages ne sont pas lus
            for path in app.side_stashes():
                try:
                    items = read_items(path, app.data)
                except Exception:   # illisible (en cours d'écriture par le jeu) : nouvel essai à la relecture suivante
                    continue
                new += app.library.record_found(items, app.data, os.path.basename(path))
        except OSError as e:
            app.status.configure(text=tr('library.error', error=e))
            return
        if new and self.window:
            self.window.refresh()
        elif new:   # écran fermé : nombre de nouveautés sur le bouton jusqu'à son ouverture
            self.new += new
            self.show_button()
        if new:
            names = ', '.join(app.catalog[k]['name'] for k in new[:3]) + (' …' if len(new) > 3 else '')
            app.status.configure(text=tr('library.new', n=len(new), names=names,
                                         found=sum(1 for k in app.catalog if k in app.library.found),
                                         total=len(app.catalog)))

    def open_transfer(self, only=None, parent=None, source=None):
        """Transfert vers la collection (conteneurs du personnage, ou only = offsets d'objets de source) : aperçu puis
        validation (TransferDialog) ; parent = fenêtre de départ (écran Library, sinon fenêtre du coffre), qui garde le
        focus ensuite ; source : (fichier, conteneur) des objets, par défaut ceux du personnage (App.transfer_sources)."""
        if (source and source[0]) or self.app.transfer_sources():
            TransferDialog(self.app, only, parent, source)

    def after_change(self, baks, message):
        """Après un transfert, une sortie ou une restauration : fichiers écrits ({fichier: sauvegarde ou None})
        notés sauvegardés, coffre et personnage relus, écrans mis à jour, message et sauvegardes."""
        app = self.app
        for path, bak in baks.items():
            app.backup_made(path, bak)
        app.refresh_files()
        if self.window:
            self.window.refresh()
        made = [os.path.basename(b) for b in baks.values() if b]
        app.status.configure(text=message + (tr('status.backup', file=', '.join(made)) if made else ''))

    def open(self):
        """Bouton « Library » : ouvre l'écran de la bibliothèque (ou le ramène devant s'il est déjà ouvert)."""
        if self.window:
            self.window.win.lift()
            self.window.win.focus_force()
        else:
            self.window = LibraryWindow(self.app)
        self.new = []
        self.show_button()

    def close(self):
        """Écran fermé (LibraryWindow.close)."""
        self.window = None

    def show_button(self):
        """Bouton « Library », avec le nombre de découvertes pas encore vues."""
        if self.button is None:
            return
        n = len(self.new)
        self.button.configure(text=tr('btn.library_new', n=n) if n else tr('btn.library'),
                              bootstyle='warning' if n else 'warning-outline')
