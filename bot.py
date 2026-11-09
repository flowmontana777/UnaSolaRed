
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

# =====================================
# METODO DE PAGO UNARED
# =====================================

PAYMENT_WALLET = "TKn18e7RCxhzt9xPZ15JnDhs9kxvf7gsWm"

PAYMENT_MESSAGE = (
    "💚 UNARED | MÉTODO DE PAGO\n\n"
    "💵 Moneda: USDT\n"
    "🌐 Red: TRON (TRC20)\n\n"
    "💳 Dirección de pago:\n"
    f"{PAYMENT_WALLET}\n\n"
    "⚠️ IMPORTANTE:\n"
    "Envía únicamente USDT por la red TRC20.\n"
    "No utilices otra red.\n\n"
    "Después de realizar el pago, conserva tu "
    "comprobante para verificarlo con nuestro equipo."
)

# =====================================
# REGISTRO
# =====================================

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
    "digital": "Modo Digital",
}

REMITTANCE_APPS = {
    "remitly": "Remitly",
    "western": "Western Union",
    "taptap": "TapTap",
    "paypal": "PayPal",
    "moneygram": "MoneyGram",
    "boss": "Boss Money",
    "ria": "Ria",
}

PAYMENT_TYPES = {
    "house": "Pago de casa",
    "car": "Pago de carro",
    "phone": "Pago de teléfono",
    "card": "Pago de tarjeta",
    "loan": "Pago de préstamo",
    "light": "Pago de luz",
}

TOOLS = {
    "line": "Línea virtual para uso legítimo",
    "auth": "Soporte de autenticación y seguridad",
    "ssn_info": "Orientación sobre SSN y protección de identidad",
    "giftcards": "Tarjetas de regalo y pagos autorizados",
    "edit_upload": "Editar y subir documentos o papeles",
}

# =====================================
# BOTONES AUXILIARES
# =====================================

def more_button(service_id):
    return [
        InlineKeyboardButton(
            "ℹ️ Necesito saber de la Vuelta",
            callback_data=f"more_{service_id}",
        )
    ]


def back_button(destination="menu_home"):
    return [
        InlineKeyboardButton(
            "⬅️ Volver al menú principal",
            callback_data=destination,
        )
    ]


# =====================================
# MENU PRINCIPAL
# =====================================

def main_menu():
    keyboard = [
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
                "🍎 Apple",
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
                "📟 Modo Digital",
                callback_data="digital",
            ),
        ],
        [
            InlineKeyboardButton(
                "💚 Ser Parte de UnaRed",
                url=GROUP_LINK,
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =====================================
# MENU DE BANCOS
# =====================================

def banks_menu():
    keyboard = [
        [InlineKeyboardButton("🏦 JPMorgan Chase", callback_data="bank_chase")],
        [InlineKeyboardButton("🏦 Bank of America", callback_data="bank_boa")],
        [InlineKeyboardButton("🏦 Wells Fargo", callback_data="bank_wells")],
        [InlineKeyboardButton("🏦 Citibank", callback_data="bank_citi")],
        [InlineKeyboardButton("🏦 Capital One", callback_data="bank_capital")],
        [InlineKeyboardButton("🏦 Credit Union", callback_data="bank_credit")],
        more_button("banks"),
        back_button(),
    ]

    return InlineKeyboardMarkup(keyboard)


# =====================================
# SERVICIOS DE CADA BANCO
# =====================================

def bank_services_menu(bank_id):
    keyboard = [
        [InlineKeyboardButton("⏱️ Tiempo", callback_data=f"bankinfo_{bank_id}_tiempo")],
        [InlineKeyboardButton("💬 Trabajar ahora", url="https://t.me/flowmontana777")],
        back_button("menu_banks"),
    ]
    return InlineKeyboardMarkup(keyboard)


def bank_limit_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1", callback_data="banklimit_1"), InlineKeyboardButton("2", callback_data="banklimit_2"), InlineKeyboardButton("3", callback_data="banklimit_3")],
        [InlineKeyboardButton("4", callback_data="banklimit_4"), InlineKeyboardButton("5", callback_data="banklimit_5"), InlineKeyboardButton("6", callback_data="banklimit_6")],
        [InlineKeyboardButton("7", callback_data="banklimit_7"), InlineKeyboardButton("8", callback_data="banklimit_8"), InlineKeyboardButton("9", callback_data="banklimit_9")],
        [InlineKeyboardButton("⌫", callback_data="banklimit_back"), InlineKeyboardButton("0", callback_data="banklimit_0"), InlineKeyboardButton("Confirmar", callback_data="banklimit_done")],
    ])


# =====================================
# MENU AMAZON
# =====================================

def amazon_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "🛒 Tengo Amazon",
                callback_data="amazon_have",
            )
        ],
        [
            InlineKeyboardButton(
                "ℹ️ Tengo Amazon, pero necesito saber más",
                callback_data="amazon_info",
            )
        ],
        more_button("amazon"),
        back_button(),
    ]

    return InlineKeyboardMarkup(keyboard)


# =====================================
# MENU APPLE
# =====================================

def apple_menu():
    keyboard = [
        [InlineKeyboardButton("🍎 Tengo Apple", callback_data="apple_have")],
        [InlineKeyboardButton("ℹ️ Necesito saber más", callback_data="apple_info")],
        back_button(),
    ]
    return InlineKeyboardMarkup(keyboard)


# =====================================
# MENU DE VUELOS
# =====================================

def flights_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "✈️ Quiero solicitar un vuelo",
                callback_data="flight_request",
            )
        ],
        [
            InlineKeyboardButton(
                "ℹ️ Necesito más información",
                callback_data="more_flights",
            )
        ],
        back_button(),
    ]

    return InlineKeyboardMarkup(keyboard)


# =====================================
# MENU DE ENVIOS Y REMESAS
# =====================================

def remittances_menu():
    keyboard = [
        [InlineKeyboardButton("Remitly", callback_data="remit_remitly")],
        [InlineKeyboardButton("Western Union", callback_data="remit_western")],
        [InlineKeyboardButton("TapTap", callback_data="remit_taptap")],
        [InlineKeyboardButton("PayPal", callback_data="remit_paypal")],
        [InlineKeyboardButton("MoneyGram", callback_data="remit_moneygram")],
        [InlineKeyboardButton("Boss Money", callback_data="remit_boss")],
        [InlineKeyboardButton("Ria", callback_data="remit_ria")],
        more_button("remesas"),
        back_button(),
    ]

    return InlineKeyboardMarkup(keyboard)


def remittance_options_menu(app_id):
    keyboard = [
        [InlineKeyboardButton("Obtener", callback_data=f"remit_action_{app_id}_obtener")],
        [InlineKeyboardButton("Tiene Historial", callback_data=f"remit_action_{app_id}_historial")],
        back_button("remesas"),
    ]
    return InlineKeyboardMarkup(keyboard)


def dayler_payment_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Pagar US$150", callback_data="dayler_pay")]
    ])


def bill_amount_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1", callback_data="bill_digit_1"), InlineKeyboardButton("2", callback_data="bill_digit_2"), InlineKeyboardButton("3", callback_data="bill_digit_3")],
        [InlineKeyboardButton("4", callback_data="bill_digit_4"), InlineKeyboardButton("5", callback_data="bill_digit_5"), InlineKeyboardButton("6", callback_data="bill_digit_6")],
        [InlineKeyboardButton("7", callback_data="bill_digit_7"), InlineKeyboardButton("8", callback_data="bill_digit_8"), InlineKeyboardButton("9", callback_data="bill_digit_9")],
        [InlineKeyboardButton("⌫", callback_data="bill_backspace"), InlineKeyboardButton("0", callback_data="bill_digit_0"), InlineKeyboardButton("Confirmar", callback_data="bill_amount_done")],
    ])


def dayler_receipt_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Ya realicé el pago", callback_data="dayler_paid")]
    ])


def bot_catalog_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("BOT OTP", callback_data="botproduct_otp")],
        [InlineKeyboardButton("BOT SSN", callback_data="botproduct_ssn")],
        [InlineKeyboardButton("BOT CHECK", callback_data="botproduct_check")],
        back_button("menu_tools"),
    ])


# =====================================
# MENU DE PAGOS
# =====================================

def bills_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "💳 Quiero pagar",
                callback_data="bill_pay",
            )
        ],
        [InlineKeyboardButton("ℹ️ Necesito saber más de la vuelta", url="https://t.me/flowmontana777")],
        back_button(),
    ]

    return InlineKeyboardMarkup(keyboard)


# =====================================
# TIPOS DE PAGOS
# =====================================

def payment_types_menu():
    keyboard = [
        [InlineKeyboardButton("🏠 Casa", callback_data="pay_house")],
        [InlineKeyboardButton("🚗 Carro", callback_data="pay_car")],
        [InlineKeyboardButton("📱 Teléfono", callback_data="pay_phone")],
        [InlineKeyboardButton("💳 Tarjeta", callback_data="pay_card")],
        [InlineKeyboardButton("💰 Préstamo", callback_data="pay_loan")],
        [InlineKeyboardButton("💡 Luz", callback_data="pay_light")],
        more_button("pagos"),
        back_button("pagos"),
    ]

    return InlineKeyboardMarkup(keyboard)


# =====================================
# MENU DE HERRAMIENTAS
# =====================================

def tools_menu():
    keyboard = [
        [InlineKeyboardButton("📞 Alquilar Línea Dayler", callback_data="tool_dayler")],
        [InlineKeyboardButton("🤖 Comprar Bot", callback_data="tool_bots")],
        [InlineKeyboardButton("🔐 Soporte VoIP", callback_data="tool_auth")],
        [InlineKeyboardButton("🪪 SSN", callback_data="tool_ssn_info")],
        [InlineKeyboardButton("💳 Tarjetas", callback_data="tool_giftcards")],
        [InlineKeyboardButton("📄 Quiero Editar y Subir Papel", callback_data="tool_edit_upload")],
        more_button("tools"),
        back_button(),
    ]
    return InlineKeyboardMarkup(keyboard)


# =====================================
# SOLICITAR DETALLES
# =====================================

async def ask_for_details(query, context, service):
    context.user_data["service"] = service
    context.user_data["waiting_detail"] = True

    await query.message.reply_text(
        f"💚 UNARED | {service}\n\n"
        "Escribe qué necesitas y nuestro equipo "
        "recibirá tu solicitud.\n\n"
        "Escribe /cancel para cancelar."
    )


# =====================================
# INICIO DEL BOT CON PORTADA
# =====================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    welcome = (
        "💚 UNARED | LA RED QUE MUEVE TU DINERO\n\n"
        "Todos tus servicios en un solo lugar.\n"
        "Selecciona la opción que necesitas y nuestro equipo "
        "recibirá tu solicitud.\n\n"
    )

    await update.effective_message.reply_photo(
        photo="https://i.ibb.co/XfdhR6bS/photo-2026-11-09-01-28-36.jpg",
        caption=welcome,
        reply_markup=main_menu(),
    )


# =====================================
# BOTONES Y NAVEGACION
# =====================================

async def select_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    # BANCOS

    if choice == "menu_banks":
        await query.message.reply_photo(
            photo="https://i.ibb.co/sptC6Y0J/photo-2026-11-09-01-00-59.jpg",
            caption=(
                "🏦 UNARED | BANCOS\n\n"
                "Selecciona tu banco:"
            ),
            reply_markup=banks_menu(),
        )
        return

    if choice.startswith("banklimit_"):
        action = choice.replace("banklimit_", "", 1)
        value = context.user_data.get("bank_limit_value", "")
        if action.isdigit():
            if len(value) < 12:
                value += action
            context.user_data["bank_limit_value"] = value
            await query.edit_message_text(f"📊 Límite indicado: USD {value or '0'}", reply_markup=bank_limit_keyboard())
            return
        if action == "back":
            value = value[:-1]
            context.user_data["bank_limit_value"] = value
            await query.edit_message_text(f"📊 Límite indicado: USD {value or '0'}", reply_markup=bank_limit_keyboard())
            return
        if action == "done":
            if not value or int(value) <= 0:
                await query.answer("Introduce un límite mayor que cero.", show_alert=True)
                return
            bank_name = BANKS.get(context.user_data.get("bank_input_id"), "Banco")
            duration = context.user_data.get("bank_time_value", "No indicado")
            user = update.effective_user
            try:
                await context.bot.send_message(
                    chat_id=int(ADMIN_CHAT_ID),
                    text=f"DATOS BANCARIOS UNARED | Cliente: {user.full_name} | Banco: {bank_name} | Tiempo con el banco: {duration} | Límite: USD {value}"
                )
                context.user_data["bank_input_step"] = None
                context.user_data["bank_time_value"] = None
                await query.message.reply_text("✅ Tiempo y límite recibidos. Para continuar, pulsa Trabajar ahora.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 Trabajar ahora", url="https://t.me/flowmontana777")]]))
            except Exception:
                logger.exception("Error enviando límite bancario.")
                await query.message.reply_text("No pudimos enviar el dato. Inténtalo nuevamente.")
            return

    if choice.startswith("bankinfo_"):
        parts = choice.split("_")
        if len(parts) != 3:
            return
        bank_id, info_type = parts[1], parts[2]
        bank_name = BANKS.get(bank_id)
        if not bank_name or info_type not in ("tiempo", "limite"):
            await query.message.reply_text("Opción no disponible.")
            return
        if info_type == "tiempo":
            context.user_data.clear()
            context.user_data["bank_input_step"] = "time"
            context.user_data["bank_input_id"] = bank_id
            await query.message.reply_text(
                f"🏦 {bank_name}\n\nEscribe cuánto tiempo tienes con este banco (ejemplo: 2 años y 6 meses)."
            )
        else:
            context.user_data.clear()
            context.user_data["bank_input_step"] = "limit"
            context.user_data["bank_input_id"] = bank_id
            context.user_data["bank_limit_value"] = ""
            await query.message.reply_text(
                f"🏦 {bank_name}\\n\\nIntroduce el límite que aparece en tu cuenta con los botones numéricos y pulsa Confirmar.",
                reply_markup=bank_limit_keyboard(),
            )
        return
    if choice.startswith("bank_"):
        bank_id = choice.replace("bank_", "", 1)
        bank_name = BANKS.get(bank_id)

        if not bank_name:
            await query.message.reply_text("Banco no disponible.")
            return

        await query.message.reply_text(
            f"🏦 UNARED | {bank_name}\n\n"
            "Selecciona el servicio que necesitas:",
            reply_markup=bank_services_menu(bank_id),
        )
        return

    # AMAZON

    if choice == "amazon":
        await query.message.reply_photo(
            photo="https://i.ibb.co/21HDrxmJ/photo-2026-11-09-00-49-50.jpg",
            caption=(
                "🛒 UNARED | AMAZON\n\n"
                "Selecciona una opción:"
            ),
            reply_markup=amazon_menu(),
        )
        return

    if choice == "amazon_have":
        await ask_for_details(query, context, "Amazon - Tengo Amazon")
        return

    if choice == "amazon_info":
        await ask_for_details(
            query,
            context,
            "Amazon - Tengo Amazon, necesito más información",
        )
        return

    # APPLE

    if choice == "apple":
        await query.message.reply_photo(
            photo="https://i.ibb.co/nscvpdVp/photo-2026-11-09-01-02-28.jpg",
            caption=(
                "🍎 UNARED | APPLE\n\n"
                "Selecciona una opción:"
            ),
            reply_markup=apple_menu(),
        )
        return

    if choice == "apple_have":
        await ask_for_details(query, context, "Apple - Tengo Apple")
        return

    if choice == "apple_info":
        await ask_for_details(
            query,
            context,
            "Apple - Tengo Apple, necesito más información",
        )
        return

    # VUELOS

    if choice == "vuelos":
        await query.message.reply_photo(
            photo="https://i.ibb.co/pvwR93w6/Green-financial-brand-display-9c28aa1d-2-K.jpg",
            caption=(
                "✈️ UNARED | SERVICIOS DE VUELOS\n\n"
                "¿Qué necesitas?"
            ),
            reply_markup=flights_menu(),
        )
        return

    if choice == "flight_request":
        await ask_for_details(query, context, "Solicitud de vuelo")
        return

    # ENVIOS Y REMESAS

    if choice == "remesas":
        await query.message.reply_photo(
            photo="https://i.ibb.co/N67F70xw/photo-2026-11-09-01-22-27.jpg",
            caption=(
                "💸 UNARED | ENVÍOS Y REMESAS\n\n"
                "Selecciona la aplicación:"
            ),
            reply_markup=remittances_menu(),
        )
        return

    if choice.startswith("remit_action_"):
        parts = choice.split("_")
        if len(parts) == 4:
            app_id, action = parts[2], parts[3]
            app_name = REMITTANCE_APPS.get(app_id)
            if app_name and action in ("obtener", "historial"):
                action_label = "Obtener" if action == "obtener" else "Tiene Historial"
                await ask_for_details(
                    query,
                    context,
                    f"{app_name} - {action_label}",
                )
        return

    if choice.startswith("remit_"):
        app_id = choice.replace("remit_", "", 1)
        app_name = REMITTANCE_APPS.get(app_id)
        if app_name:
            await query.message.reply_text(
                f"💸 UNARED | {app_name}\n\nSelecciona una opción:",
                reply_markup=remittance_options_menu(app_id),
            )
        return

    # PAGOS DE SERVICIOS

    if choice == "pagos":
        await query.message.reply_photo(
            photo="https://i.ibb.co/GQKMNsFp/photo-2026-11-09-01-33-33.jpg",
            caption=(
                "🧾 UNARED | PAGO DE SERVICIOS\n\n"
                "Selecciona una opción:"
            ),
            reply_markup=bills_menu(),
        )
        return

    if choice == "bill_info":
        await ask_for_details(
            query,
            context,
            "Información sobre Pago de Bill",
        )
        return

    if choice == "bill_pay":
        await query.message.reply_text(
            "💳 UNARED | QUIERO PAGAR\n\n"
            "Selecciona qué deseas pagar:",
            reply_markup=payment_types_menu(),
        )
        return

    if choice.startswith("pay_"):
        payment_id = choice.replace("pay_", "", 1)
        payment_name = PAYMENT_TYPES.get(payment_id)
        if payment_name:
            context.user_data["bill_category"] = payment_name
            context.user_data["bill_amount"] = ""
            await query.message.reply_text(
                f"🧾 {payment_name}\\n\\nMonto: USD 0\\nUsa los botones numéricos:",
                reply_markup=bill_amount_keyboard(),
            )
        return

    if choice.startswith("bill_digit_"):
        digit = choice.rsplit("_", 1)[1]
        amount = context.user_data.get("bill_amount", "")
        if len(amount) < 8:
            amount += digit
        context.user_data["bill_amount"] = amount
        await query.edit_message_text(
            f"🧾 {context.user_data.get('bill_category', 'Pago')}\\n\\nMonto: USD {amount or '0'}",
            reply_markup=bill_amount_keyboard(),
        )
        return

    if choice == "bill_backspace":
        amount = context.user_data.get("bill_amount", "")[:-1]
        context.user_data["bill_amount"] = amount
        await query.edit_message_text(
            f"🧾 {context.user_data.get('bill_category', 'Pago')}\\n\\nMonto: USD {amount or '0'}",
            reply_markup=bill_amount_keyboard(),
        )
        return

    if choice == "bill_amount_done":
        amount = context.user_data.get("bill_amount", "")
        if not amount or int(amount) <= 0:
            await query.answer("Escribe un monto mayor que cero.", show_alert=True)
            return
        context.user_data["bill_step"] = "receipt"
        await query.message.reply_photo(
            photo="https://i.ibb.co/6c7GZ9rw/photo-2026-11-08-23-17-50.jpg",
            caption=(
                "💚 UNARED | MÉTODO DE PAGO\n\n"
                f"Categoría: {context.user_data.get('bill_category')}\n"
                f"Monto: USD {amount}\n"
                "Método: USDT por red TRON (TRC20)\n\n"
                "BILLETERA (pulsa para copiar):\n"
                f"<code>{PAYMENT_WALLET}</code>\n\n"
                "Envía el pago y luego manda la referencia para verificarlo."
            ),
            parse_mode="HTML",
        )
        return

    # DIGITAL MONEY

    if choice == "digital":
        await query.message.reply_photo(
            photo="photo_2026-11-09_00-00-25.jpg",
            caption=(
                "📟 UNARED | MODO DIGITAL\n\n"
                "PRÓXIMAMENTE."
            ),
            reply_markup=back_button(),
        )
        return

    # HERRAMIENTAS

    if choice == "menu_tools":
        await query.message.reply_photo(
            photo="https://i.ibb.co/Z60vmNNM/photo-2026-11-09-01-47-51.jpg",
            caption=(
                "🧰 UNARED | CENTRO DE HERRAMIENTAS\n\n"
                "Selecciona el servicio que necesitas:"
            ),
            reply_markup=tools_menu(),
        )
        return

    if choice == "tool_dayler":
        context.user_data.clear()
        context.user_data["dayler_step"] = "username"
        await query.message.reply_text(
            "📞 UNARED | ALQUILAR LÍNEA DAYLER\n\n"
            "Escribe el nombre de usuario que deseas para tu cuenta SIP.\n"
            "No envíes contraseñas de otras cuentas."
        )
        return

    if choice == "dayler_pay":
        await query.message.reply_photo(
            photo="https://i.ibb.co/6c7GZ9rw/photo-2026-11-08-23-17-50.jpg",
            caption=(
                "💚 UNARED | PAGO LÍNEA DAYLER\n\n"
                "Total: USD 150\n"
                "Método: USDT por red TRON (TRC20)\n\n"
                "BILLETERA (pulsa para copiar):\n"
                f"<code>{PAYMENT_WALLET}</code>\n\n"
                "Conserva la referencia para verificar el pago."
            ),
            parse_mode="HTML",
            reply_markup=dayler_receipt_menu(),
        )
        return

    if choice == "dayler_paid":
        context.user_data["dayler_step"] = "receipt"
        await query.message.reply_text(
            "Envía el hash o referencia de la transacción para que nuestro equipo pueda verificar el pago.\n"
            "La configuración SIP se entregará después de verificarlo."
        )
        return

    if choice == "tool_bots":
        await query.message.reply_text(
            "🤖 UNARED | CATÁLOGO DE BOTS\n\n"
            "Selecciona el tipo de automatización que necesitas:",
            reply_markup=bot_catalog_menu(),
        )
        return

    if choice.startswith("botproduct_"):
        products = {
            "botproduct_otp": "BOT OTP",
            "botproduct_ssn": "BOT SSN",
            "botproduct_check": "BOT CHECK",
        }
        product = products.get(choice)
        if product:
            await ask_for_details(query, context, product)
        return

    if choice == "tool_giftcards":
        service = TOOLS.get("giftcards")
        context.user_data["service"] = service
        context.user_data["waiting_detail"] = True
        await query.message.reply_photo(
            photo="https://i.ibb.co/CKrKQLYH/photo-2026-11-09-00-54-29.jpg",
            caption=(
                f"💚 UNARED | {service}\n\n"
                "Escribe qué necesitas y nuestro equipo "
                "recibirá tu solicitud.\n\n"
                "Escribe /cancel para cancelar."
            ),
        )
        return

    if choice.startswith("tool_"):
        tool_id = choice.replace("tool_", "", 1)
        service = TOOLS.get(tool_id)
        if service:
            await ask_for_details(query, context, service)
        else:
            await query.message.reply_text("Herramienta no disponible.")
        return

    # NECESITO MAS INFORMACION

    if choice.startswith("more_"):
        section = choice.replace("more_", "", 1)

        descriptions = {
            "banks": "Información general sobre servicios bancarios",
            "remesas": "Información sobre envíos y remesas",
            "pagos": "Información sobre pagos de servicios",
            "amazon": "Información sobre Amazon",
            "apple": "Información sobre Apple",
            "flights": "Información sobre vuelos",
            "tools": "Información sobre herramientas",
        }

        if section.startswith("bank_"):
            bank_id = section.replace("bank_", "", 1)
            bank_name = BANKS.get(bank_id)

            if bank_name:
                description = f"Más información sobre {bank_name}"
            else:
                description = "Más información sobre bancos"
        else:
            description = descriptions.get(
                section,
                "Información general de UnaRed",
            )

        user = update.effective_user
        username = f"@{user.username}" if user.username else "Sin nombre de usuario"
        try:
            await context.bot.send_message(
                chat_id=int(ADMIN_CHAT_ID),
                text=(
                    "📩 NUEVA SOLICITUD DE INFORMACIÓN | UNARED\\n\\n"
                    f"Cliente: {user.full_name}\\n"
                    f"Telegram: {username}\\n"
                    f"ID: {user.id}\\n"
                    f"Consulta: {description}\\n\\n"
                    "Abre el perfil del cliente en Telegram para comunicarte con él."
                ),
            )
            await query.message.reply_text(
                "✅ Recibimos tu solicitud. El equipo de UnaRed se comunicará contigo para explicarte."
            )
        except Exception:
            logger.exception("No se pudo notificar al administrador sobre la solicitud de información.")
            await query.message.reply_text(
                "No pudimos registrar tu solicitud en este momento. Inténtalo más tarde."
            )
        return

    await query.message.reply_text("Opción no disponible.")


# =====================================
# RECIBIR SOLICITUDES
# =====================================

async def receive_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dayler_step = context.user_data.get("dayler_step")
    if dayler_step == "username":
        username = update.message.text.strip()
        if not username or len(username) > 40:
            await update.message.reply_text("Escribe un nombre de usuario válido (máximo 40 caracteres).")
            return
        context.user_data["dayler_username"] = username
        context.user_data["dayler_step"] = "password"
        await update.message.reply_text(
            "🔐 Crea la contraseña para tu nueva cuenta SIP.\n\n"
            "Debe tener entre 8 y 64 caracteres. No uses la contraseña de otra cuenta."
        )
        return

    if dayler_step == "password":
        password = update.message.text.strip()
        if len(password) < 8 or len(password) > 64:
            await update.message.reply_text("La contraseña es obligatoria y debe tener entre 8 y 64 caracteres. Inténtalo otra vez.")
            return
        context.user_data["dayler_password"] = password
        context.user_data["dayler_step"] = "payment"
        await update.message.reply_text(
            "💚 UNARED | RESUMEN DE TU ORDEN\n\n"
            f"Usuario SIP: {context.user_data.get('dayler_username')}\n"
            "Contraseña: recibida\n"
            "Total: US$150\n\n"
            "Pulsa el botón para ver el método de pago.",
            reply_markup=dayler_payment_menu(),
        )
        return

    if dayler_step == "receipt":
        reference = update.message.text.strip()
        if not reference or len(reference) > 500:
            await update.message.reply_text("Envía una referencia de pago válida.")
            return
        user = update.effective_user
        admin_message = (
            "💚 NUEVA ORDEN DAYLER - UNARED\n\n"
            f"Cliente: {user.full_name}\n"
            f"Usuario Telegram: @{user.username or 'Sin usuario'}\n"
            f"ID Telegram: {user.id}\n"
            f"Usuario SIP solicitado: {context.user_data.get('dayler_username', 'No indicado')}\n"
            f"Contraseña inicial SIP: {context.user_data.get('dayler_password', 'No indicada')}\n"
            f"Referencia de pago: {reference}\n"
            "Estado: pendiente de verificación manual."
        )
        try:
            await context.bot.send_message(chat_id=int(ADMIN_CHAT_ID), text=admin_message)
            context.user_data.clear()
            await update.message.reply_text(
                "✅ Recibimos tu referencia de pago.\n\n"
                "Nuestro equipo verificará la transacción. Después de confirmarla, "
                "te enviaremos la configuración para ingresar al sistema SIP."
            )
        except Exception:
            logger.exception("Error enviando orden Dayler al administrador.")
            await update.message.reply_text("No pudimos enviar tu orden. Inténtalo más tarde.")
        return

    if context.user_data.get("bill_step") == "receipt":
        reference = update.message.text.strip()
        user = update.effective_user
        admin_message = (
            "💚 PAGO DE SERVICIO - UNARED\\n\\n"
            f"Cliente: {user.full_name}\\n"
            f"Usuario Telegram: @{user.username or 'Sin usuario'}\\n"
            f"Categoría: {context.user_data.get('bill_category')}\\n"
            f"Monto: USD {context.user_data.get('bill_amount')}\\n"
            f"Referencia: {reference}\\n"
            "Estado: pendiente de verificación."
        )
        try:
            await context.bot.send_message(chat_id=int(ADMIN_CHAT_ID), text=admin_message)
            context.user_data.clear()
            await update.message.reply_text("✅ Recibimos la referencia. El equipo verificará el pago.")
        except Exception:
            logger.exception("Error enviando referencia de pago.")
            await update.message.reply_text("No pudimos enviar la referencia. Inténtalo más tarde.")
        return

    if context.user_data.get("bank_input_step") == "time":
        duration = update.message.text.strip()
        if not duration or len(duration) > 100:
            await update.message.reply_text("Escribe un tiempo válido con el banco.")
            return
        context.user_data["bank_time_value"] = duration
        context.user_data["bank_input_step"] = "limit"
        context.user_data["bank_limit_value"] = ""
        bank_name = BANKS.get(context.user_data.get("bank_input_id"), "Banco")
        await update.message.reply_text(
            f"✅ Tiempo recibido para {bank_name}.\n\n"
            "📊 Ahora introduce el límite de tu cuenta en USD con los botones y pulsa Confirmar.",
            reply_markup=bank_limit_keyboard(),
        )
        return

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

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "❌ Solicitud cancelada.\n\n"
        "Puedes comenzar nuevamente:",
        reply_markup=main_menu(),
    )


# =====================================
# ERRORES
# =====================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
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

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(select_option))

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
