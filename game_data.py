# game_data.py
"""
Shared game data: inventory, gold, and item definitions.
Both combat.py and world.py should import this module.
"""

# ---- PARTY CURRENCY ----
GOLD = 50  # starting gold, tweak as you like


# -----------------------------------------------
# WEAPON & ARMOR DEFINITIONS (NEW SYSTEM)
# -----------------------------------------------

WEAPONS = {
    "Rusty Sword": {
        "price": 10,
        "attack": 2,
        "defense": 0,
        "allowed_jobs": ["Hero", "Warrior"],
    },
    "Steel Sword": {
        "price": 45,
        "attack": 6,
        "defense": 0,
        "allowed_jobs": ["Hero", "Warrior"],
    },
    "Great Axe": {
        "price": 80,
        "attack": 10,
        "defense": -1,
        "allowed_jobs": ["Warrior"],
    },
    "Wizard Staff": {
        "price": 40,
        "attack": 1,
        "magic": 5,
        "defense": 0,
        "allowed_jobs": ["Mage"],
    },
}

ARMOR = {
    "Cloth Robe": {
        "price": 18,
        "defense": 2,
        "magic": 1,
        "allowed_jobs": ["Mage"],
    },
    "Leather Armor": {
        "price": 35,
        "defense": 4,
        "allowed_jobs": ["Hero", "Warrior"],
    },
    "Iron Plate": {
        "price": 60,
        "defense": 8,
        "allowed_jobs": ["Warrior"],
    },
}

# -----------------------------------------------
# SHOP INVENTORY LISTS
# -----------------------------------------------

ITEM_SHOP_STOCK = [
    ("Potion", 30),
    ("Ether", 60),
]

WEAPON_SHOP_STOCK = [
    "Rusty Sword",
    "Steel Sword",
    "Great Axe",
    "Wizard Staff",
]

ARMOR_SHOP_STOCK = [
    "Cloth Robe",
    "Leather Armor",
    "Iron Plate",
]


# ---- ITEM CATALOG ----
# Use string IDs so we can reference from combat + overworld + shops
ITEMS = {
    # --- Consumables ---
    "Potion": {
        "name": "Potion",
        "type": "consumable",
        "desc": "Restores 50 HP.",
        "hp_restore": 50,
        "price": 30,
        "sell_price": 15,
        "target": "ally",
    },
    "Hi-Potion": {
        "name": "Hi-Potion",
        "type": "consumable",
        "desc": "Restores 100 HP.",
        "hp_restore": 100,
        "price": 90,
        "sell_price": 45,
        "target": "ally",
    },
    "Ether": {
        "name": "Ether",
        "type": "consumable",
        "desc": "Restores 30 MP.",
        "mp_restore": 30,
        "price": 60,
        "sell_price": 30,
        "target": "ally",
    },
    # --- Weapons (Hero) ---
    "Bronze Sword": {
        "name": "Bronze Sword",
        "type": "weapon",
        "slot": "weapon",
        "attack_bonus": 0,
        "job": "Hero",
        "price": 0,
        "desc": "A basic bronze blade for beginners.",
    },
    "Iron Sword": {
        "name": "Iron Sword",
        "type": "weapon",
        "slot": "weapon",
        "attack_bonus": 5,
        "job": "Hero",
        "price": 150,
        "desc": "A sturdy iron sword with decent edge.",
    },
    "Steel Sword": {
        "name": "Steel Sword",
        "type": "weapon",
        "slot": "weapon",
        "attack_bonus": 10,
        "job": "Hero",
        "price": 400,
        "desc": "Forged from fine steel, sharp and deadly.",
    },
    # --- Weapons (Warrior) ---
    "Bronze Axe": {
        "name": "Bronze Axe",
        "type": "weapon",
        "slot": "weapon",
        "attack_bonus": 0,
        "job": "Warrior",
        "price": 0,
        "desc": "A crude bronze axe for training.",
    },
    "Iron Axe": {
        "name": "Iron Axe",
        "type": "weapon",
        "slot": "weapon",
        "attack_bonus": 6,
        "job": "Warrior",
        "price": 160,
        "desc": "A heavy iron axe that cleaves through foes.",
    },
    "Steel Axe": {
        "name": "Steel Axe",
        "type": "weapon",
        "slot": "weapon",
        "attack_bonus": 12,
        "job": "Warrior",
        "price": 450,
        "desc": "Massive steel axe with devastating power.",
    },
    # --- Weapons (Mage) ---
    "Wooden Staff": {
        "name": "Wooden Staff",
        "type": "weapon",
        "slot": "weapon",
        "attack_bonus": 0,
        "magic_bonus": 2,
        "job": "Mage",
        "price": 0,
        "desc": "A simple wooden staff for novice mages.",
    },
    "Silver Staff": {
        "name": "Silver Staff",
        "type": "weapon",
        "slot": "weapon",
        "attack_bonus": 4,
        "magic_bonus": 5,
        "job": "Mage",
        "price": 140,
        "desc": "Silver-tipped staff that channels magic well.",
    },
    "Mystic Staff": {
        "name": "Mystic Staff",
        "type": "weapon",
        "slot": "weapon",
        "attack_bonus": 9,
        "magic_bonus": 10,
        "job": "Mage",
        "price": 380,
        "desc": "An ancient staff pulsing with arcane power.",
    },
}

# Legacy WEAPONS dict for backward compatibility (references ITEMS)
WEAPONS = {k: v for k, v in ITEMS.items() if v.get("type") == "weapon"}


# ---- INVENTORY ----
# key: item_id (e.g. "Potion"), value: quantity
INVENTORY = {
    # Starting consumables
    "Potion": 3,
    "Ether": 0,
    # Starting weapons (characters start with these equipped)
    "Bronze Sword": 1,
    "Bronze Axe": 1,
    "Wooden Staff": 1,
    # Weapons that can be purchased (start at 0)
    "Iron Sword": 0,
    "Steel Sword": 0,
    "Iron Axe": 0,
    "Steel Axe": 0,
    "Silver Staff": 0,
    "Mystic Staff": 0,
}


# ---- Helper functions ----


def get_item_name(item_id: str) -> str:
    return ITEMS.get(item_id, {}).get("name", item_id)


def add_item(item_id: str, qty: int = 1):
    INVENTORY[item_id] = INVENTORY.get(item_id, 0) + qty


def remove_item(item_id: str, qty: int = 1) -> bool:
    """Try to remove qty from inventory. Return True if successful."""
    current = INVENTORY.get(item_id, 0)
    if current < qty:
        return False
    new_qty = current - qty
    if new_qty <= 0:
        INVENTORY.pop(item_id, None)
    else:
        INVENTORY[item_id] = new_qty
    return True


# ---- UNIFIED INTERIOR SYSTEM ----
# Build weapon/armor prices safely
_weapon_prices = {}
for name in WEAPON_SHOP_STOCK:
    if name in WEAPONS:
        _weapon_prices[name] = WEAPONS[name]["price"]

_armor_prices = {}
for name in ARMOR_SHOP_STOCK:
    if name in ARMOR:
        _armor_prices[name] = ARMOR[name]["price"]

INTERIORS = {
    "ITEM_SHOP": {
        "tile_type": "shop",
        "npc_name": "Shopkeeper",
        "npc_welcome": "Welcome! What do you need?",
        "inventory": ["Potion", "Hi-Potion", "Ether"],
        "buy_prices": {"Potion": 30, "Hi-Potion": 90, "Ether": 60},
    },
    "WEAPON_SHOP": {
        "tile_type": "weapon_shop",
        "npc_name": "Armorer",
        "npc_welcome": "Best blades in town!",
        "inventory": [name for name in WEAPON_SHOP_STOCK if name in WEAPONS],
        "buy_prices": _weapon_prices,
    },
    "ARMOR_SHOP": {
        "tile_type": "armor_shop",
        "npc_name": "Armorer",
        "npc_welcome": "Finest armor available!",
        "inventory": [name for name in ARMOR_SHOP_STOCK if name in ARMOR],
        "buy_prices": _armor_prices,
    },
    "INN": {
        "tile_type": "inn",
        "npc_name": "Innkeeper",
        "npc_welcome": "Stay the night? Only 10 gold.",
        "heal_price": 10,
    },
}


# ---- WORLD MAP TILES ----
WORLD_MAP = {
    "TOWN_CENTER": {
        "north": "TOWN_NORTH",
        "south": "SOUTH_FIELD",
        "east": "TOWN_EAST",
        "west": "TOWN_WEST",
        "tile_type": "town",
        "return_to_town": True,
    },
    "TOWN_NORTH": {
        "north": "NORTH_FOREST",
        "south": "TOWN_CENTER",
        "east": None,
        "west": None,
        "tile_type": "town_edge",
    },
    "TOWN_EAST": {
        "west": "TOWN_CENTER",
        "east": "EAST_MOUNTAINS",
        "north": None,
        "south": None,
        "tile_type": "town_edge",
    },
    "TOWN_WEST": {
        "east": "TOWN_CENTER",
        "west": "WEST_LAKE",
        "north": None,
        "south": None,
        "tile_type": "town_edge",
    },
    "NORTH_FOREST": {
        "south": "TOWN_NORTH",
        "north": "DEEP_FOREST",
        "east": None,
        "west": None,
        "tile_type": "forest",
    },
    "SOUTH_FIELD": {
        "north": "TOWN_CENTER",
        "south": "SOUTH_PLAINS",
        "east": None,
        "west": None,
        "tile_type": "field",
    },
    "EAST_MOUNTAINS": {
        "west": "TOWN_EAST",
        "east": None,
        "north": None,
        "south": None,
        "tile_type": "mountain",
    },
    "WEST_LAKE": {
        "east": "TOWN_WEST",
        "west": None,
        "north": None,
        "south": None,
        "tile_type": "lake",
    },
    "DEEP_FOREST": {
        "south": "NORTH_FOREST",
        "north": None,
        "east": None,
        "west": None,
        "tile_type": "forest",
    },
    "SOUTH_PLAINS": {
        "north": "SOUTH_FIELD",
        "south": None,
        "east": None,
        "west": None,
        "tile_type": "field",
    },
}

# World positions for minimap (x, y grid coordinates)
WORLD_POSITIONS = {
    "TOWN_CENTER": (2, 2),
    "TOWN_NORTH": (2, 1),
    "TOWN_EAST": (3, 2),
    "TOWN_WEST": (1, 2),
    "SOUTH_FIELD": (2, 3),
    "NORTH_FOREST": (2, 0),
    "EAST_MOUNTAINS": (4, 2),
    "WEST_LAKE": (0, 2),
    "DEEP_FOREST": (2, -1),
    "SOUTH_PLAINS": (2, 4),
}

# Encounter rates by tile type (chance per step)
ENCOUNTER_RATES = {
    "town": 0.0,
    "town_edge": 0.0,
    "forest": 0.020,  # 2.0% - dangerous
    "field": 0.012,  # 1.2% - safer
    "mountain": 0.025,  # 2.5% - very dangerous
    "lake": 0.008,  # 0.8% - rare
}
