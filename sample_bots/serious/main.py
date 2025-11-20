import asyncio
import random
from dataclasses import dataclass
from typing import Optional

from robocode_tank_royale.bot_api.bot import Bot
from robocode_tank_royale.bot_api.bot_info import BotInfo
from robocode_tank_royale.bot_api.events import HitByBulletEvent, HitWallEvent, ScannedBotEvent


@dataclass
class Target:
    x: float
    y: float
    energy: float
    turn_seen: int


class SeriousStriker(Bot):
    """Baseline duelist that strafes perpendicular to the enemy."""

    def __init__(self) -> None:
        info = BotInfo.from_file("bot-config.json")
        super().__init__(bot_info=info)
        self.set_adjust_gun_for_body_turn(True)
        self.set_adjust_radar_for_gun_turn(True)
        self._move_dir = 1.0
        self._last_target: Optional[Target] = None

    async def run(self) -> None:
        # Continuous radar sweep to avoid losing track of bots.
        self.set_turn_radar_right(360)
        while self.is_running():
            self._patrol()
            self._maybe_fire_last_seen()
            await self.go()

    def _patrol(self) -> None:
        # Wall avoidance: nudge inward when approaching edges.
        margin = 80
        x, y = self.get_x(), self.get_y()
        width, height = self.get_arena_width(), self.get_arena_height()
        if x < margin or x > width - margin or y < margin or y > height - margin:
            self._move_dir *= -1
            self.set_turn_right(45 * self._move_dir)
        self.set_turn_radar_right(45)
        self.set_turn_right(20 * self._move_dir)
        self.set_forward(140 * self._move_dir)

    def _maybe_fire_last_seen(self) -> None:
        if not self._last_target:
            return
        # Age out stale target info.
        if self.get_turn_number() - self._last_target.turn_seen > 15:
            self._last_target = None
            return
        bearing = self.gun_bearing_to(self._last_target.x, self._last_target.y)
        self.set_turn_gun_right(bearing)
        if self.get_gun_heat() == 0:
            dist = max(1.0, self.distance_to(self._last_target.x, self._last_target.y))
            firepower = max(0.7, min(2.8, 450 / dist))
            if self.get_energy() < 20:
                firepower = min(firepower, 1.2)
            self.set_fire(firepower)

    async def on_scanned_bot(self, e: ScannedBotEvent) -> None:
        self._last_target = Target(x=e.x, y=e.y, energy=e.energy, turn_seen=e.turn_number)
        # Strafe perpendicular to enemy bearing.
        perp = self.bearing_to(e.x, e.y) + 90 * self._move_dir
        self.set_turn_right(perp)
        self.set_forward(120 * self._move_dir)
        self.set_turn_radar_right(self.calc_delta_angle(self.get_radar_direction(), self.direction_to(e.x, e.y)))
        # Fire immediately on scan event.
        if self.get_gun_heat() == 0:
            dist = max(1.0, self.distance_to(e.x, e.y))
            firepower = max(0.7, min(2.8, 450 / dist))
            if self.get_energy() < 20:
                firepower = min(firepower, 1.2)
            self.set_turn_gun_right(self.gun_bearing_to(e.x, e.y))
            self.set_fire(firepower)

    async def on_hit_by_bullet(self, e: HitByBulletEvent) -> None:
        # Randomize move direction to break aim.
        self._move_dir *= -1 if random.random() < 0.7 else 1
        self.set_turn_right(60 * self._move_dir)
        self.set_forward(100 * self._move_dir)

    async def on_hit_wall(self, e: HitWallEvent) -> None:
        self._move_dir *= -1
        self.set_turn_right(120)
        self.set_forward(120 * self._move_dir)


async def main() -> None:
    bot = SeriousStriker()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
