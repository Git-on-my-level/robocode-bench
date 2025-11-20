import asyncio

from robocode_tank_royale.bot_api.bot import Bot
from robocode_tank_royale.bot_api.bot_info import BotInfo
from robocode_tank_royale.bot_api.events import HitWallEvent, HitByBulletEvent, ScannedBotEvent


class RammerBot(Bot):
    def __init__(self) -> None:
        info = BotInfo.from_file("bot-config.json")
        super().__init__(bot_info=info)
        self.set_adjust_gun_for_body_turn(True)
        self.set_adjust_radar_for_gun_turn(True)

    async def run(self) -> None:
        self.set_turn_radar_right(360)
        while self.is_running():
            self.set_forward(400)
            self.set_turn_right(20)
            await self.go()

    async def on_scanned_bot(self, e: ScannedBotEvent) -> None:
        # Close in and fire bigger shots as we approach.
        bearing = self.gun_bearing_to(e.x, e.y)
        self.set_turn_gun_right(bearing)
        if self.get_gun_heat() == 0:
            distance = max(1.0, self.distance_to(e.x, e.y))
            power = max(0.5, min(3.0, 3.0 - (distance / 400)))
            self.set_fire(power)
        body_bearing = self.bearing_to(e.x, e.y)
        self.set_turn_right(body_bearing)
        self.set_forward(max(50, self.distance_to(e.x, e.y) - 40))

    async def on_hit_wall(self, e: HitWallEvent) -> None:
        self.set_turn_right(90)
        self.set_back(80)

    async def on_hit_by_bullet(self, e: HitByBulletEvent) -> None:
        self.set_turn_right(30)
        self.set_forward(120)


async def main() -> None:
    bot = RammerBot()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
