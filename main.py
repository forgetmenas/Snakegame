"""
迷雾贪吃蛇 - 主入口
状态机: menu → playing → gameover → (menu | playing)
渲染顺序：背景 → 实体 → 蛇身光晕 → 蛇 → 迷雾叠加 → HUD
"""

import pygame
import sys
import math
import random

from settings import *
from camera import Camera
from snake import Snake
from fog import FogOfWar
from input_handler import InputHandler
from world import World
from audio import AudioManager


# =========================================================================
# 状态常量
# =========================================================================
STATE_MENU = "menu"
STATE_PLAYING = "playing"
STATE_GAMEOVER = "gameover"


# =========================================================================
# 预渲染纹理
# =========================================================================
_body_circle_cache = {}
_glow_circle_cache = {}
_grass_tile = None


def _make_gradient_circle(radius, center_color, edge_color):
    d = radius * 2
    surf = pygame.Surface((d, d), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    for i in range(radius, 0, -1):
        t = i / max(radius, 1)
        r = int(center_color[0] * (1 - t) + edge_color[0] * t)
        g = int(center_color[1] * (1 - t) + edge_color[1] * t)
        b = int(center_color[2] * (1 - t) + edge_color[2] * t)
        alpha = 255 if i > radius - 2 else int(255 * (i / max(radius - 1, 1)))
        alpha = max(0, min(255, alpha))
        pygame.draw.circle(surf, (r, g, b, alpha), (radius, radius), i)
    return surf


def _make_glow_circle(radius, color, alpha):
    d = radius * 2
    surf = pygame.Surface((d, d), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    for i in range(radius, 0, -1):
        a = alpha if i > radius - 3 else int(alpha * (i / max(radius - 1, 1)))
        a = max(0, min(255, a))
        pygame.draw.circle(surf, (*color, a), (radius, radius), i)
    return surf


def _get_body_circle(radius, color):
    key = (radius, color)
    if key not in _body_circle_cache:
        edge_r = int(color[0] * 0.6)
        edge_g = int(color[1] * 0.6)
        edge_b = int(color[2] * 0.6)
        _body_circle_cache[key] = _make_gradient_circle(
            radius, color, (edge_r, edge_g, edge_b))
    return _body_circle_cache[key]


def _get_glow_circle(radius, color):
    key = (radius, color, SNAKE_GLOW_ALPHA)
    if key not in _glow_circle_cache:
        _glow_circle_cache[key] = _make_glow_circle(
            radius + 4, color, SNAKE_GLOW_ALPHA)
    return _glow_circle_cache[key]


def _init_grass_tile():
    global _grass_tile
    size = GRASS_TEXTURE_SIZE
    _grass_tile = pygame.Surface((size, size))
    _grass_tile.fill(BG_COLOR)
    for y in range(size):
        for x in range(size):
            if random.random() < GRASS_DENSITY:
                shade = random.randint(0, 20)
                color = (GRASS_COLOR[0] + shade,
                         GRASS_COLOR[1] + shade,
                         GRASS_COLOR[2] + shade)
                _grass_tile.set_at((x, y), color)


# =========================================================================
# 绘制函数
# =========================================================================

def draw_background(screen, camera):
    global _grass_tile
    if _grass_tile is None:
        _init_grass_tile()
    ox, oy = camera.offset
    ts = GRASS_TEXTURE_SIZE
    tile_start_x = int(ox // ts) * ts
    tile_start_y = int(oy // ts) * ts
    for wx in range(tile_start_x - ts, int(ox + SCREEN_WIDTH) + ts, ts):
        for wy in range(tile_start_y - ts, int(oy + SCREEN_HEIGHT) + ts, ts):
            sx, sy = camera.world_to_screen(wx, wy)
            if -ts <= sx <= SCREEN_WIDTH and -ts <= sy <= SCREEN_HEIGHT:
                screen.blit(_grass_tile, (sx, sy))
    tl = camera.world_to_screen(0, 0)
    br = camera.world_to_screen(MAP_WIDTH, MAP_HEIGHT)
    border_rect = pygame.Rect(tl[0], tl[1], br[0] - tl[0], br[1] - tl[1])
    pygame.draw.rect(screen, (100, 100, 100), border_rect, 3)


def _lerp_color(c1, c2, t):
    return (int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t))


def draw_snake(screen, camera, snake):
    segs = snake.segments
    if not segs:
        return
    n = len(segs)
    # 光晕层
    for i, seg in enumerate(segs):
        sx, sy = camera.world_to_screen(seg[0], seg[1])
        t = i / max(n - 1, 1)
        radius = SNAKE_BODY_RADIUS_MAX - t * (SNAKE_BODY_RADIUS_MAX - SNAKE_BODY_RADIUS_MIN)
        radius = max(SNAKE_BODY_RADIUS_MIN, int(radius))
        body_color = _lerp_color(SNAKE_BODY_COLOR_BRIGHT, SNAKE_BODY_COLOR_DARK, t)
        glow = _get_glow_circle(radius, body_color)
        gs = glow.get_width()
        screen.blit(glow, (sx - gs // 2, sy - gs // 2))
    # 身体
    for i, seg in enumerate(segs):
        if i == 0:
            continue
        sx, sy = camera.world_to_screen(seg[0], seg[1])
        t = i / max(n - 1, 1)
        radius = SNAKE_BODY_RADIUS_MAX - t * (SNAKE_BODY_RADIUS_MAX - SNAKE_BODY_RADIUS_MIN)
        radius = max(SNAKE_BODY_RADIUS_MIN, int(radius))
        body_color = _lerp_color(SNAKE_BODY_COLOR_BRIGHT, SNAKE_BODY_COLOR_DARK, t)
        circle = _get_body_circle(radius, body_color)
        cs = circle.get_width()
        screen.blit(circle, (sx - cs // 2, sy - cs // 2))
    # 头部
    hx, hy = camera.world_to_screen(segs[0][0], segs[0][1])
    head_glow = _get_glow_circle(SNAKE_HEAD_RADIUS, SNAKE_HEAD_COLOR)
    gs = head_glow.get_width()
    screen.blit(head_glow, (hx - gs // 2, hy - gs // 2))
    head_circle = _get_body_circle(SNAKE_HEAD_RADIUS, SNAKE_HEAD_COLOR)
    cs = head_circle.get_width()
    screen.blit(head_circle, (hx - cs // 2, hy - cs // 2))
    end_x = hx + math.cos(snake.angle) * (SNAKE_HEAD_RADIUS + 6)
    end_y = hy + math.sin(snake.angle) * (SNAKE_HEAD_RADIUS + 6)
    pygame.draw.line(screen, (0, 0, 0), (hx, hy), (int(end_x), int(end_y)), 2)


def draw_satiety_bar(screen, x, y, satiety_pct):
    """绘制饱腹度进度条 (红→黄→绿)"""
    # 背景
    bar_rect = pygame.Rect(x, y, SATIETY_BAR_WIDTH, SATIETY_BAR_HEIGHT)
    pygame.draw.rect(screen, SATIETY_BAR_BG, bar_rect)
    # 填充
    fill_width = int(SATIETY_BAR_WIDTH * satiety_pct / 100)
    if fill_width > 0:
        if satiety_pct < 30:
            color = SATIETY_BAR_LOW
        elif satiety_pct < 60:
            color = SATIETY_BAR_MID
        else:
            color = SATIETY_BAR_HIGH
        fill_rect = pygame.Rect(x, y, fill_width, SATIETY_BAR_HEIGHT)
        pygame.draw.rect(screen, color, fill_rect)
    # 边框
    pygame.draw.rect(screen, (100, 100, 100), bar_rect, 1)


def draw_hud(screen, snake, font, max_length):
    """绘制 HUD：饱腹度进度条 + 百分比 + 长度 + 状态"""
    satiety = max(0, 100 - snake.hunger)

    # 半透明黑底
    hud_bg = pygame.Surface((340, 110), pygame.SRCALPHA)
    hud_bg.fill((0, 0, 0, 180))
    screen.blit(hud_bg, (10, 10))

    # 饱腹度进度条
    draw_satiety_bar(screen, 22, 40, satiety)
    satiety_text = font.render(f"饱腹度: {satiety:.0f}%", True, HUD_TEXT_COLOR)
    screen.blit(satiety_text, (22, 14))

    # 长度
    length_text = font.render(
        f"长度: {snake.length}  最大: {max_length}", True, HUD_TEXT_COLOR)
    screen.blit(length_text, (22, 62))

    # 状态
    if not snake.alive:
        status = "已死亡"
    elif not snake.moving:
        status = "右键设置方向, 按住空格移动"
    else:
        speed = SNAKE_BASE_SPEED * (1.0 - (1.0 - SNAKE_MIN_SPEED_FACTOR) * snake.hunger / HUNGER_MAX)
        status = f"移动中 | 速度: {speed:.0f} px/s"
    status_text = font.render(status, True, HUD_TEXT_COLOR)
    screen.blit(status_text, (22, 86))


def draw_text_centered(screen, font, text, color, y):
    """在屏幕水平居中位置绘制文本"""
    surf = font.render(text, True, color)
    x = (SCREEN_WIDTH - surf.get_width()) // 2
    screen.blit(surf, (x, y))


# =========================================================================
# 菜单界面
# =========================================================================

def draw_menu(screen, title_font, body_font):
    """绘制菜单界面"""
    screen.fill(MENU_BG_COLOR)

    draw_text_centered(screen, title_font, "迷雾贪吃蛇",
                       MENU_TITLE_COLOR, 200)
    draw_text_centered(screen, title_font, "Fog of War Snake",
                       MENU_TITLE_COLOR, 280)

    instructions = [
        "操作说明",
        "",
        "  鼠标右键  - 设置移动方向",
        "  按住空格  - 向设定方向移动",
        "  ESC      - 退出游戏",
        "",
        "蛇需要在迷雾中探索，寻找猎物以维持生命。",
        "饥饿值会随时间增长，越饿移动越慢。",
        "注意躲避野兽！跟随蓝色指引找到猎物。",
        "",
        "按 空格键 开始游戏",
    ]

    y = 400
    for line in instructions:
        if line.startswith("  ") or line == "":
            color = MENU_TEXT_COLOR
        elif line.endswith(":") or line.endswith("：") or line.endswith("说明"):
            color = MENU_TITLE_COLOR
        else:
            color = MENU_HINT_COLOR
        surf = body_font.render(line, True, color)
        x = (SCREEN_WIDTH - surf.get_width()) // 2
        screen.blit(surf, (x, y))
        y += 32

    # 闪烁提示
    return y


# =========================================================================
# 游戏结束界面
# =========================================================================

def draw_gameover(screen, title_font, body_font, max_length, snake):
    """绘制游戏结束界面（叠加在当前游戏画面上）"""
    # 半透明遮罩
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))

    draw_text_centered(screen, title_font, "游 戏 结 束",
                       GAMEOVER_TITLE_COLOR, 280)

    info_lines = [
        f"最终长度: {snake.length}    本轮最大: {max_length}",
        "",
        "按 R 键 - 重新开始",
        "按 M 键 - 返回菜单",
    ]
    y = 400
    for line in info_lines:
        color = GAMEOVER_TEXT_COLOR if line else MENU_HINT_COLOR
        surf = body_font.render(line, True, color)
        x = (SCREEN_WIDTH - surf.get_width()) // 2
        screen.blit(surf, (x, y))
        y += 36


# =========================================================================
# 游戏初始化
# =========================================================================

def init_game_objects():
    """创建/重置所有游戏对象，返回元组"""
    camera = Camera(MAP_WIDTH, MAP_HEIGHT, SCREEN_WIDTH, SCREEN_HEIGHT)
    snake = Snake()
    input_handler = InputHandler()
    fog = FogOfWar(SCREEN_WIDTH, SCREEN_HEIGHT, camera)
    world = World(snake)
    camera.reset()
    return camera, snake, input_handler, fog, world


# =========================================================================
# 碰撞检测
# =========================================================================

def check_collisions(snake, world, audio):
    """检测蛇头与所有实体的碰撞。
    返回: (ate_something, should_die)
    """
    hx, hy = snake.head_pos

    # 地图边界
    margin = SNAKE_HEAD_RADIUS
    if hx < margin or hx > MAP_WIDTH - margin or hy < margin or hy > MAP_HEIGHT - margin:
        return False, True

    # 猎物碰撞
    for prey in list(world.prey_list):
        dist = math.sqrt((hx - prey.x) ** 2 + (hy - prey.y) ** 2)
        if dist < COLLISION_PREY:
            snake.grow(prey.length_bonus)
            snake.hunger = 0
            world.remove_prey(prey)
            world.add_beast()
            audio.play_eat()
            return True, False

    # 野兽碰撞
    for beast in world.beast_list:
        dist = math.sqrt((hx - beast.x) ** 2 + (hy - beast.y) ** 2)
        if dist < COLLISION_BEAST:
            audio.play_death()
            return False, True

    # 指引发现
    for guide in list(world.guide_list):
        if not guide.visible:
            continue
        dist = math.sqrt((hx - guide.x) ** 2 + (hy - guide.y) ** 2)
        if dist < GUIDE_DISCOVER_RADIUS:
            world.remove_guide(guide)
            audio.play_guide()

    return False, False


# =========================================================================
# 主入口
# =========================================================================

def main():
    pygame.init()
    pygame.mixer.init(buffer=512)
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("迷雾贪吃蛇 - Fog of War Snake")
    clock = pygame.time.Clock()

    # 加载字体
    font_paths = [
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    title_font = None
    body_font = None
    for path in font_paths:
        try:
            title_font = pygame.font.Font(path, 72)
            body_font = pygame.font.Font(path, HUD_FONT_SIZE)
            break
        except (FileNotFoundError, OSError):
            continue
    if title_font is None:
        title_font = pygame.font.Font(None, 72)
        body_font = pygame.font.Font(None, HUD_FONT_SIZE)
    small_font = pygame.font.Font(None, 22)

    # 预渲染纹理
    _init_grass_tile()

    # 音效
    audio = AudioManager()

    # 状态机
    state = STATE_MENU
    camera = snake = input_handler = fog = world = None
    max_length = SNAKE_INITIAL_LENGTH
    game_time = 0.0

    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0
        if dt > 0.1:
            dt = 0.016

        events = pygame.event.get()

        # =============================================================
        # 菜单状态
        # =============================================================
        if state == STATE_MENU:
            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        # 开始游戏
                        camera, snake, input_handler, fog, world = init_game_objects()
                        max_length = SNAKE_INITIAL_LENGTH
                        game_time = 0.0
                        state = STATE_PLAYING

            draw_menu(screen, title_font, body_font)

        # =============================================================
        # 游戏状态
        # =============================================================
        elif state == STATE_PLAYING:
            # 输入
            is_moving = input_handler.handle_events(
                events, snake.head_pos[0], snake.head_pos[1], camera)
            if input_handler.quit:
                running = False

            # 更新
            snake.update(dt, input_handler.target_angle, is_moving)
            camera.update(snake.head_pos[0], snake.head_pos[1], dt)
            fog.update(snake.head_pos, snake.body_segments)
            world.update(dt, snake)
            game_time += dt

            # 碰撞检测
            _, should_die = check_collisions(snake, world, audio)
            if should_die:
                snake.alive = False

            # 蛇死亡检查
            if not snake.alive:
                state = STATE_GAMEOVER

            # 更新最大长度
            if snake.length > max_length:
                max_length = snake.length

            # 渲染
            draw_background(screen, camera)
            world.draw(screen, camera, game_time)
            draw_snake(screen, camera, snake)
            fog.apply(screen)
            draw_hud(screen, snake, body_font, max_length)

        # =============================================================
        # 游戏结束状态
        # =============================================================
        elif state == STATE_GAMEOVER:
            # 继续渲染最终画面
            draw_background(screen, camera)
            world.draw(screen, camera, game_time)
            draw_snake(screen, camera, snake)
            fog.apply(screen)
            draw_hud(screen, snake, body_font, max_length)
            draw_gameover(screen, title_font, body_font, max_length, snake)

            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_r:
                        # 重新开始
                        camera, snake, input_handler, fog, world = init_game_objects()
                        max_length = SNAKE_INITIAL_LENGTH
                        game_time = 0.0
                        state = STATE_PLAYING
                    elif event.key == pygame.K_m:
                        state = STATE_MENU

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
