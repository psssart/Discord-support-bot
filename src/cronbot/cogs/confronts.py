from __future__ import annotations
from typing import Optional

from discord.ext import commands
from discord import app_commands, Interaction, RawReactionActionEvent, PartialEmoji, Message, Member

from ..services.confronts import ConfrontService

def _as_str_emoji(emoji: PartialEmoji | str) -> str:
    return str(emoji)

class ConfrontsCog(commands.Cog):
    def __init__(self, bot: commands.Bot, svc: ConfrontService):
        self.bot = bot
        self.svc = svc


    @app_commands.command(name="confront", description="Создать правило: user [+ reaction] -> counterReaction")
    @app_commands.describe(
        user="Пользователь, за которым следим (по умолчанию ты сам)",
        reaction="Эмодзи-триггер на его сообщениях (необязательно)",
        counterreaction="Эмодзи, которую поставит бот"
    )
    async def confront(self, itx: Interaction, user: Optional[Member] = None, reaction: Optional[str] = None, counterreaction: str = "🔫"):
        target_user = user or itx.user
        if not counterreaction or len(counterreaction.strip()) == 0:
            await itx.response.send_message("counterReaction обязателен. Не издевайся.", ephemeral=True)
            return

        trigger = reaction.strip() if reaction else None
        counter = counterreaction.strip()

        rid = await self.svc.add(
            guild_id=itx.guild_id,
            target_user_id=target_user.id,
            trigger_reaction=trigger,
            counter_reaction=counter,
            created_by=itx.user.id
        )
        txt = f"Добавлено правило #{rid}: <@{target_user.id}> " + (f"+ `{trigger}` " if trigger else "(все сообщения) ") + f"→ `{counter}`"
        await itx.response.send_message(txt, ephemeral=True)

    @app_commands.command(name="confront_list", description="Показать все правила для этого сервера")
    async def confront_list(self, itx: Interaction):
        rows = await self.svc.list(itx.guild_id)
        if not rows:
            await itx.response.send_message("Пусто. Ни одной пассивно-агрессивной автоматики.", ephemeral=True)
            return
        lines = []
        for r in rows:
            who = f"<@{r['target_user_id']}>"
            trig = f"`{r['trigger_reaction']}`" if r['trigger_reaction'] else "все сообщения"
            lines.append(f"#{r['id']}: {who} — {trig} → `{r['counter_reaction']}` (by <@{r['created_by']}>)")
        await itx.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="confront_remove", description="Удалить правило по id")
    @app_commands.describe(id="ID правила из /confront_list")
    async def confront_remove(self, itx: Interaction, id: int):
        ok = await self.svc.remove(itx.guild_id, id)
        if ok:
            await itx.response.send_message(f"Удалено правило #{id}. Токсичности стало меньше на пикограмм.", ephemeral=True)
        else:
            await itx.response.send_message("Не нашёл такое правило. Проверяй id.", ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        if not payload.guild_id:
            return

        # реакции самого бота не триггерят
        if payload.user_id == self.bot.user.id:
            return

        # достаём сообщение и автора
        channel = self.bot.get_channel(payload.channel_id) or await self.bot.fetch_channel(payload.channel_id)
        try:
            msg = await channel.fetch_message(payload.message_id)
        except Exception:
            return

        if not msg.author:
            return

        # берём все конронфты гильдии и фильтруем по автору и триггеру
        rows = await self.svc.get_for_guild(payload.guild_id)
        if not rows:
            return

        trig_emoji = _as_str_emoji(payload.emoji)
        for r in rows:
            if r["target_user_id"] != msg.author.id:
                continue
            if not r["trigger_reaction"]:
                # это правило не про реакции, оно про любые сообщения
                continue
            if r["trigger_reaction"] != trig_emoji:
                continue
            try:
                await msg.add_reaction(r["counter_reaction"])
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        # DM не трогаем, самого бота не трогаем
        if message.guild is None or message.author.bot:
            return

        rows = await self.svc.get_for_guild(message.guild.id)
        if not rows:
            return

        for r in rows:
            if r["target_user_id"] != message.author.id:
                continue
            # для правил без триггер-реакции: срабатывает на каждое сообщение
            if r["trigger_reaction"] is not None:
                continue
            try:
                await message.add_reaction(r["counter_reaction"])
            except Exception:
                pass
