"""Layout-independent gameplay key bindings."""

from __future__ import annotations

import pygame


# Pygame reports platform-specific scancodes; on Windows these are typically
# the keyboard hardware set, while some environments expose SDL-like values.
SCANCODE_SETS = {
    "A": (30, 4),
    "C": (46, 6),
    "D": (32, 7),
    "M": (50, 16),
    "Q": (16, 20),
    "R": (19, 21),
    "S": (31, 22),
    "W": (17, 26),
    "1": (2, 30),
    "2": (3, 31),
    "3": (4, 32),
    "4": (5, 33),
    "ESCAPE": (1, 41),
    "SPACE": (57, 44),
    "RIGHT": (77, 79),
    "LEFT": (75, 80),
    "DOWN": (80, 81),
    "UP": (72, 82),
}


def _binding(*, keys=(), scancodes=(), chars=()):
    return {
        "keys": tuple(keys),
        "scancodes": tuple(scancodes),
        "chars": tuple(chars),
    }


ACTION_BINDINGS = {
    "quit": _binding(keys=(pygame.K_ESCAPE,), scancodes=SCANCODE_SETS["ESCAPE"]),
    "menu_classic": _binding(keys=(pygame.K_1, pygame.K_KP1), scancodes=SCANCODE_SETS["1"], chars=("1",)),
    "menu_adventure": _binding(keys=(pygame.K_2, pygame.K_KP2), scancodes=SCANCODE_SETS["2"], chars=("2",)),
    "menu_duel": _binding(keys=(pygame.K_3, pygame.K_KP3), scancodes=SCANCODE_SETS["3"], chars=("3",)),
    "menu_multiplayer": _binding(keys=(pygame.K_4, pygame.K_KP4), scancodes=SCANCODE_SETS["4"], chars=("4",)),
    "pause": _binding(keys=(pygame.K_q,), scancodes=SCANCODE_SETS["Q"], chars=("q",)),
    "resume": _binding(
        keys=(pygame.K_r, pygame.K_q, pygame.K_c),
        scancodes=SCANCODE_SETS["R"] + SCANCODE_SETS["Q"] + SCANCODE_SETS["C"],
        chars=("r", "q", "c"),
    ),
    "restart": _binding(keys=(pygame.K_r,), scancodes=SCANCODE_SETS["R"], chars=("r",)),
    "menu": _binding(keys=(pygame.K_m,), scancodes=SCANCODE_SETS["M"], chars=("m",)),
    "activate_skill": _binding(keys=(pygame.K_SPACE,), scancodes=SCANCODE_SETS["SPACE"], chars=(" ",)),
    "classic_up": _binding(keys=(pygame.K_UP, pygame.K_w), scancodes=SCANCODE_SETS["UP"] + SCANCODE_SETS["W"], chars=("w",)),
    "classic_down": _binding(keys=(pygame.K_DOWN, pygame.K_s), scancodes=SCANCODE_SETS["DOWN"] + SCANCODE_SETS["S"], chars=("s",)),
    "classic_left": _binding(keys=(pygame.K_LEFT, pygame.K_a), scancodes=SCANCODE_SETS["LEFT"] + SCANCODE_SETS["A"], chars=("a",)),
    "classic_right": _binding(keys=(pygame.K_RIGHT, pygame.K_d), scancodes=SCANCODE_SETS["RIGHT"] + SCANCODE_SETS["D"], chars=("d",)),
}


def action_pressed(event, action: str) -> bool:
    """Return True when a KEYDOWN matches the configured action."""

    if event.type != pygame.KEYDOWN:
        return False

    binding = ACTION_BINDINGS[action]
    if event.key in binding["keys"]:
        return True
    if getattr(event, "scancode", None) in binding["scancodes"]:
        return True
    return getattr(event, "unicode", "").lower() in binding["chars"]


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
