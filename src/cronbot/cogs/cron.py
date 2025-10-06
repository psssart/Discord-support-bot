from discord import app_commands, Interaction, TextChannel, User
from discord.ext import commands
from ..services.reminders import ReminderService, PRESETS
from ..scheduler import Scheduler

class CronCog(commands.Cog):
    def __init__(self, bot: commands.Bot, service: ReminderService, scheduler: Scheduler):
        self.bot = bot
        self.service = service
        self.scheduler = scheduler

    async def _send(self, channel_id:int, text:str, guild_id:int|None=None):
        from ..services.phrases import PhraseService
        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, TextChannel):
            return
        if text == "__RANDOM_PHRASE__":
            phrase = await PhraseService(self.bot._db).get_random(guild_id or channel.guild.id)  # type: ignore[attr-defined]
            if phrase is None:
                phrase = "Добавь фразы через /phrase_add"
            await channel.send(phrase)
        else:
            await channel.send(text)

    @app_commands.command(name="addcron", description="Добавить повторяющееся сообщение")
    @app_commands.describe(preset="everyday, weekdays, weekend, mon..sun", time="HH:MM", text="Текст", channel="Канал",  target_user="Кого тегать (по умолчанию — создателя)")
    @app_commands.choices(preset=[app_commands.Choice(name=k, value=k) for k in PRESETS])
    async def addcron(self, itx: Interaction, preset: app_commands.Choice[str], time: str, text: str, channel: TextChannel | None = None, target_user: User | None = None):
        await itx.response.defer(ephemeral=True)
        ch = channel or itx.channel
        if not isinstance(ch, TextChannel):
            await itx.followup.send("Нужен текстовый канал.")
            return
        try:
            rowid = await self.service.add_cron(
                itx.guild_id,
                ch.id,
                itx.user.id,
                preset.value,
                time,
                text,
                target_user.id if target_user else None
            )
        except ValueError as e:
            await itx.followup.send(str(e)); return

        # запланировать
        expr = PRESETS[preset.value]
        h, m = map(int, time.split(":"))
        mention_text = f"<@{target_user.id}> {text}" if target_user else f"<@{itx.user.id}> {text}"
        self.scheduler.add_cron(
            job_id=f"cron:{rowid}",
            send_fn=self._send,
            hour=h, minute=m, expr=expr,
            payload={"channel_id": ch.id, "text": mention_text, "guild_id": itx.guild_id},
        )
        await itx.followup.send(
            f"Создано: ID `{rowid}`, {preset.value} {time}, канал <#{ch.id}>, "
            f"тег: {target_user.mention if target_user else itx.user.mention}"
        )

    @app_commands.command(name="listcrons", description="Список кронов")
    async def listcrons(self, itx: Interaction):
        await itx.response.defer(ephemeral=True)
        rows = await self.service.list_crons(itx.guild_id)
        if not rows:
            await itx.followup.send("Пусто.")
            return
        lines = [f"ID `{r['id']}` | {r['preset']} {r['time_h']:02d}:{r['time_m']:02d} [{r['tz']}] | <#{r['channel_id']}> | {r['text']}" for r in rows]
        await itx.followup.send("\n".join(lines))

    @app_commands.command(name="delcron", description="Удалить по ID")
    @app_commands.describe(id="ID из /listcrons")
    async def delcron(self, itx: Interaction, id: int):
        await itx.response.defer(ephemeral=True)
        ok = await self.service.delete_cron(itx.guild_id, id)
        self.scheduler.remove(f"cron:{id}")
        await itx.followup.send("Удалено." if ok else "Не нашёл такой ID.")
