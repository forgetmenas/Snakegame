"""Lightweight host/client networking for multiplayer beast mode."""

from __future__ import annotations

from dataclasses import dataclass, field
import colorsys
import json
import math
import selectors
import socket
import threading
import time
from typing import Any

import pygame

from src.core.settings import (
    DUEL_MAX_VISION_MULTIPLIER,
    DUEL_OBSTACLE_LIFETIME,
    DUEL_OBSTACLE_MAX_COUNT,
    DUEL_OBSTACLE_SPAWN_INTERVAL,
    DUEL_PREY_REFRESH_INTERVAL,
    DUEL_PREY_TARGET_COUNT,
    DUEL_RESPAWN_DURATION,
    DUEL_REVEAL_DURATION,
    DUEL_SKILL_REFRESH_INTERVAL,
    DUEL_SKILL_TARGET_COUNT,
    HEAD_VISION_RADIUS,
    HUD_HINT_COLOR,
    HUD_LEFT,
    HUD_PANEL_COLOR,
    HUD_TEXT_COLOR,
    HUD_TOP,
    HUD_WIDTH,
    INITIAL_WORLD_X,
    INITIAL_WORLD_Y,
    MAP_HEIGHT,
    MAP_WIDTH,
    MENU_BG_COLOR,
    MENU_CARD_BORDER,
    MENU_CARD_COLOR,
    MENU_HINT_COLOR,
    MENU_PANEL_COLOR,
    MENU_TEXT_COLOR,
    MENU_TITLE_COLOR,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SNAKE_BODY_RADIUS_MAX,
    SNAKE_BODY_RADIUS_MIN,
    SNAKE_HEAD_RADIUS,
    SKILL_TYPES,
    WORLD_TILE_SIZE,
)
from src.entities.snake import Snake
from src.entities.world import AdventureObstacle, Beast, Guide, Prey, SkillCard, World
from src.systems.camera import Camera
from src.systems.fog import FogOfWar


DEFAULT_MULTIPLAYER_PORT = 36123
CONNECT_TIMEOUT_SECONDS = 3.0
SNAPSHOT_INTERVAL = 1.0 / 12.0
NETWORK_LOOP_INTERVAL = 0.01
VIEWPORT_MARGIN = 220


def get_hostname_name() -> str:
    """Return the local machine hostname."""

    name = socket.gethostname().strip()
    return name or "unknown-host"


def get_local_ip_addresses() -> list[str]:
    """Best-effort local IPv4 address discovery for host instructions."""

    addresses: list[str] = []

    try:
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            udp_sock.connect(("8.8.8.8", 80))
            addresses.append(udp_sock.getsockname()[0])
        finally:
            udp_sock.close()
    except OSError:
        pass

    try:
        host_info = socket.gethostbyname_ex(socket.gethostname())
        addresses.extend(host_info[2])
    except OSError:
        pass

    deduped: list[str] = []
    for address in addresses:
        if not address or address.startswith("127.") or address in deduped:
            continue
        deduped.append(address)
    return deduped or ["127.0.0.1"]


def build_multiplayer_world_config(player_count: int) -> dict[str, float]:
    """Scale duel-mode world density proportionally to human player count."""

    scale = max(1.0, player_count / 4.0)
    return {
        "prey_target": max(160, int(round(DUEL_PREY_TARGET_COUNT * scale))),
        "prey_interval": max(0.12, DUEL_PREY_REFRESH_INTERVAL / scale),
        "skill_target": max(12, int(round(DUEL_SKILL_TARGET_COUNT * scale))),
        "skill_interval": max(0.75, DUEL_SKILL_REFRESH_INTERVAL / scale),
        "obstacle_max": DUEL_OBSTACLE_MAX_COUNT,
        "obstacle_lifetime": DUEL_OBSTACLE_LIFETIME,
        "obstacle_interval": DUEL_OBSTACLE_SPAWN_INTERVAL,
    }


def player_color_triplet(index: int) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    """Generate stable readable colors for arbitrary player counts."""

    hue = (0.17 + index * 0.19) % 1.0
    bright = colorsys.hsv_to_rgb(hue, 0.52, 0.95)
    dark = colorsys.hsv_to_rgb(hue, 0.72, 0.62)
    head = colorsys.hsv_to_rgb((hue + 0.04) % 1.0, 0.42, 1.0)
    return (
        tuple(int(channel * 255) for channel in bright),
        tuple(int(channel * 255) for channel in dark),
        tuple(int(channel * 255) for channel in head),
    )


def generate_spawn_points(player_count: int) -> list[tuple[float, float]]:
    """Spread snakes around the map center on a ring."""

    if player_count <= 1:
        return [(float(INITIAL_WORLD_X), float(INITIAL_WORLD_Y))]

    radius = 820
    points: list[tuple[float, float]] = []
    for index in range(player_count):
        angle = (math.tau * index / player_count) - math.pi / 2
        x = INITIAL_WORLD_X + math.cos(angle) * radius
        y = INITIAL_WORLD_Y + math.sin(angle) * radius
        x = max(SNAKE_HEAD_RADIUS, min(MAP_WIDTH - SNAKE_HEAD_RADIUS, x))
        y = max(SNAKE_HEAD_RADIUS, min(MAP_HEIGHT - SNAKE_HEAD_RADIUS, y))
        points.append((float(x), float(y)))
    return points


def _distance_point_to_rect(point: tuple[float, float], rect: pygame.Rect) -> float:
    closest_x = max(rect.left, min(point[0], rect.right))
    closest_y = max(rect.top, min(point[1], rect.bottom))
    return math.hypot(point[0] - closest_x, point[1] - closest_y)


def _point_visible_to_snake(point: tuple[float, float], snake: Snake) -> bool:
    return math.hypot(point[0] - snake.head_pos[0], point[1] - snake.head_pos[1]) <= snake.current_vision_radius


def _rect_visible_to_snake(rect: pygame.Rect, snake: Snake) -> bool:
    return _distance_point_to_rect(snake.head_pos, rect) <= snake.current_vision_radius


def _serialize_color(color: tuple[int, int, int]) -> list[int]:
    return [int(color[0]), int(color[1]), int(color[2])]


def _deserialize_color(color: list[int] | tuple[int, int, int]) -> tuple[int, int, int]:
    return (int(color[0]), int(color[1]), int(color[2]))


def _serialize_snake(snake: Snake | None) -> dict[str, Any] | None:
    if snake is None:
        return None
    return {
        "segments": [[round(seg[0], 1), round(seg[1], 1)] for seg in snake.segments],
        "angle": round(snake.angle, 4),
        "hunger": round(snake.hunger, 3),
        "alive": snake.alive,
        "moving": snake.moving,
        "speed_boost_timer": round(snake.speed_boost_timer, 3),
        "vision_surge_timer": round(snake.vision_surge_timer, 3),
        "max_vision": float(snake.max_vision),
    }


def _copy_snake_state(
    snake: Snake,
    payload: dict[str, Any] | None,
    colors: dict[str, list[int] | tuple[int, int, int]],
) -> None:
    snake.body_color_bright = _deserialize_color(colors["body_bright"])
    snake.body_color_dark = _deserialize_color(colors["body_dark"])
    snake.head_color = _deserialize_color(colors["head_color"])
    if payload is None:
        snake.segments = []
        snake.position_history = []
        snake.alive = False
        snake.moving = False
        snake.target_point = None
        return

    snake.segments = [[float(x), float(y)] for x, y in payload["segments"]]
    snake.position_history = []
    if snake.segments:
        start_x, start_y = snake.segments[0]
        snake.position_history.append([start_x, start_y, 0.0])
    snake.angle = float(payload["angle"])
    snake.hunger = float(payload["hunger"])
    snake.alive = bool(payload["alive"])
    snake.moving = bool(payload["moving"])
    snake.speed_boost_timer = float(payload["speed_boost_timer"])
    snake.vision_surge_timer = float(payload["vision_surge_timer"])
    snake.max_vision = float(payload["max_vision"])
    snake.target_point = None
    snake.damage_taken_this_frame = False
    snake.starvation_damage_applied = False


def _serialize_world_for_player(world: World, center_point: tuple[float, float]) -> dict[str, Any]:
    view_rect = pygame.Rect(
        int(center_point[0] - SCREEN_WIDTH / 2 - VIEWPORT_MARGIN),
        int(center_point[1] - SCREEN_HEIGHT / 2 - VIEWPORT_MARGIN),
        SCREEN_WIDTH + VIEWPORT_MARGIN * 2,
        SCREEN_HEIGHT + VIEWPORT_MARGIN * 2,
    )

    prey = [
        {
            "tile_x": item.tile_x,
            "tile_y": item.tile_y,
            "kind": item.kind,
            "length_bonus": item.length_bonus,
            "color": _serialize_color(item.color),
            "radius": item.radius,
        }
        for item in world.prey_list
        if view_rect.collidepoint(item.x, item.y)
    ]
    beasts = [
        {
            "tile_x": item.tile_x,
            "tile_y": item.tile_y,
            "kind": item.kind,
            "color": _serialize_color(item.color),
        }
        for item in world.beast_list
        if view_rect.colliderect(item.rect)
    ]
    skills = [
        {
            "tile_x": item.tile_x,
            "tile_y": item.tile_y,
            "kind": item.kind,
            "color": _serialize_color(item.color),
            "ring_color": _serialize_color(item.ring_color),
            "sprite_path": item.sprite_path,
        }
        for item in world.skill_cards
        if view_rect.colliderect(item.rect)
    ]
    guides = [
        {
            "x": round(item.x, 1),
            "y": round(item.y, 1),
            "target_type": item.target_type,
            "direction_angle": round(item.direction_angle, 4),
            "visible": item.visible,
        }
        for item in world.guide_list
        if item.visible and view_rect.collidepoint(item.x, item.y)
    ]
    obstacles = [
        {
            "tile_x": item.tile_x,
            "tile_y": item.tile_y,
            "width_tiles": item.width_tiles,
            "height_tiles": item.height_tiles,
            "lifetime": round(item.lifetime, 3),
        }
        for item in world.obstacle_list
        if view_rect.colliderect(item.rect)
    ]
    return {
        "prey": prey,
        "beasts": beasts,
        "skills": skills,
        "guides": guides,
        "obstacles": obstacles,
    }


class RemoteWorldView(World):
    """World instance used only for drawing snapshots on clients."""

    def __init__(self, sprite_bank):
        super().__init__(None, sprite_bank, populate=False)

    def apply_snapshot(self, payload: dict[str, Any] | None) -> None:
        payload = payload or {}
        self.prey_list = [
            Prey(
                item["tile_x"],
                item["tile_y"],
                item["kind"],
                item["length_bonus"],
                _deserialize_color(item["color"]),
                item["radius"],
            )
            for item in payload.get("prey", [])
        ]
        self.beast_list = [
            Beast(
                item["tile_x"],
                item["tile_y"],
                item["kind"],
                _deserialize_color(item["color"]),
            )
            for item in payload.get("beasts", [])
        ]
        self.skill_cards = [
            SkillCard(
                item["tile_x"],
                item["tile_y"],
                item["kind"],
                _deserialize_color(item["color"]),
                _deserialize_color(item["ring_color"]),
                item["sprite_path"],
            )
            for item in payload.get("skills", [])
        ]
        self.guide_list = [
            Guide(
                x=float(item["x"]),
                y=float(item["y"]),
                target_type=item["target_type"],
                direction_angle=float(item["direction_angle"]),
                visible=bool(item["visible"]),
            )
            for item in payload.get("guides", [])
        ]
        self.obstacle_list = [
            AdventureObstacle(
                item["tile_x"],
                item["tile_y"],
                item["width_tiles"],
                item["height_tiles"],
                float(item["lifetime"]),
            )
            for item in payload.get("obstacles", [])
        ]


@dataclass
class MultiplayerPlayerView:
    """Client-side metadata for a player row."""

    player_id: str
    name: str
    is_host: bool
    connected: bool
    active_in_round: bool
    ready_in_lobby: bool
    eliminated: bool
    bite_dead: bool
    respawn_timer: float
    held_skill: str | None
    length: int
    alive: bool
    colors: dict[str, list[int]]


class MultiplayerSceneState:
    """Client-side state built from server snapshots."""

    def __init__(self, sprite_bank):
        self.camera = Camera(MAP_WIDTH, MAP_HEIGHT, SCREEN_WIDTH, SCREEN_HEIGHT)
        self.camera.reset()
        self.fog = FogOfWar(SCREEN_WIDTH, SCREEN_HEIGHT, self.camera)
        self.world = RemoteWorldView(sprite_bank)
        self.snakes: dict[str, Snake] = {}
        self.players: dict[str, MultiplayerPlayerView] = {}
        self.local_player_id: str | None = None
        self.host_player_id: str | None = None
        self.phase = "lobby"
        self.winner_name: str | None = None
        self.result_reason = ""
        self.reveal_timers: dict[str, float] = {}
        self.game_time = 0.0

    @property
    def local_snake(self) -> Snake | None:
        if self.local_player_id is None:
            return None
        return self.snakes.get(self.local_player_id)

    def other_player_ids(self) -> list[str]:
        return [player_id for player_id in self.players if player_id != self.local_player_id]

    def other_snakes(self) -> list[Snake]:
        return [self.snakes[player_id] for player_id in self.other_player_ids() if player_id in self.snakes]

    def apply_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.phase = snapshot.get("phase", self.phase)
        self.local_player_id = snapshot.get("you", self.local_player_id)
        self.host_player_id = snapshot.get("host_id", self.host_player_id)
        self.winner_name = snapshot.get("winner_name")
        self.result_reason = snapshot.get("result_reason", "")

        new_players: dict[str, MultiplayerPlayerView] = {}
        for payload in snapshot.get("players", []):
            player_id = payload["id"]
            new_players[player_id] = MultiplayerPlayerView(
                player_id=player_id,
                name=payload["name"],
                is_host=bool(payload["host"]),
                connected=bool(payload["connected"]),
                active_in_round=bool(payload["active_in_round"]),
                ready_in_lobby=bool(payload.get("ready_in_lobby", False)),
                eliminated=bool(payload["eliminated"]),
                bite_dead=bool(payload["bite_dead"]),
                respawn_timer=float(payload["respawn_timer"]),
                held_skill=payload.get("held_skill"),
                length=int(payload["length"]),
                alive=bool(payload["alive"]),
                colors=payload["colors"],
            )
            if player_id not in self.snakes:
                self.snakes[player_id] = Snake(max_vision=DUEL_MAX_VISION_MULTIPLIER)
            _copy_snake_state(self.snakes[player_id], payload.get("snake"), payload["colors"])

        removed_ids = set(self.players) - set(new_players)
        for player_id in removed_ids:
            self.snakes.pop(player_id, None)
            self.reveal_timers.pop(player_id, None)

        self.players = new_players
        self.world.apply_snapshot(snapshot.get("world"))

    def tick(self, dt: float) -> None:
        self.game_time += dt
        for player_id in list(self.reveal_timers):
            self.reveal_timers[player_id] = max(0.0, self.reveal_timers[player_id] - dt)
            if self.reveal_timers[player_id] <= 0:
                self.reveal_timers.pop(player_id, None)

        local_snake = self.local_snake
        if local_snake is None or not local_snake.segments:
            return

        self.camera.update(local_snake.head_pos[0], local_snake.head_pos[1], dt)
        self.fog.update(local_snake.head_pos, local_snake.current_vision_radius)

    def apply_event(self, event: dict[str, Any]) -> None:
        kind = event.get("kind")
        if kind == "eat" and event.get("player_id") == self.local_player_id:
            for player_id in self.other_player_ids():
                self.reveal_timers[player_id] = DUEL_REVEAL_DURATION
        elif kind == "respawn":
            player_id = event.get("player_id")
            if player_id is not None and player_id != self.local_player_id:
                self.reveal_timers[player_id] = DUEL_REVEAL_DURATION
        elif kind == "bite" and event.get("attacker_id") == self.local_player_id:
            victim_id = event.get("victim_id")
            if victim_id is not None:
                self.reveal_timers[victim_id] = DUEL_REVEAL_DURATION

    def is_remote_snake_visible(self, player_id: str) -> bool:
        local_snake = self.local_snake
        if local_snake is None or player_id == self.local_player_id:
            return False

        snake = self.snakes.get(player_id)
        if snake is None or not snake.segments:
            return False

        if self.reveal_timers.get(player_id, 0.0) > 0:
            return True

        for segment in snake.segments:
            if math.hypot(segment[0] - local_snake.head_pos[0], segment[1] - local_snake.head_pos[1]) <= local_snake.current_vision_radius:
                return True
        return False


class MultiplayerClient:
    """Thin non-blocking client connection used by the pygame main loop."""

    def __init__(self):
        self.socket: socket.socket | None = None
        self.recv_buffer = bytearray()
        self.send_buffer = bytearray()
        self._lock = threading.Lock()
        self.connected = False
        self.player_id: str | None = None
        self.is_host = False
        self.incoming_messages: list[dict[str, Any]] = []
        self.last_error = ""

    def connect(self, host: str, port: int, player_name: str) -> None:
        self.close()
        sock = socket.create_connection((host, port), timeout=CONNECT_TIMEOUT_SECONDS)
        sock.setblocking(False)
        self.socket = sock
        self.connected = True
        self.queue_message({"type": "hello", "name": player_name})
        self.pump()

    def queue_message(self, payload: dict[str, Any]) -> None:
        if not self.connected or self.socket is None:
            return
        encoded = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        with self._lock:
            self.send_buffer.extend(encoded)

    def pump(self) -> list[dict[str, Any]]:
        if not self.connected or self.socket is None:
            return []

        self._pump_send()
        self._pump_recv()

        messages = list(self.incoming_messages)
        self.incoming_messages.clear()
        return messages

    def _pump_send(self) -> None:
        if self.socket is None:
            return
        with self._lock:
            if not self.send_buffer:
                return
            try:
                sent = self.socket.send(self.send_buffer)
            except (BlockingIOError, InterruptedError):
                return
            except OSError as exc:
                self.last_error = str(exc)
                self.close()
                return
            if sent > 0:
                del self.send_buffer[:sent]

    def _pump_recv(self) -> None:
        if self.socket is None:
            return
        while True:
            try:
                chunk = self.socket.recv(65536)
            except (BlockingIOError, InterruptedError):
                break
            except OSError as exc:
                self.last_error = str(exc)
                self.close()
                break

            if not chunk:
                self.last_error = "连接已关闭"
                self.close()
                break

            self.recv_buffer.extend(chunk)
            while b"\n" in self.recv_buffer:
                line, _, rest = self.recv_buffer.partition(b"\n")
                self.recv_buffer = bytearray(rest)
                if not line:
                    continue
                payload = json.loads(line.decode("utf-8"))
                if payload.get("type") == "welcome":
                    self.player_id = payload.get("player_id")
                    self.is_host = bool(payload.get("host"))
                self.incoming_messages.append(payload)

    def close(self) -> None:
        if self.socket is not None:
            try:
                self.socket.close()
            except OSError:
                pass
        self.socket = None
        self.connected = False
        self.player_id = None
        self.is_host = False
        self.recv_buffer = bytearray()
        with self._lock:
            self.send_buffer = bytearray()


@dataclass
class _ServerConnection:
    sock: socket.socket
    addr: tuple[str, int]
    player_id: str | None = None
    recv_buffer: bytearray = field(default_factory=bytearray)
    send_buffer: bytearray = field(default_factory=bytearray)


@dataclass
class _RoundPlayer:
    player_id: str
    name: str
    connection: _ServerConnection
    is_host: bool
    connected: bool = True
    active_in_round: bool = False
    ready_in_lobby: bool = False
    eliminated: bool = False
    bite_dead: bool = False
    respawn_timer: float = 0.0
    held_skill: str | None = None
    body_bright: tuple[int, int, int] = (0, 0, 0)
    body_dark: tuple[int, int, int] = (0, 0, 0)
    head_color: tuple[int, int, int] = (0, 0, 0)
    snake: Snake | None = None
    spawn_point: tuple[float, float] = (float(INITIAL_WORLD_X), float(INITIAL_WORLD_Y))


class MultiplayerServer:
    """Authoritative multiplayer server running inside the host process."""

    def __init__(self, host: str = "0.0.0.0", port: int = DEFAULT_MULTIPLAYER_PORT):
        self.host = host
        self.port = port
        self.bound_port = port
        self.selector = selectors.DefaultSelector()
        self.stop_event = threading.Event()
        self.ready_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.listen_socket: socket.socket | None = None
        self.connections: dict[socket.socket, _ServerConnection] = {}
        self.players: dict[str, _RoundPlayer] = {}
        self.player_sequence = 0
        self.phase = "lobby"
        self.world: World | None = None
        self.round_number = 0
        self.host_player_id: str | None = None
        self.winner_name: str | None = None
        self.result_reason = ""
        self.last_error = ""

    def start(self) -> None:
        self.stop()
        self.stop_event.clear()
        self.ready_event.clear()
        self.thread = threading.Thread(target=self._run, name="MultiplayerServer", daemon=True)
        self.thread.start()
        if not self.ready_event.wait(timeout=2.0):
            raise RuntimeError(self.last_error or "联机服务启动超时")
        if self.last_error:
            raise RuntimeError(self.last_error)

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self.thread = None

    def _run(self) -> None:
        try:
            listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listen_socket.bind((self.host, self.port))
            listen_socket.listen()
            listen_socket.setblocking(False)
            self.bound_port = int(listen_socket.getsockname()[1])
            self.listen_socket = listen_socket
            self.selector.register(listen_socket, selectors.EVENT_READ, data=None)
            self.ready_event.set()

            last_tick = time.monotonic()
            next_snapshot = last_tick

            while not self.stop_event.is_set():
                timeout = max(0.0, min(NETWORK_LOOP_INTERVAL, next_snapshot - time.monotonic()))
                events = self.selector.select(timeout)
                for key, mask in events:
                    if key.data is None:
                        self._accept_connection()
                    else:
                        self._service_connection(key, mask)

                now = time.monotonic()
                dt = min(0.05, now - last_tick)
                last_tick = now

                if self.phase == "playing":
                    self._update_round(dt)

                if now >= next_snapshot:
                    self._broadcast_snapshots()
                    next_snapshot = now + SNAPSHOT_INTERVAL
        except Exception as exc:  # pragma: no cover - defensive guard
            self.last_error = str(exc)
            self.ready_event.set()
        finally:
            self._shutdown()

    def _accept_connection(self) -> None:
        if self.listen_socket is None:
            return
        client_socket, addr = self.listen_socket.accept()
        client_socket.setblocking(False)
        connection = _ServerConnection(sock=client_socket, addr=addr)
        self.connections[client_socket] = connection
        self.selector.register(client_socket, selectors.EVENT_READ, data=connection)

    def _service_connection(self, key: selectors.SelectorKey, mask: int) -> None:
        connection: _ServerConnection = key.data

        if mask & selectors.EVENT_READ:
            try:
                chunk = connection.sock.recv(65536)
            except (BlockingIOError, InterruptedError):
                chunk = None
            except OSError:
                self._close_connection(connection)
                return

            if chunk == b"":
                self._close_connection(connection)
                return

            if chunk:
                connection.recv_buffer.extend(chunk)
                while b"\n" in connection.recv_buffer:
                    line, _, rest = connection.recv_buffer.partition(b"\n")
                    connection.recv_buffer = bytearray(rest)
                    if not line:
                        continue
                    payload = json.loads(line.decode("utf-8"))
                    self._handle_message(connection, payload)

        if mask & selectors.EVENT_WRITE:
            if connection.send_buffer:
                try:
                    sent = connection.sock.send(connection.send_buffer)
                except (BlockingIOError, InterruptedError):
                    sent = 0
                except OSError:
                    self._close_connection(connection)
                    return
                if sent > 0:
                    del connection.send_buffer[:sent]
            if not connection.send_buffer:
                self._set_selector_events(connection, selectors.EVENT_READ)

    def _set_selector_events(self, connection: _ServerConnection, events: int) -> None:
        try:
            self.selector.modify(connection.sock, events, data=connection)
        except KeyError:
            return

    def _queue_message(self, connection: _ServerConnection, payload: dict[str, Any]) -> None:
        connection.send_buffer.extend((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        self._set_selector_events(connection, selectors.EVENT_READ | selectors.EVENT_WRITE)

    def _broadcast(self, payload: dict[str, Any]) -> None:
        for connection in list(self.connections.values()):
            self._queue_message(connection, payload)

    def _handle_message(self, connection: _ServerConnection, payload: dict[str, Any]) -> None:
        message_type = payload.get("type")

        if message_type == "hello":
            if self.phase == "playing":
                self._queue_message(connection, {"type": "error", "message": "房间正在对局，请等下一局再加入。"})
                self._close_connection(connection)
                return
            self.player_sequence += 1
            player_id = f"player-{self.player_sequence}"
            player_name = self._dedupe_name(str(payload.get("name") or "player"))
            is_host = self.host_player_id is None
            if is_host:
                self.host_player_id = player_id
            connection.player_id = player_id
            self.players[player_id] = _RoundPlayer(
                player_id=player_id,
                name=player_name,
                connection=connection,
                is_host=is_host,
            )
            self._queue_message(
                connection,
                {
                    "type": "welcome",
                    "player_id": player_id,
                    "host": is_host,
                    "port": self.bound_port,
                },
            )
            return

        if connection.player_id is None:
            return

        player = self.players.get(connection.player_id)
        if player is None:
            return

        if message_type == "disconnect":
            self._close_connection(connection)
            return

        if message_type == "start_match":
            if player.is_host and self.phase == "lobby" and self._can_host_start_match():
                self._start_match()
            return

        if message_type == "toggle_ready":
            if self.phase == "lobby":
                player.ready_in_lobby = not player.ready_in_lobby
            return

        if message_type == "restart_match":
            if player.is_host and self.phase == "result" and self.players:
                self._start_match()
            return

        if self.phase != "playing" or not player.active_in_round or player.snake is None:
            return

        if message_type == "input":
            target = payload.get("target")
            if (
                isinstance(target, list)
                and len(target) == 2
                and not player.eliminated
                and not player.bite_dead
                and player.snake.alive
            ):
                player.snake.set_target(float(target[0]), float(target[1]))
            return

        if message_type == "activate_skill":
            if not player.eliminated and not player.bite_dead:
                self._activate_player_skill(player)

    def _dedupe_name(self, base_name: str) -> str:
        active_names = {player.name for player in self.players.values()}
        if base_name not in active_names:
            return base_name
        suffix = 2
        while f"{base_name}-{suffix}" in active_names:
            suffix += 1
        return f"{base_name}-{suffix}"

    def _can_host_start_match(self) -> bool:
        connected_players = [player for player in self.players.values() if player.connected]
        if not connected_players:
            return False
        if len(connected_players) < 2:
            return False
        return all(player.ready_in_lobby for player in connected_players)

    def _start_match(self) -> None:
        participants = [player for player in self.players.values() if player.connected]
        if not participants:
            return

        self.round_number += 1
        self.phase = "playing"
        self.winner_name = None
        self.result_reason = ""

        spawn_points = generate_spawn_points(len(participants))
        for index, player in enumerate(participants):
            body_bright, body_dark, head_color = player_color_triplet(index)
            player.spawn_point = spawn_points[index]
            player.body_bright = body_bright
            player.body_dark = body_dark
            player.head_color = head_color
            player.snake = Snake(
                spawn_point=player.spawn_point,
                body_color_bright=body_bright,
                body_color_dark=body_dark,
                head_color=head_color,
                max_vision=DUEL_MAX_VISION_MULTIPLIER,
            )
            player.connected = True
            player.active_in_round = True
            player.ready_in_lobby = False
            player.eliminated = False
            player.bite_dead = False
            player.respawn_timer = 0.0
            player.held_skill = None

        world_owner = participants[0].snake
        other_snakes = [player.snake for player in participants[1:]]
        self.world = World(world_owner, None, other_snakes=other_snakes, config=build_multiplayer_world_config(len(participants)))
        self._broadcast({"type": "event", "kind": "round_started"})

    def _update_round(self, dt: float) -> None:
        if self.world is None:
            return

        active_players = [player for player in self.players.values() if player.active_in_round and player.connected and player.snake is not None]

        for player in active_players:
            snake = player.snake
            if snake is None or player.eliminated:
                continue
            if player.bite_dead:
                player.respawn_timer = max(0.0, player.respawn_timer - dt)
                if player.respawn_timer <= 0.0:
                    player.bite_dead = False
                    snake.reset()
                    snake.alive = True
                    self._broadcast({"type": "event", "kind": "respawn", "player_id": player.player_id})
                continue
            snake.update(dt)

        self.world.update(dt, [player.snake for player in active_players if player.snake is not None and not player.eliminated])
        self._handle_round_collisions(active_players)
        self._check_round_end()

    def _handle_round_collisions(self, active_players: list[_RoundPlayer]) -> None:
        if self.world is None:
            return

        for player in active_players:
            snake = player.snake
            if snake is None or player.eliminated or player.bite_dead or not snake.alive or not snake.segments:
                continue

            head_x, head_y = snake.head_pos
            prey = self.world.get_colliding_prey(head_x, head_y)
            if prey is not None:
                snake.grow(prey.length_bonus)
                snake.hunger = 0.0
                self.world.remove_prey(prey)
                self.world.add_beast()
                self._broadcast({"type": "event", "kind": "eat", "player_id": player.player_id})

            beast = self.world.get_colliding_beast(head_x, head_y)
            if beast is not None:
                self._eliminate_player(player, "beast")
                continue

            obstacle = self.world.get_colliding_obstacle(head_x, head_y)
            if obstacle is not None:
                if not snake.starvation_damage_applied:
                    snake.lose_segments(1, can_defeat=True)
                self.world.remove_obstacle(obstacle)
                self._broadcast({"type": "event", "kind": "guide", "player_id": player.player_id})
                if not snake.alive:
                    self._eliminate_player(player, "obstacle")
                    continue

            if player.held_skill is None:
                skill_card = self.world.get_colliding_skill_card(head_x, head_y)
                if skill_card is not None:
                    player.held_skill = skill_card.kind
                    self.world.remove_skill_card(skill_card)
                    self._broadcast(
                        {
                            "type": "event",
                            "kind": "skill_pickup",
                            "player_id": player.player_id,
                            "skill": skill_card.kind,
                        }
                    )

        for attacker in active_players:
            attacker_snake = attacker.snake
            if (
                attacker_snake is None
                or attacker.eliminated
                or attacker.bite_dead
                or not attacker_snake.alive
                or not attacker_snake.segments
            ):
                continue

            bite_happened = False
            for victim in active_players:
                if attacker.player_id == victim.player_id:
                    continue
                victim_snake = victim.snake
                if (
                    victim_snake is None
                    or victim.eliminated
                    or victim.bite_dead
                    or not victim_snake.segments
                    or not attacker_snake.alive
                ):
                    continue

                collision_index = self._check_snake_bite(attacker_snake, victim_snake)
                if collision_index < 0:
                    continue

                if collision_index == 0:
                    victim_snake.trim_from_collision(1)
                else:
                    victim_snake.trim_from_collision(collision_index)

                attacker_snake.alive = False
                attacker_snake.clear_target()
                attacker.bite_dead = True
                attacker.respawn_timer = DUEL_RESPAWN_DURATION
                self._broadcast(
                    {
                        "type": "event",
                        "kind": "bite",
                        "attacker_id": attacker.player_id,
                        "victim_id": victim.player_id,
                    }
                )
                bite_happened = True
                break

            if bite_happened:
                continue

    def _check_snake_bite(self, attacker: Snake, victim: Snake) -> int:
        if not attacker.alive or not victim.segments:
            return -1
        head_x, head_y = attacker.head_pos
        for index, segment in enumerate(victim.segments):
            distance = math.hypot(head_x - segment[0], head_y - segment[1])
            threshold = SNAKE_HEAD_RADIUS + (SNAKE_BODY_RADIUS_MAX if index == 0 else SNAKE_BODY_RADIUS_MIN + 4)
            if distance < threshold:
                return index
        return -1

    def _activate_player_skill(self, player: _RoundPlayer) -> bool:
        if self.world is None or player.snake is None or player.held_skill is None:
            return False

        snake = player.snake
        skill_kind = player.held_skill
        used = False

        if skill_kind == "purge":
            visible_beasts = self.world.visible_beasts(lambda rect: _rect_visible_to_snake(rect, snake))
            if visible_beasts:
                self.world.clear_beasts(visible_beasts)
            used = True
        elif skill_kind == "haste":
            snake.apply_speed_boost()
            used = True
        elif skill_kind == "harvest":
            visible_prey = self.world.visible_prey(lambda point: _point_visible_to_snake(point, snake))
            total_growth = sum(prey.length_bonus for prey in visible_prey)
            for prey in visible_prey:
                self.world.remove_prey(prey)
            if total_growth > 0:
                snake.grow(total_growth)
                snake.hunger = 0.0
            used = True
        elif skill_kind == "grow":
            snake.grow(1)
            used = True
        elif skill_kind == "vision":
            snake.apply_vision_surge()
            used = True

        if used:
            player.held_skill = None
            self._broadcast(
                {
                    "type": "event",
                    "kind": "skill_used",
                    "player_id": player.player_id,
                    "skill": skill_kind,
                }
            )
        return used

    def _eliminate_player(self, player: _RoundPlayer, reason: str) -> None:
        if player.snake is None or player.eliminated:
            return
        player.eliminated = True
        player.bite_dead = False
        player.respawn_timer = 0.0
        player.snake.alive = False
        player.snake.clear_target()
        self._broadcast({"type": "event", "kind": "death", "player_id": player.player_id, "reason": reason})

    def _check_round_end(self) -> None:
        survivors = [player for player in self.players.values() if player.active_in_round and player.connected and not player.eliminated]
        if len(survivors) > 1:
            return

        self.phase = "result"
        if len(survivors) == 1:
            self.winner_name = survivors[0].name
            self.result_reason = "last_survivor"
        else:
            best_length = -1
            winners: list[_RoundPlayer] = []
            for player in self.players.values():
                if not player.active_in_round or player.snake is None:
                    continue
                length = player.snake.length
                if length > best_length:
                    winners = [player]
                    best_length = length
                elif length == best_length:
                    winners.append(player)
            self.winner_name = winners[0].name if len(winners) == 1 else "draw"
            self.result_reason = "length_tiebreak"

        self._broadcast(
            {
                "type": "event",
                "kind": "round_ended",
                "winner_name": self.winner_name,
                "reason": self.result_reason,
            }
        )

    def _close_connection(self, connection: _ServerConnection) -> None:
        try:
            self.selector.unregister(connection.sock)
        except Exception:
            pass
        try:
            connection.sock.close()
        except OSError:
            pass
        self.connections.pop(connection.sock, None)

        player_id = connection.player_id
        if player_id is None:
            return

        player = self.players.get(player_id)
        if player is None:
            return

        player.connected = False
        player.active_in_round = self.phase != "lobby"

        if player.is_host:
            for other in list(self.connections.values()):
                self._queue_message(other, {"type": "shutdown", "reason": "房主已离开，房间已关闭。"})
            self.stop_event.set()
            return

        if self.phase == "lobby":
            self.players.pop(player_id, None)
        else:
            self._check_round_end()

    def _broadcast_snapshots(self) -> None:
        for player in self.players.values():
            if not player.connected:
                continue
            payload = self._build_snapshot_for_player(player)
            self._queue_message(player.connection, payload)

    def _build_snapshot_for_player(self, player: _RoundPlayer) -> dict[str, Any]:
        players_payload = []
        for item in self.players.values():
            snake_payload = _serialize_snake(item.snake)
            players_payload.append(
                {
                    "id": item.player_id,
                    "name": item.name,
                    "host": item.is_host,
                    "connected": item.connected,
                    "active_in_round": item.active_in_round,
                    "ready_in_lobby": item.ready_in_lobby,
                    "eliminated": item.eliminated,
                    "bite_dead": item.bite_dead,
                    "respawn_timer": round(item.respawn_timer, 3),
                    "held_skill": item.held_skill,
                    "length": item.snake.length if item.snake is not None else 0,
                    "alive": item.snake.alive if item.snake is not None else False,
                    "colors": {
                        "body_bright": _serialize_color(item.body_bright),
                        "body_dark": _serialize_color(item.body_dark),
                        "head_color": _serialize_color(item.head_color),
                    },
                    "snake": snake_payload,
                }
            )

        if player.snake is not None and player.snake.segments:
            center_point = player.snake.head_pos
        else:
            center_point = player.spawn_point

        world_payload = _serialize_world_for_player(self.world, center_point) if self.world is not None else None

        return {
            "type": "snapshot",
            "phase": self.phase,
            "you": player.player_id,
            "host_id": self.host_player_id,
            "players": players_payload,
            "world": world_payload,
            "winner_name": self.winner_name,
            "result_reason": self.result_reason,
            "round": self.round_number,
        }

    def _shutdown(self) -> None:
        try:
            if self.listen_socket is not None:
                try:
                    self.selector.unregister(self.listen_socket)
                except Exception:
                    pass
                try:
                    self.listen_socket.close()
                except OSError:
                    pass
        finally:
            self.listen_socket = None

        for connection in list(self.connections.values()):
            try:
                self.selector.unregister(connection.sock)
            except Exception:
                pass
            try:
                connection.sock.close()
            except OSError:
                pass
        self.connections.clear()

        try:
            self.selector.close()
        except Exception:
            pass


def parse_host_port(text: str, default_port: int = DEFAULT_MULTIPLAYER_PORT) -> tuple[str, int]:
    """Parse host[:port] input from the join screen."""

    value = text.strip()
    if not value:
        raise ValueError("请输入房主地址")

    if value.count(":") == 0:
        return value, default_port

    host, port_text = value.rsplit(":", 1)
    if not host:
        raise ValueError("地址格式不正确")

    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError("端口必须是数字") from exc

    if port <= 0 or port > 65535:
        raise ValueError("端口范围必须在 1-65535")

    return host, port


def draw_multiplayer_setup(
    screen,
    title_font,
    body_font,
    small_font,
    setup_state: dict[str, Any],
    host_button: pygame.Rect,
    join_button: pygame.Rect,
    connect_button: pygame.Rect,
    input_rect: pygame.Rect,
) -> None:
    """Draw the host/join setup scene."""

    screen.fill(MENU_BG_COLOR)
    panel_rect = pygame.Rect(80, 64, SCREEN_WIDTH - 160, SCREEN_HEIGHT - 128)
    panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
    panel.fill(MENU_PANEL_COLOR)
    screen.blit(panel, panel_rect.topleft)

    title = title_font.render("多人野兽模式", True, MENU_TITLE_COLOR)
    screen.blit(title, ((SCREEN_WIDTH - title.get_width()) // 2, panel_rect.y + 24))

    subtitle = "主机权威同步，主机创建房间，其他玩家输入 IP:端口 加入"
    sub_surface = body_font.render(subtitle, True, MENU_TEXT_COLOR)
    screen.blit(sub_surface, ((SCREEN_WIDTH - sub_surface.get_width()) // 2, panel_rect.y + 118))

    for rect, label in ((host_button, "创建房间"), (join_button, "加入房间")):
        pygame.draw.rect(screen, MENU_CARD_COLOR, rect, border_radius=20)
        pygame.draw.rect(screen, MENU_CARD_BORDER, rect, width=3, border_radius=20)
        text_surface = body_font.render(label, True, MENU_TEXT_COLOR)
        screen.blit(
            text_surface,
            (rect.centerx - text_surface.get_width() // 2, rect.centery - text_surface.get_height() // 2),
        )

    local_name = setup_state.get("hostname") or get_hostname_name()
    local_ips = setup_state.get("local_ips") or get_local_ip_addresses()
    ip_text = " / ".join(local_ips[:3])
    info_lines = [
        f"本机蛇名: {local_name}",
        f"建议房主地址: {ip_text}:{DEFAULT_MULTIPLAYER_PORT}",
        "多人模式中 Q 只打开本地菜单，不会暂停其他玩家。",
    ]
    y = panel_rect.y + 250
    for line in info_lines:
        surface = small_font.render(line, True, MENU_HINT_COLOR)
        screen.blit(surface, (panel_rect.x + 48, y))
        y += 36

    field_title = body_font.render("加入房间", True, MENU_TEXT_COLOR)
    screen.blit(field_title, (panel_rect.x + 48, panel_rect.y + 390))
    pygame.draw.rect(screen, (18, 28, 20), input_rect, border_radius=14)
    pygame.draw.rect(screen, MENU_CARD_BORDER, input_rect, width=2, border_radius=14)
    address_text = setup_state.get("join_address", "")
    address_surface = body_font.render(address_text or "192.168.1.8:36123", True, MENU_TEXT_COLOR if address_text else MENU_HINT_COLOR)
    screen.blit(address_surface, (input_rect.x + 18, input_rect.centery - address_surface.get_height() // 2))

    pygame.draw.rect(screen, MENU_CARD_COLOR, connect_button, border_radius=16)
    pygame.draw.rect(screen, MENU_CARD_BORDER, connect_button, width=2, border_radius=16)
    connect_surface = body_font.render("连接", True, MENU_TEXT_COLOR)
    screen.blit(
        connect_surface,
        (
            connect_button.centerx - connect_surface.get_width() // 2,
            connect_button.centery - connect_surface.get_height() // 2,
        ),
    )

    hint_lines = [
        "按 Enter 也可以直接连接，M 返回主页，ESC 退出。",
        setup_state.get("status_message", ""),
    ]
    y = panel_rect.bottom - 94
    for line in hint_lines:
        if not line:
            continue
        color = MENU_TEXT_COLOR if "成功" in line else MENU_HINT_COLOR
        surface = small_font.render(line, True, color)
        screen.blit(surface, (panel_rect.x + 48, y))
        y += 30


def draw_multiplayer_lobby(
    screen,
    title_font,
    body_font,
    small_font,
    scene_state: MultiplayerSceneState,
    local_hostname: str,
    local_ips: list[str],
    status_message: str = "",
) -> None:
    """Draw the pre-match lobby."""

    screen.fill(MENU_BG_COLOR)
    panel_rect = pygame.Rect(90, 70, SCREEN_WIDTH - 180, SCREEN_HEIGHT - 140)
    panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
    panel.fill(MENU_PANEL_COLOR)
    screen.blit(panel, panel_rect.topleft)

    header = title_font.render("多人野兽大厅", True, MENU_TITLE_COLOR)
    screen.blit(header, ((SCREEN_WIDTH - header.get_width()) // 2, panel_rect.y + 24))

    role = "房主" if scene_state.local_player_id == scene_state.host_player_id else "玩家"
    subtitle = f"{role}: {local_hostname}"
    subtitle_surface = body_font.render(subtitle, True, MENU_TEXT_COLOR)
    screen.blit(subtitle_surface, ((SCREEN_WIDTH - subtitle_surface.get_width()) // 2, panel_rect.y + 120))

    ip_line = "房间地址: " + " / ".join(f"{ip}:{DEFAULT_MULTIPLAYER_PORT}" for ip in local_ips[:3])
    ip_surface = small_font.render(ip_line, True, MENU_HINT_COLOR)
    screen.blit(ip_surface, ((SCREEN_WIDTH - ip_surface.get_width()) // 2, panel_rect.y + 170))

    tips = [
        "蛇名自动使用各自主机名。",
        "Space 切换准备 / 取消准备。",
        "全部玩家准备后，房主按 Enter 开始对局。",
        "Q 打开本地菜单，M 断开并返回主页。",
    ]
    y = panel_rect.y + 230
    for line in tips:
        surface = small_font.render(line, True, MENU_HINT_COLOR)
        screen.blit(surface, (panel_rect.x + 48, y))
        y += 34

    list_rect = pygame.Rect(panel_rect.x + 48, panel_rect.y + 360, panel_rect.width - 96, panel_rect.height - 430)
    pygame.draw.rect(screen, MENU_CARD_COLOR, list_rect, border_radius=18)
    pygame.draw.rect(screen, MENU_CARD_BORDER, list_rect, width=2, border_radius=18)

    line_y = list_rect.y + 22
    for index, player in enumerate(scene_state.players.values(), start=1):
        label = f"{index}. {player.name}"
        if player.is_host:
            label += " [房主]"
        if not player.connected:
            state = "已离线"
        elif player.ready_in_lobby:
            state = "已准备"
        else:
            state = "未准备"
        color = _deserialize_color(player.colors["head_color"])
        text = small_font.render(f"{label}  {state}", True, color)
        screen.blit(text, (list_rect.x + 22, line_y))
        line_y += 34

    if status_message:
        status_surface = small_font.render(status_message, True, MENU_HINT_COLOR)
        screen.blit(status_surface, (list_rect.x + 22, list_rect.bottom - 34))


def draw_multiplayer_score_panel(
    screen,
    small_font,
    players: list[MultiplayerPlayerView],
    local_player_id: str | None,
) -> None:
    """Draw the shared right-side scoreboard for multiplayer matches."""

    panel_height = max(72, 32 * len(players) + 20)
    panel_x = SCREEN_WIDTH - HUD_LEFT - HUD_WIDTH
    panel = pygame.Surface((HUD_WIDTH, panel_height), pygame.SRCALPHA)
    panel.fill(HUD_PANEL_COLOR)
    screen.blit(panel, (panel_x, HUD_TOP))

    y_offset = HUD_TOP + 10
    for player in players:
        prefix = "你" if player.player_id == local_player_id else player.name
        if player.eliminated:
            status = "出局"
        elif player.bite_dead:
            status = f"复活 {player.respawn_timer:.1f}s"
        elif not player.connected:
            status = "离线"
        else:
            status = f"长度 {player.length}"
        color = _deserialize_color(player.colors["head_color"])
        surface = small_font.render(f"{prefix} {status}", True, color)
        screen.blit(surface, (panel_x + 18, y_offset))
        y_offset += 32


def draw_multiplayer_status_text(
    screen,
    body_font,
    scene_state: MultiplayerSceneState,
) -> None:
    """Draw local-only mode status near the bottom edge."""

    local_player = scene_state.players.get(scene_state.local_player_id or "")
    if local_player is None:
        return

    if local_player.eliminated:
        text = "你已出局，当前为观战视角"
    elif local_player.bite_dead:
        text = f"你被蛇咬中，{local_player.respawn_timer:.1f}s 后复活"
    else:
        text = "联机进行中"

    surface = body_font.render(text, True, HUD_TEXT_COLOR)
    panel = pygame.Surface((surface.get_width() + 28, surface.get_height() + 14), pygame.SRCALPHA)
    panel.fill(HUD_PANEL_COLOR)
    x = (SCREEN_WIDTH - panel.get_width()) // 2
    y = SCREEN_HEIGHT - 80
    screen.blit(panel, (x, y))
    screen.blit(surface, (x + 14, y + 7))


def draw_multiplayer_result(
    screen,
    title_font,
    body_font,
    winner_name: str | None,
) -> None:
    """Draw the multiplayer round result overlay."""

    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 176))
    screen.blit(overlay, (0, 0))

    if winner_name == "draw":
        title = "平局"
    elif winner_name:
        title = f"{winner_name} 获胜"
    else:
        title = "对局结束"

    title_surface = title_font.render(title, True, MENU_TITLE_COLOR)
    hint_surface = body_font.render("房主按 R 重新开始，M 返回主页", True, HUD_TEXT_COLOR)
    screen.blit(title_surface, ((SCREEN_WIDTH - title_surface.get_width()) // 2, SCREEN_HEIGHT // 3))
    screen.blit(hint_surface, ((SCREEN_WIDTH - hint_surface.get_width()) // 2, SCREEN_HEIGHT // 2))


def draw_multiplayer_pause_overlay(
    screen,
    title_font,
    body_font,
    small_font,
) -> None:
    """Draw a local-only pause menu for multiplayer sessions."""

    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    screen.blit(overlay, (0, 0))

    panel_rect = pygame.Rect((SCREEN_WIDTH - 640) // 2, (SCREEN_HEIGHT - 300) // 2, 640, 300)
    panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
    panel.fill(MENU_PANEL_COLOR)
    screen.blit(panel, panel_rect.topleft)

    title = title_font.render("联机菜单", True, MENU_TITLE_COLOR)
    line1 = body_font.render("R / Q 继续，M 断开返回主页，ESC 退出游戏", True, MENU_TEXT_COLOR)
    line2 = small_font.render("这个菜单只影响你自己，不会暂停其他玩家。", True, HUD_HINT_COLOR)
    screen.blit(title, (panel_rect.centerx - title.get_width() // 2, panel_rect.y + 34))
    screen.blit(line1, (panel_rect.centerx - line1.get_width() // 2, panel_rect.y + 132))
    screen.blit(line2, (panel_rect.centerx - line2.get_width() // 2, panel_rect.y + 196))
