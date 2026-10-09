"""Installation de Median XL : dossier du jeu, version, empreinte, reconstruction du dossier data/.

data/ contient ce que l'éditeur extrait des archives du jeu (MPQ) : tables (.bin / .tbl), animations (animdata.d2)
et icônes des objets (PNG dans data/items/). Il doit être reconstruit à chaque nouvelle version du mod.
- Empreinte d'une installation (fingerprint) : version du mod (medianxl-version.mpq) et nom / taille / date de chaque
  archive medianxl-*.mpq. Enregistrée dans data/install.json à la fin de chaque reconstruction ; si elle ne
  correspond plus à l'installation, data/ est périmé.
- Contenu de data/ (manifest) : chaque fichier extrait avec sa taille et son md5, aussi dans install.json.
  check_data vérifie que data/ est intact : rapide (présence et taille, au lancement) ou complet (contenu).
- Réparation (repair_data) : si le jeu n'a pas changé, seuls les fichiers absents ou abîmés sont ré-extraits, chacun
  vérifié par son md5 avant de remplacer l'ancien ; sinon, reconstruction complète.
- Reconstruction sûre (rebuild_data) : extraction complète dans <data>.new, contrôle (tables lisibles, icônes
  présentes), puis remplacement : l'ancien dossier devient <data>.old (un seul gardé) ; en cas d'erreur, data/ est
  intact.
"""
import glob, hashlib, json, os, shutil
from mpq import MPQ

TABLES_MPQ = 'medianxl-YmludGJsdHh0.mpq'     # « bintbltxt » en base64 : tables .bin / .tbl
ANIMDATA_MPQ = 'medianxl-YW5pbWRhdGE.mpq'    # « animdata » : animdata.d2
VERSION_MPQ = 'medianxl-version.mpq'         # version.mxl : version du mod (ex. « 2.14.4 »)
INSTALL_FILE = 'install.json'                # empreinte de l'installation dont data/ est extrait
# version du contenu extrait (install.json) : augmentée quand l'éditeur extrait de nouveaux fichiers -> data/ d'une
# version antérieure = 'unknown' (reconstruction proposée). 2 : icônes propres des uniques et des objets de set
EXTRACT_VERSION = 3   # 3 : icônes des compétences (data/skills)


def is_game_dir(path):
    """Vrai si path est un dossier d'installation de Median XL (archive des tables présente)."""
    return bool(path) and os.path.isfile(os.path.join(path, TABLES_MPQ))


def game_version(game_dir):
    """Version du mod lue dans medianxl-version.mpq (ex. « 2.14.4 »), ou None."""
    try:
        raw = MPQ(os.path.join(game_dir, VERSION_MPQ)).read('version.mxl')
        return raw.decode('latin1').strip() if raw else None
    except (OSError, ValueError, KeyError):
        return None


def fingerprint(game_dir):
    """Empreinte de l'installation : {version, files: {archive medianxl-*.mpq: [taille, date]}}."""
    files = {}
    for p in sorted(glob.glob(os.path.join(game_dir, 'medianxl-*.mpq'))):
        st = os.stat(p)
        files[os.path.basename(p)] = [st.st_size, int(st.st_mtime)]
    return dict(version=game_version(game_dir), files=files)


def installed(data_dir):
    """Empreinte enregistrée dans data/install.json, ou None (absente : data/ d'avant cette fonction)."""
    try:
        with open(os.path.join(data_dir, INSTALL_FILE), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def manifest(data_dir):
    """Contenu de data_dir : {chemin relatif ('/'): [taille, md5]} de chaque fichier, sauf install.json."""
    out = {}
    for d, _, files in os.walk(data_dir):
        for f in files:
            p = os.path.join(d, f)
            rel = os.path.relpath(p, data_dir).replace(os.sep, '/')
            if rel != INSTALL_FILE:
                with open(p, 'rb') as fh:
                    b = fh.read()
                out[rel] = [len(b), hashlib.md5(b).hexdigest()]
    return out


def check_data(data_dir, full=False):
    """Fichiers de data_dir absents ou différents de ceux extraits (liste de l'empreinte), [] si intact, None si
    l'empreinte ne contient pas la liste. Rapide : présence et taille (0,02 s) ; full : contenu (md5, environ 1 s)."""
    expected = (installed(data_dir) or {}).get('manifest')
    if not expected:
        return None
    bad = []
    for rel, (size, md5) in sorted(expected.items()):
        p = os.path.join(data_dir, *rel.split('/'))
        try:
            if os.path.getsize(p) != size:
                bad.append(rel)
            elif full:
                with open(p, 'rb') as fh:
                    if hashlib.md5(fh.read()).hexdigest() != md5:
                        bad.append(rel)
        except OSError:
            bad.append(rel)
    return bad


def data_state(data_dir, game_dir, full=False):
    """État de data_dir pour l'installation game_dir : 'missing' (ni tables ni empreinte), 'unknown' (extraites par
    une ancienne version de l'éditeur : tables sans empreinte, ou version d'extraction antérieure à EXTRACT_VERSION),
    'outdated' (le jeu a changé : reconstruction complète), 'damaged' (même jeu, fichiers absents ou modifiés,
    check_data : réparables) ou 'ok'."""
    fp = installed(data_dir)
    if fp is None or not fp.get('manifest'):
        return 'unknown' if os.path.isfile(os.path.join(data_dir, 'itemstatcost.bin')) else 'missing'
    if fp.get('files') != fingerprint(game_dir)['files']:
        return 'outdated'
    if fp.get('extract_version', 1) < EXTRACT_VERSION:   # extrait par un éditeur qui extrayait moins de fichiers
        return 'unknown'
    return 'damaged' if check_data(data_dir, full) else 'ok'


def build_data(game_dir, out_dir, progress=None):
    """Extraction complète des données du jeu dans out_dir (créé) : tables et fichiers de bintbltxt, animdata.d2,
    icônes des objets et slot de sertissage (out_dir/items), puis empreinte (install.json).
    progress(étape, fait, total) est appelé au fil de l'extraction (étapes : 'tables', 'icons')."""
    from mxl_data import Data                      # imports locaux : Data lit les tables qu'on vient d'extraire
    from mxl_gfx import extract_icons, extract_ui, extract_skill_icons
    progress = progress or (lambda step, done, total: None)
    os.makedirs(out_dir, exist_ok=True)
    for mpq_name, keep in ((TABLES_MPQ, None), (ANIMDATA_MPQ, 'animdata.d2')):
        m = MPQ(os.path.join(game_dir, mpq_name))
        names = [n for n in m.read('(listfile)').decode('latin1').split() if keep is None or n.endswith(keep)]
        for k, name in enumerate(names):
            with open(os.path.join(out_dir, name.split('\\')[-1]), 'wb') as f:
                f.write(m.read(name))
            progress('tables', k + 1, len(names))
    items = os.path.join(out_dir, 'items')
    ok, missing = extract_icons(game_dir, Data(out_dir), items, progress=lambda d, t: progress('icons', d, t))
    extract_ui(game_dir, items)
    extract_skill_icons(game_dir, Data(out_dir), os.path.join(out_dir, 'skills'))
    with open(os.path.join(out_dir, INSTALL_FILE), 'w', encoding='utf-8') as f:
        json.dump(dict(fingerprint(game_dir), game_dir=game_dir, extract_version=EXTRACT_VERSION, manifest=manifest(out_dir)),
                  f, ensure_ascii=False, indent=1)
    return ok, missing


def repair_data(game_dir, data_dir, files, progress=None):
    """Ré-extrait seulement les fichiers files (chemins relatifs de la liste de install.json) depuis game_dir, qui doit
    être l'installation dont data_dir est extrait (même empreinte). Chaque fichier est écrit à côté, contrôlé par son
    md5, puis remplace l'ancien. Lève ValueError si l'installation a changé ou si un fichier ne peut pas être
    retrouvé à l'identique (reconstruction complète nécessaire). progress(étape 'repair', fait, total)."""
    from mxl_gfx import open_archives, load_palette, read_file, decode_dc6, skill_icon_image, ITEMS_DIR, UI_FILES
    import io
    fp = installed(data_dir) or {}
    expected = fp.get('manifest') or {}
    if not expected or fp.get('files') != fingerprint(game_dir)['files']:
        raise ValueError('game installation changed: full rebuild needed')
    sources = {}   # nom de fichier -> (archive, chemin dans l'archive), pour les tables et animdata.d2
    for mpq_name, keep in ((TABLES_MPQ, None), (ANIMDATA_MPQ, 'animdata.d2')):
        m = MPQ(os.path.join(game_dir, mpq_name))
        for name in m.read('(listfile)').decode('latin1').split():
            if keep is None or name.endswith(keep):
                sources[name.split('\\')[-1]] = (m, name)
    archives = palette = None
    for k, rel in enumerate(files):
        if rel not in expected:
            raise ValueError(f'{rel}: not in the manifest')
        if rel.startswith('items/'):   # icône (ou slot de sertissage) : DC6 décodé en PNG
            if archives is None:
                archives = open_archives(game_dir)
                palette = load_palette(archives)
            name = rel[len('items/'):-len('.png')]
            raw = read_file(archives, UI_FILES.get(name) or f'{ITEMS_DIR}\\{name}.dc6')
            if raw is None:
                raise ValueError(f'{rel}: not found in the game archives')
            buf = io.BytesIO()
            decode_dc6(raw, palette).save(buf, 'PNG')
            content = buf.getvalue()
        elif rel.startswith('skills/'):   # icône de compétence : image d'un DC6 décodée en PNG
            if archives is None:
                archives = open_archives(game_dir)
                palette = load_palette(archives)
            img = skill_icon_image(archives, palette, rel[len('skills/'):-len('.png')])
            if img is None:
                raise ValueError(f'{rel}: not found in the game archives')
            buf = io.BytesIO()
            img.save(buf, 'PNG')
            content = buf.getvalue()
        else:
            if rel not in sources:
                raise ValueError(f'{rel}: not found in the game archives')
            m, name = sources[rel]
            content = m.read(name)
        if hashlib.md5(content).hexdigest() != expected[rel][1]:
            raise ValueError(f'{rel}: extracted file differs from the original')
        path = os.path.join(data_dir, *rel.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + '.tmp', 'wb') as f:
            f.write(content)
        os.replace(path + '.tmp', path)
        if progress:
            progress('repair', k + 1, len(files))
    return len(files)


def rebuild_data(game_dir, data_dir, progress=None):
    """Reconstruit data_dir depuis l'installation game_dir, sans risque : extraction dans <data_dir>.new, contrôle
    (tables lisibles par Data, icônes extraites), puis <data_dir> -> <data_dir>.old et <data_dir>.new -> <data_dir>.
    Renvoie (icônes extraites, icônes introuvables). En cas d'erreur, data_dir n'est pas modifié."""
    from mxl_data import Data
    new, old = data_dir + '.new', data_dir + '.old'
    shutil.rmtree(new, ignore_errors=True)
    try:
        ok, missing = build_data(game_dir, new, progress)
        Data(new)   # contrôle : les tables extraites se lisent, les fichiers sont conformes à la liste enregistrée
        if not ok:
            raise ValueError('no item icon extracted')
        if check_data(new, full=True):
            raise ValueError('extracted files differ from their manifest')
    except BaseException:
        shutil.rmtree(new, ignore_errors=True)
        raise
    shutil.rmtree(old, ignore_errors=True)
    if os.path.exists(data_dir):
        os.replace(data_dir, old)
    os.replace(new, data_dir)
    return ok, missing
