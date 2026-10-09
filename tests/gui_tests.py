"""Tests de l'interface (lancés par run_tests.py, un processus par test) sur une copie du coffre de référence.

Usage : python tests/gui_tests.py smoke|drag|library|transfer|shared|xfer|cube|inventory|bag|nocube — code de sortie 0 si
le test passe, sinon 1 et le détail. Module mxl_editor présent (et MXL_NO_EDITOR absent) : ses tests d'interface
(mxl_editor/tests/gui_editor_tests.py : slider, quantity, options, copie de transfer) sont chargés ici, avec les mêmes
outils (app, root, check…) ; sans lui, les parties d'édition vérifient seulement que rien n'est écrit.
- xfer : glisser-déposer du coffre du personnage vers le coffre partagé (survol du bouton de coffre), annulation ;
- shared : choix du personnage, coffre partagé affiché pour ce personnage, retour au coffre du personnage, coffre
  absent (personnage sans coffre, coffre partagé pas encore créé), choix retenus ; surveillance : coffre modifié
  sur le disque relu, coffre apparu ouvert, aucune relecture sans changement ;
- smoke : ouverture (coffre retenu comme dernier coffre ouvert), rendu de toutes les pages et du détail de chaque objet ;
  droits refusés par « false » (curseurs grisés, aucune écriture) ;
- drag : glisser-déposer dans la même page, vers une page vide par survol de deux onglets, dépôt refusé
  (chevauchement) ; une seule sauvegarde .bak ;
- library : écran « Library » (découverte à l'ouverture d'un coffre, 2 022 entrées, recherche, filtre, tri,
  traduction) ;
- transfer : transfert vers la collection (aperçu, option C, destruction, restauration), consultation et sortie ;
"""
import sys, os, glob, shutil, tempfile, ctypes
# dossier de l'utilisateur des tests (sauvegardes .bak) : temporaire et vierge à chaque test
os.environ['MXL_HOME'] = tempfile.mkdtemp(prefix='mxl_gui_tests_home_')
# réglages des tests dans un fichier temporaire : ceux de l'utilisateur (langue, dernier coffre) ne changent pas
os.environ['MXL_SETTINGS'] = os.path.join(tempfile.gettempdir(), 'mxl_tests_settings.json')
# bibliothèque des tests dans un fichier temporaire, vierge à chaque test
os.environ['MXL_LIBRARY'] = os.path.join(tempfile.gettempdir(), 'mxl_tests_library.json')
# bibliothèque et réglages vierges à chaque test (priorités par défaut), copies comprises (.bak, .broken, .tmp,
# verrou) : sinon la copie d'un test précédent serait relue
for _f in glob.glob(os.environ['MXL_LIBRARY'] + '*') + glob.glob(os.environ['MXL_SETTINGS'] + '*'):
    os.remove(_f)
# droits (module mxl_editor présent : actifs sans ligne ; sans lui, toujours inactifs) : édition pour inventory, bag
# et les tests du module, copie sur demande (transfer) ; smoke : droits refusés par « false » (curseurs grisés)
with open(os.environ['MXL_SETTINGS'], 'w', encoding='utf-8') as f:
    f.write('{"edition_enabled": false, "duplication_enabled": false}' if sys.argv[1:2] == ['smoke']
            else '{"edition_enabled": true, "duplication_enabled": false}')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from paths import BACKUP_DIR
bak_glob = lambda path: os.path.join(BACKUP_DIR, glob.escape(os.path.basename(path)) + '.bak-*')   # sauvegardes d'un fichier
import mxl_game   # jeu considéré fermé pendant les tests (écritures permises même si Median XL est ouvert)
mxl_game.running_processes = lambda: []
sys.argv = sys.argv[:2]
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass
import i18n
i18n.set_language('en', save=False)
# langue de test (écran traduit au changement de langue) : copie de l'anglais, un texte changé, dans un dossier temporaire
import json as _json
_LANG = tempfile.mkdtemp(prefix='mxl_tests_lang_')
_texts = _json.load(open(os.path.join(os.path.dirname(HERE), 'lang', 'en.json'), encoding='utf-8'))
_json.dump(dict(_texts, _language='Test', **{'library.col.name': 'Nom-test'}),
           open(os.path.join(_LANG, 'xx.json'), 'w', encoding='utf-8'), ensure_ascii=False)
i18n.LANG_DIRS = i18n.LANG_DIRS + [_LANG]
import mxl_gui
import ttkbootstrap as ttk
from tkinter import messagebox
from mxl_edit import edit_groups, priority_profile   # edit_groups : tests du module (gui_editor_tests.py)
from mxl_ext import editor
EDITOR = editor() is not None   # module mxl_editor présent et pris en compte (sinon : base seule)

TEST = sys.argv[1] if len(sys.argv) > 1 else 'smoke'
TMP = tempfile.mkdtemp(prefix='mxl_gui_tests_')
P = os.path.join(TMP, 'Nekratall.stash')
for ext in ('.stash', '.d2s'):
    shutil.copy2(os.path.join(HERE, 'fixtures', 'Nekratall' + ext), os.path.join(TMP, 'Nekratall' + ext))
errors, failures = [], []
messagebox.showerror = lambda title, msg, **k: errors.append(msg)   # parent=… accepté (fenêtres secondaires)
# pas de fenêtre bloquante : choix du dossier du jeu annulé, reconstruction de data/ refusée (data/ jamais modifié)
from tkinter import filedialog
messagebox.showinfo = lambda *a, **k: None
messagebox.askyesno = lambda *a, **k: False
filedialog.askdirectory = lambda *a, **k: None
root = ttk.Window(themename='darkly')
app = mxl_gui.App(root, P)
root.geometry('1760x840')   # panneau du personnage, coffre et détail en entier


def check(cond, msg):
    if not cond:
        failures.append(msg)


def finish():
    root.destroy()
    shutil.rmtree(TMP, ignore_errors=True)
    shutil.rmtree(_LANG, ignore_errors=True)
    if failures:
        print('\n'.join(failures))
        sys.exit(1)
    print('OK')
    sys.exit(0)


class Ev:
    """Événement souris simulé en (x, y) du canevas."""
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.x_root, self.y_root = app.grid.canvas.winfo_rootx() + x, app.grid.canvas.winfo_rooty() + y


def cell(cx, cy):
    return Ev(cx * app.grid.cell + app.grid.cell // 2, cy * app.grid.cell + app.grid.cell // 2)


def tab(i):
    """Événement souris sur l'onglet i."""
    nb = app.notebook
    for x in range(0, nb.winfo_width(), 3):
        try:
            if nb.index(f'@{x},10') == i:
                e = Ev(0, 0)
                e.x_root, e.y_root = nb.winfo_rootx() + x + 8, nb.winfo_rooty() + 10
                e.x, e.y = e.x_root - app.grid.canvas.winfo_rootx(), e.y_root - app.grid.canvas.winfo_rooty()
                return e
        except Exception:
            pass
    raise AssertionError(f'onglet {i} introuvable')


def shark():
    return next(i for i in app.items if i['code'] == '160 ')


def free_spot(page, w, h, avoid=None):
    occ = set()
    for o in app.items:
        if o['page'] == page and o is not avoid:
            ow, oh = app.size(o)
            occ |= {(o['x'] + a, o['y'] + b) for a in range(ow) for b in range(oh)}
    for y in range(mxl_gui.STASH.rows - h + 1):
        for x in range(mxl_gui.STASH.cols - w + 1):
            if all((x + a, y + b) not in occ for a in range(w) for b in range(h)):
                return x, y


# ---------------------------------------------------------------- smoke
def show_equipment():
    """Affiche le panneau du personnage (replié à l'ouverture)."""
    if not app.show_char.get():
        app.btn_char.invoke()
    root.update()


def smoke():
    check(not app.show_char.get() and not app.char_view.frame.winfo_ismapped(), "panneau du personnage affiché à l'ouverture")
    for p in range(mxl_gui.STASH.pages):
        app.notebook.select(p)
        app.draw_grid()
    for it in app.items:
        app.set_detail(it)
    root.update()
    check(len(app.items) > 0, 'aucun objet lu')
    # détails techniques (masqués par défaut, réglage du code) : affichés sans erreur pour tous les objets
    # (objets sertis, runewords, gemmes : bonus selon le type du porteur)
    import mxl_gui_detail
    mxl_gui_detail.SHOW_TECHNICAL_DETAILS = True
    try:
        for it in app.items:
            app.set_detail(it)
            text = app.detail.get('1.0', 'end')
            check(i18n.tr('detail.tech') in text and f"code {it['code'].strip()}" in text, f"détails techniques : {it['name']}")
    finally:
        mxl_gui_detail.SHOW_TECHNICAL_DETAILS = False
    app.set_detail(None); root.update()
    # installation du jeu (GameInstall) : version des données affichée ; après une reconstruction de data/ (bouton
    # « Game folder… »), tables relues et coffre réaffiché
    check('2.14' in app.game_label.cget('text'), f"version des données : {app.game_label.cget('text')}")
    from mxl_theme import LABEL_DIM   # libellés secondaires éclaircis (pas le gris #444444 du thème, trop sombre)
    check(root.style.lookup('secondary.TLabel', 'foreground') == LABEL_DIM, 'couleur des libellés secondaires')
    n_items, old_data = len(app.items), app.data
    app.install.on_rebuilt(); root.update()
    check(app.data is not old_data and len(app.items) == n_items, 'relecture des tables après une reconstruction')
    # boutons et onglets : pas de focus au clic (procédure de clic de ttk), donc pas de cadre en pointillés
    for w_ in (app.btn_views['shared'], app.btn_library, app.notebook):
        root.tk.call('ttk::clickToFocus', w_)
        root.update()
        check(str(root.tk.call('focus')) != str(w_), f'focus pris au clic : {w_}')
    # droits refusés par « false » (respecté, jamais retiré ni réécrit) : curseurs grisés, relâchement sans écriture
    import settings as st
    check(st.load().get('edition_enabled') is False and st.load().get('duplication_enabled') is False
          and not app.editing_setting and not app.duplication_setting, f"droits : {st.load()}")
    it = next(i for i in app.items if i['code'] == '7@5 ')
    app.set_detail(it); root.update()
    check(app.panel.edit_scales and all(s.instate(['disabled']) for s in app.panel.edit_scales), 'curseurs actifs alors que l\'édition est désactivée')
    check(not hasattr(app, 'detail_image'), "image de l'objet dans le panneau du coffre")
    before = open(P, 'rb').read()
    check((app.panel.editor is not None) == EDITOR, f'partie active de la section : {app.panel.editor}')
    if EDITOR:   # relâchement d'un curseur (module) : rien d'écrit sans le droit
        g = app.panel.edit_groups_shown[0]
        f = g['fields'][0]
        app.panel.editor.edit_commit(it, g, f, Var(f['lo'] if f['value'] != f['lo'] else f['hi']))
    check(open(P, 'rb').read() == before, 'fichier modifié alors que l\'édition est désactivée')
    import settings
    check(settings.get('last_stash') == os.path.abspath(P), 'dernier coffre ouvert non retenu dans les réglages')
    # barre du bas toujours sur une ligne : un nom du jeu sur plusieurs lignes n'agrandit pas la fenêtre
    from mxl_gui_detail import full_name
    root.update()
    height = root.winfo_height()
    name = full_name({'code': 'qum ', 'name': app.data.base('qum ').name, 'quality': 'normal'}, app.data)
    app.status.configure(text=name + '\nsecond line\nthird line'); root.update()
    check(name == 'Arcane Crystal' and app.status.cget('text') == 'Arcane Crystal / second line / third line'
          and root.winfo_height() == height, f"barre : {app.status.cget('text')!r}, hauteur {height} -> {root.winfo_height()}")
    # explication au survol (compétence, Mystic Orb) : près de la souris, sur l'écran où elle se trouve (plusieurs
    # écrans : avant le 08/10, ramenée sur l'écran principal)
    from mxl_widgets import screen_area
    px, py = root.winfo_pointerxy()
    # centre d'un écran à gauche de l'écran principal (bureau virtuel qui commence en x négatif), s'il y en a un
    if root.winfo_vrootx() < 0:
        left, top, right, bottom = screen_area(root, root.winfo_vrootx() + 10, root.winfo_screenheight() // 2)
        if left < 0:
            px, py = (left + right) // 2, (top + bottom) // 2
    hover = app.panel.hover
    hover.data = app.data
    hover.show(dict(kind='orb', orb=3), type('E', (), {'x_root': px, 'y_root': py})()); root.update()
    pop = hover.popup
    pw, ph, gx, gy = pop.winfo_width(), pop.winfo_height(), pop.winfo_rootx(), pop.winfo_rooty()
    check(abs(gx - px) <= pw + 40 and abs(gy - py) <= ph + 40, f'explication : {gx},{gy} {pw}x{ph}, souris {px},{py}')
    hover.hide()
    check(not errors, f'erreurs : {errors}')
    finish()


# ---------------------------------------------------------------- drag
state = {}


def drag1():
    sh = shark()
    w, h = app.size(sh)
    app.notebook.select(sh['page'])
    root.update()
    fx, fy = free_spot(sh['page'], w, h, avoid=sh)
    app.on_click(cell(sh['x'], sh['y'])); app.on_drag(cell(fx, fy)); app.on_release(cell(fx, fy)); root.update()
    sh2 = shark()
    check((sh2['page'], sh2['x'], sh2['y']) == (sh['page'], fx, fy), f"même page : Shark en {sh2['page'], sh2['x'], sh2['y']}")
    state['target'] = next(p for p in range(mxl_gui.STASH.pages) if not any(i['page'] == p for i in app.items))
    state['via'] = next(p for p in range(mxl_gui.STASH.pages) if p not in (sh2['page'], state['target']))
    app.on_click(cell(sh2['x'], sh2['y'])); app.on_drag(tab(state['via']))
    root.after(mxl_gui.TAB_HOVER_MS + 200, drag2)


def drag2():
    check(app.page() == state['via'], f"survol de l'onglet {state['via'] + 1} : page {app.page() + 1} affichée")
    app.on_drag(tab(state['target']))
    root.after(mxl_gui.TAB_HOVER_MS + 200, drag3)


def drag3():
    check(app.page() == state['target'], f"survol de l'onglet {state['target'] + 1} : page {app.page() + 1} affichée")
    app.on_drag(cell(3, 3)); app.on_release(cell(3, 3)); root.update()
    sh = shark()
    check((sh['page'], sh['x'], sh['y']) == (state['target'], 3, 3), f"entre pages : Shark en {sh['page'], sh['x'], sh['y']}")
    check([x['code'] for x in sh['socketed']] == [x['code'] for x in state.setdefault('sockets', sh['socketed'])],
          'objets sertis perdus')
    state['rune'] = next(i for i in app.items if i['code'].startswith('r0') and i['page'] == 0)
    app.on_click(cell(sh['x'], sh['y'])); app.on_drag(tab(0))
    root.after(mxl_gui.TAB_HOVER_MS + 200, drag4)


def drag4():
    r = state['rune']
    app.on_drag(cell(r['x'], r['y'])); app.on_release(cell(r['x'], r['y'])); root.update()
    sh = shark()
    check((sh['page'], sh['x'], sh['y']) == (state['target'], 3, 3), 'dépôt sur une rune : le Shark a bougé')
    check(not errors, f'erreurs : {errors}')
    baks = glob.glob(bak_glob(P))
    check(len(baks) == 1, f'sauvegardes : {baks} (une seule attendue)')
    finish()


class Var:
    """Variable de curseur simulée (valeur fixe)."""
    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


# ---------------------------------------------------------------- library
def library():
    s2 = os.path.join(TMP, 'stash2')   # 2e coffre (Jared's Fragmentor), lu seulement
    os.makedirs(s2)
    for ext in ('.stash', '.d2s'):
        shutil.copy2(os.path.join(HERE, 'fixtures', 'stash2', 'Nekratall' + ext), os.path.join(s2, 'Nekratall' + ext))
    app.load(os.path.join(s2, 'Nekratall.stash'))   # message lu avant que la souris ne change la barre du bas
    check("Jared's Fragmentor" in app.status.cget('text'), f"découverte non annoncée : {app.status.cget('text')}")
    root.update()
    check('1' in app.btn_library.cget('text'), f"nouveauté absente du bouton : {app.btn_library.cget('text')}")
    app.library_ui.open(); root.update()
    check(app.btn_library.cget('text') == 'Library', f"bouton après ouverture : {app.btn_library.cget('text')}")
    w = app.library_ui.window
    # texte de recherche préparé par étapes après l'ouverture (fenêtre affichée sans l'attendre), puis complet
    check(w.index_job is not None, "texte de recherche déjà complet à l'ouverture (préparation bloquante ?)")
    check(wait(lambda: w.index_job is None, 10) and len(w.index['items']) == len(app.catalog), 'texte de recherche incomplet')
    check(len(w.item_iids()) == len(app.catalog) == 1918, f'entrées affichées : {len(w.item_iids())}')
    for t in '1234':   # filtre Type : uniques d'un tiers (objet de base « (t) »)
        w.kind_box.set(f'Tier {t} Uniques'); w.kind_box.event_generate('<<ComboboxSelected>>'); root.update()
        want = sorted(k for k, e in app.catalog.items() if e['family'] == 'tiered' and e['base'].endswith(f'({t})'))
        check(want and sorted(w.item_iids()) == want, f'filtre Tier {t} Uniques : {len(w.item_iids())} / {len(want)}')
    w.kind_box.set('All'); w.kind_box.event_generate('<<ComboboxSelected>>'); root.update()
    # regroupement par set (coché par défaut) : une ligne par set après les uniques, repliée, progression sur les
    # pièces trouvées ; recherche du nom du set = set déplié avec toutes ses pièces ; ligne du set = pièces et bonus
    import mxl_library_gui as lg
    groups = [i for i in w.tree.get_children() if i.startswith(lg.SET_ROW)]
    check(w.group_sets.get() and len(groups) == len({w.set_ids[k] for k in w.set_ids}), f'lignes de set : {len(groups)}')
    check(not any(w.tree.item(g, 'open') for g in groups), 'lignes de set dépliées par défaut')
    check(not any(i.startswith('set:') for i in w.tree.get_children()), 'objet de set hors de son set')
    w.search.set('pantheon'); root.update()   # set trouvé par son nom : sa ligne, repliée, avec ses 4 pièces
    top = list(w.tree.get_children())
    check(len(top) == 1 and not w.tree.item(top[0], 'open') and len(w.tree.get_children(top[0])) == 4,
          f'recherche du set Pantheon : {top} {[w.tree.get_children(t_) for t_ in top]}')
    check(w.tree.item(top[0])['values'][1] == '0 / 4 found · 0 stored', f"progression : {w.tree.item(top[0])['values']}")
    w.tree.selection_set(top[0]); root.update()
    text = w.detail.get('1.0', 'end')
    check('Pantheon' in text and 'Earth' in text and 'Set Bonus with 2 or more set items:' in text
          and '+50% Attack Speed' in text and 'Set Bonus with complete set:' in text and '+200 to Dexterity' in text,
          f'détail du set : {text[:400]}')
    w.group_sets.set(False); w.refresh(); root.update()   # sans regroupement : pièces à plat
    check(sorted(w.tree.get_children()) == sorted(w.tree.get_children()) and all(not i.startswith(lg.SET_ROW) for i in w.tree.get_children())
          and len(w.tree.get_children()) == 4, f'sans regroupement : {w.tree.get_children()}')
    w.group_sets.set(True); root.update()
    # pièce trouvée par son propre texte : seule, hors de son set (« Earth » : nom de la pièce de Pantheon)
    w.search.set('"earth"'); root.update()
    earth = next(k for k in w.set_ids if app.catalog[k]['name'] == 'Earth')
    check(earth in w.tree.get_children() and not w.tree.parent(earth), f'pièce trouvée dans son set : {w.tree.parent(earth)}')
    w.search.set(''); root.update()
    w.search.set('fragmentor'); root.update()
    rows = [w.tree.item(i) for i in w.tree.get_children()]
    check([r['values'][1] for r in rows] == [f'Claymore ({k})' for k in (1, 2, 3, 4)], f'recherche : {rows}')
    check(rows[0]['tags'] == ['found'] and all(r['tags'] == ['missing'] for r in rows[1:]), 'tier 1 trouvé, tiers 2 à 4 manquants')
    w.tree.selection_set('unique:376'); root.update()   # entrée non trouvée : infobulle du catalogue
    text = w.detail.get('1.0', 'end')
    # dans le contexte du personnage sélectionné (Nekratall, Nécromancien) : pas de « One-Hand Damage » (Barbare
    # seulement), bonus de Force calculé
    check('Claymore (2)' in text and '(27 - 30) to (37 - 44)' in text and 'One-Hand' not in text
          and 'Strength Damage Bonus: 7%' in text and 'Not found yet' in text, f'infobulle du catalogue : {text[:200]}')
    # chance de lancer seule (Spike Nova) : explication sans coût en mana (jamais payé en jeu)
    nova = [i for i in w.panel.hover.items if w.detail.get(i['start'], i['end']) == 'Spike Nova']
    check(len(nova) == 1 and nova[0]['mana'] is False, f'Spike Nova : {nova}')
    check(w.detail_image.find_withtag('calque1'), "image de l'objet de base absente (entrée du catalogue)")
    # entrée non rangée : image estompée (fond noir, 50 %) = un seul élément, calque 1 seulement
    check(len(w.detail_image.find_withtag('img')) == 1 and [k[2] for k in w.catalog_images] == [1.0],
          f'image du catalogue (vue normale, sans opacité) : {list(w.catalog_images)}')
    # vue Ethereal sans exemplaire rangé : infobulle éthérée du catalogue, image à 50 %
    w.btn_views['ethereal'].invoke(); root.update()
    text = w.detail.get('1.0', 'end')
    check('Ethereal' in text and '(34 - 38) to (43 - 51)' in text and 'Required Strength: 59' in text,
          f'infobulle éthérée du catalogue : {text[:300]}')
    check(sorted(k[2] for k in w.catalog_images) == [0.5, 1.0], f'image éthérée à 50 % : {list(w.catalog_images)}')
    w.btn_views['normal'].invoke(); root.update()
    # apparences possibles d'une entrée non rangée : joyau 6, bague 5, amulette 3, relique 6 ; icône propre : 1.
    # Bascule Normal / Ethereal affichée seulement si les deux
    # variantes existent en jeu : arme (Jared's Fragmentor) oui ; joyau, bague, amulette, relique, toujours éthéré non
    w.search.set(''); root.update()
    counts = {}
    eth_state = {}
    for key in ('unique:153', 'unique:172', 'unique:119', 'unique:1067', 'unique:193', 'unique:1653',
                'unique:376'):
        w.tree.see(key); w.tree.selection_set(key); root.update()
        counts[key] = len(w.detail_image.find_withtag('img'))
        eth_state[key] = bool(w.views.winfo_ismapped())
        if key == 'unique:153':   # grille complète (joyau) : dans la largeur de la colonne de l'image
            x0, y0, x1, y1 = w.detail_image.bbox('img')
            width = x1 - x0
    check(counts == {'unique:153': 6, 'unique:172': 5, 'unique:119': 3, 'unique:1067': 6, 'unique:193': 1,
                     'unique:1653': 1, 'unique:376': 1}, f'apparences possibles : {counts}')
    check(eth_state['unique:376'] and not any(v for k, v in eth_state.items() if k != 'unique:376'),
          f'bascule Normal / Ethereal affichée : {eth_state}')
    check(width <= int(w.detail_image.cget('width')), f'grille des apparences plus large que la colonne : {width}')
    w.search.set('fragmentor'); w.tree.selection_set('unique:376'); root.update()
    # image centrée verticalement sur l'infobulle (zone 'tip'), infobulle de même largeur que dans le coffre
    t, cv = w.detail, w.detail_image
    r = t.tag_ranges('tip')
    y0, y1 = t.bbox(r[0])[1], t.dlineinfo(t.index(f'{r[-1]} - 1 lines'))
    tip_mid = t.winfo_rooty() + (y0 + y1[1] + y1[3]) / 2
    x0, iy0, x1, iy1 = cv.bbox('img')
    img_mid = cv.winfo_rooty() + (iy0 + iy1) / 2
    check(abs(img_mid - tip_mid) <= 3, f"image non centrée sur l'infobulle : {img_mid} / {tip_mid}")
    check(cv.winfo_rootx() + cv.winfo_width() <= t.winfo_rootx(), "image sur la largeur de l'infobulle")
    check(t.winfo_width() == app.detail.winfo_width(), f'largeurs : collection {t.winfo_width()}, coffre {app.detail.winfo_width()}')
    # pas de clignotement : aucune image dans le canevas quand le panneau s'affiche (update_idletasks), elle n'est
    # dessinée qu'ensuite, déjà centrée
    seen, idle = [], t.update_idletasks
    t.update_idletasks = lambda: (seen.append(bool(cv.find_withtag('img'))), idle())
    w.tree.selection_set('unique:377'); root.update()
    del t.update_idletasks
    check(seen == [False] and cv.find_withtag('img'), f"image affichée avant d'être centrée : {seen}")
    w.search.set(''); w.state_box.current(1); w.refresh(); root.update()
    check(list(w.tree.get_children()) == ['unique:375'], f'filtre trouvés : {w.tree.get_children()}')
    w.state_box.current(0); w.sort_by('level_req'); w.sort_by('level_req'); root.update()
    first = w.tree.item(w.tree.get_children()[0])['values']
    check(int(first[3]) >= 100, f'tri par niveau requis décroissant : {first}')
    app.library_ui.open()   # déjà ouvert : même fenêtre
    check(app.library_ui.window is w, 'deuxième fenêtre ouverte')
    app.lang_combo.current([c for c, _ in app.languages].index('xx')); app.change_language(); root.update()
    check(app.library_ui.window and app.library_ui.window.tree.heading('name')['text'].startswith('Nom-test'), 'écran non traduit')
    # recherche dans le texte complet : ligne « Magic Find » surlignée dans le panneau de l'entrée choisie
    w = app.library_ui.window
    w.search.set('magic find'); root.update()
    first = w.item_iids()[0]
    w.tree.selection_set(first); root.update()
    hit = w.detail.tag_ranges('hit')
    check(hit and 'magic find' in w.detail.get(hit[0], hit[1]).lower(), f'ligne trouvée non surlignée : {first}')
    # surlignage du 1er caractère de la ligne au dernier, pas depuis la marge de centrage (caractère invisible en tête)
    line = str(hit[0]).split('.')[0]
    check(str(hit[0]).endswith('.1') and w.detail.get(f'{line}.0') == '​', f'début du surlignage : {hit[0]}')
    w.search.set(''); root.update()
    check(not w.detail.tag_ranges('hit'), 'surlignage resté sans recherche')
    # compétences de l'infobulle : nom souligné en pointillé, explication au survol (nom, description, niveau donné)
    ada = next(k for k, e in app.catalog.items() if e['name'] == 'Auto Da Fe')
    w.tree.see(ada); w.tree.selection_set(ada); root.update(); root.update_idletasks(); root.update()
    hv = w.panel.hover
    check([(i['skill'], i['lo'], i['hi']) for i in hv.items] == [(470, 1, 2), (523, 3, 4)], f'compétences : {hv.items}')
    check([w.detail.get(i['start'], i['end']) for i in hv.items] == ['Ignis Fatuus', 'Flamefront'], 'noms soulignés')
    check(all(i['line'].winfo_ismapped() and i['line'].winfo_width() > 40 for i in hv.items), 'pointillés absents')
    ev = Ev(0, 0); ev.x_root, ev.y_root = w.detail.winfo_rootx() + 50, w.detail.winfo_rooty() + 50
    hv.show(hv.items[1], ev); root.update()
    # une ligne = un cadre de morceaux de couleur (étiquettes côte à côte)
    shown = [''.join(p.cget('text') for p in row.winfo_children())
             for f_ in hv.popup.winfo_children()[0].winfo_children() for row in f_.winfo_children()
             if row.winfo_class() == 'Frame']
    check(shown[:2] == ['Flamefront', 'spell - casts a wave of exploding firebolts in front of you']
          and shown[3:] == ['Current Skill Level: 3 to 4', 'Firebolts: 3',   # calculée pour le personnage
                              'Fire Damage: 10-13 to 12-16', 'Mana Cost: 8'], f'explication : {shown}')
    # icône à gauche, centrée verticalement sur la hauteur de l'explication
    box = hv.popup.winfo_children()[0]
    icon = next((c for c in box.winfo_children() if c.winfo_class() == 'Label'), None)
    check(icon is not None, "icône absente de l'explication")
    if icon is not None:
        middle = icon.winfo_y() + icon.winfo_height() / 2
        check(abs(middle - box.winfo_height() / 2) <= 2, f'icône non centrée : {middle} / {box.winfo_height() / 2}')
    hv.hide()
    # compétence modifiée sans niveau donné (stat cachée 383 + texte d'effet) : soulignée, explication au niveau 1
    vision = next(k for k, e in app.catalog.items() if e['name'] == 'Vision of the Furies')
    w.tree.see(vision); w.tree.selection_set(vision); root.update(); root.update_idletasks(); root.update()
    fire = [i for i in hv.items if w.detail.get(i['start'], i['end']) == 'Fire Elementals']
    check(len(fire) == 1 and fire[0]['skill'] == 1042 and fire[0]['lo'] is None, f'Fire Elementals : {hv.items}')
    if fire:
        hv.show(fire[0], ev); root.update()
        shown = [''.join(p.cget('text') for p in row.winfo_children())
                 for f_ in hv.popup.winfo_children()[0].winfo_children() for row in f_.winfo_children()
                 if row.winfo_class() == 'Frame']
        check('Current Skill Level: 1' in shown, f'explication sans niveau : {shown}')
        hv.hide()
    # titre de l'objet homonyme d'une compétence qu'il donne : pas souligné
    tawiz = next(k for k, e in app.catalog.items() if e['name'] == "Jerhyn's Tawiz")
    w.tree.see(tawiz); w.tree.selection_set(tawiz); root.update(); root.update_idletasks(); root.update()
    check(not hv.items, f"titre Jerhyn's Tawiz souligné : {[w.detail.get(i['start'], i['end']) for i in hv.items]}")
    w.tree.selection_set(w.item_iids()[0]); root.update()
    check(hv.popup is None and all(i['skill'] != 523 for i in hv.items), 'explication ou soulignements restés après un changement')
    check(not errors, f'erreurs : {errors}')
    # niveau de zone minimum sous l'infobulle : entrée non rangée, puis objet du coffre
    w.search.set(''); root.update()
    w.tree.see('unique:378'); w.tree.selection_set('unique:378'); root.update()   # entrée non rangée : sous l'infobulle
    check('Drops from area level 77+' in w.detail.get('1.0', 'end'), 'niveau de zone (entrée du catalogue)')
    w.tree.see('unique:1401'); w.tree.selection_set('unique:1401'); root.update()   # unique sacré : part sur sa base
    check('Share among uniques of this base: 0.3% (area level 130+)' in w.detail.get('1.0', 'end'), "part de Tyrael's Might")
    jared = next(i for i in app.items if i['code'] == '108 ')   # coffre : sous l'infobulle de l'objet
    app.selected = jared; app.set_detail(jared); root.update()
    check('Drops from area level 10 to 50' in app.detail.get('1.0', 'end'), 'plage de chute dans le coffre')
    finish()


# ---------------------------------------------------------------- transfer
def transfer():
    """Transfert vers la collection : 3 exemplaires de Jared's Fragmentor (ED 57 du 2e coffre + 60 et 41 fabriqués),
    option C sur les moins bons (41 détruit, 57 gardé), validation, écran à jour, restauration du détruit."""
    from mxl_save import parse_stash, blob_item, edit_stash, free_spot, item_blob, read_file
    from common import set_raw_stat
    from mxl_library_transfer import TransferDialog
    s2 = os.path.join(TMP, 'stash2')
    os.makedirs(s2)
    p2 = os.path.join(s2, 'Nekratall.stash')
    for ext in ('.stash', '.d2s'):
        shutil.copy2(os.path.join(HERE, 'fixtures', 'stash2', 'Nekratall' + ext), os.path.join(s2, 'Nekratall' + ext))
    d = app.data
    c = next(i for i in parse_stash(p2, d) if i['code'] == '108 ')
    blob = item_blob(read_file(p2), c)

    def variant(v):
        b = bytearray(blob)
        set_raw_stat(b, blob_item(blob, d), 17, v, d)
        return bytes(b)
    items = parse_stash(p2, d)
    a1 = free_spot(items, blob_item(blob, d), d)
    a2 = free_spot(items + [dict(code='108 ', name='x', page=a1[0], x=a1[1], y=a1[2])], blob_item(blob, d), d)
    edit_stash(p2, d, insert=[(*a1, variant(60)), (*a2, variant(41))], backup=False)
    app.load(p2); app.library_ui.open(); root.update()
    confirms = []
    messagebox.askyesno = lambda t, m, **k: confirms.append(m) or True
    ed = lambda it: next(s['value'] for s in it['stats'] if s['id'] == 17)
    d2s = os.path.join(s2, 'Nekratall.d2s')   # sources : son coffre, son sac, son cube (cube Horadrim dans le sac)
    check(app.transfer_sources() == [(p2, None), (d2s, 'inventory'), (d2s, 'cube')], f'sources : {app.transfer_sources()}')
    check(app.library_ui.window.btn_transfer.cget('text') == 'Transfer from character…', 'libellé du bouton')
    dlg = TransferDialog(app, parent=app.library_ui.window.win)   # lancé depuis l'écran Library
    check({dlg.tree.set(k, 'source') for k in dlg.tree.get_children()} == {'Stash'}, 'colonne Source')
    names = [dlg.tree.set(k, 'name') for k in dlg.tree.get_children()]   # supérieurs du coffre : objet de base, sockets
    check(any('socket(s)' in n_ for n_ in names), f'supérieurs absents du plan : {names}')
    root.update()   # options : libellés entiers, boutons de chaque choix dans la même colonne
    cells = {(int(w.grid_info()['row']), int(w.grid_info()['column'])): w for w in dlg.option_grid.winfo_children()}
    check(all(w.winfo_width() >= w.winfo_reqwidth() for w in cells.values()), 'libellé ou bouton coupé')
    check(cells[(0, 1)].cget('text') == 'Keep in place', f"1er choix : {cells[(0, 1)].cget('text')}")
    check([(a['kind'], ed(a['item'])) for a in dlg.plan if a['item']['code'] == '108 '] == [('store', 60), ('worse', 57), ('worse', 41)],
          f'plan : {dlg.plan}')
    dlg.options['worse'].set('choose'); dlg.refresh(); root.update()
    k41 = next(k for k, a in enumerate(dlg.plan) if a['kind'] == 'worse' and ed(a['item']) == 41)
    bbox = dlg.tree.bbox(str(k41))

    class Ev:
        y = bbox[1] + 2
    dlg.toggle(Ev()); root.update()   # double-clic sur la ligne du 41 : « détruire »
    check(dlg.destroyed == 1, f'objets à détruire : {dlg.destroyed}')
    dlg.validate(); root.update()
    focus = root.focus_get()   # après validation : focus rendu à l'écran Library, pas à la fenêtre du coffre
    check(focus is not None and focus.winfo_toplevel() is app.library_ui.window.win,
          f"focus après le transfert : {focus.winfo_toplevel() if focus else None}")
    check(len(confirms) == 1, f'confirmations : {confirms}')
    check(sorted(ed(i) for i in app.items if i['code'] == '108 ') == [57], 'coffre après transfert')
    check(ed(app.library.stored_item('unique:375', d)) == 60 and len(app.library.journal['items']) == 1, 'collection / journal')
    # onglet Storage : supérieurs stockés par le transfert (coffre de test), tableau, panneau de détail, sortie
    w = app.library_ui.window
    stored_sup = sorted(app.library.storage)
    check(stored_sup, 'aucun supérieur stocké par le transfert')
    w.btn_modes['storage'].invoke(); root.update()
    check(w.stor_box.winfo_ismapped() and not w.coll_box.winfo_ismapped() and not w.progress_box.winfo_ismapped(),
          'onglet Storage non affiché')
    check(sorted(w.stree.get_children()) == stored_sup, f'tableau Storage : {w.stree.get_children()}')
    from mxl_library import base_tier, storage_parts
    tier_of = lambda sl: base_tier(app.data.base(storage_parts(sl)[0].ljust(4)).name)

    def type_filter(label):
        w.stor_tier_box.set(label); w.stor_tier_box.event_generate('<<ComboboxSelected>>'); root.update()
        return sorted(w.stree.get_children())
    for t in ('1', '2', 'sacred'):
        want = sorted(sl for sl in stored_sup if tier_of(sl) == t)
        check(type_filter(i18n.tr('library.tier.' + t)) == want, f'filtre Type {t} : {w.stree.get_children()}')
    check(type_filter(i18n.tr('library.all')) == stored_sup, 'filtre Type : tous')
    slot = stored_sup[0]
    w.stree.selection_set(slot); root.update()
    check('Stored on' in w.detail.get('1.0', 'end') and w.detail_image.find_withtag('img')
          and str(w.btn_take.cget('state')) == 'normal', 'panneau de détail du Storage')
    n_items = len(app.items)
    w.take_out(); root.update()
    check(slot not in app.library.storage and len(app.items) == n_items + 1 and not w.stree.exists(slot),
          'sortie depuis le Storage')
    w.btn_modes['collection'].invoke(); root.update()
    check(w.coll_box.winfo_ismapped() and w.progress_box.winfo_ismapped() and not w.stor_box.winfo_ismapped(),
          "retour à l'onglet Collection")
    w = app.library_ui.window
    w.search.set('fragmentor'); root.update()
    check(w.tree.item('unique:375')['tags'] == ['stored'], 'entrée non marquée rangée')
    w.restore(); root.update()
    check(sorted(ed(i) for i in app.items if i['code'] == '108 ') == [41, 57] and not app.library.journal['items'], 'restauration')
    w.tree.selection_set('unique:375'); root.update()   # consultation : même panneau que le coffre
    check('Drops from area level 10 to 50' in w.detail.get('1.0', 'end'), 'plage de chute sous l\'infobulle (exemplaire rangé)')
    text = w.detail.get('1.0', 'end')
    cd = w.panel
    check("Jared's Fragmentor" in text and '+60%' in text, f'infobulle rangée : {text[:200]}')
    check(w.detail_image.find_withtag('calque1'), "image de l'exemplaire rangé absente")
    check('Found on' in text and 'Stored on' in text and text.index('Found on') < text.index('Stored on'),
          f'dates de découverte et de rangement : {text[-200:]}')
    check('%' in cd.quality_label.cget('text'), f"qualité : {cd.quality_label.cget('text')}")
    check(cd.edit_scales and all(sc.instate(['disabled']) for sc in cd.edit_scales), 'curseurs absents ou actifs')
    check(not any(isinstance(x, ttk.Button) for x in cd.edit_widgets), 'bouton de transfert dans la collection')
    key = next(iter(cd.stars))
    w.detail.yview_moveto(1.0); root.update()   # ascenseur en bas : doit y rester
    scales, view = list(cd.edit_scales), w.detail.yview()
    cd.set_priority(key, 3 if cd.priorities.get(key, 2) != 3 else 1); root.update()   # étoile : priorité partagée
    check(w.tree.selection() == ('unique:375',) and cd.edit_scales == scales, 'sélection perdue / panneau reconstruit')
    check(w.detail.yview() == view, f'défilement déplacé : {view} -> {w.detail.yview()}')
    check(app.saved_priorities[priority_profile(app.library.stored_item('unique:375', d), d)[0]].get(key) is not None,
          'priorité non enregistrée')
    from mxl_library import rank
    q = f"{rank(app.library.stored_item('unique:375', d), d, app.saved_priorities)[1]:.0f} %"
    check(w.tree.set('unique:375', 'stored') == q, f"qualité du tableau : {w.tree.set('unique:375', 'stored')} au lieu de {q}")
    check(str(w.btn_take.cget('state')) == 'normal', 'bouton de sortie inactif')
    # exemplaire normal rangé : la vue Ethereal (infobulle éthérée du catalogue) reste consultable, même après une
    # mise à jour du tableau, et on revient à l'exemplaire rangé
    w.btn_views['ethereal'].invoke(); root.update()
    text = w.detail.get('1.0', 'end')
    check(w.view.get() == 'ethereal' and 'Ethereal' in text and not w.panel.edit_scales
          and str(w.btn_take.cget('state')) == 'disabled' and 'No ethereal copy in the collection.' in text,
          f'vue Ethereal avec un exemplaire normal rangé : {w.view.get()} {text[-150:]!r}')
    w.refresh(); root.update()
    check(w.view.get() == 'ethereal', 'vue Ethereal perdue après une mise à jour du tableau')
    w.btn_views['normal'].invoke(); root.update()
    check(w.view.get() == 'normal' and w.panel.edit_scales and '+60%' in w.detail.get('1.0', 'end'),
          'retour à l\'exemplaire normal rangé')
    w.take_out(); root.update()   # sortie vers le coffre (confirmation acceptée)
    check(sorted(ed(i) for i in app.items if i['code'] == '108 ') == [41, 57, 60] and 'unique:375' not in app.library.collection,
          'sortie vers le coffre')
    check(str(w.btn_take.cget('state')) == 'disabled', 'bouton de sortie actif sans exemplaire rangé')
    # exemplaire éthéré (drapeau : octet 4, bit 6) : place séparée, colonne « Ethereal », bascule, sortie de celui affiché
    eb = bytearray(variant(50))
    eb[4] |= 0x40
    edit_stash(p2, d, insert=[(*free_spot(app.items, blob_item(blob, d), d), bytes(eb))], backup=False)
    app.load(p2); root.update()
    eth = next(i for i in app.items if i['code'] == '108 ' and i['ethereal'])
    dlg = TransferDialog(app, only={eth['_offset']}, source=(p2, None))   # bouton de l'objet (App.transfer)
    check([(a['kind'], a['key']) for a in dlg.plan] == [('store', 'unique:375:eth')], f'plan éthéré : {dlg.plan}')
    dlg.validate(); root.update()
    check(w.tree.set('unique:375', 'ethereal') != '' and w.tree.set('unique:375', 'stored') == '',
          f"colonnes : {w.tree.set('unique:375')}")
    w.tree.selection_set('unique:375'); root.update()
    check(w.view.get() == 'ethereal' and str(w.btn_views['ethereal'].cget('state')) == 'normal',
          f"vue : {w.view.get()}, bouton {w.btn_views['ethereal'].cget('state')}")
    check('Ethereal' in w.detail.get('1.0', 'end') and w.panel.edit_scales, 'panneau de l\'exemplaire éthéré')
    w.take_out(); root.update()
    check('unique:375:eth' not in app.library.collection and any(i['ethereal'] for i in app.items if i['code'] == '108 '),
          'sortie de l\'exemplaire éthéré')
    # vue Ethereal gardée après la sortie (aucun exemplaire rangé) : infobulle éthérée du catalogue
    check(str(w.btn_views['ethereal'].cget('state')) == 'normal' and w.view.get() == 'ethereal'
          and 'Ethereal' in w.detail.get('1.0', 'end'), f"bascule après sortie : {w.view.get()}")
    check(not errors, f'erreurs : {errors}')
    # copie vers le coffre (module) : bouton absent sans le droit duplication_enabled (base seule : jamais)
    check(getattr(w, 'btn_copy', None) is None, 'bouton de copie affiché sans le droit duplication_enabled')
    root.update()   # « Take out » seul : toute la largeur de l'infobulle
    check(abs(w.btn_take.winfo_width() - w.out_row.winfo_width()) <= 1, f'Take out : {w.btn_take.winfo_width()} / {w.out_row.winfo_width()}')
    if EDITOR:   # copie posée (gui_editor_tests.py)
        w = transfer_copy(w, variant, ed)  # noqa: F821 (défini par gui_editor_tests.py)
    # jeu ouvert (simulé) : transfert refusé avec un message, coffre et collection inchangés
    before, stored = open(p2, 'rb').read(), dict(app.library.collection)
    mxl_game.running_processes, mxl_game.process_path = lambda: [('Game.exe', 1)], lambda pid: None
    try:
        dlg = TransferDialog(app, parent=w.win)
        check(bool(dlg.plan), 'rien à transférer : refus non testé')
        dlg.validate(); root.update()
    finally:
        mxl_game.running_processes = lambda: []
    check(len(errors) == 1 and 'Game.exe' in errors[0], f'message du jeu ouvert : {errors}')
    check(open(p2, 'rb').read() == before and dict(app.library.collection) == stored, 'coffre ou collection modifiés')
    dlg.win.destroy()
    finish()


# ---------------------------------------------------------------- shared
def wait(cond, secs=5):
    """Traite les événements de la fenêtre jusqu'à ce que cond() soit vrai (au plus secs secondes)."""
    import time
    end = time.time() + secs
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.05)
    return bool(cond())


def shared():
    import settings
    from mxl_save import parse_stash, move_item, free_spot as free_spot_
    sp = os.path.join(TMP, mxl_gui.SHARED_STASH)
    shutil.copy2(os.path.join(HERE, 'fixtures', 'stash2', 'Nekratall.stash'), sp)   # même format qu'un .stash
    shutil.copy2(os.path.join(HERE, 'fixtures', 'stash2', 'Nekratall.d2s'), os.path.join(TMP, 'Krom.d2s'))
    check(app.char_combo.get() == 'Nekratall' and app.view.get() == 'character' and app.path == P, 'ouverture : '
          f'{app.char_combo.get()} {app.view.get()} {app.path}')
    own = app.char
    # coffre partagé apparu sur le disque alors que le coffre du personnage est affiché : ses objets du catalogue sont
    # enregistrés comme trouvés quand même (surveillance des fichiers)
    from mxl_library import entry_key
    keys = {entry_key(x, app.data) for i in parse_stash(sp, app.data) for x in [i] + i.get('socketed', [])} - {None}
    check(keys and wait(lambda: all(app.library.found.get(k, {}).get('source') == mxl_gui.SHARED_STASH for k in keys)),
          f'objets du coffre partagé non trouvés : {keys}')
    app.btn_views['shared'].invoke(); root.update()
    # coffre du personnage modifié sur le disque alors que le coffre partagé est affiché : ses objets du catalogue sont
    # enregistrés (surveillance), avec ce coffre pour source
    own = open(P, 'rb').read()
    read_from = []
    record0 = app.library.record_found
    app.library.record_found = lambda items, data, source: (read_from.append((source, len(items))),
                                                            record0(items, data, source))[1]
    shutil.copy2(os.path.join(HERE, 'fixtures', 'stash2', 'Nekratall.stash'), P)   # coffre du personnage changé
    n = len(parse_stash(P, app.data))
    check(wait(lambda: ('Nekratall.stash', n) in read_from), f'coffre du personnage non affiché non relu : {read_from}')
    app.library.record_found = record0
    open(P, 'wb').write(own)
    own = app.char
    check(app.path == sp and len(app.items) == len(parse_stash(sp, app.data)) > 0, f'coffre partagé : {app.path}')
    check(app.char == own and app.char_file == os.path.join(TMP, 'Nekratall.d2s'), 'personnage de référence du coffre partagé')
    check((settings.get('last_character'), settings.get('last_view')) == ('Nekratall', 'shared'), 'choix non retenus')
    for it in app.items:   # affichage de chaque objet avec le personnage de référence
        app.set_detail(it)
    app.reload(); root.update()
    check(app.char == own, 'personnage perdu au rechargement du coffre partagé')
    loads = []   # relectures de la surveillance (aucune sans changement du fichier)
    load0 = app.load
    app.load = lambda *a, **k: (loads.append(a), load0(*a, **k))[1]
    wait(lambda: False, 1.5)
    check(not loads, f'coffre relu sans changement : {len(loads)} fois')
    # déplacement dans le coffre partagé : écriture et relecture
    it = app.items[0]
    page, x, y = free_spot_(app.items, it, app.data)
    items0 = app.items   # move_item met aussi à jour l'objet en mémoire : attendre une nouvelle lecture
    move_item(sp, it, x, y, app.data, page=page)   # écriture hors de l'éditeur (comme le jeu) : relu seul
    check(wait(lambda: app.items is not items0 and any((i['page'], i['x'], i['y']) == (page, x, y) for i in app.items)),
          'coffre partagé modifié sur le disque non relu')
    check(app.status.cget('text') == i18n.tr('status.reloaded'), f"message : {app.status.cget('text')}")
    app.load = load0
    # autre personnage (liste relue à l'ouverture de la liste) : coffre partagé affiché pour lui
    root.tk.eval(app.char_combo.cget('postcommand'))
    check(list(app.char_combo.cget('values')) == ['Krom', 'Nekratall'], f"personnages : {app.char_combo.cget('values')}")
    app.char_combo.set('Krom'); app.open_view(); root.update()
    check(app.path == sp and app.char_file == os.path.join(TMP, 'Krom.d2s'), 'coffre partagé pour un autre personnage')
    app.btn_views['character'].invoke(); root.update()   # Krom n'a pas de coffre
    check(app.path is None and not app.items and app.status.cget('text') == i18n.tr('status.no_stash', file='Krom.stash'), 'personnage sans coffre')
    app.char_combo.set('Nekratall'); app.open_view(); root.update()
    check(app.path == P and app.char == own, 'retour au coffre du personnage')
    saved = open(sp, 'rb').read()
    os.remove(sp)
    app.btn_views['shared'].invoke(); root.update()
    check(app.path is None and not app.items, 'coffre partagé absent')
    open(sp, 'wb').write(saved)   # coffre partagé créé par le jeu : ouvert seul
    check(wait(lambda: app.path == sp and app.items), 'coffre partagé apparu non ouvert')
    check(not errors, f'erreurs : {errors}')
    finish()


# ---------------------------------------------------------------- xfer
def view_button(view):
    """Événement souris sur le bouton de coffre view ('character' / 'shared')."""
    b, e = app.btn_views[view], Ev(0, 0)
    e.x_root, e.y_root = b.winfo_rootx() + 6, b.winfo_rooty() + 6
    e.x, e.y = e.x_root - app.grid.canvas.winfo_rootx(), e.y_root - app.grid.canvas.winfo_rooty()
    return e


def xfer():
    """Glisser-déposer d'un coffre à l'autre : survol du bouton « Coffre partagé » = coffre partagé affiché (même
    page), dépôt = objet transféré (sertis compris), une sauvegarde par fichier ; relâché hors de la grille après
    changement de coffre = retour au coffre d'origine, rien ne bouge."""
    from mxl_save import parse_stash, free_spot as free_spot_
    sp = os.path.join(TMP, mxl_gui.SHARED_STASH)
    shutil.copy2(os.path.join(HERE, 'fixtures', 'stash2', 'Nekratall.stash'), sp)
    sh = shark()
    n_src, n_dst = len(app.items), len(parse_stash(sp, app.data))
    app.notebook.select(sh['page']); root.update()
    app.on_click(cell(sh['x'], sh['y'])); app.on_drag(view_button('shared'))
    check(wait(lambda: app.view.get() == 'shared', 3) and app.path == sp, 'survol du bouton : coffre partagé non affiché')
    check(app.page() == sh['page'], f"page changée en passant au coffre partagé : {app.page() + 1}")
    spot = free_spot_(app.items, sh, app.data, pages=[app.page()])
    check(spot is not None, 'pas de place libre dans la page du coffre partagé')
    _, fx, fy = spot
    app.on_drag(cell(fx, fy)); app.on_release(cell(fx, fy)); root.update()
    got = next((i for i in app.items if (i['page'], i['x'], i['y']) == (sh['page'], fx, fy)), None)
    check(got and got['code'] == sh['code'] and len(got['socketed']) == len(sh['socketed']), 'objet absent du coffre partagé')
    check((len(app.items), len(parse_stash(P, app.data))) == (n_dst + 1, n_src - 1), 'nombres d\'objets après le transfert')
    check(len(glob.glob(bak_glob(P))) == 1 and len(glob.glob(bak_glob(sp))) == 1, 'une sauvegarde par fichier attendue')
    check(app.selected is got and app.view.get() == 'shared', 'objet transféré non sélectionné')
    # annulation : vers le coffre du personnage, relâché hors de la grille -> retour au coffre partagé, rien ne bouge
    before = open(P, 'rb').read(), open(sp, 'rb').read()
    app.on_click(cell(got['x'], got['y'])); app.on_drag(view_button('character'))
    check(wait(lambda: app.view.get() == 'character', 3) and app.path == P, 'survol : coffre du personnage non affiché')
    app.on_release(view_button('character')); root.update()
    check(app.view.get() == 'shared' and app.path == sp, 'annulation : coffre d\'origine non réaffiché')
    check((open(P, 'rb').read(), open(sp, 'rb').read()) == before, 'fichiers modifiés par une annulation')
    check(not errors, f'erreurs : {errors}')
    finish()


# ---------------------------------------------------------------- cube
def cube():
    """Cube du personnage : un coffre sans page, modifiable comme un coffre (déplacement, transfert vers un coffre
    et depuis un coffre par survol des boutons) ; le .d2s reste valide ; la fenêtre ne change pas de taille (cases
    plus petites pour les 15 colonnes)."""
    import settings, struct
    from mxl_save import parse_stash, free_spot as free_spot_, character_checksum, load_character
    d2s = os.path.join(TMP, 'Nekratall.d2s')
    shutil.copy2(os.path.join(HERE, 'fixtures', 'character', 'Nekratall.d2s'), d2s)   # 2 objets dans le cube
    width, base = app.grid.canvas.winfo_width(), app.grid.cell
    top = app.grid.canvas.winfo_rooty()

    def sound():
        b = open(d2s, 'rb').read()
        ch = load_character(d2s, app.data)
        return struct.unpack_from('<II', b, 8) == (len(b), character_checksum(b)) and not ch['extra_error'] \
            and len(ch['mercenary']['items']) == 6

    app.btn_views['cube'].invoke(); root.update()
    check(app.path == d2s and sorted(i['code'] for i in app.items) == ['618 ', '7@5 '], f'cube : {app.path} {len(app.items)} objets')
    check((app.box.cols, app.box.rows, app.box.pages) == (15, 10, 1) and app.page() == 0, 'grille du cube')
    check(not app.notebook.winfo_ismapped(), 'onglets des pages affichés pour le cube')
    check(app.grid.canvas.winfo_rooty() == top, 'grille déplacée en hauteur en passant au cube')
    check(app.grid.canvas.winfo_width() == width and app.grid.cell * 15 <= width and app.grid.cell < base, 'largeur de la grille changée')
    check(app.stash_path == d2s, 'cube non modifiable')
    check(app.count_page.cget('text') == '' and app.count_total.cget('text') == i18n.tr('count.cube', n=2), 'barre du bas')
    check(settings.get('last_view') == 'cube', 'vue non retenue')
    for other in app.items:
        app.set_detail(other)
    # déplacement dans le cube
    it = next(i for i in app.items if i['code'] == '618 ')
    app.on_click(cell(it['x'] + 1, it['y'] + 1)); root.update()
    check(app.selected is it and app.drag is not None, 'clic dans le cube : glisser-déposer non commencé')
    app.on_drag(cell(14, 9)); app.on_release(cell(14, 9)); root.update()   # case saisie (1, 1) : objet en (13, 8)
    it = next(i for i in app.items if i['code'] == '618 ')
    check((it['x'], it['y']) == (13, 8) and app.selected is it and sound(), f"déplacement dans le cube : ({it['x']}, {it['y']})")
    check(len(glob.glob(bak_glob(d2s))) == 1, 'sauvegarde du personnage attendue')
    check(app.status.cget('text').startswith(i18n.tr('status.moved_cube', item=app.full_name(it), x=13, y=8)), f"message : {app.status.cget('text')}")
    # cube -> coffre du personnage
    n_stash = len(parse_stash(P, app.data))
    app.on_click(cell(13, 8)); app.on_drag(view_button('character'))
    check(wait(lambda: app.view.get() == 'character', 3) and app.path == P and app.notebook.winfo_ismapped()
          and app.grid.cell == base, 'survol du bouton : coffre du personnage non affiché')
    _, fx, fy = free_spot_(app.items, it, app.data, pages=[app.page()])
    app.on_drag(cell(fx, fy)); app.on_release(cell(fx, fy)); root.update()
    got = next((i for i in app.items if (i['page'], i['x'], i['y']) == (app.page(), fx, fy)), None)
    check(got and got['code'] == '618 ' and len(app.items) == n_stash + 1, 'objet du cube absent du coffre')
    check(sound() and [i['code'] for i in mxl_gui.read_items(d2s, app.data)] == ['7@5 '], 'cube après le départ')
    # coffre -> cube (objet avec objets sertis)
    sh = shark()
    app.notebook.select(sh['page']); root.update()
    app.on_click(cell(sh['x'], sh['y'])); app.on_drag(view_button('cube'))
    check(wait(lambda: app.view.get() == 'cube', 3) and app.path == d2s, 'survol du bouton : cube non affiché')
    _, fx, fy = free_spot_(app.items, sh, app.data, box=app.box)
    app.on_drag(cell(fx, fy)); app.on_release(cell(fx, fy)); root.update()
    got = next((i for i in app.items if (i['x'], i['y']) == (fx, fy)), None)
    check(got and got['code'] == sh['code'] and len(got['socketed']) == len(sh['socketed']) and got['panel'] == 4, 'objet absent du cube')
    check(sound() and len(parse_stash(P, app.data)) == n_stash, 'personnage ou coffre après le transfert')
    app.reload(); root.update()
    check(len(app.items) == 2 and app.box.pages == 1, 'cube perdu au rechargement')
    check(not errors, f'erreurs : {errors}')
    finish()


# ---------------------------------------------------------------- inventory
def inventory():
    """Panneau du personnage : équipement aux emplacements du jeu, sac ; clic = sélection commune avec la grille,
    lecture seule ; panneau replié à l'ouverture, affiché à la demande ; fenêtre assez haute pour le contenir."""
    import settings
    d2s = os.path.join(TMP, 'Nekratall.d2s')
    shutil.copy2(os.path.join(HERE, 'fixtures', 'character', 'Nekratall.d2s'), d2s)   # 10 portés, 2 dans le sac
    check(wait(lambda: app.char and len(app.char['items']) == 20), 'personnage modifié sur le disque non relu')
    root.geometry(''); root.update()
    v = app.char_view
    check(not v.frame.winfo_ismapped() and not app.show_char.get(), "panneau du personnage affiché à l'ouverture")
    show_equipment()
    check(v.frame.winfo_ismapped() and app.show_char.get(), 'panneau du personnage non affiché')
    check(sorted(it['equipped'] for it in v.worn.values()) == list(range(1, 11)), f'emplacements : {sorted(v.worn)}')
    check(len(v.bag.items) == 2 and (v.bag.box.cols, v.bag.box.rows) == (15, 10), f'sac : {len(v.bag.items)} objets')
    # disposition du jeu : tête au-dessus de l'armure, armes de part et d'autre, ceinture dessous, rien hors du canevas
    s = v.slots
    check(s[1][3] <= s[3][1] and s[3][3] <= s[8][1] and s[4][2] <= s[3][0] and s[3][2] <= s[5][0], f'disposition : {s}')
    check(all(0 <= x0 < x1 <= v.canvas.winfo_width() and 0 <= y0 < y1 <= v.canvas.winfo_height() for x0, y0, x1, y1 in s.values()), 'emplacement hors du panneau')
    check(root.winfo_height() >= v.frame.winfo_reqheight() and v.bag.canvas.winfo_rooty() + v.bag.canvas.winfo_height() <= app.status.winfo_rooty() + 2,
          f'fenêtre trop basse : {root.winfo_height()}')
    # clic sur l'armure : sélectionnée, détail affiché, pas d'édition ni de transfert
    x0, y0, x1, y1 = s[3]
    v.on_click(Ev((x0 + x1) // 2, (y0 + y1) // 2)); root.update()
    armor = v.worn[3]
    check(app.selected is armor and app.panel.item is armor, 'clic sur un emplacement : objet non sélectionné')
    check(app.editing == EDITOR and not app.can_transfer(armor), 'objet porté : édition ou transfert')
    st = next(s for s in armor['stats'] if s['id'] == 79)   # +4% Gold Find [3-5]
    before = open(app.char_file, 'rb').read()
    ok, new = app.commit_edit(armor, dict(offset=armor['_offset'], code=armor['code'], kind='stat', stat=79, param=None,
                                          value=3 if st['value'] != 3 else 5))
    if EDITOR:
        check(ok and new is app.selected and new is v.worn[3] and next(s['value'] for s in new['stats'] if s['id'] == 79) != st['value'],
              "édition d'un objet porté")
    else:   # base seule : jamais d'écriture de valeur
        check(not ok and new is None and open(app.char_file, 'rb').read() == before, 'édition écrite sans le module')
    app.reload(); root.update()
    check(app.selected is not None and app.selected is app.char_view.worn[3], 'sélection perdue à la relecture')
    # second jeu d'armes : emplacements d'armes vides, retour au premier
    tx0, ty0, tx1, ty1 = v.tabs[4, 2]
    v.on_click(Ev((tx0 + tx1) // 2, (ty0 + ty1) // 2)); root.update()
    check(v.weapon_set == 2 and 4 not in v.worn and 5 not in v.worn and 3 in v.worn, 'jeu d\'armes II')
    tx0, ty0, tx1, ty1 = v.tabs[5, 1]
    v.on_click(Ev((tx0 + tx1) // 2, (ty0 + ty1) // 2)); root.update()
    check(v.weapon_set == 1 and 4 in v.worn, 'retour au jeu d\'armes I')
    # mercenaire : son équipement (pas d'anneaux, pas de sac), modifiable par curseurs, exigences non évaluées
    import settings as settings_
    v.btn_who['mercenary'].invoke(); root.update()
    merc = app.char['mercenary']['items']
    check(v.mercenary() and settings_.get('panel_view') == 'mercenary' and not v.bag.canvas.winfo_ismapped(), 'vue mercenaire')
    check(sorted(it['equipped'] for it in v.worn.values()) == sorted(it['equipped'] for it in merc) and 6 not in v.worn, f'mercenaire : {sorted(v.worn)}')
    x0, y0, x1, y1 = s[3]
    v.on_click(Ev((x0 + x1) // 2, (y0 + y1) // 2)); root.update()
    it = v.worn[3]
    check(app.selected is it and app.in_mercenary(it) and app.editing == EDITOR and not app.can_transfer(it)
          and app.char_for(it) is None and app.panel.char is None, 'objet du mercenaire : sélection, édition sans transfert')
    st = next(s_ for s_ in it['stats'] if s_['id'] == 16)   # Hard Leather Armor : défense améliorée [35-50]
    ok, new = app.commit_edit(it, dict(offset=it['_offset'], code=it['code'], kind='stat', stat=16, param=None,
                                       value=35 if st['value'] != 35 else 50))
    if EDITOR:
        check(ok and new is app.selected and new is v.worn[3] and app.in_mercenary(new)
              and next(s_['value'] for s_ in new['stats'] if s_['id'] == 16) != st['value'], "édition d'un objet du mercenaire")
    else:
        check(not ok and new is None, 'édition du mercenaire écrite sans le module')
    check('bag' not in app.zones(), 'sac du personnage déposable en vue mercenaire')
    app.reload(); root.update()
    check(app.selected is v.worn.get(3), 'sélection du mercenaire perdue à la relecture')
    v.btn_who['character'].invoke(); root.update()
    check(not v.mercenary() and v.bag.canvas.winfo_ismapped() and len(v.worn) == 10 and app.selected is None, 'retour au personnage')
    # clic dans le sac, puis dans la grille du coffre : une seule sélection
    bag = v.bag.items[0]
    app.select_worn(bag); root.update()
    check(app.selected is bag and app.editing == EDITOR, 'objet du sac non sélectionné ou non modifiable')
    sh = shark()
    app.notebook.select(sh['page']); root.update()
    app.on_click(cell(sh['x'], sh['y'])); app.on_release(cell(sh['x'], sh['y'])); root.update()
    check(app.selected is sh and not app.in_character(app.selected), 'clic dans le coffre : sélection non reprise')
    # panneau replié : grille du coffre au bord gauche, choix retenu ; réaffiché
    app.select_worn(bag); width, height = root.winfo_width(), root.winfo_height()
    app.btn_char.invoke(); root.update()
    check(not v.frame.winfo_ismapped() and app.selected is None, 'panneau non replié')
    check(root.winfo_width() < width, 'fenêtre non rétrécie')
    check(root.winfo_height() == height, f'hauteur de la fenêtre changée panneau replié : {root.winfo_height()} au lieu de {height}')
    app.btn_char.invoke(); root.update()
    check(v.frame.winfo_ismapped() and len(v.worn) == 10, 'panneau non réaffiché')
    check(not errors, f'erreurs : {errors}')
    finish()


# ---------------------------------------------------------------- bag
def bag():
    """Sac modifiable : déplacement dans le sac, sac <-> coffre, sac <-> cube du même personnage (glisser-déposer entre
    le panneau de gauche et la grille de droite), édition d'un objet du sac ; cube Horadrim refusé dans le cube ; le
    .d2s reste valide."""
    import struct
    from mxl_save import parse_stash, character_checksum, load_character, read_items
    from mxl_containers import placed
    d2s = os.path.join(TMP, 'Nekratall.d2s')
    shutil.copy2(os.path.join(HERE, 'fixtures', 'character', 'Nekratall.d2s'), d2s)   # sac : cube Horadrim + catalyseur
    check(wait(lambda: app.char and len(app.char['items']) == 20), 'personnage non relu')
    show_equipment()
    v = app.char_view

    def sound(bag_n, cube_n):
        b = open(d2s, 'rb').read()
        ch = load_character(d2s, app.data)
        return struct.unpack_from('<II', b, 8) == (len(b), character_checksum(b)) and not ch['extra_error'] and \
            [len(placed(ch['items'], w)) for w in ('equipped', 'belt', 'inventory', 'cube')] == [10, 6, bag_n, cube_n]

    def bag_cell(cx, cy):
        c, g = v.bag.canvas, v.bag
        e = Ev(0, 0)
        e.x, e.y = g.left(cx) + g.cell // 2, cy * g.cell + g.cell // 2
        e.x_root, e.y_root = c.winfo_rootx() + e.x, c.winfo_rooty() + e.y
        return e

    box = next(i for i in v.bag.items if i['code'] == 'box ')
    check(app.can_transfer(box) is False, 'cube Horadrim transférable vers la collection')
    # déplacement dans le sac
    app.on_bag_click(bag_cell(box['x'], box['y']))
    check(app.selected is box and app.drag and app.drag['src'] == 'bag' and app.editing == EDITOR, 'clic dans le sac : glisser non commencé')
    app.on_drag(bag_cell(6, 4)); app.on_release(bag_cell(6, 4)); root.update()
    box = next((i for i in v.bag.items if i['code'] == 'box '), None)
    check(box and (box['x'], box['y']) == (6, 4) and app.selected is box and sound(2, 2), 'déplacement dans le sac')
    check(app.status.cget('text').startswith(i18n.tr('status.moved_bag', item=app.full_name(box), x=6, y=4)), f"message : {app.status.cget('text')}")
    # sac -> coffre du personnage
    n_stash = len(app.items)
    app.notebook.select(0); root.update()
    from mxl_save import free_spot as free_spot_
    _, fx, fy = free_spot_(app.items, box, app.data, pages=[0])
    app.on_bag_click(bag_cell(6, 4)); app.on_drag(cell(fx, fy)); app.on_release(cell(fx, fy)); root.update()
    got = next((i for i in app.items if (i['page'], i['x'], i['y']) == (0, fx, fy)), None)
    check(got and got['code'] == 'box ' and len(app.items) == n_stash + 1 and sound(1, 2) and app.selected is got, 'sac -> coffre')
    # coffre -> sac
    app.on_click(cell(fx, fy)); app.on_drag(bag_cell(0, 0)); app.on_release(bag_cell(0, 0)); root.update()
    box = next((i for i in v.bag.items if i['code'] == 'box '), None)
    check(box and (box['x'], box['y']) == (0, 0) and len(parse_stash(P, app.data)) == n_stash and sound(2, 2), 'coffre -> sac')
    # cube affiché : le cube Horadrim y est refusé ; un autre objet du sac y va (même fichier, une écriture)
    app.btn_views['cube'].invoke(); root.update()
    before = open(d2s, 'rb').read()
    app.on_bag_click(bag_cell(0, 0)); app.on_drag(cell(5, 5))
    zone, _, _, ok = app.drop_target(cell(5, 5), app.drag)
    check(zone == 'main' and not ok, 'cube Horadrim déposable dans le cube')
    app.on_release(cell(5, 5)); root.update()
    check(open(d2s, 'rb').read() == before and not errors, 'cube Horadrim écrit dans le cube')
    cat = next(i for i in v.bag.items if i['code'] != 'box ')
    app.on_bag_click(bag_cell(cat['x'], cat['y'])); app.on_drag(cell(7, 7)); app.on_release(cell(7, 7)); root.update()
    got = next((i for i in app.items if (i['x'], i['y']) == (7, 7)), None)
    check(got and got['code'] == cat['code'] and sound(1, 3) and len(glob.glob(bak_glob(d2s))) == 1, 'sac -> cube')
    check(app.status.cget('text').startswith(i18n.tr('status.moved_to_cube', item=app.full_name(got), x=7, y=7)), f"message : {app.status.cget('text')}")
    # cube -> sac
    helm = next(i for i in app.items if i['code'] == '618 ')
    app.on_click(cell(helm['x'], helm['y'])); app.on_drag(bag_cell(3, 3)); app.on_release(bag_cell(3, 3)); root.update()
    helm = next((i for i in v.bag.items if i['code'] == '618 '), None)
    check(helm and (helm['x'], helm['y']) == (3, 3) and sound(2, 2) and len(app.items) == 2, 'cube -> sac')
    # édition d'un objet du sac (Énergie 8-10)
    app.select_worn(helm); root.update()
    st = next(s for s in helm['stats'] if s['id'] == 1)
    edit = dict(offset=helm['_offset'], code=helm['code'], kind='stat', stat=1, param=None, value=8 if st['value'] != 8 else 9)
    ok, new = app.commit_edit(helm, edit)
    got = next(s['value'] for s in new['stats'] if s['id'] == 1) if new else None
    written = next(s['value'] for i in read_items(d2s, app.data, 'inventory') if i['code'] == '618 ' for s in i['stats'] if s['id'] == 1)
    if EDITOR:
        check(ok and got == edit['value'] and app.selected is new and sound(2, 2), f'édition dans le sac : {got}')
        check(written == edit['value'], 'édition non écrite')
    else:
        check(not ok and new is None and written == st['value'], 'édition dans le sac écrite sans le module')
    check(not errors, f'erreurs : {errors}')
    finish()


# ---------------------------------------------------------------- nocube
def nocube():
    """Onglet Cube selon le cube Horadrim du personnage : présent (sac ou coffre) = modifiable ; absent avec des objets
    dans le cube = lecture seule ; absent et cube vide = bouton grisé (vue Cube quittée) ; jamais dans le coffre partagé."""
    from mxl_save import transfer_item, edit_stash, read_items, parse_stash, free_spot as free_spot_
    d2s, other = os.path.join(TMP, 'Nekratall.d2s'), os.path.join(TMP, 'Other.stash')
    shutil.copy2(os.path.join(HERE, 'fixtures', 'character', 'Nekratall.d2s'), d2s)   # cube Horadrim dans le sac
    shutil.copy2(os.path.join(HERE, 'fixtures', 'stash2', 'Nekratall.stash'), other)
    sp = os.path.join(TMP, mxl_gui.SHARED_STASH)
    shutil.copy2(os.path.join(HERE, 'fixtures', 'stash2', 'Nekratall.stash'), sp)
    check(wait(lambda: app.char and len(app.char['items']) == 20), 'personnage non relu')
    show_equipment()
    check(app.cube_state == 'ok' and not app.btn_views['cube'].instate(['disabled']), f'état : {app.cube_state}')
    # glisser le cube Horadrim du sac vers le coffre partagé : refusé (surbrillance rouge, rien d'écrit)
    app.btn_views['shared'].invoke(); root.update()
    v = app.char_view
    box = next(i for i in v.bag.items if i['code'] == 'box ')
    c = v.bag.canvas
    e = Ev(0, 0); e.x, e.y = box['x'] * v.bag.cell + 5, box['y'] * v.bag.cell + 5
    e.x_root, e.y_root = c.winfo_rootx() + e.x, c.winfo_rooty() + e.y
    before = open(sp, 'rb').read(), open(d2s, 'rb').read()
    app.on_bag_click(e)
    page, fx, fy = free_spot_(app.items, box, app.data, pages=[app.page()])
    check(app.drop_target(cell(fx, fy), app.drag)[3] is False, 'cube Horadrim déposable dans le coffre partagé')
    app.on_drag(cell(fx, fy)); app.on_release(cell(fx, fy)); root.update()
    check((open(sp, 'rb').read(), open(d2s, 'rb').read()) == before, 'cube Horadrim écrit dans le coffre partagé')
    # cube Horadrim parti ailleurs (autre coffre) : cube en lecture seule, ses objets restent visibles
    box = next(i for i in read_items(d2s, app.data, 'inventory') if i['code'] == 'box ')
    page, x, y = free_spot_(parse_stash(other, app.data), box, app.data)
    transfer_item(d2s, other, box, page, x, y, app.data, backup_src=False, backup_dst=False, src_where='inventory')
    check(wait(lambda: app.cube_state == 'readonly'), f'état sans cube Horadrim : {app.cube_state}')
    app.btn_views['cube'].invoke(); root.update()
    check(app.path == d2s and len(app.items) == 2 and not app.box.writable and not app.editing and app.stash_path is None,
          'cube non affiché en lecture seule')
    check(app.status.cget('text') == i18n.tr('status.cube_readonly'), f"message : {app.status.cget('text')}")
    it = app.items[0]
    app.on_click(cell(it['x'], it['y']))
    check(app.drag is None, 'glisser-déposer depuis un cube en lecture seule')
    cat = next(i for i in v.bag.items if i['code'] != 'box ')
    e = Ev(0, 0); e.x, e.y = cat['x'] * v.bag.cell + 5, cat['y'] * v.bag.cell + 5
    e.x_root, e.y_root = c.winfo_rootx() + e.x, c.winfo_rooty() + e.y
    app.on_bag_click(e)
    check(app.drop_target(cell(6, 6), app.drag)[3] is False, 'dépôt permis dans un cube en lecture seule')
    app.on_release(cell(6, 6)); root.update()
    # cube vidé : bouton grisé, retour au coffre du personnage
    edit_stash(d2s, app.data, remove=[i['_offset'] for i in read_items(d2s, app.data, 'cube')], backup=False, where='cube')
    check(wait(lambda: app.cube_state == 'none'), f'état sans cube ni contenu : {app.cube_state}')
    check(app.btn_views['cube'].instate(['disabled']), 'bouton Cube actif sans cube')
    app.view.set('cube'); app.open_view(); root.update()
    check(app.view.get() == 'character' and app.path == P, 'vue Cube ouverte sans cube')
    # cube Horadrim revenu (dans le coffre du personnage) : cube de nouveau modifiable
    box = next(i for i in parse_stash(other, app.data) if i['code'] == 'box ')
    page, x, y = free_spot_(parse_stash(P, app.data), box, app.data)
    transfer_item(other, P, box, page, x, y, app.data, backup_src=False, backup_dst=False)
    check(wait(lambda: app.cube_state == 'ok') and not app.btn_views['cube'].instate(['disabled']), 'cube Horadrim revenu : bouton grisé')
    check(not errors, f'erreurs : {errors}')
    finish()


def crashed(exc, val, tb):
    """Exception dans un test ou un rappel de l'interface : échec signalé et fenêtres fermées (le test ne reste
    jamais bloqué en attendant qu'on les ferme à la main)."""
    import traceback
    failures.append('exception : ' + ''.join(traceback.format_exception(exc, val, tb)))
    finish()


def timeout():
    failures.append(f'délai dépassé ({TIMEOUT} s) : test interrompu')
    finish()


TIMEOUT = 120   # secondes : filet de sécurité, les tests durent quelques secondes
root.report_callback_exception = crashed
root.after(TIMEOUT * 1000, timeout)
TESTS = {'smoke': smoke, 'drag': drag1, 'library': library, 'transfer': transfer, 'shared': shared, 'xfer': xfer,
         'cube': cube, 'inventory': inventory, 'bag': bag, 'nocube': nocube}
EDITOR_TESTS = os.path.join(os.path.dirname(HERE), 'mxl_editor', 'tests', 'gui_editor_tests.py')
if EDITOR:   # tests du module : définis ici, avec les outils de ce fichier ; ajoutés à TESTS (et transfer_copy)
    exec(compile(open(EDITOR_TESTS, encoding='utf-8').read(), EDITOR_TESTS, 'exec'))
root.after(1200, TESTS[TEST])
root.mainloop()
