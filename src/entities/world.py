"""Entity management for the adventure mode."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

import pygame

from src.core.settings import (
    ADVENTURE_OBSTACLE_LIFETIME,
    ADVENTURE_OBSTACLE_MAX_COUNT,
    ADVENTURE_OBSTACLE_SPAWN_INTERVAL,
    BEAST_SPRITE_PATHS,
    BEAST_TILE_FOOTPRINT,
    BEAST_TYPES,
    BEAST_SPAWN_EXCLUSION_RADIUS,
    CLICK_EFFECT_ACCENT,
    COLLISION_PREY,
    GUIDE_SPAWN_EXCLUSION_RADIUS,
    GUIDE_ARROW_LENGTH,
    GUIDE_COUNT,
    GUIDE_DISCOVER_RADIUS,
    GUIDE_LIFETIME,
    INITIAL_BEAST_COUNT,
    PREY_SPAWN_EXCLUSION_RADIUS,
    PREY_REFRESH_INTERVAL,
    PREY_TARGET_COUNT,
    PREY_TYPES,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SKILL_PICKUP_RADIUS,
    SKILL_SPAWN_EXCLUSION_RADIUS,
    SKILL_REFRESH_INTERVAL,
    SKILL_TARGET_COUNT,
    SKILL_TYPES,
    SNAKE_HEAD_RADIUS,
    WORLD_COLS,
    WORLD_ROWS,
    WORLD_TILE_SIZE,
)


@dataclass
class Prey:
    tile_x: int
    tile_y: int
    kind: str
    length_bonus: int
    color: tuple[int, int, int]
    radius: int

    @property
    def x(self):
        return self.tile_x * WORLD_TILE_SIZE + WORLD_TILE_SIZE / 2

    @property
    def y(self):
        return self.tile_y * WORLD_TILE_SIZE + WORLD_TILE_SIZE / 2


@dataclass
class Beast:
    tile_x: int
    tile_y: int
    kind: str
    color: tuple[int, int, int]

    @property
    def rect(self):
        return pygame.Rect(
            self.tile_x * WORLD_TILE_SIZE,
            self.tile_y * WORLD_TILE_SIZE,
            BEAST_TILE_FOOTPRINT * WORLD_TILE_SIZE,
            BEAST_TILE_FOOTPRINT * WORLD_TILE_SIZE,
        )

    @property
    def x(self):
        return self.rect.centerx

    @property
    def y(self):
        return self.rect.centery

    @property
    def sprite_path(self):
        return BEAST_SPRITE_PATHS[self.kind]


@dataclass
class SkillCard:
    tile_x: int
    tile_y: int
    kind: str
    color: tuple[int, int, int]
    ring_color: tuple[int, int, int]
    sprite_path: str

    @property
    def rect(self):
        return pygame.Rect(
            self.tile_x * WORLD_TILE_SIZE,
            self.tile_y * WORLD_TILE_SIZE,
            WORLD_TILE_SIZE,
            WORLD_TILE_SIZE,
        )

    @property
    def x(self):
        return self.rect.centerx

    @property
    def y(self):
        return self.rect.centery


@dataclass
class Guide:
    x: float
    y: float
    target_type: str
    direction_angle: float = 0.0
    lifetime: float = GUIDE_LIFETIME
    visible: bool = True


@dataclass
class AdventureObstacle:
    tile_x: int
    tile_y: int
    width_tiles: int
    height_tiles: int
    lifetime: float = ADVENTURE_OBSTACLE_LIFETIME

    @property
    def rect(self):
        return pygame.Rect(
            self.tile_x * WORLD_TILE_SIZE,
            self.tile_y * WORLD_TILE_SIZE,
            self.width_tiles * WORLD_TILE_SIZE,
            self.height_tiles * WORLD_TILE_SIZE,
        )


class World:
    """Tracks prey, beasts, guides, and adventure mode skill cards."""

    def __init__(self, snake_ref, sprite_bank, other_snakes=None, config=None, *, populate=True):
        self.snake = snake_ref
        self.snakes = [snake_ref]
        if other_snakes:
            self.snakes.extend(other_snakes)
        self.sprite_bank = sprite_bank
        self.prey_list = []
        self.beast_list = []
        self.guide_list = []
        self.skill_cards = []
        self.obstacle_list = []
        self._prey_timer = 0.0
        self._skill_timer = 0.0
        self._obstacle_timer = 0.0

        cfg = config or {}
        self._prey_target = cfg.get("prey_target", PREY_TARGET_COUNT)
        self._prey_interval = cfg.get("prey_interval", PREY_REFRESH_INTERVAL)
        self._skill_target = cfg.get("skill_target", SKILL_TARGET_COUNT)
        self._skill_interval = cfg.get("skill_interval", SKILL_REFRESH_INTERVAL)
        self._obstacle_max = cfg.get("obstacle_max", ADVENTURE_OBSTACLE_MAX_COUNT)
        self._obstacle_lifetime = cfg.get("obstacle_lifetime", ADVENTURE_OBSTACLE_LIFETIME)
        self._obstacle_interval = cfg.get("obstacle_interval", ADVENTURE_OBSTACLE_SPAWN_INTERVAL)

        if populate:
            self._spawn_initial()

    def _spawn_initial(self):
        for _ in range(INITIAL_BEAST_COUNT):
            self._spawn_beast()

        for _ in range(GUIDE_COUNT):
            guide = self._create_guide()
            if guide is not None:
                self.guide_list.append(guide)

        self._spawn_prey_to_target()
        self._spawn_initial_nearby_prey_if_needed()
        self._spawn_skill_cards_to_target()
        self._spawn_initial_nearby_skill_if_needed()

    def _tile_rect(self, tile_x, tile_y, size_tiles=1):
        return pygame.Rect(
            tile_x * WORLD_TILE_SIZE,
            tile_y * WORLD_TILE_SIZE,
            size_tiles * WORLD_TILE_SIZE,
            size_tiles * WORLD_TILE_SIZE,
        )

    def _set_snakes(self, snake_or_snakes):
        if isinstance(snake_or_snakes, (list, tuple)):
            snakes = list(snake_or_snakes)
        else:
            snakes = [snake_or_snakes]
        self.snakes = [snake for snake in snakes if snake is not None]
        if self.snakes:
            self.snake = self.snakes[0]

    def _head_positions(self):
        return [snake.head_pos for snake in self.snakes if snake.segments]

    def _random_tile_slot(self, size_tiles, exclude_x, exclude_y, exclude_radius):
        max_x = WORLD_COLS - size_tiles
        max_y = WORLD_ROWS - size_tiles

        for _ in range(180):
            tile_x = random.randint(0, max_x)
            tile_y = random.randint(0, max_y)
            rect = self._tile_rect(tile_x, tile_y, size_tiles)
            if math.hypot(rect.centerx - exclude_x, rect.centery - exclude_y) <= exclude_radius:
                continue
            if any(
                math.hypot(rect.centerx - head_x, rect.centery - head_y) <= exclude_radius
                for head_x, head_y in self._head_positions()
            ):
                continue
            if self._rect_is_occupied(rect):
                continue
            return tile_x, tile_y
        return None

    def _random_tile_slot_in_radius(self, size_tiles, min_distance, max_distance):
        max_x = WORLD_COLS - size_tiles
        max_y = WORLD_ROWS - size_tiles
        head_x, head_y = self.snake.head_pos
        candidates = []
        for tile_x in range(max_x + 1):
            for tile_y in range(max_y + 1):
                rect = self._tile_rect(tile_x, tile_y, size_tiles)
                distance = math.hypot(rect.centerx - head_x, rect.centery - head_y)
                if distance < min_distance or distance > max_distance:
                    continue
                if self._rect_is_occupied(rect):
                    continue
                candidates.append((tile_x, tile_y))
        if not candidates:
            return None
        return random.choice(candidates)

    def _rect_is_occupied(self, rect):
        for beast in self.beast_list:
            if rect.colliderect(beast.rect.inflate(8, 8)):
                return True

        for prey in self.prey_list:
            if rect.colliderect(self._tile_rect(prey.tile_x, prey.tile_y)):
                return True

        for card in self.skill_cards:
            if rect.colliderect(card.rect):
                return True

        for obstacle in self.obstacle_list:
            if rect.colliderect(obstacle.rect.inflate(8, 8)):
                return True

        for guide in self.guide_list:
            guide_rect = pygame.Rect(guide.x - 24, guide.y - 24, 48, 48)
            if rect.colliderect(guide_rect):
                return True

        for snake in self.snakes:
            for segment in snake.segments:
                segment_rect = pygame.Rect(
                    int(segment[0] - SNAKE_HEAD_RADIUS - 4),
                    int(segment[1] - SNAKE_HEAD_RADIUS - 4),
                    (SNAKE_HEAD_RADIUS + 4) * 2,
                    (SNAKE_HEAD_RADIUS + 4) * 2,
                )
                if rect.colliderect(segment_rect):
                    return True

        return False

    def _spawn_prey_to_target(self):
        weights = [prey_type[1] for prey_type in PREY_TYPES]
        while len(self.prey_list) < self._prey_target:
            slot = self._random_tile_slot(
                1,
                self.snake.head_pos[0],
                self.snake.head_pos[1],
                PREY_SPAWN_EXCLUSION_RADIUS,
            )
            if slot is None:
                break

            prey_kind, _, length_bonus, color, radius = random.choices(PREY_TYPES, weights=weights, k=1)[0]
            self.prey_list.append(
                Prey(slot[0], slot[1], prey_kind, length_bonus, color, radius)
            )

    def _spawn_skill_cards_to_target(self):
        all_kinds = list(SKILL_TYPES.keys())
        while len(self.skill_cards) < self._skill_target:
            slot = self._random_tile_slot(
                1,
                self.snake.head_pos[0],
                self.snake.head_pos[1],
                SKILL_SPAWN_EXCLUSION_RADIUS,
            )
            if slot is None:
                break

            existing_kinds = {card.kind for card in self.skill_cards}
            missing = [kind for kind in all_kinds if kind not in existing_kinds]
            kind = random.choice(missing or all_kinds)
            cfg = SKILL_TYPES[kind]
            self.skill_cards.append(
                SkillCard(slot[0], slot[1], kind, cfg["color"], cfg["ring_color"], cfg["path"])
            )

    def _spawn_initial_nearby_prey_if_needed(self):
        head_x, head_y = self.snake.head_pos
        if any(math.hypot(prey.x - head_x, prey.y - head_y) <= 240 for prey in self.prey_list):
            return

        slot = self._random_tile_slot_in_radius(1, 120, 220)
        if slot is None:
            return

        prey_kind, _, length_bonus, color, radius = random.choices(
            PREY_TYPES,
            weights=[prey_type[1] for prey_type in PREY_TYPES],
            k=1,
        )[0]
        self.prey_list.append(Prey(slot[0], slot[1], prey_kind, length_bonus, color, radius))

    def _spawn_initial_nearby_skill_if_needed(self):
        head_x, head_y = self.snake.head_pos
        if any(math.hypot(card.x - head_x, card.y - head_y) <= 260 for card in self.skill_cards):
            return

        slot = self._random_tile_slot_in_radius(1, 150, 250)
        if slot is None:
            return

        kind = random.choice(list(SKILL_TYPES.keys()))
        cfg = SKILL_TYPES[kind]
        self.skill_cards.append(SkillCard(slot[0], slot[1], kind, cfg["color"], cfg["ring_color"], cfg["path"]))

    def _spawn_beast(self):
        slot = self._random_tile_slot(
            BEAST_TILE_FOOTPRINT,
            self.snake.head_pos[0],
            self.snake.head_pos[1],
            BEAST_SPAWN_EXCLUSION_RADIUS,
        )
        if slot is None:
            return False

        kind, color = random.choice(BEAST_TYPES)
        self.beast_list.append(Beast(slot[0], slot[1], kind, color))
        return True

    def _spawn_obstacle(self):
        if len(self.obstacle_list) >= self._obstacle_max:
            return False

        width_tiles = random.randint(1, 2)
        height_tiles = random.randint(1, 2)
        slot = self._random_tile_slot(
                max(width_tiles, height_tiles),
                self.snake.head_pos[0],
                self.snake.head_pos[1],
                BEAST_SPAWN_EXCLUSION_RADIUS,
            )
        if slot is None:
            return False

        self.obstacle_list.append(
            AdventureObstacle(slot[0], slot[1], width_tiles, height_tiles, self._obstacle_lifetime)
        )
        return True

    def _create_guide(self):
        slot = self._random_tile_slot(
            1,
            self.snake.head_pos[0],
            self.snake.head_pos[1],
            GUIDE_SPAWN_EXCLUSION_RADIUS,
        )
        if slot is None:
            return None
        x = slot[0] * WORLD_TILE_SIZE + WORLD_TILE_SIZE / 2
        y = slot[1] * WORLD_TILE_SIZE + WORLD_TILE_SIZE / 2
        return Guide(x=x, y=y, target_type=random.choice(["prey", "beast"]))

    def add_beast(self):
        self._spawn_beast()

    def update(self, dt, snake):
        self._set_snakes(snake)
        self._prey_timer += dt
        self._skill_timer += dt
        self._obstacle_timer += dt
        if self._prey_timer >= self._prey_interval:
            self._prey_timer -= self._prey_interval
            self._spawn_prey_to_target()

        if self._skill_timer >= self._skill_interval:
            self._skill_timer -= self._skill_interval
            self._spawn_skill_cards_to_target()

        self._update_obstacles(dt)
        self._update_guides(dt)

    def _update_obstacles(self, dt):
        for obstacle in self.obstacle_list:
            obstacle.lifetime -= dt
        self.obstacle_list = [obstacle for obstacle in self.obstacle_list if obstacle.lifetime > 0]

        while self._obstacle_timer >= self._obstacle_interval:
            self._obstacle_timer -= self._obstacle_interval
            if len(self.obstacle_list) < self._obstacle_max:
                self._spawn_obstacle()

    def _update_guides(self, dt):
        for guide in self.guide_list:
            guide.lifetime -= dt
            if guide.lifetime <= 0:
                self._refresh_guide(guide)
                continue

            target_list = self.prey_list if guide.target_type == "prey" else self.beast_list
            if not target_list:
                guide.visible = False
                continue

            nearest = min(
                target_list,
                key=lambda entity: math.hypot(entity.x - guide.x, entity.y - guide.y),
            )
            guide.direction_angle = math.atan2(nearest.y - guide.y, nearest.x - guide.x)
            guide.visible = True

    def _refresh_guide(self, guide):
        new_guide = self._create_guide()
        if new_guide is None:
            guide.visible = False
            return

        guide.x = new_guide.x
        guide.y = new_guide.y
        guide.lifetime = GUIDE_LIFETIME
        guide.target_type = random.choice(["prey", "beast"])
        guide.direction_angle = 0.0
        guide.visible = True

    def draw(self, screen, camera, time):
        for obstacle in self.obstacle_list:
            rect = obstacle.rect
            screen_x, screen_y = camera.world_to_screen(rect.x, rect.y)
            if self._in_viewport(screen_x, screen_y, rect.width + rect.height):
                self._draw_obstacle(screen, screen_x, screen_y, obstacle)

        for prey in self.prey_list:
            screen_x, screen_y = camera.world_to_screen(prey.x, prey.y)
            if self._in_viewport(screen_x, screen_y, prey.radius + 12):
                self._draw_prey(screen, screen_x, screen_y, prey)

        for card in self.skill_cards:
            screen_x, screen_y = camera.world_to_screen(card.rect.x, card.rect.y)
            if self._in_viewport(screen_x, screen_y, WORLD_TILE_SIZE):
                self._draw_skill_card(screen, screen_x, screen_y, card, time)

        for beast in self.beast_list:
            rect = beast.rect
            screen_x, screen_y = camera.world_to_screen(rect.x, rect.y)
            if self._in_viewport(screen_x, screen_y, rect.width):
                self._draw_beast(screen, screen_x, screen_y, beast)

        for guide in self.guide_list:
            if not guide.visible:
                continue
            screen_x, screen_y = camera.world_to_screen(guide.x, guide.y)
            if self._in_viewport(screen_x, screen_y, 32):
                self._draw_guide(screen, screen_x, screen_y, guide, time)

    def _in_viewport(self, screen_x, screen_y, margin):
        return (
            -margin <= screen_x <= SCREEN_WIDTH + margin
            and -margin <= screen_y <= SCREEN_HEIGHT + margin
        )

    def _draw_prey(self, screen, screen_x, screen_y, prey):
        pygame.draw.circle(screen, prey.color, (int(screen_x), int(screen_y)), prey.radius)
        pygame.draw.circle(screen, (60, 68, 56), (int(screen_x), int(screen_y)), prey.radius, 2)

        if prey.kind == "mouse":
            pygame.draw.circle(screen, (244, 244, 244), (int(screen_x) - 5, int(screen_y) - 8), 3)
            pygame.draw.circle(screen, (244, 244, 244), (int(screen_x) + 5, int(screen_y) - 8), 3)
        elif prey.kind == "rabbit":
            pygame.draw.line(screen, (250, 240, 224), (screen_x - 4, screen_y - 8), (screen_x - 6, screen_y - 16), 3)
            pygame.draw.line(screen, (250, 240, 224), (screen_x + 4, screen_y - 8), (screen_x + 6, screen_y - 16), 3)
        elif prey.kind == "pheasant":
            pygame.draw.polygon(
                screen,
                (232, 176, 74),
                [(screen_x + prey.radius, screen_y), (screen_x + prey.radius + 8, screen_y - 4), (screen_x + prey.radius + 8, screen_y + 4)],
            )
        elif prey.kind == "deer":
            pygame.draw.line(screen, (208, 184, 140), (screen_x - 4, screen_y - 10), (screen_x - 10, screen_y - 18), 2)
            pygame.draw.line(screen, (208, 184, 140), (screen_x + 4, screen_y - 10), (screen_x + 10, screen_y - 18), 2)

    def _draw_obstacle(self, screen, screen_x, screen_y, obstacle):
        rect = pygame.Rect(
            int(screen_x),
            int(screen_y),
            obstacle.width_tiles * WORLD_TILE_SIZE,
            obstacle.height_tiles * WORLD_TILE_SIZE,
        )
        inner = rect.inflate(-6, -6)
        pygame.draw.rect(screen, (92, 88, 82), inner, border_radius=16)
        pygame.draw.rect(screen, (58, 54, 48), inner, width=3, border_radius=16)
        pebble_points = [
            (inner.x + inner.width // 4, inner.y + inner.height // 3),
            (inner.centerx, inner.centery),
            (inner.right - inner.width // 4, inner.bottom - inner.height // 3),
        ]
        for pebble_x, pebble_y in pebble_points:
            pygame.draw.circle(screen, (132, 126, 118), (pebble_x, pebble_y), 5)

    def _draw_beast(self, screen, screen_x, screen_y, beast):
        rect = pygame.Rect(
            int(screen_x),
            int(screen_y),
            BEAST_TILE_FOOTPRINT * WORLD_TILE_SIZE,
            BEAST_TILE_FOOTPRINT * WORLD_TILE_SIZE,
        )

        shadow = pygame.Surface((rect.width + 18, rect.height + 18), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 72), shadow.get_rect())
        screen.blit(shadow, (rect.x - 4, rect.y + 12))

        base_rect = rect.inflate(-6, -6)
        pygame.draw.rect(screen, (*beast.color, 66), base_rect, border_radius=18)
        pygame.draw.rect(screen, (56, 38, 30), base_rect, width=3, border_radius=18)

        for step in range(1, BEAST_TILE_FOOTPRINT):
            offset = step * WORLD_TILE_SIZE
            pygame.draw.line(screen, (84, 62, 44), (rect.x + offset, rect.y + 8), (rect.x + offset, rect.bottom - 8), 1)
            pygame.draw.line(screen, (84, 62, 44), (rect.x + 8, rect.y + offset), (rect.right - 8, rect.y + offset), 1)

        sprite_rect = rect.inflate(-16, -16)
        sprite = self.sprite_bank.get(
            beast.sprite_path,
            (sprite_rect.width, sprite_rect.height),
            beast.color,
            padding_ratio=0.06,
        )
        screen.blit(sprite, sprite_rect.topleft)

    def _draw_skill_card(self, screen, screen_x, screen_y, card, time):
        tile_rect = pygame.Rect(int(screen_x), int(screen_y), WORLD_TILE_SIZE, WORLD_TILE_SIZE)
        center = tile_rect.center

        pulse = 0.75 + 0.25 * math.sin(time * 4.8)
        glow_radius = int(22 * pulse)
        glow_size = glow_radius * 2
        glow = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*card.color, 78), (glow_radius, glow_radius), glow_radius)
        screen.blit(glow, (center[0] - glow_radius, center[1] - glow_radius))

        outer_radius = WORLD_TILE_SIZE // 2 - 6
        inner_radius = max(outer_radius - 5, 10)
        pygame.draw.circle(screen, (20, 30, 22), center, outer_radius + 2)
        pygame.draw.circle(screen, (*card.color, 46), center, outer_radius)
        pygame.draw.circle(screen, card.ring_color, center, outer_radius, 4)
        pygame.draw.circle(screen, (34, 48, 34), center, inner_radius)

        icon_size = max(WORLD_TILE_SIZE - 20, 20)
        icon_rect = pygame.Rect(0, 0, icon_size, icon_size)
        icon_rect.center = center
        icon = self.sprite_bank.get(
            card.sprite_path,
            icon_rect.size,
            card.color,
            padding_ratio=0.12,
        )
        screen.blit(icon, icon_rect.topleft)

    def _draw_guide(self, screen, screen_x, screen_y, guide, time):
        pulse = (math.sin(time * 4.0) + 1.0) / 2.0
        glow_radius = 8 + int(pulse * 8)
        glow_alpha = int(74 + pulse * 120)

        glow = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            glow,
            (180, 230, 255, glow_alpha),
            (glow_radius, glow_radius),
            glow_radius,
        )
        screen.blit(glow, (screen_x - glow_radius, screen_y - glow_radius))

        pygame.draw.circle(screen, (232, 244, 255), (int(screen_x), int(screen_y)), 3)

        angle = guide.direction_angle
        tip_x = screen_x + math.cos(angle) * GUIDE_ARROW_LENGTH
        tip_y = screen_y + math.sin(angle) * GUIDE_ARROW_LENGTH
        tail_x = screen_x - math.cos(angle) * (GUIDE_ARROW_LENGTH * 0.5)
        tail_y = screen_y - math.sin(angle) * (GUIDE_ARROW_LENGTH * 0.5)
        left_angle = angle + math.pi * 0.75
        right_angle = angle - math.pi * 0.75
        left_x = screen_x + math.cos(left_angle) * (GUIDE_ARROW_LENGTH * 0.42)
        left_y = screen_y + math.sin(left_angle) * (GUIDE_ARROW_LENGTH * 0.42)
        right_x = screen_x + math.cos(right_angle) * (GUIDE_ARROW_LENGTH * 0.42)
        right_y = screen_y + math.sin(right_angle) * (GUIDE_ARROW_LENGTH * 0.42)

        arrow_color = (186, 224, 255) if guide.target_type == "prey" else CLICK_EFFECT_ACCENT
        pygame.draw.line(screen, arrow_color, (tail_x, tail_y), (tip_x, tip_y), 2)
        pygame.draw.line(screen, arrow_color, (screen_x, screen_y), (left_x, left_y), 2)
        pygame.draw.line(screen, arrow_color, (screen_x, screen_y), (right_x, right_y), 2)

    def get_colliding_prey(self, head_x, head_y):
        for prey in list(self.prey_list):
            if math.hypot(head_x - prey.x, head_y - prey.y) < COLLISION_PREY:
                return prey
        return None

    def get_colliding_skill_card(self, head_x, head_y):
        for card in list(self.skill_cards):
            if math.hypot(head_x - card.x, head_y - card.y) < SKILL_PICKUP_RADIUS:
                return card
        return None

    def get_colliding_beast(self, head_x, head_y):
        point = (head_x, head_y)
        for beast in self.beast_list:
            if beast.rect.inflate(SNAKE_HEAD_RADIUS * 2, SNAKE_HEAD_RADIUS * 2).collidepoint(point):
                return beast
        return None

    def get_colliding_obstacle(self, head_x, head_y):
        point = (head_x, head_y)
        for obstacle in self.obstacle_list:
            if obstacle.rect.inflate(SNAKE_HEAD_RADIUS * 2, SNAKE_HEAD_RADIUS * 2).collidepoint(point):
                return obstacle
        return None

    def get_colliding_guide(self, head_x, head_y):
        for guide in list(self.guide_list):
            if not guide.visible:
                continue
            if math.hypot(head_x - guide.x, head_y - guide.y) < GUIDE_DISCOVER_RADIUS:
                return guide
        return None

    def remove_prey(self, prey):
        if prey in self.prey_list:
            self.prey_list.remove(prey)

    def remove_skill_card(self, card):
        if card in self.skill_cards:
            self.skill_cards.remove(card)

    def remove_obstacle(self, obstacle):
        if obstacle in self.obstacle_list:
            self.obstacle_list.remove(obstacle)

    def remove_guide(self, guide):
        if guide in self.guide_list:
            self._refresh_guide(guide)

    def clear_beasts(self, beasts_to_remove):
        self.beast_list = [beast for beast in self.beast_list if beast not in beasts_to_remove]

    def visible_prey(self, point_visible_predicate):
        return [prey for prey in self.prey_list if point_visible_predicate((prey.x, prey.y))]

    def visible_beasts(self, rect_visible_predicate):
        return [beast for beast in self.beast_list if rect_visible_predicate(beast.rect)]

    def reset(self, snake):
        self._set_snakes(snake)
        self.prey_list.clear()
        self.beast_list.clear()
        self.guide_list.clear()
        self.skill_cards.clear()
        self.obstacle_list.clear()
        self._prey_timer = 0.0
        self._skill_timer = 0.0
        self._obstacle_timer = 0.0
        self._spawn_initial()
