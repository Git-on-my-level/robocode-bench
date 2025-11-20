"""Starter bot template for LLM-generated Tank Royale bots.

The orchestrator copies this file into each attempt workspace. Models should
edit within the `bot/` directory only.
"""

from __future__ import annotations

import asyncio
import math

from robocode_tank_royale.bot_api.bot import Bot
from robocode_tank_royale.bot_api.bot_info import BotInfo
from robocode_tank_royale.bot_api.events import (  # type: ignore
    HitByBulletEvent,
    HitWallEvent,
    ScannedBotEvent,
)


class LlmStarterBot(Bot):
    def __init__(self) -> None:
        info = BotInfo.from_file("bot-config.json")
        super().__init__(bot_info=info)
        self.set_adjust_gun_for_body_turn(True)
        self.set_adjust_radar_for_gun_turn(True)

    async def run(self) -> None:
        # Simple gun/radar sweep with lightweight movement to avoid skipped turns.
        self.set_turn_radar_right(360)
        while self.is_running():
            if self.get_gun_heat() == 0 and self.get_energy() > 1:
                self.set_fire(1.1)
            self.set_turn_right(10)
            self.set_forward(80)
            await self.go()

    async def on_scanned_bot(self, e: ScannedBotEvent) -> None:
        # Aim using relative position; adjust firepower by distance.
        bearing = self.gun_bearing_to(e.x, e.y)
        self.set_turn_gun_right(bearing)
        if self.get_gun_heat() == 0:
            distance = max(1.0, self.distance_to(e.x, e.y))
            power = max(0.5, min(2.0, 400 / max(distance, 50)))
            self.set_fire(power)

    async def on_hit_by_bullet(self, e: HitByBulletEvent) -> None:
        # Strafe in a predictable but quick dodge.
        self.set_turn_right(90)
        self.set_back(80)

    async def on_hit_wall(self, e: HitWallEvent) -> None:
        self.set_turn_right(90)
        self.set_back(50)


async def main() -> None:
    bot = LlmStarterBot()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
