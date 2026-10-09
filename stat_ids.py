"""Numéros des stats du jeu (itemstatcost.bin) utilisés par le code, avec un nom lisible.

Seules les stats traitées spécialement par le code figurent ici ; toutes les autres sont gérées de façon
générique à partir des tables (textes, fonctions d'affichage, plages).
"""
# attributs du personnage
STRENGTH, ENERGY, DEXTERITY, VITALITY = 0, 1, 2, 3
ATTRIBUTES = (STRENGTH, ENERGY, DEXTERITY, VITALITY)
LEVEL = 12                      # niveau du personnage (base des stats « par niveau »)
GOLD = 14                       # dernière stat lue dans l'en-tête d'un .d2s

# défense et dégâts
ENH_DEFENSE = 16                # % de défense améliorée
ENH_DAMAGE_MAX, ENH_DAMAGE_MIN = 17, 18   # % de dégâts améliorés (toujours ensemble)
MIN_DAMAGE, MAX_DAMAGE = 21, 22            # dégâts plats, arme principale
MIN_DAMAGE_2, MAX_DAMAGE_2 = 23, 24        # dégâts plats, 2e ligne (deux mains)
THROW_MIN_DAMAGE, THROW_MAX_DAMAGE = 159, 160   # dégâts plats de lancer
DEFENSE = 31                    # défense plate (et largeur / décalage de la défense de base stockée)

# dégâts élémentaires (min, max, durée)
FIRE_MIN, FIRE_MAX = 48, 49
LIGHTNING_MIN, LIGHTNING_MAX = 50, 51
MAGIC_MIN, MAGIC_MAX = 52, 53
COLD_MIN, COLD_MAX, COLD_LENGTH = 54, 55, 56
POISON_MIN, POISON_MAX, POISON_LENGTH = 57, 58, 59
ELEMENTAL_WITH_LENGTH = (COLD_MIN, COLD_MAX, COLD_LENGTH, POISON_MIN, POISON_MAX, POISON_LENGTH)

# durabilité (largeur et décalage des champs stockés dans l'objet)
DURABILITY, MAX_DURABILITY = 72, 73

LIFE_REGEN = 74                 # vie régénérée : le jeu affiche ~valeur / 10
CLASS_SKILLS = 83               # +x aux compétences d'une classe (param = classe)
REQUIREMENTS = 91               # « Requirements -x% »
LEVEL_REQ = 92                  # « +x Required Level » (ajouté au niveau requis)
VENDOR_PRICES = 87              # « -x% to All Vendor Prices »
MANA_COST = 228                 # « Mana Cost of Skills -x% »
STAMINA_DRAIN = 154             # « x% to Stamina Drain » (positif) / « x% Faster Stamina Drain » (négatif enregistré)
ENEMY_RESISTANCES = (333, 334, 335, 336)   # « -x% to Enemy Fire / Lightning / Cold / Poison Resistance »
BASE_BLOCK = 20                 # « +x% Base Block Chance » (ajouté à la chance de blocage)
ATTACK_SPEED = 93               # % de vitesse d'attaque
SINGLE_SKILL, SINGLE_SKILL_2 = 97, 107   # +x à une compétence précise (param = compétence)
CHANCE_TO_CAST = range(195, 204)         # « x % de chance de lancer … » (param = compétence × 64 + niveau)
CHARGES = 204                            # charges (param = compétence × 64 + niveau)
QUANTITY = 501                           # quantité des Containers, Clusters et Shrine Vessels de Median XL
PREFIX_COUNT, SUFFIX_COUNT = 410, 411    # compteurs « Prefixes: n » / « Suffixes: n »
