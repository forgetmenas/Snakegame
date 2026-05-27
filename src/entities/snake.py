"""Continuous snake model used by the adventure modes."""

from __future__ import annotations

import math

from src.core.settings import (
    HEAD_VISION_RADIUS,
    HUNGER_MAX,
    HUNGER_RATE,
    INITIAL_WORLD_X,
    INITIAL_WORLD_Y,
    MAP_HEIGHT,
    MAP_WIDTH,
    MAX_VISION_MULTIPLIER,
    MIN_VISION_MULTIPLIER,
    SNAKE_BASE_SPEED,
    SNAKE_BODY_COLOR_BRIGHT,
    SNAKE_BODY_COLOR_DARK,
    SNAKE_HEAD_RADIUS,
    SNAKE_HEAD_COLOR,
    SNAKE_INITIAL_LENGTH,
    SNAKE_MIN_SPEED_FACTOR,
    SNAKE_SEGMENT_SPACING,
    SNAKE_SPEED_BOOST_DURATION,
    SNAKE_SPEED_BOOST_MULTIPLIER,
    SNAKE_TARGET_REACHED_DISTANCE,
    SNAKE_TURN_SPEED,
    SNAKE_VISION_SURGE_DURATION,
    SNAKE_VISION_SURGE_MULTIPLIER,
    STARVATION_STEP_DISTANCE,
    VISION_GROWTH_PER_SEGMENT,
    VISION_PENALTY_PER_MISSING_SEGMENT,
)


class Snake:
    """A smooth snake that moves toward a clicked world target."""

    def __init__(
        self,
        spawn_point: tuple[float, float] | None = None,
        *,
        body_color_bright=SNAKE_BODY_COLOR_BRIGHT,
        body_color_dark=SNAKE_BODY_COLOR_DARK,
        head_color=SNAKE_HEAD_COLOR,
        max_vision=MAX_VISION_MULTIPLIER,
    ):
        self.spawn_point = spawn_point or (float(INITIAL_WORLD_X), float(INITIAL_WORLD_Y))
        self.body_color_bright = body_color_bright
        self.body_color_dark = body_color_dark
        self.head_color = head_color
        self.max_vision = max_vision
        self.segments = []
        self.position_history = []
        self.angle = 0.0
        self.hunger = 0.0
        self.alive = True
        self.moving = False
        self.target_point = None
        self.speed_boost_timer = 0.0
        self.vision_surge_timer = 0.0
        self.starvation_distance = 0.0
        self.damage_taken_this_frame = False
        self.starvation_damage_applied = False
        self.reset()

    @property
    def head_pos(self):
        return (self.segments[0][0], self.segments[0][1])

    @property
    def body_segments(self):
        return self.segments

    @property
    def length(self):
        return len(self.segments)

    @property
    def current_speed(self):
        hunger_ratio = self.hunger / HUNGER_MAX
        speed_factor = 1.0 - (1.0 - SNAKE_MIN_SPEED_FACTOR) * hunger_ratio
        speed = SNAKE_BASE_SPEED * speed_factor
        if self.speed_boost_timer > 0:
            speed *= SNAKE_SPEED_BOOST_MULTIPLIER
        return speed

    @property
    def vision_multiplier(self):
        if self.vision_surge_timer > 0:
            return max(self.growth_vision_multiplier, SNAKE_VISION_SURGE_MULTIPLIER)
        return self.growth_vision_multiplier

    @property
    def growth_vision_multiplier(self):
        if self.length >= SNAKE_INITIAL_LENGTH:
            extra_segments = self.length - SNAKE_INITIAL_LENGTH
            return min(self.max_vision, 1.0 + extra_segments * VISION_GROWTH_PER_SEGMENT)

        missing_segments = SNAKE_INITIAL_LENGTH - self.length
        penalty = missing_segments * VISION_PENALTY_PER_MISSING_SEGMENT
        return max(MIN_VISION_MULTIPLIER, 1.0 - penalty)

    @property
    def current_vision_radius(self):
        return int(HEAD_VISION_RADIUS * self.vision_multiplier)

    def reset(self):
        self.segments = []
        start_x, start_y = self.spawn_point
        for index in range(SNAKE_INITIAL_LENGTH):
            self.segments.append([
                start_x - index * SNAKE_SEGMENT_SPACING,
                start_y,
            ])

        self.position_history = [[start_x, start_y, 0.0]]
        self.angle = 0.0
        self.hunger = 0.0
        self.alive = True
        self.moving = False
        self.target_point = None
        self.speed_boost_timer = 0.0
        self.vision_surge_timer = 0.0
        self.starvation_distance = 0.0
        self.damage_taken_this_frame = False
        self.starvation_damage_applied = False

    def set_target(self, world_x, world_y):
        self.target_point = [
            max(SNAKE_HEAD_RADIUS, min(MAP_WIDTH - SNAKE_HEAD_RADIUS, world_x)),
            max(SNAKE_HEAD_RADIUS, min(MAP_HEIGHT - SNAKE_HEAD_RADIUS, world_y)),
        ]

    def clear_target(self):
        self.target_point = None
        self.moving = False

    def restore_satiety(self):
        self.hunger = 0.0
        self.starvation_distance = 0.0

    def apply_speed_boost(self, duration=SNAKE_SPEED_BOOST_DURATION):
        self.speed_boost_timer = max(self.speed_boost_timer, duration)

    def apply_vision_surge(self, duration=SNAKE_VISION_SURGE_DURATION):
        self.vision_surge_timer = max(self.vision_surge_timer, duration)

    def update(self, dt):
        self.damage_taken_this_frame = False
        self.starvation_damage_applied = False

        if not self.alive:
            return

        self.hunger = min(HUNGER_MAX, self.hunger + HUNGER_RATE * dt)

        if self.speed_boost_timer > 0:
            self.speed_boost_timer = max(0.0, self.speed_boost_timer - dt)
        if self.vision_surge_timer > 0:
            self.vision_surge_timer = max(0.0, self.vision_surge_timer - dt)

        if self.target_point is None:
            self.moving = False
            return

        head_x, head_y = self.head_pos
        target_x, target_y = self.target_point
        dx_to_target = target_x - head_x
        dy_to_target = target_y - head_y
        direct_distance = math.hypot(dx_to_target, dy_to_target)

        if direct_distance <= SNAKE_TARGET_REACHED_DISTANCE:
            self.clear_target()
            return

        desired_angle = math.atan2(dy_to_target, dx_to_target)
        self._turn_toward(desired_angle, dt)

        travel_distance = min(self.current_speed * dt, direct_distance)
        step_x = math.cos(self.angle) * travel_distance
        step_y = math.sin(self.angle) * travel_distance

        next_x = max(
            SNAKE_HEAD_RADIUS,
            min(MAP_WIDTH - SNAKE_HEAD_RADIUS, head_x + step_x),
        )
        next_y = max(
            SNAKE_HEAD_RADIUS,
            min(MAP_HEIGHT - SNAKE_HEAD_RADIUS, head_y + step_y),
        )

        actual_dx = next_x - head_x
        actual_dy = next_y - head_y
        actual_distance = math.hypot(actual_dx, actual_dy)

        if actual_distance <= 0.001:
            self.moving = False
            return

        self.moving = True
        self.segments[0][0] = next_x
        self.segments[0][1] = next_y

        new_cumulative = self.position_history[-1][2] + actual_distance
        self.position_history.append([next_x, next_y, new_cumulative])

        max_needed = len(self.segments) * SNAKE_SEGMENT_SPACING + 240
        while (
            len(self.position_history) > 2
            and (new_cumulative - self.position_history[0][2]) > max_needed
        ):
            self.position_history.pop(0)

        for index in range(1, len(self.segments)):
            target_dist = new_cumulative - index * SNAKE_SEGMENT_SPACING
            if target_dist <= 0:
                continue
            sample = self._sample_history(target_dist)
            if sample is not None:
                self.segments[index][0] = sample[0]
                self.segments[index][1] = sample[1]

        if self.hunger >= HUNGER_MAX and self.alive:
            self.starvation_distance += actual_distance
            while self.starvation_distance >= STARVATION_STEP_DISTANCE and self.alive:
                self.starvation_distance -= STARVATION_STEP_DISTANCE
                self.apply_damage(1, source="starvation", can_defeat=True)

    def _turn_toward(self, target_angle, dt):
        angle_diff = target_angle - self.angle
        while angle_diff > math.pi:
            angle_diff -= math.tau
        while angle_diff < -math.pi:
            angle_diff += math.tau

        max_turn = SNAKE_TURN_SPEED * dt
        if abs(angle_diff) <= max_turn:
            self.angle = target_angle
        else:
            self.angle += max_turn * (1 if angle_diff > 0 else -1)

        while self.angle > math.pi:
            self.angle -= math.tau
        while self.angle < -math.pi:
            self.angle += math.tau

    def _sample_history(self, target_dist):
        if len(self.position_history) < 2:
            return None

        for index in range(len(self.position_history) - 1):
            start = self.position_history[index]
            end = self.position_history[index + 1]
            if start[2] <= target_dist <= end[2]:
                span = end[2] - start[2]
                if span < 0.001:
                    return (start[0], start[1])
                ratio = (target_dist - start[2]) / span
                x = start[0] + (end[0] - start[0]) * ratio
                y = start[1] + (end[1] - start[1]) * ratio
                return (x, y)
        return None

    def _trim_history(self):
        if len(self.position_history) <= 2:
            return

        keep_history = max(len(self.segments), 1) * SNAKE_SEGMENT_SPACING + 240
        newest = self.position_history[-1][2]
        while (
            len(self.position_history) > 2
            and (newest - self.position_history[0][2]) > keep_history
        ):
            self.position_history.pop(0)

    def lose_segments(self, amount=1, *, can_defeat=False, source="damage"):
        return self.apply_damage(amount, source=source, can_defeat=can_defeat)

    def apply_damage(self, amount=1, *, source="damage", can_defeat=False):
        if amount <= 0 or not self.alive:
            return 0

        removed = 0
        for _ in range(amount):
            if len(self.segments) > 1:
                self.segments.pop()
                removed += 1
                continue
            if can_defeat:
                self.alive = False
                removed += 1
            break

        if removed > 0:
            self.damage_taken_this_frame = True
            self.starvation_damage_applied = source == "starvation"
            self._trim_history()
            if not self.alive:
                self.clear_target()

        return removed

    def trim_from_collision(self, collision_index):
        keep_count = max(1, collision_index)
        removed = max(0, len(self.segments) - keep_count)
        if removed <= 0:
            return 0

        self.segments = self.segments[:keep_count]
        self.damage_taken_this_frame = True
        self.starvation_damage_applied = False
        self._trim_history()
        return removed

    def grow(self, amount=1):
        for _ in range(amount):
            tail = self.segments[-1]
            if len(self.segments) > 1:
                prev = self.segments[-2]
                dx = tail[0] - prev[0]
                dy = tail[1] - prev[1]
            else:
                dx = -SNAKE_SEGMENT_SPACING
                dy = 0.0

            distance = math.hypot(dx, dy)
            if distance < 1.0:
                dx = -SNAKE_SEGMENT_SPACING
                dy = 0.0
                distance = SNAKE_SEGMENT_SPACING

            self.segments.append([
                tail[0] + (dx / distance) * SNAKE_SEGMENT_SPACING,
                tail[1] + (dy / distance) * SNAKE_SEGMENT_SPACING,
            ])
