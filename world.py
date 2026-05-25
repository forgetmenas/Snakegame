"""
实体管理系统 - Prey/Beast/Guide + World 管理器
完整实体生命周期：生成、刷新、指引方向、绘制
"""

import math
import random
import pygame
from settings import *


# =========================================================================
# 实体类
# =========================================================================

class Prey:
    """猎物实体"""
    __slots__ = ('x', 'y', 'type_idx', 'type_name', 'length_bonus', 'color', 'radius')

    def __init__(self, x, y, type_idx):
        self.x = x
        self.y = y
        self.type_idx = type_idx
        name, weight, bonus, color, radius = PREY_TYPES[type_idx]
        self.type_name = name
        self.length_bonus = bonus
        self.color = color
        self.radius = radius


class Beast:
    """野兽实体"""
    __slots__ = ('x', 'y', 'type_idx', 'type_name', 'color', 'radius')

    def __init__(self, x, y, type_idx):
        self.x = x
        self.y = y
        self.type_idx = type_idx
        name, color, radius = BEAST_TYPES[type_idx]
        self.type_name = name
        self.color = color
        self.radius = radius


class Guide:
    """指引实体 - 指向最近的目标实体"""
    __slots__ = ('x', 'y', 'target_type', 'direction_angle', 'lifetime', 'visible')

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.target_type = random.choice(["prey", "beast"])
        self.direction_angle = 0.0
        self.lifetime = GUIDE_LIFETIME
        self.visible = True


# =========================================================================
# 权重采样工具
# =========================================================================

def _weighted_choice(weighted_items):
    """从 [(item, weight), ...] 列表中按权重随机选择一个 item"""
    total = sum(w for _, w in weighted_items)
    r = random.uniform(0, total)
    cumulative = 0
    for item, w in weighted_items:
        cumulative += w
        if r <= cumulative:
            return item
    return weighted_items[-1][0]


# =========================================================================
# World 管理器
# =========================================================================

class World:
    """管理所有实体：猎物、野兽、指引"""

    def __init__(self, snake_ref):
        self.snake = snake_ref
        self.prey_list = []
        self.beast_list = []
        self.guide_list = []

        self._prey_timer = 0.0
        self._spawn_initial()

    # ------------------------------------------------------------------
    # 初始生成
    # ------------------------------------------------------------------

    def _spawn_initial(self):
        """初始生成所有实体，均避开蛇头"""
        hx, hy = self.snake.head_pos

        for _ in range(INITIAL_BEAST_COUNT):
            pos = self._random_position(hx, hy, SPAWN_EXCLUSION_RADIUS)
            type_idx = random.randrange(len(BEAST_TYPES))
            self.beast_list.append(Beast(pos[0], pos[1], type_idx))

        for _ in range(GUIDE_COUNT):
            pos = self._random_position(hx, hy, SPAWN_EXCLUSION_RADIUS)
            self.guide_list.append(Guide(pos[0], pos[1]))

        self._refresh_prey(self.snake.length)

    # ------------------------------------------------------------------
    # 随机位置
    # ------------------------------------------------------------------

    def _random_position(self, exclude_x, exclude_y, exclude_radius):
        """在地图内随机生成位置，避开排除区域"""
        margin = 50
        for _ in range(80):
            x = random.uniform(margin, MAP_WIDTH - margin)
            y = random.uniform(margin, MAP_HEIGHT - margin)
            dist = math.sqrt((x - exclude_x) ** 2 + (y - exclude_y) ** 2)
            if dist > exclude_radius:
                return [x, y]
        # 回退
        return [random.uniform(0, MAP_WIDTH), random.uniform(0, MAP_HEIGHT)]

    # ------------------------------------------------------------------
    # 猎物刷新
    # ------------------------------------------------------------------

    def _target_prey_count(self):
        """刷新公式: max(1, ceil(PREY_BASE_COUNT + 0.0015*MAP_AREA + 0.15*length - beast_count))"""
        raw = (PREY_BASE_COUNT + 0.0015 * MAP_AREA +
               0.15 * self.snake.length - len(self.beast_list))
        target = max(1, math.ceil(raw))
        return min(target, PREY_MAX_COUNT)

    def _refresh_prey(self, snake_length):
        """补充猎物到目标数量"""
        target = self._target_prey_count()
        current = len(self.prey_list)
        to_spawn = target - current
        if to_spawn <= 0:
            return

        hx, hy = self.snake.head_pos
        # 构建权重列表: [(type_idx, weight), ...]
        weights = [(i, PREY_TYPES[i][1]) for i in range(len(PREY_TYPES))]

        for _ in range(to_spawn):
            pos = self._random_position(hx, hy, SPAWN_EXCLUSION_RADIUS)
            type_idx = _weighted_choice(weights)
            self.prey_list.append(Prey(pos[0], pos[1], type_idx))

    # ------------------------------------------------------------------
    # 野兽
    # ------------------------------------------------------------------

    def add_beast(self):
        """蛇捕获猎物时，在地图上新增一只野兽（避开蛇头）"""
        hx, hy = self.snake.head_pos
        pos = self._random_position(hx, hy, SPAWN_EXCLUSION_RADIUS)
        type_idx = random.randrange(len(BEAST_TYPES))
        self.beast_list.append(Beast(pos[0], pos[1], type_idx))

    # ------------------------------------------------------------------
    # 指引管理
    # ------------------------------------------------------------------

    def _update_guides(self):
        """更新所有指引的方向和生命周期"""
        for guide in self.guide_list:
            guide.lifetime -= 1.0 / FPS  # 近似每帧扣除

            # 查找最近目标实体
            if guide.target_type == "prey":
                target_list = self.prey_list
            else:
                target_list = self.beast_list

            if not target_list:
                guide.visible = False
                continue

            # 找最近的
            nearest = None
            nearest_dist = float('inf')
            for entity in target_list:
                d = math.sqrt((entity.x - guide.x) ** 2 + (entity.y - guide.y) ** 2)
                if d < nearest_dist:
                    nearest_dist = d
                    nearest = entity

            if nearest is not None:
                guide.direction_angle = math.atan2(
                    nearest.y - guide.y, nearest.x - guide.x)
                guide.visible = True

    def _refresh_guide(self, guide):
        """将一个指引重新生成到随机位置（保持 target_type 不变）"""
        hx, hy = self.snake.head_pos
        pos = self._random_position(hx, hy, SPAWN_EXCLUSION_RADIUS)
        guide.x, guide.y = pos[0], pos[1]
        guide.lifetime = GUIDE_LIFETIME
        guide.target_type = random.choice(["prey", "beast"])

    # ------------------------------------------------------------------
    # 每帧更新
    # ------------------------------------------------------------------

    def update(self, dt, snake):
        """每帧更新"""
        # 猎物定时刷新
        self._prey_timer += dt
        if self._prey_timer >= PREY_REFRESH_INTERVAL:
            self._prey_timer -= PREY_REFRESH_INTERVAL
            self._refresh_prey(snake.length)

        # 指引：移除过期的并刷新
        expired = [g for g in self.guide_list if g.lifetime <= 0]
        for g in expired:
            self._refresh_guide(g)

        self._update_guides()

    # ------------------------------------------------------------------
    # 绘制（仅绘制镜头内的实体）
    # ------------------------------------------------------------------

    def draw(self, screen, camera, time):
        """绘制所有在镜头内的实体。
        time: 游戏运行时间（秒），用于动画
        """
        for prey in self.prey_list:
            sx, sy = camera.world_to_screen(prey.x, prey.y)
            if not self._in_viewport(sx, sy, prey.radius):
                continue
            self._draw_prey(screen, sx, sy, prey)

        for beast in self.beast_list:
            sx, sy = camera.world_to_screen(beast.x, beast.y)
            if not self._in_viewport(sx, sy, beast.radius):
                continue
            self._draw_beast(screen, sx, sy, beast)

        for guide in self.guide_list:
            if not guide.visible:
                continue
            sx, sy = camera.world_to_screen(guide.x, guide.y)
            if not self._in_viewport(sx, sy, 30):
                continue
            self._draw_guide(screen, sx, sy, guide, time)

    def _in_viewport(self, sx, sy, margin):
        """判断屏幕坐标是否在可视范围内"""
        return (-margin <= sx <= SCREEN_WIDTH + margin and
                -margin <= sy <= SCREEN_HEIGHT + margin)

    # ------------------------------------------------------------------
    # 实体绘制
    # ------------------------------------------------------------------

    def _draw_prey(self, screen, sx, sy, prey):
        """绘制猎物：带颜色圆形 + 内部类型符号"""
        r = prey.radius
        # 主体圆形
        pygame.draw.circle(screen, prey.color, (sx, sy), r)
        # 边框
        pygame.draw.circle(screen, (60, 60, 60), (sx, sy), r, 1)

        # 内部符号（根据类型）
        name = prey.type_name
        if name == "老鼠":
            # 两个小圆点（耳朵）
            pygame.draw.circle(screen, (100, 100, 100), (sx - 2, sy - r + 1), 2)
            pygame.draw.circle(screen, (100, 100, 100), (sx + 2, sy - r + 1), 2)
        elif name == "兔子":
            # 两个长耳朵（小椭圆用线条近似）
            for ox in (-2, 2):
                pygame.draw.line(screen, prey.color,
                                 (sx + ox, sy - r), (sx + ox, sy - r - 4), 2)
        elif name == "野鸡":
            # 小三角形喙
            pts = [(sx + r, sy), (sx + r + 4, sy - 2), (sx + r + 4, sy + 2)]
            pygame.draw.polygon(screen, (200, 140, 40), pts)
        elif name == "鹿":
            # 两个小鹿角
            for ox, dir in [(-3, -1), (3, 1)]:
                pygame.draw.line(screen, (120, 80, 40),
                                 (sx + ox, sy - r),
                                 (sx + ox + dir * 3, sy - r - 5), 2)

    def _draw_beast(self, screen, sx, sy, beast):
        """绘制野兽：红色调圆形 + 爪痕"""
        r = beast.radius
        # 主体
        pygame.draw.circle(screen, beast.color, (sx, sy), r)
        pygame.draw.circle(screen, (80, 30, 20), (sx, sy), r, 2)
        # 爪痕（三条短线）
        for angle_offs in (-0.4, 0, 0.4):
            a = math.pi * 0.75 + angle_offs
            x1 = sx + math.cos(a) * (r - 2)
            y1 = sy - math.sin(a) * (r - 2)
            x2 = sx + math.cos(a) * (r + 5)
            y2 = sy - math.sin(a) * (r + 5)
            pygame.draw.line(screen, (40, 10, 5), (x1, y1), (x2, y2), 2)

    def _draw_guide(self, screen, sx, sy, guide, time):
        """绘制指引：脉冲光点 + 旋转箭头"""
        # 脉冲光点（alpha 随 sin 变化）
        pulse = (math.sin(time * 4.0) + 1) / 2  # 0..1
        glow_radius = 8 + int(pulse * 8)
        glow_alpha = int(60 + pulse * 120)

        glow_surf = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (180, 220, 255, glow_alpha),
                           (glow_radius, glow_radius), glow_radius)
        screen.blit(glow_surf, (sx - glow_radius, sy - glow_radius))

        # 中心白点
        pygame.draw.circle(screen, (220, 240, 255), (sx, sy), 3)

        # 箭头（指向目标方向）
        angle = guide.direction_angle
        arrow_len = GUIDE_ARROW_LENGTH
        # 箭头尖端
        tip_x = sx + math.cos(angle) * arrow_len
        tip_y = sy + math.sin(angle) * arrow_len
        # 箭头尾部
        tail_x = sx - math.cos(angle) * (arrow_len * 0.5)
        tail_y = sy - math.sin(angle) * (arrow_len * 0.5)
        # 箭头两侧
        left_angle = angle + math.pi * 0.75
        right_angle = angle - math.pi * 0.75
        left_x = sx + math.cos(left_angle) * (arrow_len * 0.4)
        left_y = sy + math.sin(left_angle) * (arrow_len * 0.4)
        right_x = sx + math.cos(right_angle) * (arrow_len * 0.4)
        right_y = sy + math.sin(right_angle) * (arrow_len * 0.4)

        arrow_color = (180, 220, 255) if guide.target_type == "prey" else (255, 180, 140)
        pygame.draw.line(screen, arrow_color, (tail_x, tail_y), (tip_x, tip_y), 2)
        pygame.draw.line(screen, arrow_color, (sx, sy), (left_x, left_y), 2)
        pygame.draw.line(screen, arrow_color, (sx, sy), (right_x, right_y), 2)

    # ------------------------------------------------------------------
    # 实体移除
    # ------------------------------------------------------------------

    def remove_prey(self, prey):
        if prey in self.prey_list:
            self.prey_list.remove(prey)

    def remove_guide(self, guide):
        """移除指引并立即刷新一个新的"""
        if guide in self.guide_list:
            self._refresh_guide(guide)

    def reset(self, snake):
        """重置所有实体（用于重新开始游戏）"""
        self.snake = snake
        self.prey_list.clear()
        self.beast_list.clear()
        self.guide_list.clear()
        self._prey_timer = 0.0
        self._spawn_initial()
