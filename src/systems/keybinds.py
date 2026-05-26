"""Layout-independent gameplay key bindings."""

from __future__ import annotations

import pygame


# SDL scancodes keep physical keys stable across IME layouts and Caps Lock.
SCANCODE_A = 4
SCANCODE_C = 6
SCANCODE_D = 7
SCANCODE_M = 16
SCANCODE_Q = 20
SCANCODE_R = 21
SCANCODE_S = 22
SCANCODE_W = 26
SCANCODE_1 = 30
SCANCODE_2 = 31
SCANCODE_ESCAPE = 41
SCANCODE_SPACE = 44
SCANCODE_RIGHT = 79
SCANCODE_LEFT = 80
SCANCODE_DOWN = 81
SCANCODE_UP = 82


def _binding(*, keys=(), scancodes=()):
    return {
        "keys": tuple(keys),
        "scancodes": tuple(scancodes),
    }


ACTION_BINDINGS = {
    "quit": _binding(keys=(pygame.K_ESCAPE,), scancodes=(SCANCODE_ESCAPE,)),
    "menu_classic": _binding(keys=(pygame.K_1, pygame.K_KP1), scancodes=(SCANCODE_1,)),
    "menu_adventure": _binding(keys=(pygame.K_2, pygame.K_KP2), scancodes=(SCANCODE_2,)),
    "pause": _binding(keys=(pygame.K_q,), scancodes=(SCANCODE_Q,)),
    "resume": _binding(keys=(pygame.K_r, pygame.K_q, pygame.K_c), scancodes=(SCANCODE_R, SCANCODE_Q, SCANCODE_C)),
    "restart": _binding(keys=(pygame.K_r,), scancodes=(SCANCODE_R,)),
    "menu": _binding(keys=(pygame.K_m,), scancodes=(SCANCODE_M,)),
    "activate_skill": _binding(keys=(pygame.K_SPACE,), scancodes=(SCANCODE_SPACE,)),
    "classic_up": _binding(keys=(pygame.K_UP, pygame.K_w), scancodes=(SCANCODE_UP, SCANCODE_W)),
    "classic_down": _binding(keys=(pygame.K_DOWN, pygame.K_s), scancodes=(SCANCODE_DOWN, SCANCODE_S)),
    "classic_left": _binding(keys=(pygame.K_LEFT, pygame.K_a), scancodes=(SCANCODE_LEFT, SCANCODE_A)),
    "classic_right": _binding(keys=(pygame.K_RIGHT, pygame.K_d), scancodes=(SCANCODE_RIGHT, SCANCODE_D)),
}


def action_pressed(event, action: str) -> bool:
    """Return True when a KEYDOWN matches the configured action."""

    if event.type != pygame.KEYDOWN:
        return False

    binding = ACTION_BINDINGS[action]
    if event.key in binding["keys"]:
        return True
    return getattr(event, "scancode", None) in binding["scancodes"]


def classic_direction_from_event(event):
    """Map classic-mode movement input to a grid direction."""

    if action_pressed(event, "classic_up"):
        return (0, -1)
    if action_pressed(event, "classic_down"):
        return (0, 1)
    if action_pressed(event, "classic_left"):
        return (-1, 0)
    if action_pressed(event, "classic_right"):
        return (1, 0)
    return None
