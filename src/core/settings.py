"""Shared configuration for the snake game."""

from __future__ import annotations

import ctypes


def _enable_dpi_awareness():
    """Ask Windows for physical desktop pixels so fullscreen layout is not scaled."""

    try:
        shcore = ctypes.windll.shcore
        shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _detect_screen_size():
    default_width = 1920
    default_height = 1080
    try:
        _enable_dpi_awareness()
        user32 = ctypes.windll.user32
        display_width = int(user32.GetSystemMetrics(0))
        display_height = int(user32.GetSystemMetrics(1))
        if display_width <= 0 or display_height <= 0:
            raise ValueError("invalid display size")
        return display_width, display_height
    except Exception:
        return default_width, default_height


# Screen and world
SCREEN_WIDTH, SCREEN_HEIGHT = _detect_screen_size()
MAP_WIDTH = 16000
MAP_HEIGHT = 16000
FPS = 60

WORLD_TILE_SIZE = 60
WORLD_COLS = MAP_WIDTH // WORLD_TILE_SIZE
WORLD_ROWS = MAP_HEIGHT // WORLD_TILE_SIZE

# Snake tuning
SNAKE_BASE_SPEED = 320.0
SNAKE_MIN_SPEED_FACTOR = 0.35
SNAKE_TURN_SPEED = 5.4
SNAKE_INITIAL_LENGTH = 10
SNAKE_HEAD_RADIUS = 14
SNAKE_SEGMENT_SPACING = 26
SNAKE_BODY_RADIUS_MAX = 14
SNAKE_BODY_RADIUS_MIN = 8
SNAKE_TARGET_REACHED_DISTANCE = 22
SNAKE_SPEED_BOOST_MULTIPLIER = 1.65
SNAKE_SPEED_BOOST_DURATION = 5.0
SNAKE_VISION_SURGE_MULTIPLIER = 2.0
SNAKE_VISION_SURGE_DURATION = 5.0
SNAKE_GLOW_ALPHA = 58
VISION_GROWTH_PER_SEGMENT = 0.05
MAX_VISION_MULTIPLIER = 1.5
MIN_VISION_MULTIPLIER = 0.2
VISION_PENALTY_PER_MISSING_SEGMENT = 0.1

SNAKE_BODY_COLOR_BRIGHT = (142, 232, 112)
SNAKE_BODY_COLOR_DARK = (52, 156, 52)
SNAKE_HEAD_COLOR = (255, 226, 92)
AI_SNAKE_BODY_COLOR_BRIGHT = (118, 214, 255)
AI_SNAKE_BODY_COLOR_DARK = (54, 112, 188)
AI_SNAKE_HEAD_COLOR = (255, 132, 132)

AI_SNAKE2_BODY_COLOR_BRIGHT = (255, 180, 120)
AI_SNAKE2_BODY_COLOR_DARK = (188, 100, 54)
AI_SNAKE2_HEAD_COLOR = (255, 220, 80)

AI_SNAKE3_BODY_COLOR_BRIGHT = (200, 140, 255)
AI_SNAKE3_BODY_COLOR_DARK = (120, 60, 188)
AI_SNAKE3_HEAD_COLOR = (180, 255, 160)

# Hunger
HUNGER_MAX = 100.0
HUNGER_RATE = 100.0 / 30.0
HUNGER_PENALTY_RESET = 50.0
STARVATION_STEP_DISTANCE = WORLD_TILE_SIZE * 5

# Fog of war
HEAD_VISION_RADIUS = 200
FOG_EDGE_FEATHER = 40
FOG_COLOR = (20, 20, 30)
FOG_COOKIE_QUALITY = 50

# Camera
CAMERA_LERP = 0.12

# Background and scene lighting
BG_COLOR = (84, 118, 78)
GRASS_COLOR = (102, 142, 94)
GRASS_DENSITY = 0.005
GRASS_TEXTURE_SIZE = 256
WORLD_BORDER_COLOR = (230, 60, 60)

# Initial spawn
INITIAL_WORLD_X = MAP_WIDTH // 2
INITIAL_WORLD_Y = MAP_HEIGHT // 2
DUEL_PLAYER_SPAWN = (INITIAL_WORLD_X - 800, INITIAL_WORLD_Y)
DUEL_AI_SPAWN = (INITIAL_WORLD_X + 800, INITIAL_WORLD_Y)
DUEL_AI2_SPAWN = (INITIAL_WORLD_X, INITIAL_WORLD_Y - 800)
DUEL_AI3_SPAWN = (INITIAL_WORLD_X, INITIAL_WORLD_Y + 800)

# World population
PREY_TARGET_COUNT = 400
PREY_REFRESH_INTERVAL = 1.5
GUIDE_COUNT = 8
INITIAL_BEAST_COUNT = 5
SKILL_TARGET_COUNT = 24
SKILL_REFRESH_INTERVAL = 8.0
PREY_SPAWN_EXCLUSION_RADIUS = 150
SKILL_SPAWN_EXCLUSION_RADIUS = 150
BEAST_SPAWN_EXCLUSION_RADIUS = 320
GUIDE_SPAWN_EXCLUSION_RADIUS = 260
BEAST_TILE_FOOTPRINT = 2
ADVENTURE_OBSTACLE_MAX_COUNT = 35
ADVENTURE_OBSTACLE_LIFETIME = 30.0
ADVENTURE_OBSTACLE_SPAWN_INTERVAL = 6.0

# Duel mode overrides
DUEL_PREY_TARGET_COUNT = 900
DUEL_PREY_REFRESH_INTERVAL = 0.5
DUEL_SKILL_TARGET_COUNT = 48
DUEL_SKILL_REFRESH_INTERVAL = 3.0
DUEL_MAX_VISION_MULTIPLIER = 2.0
DUEL_OBSTACLE_MAX_COUNT = 75
DUEL_OBSTACLE_LIFETIME = 30.0
DUEL_OBSTACLE_SPAWN_INTERVAL = 4.0
DUEL_AI_SPEED_FACTOR = 0.75

PREY_TYPES = [
    ("mouse", 40, 1, (212, 214, 212), 10),
    ("rabbit", 30, 2, (230, 210, 174), 12),
    ("pheasant", 20, 3, (218, 170, 108), 13),
    ("deer", 10, 5, (194, 150, 96), 16),
]

BEAST_TYPES = [
    ("wolf", (240, 116, 92)),
    ("boar", (236, 176, 82)),
    ("bear", (188, 122, 82)),
    ("tiger", (248, 158, 72)),
]

SKILL_TYPES = {
    "purge": {
        "path": "assets/sprites/skills/purge.png",
        "color": (255, 140, 112),
        "ring_color": (255, 96, 72),
    },
    "haste": {
        "path": "assets/sprites/skills/haste.png",
        "color": (120, 214, 255),
        "ring_color": (70, 182, 255),
    },
    "harvest": {
        "path": "assets/sprites/skills/harvest.png",
        "color": (255, 214, 120),
        "ring_color": (255, 184, 62),
    },
    "grow": {
        "path": "assets/sprites/skills/grow.png",
        "color": (132, 234, 136),
        "ring_color": (88, 208, 108),
    },
    "vision": {
        "path": "assets/sprites/skills/vision.png",
        "color": (210, 170, 255),
        "ring_color": (166, 112, 255),
    },
}

BEAST_SPRITE_PATHS = {
    "wolf": "assets/sprites/beasts/wolf.png",
    "boar": "assets/sprites/beasts/boar.png",
    "bear": "assets/sprites/beasts/bear.png",
    "tiger": "assets/sprites/beasts/tiger.png",
}

# Collision
COLLISION_PREY = SNAKE_HEAD_RADIUS + 24
GUIDE_DISCOVER_RADIUS = 72
GUIDE_LIFETIME = 18.0
GUIDE_ARROW_LENGTH = 22
SKILL_PICKUP_RADIUS = SNAKE_HEAD_RADIUS + 22

# HUD
HUD_TEXT_COLOR = (234, 240, 228)
HUD_HINT_COLOR = (182, 208, 176)
HUD_ACCENT_COLOR = (255, 222, 96)
HUD_FONT_SIZE = 28
HUD_LEFT = 48
HUD_TOP = 18
HUD_WIDTH = 420
HUD_HEIGHT = 128
HUD_PANEL_COLOR = (8, 14, 8, 166)
SKILL_HUD_SIZE = 92
SKILL_HUD_LEFT = 34
SKILL_HUD_BOTTOM = 34

SATIETY_BAR_WIDTH = 228
SATIETY_BAR_HEIGHT = 18
SATIETY_BAR_BG = (46, 56, 44)
SATIETY_BAR_LOW = (228, 82, 70)
SATIETY_BAR_MID = (236, 194, 86)
SATIETY_BAR_HIGH = (118, 224, 104)

# Menu and overlays
MENU_BG_COLOR = (30, 46, 34)
MENU_PANEL_COLOR = (12, 18, 14, 176)
MENU_CARD_COLOR = (54, 78, 58)
MENU_CARD_BORDER = (188, 220, 166)
MENU_TITLE_COLOR = (255, 228, 110)
MENU_TEXT_COLOR = (224, 232, 220)
MENU_HINT_COLOR = (178, 198, 172)
GAMEOVER_TITLE_COLOR = (255, 126, 92)
GAMEOVER_TEXT_COLOR = (236, 228, 210)
PAUSE_PANEL_COLOR = (10, 16, 12, 188)
PAUSE_BUTTON_COLOR = (54, 78, 58)
PAUSE_BUTTON_BORDER = (188, 220, 166)
DUEL_ALERT_COLOR = (255, 72, 72)
DUEL_ALERT_DURATION = 2.5
DUEL_RESPAWN_DURATION = 3.0
DUEL_OVERLAY_COLOR = (120, 0, 0, 132)
DUEL_OVERLAY_EDGE = (255, 98, 98)
DUEL_REVEAL_DURATION = 5.0
AI_TARGET_REFRESH_INTERVAL = 0.45

DUEL_AI_NAMES = ["Forgetmena", "Bai-Kking", "earth34online"]

# Click effect
CLICK_EFFECT_DURATION = 0.46
CLICK_EFFECT_COLOR = (116, 214, 255)
CLICK_EFFECT_ACCENT = (255, 236, 160)

# Classic mode
CLASSIC_GRID_COLS = 40
CLASSIC_GRID_ROWS = 22
CLASSIC_MOVE_INTERVAL = 0.14
CLASSIC_INITIAL_LENGTH = 4
CLASSIC_BOARD_MARGIN = 24
CLASSIC_BOARD_BG = (24, 34, 26)
CLASSIC_BOARD_LINE = (70, 98, 72)
CLASSIC_SNAKE_BODY = (114, 214, 106)
CLASSIC_SNAKE_HEAD = (255, 226, 92)
CLASSIC_FOOD = (255, 108, 92)
CLASSIC_OBSTACLE = (84, 100, 88)
CLASSIC_OBSTACLE_EDGE = (44, 56, 48)
CLASSIC_TEXT_SHADOW = (16, 22, 14)

# Audio
AUDIO_EAT = "eat.wav"
AUDIO_DEATH = "death.wav"
AUDIO_GUIDE = "guide.wav"
