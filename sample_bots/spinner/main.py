import asyncio
import math

from robocode_tank_royale.bot_api.bot import Bot
from robocode_tank_royale.bot_api.bot_info import BotInfo
from robocode_tank_royale.bot_api.events import HitByBulletEvent, HitWallEvent, ScannedBotEvent


class SpinnerBot(Bot):
    def __init__(self) -> None:
        info = BotInfo.from_file("bot-config.json")
        super().__init__(bot_info=info)
        self.set_adjust_gun_for_body_turn(True)
        self.set_adjust_radar_for_gun_turn(True)

    async def run(self) -> None:
        self.set_turn_radar_right(360)
        while self.is_running():
            # Slow circular strafe with continuous radar spin.
            self.set_turn_right(15)
            self.set_turn_gun_left(20)
            self.set_forward(120)
            if self.get_gun_heat() == 0 and self.get_energy() > 1:
                self.set_fire(1.5)
            await self.go()

    async def on_scanned_bot(self, e: ScannedBotEvent) -> None:
        bearing = self.gun_bearing_to(e.x, e.y)
        self.set_turn_gun_right(bearing)
        if self.get_gun_heat() == 0:
            distance = max(1.0, self.distance_to(e.x, e.y))
            power = max(0.5, min(2.5, 2.5 - (distance / 500)))
            self.set_fire(power)

    async def on_hit_wall(self, e: HitWallEvent) -> None:
        self.set_turn_right(120)
        self.set_back(80)

    async def on_hit_by_bullet(self, e: HitByBulletEvent) -> None:
        self.set_turn_right(45)
        self.set_forward(80)


async def main() -> None:
    bot = SpinnerBot()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
