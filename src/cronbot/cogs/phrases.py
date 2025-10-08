from discord.ext import commands
from discord import app_commands, Interaction
from ..services.phrases import PhraseService

class PhrasesCog(commands.Cog):
    def __init__(self, bot: commands.Bot, svc: PhraseService):
        self.bot = bot
        self.svc = svc

    @app_commands.command(name="phrase_add", description="Добавить фразу в список для рандома")
    async def phrase_add(self, itx: Interaction, text: str):
        await itx.response.defer(ephemeral=True)
        pid = await self.svc.add_phrase(itx.guild_id, text)
        await itx.followup.send(f"Добавил фразу #{pid}.")

    @app_commands.command(name="phrase_list", description="Показать фразы")
    async def phrase_list(self, itx: Interaction):
        await itx.response.defer(ephemeral=True)
        rows = await self.svc.list_phrases(itx.guild_id)
        if not rows:
            await itx.followup.send("Список пуст. Добавь через /phrase_add.")
            return
        lines = [f"`{r['id']}`: {r['text']}" for r in rows]
        await itx.followup.send("\n".join(lines))

    @app_commands.command(name="phrase_del", description="Удалить фразу по ID")
    async def phrase_del(self, itx: Interaction, id: int):
        await itx.response.defer(ephemeral=True)
        ok = await self.svc.delete_phrase(itx.guild_id, id)
        await itx.followup.send("Удалил." if ok else "Такой фразы нет.")

    @commands.hybrid_command(name="phrase", description="Выдать случайную фразу")
    async def phrase(self, ctx:commands.Context):
        if ctx.guild is None:
            await ctx.reply("Эта команда доступна только на сервере.")
            return
        text = await self.phrases.get_random(ctx.guild.id)
        if text is None:
            await ctx.reply("Список фраз пуст.")
        else:
            await ctx.reply(text)
