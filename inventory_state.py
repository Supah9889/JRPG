# inventory_state.py

# Shared gold pool
player_gold = 100  # tweak starting value

# Shared item inventory
# IMPORTANT: use the same IDs/names you use in combat & shops
inventory = {
    "Potion": 3,
    "Hi-Potion": 0,
    "Ether": 0,
}

# --- EQUIPMENT DATA ---------------------------------------------------------

# All weapons the game knows about
WEAPON_DEFS = {
    "rusty_sword": {
        "name": "Rusty Sword",
        "price": 0,  # starter gear
        "attack_bonus": 3,
        "for": "Hero",
    },
    "iron_sword": {
        "name": "Iron Sword",
        "price": 120,
        "attack_bonus": 6,
        "for": "Hero",
    },
    "wooden_axe": {
        "name": "Wooden Axe",
        "price": 0,
        "attack_bonus": 4,
        "for": "Warrior",
    },
    "bronze_axe": {
        "name": "Bronze Axe",
        "price": 120,
        "attack_bonus": 7,
        "for": "Warrior",
    },
    "apprentice_staff": {
        "name": "Apprentice Staff",
        "price": 0,
        "attack_bonus": 2,
        "for": "Mage",
    },
    "oak_staff": {
        "name": "Oak Staff",
        "price": 120,
        "attack_bonus": 5,
        "for": "Mage",
    },
}

# Legacy WEAPONS dict for backwards compatibility with existing code
WEAPONS = {
    "Rusty Sword": {
        "job": "Hero",
        "atk_bonus": 0,
        "price": 0,
    },
    "Bronze Sword": {
        "job": "Hero",
        "atk_bonus": 3,
        "price": 50,
    },
    "Iron Sword": {
        "job": "Hero",
        "atk_bonus": 6,
        "price": 120,
    },
    "Wooden Axe": {
        "job": "Warrior",
        "atk_bonus": 2,
        "price": 40,
    },
    "Battle Axe": {
        "job": "Warrior",
        "atk_bonus": 6,
        "price": 130,
    },
    "Apprentice Staff": {
        "job": "Mage",
        "atk_bonus": 1,
        "price": 30,
    },
    "Sage Staff": {
        "job": "Mage",
        "atk_bonus": 4,
        "price": 110,
    },
}

# What each character currently has equipped (by weapon_id).
# These should match what your Status screen currently shows.
equipped_weapons = {
    "Hero": "rusty_sword",
    "Warrior": "wooden_axe",
    "Mage": "apprentice_staff",
}

# Weapon shop stock - what the shop sells (character_name, weapon_id)
WEAPON_SHOP_STOCK = [
    ("Hero", "iron_sword"),
    ("Warrior", "bronze_axe"),
    ("Mage", "oak_staff"),
]

# --- Base stats to keep shops & combat in sync ---
BASE_ATTACK = {
    "Hero": 15,  # Matches combat.py hero.attack
    "Warrior": 12,  # Matches combat.py ally1.attack
    "Mage": 8,  # Matches combat.py ally2.attack
}

# Cost to stay at the inn
INN_COST = 20


# --- EQUIPMENT HELPER FUNCTIONS ---------------------------------------------


def get_weapon_for_actor(actor_name: str):
    """Get the weapon definition for the given actor."""
    wid = equipped_weapons.get(actor_name)
    if not wid:
        return None
    return WEAPON_DEFS.get(wid)


def equip_weapon_on_entity(entity, weapon_id: str):
    """
    Apply the weapon's attack_bonus to the Entity.
    We assume the Entity has .name and .attack.
    We cache their 'base_attack' the first time we see them.
    """
    if not hasattr(entity, "base_attack"):
        entity.base_attack = entity.attack

    weapon = WEAPON_DEFS.get(weapon_id)
    if weapon is None:
        # Failsafe: strip weapon bonus, just use base_attack
        entity.attack = entity.base_attack
        entity.weapon_name = "None"
        equipped_weapons[entity.name] = None
        return

    bonus = weapon.get("attack_bonus", 0)
    entity.attack = entity.base_attack + bonus
    entity.weapon_name = weapon.get("name", weapon_id)
    equipped_weapons[entity.name] = weapon_id


# --- INVENTORY HELPER FUNCTIONS ---------------------------------------------


def add_item(item_id: str, qty: int = 1):
    """Add qty of an item to the inventory."""
    if qty <= 0:
        return
    inventory[item_id] = inventory.get(item_id, 0) + qty


def remove_item(item_id: str, qty: int = 1) -> bool:
    """
    Try to remove qty from inventory.
    Return True if successful, False if not enough quantity.
    """
    current = inventory.get(item_id, 0)
    if current < qty:
        return False
    new_qty = current - qty
    if new_qty <= 0:
        inventory.pop(item_id, None)
    else:
        inventory[item_id] = new_qty
    return True


def get_inventory_list():
    """
    Return a sorted list of (item_id, name, qty, desc)
    for all items in the player's inventory (qty > 0).
    """
    # Import here to avoid circular dependency
    import game_data as gd

    items = []
    for item_id, qty in inventory.items():
        if qty <= 0:
            continue

        data = gd.ITEMS.get(item_id, {})
        name = data.get("name", item_id)
        desc = data.get("desc", "")
        items.append((item_id, name, qty, desc))

    # Sort by name so it's stable and nice to read
    items.sort(key=lambda t: t[1].lower())
    return items
