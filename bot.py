
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
    "citi": "Citi",
    "citizens": "Citizens Bank",
    "boa": "Bank of America",
    "chase": "JPMorgan Chase",
    "discover": "Discover Bank",
    "capital": "Capital One",
    "navy": "Navy Federal Credit Union",
    "pnc": "PNC Bank",
    "dcu": "DCU",
    "santander": "Santander",
    "regions": "Regions Bank",
    "truist": "Truist Bank",
    "wells": "Wells Fargo",
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
    "profiles": "Perfiles y configuración de perfiles",
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
    # JPMorgan Chase destacado arriba; los demás bancos en dos columnas.
    keyboard = [
        [InlineKeyboardButton("🏆 JPMorgan Chase", callback_data="bank_chase")],
        [
            InlineKeyboardButton("🏦 Bank of America", callback_data="bank_boa"),
            InlineKeyboardButton("🏦 Wells Fargo", callback_data="bank_wells"),
        ],
        [
            InlineKeyboardButton("🏦 Citibank", callback_data="bank_citi"),
            InlineKeyboardButton("🏦 Capital One", callback_data="bank_capital"),
        ],
        [
            InlineKeyboardButton("🏦 Navy Federal", callback_data="bank_navy"),
            InlineKeyboardButton("🏦 PNC Bank", callback_data="bank_pnc"),
        ],
        [
            InlineKeyboardButton("🏦 Discover Bank", callback_data="bank_discover"),
            InlineKeyboardButton("🏦 Truist Bank", callback_data="bank_truist"),
        ],
        [
            InlineKeyboardButton("🏦 Citizens Bank", callback_data="bank_citizens"),
            InlineKeyboardButton("🏦 Santander", callback_data="bank_santander"),
        ],
        [
            InlineKeyboardButton("🏦 Regions Bank", callback_data="bank_regions"),
            InlineKeyboardButton("🏦 DCU", callback_data="bank_dcu"),
        ],
        more_button("banks"),
        back_button(),
    ]
    return InlineKeyboardMarkup(keyboard)


# =====================================
# SERVICIOS DE CADA BANCO
# =====================================

def bank_services_menu(bank_id):
    keyboard = [
        [InlineKeyboardButton("💬 Consultar servicios", url="https://t.me/flowmontana777")],
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
        [InlineKeyboardButton("📞 Alquilar Línea Dialer", callback_data="tool_dayler")],
        [InlineKeyboardButton("🗂️ Páginas Buy CC | OFERTA US$17", callback_data="tool_pages")],
        [InlineKeyboardButton("🤖 Comprar Bot", callback_data="tool_bots")],
        [InlineKeyboardButton("🪪 SSN", callback_data="tool_ssn_info")],
        [
            InlineKeyboardButton("👤 Perfiles", callback_data="tool_profiles"),
            InlineKeyboardButton("🛒 Amazon", callback_data="tool_amazon"),
        ],
        [
            InlineKeyboardButton("🍎 iCloud", callback_data="tool_icloud"),
            InlineKeyboardButton("💰 Préstamos", callback_data="tool_loans"),
        ],
        [InlineKeyboardButton("💵 Método PyP | OFERTA US$100", callback_data="tool_pyp")],
        [InlineKeyboardButton("📄 Papeles", callback_data="edit_buy_paper")],
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

        bank_images = {
            "citi": "https://i.ibb.co/3YcCXcLb/Citi-Bank-promotional-image-design-d7e032d9.jpg",
            "citizens": "https://i.ibb.co/Vpc6DZsJ/Citizens-Bank-promotional-image-0dcbc19c.jpg",
            "boa": "https://i.ibb.co/v41k3ZqX/Create-Bank-of-America-promotion-f3f42bce.jpg",
            "chase": "https://i.ibb.co/wFvLyH1g/Create-Chase-Bank-promotional-image-b0f4d9af.jpg",
            "discover": "https://i.ibb.co/FkvqfqsC/Creating-Discover-Bank-promotion-a0435e92.jpg",
            "capital": "https://i.ibb.co/sJd00ZP8/Designing-Capital-One-promotiona-a4b6e8aa.jpg",
            "navy": "https://i.ibb.co/bgmvgSfg/Navy-Federal-promotional-image-d-a1e37228.jpg",
            "pnc": "https://i.ibb.co/TxMtDQQ4/PNC-Bank-promotional-image-design-581507fe.jpg",
            "dcu": "https://i.ibb.co/QSqVqsw/Promotional-image-design-for-DCU-3e4dda17.jpg",
            "santander": "https://i.ibb.co/81f40BH/Promotional-image-for-Santander-175c3219.jpg",
            "regions": "https://i.ibb.co/Qv0RN1n9/Regions-Bank-promotional-image-d-1ca0273b.jpg",
            "truist": "https://i.ibb.co/YBY77HgC/Truist-Bank-promotional-image-de-846cdc0d.jpg",
            "wells": "https://i.ibb.co/wNg8zHSv/Wells-Fargo-promotional-image-de-77ab0756.jpg",
        }
        bank_image = bank_images.get(bank_id)
        caption = (
            f"🏦 UNARED | {bank_name}\n\n"
            "Selecciona el servicio que necesitas:"
        )
        if bank_image:
            await query.message.reply_photo(
                photo=bank_image,
                caption=caption,
                reply_markup=bank_services_menu(bank_id),
            )
        else:
            await query.message.reply_text(
                caption,
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
            remittance_images = {
                "moneygram": "https://i.ibb.co/zh3qqz6g/Create-promotional-image-for-Mon-a81f61c0.jpg",
                "ria": "https://i.ibb.co/7TvCXwv/Designing-Ria-promotional-image-e4ea90ac.jpg",
                "paypal": "https://i.ibb.co/Y71ZLQGQ/Pay-Pal-promotional-image-design-4c23fd05.jpg",
                "taptap": "https://i.ibb.co/JRLwQMJM/esta-es-Tap-Tap-7e13b4cc.jpg",
                "western": "https://i.ibb.co/W4PJKPjb/Western-Union-promotional-image-df5c8464.jpg",
                "remitly": "https://i.ibb.co/sJjzgYX7/Creating-promotional-image-for-R-42f525cf.jpg",
                "boss": "https://i.ibb.co/4Rm90Fw9/Create-promotional-image-for-Bos-852877e1.jpg",
            }
            caption = f"💸 UNARED | {app_name}\n\nSelecciona una opción:"
            image_url = remittance_images.get(app_id)
            if image_url:
                await query.message.reply_photo(
                    photo=image_url,
                    caption=caption,
                    reply_markup=remittance_options_menu(app_id),
                )
            else:
                await query.message.reply_text(
                    caption,
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
        await query.message.reply_photo(
            photo="https://i.ibb.co/7xp7rTMV/Create-promotional-image-for-tel-a730da20-2-K.jpg",
            caption=(
                "📞 UNARED | ALQUILAR LÍNEA DAYLER\n\n"
                "Pulsa Empezar para solicitar tu nueva línea SIP."
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Empezar", callback_data="dayler_start")],
                [InlineKeyboardButton("🔐 Soporte VoIP", callback_data="tool_auth")],
            ]),
        )
        return

    if choice == "dayler_start":
        context.user_data["dayler_step"] = "username"
        await query.message.reply_text(
            "👤 Escribe el usuario que deseas para tu nueva línea SIP."
        )
        return

    if choice == "tool_auth":
        await ask_for_details(query, context, "Soporte VoIP")
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
        await query.message.reply_photo(
            photo="https://i.ibb.co/9Ct8LfQ/Create-promotional-image-for-tel-740dbeb8.jpg",
            caption=(
                "🤖 UNARED | CATÁLOGO DE BOTS\n\n"
                "Selecciona el tipo de automatización que necesitas:"
            ),
            reply_markup=bot_catalog_menu(),
        )
        return

    if choice == "botproduct_otp":
        context.user_data["service"] = "BOT OTP"
        context.user_data["waiting_detail"] = True
        await query.message.reply_text(
            "🔐 OTP Verification System v3.2\n\n"
            "Automated call & SMS verification tool.\n\n"
            "💵 Precio: US$35\n\n"
            "💳 MÉTODO DE PAGO\n"
            "Moneda: USDT\n"
            "Red: TRON (TRC20)\n"
            f"Dirección: {PAYMENT_WALLET}\n\n"
            "Después de realizar el pago, conserva el comprobante y contacta al equipo para verificarlo.\n\n"
            "🔎 Si quieres un bot que esté funcionando, aquí lo buscamos y lo probamos "
            "en entornos de prueba o cuentas que tengas autorización para verificar.\n\n"
            "✨ Features:\n"
            "• Real time call panel\n"
            "• Human voice AI\n"
            "• Caller ID verificado y configurable\n"
            "• Multi country routes autorizadas\n"
            "• Live status logs\n\n"
            "📩 Escribe tu consulta para que el equipo de UnaRed pueda ayudarte."
        )
        return

    if choice.startswith("botproduct_"):
        products = {
            "botproduct_ssn": "BOT SSN",
            "botproduct_check": "BOT CHECK",
        }
        product = products.get(choice)
        if product:
            await ask_for_details(query, context, product)
        return

    if choice == "tool_pyp":
        await query.message.reply_text(
            "💚 UNARED | MÉTODO PyP\n\n"
            "🎉 OFERTA PARA CLIENTES NUEVOS: US$100\n\n"
            "Para conocer los detalles del servicio y confirmar disponibilidad, "
            "contacta directamente con nuestro equipo.\n"
            "No envíes contraseñas, códigos de verificación ni datos bancarios.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Consultar y solicitar", url="https://t.me/flowmontana777")],
                [InlineKeyboardButton("⬅️ Volver a Herramientas", callback_data="menu_tools")],
            ]),
        )
        return

    if choice == "tool_pages":
        context.user_data["pages_quantity"] = 1
        quantity = 1
        total = quantity * 17
        await query.message.reply_photo(
            photo="https://i.ibb.co/dJQ4yzbg/Create-promotional-image-for-tel-003ed2cb.jpg",
            caption=(
                "💚 UNARED | PÁGINAS DE PAGO\n\n"
                "Catálogo de páginas legítimas de comercio electrónico y procesamiento de pagos.\n"
                "🏷️ Precio por unidad: US$17\n"
                "Precio regular: US$20\n\n"
                f"📦 Cantidad: {quantity}\n"
                f"💵 Total: US\${total}"
            ),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("➖", callback_data="pages_qty_minus"),
                    InlineKeyboardButton(f"{quantity}", callback_data="pages_qty_display"),
                    InlineKeyboardButton("➕", callback_data="pages_qty_plus"),
                ],
                [InlineKeyboardButton("📋 Solicitar selección", url="https://t.me/flowmontana777")],
                [InlineKeyboardButton("⬅️ Volver a Herramientas", callback_data="menu_tools")],
            ]),
        )
        return

    if choice in ("pages_qty_plus", "pages_qty_minus"):
        quantity = int(context.user_data.get("pages_quantity", 1))
        if choice == "pages_qty_plus":
            quantity = min(quantity + 1, 99)
        else:
            quantity = max(quantity - 1, 1)
        context.user_data["pages_quantity"] = quantity
        total = quantity * 17
        await query.edit_message_caption(
            caption=(
                "💚 UNARED | PÁGINAS DE PAGO\n\n"
                "Catálogo de páginas legítimas de comercio electrónico y procesamiento de pagos.\n"
                "🏷️ Precio por unidad: US$17\n"
                "Precio regular: US$20\n\n"
                f"📦 Cantidad: {quantity}\n"
                f"💵 Total: US\${total}"
            ),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("➖", callback_data="pages_qty_minus"),
                    InlineKeyboardButton(f"{quantity}", callback_data="pages_qty_display"),
                    InlineKeyboardButton("➕", callback_data="pages_qty_plus"),
                ],
                [InlineKeyboardButton("📋 Solicitar selección", url="https://t.me/flowmontana777")],
                [InlineKeyboardButton("⬅️ Volver a Herramientas", callback_data="menu_tools")],
            ]),
        )
        return

    if choice == "pages_qty_display":
        await query.answer("Usa ➕ o ➖ para cambiar la cantidad.")
        return

    if choice == "tool_ssn_info":
        await query.message.reply_photo(
            photo="https://i.ibb.co/xqSWw0jN/Creating-promotional-image-for-U-bc5b392a.jpg",
            caption=(
                "🪪 UNARED | INFORMACIÓN SSN\n\n"
                "Quiero Búsqueda de Seguro Social de Estados Unidos."
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Consultar servicio", url="https://t.me/flowmontana777")],
                [InlineKeyboardButton("⬅️ Volver a Herramientas", callback_data="menu_tools")],
            ]),
        )
        return

    if choice in ("tool_profiles", "tool_amazon", "tool_icloud", "tool_loans"):
        labels = {
            "tool_profiles": "PERFILES",
            "tool_amazon": "AMAZON",
            "tool_icloud": "ICLOUD",
            "tool_loans": "PRÉSTAMOS",
        }
        await query.message.reply_text(
            f"💚 UNARED | {labels[choice]}\n\n"
            "Consulta los servicios disponibles con nuestro equipo. "
            "No compartas contraseñas ni códigos de verificación.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Consultar servicio", url="https://t.me/flowmontana777")],
                [InlineKeyboardButton("⬅️ Volver a Herramientas", callback_data="menu_tools")],
            ]),
        )
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

    if choice == "tool_edit_upload":
        context.user_data["edit_upload_step"] = None
        await query.message.reply_photo(
            photo="https://i.ibb.co/YTWPTVJZ/photo-2026-11-09-15-54-09.jpg",
            caption=(
                "📄 UNARED | QUIERO EDITAR Y SUBIR PAPEL\n\n"
                "💵 Precio: US$200\n\n"
                "🎥 ¿Qué recibes?\n"
                "• Una videollamada editando con UnaRed\n"
                "• Link de Photoshop ilimitado\n"
                "• Papel para empezar\n"
                "• Contacto para comprar papel\n\n"
                "💳 MÉTODO DE PAGO\n"
                "Moneda: USDT\n"
                "Red: TRON (TRC20)\n"
                f"Dirección: {PAYMENT_WALLET}\n\n"
                "Después de pagar, pulsa «Ya Pagué» y envía el comprobante."
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Ya Pagué", callback_data="edit_upload_paid")],
                [InlineKeyboardButton("ℹ️ Quiero Saber Más", url="https://t.me/flowmontana777")],
            ]),
        )
        return

    if choice == "edit_buy_paper":
        await query.message.reply_text(
            "📄 QUIERO COMPRAR PAPEL\n\n"
            "Para consultar la compra de papel, comunícate directamente con UnaRed.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📲 Contacto", url="https://t.me/flowmontana777")],
                [InlineKeyboardButton("⬅️ Volver a Herramientas", callback_data="menu_tools")],
            ]),
        )
        return

    if choice == "edit_upload_paid":
        context.user_data["edit_upload_step"] = "receipt"
        await query.message.reply_text(
            "📩 Envía ahora el comprobante de pago como foto o archivo. "
            "Lo enviaremos al equipo de UnaRed para verificarlo."
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
    if context.user_data.get("edit_upload_step") == "receipt":
        if not update.message.photo and not update.message.document:
            await update.message.reply_text("Por favor, envía el comprobante como foto o archivo.")
            return
        user = update.effective_user
        caption = (
            "💚 COMPROBANTE | EDITAR Y SUBIR PAPEL - UNARED\n"
            f"Cliente: {user.full_name}\n"
            f"Usuario: @{user.username or 'Sin usuario'}\n"
            f"ID: {user.id}\n"
            "Monto indicado: US$200\n"
            "Estado: pendiente de verificación."
        )
        try:
            if update.message.photo:
                await context.bot.send_photo(
                    chat_id=int(ADMIN_CHAT_ID),
                    photo=update.message.photo[-1].file_id,
                    caption=caption,
                )
            else:
                await context.bot.send_document(
                    chat_id=int(ADMIN_CHAT_ID),
                    document=update.message.document.file_id,
                    caption=caption,
                )
            context.user_data.pop("edit_upload_step", None)
            await update.message.reply_text(
                "✅ Recibimos tu comprobante. El equipo de UnaRed verificará el pago y te contactará."
            )
        except Exception:
            logger.exception("Error enviando comprobante de Editar y Subir Papel.")
            await update.message.reply_text("No pudimos enviar el comprobante. Inténtalo nuevamente.")
        return

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
        # No conservar ni reenviar contraseñas por seguridad.
        context.user_data["dayler_step"] = "payment"
        try:
            await update.message.delete()
        except Exception:
            logger.warning("No se pudo borrar el mensaje con la contraseña SIP.")
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

    if not update.message.text:
        await update.message.reply_text("Por favor, envía el texto de tu solicitud.")
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
            (filters.TEXT & ~filters.COMMAND) | filters.PHOTO | filters.Document.ALL,
            receive_request,
        )
    )

    app.add_error_handler(error_handler)

    print("💚 UnaRed Bot está funcionando.")

    app.run_polling()


if __name__ == "__main__":
    main()
