import pygame
import sys
import subprocess  # <-- for launching combat.py
import random  # for random encounters
import inventory_state as inv
from inventory_state import add_item, remove_item
import party_state as party
from party_state import party as party_list
import game_data as gd
from game_data import WEAPONS, WEAPON_SHOP_STOCK, ARMOR, ARMOR_SHOP_STOCK
import combat

pygame.init()

# ---------------------------
# GLOBAL GAME STATE CLEANUP
# ---------------------------

# Overworld menu (ESC)
world_menu_open = False

# Interior system: None = overworld, otherwise "ITEM_SHOP", "INN", etc.
CURRENT_INTERIOR = None

# Dialog system
dialog_active = False

# Player movement lock flag (debug tool)
movement_debug_enabled = True

# ----------- UNIFIED INTERIOR SYSTEM -----------
# CURRENT_INTERIOR defined above in GLOBAL GAME STATE CLEANUP
interior_surface = None
shop_selection = 0
inn_prompt_active = False

# ----------- BASIC SETUP -----------
WIDTH, HEIGHT = 960, 540
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("JRPG Overworld Prototype (Tilemap)")

CLOCK = pygame.time.Clock()
FONT = pygame.font.SysFont("arial", 18)

TILE_SIZE = 32
COLS = WIDTH // TILE_SIZE  # 30
ROWS = HEIGHT // TILE_SIZE  # 16
PLAYER_SIZE = TILE_SIZE // 2  # 16 (half a tile)

# --- World area state (screen-by-screen overworld) ---
current_area = "TOWN"  # logical region name
area_x = 0  # horizontal screen index
area_y = 0  # vertical screen index

# --- Town NPC definitions ---
# You can tweak the positions once you see them in-game.

TOWN_NPCS = [
    {
        "name": "Mayor Elric",
        "role": "quest_giver",
        # Standing in front of a house near town center – adjust as needed
        "x": 12 * TILE_SIZE,
        "y": 7 * TILE_SIZE,
        "dialog_before": [
            "Mayor Elric: Ah, travelers!",
            "The old shrine in the woods has grown restless...",
            "Monsters spill out at night. We need help.",
            "Please, clear out the monsters at the Old Shrine.",
        ],
        "dialog_after_accept": [
            "Mayor Elric: The town is counting on you.",
            "Follow the north road into the forest.",
        ],
        "dialog_after_complete": [
            "Mayor Elric: You've done it!",
            "The air feels lighter already.",
            "Thank you, brave ones.",
        ],
    },
    {
        "name": "Old Farmer",
        "role": "flavor",
        "x": 8 * TILE_SIZE,
        "y": 10 * TILE_SIZE,
        "dialog": [
            "Farmer: Fields were safer before the shrine went sour.",
            "Farmer: Just keep your boots out of my crops, yeah?",
        ],
    },
    {
        "name": "Young Girl",
        "role": "flavor",
        "x": 16 * TILE_SIZE,
        "y": 9 * TILE_SIZE,
        "dialog": [
            "Girl: I heard there's treasure in the forest.",
            "Girl: ...I'm definitely not going to look for it. Nope.",
        ],
    },
]

# ----------- COLORS -----------
WHITE = (255, 255, 255)
GRASS = (24, 120, 40)
ROAD = (150, 110, 70)
HOUSE = (205, 90, 60)
ROOF = (180, 60, 50)
DOOR = (70, 40, 0)
UI_BG = (0, 0, 0)
UI_TEXT = (255, 255, 255)
PLAYER_COLOR = (240, 240, 255)

MENU_BG = (10, 10, 25)
MENU_BORDER = (230, 230, 230)
MENU_HILIGHT = (255, 255, 0)

# ----------- TILEMAP -----------
"""
Legend:
G = grass
R = road
H = house wall (solid)
D = door (walkable)
^ = roof edge (non-solid, decorative)
. = grass
"""

TOWN_MAP = [
    "GGGGGGGGGGGGGGGGGGGGGGGGGGGG",  # 0
    "GGGGGGGGGGGGGGGGGGGGGGGGGGGG",  # 1
    "GG^HHHH^GGGGGGGGGG^HHHH^GGGG",  # 2 roofs
    "GGHDDDHGGGGGGGGGGGHDDDHGGGG",  # 3 walls/doors
    "GGHHHHHGGGGGGGGGGGHHHHHGGGG",  # 4 walls
    "GGGGGGGGGGGGGGGGGGGGGGGGGGGG",  # 5
    "GGGGGGGGGGGGGGGGGGGGGGGGGGGG",  # 6
    "GGGGGGGGGGGGGGGGGGGGGGGGGGGG",  # 7
    "GGGGGGGGGGGGGGGGGGGGGGGGGGGG",  # 8
    "GGGGGRRRRRRRRRRRRRRRRRGGGGGG",  # 9 road
    "GGGGGRRRRRRRRRRRRRRRRRGGGGGG",  # 10 road
    "GGGGGGGGGGGGGGGGGGGGGGGGGGGG",  # 11
    "GG^HHHH^GGGGGGGGGGGGGGGGGGGG",  # 12 right house roof
    "GGHDDDHGGGGGGGGGGGGGGGGGGGG",  # 13 right house walls/door
    "GGHHHHHGGGGGGGGGGGGGGGGGGGG",  # 14 right house walls
    "GGGGGGGGGGGGGGGGGGGGGGGGGGGG",  # 15
]

# Any tile in this set is solid.
SOLID_TILES = {"H"}

# --- DOOR DEFINITIONS -------------------------------------------------


# helper: convert tile coord to world rect
def tile_rect(tx, ty):
    return pygame.Rect(tx * TILE_SIZE, ty * TILE_SIZE, TILE_SIZE, TILE_SIZE)


# Doors in the town, by tile coordinate
DOORS_TOWN = [
    {
        "name": "Inn",
        "rect": tile_rect(4, 4),
        "interior": "INN",
        "target_scene": "INN",
        "return_pos": (4 * TILE_SIZE, 4 * TILE_SIZE),
    },
    {
        "name": "Item Shop",
        "rect": tile_rect(20, 4),
        "interior": "ITEM_SHOP",
        "target_scene": "ITEM_SHOP",
        "return_pos": (20 * TILE_SIZE, 4 * TILE_SIZE),
    },
    {
        "name": "Weapon Shop",
        "rect": tile_rect(4, 14),
        "interior": "WEAPON_SHOP",
        "target_scene": "WEAPON_SHOP",
        "return_pos": (4 * TILE_SIZE, 14 * TILE_SIZE),
    },
    {
        "name": "Town Gate",
        "rect": tile_rect(12, 0),  # top of map
        "target_scene": "WORLD",
        "return_pos": (WIDTH // 2, HEIGHT - 40),  # start at bottom when entering world
    },
]

# ----------- PLAYER -----------
player_x = WIDTH // 2
player_y = 9 * TILE_SIZE + TILE_SIZE // 2  # start on the road
player_speed = 3

debug_message = ""  # bottom-left text (e.g., after battles)

# ----------- SCENE TRACKING -----------
# High-level scenes:
# "TITLE"        – title menu
# "TOWN"         – overworld town
# "WORLD"        – multi-tile overworld
# "INN"          – inside inn
# "ITEM_SHOP"    – inside item shop
# "WEAPON_SHOP"  – inside weapon shop
# "ARMOR_SHOP"   – inside armor shop
# "EQUIPMENT_MENU" – equipment selection menu
# "EQUIP_MEMBER" – individual member equipment screen
# "EQUIP_SELECT" – item selection for equipping
current_scene = "TITLE"

# Equipment menu scenes
SCENE_EQUIPMENT = "EQUIPMENT_MENU"
SCENE_EQUIP_MEMBER = "EQUIP_MEMBER"
SCENE_EQUIP_SELECT = "EQUIP_SELECT"

# where to put the player when we leave an interior
last_town_position = (0, 0)

# ----------- WORLD TILE SYSTEM -----------
current_tile = "TOWN_CENTER"
tile_background = None
tile_objects = []
step_count = 0  # track steps for encounter calculation

# ----------- OVERWORLD MENU STATE -----------
menu_active = False  # is the overworld menu open?
menu_mode = "MAIN"  # "MAIN" or "INVENTORY"
menu_index = 0  # selection in the main menu
OVERWORLD_MENU_OPTIONS = ["Resume", "Quit to Desktop"]

# Inventory view state (when menu_mode == "INVENTORY")
inv_cursor = 0  # which item is highlighted

# --- Overworld menu state (new tabbed system) ---
world_menu_open = False
world_menu_tabs = ["Status", "Inventory", "Equipment", "System"]
world_menu_tab_index = 0  # which tab is selected
world_menu_cursor = 0  # for lists within the active tab

# Inventory tab settings
inv_scroll = 0  # scroll offset for inventory list
INV_VISIBLE_MAX = 8  # max items visible at once

# Equipment tab settings
equip_cursor_char = 0  # which character (Hero, Warrior, Mage)
equip_cursor_item = 0  # which weapon in the list
equip_item_scroll = 0
EQUIP_VISIBLE_MAX = 8

# --- Shop stock definitions ---
SHOP_STOCK = [
    {"id": "Potion", "name": "Potion", "price": 30, "desc": "Heals 30 HP."},
    {"id": "Hi-Potion", "name": "Hi-Potion", "price": 90, "desc": "Heals 90 HP."},
    {"id": "Ether", "name": "Ether", "price": 60, "desc": "Restores 30 MP."},
]

SHOP_VISIBLE_MAX = 5  # how many items to show on screen at once

# Item data for display in menus
ITEM_DATA = {
    "Potion": {"name": "Potion", "desc": "Heals 30 HP."},
    "Hi-Potion": {"name": "Hi-Potion", "desc": "Heals 90 HP."},
    "Ether": {"name": "Ether", "desc": "Restores 30 MP."},
}

# Item shop UI
shop_ui_open = False
shop_menu_index = 0

# Weapon shop state
weapon_shop_open = False
weapon_shop_cursor = 0
weapon_shop_items = []  # filled when you enter shop
weapon_shop_target = "Hero"  # which character we are buying for (expand later)

# Armor shop state
armor_shop_open = False
armor_shop_cursor = 0
shop_message = ""  # for displaying purchase feedback

# Equipment menu state
equip_index = 0  # which party member is selected
equip_slot_index = 0  # 0 = weapon, 1 = armor
equip_select_index = 0  # which item in the selection list
equip_current_member = None  # currently selected party member
equip_current_slot = ""  # "weapon" or "armor"

# --- Inn UI state ---
inn_ui_open = False
inn_menu_index = 0  # 0 = Yes, 1 = No
inn_message = ""
inn_message_timer = 0
inn_dialog_state = 0  # 0 = no dialog, 1 = asking Y/N, 2 = result message (legacy)
inn_cursor_index = 0  # 0 = Yes, 1 = No (legacy)

# Rects used inside item shop for interaction
shopkeeper_rect = None
itemshop_door_rect = None

# Rects used inside weapon shop for interaction
weaponshop_keeper_rect = None
weaponshop_door_rect = None

# --- Quest / story flags ---
quest_flags = {
    "shrine_quest_accepted": False,
    "shrine_quest_completed": False,
}

# --- Simple dialog state for overworld NPCs ---
dialog_active = False
dialog_lines = []
dialog_index = 0


# ----------- TILE HELPERS -----------
def tile_at(px: float, py: float):
    """Return the map character at world pixel position (px, py)."""
    # Only check TOWN_MAP for the main town area (0, 0)
    if current_area != "TOWN" or area_x != 0 or area_y != 0:
        return "G"  # treat other areas as grass (no collision)

    tx = int(px // TILE_SIZE)
    ty = int(py // TILE_SIZE)

    if tx < 0 or ty < 0 or ty >= ROWS or tx >= len(TOWN_MAP[0]):
        return "G"  # treat outside as grass

    return TOWN_MAP[ty][tx]


def is_blocked(px: float, py: float) -> bool:
    """Return True if the given pixel position is blocked by a solid tile."""
    # Only check collision in main town area
    if current_area != "TOWN" or area_x != 0 or area_y != 0:
        return False  # no collision in other areas

    ch = tile_at(px, py)
    return ch in SOLID_TILES


def move_player(dx: float, dy: float):
    """Move the player with simple tile-based collision (separate axis)."""
    global player_x, player_y, step_count

    old_x = player_x
    old_y = player_y
    moved = False

    # Horizontal
    new_x = player_x + dx
    if not is_blocked(new_x, player_y):
        player_x = new_x
        moved = True

    # Vertical
    new_y = player_y + dy
    if not is_blocked(player_x, new_y):
        player_y = new_y
        moved = True

    # Check collision with world tile objects (in WORLD scene)
    if current_scene == "WORLD":
        player_rect = pygame.Rect(
            player_x - PLAYER_SIZE // 2,
            player_y - PLAYER_SIZE // 2,
            PLAYER_SIZE,
            PLAYER_SIZE,
        )

        for obj in tile_objects:
            if obj.get("solid") and obj.get("rect"):
                if player_rect.colliderect(obj["rect"]):
                    # Collision detected - revert movement
                    player_x = old_x
                    player_y = old_y
                    moved = False
                    break

    # Increment step count if player actually moved
    if moved and current_scene == "WORLD" and (dx != 0 or dy != 0):
        step_count += 1


def handle_world_tile_transitions():
    """Check if player has moved off screen edge and transition to adjacent tile."""
    global player_x, player_y, current_tile

    transitioned = False

    if player_x < 0:
        new_tile = gd.WORLD_MAP[current_tile].get("west")
        if new_tile:
            fade_transition()
            current_tile = new_tile
            player_x = WIDTH - 40
            load_world_tile(current_tile)
            transitioned = True
        else:
            player_x = 0

    elif player_x > WIDTH:
        new_tile = gd.WORLD_MAP[current_tile].get("east")
        if new_tile:
            fade_transition()
            current_tile = new_tile
            player_x = 20
            load_world_tile(current_tile)
            transitioned = True
        else:
            player_x = WIDTH

    if player_y < 0:
        new_tile = gd.WORLD_MAP[current_tile].get("north")
        if new_tile:
            fade_transition()
            current_tile = new_tile
            player_y = HEIGHT - 40
            load_world_tile(current_tile)
            transitioned = True
        else:
            player_y = 0

    elif player_y > HEIGHT:
        new_tile = gd.WORLD_MAP[current_tile].get("south")
        if new_tile:
            fade_transition()
            current_tile = new_tile
            player_y = 20
            load_world_tile(current_tile)
            transitioned = True
        else:
            player_y = HEIGHT

    # Random encounter check using centralized rates from game_data
    if not transitioned and current_tile in gd.WORLD_MAP:
        tile_type = gd.WORLD_MAP[current_tile]["tile_type"]
        encounter_rate = gd.ENCOUNTER_RATES.get(tile_type, 0.0)

        if encounter_rate > 0 and random.random() < encounter_rate:
            start_battle()


def get_town_door_player_is_on(player_rect):
    """Return the door dict the player is overlapping, or None."""
    for door in DOORS_TOWN:
        if player_rect.colliderect(door["rect"]):
            return door
    return None


def get_player_rect():
    """Return a rect representing the player's current position."""
    return pygame.Rect(
        player_x - PLAYER_SIZE // 2,
        player_y - PLAYER_SIZE // 2,
        PLAYER_SIZE,
        PLAYER_SIZE,
    )


def try_talk_to_npc():
    """Check if player is near an NPC and initiate dialog."""
    global dialog_active, dialog_lines, dialog_index, quest_flags

    player_rect = get_player_rect()

    # Small interaction range
    interact_rect = player_rect.inflate(16, 16)

    for npc in TOWN_NPCS:
        npc_rect = pygame.Rect(npc["x"], npc["y"], TILE_SIZE, TILE_SIZE)
        if interact_rect.colliderect(npc_rect):
            # Quest giver logic
            if npc["role"] == "quest_giver":
                if not quest_flags["shrine_quest_accepted"]:
                    dialog_lines = npc["dialog_before"] + [
                        "",
                        ">>> Quest accepted: 'Clear the Old Shrine.'",
                    ]
                    quest_flags["shrine_quest_accepted"] = True
                elif not quest_flags["shrine_quest_completed"]:
                    dialog_lines = npc["dialog_after_accept"]
                else:
                    dialog_lines = npc["dialog_after_complete"]
            else:
                dialog_lines = npc["dialog"]

            dialog_index = 0
            dialog_active = True
            return  # only talk to the first one we find


def handle_area_transition(player_rect):
    """
    If the player walks off the screen, move to a neighboring area and
    place them on the opposite edge.

    For now we only support:
      - TOWN (0,0) <-> TOWN (1,0) horizontally
      - TOWN (0,0) -> FIELD (0,1) by walking down
      - FIELD (0,1) -> TOWN (0,0) by walking up
    """
    global current_area, area_x, area_y, player_x, player_y

    prev_area = current_area
    prev_x = area_x
    prev_y = area_y

    # --- move horizontally inside same region ---
    if current_area == "TOWN":
        if player_rect.right > WIDTH:
            # move to east town screen if it exists
            if ("TOWN", area_x + 1, area_y) in AREA_DRAWERS:
                area_x += 1
                player_rect.left = 0
            else:
                player_rect.right = WIDTH
        elif player_rect.left < 0:
            if ("TOWN", area_x - 1, area_y) in AREA_DRAWERS:
                area_x -= 1
                player_rect.right = WIDTH
            else:
                player_rect.left = 0

    # --- vertical transitions between TOWN (0,0) and FIELD (0,1) ---
    # from town center down into field
    if current_area == "TOWN" and area_x == 0 and area_y == 0:
        if player_rect.bottom > HEIGHT:
            current_area = "FIELD"
            area_x = 0
            area_y = 1
            player_rect.top = 0  # appear at top edge of field

    # from field back up into town center
    elif current_area == "FIELD" and area_x == 0 and area_y == 1:
        if player_rect.top < 0:
            current_area = "TOWN"
            area_x = 0
            area_y = 0
            player_rect.bottom = HEIGHT  # appear at bottom edge of town

    # clamp horizontally in field (no neighbors yet)
    if current_area == "FIELD":
        if player_rect.left < 0:
            player_rect.left = 0
        if player_rect.right > WIDTH:
            player_rect.right = WIDTH
        if player_rect.bottom > HEIGHT:
            player_rect.bottom = HEIGHT

    # Update global player position from rect
    player_x = player_rect.centerx
    player_y = player_rect.centery


# ----------- DRAWING -----------
def draw_tile(x, y, ch):
    """Draw a single tile at tile coordinates (x, y)."""
    px = x * TILE_SIZE
    py = y * TILE_SIZE

    if ch == "G" or ch == ".":
        pygame.draw.rect(SCREEN, GRASS, (px, py, TILE_SIZE, TILE_SIZE))
    elif ch == "R":
        pygame.draw.rect(SCREEN, ROAD, (px, py, TILE_SIZE, TILE_SIZE))
    elif ch == "H":
        pygame.draw.rect(SCREEN, HOUSE, (px, py, TILE_SIZE, TILE_SIZE))
    elif ch == "D":
        pygame.draw.rect(SCREEN, HOUSE, (px, py, TILE_SIZE, TILE_SIZE))
        door_rect = pygame.Rect(
            px + TILE_SIZE // 4,
            py + TILE_SIZE // 4,
            TILE_SIZE // 2,
            TILE_SIZE * 3 // 4,
        )
        pygame.draw.rect(SCREEN, DOOR, door_rect)
    elif ch == "^":
        pygame.draw.rect(
            SCREEN, HOUSE, (px, py + TILE_SIZE // 4, TILE_SIZE, TILE_SIZE * 3 // 4)
        )
        pygame.draw.rect(SCREEN, ROOF, (px, py, TILE_SIZE, TILE_SIZE // 3))
    else:
        pygame.draw.rect(SCREEN, GRASS, (px, py, TILE_SIZE, TILE_SIZE))


def draw_town_doors(player_rect):
    """Draw interactable door areas and show highlight/prompt when player is close."""
    global active_building

    door_rects = []  # (rect, name)

    # Inn door
    inn_door = pygame.Rect(140, 165, 40, 40)
    door_rects.append((inn_door, "Inn"))

    # Item shop door
    item_door = pygame.Rect(740, 165, 40, 40)
    door_rects.append((item_door, "Item Shop"))

    # Weapon shop door
    weapon_door = pygame.Rect(140, 455, 40, 40)
    door_rects.append((weapon_door, "Weapon Shop"))

    # draw doors
    for rect, name in door_rects:
        pygame.draw.rect(SCREEN, (120, 70, 20), rect)

    # check for overlap with player
    for rect, name in door_rects:
        if player_rect.colliderect(rect):
            pygame.draw.rect(SCREEN, (255, 255, 0), rect, 3)

            prompt = FONT.render(f"Press ENTER to enter {name}", True, (255, 255, 255))
            SCREEN.blit(prompt, (rect.x - 20, rect.y - 30))

            active_building = name
            return

    active_building = None


# Track which building is active
active_building = None


def draw_town_npcs(surface):
    """Draw NPCs in the town area (only when in TOWN 0,0)."""
    # Only draw NPCs in the main town area
    if current_area != "TOWN" or area_x != 0 or area_y != 0:
        return

    for npc in TOWN_NPCS:
        rect = pygame.Rect(npc["x"], npc["y"], TILE_SIZE, TILE_SIZE)
        # Simple placeholder: blue-ish square for NPCs
        pygame.draw.rect(surface, (80, 120, 255), rect)
        name_text = FONT.render(npc["name"], True, (255, 255, 255))
        surface.blit(name_text, (npc["x"], npc["y"] - 14))


# --- Area drawing functions ---


def draw_town_0_0(surface, player_rect):
    """
    Starting town screen: inn (top-left), item shop (top-right),
    weapon shop (bottom-left), road, grass, etc.

    This is the main town area at coordinates (0, 0).
    """
    draw_town()


def draw_town_1_0(surface, player_rect):
    """East side of town – more houses, no shops wired yet."""
    surface.fill((10, 40, 10))  # grass

    # simple dirt road across the middle
    road_rect = pygame.Rect(0, HEIGHT // 2 - 40, WIDTH, 80)
    pygame.draw.rect(surface, (150, 115, 70), road_rect)

    # some extra houses to imply a bigger town
    house_color = (200, 90, 60)
    roof_color = (170, 50, 40)
    door_color = (90, 50, 20)

    # left house
    left_house = pygame.Rect(80, 120, 180, 140)
    pygame.draw.rect(surface, house_color, left_house)
    pygame.draw.rect(
        surface, roof_color, (left_house.x, left_house.y - 20, left_house.width, 20)
    )
    pygame.draw.rect(
        surface, door_color, (left_house.centerx - 10, left_house.bottom - 35, 20, 35)
    )

    # right house
    right_house = pygame.Rect(WIDTH - 260, 120, 180, 140)
    pygame.draw.rect(surface, house_color, right_house)
    pygame.draw.rect(
        surface, roof_color, (right_house.x, right_house.y - 20, right_house.width, 20)
    )
    pygame.draw.rect(
        surface, door_color, (right_house.centerx - 10, right_house.bottom - 35, 20, 35)
    )

    # Player
    pygame.draw.rect(surface, PLAYER_COLOR, player_rect)

    # "Town East" label
    label = FONT.render("Town East", True, (255, 255, 255))
    surface.blit(label, (WIDTH // 2 - label.get_width() // 2, 20))


def draw_field_0_1(surface, player_rect):
    """Simple road + grass field south of town."""
    surface.fill((5, 60, 5))

    # vertical road up the middle
    road_rect = pygame.Rect(WIDTH // 2 - 60, 0, 120, HEIGHT)
    pygame.draw.rect(surface, (140, 110, 70), road_rect)

    # a couple of trees as obstacles / landmarks
    tree_trunk = (90, 60, 30)
    tree_leaves = (20, 100, 20)

    for x in (140, WIDTH - 180):
        trunk = pygame.Rect(x, HEIGHT // 2 + 40, 20, 40)
        pygame.draw.rect(surface, tree_trunk, trunk)
        pygame.draw.circle(surface, tree_leaves, (x + 10, HEIGHT // 2 + 30), 35)

    # Player
    pygame.draw.rect(surface, PLAYER_COLOR, player_rect)

    label = FONT.render("South Road", True, (255, 255, 255))
    surface.blit(label, (WIDTH // 2 - label.get_width() // 2, 20))


# Area registry: maps (area_name, x, y) -> draw function
AREA_DRAWERS = {
    ("TOWN", 0, 0): draw_town_0_0,
    ("TOWN", 1, 0): draw_town_1_0,
    ("FIELD", 0, 1): draw_field_0_1,
}


def draw_current_area(surface, player_rect):
    """Dispatch to the correct area draw function."""
    key = (current_area, area_x, area_y)
    func = AREA_DRAWERS.get(key, draw_town_0_0)  # safe fallback
    func(surface, player_rect)


# ----------- WORLD TILE LOADING FUNCTIONS -----------


def load_town_center():
    """Town center background."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((180, 150, 100))  # dirt/town color
    # Add some texture
    for i in range(50):
        x = random.randint(0, WIDTH)
        y = random.randint(0, HEIGHT)
        pygame.draw.circle(surf, (170, 140, 90), (x, y), 3)
    return surf


def load_town_edge():
    """Town edge background."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((170, 130, 90))
    # Add grass patches
    for i in range(30):
        x = random.randint(0, WIDTH)
        y = random.randint(0, HEIGHT)
        pygame.draw.circle(surf, (100, 140, 80), (x, y), 8)
    return surf


def load_forest_route():
    """Forest area background."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((40, 80, 40))  # dark green
    # Add darker grass texture
    for i in range(80):
        x = random.randint(0, WIDTH)
        y = random.randint(0, HEIGHT)
        pygame.draw.circle(surf, (30, 70, 30), (x, y), 4)
    return surf


def load_grass_field():
    """Grass field background."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((90, 180, 90))  # bright green
    # Add lighter patches
    for i in range(60):
        x = random.randint(0, WIDTH)
        y = random.randint(0, HEIGHT)
        pygame.draw.circle(surf, (100, 200, 100), (x, y), 6)
    return surf


def load_mountain():
    """Mountain area background."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((100, 100, 120))  # gray rocky
    # Add rocks
    for i in range(40):
        x = random.randint(0, WIDTH)
        y = random.randint(0, HEIGHT)
        pygame.draw.circle(surf, (80, 80, 100), (x, y), 5)
    return surf


def load_lake():
    """Lake/water area background."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((60, 120, 180))  # blue water
    # Add water ripples
    for i in range(50):
        x = random.randint(0, WIDTH)
        y = random.randint(0, HEIGHT)
        pygame.draw.circle(surf, (70, 130, 190), (x, y), 7)
    return surf


def load_blank():
    """Fallback blank background."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((0, 0, 0))  # black
    return surf


def place_forest_trees():
    """Return list of tree objects for forest tiles."""
    objects = []
    for i in range(10):
        x = random.randint(80, WIDTH - 80)
        y = random.randint(80, HEIGHT - 80)
        # Draw tree on surface
        tree_surf = pygame.Surface((40, 60), pygame.SRCALPHA)
        # Trunk
        pygame.draw.rect(tree_surf, (60, 40, 20), (15, 35, 10, 25))
        # Leaves
        pygame.draw.circle(tree_surf, (20, 80, 20), (20, 20), 20)

        rect = pygame.Rect(x, y, 40, 60)
        objects.append({"image": tree_surf, "pos": (x, y), "rect": rect, "solid": True})
    return objects


def place_boulders():
    """Return list of boulder objects for field tiles."""
    objects = []
    for i in range(8):
        x = random.randint(80, WIDTH - 80)
        y = random.randint(80, HEIGHT - 80)
        size = random.randint(25, 40)
        boulder_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(
            boulder_surf, (120, 120, 120), (size // 2, size // 2), size // 2
        )
        pygame.draw.circle(
            boulder_surf, (100, 100, 100), (size // 2 - 3, size // 2 - 3), size // 2 - 5
        )

        rect = pygame.Rect(x, y, size, size)
        objects.append(
            {"image": boulder_surf, "pos": (x, y), "rect": rect, "solid": True}
        )
    return objects


def place_rocks():
    """Return list of rock objects for mountain tiles."""
    objects = []
    for i in range(12):
        x = random.randint(60, WIDTH - 60)
        y = random.randint(60, HEIGHT - 60)
        size = random.randint(30, 50)
        rock_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.polygon(
            rock_surf, (80, 80, 100), [(size // 2, 0), (size, size), (0, size)]
        )

        rect = pygame.Rect(x, y, size, size)
        objects.append({"image": rock_surf, "pos": (x, y), "rect": rect, "solid": True})
    return objects


def place_water_reeds():
    """Return list of reed objects for lake tiles."""
    objects = []
    for i in range(15):
        x = random.randint(60, WIDTH - 60)
        y = random.randint(60, HEIGHT - 60)
        reed_surf = pygame.Surface((10, 30), pygame.SRCALPHA)
        pygame.draw.line(reed_surf, (40, 100, 60), (5, 30), (5, 0), 3)

        objects.append(
            {"image": reed_surf, "pos": (x, y), "rect": None, "solid": False}
        )
    return objects


def generate_tile_objects(tile_name):
    """Generate objects for a tile based on its type (unified generator)."""
    if tile_name not in gd.WORLD_MAP:
        return []

    tile_type = gd.WORLD_MAP[tile_name]["tile_type"]

    if tile_type == "forest":
        return place_forest_trees()
    elif tile_type == "field":
        return place_boulders()
    elif tile_type == "mountain":
        return place_rocks()
    elif tile_type == "lake":
        return place_water_reeds()
    else:
        return []


def load_world_tile(tile_id):
    """Load the correct area graphics based on tile_type."""
    global tile_background, tile_objects

    # --- FULL STATE RESET WHEN ENTERING A NEW MAP ---
    global CURRENT_INTERIOR, world_menu_open, dialog_active, step_count
    CURRENT_INTERIOR = None
    world_menu_open = False
    dialog_active = False

    # Reset step counter so movement doesn't trigger effects on spawn
    step_count = 0

    data = gd.WORLD_MAP[tile_id]
    tile_type = data["tile_type"]

    if tile_type == "town":
        tile_background = load_town_center()
        tile_objects = []
    elif tile_type == "town_edge":
        tile_background = load_town_edge()
        tile_objects = []
    elif tile_type == "forest":
        tile_background = load_forest_route()
        tile_objects = place_forest_trees()
    elif tile_type == "field":
        tile_background = load_grass_field()
        tile_objects = place_boulders()
    elif tile_type == "mountain":
        tile_background = load_mountain()
        tile_objects = place_rocks()
    elif tile_type == "lake":
        tile_background = load_lake()
        tile_objects = place_water_reeds()
    else:
        tile_background = load_blank()
        tile_objects = []


def fade_transition():
    """Fade out/in effect for tile transitions."""
    for alpha in range(0, 255, 15):
        fade_surface = pygame.Surface((WIDTH, HEIGHT))
        fade_surface.fill(BLACK)
        fade_surface.set_alpha(alpha)
        SCREEN.blit(fade_surface, (0, 0))
        pygame.display.update()
        CLOCK.tick(60)

    # Fade back in
    for alpha in range(255, 0, -15):
        fade_surface = pygame.Surface((WIDTH, HEIGHT))
        fade_surface.fill(BLACK)
        fade_surface.set_alpha(alpha)
        SCREEN.blit(fade_surface, (0, 0))
        pygame.display.update()
        CLOCK.tick(60)


def draw_minimap(screen):
    """Draw FF-style minimap in top-right corner."""
    mini_size = 180
    tile_size = 28
    mini = pygame.Surface((mini_size, mini_size))
    mini.fill((20, 20, 20))

    # Border
    pygame.draw.rect(mini, (100, 100, 150), (0, 0, mini_size, mini_size), 2)

    # Draw all known tiles
    for tile_id, data in gd.WORLD_MAP.items():
        if tile_id in gd.WORLD_POSITIONS:
            grid_x, grid_y = gd.WORLD_POSITIONS[tile_id]

            # Offset to center the map
            offset_x = 2
            offset_y = 3

            x = (grid_x + offset_x) * tile_size + 10
            y = (grid_y + offset_y) * tile_size + 10

            # Color by biome
            tile_type = data["tile_type"]
            if tile_type == "town":
                color = (200, 200, 0)  # yellow
            elif tile_type == "town_edge":
                color = (180, 150, 100)  # tan
            elif tile_type == "forest":
                color = (0, 150, 0)  # green
            elif tile_type == "field":
                color = (100, 200, 100)  # light green
            elif tile_type == "mountain":
                color = (120, 120, 150)  # gray
            elif tile_type == "lake":
                color = (60, 120, 200)  # blue
            else:
                color = (80, 80, 80)  # gray

            pygame.draw.rect(mini, color, (x, y, tile_size - 4, tile_size - 4))

    # Highlight current tile
    if current_tile in gd.WORLD_POSITIONS:
        grid_x, grid_y = gd.WORLD_POSITIONS[current_tile]
        offset_x = 2
        offset_y = 3
        x = (grid_x + offset_x) * tile_size + 10
        y = (grid_y + offset_y) * tile_size + 10
        pygame.draw.rect(mini, (255, 255, 255), (x, y, tile_size - 4, tile_size - 4), 3)

    # Title
    title = FONT.render("Map", True, (255, 255, 255))
    mini.blit(title, (mini_size // 2 - title.get_width() // 2, 4))

    screen.blit(mini, (WIDTH - mini_size - 10, 10))


def draw_town():
    """Draw the town tilemap and base UI."""
    SCREEN.fill(GRASS)

    # Tilemap
    for y in range(ROWS):
        row = TOWN_MAP[y]
        for x in range(len(row)):
            draw_tile(x, y, row[x])

    # Create player rect (used for door highlighting and drawing)
    player_rect = pygame.Rect(0, 0, PLAYER_SIZE, PLAYER_SIZE)
    player_rect.center = (int(player_x), int(player_y))

    # Draw doors with highlighting
    draw_town_doors(player_rect)

    # Draw NPCs
    draw_town_npcs(SCREEN)

    # Draw player on top of everything
    pygame.draw.rect(SCREEN, PLAYER_COLOR, player_rect)

    # Simple UI strip at top-left for instructions
    ui_rect = pygame.Rect(8, 8, 360, 56)
    pygame.draw.rect(SCREEN, UI_BG, ui_rect)
    pygame.draw.rect(SCREEN, UI_TEXT, ui_rect, 1)

    text1 = FONT.render("Arrows / WASD: Move", True, UI_TEXT)
    text2 = FONT.render("B: Start Battle   ESC: Overworld Menu", True, UI_TEXT)
    SCREEN.blit(text1, (ui_rect.x + 8, ui_rect.y + 6))
    SCREEN.blit(text2, (ui_rect.x + 8, ui_rect.y + 28))

    if debug_message:
        msg = FONT.render(debug_message, True, UI_TEXT)
        SCREEN.blit(msg, (8, HEIGHT - 26))


def draw_world_tile():
    """Draw the current world tile (multi-screen overworld)."""
    # Draw background
    if tile_background:
        SCREEN.blit(tile_background, (0, 0))
    else:
        SCREEN.fill(BLACK)

    # Draw tile objects (trees, boulders, etc.)
    for obj in tile_objects:
        SCREEN.blit(obj["image"], obj["pos"])

    # Draw player
    player_rect = pygame.Rect(0, 0, PLAYER_SIZE, PLAYER_SIZE)
    player_rect.center = (int(player_x), int(player_y))
    pygame.draw.rect(SCREEN, PLAYER_COLOR, player_rect)

    # Draw minimap
    draw_minimap(SCREEN)

    # UI strip at bottom-left for instructions
    ui_rect = pygame.Rect(8, HEIGHT - 70, 540, 56)
    pygame.draw.rect(SCREEN, UI_BG, ui_rect)
    pygame.draw.rect(SCREEN, UI_TEXT, ui_rect, 1)

    text1 = FONT.render("Arrows/WASD: Move  ESC: Menu  B: Battle", True, UI_TEXT)

    # Show biome name and step counter
    tile_type = gd.WORLD_MAP[current_tile]["tile_type"]
    biome_name = tile_type.replace("_", " ").title()
    encounter_rate = gd.ENCOUNTER_RATES.get(tile_type, 0.0)
    text2 = FONT.render(
        f"{current_tile} ({biome_name}) | Steps: {step_count} | Rate: {encounter_rate*100:.1f}%",
        True,
        (200, 200, 255),
    )

    SCREEN.blit(text1, (ui_rect.x + 8, ui_rect.y + 6))
    SCREEN.blit(text2, (ui_rect.x + 8, ui_rect.y + 32))

    # Show prompt to enter town if on TOWN_CENTER
    if current_tile == "TOWN_CENTER":
        prompt_rect = pygame.Rect(WIDTH // 2 - 150, HEIGHT // 2 - 40, 300, 80)
        pygame.draw.rect(SCREEN, (40, 40, 80), prompt_rect)
        pygame.draw.rect(SCREEN, (255, 255, 0), prompt_rect, 3)

        prompt1 = FONT.render("TOWN GATE", True, (255, 255, 0))
        prompt2 = FONT.render("Press ENTER to", True, (255, 255, 255))
        prompt3 = FONT.render("enter town", True, (255, 255, 255))
        SCREEN.blit(
            prompt1,
            (prompt_rect.x + 150 - prompt1.get_width() // 2, prompt_rect.y + 10),
        )
        SCREEN.blit(
            prompt2,
            (prompt_rect.x + 150 - prompt2.get_width() // 2, prompt_rect.y + 35),
        )
        SCREEN.blit(
            prompt3,
            (prompt_rect.x + 150 - prompt3.get_width() // 2, prompt_rect.y + 55),
        )

    if debug_message:
        msg = FONT.render(debug_message, True, (255, 255, 0))
        msg_rect = pygame.Rect(8, 8, msg.get_width() + 16, 30)
        pygame.draw.rect(SCREEN, (40, 40, 80), msg_rect)
        pygame.draw.rect(SCREEN, (255, 255, 0), msg_rect, 2)
        SCREEN.blit(msg, (msg_rect.x + 8, msg_rect.y + 6))


def draw_interior(title_text, counter_color):
    """Draw a simple interior scene with title and counter."""
    # Dark background
    SCREEN.fill((15, 15, 40))

    # Simple walls
    pygame.draw.rect(SCREEN, (40, 40, 80), (80, 60, WIDTH - 160, HEIGHT - 120), 4)

    # Simple counter/desk
    pygame.draw.rect(SCREEN, counter_color, (140, 140, WIDTH - 280, 80))

    # Title label
    title = FONT.render(title_text, True, WHITE)
    title_rect = title.get_rect(center=(WIDTH // 2, 90))
    SCREEN.blit(title, title_rect)

    # Player standing at bottom
    player_rect = pygame.Rect(0, 0, PLAYER_SIZE, PLAYER_SIZE)
    player_rect.center = (int(player_x), int(player_y))
    pygame.draw.rect(SCREEN, (230, 230, 230), player_rect)

    # Exit prompt
    prompt = FONT.render("Press Enter / Esc to leave", True, WHITE)
    prompt_rect = prompt.get_rect(center=(WIDTH // 2, HEIGHT - 40))
    SCREEN.blit(prompt, prompt_rect)


# ============================================================================
# UNIFIED INTERIOR SYSTEM
# ============================================================================


def load_interior(name):
    """Load an interior by name from INTERIORS data."""
    global interior_surface, shop_selection, inn_prompt_active, CURRENT_INTERIOR

    if name not in gd.INTERIORS:
        return

    CURRENT_INTERIOR = name
    data = gd.INTERIORS[name]

    # Create background
    interior_surface = pygame.Surface((WIDTH, HEIGHT))
    interior_surface.fill((60, 40, 40))

    # Draw walls
    pygame.draw.rect(
        interior_surface, (40, 40, 80), (80, 60, WIDTH - 160, HEIGHT - 120), 4
    )

    # Draw counter
    counter_color = (100, 60, 40) if data["tile_type"] == "shop" else (80, 80, 120)
    pygame.draw.rect(interior_surface, counter_color, (140, 140, WIDTH - 280, 80))

    # NPC placeholder (simple sprite)
    pygame.draw.rect(
        interior_surface,
        (230, 200, 150),
        pygame.Rect(WIDTH // 2 - 20, HEIGHT // 2 - 60, 40, 60),
    )

    # Reset UI state
    shop_selection = 0
    inn_prompt_active = False


def leave_interior():
    """Exit current interior and return to town."""
    global CURRENT_INTERIOR, current_scene, player_x, player_y

    # Find the door we entered from
    for door in DOORS_TOWN:
        if door.get("interior") == CURRENT_INTERIOR:
            player_x, player_y = door["return_pos"]
            break

    CURRENT_INTERIOR = None
    current_scene = "TOWN"


def draw_interior_ui():
    """Draw the UI for the current interior."""
    global shop_selection

    if not CURRENT_INTERIOR or CURRENT_INTERIOR not in gd.INTERIORS:
        return

    data = gd.INTERIORS[CURRENT_INTERIOR]
    npc_name = data["npc_name"]
    welcome = data["npc_welcome"]

    # Draw background
    if interior_surface:
        SCREEN.blit(interior_surface, (0, 0))

    # Draw player
    player_rect = pygame.Rect(0, 0, PLAYER_SIZE, PLAYER_SIZE)
    player_rect.center = (int(player_x), int(player_y))
    pygame.draw.rect(SCREEN, PLAYER_COLOR, player_rect)

    # NPC name
    name_txt = FONT.render(npc_name, True, (255, 255, 0))
    SCREEN.blit(name_txt, (WIDTH // 2 - name_txt.get_width() // 2, 80))

    # Greeting
    welcome_txt = FONT.render(welcome, True, WHITE)
    SCREEN.blit(welcome_txt, (WIDTH // 2 - welcome_txt.get_width() // 2, 110))

    # Shop UI
    if CURRENT_INTERIOR in ("ITEM_SHOP", "WEAPON_SHOP", "ARMOR_SHOP"):
        items = data["inventory"]
        prices = data["buy_prices"]

        # Draw shop menu
        menu_y = 250
        for i, item in enumerate(items):
            color = (255, 255, 0) if i == shop_selection else WHITE
            price = prices.get(item, 0)
            line = f"{item} - {price}g"
            txt = FONT.render(line, True, color)
            SCREEN.blit(txt, (WIDTH // 2 - 100, menu_y + i * 25))

        # Gold display
        gold_txt = FONT.render(f"Gold: {inv.player_gold}g", True, (255, 255, 0))
        SCREEN.blit(gold_txt, (WIDTH - gold_txt.get_width() - 20, 20))

        # Instructions
        instr = FONT.render(
            "↑↓ Select   Enter: Buy   Esc: Leave", True, (180, 180, 180)
        )
        SCREEN.blit(instr, (WIDTH // 2 - instr.get_width() // 2, HEIGHT - 40))

    # Inn UI
    elif CURRENT_INTERIOR == "INN":
        price = data["heal_price"]
        line = f"Stay the night? {price} gold."
        txt = FONT.render(line, True, WHITE)
        SCREEN.blit(txt, (WIDTH // 2 - txt.get_width() // 2, HEIGHT // 2))

        instr = FONT.render("Enter: Yes   Esc: No", True, (180, 180, 180))
        SCREEN.blit(instr, (WIDTH // 2 - instr.get_width() // 2, HEIGHT // 2 + 40))

        # Gold display
        gold_txt = FONT.render(f"Gold: {inv.player_gold}g", True, (255, 255, 0))
        SCREEN.blit(gold_txt, (WIDTH - gold_txt.get_width() - 20, 20))


def attempt_purchase(item_id, price):
    """Attempt to buy an item from a shop."""
    global debug_message

    if inv.player_gold >= price:
        inv.player_gold -= price
        add_item(item_id, 1)
        debug_message = f"Bought {item_id}!"
    else:
        debug_message = "Not enough gold!"


def attempt_inn_rest():
    """Attempt to rest at the inn."""
    global debug_message

    if "INN" not in gd.INTERIORS:
        return

    price = gd.INTERIORS["INN"]["heal_price"]

    if inv.player_gold >= price:
        inv.player_gold -= price
        # Heal all party members
        for member in party_list:
            if hasattr(member, "hp"):
                member.hp = member.max_hp
            if hasattr(member, "mp"):
                member.mp = member.max_mp
        debug_message = "Party healed! Rested well."
        leave_interior()
    else:
        debug_message = "Not enough gold!"


def draw_item_shop_interior(screen, font, player_rect):
    """Draw the item shop interior and, if open, the shop UI."""
    global shop_ui_open, shop_menu_index, shopkeeper_rect, itemshop_door_rect

    # Background + room frame
    screen.fill((5, 5, 25))
    room_rect = pygame.Rect(20, 40, WIDTH - 40, HEIGHT - 80)
    pygame.draw.rect(screen, (15, 15, 40), room_rect)
    pygame.draw.rect(screen, (120, 120, 200), room_rect, 2)

    # Title
    title = font.render("Item Shop", True, WHITE)
    title_rect = title.get_rect(center=(WIDTH // 2, 60))
    screen.blit(title, title_rect)

    # Walls band
    wall_thickness = 50
    wall_color = (30, 130, 50)
    pygame.draw.rect(
        screen,
        wall_color,
        (room_rect.x + 10, room_rect.y + 80, room_rect.width - 20, wall_thickness),
    )
    pygame.draw.rect(
        screen,
        wall_color,
        (room_rect.x + 10, room_rect.y + 80, 24, room_rect.height - 120),
    )
    pygame.draw.rect(
        screen,
        wall_color,
        (room_rect.right - 34, room_rect.y + 80, 24, room_rect.height - 120),
    )
    pygame.draw.rect(
        screen,
        wall_color,
        (room_rect.x + 10, room_rect.bottom - 50, room_rect.width - 20, 24),
    )

    # Back shelves
    shelf_color = (120, 120, 220)
    shelf_w = 120
    shelf_h = 40
    shelf_y = room_rect.y + 150
    shelf_xs = (
        room_rect.x + 80,
        room_rect.centerx - shelf_w // 2,
        room_rect.right - 80 - shelf_w,
    )
    for bx in shelf_xs:
        pygame.draw.rect(screen, shelf_color, (bx, shelf_y, shelf_w, shelf_h))

    # Front shelves
    front_y = room_rect.y + 260
    front_w = 70
    front_h = 80
    front_xs = (
        room_rect.x + 120,
        room_rect.x + 210,
        room_rect.centerx - front_w // 2,
        room_rect.right - 210 - front_w,
        room_rect.right - 120 - front_w,
    )
    for bx in front_xs:
        pygame.draw.rect(screen, shelf_color, (bx, front_y, front_w, front_h))

    # Counter + shopkeeper up top
    counter_color = (150, 90, 40)
    counter_top = shelf_y + 60
    counter_rect = pygame.Rect(
        room_rect.x + 120, counter_top, room_rect.width - 240, 32
    )
    pygame.draw.rect(screen, counter_color, counter_rect)
    pygame.draw.rect(screen, counter_color, (counter_rect.x, counter_rect.y, 24, 60))
    pygame.draw.rect(
        screen, counter_color, (counter_rect.right - 24, counter_rect.y, 24, 60)
    )

    # Shopkeeper
    keeper_color = (240, 220, 60)
    shopkeeper_rect = pygame.Rect(0, 0, 24, 24)
    shopkeeper_rect.centerx = counter_rect.centerx
    shopkeeper_rect.bottom = counter_rect.top
    pygame.draw.rect(screen, keeper_color, shopkeeper_rect)

    # Bottom door
    door_w = 40
    door_h = 26
    door_x = WIDTH // 2 - door_w // 2
    door_y = room_rect.bottom - 10
    itemshop_door_rect = pygame.Rect(door_x, door_y, door_w, door_h)
    pygame.draw.rect(screen, (160, 40, 80), itemshop_door_rect)

    # Player character
    pygame.draw.rect(screen, WHITE, player_rect)

    # Hint
    hint = font.render("Enter: Talk / Door   Esc: Leave", True, WHITE)
    hint_rect = hint.get_rect(center=(WIDTH // 2, HEIGHT - 30))
    screen.blit(hint, hint_rect)

    # --- Shop UI overlay ---
    if shop_ui_open:
        panel_w = WIDTH - 260
        panel_h = 150
        panel_rect = pygame.Rect(
            (WIDTH - panel_w) // 2,
            HEIGHT - panel_h - 50,
            panel_w,
            panel_h,
        )
        pygame.draw.rect(screen, (10, 10, 35), panel_rect)
        pygame.draw.rect(screen, WHITE, panel_rect, 2)

        # Gold display
        gold_text = font.render(f"Gold: {inv.player_gold}", True, MENU_HILIGHT)
        screen.blit(gold_text, (panel_rect.x + 12, panel_rect.y + 10))

        # Item list
        start = 0
        end = min(len(SHOP_STOCK), start + SHOP_VISIBLE_MAX)

        y = panel_rect.y + 30
        for i, item in enumerate(SHOP_STOCK[start:end]):
            idx = start + i
            name = item["name"]
            price = item["price"]
            qty = inv.inventory.get(item["id"], 0)

            color = MENU_HILIGHT if idx == shop_menu_index else WHITE
            label = f"{name:<10}  {price:>3} G   (Have: {qty})"
            text = font.render(label, True, color)
            screen.blit(text, (panel_rect.x + 20, y))
            y += 22

        help_text = font.render(
            "Up/Down: Select   Enter: Buy   Esc: Cancel", True, WHITE
        )
        help_rect = help_text.get_rect(
            midbottom=(panel_rect.centerx, panel_rect.bottom - 8)
        )
        screen.blit(help_text, help_rect)

    # expose key rects to main() for interaction
    draw_item_shop_interior.shopkeeper_rect = shopkeeper_rect
    draw_item_shop_interior.itemshop_door_rect = itemshop_door_rect


def draw_overworld_menu():
    """Overlay pause-style overworld menu with MAIN/INVENTORY modes."""
    # Dim the world
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    SCREEN.blit(overlay, (0, 0))

    panel_w = WIDTH - 200
    panel_h = HEIGHT - 160
    panel_rect = pygame.Rect(
        (WIDTH - panel_w) // 2,
        (HEIGHT - panel_h) // 2,
        panel_w,
        panel_h,
    )

    pygame.draw.rect(SCREEN, (20, 20, 40), panel_rect)
    pygame.draw.rect(SCREEN, WHITE, panel_rect, 2)

    if menu_mode == "MAIN":
        draw_overworld_main_menu(SCREEN, panel_rect)
    elif menu_mode == "INVENTORY":
        draw_overworld_inventory(SCREEN, panel_rect)


def draw_overworld_main_menu(screen, panel_rect):
    """Draw the main menu options."""
    title = FONT.render("Menu", True, WHITE)
    title_rect = title.get_rect(midtop=(panel_rect.centerx, panel_rect.y + 10))
    screen.blit(title, title_rect)

    options = ["Resume", "Inventory", "Quit"]
    y = title_rect.bottom + 20

    for i, text in enumerate(options):
        color = WHITE
        if i == menu_index:
            color = MENU_HILIGHT
        label = FONT.render(text, True, color)
        screen.blit(label, (panel_rect.x + 40, y))
        y += 26


def draw_overworld_inventory(screen, panel_rect):
    """Draw the inventory view."""
    # Title
    title = FONT.render("Inventory", True, WHITE)
    title_rect = title.get_rect(midtop=(panel_rect.centerx, panel_rect.y + 10))
    screen.blit(title, title_rect)

    # Show current gold
    gold_text = FONT.render(f"Gold: {inv.player_gold}", True, MENU_HILIGHT)
    screen.blit(gold_text, (panel_rect.x + 20, title_rect.bottom + 10))

    # List items
    items = [(k, v) for k, v in inv.inventory.items() if v > 0]
    y = title_rect.bottom + 40

    if not items:
        msg = FONT.render("You have no items.", True, (200, 200, 200))
        screen.blit(msg, (panel_rect.x + 20, y))
        return

    for i, (item_id, qty) in enumerate(items):
        color = WHITE
        if i == inv_cursor:
            color = MENU_HILIGHT

        label = FONT.render(f"{item_id} x{qty}", True, color)
        screen.blit(label, (panel_rect.x + 20, y))
        y += 22

    # Small hint at bottom
    hint = FONT.render("ESC: Back", True, (200, 200, 200))
    hint_rect = hint.get_rect(
        bottomright=(panel_rect.right - 10, panel_rect.bottom - 10)
    )
    screen.blit(hint, hint_rect)


def launch_battle():
    """Launch combat.py as a subprocess."""
    global debug_message
    subprocess.run([sys.executable, "combat.py"])
    debug_message = "Returned from battle."


def start_battle():
    """Alias for launch_battle, used by random encounters."""
    launch_battle()


def draw_weapon_shop_interior(screen, font, player_rect):
    """Draw the weapon shop interior."""
    global weaponshop_keeper_rect, weaponshop_door_rect

    # Dark room + border, same style as item shop
    screen.fill((5, 5, 25))
    room_rect = pygame.Rect(20, 40, WIDTH - 40, HEIGHT - 80)
    pygame.draw.rect(screen, (15, 15, 40), room_rect)
    pygame.draw.rect(screen, (120, 120, 200), room_rect, 2)

    title = font.render("Weapon Shop", True, WHITE)
    title_rect = title.get_rect(center=(WIDTH // 2, 60))
    screen.blit(title, title_rect)

    # Walls
    wall_thickness = 40
    wall_color = (30, 130, 50)
    pygame.draw.rect(
        screen,
        wall_color,
        (room_rect.x + 10, room_rect.y + 60, room_rect.width - 20, wall_thickness),
    )
    pygame.draw.rect(
        screen,
        wall_color,
        (room_rect.x + 10, room_rect.y + 60, 24, room_rect.height - 120),
    )
    pygame.draw.rect(
        screen,
        wall_color,
        (room_rect.right - 34, room_rect.y + 60, 24, room_rect.height - 120),
    )
    pygame.draw.rect(
        screen,
        wall_color,
        (room_rect.x + 10, room_rect.bottom - 50, room_rect.width - 20, 24),
    )

    # Counter + shopkeeper
    counter_color = (150, 90, 40)
    counter_top = room_rect.y + 110
    counter_rect = pygame.Rect(room_rect.x + 80, counter_top, room_rect.width - 160, 32)
    pygame.draw.rect(screen, counter_color, counter_rect)
    pygame.draw.rect(
        screen,
        counter_color,
        (counter_rect.x, counter_rect.y, 24, 60),
    )
    pygame.draw.rect(
        screen,
        counter_color,
        (counter_rect.right - 24, counter_rect.y, 24, 60),
    )

    shopkeeper_color = (240, 220, 60)
    weaponshop_keeper_rect = pygame.Rect(0, 0, 24, 24)
    weaponshop_keeper_rect.centerx = counter_rect.centerx
    weaponshop_keeper_rect.bottom = counter_rect.top
    pygame.draw.rect(screen, shopkeeper_color, weaponshop_keeper_rect)

    # Shelves / weapon displays (purely decorative)
    shelf_color = (120, 120, 210)
    shelf_w = 60
    shelf_h = 80
    left_y = room_rect.y + 210

    for i, x in enumerate((room_rect.x + 120, room_rect.x + 210, room_rect.x + 300)):
        pygame.draw.rect(screen, shelf_color, (x, left_y, shelf_w, shelf_h))

    for i, x in enumerate(
        (room_rect.right - 360, room_rect.right - 270, room_rect.right - 180)
    ):
        pygame.draw.rect(screen, shelf_color, (x, left_y, shelf_w, shelf_h))

    # Door at bottom center
    door_w = 40
    door_h = 26
    weaponshop_door_rect = pygame.Rect(0, 0, door_w, door_h)
    weaponshop_door_rect.centerx = WIDTH // 2
    weaponshop_door_rect.bottom = room_rect.bottom - 10
    pygame.draw.rect(screen, (160, 40, 80), weaponshop_door_rect)

    # Player
    pygame.draw.rect(screen, WHITE, player_rect)

    # HUD text
    hint = font.render("Enter at door: leave   Enter at counter: talk", True, WHITE)
    hint_rect = hint.get_rect(center=(WIDTH // 2, HEIGHT - 30))
    screen.blit(hint, hint_rect)


def price_str(v):
    """Format a gold price value."""
    return f"{v} G"


def calculate_weapon_preview(member, weapon_name):
    """Return (old_attack, new_attack) if equipped."""
    from game_data import WEAPONS

    weapon_data = WEAPONS[weapon_name]

    old_atk = member.attack
    temp_weapon = member.weapon

    # Temporarily equip for preview
    member.weapon = weapon_name
    member.recalc_stats()
    new_atk = member.attack

    # Revert
    member.weapon = temp_weapon
    member.recalc_stats()

    return old_atk, new_atk


def draw_weapon_shop_ui(screen):
    """Draw the weapon shop purchase UI overlay - NEW SYSTEM."""
    panel_w = WIDTH - 100
    panel_h = HEIGHT - 100
    panel_rect = pygame.Rect(50, 50, panel_w, panel_h)

    pygame.draw.rect(screen, (20, 20, 20), panel_rect)
    pygame.draw.rect(screen, (255, 255, 255), panel_rect, 2)

    # Title
    title = FONT.render("Weapon Shop", True, (255, 255, 255))
    screen.blit(title, (panel_rect.x + 20, panel_rect.y + 10))

    # Gold display
    gold_text = FONT.render(f"Gold: {inv.player_gold} G", True, (255, 220, 100))
    screen.blit(gold_text, (panel_rect.right - 160, panel_rect.y + 10))

    # -------------------------------
    # LEFT SIDE — WEAPON LIST
    # -------------------------------
    list_x = panel_rect.x + 20
    list_y = panel_rect.y + 60

    for i, item_name in enumerate(WEAPON_SHOP_STOCK):
        weapon = WEAPONS[item_name]
        y = list_y + i * 36

        # Highlight selected item
        if i == weapon_shop_cursor:
            pygame.draw.rect(screen, (60, 60, 120), (list_x - 5, y - 4, 280, 32))
            color = (255, 255, 0)
        else:
            color = (255, 255, 255)

        text = FONT.render(f"{item_name} - {weapon['price']}G", True, color)
        screen.blit(text, (list_x, y))

    # -------------------------------
    # RIGHT SIDE — STAT PREVIEW
    # -------------------------------
    if WEAPON_SHOP_STOCK:
        item_name = WEAPON_SHOP_STOCK[weapon_shop_cursor]
        weapon = WEAPONS[item_name]

        preview_x = panel_rect.x + 340
        preview_y = panel_rect.y + 60

        # Item Title
        name_text = FONT.render(item_name, True, (255, 255, 255))
        screen.blit(name_text, (preview_x, preview_y))

        # Show which party members can equip
        allowed_label = FONT.render("Can Equip:", True, (255, 255, 255))
        screen.blit(allowed_label, (preview_x, preview_y + 30))
        allowed = ", ".join(weapon["allowed_jobs"])
        allowed_text = FONT.render(allowed, True, (100, 255, 100))
        screen.blit(allowed_text, (preview_x + 100, preview_y + 30))

        # Preview for Hero (party_list[0])
        if party_list:
            member = party_list[0]
            # Check if member has the new PartyMember class methods
            if hasattr(member, "recalc_stats"):
                old_atk, new_atk = calculate_weapon_preview(member, item_name)
            else:
                # Fallback for dict-based party
                old_atk = member.get("attack", 0)
                new_atk = old_atk + weapon.get("attack", 0)

            atk_old = FONT.render(f"Current ATK: {old_atk}", True, (255, 255, 255))
            screen.blit(atk_old, (preview_x, preview_y + 70))

            atk_new = FONT.render(f"New ATK:     {new_atk}", True, (255, 255, 0))
            screen.blit(atk_new, (preview_x, preview_y + 90))

        # Bottom description
        desc_box = pygame.Rect(
            panel_rect.x + 20, panel_rect.bottom - 80, panel_rect.width - 40, 60
        )
        pygame.draw.rect(screen, (35, 35, 35), desc_box)
        pygame.draw.rect(screen, (255, 255, 255), desc_box, 2)

        desc_text = f"ATK +{weapon.get('attack', 0)}"
        if weapon.get("magic", 0) > 0:
            desc_text += f"  MAG +{weapon['magic']}"
        if weapon.get("defense", 0) != 0:
            desc_text += f"  DEF {weapon['defense']:+d}"

        desc = FONT.render(desc_text, True, (255, 255, 255))
        screen.blit(desc, (desc_box.x + 10, desc_box.y + 10))

        hint = FONT.render(
            "↑/↓: Select   Enter: Buy   ESC: Exit", True, (180, 180, 180)
        )
        screen.blit(hint, (desc_box.x + 10, desc_box.y + 35))


def calculate_armor_preview(member, armor_name):
    """Returns (old_defense, new_defense) after equipping armor."""
    from game_data import ARMOR

    armor_data = ARMOR[armor_name]
    old_def = member.defense

    temp = member.armor  # save old armor
    member.armor = armor_name
    member.recalc_stats()
    new_def = member.defense

    member.armor = temp  # revert
    member.recalc_stats()

    return old_def, new_def


def draw_armor_shop_ui(screen):
    """Draw the armor shop purchase UI overlay - NEW SYSTEM."""
    panel_w = WIDTH - 100
    panel_h = HEIGHT - 100
    panel_rect = pygame.Rect(50, 50, panel_w, panel_h)

    pygame.draw.rect(screen, (20, 20, 20), panel_rect)
    pygame.draw.rect(screen, (255, 255, 255), panel_rect, 2)

    # Title
    title = FONT.render("Armor Shop", True, (255, 255, 255))
    screen.blit(title, (panel_rect.x + 20, panel_rect.y + 10))

    # Gold display
    gold_text = FONT.render(f"Gold: {inv.player_gold} G", True, (255, 220, 100))
    screen.blit(gold_text, (panel_rect.right - 160, panel_rect.y + 10))

    # -------------------------------
    # LEFT SIDE — ARMOR LIST
    # -------------------------------
    list_x = panel_rect.x + 20
    list_y = panel_rect.y + 60

    # Need to access armor_shop_cursor - will be defined globally
    cursor = globals().get("armor_shop_cursor", 0)

    for i, item_name in enumerate(ARMOR_SHOP_STOCK):
        armor = ARMOR[item_name]
        y = list_y + i * 36

        # Highlight selected item
        if i == cursor:
            pygame.draw.rect(screen, (60, 60, 120), (list_x - 5, y - 4, 280, 32))
            color = (255, 255, 0)
        else:
            color = (255, 255, 255)

        text = FONT.render(f"{item_name} - {armor['price']}G", True, color)
        screen.blit(text, (list_x, y))

    # -------------------------------
    # RIGHT SIDE — STAT PREVIEW
    # -------------------------------
    if ARMOR_SHOP_STOCK:
        item_name = ARMOR_SHOP_STOCK[cursor]
        armor = ARMOR[item_name]

        preview_x = panel_rect.x + 340
        preview_y = panel_rect.y + 60

        # Item Title
        name_text = FONT.render(item_name, True, (255, 255, 255))
        screen.blit(name_text, (preview_x, preview_y))

        # Show which party members can equip
        allowed_label = FONT.render("Can Equip:", True, (255, 255, 255))
        screen.blit(allowed_label, (preview_x, preview_y + 30))
        allowed = ", ".join(armor["allowed_jobs"])
        allowed_text = FONT.render(allowed, True, (100, 255, 100))
        screen.blit(allowed_text, (preview_x + 100, preview_y + 30))

        # Preview for Hero (party_list[0])
        if party_list:
            member = party_list[0]
            # Check if member has the new PartyMember class methods
            if hasattr(member, "recalc_stats"):
                old_def, new_def = calculate_armor_preview(member, item_name)
            else:
                # Fallback for dict-based party
                old_def = member.get("defense", 0)
                new_def = old_def + armor.get("defense", 0)

            def_old = FONT.render(f"Current DEF: {old_def}", True, (255, 255, 255))
            screen.blit(def_old, (preview_x, preview_y + 70))

            def_new = FONT.render(f"New DEF:     {new_def}", True, (255, 255, 0))
            screen.blit(def_new, (preview_x, preview_y + 90))

        # Bottom description
        desc_box = pygame.Rect(
            panel_rect.x + 20, panel_rect.bottom - 80, panel_rect.width - 40, 60
        )
        pygame.draw.rect(screen, (35, 35, 35), desc_box)
        pygame.draw.rect(screen, (255, 255, 255), desc_box, 2)

        desc_text = f"DEF +{armor.get('defense', 0)}"
        if armor.get("magic", 0) > 0:
            desc_text += f"  MAG +{armor['magic']}"

        desc = FONT.render(desc_text, True, (255, 255, 255))
        screen.blit(desc, (desc_box.x + 10, desc_box.y + 10))

        hint = FONT.render(
            "↑/↓: Select   Enter: Buy   ESC: Exit", True, (180, 180, 180)
        )
        screen.blit(hint, (desc_box.x + 10, desc_box.y + 35))


def draw_inn_interior(screen, font):
    """Draw the Inn interior with beds, counter, innkeeper, and dialog."""
    global inn_dialog_state, inn_cursor_index

    # Background + room frame
    screen.fill((5, 5, 25))
    room_rect = pygame.Rect(20, 40, WIDTH - 40, HEIGHT - 80)
    pygame.draw.rect(screen, (15, 15, 40), room_rect)
    pygame.draw.rect(screen, (120, 120, 200), room_rect, 2)

    # Title
    title = font.render("Inn", True, WHITE)
    title_rect = title.get_rect(center=(WIDTH // 2, 60))
    screen.blit(title, title_rect)

    # Walls (green band around)
    wall_thickness = 40
    wall_color = (30, 130, 50)
    pygame.draw.rect(
        screen,
        wall_color,
        (room_rect.x + 10, room_rect.y + 60, room_rect.width - 20, wall_thickness),
    )
    pygame.draw.rect(
        screen,
        wall_color,
        (room_rect.x + 10, room_rect.y + 60, 24, room_rect.height - 120),
    )
    pygame.draw.rect(
        screen,
        wall_color,
        (room_rect.right - 34, room_rect.y + 60, 24, room_rect.height - 120),
    )
    pygame.draw.rect(
        screen,
        wall_color,
        (room_rect.x + 10, room_rect.bottom - 50, room_rect.width - 20, 24),
    )

    # Beds along the back wall
    bed_color = (160, 140, 220)
    bed_w = 80
    bed_h = 40
    bed_y = room_rect.y + 120
    bed_xs = (
        room_rect.x + 80,
        room_rect.x + 200,
        room_rect.right - 280,
        room_rect.right - 160,
    )
    for bx in bed_xs:
        pygame.draw.rect(screen, bed_color, (bx, bed_y, bed_w, bed_h))

    # Counter + innkeeper near middle
    counter_color = (150, 90, 40)
    counter_top = bed_y + 80
    counter_rect = pygame.Rect(
        room_rect.x + 120, counter_top, room_rect.width - 240, 32
    )
    pygame.draw.rect(screen, counter_color, counter_rect)
    pygame.draw.rect(screen, counter_color, (counter_rect.x, counter_rect.y, 24, 60))
    pygame.draw.rect(
        screen, counter_color, (counter_rect.right - 24, counter_rect.y, 24, 60)
    )

    # Innkeeper sprite
    keeper_color = (240, 220, 60)
    keeper_rect = pygame.Rect(0, 0, 24, 24)
    keeper_rect.centerx = counter_rect.centerx
    keeper_rect.bottom = counter_rect.top
    pygame.draw.rect(screen, keeper_color, keeper_rect)

    # Bottom door
    door_w = 40
    door_h = 26
    door_x = WIDTH // 2 - door_w // 2
    door_y = room_rect.bottom - 10
    door_rect = pygame.Rect(door_x, door_y, door_w, door_h)
    pygame.draw.rect(screen, (160, 40, 80), door_rect)

    # Player
    player_rect = pygame.Rect(0, 0, PLAYER_SIZE, PLAYER_SIZE)
    player_rect.center = (int(player_x), int(player_y))
    pygame.draw.rect(screen, WHITE, player_rect)

    # Hint text
    hint = font.render("Enter at door: leave   Enter at counter: talk", True, WHITE)
    hint_rect = hint.get_rect(center=(WIDTH // 2, HEIGHT - 30))
    screen.blit(hint, hint_rect)

    # --- Inn dialog window (on top) ---
    if inn_dialog_state > 0:
        panel_w = WIDTH - 260
        panel_h = 90
        panel_rect = pygame.Rect(
            (WIDTH - panel_w) // 2,
            HEIGHT - panel_h - 60,
            panel_w,
            panel_h,
        )
        pygame.draw.rect(screen, (10, 10, 35), panel_rect)
        pygame.draw.rect(screen, WHITE, panel_rect, 2)

        if inn_dialog_state == 1:
            # Ask to stay
            msg = font.render(
                f"Stay the night for {INN_PRICE} G? (Gold: {inv.player_gold})",
                True,
                WHITE,
            )
            screen.blit(msg, (panel_rect.x + 12, panel_rect.y + 10))

            options = ["Yes", "No"]
            for i, label in enumerate(options):
                c = MENU_HILIGHT if i == inn_cursor_index else WHITE
                t = font.render(label, True, c)
                screen.blit(t, (panel_rect.x + 40 + i * 80, panel_rect.y + 40))

        elif inn_dialog_state == 2:
            # Result text only; press any key to close
            msg = getattr(draw_inn_interior, "last_message", "You feel rested.")
            text = font.render(msg, True, WHITE)
            text_rect = text.get_rect(center=panel_rect.center)
            screen.blit(text, text_rect)

    # Store rects we need for interaction (hacky but easy):
    draw_inn_interior.keeper_rect = keeper_rect
    draw_inn_interior.door_rect = door_rect


def draw_inn_ui(screen):
    """Draw the inn stay/rest UI dialog."""
    panel_w = 420
    panel_h = 180
    panel_rect = pygame.Rect(
        (WIDTH - panel_w) // 2,
        (HEIGHT - panel_h) // 2,
        panel_w,
        panel_h,
    )

    pygame.draw.rect(screen, (20, 20, 40), panel_rect)
    pygame.draw.rect(screen, (255, 255, 255), panel_rect, 2)

    title = FONT.render("Inn", True, (255, 255, 255))
    screen.blit(title, (panel_rect.x + 16, panel_rect.y + 12))

    cost_text = FONT.render(
        f"Stay the night for {inv.INN_COST}G?",
        True,
        (255, 255, 255),
    )
    screen.blit(cost_text, (panel_rect.x + 16, panel_rect.y + 48))

    gold_text = FONT.render(
        f"Gold: {inv.player_gold}",
        True,
        (255, 255, 200),
    )
    screen.blit(gold_text, (panel_rect.x + 16, panel_rect.y + 72))

    # Yes / No options
    options = ["Yes", "No"]
    y = panel_rect.y + 110
    for i, opt in enumerate(options):
        color = (255, 255, 255)
        if i == inn_menu_index:
            color = (240, 220, 120)
            arrow = FONT.render("▶", True, color)
            screen.blit(arrow, (panel_rect.x + 16, y))
            text_x = panel_rect.x + 32
        else:
            text_x = panel_rect.x + 32

        label = FONT.render(opt, True, color)
        screen.blit(label, (text_x, y))
        y += 24

    hint = FONT.render(
        "↑↓: Select   Enter: Confirm   ESC: Cancel",
        True,
        (200, 200, 200),
    )
    screen.blit(hint, (panel_rect.x + 16, panel_rect.bottom - 26))


def draw_inn_message(screen):
    """Draw the inn message banner at the bottom of the screen."""
    panel_w = 360
    panel_h = 60
    panel_rect = pygame.Rect(
        (WIDTH - panel_w) // 2,
        HEIGHT - panel_h - 24,
        panel_w,
        panel_h,
    )

    pygame.draw.rect(screen, (0, 0, 0, 200), panel_rect)
    pygame.draw.rect(screen, (255, 255, 255), panel_rect, 2)

    msg = FONT.render(inn_message, True, (255, 255, 255))
    msg_rect = msg.get_rect(center=panel_rect.center)
    screen.blit(msg, msg_rect)


def draw_dialog_box(surface):
    """Draw the NPC dialog box at the bottom of the screen."""
    if not dialog_active or not dialog_lines:
        return

    box_height = 120
    box_rect = pygame.Rect(
        16,
        HEIGHT - box_height - 16,
        WIDTH - 32,
        box_height,
    )

    pygame.draw.rect(surface, (0, 0, 0), box_rect)
    pygame.draw.rect(surface, (255, 255, 255), box_rect, 2)

    # Show current line
    if dialog_index < len(dialog_lines):
        line = dialog_lines[dialog_index]
        text_surf = FONT.render(line, True, (255, 255, 255))
        surface.blit(text_surf, (box_rect.x + 12, box_rect.y + 16))

    hint = FONT.render("[Enter] to continue", True, (200, 200, 200))
    surface.blit(hint, (box_rect.right - 180, box_rect.bottom - 24))


def draw_overworld_menu(surface):
    """Draw the overworld menu with tab-based navigation."""
    if not menu_active:
        return

    panel_rect = pygame.Rect(
        40,
        40,
        WIDTH - 80,
        HEIGHT - 80,
    )
    pygame.draw.rect(surface, (0, 0, 0), panel_rect)
    pygame.draw.rect(surface, (255, 255, 255), panel_rect, 2)

    # --- Tabs along the top ---
    tab_y = panel_rect.y + 8
    tab_x = panel_rect.x + 16
    for i, tab in enumerate(world_menu_tabs):
        color = (255, 255, 255)
        if i == world_menu_tab_index:
            color = (255, 255, 0)
        text = FONT.render(tab, True, color)
        surface.blit(text, (tab_x, tab_y))
        tab_x += text.get_width() + 24

    current_tab = world_menu_tabs[world_menu_tab_index]

    if current_tab == "Status":
        draw_status_tab(surface, panel_rect)
    elif current_tab == "Inventory":
        draw_inventory_tab(surface, panel_rect)
    elif current_tab == "Equipment":
        draw_equipment_tab(surface, panel_rect)
    elif current_tab == "System":
        draw_system_tab(surface, panel_rect)


def draw_status_tab(surface, panel_rect):
    """Draw the Status tab showing detailed party member stats."""
    title = FONT.render("Party Status", True, (255, 255, 255))
    surface.blit(title, (panel_rect.x + 20, panel_rect.y + 40))

    # Show all party members in columns
    y_start = panel_rect.y + 80
    x_offset = panel_rect.x + 20

    for i, member in enumerate(combat.party):
        y = y_start + (i * 140)

        # Member name and level
        name_text = FONT.render(
            f"{member.name} (Lv {member.level})", True, (255, 255, 0)
        )
        surface.blit(name_text, (x_offset, y))

        # Job
        job_text = FONT.render(f"Job: {member.job}", True, (200, 200, 200))
        surface.blit(job_text, (x_offset, y + 25))

        # HP/MP
        hp_text = FONT.render(f"HP: {member.hp}/{member.max_hp}", True, (255, 255, 255))
        surface.blit(hp_text, (x_offset + 200, y))

        mp_text = FONT.render(f"MP: {member.mp}/{member.max_mp}", True, (255, 255, 255))
        surface.blit(mp_text, (x_offset + 200, y + 25))

        # Stats
        stats_text = f"ATK: {member.attack}  DEF: {member.defense}  MAG: {member.magic}"
        stats = FONT.render(stats_text, True, (255, 255, 255))
        surface.blit(stats, (x_offset, y + 50))

        # XP Bar
        xp_label = FONT.render(
            f"XP: {member.xp}/{member.xp_to_next}", True, (200, 200, 200)
        )
        surface.blit(xp_label, (x_offset, y + 75))

        bar_x = x_offset + 80
        bar_y = y + 80
        bar_w = 150
        bar_h = 12

        # XP bar background
        pygame.draw.rect(surface, (60, 60, 60), (bar_x, bar_y, bar_w, bar_h))
        # XP bar fill
        if member.xp_to_next > 0:
            fill_w = int((member.xp / member.xp_to_next) * bar_w)
            pygame.draw.rect(surface, (100, 200, 100), (bar_x, bar_y, fill_w, bar_h))
        pygame.draw.rect(surface, (255, 255, 255), (bar_x, bar_y, bar_w, bar_h), 1)

        # Equipment info
        weapon_name = "None"
        armor_name = "None"

        # Try to get equipment from party_list
        if i < len(party_list):
            p_member = party_list[i]
            if hasattr(p_member, "weapon"):
                weapon_name = p_member.weapon or "None"
            if hasattr(p_member, "armor"):
                armor_name = p_member.armor or "None"

        equip_text = FONT.render(
            f"Weapon: {weapon_name}  Armor: {armor_name}", True, (180, 180, 255)
        )
        surface.blit(equip_text, (x_offset, y + 100))

    # Show gold at bottom
    gold_line = f"Gold: {inv.player_gold} G"
    gold_text = FONT.render(gold_line, True, (255, 220, 100))
    surface.blit(gold_text, (panel_rect.x + 20, panel_rect.bottom - 40))

    # Hint
    hint = FONT.render("View detailed stats for each character", True, (150, 150, 150))
    surface.blit(hint, (panel_rect.x + 20, panel_rect.bottom - 20))


def draw_inventory_tab(surface, panel_rect):
    """Draw the Inventory tab showing items with scrolling."""
    title = FONT.render("Inventory", True, (255, 255, 255))
    surface.blit(title, (panel_rect.x + 20, panel_rect.y + 40))

    # Show gold in top-right
    gold_text = FONT.render(f"Gold: {inv.player_gold} G", True, (255, 220, 100))
    surface.blit(gold_text, (panel_rect.right - 180, panel_rect.y + 40))

    items = get_inventory_items_as_list()
    if not items:
        msg = FONT.render("No items.", True, (200, 200, 200))
        surface.blit(msg, (panel_rect.x + 20, panel_rect.y + 80))
        return

    start = inv_scroll
    end = min(start + INV_VISIBLE_MAX, len(items))

    y = panel_rect.y + 80
    for draw_i, idx in enumerate(range(start, end)):
        item_id, qty = items[idx]

        # Look up item data
        item_def = ITEM_DATA.get(item_id, {"name": item_id, "desc": ""})
        name = item_def["name"]
        line = f"{name}  x{qty}"

        color = (255, 255, 255)
        if idx == inv_cursor:
            color = (255, 255, 0)

        text = FONT.render(line, True, color)
        surface.blit(text, (panel_rect.x + 20, y))

        y += 22


def draw_equipment_tab(surface, panel_rect):
    """Draw the Equipment tab."""
    title = FONT.render("Equipment", True, (255, 255, 255))
    surface.blit(title, (panel_rect.x + 20, panel_rect.y + 40))

    if not combat.party:
        msg = FONT.render("No party members.", True, (200, 200, 200))
        surface.blit(msg, (panel_rect.x + 20, panel_rect.y + 80))
        return

    # --- Character selection row ---
    y = panel_rect.y + 80
    x = panel_rect.x + 20

    label = FONT.render("Character:", True, (255, 255, 255))
    surface.blit(label, (x, y))

    cx = x + 120
    for i, member in enumerate(combat.party):
        color = (255, 255, 255)
        if i == equip_cursor_char:
            color = (255, 255, 0)
        name_text = FONT.render(member.name, True, color)
        surface.blit(name_text, (cx, y))
        cx += name_text.get_width() + 24

    # --- Selected character info ---
    actor = combat.party[equip_cursor_char]
    y += 30
    info_line = f"LV {actor.level}   ATK {actor.attack}   MAG {actor.magic}"
    info_text = FONT.render(info_line, True, (255, 255, 255))
    surface.blit(info_text, (panel_rect.x + 20, y))

    # Current weapon display
    cur_weapon_id = combat.get_equipped_weapon(actor)
    if cur_weapon_id is None:
        weap_name = "None"
        weap_bonus = 0
    else:
        weap_data = gd.ITEMS.get(cur_weapon_id, {})
        weap_name = weap_data.get("name", cur_weapon_id)
        weap_bonus = combat.get_weapon_attack_bonus(cur_weapon_id)

    y += 24
    current_line = f"Weapon: {weap_name}  (ATK +{weap_bonus})"
    current_text = FONT.render(current_line, True, (200, 200, 255))
    surface.blit(current_text, (panel_rect.x + 20, y))

    # --- Weapon list from inventory ---
    y += 36
    weapons = get_weapon_inventory_list()

    if not weapons:
        msg = FONT.render("No weapons in inventory.", True, (200, 200, 200))
        surface.blit(msg, (panel_rect.x + 20, y))
        return

    list_title = FONT.render("Equip from Bag:", True, (255, 255, 255))
    surface.blit(list_title, (panel_rect.x + 20, y))
    y += 20

    start = equip_item_scroll
    end = min(start + EQUIP_VISIBLE_MAX, len(weapons))

    for draw_i, idx in enumerate(range(start, end)):
        item_id, qty = weapons[idx]
        data = gd.ITEMS.get(item_id, {})
        name = data.get("name", item_id)
        atk_bonus = combat.get_weapon_attack_bonus(item_id)

        # preview new ATK if this was equipped
        preview_attack = actor.attack
        # Remove current weapon's bonus to compute "true" base+other gear
        if cur_weapon_id is not None:
            preview_attack -= combat.get_weapon_attack_bonus(cur_weapon_id)
        preview_attack += atk_bonus

        line = f"{name} x{qty}   ATK +{atk_bonus}  -> ATK {preview_attack}"

        color = (255, 255, 255)
        if idx == equip_cursor_item:
            color = (255, 255, 0)

        text = FONT.render(line, True, color)
        surface.blit(text, (panel_rect.x + 20, y))

        y += 22

    # Optional hint
    hint = FONT.render(
        "←/→: Change character   ↑/↓: Select weapon   Enter: Equip",
        True,
        (180, 180, 180),
    )
    surface.blit(hint, (panel_rect.x + 20, panel_rect.bottom - 30))


def draw_system_tab(surface, panel_rect):
    """Draw the System tab with save/load/quit options."""
    title = FONT.render("System", True, (255, 255, 255))
    surface.blit(title, (panel_rect.x + 20, panel_rect.y + 40))

    msg = FONT.render("Save/Load/Quit will go here.", True, (200, 200, 200))
    surface.blit(msg, (panel_rect.x + 20, panel_rect.y + 80))


# ============================================================================
# EQUIPMENT MENU SYSTEM
# ============================================================================


def get_equippable_items(member, slot):
    """Get list of items from inventory that member can equip in slot."""
    results = []

    if slot == "weapon":
        source_dict = WEAPONS
    elif slot == "armor":
        source_dict = ARMOR
    else:
        return results

    # Get member's job
    member_job = member.get("job", "Hero") if isinstance(member, dict) else member.job

    for item_name, item_data in source_dict.items():
        # Check if member's job can use this item
        if member_job in item_data.get("allowed_jobs", []):
            results.append((item_name, item_data))

    return results


def draw_equipment_menu():
    """Draw the party member selection screen for equipment."""
    SCREEN.fill((20, 20, 35))

    title = FONT.render("Equipment - Select Party Member", True, (255, 255, 255))
    SCREEN.blit(title, (40, 20))

    # Use party_list for display
    y = 120
    for i, member in enumerate(party_list):
        member_name = (
            member.get("name", "Unknown") if isinstance(member, dict) else member.name
        )
        color = (255, 255, 0) if i == equip_index else (255, 255, 255)
        text = FONT.render(member_name, True, color)
        SCREEN.blit(text, (60, y + i * 40))

    hint = FONT.render("Enter = Select   ESC = Back", True, (200, 200, 200))
    SCREEN.blit(hint, (40, HEIGHT - 60))


def draw_equip_member(member):
    """Draw the equipment slots for a specific member."""
    SCREEN.fill((25, 25, 40))

    # Get member details
    member_name = (
        member.get("name", "Unknown") if isinstance(member, dict) else member.name
    )

    title = FONT.render(f"{member_name}'s Equipment", True, (255, 255, 255))
    SCREEN.blit(title, (40, 20))

    options = ["Weapon", "Armor"]
    y_start = 120

    for i, slot in enumerate(options):
        y = y_start + i * 80

        # Slot name
        color = (255, 255, 0) if i == equip_slot_index else (255, 255, 255)
        text = FONT.render(f"{slot}:", True, color)
        SCREEN.blit(text, (60, y))

        # Current equipment
        if hasattr(member, slot.lower()):
            current = getattr(member, slot.lower())
        else:
            current = member.get(f"equipped_{slot.lower()}", "None")

        if current is None:
            current = "None"

        eq_text = FONT.render(f"{current}", True, (180, 180, 255))
        SCREEN.blit(eq_text, (240, y))

        # Show stats
        if i == 0:  # Weapon
            member_atk = (
                member.get("attack", 0) if isinstance(member, dict) else member.attack
            )
            stat_text = FONT.render(f"ATK: {member_atk}", True, (200, 200, 200))
            SCREEN.blit(stat_text, (240, y + 25))
        else:  # Armor
            member_def = (
                member.get("defense", 0) if isinstance(member, dict) else member.defense
            )
            stat_text = FONT.render(f"DEF: {member_def}", True, (200, 200, 200))
            SCREEN.blit(stat_text, (240, y + 25))

    hint = FONT.render("Enter = Change   ESC = Back", True, (200, 200, 200))
    SCREEN.blit(hint, (40, HEIGHT - 60))


def draw_equip_select(member, slot, items, selected):
    """Draw the item selection screen for equipping."""
    SCREEN.fill((10, 10, 20))

    member_name = (
        member.get("name", "Unknown") if isinstance(member, dict) else member.name
    )
    title = FONT.render(
        f"Equip {slot.capitalize()} - {member_name}", True, (255, 255, 255)
    )
    SCREEN.blit(title, (40, 20))

    if not items:
        msg = FONT.render("No equippable items available.", True, (200, 200, 200))
        SCREEN.blit(msg, (60, 120))
    else:
        y = 120
        for i, (item_name, item_data) in enumerate(items):
            color = (255, 255, 0) if i == selected else (255, 255, 255)

            # Item name and stats
            stat_bonus = ""
            if slot == "weapon":
                atk = item_data.get("attack", 0)
                stat_bonus = f" (ATK +{atk})"
            elif slot == "armor":
                defense = item_data.get("defense", 0)
                stat_bonus = f" (DEF +{defense})"

            text = FONT.render(f"{item_name}{stat_bonus}", True, color)
            SCREEN.blit(text, (60, y + i * 35))

            # Price if available
            if "price" in item_data:
                price_text = FONT.render(
                    f"{item_data['price']}G", True, (200, 200, 200)
                )
                SCREEN.blit(price_text, (400, y + i * 35))

    hint = FONT.render("Enter = Equip   ESC = Back", True, (200, 200, 200))
    SCREEN.blit(hint, (40, HEIGHT - 60))


def draw_world_menu(screen):
    """Draw the tabbed world menu overlay."""
    # Main panel
    panel_w = 600
    panel_h = 400
    panel_x = (WIDTH - panel_w) // 2
    panel_y = (HEIGHT - panel_h) // 2
    panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

    pygame.draw.rect(screen, (20, 20, 40), panel_rect)
    pygame.draw.rect(screen, (200, 200, 200), panel_rect, 2)

    # Tab bar
    tab_bar_height = 40
    tab_width = panel_w // len(world_menu_tabs)

    for i, tab_name in enumerate(world_menu_tabs):
        tab_x = panel_x + i * tab_width
        tab_rect = pygame.Rect(tab_x, panel_y, tab_width, tab_bar_height)

        # Highlight selected tab
        if i == world_menu_tab_index:
            pygame.draw.rect(screen, (60, 60, 100), tab_rect)
        else:
            pygame.draw.rect(screen, (40, 40, 60), tab_rect)

        pygame.draw.rect(screen, (200, 200, 200), tab_rect, 1)

        tab_text = FONT.render(tab_name, True, (255, 255, 255))
        tab_text_rect = tab_text.get_rect(center=tab_rect.center)
        screen.blit(tab_text, tab_text_rect)

    # Content area
    content_y = panel_y + tab_bar_height + 10
    content_height = panel_h - tab_bar_height - 20

    active_tab = world_menu_tabs[world_menu_tab_index]

    # ---- STATUS TAB ----
    if active_tab == "Status":
        y_offset = content_y

        # Draw party members with equipment
        for char_name in ["Hero", "Warrior", "Mage"]:
            base_atk = inv.BASE_ATTACK.get(char_name, 10)
            weapon_name = inv.equipped_weapons.get(char_name, "None")
            weapon_data = inv.WEAPONS.get(weapon_name, {})
            weapon_bonus = weapon_data.get("atk_bonus", 0)
            total_atk = base_atk + weapon_bonus

            name_text = FONT.render(f"{char_name}", True, (255, 255, 100))
            screen.blit(name_text, (panel_x + 20, y_offset))

            atk_text = FONT.render(f"ATK: {total_atk}", True, (255, 255, 255))
            screen.blit(atk_text, (panel_x + 180, y_offset))

            weapon_text = FONT.render(f"Weapon: {weapon_name}", True, (200, 200, 200))
            screen.blit(weapon_text, (panel_x + 280, y_offset))

            y_offset += 35

    # ---- INVENTORY TAB ----
    elif active_tab == "Inventory":
        items = inv.get_inventory_list()

        if not items:
            no_items_text = FONT.render("No items in inventory", True, (150, 150, 150))
            screen.blit(no_items_text, (panel_x + 20, content_y))
        else:
            # Clamp cursor
            global world_menu_cursor
            world_menu_cursor = max(0, min(world_menu_cursor, len(items) - 1))

            y_offset = content_y
            for i, (item_id, name, qty, desc) in enumerate(items):
                if i == world_menu_cursor:
                    # Highlight selected item
                    highlight_rect = pygame.Rect(
                        panel_x + 10, y_offset - 2, panel_w - 20, 30
                    )
                    pygame.draw.rect(screen, (80, 80, 120), highlight_rect)

                item_text = FONT.render(f"{name} x{qty}", True, (255, 255, 255))
                screen.blit(item_text, (panel_x + 20, y_offset))

                y_offset += 35

                # Show description for selected item
                if i == world_menu_cursor and desc:
                    desc_y = panel_y + panel_h - 60
                    desc_text = FONT.render(desc, True, (200, 200, 200))
                    screen.blit(desc_text, (panel_x + 20, desc_y))

    # ---- SYSTEM TAB ----
    elif active_tab == "System":
        quit_text = FONT.render("Press Enter to Quit Game", True, (255, 100, 100))
        quit_rect = quit_text.get_rect(center=(panel_x + panel_w // 2, content_y + 50))
        screen.blit(quit_text, quit_rect)

        hint_text = FONT.render("(or ESC to return)", True, (150, 150, 150))
        hint_rect = hint_text.get_rect(center=(panel_x + panel_w // 2, content_y + 90))
        screen.blit(hint_text, hint_rect)


def enter_item_shop():
    """Enter the item shop and spawn player at the door."""
    global current_scene, last_town_position, player_x, player_y, shop_ui_open, shop_menu_index
    last_town_position = (player_x, player_y)
    current_scene = "ITEM_SHOP"
    shop_ui_open = False
    shop_menu_index = 0

    # Spawn just inside the door (bottom middle of the interior frame)
    door_y = HEIGHT - 80
    player_x = WIDTH // 2
    player_y = door_y


def enter_weapon_shop():
    """Enter the weapon shop and spawn player at the door."""
    global current_scene, last_town_position, player_x, player_y
    global weapon_shop_open, weapon_shop_cursor, weapon_shop_items
    last_town_position = (player_x, player_y)
    current_scene = "WEAPON_SHOP"
    weapon_shop_open = False
    weapon_shop_cursor = 0

    # Build weapon shop inventory based on WEAPON_SHOP_STOCK
    weapon_shop_items = []
    for char_name, weapon_id in inv.WEAPON_SHOP_STOCK:
        weapon = inv.WEAPON_DEFS.get(weapon_id)
        if weapon:
            weapon_shop_items.append((char_name, weapon_id))

    # Spawn just inside the door (bottom middle of the interior frame)
    door_y = HEIGHT - 80
    player_x = WIDTH // 2
    player_y = door_y


def buy_weapon_at_cursor():
    """Purchase the weapon currently selected in the weapon shop."""
    global weapon_shop_cursor

    if not weapon_shop_items:
        return

    weapon_name = weapon_shop_items[weapon_shop_cursor]
    weapon_data = inv.WEAPONS[weapon_name]

    price = weapon_data.get("price", 0)

    # For now we buy for Hero; expand later with a selector if you want
    target = "Hero"

    # Check if already equipped
    if inv.equipped_weapons.get(target) == weapon_name:
        return  # Already equipped, fail silently

    if inv.player_gold < price:
        # You can add a message system later; for now just fail silently
        return

    inv.player_gold -= price
    inv.equipped_weapons[target] = weapon_name
    # Equipment will affect combat ATK on next battle via sync_party_equipment_from_inventory()


def handle_weapon_shop_input(event):
    """Handle input when the weapon shop UI is open - NEW SYSTEM."""
    global weapon_shop_open, weapon_shop_cursor, menu_active

    if event.type != pygame.KEYDOWN:
        return

    if event.key == pygame.K_UP:
        weapon_shop_cursor = (weapon_shop_cursor - 1) % len(WEAPON_SHOP_STOCK)
    elif event.key == pygame.K_DOWN:
        weapon_shop_cursor = (weapon_shop_cursor + 1) % len(WEAPON_SHOP_STOCK)

    elif event.key == pygame.K_ESCAPE:
        weapon_shop_open = False
        menu_active = False

    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
        # Try to buy/equip the selected weapon
        chosen = WEAPON_SHOP_STOCK[weapon_shop_cursor]
        data = WEAPONS[chosen]

        # Check gold
        if inv.player_gold < data["price"]:
            print("Not enough gold!")
            return

        # Check if Hero (party_list[0]) can equip
        if party_list:
            hero = party_list[0]
            hero_job = hero.get("job", "Hero") if isinstance(hero, dict) else hero.job

            if hero_job not in data["allowed_jobs"]:
                print("Your class can't equip that!")
                return

            # Purchase
            inv.player_gold -= data["price"]

            # Equip immediately
            if hasattr(hero, "equip_weapon"):
                # New PartyMember class
                hero.equip_weapon(chosen, data)
            else:
                # Dict-based fallback
                hero["equipped_weapon"] = chosen
                if "attack" in hero:
                    hero["attack"] = hero.get("base_attack", hero["attack"]) + data.get(
                        "attack", 0
                    )

            print(f"Equipped {chosen}!")
            weapon_shop_open = False


def handle_armor_shop_input(event):
    """Handle input when the armor shop UI is open - NEW SYSTEM."""
    global armor_shop_open, armor_shop_cursor, menu_active, shop_message

    if event.type != pygame.KEYDOWN:
        return

    if event.key == pygame.K_UP:
        armor_shop_cursor = (armor_shop_cursor - 1) % len(ARMOR_SHOP_STOCK)
        shop_message = ""
    elif event.key == pygame.K_DOWN:
        armor_shop_cursor = (armor_shop_cursor + 1) % len(ARMOR_SHOP_STOCK)
        shop_message = ""

    elif event.key == pygame.K_ESCAPE:
        armor_shop_open = False
        menu_active = False
        shop_message = ""

    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
        # Try to buy/equip the selected armor
        chosen = ARMOR_SHOP_STOCK[armor_shop_cursor]
        data = ARMOR[chosen]

        # Check gold
        if inv.player_gold < data["price"]:
            shop_message = "Not enough gold!"
            return

        # Check if Hero (party_list[0]) can equip
        if party_list:
            hero = party_list[0]
            hero_job = hero.get("job", "Hero") if isinstance(hero, dict) else hero.job

            if hero_job not in data["allowed_jobs"]:
                shop_message = "Your class can't equip that!"
                return

            # Purchase
            inv.player_gold -= data["price"]

            # Equip immediately
            if hasattr(hero, "equip_armor"):
                # New PartyMember class
                hero.equip_armor(chosen, data)
            else:
                # Dict-based fallback
                hero["equipped_armor"] = chosen
                if "defense" in hero:
                    hero["defense"] = hero.get(
                        "base_defense", hero["defense"]
                    ) + data.get("defense", 0)

            shop_message = f"Equipped {chosen}!"
            armor_shop_open = False


def handle_overworld_menu_input(event):
    """Handle input when the overworld menu is open."""
    global menu_active, world_menu_tab_index, inv_cursor, inv_scroll

    if event.type != pygame.KEYDOWN:
        return

    # TAB SELECTION (left/right)
    if event.key == pygame.K_LEFT:
        world_menu_tab_index = (world_menu_tab_index - 1) % len(world_menu_tabs)
        inv_cursor = 0
        inv_scroll = 0
    elif event.key == pygame.K_RIGHT:
        world_menu_tab_index = (world_menu_tab_index + 1) % len(world_menu_tabs)
        inv_cursor = 0
        inv_scroll = 0

    # Close menu
    elif event.key == pygame.K_ESCAPE:
        menu_active = False

    # Tab-specific handling
    current_tab = world_menu_tabs[world_menu_tab_index]

    if current_tab == "Inventory":
        handle_inventory_tab_input(event)
    elif current_tab == "Equipment":
        handle_equipment_tab_input(event)
    # Status/System can be simple for now


def get_inventory_items_as_list():
    """
    Return [(item_id, qty), ...] for items that have qty > 0.
    Uses the centralized inventory from inventory_state module.
    """
    items = []
    for item_id, qty in inv.inventory.items():
        if qty > 0:
            items.append((item_id, qty))
    return items


def get_weapon_inventory_list():
    """
    Return list of (item_id, qty) for all weapon items in inventory
    that have qty > 0.
    """
    items = []
    for item_id, qty in gd.INVENTORY.items():
        if qty <= 0:
            continue
        data = gd.ITEMS.get(item_id)
        if not data:
            continue
        if data.get("type") == "weapon":
            items.append((item_id, qty))
    return items


def handle_inventory_tab_input(event):
    """Handle input for the Inventory tab."""
    global inv_cursor, inv_scroll

    items = get_inventory_items_as_list()
    if not items:
        # Nothing to navigate
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            # maybe show "No items." message later
            pass
        return

    if event.key == pygame.K_UP:
        old = inv_cursor
        inv_cursor = (inv_cursor - 1) % len(items)

        if inv_cursor > old:  # wrapped to bottom
            inv_scroll = max(0, len(items) - INV_VISIBLE_MAX)
        elif inv_cursor < inv_scroll:
            inv_scroll = inv_cursor

    elif event.key == pygame.K_DOWN:
        old = inv_cursor
        inv_cursor = (inv_cursor + 1) % len(items)

        if inv_cursor < old:  # wrapped to top
            inv_scroll = 0
        elif inv_cursor >= inv_scroll + INV_VISIBLE_MAX:
            inv_scroll = inv_cursor - INV_VISIBLE_MAX + 1

    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
        # Here you could open a "Use / Details / Cancel" sub-menu.
        # For now, we just do nothing – we're setting up the viewer UI.
        pass


def handle_equipment_tab_input(event):
    """Handle input for the Equipment tab."""
    global equip_cursor_char, equip_cursor_item, equip_item_scroll

    if event.type != pygame.KEYDOWN:
        return

    current_tab = world_menu_tabs[world_menu_tab_index]
    if current_tab != "Equipment":
        return

    # No party = nothing to do
    if not combat.party:
        return

    # First row: character selection with LEFT/RIGHT
    if event.key == pygame.K_LEFT:
        equip_cursor_char = (equip_cursor_char - 1) % len(combat.party)
        equip_cursor_item = 0
        equip_item_scroll = 0
        return
    elif event.key == pygame.K_RIGHT:
        equip_cursor_char = (equip_cursor_char + 1) % len(combat.party)
        equip_cursor_item = 0
        equip_item_scroll = 0
        return

    # Weapon list navigation
    weapons = get_weapon_inventory_list()
    if not weapons:
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            # No weapons to equip, nothing happens.
            return
    else:
        if event.key == pygame.K_UP:
            old = equip_cursor_item
            equip_cursor_item = (equip_cursor_item - 1) % len(weapons)
            if equip_cursor_item > old:
                equip_item_scroll = max(0, len(weapons) - EQUIP_VISIBLE_MAX)
            elif equip_cursor_item < equip_item_scroll:
                equip_item_scroll = equip_cursor_item

        elif event.key == pygame.K_DOWN:
            old = equip_cursor_item
            equip_cursor_item = (equip_cursor_item + 1) % len(weapons)
            if equip_cursor_item < old:
                equip_item_scroll = 0
            elif equip_cursor_item >= equip_item_scroll + EQUIP_VISIBLE_MAX:
                equip_item_scroll = equip_cursor_item - EQUIP_VISIBLE_MAX + 1

        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            # Equip selected weapon on selected character
            item_id, qty = weapons[equip_cursor_item]
            if qty <= 0:
                return

            actor = combat.party[equip_cursor_char]
            # Use the shared equip helper from combat
            combat.equip_weapon(actor, item_id)


def open_inn_ui():
    """Open the inn UI dialog when talking to innkeeper."""
    global inn_ui_open, inn_menu_index, inn_message, inn_message_timer
    inn_ui_open = True
    inn_menu_index = 0
    inn_message = ""
    inn_message_timer = 0


def stay_at_inn():
    """Handle staying at the inn - heal party and charge gold."""
    global inn_ui_open, inn_message, inn_message_timer

    cost = inv.INN_COST

    if inv.player_gold < cost:
        inn_message = "Not enough gold..."
        inn_message_timer = 120  # 2 seconds at 60 FPS
        return

    # Pay the inn
    inv.player_gold -= cost

    # TODO: hook real healing when HP/MP persist in overworld.
    # For now, just flavor text + a later hook point.
    # Later we'll add:
    # from combat import party
    # for member in party:
    #     member.hp = member.max_hp
    #     member.mp = member.max_mp
    #     member.statuses.clear()

    inn_message = "You rest and feel fully restored."
    inn_message_timer = 180  # 3 seconds
    inn_ui_open = False


def enter_inn():
    """Move player into the Inn interior scene."""
    global current_scene, last_town_position, player_x, player_y
    global inn_dialog_state, inn_cursor_index
    last_town_position = (player_x, player_y)
    current_scene = "INN"
    inn_dialog_state = 0
    inn_cursor_index = 0

    # Spawn just inside the bottom door, centered
    door_y = HEIGHT - 80
    player_x = WIDTH // 2
    player_y = door_y


def enter_building(door):
    """Enter a building interior."""
    global current_scene, last_town_position, player_x, player_y
    last_town_position = (player_x, player_y)
    player_x = (WIDTH // 2) - (TILE_SIZE // 2)
    player_y = HEIGHT - (TILE_SIZE * 2)
    current_scene = door["target_scene"]


def exit_building():
    """Exit building and return to town."""
    global current_scene, player_x, player_y
    player_x, player_y = last_town_position
    current_scene = "TOWN"


def main():
    global debug_message, menu_active, menu_mode, menu_index, inv_cursor, current_scene
    global shop_ui_open, shop_menu_index
    global weapon_shop_open, weapon_shop_cursor
    global inn_dialog_state, inn_cursor_index
    global inn_ui_open, inn_menu_index, inn_message, inn_message_timer
    global player_weapons
    global world_menu_open, world_menu_tab_index, world_menu_cursor
    global dialog_active, dialog_lines, dialog_index
    global inv_scroll, equip_cursor_char, equip_cursor_slot

    # Initialize world tile system
    load_world_tile(current_tile)

    current_scene = "WORLD"  # Start in world tile system
    running = True
    while running:
        dt = CLOCK.tick(60) / 1000.0

        dx = dy = 0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # --- WEAPON SHOP HAS PRIORITY WHEN OPEN ---
            if current_scene == "WEAPON_SHOP" and weapon_shop_open:
                handle_weapon_shop_input(event)
                # Do NOT let other handlers see this event
                continue

            if event.type == pygame.KEYDOWN:
                # -------------------------------------------------
                # ESC => toggle world menu (if not in a shop/inn scene)
                # -------------------------------------------------
                if event.key == pygame.K_ESCAPE:
                    # Block if we're in ITEM_SHOP, WEAPON_SHOP, or INN and a UI is open
                    block_toggle = False
                    if current_scene == "ITEM_SHOP" and shop_ui_open:
                        block_toggle = True
                    elif current_scene == "WEAPON_SHOP" and weapon_shop_open:
                        block_toggle = True
                    elif current_scene == "INN" and inn_ui_open:
                        block_toggle = True

                    if not block_toggle:
                        # Toggle the world menu
                        world_menu_open = not world_menu_open
                        menu_active = world_menu_open
                        if world_menu_open:
                            world_menu_tab_index = 0
                            world_menu_cursor = 0
                            inv_scroll = 0
                        continue  # skip other ESC handlers

                # -------------------------------------------------
                # If world menu is open, handle tab/cursor navigation
                # -------------------------------------------------
                if world_menu_open:
                    if event.key == pygame.K_LEFT:
                        world_menu_tab_index = (world_menu_tab_index - 1) % len(
                            world_menu_tabs
                        )
                        world_menu_cursor = 0
                    elif event.key == pygame.K_RIGHT:
                        world_menu_tab_index = (world_menu_tab_index + 1) % len(
                            world_menu_tabs
                        )
                        world_menu_cursor = 0
                    elif event.key == pygame.K_UP:
                        # navigate within the active tab
                        if world_menu_tabs[world_menu_tab_index] == "Inventory":
                            world_menu_cursor = max(0, world_menu_cursor - 1)
                    elif event.key == pygame.K_DOWN:
                        if world_menu_tabs[world_menu_tab_index] == "Inventory":
                            world_menu_cursor += 1  # clamp in draw code
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        # System tab => quit
                        if world_menu_tabs[world_menu_tab_index] == "System":
                            running = False
                    continue  # consume input when world menu is open

                # When menu is open, only handle menu navigation
                if menu_active:
                    if menu_mode == "MAIN":
                        main_options = ["Resume", "Inventory", "Quit"]

                        if event.key == pygame.K_UP:
                            menu_index = (menu_index - 1) % len(main_options)
                        elif event.key == pygame.K_DOWN:
                            menu_index = (menu_index + 1) % len(main_options)
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            choice = main_options[menu_index]
                            if choice == "Resume":
                                menu_active = False
                            elif choice == "Inventory":
                                menu_mode = "INVENTORY"
                                inv_cursor = 0
                            elif choice == "Quit":
                                running = False
                        elif event.key == pygame.K_ESCAPE:
                            # ESC closes menu from MAIN
                            menu_active = False

                    elif menu_mode == "INVENTORY":
                        # Build a list of items that actually exist (qty > 0)
                        items = [(k, v) for k, v in inv.inventory.items() if v > 0]

                        if event.key == pygame.K_ESCAPE:
                            # back to main menu
                            menu_mode = "MAIN"
                            menu_index = 0

                        elif items:
                            if event.key == pygame.K_UP:
                                inv_cursor = (inv_cursor - 1) % len(items)
                            elif event.key == pygame.K_DOWN:
                                inv_cursor = (inv_cursor + 1) % len(items)

                            # For now, inventory in overworld is VIEW ONLY
                            # Later we can add "use potion outside battle".
                            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                                pass

                else:
                    # ---- Normal overworld controls ----
                    # (ESC for menu is handled above with world_menu_open)

                    if event.key == pygame.K_b:
                        launch_battle()

                    # Scene-specific controls
                    if current_scene == "TOWN":
                        # Handle dialog advancement if active
                        if dialog_active:
                            if event.key in (
                                pygame.K_RETURN,
                                pygame.K_SPACE,
                                pygame.K_z,
                            ):
                                dialog_index += 1
                                if dialog_index >= len(dialog_lines):
                                    # end dialog
                                    dialog_active = False
                                    dialog_lines = []
                                    dialog_index = 0
                        else:
                            # Normal town controls
                            if event.key == pygame.K_RETURN:
                                # First try talking to NPCs
                                try_talk_to_npc()

                                # Then check for building entry
                                if (
                                    not dialog_active
                                ):  # only if we didn't start a dialog
                                    # Check if building has unified interior
                                    door = None
                                    for d in DOORS_TOWN:
                                        if d.get("name") == active_building:
                                            door = d
                                            break

                                    if door and "interior" in door:
                                        # Use unified interior system
                                        load_interior(door["interior"])
                                        current_scene = door["target_scene"]
                                    elif active_building == "Town Gate":
                                        # Enter world tile system
                                        current_scene = "WORLD"
                                        player_x = WIDTH // 2
                                        player_y = HEIGHT - 40
                                        load_world_tile(current_tile)
                                        debug_message = "Entered overworld"

                    # ============================================================================
                    # UNIFIED INTERIOR INPUT HANDLING
                    # ============================================================================
                    elif CURRENT_INTERIOR:
                        data = gd.INTERIORS.get(CURRENT_INTERIOR, {})

                        # Shop navigation and purchase
                        if CURRENT_INTERIOR in (
                            "ITEM_SHOP",
                            "WEAPON_SHOP",
                            "ARMOR_SHOP",
                        ):
                            if event.key == pygame.K_UP:
                                shop_selection = (shop_selection - 1) % len(
                                    data["inventory"]
                                )
                            elif event.key == pygame.K_DOWN:
                                shop_selection = (shop_selection + 1) % len(
                                    data["inventory"]
                                )
                            elif event.key == pygame.K_RETURN:
                                item_id = data["inventory"][shop_selection]
                                price = data["buy_prices"][item_id]
                                attempt_purchase(item_id, price)
                            elif event.key == pygame.K_ESCAPE:
                                leave_interior()

                        # Inn rest
                        elif CURRENT_INTERIOR == "INN":
                            if event.key == pygame.K_RETURN:
                                attempt_inn_rest()
                            elif event.key == pygame.K_ESCAPE:
                                leave_interior()

                    elif current_scene == "ITEM_SHOP":
                        # ---- ITEM SHOP INPUT ----
                        if shop_ui_open:
                            # Shop menu is open
                            if event.key == pygame.K_UP:
                                shop_menu_index = (shop_menu_index - 1) % len(
                                    SHOP_STOCK
                                )
                            elif event.key == pygame.K_DOWN:
                                shop_menu_index = (shop_menu_index + 1) % len(
                                    SHOP_STOCK
                                )
                            elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                                shop_ui_open = False
                            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                                # Attempt to buy selected item
                                item = SHOP_STOCK[shop_menu_index]
                                price = item["price"]
                                item_id = item["id"]

                                if inv.player_gold >= price:
                                    inv.player_gold -= price
                                    inv.inventory[item_id] = (
                                        inv.inventory.get(item_id, 0) + 1
                                    )
                                    print(
                                        f"Bought {item['name']}! Now have {inv.inventory[item_id]}"
                                    )
                                else:
                                    print("Not enough gold.")
                        else:
                            # No menu open: walk around / talk / leave
                            if event.key == pygame.K_ESCAPE:
                                # leave via Esc from anywhere
                                exit_building()
                            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                                # check door / shopkeeper
                                player_rect = pygame.Rect(
                                    0, 0, PLAYER_SIZE, PLAYER_SIZE
                                )
                                player_rect.center = (int(player_x), int(player_y))

                                # Leave via door
                                door_rect = getattr(
                                    draw_item_shop_interior, "itemshop_door_rect", None
                                )
                                if door_rect and player_rect.colliderect(door_rect):
                                    exit_building()
                                else:
                                    # Talk to shopkeeper to open menu
                                    keeper_rect = getattr(
                                        draw_item_shop_interior, "shopkeeper_rect", None
                                    )
                                    if keeper_rect and player_rect.colliderect(
                                        keeper_rect.inflate(40, 40)
                                    ):
                                        shop_ui_open = True
                                        shop_menu_index = 0

                    elif current_scene == "WEAPON_SHOP":
                        # ---- WEAPON SHOP INPUT ----
                        if weapon_shop_open:
                            # --- MENU OPEN: use dedicated input handler ---
                            handle_weapon_shop_input(event)
                        else:
                            # --- MENU CLOSED: walking / interacting / leaving ---
                            if event.key == pygame.K_ESCAPE:
                                # leave via Esc from anywhere
                                exit_building()
                            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                                # check door / shopkeeper
                                player_rect = pygame.Rect(
                                    0, 0, PLAYER_SIZE, PLAYER_SIZE
                                )
                                player_rect.center = (int(player_x), int(player_y))
                                if weaponshop_door_rect and player_rect.colliderect(
                                    weaponshop_door_rect
                                ):
                                    exit_building()
                                elif weaponshop_keeper_rect and player_rect.colliderect(
                                    weaponshop_keeper_rect.inflate(40, 40)
                                ):
                                    # Standing near the counter → open shop UI
                                    weapon_shop_open = True
                                    menu_active = True
                                    weapon_shop_cursor = 0

                    elif current_scene == "INN":
                        # ---- INN INPUT ----
                        # New inn UI system
                        if inn_ui_open:
                            if event.key == pygame.K_ESCAPE:
                                # Close inn UI
                                inn_ui_open = False
                                inn_message = ""
                                inn_message_timer = 0

                            elif event.key in (pygame.K_UP, pygame.K_DOWN):
                                # Toggle Yes/No
                                inn_menu_index = 1 - inn_menu_index

                            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                                if inn_menu_index == 0:
                                    # YES
                                    stay_at_inn()
                                else:
                                    # NO
                                    inn_ui_open = False
                                    inn_message = ""
                                    inn_message_timer = 0

                        # Legacy dialog system (keeping for backwards compatibility)
                        elif inn_dialog_state == 1:
                            # Yes / No selection
                            if event.key in (
                                pygame.K_LEFT,
                                pygame.K_RIGHT,
                                pygame.K_UP,
                                pygame.K_DOWN,
                            ):
                                inn_cursor_index = (
                                    1 - inn_cursor_index
                                )  # toggle 0 <-> 1
                            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                                if inn_cursor_index == 0:  # Yes
                                    if inv.player_gold >= INN_PRICE:
                                        inv.player_gold -= INN_PRICE
                                        msg = "You stay the night. You feel rested."
                                        # later: actually heal party HP/MP here
                                    else:
                                        msg = "Not enough gold..."
                                    inn_dialog_state = 2
                                    draw_inn_interior.last_message = msg
                                else:
                                    # No – close dialog
                                    inn_dialog_state = 0
                            elif event.key == pygame.K_ESCAPE:
                                inn_dialog_state = 0

                        elif inn_dialog_state == 2:
                            # Result message; any key closes
                            if event.key in (
                                pygame.K_RETURN,
                                pygame.K_SPACE,
                                pygame.K_ESCAPE,
                            ):
                                inn_dialog_state = 0

                        else:
                            # No dialog: walk around / leave / talk to innkeeper
                            if event.key == pygame.K_ESCAPE:
                                # leave via Esc from anywhere
                                exit_building()
                            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                                # check door / innkeeper
                                player_rect = pygame.Rect(
                                    0, 0, PLAYER_SIZE, PLAYER_SIZE
                                )
                                player_rect.center = (int(player_x), int(player_y))

                                # Leave if at door
                                door_rect = getattr(
                                    draw_inn_interior, "door_rect", None
                                )
                                if door_rect and player_rect.colliderect(door_rect):
                                    exit_building()
                                else:
                                    # Start dialog if facing innkeeper
                                    keeper_rect = getattr(
                                        draw_inn_interior, "keeper_rect", None
                                    )
                                    if keeper_rect and player_rect.colliderect(
                                        keeper_rect.inflate(40, 40)
                                    ):
                                        open_inn_ui()

                    # ============================================================================
                    # EQUIPMENT MENU INPUT HANDLING
                    # ============================================================================
                    elif current_scene == SCENE_EQUIPMENT:
                        if event.key == pygame.K_UP:
                            equip_index = (equip_index - 1) % len(party_list)
                        elif event.key == pygame.K_DOWN:
                            equip_index = (equip_index + 1) % len(party_list)
                        elif event.key == pygame.K_RETURN:
                            current_scene = SCENE_EQUIP_MEMBER
                            equip_slot_index = 0
                            equip_current_member = party_list[equip_index]
                        elif event.key == pygame.K_ESCAPE:
                            menu_active = False
                            current_scene = "TOWN"

                    elif current_scene == SCENE_EQUIP_MEMBER:
                        member = party_list[equip_index]

                        if event.key == pygame.K_UP:
                            equip_slot_index = (equip_slot_index - 1) % 2
                        elif event.key == pygame.K_DOWN:
                            equip_slot_index = (equip_slot_index + 1) % 2
                        elif event.key == pygame.K_RETURN:
                            slot = "weapon" if equip_slot_index == 0 else "armor"
                            equip_current_slot = slot
                            equip_select_index = 0
                            current_scene = SCENE_EQUIP_SELECT
                        elif event.key == pygame.K_ESCAPE:
                            current_scene = SCENE_EQUIPMENT

                    elif current_scene == SCENE_EQUIP_SELECT:
                        member = party_list[equip_index]
                        slot = equip_current_slot
                        equippable = get_equippable_items(member, slot)

                        if not equippable:
                            if event.key == pygame.K_ESCAPE:
                                current_scene = SCENE_EQUIP_MEMBER
                        else:
                            if event.key == pygame.K_UP:
                                equip_select_index = (equip_select_index - 1) % len(
                                    equippable
                                )
                            elif event.key == pygame.K_DOWN:
                                equip_select_index = (equip_select_index + 1) % len(
                                    equippable
                                )
                            elif event.key == pygame.K_RETURN:
                                item_name, item_data = equippable[equip_select_index]

                                # Equip the item using the new system
                                if hasattr(member, "equip_weapon") and slot == "weapon":
                                    member.equip_weapon(item_name, item_data)
                                elif hasattr(member, "equip_armor") and slot == "armor":
                                    member.equip_armor(item_name, item_data)
                                else:
                                    # Fallback for dict-based party
                                    if isinstance(member, dict):
                                        member[f"equipped_{slot}"] = item_name
                                        if slot == "weapon":
                                            member["attack"] = member.get(
                                                "base_attack", member.get("attack", 0)
                                            ) + item_data.get("attack", 0)
                                        elif slot == "armor":
                                            member["defense"] = member.get(
                                                "base_defense", member.get("defense", 0)
                                            ) + item_data.get("defense", 0)

                                # Return to member equipment screen
                                current_scene = SCENE_EQUIP_MEMBER

                            elif event.key == pygame.K_ESCAPE:
                                current_scene = SCENE_EQUIP_MEMBER

                    # -------------------------------------------------
                    # WORLD scene - handle town entry
                    # -------------------------------------------------
                    elif current_scene == "WORLD" and not world_menu_open:
                        if event.key == pygame.K_RETURN:
                            # Check if on TOWN_CENTER tile
                            if current_tile == "TOWN_CENTER":
                                current_scene = "TOWN"
                                player_x = WIDTH // 2
                                player_y = HEIGHT // 2
                                debug_message = "Entered town"

        # Movement only when not in menu/dialog and not in interior (CURRENT_INTERIOR handles all shops/inns)
        can_move = (
            not world_menu_open
            and not dialog_active
            and CURRENT_INTERIOR is None
        )

        if movement_debug_enabled:
            keys = pygame.key.get_pressed()
            if (
                keys[pygame.K_LEFT]
                or keys[pygame.K_a]
                or keys[pygame.K_RIGHT]
                or keys[pygame.K_d]
                or keys[pygame.K_UP]
                or keys[pygame.K_w]
                or keys[pygame.K_DOWN]
                or keys[pygame.K_s]
            ):
                if not can_move:
                    print(
                        "BLOCKED → world_menu_open:",
                        world_menu_open,
                        "dialog_active:",
                        dialog_active,
                        "CURRENT_INTERIOR:",
                        CURRENT_INTERIOR,
                    )

        if can_move:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                dx -= player_speed
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                dx += player_speed
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                dy -= player_speed
            if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                dy += player_speed

            if dx or dy:
                debug_message = ""

            move_player(dx, dy)

            # Handle transitions between areas
            if current_scene == "TOWN":
                player_rect = pygame.Rect(0, 0, PLAYER_SIZE, PLAYER_SIZE)
                player_rect.center = (int(player_x), int(player_y))
                handle_area_transition(player_rect)

            # Handle world tile transitions
            elif current_scene == "WORLD":
                handle_world_tile_transitions()

        # ----- DRAW -----
        # Unified interior drawing takes precedence
        if CURRENT_INTERIOR:
            draw_interior_ui()
        elif current_scene == "TOWN":
            player_rect = pygame.Rect(0, 0, PLAYER_SIZE, PLAYER_SIZE)
            player_rect.center = (int(player_x), int(player_y))
            draw_current_area(SCREEN, player_rect)
            if menu_active:
                draw_overworld_menu(SCREEN)
            draw_dialog_box(SCREEN)
        elif current_scene == "WORLD":
            draw_world_tile()
        elif current_scene == "INN":
            draw_inn_interior(SCREEN, FONT)
            if inn_ui_open:
                draw_inn_ui(SCREEN)
            if inn_message_timer > 0 and inn_message:
                draw_inn_message(SCREEN)
        elif current_scene == "ITEM_SHOP":
            player_rect = pygame.Rect(0, 0, PLAYER_SIZE, PLAYER_SIZE)
            player_rect.center = (int(player_x), int(player_y))
            draw_item_shop_interior(SCREEN, FONT, player_rect)
        elif current_scene == "WEAPON_SHOP":
            player_rect = pygame.Rect(0, 0, PLAYER_SIZE, PLAYER_SIZE)
            player_rect.center = (int(player_x), int(player_y))
            draw_weapon_shop_interior(SCREEN, FONT, player_rect)
            if weapon_shop_open:
                draw_weapon_shop_ui(SCREEN)

        # ============================================================================
        # EQUIPMENT MENU DRAWING
        # ============================================================================
        elif current_scene == SCENE_EQUIPMENT:
            draw_equipment_menu()
        elif current_scene == SCENE_EQUIP_MEMBER:
            member = party_list[equip_index]
            draw_equip_member(member)
        elif current_scene == SCENE_EQUIP_SELECT:
            member = party_list[equip_index]
            slot = equip_current_slot
            equippable = get_equippable_items(member, slot)
            draw_equip_select(member, slot, equippable, equip_select_index)

        else:
            # Fallback for TITLE or unknown scenes
            draw_town()

        # Update inn message timer
        if inn_message_timer > 0:
            inn_message_timer -= 1
            if inn_message_timer == 0:
                inn_message = ""

        # Draw world menu overlay if open
        if world_menu_open:
            draw_world_menu(SCREEN)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
