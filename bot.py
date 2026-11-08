
import os
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "5864523026")

GROUP_LINK = "https://t.me/+slI1SJL6HIQ4Nzcx"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

BANKS = {
    "chase": "JPMorgan Chase",
    "boa": "Bank of America",
    "wells": "Wells Fargo",
    "citi": "Citibank",
    "capital": "Capital One",
    "credit": "Credit Union",
}

TOOLS = {
    "profiles": "👤 Perfiles",
    "authorized": "🧰 Herramientas autorizadas",
    "support": "🛠️ Soporte técnico",
}

SERVICES = {
    "remesas": "💸 Envíos y remesas",
    "pagos": "🧾 Pago de servicios",
    "amazon": "🛒 Amazon",
    "apple": "📱 Apple / iCloud",
    "vuelos": "✈️ Vuelos",
    "digital": "🎵 Digital Money",
}


def main_menu():
    keyboard = [
        [InlineKeyboardButton("💚 Ser Parte de UnaRed", url="https://t.me/+slI1SJL6HIQ4Nzcx"),
        [
            InlineKeyboardButton("🏦 Bancos", callback_data="menu_banks"),
            InlineKeyboardButton("💸 Envíos y remesas", callback_data="remesas"),
        ],
        [
            InlineKeyboardButton("🧾 Pago de servicios", callback_data="pagos"),
            InlineKeyboardButton("🛒 Amazon", callback_data="amazon"),
        ],
        [
            InlineKeyboardButton("📱 Apple / iCloud", callback_data="apple"),
            InlineKeyboardButton("✈️ Vuelos", callback_data="vuelos"),
        ],
        [
            InlineKeyboardButton("🧰 Herramientas", callback_data="menu_tools"),
            InlineKeyboardButton("🎵 Digital Money", callback_data="digital"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def banks_menu():
    keyboard = [
        [InlineKeyboardButton("JPMorgan Chase", callback_data="bank_chase")],
        [InlineKeyboardButton("Bank of America", callback_data="bank_boa")],
        [InlineKeyboardButton("Wells Fargo", callback_data="bank_wells")],
        [InlineKeyboardButton("Citibank", callback_data="bank_citi")],
        [InlineKeyboardButton("Capital One", callback_data="bank_capital")],
        [InlineKeyboardButton("Credit Union", callback_data="bank_credit")],
        [InlineKeyboardButton("⬅️ Volver al menú", callback_data="menu_home")],
    ]
    return InlineKeyboardMarkup(keyboard)


def tools_menu():
    keyboard = [
        [InlineKeyboardButton("👤 Perfiles", callback_data="tool_profiles")],
        [InlineKeyboardButton("🧰 Herramientas autorizadas", callback_data="tool_authorized")],
        [InlineKeyboardButton("🛠️ Soporte técnico", callback_data="tool_support")],
        [InlineKeyboardButton("⬅️ Volver al menú", callback_data="menu_home")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "💚 BIENVENIDO A UNARED\n\n"
        "LA RED QUE MUEVE TU DINERO.\n\n"
        "Selecciona el servicio que necesitas.\n"
        "Nuestro equipo recibirá tu solicitud.",
        reply_markup=main_menu(),
    )


async def select_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    choice = query.data

    if choice == "menu_home":
        context.user_data.clear()
        await query.message.reply_text(
            "💚 Menú principal de UnaRed:",
            reply_markup=main_menu(),
        )
        return

    if choice == "menu_banks":
        await query.message.reply_text(
            "🏦 Selecciona el banco:",
            reply_markup=banks_menu(),
        )
        return

    if choice == "menu_tools":
        await query.message.reply_text(
            "🧰 Selecciona una herramienta:",
            reply_markup=tools_menu(),
        )
        return

    if choice.startswith("bank_"):
        bank_id = choice.replace("bank_", "")
        service = BANKS.get(bank_id)

    elif choice.startswith("tool_"):
        tool_id = choice.replace("tool_", "")
        service = TOOLS.get(tool_id)

    else:
        service = SERVICES.get(choice)

    if not service:
        await query.message.reply_text("Opción no disponible.")
        return

    context.user_data["service"] = service
    context.user_data["waiting_detail"] = True

    await query.message.reply_text(
        f"✅ Seleccionaste: {service}\n\n"
        "Escribe qué necesitas para que nuestro equipo "
        "reciba tu solicitud.\n\n"
        "⚠️ No envíes contraseñas, números completos de tarjetas, "
        "SSN, códigos OTP ni datos bancarios confidenciales.\n\n"
        "Escribe /cancel para cancelar."
    )


async def receive_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_detail"):
        await update.message.reply_text(
            "Selecciona primero un servicio:",
            reply_markup=main_menu(),
        )
        return

    detail = update.message.text.strip()

    if not detail:
        await update.message.reply_text("Escribe los detalles de tu solicitud.")
        return

    if len(detail) > 3000:
        await update.message.reply_text("El mensaje es demasiado largo.")
        return

    user = update.effective_user
    service = context.user_data.get("service", "No especificado")

    message = (
        "📩 NUEVA SOLICITUD - UNARED\n\n"
        f"📌 Servicio: {service}\n"
        f"👤 Cliente: {user.full_name}\n"
        f"🔹 Usuario: @{user.username or 'Sin usuario'}\n"
        f"🆔 ID: {user.id}\n\n"
        f"📝 Solicitud:\n{detail}"
    )

    try:
        await context.bot.send_message(
            chat_id=int(ADMIN_CHAT_ID),
            text=message,
        )

        context.user_data.clear()

        await update.message.reply_text(
            "✅ ¡Solicitud enviada correctamente!\n\n"
            "Nuestro equipo de UnaRed recibió tu mensaje. 💚",
            reply_markup=main_menu(),
        )

    except Exception:
        logging.exception("Error enviando solicitud al administrador.")
        await update.message.reply_text(
            "❌ No pudimos enviar tu solicitud. Inténtalo más tarde."
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Solicitud cancelada. 💚",
        reply_markup=main_menu(),
    )


def main():
    if not TOKEN:
        raise RuntimeError("Falta configurar TELEGRAM_BOT_TOKEN.")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(select_option))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_request)
    )

    print("UnaRed Bot está funcionando...")
    app.run_polling()


if __name__ == "__main__":
    main()
