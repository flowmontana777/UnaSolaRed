import os
import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =====================================
# CONFIGURACION
# =====================================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "5864523026")

GROUP_LINK = "https://t.me/+slI1SJL6HIQ4Nzcx"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =====================================
# BANCOS
# =====================================

BANKS = {
    "chase": "JPMorgan Chase",
    "boa": "Bank of America",
    "wells": "Wells Fargo",
    "citi": "Citibank",
    "capital": "Capital One",
    "credit": "Credit Union",
}

BANK_SERVICES = {
    "account": "Información y apertura de cuentas",
    "cards": "Consultas sobre tarjetas",
    "transfers": "Transferencias",
    "statements": "Estados de cuenta",
    "online": "Banca en línea y soporte",
    "other": "Otra consulta bancaria",
}


# =====================================
# OTROS SERVICIOS
# =====================================

SERVICES = {
    "remesas": "Envíos y remesas",
    "pagos": "Pago de servicios",
    "amazon": "Amazon",
    "apple": "Apple / iCloud",
    "vuelos": "Vuelos",
    "digital": "Digital Money",
}

TOOLS = {
    "profiles": "Perfiles",
    "authorized": "Herramientas autorizadas",
    "support": "Soporte técnico",
}


# =====================================
# MENU PRINCIPAL
# =====================================

def main_menu():

    keyboard = [
        [
            InlineKeyboardButton(
                "💚 Ser Parte de UnaRed",
                url=GROUP_LINK,
            )
        ],
        [
            InlineKeyboardButton(
                "🏦 Bancos",
                callback_data="menu_banks",
            ),
            InlineKeyboardButton(
                "💸 Envíos y remesas",
                callback_data="remesas",
            ),
        ],
        [
            InlineKeyboardButton(
                "🧾 Pago de servicios",
                callback_data="pagos",
            ),
            InlineKeyboardButton(
                "🛒 Amazon",
                callback_data="amazon",
            ),
        ],
        [
            InlineKeyboardButton(
                "📱 Apple / iCloud",
                callback_data="apple",
            ),
            InlineKeyboardButton(
                "✈️ Vuelos",
                callback_data="vuelos",
            ),
        ],
        [
            InlineKeyboardButton(
                "🧰 Herramientas",
                callback_data="menu_tools",
            ),
            InlineKeyboardButton(
                "🎵 Digital Money",
                callback_data="digital",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =====================================
# MENU DE BANCOS
# =====================================

def banks_menu():

    keyboard = [
        [
            InlineKeyboardButton(
                "🏦 JPMorgan Chase",
                callback_data="bank_chase",
            )
        ],
        [
            InlineKeyboardButton(
                "🏦 Bank of America",
                callback_data="bank_boa",
            )
        ],
        [
            InlineKeyboardButton(
                "🏦 Wells Fargo",
                callback_data="bank_wells",
            )
        ],
        [
            InlineKeyboardButton(
                "🏦 Citibank",
                callback_data="bank_citi",
            )
        ],
        [
            InlineKeyboardButton(
                "🏦 Capital One",
                callback_data="bank_capital",
            )
        ],
        [
            InlineKeyboardButton(
                "🏦 Credit Union",
                callback_data="bank_credit",
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Volver al menú",
                callback_data="menu_home",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =====================================
# SERVICIOS DE CADA BANCO
# =====================================

def bank_services_menu(bank_id):

    keyboard = [
        [
            InlineKeyboardButton(
                "🏦 Cuentas",
                callback_data=f"bankservice_{bank_id}_account",
            )
        ],
        [
            InlineKeyboardButton(
                "💳 Tarjetas",
                callback_data=f"bankservice_{bank_id}_cards",
            )
        ],
        [
            InlineKeyboardButton(
                "💸 Transferencias",
                callback_data=f"bankservice_{bank_id}_transfers",
            )
        ],
        [
            InlineKeyboardButton(
                "📄 Estados de cuenta",
                callback_data=f"bankservice_{bank_id}_statements",
            )
        ],
        [
            InlineKeyboardButton(
                "🔐 Banca en línea y soporte",
                callback_data=f"bankservice_{bank_id}_online",
            )
        ],
        [
            InlineKeyboardButton(
                "📩 Otra consulta",
                callback_data=f"bankservice_{bank_id}_other",
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Volver a bancos",
                callback_data="menu_banks",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =====================================
# MENU DE HERRAMIENTAS
# =====================================

def tools_menu():

    keyboard = [
        [
            InlineKeyboardButton(
                "👤 Perfiles",
                callback_data="tool_profiles",
            )
        ],
        [
            InlineKeyboardButton(
                "🧰 Herramientas autorizadas",
                callback_data="tool_authorized",
            )
        ],
        [
            InlineKeyboardButton(
                "🛠️ Soporte técnico",
                callback_data="tool_support",
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Volver al menú",
                callback_data="menu_home",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =====================================
# INICIO DEL BOT CON PORTADA
# =====================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    context.user_data.clear()

    welcome = (
        "💚 UNARED | LA RED QUE MUEVE TU DINERO\n\n"
        "Todos tus servicios en un solo lugar.\n"
        "Selecciona la opción que necesitas y nuestro equipo "
        "recibirá tu solicitud.\n\n"
        "🔒 No compartas contraseñas ni códigos de seguridad."
    )

    photo_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "assets",
        "unared_portada.jpeg",
    )

    if os.path.isfile(photo_path):

        with open(photo_path, "rb") as photo:

            await update.effective_message.reply_photo(
                photo=photo,
                caption=welcome,
                reply_markup=main_menu(),
            )

    else:

        await update.effective_message.reply_text(
            welcome,
            reply_markup=main_menu(),
        )


# =====================================
# SOLICITAR DETALLES
# =====================================

async def ask_for_details(
    query,
    context,
    service,
):

    context.user_data["service"] = service
    context.user_data["waiting_detail"] = True

    await query.message.reply_text(
        f"💚 UNA RED | {service}\n\n"
        "Escribe qué necesitas y nuestro equipo "
        "recibirá tu solicitud.\n\n"
        "⚠️ No envíes contraseñas, números completos "
        "de tarjetas, SSN, códigos OTP ni datos "
        "bancarios confidenciales.\n\n"
        "Escribe /cancel para cancelar."
    )


# =====================================
# BOTONES
# =====================================

async def select_option(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    choice = query.data

    # VOLVER AL MENU PRINCIPAL

    if choice == "menu_home":

        context.user_data.clear()

        await query.message.reply_text(
            "💚 UNARED | MENÚ PRINCIPAL\n\n"
            "LA RED QUE MUEVE TU DINERO.",
            reply_markup=main_menu(),
        )

        return

    # MENU DE BANCOS

    if choice == "menu_banks":

        await query.message.reply_text(
            "🏦 UNARED | SERVICIOS BANCARIOS\n\n"
            "Selecciona tu banco:",
            reply_markup=banks_menu(),
        )

        return

    # MENU DE HERRAMIENTAS

    if choice == "menu_tools":

        await query.message.reply_text(
            "🧰 UNARED | CENTRO DE HERRAMIENTAS\n\n"
            "Selecciona una herramienta:",
            reply_markup=tools_menu(),
        )

        return

    # SELECCIONAR BANCO

    if choice.startswith("bank_"):

        bank_id = choice.replace("bank_", "", 1)

        bank_name = BANKS.get(bank_id)

        if not bank_name:

            await query.message.reply_text(
                "Banco no disponible."
            )

            return

        await query.message.reply_text(
            f"🏦 UNARED | {bank_name}\n\n"
            "Selecciona el servicio que necesitas:",
            reply_markup=bank_services_menu(bank_id),
        )

        return

    # SERVICIOS ESPECIFICOS DE LOS BANCOS

    if choice.startswith("bankservice_"):

        parts = choice.split("_")

        if len(parts) != 3:
            return

        bank_id = parts[1]
        service_id = parts[2]

        bank_name = BANKS.get(bank_id)
        bank_service = BANK_SERVICES.get(service_id)

        if not bank_name or not bank_service:

            await query.message.reply_text(
                "Servicio no disponible."
            )

            return

        await ask_for_details(
            query,
            context,
            f"{bank_name} - {bank_service}",
        )

        return

    # HERRAMIENTAS

    if choice.startswith("tool_"):

        tool_id = choice.replace("tool_", "", 1)

        service = TOOLS.get(tool_id)

        if service:

            await ask_for_details(
                query,
                context,
                service,
            )

        else:

            await query.message.reply_text(
                "Herramienta no disponible."
            )

        return

    # OTROS SERVICIOS

    service = SERVICES.get(choice)

    if service:

        await ask_for_details(
            query,
            context,
            service,
        )

        return

    await query.message.reply_text(
        "Opción no disponible."
    )


# =====================================
# RECIBIR SOLICITUDES
# =====================================

async def receive_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not context.user_data.get("waiting_detail"):

        await update.message.reply_text(
            "Selecciona primero un servicio:",
            reply_markup=main_menu(),
        )

        return

    detail = update.message.text.strip()

    if not detail:

        await update.message.reply_text(
            "Escribe los detalles de tu solicitud."
        )

        return

    if len(detail) > 3000:

        await update.message.reply_text(
            "Tu mensaje es demasiado largo. "
            "Envíalo en menos de 3000 caracteres."
        )

        return

    user = update.effective_user

    service = context.user_data.get(
        "service",
        "No especificado",
    )

    message = (
        "💚 NUEVA SOLICITUD - UNARED\n\n"
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
            "Nuestro equipo de UnaRed recibió tu mensaje.\n"
            "Gracias por confiar en nosotros. 💚",
            reply_markup=main_menu(),
        )

    except Exception:

        logger.exception(
            "Error enviando solicitud al administrador."
        )

        await update.message.reply_text(
            "❌ No pudimos enviar tu solicitud "
            "en este momento. Inténtalo más tarde."
        )


# =====================================
# CANCELAR SOLICITUD
# =====================================

async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    context.user_data.clear()

    await update.message.reply_text(
        "❌ Solicitud cancelada.\n\n"
        "Puedes comenzar nuevamente:",
        reply_markup=main_menu(),
    )


# =====================================
# ERRORES
# =====================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    logger.error(
        "Error procesando una actualización:",
        exc_info=context.error,
    )


# =====================================
# EJECUTAR BOT
# =====================================

def main():

    if not TOKEN:

        raise RuntimeError(
            "Falta configurar TELEGRAM_BOT_TOKEN en Railway."
        )

    if not ADMIN_CHAT_ID:

        raise RuntimeError(
            "Falta configurar ADMIN_CHAT_ID en Railway."
        )

    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("cancel", cancel)
    )

    app.add_handler(
        CallbackQueryHandler(select_option)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            receive_request,
        )
    )

    app.add_error_handler(error_handler)

    print("💚 UnaRed Bot está funcionando.")

    app.run_polling()


if __name__ == "__main__":
    main()
