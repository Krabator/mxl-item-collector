"""Feuille de statistiques : panneau affiché à gauche du coffre à la place de l'équipement (bouton « Stats »), dans
l'esprit des trois pages de statistiques du jeu. Onglets : Character, Mercenary (grisé sans mercenaire), Summons
(à venir, grisé) ; pages choisies en bas (Main, General, Speed & defenses, Summons & more ; trois pour le mercenaire).

Chaque section est une grille de 12 colonnes de même largeur (mêmes bords et mêmes colonnes dans toutes les sections) :
couples libellé / valeur deux par ligne, tableaux par élément. Largeur fixe ; hauteur fixe, celle de la plus longue
page du personnage et de son mercenaire (la fenêtre ne change pas de taille d'une page à l'autre). Valeurs :
mxl_char_stats (CharacterStats, MercenaryStats) ; une case « valeur / plafond » quand le jeu plafonne la stat.
Dégâts des armes et des compétences, Attack Rating : pas encore (onglet à part prévu). host : la fenêtre (data, char).
"""
import tkinter as tk
import tkinter.font as tkfont
import ttkbootstrap as ttk

from i18n import tr
from mxl_char_stats import character_stats, MercenaryStats, WEAPON_ELEMENTS
from mxl_widgets import AutoScrollbar, screen_area
from mxl_rules import CLASSES
from mxl_theme import (DIM, LABEL_DIM, FONT, GAME_COLORS, STATS_BG as BG, STATS_CELL as CELL, STATS_HEAD as HEAD, STATS_LINE as LINE,
                       STATS_LABEL as GOLD, STATS_VALUE as WHITE, STATS_MAGIC, STATS_INNATE as INNATE)

EL = {'fire': GAME_COLORS['1'], 'cold': GAME_COLORS['3'], 'light': GAME_COLORS['9'], 'poison': GAME_COLORS['2'],
      'magic': STATS_MAGIC}
# colonnes des tableaux par élément : (clé de traduction, couleur) ; ordre de la feuille du jeu
ELEMENTS = (('stats.el.fire', 'fire'), ('stats.el.cold', 'cold'), ('stats.el.lightning', 'light'),
            ('stats.el.poison', 'poison'))
EL_RESISTS, EL_SPELL, EL_PIERCE = (39, 43, 41, 45), (329, 331, 330, 332), (333, 335, 334, 336)
# absorption (feuille du jeu : feu, froid, foudre, magie ; pas de poison) : valeur fixe (descfunc 1) et % (descfunc 2)
EL_ABSORB, EL_ABSORB_PCT = (143, 149, 145, 147), (142, 148, 144, 146)
ABSORB_COLUMNS = (('stats.el.fire', 'fire'), ('stats.el.cold', 'cold'), ('stats.el.lightning', 'light'),
                  ('stats.el.magic', 'magic'))
COLS, WIDTH = 12, 540
ATTRIBUTE_KEYS = {0: 'strength', 1: 'energy', 2: 'dexterity', 3: 'vitality'}   # libellés (stats.*)
TIP_MIN_WIDTH = 640   # infobulle de la facture (DamageTip) : largeur minimale
F, FB, FT = (FONT, 9), (FONT, 9, 'bold'), (FONT, 10, 'bold')
# plafonds affichés « valeur / plafond » : Evade, Dodge, Avoid 60 % ; Slow Target, Slow Attacker 90 % ; Spell Focus
# 1000 ; bonus de résistance des invocations (D2Sigma.dll 0x10068250) : physique 50 %, élémentaire 105 %
# dégâts élémentaires d'une arme (section Weapon) : clé du libellé, stats min / max, couleur
WEAPON_ELEMENT_ROWS = (('fire_damage', 48, 49, 'fire'), ('cold_damage', 54, 55, 'cold'), ('lightning_damage', 50, 51, 'light'),
                       ('poison_damage', 57, 58, 'poison'), ('magic_damage', 52, 53, 'magic'))
AVOID_CAP, SLOW_CAP, SPELL_FOCUS_CAP, SUMMON_PHYS_CAP, SUMMON_ELE_CAP = 60, 90, 1000, 50, 105
REANIMATE = 155        # « x% Reanimate as: <monstre> » : param = ligne de monstats
# pages (n° utilisé par char_page / merc_page) dans l'ordre des boutons ; mercenaire : sans Skill ni Summons & more
SKILL_PAGE = 5
SKILL_ENABLED = False   # page Skill : bouton grisé pour l'instant (dégâts des compétences à venir)
PAGES = (('stats.page.main', 1), ('stats.page.general', 2), ('stats.page.skill', SKILL_PAGE),
         ('stats.page.defenses', 3), ('stats.page.summons', 4))
MERC_PAGES = (1, 2, 3)
SKILLS = ('attack',)   # compétences dont la feuille détaille le calcul (page Skill)
# barre du multiplicateur (page Skill) : base, W. Physical Damage, bonus de Force, de Dextérité
BAR = {'base': LABEL_DIM, 'weapon_physical': INNATE, 'strength': GAME_COLORS['1'], 'dexterity': GAME_COLORS['2']}


def pct(v):
    return f'{v}%'


def yes_no(v):
    """Stat sans valeur (1 bit, effet présent ou non : Half Freeze Duration, Cannot Be Frozen) : Yes / No."""
    return tr('stats.yes' if v > 0 else 'stats.no')


def capped(v, cap, unit='%'):
    return f'{v}{unit} / {cap}{unit}'


class Section:
    """Section : titre centré entre deux filets, puis une grille de 12 colonnes de même largeur."""

    def __init__(self, parent, title):
        head = tk.Frame(parent, bg=BG)
        head.pack(side='top', fill='x', pady=(10, 3))
        tk.Frame(head, bg=GOLD, height=1).pack(side='left', fill='x', expand=True, pady=(8, 0))
        tk.Label(head, text=title.upper(), fg=GOLD, bg=BG, font=FT, padx=10).pack(side='left')
        tk.Frame(head, bg=GOLD, height=1).pack(side='left', fill='x', expand=True, pady=(8, 0))
        self.g = tk.Frame(parent, bg=BG)
        self.g.pack(side='top', fill='x')
        for c in range(COLS):
            self.g.columnconfigure(c, weight=1, uniform='col')
        self.row = 0

    def cell(self, col, span, text, fg=WHITE, bold=False, bg=CELL):
        label = tk.Label(self.g, text=text, fg=fg, bg=bg, font=FB if bold else F, padx=4, pady=3, highlightthickness=1,
                         width=1, highlightbackground=LINE)
        label.grid(row=self.row, column=col, columnspan=span, sticky='nsew', padx=1, pady=1)
        return label

    def pairs(self, items, half_last=False):
        """Deux couples (libellé, valeur[, couleur]) par ligne : 4 + 2 | 4 + 2 colonnes ; nombre impair : le dernier
        sur toute la largeur, ou dans la colonne de gauche seulement (half_last : aligné sur ceux du dessus). Renvoie
        les cases des valeurs, dans l'ordre."""
        values = []
        for i in range(0, len(items), 2):
            if i + 1 == len(items) and not half_last:
                values.append(self.wide(*items[i]))
                break
            for k, item in enumerate(items[i:i + 2]):
                self.cell(6 * k, 4, item[0], GOLD)
                values.append(self.cell(6 * k + 4, 2, item[1], item[2] if len(item) > 2 else WHITE, bold=True))
            self.row += 1
        return values

    def wide(self, lab, val, fg=WHITE):
        """Un couple sur toute la largeur : 4 + 8 colonnes ; renvoie la case de la valeur."""
        self.cell(0, 4, lab, GOLD)
        value = self.cell(4, 8, val, fg, bold=True)
        self.row += 1
        return value

    def table(self, headers, rows, colors=None):
        """Tableau : libellé, puis une colonne par en-tête, de même largeur (3 en-têtes : 3 + 3 × 3, 4 : 4 + 4 × 2,
        2 : 4 + 2 × 4)."""
        n = len(headers)
        span = {3: 3, 5: 2}.get(n, (COLS - 4) // n)
        first = COLS - span * n
        self.cell(0, first, '', bg=BG)
        for k, h in enumerate(headers):
            self.cell(first + span * k, span, h, colors[k] if colors else GOLD, bold=True, bg=HEAD)
        self.row += 1
        for lab, vals in rows:
            self.cell(0, first, lab, GOLD)
            for k, v in enumerate(vals):
                self.cell(first + span * k, span, v, colors[k] if colors else WHITE, bold=True)
            self.row += 1


class StatsView:
    def __init__(self, parent, host):
        self.host = host
        self.frame = ttk.Frame(parent, padding=(0, 0, 8, 0))
        self.who = tk.StringVar(value='character')
        self.page = tk.IntVar(value=1)
        row = ttk.Frame(self.frame)
        row.pack(side='top', fill='x', pady=(0, 4))
        self.btn_who = {}
        for who, key in (('character', 'btn.panel_character'), ('mercenary', 'btn.panel_mercenary'),
                         ('summons', 'btn.panel_summons')):
            b = ttk.Radiobutton(row, text=tr(key), value=who, variable=self.who, command=self.draw,
                                bootstyle='info-outline-toolbutton')
            b.pack(side='left')
            self.btn_who[who] = b
        self.btn_who['summons'].state(['disabled'])   # à venir
        self.sheet = tk.Frame(self.frame, bg=BG, width=WIDTH)
        self.sheet.pack(side='top', fill='y', expand=True)
        self.sheet.pack_propagate(False)
        self.fitted = None   # personnage dont la hauteur fixe a été calculée
        self.measuring = False   # mesure de la hauteur fixe en cours (fit_height : une seule arme)
        self.damage_tips = []
        self.skill = tk.StringVar(value=SKILLS[0])   # compétence détaillée (page Skill)

    def retranslate(self):
        for who, key in (('character', 'btn.panel_character'), ('mercenary', 'btn.panel_mercenary'),
                         ('summons', 'btn.panel_summons')):
            self.btn_who[who].configure(text=tr(key))
        self.fitted = None

    # ---------- statistiques ----------
    def other_set(self):
        """Vrai si l'onglet I / II affiché dans le panneau Equipment n'est pas le jeu d'armes actif du jeu."""
        ch = self.host.char
        view = getattr(self.host, 'char_view', None)
        if not ch or view is None or view.shown_char != (ch['path'], ch['weapon_switch']):
            return False
        return view.weapon_set != (2 if ch['weapon_switch'] else 1)

    def weapon_set(self):
        """Onglet I / II (1 / 2) dont les armes comptent."""
        ch = self.host.char
        active = 2 if ch and ch['weapon_switch'] else 1
        return 3 - active if self.other_set() else active

    def char_stats(self):
        """CharacterStats du personnage, avec le jeu d'armes de l'onglet affiché dans le panneau Equipment."""
        return character_stats(self.host.char, self.host.data, self.other_set())

    def mercenary(self):
        """MercenaryStats du mercenaire du personnage (mort compris), ou None."""
        ch, data = self.host.char, self.host.data
        if not ch or not ch.get('mercenary'):
            return None
        cs = character_stats(ch, data)
        return cs.mercenary or MercenaryStats(ch['mercenary'], data, ch.get('difficulty') or 0)

    def draw(self):
        """Dessine la page choisie (rien sans personnage) ; hauteur fixée au premier dessin de chaque personnage."""
        ch = self.host.char
        has_merc = bool(ch and ch.get('mercenary'))
        self.btn_who['mercenary'].state(['!disabled' if has_merc else 'disabled'])
        if not has_merc and self.who.get() == 'mercenary':
            self.who.set('character')
        if (self.who.get() == 'mercenary' and self.page.get() not in MERC_PAGES) or (
                self.page.get() == SKILL_PAGE and not SKILL_ENABLED):
            self.page.set(1)
        key = (id(ch), ch and ch.get('path'))
        if ch is not None and key != self.fitted:
            self.fitted = key
            self.fit_height()
        self.render()

    def fit_height(self):
        """Hauteur fixe : celle de la plus longue page du personnage et de son mercenaire, mesurée dans un cadre jamais
        affiché (la fenêtre ne change pas de taille pendant la mesure : pas de clignotement)."""
        probe = tk.Frame(self.frame, bg=BG, width=WIDTH)
        best = 0
        self.measuring = True   # une seule arme : deux armes (Barbare, Assassin) -> ascenseur, même hauteur
        try:
            for w in ('character', 'mercenary'):
                for n in (n for _, n in PAGES if SKILL_ENABLED or n != SKILL_PAGE) if w == 'character' else MERC_PAGES:
                    self.render(probe, w, n)
                    probe.update_idletasks()
                    best = max(best, probe.winfo_reqheight())
        finally:
            self.measuring = False
        probe.destroy()
        self.sheet.configure(height=best, width=WIDTH)

    def render(self, target=None, who=None, page=None):
        """Dessine une page dans target (la feuille affichée par défaut) : who, page (choix affichés par défaut)."""
        target = target or self.sheet
        who, page = who or self.who.get(), page or self.page.get()
        for w in target.winfo_children():
            w.destroy()
        ch, data = self.host.char, self.host.data
        if not ch:
            return
        merc = self.mercenary() if who == 'mercenary' else None
        if merc is not None:
            act = merc.act()
            kind = (tr('stats.merc.kind', subclass=merc.subclass(), act=tr(f'stats.act.{act}'))
                    if merc.subclass() and act else tr('btn.panel_mercenary'))
            title = tr('stats.title.merc', name=merc.name() or tr('btn.panel_mercenary'), kind=kind,
                       level=merc.char['level'])
        else:
            cls = CLASSES[ch['cls']] if 0 <= ch['cls'] < len(CLASSES) else '?'
            title = tr('stats.title.char', name=ch['name'], cls=cls, level=ch['level'],
                       difficulty=tr(f"stats.difficulty.{ch.get('difficulty') or 0}"))
        tk.Label(target, text=title, fg=GOLD, bg=BG, font=(FONT, 12, 'bold')).pack(side='top', pady=(8, 0))
        # navigation des pages, centrée en bas comme les flèches du jeu (placée avant le contenu : toujours visible)
        nav = tk.Frame(target, bg=BG)
        nav.pack(side='bottom', pady=(10, 10))
        if target is self.sheet:   # contenu plus haut que la feuille : ascenseur
            body = self.scroll_area(target)
        else:
            body = tk.Frame(target, bg=BG, padx=10)
            body.pack(side='top', fill='both', expand=True)
        if merc is not None:
            self.merc_page(body, merc, page)
        else:
            self.char_page(body, self.char_stats(), page)
        buttons = {}
        for key, n in [(k, n) for k, n in PAGES if merc is None or n in MERC_PAGES]:
            b = ttk.Radiobutton(nav, text=tr(key), value=n, variable=self.page, bootstyle='warning-outline-toolbutton',
                                command=self.render)
            b.pack(side='left', padx=2)
            if n == SKILL_PAGE and not SKILL_ENABLED:
                b.state(['disabled'])
            buttons[n] = b
        if target is self.sheet:
            self.btn_pages = buttons

    def scroll_area(self, target):
        """Zone de contenu de la feuille : cadre dans un canevas de la largeur de la feuille ; ascenseur à droite
        seulement si le contenu dépasse la hauteur fixe ; molette de la souris sur la feuille."""
        area = tk.Frame(target, bg=BG)
        area.pack(side='top', fill='both', expand=True)
        canvas = tk.Canvas(area, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(area, command=canvas.yview, bootstyle='round')
        body = tk.Frame(canvas, bg=BG, padx=10)
        window = canvas.create_window(0, 0, window=body, anchor='nw')

        def yset(first, last):
            sb.set(first, last)
            if float(first) <= 0 and float(last) >= 1:
                sb.pack_forget()
            elif not sb.winfo_manager():
                sb.pack(side='right', fill='y', before=canvas)
        canvas.configure(yscrollcommand=yset)
        canvas.pack(side='left', fill='both', expand=True)
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))
        body.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))

        def wheel(ev):
            if sb.winfo_manager():
                canvas.yview_scroll(-1 if ev.delta > 0 else 1, 'units')
        def leave(ev):   # sortie vers une case de la feuille (Leave du cadre parent) : molette gardée
            w = area.winfo_containing(ev.x_root, ev.y_root)
            if w is None or not str(w).startswith(str(area)):
                area.unbind_all('<MouseWheel>')
        area.bind('<Enter>', lambda e: area.bind_all('<MouseWheel>', wheel))
        area.bind('<Leave>', leave)
        self.scroll = (canvas, sb)
        return body

    # ---------- pages ----------
    def resist_rows(self, cs):
        """Ligne « résistance / plafond » du tableau des éléments, puis Physical / Magic Resistance avec plafond."""
        return [(tr('stats.resistance'), [capped(cs.shown_resist(sid), cs.resist_cap(sid)) for sid in EL_RESISTS])]

    def char_page(self, body, cs, p):
        s, T = cs.stat, lambda k: tr('stats.' + k)
        if p == SKILL_PAGE:
            return self.skill_page(body, cs)
        el_colors = [EL[e] for _, e in ELEMENTS]
        headers = [tr(k) for k, _ in ELEMENTS]
        if p == 1:
            Section(body, T('sec.attributes')).pairs([
                (T('strength'), f'{cs.attribute(0):,}'), (T('vitality'), f'{cs.attribute(3):,}'),
                (T('dexterity'), f'{cs.attribute(2):,}'), (T('energy'), f'{cs.attribute(1):,}')])
            sec = Section(body, T('sec.resistances'))
            sec.table(headers, self.resist_rows(cs), el_colors)
            sec.pairs([(T('physical_resistance'), capped(cs.shown_resist(36), cs.resist_cap(36))),
                       (T('magic_resistance'), capped(cs.shown_resist(37), cs.resist_cap(37)), EL['magic'])])
            sec = Section(body, T('sec.defense'))
            sec.wide(T('defense'), f'{cs.defense():,}')
            sec.pairs([(T('block_chance'), capped(cs.block_chance(), cs.block_cap())), (T('grit'), pct(s(184)))])
        elif p == 2:
            sec = Section(body, T('sec.general'))
            rows = [(T(lab), [f'{cs.attribute(sid):,}', pct(s(pc)), f'{cs.base_stat(sid):,}'])
                    for lab, sid, pc in (('strength', 0, 359), ('dexterity', 2, 360), ('vitality', 3, 362),
                                         ('energy', 1, 361))]
            rows += [(T('life'), [f'{int(cs.max_life()):,}', pct(s(76)), f'{cs.base(7) // 256:,}']),
                     (T('mana'), [f'{int(cs.max_mana()):,}', pct(s(77)), f'{cs.base(9) // 256:,}']),
                     (T('stamina'), [f'{int(cs.max_stamina()):,}', '', f'{cs.base(11) // 256:,}'])]
            sec.table([T('col.total'), T('col.bonus'), T('col.base')], rows)
            Section(body, T('sec.skills')).pairs([
                (T('all_skills'), s(127)), (T('class_skills'), s(83, cs.char.get('cls'))),
                (T('skill_duration'), pct(s(409)))], half_last=True)
            self.weapon(body, cs, [(T('innate_ele_damage'), pct(s(484)))])
            sec = Section(body, T('sec.spells'))
            sec.table(headers, [(T('spell_damage'), [pct(s(i)) for i in EL_SPELL]),
                                (T('pierce'), [pct(cs.shown_stat(i)) for i in EL_PIERCE])], el_colors)
            sec.pairs([(T('phys_magic_damage'), pct(s(357)), EL['magic']),
                       (T('poison_skill_duration'), pct(s(431)), EL['poison']),
                       (T('spell_focus'), capped(s(485), SPELL_FOCUS_CAP, ''))])
        elif p == 3:
            self.speed(body, s)
            sec = Section(body, T('sec.defenses'))
            sec.pairs([(T('bonus_defense'), pct(s(171))), (T('evade'), capped(s(338), AVOID_CAP)),
                       (T('base_block'), pct(cs.base_block_chance())), (T('dodge'), capped(s(339), AVOID_CAP)),
                       (T('avoid'), capped(s(340), AVOID_CAP))], half_last=True)
            sec.table(headers, [(T('stacked_resists'), [pct(s(i)) for i in EL_RESISTS])], el_colors)
            self.absorb(sec, s)
            plr = cs.shown_resist(110)
            sec.pairs([(T('stacked_magic'), pct(s(37)), EL['magic']), (T('stacked_physical'), pct(s(36)))]
                      + self.reductions(s, plr, EL['fire'] if plr < 0 else WHITE))
            self.sustain(body, s)
        else:
            sec = Section(body, T('sec.summons'))
            sec.pairs([(T('summon_damage'), pct(s(470))), (T('summon_ar'), pct(s(500))),
                       (T('summon_life'), pct(s(444))), (T('summon_phys'), capped(s(229), SUMMON_PHYS_CAP)),
                       (T('summon_ele'), capped(s(487), SUMMON_ELE_CAP))], half_last=True)
            names = self.host.data.monster_names
            for (sid, mon), v in sorted(cs.totals.items(), key=lambda kv: (kv[0][0], -kv[1])):
                if sid == REANIMATE and v and mon is not None:
                    name = names[mon] if 0 <= mon < len(names) else f'#{mon}'
                    sec.wide(T('reanimate'), f'{v}%  {name}')
            self.misc(body, s)

    def merc_page(self, body, m, p):
        """Pages du mercenaire : seulement ce qui lui sert (ni Vitalité, Endurance, Mana, compétences de classe,
        invocations ; Grit : Barbarian seulement) ; valeur en bleu : bonus inné compris."""
        s, T = m.stat, lambda k: tr('stats.' + k)
        el_colors = [EL[e] for _, e in ELEMENTS]
        headers = [tr(k) for k, _ in ELEMENTS]

        def inn(sid, text, other=WHITE):
            return text, INNATE if m.innate.get(sid) else other

        if p == 1:
            Section(body, T('sec.attributes')).pairs([
                (T('strength'), f'{m.attribute(0):,}'), (T('dexterity'), f'{m.attribute(2):,}'),
                (T('energy'), f'{m.attribute(1):,}', INNATE if m.base_stat(1) else WHITE)], half_last=True)
            sec = Section(body, T('sec.resistances'))
            sec.table(headers, self.resist_rows(m), el_colors)
            sec.pairs([(T('physical_resistance'), *inn(36, capped(m.shown_resist(36), m.resist_cap(36)))),
                       (T('magic_resistance'), capped(m.shown_resist(37), m.resist_cap(37)), EL['magic'])])
            sec = Section(body, T('sec.defense'))
            sec.pairs([(T('life'), f'{int(m.max_life()):,}'), (T('defense'), f'{m.defense():,}')])
            if s(184):
                sec.pairs([(T('grit'), *inn(184, pct(s(184))))], half_last=True)
            self.misc(body, s, inn)
            tk.Label(body, text=T('innate_legend'), fg=INNATE, bg=BG, font=F).pack(side='top', pady=(10, 0))
        elif p == 2:
            sec = Section(body, T('sec.general'))
            rows = [(T(lab), [f'{m.attribute(sid):,}', pct(s(pc)), f'{m.base_stat(sid):,}'])
                    for lab, sid, pc in (('strength', 0, 359), ('dexterity', 2, 360), ('energy', 1, 361))]
            rows.append((T('life'), [f'{int(m.max_life()):,}', pct(s(76)), f'{m.base(7) // 256:,}']))
            sec.table([T('col.total'), T('col.bonus'), T('col.base')], rows)
            Section(body, T('sec.skills')).pairs([(T('all_skills'), s(127)), (T('skill_duration'), pct(s(409)))])
            # Innate Elemental Damage : augmente les dégâts élémentaires « % de Force / Dextérité » des compétences
            # données par certains objets (Zephyr, Azurewrath, Amok…), que le mercenaire peut porter
            self.weapon(body, m, [(T('innate_ele_damage'), pct(s(484)))], inn)
            sec = Section(body, T('sec.spells'))
            sec.table(headers, [(T('spell_damage'), [pct(s(i)) for i in EL_SPELL]),
                                (T('pierce'), [pct(m.shown_stat(i)) for i in EL_PIERCE])], el_colors)
            # Poison Skill Duration : lue par la formule de durée (skills.bin 0x224) de Miasma (Necrolyte) et de 11 des
            # 13 procs de poison des objets (Snakehair, Shadowstrike…), que tout mercenaire peut porter
            sec.pairs([(T('phys_magic_damage'), pct(s(357)), EL['magic']),
                       (T('poison_skill_duration'), pct(s(431)), EL['poison']),
                       (T('spell_focus'), *inn(485, capped(s(485), SPELL_FOCUS_CAP, '')))])
        else:
            self.speed(body, s)
            sec = Section(body, T('sec.defenses'))
            sec.pairs([(T('bonus_defense'), *inn(171, pct(s(171)))), (T('evade'), *inn(338, capped(s(338), AVOID_CAP))),
                       (T('dodge'), capped(s(339), AVOID_CAP)), (T('avoid'), capped(s(340), AVOID_CAP))])
            self.absorb(sec, s)
            plr = m.shown_resist(110)
            sec.pairs(self.reductions(s, plr, INNATE))
            self.sustain(body, s, mana=False)

    # ---------- page Skill : calcul détaillé (« facture ») ----------
    def skill_page(self, body, cs):
        """Compétence choisie parmi SKILLS (Attack) et son calcul étape par étape : arme, dégâts plats des autres
        objets, multiplicateur (barre proportionnelle et sources), résultat."""
        T = lambda k: tr('stats.' + k)
        row = tk.Frame(body, bg=BG)
        row.pack(side='top', pady=(10, 0))
        tk.Label(row, text=T('skill.choose'), fg=GOLD, bg=BG, font=F).pack(side='left', padx=(0, 6))
        names = {tr('stats.skill.' + k): k for k in SKILLS}
        box = ttk.Combobox(row, state='readonly', width=18, values=list(names))
        box.set(tr('stats.skill.' + self.skill.get()))
        box.bind('<<ComboboxSelected>>', lambda e: (self.skill.set(names[box.get()]), self.render()))
        box.pack(side='left')
        d = cs.weapon_damage_detail()
        if d is None:
            tk.Label(body, text=T('skill.no_weapon'), fg=WHITE, bg=BG, font=F).pack(side='top', pady=20)
            return
        self.invoice(body, d)

    def invoice(self, body, d):
        """Facture des dégâts physiques de l'arme (CharacterStats.weapon_damage_detail d) : 1. l'arme jusqu'à son
        infobulle, 2. dégâts plats des autres objets, 3. multiplicateur (barre proportionnelle et chaque source), 4.
        résultat. Page Skill et infobulle de Physical Damage (DamageTip)."""
        T = lambda k: tr('stats.' + k)
        name = lambda it: self.host.full_name(it).split('\n')[0]
        # 1. l'arme, jusqu'à son infobulle (son nom est dans le titre)
        sec = Section(body, T('skill.sec.weapon').format(name=name(d['weapon'])))
        rows = [(T('skill.base'), d['base'], WHITE)]
        if d['ethereal']:
            rows.append((T('skill.ethereal'), d['ethereal'], DIM))
        rows.append((T('skill.ed').format(ed=d['ed']), d['after_ed'], INNATE))
        if any(d['weapon_flat']):
            rows.append((T('skill.weapon_flat'), [f'+{v}' for v in d['weapon_flat']], INNATE))
        rows.append((T('skill.tooltip'), d['tooltip'], GOLD))
        self.min_max(sec, rows)
        # 2. dégâts plats des autres objets
        sec = Section(body, T('skill.sec.flat'))
        rows = [('+ ' + self.source_name(kind, ref, name), [f'+{v}' for v in vals], WHITE) for kind, ref, vals in d['flat']]
        self.min_max(sec, rows + [(T('skill.damage'), d['damage'], GOLD)])
        # 3. multiplicateur : barre proportionnelle, puis chaque source
        sec = Section(body, T('skill.sec.multiplier'))
        groups = {}
        for kind, ref, v in d['percent']:
            g = kind if kind in BAR else 'weapon_physical'
            groups[g] = groups.get(g, 0) + v
        self.bar(sec, [(T('skill.bar.' + g), v, BAR[g]) for g, v in groups.items()], d['multiplier'])
        for kind, ref, v in d['percent']:
            if kind == 'base':
                lab, val = T('skill.base_pct'), '100%'
            elif kind in ('strength', 'dexterity'):
                attr, coef = ref
                lab, val = T('skill.' + kind).format(attr=f'{attr:,}', coef=f'{coef / 100:g}'), f'+{v}%'
            else:
                lab, val = T('skill.weapon_physical').format(source=self.source_name(kind, ref, name)), f'+{v}%'
            sec.cell(0, 9, lab, GOLD)
            sec.cell(9, 3, val, WHITE, bold=True)
            sec.row += 1
        sec.cell(0, 9, T('skill.multiplier'), GOLD)
        sec.cell(9, 3, f"{d['multiplier']}%  (× {d['multiplier'] / 100:g})", GOLD, bold=True)
        sec.row += 1
        # 4. résultat
        sec = Section(body, T('skill.sec.result'))
        lo, hi = d['result']
        self.min_max(sec, [(T('skill.damage_short'), d['damage'], WHITE),
                           (T('skill.times').format(m=f"{d['multiplier'] / 100:g}"), [f'{lo:,}', f'{hi:,}'], GOLD)])

    def element_invoice(self, body, cs, it, key, lo_id, hi_id):
        """Facture d'un élément d'une arme : 1. dégâts ajoutés par les objets, 2. dégâts innés (compétences cachées,
        terme par terme : % × attribut, × (100 + Innate Ele Damage) si la formule l'applique), 3. résultat."""
        T = lambda k: tr('stats.' + k)
        name = lambda x: self.host.full_name(x).split('\n')[0]
        d = cs.element_detail(it, lo_id, hi_id)
        element = T(key).replace(' Damage', '')
        n = 0   # parties numérotées dans l'ordre affiché
        if d['added']:
            n += 1
            sec = Section(body, T('skill.sec.added').format(n=n, element=element))
            rows = [('+ ' + self.source_name(kind, ref, name), [f'+{v:,}' for v in vals], WHITE) for kind, ref, vals in d['added']]
            self.min_max(sec, rows + [(T('skill.added'), d['added_total'], GOLD)])
        innate = cs.stat(484)
        for skill in d['innate']:
            n += 1
            sec = Section(body, T('skill.sec.innate').format(n=n))
            for a, pct_, origin, raw, part in skill['terms']:
                sec.cell(0, 6, T('skill.term').format(pct=f'{pct_:g}', attr=T(ATTRIBUTE_KEYS[a]),
                                                      origin=T('skill.origin.' + origin)), GOLD)
                sec.cell(6, 3, f'× {cs.attribute(a):,}', WHITE)
                sec.cell(9, 3, f'{raw:,}', WHITE, bold=True)
                sec.row += 1
                if part != raw:   # terme augmenté par Innate Ele Damage
                    sec.cell(0, 6, T('skill.innate_bonus').format(innate=innate), INNATE)
                    sec.cell(6, 3, '', WHITE)
                    sec.cell(9, 3, f'{part:,}', INNATE, bold=True)
                    sec.row += 1
            lo, hi = skill['total']
            sec.cell(0, 9, T('skill.innate_total'), GOLD)
            sec.cell(9, 3, f'{lo:,}' if lo == hi else f'{lo:,} - {hi:,}', GOLD, bold=True)
            sec.row += 1
        sec = Section(body, T('skill.sec.element_result').format(n=n + 1))
        rows = [(T('skill.added_short'), d['added_total'], WHITE)]
        if d['innate']:
            lo = sum(s['total'][0] for s in d['innate'])
            hi = sum(s['total'][1] for s in d['innate'])
            rows.append((T('skill.innate_short'), [f'+{lo:,}', f'+{hi:,}'], WHITE))
        rows.append(('= ' + T(key), d['result'], GOLD))
        self.min_max(sec, rows)

    def source_name(self, kind, ref, name):
        """Nom d'une source de stat (CharacterStats.sources) : objet, bonus de set, aura / passive, bonus inné…"""
        if kind == 'item':
            return name(ref)
        if kind in ('aura', 'passive'):
            return self.host.data.skill(ref)
        return tr('stats.skill.source.' + kind)

    def min_max(self, sec, rows):
        """Tableau Min / Max de la facture : libellé sur 6 colonnes, valeurs sur 3 chacune ; lignes (libellé, (min,
        max), couleur des valeurs)."""
        sec.cell(0, 6, '', bg=BG)
        for k, h in enumerate(('stats.col.min', 'stats.col.max')):
            sec.cell(6 + 3 * k, 3, tr(h), GOLD, bold=True, bg=HEAD)
        sec.row += 1
        for lab, vals, fg in rows:
            sec.cell(0, 6, lab, GOLD)
            for k, v in enumerate(vals):
                sec.cell(6 + 3 * k, 3, v if isinstance(v, str) else f'{v:,}', fg, bold=True)
            sec.row += 1

    def bar(self, sec, parts, total):
        """Barre proportionnelle des parts du multiplicateur : (libellé, %, couleur), libellé sous chaque part."""
        cv = tk.Canvas(sec.g, height=46, bg=BG, highlightthickness=0, width=1)
        cv.grid(row=sec.row, column=0, columnspan=COLS, sticky='ew', padx=1, pady=(2, 4))
        sec.row += 1

        def paint(_ev=None):
            cv.delete('all')
            width, x = cv.winfo_width(), 0
            for lab, v, col in parts:
                x2 = x + width * v / total
                cv.create_rectangle(x, 4, x2, 30, fill=col, outline=BG)
                cv.create_text((x + x2) / 2, 17, text=f'{v}%', fill='#000000', font=FB)
                cv.create_text((x + x2) / 2, 40, text=lab, fill=col, font=F)
                x = x2
        cv.bind('<Configure>', paint)

    # ---------- sections communes ----------
    def weapon(self, body, cs, extra, inn=None):
        """Section Weapon : pour chaque arme (une, ou main gauche puis main droite), son nom, ses dégâts physiques
        (survol : facture), élémentaires et bonus de Force / Dextérité ; puis les valeurs communes aux armes."""
        s, T = cs.stat, lambda k: tr('stats.' + k)
        inn = inn or (lambda sid, text: (text, WHITE))
        # personnage : onglet I / II dont les armes comptent (celui affiché dans le panneau Equipment)
        sec = Section(body, T('sec.weapon') if isinstance(cs, MercenaryStats)
                      else T('sec.weapon_set').format(set='I' * self.weapon_set()))
        weapons = cs.weapons()
        if self.measuring:   # hauteur fixe de la feuille : une seule arme
            weapons = weapons[-1:]
        self.damage_tips = []
        self.element_tips = {}
        for it in weapons or [None]:
            if it is None:
                sec.wide(T('weapon'), '—', GOLD)
                phys, el, (str_b, dex_b) = None, {sid: s(sid) for sid in WEAPON_ELEMENTS}, (0, 0)
            else:
                sec.wide(T('weapon'), self.host.full_name(it).split('\n')[0], GOLD)
                detail = cs.weapon_damage_detail(it)
                phys, el, (str_b, dex_b) = detail['result'], cs.weapon_elemental(it), cs.damage_bonus(it)
            cells = sec.pairs([(T('physical_damage'), f'{phys[0]:,} - {phys[1]:,}' if phys else '—')] +
                              [(T(key), f'{el[a]} - {el[b]}', EL[col]) for key, a, b, col in WEAPON_ELEMENT_ROWS] +
                              [(T('str_damage_bonus'), pct(str_b)), (T('dex_damage_bonus'), pct(dex_b))])
            if phys:   # survol : facture du calcul de cette arme
                self.damage_tips.append(DamageTip(self, cells[0], cs, it))
            for cell, (key, a, b, col) in zip(cells[1:], WEAPON_ELEMENT_ROWS):   # survol : facture de l'élément
                if it is not None and (el[a] or el[b]):
                    tip = DamageTip(self, cell, cs, it, render=lambda f, k=key, a=a, b=b: self.element_invoice(f, cs, it, k, a, b))
                    self.element_tips[key] = tip
        self.damage_tip = self.damage_tips[-1] if self.damage_tips else None
        tk.Frame(sec.g, bg=BG, height=16).grid(row=sec.row, column=0, columnspan=COLS)
        sec.row += 1
        sec.pairs([(T('weapon_physical'), *inn(25, pct(s(25))))] + extra +
                  [(T('crushing_blow'), *inn(136, pct(s(136)))), (T('deadly_strike'), pct(s(141))),
                   (T('damage_demons'), pct(s(121))), (T('damage_undead'), pct(s(122))),
                   (T('attack_rating_pct'), pct(s(119)))], half_last=True)

    def speed(self, body, s):
        T = lambda k: tr('stats.' + k)
        Section(body, T('sec.speed')).pairs([
            (T('speed_attack'), pct(s(93))), (T('speed_cast'), pct(s(105))), (T('speed_block'), pct(s(102))),
            (T('speed_hit_recovery'), pct(s(99))), (T('speed_movement'), pct(s(96)))], half_last=True)

    def absorb(self, sec, s):
        """Tableau de l'absorption : fixe et %, par élément (feu, froid, foudre, magie)."""
        T = lambda k: tr('stats.' + k)
        sec.table([tr(k) for k, _ in ABSORB_COLUMNS], [(T('absorb'), [str(s(i)) for i in EL_ABSORB]),
                                                       (T('absorb_pct'), [pct(s(i)) for i in EL_ABSORB_PCT])],
                  [EL[e] for _, e in ABSORB_COLUMNS])

    def reductions(self, s, plr, plr_color):
        T = lambda k: tr('stats.' + k)
        return [(T('phys_damage_reduction'), s(34)), (T('ele_damage_reduction'), s(35)),
                (T('curse_length'), pct(s(109))), (T('poison_length'), pct(plr), plr_color),
                (T('half_freeze'), yes_no(s(118))), (T('cannot_be_frozen'), yes_no(s(153)))]

    def sustain(self, body, s, mana=True):
        """Régénération et vol de vie et de mana ; mana=False (mercenaire, mana infinie) : vie seulement."""
        T = lambda k: tr('stats.' + k)
        rows = [(T('regeneration'), [s(74) // 10, pct(s(27))]), (T('leech'), [pct(s(60)), pct(s(62))]),
                (T('on_melee_attack'), [s(210), s(295)]), (T('on_striking'), [s(208), s(209)]),
                (T('after_kill'), [s(86), s(138)])]
        n = 2 if mana else 1
        Section(body, T('sec.sustain')).table([T('life'), T('mana')][:n], [(lab, v[:n]) for lab, v in rows],
                                              [EL['fire'], EL['cold']][:n])

    def misc(self, body, s, inn=None):
        T = lambda k: tr('stats.' + k)
        inn = inn or (lambda sid, text: (text, WHITE))
        Section(body, T('sec.misc')).pairs([
            (T('magic_find'), pct(s(80))), (T('gold_find'), pct(s(79))), (T('experience'), *inn(85, pct(s(85)))),
            (T('light_radius'), s(89)), (T('slow_target'), capped(s(150), SLOW_CAP)),
            (T('slow_attacker'), *inn(363, capped(s(363), SLOW_CAP))), (T('activation'), pct(s(427)))])


class DamageTip:
    """Infobulle de la case Physical Damage : la facture des dégâts de l'arme (StatsView.invoice), à côté de la case,
    sur la largeur que demandent ses textes (nom d'arme long compris, au moins TIP_MIN_WIDTH) ; plus haute que l'écran :
    ascenseur (affiché seulement alors ; molette de la souris sur la case)."""

    def __init__(self, view, cell, cs, it=None, render=None):
        """render(cadre) : contenu de l'infobulle (par défaut : facture de Physical Damage de l'arme it)."""
        self.view, self.cell, self.cs, self.it, self.win = view, cell, cs, it, None
        self.render = render
        cell.configure(cursor='question_arrow')
        cell.bind('<Enter>', self.show)
        cell.bind('<Leave>', self.hide)
        cell.bind('<Destroy>', self.hide)
        cell.bind('<MouseWheel>', self.wheel)

    def show(self, _ev=None):
        if self.win is not None:
            return
        render = self.render
        if render is None:
            d = self.cs.weapon_damage_detail(self.it)
            if d is None:
                return
            render = lambda frame: self.view.invoice(frame, d)
        cell = self.cell
        self.win = win = tk.Toplevel(cell)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes('-topmost', True)
        outer = tk.Frame(win, bg=BG, highlightthickness=1, highlightbackground=GOLD)
        outer.pack()
        self.canvas = canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        inner = tk.Frame(canvas, bg=BG, padx=10)
        render(inner)
        tk.Frame(inner, bg=BG, height=10).pack(side='top')
        inner.update_idletasks()
        width = natural_width(inner)
        canvas.create_window(0, 0, window=inner, anchor='nw', width=width)
        inner.update_idletasks()
        height = inner.winfo_reqheight()
        x0, y0 = cell.winfo_rootx(), cell.winfo_rooty()
        left, top, right, bottom = screen_area(cell, x0, y0)
        shown = min(height, bottom - top - 20)
        canvas.configure(width=width, height=shown, scrollregion=(0, 0, width, height))
        canvas.pack(side='left')
        if shown < height:   # ascenseur seulement si la facture dépasse l'écran
            sb = AutoScrollbar(outer, command=canvas.yview, bootstyle='round')
            canvas.configure(yscrollcommand=sb.set)
            sb.pack(side='left', fill='y')
        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        x = x0 + cell.winfo_width() + 8
        if x + w > right:   # pas la place à droite : à gauche de la case
            x = max(left, x0 - w - 8)
        y = min(max(top + 10, y0 + cell.winfo_height() // 2 - h // 2), bottom - h - 10)
        win.geometry(f'+{x}+{y}')
        win.deiconify()

    def hide(self, _ev=None):
        if self.win is not None:
            self.win.destroy()
            self.win = None

    def wheel(self, ev):
        if self.win is not None:
            self.canvas.yview_scroll(-1 if ev.delta > 0 else 1, 'units')
            return 'break'   # pas la feuille dessous


def natural_width(frame):
    """Largeur qu'il faut à une facture pour que rien ne soit coupé : texte de chaque case de grille (largeur de sa
    part des COLS colonnes) et de chaque titre de section (entre ses deux filets) ; au moins TIP_MIN_WIDTH."""
    need, todo = TIP_MIN_WIDTH, [frame]
    while todo:
        w = todo.pop()
        todo.extend(w.winfo_children())
        if w.winfo_class() != 'Label' or not str(w.cget('text')):
            continue
        text = tkfont.Font(font=w.cget('font')).measure(str(w.cget('text')))
        info = w.grid_info()
        if info:   # case : texte + marges, sur sa part des colonnes
            need = max(need, (text + 16) * COLS // int(info.get('columnspan', 1)) + 20)
        else:      # titre de section : texte + deux filets
            need = max(need, text + 140)
    return need
