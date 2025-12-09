import pygame
import sys
import random

import game_data as gd
import inventory_state as inv
import party_state as party_data
from inventory_state import add_item, remove_item
from party_state import party

pygame.init()

# --- Display Setup ---
WIDTH, HEIGHT = 1024, 640
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("JRPG Combat Prototype")
clock = pygame.time.Clock()

# --- Colors ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (60, 60, 60)
YELLOW = (240, 220, 120)
GREEN = (80, 200, 120)
RED = (200, 80, 80)
LOCKED = (130, 130, 130)

# --- Fonts ---
font_big = pygame.font.Font(None, 64)
font_med = pygame.font.Font(None, 32)
font_small = pygame.font.Font(None, 24)


# --- Damage popup constants ---
POPUP_TIME = 60  # frames
POPUP_VY = -2  # vertical velocity

# --- Global state for damage popups ---
damage_popups = []

# --- Post-battle results ---
post_battle_results = None
post_battle_gold = 0
post_battle_items = []  # list of item_ids dropped this battle
end_step = 0
results_anim_state = None

# Inventory GUI state (used during victory screen)
inventory_menu_index = 0
inventory_scroll = 0
INVENTORY_VISIBLE_MAX = 10  # how many items to show at once


# --- Entity class definition ---
class Entity:
    """A combatant (hero or enemy)."""

    def __init__(self, name, max_hp, max_mp, attack, magic, defense, speed):
        self.name = name
        self.max_hp = max_hp
        self.hp = max_hp
        self.max_mp = max_mp
        self.mp = max_mp
        self.attack = attack
        self.magic = magic
        self.defense = defense
        self.speed = speed

        self.statuses = []
        self.defending = False

        # Per-entity progression
        self.level = 1
        self.xp = 0
        self.xp_to_next = 20
        self.job = "Hero"  # Default job

        # Per-battle performance counters
        self.battle_damage_dealt = 0
        self.battle_damage_taken = 0
        self.battle_kills = 0
        self.battle_status_inflicted = 0

    def is_alive(self):
        return self.hp > 0


def sync_party_equipment_from_inventory():
    """Update each party member's attack based on equipped weapons."""
    # Map party name -> object for convenience
    name_to_member = {m.name: m for m in party}

    for char_name, weapon_name in inv.equipped_weapons.items():
        member = name_to_member.get(char_name)
        weapon = inv.WEAPONS.get(weapon_name)

        if member is None or weapon is None:
            continue

        bonus = weapon.get("atk_bonus", 0)
        # Ensure base_attack exists
        if not hasattr(member, "base_attack"):
            member.base_attack = member.attack

        member.weapon_bonus = bonus
        member.attack = member.base_attack + member.weapon_bonus


def sync_party_from_shared_state():
    """Synchronize Entity objects with shared party_state data (equipment, attack, etc.)."""
    for i, entity in enumerate(party):
        if i < len(party_data.party):
            char_data = party_data.party[i]
            # Sync attack stat from equipped weapon
            entity.attack = char_data["attack"]
            # Could also sync HP/MP, level, etc. if needed
            entity.level = char_data.get("level", entity.level)
            entity.xp = char_data.get("xp", entity.xp)
            entity.xp_to_next = char_data.get("xp_to_next", entity.xp_to_next)


def sync_party_to_shared_state():
    """Synchronize shared party_state with Entity objects (HP/MP, XP, level)."""
    for i, entity in enumerate(party):
        if i < len(party_data.party):
            char_data = party_data.party[i]
            char_data["hp"] = entity.hp
            char_data["mp"] = entity.mp
            char_data["level"] = entity.level
            char_data["xp"] = entity.xp
            char_data["xp_to_next"] = entity.xp_to_next
            char_data["max_hp"] = entity.max_hp
            char_data["max_mp"] = entity.max_mp


def get_enemy_popup_position(idx):
    """Return (x, y) for the enemy at slot `idx` (0–2)."""
    field_height = HEIGHT - 240
    field_rect = pygame.Rect(16, 16, WIDTH - 32, field_height)
    mid_y = field_rect.centery
    spacing = 90
    enemy_x = field_rect.x + 120

    if idx == 0:
        return (enemy_x, mid_y - spacing)
    elif idx == 1:
        return (enemy_x, mid_y)
    else:  # idx == 2
        return (enemy_x, mid_y + spacing)


# --- Item definitions (for loot & later inventory GUI) ---
# item_id is the dict key; "name" is what we show to the player.
# Items are now defined in game_data.ITEMS

SKILLS = [
    # ===== HERO SKILLS =====
    {
        "name": "Power Slash",
        "user": "Hero",
        "level_req": 2,
        "mp_cost": 4,
        "target": "single",
        "type": "physical",
        "mult": 1.6,
        "hits": 1,
        "lifesteal": 0.0,
        "execute_threshold": None,
        "execute_mult": 1.0,
        "desc": "Heavy physical strike to one foe.",
    },
    {
        "name": "Shield Breaker",
        "user": "Hero",
        "level_req": 4,
        "mp_cost": 5,
        "target": "single",
        "type": "physical",
        "mult": 1.4,
        "hits": 1,
        "lifesteal": 0.0,
        "execute_threshold": None,
        "execute_mult": 1.0,
        "inflict": "Weaken",
        "inflict_chance": 0.7,
        "status_power": 0,
        "status_duration": 3,
        "desc": "Strike that weakens the foe's attacks.",
    },
    {
        "name": "Shadow Step",
        "user": "Hero",
        "level_req": 8,
        "mp_cost": 6,
        "target": "single",
        "type": "physical",
        "mult": 1.4,
        "hits": 2,
        "lifesteal": 0.0,
        "execute_threshold": None,
        "execute_mult": 1.0,
        "desc": "Quick precise strikes, hits twice.",
    },
    {
        "name": "Dragon Fang",
        "user": "Hero",
        "level_req": 13,
        "mp_cost": 9,
        "target": "single",
        "type": "physical",
        "mult": 2.2,
        "hits": 1,
        "lifesteal": 0.0,
        "execute_threshold": 0.30,  # extra damage below 30% HP
        "execute_mult": 2.0,
        "desc": "Ferocious finisher, stronger on weakened foes.",
    },
    # ===== WARRIOR SKILLS =====
    {
        "name": "Cleave",
        "user": "Warrior",
        "level_req": 3,
        "mp_cost": 4,
        "target": "all",
        "type": "physical",
        "mult": 1.1,
        "hits": 1,
        "lifesteal": 0.0,
        "execute_threshold": None,
        "execute_mult": 1.0,
        "desc": "Wide swing that hits all enemies.",
    },
    {
        "name": "Guard Stance",
        "user": "Warrior",
        "level_req": 5,
        "mp_cost": 3,
        "target": "single",
        "type": "physical",
        "mult": 0.0,
        "hits": 0,
        "lifesteal": 0.0,
        "execute_threshold": None,
        "execute_mult": 1.0,
        "inflict": "Weaken",
        "inflict_chance": 0.0,
        "status_power": 0,
        "status_duration": 0,
        "desc": "Focus on defense (use Defend command instead for now).",
    },
    {
        "name": "Blood Wave",
        "user": "Warrior",
        "level_req": 7,
        "mp_cost": 8,
        "target": "all",
        "type": "magic",  # dark physical-ish magic
        "mult": 1.3,
        "hits": 1,
        "lifesteal": 0.25,
        "execute_threshold": None,
        "execute_mult": 1.0,
        "inflict": "Bleed",
        "inflict_chance": 0.9,
        "status_power": 4,
        "status_duration": 3,
        "desc": "Crimson wave that bleeds all foes and restores some HP.",
    },
    {
        "name": "War Cry",
        "user": "Warrior",
        "level_req": 11,
        "mp_cost": 6,
        "target": "all",
        "type": "magic",
        "mult": 0.0,
        "hits": 0,
        "lifesteal": 0.0,
        "execute_threshold": None,
        "execute_mult": 1.0,
        "inflict": "Weaken",
        "inflict_chance": 0.8,
        "status_power": 0,
        "status_duration": 3,
        "desc": "Battle roar that weakens enemies' attacks.",
    },
    # ===== MAGE SKILLS =====
    {
        "name": "Soul Flame",
        "user": "Mage",
        "level_req": 2,
        "mp_cost": 5,
        "target": "single",
        "type": "magic",
        "mult": 1.8,
        "hits": 1,
        "lifesteal": 0.0,
        "execute_threshold": None,
        "execute_mult": 1.0,
        "inflict": "Poison",
        "inflict_chance": 0.8,
        "status_power": 3,
        "status_duration": 3,
        "desc": "Flame that burns and poisons a target.",
    },
    {
        "name": "Frost Lance",
        "user": "Mage",
        "level_req": 4,
        "mp_cost": 6,
        "target": "single",
        "type": "magic",
        "mult": 1.9,
        "hits": 1,
        "lifesteal": 0.0,
        "execute_threshold": None,
        "execute_mult": 1.0,
        "desc": "Piercing ice strike with high damage.",
    },
    {
        "name": "Nightfall",
        "user": "Mage",
        "level_req": 7,
        "mp_cost": 10,
        "target": "all",
        "type": "magic",
        "mult": 1.5,
        "hits": 1,
        "lifesteal": 0.0,
        "execute_threshold": None,
        "execute_mult": 1.0,
        "inflict": "Weaken",
        "inflict_chance": 0.6,
        "status_power": 0,
        "status_duration": 3,
        "desc": "Darkness falls, sometimes weakening all foes.",
    },
    {
        "name": "Crimson Eclipse",
        "user": "Mage",
        "level_req": 12,
        "mp_cost": 16,
        "target": "all",
        "type": "magic",
        "mult": 2.1,
        "hits": 1,
        "lifesteal": 0.4,
        "execute_threshold": None,
        "execute_mult": 1.0,
        "inflict": "Curse",
        "inflict_chance": 0.5,
        "status_power": 0,
        "status_duration": 3,
        "desc": "Devastating spell that may curse and heals the caster.",
    },
]


def spawn_enemy_damage_popup(enemy, amount, color=YELLOW):
    """Create a floating damage popup for the given enemy."""
    try:
        idx = enemies.index(enemy)
    except ValueError:
        return  # enemy not found (shouldn't happen, but be safe)

    x, y = get_enemy_popup_position(idx)
    damage_popups.append(
        {
            "x": x,
            "y": y,
            "text": str(amount),
            "color": color,
            "timer": POPUP_TIME,
            "vy": POPUP_VY,
        }
    )


def update_damage_popups():
    """Move popups and remove expired ones."""
    global damage_popups
    for p in damage_popups:
        p["y"] += p["vy"]
        p["timer"] -= 1
    damage_popups = [p for p in damage_popups if p["timer"] > 0]


def use_item_in_battle(user: Entity, item_id: str, target: Entity) -> bool:
    """Apply an item effect in battle. Returns True if the turn is consumed."""
    if inv.inventory.get(item_id, 0) <= 0:
        add_message("No more of that item!")
        return False

    item = gd.ITEMS.get(item_id)
    if not item:
        add_message("Nothing happens...")
        return False

    name = item.get("name", item_id)
    hp_restore = item.get("hp_restore", 0)
    mp_restore = item.get("mp_restore", 0)

    # Check if target is valid
    if not target.is_alive():
        add_message(f"{target.name} cannot use items right now.")
        return False

    # Apply HP restoration
    if hp_restore > 0:
        old_hp = target.hp
        target.hp = min(target.max_hp, target.hp + hp_restore)
        healed = target.hp - old_hp

        if healed <= 0:
            add_message(f"{target.name} is already at full HP.")
            # Still consume the item even if no healing occurred

        add_message(f"{user.name} uses {name} on {target.name}, restoring {healed} HP!")

    # Apply MP restoration
    if mp_restore > 0:
        old_mp = target.mp
        target.mp = min(target.max_mp, target.mp + mp_restore)
        restored = target.mp - old_mp

        if restored > 0:
            add_message(f"{target.name} restored {restored} MP!")

    # If item does nothing
    if hp_restore == 0 and mp_restore == 0:
        add_message(f"{user.name} uses {name}, but nothing special happens...")

    # Consume 1 item using game_data's remove function
    gd.remove_item(item_id, 1)

    return True


# Enemies will be a list of Entity objects
enemies = []

# --- Economy / inventory ---
# Now using inventory_state.INVENTORY and inventory_state.player_gold


def get_inventory_items():
    """Return a sorted list of (item_id, qty) that the party actually has."""
    items = []
    for item_id, qty in inv.inventory.items():
        if qty > 0 and item_id in gd.ITEMS:
            items.append((item_id, qty))

    # sort by item name for a stable menu
    items.sort(key=lambda pair: gd.ITEMS[pair[0]]["name"])
    return items


# --- Equipment helpers ---


def is_weapon_item(item_id: str) -> bool:
    """Check if an item_id is a weapon."""
    data = gd.ITEMS.get(item_id)
    return bool(data and data.get("type") == "weapon")


def get_weapon_attack_bonus(item_id: str) -> int:
    """Get the attack bonus from a weapon item."""
    data = gd.ITEMS.get(item_id)
    if not data:
        return 0
    return int(data.get("attack_bonus", 0))


def get_weapon_magic_bonus(item_id: str) -> int:
    """Get the magic bonus from a weapon item."""
    data = gd.ITEMS.get(item_id)
    if not data:
        return 0
    return int(data.get("magic_bonus", 0))


def get_equipped_weapon(actor) -> str | None:
    """Return currently equipped weapon item_id or None."""
    return getattr(actor, "equipped_weapon", None)


def equip_weapon(actor, new_item_id: str | None):
    """
    Equip a new weapon on this actor.

    - Removes the old weapon's ATK/MAG bonus from stats.
    - Adds the new weapon's ATK/MAG bonus.
    - Sets actor.equipped_weapon = new_item_id.
    """
    if new_item_id is not None and not is_weapon_item(new_item_id):
        # Not actually a weapon; ignore.
        return

    current = get_equipped_weapon(actor)
    if current == new_item_id:
        return  # nothing to change

    # Remove old bonuses
    if current is not None:
        actor.attack -= get_weapon_attack_bonus(current)
        actor.magic -= get_weapon_magic_bonus(current)

    # Add new bonuses
    if new_item_id is not None:
        actor.attack += get_weapon_attack_bonus(new_item_id)
        actor.magic += get_weapon_magic_bonus(new_item_id)

    actor.equipped_weapon = new_item_id


# --- Party creation (moved here after equip_weapon is defined) ---
hero = Entity("Hero", max_hp=100, max_mp=30, attack=12, magic=8, defense=5, speed=10)
hero.job = "Hero"
hero.level = 1
hero.xp = 0
hero.xp_to_next = 10
hero.statuses = []
hero.equipped_weapon = None

ally1 = Entity("Warrior", max_hp=80, max_mp=20, attack=15, magic=6, defense=4, speed=9)
ally1.job = "Warrior"
ally1.level = 1
ally1.xp = 0
ally1.xp_to_next = 10
ally1.statuses = []
ally1.equipped_weapon = None

ally2 = Entity("Mage", max_hp=70, max_mp=40, attack=8, magic=14, defense=3, speed=11)
ally2.job = "Mage"
ally2.level = 1
ally2.xp = 0
ally2.xp_to_next = 10
ally2.statuses = []
ally2.equipped_weapon = None

party = [hero, ally1, ally2]

# Equip starting weapons (these are already in inventory from game_data.py)
equip_weapon(hero, "Bronze Sword")
equip_weapon(ally1, "Bronze Axe")
equip_weapon(ally2, "Wooden Staff")


# --- Battle state ---
MENU_OPTIONS = ["Attack", "Magic", "Skill", "Defend", "Run"]
menu_index = 0

# Jobs that should default to Magic-first in the command list
MAGIC_JOBS = {"Mage", "Wizard", "Sorcerer", "Cleric"}


def get_command_options(actor: Entity):
    """
    Return the command list for the current actor.

    - Physical/normal jobs: Attack, then Magic
    - Magic jobs: Magic, then Attack
    """
    base = ["Attack", "Magic", "Skill", "Item", "Defend", "Run"]

    job = getattr(actor, "job", "Hero")

    # Treat anything in MAGIC_JOBS, or with clearly higher magic than attack,
    # as a caster who should have Magic on top.
    if job in MAGIC_JOBS or actor.magic > actor.attack:
        return ["Magic", "Attack", "Skill", "Item", "Defend", "Run"]

    return base


# --- Battle state ---
# States: PLAYER_CHOICE, SKILL_MENU, ITEM_MENU, TARGET_SELECT, ITEM_TARGET, ENEMY_TURN, END, PAUSE_MENU
battle_state = "PLAYER_CHOICE"
message_log = []
winner = None

# Pause menu state
pause_menu_index = 0
PAUSE_OPTIONS = ["Resume", "Quit"]

# Targeting / skills state
target_index = 0
pending_action = None  # "Attack", "Magic", "SKILL", "ITEM"
selected_skill = None
selected_item = None
skill_index = 0
skill_scroll = 0  # for scrolling the skill list later
SKILL_VISIBLE_MAX = 5  # how many skills to show at once

item_index = 0
item_scroll = 0  # for scrolling the item list later
ITEM_VISIBLE_MAX = 5  # how many items to show at once

current_hero_index = 0  # which party member is currently acting
party_acted_this_round = set()

ally_target_index = 0  # which ally we're targeting with an item

# Hero = physical finisher, Warrior = big AoE / bleed, Mage = nasty magic & debuffs.


def get_actor_skills(actor: Entity):
    """Return all skills this actor is allowed to use (ignoring level)."""
    job = getattr(actor, "job", "Hero")
    available = []
    for s in SKILLS:
        user = s.get("user", "Any")
        if user in ("Any", job):
            available.append(s)
    return available


def level_up_if_needed(actor: Entity):
    """
    Check if this actor should level up based on their own XP.
    Only the main Hero gets stat increases; others just unlock skills.
    """
    leveled_up = False

    while actor.xp >= actor.xp_to_next:
        actor.xp -= actor.xp_to_next
        actor.level += 1
        actor.xp_to_next += 10  # simple curve

        # Only Hero's stats grow
        if actor is hero or getattr(actor, "job", "") == "Hero":
            actor.max_hp += 10
            actor.max_mp += 3
            actor.attack += 4
            actor.magic += 3
            actor.defense += 2

        # Full heal on level-up
        actor.hp = actor.max_hp
        actor.mp = actor.max_mp

        add_message(f"{actor.name} reached level {actor.level}!")
        if actor is hero:
            add_message("Hero's stats increased and HP/MP restored!")
        else:
            add_message("HP/MP restored!")

        leveled_up = True

    return leveled_up


def add_message(text: str):
    """Add a line to the battle log (max 6 lines)."""
    global message_log
    message_log.append(text)
    if len(message_log) > 6:
        message_log = message_log[-6:]


def calculate_physical_damage(attacker: Entity, defender: Entity) -> int:
    base = attacker.attack + random.randint(-2, 2)

    # Non-damage status: Weaken reduces outgoing physical damage
    if has_status(attacker, "Weaken"):
        base = int(base * 0.6)  # 40% reduction

    mitigated = base - defender.defense

    if defender.defending:
        mitigated = mitigated // 2

    return max(1, mitigated)


def calculate_magic_damage(attacker: Entity, defender: Entity) -> int:
    base = attacker.magic + random.randint(-3, 3)

    # Weaken + Curse both hurt magic damage
    if has_status(attacker, "Weaken"):
        base = int(base * 0.7)
    if has_status(attacker, "Curse"):
        base = int(base * 0.7)

    mitigated = base - defender.defense // 2
    return max(3, mitigated)


# --- Status effect helpers ---


def add_status(target: Entity, name: str, duration: int, power: int = 0):
    """Apply or refresh a status on a target."""
    for s in target.statuses:
        if s["name"] == name:
            s["duration"] = max(s["duration"], duration)
            s["power"] = max(s["power"], power)
            return

    target.statuses.append(
        {
            "name": name,
            "duration": duration,
            "power": power,
        }
    )


def has_status(entity: Entity, name: str) -> bool:
    """Return True if this entity has a status with the given name."""
    return any(s["name"] == name for s in entity.statuses)


def get_status_codes(entity: Entity) -> str:
    """Return a short comma-separated code string like 'PSN, BLD'."""
    if not entity.statuses:
        return ""

    abbrev_map = {
        "Poison": "PSN",
        "Bleed": "BLD",
        "Weaken": "WKN",
        "Stun": "STN",
        "Curse": "CRS",
    }

    codes = []
    for s in entity.statuses:
        code = abbrev_map.get(s["name"], s["name"][:3].upper())
        if code not in codes:
            codes.append(code)

    return ", ".join(codes)


def process_statuses_on_enemies():
    """Tick statuses on all enemies (damage over time, etc.)."""
    global enemies

    for e in enemies:
        if not e.is_alive():
            continue

        remaining_statuses = []
        for s in e.statuses:
            name = s["name"]
            duration = s["duration"]
            power = s["power"]

            # Damage-over-time statuses
            if name == "Poison":
                dmg = max(1, power)
                e.hp = max(0, e.hp - dmg)
                add_message(f"{e.name} suffers {dmg} poison damage!")

            elif name == "Bleed":
                dmg = max(1, power)
                e.hp = max(0, e.hp - dmg)
                add_message(f"{e.name} bleeds for {dmg} damage!")

            # Decrease duration and keep if still active
            duration -= 1
            if duration > 0 and e.is_alive():
                s["duration"] = duration
                remaining_statuses.append(s)
            else:
                if e.is_alive():
                    add_message(f"{e.name} is no longer affected by {name.lower()}.")

        e.statuses = remaining_statuses


def process_statuses_on_party():
    """Tick statuses on all living party members (damage over time, etc.)."""
    for member in party:
        if not member.is_alive():
            continue

        remaining_statuses = []
        for s in member.statuses:
            name = s["name"]
            duration = s["duration"]
            power = s["power"]

            if name == "Poison":
                dmg = max(1, power)
                member.hp = max(0, member.hp - dmg)
                add_message(f"{member.name} suffers {dmg} poison damage!")

            elif name == "Bleed":
                dmg = max(1, power)
                member.hp = max(0, member.hp - dmg)
                add_message(f"{member.name} bleeds for {dmg} damage!")

            duration -= 1
            if duration > 0 and member.is_alive():
                s["duration"] = duration
                remaining_statuses.append(s)
            else:
                if member.is_alive():
                    add_message(
                        f"{member.name} is no longer affected by {name.lower()}."
                    )

        member.statuses = remaining_statuses


def maybe_apply_status_from_skill(skill: dict, target: Entity, source: Entity = None):
    """Roll chance to apply a status from a skill to a target.

    If `source` is provided, increment its `battle_status_inflicted` counter
    when the status is successfully applied.
    """
    if target is None or not target.is_alive():
        return

    name = skill.get("inflict")
    if not name:
        return

    chance = skill.get("inflict_chance", 0.0)
    duration = skill.get("status_duration", 0)
    power = skill.get("status_power", 0)

    if duration <= 0 or chance <= 0.0:
        return

    if random.random() <= chance:
        add_status(target, name, duration, power)
        add_message(f"{target.name} is afflicted with {name.lower()}!")
        if source is not None:
            setattr(
                source,
                "battle_status_inflicted",
                getattr(source, "battle_status_inflicted", 0) + 1,
            )

        # --- Enemy spawn definitions (level gating + rarity) ---


ENEMY_BLUEPRINTS = [
    # type,              min_level, weight (higher = more common)
    {"type": "Slime", "min_level": 1, "weight": 40},
    {"type": "Bat", "min_level": 2, "weight": 30},
    {"type": "Cultist", "min_level": 3, "weight": 25},
    {"type": "Ghoul", "min_level": 4, "weight": 20},
    {"type": "Vampire Thrall", "min_level": 6, "weight": 15},
    {"type": "Shadow Fiend", "min_level": 8, "weight": 10},
]

# Simple per-enemy loot table: enemy name -> list of (item_id, drop_chance)
ENEMY_LOOT_TABLE = {
    "Slime": [
        ("potion", 0.30),  # 30% chance for 1 Potion
    ],
    "Bat": [
        ("potion", 0.15),
    ],
    "Cultist": [
        ("potion", 0.40),
    ],
    "Ghoul": [
        ("potion", 0.20),
    ],
    "Vampire Thrall": [
        ("potion", 0.50),
    ],
    "Shadow Fiend": [
        ("potion", 0.60),
    ],
}

# --- Multiple enemy types ---


def create_enemy(enemy_type: str) -> Entity:
    """Factory for different enemy types."""
    if enemy_type == "Slime":
        e = Entity(
            "Slime",
            max_hp=35,
            max_mp=0,
            attack=8,
            magic=0,
            defense=2,
            speed=5,
        )
        e.xp_value = 10
        e.gold_min = 3
        e.gold_max = 6
        e.drops = [("Potion", 0.20)]  # 20% chance for a Potion

    elif enemy_type == "Bat":
        # Fast, fragile, slightly trickier damage
        e = Entity(
            "Bat",
            max_hp=25,
            max_mp=0,
            attack=9,
            magic=0,
            defense=1,
            speed=14,
        )
        e.xp_value = 14
        e.gold_min = 5
        e.gold_max = 9
        e.drops = [("Potion", 0.10)]

    elif enemy_type == "Cultist":
        # Tougher, hits a little harder
        e = Entity(
            "Cultist",
            max_hp=45,
            max_mp=10,
            attack=11,
            magic=0,
            defense=3,
            speed=8,
        )
        e.xp_value = 20
        e.gold_min = 8
        e.gold_max = 15
        e.drops = [("Potion", 0.25)]

    elif enemy_type == "Ghoul":
        # Chunky HP, decent attack, kinda slow
        e = Entity(
            "Ghoul",
            max_hp=60,
            max_mp=0,
            attack=12,
            magic=0,
            defense=3,
            speed=7,
        )
        e.xp_value = 28
        e.gold_min = 10
        e.gold_max = 20
        e.drops = [("Potion", 0.15)]

    elif enemy_type == "Vampire Thrall":
        # Faster, stronger, “elite” feeling
        e = Entity(
            "Vampire Thrall",
            max_hp=55,
            max_mp=5,
            attack=14,
            magic=5,
            defense=4,
            speed=12,
        )
        e.xp_value = 35
        e.gold_min = 15
        e.gold_max = 25
        e.drops = [("Potion", 0.30)]

    elif enemy_type == "Shadow Fiend":
        e = Entity(
            "Shadow Fiend",
            max_hp=40,
            max_mp=15,
            attack=9,
            magic=16,
            defense=2,
            speed=13,
        )
        e.xp_value = 40
        e.gold_min = 20
        e.gold_max = 30
        e.drops = [("Potion", 0.35)]

    else:
        e = Entity(
            "Unknown",
            max_hp=30,
            max_mp=0,
            attack=7,
            magic=0,
            defense=2,
            speed=5,
        )
        e.xp_value = 8
        e.gold_min = 3
        e.gold_max = 6
        e.drops = []

    # --- Scale enemy by Hero's level so they don't fall behind ---
    scale = max(0, get_party_main_level() - 1)  # no bonus at level 1
    if scale > 0:
        e.max_hp += 5 * scale
        e.hp = e.max_hp
        e.attack += 1 * scale
        e.defense += 1 * (scale // 2)

    return e


def get_party_main_level() -> int:
    """Return the party's main level used for gating enemy spawns.

    Currently this is the main `hero`'s level. Kept as a helper to allow
    future changes (e.g. highest-level member) without touching spawn logic.
    """
    return getattr(hero, "level", 1)


def pick_enemy_group():
    """Choose a random group of 1–3 enemies, gated by hero level."""
    group = []

    # Random group size between 1 and 3
    group_size = random.randint(1, 3)

    # Which enemy types are allowed at this level?
    candidates = [
        bp for bp in ENEMY_BLUEPRINTS if get_party_main_level() >= bp["min_level"]
    ]
    if not candidates:
        # Failsafe: always at least Slime
        candidates = [ENEMY_BLUEPRINTS[0]]

    weights = [bp["weight"] for bp in candidates]

    for _ in range(group_size):
        bp = random.choices(candidates, weights=weights, k=1)[0]
        group.append(create_enemy(bp["type"]))

    return group


def grant_loot_for_group(group):
    """Return (gold_gain, item_drops_list) for a defeated enemy group.

    item_drops_list: list of item_id strings that were dropped
    """
    gold_gain = 0
    item_drops = []

    for e in group:
        gmin = getattr(e, "gold_min", 1)
        gmax = getattr(e, "gold_max", 3)
        if gmax < gmin:
            gmax = gmin
        gold_gain += random.randint(gmin, gmax)

        # look up loot table for this enemy's name
        loot_entries = ENEMY_LOOT_TABLE.get(e.name, [])
        for item_id, chance in loot_entries:
            if random.random() <= chance:
                item_drops.append(item_id)

    return gold_gain, item_drops


def grant_rewards_for_group(group):
    """Compute total XP, gold, and item drops for a defeated enemy group."""
    total_xp = 0
    total_gold = 0
    drops = []

    for e in group:
        total_xp += getattr(e, "xp_value", 5)

        gmin = getattr(e, "gold_min", 1)
        gmax = getattr(e, "gold_max", 3)
        if gmax < gmin:
            gmax = gmin
        total_gold += random.randint(gmin, gmax)

        for item_id, chance in getattr(e, "drops", []):
            if random.random() <= chance:
                drops.append(item_id)

    return total_xp, total_gold, drops


def apply_gold_and_loot(gold_amount: int, items: list[str]):
    """Apply rewards to the party's global gold + inventory."""
    inv.player_gold += max(0, gold_amount)
    for item_id in items:
        add_item(item_id)


def distribute_xp_among_party(total_xp: int):
    """Distribute `total_xp` to the living party members using an
    80/20 split: 80% baseline evenly among living members, 20% as a
    performance bonus (damage dealt, kills, statuses inflicted).

    Sets the global `post_battle_results` list for display by the UI
    and initializes `results_anim_state` used to animate the results.
    """
    global post_battle_results, results_anim_state

    living = [m for m in party if m.is_alive()]
    if not living:
        post_battle_results = []
        results_anim_state = None
        return

    baseline = int(total_xp * 0.8)
    bonus_pool = total_xp - baseline

    base_share = baseline // len(living)
    base_remainder = baseline - base_share * len(living)

    # Compute performance scores
    scores = []
    total_score = 0
    for m in living:
        dmg = getattr(m, "battle_damage_dealt", 0)
        kills = getattr(m, "battle_kills", 0)
        statuses = getattr(m, "battle_status_inflicted", 0)
        score = dmg + (kills * 15) + (statuses * 8)
        scores.append(score)
        total_score += score

    # Allocate XP
    results = []
    # Pre-calc bonus shares (may be zero if nobody scored)
    bonus_shares = [0] * len(living)
    if total_score > 0 and bonus_pool > 0:
        for i, s in enumerate(scores):
            bonus_shares[i] = int(bonus_pool * (s / total_score))

        # Fix rounding remainder by giving to highest scorers
        assigned = sum(bonus_shares)
        remain = bonus_pool - assigned
        if remain > 0:
            idxs = sorted(range(len(living)), key=lambda i: scores[i], reverse=True)
            for j in range(remain):
                bonus_shares[idxs[j % len(idxs)]] += 1

    for i, m in enumerate(living):
        # Snapshot BEFORE awarding XP so we can animate correctly
        level_before = m.level
        xp_before = m.xp
        xp_to_next_before = m.xp_to_next

        xp_gain = base_share + (1 if i < base_remainder else 0) + bonus_shares[i]

        m.xp += xp_gain
        level_up_if_needed(m)

        results.append(
            {
                "name": m.name,
                "xp": xp_gain,
                "level_before": level_before,
                "level_after": m.level,
                "score": scores[i],
                "xp_before": xp_before,
                "xp_to_next_before": xp_to_next_before,
            }
        )

    # Sort by performance score (MVP at top)
    post_battle_results = sorted(results, key=lambda r: r["score"], reverse=True)

    # --- Initialize animation state for odometer + bar fill ---
    results_anim_state = []
    for r in post_battle_results:
        # XP needed *from this battle* to finish current level
        needed_this_level = r["xp_to_next_before"] - r["xp_before"]
        if needed_this_level <= 0:
            # Failsafe: if already at threshold, treat as needing full bar
            needed_this_level = r["xp_to_next_before"]

        results_anim_state.append(
            {
                # 0 = counting numbers, 1 = filling bars, 2 = finished
                "phase": 0,
                "xp_display": 0,  # shown "+XX XP" value
                "remaining_xp": r["xp"],  # XP left to pump into bars
                "segment_cap": needed_this_level,  # XP to fill this bar segment
                "segment_progress": 0,  # how much of this segment is filled
                "anim_level": r["level_before"],
                "xp_to_next_for_level": r["xp_to_next_before"],
            }
        )


def update_results_animation():
    """Animate XP numbers and XP bars during the Battle Results screen."""
    global results_anim_state

    if battle_state != "END" or winner != "HERO" or end_step != 1:
        return
    if not post_battle_results or not results_anim_state:
        return

    for r, st in zip(post_battle_results, results_anim_state):
        # --- Phase 0: odometer-style XP count ---
        if st["phase"] == 0:
            target = r["xp"]
            if st["xp_display"] < target:
                # Speed: about ~30 frames to reach the final value
                step = max(1, target // 30)
                st["xp_display"] = min(target, st["xp_display"] + step)
            else:
                st["phase"] = 1  # move on to bar animation

        # --- Phase 1: bar fill with rollover on level-ups ---
        elif st["phase"] == 1:
            if st["remaining_xp"] <= 0:
                st["phase"] = 2
                continue

            # How fast the bar fills (bigger cap -> larger step)
            step = max(1, st["segment_cap"] // 40)
            step = min(
                step,
                st["remaining_xp"],
                st["segment_cap"] - st["segment_progress"],
            )

            st["segment_progress"] += step
            st["remaining_xp"] -= step

            # Reached the end of this level's bar segment
            if st["segment_progress"] >= st["segment_cap"]:
                if st["remaining_xp"] > 0:
                    # LEVEL UP: odometer-style bar reset
                    st["anim_level"] += 1
                    st["xp_to_next_for_level"] += 10  # same curve as level_up_if_needed
                    st["segment_cap"] = st["xp_to_next_for_level"]
                    st["segment_progress"] = 0  # bar back to empty, ready to refill
                else:
                    st["phase"] = 2

        # Phase 2: finished – nothing else to animate


def all_enemies_dead():
    return all(not e.is_alive() for e in enemies)


def get_first_alive_enemy():
    for e in enemies:
        if e.is_alive():
            return e
    return None


def get_next_alive_index(current):
    """Get the next alive enemy index (wraps around)."""
    if not enemies:
        return 0
    n = len(enemies)
    for i in range(1, n + 1):
        idx = (current + i) % n
        if enemies[idx].is_alive():
            return idx
    return current


def get_prev_alive_index(current):
    """Get the previous alive enemy index (wraps around)."""
    if not enemies:
        return 0
    n = len(enemies)
    for i in range(1, n + 1):
        idx = (current - i) % n
        if enemies[idx].is_alive():
            return idx
    return current


def living_party_members():
    """Return a list of all living party members."""
    return [m for m in party if m.is_alive()]


def all_party_dead():
    return all(not m.is_alive() for m in party)


def get_next_living_hero_index(current):
    """Next living hero index (wraps around)."""
    if not party:
        return 0
    n = len(party)
    for i in range(1, n + 1):
        idx = (current + i) % n
        if party[idx].is_alive():
            return idx
    return current


def get_active_hero():
    """Convenience: who is currently acting."""
    return party[current_hero_index]


def hero_take_action(actor, choice, target=None):
    """Resolve the hero's chosen action for the given party member."""
    global battle_state, winner, enemies, selected_skill, selected_item

    actor_idx = party.index(actor)

    # If this hero is stunned, they lose their turn
    if has_status(actor, "Stun"):
        add_message(f"{actor.name} is stunned and can't move!")
        actor.defending = False

        # Still tick enemy statuses, then move turn forward
        process_statuses_on_enemies()
        if battle_state != "END":
            _advance_turn_after_hero(actor_idx)
        return

    # Resolve target for normal Attack/Magic (SKILL resolves differently)
    if choice in ("Attack", "Magic", "SKILL"):
        if choice != "SKILL" and target is None:
            target = get_first_alive_enemy()
        if choice != "SKILL" and target is None:
            return  # no enemies to hit

    if choice == "Attack":
        dmg = calculate_physical_damage(actor, target)
        target.hp = max(0, target.hp - dmg)
        add_message(f"{actor.name} attacks {target.name} for {dmg} damage!")
        spawn_enemy_damage_popup(target, dmg)
        # Track performance
        actor.battle_damage_dealt = getattr(actor, "battle_damage_dealt", 0) + dmg
        target.battle_damage_taken = getattr(target, "battle_damage_taken", 0) + dmg
        if target.hp == 0:
            actor.battle_kills = getattr(actor, "battle_kills", 0) + 1
        actor.defending = False

    elif choice == "Magic":
        cost = 5
        if actor.mp < cost:
            add_message(f"{actor.name} tried to cast a spell, but is out of MP!")
        else:
            actor.mp -= cost
            dmg = calculate_magic_damage(actor, target)
            target.hp = max(0, target.hp - dmg)
            add_message(f"{actor.name} casts Fire on {target.name} for {dmg} damage!")
            spawn_enemy_damage_popup(target, dmg)
            # Track performance
            actor.battle_damage_dealt = getattr(actor, "battle_damage_dealt", 0) + dmg
            target.battle_damage_taken = getattr(target, "battle_damage_taken", 0) + dmg
            if target.hp == 0:
                actor.battle_kills = getattr(actor, "battle_kills", 0) + 1
        actor.defending = False

    elif choice == "SKILL":
        skill = selected_skill
        if skill is None:
            add_message("No skill selected.")
        elif actor.level < skill["level_req"]:
            # Skill unlocks are based on the acting character's level
            add_message(f"{actor.name} hasn't learned {skill['name']} yet!")
        elif actor.mp < skill["mp_cost"]:
            add_message(f"Not enough MP to use {skill['name']}!")
        else:
            actor.mp -= skill["mp_cost"]

            hits = skill.get("hits", 1)
            lifesteal_frac = skill.get("lifesteal", 0.0)
            exec_thresh = skill.get("execute_threshold", None)
            exec_mult = skill.get("execute_mult", 1.0)

            total_damage_done = 0

            # --- AoE skills: hit all living enemies once ---
            if skill["target"] == "all":
                for e in enemies:
                    if not e.is_alive():
                        continue

                    # choose base damage type
                    if skill["type"] == "physical":
                        base = calculate_physical_damage(actor, e)
                    else:
                        base = calculate_magic_damage(actor, e)

                    # execute bonus (per target)
                    if exec_thresh is not None and e.max_hp > 0:
                        if e.hp / e.max_hp <= exec_thresh:
                            base = int(base * exec_mult)

                    dmg = int(base * skill["mult"])
                    e.hp = max(0, e.hp - dmg)
                    total_damage_done += dmg

                    add_message(
                        f"{actor.name} uses {skill['name']} on {e.name} for {dmg} damage!"
                    )
                    spawn_enemy_damage_popup(e, dmg)
                    # Track performance per target
                    actor.battle_damage_dealt = (
                        getattr(actor, "battle_damage_dealt", 0) + dmg
                    )
                    e.battle_damage_taken = getattr(e, "battle_damage_taken", 0) + dmg
                    if e.hp == 0:
                        actor.battle_kills = getattr(actor, "battle_kills", 0) + 1
                    maybe_apply_status_from_skill(skill, e, actor)

            else:
                # --- Single-target skills (support multi-hit) ---
                if target is None or not target.is_alive():
                    target = get_first_alive_enemy()

                for hit in range(hits):
                    if target is None or not target.is_alive():
                        target = get_first_alive_enemy()
                        if target is None:
                            break  # nobody left to hit

                    if skill["type"] == "physical":
                        base = calculate_physical_damage(actor, target)
                    else:
                        base = calculate_magic_damage(actor, target)

                    # Execute bonus
                    if exec_thresh is not None and target.max_hp > 0:
                        if target.hp / target.max_hp <= exec_thresh:
                            base = int(base * exec_mult)

                    dmg = int(base * skill["mult"])
                    target.hp = max(0, target.hp - dmg)
                    total_damage_done += dmg

                    if hits > 1:
                        add_message(
                            f"{actor.name}'s {skill['name']} hits {target.name} "
                            f"for {dmg} damage! (hit {hit + 1})"
                        )
                    else:
                        add_message(
                            f"{actor.name} uses {skill['name']} on {target.name} "
                            f"for {dmg} damage!"
                        )

                    spawn_enemy_damage_popup(target, dmg)
                    # Track performance per hit/target
                    actor.battle_damage_dealt = (
                        getattr(actor, "battle_damage_dealt", 0) + dmg
                    )
                    target.battle_damage_taken = (
                        getattr(target, "battle_damage_taken", 0) + dmg
                    )
                    if target.hp == 0:
                        actor.battle_kills = getattr(actor, "battle_kills", 0) + 1
                    # apply status on each hit/target
                    maybe_apply_status_from_skill(skill, target, actor)

            # --- Lifesteal healing ---
            if lifesteal_frac > 0 and total_damage_done > 0:
                heal = int(total_damage_done * lifesteal_frac)
                if heal > 0:
                    old_hp = actor.hp
                    actor.hp = min(actor.max_hp, actor.hp + heal)
                    actual = actor.hp - old_hp
                    if actual > 0:
                        add_message(f"{actor.name} absorbs {actual} HP!")

        actor.defending = False
        selected_skill = None

    elif choice == "ITEM":
        item_id = selected_item
        if item_id is None:
            add_message("No item selected.")
        else:
            if target is None:
                target = actor  # fallback: use on self
            used = use_item_in_battle(actor, item_id, target)
            # whether or not we want to refund the turn on failure
            # is a design choice; for now, the turn is still consumed.
        actor.defending = False
        selected_item = None

    elif choice == "Defend":
        actor.defending = True
        add_message(f"{actor.name} braces for impact!")

    elif choice == "Run":
        if random.random() < 0.5:
            add_message(f"{actor.name} successfully escaped!")
            battle_state = "END"
            winner = "ESCAPE"
            return
        else:
            add_message(f"{actor.name} tried to run, but couldn't escape!")
        actor.defending = False

    # After the hero acts, tick enemy status effects
    process_statuses_on_enemies()

    # Check if all enemies died
    if all_enemies_dead() and battle_state != "END":
        add_message("All enemies are defeated!")

        global post_battle_gold, post_battle_items

        total_xp, total_gold, drops = grant_rewards_for_group(enemies)
        add_message(f"Party gains {total_xp} XP!")
        if total_gold > 0:
            add_message(f"Found {total_gold} G!")

        if drops:
            names = [gd.ITEMS[i]["name"] for i in drops]
            add_message("Loot: " + ", ".join(names))

        distribute_xp_among_party(total_xp)
        apply_gold_and_loot(total_gold, drops)

        # Store for results UI - convert drops list to (item_id, qty) tuples
        post_battle_gold = total_gold
        post_battle_items = []
        item_counts = {}
        for item_id in drops:
            item_counts[item_id] = item_counts.get(item_id, 0) + 1
        for item_id, qty in item_counts.items():
            post_battle_items.append((item_id, qty))

        battle_state = "END"
        winner = "HERO"

        # start END state at phase 0: Victory! screen
        global end_step
        end_step = 0
        return

    if battle_state != "END":
        _advance_turn_after_hero(actor_idx)


def _advance_turn_after_hero(last_actor_index):
    """
    Move to the next living hero who hasn't acted this round.
    If everyone has acted, go to ENEMY_TURN.
    """
    global battle_state, current_hero_index, party_acted_this_round, menu_index

    party_acted_this_round.add(last_actor_index)

    # find next living hero who has NOT acted yet
    for offset in range(1, len(party) + 1):
        idx = (last_actor_index + offset) % len(party)
        if party[idx].is_alive() and idx not in party_acted_this_round:
            current_hero_index = idx
            menu_index = 0  # start them on their main command
            battle_state = "PLAYER_CHOICE"
            return

    # nobody left this round -> enemies act next
    party_acted_this_round.clear()
    battle_state = "ENEMY_TURN"


def enemy_take_action():
    """Each alive enemy acts in turn."""
    global battle_state, winner, current_hero_index, party_acted_this_round

    # Each enemy gets one action
    for e in enemies:
        if not e.is_alive():
            continue

        if not living_party_members():
            break

        # If an enemy is stunned, they lose their action
        if has_status(e, "Stun"):
            add_message(f"{e.name} is stunned and cannot act!")
            continue

        # pick a random living party member to target
        target = random.choice(living_party_members())

        if e.name == "Slime":
            # Simple physical attack
            dmg = calculate_physical_damage(e, target)
            target.hp = max(0, target.hp - dmg)
            add_message(f"{e.name} slaps {target.name} for {dmg} damage!")
            # Track simple enemy performance
            e.battle_damage_dealt = getattr(e, "battle_damage_dealt", 0) + dmg
            target.battle_damage_taken = getattr(target, "battle_damage_taken", 0) + dmg

        elif e.name == "Bat":
            roll = random.random()
            if roll < 0.30:
                # Poisonous bite that can inflict poison
                dmg = calculate_physical_damage(e, target)
                target.hp = max(0, target.hp - dmg)
                add_message(
                    f"{e.name} sinks its fangs into {target.name} for {dmg} damage!"
                )
                # 60% chance to inflict poison
                if random.random() < 0.60:
                    add_status(target, "Poison", duration=3, power=2)
                    add_message(f"{target.name} is afflicted with poison!")
                e.battle_damage_dealt = getattr(e, "battle_damage_dealt", 0) + dmg
                target.battle_damage_taken = (
                    getattr(target, "battle_damage_taken", 0) + dmg
                )
            else:
                dmg = calculate_physical_damage(e, target)
                target.hp = max(0, target.hp - dmg)
                add_message(f"{e.name} bites {target.name} for {dmg} damage!")
                e.battle_damage_dealt = getattr(e, "battle_damage_dealt", 0) + dmg
                target.battle_damage_taken = (
                    getattr(target, "battle_damage_taken", 0) + dmg
                )

        elif e.name == "Cultist":
            roll = random.random()
            if roll < 0.35:
                # Blood hex that causes bleeding
                dmg = calculate_physical_damage(e, target)
                target.hp = max(0, target.hp - dmg)
                add_message(
                    f"{e.name} casts a blood hex on {target.name} for {dmg} damage!"
                )
                # 70% chance to inflict bleed
                if random.random() < 0.70:
                    add_status(target, "Bleed", duration=3, power=3)
                    add_message(f"{target.name} starts bleeding!")
                e.battle_damage_dealt = getattr(e, "battle_damage_dealt", 0) + dmg
                target.battle_damage_taken = (
                    getattr(target, "battle_damage_taken", 0) + dmg
                )

            elif roll < 0.60:
                # Shadow bind that stuns
                add_message(f"{e.name} binds {target.name} in shadowy chains!")
                add_status(target, "Stun", duration=1, power=0)

            else:
                dmg = calculate_physical_damage(e, target) + 1
                target.hp = max(0, target.hp - dmg)
                add_message(f"{e.name} strikes {target.name} for {dmg} damage!")
                e.battle_damage_dealt = getattr(e, "battle_damage_dealt", 0) + dmg
                target.battle_damage_taken = (
                    getattr(target, "battle_damage_taken", 0) + dmg
                )

    # After all enemies act, tick party status effects (poison, bleed, etc.)
    process_statuses_on_party()

    # Reset defending after enemy phase
    for member in party:
        member.defending = False

    if all_party_dead():
        add_message("The party has fallen...")
        battle_state = "END"
        winner = "ENEMY"
    else:
        # New round: start from first living party member
        party_acted_this_round.clear()
        for i, m in enumerate(party):
            if m.is_alive():
                current_hero_index = i
                break
        menu_index = 0
        battle_state = "PLAYER_CHOICE"


def draw_health_bar(x, y, width, height, current, maximum):
    ratio = current / maximum
    ratio = max(0.0, min(1.0, ratio))
    pygame.draw.rect(screen, RED, (x, y, width, height))
    pygame.draw.rect(screen, GREEN, (x, y, int(width * ratio), height))


def draw_battle_screen():
    screen.fill(BLACK)

    # ---------- MAIN BATTLE FIELD (top half) ----------
    # Top "stage" area – enemies on left, heroes on right
    field_height = HEIGHT - 240  # leaves room for bottom UI
    field_rect = pygame.Rect(16, 16, WIDTH - 32, field_height)

    # Stage border
    pygame.draw.rect(screen, WHITE, field_rect, 2)

    # Simple layered background to feel like a 2D stage
    pygame.draw.rect(screen, (20, 20, 50), field_rect)  # dark base
    pygame.draw.rect(
        screen,
        (35, 35, 80),
        (
            field_rect.x,
            field_rect.y + field_rect.height // 3,
            field_rect.width,
            field_rect.height // 3,
        ),
    )
    pygame.draw.rect(
        screen,
        (10, 10, 30),
        (
            field_rect.x,
            field_rect.y + 2 * field_rect.height // 3,
            field_rect.width,
            field_rect.height // 3,
        ),
    )

    # --- Slot positions for 3v3 layout ---
    mid_y = field_rect.centery
    spacing = 90  # vertical spacing between slots

    enemy_x = field_rect.x + 120  # left side for enemies
    hero_x = field_rect.right - 120  # right side for heroes

    enemy_slots = [
        (enemy_x, mid_y - spacing),
        (enemy_x, mid_y),
        (enemy_x, mid_y + spacing),
    ]
    hero_slots = [
        (hero_x, mid_y - spacing),
        (hero_x, mid_y),
        (hero_x, mid_y + spacing),
    ]

    # ---------- ENEMIES (left side, up to 3) ----------
    for idx, e in enumerate(enemies):
        if idx >= 3:
            break

        x, y = enemy_slots[idx]

        # Simple placeholder "sprite": a square
        sprite_rect = pygame.Rect(0, 0, 60, 60)
        sprite_rect.center = (x, y)

        color = RED if e.is_alive() else GRAY
        pygame.draw.rect(screen, color, sprite_rect)

        # Name under the enemy
        name_text = font_small.render(e.name, True, WHITE)
        name_rect = name_text.get_rect(center=(x, y + 42))
        screen.blit(name_text, name_rect)

        # Target cursor when selecting
        if battle_state == "TARGET_SELECT" and idx == target_index and e.is_alive():
            arrow_text = font_small.render("▶", True, YELLOW)
            arrow_rect = arrow_text.get_rect(midright=(sprite_rect.left - 8, y))
            screen.blit(arrow_text, arrow_rect)

    # ---------- HEROES (right side, up to 3) ----------
    for idx, h in enumerate(party):
        if idx >= 3:
            break

        x, y = hero_slots[idx]

        sprite_rect = pygame.Rect(0, 0, 60, 60)
        sprite_rect.center = (x, y)

        color = GREEN if h.is_alive() else GRAY
        pygame.draw.rect(screen, color, sprite_rect)

        # Highlight the active hero with a border
        if idx == current_hero_index and battle_state in (
            "PLAYER_CHOICE",
            "SKILL_MENU",
            "TARGET_SELECT",
        ):
            pygame.draw.rect(screen, YELLOW, sprite_rect, 3)

        # Name under hero
        name_text = font_small.render(h.name, True, WHITE)
        name_rect = name_text.get_rect(center=(x, y + 42))
        screen.blit(name_text, name_rect)

    # ---------- DAMAGE POPUPS (float over battlefield) ----------
    for p in damage_popups:
        txt = font_med.render(p["text"], True, p["color"])
        rect = txt.get_rect(center=(int(p["x"]), int(p["y"])))
        screen.blit(txt, rect)

    # ---------- BOTTOM BAR (Party + Commands) ----------
    bottom_y = field_rect.bottom + 12
    bottom_height = HEIGHT - bottom_y - 16
    bottom_rect = pygame.Rect(16, bottom_y, WIDTH - 32, bottom_height)
    pygame.draw.rect(screen, WHITE, bottom_rect, 2)

    # Vertical split: left = party info, right = command/skill menu
    split_x = bottom_rect.x + int(bottom_rect.width * 0.60)
    pygame.draw.line(
        screen,
        WHITE,
        (split_x, bottom_rect.y),
        (split_x, bottom_rect.bottom),
        2,
    )

    # Content areas
    party_rect = pygame.Rect(
        bottom_rect.x + 10,
        bottom_rect.y + 10,
        split_x - bottom_rect.x - 14,
        bottom_rect.height - 20,
    )
    menu_rect = pygame.Rect(
        split_x + 10,
        bottom_rect.y + 10,
        bottom_rect.right - split_x - 20,
        bottom_rect.height - 20,
    )

    # ---------- PARTY BOX (bottom-left, per-character info only) ----------
    # No overall "Party LV" line – just each member's info.
    row_h = 56
    start_y = party_rect.y + 6  # move everybody up so they fit inside the box

    for idx, h in enumerate(party):
        y = start_y + idx * row_h

        name_color = WHITE
        if idx == current_hero_index and battle_state in (
            "PLAYER_CHOICE",
            "SKILL_MENU",
            "TARGET_SELECT",
        ):
            name_color = YELLOW

        # Name
        name_text = font_small.render(h.name, True, name_color)
        screen.blit(name_text, (party_rect.x, y))

        # Personal level under the name
        lv_text = font_small.render(f"(LV {h.level})", True, WHITE)
        screen.blit(lv_text, (party_rect.x + 18, y + 14))

        stats_x = party_rect.x + 150

        # HP + MP line
        hp_mp_line = font_small.render(
            f"HP {h.hp}/{h.max_hp}   MP {h.mp}/{h.max_mp}",
            True,
            WHITE,
        )
        screen.blit(hp_mp_line, (stats_x, y + 10))

        # XP line (per character)
        xp_line = font_small.render(
            f"XP {h.xp}/{h.xp_to_next}",
            True,
            WHITE,
        )
        screen.blit(xp_line, (stats_x, y + 26))

        # HP bar under stats
        bar_y = y + 40
        bar_w = party_rect.width - (stats_x - party_rect.x) - 10
        draw_health_bar(stats_x, bar_y, bar_w, 8, h.hp, h.max_hp)

        # Arrow when selecting an ally for an item
        if battle_state == "ITEM_TARGET" and idx == ally_target_index and h.is_alive():
            arrow_text = font_small.render("▶", True, YELLOW)
            screen.blit(arrow_text, (party_rect.x - 14, y + 8))

    # ---------- COMMAND MENU (bottom-right) ----------
    title = font_small.render("Commands", True, WHITE)
    screen.blit(title, (menu_rect.x, menu_rect.y))

    actor = get_active_hero()
    options = get_command_options(actor)

    for i, option in enumerate(options):
        color = WHITE
        if battle_state == "PLAYER_CHOICE" and i == menu_index:
            color = YELLOW
        text = font_small.render(option, True, color)
        screen.blit(text, (menu_rect.x + 10, menu_rect.y + 24 + i * 22))

    # keep MENU_OPTIONS in sync with the actual order
    MENU_OPTIONS[:] = options

    # ---------- SKILL MENU OVERLAY (uses the same menu_rect area) ----------
    if battle_state == "SKILL_MENU":
        # cover command area and redraw as skill box
        pygame.draw.rect(screen, BLACK, menu_rect)
        pygame.draw.rect(screen, WHITE, menu_rect, 2)

        actor = get_active_hero()
        skills = get_actor_skills(actor)

        title = font_small.render("Skills", True, WHITE)
        screen.blit(title, (menu_rect.x + 8, menu_rect.y + 4))

        if not skills:
            # This class literally has no defined skills
            msg = font_small.render("No skills for this character yet.", True, WHITE)
            screen.blit(msg, (menu_rect.x + 10, menu_rect.y + 28))
        else:
            start = skill_scroll
            end = min(start + SKILL_VISIBLE_MAX, len(skills))

            for draw_i, skill_i in enumerate(range(start, end)):
                skill = skills[skill_i]
                learned = actor.level >= skill["level_req"]

                if not learned:
                    color = LOCKED
                else:
                    color = YELLOW if skill_i == skill_index else WHITE

                label = f"{skill['name']} (MP {skill['mp_cost']})"
                text = font_small.render(label, True, color)
                screen.blit(text, (menu_rect.x + 10, menu_rect.y + 24 + draw_i * 20))

            # scroll arrows
            if skill_scroll > 0:
                up_text = font_small.render("↑", True, WHITE)
                screen.blit(up_text, (menu_rect.right - 18, menu_rect.y + 22))
            if end < len(skills):
                dn_text = font_small.render("↓", True, WHITE)
                screen.blit(
                    dn_text,
                    (
                        menu_rect.right - 18,
                        menu_rect.y + 24 + (SKILL_VISIBLE_MAX - 1) * 20,
                    ),
                )

    # ---------- ITEM MENU OVERLAY ----------
    if battle_state == "ITEM_MENU":
        pygame.draw.rect(screen, BLACK, menu_rect)
        pygame.draw.rect(screen, WHITE, menu_rect, 2)

        items = get_inventory_items()

        title = font_small.render("Items", True, WHITE)
        screen.blit(title, (menu_rect.x + 8, menu_rect.y + 4))

        if not items:
            msg = font_small.render("No items.", True, WHITE)
            screen.blit(msg, (menu_rect.x + 10, menu_rect.y + 28))
        else:
            start = item_scroll
            end = min(start + ITEM_VISIBLE_MAX, len(items))

            for draw_i, item_i in enumerate(range(start, end)):
                item_id, qty = items[item_i]
                item_name = gd.ITEMS[item_id]["name"]
                label = f"{item_name} x{qty}"
                color = YELLOW if item_i == item_index else WHITE
                text = font_small.render(label, True, color)
                screen.blit(text, (menu_rect.x + 10, menu_rect.y + 24 + draw_i * 20))

            # scroll arrows
            if item_scroll > 0:
                up_text = font_small.render("↑", True, WHITE)
                screen.blit(up_text, (menu_rect.right - 18, menu_rect.y + 22))
            if end < len(items):
                dn_text = font_small.render(
                    "↓",
                    True,
                    WHITE,
                )
                screen.blit(
                    dn_text,
                    (
                        menu_rect.right - 18,
                        menu_rect.y + 24 + (ITEM_VISIBLE_MAX - 1) * 20,
                    ),
                )

    # ---------- PAUSE MENU OVERLAY ----------
    if battle_state == "PAUSE_MENU":
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        panel_width = 320
        panel_height = 160
        panel_rect = pygame.Rect(
            (WIDTH - panel_width) // 2,
            (HEIGHT - panel_height) // 2,
            panel_width,
            panel_height,
        )

        pygame.draw.rect(screen, (15, 15, 35), panel_rect)
        pygame.draw.rect(screen, WHITE, panel_rect, 2)

        title = font_med.render("Paused", True, WHITE)
        title_rect = title.get_rect(midtop=(panel_rect.centerx, panel_rect.y + 12))
        screen.blit(title, title_rect)

        # Options: Resume / Quit
        row_y = title_rect.bottom + 16
        row_h = 28

        for i, option in enumerate(PAUSE_OPTIONS):
            color = YELLOW if i == pause_menu_index else WHITE
            txt = font_small.render(option, True, color)
            txt_rect = txt.get_rect(midleft=(panel_rect.x + 40, row_y + i * row_h))
            screen.blit(txt, txt_rect)

        hint = font_small.render(
            "↑/↓: Move   ENTER: Select   ESC: Resume",
            True,
            WHITE,
        )
        hint_rect = hint.get_rect(
            midbottom=(panel_rect.centerx, panel_rect.bottom - 10)
        )
        screen.blit(hint, hint_rect)

    # ---------- END OVERLAY ----------
    if battle_state == "END":
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        screen.blit(overlay, (0, 0))

        if winner == "HERO":
            if end_step == 0:
                # Phase 0: Simple Victory prompt
                title = font_big.render("Victory!", True, WHITE)
                title_rect = title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40))
                screen.blit(title, title_rect)

                prompt = font_small.render(
                    "Press any key for results   (ESC: Quit)",
                    True,
                    WHITE,
                )
                prompt_rect = prompt.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 10))
                screen.blit(prompt, prompt_rect)

            elif end_step == 1:
                # Phase 1: XP RESULTS UI + Loot
                panel_width = WIDTH - 200
                panel_height = 260
                panel_rect = pygame.Rect(
                    (WIDTH - panel_width) // 2,
                    (HEIGHT - panel_height) // 2,
                    panel_width,
                    panel_height,
                )

                pygame.draw.rect(screen, (15, 15, 35), panel_rect)
                pygame.draw.rect(screen, WHITE, panel_rect, 2)

                title = font_med.render("Battle Results", True, WHITE)
                title_rect = title.get_rect(
                    midtop=(panel_rect.centerx, panel_rect.y + 10)
                )
                screen.blit(title, title_rect)

                # ---- XP RESULTS ----
                if post_battle_results:
                    row_y = title_rect.bottom + 10
                    row_h = 40
                    bar_margin_x = 180

                    for idx, r in enumerate(post_battle_results):
                        state = None
                        if results_anim_state and idx < len(results_anim_state):
                            state = results_anim_state[idx]

                        # Name + level
                        name_txt = font_small.render(
                            f"{r['name']}  LV {r['level_before']}→{r['level_after']}",
                            True,
                            WHITE,
                        )
                        screen.blit(name_txt, (panel_rect.x + 20, row_y))

                        # XP text with odometer effect
                        shown_xp = r["xp"]
                        if state is not None:
                            shown_xp = state["xp_display"]
                        xp_txt = font_small.render(f"+{shown_xp} XP", True, YELLOW)
                        screen.blit(xp_txt, (panel_rect.x + 20, row_y + 18))

                        # XP bar
                        bar_x = panel_rect.x + bar_margin_x
                        bar_y = row_y + 10
                        bar_w = panel_rect.width - bar_margin_x - 20
                        bar_h = 12

                        pygame.draw.rect(screen, GRAY, (bar_x, bar_y, bar_w, bar_h))

                        fill_ratio = 0.0
                        if state is not None and state["segment_cap"] > 0:
                            fill_ratio = (
                                state["segment_progress"] / state["segment_cap"]
                            )
                            fill_ratio = max(0.0, min(1.0, fill_ratio))

                        pygame.draw.rect(
                            screen,
                            GREEN,
                            (bar_x, bar_y, int(bar_w * fill_ratio), bar_h),
                        )

                        row_y += row_h

                # ---- GOLD + LOOT SUMMARY ----
                loot_y = title_rect.bottom + 10 + 40 * len(post_battle_results or [])
                loot_y += 8

                gold_line = font_small.render(
                    f"Gold found: {post_battle_gold}",
                    True,
                    WHITE,
                )
                screen.blit(gold_line, (panel_rect.x + 20, loot_y))
                loot_y += 20

                if post_battle_items:
                    items_title = font_small.render("Items found:", True, WHITE)
                    screen.blit(items_title, (panel_rect.x + 20, loot_y))
                    loot_y += 18

                    for item_id, qty in post_battle_items:
                        item_name = gd.ITEMS.get(item_id, {}).get("name", item_id)
                        line = font_small.render(f"- {item_name} x{qty}", True, WHITE)
                        screen.blit(line, (panel_rect.x + 40, loot_y))
                        loot_y += 18

                prompt = font_small.render(
                    "Any key: Inventory   (ESC: Quit)",
                    True,
                    WHITE,
                )
                prompt_rect = prompt.get_rect(
                    center=(panel_rect.centerx, panel_rect.bottom - 16)
                )
                screen.blit(prompt, prompt_rect)

            elif end_step == 2:
                # Phase 2: INVENTORY GUI
                panel_width = WIDTH - 200
                panel_height = 260
                panel_rect = pygame.Rect(
                    (WIDTH - panel_width) // 2,
                    (HEIGHT - panel_height) // 2,
                    panel_width,
                    panel_height,
                )

                pygame.draw.rect(screen, (10, 15, 30), panel_rect)
                pygame.draw.rect(screen, WHITE, panel_rect, 2)

                title = font_med.render("Inventory", True, WHITE)
                title_rect = title.get_rect(
                    midtop=(panel_rect.centerx, panel_rect.y + 10)
                )
                screen.blit(title, title_rect)

                # Build a sorted list of items from the inventory
                items = [
                    (item_id, qty) for item_id, qty in inv.inventory.items() if qty > 0
                ]
                items.sort(key=lambda t: gd.ITEMS.get(t[0], {}).get("name", t[0]))

                # If empty:
                if not items:
                    empty_txt = font_small.render(
                        "You don't have any items yet.",
                        True,
                        WHITE,
                    )
                    empty_rect = empty_txt.get_rect(
                        center=(panel_rect.centerx, panel_rect.centery)
                    )
                    screen.blit(empty_txt, empty_rect)
                else:
                    list_x = panel_rect.x + 30
                    list_y = title_rect.bottom + 10
                    row_h = 22

                    # Scroll window into items
                    start = inventory_scroll
                    end = min(start + INVENTORY_VISIBLE_MAX, len(items))

                    for draw_i, idx in enumerate(range(start, end)):
                        item_id, qty = items[idx]
                        item_name = gd.ITEMS.get(item_id, {}).get("name", item_id)

                        line_text = f"{item_name}  x{qty}"
                        color = YELLOW if idx == inventory_menu_index else WHITE

                        line = font_small.render(line_text, True, color)
                        screen.blit(line, (list_x, list_y + draw_i * row_h))

                    # Scroll hints
                    if inventory_scroll > 0:
                        up_txt = font_small.render("↑", True, WHITE)
                        screen.blit(
                            up_txt,
                            (panel_rect.right - 30, list_y),
                        )
                    if end < len(items):
                        dn_txt = font_small.render("↓", True, WHITE)
                        screen.blit(
                            dn_txt,
                            (
                                panel_rect.right - 30,
                                list_y + (INVENTORY_VISIBLE_MAX - 1) * row_h,
                            ),
                        )

                prompt = font_small.render(
                    "ESC: Quit   ENTER/SPACE: Next battle",
                    True,
                    WHITE,
                )
                prompt_rect = prompt.get_rect(
                    center=(panel_rect.centerx, panel_rect.bottom - 16)
                )
                screen.blit(prompt, prompt_rect)

        else:
            # Defeat or Escape – keep it simple
            if winner == "ENEMY":
                result_text = font_big.render("Defeat...", True, WHITE)
            else:
                result_text = font_big.render("Escaped", True, WHITE)

            result_rect = result_text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
            screen.blit(result_text, result_rect)

            small = font_small.render(
                "ESC: Quit   Any other key: Next battle",
                True,
                WHITE,
            )
            small_rect = small.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 50))
            screen.blit(small, small_rect)


def start_new_battle():
    """Reset battle state and spawn a new random enemy group."""
    global menu_index, battle_state, enemies, message_log, winner
    global target_index, pending_action, selected_skill, skill_index
    global current_hero_index, party_acted_this_round
    global end_step, post_battle_results
    global selected_item, item_index, item_scroll, ally_target_index
    global post_battle_gold, post_battle_items
    global inventory_menu_index, inventory_scroll

    # NEW: sync equipment to stats at the start of each battle
    sync_party_equipment_from_inventory()

    # Sync party stats from shared state (equipment changes, etc.)
    sync_party_from_shared_state()

    # reset end-phase
    end_step = 0
    post_battle_results = None
    post_battle_gold = 0
    post_battle_items = []

    # reset inventory GUI state
    inventory_menu_index = 0
    inventory_scroll = 0

    # reset turn tracker
    party_acted_this_round = set()
    current_hero_index = 0

    menu_index = 0
    battle_state = "PLAYER_CHOICE"
    message_log = []
    winner = None

    pending_action = None
    selected_skill = None
    selected_item = None
    target_index = 0
    skill_index = 0
    skill_scroll = 0
    item_index = 0
    item_scroll = 0
    ally_target_index = 0

    # Restore hero/party HP/MP and reset per-battle performance counters
    for member in party:
        member.hp = member.max_hp
        member.mp = member.max_mp
        member.defending = False
        member.statuses.clear()
        member.battle_damage_dealt = 0
        member.battle_damage_taken = 0
        member.battle_kills = 0
        member.battle_status_inflicted = 0

    # New random enemy group
    enemies[:] = pick_enemy_group()

    # add these 4 lines here (this fixes poison/bleed carrying over!)
    hero.statuses.clear()  # Clear hero statuses (future-proof)

    # Clear statuses from the OLD enemies that are about to be replaced
    for enemy in enemies:
        enemy.statuses.clear()
        enemy.battle_damage_taken = 0

    if len(enemies) == 1:
        add_message(f"A wild {enemies[0].name} appears!")
    else:
        names = ", ".join(e.name for e in enemies)
        add_message(f"Enemies appear: {names}!")


def main():
    global menu_index, battle_state, enemies, message_log, winner
    global target_index, pending_action, selected_skill, skill_index, skill_scroll
    global selected_item, item_index, item_scroll, ally_target_index
    global pause_menu_index

    # Start the first battle
    start_new_battle()

    running = True

    while running:
        # ----- HANDLE EVENTS -----
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # ----- PLAYER CHOICE STATE -----
            if battle_state == "PLAYER_CHOICE":
                if event.type == pygame.KEYDOWN:
                    actor = get_active_hero()
                    options = get_command_options(actor)

                    # --- ESC opens pause menu ---
                    if event.key == pygame.K_ESCAPE:
                        battle_state = "PAUSE_MENU"
                        pause_menu_index = 0
                        continue

                    if event.key == pygame.K_UP:
                        menu_index = (menu_index - 1) % len(options)
                    elif event.key == pygame.K_DOWN:
                        menu_index = (menu_index + 1) % len(options)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        choice = options[menu_index]

                        if choice in ("Attack", "Magic") and not all_enemies_dead():
                            # Enter target selection mode
                            pending_action = choice
                            target_index = 0
                            if enemies and not enemies[target_index].is_alive():
                                target_index = get_next_alive_index(target_index)
                            battle_state = "TARGET_SELECT"

                        elif choice == "Skill":
                            battle_state = "SKILL_MENU"
                            skill_index = 0
                            skill_scroll = 0

                        elif choice == "Item":
                            battle_state = "ITEM_MENU"
                            item_index = 0
                            item_scroll = 0

                        else:
                            hero_take_action(actor, choice)

            # ----- PAUSE MENU STATE -----
            elif battle_state == "PAUSE_MENU":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        pause_menu_index = (pause_menu_index - 1) % len(PAUSE_OPTIONS)
                    elif event.key == pygame.K_DOWN:
                        pause_menu_index = (pause_menu_index + 1) % len(PAUSE_OPTIONS)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        choice = PAUSE_OPTIONS[pause_menu_index]
                        if choice == "Resume":
                            battle_state = "PLAYER_CHOICE"
                        elif choice == "Quit":
                            pygame.quit()
                            sys.exit()
                    elif event.key == pygame.K_ESCAPE:
                        battle_state = "PLAYER_CHOICE"

            # ----- SKILL MENU STATE -----
            elif battle_state == "SKILL_MENU":
                if event.type == pygame.KEYDOWN:
                    actor = get_active_hero()
                    skills = get_actor_skills(actor)

                    # --- UP ---
                    if event.key == pygame.K_UP:
                        if skills:
                            old_index = skill_index
                            skill_index = (skill_index - 1) % len(skills)

                            # wrapped from 0 → last
                            if skill_index > old_index:
                                skill_scroll = max(0, len(skills) - SKILL_VISIBLE_MAX)
                            else:
                                if skill_index < skill_scroll:
                                    skill_scroll = skill_index

                    # --- DOWN ---
                    elif event.key == pygame.K_DOWN:
                        if skills:
                            old_index = skill_index
                            skill_index = (skill_index + 1) % len(skills)

                            # wrapped from last → 0
                            if skill_index < old_index:
                                skill_scroll = 0
                            else:
                                if skill_index >= skill_scroll + SKILL_VISIBLE_MAX:
                                    skill_scroll = skill_index - SKILL_VISIBLE_MAX + 1

                    # --- ESCAPE ---
                    elif event.key == pygame.K_ESCAPE:
                        battle_state = "PLAYER_CHOICE"
                        selected_skill = None

                    # --- ENTER / SPACE: choose skill ---
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if not skills:
                            # No class skills at all
                            battle_state = "PLAYER_CHOICE"
                        else:
                            skill = skills[skill_index]
                            if actor.level < skill["level_req"]:
                                add_message(
                                    f"{actor.name} hasn't learned {skill['name']} yet!"
                                )
                            elif actor.mp < skill["mp_cost"]:
                                add_message(f"Not enough MP to use {skill['name']}!")
                            else:
                                selected_skill = skill
                                if skill["target"] == "single":
                                    # Go to target selection
                                    pending_action = "SKILL"
                                    target_index = 0
                                    if enemies and not enemies[target_index].is_alive():
                                        target_index = get_next_alive_index(
                                            target_index
                                        )
                                    battle_state = "TARGET_SELECT"
                                else:
                                    # All-target skill: fire immediately
                                    pending_action = None
                                    hero_take_action(actor, "SKILL")

            elif battle_state == "ITEM_MENU":
                if event.type == pygame.KEYDOWN:
                    actor = get_active_hero()
                    items = get_inventory_items()

                    if event.key == pygame.K_UP:
                        if items:
                            old_index = item_index
                            item_index = (item_index - 1) % len(items)
                            if item_index > old_index:
                                item_scroll = max(0, len(items) - ITEM_VISIBLE_MAX)
                            else:
                                if item_index < item_scroll:
                                    item_scroll = item_index

                    elif event.key == pygame.K_DOWN:
                        if items:
                            old_index = item_index
                            item_index = (item_index + 1) % len(items)
                            if item_index < old_index:
                                item_scroll = 0
                            else:
                                if item_index >= item_scroll + ITEM_VISIBLE_MAX:
                                    item_scroll = item_index - ITEM_VISIBLE_MAX + 1

                    elif event.key == pygame.K_ESCAPE:
                        battle_state = "PLAYER_CHOICE"
                        selected_item = None

                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if not items:
                            battle_state = "PLAYER_CHOICE"
                        else:
                            item_id, qty = items[item_index]
                            selected_item = item_id

                            # start targeting allies
                            ally_target_index = 0
                            for i, m in enumerate(party):
                                if m.is_alive():
                                    ally_target_index = i
                                    break

                            battle_state = "ITEM_TARGET"

            # ----- TARGET SELECTION STATE -----
            elif battle_state == "TARGET_SELECT":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        target_index = get_prev_alive_index(target_index)
                    elif event.key == pygame.K_DOWN:
                        target_index = get_next_alive_index(target_index)
                    elif event.key == pygame.K_ESCAPE:
                        # Cancel targeting
                        if pending_action == "SKILL":
                            battle_state = "SKILL_MENU"
                        else:
                            battle_state = "PLAYER_CHOICE"
                        pending_action = None
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if enemies and enemies[target_index].is_alive():
                            target = enemies[target_index]
                            actor = get_active_hero()
                            if pending_action == "SKILL":
                                hero_take_action(actor, "SKILL", target)
                            else:
                                hero_take_action(actor, pending_action, target)

                        pending_action = None
                        # hero_take_action will swap to ENEMY_TURN or END

            elif battle_state == "ITEM_TARGET":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        # previous living party member
                        n = len(party)
                        for i in range(1, n + 1):
                            idx = (ally_target_index - i) % n
                            if party[idx].is_alive():
                                ally_target_index = idx
                                break

                    elif event.key == pygame.K_DOWN:
                        # next living party member
                        n = len(party)
                        for i in range(1, n + 1):
                            idx = (ally_target_index + i) % n
                            if party[idx].is_alive():
                                ally_target_index = idx
                                break

                    elif event.key == pygame.K_ESCAPE:
                        # go back to item list
                        battle_state = "ITEM_MENU"

                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        actor = get_active_hero()
                        target = party[ally_target_index]
                        hero_take_action(actor, "ITEM", target)
                        # hero_take_action will advance state / turn

            # ----- END OF BATTLE -----
            elif battle_state == "END":
                if event.type == pygame.KEYDOWN:
                    global end_step, inventory_menu_index, inventory_scroll

                    # INVENTORY PHASE (end_step == 2) has special controls
                    if winner == "HERO" and end_step == 2:
                        if event.key == pygame.K_ESCAPE:
                            running = False

                        else:
                            # Rebuild the same item list we draw, to know its length
                            items = [
                                (item_id, qty)
                                for item_id, qty in inv.inventory.items()
                                if qty > 0
                            ]
                            items.sort(
                                key=lambda t: gd.ITEMS.get(t[0], {}).get("name", t[0])
                            )

                            if event.key == pygame.K_UP and items:
                                inventory_menu_index = (inventory_menu_index - 1) % len(
                                    items
                                )
                                # Adjust scroll if cursor goes above window
                                if inventory_menu_index < inventory_scroll:
                                    inventory_scroll = inventory_menu_index

                            elif event.key == pygame.K_DOWN and items:
                                inventory_menu_index = (inventory_menu_index + 1) % len(
                                    items
                                )
                                # Adjust scroll if cursor goes below window
                                if (
                                    inventory_menu_index
                                    >= inventory_scroll + INVENTORY_VISIBLE_MAX
                                ):
                                    inventory_scroll = (
                                        inventory_menu_index - INVENTORY_VISIBLE_MAX + 1
                                    )

                            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                                # Sync party state back to shared module before next battle
                                sync_party_to_shared_state()
                                # For now: inventory is view-only, ENTER starts next battle
                                start_new_battle()

                            # Any other keys during inventory we just ignore
                    else:
                        # Normal END behavior for Victory/Results/Defeat/Escape
                        if event.key == pygame.K_ESCAPE:
                            running = False
                        else:
                            if winner == "HERO":
                                if end_step == 0:
                                    # Victory -> Results (XP/loot)
                                    end_step = 1
                                elif end_step == 1:
                                    # Results -> Inventory
                                    end_step = 2
                                    inventory_menu_index = 0
                                    inventory_scroll = 0
                                else:
                                    # Shouldn't really happen, but just in case
                                    start_new_battle()
                            else:
                                # Defeat / Escape: sync and restart immediately
                                sync_party_to_shared_state()
                                start_new_battle()

        # ----- ENEMY TURN (no input needed) -----
        if battle_state == "ENEMY_TURN":
            enemy_take_action()

        # ----- UPDATE VISUAL EFFECTS -----
        update_damage_popups()
        update_results_animation()  # animate XP numbers + bars on results screen

        # ----- DRAW FRAME -----
        draw_battle_screen()
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
