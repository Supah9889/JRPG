# Shared party state for equipment and stats
# This ensures character equipment and stats persist between world and combat


# -----------------------------------------------
# PARTY MEMBER CLASS (NEW EQUIPMENT SYSTEM)
# -----------------------------------------------


class PartyMember:
    def __init__(self, name, job, max_hp, max_mp, attack, magic, defense, level=1):
        self.name = name
        self.job = job
        self.level = level

        # Base stats before gear
        self.base_max_hp = max_hp
        self.base_max_mp = max_mp
        self.base_attack = attack
        self.base_magic = magic
        self.base_defense = defense

        # Current stats
        self.max_hp = max_hp
        self.max_mp = max_mp
        self.attack = attack
        self.magic = magic
        self.defense = defense

        # Equipment slots
        self.weapon = None
        self.armor = None

        # EXP stuff
        self.xp = 0
        self.xp_to_next = 10

        # Battle stats
        self.hp = max_hp
        self.mp = max_mp

    def equip_weapon(self, weapon_name, weapon_data):
        self.weapon = weapon_name
        self.recalc_stats()

    def equip_armor(self, armor_name, armor_data):
        self.armor = armor_name
        self.recalc_stats()

    def recalc_stats(self):
        """
        Recalculate final stats from base stats + equipment bonuses.
        Called whenever we equip something or level up.
        """
        from game_data import WEAPONS, ARMOR

        # Reset to base
        self.attack = self.base_attack
        self.magic = self.base_magic
        self.defense = self.base_defense

        # Apply weapon bonuses
        if self.weapon and self.weapon in WEAPONS:
            w = WEAPONS[self.weapon]
            self.attack += w.get("attack", 0)
            self.defense += w.get("defense", 0)
            self.magic += w.get("magic", 0)

        # Apply armor bonuses
        if self.armor and self.armor in ARMOR:
            a = ARMOR[self.armor]
            self.defense += a.get("defense", 0)
            self.magic += a.get("magic", 0)


# -----------------------------------------------
# LEGACY PARTY DATA (DICT-BASED FOR COMPATIBILITY)
# -----------------------------------------------

# Character data structure: each character has base stats and equipped weapon
party = [
    {
        "name": "Hero",
        "job": "Hero",
        "level": 1,
        "xp": 0,
        "xp_to_next": 20,
        "max_hp": 100,
        "hp": 100,
        "max_mp": 30,
        "mp": 30,
        "base_attack": 15,
        "magic": 8,
        "defense": 5,
        "speed": 10,
        "equipped_weapon": "Bronze Sword",  # weapon ID
        # Computed stats
        "attack": 15,  # base_attack + weapon bonus
    },
    {
        "name": "Ally1",
        "job": "Warrior",
        "level": 1,
        "xp": 0,
        "xp_to_next": 20,
        "max_hp": 80,
        "hp": 80,
        "max_mp": 20,
        "mp": 20,
        "base_attack": 12,
        "magic": 6,
        "defense": 4,
        "speed": 9,
        "equipped_weapon": "Bronze Axe",
        "attack": 12,
    },
    {
        "name": "Ally2",
        "job": "Mage",
        "level": 1,
        "xp": 0,
        "xp_to_next": 20,
        "max_hp": 70,
        "hp": 70,
        "max_mp": 40,
        "mp": 40,
        "base_attack": 8,
        "magic": 14,
        "defense": 3,
        "speed": 11,
        "equipped_weapon": "Wooden Staff",
        "attack": 8,
    },
]


def get_attack(char_data):
    """Calculate total attack including weapon bonus."""
    weapon_id = char_data.get("equipped_weapon")
    if not weapon_id:
        return char_data["base_attack"]

    # Import here to avoid circular dependency
    import game_data as gd

    weapon = gd.ITEMS.get(weapon_id)
    if not weapon:
        return char_data["base_attack"]

    return char_data["base_attack"] + weapon.get("attack_bonus", 0)


def update_attack(char_data):
    """Recalculate and update the attack stat."""
    char_data["attack"] = get_attack(char_data)


def equip_weapon(char_index, weapon_id):
    """Equip a weapon to a character and update their attack stat."""
    if 0 <= char_index < len(party):
        party[char_index]["equipped_weapon"] = weapon_id
        update_attack(party[char_index])


# Initialize attack stats based on equipped weapons
for char in party:
    update_attack(char)
