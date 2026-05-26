"""Main entry point for the snake game."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
import sys

import pygame

from src.core.settings import (
    BG_COLOR,
    CLICK_EFFECT_ACCENT,
    CLICK_EFFECT_COLOR,
    CLICK_EFFECT_DURATION,
    FPS,
    GAMEOVER_TEXT_COLOR,
    GAMEOVER_TITLE_COLOR,
    GRASS_COLOR,
    GRASS_DENSITY,
    GRASS_TEXTURE_SIZE,
    HUD_ACCENT_COLOR,
    HUD_HEIGHT,
    HUD_HINT_COLOR,
    HUD_LEFT,
    HUD_PANEL_COLOR,
    HUD_TEXT_COLOR,
    HUD_TOP,
    HUD_WIDTH,
    MAP_HEIGHT,
    MAP_WIDTH,
    MENU_BG_COLOR,
    MENU_CARD_BORDER,
    MENU_CARD_COLOR,
    MENU_HINT_COLOR,
    MENU_PANEL_COLOR,
    MENU_TEXT_COLOR,
    MENU_TITLE_COLOR,
    PAUSE_BUTTON_BORDER,
    PAUSE_BUTTON_COLOR,
    PAUSE_PANEL_COLOR,
    SATIETY_BAR_BG,
    SATIETY_BAR_HEIGHT,
    SATIETY_BAR_HIGH,
    SATIETY_BAR_LOW,
    SATIETY_BAR_MID,
    SATIETY_BAR_WIDTH,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SKILL_HUD_BOTTOM,
    SKILL_HUD_LEFT,
    SKILL_HUD_SIZE,
    SKILL_TYPES,
    SNAKE_BODY_COLOR_BRIGHT,
    SNAKE_BODY_COLOR_DARK,
    SNAKE_BODY_RADIUS_MAX,
    SNAKE_BODY_RADIUS_MIN,
    SNAKE_GLOW_ALPHA,
    SNAKE_HEAD_COLOR,
    SNAKE_HEAD_RADIUS,
    SNAKE_INITIAL_LENGTH,
    WORLD_BORDER_COLOR,
    WORLD_TILE_SIZE,
)
from src.entities.classic_mode import ClassicSnakeGame
from src.entities.snake import Snake
from src.entities.world import World
from src.systems.audio import AudioManager
from src.systems.camera import Camera
from src.systems.fog import FogOfWar
from src.systems.input_handler import InputHandler
from src.systems.sprite_bank import SpriteBank


STATE_MENU = "menu"
STATE_ADVENTURE = "adventure"
STATE_CLASSIC = "classic"
STATE_GAMEOVER = "gameover"
STATE_PAUSED = "paused"

MODE_CLASSIC = "classic"
MODE_ADVENTURE = "adventure"

_body_circle_cache = {}
_glow_circle_cache = {}
_grass_tile = None


@dataclass
class ClickEffect:
    world_x: float
    world_y: float
    age: float = 0.0

    def update(self, dt):
        self.age += dt
        return self.age < CLICK_EFFECT_DURATION

    def draw(self, screen, camera):
        progress = min(1.0, self.age / CLICK_EFFECT_DURATION)
        alpha = max(0, int(220 * (1.0 - progress)))
        radius = 16 + int(progress * 46)
        ring_thickness = max(2, int(5 - progress * 3))
        screen_x, screen_y = camera.world_to_screen(self.world_x, self.world_y)

        ring_surface = pygame.Surface((radius * 2 + 12, radius * 2 + 12), pygame.SRCALPHA)
        center = ring_surface.get_rect().center
        pygame.draw.circle(ring_surface, (*CLICK_EFFECT_COLOR, alpha), center, radius, ring_thickness)
        pygame.draw.circle(ring_surface, (*CLICK_EFFECT_ACCENT, alpha // 2), center, max(6, radius // 3), 2)
        screen.blit(
            ring_surface,
            (screen_x - ring_surface.get_width() // 2, screen_y - ring_surface.get_height() // 2),
        )

        chevron_length = 18 + progress * 12
        for base_angle in (-2.4, -0.7, 0.7, 2.4):
            tip_x = screen_x + math.cos(base_angle) * chevron_length
            tip_y = screen_y + math.sin(base_angle) * chevron_length
            left_x = tip_x + math.cos(base_angle + 2.6) * 8
            left_y = tip_y + math.sin(base_angle + 2.6) * 8
            right_x = tip_x + math.cos(base_angle - 2.6) * 8
            right_y = tip_y + math.sin(base_angle - 2.6) * 8
            pygame.draw.polygon(
                screen,
                (*CLICK_EFFECT_COLOR, alpha),
                [(tip_x, tip_y), (left_x, left_y), (right_x, right_y)],
            )


def _make_gradient_circle(radius, center_color, edge_color):
    diameter = radius * 2
    surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))
    for current_radius in range(radius, 0, -1):
        ratio = current_radius / max(radius, 1)
        red = int(center_color[0] * (1 - ratio) + edge_color[0] * ratio)
        green = int(center_color[1] * (1 - ratio) + edge_color[1] * ratio)
        blue = int(center_color[2] * (1 - ratio) + edge_color[2] * ratio)
        alpha = 255 if current_radius > radius - 2 else int(255 * (current_radius / max(radius - 1, 1)))
        pygame.draw.circle(surface, (red, green, blue, alpha), (radius, radius), current_radius)
    return surface


def _make_glow_circle(radius, color, alpha):
    diameter = radius * 2
    surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))
    for current_radius in range(radius, 0, -1):
        current_alpha = alpha if current_radius > radius - 3 else int(alpha * (current_radius / max(radius - 1, 1)))
        pygame.draw.circle(surface, (*color, current_alpha), (radius, radius), current_radius)
    return surface


def _get_body_circle(radius, color):
    key = (radius, color)
    if key not in _body_circle_cache:
        edge_color = (int(color[0] * 0.6), int(color[1] * 0.6), int(color[2] * 0.6))
        _body_circle_cache[key] = _make_gradient_circle(radius, color, edge_color)
    return _body_circle_cache[key]


def _get_glow_circle(radius, color):
    key = (radius, color, SNAKE_GLOW_ALPHA)
    if key not in _glow_circle_cache:
        _glow_circle_cache[key] = _make_glow_circle(radius + 4, color, SNAKE_GLOW_ALPHA)
    return _glow_circle_cache[key]


def _init_grass_tile():
    global _grass_tile
    size = GRASS_TEXTURE_SIZE
    _grass_tile = pygame.Surface((size, size))
    _grass_tile.fill(BG_COLOR)
    for y in range(size):
        for x in range(size):
            if random.random() < GRASS_DENSITY:
                shade = random.randint(0, 22)
                color = (
                    min(255, GRASS_COLOR[0] + shade),
                    min(255, GRASS_COLOR[1] + shade),
                    min(255, GRASS_COLOR[2] + shade),
                )
                _grass_tile.set_at((x, y), color)


def draw_background(screen, camera):
    global _grass_tile
    if _grass_tile is None:
        _init_grass_tile()

    offset_x, offset_y = camera.offset
    tile_size = GRASS_TEXTURE_SIZE
    tile_start_x = int(offset_x // tile_size) * tile_size
    tile_start_y = int(offset_y // tile_size) * tile_size

    for world_x in range(tile_start_x - tile_size, int(offset_x + SCREEN_WIDTH) + tile_size, tile_size):
        for world_y in range(tile_start_y - tile_size, int(offset_y + SCREEN_HEIGHT) + tile_size, tile_size):
            screen_x, screen_y = camera.world_to_screen(world_x, world_y)
            if -tile_size <= screen_x <= SCREEN_WIDTH and -tile_size <= screen_y <= SCREEN_HEIGHT:
                screen.blit(_grass_tile, (screen_x, screen_y))

    grid_color = (126, 160, 118)
    grid_start_x = int(offset_x // WORLD_TILE_SIZE) * WORLD_TILE_SIZE
    grid_start_y = int(offset_y // WORLD_TILE_SIZE) * WORLD_TILE_SIZE
    for world_x in range(grid_start_x, int(offset_x + SCREEN_WIDTH) + WORLD_TILE_SIZE, WORLD_TILE_SIZE):
        screen_x, _ = camera.world_to_screen(world_x, 0)
        pygame.draw.line(screen, grid_color, (screen_x, 0), (screen_x, SCREEN_HEIGHT), 1)
    for world_y in range(grid_start_y, int(offset_y + SCREEN_HEIGHT) + WORLD_TILE_SIZE, WORLD_TILE_SIZE):
        _, screen_y = camera.world_to_screen(0, world_y)
        pygame.draw.line(screen, grid_color, (0, screen_y), (SCREEN_WIDTH, screen_y), 1)

    top_left = camera.world_to_screen(0, 0)
    bottom_right = camera.world_to_screen(MAP_WIDTH, MAP_HEIGHT)
    border_rect = pygame.Rect(top_left[0], top_left[1], bottom_right[0] - top_left[0], bottom_right[1] - top_left[1])
    pygame.draw.rect(screen, WORLD_BORDER_COLOR, border_rect, 4)


def _lerp_color(color_a, color_b, ratio):
    return (
        int(color_a[0] + (color_b[0] - color_a[0]) * ratio),
        int(color_a[1] + (color_b[1] - color_a[1]) * ratio),
        int(color_a[2] + (color_b[2] - color_a[2]) * ratio),
    )


def draw_snake(screen, camera, snake):
    if not snake.segments:
        return

    segment_count = len(snake.segments)
    for index, segment in enumerate(snake.segments):
        screen_x, screen_y = camera.world_to_screen(segment[0], segment[1])
        ratio = index / max(segment_count - 1, 1)
        radius = SNAKE_BODY_RADIUS_MAX - ratio * (SNAKE_BODY_RADIUS_MAX - SNAKE_BODY_RADIUS_MIN)
        radius = max(SNAKE_BODY_RADIUS_MIN, int(radius))
        body_color = _lerp_color(SNAKE_BODY_COLOR_BRIGHT, SNAKE_BODY_COLOR_DARK, ratio)
        glow = _get_glow_circle(radius, body_color)
        screen.blit(glow, (screen_x - glow.get_width() // 2, screen_y - glow.get_height() // 2))

    for index, segment in enumerate(snake.segments[1:], start=1):
        screen_x, screen_y = camera.world_to_screen(segment[0], segment[1])
        ratio = index / max(segment_count - 1, 1)
        radius = SNAKE_BODY_RADIUS_MAX - ratio * (SNAKE_BODY_RADIUS_MAX - SNAKE_BODY_RADIUS_MIN)
        radius = max(SNAKE_BODY_RADIUS_MIN, int(radius))
        body_color = _lerp_color(SNAKE_BODY_COLOR_BRIGHT, SNAKE_BODY_COLOR_DARK, ratio)
        circle = _get_body_circle(radius, body_color)
        screen.blit(circle, (screen_x - circle.get_width() // 2, screen_y - circle.get_height() // 2))

    head_x, head_y = camera.world_to_screen(snake.segments[0][0], snake.segments[0][1])
    head_glow = _get_glow_circle(SNAKE_HEAD_RADIUS, SNAKE_HEAD_COLOR)
    head_circle = _get_body_circle(SNAKE_HEAD_RADIUS, SNAKE_HEAD_COLOR)
    screen.blit(head_glow, (head_x - head_glow.get_width() // 2, head_y - head_glow.get_height() // 2))
    screen.blit(head_circle, (head_x - head_circle.get_width() // 2, head_y - head_circle.get_height() // 2))

    end_x = head_x + math.cos(snake.angle) * (SNAKE_HEAD_RADIUS + 8)
    end_y = head_y + math.sin(snake.angle) * (SNAKE_HEAD_RADIUS + 8)
    pygame.draw.line(screen, (0, 0, 0), (head_x, head_y), (int(end_x), int(end_y)), 2)


def draw_satiety_bar(screen, x, y, satiety_pct):
    bar_rect = pygame.Rect(x, y, SATIETY_BAR_WIDTH, SATIETY_BAR_HEIGHT)
    pygame.draw.rect(screen, SATIETY_BAR_BG, bar_rect, border_radius=8)

    fill_width = int(SATIETY_BAR_WIDTH * satiety_pct / 100)
    if fill_width > 0:
        if satiety_pct < 30:
            color = SATIETY_BAR_LOW
        elif satiety_pct < 60:
            color = SATIETY_BAR_MID
        else:
            color = SATIETY_BAR_HIGH
        pygame.draw.rect(screen, color, pygame.Rect(x, y, fill_width, SATIETY_BAR_HEIGHT), border_radius=8)

    pygame.draw.rect(screen, (132, 148, 120), bar_rect, 1, border_radius=8)


def draw_adventure_hud(screen, snake, font, small_font, max_length, held_skill, sprite_bank):
    satiety = max(0.0, 100.0 - snake.hunger)
    panel = pygame.Surface((HUD_WIDTH, HUD_HEIGHT), pygame.SRCALPHA)
    panel.fill(HUD_PANEL_COLOR)
    screen.blit(panel, (HUD_LEFT, HUD_TOP))

    draw_satiety_bar(screen, HUD_LEFT + 18, HUD_TOP + 44, satiety)
    screen.blit(font.render(f"饱腹度 {satiety:.0f}%", True, HUD_TEXT_COLOR), (HUD_LEFT + 18, HUD_TOP + 14))
    screen.blit(font.render(f"长度 {snake.length} / 最高 {max_length}", True, HUD_TEXT_COLOR), (HUD_LEFT + 18, HUD_TOP + 72))

    if not snake.alive:
        status = "状态 已死亡"
    elif snake.speed_boost_timer > 0 and snake.moving:
        status = f"自动游走  加速 {snake.speed_boost_timer:.1f}s  视野 x{snake.vision_multiplier:.2f}"
    elif snake.speed_boost_timer > 0:
        status = f"等待指令  加速保留 {snake.speed_boost_timer:.1f}s  视野 x{snake.vision_multiplier:.2f}"
    elif snake.moving:
        status = f"自动游走  速度 {snake.current_speed:.0f}px/s  视野 x{snake.vision_multiplier:.2f}"
    else:
        status = f"等待左键指令  视野 x{snake.vision_multiplier:.2f}"
    screen.blit(small_font.render(status, True, HUD_HINT_COLOR), (HUD_LEFT + 18, HUD_TOP + 102))

    if held_skill is not None:
        draw_held_skill(screen, held_skill, sprite_bank)


def draw_held_skill(screen, held_skill, sprite_bank):
    rect = pygame.Rect(
        SKILL_HUD_LEFT,
        SCREEN_HEIGHT - SKILL_HUD_BOTTOM - SKILL_HUD_SIZE,
        SKILL_HUD_SIZE,
        SKILL_HUD_SIZE,
    )
    surface = pygame.Surface(rect.size, pygame.SRCALPHA)
    surface.fill((16, 28, 18, 138))
    screen.blit(surface, rect.topleft)
    pygame.draw.rect(screen, (122, 166, 120), rect, 2, border_radius=18)
    config = SKILL_TYPES[held_skill]
    icon_rect = rect.inflate(-12, -12)
    icon = sprite_bank.get(config["path"], icon_rect.size, config["color"])
    screen.blit(icon, icon_rect.topleft)


def draw_text_centered(screen, font, text, color, y):
    surface = font.render(text, True, color)
    screen.blit(surface, ((SCREEN_WIDTH - surface.get_width()) // 2, y))


def get_menu_button_rects():
    gap = max(40, SCREEN_WIDTH // 24)
    card_width = min(360, (SCREEN_WIDTH - gap - 140) // 2)
    card_height = min(270, SCREEN_HEIGHT // 3)
    total_width = card_width * 2 + gap
    start_x = (SCREEN_WIDTH - total_width) // 2
    top_y = int(SCREEN_HEIGHT * 0.34)
    return {
        MODE_CLASSIC: pygame.Rect(start_x, top_y, card_width, card_height),
        MODE_ADVENTURE: pygame.Rect(start_x + card_width + gap, top_y, card_width, card_height),
    }


def draw_menu(screen, title_font, body_font, small_font, number_font):
    screen.fill(MENU_BG_COLOR)
    panel_rect = pygame.Rect(60, 48, SCREEN_WIDTH - 120, SCREEN_HEIGHT - 96)
    panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
    panel.fill(MENU_PANEL_COLOR)
    screen.blit(panel, panel_rect.topleft)

    draw_text_centered(screen, title_font, "贪吃蛇双模式", MENU_TITLE_COLOR, max(72, SCREEN_HEIGHT // 10))
    draw_text_centered(screen, body_font, "点击 1 / 2 或直接点击卡片进入对应玩法", MENU_TEXT_COLOR, max(160, SCREEN_HEIGHT // 5))

    buttons = get_menu_button_rects()
    card_info = {
        MODE_CLASSIC: {
            "number": "1",
            "title": "经典模式",
            "lines": [
                "全屏障碍地图",
                "方向键 / WASD 转向",
                "撞墙、撞障碍、撞自己即结束",
            ],
        },
        MODE_ADVENTURE: {
            "number": "2",
            "title": "野兽模式",
            "lines": [
                "左键点地后自动游走",
                "边界只能贴边，不会出图",
                "空格释放当前技能卡",
            ],
        },
    }

    for mode, rect in buttons.items():
        pygame.draw.rect(screen, MENU_CARD_COLOR, rect, border_radius=22)
        pygame.draw.rect(screen, MENU_CARD_BORDER, rect, width=3, border_radius=22)
        screen.blit(number_font.render(card_info[mode]["number"], True, MENU_TITLE_COLOR), (rect.x + 26, rect.y + 18))
        screen.blit(body_font.render(card_info[mode]["title"], True, MENU_TEXT_COLOR), (rect.x + 26, rect.y + 118))

        y = rect.y + 170
        for line in card_info[mode]["lines"]:
            screen.blit(small_font.render(line, True, MENU_HINT_COLOR), (rect.x + 26, y))
            y += 30

    footer_y = min(SCREEN_HEIGHT - 100, buttons[MODE_CLASSIC].bottom + 56)
    footer_lines = [
        "Q 在游戏中会进入暂停菜单；暂停后按 R 继续、M 回主界面、ESC 退出。",
        "模式 2 的野兽占 3x3 格，技能卡占 1x1 格，贴图接口已保留。",
    ]
    for line in footer_lines:
        draw_text_centered(screen, small_font, line, MENU_HINT_COLOR, footer_y)
        footer_y += 30


def draw_gameover(screen, title_font, body_font, mode, snake, max_length, classic_game):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 176))
    screen.blit(overlay, (0, 0))
    draw_text_centered(screen, title_font, "游戏结束", GAMEOVER_TITLE_COLOR, SCREEN_HEIGHT // 4)

    if mode == MODE_ADVENTURE:
        info_lines = [
            f"野兽模式结束  最终长度 {snake.length}  本局最高 {max_length}",
            "R 重新开始当前模式",
            "M 返回模式菜单",
        ]
    else:
        info_lines = [
            f"经典模式结束  得分 {classic_game.score}  长度 {classic_game.length}",
            "R 重新开始当前模式",
            "M 返回模式菜单",
        ]

    y = SCREEN_HEIGHT // 2 - 40
    for index, line in enumerate(info_lines):
        color = GAMEOVER_TEXT_COLOR if index == 0 else HUD_TEXT_COLOR
        surface = body_font.render(line, True, color)
        screen.blit(surface, ((SCREEN_WIDTH - surface.get_width()) // 2, y))
        y += 52


def get_pause_button_rects():
    width = min(300, SCREEN_WIDTH // 3)
    height = 68
    gap = 18
    total_height = height * 3 + gap * 2
    start_y = (SCREEN_HEIGHT - total_height) // 2 + 48
    x = (SCREEN_WIDTH - width) // 2
    return {
        "resume": pygame.Rect(x, start_y, width, height),
        "menu": pygame.Rect(x, start_y + height + gap, width, height),
        "quit": pygame.Rect(x, start_y + (height + gap) * 2, width, height),
    }


def draw_pause_overlay(screen, title_font, body_font, small_font):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    screen.blit(overlay, (0, 0))

    panel_width = min(520, SCREEN_WIDTH - 120)
    panel_height = 360
    panel_rect = pygame.Rect((SCREEN_WIDTH - panel_width) // 2, (SCREEN_HEIGHT - panel_height) // 2, panel_width, panel_height)
    panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
    panel.fill(PAUSE_PANEL_COLOR)
    screen.blit(panel, panel_rect.topleft)

    draw_text_centered(screen, title_font, "暂停", MENU_TITLE_COLOR, panel_rect.y + 24)
    draw_text_centered(screen, small_font, "R 继续，M 回主界面，ESC 退出", MENU_HINT_COLOR, panel_rect.y + 108)

    labels = {
        "resume": "继续游戏",
        "menu": "返回主界面",
        "quit": "退出游戏",
    }
    for key, rect in get_pause_button_rects().items():
        pygame.draw.rect(screen, PAUSE_BUTTON_COLOR, rect, border_radius=18)
        pygame.draw.rect(screen, PAUSE_BUTTON_BORDER, rect, width=2, border_radius=18)
        text = body_font.render(labels[key], True, MENU_TEXT_COLOR)
        screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))


def distance_point_to_rect(point, rect):
    closest_x = max(rect.left, min(point[0], rect.right))
    closest_y = max(rect.top, min(point[1], rect.bottom))
    return math.hypot(point[0] - closest_x, point[1] - closest_y)


def point_visible_to_snake(point, snake):
    return math.hypot(point[0] - snake.head_pos[0], point[1] - snake.head_pos[1]) <= snake.current_vision_radius


def rect_visible_to_snake(rect, snake):
    return distance_point_to_rect(snake.head_pos, rect) <= snake.current_vision_radius


def activate_held_skill(skill_kind, snake, world, audio):
    if skill_kind == "purge":
        visible_beasts = world.visible_beasts(lambda rect: rect_visible_to_snake(rect, snake))
        if visible_beasts:
            world.clear_beasts(visible_beasts)
            audio.play_guide()
        return True

    if skill_kind == "haste":
        snake.apply_speed_boost()
        audio.play_guide()
        return True

    if skill_kind == "harvest":
        visible_prey = world.visible_prey(lambda point: point_visible_to_snake(point, snake))
        total_growth = sum(prey.length_bonus for prey in visible_prey)
        for prey in visible_prey:
            world.remove_prey(prey)
        if total_growth > 0:
            snake.grow(total_growth)
            snake.hunger = 0.0
            audio.play_eat()
        return True

    if skill_kind == "grow":
        snake.grow(1)
        audio.play_eat()
        return True

    return False


def init_adventure_objects(sprite_bank):
    camera = Camera(MAP_WIDTH, MAP_HEIGHT, SCREEN_WIDTH, SCREEN_HEIGHT)
    snake = Snake()
    input_handler = InputHandler()
    fog = FogOfWar(SCREEN_WIDTH, SCREEN_HEIGHT, camera)
    world = World(snake, sprite_bank)
    camera.reset()
    fog.update(snake.head_pos, snake.current_vision_radius)
    return camera, snake, input_handler, fog, world


def handle_adventure_collisions(snake, world, audio, held_skill):
    head_x, head_y = snake.head_pos

    prey = world.get_colliding_prey(head_x, head_y)
    if prey is not None:
        snake.grow(prey.length_bonus)
        snake.hunger = 0.0
        world.remove_prey(prey)
        world.add_beast()
        audio.play_eat()

    beast = world.get_colliding_beast(head_x, head_y)
    if beast is not None:
        snake.alive = False
        audio.play_death()

    obstacle = world.get_colliding_obstacle(head_x, head_y)
    if obstacle is not None:
        snake.alive = False
        audio.play_death()

    guide = world.get_colliding_guide(head_x, head_y)
    if guide is not None:
        world.remove_guide(guide)
        audio.play_guide()

    if held_skill is None:
        skill_card = world.get_colliding_skill_card(head_x, head_y)
        if skill_card is not None:
            held_skill = skill_card.kind
            world.remove_skill_card(skill_card)

    return held_skill


def load_fonts():
    font_paths = [
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    title_font = body_font = small_font = number_font = None
    for path in font_paths:
        try:
            title_font = pygame.font.Font(path, 72)
            body_font = pygame.font.Font(path, 32)
            small_font = pygame.font.Font(path, 24)
            number_font = pygame.font.Font(path, 92)
            break
        except (FileNotFoundError, OSError):
            continue

    if title_font is None:
        title_font = pygame.font.Font(None, 72)
        body_font = pygame.font.Font(None, 32)
        small_font = pygame.font.Font(None, 24)
        number_font = pygame.font.Font(None, 92)
    return title_font, body_font, small_font, number_font


def start_mode(mode, sprite_bank):
    if mode == MODE_ADVENTURE:
        camera, snake, input_handler, fog, world = init_adventure_objects(sprite_bank)
        return {
            "state": STATE_ADVENTURE,
            "camera": camera,
            "snake": snake,
            "input_handler": input_handler,
            "fog": fog,
            "world": world,
            "held_skill": None,
            "click_effects": [],
            "max_length": SNAKE_INITIAL_LENGTH,
            "game_time": 0.0,
            "classic_game": None,
            "active_mode": MODE_ADVENTURE,
        }

    return {
        "state": STATE_CLASSIC,
        "camera": None,
        "snake": None,
        "input_handler": None,
        "fog": None,
        "world": None,
        "held_skill": None,
        "click_effects": [],
        "max_length": 0,
        "game_time": 0.0,
        "classic_game": ClassicSnakeGame(),
        "active_mode": MODE_CLASSIC,
    }


def _apply_mode_state(mode_state):
    return (
        mode_state["state"],
        mode_state["active_mode"],
        mode_state["camera"],
        mode_state["snake"],
        mode_state["input_handler"],
        mode_state["fog"],
        mode_state["world"],
        mode_state["classic_game"],
        mode_state["held_skill"],
        mode_state["click_effects"],
        mode_state["max_length"],
        mode_state["game_time"],
    )


def draw_adventure_scene(screen, camera, world, snake, fog, click_effects, game_time):
    draw_background(screen, camera)
    world.draw(screen, camera, game_time)
    draw_snake(screen, camera, snake)
    fog.apply(screen)
    for effect in click_effects:
        effect.draw(screen, camera)


def main():
    pygame.init()
    try:
        pygame.mixer.init(buffer=512)
    except pygame.error:
        pass

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
    pygame.display.set_caption("贪吃蛇双模式")
    clock = pygame.time.Clock()

    title_font, body_font, small_font, number_font = load_fonts()
    sprite_bank = SpriteBank()
    _init_grass_tile()
    audio = AudioManager()

    state = STATE_MENU
    active_mode = None
    paused_mode = None
    camera = None
    snake = None
    input_handler = None
    fog = None
    world = None
    classic_game = None
    held_skill = None
    click_effects = []
    max_length = SNAKE_INITIAL_LENGTH
    game_time = 0.0
    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0
        if dt > 0.1:
            dt = 0.016

        events = pygame.event.get()

        if state == STATE_MENU:
            buttons = get_menu_button_rects()
            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_1:
                        mode_state = start_mode(MODE_CLASSIC, sprite_bank)
                        (
                            state,
                            active_mode,
                            camera,
                            snake,
                            input_handler,
                            fog,
                            world,
                            classic_game,
                            held_skill,
                            click_effects,
                            max_length,
                            game_time,
                        ) = _apply_mode_state(mode_state)
                    elif event.key == pygame.K_2:
                        mode_state = start_mode(MODE_ADVENTURE, sprite_bank)
                        (
                            state,
                            active_mode,
                            camera,
                            snake,
                            input_handler,
                            fog,
                            world,
                            classic_game,
                            held_skill,
                            click_effects,
                            max_length,
                            game_time,
                        ) = _apply_mode_state(mode_state)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if buttons[MODE_CLASSIC].collidepoint(event.pos):
                        mode_state = start_mode(MODE_CLASSIC, sprite_bank)
                    elif buttons[MODE_ADVENTURE].collidepoint(event.pos):
                        mode_state = start_mode(MODE_ADVENTURE, sprite_bank)
                    else:
                        mode_state = None
                    if mode_state is not None:
                        (
                            state,
                            active_mode,
                            camera,
                            snake,
                            input_handler,
                            fog,
                            world,
                            classic_game,
                            held_skill,
                            click_effects,
                            max_length,
                            game_time,
                        ) = _apply_mode_state(mode_state)
            draw_menu(screen, title_font, body_font, small_font, number_font)

        elif state == STATE_ADVENTURE:
            actions = input_handler.handle_events(events, camera)
            if actions.quit:
                running = False
            elif actions.pause_requested:
                paused_mode = MODE_ADVENTURE
                state = STATE_PAUSED
            elif actions.back_to_menu:
                state = STATE_MENU
            else:
                if actions.restart:
                    mode_state = start_mode(MODE_ADVENTURE, sprite_bank)
                    (
                        state,
                        active_mode,
                        camera,
                        snake,
                        input_handler,
                        fog,
                        world,
                        classic_game,
                        held_skill,
                        click_effects,
                        max_length,
                        game_time,
                    ) = _apply_mode_state(mode_state)
                else:
                    if actions.target_point is not None:
                        snake.set_target(*actions.target_point)
                        click_effects.append(ClickEffect(*actions.click_world))

                    if actions.activate_skill and held_skill is not None:
                        if activate_held_skill(held_skill, snake, world, audio):
                            held_skill = None

                    snake.update(dt)
                    camera.update(snake.head_pos[0], snake.head_pos[1], dt)
                    fog.update(snake.head_pos, snake.current_vision_radius)
                    world.update(dt, snake)
                    held_skill = handle_adventure_collisions(snake, world, audio, held_skill)
                    click_effects = [effect for effect in click_effects if effect.update(dt)]
                    game_time += dt
                    max_length = max(max_length, snake.length)

                    if not snake.alive:
                        state = STATE_GAMEOVER

            draw_adventure_scene(screen, camera, world, snake, fog, click_effects, game_time)
            draw_adventure_hud(screen, snake, body_font, small_font, max_length, held_skill, sprite_bank)

        elif state == STATE_CLASSIC:
            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_q:
                        paused_mode = MODE_CLASSIC
                        state = STATE_PAUSED
                    elif event.key == pygame.K_r:
                        classic_game.reset()
                    elif event.key == pygame.K_m:
                        state = STATE_MENU
                    else:
                        classic_game.handle_event(event)

            if state == STATE_CLASSIC:
                classic_game.update(dt)
                if not classic_game.alive:
                    state = STATE_GAMEOVER
                classic_game.draw(screen, body_font, small_font)

        elif state == STATE_PAUSED:
            if paused_mode == MODE_ADVENTURE:
                draw_adventure_scene(screen, camera, world, snake, fog, click_effects, game_time)
                draw_adventure_hud(screen, snake, body_font, small_font, max_length, held_skill, sprite_bank)
            else:
                classic_game.draw(screen, body_font, small_font)

            draw_pause_overlay(screen, title_font, body_font, small_font)

            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_r, pygame.K_c, pygame.K_q):
                        state = STATE_ADVENTURE if paused_mode == MODE_ADVENTURE else STATE_CLASSIC
                    elif event.key == pygame.K_m:
                        state = STATE_MENU
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    buttons = get_pause_button_rects()
                    if buttons["resume"].collidepoint(event.pos):
                        state = STATE_ADVENTURE if paused_mode == MODE_ADVENTURE else STATE_CLASSIC
                    elif buttons["menu"].collidepoint(event.pos):
                        state = STATE_MENU
                    elif buttons["quit"].collidepoint(event.pos):
                        running = False

        elif state == STATE_GAMEOVER:
            if active_mode == MODE_ADVENTURE:
                draw_adventure_scene(screen, camera, world, snake, fog, click_effects, game_time)
                draw_adventure_hud(screen, snake, body_font, small_font, max_length, held_skill, sprite_bank)
            else:
                classic_game.draw(screen, body_font, small_font)

            draw_gameover(screen, title_font, body_font, active_mode, snake, max_length, classic_game)

            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_r:
                        mode_state = start_mode(active_mode, sprite_bank)
                        (
                            state,
                            active_mode,
                            camera,
                            snake,
                            input_handler,
                            fog,
                            world,
                            classic_game,
                            held_skill,
                            click_effects,
                            max_length,
                            game_time,
                        ) = _apply_mode_state(mode_state)
                    elif event.key == pygame.K_m:
                        state = STATE_MENU

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
