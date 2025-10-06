from discord import app_commands, Interaction, TextChannel, User
from discord.ext import commands
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

class MiscCog(commands.Cog):
    def __init__(self, bot: commands.Bot, tz: str):
        self.bot = bot
        self.tz = ZoneInfo(tz)

    async def _send(self, channel_id:int, text:str):
        ch = self.bot.get_channel(channel_id)
        if isinstance(ch, TextChannel):
            await ch.send(text)

    @app_commands.command(name="remind", description="Разовое напоминание через N минут")
    @app_commands.describe(minutes="Через сколько минут", text="Текст напоминания", target_user="Кого тегать (по умолчанию — себя)")
    async def remind(self, itx: Interaction, minutes: int, text: str, target_user: User | None = None):
        await itx.response.defer(ephemeral=True)
        if minutes < 1 or minutes > 7*24*60:
            await itx.followup.send("Минуты: 1..10080"); return
        ch = itx.channel
        if not isinstance(ch, TextChannel):
            await itx.followup.send("Нужен текстовый канал."); return
        when = datetime.now(self.tz) + timedelta(minutes=minutes)
        from ..scheduler import Scheduler  # доступ к инстансу получим через bot
        scheduler: Scheduler = self.bot._scheduler  # да, осознанный хак: присваиваем в bot
        mention = target_user.mention if target_user else itx.user.mention
        scheduler.add_once(
            self._send,
            when,
            {"channel_id": ch.id, "text": f"{mention} напоминаю: {text}"}
        )
        await itx.followup.send(f"Ок, напомню {mention} в {when.strftime('%Y-%m-%d %H:%M')}.")

    @app_commands.command(name="set_default_channel", description="Указать основной канал для дефолтных сообщений")
    async def set_default_channel(self, itx: Interaction, channel: TextChannel):
        await itx.response.defer(ephemeral=True)
        db = await self.bot._db.connect()  # type: ignore[attr-defined]
        try:
            await db.execute(
                "INSERT INTO guild_settings (guild_id, default_channel_id) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET default_channel_id=excluded.default_channel_id",
                (itx.guild_id, channel.id)
            )
            await db.commit()
        finally:
            await db.close()
        await itx.followup.send(f"Ок, основной канал: <#{channel.id}>")
