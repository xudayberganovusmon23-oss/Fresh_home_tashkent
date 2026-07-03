import logging
import re
from datetime import datetime

import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

TOKEN = "8929048013:AAG_jBIx3ZQbr-yMPST0S0Lv2Tiju0oev8g"
CHAT_ID = "5626439246"
CBU_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_rates() -> list[dict]:
    async with aiohttp.ClientSession() as session:
        async with session.get(CBU_URL, timeout=10) as resp:
            return await resp.json()


def format_single(item: dict) -> str:
    code = item["Ccy"]
    name = item["CcyNm_UZ"]
    rate = item["Rate"]
    date = item["Date"]
    diff = item.get("Diff", "")
    lines = [
        f"💱 <b>{code}</b> — {name}",
        "━━━━━━━━━━━━━━━━━━━",
        f"💰 <b>1</b> {code} = <b>{rate}</b> so'm",
    ]
    if diff:
        d = float(diff)
        arrow = "🟢" if d > 0 else "🔴"
        sign = "+" if d > 0 else ""
        lines.append(f"   {arrow} {sign}{d:.2f}")
    lines.extend(["", f"📅 {date}", "", "🔄 <i>Markaziy bank ma'lumotlari</i>"])
    return "\n".join(lines)


def format_all(data: list[dict]) -> list[str]:
    chunks = []
    chunk = [f"🌍 <b>Valyuta kurslari</b> | {datetime.now().strftime('%d.%m.%Y %H:%M')}", "━━━━━━━━━━━━━━━━━━━"]
    for item in data:
        code = item["Ccy"]
        name = item["CcyNm_UZ"]
        rate = item["Rate"]
        diff = item.get("Diff", "")
        arrow = ""
        if diff:
            d = float(diff)
            arrow = " 🟢" if d > 0 else " 🔴"
        line = f"<b>{code}</b> {name} — 1 {code} = {rate} so'm{arrow}"
        next_len = len("\n".join(chunk)) + len(line) + 1
        if next_len > 4000:
            chunk.append("")
            chunk.append("🔄 <i>Markaziy bank ma'lumotlari</i>")
            chunks.append("\n".join(chunk))
            chunk = [f"🌍 <b>Valyuta kurslari</b> (davomi)", "━━━━━━━━━━━━━━━━━━━"]
        chunk.append(line)
    chunk.append("")
    chunk.append("🔄 <i>Markaziy bank ma'lumotlari</i>")
    chunks.append("\n".join(chunk))
    return chunks


async def send_sticker(update: Update) -> None:
    sets = ["MONEY", "MoneyBag", "MONEYBAG", "CashMoney", "MoneyFace"]
    for name in sets:
        try:
            sticker_set = await update.message.bot.get_sticker_set(name)
            await update.message.reply_sticker(sticker_set.stickers[0].file_id)
            return
        except Exception:
            continue


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 <b>Valyuta kurslari botiga xush kelibsiz!</b>\n\n"
        "📌 <b>Komandalar:</b>\n"
        "  /kurs — barcha valyutalar\n"
        "  /start — bu xabar\n\n"
        "💡 <b>Yoki valyuta kodini yozing:</b>\n"
        "  Masalan: <code>USD</code>, <code>EUR</code>, <code>RUB</code>",
        parse_mode="HTML",
    )


async def kurs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Yuklanmoqda...")
    try:
        data = await get_rates()
        chunks = format_all(data)
        await msg.edit_text(chunks[0], parse_mode="HTML")
        for c in chunks[1:]:
            await update.message.reply_text(c, parse_mode="HTML")
    except Exception:
        logger.exception("Xatolik")
        await msg.edit_text("❌ Xatolik yuz berdi. Keyinroq urinib ko'ring.")


async def auto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("✅ Avtomatik xabar yoqildi (har kuni 09:00 da yuboriladi)")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    code = update.message.text.strip().upper()
    if not re.match(r"^[A-Z]{2,4}$", code):
        await update.message.reply_text(
            "❌ Noto'g'ri valyuta kodi. Masalan: <code>USD</code>, <code>EUR</code>, <code>RUB</code>",
            parse_mode="HTML",
        )
        return

    msg = await update.message.reply_text("⏳ Yuklanmoqda...")
    try:
        data = await get_rates()
        for item in data:
            if item["Ccy"] == code:
                text = format_single(item)
                await msg.edit_text(text, parse_mode="HTML")
                await send_sticker(update)
                return
        await msg.edit_text(f"❌ <code>{code}</code> topilmadi. Boshqa kod bilan urinib ko'ring.", parse_mode="HTML")
    except Exception:
        logger.exception("Xatolik")
        await msg.edit_text("❌ Xatolik yuz berdi. Keyinroq urinib ko'ring.")


async def scheduled_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        data = await get_rates()
        chunks = format_all(data)
        for c in chunks:
            await context.bot.send_message(chat_id=CHAT_ID, text=c, parse_mode="HTML")
    except Exception:
        logger.exception("Avtomatik xatolik")


def main() -> None:
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("kurs", kurs))
    app.add_handler(CommandHandler("auto", auto))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.job_queue.run_daily(scheduled_job, time=datetime.strptime("09:00", "%H:%M").time())

    logger.info("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
