"""Chemins de l'application, définis une seule fois (dossier du programme, pas le dossier courant).

Un seul dossier pour tout ce qui appartient à l'utilisateur (HOME_DIR, décision du 08/10, option C) :
« MXL Item Collector » dans le dossier des sauvegardes du jeu (il voyage avec les personnages et les coffres) :
réglages (settings.json), bibliothèque (library.json : la collection contient de vrais objets), sauvegardes des
fichiers du jeu avant chaque écriture (backups/), traductions ajoutées (lang/). Seul le cache des données extraites du
jeu (DATA_DIR, ~25 Mo, recréable) est ailleurs : dossier du programme lancé depuis les sources, %LOCALAPPDATA%\\MXL Item
Collector pour l'exécutable Windows (build_exe.py, PyInstaller ; fichiers livrés dans RESOURCE_DIR).
Autres dossiers (tests) : MXL_SAVE_DIR (sauvegardes du jeu), MXL_HOME (dossier de l'utilisateur), MXL_USER_DIR (cache).
"""
import os
import sys

FROZEN = getattr(sys, 'frozen', False)   # exécutable construit par PyInstaller
APP_DIR = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
RESOURCE_DIR = getattr(sys, '_MEIPASS', APP_DIR)   # fichiers livrés avec le programme (lecture seule)
# dossier des sauvegardes du jeu
SAVE_DIR = os.environ.get('MXL_SAVE_DIR') or os.path.expandvars(r'%APPDATA%\MedianXL\save')
HOME_NAME = 'MXL Item Collector'
HOME_DIR = os.environ.get('MXL_HOME') or os.path.join(SAVE_DIR, HOME_NAME)   # tout ce qui appartient à l'utilisateur
SETTINGS_FILE = os.path.join(HOME_DIR, 'settings.json')   # réglages de l'utilisateur (settings.py)
LIBRARY_FILE = os.path.join(HOME_DIR, 'library.json')     # bibliothèque, collection (mxl_library)
BACKUP_DIR = os.path.join(HOME_DIR, 'backups')            # sauvegardes des fichiers du jeu (mxl_save.make_backup)
# cache des données extraites du jeu (mxl_install) : tables, animdata, icônes
USER_DIR = os.environ.get('MXL_USER_DIR') or (
    os.path.join(os.environ.get('LOCALAPPDATA') or APP_DIR, HOME_NAME) if FROZEN else APP_DIR)
DATA_DIR = os.path.join(USER_DIR, 'data')
ICONS_DIR = os.path.join(DATA_DIR, 'items')   # icônes des objets et slot de sertissage (PNG)
SKILL_ICONS_DIR = os.path.join(DATA_DIR, 'skills')   # icônes des compétences (PNG)
# traductions (i18n) : livrées, puis celles de l'utilisateur (un fichier de même nom remplace celui livré)
LANG_DIRS = list(dict.fromkeys([os.path.join(RESOURCE_DIR, 'lang'), os.path.join(HOME_DIR, 'lang')]))
# anciens emplacements (avant le 08/10), repris au lancement (mxl_home.migrate) : réglages à côté du programme
# (sources) ou dans %LOCALAPPDATA% (exécutable) ; sauvegardes à côté des fichiers du jeu
OLD_SETTINGS_FILE = os.path.join(USER_DIR, 'settings.json')
