# Affixes « Magic Find » — Median XL 2.14.5

Source : `magicprefix.bin` extrait du jeu. Stat 80 (item_magicbonus), propriété 103.

## Règles
- Magic Find est **toujours un préfixe**, groupe 113 : un seul préfixe MF par objet (magique ou rare). Les joyaux ont leur propre groupe (160).
- Octet @0x54 = affixe actif (1) ou désactivé (0). Les paliers à 0 (anciens) ne tombent plus : cohérent avec tous les objets observés.
- Niveau d'objet minimum @0x58, niveau d'objet max @0x60 (0 = pas de limite), niveau requis @0x65.
- Aucune source MF en auto-affixe (automagic) ni en suffixe. Pas de MF de préfixe sur amulettes ni boucliers.

## Paliers actifs (valeur, ilvl min → ilvl max, niveau requis)
**Armures de torse (`tors`) et armes (`weap`)**
20–24 (ilvl 3→69, req 3) · 25–28 (40→85, req 33) · 28–33 (49→90, req 41) · 33–38 (59→90, req 49) · 41–50 (68+, req 56) · 51–60 (82+, req 64)

**Anneaux, gants, ceintures, casques (`ring glov belt helm misl`)**
8–10 (ilvl 3→69, req 3) · 11–13 (40→85, req 33) · 13–15 (49→90, req 41) · 16–18 (59→90, req 49) · 18–20 (68+, req 56)
Variante `aglv ablt ahlm abot` : 30–35 (68+, req 56)

**Bottes (`boot`)**
5–10 (ilvl 9→66, req 9) · 11–15 (38→82, req 32) · 16–20 (48+, req 40)

**Joyaux (`jewl`)**
2–3 (ilvl 14→56, req 12) · 3–5 (41+, req 34)

## Exemple observé
Sash « Hailstone Lash » (rare, ilvl 5) : préfixe 590 = MF 8–10 → +10 % (max du palier).
