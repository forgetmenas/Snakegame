"""蛇模块 - 连续移动、平滑转向、饥饿系统、基于位置历史的身体跟随
变更：
- update 增加 is_moving 参数，只有移动时才更新头部和身体
- 饥饿值始终随时间增长，不受移动状态影响
- 停止时身体保持静止（不添加位置历史，无惯性滑动）
"""

import math
from settings import *


class Snake:
    """连续移动的蛇，使用位置历史实现自然的身体跟随"""

    def __init__(self):
        # 身体段：segments[0] 是头部，每个段为 [x, y] 浮点数
        self.segments = []
        start_x = INITIAL_WORLD_X
        start_y = INITIAL_WORLD_Y
        for i in range(SNAKE_INITIAL_LENGTH):
            self.segments.append([
                start_x - i * SNAKE_SEGMENT_SPACING,
                float(start_y)
            ])

        self.angle = 0.0          # 当前朝向 (弧度, 0=右)
        self.hunger = 0.0         # 饥饿值 0~100
        self.alive = True         # 是否存活
        self.moving = False       # 当前是否在移动（由 update 的 is_moving 参数同步）

        # 位置历史：[[x, y, cumulative_distance], ...]
        # 身体段通过回溯历史找到对应位置
        self.position_history = [[start_x, start_y, 0.0]]

    @property
    def head_pos(self):
        """蛇头世界坐标 (x, y)"""
        return (self.segments[0][0], self.segments[0][1])

    @property
    def body_segments(self):
        """所有身体段的世界坐标列表"""
        return self.segments

    @property
    def length(self):
        """身体段数量"""
        return len(self.segments)

    def update(self, dt, target_angle, is_moving):
        """每帧更新蛇的状态。
        dt: 帧间隔 (秒)
        target_angle: 目标方向角 (弧度)
        is_moving: bool — 本帧是否移动（按住空格键时由 InputHandler 传入）
        """
        if not self.alive:
            return

        self.moving = is_moving   # 同步移动状态（供 HUD 等外部读取）

        # --- 饥饿值始终更新，不受移动状态影响 ---
        self.hunger += HUNGER_RATE * dt
        if self.hunger >= HUNGER_MAX:
            self._apply_hunger_penalty()

        # --- 移动逻辑：只有 is_moving 为 True 时才更新位置 ---
        if not is_moving:
            return  # 不添加位置历史，身体段保持静止，无惯性滑动

        # --- 1. 根据饥饿值计算实际移动速度 ---
        hunger_ratio = self.hunger / HUNGER_MAX
        speed_factor = 1.0 - (1.0 - SNAKE_MIN_SPEED_FACTOR) * hunger_ratio
        current_speed = SNAKE_BASE_SPEED * speed_factor

        # --- 2. 平滑转向目标角度 ---
        angle_diff = target_angle - self.angle
        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi

        max_turn = SNAKE_TURN_SPEED * dt
        if abs(angle_diff) <= max_turn:
            self.angle = target_angle
        else:
            self.angle += max_turn * (1 if angle_diff > 0 else -1)

        while self.angle > math.pi:
            self.angle -= 2 * math.pi
        while self.angle < -math.pi:
            self.angle += 2 * math.pi

        # --- 3. 移动头部 ---
        dx = math.cos(self.angle) * current_speed * dt
        dy = math.sin(self.angle) * current_speed * dt
        new_hx = self.segments[0][0] + dx
        new_hy = self.segments[0][1] + dy

        margin = SNAKE_HEAD_RADIUS
        new_hx = max(margin, min(MAP_WIDTH - margin, new_hx))
        new_hy = max(margin, min(MAP_HEIGHT - margin, new_hy))

        dist_moved = math.sqrt(dx ** 2 + dy ** 2)
        self.segments[0][0] = new_hx
        self.segments[0][1] = new_hy

        # --- 4. 记录位置历史 ---
        new_cumulative = self.position_history[-1][2] + dist_moved
        self.position_history.append([new_hx, new_hy, new_cumulative])

        max_needed = len(self.segments) * SNAKE_SEGMENT_SPACING + 200
        while (len(self.position_history) > 2 and
               (new_cumulative - self.position_history[0][2]) > max_needed):
            self.position_history.pop(0)

        # --- 5. 身体段跟随（回溯位置历史） ---
        for i in range(1, len(self.segments)):
            target_dist = new_cumulative - i * SNAKE_SEGMENT_SPACING
            if target_dist <= 0:
                continue
            pos = self._sample_history(target_dist)
            if pos is not None:
                self.segments[i][0] = pos[0]
                self.segments[i][1] = pos[1]

    def _sample_history(self, target_dist):
        """在位置历史中线性插值查找指定累积距离处的坐标"""
        if len(self.position_history) < 2:
            return None

        for j in range(len(self.position_history) - 1):
            d0 = self.position_history[j][2]
            d1 = self.position_history[j + 1][2]
            if d0 <= target_dist <= d1:
                if d1 - d0 < 0.001:
                    return (self.position_history[j][0], self.position_history[j][1])
                t = (target_dist - d0) / (d1 - d0)
                x = self.position_history[j][0] + (self.position_history[j+1][0] - self.position_history[j][0]) * t
                y = self.position_history[j][1] + (self.position_history[j+1][1] - self.position_history[j][1]) * t
                return (x, y)

        return None

    def _apply_hunger_penalty(self):
        """饥饿值满：长度减1，饥饿值重置为50。长度为0则死亡。"""
        if len(self.segments) > 1:
            self.segments.pop()
        else:
            self.alive = False
        self.hunger = HUNGER_PENALTY_RESET

    def reset(self):
        """重置蛇到初始状态（用于重新开始游戏）"""
        self.segments.clear()
        start_x = INITIAL_WORLD_X
        start_y = INITIAL_WORLD_Y
        for i in range(SNAKE_INITIAL_LENGTH):
            self.segments.append([
                start_x - i * SNAKE_SEGMENT_SPACING,
                float(start_y)
            ])
        self.angle = 0.0
        self.hunger = 0.0
        self.alive = True
        self.moving = False
        self.position_history = [[start_x, start_y, 0.0]]

    def grow(self, amount=1):
        """增加身体段数"""
        for _ in range(amount):
            last = self.segments[-1]
            if len(self.segments) > 1:
                prev = self.segments[-2]
                dx = last[0] - prev[0]
                dy = last[1] - prev[1]
            else:
                dx, dy = -SNAKE_SEGMENT_SPACING, 0
            dist = math.sqrt(dx ** 2 + dy ** 2)
            if dist < 1:
                dx, dy = -SNAKE_SEGMENT_SPACING, 0
                dist = SNAKE_SEGMENT_SPACING
            new_x = last[0] + (dx / dist) * SNAKE_SEGMENT_SPACING
            new_y = last[1] + (dy / dist) * SNAKE_SEGMENT_SPACING
            self.segments.append([new_x, new_y])
