"""Écran Library : image de l'objet dans la colonne à gauche de l'infobulle : exemplaire rangé (3 calques, comme
dans la grille) ou entrée non rangée (calque 1 de chaque apparence possible), centrée verticalement sur l'infobulle et
suivant son défilement.

DetailImage est une classe mixte de mxl_library_gui.LibraryWindow : elle en utilise app, detail (zone de texte de
l'infobulle), detail_image (canevas), image_y et catalog_images.
"""
from mxl_gui_detail import LAYERS_SHOWN
from mxl_rules import table_row
from mxl_theme import DETAIL_BG
from mxl_gfx import icon_layers, has_variants
from paths import ICONS_DIR

IMAGE_PAD = 10   # marge (px) à gauche de l'image de l'objet, dans le panneau de détail de la collection


class DetailImage:
    """Image de l'objet du panneau de détail de l'écran Library (classe mixte de LibraryWindow)."""

    def draw_image(self, it, bg):
        """Image de l'objet (3 calques, comme dans la grille) sur son fond de case, centrée horizontalement dans la
        colonne de gauche, centre en y = 0 (placée ensuite par place_image)."""
        cv, s = self.detail_image, self.app.grid.base_cell
        w, h = self.app.size(it)
        cx = (IMAGE_PAD + int(cv.cget('width'))) / 2
        cv.create_rectangle(cx - w * s / 2 + 1, -h * s / 2 + 1, cx + w * s / 2 - 1, h * s / 2 - 1, fill=bg, outline='',
                            tags=('img',))
        imgs = self.app.grid.icon(it, bg, (w * s - 2, h * s - 2))
        # référence gardée ici : le cache de la grille est vidé à chaque relecture du coffre (App.load), et un panneau
        # non reconstruit (contenu inchangé, detail_signature) perdrait son image
        self.detail_photos = imgs
        for k in (1, 2, 3):
            if imgs and imgs[k] is not None and k in LAYERS_SHOWN:
                cv.create_image(cx, 0, image=imgs[k], tags=('img', f'calque{k}'))
        self.image_y = 0

    def catalog_variants(self, entry):
        """Apparences possibles d'une entrée non rangée : n° des variantes du type d'objet (bagues, amulettes, joyaux,
        reliques…, tirée au hasard sur chaque exemplaire), ou [None] : une seule apparence (icône propre de l'unique /
        objet de set, ou type sans variantes)."""
        data = self.app.data
        row = table_row(entry['key'], data)
        if row['inv_file'] or not has_variants(entry['code'], data):
            return [None]
        t = data.base(entry['code']).type
        return [k for k, v in enumerate(data.itype_gfx[t]) if v]

    def draw_catalog_image(self, entry, opacity):
        """Entrée non rangée (trouvée ou non) : calque 1 de chaque apparence possible (catalog_variants ; icône propre
        de l'unique / objet de set, sinon variante du type ou icône de l'objet de base) sur fond noir, à cette opacité
        sur le fond du panneau (mélange PIL : pas de transparence dans un canevas Tk). Plusieurs apparences : grille de
        2 colonnes (largeur de la colonne de l'image), lignes centrées ; le tout centré comme draw_image."""
        from PIL import Image, ImageTk
        cv, s = self.detail_image, self.app.grid.base_cell
        w, h = self.app.data.base(entry['code']).size
        size = (w * s - 2, h * s - 2)   # même taille que l'image d'un objet dans la grille
        variants = self.catalog_variants(entry)
        cols, gap = max(1, min(len(variants), 2 // w)), 4
        rows = -(-len(variants) // cols)
        cx = (IMAGE_PAD + int(cv.cget('width'))) / 2
        top = -(rows * size[1] + (rows - 1) * gap) / 2   # grille centrée sur y = 0 (placée ensuite par place_image)
        for n, k in enumerate(variants):
            key = (entry['key'], size, opacity, k)
            if key not in self.catalog_images:
                # objet minimal de l'entrée : qualité et n° de ligne (icône propre, icon_name), n° de variante
                it = dict(code=entry['code'], quality=entry['kind'], set_unique_id=entry['row'], image=k)
                layers = icon_layers(it, self.app.data, '#000000', ICONS_DIR)
                img = layers[1].resize(size, Image.LANCZOS) if layers else Image.new('RGBA', size, '#000000')
                img = Image.blend(Image.new('RGBA', size, DETAIL_BG), img, opacity)
                self.catalog_images[key] = ImageTk.PhotoImage(img)
            r, c = divmod(n, cols)
            in_row = min(cols, len(variants) - r * cols)   # dernière ligne incomplète : centrée
            x = cx + (c - (in_row - 1) / 2) * (size[0] + gap)
            y = top + r * (size[1] + gap) + size[1] / 2
            cv.create_image(x, y, image=self.catalog_images[key], tags=('img', 'calque1'))
        self.image_y = 0

    def place_image(self):
        """Image centrée verticalement sur l'infobulle (zone de fond 'tip' du texte), en suivant le défilement."""
        t, cv = self.detail, self.detail_image
        ranges = t.tag_ranges('tip')
        if not ranges or not cv.find_withtag('img'):
            return

        def px(a, b):   # hauteur en pixels du texte entre deux positions (lignes hors de la vue comprises)
            r = t.count(a, b, 'update', 'ypixels')
            return (r[0] if isinstance(r, tuple) else r) or 0
        total = px('1.0', 'end')
        center = int(t.cget('pady')) + (px('1.0', ranges[0]) + px('1.0', ranges[-1])) / 2 - t.yview()[0] * total
        cv.move('img', 0, center - self.image_y)
        self.image_y = center
