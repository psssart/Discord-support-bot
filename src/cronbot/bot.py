# src/cronbot/bot.py
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Callable, Awaitable

import aiosqlite
from discord import Intents, Object, TextChannel
from discord.ext import commands

from .config import Settings
from .logging_setup import setup_logging
from .db import Database
from .scheduler import Scheduler
from .services.reminders import ReminderService, PRESETS, parse_hhmm
from .services.phrases import PhraseService
from .cogs.cron import CronCog
from .cogs.misc import MiscCog
from .cogs.phrases import PhrasesCog
from .services.confronts import ConfrontService
from .cogs.confronts import ConfrontsCog

RANDOM_MARKER = "__RANDOM_PHRASE__"


def _make_send_fn(bot: commands.Bot, phrase_svc: PhraseService) -> Callable[..., Awaitable[None]]:
    """
    Возвращает async-функцию для APScheduler:
      _send(channel_id:int, text:str, guild_id:int|None=None)
    Заменяет маркер на случайную фразу.
    """
    async def _send(channel_id: int, text: str, guild_id: Optional[int] = None) -> None:
        ch = bot.get_channel(channel_id)
        if not isinstance(ch, TextChannel):
            return

        if text == RANDOM_MARKER:
            gid = guild_id or (ch.guild.id if ch and ch.guild else None)
            phrase = await phrase_svc.get_random(gid) if gid else None
            await ch.send(phrase or "Добавь фразы через /phrase_add")
        else:
            await ch.send(text)

    return _send


async def _resolve_default_channel_id(bot: commands.Bot, guild) -> Optional[int]:
    """
    Основной канал: guild_settings.default_channel_id → system_channel → первый доступный текстовый.
    """
    db: Database = bot._db  # type: ignore[attr-defined]
    conn = await db.connect()
    try:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT default_channel_id FROM guild_settings WHERE guild_id = ?",
            (guild.id,)
        )
        row = await cur.fetchone()
        if row and row["default_channel_id"]:
            return int(row["default_channel_id"])
    finally:
        await conn.close()

    me = guild.me
    if guild.system_channel and guild.system_channel.permissions_for(me).send_messages:  # type: ignore[arg-type]
        return guild.system_channel.id

    for ch in guild.text_channels:
        if ch.permissions_for(me).send_messages:  # type: ignore[arg-type]
            return ch.id

    return None


async def _ensure_default_phrase_cron(
    bot: commands.Bot,
    guild,
    cfg: Settings,
    db: Database,
    scheduler: Scheduler,
    phrase_svc: PhraseService,
    send_fn: Callable[..., Awaitable[None]],
) -> None:
    """
    Гарантирует наличие дефолтного крона с рандомной фразой и синхронизирует его время из конфига.
    """
    log = logging.getLogger("cronbot")

    if not cfg.DEFAULT_PHRASE_ENABLED:
        return

    # сид фраз для гильдии, если пусто
    try:
        inserted = await phrase_svc.seed_if_empty(guild.id, cfg.DEFAULT_PHRASES)
        if inserted:
            log.info("Seeded %d phrases for guild %s", inserted, guild.id)
    except Exception as e:
        log.exception("Failed to seed phrases for guild %s: %s", guild.id, e)

    # найти существующий дефолтный крон (по маркеру)
    conn = await db.connect()
    try:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT * FROM crons WHERE guild_id = ? AND text = ? LIMIT 1",
            (guild.id, RANDOM_MARKER),
        )
        row = await cur.fetchone()
    finally:
        await conn.close()

    # парсим время из конфига
    h, m = parse_hhmm(cfg.DEFAULT_PHRASE_TIME)
    expr = PRESETS[cfg.DEFAULT_PHRASE_PRESET]

    if row is None:
        ch_id = await _resolve_default_channel_id(bot, guild)
        if ch_id is None:
            log.warning("No writable channel in guild %s; skipping default phrase cron", guild.id)
            return

        conn = await db.connect()
        try:
            await conn.execute(
                "INSERT INTO crons (guild_id, channel_id, user_id, preset, time_h, time_m, tz, text, targetUser, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    guild.id,
                    ch_id,
                    bot.user.id,                        # creator — сам бот
                    cfg.DEFAULT_PHRASE_PRESET,
                    h,
                    m,
                    scheduler.tz.key,
                    RANDOM_MARKER,
                    None,
                    datetime.utcnow().isoformat(),
                ),
            )
            await conn.commit()
            cur = await conn.execute("SELECT last_insert_rowid()")
            rid = (await cur.fetchone())[0]
        finally:
            await conn.close()

        scheduler.add_cron(
            job_id=f"cron:{rid}",
            send_fn=send_fn,
            hour=h,
            minute=m,
            expr=expr,
            payload={"channel_id": ch_id, "text": RANDOM_MARKER, "guild_id": guild.id},
        )
        log.info("Default phrase cron created for guild %s at %02d:%02d", guild.id, h, m)
        return

    # есть запись — обновим время/пресет при расхождении
    need_update = (row["time_h"] != h) or (row["time_m"] != m) or (row["preset"] != cfg.DEFAULT_PHRASE_PRESET)
    if need_update:
        conn = await db.connect()
        try:
            await conn.execute(
                "UPDATE crons SET preset = ?, time_h = ?, time_m = ? WHERE id = ?",
                (cfg.DEFAULT_PHRASE_PRESET, h, m, row["id"]),
            )
            await conn.commit()
        finally:
            await conn.close()

    # запланировать или пересоздать джобу (remove внутри add_cron уже делается)
    scheduler.add_cron(
        job_id=f"cron:{row['id']}",
        send_fn=send_fn,
        hour=h,
        minute=m,
        expr=expr,
        payload={"channel_id": row["channel_id"], "text": RANDOM_MARKER, "guild_id": guild.id},
    )
    if need_update:
        log.info("Default phrase cron updated for guild %s to %02d:%02d", guild.id, h, m)


async def create_bot() -> commands.Bot:
    """
    Сборка бота: DI инфраструктуры, регистрация когов, восстановление задач, дефолтный крон.
    """
    setup_logging()
    log = logging.getLogger("cronbot")
    cfg = Settings()

    intents = Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents)

    # инфраструктура
    db = Database(cfg.DB_PATH)
    scheduler = Scheduler(cfg.TZ)
    reminder_service = ReminderService(db, cfg.TZ)
    phrase_service = PhraseService(db)
    send_fn = _make_send_fn(bot, phrase_service)
    confront_service = ConfrontService(db)

    # простой DI в объект бота
    bot._cfg = cfg                 # type: ignore[attr-defined]
    bot._db = db                   # type: ignore[attr-defined]
    bot._scheduler = scheduler     # type: ignore[attr-defined]
    bot._service = reminder_service# type: ignore[attr-defined]
    bot._phrases = phrase_service  # type: ignore[attr-defined]
    bot._send_fn = send_fn         # type: ignore[attr-defined]
    bot._confronts = confront_service # type: ignore[attr-defined]

    # коги
    await bot.add_cog(CronCog(bot, reminder_service, scheduler))
    await bot.add_cog(MiscCog(bot, cfg.TZ))
    await bot.add_cog(PhrasesCog(bot, phrase_service))
    await bot.add_cog(ConfrontsCog(bot, confront_service))

    @bot.event
    async def on_ready():
        log.info("Logged in as %s", bot.user)

        # восстановить все задачи из БД
        async for row in db.iter_crons():
            scheduler.add_cron(
                job_id=f"cron:{row['id']}",
                send_fn=send_fn,
                hour=row["time_h"],
                minute=row["time_m"],
                expr=PRESETS[row["preset"]],
                payload={
                    "channel_id": row["channel_id"],
                    "text": row["text"],
                    "guild_id": row["guild_id"],
                },
            )

        # дефолтный крон с фразами на основе конфига (создать/обновить)
        for guild in bot.guilds:
            await _ensure_default_phrase_cron(
                bot=bot,
                guild=guild,
                cfg=cfg,
                db=db,
                scheduler=scheduler,
                phrase_svc=phrase_service,
                send_fn=send_fn,
            )

        scheduler.start()

        # sync команд: для разработки можно указать GUILD_IDS в .env
        if cfg.GUILD_IDS:
            for gid in cfg.GUILD_IDS:
                await bot.tree.sync(guild=Object(id=gid))
                log.info("Slash commands synced for guild %s", gid)
        else:
            await bot.tree.sync(guild=None)
            log.info("Slash commands synced globally")

    return bot
