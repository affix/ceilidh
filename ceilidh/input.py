from __future__ import annotations

import time
from dataclasses import dataclass

import pygame

from .config import ACTIONS, Config


@dataclass
class InputEvent:
    player: int
    action: str
    pressed: bool
    time: float          # perf_counter at poll time
    from_pad: bool = True


def parse_binding(spec: str) -> tuple[str, int, object] | None:
    parts = spec.split(":")
    kind = parts[0]
    try:
        if kind == "button":
            return ("button", int(parts[1]), None)
        if kind == "hat":
            return ("hat", int(parts[1]), tuple(int(x) for x in parts[2].split(",")))
        if kind == "axis":
            return ("axis", int(parts[1]), 1 if parts[2] == "+" else -1)
        if kind == "key":
            return ("key", pygame.key.key_code(parts[1]), None)
    except (IndexError, ValueError):
        return None
    return None


def describe_binding(spec: str) -> str:
    parsed = parse_binding(spec)
    if parsed is None:
        return spec
    kind, index, value = parsed
    if kind == "button":
        return f"Button {index}"
    if kind == "hat":
        names = {(-1, 0): "Left", (1, 0): "Right", (0, 1): "Up", (0, -1): "Down"}
        return f"D-pad {names.get(value, value)}"
    if kind == "axis":
        return f"Axis {index}{'+' if value == 1 else '-'}"
    if kind == "key":
        return f"Key {pygame.key.name(index).upper()}"
    return spec


class InputManager:
    """Maps SDL joystick/keyboard events onto per-player dance pad actions."""

    AXIS_THRESHOLD = 0.55

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.joysticks: dict[int, pygame.joystick.Joystick] = {}
        self.player_device: dict[int, int] = {}
        self.capture = None  # callback for the binding screen
        self._hat_state: dict[tuple[int, int], tuple[int, int]] = {}
        self._axis_state: dict[tuple[int, int], int] = {}
        self.state: dict[tuple[int, str], bool] = {}
        self.refresh_devices()

    def refresh_devices(self) -> None:
        # never quit() the subsystem here: re-initialising it on Linux posts
        # JOYDEVICEADDED for every pad already plugged in, which lands back
        # here and renumbers the instance ids faster than presses arrive
        pygame.joystick.init()
        self.joysticks.clear()
        devices = []
        for index in range(pygame.joystick.get_count()):
            joy = pygame.joystick.Joystick(index)
            self.joysticks[joy.get_instance_id()] = joy
            devices.append(joy)

        self.player_device.clear()
        taken: set[int] = set()
        # honour saved GUIDs first
        for player, pcfg in enumerate(self.cfg.players):
            if not pcfg.device_guid:
                continue
            for joy in devices:
                iid = joy.get_instance_id()
                if iid in taken:
                    continue
                if joy.get_guid() == pcfg.device_guid:
                    self.player_device[player] = iid
                    taken.add(iid)
                    break
        # then fill remaining players in plug order
        for player, pcfg in enumerate(self.cfg.players):
            if player in self.player_device:
                continue
            for joy in devices:
                iid = joy.get_instance_id()
                if iid in taken:
                    continue
                self.player_device[player] = iid
                taken.add(iid)
                pcfg.device_guid = joy.get_guid()
                pcfg.device_name = joy.get_name()
                break
        self._rebuild_maps()

    def assign_device(self, player: int, instance_id: int) -> None:
        joy = self.joysticks.get(instance_id)
        if joy is None:
            return
        for other, iid in list(self.player_device.items()):
            if iid == instance_id and other != player:
                del self.player_device[other]
                self.cfg.players[other].device_guid = None
                self.cfg.players[other].device_name = ""
        self.player_device[player] = instance_id
        self.cfg.players[player].device_guid = joy.get_guid()
        self.cfg.players[player].device_name = joy.get_name()
        self._rebuild_maps()

    def device_name(self, player: int) -> str:
        iid = self.player_device.get(player)
        if iid is None:
            return "no pad"
        joy = self.joysticks.get(iid)
        return joy.get_name() if joy else "no pad"

    def pad_count(self) -> int:
        return len(self.joysticks)

    def _rebuild_maps(self) -> None:
        self.button_map: dict[tuple[int, int], list[tuple[int, str]]] = {}
        self.hat_map: dict[tuple[int, int], list[tuple[tuple[int, int], int, str]]] = {}
        self.axis_map: dict[tuple[int, int], list[tuple[int, int, str]]] = {}
        self.key_map: dict[int, list[tuple[int, str]]] = {}

        for player, pcfg in enumerate(self.cfg.players):
            iid = self.player_device.get(player)
            if iid is not None:
                for action in ACTIONS:
                    for spec in pcfg.bindings.get(action, []):
                        parsed = parse_binding(spec)
                        if parsed is None:
                            continue
                        kind, index, value = parsed
                        if kind == "button":
                            self.button_map.setdefault((iid, index), []).append((player, action))
                        elif kind == "hat":
                            self.hat_map.setdefault((iid, index), []).append((value, player, action))
                        elif kind == "axis":
                            self.axis_map.setdefault((iid, index), []).append((value, player, action))
            for action in ACTIONS:
                for spec in pcfg.keyboard.get(action, []):
                    parsed = parse_binding(spec)
                    if parsed and parsed[0] == "key":
                        self.key_map.setdefault(parsed[1], []).append((player, action))

        self.state = {(p, a): False for p in range(len(self.cfg.players)) for a in ACTIONS}

    def process(self, events: list[pygame.event.Event]) -> list[InputEvent]:
        now = time.perf_counter()
        out: list[InputEvent] = []

        for event in events:
            etype = event.type
            if etype in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                self.refresh_devices()
                continue

            if self.capture is not None:
                captured = self._capture_spec(event)
                if captured is not None:
                    callback, self.capture = self.capture, None
                    callback(captured[0], captured[1])
                    continue
                continue

            if etype == pygame.JOYBUTTONDOWN or etype == pygame.JOYBUTTONUP:
                pressed = etype == pygame.JOYBUTTONDOWN
                for player, action in self.button_map.get((event.instance_id, event.button), []):
                    out.append(InputEvent(player, action, pressed, now))
            elif etype == pygame.JOYHATMOTION:
                key = (event.instance_id, event.hat)
                previous = self._hat_state.get(key, (0, 0))
                self._hat_state[key] = event.value
                for direction, player, action in self.hat_map.get(key, []):
                    was = self._hat_match(previous, direction)
                    now_on = self._hat_match(event.value, direction)
                    if was != now_on:
                        out.append(InputEvent(player, action, now_on, now))
            elif etype == pygame.JOYAXISMOTION:
                key = (event.instance_id, event.axis)
                bindings = self.axis_map.get(key)
                if not bindings:
                    continue
                value = event.value
                current = 1 if value > self.AXIS_THRESHOLD else (-1 if value < -self.AXIS_THRESHOLD else 0)
                previous = self._axis_state.get(key, 0)
                if current == previous:
                    continue
                self._axis_state[key] = current
                for direction, player, action in bindings:
                    was = previous == direction
                    now_on = current == direction
                    if was != now_on:
                        out.append(InputEvent(player, action, now_on, now))
            elif etype == pygame.KEYDOWN or etype == pygame.KEYUP:
                pressed = etype == pygame.KEYDOWN
                for player, action in self.key_map.get(event.key, []):
                    out.append(InputEvent(player, action, pressed, now, from_pad=False))

        deduped: list[InputEvent] = []
        for ev in out:
            key = (ev.player, ev.action)
            if self.state.get(key) == ev.pressed:
                continue
            self.state[key] = ev.pressed
            deduped.append(ev)
        return deduped

    @staticmethod
    def _hat_match(value: tuple[int, int], direction: tuple[int, int]) -> bool:
        return all(value[i] == direction[i] for i in range(2) if direction[i] != 0)

    def held(self, player: int, action: str) -> bool:
        return self.state.get((player, action), False)

    def rebuild(self) -> None:
        self._rebuild_maps()

    def start_capture(self, callback) -> None:
        self.capture = callback

    def cancel_capture(self) -> None:
        self.capture = None

    def _capture_spec(self, event: pygame.event.Event) -> tuple[str, int | None] | None:
        if event.type == pygame.JOYBUTTONDOWN:
            return f"button:{event.button}", event.instance_id
        if event.type == pygame.JOYHATMOTION and event.value != (0, 0):
            return f"hat:{event.hat}:{event.value[0]},{event.value[1]}", event.instance_id
        if event.type == pygame.JOYAXISMOTION and abs(event.value) > 0.8:
            key = (event.instance_id, event.axis)
            if self._axis_state.get(key, 0) != 0:
                return None
            self._axis_state[key] = 1 if event.value > 0 else -1
            return f"axis:{event.axis}:{'+' if event.value > 0 else '-'}", event.instance_id
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "", None
            return f"key:{pygame.key.name(event.key)}", None
        return None
