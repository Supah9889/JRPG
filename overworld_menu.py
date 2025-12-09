import pygame
import sys

pygame.init()

# --- Window setup ---
WIDTH, HEIGHT = 1024, 640
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Overworld Menu Prototype")

clock = pygame.time.Clock()

# --- Colors ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (60, 60, 60)
YELLOW = (240, 220, 120)
BLUE = (40, 60, 110)

# --- Fonts ---
font_big = pygame.font.Font(None, 64)
font_med = pygame.font.Font(None, 36)
font_small = pygame.font.Font(None, 24)

# --- Overworld menu state ---
OVERWORLD_MENU_OPTIONS = ["Items", "Party", "Save", "Quit Game"]
overworld_menu_index = 0
overworld_menu_open = False

# Message line at bottom (for “not implemented yet” feedback)
status_message = ""


def draw_overworld_base():
    """Draw the basic overworld background (no menu)."""
    screen.fill(BLUE)

    # Simple layered "distance" just for vibes
    pygame.draw.rect(screen, (20, 40, 90), (0, HEIGHT // 3, WIDTH, HEIGHT // 3))
    pygame.draw.rect(screen, (10, 25, 60), (0, 2 * HEIGHT // 3, WIDTH, HEIGHT // 3))

    title = font_big.render("Overworld (Prototype)", True, WHITE)
    title_rect = title.get_rect(center=(WIDTH // 2, 80))
    screen.blit(title, title_rect)

    hint1 = font_small.render("ESC: Open/close Overworld Menu", True, WHITE)
    hint2 = font_small.render(
        "Up/Down: Move   Enter: Select   Quit Game: Exit", True, WHITE
    )

    screen.blit(hint1, (40, HEIGHT - 80))
    screen.blit(hint2, (40, HEIGHT - 50))


def draw_overworld_menu():
    """Draw the overworld menu panel when it's open."""
    # Dim the world a bit
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 140))
    screen.blit(overlay, (0, 0))

    # Panel
    panel_w, panel_h = 400, 260
    panel_rect = pygame.Rect(
        (WIDTH - panel_w) // 2,
        (HEIGHT - panel_h) // 2,
        panel_w,
        panel_h,
    )

    pygame.draw.rect(screen, (15, 15, 35), panel_rect)
    pygame.draw.rect(screen, WHITE, panel_rect, 2)

    title = font_med.render("Menu", True, WHITE)
    title_rect = title.get_rect(midtop=(panel_rect.centerx, panel_rect.y + 12))
    screen.blit(title, title_rect)

    # Options
    start_y = title_rect.bottom + 20
    row_h = 32

    for i, option in enumerate(OVERWORLD_MENU_OPTIONS):
        color = YELLOW if i == overworld_menu_index else WHITE
        txt = font_small.render(option, True, color)
        txt_rect = txt.get_rect(x=panel_rect.x + 40, y=start_y + i * row_h)
        screen.blit(txt, txt_rect)

    # Tiny hint
    hint = font_small.render("ESC: Close menu", True, WHITE)
    hint_rect = hint.get_rect(midbottom=(panel_rect.centerx, panel_rect.bottom - 12))
    screen.blit(hint, hint_rect)


def main():
    global overworld_menu_index, overworld_menu_open, status_message

    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # --- Menu open: handle menu navigation ---
            if overworld_menu_open:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        overworld_menu_index = (overworld_menu_index - 1) % len(
                            OVERWORLD_MENU_OPTIONS
                        )
                    elif event.key == pygame.K_DOWN:
                        overworld_menu_index = (overworld_menu_index + 1) % len(
                            OVERWORLD_MENU_OPTIONS
                        )
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        choice = OVERWORLD_MENU_OPTIONS[overworld_menu_index]

                        if choice == "Items":
                            status_message = (
                                "Items menu (overworld) not implemented yet."
                            )
                            overworld_menu_open = False

                        elif choice == "Party":
                            status_message = "Party/status screen not implemented yet."
                            overworld_menu_open = False

                        elif choice == "Save":
                            status_message = "Save system not implemented yet."
                            overworld_menu_open = False

                        elif choice == "Quit Game":
                            running = False

                    elif event.key == pygame.K_ESCAPE:
                        overworld_menu_open = False

            # --- Menu closed: overworld controls ---
            else:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        overworld_menu_open = True

        # --- DRAW ---
        draw_overworld_base()

        # Bottom status line
        if status_message:
            msg = font_small.render(status_message, True, WHITE)
            msg_rect = msg.get_rect(midbottom=(WIDTH // 2, HEIGHT - 8))
            screen.blit(msg, msg_rect)

        if overworld_menu_open:
            draw_overworld_menu()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
