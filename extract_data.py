"""Reconstruit le dossier data/ (tables, animations, icônes) depuis l'installation de Median XL (mxl_install).

Usage : python extract_data.py [DOSSIER_DU_JEU]
Sans argument : dossier du jeu des réglages (game_dir, choisi dans l'interface). L'ancien data/ est gardé en
data.old/ ; en cas d'erreur, data/ n'est pas modifié. L'interface propose la même reconstruction à chaque nouvelle
version du mod.
"""
import sys
import settings
from i18n import tr
from mxl_install import rebuild_data, is_game_dir, game_version
from paths import DATA_DIR


if __name__ == '__main__':
    game_dir = sys.argv[1] if len(sys.argv) > 1 else settings.get('game_dir')
    if not is_game_dir(game_dir):
        sys.exit(tr('cli.no_game_dir', path=game_dir or '-'))
    print(tr('cli.rebuilding', version=game_version(game_dir) or '?', path=game_dir))
    ok, missing = rebuild_data(game_dir, DATA_DIR)
    print(tr('cli.extracted', n=ok) + (tr('cli.extract_missing', n=len(missing)) if missing else ''))
