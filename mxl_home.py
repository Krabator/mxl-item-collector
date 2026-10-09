"""Dossier unique de l'utilisateur (paths.HOME_DIR) : reprise des fichiers rangés ailleurs par les versions d'avant le
08/10, au lancement (migrate). Jamais de perte : un fichier n'est retiré de son ancien emplacement qu'une fois sa copie
écrite et relue à l'identique ; un fichier déjà présent dans le nouvel emplacement n'est jamais écrasé (l'ancien reste
alors en place).
"""
import glob
import os
import re
import shutil
from paths import APP_DIR, SAVE_DIR, SETTINGS_FILE, LIBRARY_FILE, BACKUP_DIR, OLD_SETTINGS_FILE

# sauvegarde d'un fichier du jeu faite par l'éditeur (mxl_save.make_backup) : <fichier>.bak-AAAAMMJJ-HHMMSS[-n]
BACKUP_NAME = re.compile(r'.+\.bak-\d{8}-\d{6}(-\d+)?$')


def _move(src, dst):
    """Déplace src vers dst (copie, relecture identique, puis suppression de src) ; rien si dst existe déjà ou si src
    est absent. Vrai si déplacé."""
    if not os.path.isfile(src) or os.path.exists(dst) or os.path.normcase(src) == os.path.normcase(dst):
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    with open(src, 'rb') as a, open(dst, 'rb') as b:
        if a.read() != b.read():
            os.remove(dst)
            return False
    os.remove(src)
    return True


def migrate():
    """Reprend dans HOME_DIR ce qui était rangé ailleurs : réglages (à côté du programme lancé depuis les sources, ou
    %LOCALAPPDATA% pour l'exécutable) et leur copie .bak, bibliothèque à côté du programme (avant le 27/09),
    sauvegardes des fichiers du jeu faites par l'éditeur (à côté de chaque fichier, dans SAVE_DIR) vers backups/.
    Les emplacements de test (MXL_SETTINGS, MXL_LIBRARY) ne sont pas concernés. Renvoie le nombre de fichiers repris."""
    moved = 0
    if not os.environ.get('MXL_SETTINGS'):
        for suffix in ('', '.bak'):
            moved += _move(OLD_SETTINGS_FILE + suffix, SETTINGS_FILE + suffix)
    if not os.environ.get('MXL_LIBRARY'):
        moved += _move(os.path.join(APP_DIR, 'library.json'), LIBRARY_FILE)
    if os.path.isdir(SAVE_DIR):
        for old in glob.glob(os.path.join(glob.escape(SAVE_DIR), '*.bak-*')):
            if BACKUP_NAME.fullmatch(os.path.basename(old)):
                moved += _move(old, os.path.join(BACKUP_DIR, os.path.basename(old)))
    return moved
