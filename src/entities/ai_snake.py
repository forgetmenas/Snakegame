"""AI-controlled snake for duel mode."""

from __future__ import annotations

import math
import random

from src.core.settings import (
    AI_SNAKE_BODY_COLOR_BRIGHT,
    AI_SNAKE_BODY_COLOR_DARK,
    AI_SNAKE_HEAD_COLOR,
    AI_TARGET_REFRESH_INTERVAL,
    BEAST_TILE_FOOTPRINT,
    DUEL_AI_SPAWN,
    DUEL_AI_SPEED_FACTOR,
    MAP_HEIGHT,
    MAP_WIDTH,
    SNAKE_BASE_SPEED,
    SNAKE_HEAD_RADIUS,
    SNAKE_MIN_SPEED_FACTOR,
    SNAKE_SPEED_BOOST_MULTIPLIER,
    WORLD_TILE_SIZE,
)
from src.core.settings import HUNGER_MAX
from src.entities.snake import Snake


class AISnake(Snake):
    """Snake driven by simple AI: seek prey, avoid beasts, attack other snakes."""

    def __init__(
        self,
        spawn_point=None,
        body_color_bright=AI_SNAKE_BODY_COLOR_BRIGHT,
        body_color_dark=AI_SNAKE_BODY_COLOR_DARK,
        head_color=AI_SNAKE_HEAD_COLOR,
    ):
        super().__init__(
            spawn_point=spawn_point or DUEL_AI_SPAWN,
            body_color_bright=body_color_bright,
            body_color_dark=body_color_dark,
            head_color=head_color,
        )
        self._target_timer = 0.0
        self._wander_target = None

    @property
    def current_speed(self):
        hunger_ratio = self.hunger / HUNGER_MAX
        speed_factor = 1.0 - (1.0 - SNAKE_MIN_SPEED_FACTOR) * hunger_ratio
        speed = SNAKE_BASE_SPEED * speed_factor * DUEL_AI_SPEED_FACTOR
        if self.speed_boost_timer > 0:
            speed *= SNAKE_SPEED_BOOST_MULTIPLIER
        return speed

    def ai_update(self, dt, world, target_snakes):
        """Update AI. target_snakes can be a single snake or a list of snakes to attack."""
        if isinstance(target_snakes, (list, tuple)):
            enemies = [s for s in target_snakes if s is not self]
        else:
            enemies = [target_snakes]
        self._target_timer += dt
        if self._target_timer >= AI_TARGET_REFRESH_INTERVAL:
            self._target_timer = 0.0
            self._pick_target(world, enemies)

        if self._wander_target is not None:
            self.set_target(*self._wander_target)

        self.update(dt)

    def _pick_target(self, world, enemies):
        head_x, head_y = self.head_pos

        danger_zones = []
        for beast in world.beast_list:
            danger_zones.append((beast.x, beast.y, BEAST_TILE_FOOTPRINT * WORLD_TILE_SIZE))
        for obstacle in world.obstacle_list:
            r = obstacle.rect
            danger_zones.append((r.centerx, r.centery, max(r.width, r.height)))

        alive_enemies = [s for s in enemies if s.alive and s.length > 1]
        if alive_enemies and random.random() < 0.6:
            nearest_enemy = min(
                alive_enemies,
                key=lambda s: math.hypot(s.head_pos[0] - head_x, s.head_pos[1] - head_y),
            )
            enemy_dist = math.hypot(
                nearest_enemy.head_pos[0] - head_x,
                nearest_enemy.head_pos[1] - head_y,
            )
            if enemy_dist < 1000:
                target_idx = min(2, len(nearest_enemy.segments) - 1)
                seg = nearest_enemy.segments[target_idx]
                self._wander_target = (seg[0], seg[1])
                return

        best_prey = None
        best_dist = float("inf")
        for prey in world.prey_list:
            d = math.hypot(prey.x - head_x, prey.y - head_y)
            if d < best_dist:
                safe = True
                for dx, dy, radius in danger_zones:
                    if math.hypot(prey.x - dx, prey.y - dy) < radius + 60:
                        safe = False
                        break
                if safe:
                    best_dist = d
                    best_prey = prey

        if best_prey is not None and best_dist < 1200:
            self._wander_target = (best_prey.x, best_prey.y)
            return

        for _ in range(10):
            tx = random.uniform(
                max(SNAKE_HEAD_RADIUS, head_x - 600),
                min(MAP_WIDTH - SNAKE_HEAD_RADIUS, head_x + 600),
            )
            ty = random.uniform(
                max(SNAKE_HEAD_RADIUS, head_y - 600),
                min(MAP_HEIGHT - SNAKE_HEAD_RADIUS, head_y + 600),
            )
            safe = True
            for dx, dy, radius in danger_zones:
                if math.hypot(tx - dx, ty - dy) < radius + 80:
                    safe = False
                    break
            if safe:
                self._wander_target = (tx, ty)
                return

        self._wander_target = (
            random.uniform(SNAKE_HEAD_RADIUS, MAP_WIDTH - SNAKE_HEAD_RADIUS),
            random.uniform(SNAKE_HEAD_RADIUS, MAP_HEIGHT - SNAKE_HEAD_RADIUS),
        )
