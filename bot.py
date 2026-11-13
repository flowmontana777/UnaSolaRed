
import os
import logging
import asyncio
import hmac
import hashlib
import json
import sqlite3
from decimal import Decimal, InvalidOperation

import aiohttp
from aiohttp import web

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
WOLVPAY_API_KEY = os.getenv("WOLVPAY_API_KEY")
WOLVPAY_WEBHOOK_SECRET = os.getenv("WOLVPAY_WEBHOOK_SECRET")
WOLVPAY_API_URL = "https://wolvpay.com/api/v1"
DATABASE_PATH = os.getenv("DATABASE_PATH", "unared_payments.sqlite3")

GROUP_LINK = "https://t.me/+slI1SJL6HIQ4Nzcx"

# =====================================
# METODO DE PAGO UNARED
# =====================================

async def schedule_payment_reminder(application, table_name, invoice_id, telegram_id, amount, service, invoice_url=None):
    """Send a reminder after 10 minutes only if this invoice is still pending."""
    await asyncio.sleep(600)
    if table_name not in {"dayler_invoices", "demo_bot_invoices", "pages_invoices", "icloud_invoices", "bill_invoices", "edit_upload_invoices"}:
        return
    try:
        with sqlite3.connect(DATABASE_PATH) as db:
            row = db.execute(
                f"SELECT status FROM {table_name} WHERE invoice_id = ?",
                (invoice_id,),
            ).fetchone()
        if not row or str(row[0]).upper() != "PENDING":
            return
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔔 Volver a la factura", url=invoice_url)]
        ]) if invoice_url else None
        await application.bot.send_message(
            chat_id=int(telegram_id),
            text=(
                f"⏰ RECORDATORIO DE PAGO | UNARED\\n\\n"
                f"Tu factura de {service} todavía aparece pendiente. "
                "Si deseas completar el servicio, puedes finalizar el pago desde tu factura. "
                "Si ya pagaste, espera la confirmación automática de WolvPay."
                f"\\n\\n💵 Importe: US${amount}"
            ),
            reply_markup=keyboard,
        )
    except Exception:
        logger.exception("No se pudo enviar el recordatorio de pago para %s.", invoice_id)



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
# MODO DIGITAL - MUSICA
# =====================================

def digital_music_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎧 Escuchar música", callback_data="music_catalog")],
        [InlineKeyboardButton("📥 Enviar una canción", callback_data="music_submit")],
        back_button(),
    ])


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
                "📞 Agendar Llamada!",
                url="https://t.me/flowmontana777",
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
        [InlineKeyboardButton("📞 Agendar Llamada!", url="https://t.me/flowmontana777")],
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


def dayler_coin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("₿ Bitcoin (BTC)", callback_data="dayler_coin_btc")],
        [InlineKeyboardButton("₮ USDT (TRC20)", callback_data="dayler_coin_trc20_usdt")],
        [InlineKeyboardButton("⬅️ Volver", callback_data="menu_tools")],
    ])


def pages_coin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("₿ Bitcoin (BTC)", callback_data="pages_coin_btc")],
        [InlineKeyboardButton("₮ USDT (TRC20)", callback_data="pages_coin_trc20_usdt")],
        [InlineKeyboardButton("⬅️ Volver al catálogo", callback_data="tool_pages")],
    ])


def icloud_coin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("₿ Bitcoin (BTC)", callback_data="icloud_coin_btc")],
        [InlineKeyboardButton("₮ USDT (TRC20)", callback_data="icloud_coin_trc20_usdt")],
        [InlineKeyboardButton("⬅️ Volver a Perfiles", callback_data="tool_icloud")],
    ])


def edit_upload_coin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("₿ Bitcoin (BTC)", callback_data="edit_upload_coin_btc")],
        [InlineKeyboardButton("₮ USDT (TRC20)", callback_data="edit_upload_coin_trc20_usdt")],
        [InlineKeyboardButton("⬅️ Volver al servicio", callback_data="tool_edit_upload")],
    ])


def bill_amount_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1", callback_data="bill_digit_1"), InlineKeyboardButton("2", callback_data="bill_digit_2"), InlineKeyboardButton("3", callback_data="bill_digit_3")],
        [InlineKeyboardButton("4", callback_data="bill_digit_4"), InlineKeyboardButton("5", callback_data="bill_digit_5"), InlineKeyboardButton("6", callback_data="bill_digit_6")],
        [InlineKeyboardButton("7", callback_data="bill_digit_7"), InlineKeyboardButton("8", callback_data="bill_digit_8"), InlineKeyboardButton("9", callback_data="bill_digit_9")],
        [InlineKeyboardButton("⌫", callback_data="bill_backspace"), InlineKeyboardButton("0", callback_data="bill_digit_0"), InlineKeyboardButton("Confirmar", callback_data="bill_amount_done")],
    ])


def bill_coin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("₿ Bitcoin (BTC)", callback_data="bill_coin_btc")],
        [InlineKeyboardButton("₮ USDT (TRC20)", callback_data="bill_coin_trc20_usdt")],
        [InlineKeyboardButton("⬅️ Volver", callback_data="bill_pay")],
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
        [InlineKeyboardButton("👤 Perfiles", callback_data="tool_profiles")],
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

    user = update.effective_user
    if user:
        with sqlite3.connect(DATABASE_PATH) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS digital_music_subscribers (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL DEFAULT '',
                full_name TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            db.execute(
                """INSERT INTO digital_music_subscribers (telegram_id, username, full_name)
                   VALUES (?, ?, ?)
                   ON CONFLICT(telegram_id) DO UPDATE SET
                     username = excluded.username,
                     full_name = excluded.full_name""",
                (user.id, user.username or "", user.full_name or ""),
            )

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
                await query.message.reply_text(
                    "¿Quieres coordinar una llamada con UnaRed?",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📞 Agendar Llamada", callback_data="remit_schedule_call")],
                    ]),
                )
        return

    if choice == "remit_schedule_call":
        user = update.effective_user
        service = context.user_data.get("service", "Envíos y Remesas")
        username = f"@{user.username}" if user.username else "Sin username público"
        try:
            await context.bot.send_message(
                chat_id=int(ADMIN_CHAT_ID),
                text=(
                    "📞 NUEVA SOLICITUD DE LLAMADA | UNARED\n\n"
                    f"👤 Cliente: {user.full_name}\n"
                    f"🔗 Usuario: {username}\n"
                    f"🆔 Telegram ID: {user.id}\n"
                    f"📲 Servicio: {service}\n"
                    "🟢 Estado: Solicitud recibida; pendiente de coordinar."
                ),
            )
            await query.message.reply_text(
                "✅ Tu solicitud para agendar una llamada fue enviada a UnaRed. Puedes contactar al equipo aquí:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Contactar a UnaRed", url="https://t.me/flowmontana777")],
                ]),
            )
        except Exception:
            logger.exception("No se pudo notificar la solicitud de llamada.")
            await query.message.reply_text("No pudimos registrar tu solicitud ahora. Inténtalo nuevamente.")
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
        await query.message.reply_text(
            "🧾 UNARED | PAGO DE SERVICIOS\\n\\n"
            "Selecciona una opción:",
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
        amount = str(Decimal(amount).quantize(Decimal("0.01")))
        context.user_data["bill_amount"] = amount
        await query.message.reply_text(
            "💚 UNARED | MÉTODO DE PAGO\\n\\n"
            f"Categoría: {context.user_data.get('bill_category')}\\n"
            f"Monto: USD {amount}\\n\\n"
            "Selecciona cómo deseas pagar mediante una factura de WolvPay:",
            reply_markup=bill_coin_menu(),
        )
        return

    if choice.startswith("bill_coin_"):
        coin = choice.replace("bill_coin_", "", 1)
        if coin not in ("btc", "trc20_usdt"):
            await query.message.reply_text("Método de pago no disponible.")
            return
        if not WOLVPAY_API_KEY:
            await query.message.reply_text("El pago automático no está configurado. Contacta al equipo de UnaRed.")
            return
        amount = context.user_data.get("bill_amount")
        category = context.user_data.get("bill_category")
        if not amount or not category:
            await query.message.reply_text("No encontramos tu solicitud. Vuelve a iniciar el proceso desde Pago de servicios.")
            return
        user = update.effective_user
        username = user.username or ""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{WOLVPAY_API_URL}/invoices",
                    headers={"Authorization": f"Bearer {WOLVPAY_API_KEY}", "Content-Type": "application/json"},
                    json={
                        "amount": float(amount), "currency": "USD", "coin": coin,
                        "description": f"UNARED_BILL|telegram_id={user.id}|category={category}",
                        "white_label": False,
                    },
                    timeout=aiohttp.ClientTimeout(total=25),
                ) as response:
                    payload = await response.json(content_type=None)
                    if response.status not in (200, 201) or payload.get("success") is False:
                        logger.error("WolvPay bill invoice error: HTTP %s", response.status)
                        raise RuntimeError("Invoice creation failed")
            data = payload.get("data") or payload
            invoice_id = data.get("invoice_id")
            invoice_url = data.get("url") or data.get("payment_url")
            if not invoice_id or not invoice_url:
                raise RuntimeError("Incomplete WolvPay bill invoice response")
            with sqlite3.connect(DATABASE_PATH) as db:
                db.execute("""CREATE TABLE IF NOT EXISTS bill_invoices (
                    invoice_id TEXT PRIMARY KEY, telegram_id INTEGER NOT NULL,
                    amount TEXT NOT NULL, category TEXT NOT NULL,
                    username TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'PENDING'
                )""")
                db.execute(
                    """INSERT INTO bill_invoices
                       (invoice_id, telegram_id, amount, category, username, status)
                       VALUES (?, ?, ?, ?, ?, 'PENDING')""",
                    (invoice_id, user.id, amount, category, username),
                )
            asyncio.create_task(schedule_payment_reminder(
                context.application, "bill_invoices", invoice_id, user.id, amount, category, invoice_url
            ))
            await query.message.reply_text(
                "💚 UNARED | FACTURA DE PAGO DE SERVICIOS\\n\\n"
                f"Servicio: {category}\\nImporte: USD {amount}\\n"
                f"Moneda: {'Bitcoin (BTC)' if coin == 'btc' else 'USDT (TRC20)'}\\n"
                f"Factura: {invoice_id}\\n\\n"
                "Completa el pago desde la factura. WolvPay confirmará el pago automáticamente.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Abrir factura y pagar", url=invoice_url)],
                    [InlineKeyboardButton("⬅️ Volver a Pago de servicios", callback_data="pagos")],
                ]),
            )
        except Exception:
            logger.exception("No se pudo crear la factura WolvPay para Pago de servicios.")
            await query.message.reply_text(
                "No pudimos generar la factura. No realices transferencias manuales; inténtalo más tarde o contacta al equipo."
            )
        return

    # MODO DIGITAL - MUSICA

    if choice == "digital":
        context.user_data.pop("music_upload_mode", None)
        await query.message.reply_text(
            "📟 UNARED | MODO DIGITAL\n\n"
            "🎵 Música para escuchar directamente en Telegram.\n"
            "Explora el catálogo aprobado o envía una canción para revisión.",
            reply_markup=digital_music_menu(),
        )
        return

    if choice == "music_submit":
        context.user_data["music_upload_mode"] = True
        await query.message.reply_text(
            "📥 ENVIAR CANCIÓN | UNARED\n\n"
            "Envía tu canción en formato audio MP3 usando la opción «Enviar como audio» de Telegram. "
            "La canción quedará pendiente de aprobación antes de aparecer en el catálogo.\n\n"
            "Envía /cancel si deseas salir."
        )
        return

    if choice == "music_catalog":
        with sqlite3.connect(DATABASE_PATH) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS digital_music (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL,
                title TEXT NOT NULL,
                performer TEXT NOT NULL DEFAULT '',
                submitted_by INTEGER NOT NULL,
                submitter_name TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'PENDING',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            songs = db.execute(
                "SELECT id, title, performer FROM digital_music WHERE status = 'APPROVED' ORDER BY id DESC LIMIT 20"
            ).fetchall()
        if not songs:
            await query.message.reply_text(
                "🎵 El catálogo todavía está vacío. Puedes enviar una canción para que UnaRed la revise.",
                reply_markup=digital_music_menu(),
            )
            return
        keyboard = [
            [InlineKeyboardButton(
                f"🎧 {title[:35]} - {performer[:25]}".strip(" -"),
                callback_data=f"music_play_{song_id}",
            )]
            for song_id, title, performer in songs
        ]
        keyboard.append([InlineKeyboardButton("⬅️ Volver a Modo Digital", callback_data="digital")])
        await query.message.reply_text("🎼 UNARED | CATÁLOGO MUSICAL", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if choice.startswith("music_play_"):
        try:
            song_id = int(choice.rsplit("_", 1)[1])
        except ValueError:
            await query.message.reply_text("Canción no válida.")
            return
        with sqlite3.connect(DATABASE_PATH) as db:
            row = db.execute(
                "SELECT file_id, title, performer FROM digital_music WHERE id = ? AND status = 'APPROVED'",
                (song_id,),
            ).fetchone()
        if not row:
            await query.message.reply_text("Esta canción ya no está disponible.")
            return
        file_id, title, performer = row
        await context.bot.send_audio(
            chat_id=update.effective_chat.id,
            audio=file_id,
            title=title,
            performer=performer or None,
            caption=f"🎵 UNARED | MODO DIGITAL\n{title}",
        )
        return

    if choice.startswith("music_approve_") or choice.startswith("music_reject_"):
        if str(update.effective_user.id) != str(ADMIN_CHAT_ID):
            await query.answer("Esta acción es solo para el administrador.", show_alert=True)
            return
        action = "approve" if choice.startswith("music_approve_") else "reject"
        try:
            song_id = int(choice.rsplit("_", 1)[1])
        except ValueError:
            await query.message.reply_text("Solicitud no válida.")
            return
        new_status = "APPROVED" if action == "approve" else "REJECTED"
        with sqlite3.connect(DATABASE_PATH) as db:
            db.execute(
                "UPDATE digital_music SET status = ? WHERE id = ? AND status = 'PENDING'",
                (new_status, song_id),
            )
            row = db.execute(
                "SELECT submitted_by, title FROM digital_music WHERE id = ?",
                (song_id,),
            ).fetchone()
        if not row:
            await query.message.reply_text("No encontramos esa canción.")
            return
        try:
            await context.bot.send_message(
                chat_id=int(row[0]),
                text=("✅ Tu canción fue aprobada y ya está disponible en el catálogo de UnaRed."
                      if new_status == "APPROVED"
                      else "ℹ️ Tu canción no fue aprobada para el catálogo de UnaRed.")
            )
        except Exception:
            logger.warning("No se pudo notificar al usuario sobre la revisión musical %s.", song_id)
        await query.edit_message_caption(
            caption=f"🎵 Revisión musical: {row[1]}\nEstado: {new_status}",
            reply_markup=None,
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
                "💚 UNARED | LA RED QUE MUEVE TU DINERO\n"
                "📞 ALQUILER DE LÍNEA SIP\n\n"
                "¿Necesitas configurar una línea SIP para realizar llamadas desde MicroSIP?\n\n"
                "💰 OFERTA DE ACTIVACIÓN\n"
                "Paga US$150 y recibe US$50 de saldo acreditado en tu panel, para comenzar a realizar llamadas desde YA.\n\n"
                "🏦 BANCOS DISPONIBLES\n"
                "🏦 Wells Fargo\n"
                "🏦 Bank of America (BOFA)\n"
                "🏦 Discover\n"
                "🏦 Capital One\n"
                "🏦 KeyBank\n"
                "🏦 Citi Bank – Débito y Crédito\n"
                "🏦 Chase Bank\n"
                "🏦 US Bank\n"
                "🏦 First National Bank\n"
                "🏦 TD Bank\n\n"
                "🏦 ¡Y demás bancos que desees llamar!\n\n"
                "🚀 Solicita tu línea de forma rápida y sencilla desde UnaRed.\n\n"
                "👇 Pulsa «Empezar» para iniciar tu solicitud y recibir los detalles del servicio."
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Empezar", callback_data="dayler_start")],
                [InlineKeyboardButton("🔐 Soporte VoIP", callback_data="tool_auth")],
            ]),
        )
        return

    if choice == "dayler_start":
        context.user_data["dayler_step"] = "username"
        await query.message.reply_photo(
            photo="https://i.ibb.co/tws5NH0C/Promotional-graphic-card-design-6f106e97.jpg",
            caption="👤 Escribe el usuario que deseas para tu nueva línea SIP."
        )
        return

    if choice == "tool_auth":
        await ask_for_details(query, context, "Soporte VoIP")
        return

    if choice == "dayler_pay":
        await query.message.reply_text(
            "💚 UNARED | PAGO LÍNEA DAYLER\n\n"
            "Total: US$150\n"
            "Selecciona la criptomoneda para generar tu factura individual:",
            reply_markup=dayler_coin_menu(),
        )
        return

    if choice.startswith("dayler_coin_"):
        coin = choice.replace("dayler_coin_", "", 1)
        if coin not in ("btc", "trc20_usdt"):
            await query.message.reply_text("Método de pago no disponible.")
            return
        if not WOLVPAY_API_KEY:
            await query.message.reply_text(
                "El pago automático no está configurado todavía. "
                "Contacta al equipo de UnaRed."
            )
            return
        username = context.user_data.get("dayler_username")
        if not username:
            await query.message.reply_text(
                "No encontramos tu solicitud Dayler. Vuelve a iniciar el proceso desde Herramientas."
            )
            return
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{WOLVPAY_API_URL}/invoices",
                    headers={
                        "Authorization": f"Bearer {WOLVPAY_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "amount": 150,
                        "currency": "USD",
                        "coin": coin,
                        "description": f"UNARED_DAYLER|telegram_id={update.effective_user.id}|username={username}",
                        "white_label": False,
                    },
                    timeout=aiohttp.ClientTimeout(total=25),
                ) as response:
                    payload = await response.json(content_type=None)
                    if response.status not in (200, 201) or payload.get("success") is False:
                        logger.error("WolvPay invoice error: HTTP %s", response.status)
                        raise RuntimeError("No se pudo crear la factura.")
            invoice_data = payload.get("data") or payload
            invoice_id = invoice_data.get("invoice_id")
            invoice_url = invoice_data.get("url") or invoice_data.get("payment_url")
            if not invoice_id or not invoice_url:
                logger.error("WolvPay response missing invoice id or hosted URL.")
                raise RuntimeError("Respuesta incompleta del proveedor.")
            with sqlite3.connect(DATABASE_PATH) as db:
                db.execute(
                    """CREATE TABLE IF NOT EXISTS dayler_invoices (
                        invoice_id TEXT PRIMARY KEY,
                        telegram_id INTEGER NOT NULL,
                        amount TEXT NOT NULL,
                        username TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'PENDING'
                    )"""
                )
                db.execute(
                    """INSERT INTO dayler_invoices
                       (invoice_id, telegram_id, amount, username, status)
                       VALUES (?, ?, ?, ?, 'PENDING')""",
                    (invoice_id, update.effective_user.id, "150.00", username),
                )
            asyncio.create_task(schedule_payment_reminder(context.application, "dayler_invoices", invoice_id, update.effective_user.id, "150", "Dayler", invoice_url))
            await query.message.reply_text(
                f"💚 UNARED | FACTURA DAYLER\n\n"
                f"Importe: US$150\n"
                f"Moneda: {'Bitcoin (BTC)' if coin == 'btc' else 'USDT (TRC20)'}\n"
                f"Factura: {invoice_id}\n\n"
                "Pulsa el botón para completar el pago. "
                "La orden se confirmará automáticamente cuando WolvPay valide el pago.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Abrir factura y pagar", url=invoice_url)],
                    [InlineKeyboardButton("🔎 Verificar pago", callback_data="dayler_verify")],
                    [InlineKeyboardButton("✅ ¡Ya pagué!", callback_data="dayler_paid")]
                ]),
            )
        except Exception:
            logger.exception("No se pudo crear la factura WolvPay para Dayler.")
            await query.message.reply_text(
                "No pudimos generar la factura en este momento. "
                "No realices ninguna transferencia manual; inténtalo más tarde o contacta al equipo."
            )
        return

    if choice == "dayler_verify":
        if not WOLVPAY_API_KEY:
            await query.message.reply_text("La verificación automática no está disponible. Contacta al equipo de UnaRed.")
            return
        try:
            with sqlite3.connect(DATABASE_PATH) as db:
                db.execute("""CREATE TABLE IF NOT EXISTS dayler_invoices (
                    invoice_id TEXT PRIMARY KEY,
                    telegram_id INTEGER NOT NULL,
                    amount TEXT NOT NULL,
                    username TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING'
                )""")
                row = db.execute(
                    "SELECT invoice_id, amount, status FROM dayler_invoices WHERE telegram_id = ? ORDER BY rowid DESC LIMIT 1",
                    (update.effective_user.id,),
                ).fetchone()
            if not row:
                await query.message.reply_text("No encontramos una factura asociada a tu cuenta.")
                return
            invoice_id, expected_amount, current_status = row
            if current_status == "PAID":
                await query.message.reply_text("✅ Tu pago ya está confirmado. El equipo de UnaRed continuará con tu solicitud.")
                return
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{WOLVPAY_API_URL}/invoices/{invoice_id}",
                    headers={"Authorization": f"Bearer {WOLVPAY_API_KEY}"},
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as response:
                    payload = await response.json(content_type=None)
                    if response.status != 200:
                        logger.error("WolvPay manual verification returned HTTP %s", response.status)
                        await query.message.reply_text("No pudimos consultar la factura ahora mismo. Inténtalo nuevamente en unos minutos.")
                        return
            invoice = payload.get("data") or payload
            status = str(invoice.get("status", "")).upper()
            verified_amount = Decimal(str(invoice.get("amount", "0")))
            if status == "PAID" and str(invoice.get("invoice_id", invoice_id)) == invoice_id and verified_amount == Decimal(expected_amount):
                with sqlite3.connect(DATABASE_PATH) as db:
                    db.execute("UPDATE dayler_invoices SET status = 'PAID' WHERE invoice_id = ? AND status = 'PENDING'", (invoice_id,))
                await query.message.reply_text("✅ WolvPay confirma que tu pago está realizado. El equipo de UnaRed continuará con tu solicitud.")
                await context.bot.send_message(
                    chat_id=int(ADMIN_CHAT_ID),
                    text=f"💚 PAGO DAYLER CONFIRMADO | UNARED\\nCliente: {'@' + update.effective_user.username if update.effective_user.username else 'No tiene username público'}\\nFactura: {invoice_id}\\nCliente Telegram ID: {update.effective_user.id}\\nEstado: PAGADO (consulta manual verificada con WolvPay)."
                )
            else:
                await query.message.reply_text("⏳ WolvPay todavía no confirma el pago. Espera unos minutos y vuelve a pulsar «Verificar pago».")
        except (aiohttp.ClientError, asyncio.TimeoutError, sqlite3.Error, InvalidOperation, ValueError, TypeError):
            logger.exception("Error during manual WolvPay verification.")
            await query.message.reply_text("No pudimos verificar el pago en este momento. Inténtalo más tarde.")
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
        await query.message.reply_photo(
            photo="https://i.ibb.co/21033K6c/Creating-promotional-image-design-310bdb13.jpg",
            caption=(
                "🔐 OTP Verification System v3.2\n\n"
                "💵 Precio: US$35"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Comprar $35", callback_data="botdemo_buy_otp")],
                [InlineKeyboardButton("📩 Contactar", url="https://t.me/flowmontana777")],
                [InlineKeyboardButton("⬅️ Volver al catálogo", callback_data="tool_bots")],
            ]),
        )
        return

    if choice == "botproduct_ssn":
        await query.message.reply_photo(
            photo="https://i.ibb.co/RpJHvdrL/Create-promotional-image-with-logo-fb0d71ac.jpg",
            caption="💚 UNARED | BOT SSN\\n\\nConsulta información y disponibilidad con nuestro equipo.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Comprar $35", callback_data="botdemo_buy_ssn")],
                [InlineKeyboardButton("📩 Contactar", url="https://t.me/flowmontana777")],
                [InlineKeyboardButton("⬅️ Volver al catálogo", callback_data="tool_bots")],
            ]),
        )
        return

    if choice == "botproduct_check":
        await query.message.reply_photo(
            photo="https://i.ibb.co/HDb1BtDq/Create-Bot-Check-promotional-image-2a47bb9b.jpg",
            caption="💚 UNARED | BOT CHECK\\n\\nConsulta información y disponibilidad con nuestro equipo.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Comprar $35", callback_data="botdemo_buy_check")],
                [InlineKeyboardButton("📩 Contactar", url="https://t.me/flowmontana777")],
                [InlineKeyboardButton("⬅️ Volver al catálogo", callback_data="tool_bots")],
            ]),
        )
        return

    # DEMOS AISLADAS: DATOS SINTÉTICOS; NO HAY CONSULTAS A DATOS REALES
    if choice.startswith("botdemo_buy_"):
        product = choice.rsplit("_", 1)[-1]
        labels = {"otp": "BOT OTP", "ssn": "BOT SSN", "check": "BOT CHECK"}
        if product not in labels:
            await query.message.reply_text("Producto no disponible.")
            return
        if not WOLVPAY_API_KEY:
            await query.message.reply_text("El pago automático no está configurado.")
            return
        user = update.effective_user
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{WOLVPAY_API_URL}/invoices",
                    headers={"Authorization": f"Bearer {WOLVPAY_API_KEY}", "Content-Type": "application/json"},
                    json={"amount": 35, "currency": "USD", "coin": "trc20_usdt",
                          "description": f"UNARED_SANDBOX_DEMO|product={product}|telegram_id={user.id}",
                          "white_label": False},
                    timeout=aiohttp.ClientTimeout(total=25),
                ) as response:
                    payload = await response.json(content_type=None)
                    if response.status not in (200, 201) or payload.get("success") is False:
                        raise RuntimeError("WolvPay invoice creation failed")
            data = payload.get("data") or payload
            invoice_id = data.get("invoice_id")
            invoice_url = data.get("url") or data.get("payment_url")
            if not invoice_id or not invoice_url:
                raise RuntimeError("Incomplete invoice response")
            with sqlite3.connect(DATABASE_PATH) as db:
                db.execute("""CREATE TABLE IF NOT EXISTS demo_bot_invoices (
                    invoice_id TEXT PRIMARY KEY, telegram_id INTEGER NOT NULL, amount TEXT NOT NULL,
                    product TEXT NOT NULL, username TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING'
                )""")
                db.execute(
                    "INSERT INTO demo_bot_invoices VALUES (?, ?, ?, ?, ?, 'PENDING')",
                    (invoice_id, user.id, "35.00", product, user.username or ""),
                )
            asyncio.create_task(schedule_payment_reminder(context.application, "demo_bot_invoices", invoice_id, user.id, "35", labels[product], invoice_url))
            await query.message.reply_text(
                f"💚 UNARED | FACTURA\nProducto: {labels[product]}\nImporte: US$35\nFactura: {invoice_id}\n"
                "Uso de demostración con datos ficticios únicamente.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Abrir factura y pagar", url=invoice_url)],
                    [InlineKeyboardButton("🔎 Verificar pago", callback_data=f"botdemo_verify_{product}")],
                    [InlineKeyboardButton("✅ ¡Ya pagué!", callback_data=f"botdemo_paid_{product}")],
                    [InlineKeyboardButton("⬅️ Volver", callback_data="tool_bots")],
                ]),
            )
        except Exception:
            logger.exception("Error creando factura de demo sandbox.")
            await query.message.reply_text("No pudimos generar la factura. Inténtalo más tarde.")
        return

    if choice.startswith("botdemo_paid_"):
        product = choice.rsplit("_", 1)[-1]
        labels = {"otp": "BOT OTP", "ssn": "BOT SSN", "check": "BOT CHECK"}
        if product not in labels:
            await query.message.reply_text("Producto no disponible.")
            return
        with sqlite3.connect(DATABASE_PATH) as db:
            row = db.execute(
                "SELECT invoice_id, amount, status FROM demo_bot_invoices WHERE telegram_id = ? AND product = ? ORDER BY rowid DESC LIMIT 1",
                (update.effective_user.id, product),
            ).fetchone()
        if not row:
            await query.message.reply_text("No encontramos una factura asociada a tu cuenta.")
            return
        invoice_id, amount, status = row
        await context.bot.send_message(
            chat_id=int(ADMIN_CHAT_ID),
            text=("🔔 CLIENTE INDICA QUE PAGÓ | UNARED\nProducto: " + labels[product] +
                  "\nCliente: @" + (update.effective_user.username or "sin_username") +
                  "\nTelegram ID: " + str(update.effective_user.id) +
                  "\nFactura: " + invoice_id + "\nImporte: US$" + str(amount) +
                  "\nEstado registrado: " + str(status) +
                  "\nAviso informativo: no confirma el pago; verificar en WolvPay."),
        )
        await query.message.reply_text("📨 Aviso enviado al equipo. El pago sigue pendiente hasta confirmación de WolvPay.")
        return

    if choice.startswith("botdemo_verify_"):
        product = choice.rsplit("_", 1)[-1]
        labels = {"otp": "BOT OTP", "ssn": "BOT SSN", "check": "BOT CHECK"}
        if product not in labels:
            await query.message.reply_text("Producto no disponible.")
            return
        if not WOLVPAY_API_KEY:
            await query.message.reply_text("La verificación automática no está configurada.")
            return
        try:
            with sqlite3.connect(DATABASE_PATH) as db:
                row = db.execute(
                    "SELECT invoice_id, amount, status FROM demo_bot_invoices WHERE telegram_id = ? AND product = ? ORDER BY rowid DESC LIMIT 1",
                    (update.effective_user.id, product),
                ).fetchone()
            if not row:
                await query.message.reply_text("No encontramos una factura asociada a tu cuenta.")
                return
            invoice_id, amount, current = row
            if current == "PAID":
                await query.message.reply_text("✅ El pago ya está confirmado.")
                return
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{WOLVPAY_API_URL}/invoices/{invoice_id}",
                    headers={"Authorization": f"Bearer {WOLVPAY_API_KEY}"},
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as response:
                    payload = await response.json(content_type=None)
                    if response.status != 200:
                        await query.message.reply_text("No pudimos consultar la factura.")
                        return
            invoice = payload.get("data") or payload
            paid = (str(invoice.get("status", "")).upper() == "PAID"
                    and str(invoice.get("invoice_id", invoice_id)) == invoice_id
                    and Decimal(str(invoice.get("amount", "0"))) == Decimal(amount))
            if not paid:
                await query.message.reply_text("⏳ WolvPay todavía no confirma el pago.")
                return
            with sqlite3.connect(DATABASE_PATH) as db:
                db.execute("UPDATE demo_bot_invoices SET status = 'PAID' WHERE invoice_id = ?", (invoice_id,))
            await query.message.reply_text("✅ WolvPay confirma el pago de la demo sandbox.")
            await context.bot.send_message(
                chat_id=int(ADMIN_CHAT_ID),
                text=("💚 DEMO SANDBOX PAGADA | " + labels[product] +
                      "\nCliente Telegram ID: " + str(update.effective_user.id) +
                      "\nImporte: US$" + str(amount) + "\nFactura: " + invoice_id +
                      "\nEstado: PAID verificado con WolvPay."),
            )
        except (aiohttp.ClientError, asyncio.TimeoutError, sqlite3.Error, InvalidOperation, ValueError, TypeError):
            logger.exception("Error verificando pago de demo sandbox.")
            await query.message.reply_text("No pudimos verificar el pago en este momento.")
        return

    if choice == "tool_pyp":
        await query.message.reply_photo(
            photo="https://i.ibb.co/Nqmk8fV/Promotional-graphic-card-design-9f04e875-2-K.jpg",
            caption=(
                "💚 UNARED | MÉTODO PyP\n\n"
                "🎉 OFERTA PARA CLIENTES NUEVOS: US$100\n\n"
                "Aquí podrás encontrar información sobre oportunidades de pagos legítimos en Alemania.\n\n"
                "📋 Requisitos: móvil y traductor.\n\n"
                "Fue mi primera experiencia y todavía está activa; hoy la comparto "
                "con quienes desean conocer estas oportunidades."
            ),
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
                "💚 UNARED | PÁGINAS WEB\n\n"
                "Catálogo de páginas web para comercios legítimos.\n"
                "🏷️ Precio por unidad: US$17\n"
                "Precio regular: US$20\n\n"
                f"📦 Cantidad: {quantity}\n"
                f"💵 Total: US${total}"
            ),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("➖", callback_data="pages_qty_minus"),
                    InlineKeyboardButton(str(quantity), callback_data="pages_qty_display"),
                    InlineKeyboardButton("➕", callback_data="pages_qty_plus"),
                ],
                [InlineKeyboardButton("💳 ¡Pagar!", callback_data="pages_pay")],
                [InlineKeyboardButton("📋 Solicitar selección", url="https://t.me/flowmontana777")],
                [InlineKeyboardButton("⬅️ Volver a Herramientas", callback_data="menu_tools")],
            ]),
        )
        return

    if choice in ("pages_qty_plus", "pages_qty_minus"):
        quantity = int(context.user_data.get("pages_quantity", 1))
        quantity = min(quantity + 1, 99) if choice == "pages_qty_plus" else max(quantity - 1, 1)
        context.user_data["pages_quantity"] = quantity
        total = quantity * 17
        await query.edit_message_caption(
            caption=(
                "💚 UNARED | PÁGINAS WEB\n\n"
                "Catálogo de páginas web para comercios legítimos.\n"
                "🏷️ Precio por unidad: US$17\n"
                "Precio regular: US$20\n\n"
                f"📦 Cantidad: {quantity}\n"
                f"💵 Total: US${total}"
            ),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("➖", callback_data="pages_qty_minus"),
                    InlineKeyboardButton(str(quantity), callback_data="pages_qty_display"),
                    InlineKeyboardButton("➕", callback_data="pages_qty_plus"),
                ],
                [InlineKeyboardButton("💳 ¡Pagar!", callback_data="pages_pay")],
                [InlineKeyboardButton("📋 Solicitar selección", url="https://t.me/flowmontana777")],
                [InlineKeyboardButton("⬅️ Volver a Herramientas", callback_data="menu_tools")],
            ]),
        )
        return

    if choice == "pages_qty_display":
        await query.answer("Usa ➕ o ➖ para cambiar la cantidad.")
        return

    if choice == "pages_pay":
        quantity = int(context.user_data.get("pages_quantity", 1))
        context.user_data["pages_checkout_quantity"] = quantity
        total = quantity * 17
        await query.message.reply_text(
            "💚 UNARED | PAGO DE PÁGINAS WEB\n\n"
            f"📦 Cantidad: {quantity}\n"
            f"💵 Total: US${total}\n\n"
            "Selecciona tu método de pago:",
            reply_markup=pages_coin_menu(),
        )
        return

    if choice.startswith("pages_coin_"):
        coin = choice.replace("pages_coin_", "", 1)
        if coin not in ("btc", "trc20_usdt"):
            await query.message.reply_text("Método de pago no disponible.")
            return
        if not WOLVPAY_API_KEY:
            await query.message.reply_text("El pago automático no está configurado. Contacta al equipo de UnaRed.")
            return
        quantity = int(context.user_data.get("pages_checkout_quantity", 1))
        total = quantity * 17
        user = update.effective_user
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{WOLVPAY_API_URL}/invoices",
                    headers={"Authorization": f"Bearer {WOLVPAY_API_KEY}", "Content-Type": "application/json"},
                    json={
                        "amount": total,
                        "currency": "USD",
                        "coin": coin,
                        "description": f"UNARED_PAGINAS_WEB|telegram_id={user.id}|quantity={quantity}",
                        "white_label": False,
                    },
                    timeout=aiohttp.ClientTimeout(total=25),
                ) as response:
                    payload = await response.json(content_type=None)
                    if response.status not in (200, 201) or payload.get("success") is False:
                        logger.error("WolvPay pages invoice error: HTTP %s; response=%s", response.status, payload)
                        raise RuntimeError("Invoice creation failed")
            data = payload.get("data") or payload
            invoice_id = data.get("invoice_id")
            invoice_url = data.get("url") or data.get("payment_url")
            if not invoice_id or not invoice_url:
                logger.error("Incomplete WolvPay pages response: %s", payload)
                raise RuntimeError("Incomplete invoice response")
            with sqlite3.connect(DATABASE_PATH) as db:
                db.execute("""CREATE TABLE IF NOT EXISTS pages_invoices (
                    invoice_id TEXT PRIMARY KEY,
                    telegram_id INTEGER NOT NULL,
                    amount TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING'
                )""")
                db.execute(
                    "INSERT INTO pages_invoices (invoice_id, telegram_id, amount, quantity, status) VALUES (?, ?, ?, ?, 'PENDING')",
                    (invoice_id, user.id, str(total), quantity),
                )
            asyncio.create_task(schedule_payment_reminder(context.application, "pages_invoices", invoice_id, user.id, str(total), "Páginas Web", invoice_url))
            await query.message.reply_text(
                "💚 UNARED | FACTURA DE PÁGINAS WEB\n\n"
                f"📦 Cantidad: {quantity}\n"
                f"💵 Total: US${total}\n"
                f"🧾 Factura: {invoice_id}\n\n"
                "Completa el pago desde WolvPay.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Abrir factura y pagar", url=invoice_url)],
                    [InlineKeyboardButton("🔎 Verificar pago", callback_data="pages_verify")],
                    [InlineKeyboardButton("✅ ¡Ya pagué!", callback_data="pages_paid")],
                    [InlineKeyboardButton("⬅️ Volver a Herramientas", callback_data="menu_tools")],
                ]),
            )
        except Exception:
            logger.exception("No se pudo crear la factura WolvPay para Páginas Web.")
            await query.message.reply_text(
                "No pudimos generar la factura. No realices transferencias manuales; inténtalo más tarde o contacta al equipo."
            )
        return

    if choice == "pages_paid":
        try:
            with sqlite3.connect(DATABASE_PATH) as db:
                row = db.execute(
                    "SELECT invoice_id, amount, quantity, status FROM pages_invoices WHERE telegram_id = ? ORDER BY rowid DESC LIMIT 1",
                    (update.effective_user.id,),
                ).fetchone()
            if not row:
                await query.message.reply_text("No encontramos una factura de páginas web asociada a tu cuenta.")
                return
            invoice_id, amount, quantity, status = row
            if status == "PAID":
                await query.message.reply_text("✅ Tu pago ya está confirmado. El equipo continuará con tu solicitud.")
                return
            username = update.effective_user.username
            username_text = f"@{username}" if username else "No tiene username público"
            await context.bot.send_message(
                chat_id=int(ADMIN_CHAT_ID),
                text=(
                    "🔔 AVISO DE PAGO | PÁGINAS WEB\\n"
                    f"Cliente: {username_text}\\n"
                    f"Cliente Telegram ID: {update.effective_user.id}\\n"
                    f"Cantidad: {quantity}\\nImporte: US${amount}\\nFactura: {invoice_id}\\n"
                    "El cliente pulsó «¡Ya pagué!». El pago sigue pendiente de verificación automática."
                ),
            )
            await query.message.reply_text("📩 Avisamos al equipo de UnaRed. Tu pago todavía debe ser confirmado por WolvPay; no envíes otro pago.")
        except (sqlite3.Error, ValueError, TypeError):
            logger.exception("Error procesando el aviso de pago de Páginas Web.")
            await query.message.reply_text("No pudimos registrar el aviso ahora. Inténtalo de nuevo.")
        return
    if choice == "pages_verify":
        if not WOLVPAY_API_KEY:
            await query.message.reply_text("La verificación automática no está disponible.")
            return
        try:
            with sqlite3.connect(DATABASE_PATH) as db:
                db.execute("""CREATE TABLE IF NOT EXISTS pages_invoices (
                    invoice_id TEXT PRIMARY KEY,
                    telegram_id INTEGER NOT NULL,
                    amount TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING'
                )""")
                row = db.execute(
                    "SELECT invoice_id, amount, quantity, status FROM pages_invoices WHERE telegram_id = ? ORDER BY rowid DESC LIMIT 1",
                    (update.effective_user.id,),
                ).fetchone()
            if not row:
                await query.message.reply_text("No encontramos una factura de páginas web asociada a tu cuenta.")
                return
            invoice_id, expected_amount, quantity, current_status = row
            if current_status == "PAID":
                await query.message.reply_text("✅ Tu pago ya está confirmado.")
                return
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{WOLVPAY_API_URL}/invoices/{invoice_id}",
                    headers={"Authorization": f"Bearer {WOLVPAY_API_KEY}"},
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as response:
                    payload = await response.json(content_type=None)
                    if response.status != 200:
                        logger.error("WolvPay pages verification HTTP %s: %s", response.status, payload)
                        await query.message.reply_text("No pudimos consultar la factura. Inténtalo de nuevo.")
                        return
            invoice = payload.get("data") or payload
            paid = (
                str(invoice.get("status", "")).upper() == "PAID"
                and str(invoice.get("invoice_id", invoice_id)) == invoice_id
                and Decimal(str(invoice.get("amount", "0"))) == Decimal(expected_amount)
            )
            if not paid:
                await query.message.reply_text("⏳ WolvPay todavía no confirma el pago. Vuelve a verificar en unos minutos.")
                return
            with sqlite3.connect(DATABASE_PATH) as db:
                db.execute(
                    "UPDATE pages_invoices SET status = 'PAID' WHERE invoice_id = ? AND status = 'PENDING'",
                    (invoice_id,),
                )
            await query.message.reply_text("✅ WolvPay confirma tu pago. El equipo de UnaRed continuará con tu solicitud.")
            await context.bot.send_message(
                chat_id=int(ADMIN_CHAT_ID),
                text=(
                    "💚 PAGO DE PÁGINAS WEB CONFIRMADO | UNARED\n"
                    f"Cliente: {update.effective_user.id}\n"
                    f"Cantidad: {quantity}\n"
                    f"Importe: US${expected_amount}\n"
                    f"Factura: {invoice_id}"
                ),
            )
        except (aiohttp.ClientError, asyncio.TimeoutError, sqlite3.Error, InvalidOperation, ValueError, TypeError):
            logger.exception("Error verificando pago de páginas web.")
            await query.message.reply_text("No pudimos verificar el pago en este momento.")
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

    if choice == "tool_profiles":
        await query.message.reply_photo(
            photo="https://i.ibb.co/HTfzWz7m/Create-promotional-graphic-card-b9bb92c4-2-K.jpg",
            caption=(
                "💚 UNARED | PERFILES\n\n"
                "Selecciona el servicio que necesitas:"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Amazon", callback_data="tool_amazon")],
                [InlineKeyboardButton("🍎 iCloud", callback_data="tool_icloud")],
                [InlineKeyboardButton("💰 Préstamos", callback_data="tool_loans")],
                [InlineKeyboardButton("⬅️ Volver a Herramientas", callback_data="menu_tools")],
            ]),
        )
        return

    if choice in ("tool_amazon", "tool_loans"):
        label = "AMAZON" if choice == "tool_amazon" else "PRÉSTAMOS"
        await query.message.reply_text(
            f"💚 UNARED | {label}\n\nEste servicio estará disponible próximamente.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⏳ Próximamente", callback_data="profiles_coming_soon")],
                [InlineKeyboardButton("⬅️ Volver a Perfiles", callback_data="tool_profiles")],
            ]),
        )
        return

    if choice == "profiles_coming_soon":
        await query.answer("Este servicio estará disponible próximamente.")
        return

    if choice == "tool_icloud":
        quantity = int(context.user_data.get("icloud_quantity", 1))
        quantity = max(1, min(quantity, 99))
        context.user_data["icloud_quantity"] = quantity
        total = quantity * 25
        await query.message.reply_text(
            "💚 UNARED | ICLOUD\n\nAsistencia legítima para configurar iCloud en tu propio dispositivo. "
            "No compartas contraseñas ni códigos de verificación.\n\n"
            "🏷️ Precio por servicio: US$25\n"
            f"📦 Cantidad: {quantity}\n💵 Total: US${total}",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("➖", callback_data="icloud_qty_minus"),
                    InlineKeyboardButton(str(quantity), callback_data="icloud_qty_display"),
                    InlineKeyboardButton("➕", callback_data="icloud_qty_plus"),
                ],
                [InlineKeyboardButton("💳 ¡Pagar!", callback_data="icloud_pay")],
                [InlineKeyboardButton("📩 Contactar", url="https://t.me/flowmontana777")],
                [InlineKeyboardButton("⬅️ Volver a Perfiles", callback_data="tool_profiles")],
            ]),
        )
        return

    if choice in ("icloud_qty_plus", "icloud_qty_minus"):
        quantity = int(context.user_data.get("icloud_quantity", 1))
        quantity = min(quantity + 1, 99) if choice == "icloud_qty_plus" else max(quantity - 1, 1)
        context.user_data["icloud_quantity"] = quantity
        total = quantity * 25
        await query.edit_message_text(
            "💚 UNARED | ICLOUD\n\nAsistencia legítima para configurar iCloud en tu propio dispositivo. "
            "No compartas contraseñas ni códigos de verificación.\n\n"
            "🏷️ Precio por servicio: US$25\n"
            f"📦 Cantidad: {quantity}\n💵 Total: US${total}",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("➖", callback_data="icloud_qty_minus"),
                    InlineKeyboardButton(str(quantity), callback_data="icloud_qty_display"),
                    InlineKeyboardButton("➕", callback_data="icloud_qty_plus"),
                ],
                [InlineKeyboardButton("💳 ¡Pagar!", callback_data="icloud_pay")],
                [InlineKeyboardButton("📩 Contactar", url="https://t.me/flowmontana777")],
                [InlineKeyboardButton("⬅️ Volver a Perfiles", callback_data="tool_profiles")],
            ]),
        )
        return

    if choice == "icloud_qty_display":
        await query.answer("Usa ➕ o ➖ para cambiar la cantidad.")
        return

    if choice == "icloud_pay":
        quantity = int(context.user_data.get("icloud_quantity", 1))
        total = quantity * 25
        context.user_data["icloud_checkout_quantity"] = quantity
        await query.message.reply_text(
            "💚 UNARED | PAGO DE ICLOUD\n\n"
            f"📦 Cantidad: {quantity}\n💵 Total: US${total}\n\n"
            "Selecciona tu método de pago:",
            reply_markup=icloud_coin_menu(),
        )
        return

    if choice.startswith("icloud_coin_"):
        coin = choice.replace("icloud_coin_", "", 1)
        if coin not in ("btc", "trc20_usdt"):
            await query.message.reply_text("Método de pago no disponible.")
            return
        if not WOLVPAY_API_KEY:
            await query.message.reply_text("El pago automático no está configurado. Contacta al equipo de UnaRed.")
            return
        user = update.effective_user
        quantity = int(context.user_data.get("icloud_checkout_quantity", 1))
        total = quantity * 25
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{WOLVPAY_API_URL}/invoices",
                    headers={"Authorization": f"Bearer {WOLVPAY_API_KEY}", "Content-Type": "application/json"},
                    json={"amount": total, "currency": "USD", "coin": coin,
                          "description": f"UNARED_ICLOUD|telegram_id={user.id}|quantity={quantity}", "white_label": False},
                    timeout=aiohttp.ClientTimeout(total=25),
                ) as response:
                    payload = await response.json(content_type=None)
                    if response.status not in (200, 201) or payload.get("success") is False:
                        logger.error("WolvPay iCloud invoice error: HTTP %s; response=%s", response.status, payload)
                        raise RuntimeError("Invoice creation failed")
            data = payload.get("data") or payload
            invoice_id = data.get("invoice_id")
            invoice_url = data.get("url") or data.get("payment_url")
            if not invoice_id or not invoice_url:
                raise RuntimeError("Incomplete invoice response")
            with sqlite3.connect(DATABASE_PATH) as db:
                db.execute("""CREATE TABLE IF NOT EXISTS icloud_invoices (
                    invoice_id TEXT PRIMARY KEY, telegram_id INTEGER NOT NULL,
                    amount TEXT NOT NULL, quantity INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'PENDING'
                )""")
                columns = [column[1] for column in db.execute("PRAGMA table_info(icloud_invoices)").fetchall()]
                if "quantity" not in columns:
                    db.execute("ALTER TABLE icloud_invoices ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1")
                db.execute("INSERT INTO icloud_invoices (invoice_id, telegram_id, amount, quantity, status) VALUES (?, ?, ?, ?, 'PENDING')", (invoice_id, user.id, str(total), quantity))
            asyncio.create_task(schedule_payment_reminder(context.application, "icloud_invoices", invoice_id, user.id, str(total), "iCloud", invoice_url))
            await query.message.reply_text(
                "💚 UNARED | FACTURA ICLOUD\n\n"
                f"📦 Cantidad: {quantity}\n💵 Total: US${total}\n"
                f"Factura: {invoice_id}\n\nCompleta el pago desde WolvPay.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Abrir factura y pagar", url=invoice_url)],
                    [InlineKeyboardButton("🔎 Verificar pago", callback_data="icloud_verify")],
                    [InlineKeyboardButton("✅ ¡Ya pagué!", callback_data="icloud_paid")],
                    [InlineKeyboardButton("⬅️ Volver a Perfiles", callback_data="tool_profiles")],
                ]),
            )
        except Exception:
            logger.exception("No se pudo generar la factura WolvPay para iCloud.")
            await query.message.reply_text("No pudimos generar la factura. Inténtalo más tarde o contacta al equipo.")
        return

    if choice in ("icloud_paid", "icloud_verify"):
        if not WOLVPAY_API_KEY:
            await query.message.reply_text("La verificación automática no está disponible.")
            return
        try:
            with sqlite3.connect(DATABASE_PATH) as db:
                db.execute("""CREATE TABLE IF NOT EXISTS icloud_invoices (
                    invoice_id TEXT PRIMARY KEY, telegram_id INTEGER NOT NULL,
                    amount TEXT NOT NULL, quantity INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'PENDING'
                )""")
                columns = [column[1] for column in db.execute("PRAGMA table_info(icloud_invoices)").fetchall()]
                if "quantity" not in columns:
                    db.execute("ALTER TABLE icloud_invoices ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1")
                row = db.execute("SELECT invoice_id, amount, status FROM icloud_invoices WHERE telegram_id = ? ORDER BY rowid DESC LIMIT 1", (update.effective_user.id,)).fetchone()
            if not row:
                await query.message.reply_text("No encontramos una factura de iCloud asociada a tu cuenta.")
                return
            invoice_id, expected_amount, current_status = row
            if current_status == "PAID":
                await query.message.reply_text("✅ Tu pago ya está confirmado. El equipo continuará con tu solicitud.")
                return
            if choice == "icloud_paid":
                await context.bot.send_message(
                    chat_id=int(ADMIN_CHAT_ID),
                    text=("🔔 AVISO DE PAGO | ICLOUD\n"
                          f"Cliente: {'@' + update.effective_user.username if update.effective_user.username else 'No tiene username público'}\n"
                          f"Cliente Telegram ID: {update.effective_user.id}\n"
                          f"Importe: US${expected_amount}\nFactura: {invoice_id}\n"
                          "El cliente pulsó «¡Ya pagué!». El pago sigue pendiente de verificación automática."),
                )
                await query.message.reply_text("📩 Avisamos al equipo de UnaRed. El pago aún debe ser confirmado por WolvPay.")
                return
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{WOLVPAY_API_URL}/invoices/{invoice_id}",
                    headers={"Authorization": f"Bearer {WOLVPAY_API_KEY}"},
                    timeout=aiohttp.ClientTimeout(total=20)) as response:
                    payload = await response.json(content_type=None)
                    if response.status != 200:
                        await query.message.reply_text("No pudimos consultar la factura. Inténtalo de nuevo.")
                        return
            invoice = payload.get("data") or payload
            paid = (str(invoice.get("status", "")).upper() == "PAID"
                    and str(invoice.get("invoice_id", invoice_id)) == invoice_id
                    and Decimal(str(invoice.get("amount", "0"))) == Decimal(expected_amount))
            if not paid:
                await query.message.reply_text("⏳ WolvPay todavía no confirma el pago. Vuelve a verificar en unos minutos.")
                return
            with sqlite3.connect(DATABASE_PATH) as db:
                db.execute("UPDATE icloud_invoices SET status = 'PAID' WHERE invoice_id = ? AND status = 'PENDING'", (invoice_id,))
            await query.message.reply_text("✅ WolvPay confirma tu pago. El equipo de UnaRed continuará con tu solicitud.")
            await context.bot.send_message(chat_id=int(ADMIN_CHAT_ID),
                text=f"💚 PAGO ICLOUD CONFIRMADO | UNARED\nCliente Telegram ID: {update.effective_user.id}\nImporte: US${expected_amount}\nFactura: {invoice_id}")
        except (aiohttp.ClientError, asyncio.TimeoutError, sqlite3.Error, InvalidOperation, ValueError, TypeError):
            logger.exception("Error procesando iCloud payment action.")
            await query.message.reply_text("No pudimos procesar la solicitud en este momento.")
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
        await query.message.reply_video(
            video="https://cdn.rapidfile.cc/Zj9CDYTzLH/Logo_pulsing_in_neon_light_5a417536.mp4",
            caption=(
                "📄 UNARED | QUIERO EDITAR Y SUBIR PAPEL\n\n"
                "💵 Precio: US$250\n\n"
                "🎥 ¿Qué recibes?\n"
                "• Una videollamada editando con UnaRed\n"
                "• Link de Photoshop ilimitado con licencia\n"
                "• Papel para empezar\n"
                "• Contacto para comprar papel\n\n"
                "Después de pagar, pulsa «Ya Pagué» y envía el comprobante."
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Comprar US$250", callback_data="edit_upload_buy")],
                [InlineKeyboardButton("💳 Otro método de pago", url="https://t.me/flowmontana777")],
                [InlineKeyboardButton("ℹ️ Quiero Saber Más", url="https://t.me/flowmontana777")],
            ]),
        )
        return

    if choice == "edit_upload_buy":
        await query.message.reply_text(
            "💚 UNARED | PAGO DE QUIERO EDITAR Y SUBIR PAPEL\n\n"
            "💵 Importe: US$250\n\n"
            "Selecciona tu método de pago:",
            reply_markup=edit_upload_coin_menu(),
        )
        return

    if choice.startswith("edit_upload_coin_"):
        coin = choice.replace("edit_upload_coin_", "", 1)
        if coin not in ("btc", "trc20_usdt"):
            await query.message.reply_text("Método de pago no disponible.")
            return
        if not WOLVPAY_API_KEY:
            await query.message.reply_text("El pago automático no está configurado. Contacta al equipo de UnaRed.")
            return
        user = update.effective_user
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{WOLVPAY_API_URL}/invoices",
                    headers={"Authorization": f"Bearer {WOLVPAY_API_KEY}", "Content-Type": "application/json"},
                    json={
                        "amount": 250,
                        "currency": "USD",
                        "coin": coin,
                        "description": f"UNARED_EDITAR_SUBIR_PAPEL|telegram_id={user.id}",
                        "white_label": False,
                    },
                    timeout=aiohttp.ClientTimeout(total=25),
                ) as response:
                    payload = await response.json(content_type=None)
                    if response.status not in (200, 201) or payload.get("success") is False:
                        logger.error("WolvPay edit/upload invoice error: HTTP %s; response=%s", response.status, payload)
                        raise RuntimeError("Invoice creation failed")
            data = payload.get("data") or payload
            invoice_id = data.get("invoice_id")
            invoice_url = data.get("url") or data.get("payment_url")
            if not invoice_id or not invoice_url:
                logger.error("Incomplete WolvPay edit/upload response: %s", payload)
                raise RuntimeError("Incomplete invoice response")
            with sqlite3.connect(DATABASE_PATH) as db:
                db.execute("""CREATE TABLE IF NOT EXISTS edit_upload_invoices (
                    invoice_id TEXT PRIMARY KEY,
                    telegram_id INTEGER NOT NULL,
                    amount TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING'
                )""")
                db.execute(
                    "INSERT INTO edit_upload_invoices (invoice_id, telegram_id, amount, status) VALUES (?, ?, '250', 'PENDING')",
                    (invoice_id, user.id),
                )
            asyncio.create_task(schedule_payment_reminder(context.application, "edit_upload_invoices", invoice_id, user.id, "250", "Editar y subir papel", invoice_url))
            await query.message.reply_text(
                "💚 UNARED | FACTURA - QUIERO EDITAR Y SUBIR PAPEL\n\n"
                "💵 Total: US$250\n"
                f"🧾 Factura: {invoice_id}\n\n"
                "Completa el pago desde WolvPay. La confirmación se enviará automáticamente cuando el proveedor verifique el pago.\n",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Abrir factura y pagar", url=invoice_url)],
                    [InlineKeyboardButton("✅ Ya Pagué", callback_data="edit_upload_invoice_paid")],
                    [InlineKeyboardButton("💬 Contactar a UnaRed", url="https://t.me/flowmontana777")],
                    [InlineKeyboardButton("⬅️ Volver a Herramientas", callback_data="menu_tools")],
                ]),
            )
        except Exception:
            logger.exception("No se pudo crear la factura WolvPay para Editar y Subir Papel.")
            await query.message.reply_text(
                "No pudimos generar la factura. No realices transferencias manuales; inténtalo más tarde o contacta al equipo."
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

    if choice == "edit_upload_invoice_paid":
        user = update.effective_user
        with sqlite3.connect(DATABASE_PATH) as db:
            invoice = db.execute(
                "SELECT invoice_id, amount, status FROM edit_upload_invoices WHERE telegram_id = ? ORDER BY rowid DESC LIMIT 1",
                (user.id,),
            ).fetchone()
        if not invoice:
            await query.message.reply_text("No encontramos una factura de este servicio asociada a tu cuenta.")
            return
        invoice_id, amount, status = invoice
        if str(status).upper() == "PAID":
            await query.message.reply_text("✅ El pago de esta factura ya está confirmado.")
            return
        username = f"@{user.username}" if user.username else "Sin username público"
        await context.bot.send_message(
            chat_id=int(ADMIN_CHAT_ID),
            text=(
                "💚 UNARED | AVISO: CLIENTE INDICA QUE PAGÓ\\n\\n"
                f"👤 Cliente: {user.full_name}\\n"
                f"🔗 Usuario: {username}\\n"
                f"🆔 Telegram ID: {user.id}\\n"
                "📄 Servicio: Quiero Editar y Subir Papel\\n"
                f"💵 Importe: US${amount}\\n"
                f"🧾 Factura: {invoice_id}\\n"
                "🟡 Estado: Cliente pulsó «Ya Pagué»; pendiente de confirmación automática de WolvPay."
            ),
        )
        await query.message.reply_text(
            "📩 Recibimos tu aviso. Estamos esperando la confirmación del pago por WolvPay. "
            "No necesitas enviar el comprobante por aquí."
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
                    "📩 NUEVA SOLICITUD DE INFORMACIÓN | UNARED\n\n"
                    f"👤 Cliente: {user.full_name}\n"
                    f"🔗 Telegram: {username}\n"
                    f"🆔 ID: {user.id}\n"
                    f"📝 Consulta: {description}\n\n"
                    "📲 Abre el perfil del cliente en Telegram para comunicarte con él."
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
# IMPORTAR MUSICA PUBLICADA EN EL CANAL UNARED
# =====================================

async def channel_music_ingest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post
    if not message or not message.chat or (message.chat.username or "").lower() != "una1red":
        return

    audio = message.audio
    if not audio:
        return
    if audio.mime_type and audio.mime_type not in ("audio/mpeg", "audio/mp3"):
        return

    title = (audio.title or message.caption or "Canción de UnaRed").strip()[:120]
    performer = (audio.performer or "").strip()[:120]
    with sqlite3.connect(DATABASE_PATH) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS digital_music (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT NOT NULL,
            title TEXT NOT NULL,
            performer TEXT NOT NULL DEFAULT '',
            submitted_by INTEGER NOT NULL,
            submitter_name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'PENDING',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS digital_music_subscribers (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL DEFAULT '',
            full_name TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        exists = db.execute(
            "SELECT id FROM digital_music WHERE file_id = ? LIMIT 1",
            (audio.file_id,),
        ).fetchone()
        if exists:
            return
        db.execute(
            """INSERT INTO digital_music
               (file_id, title, performer, submitted_by, submitter_name, status)
               VALUES (?, ?, ?, ?, ?, 'APPROVED')""",
            (audio.file_id, title, performer, 0, "Canal @Una1Red"),
        )
        subscribers = [
            row[0] for row in db.execute(
                "SELECT telegram_id FROM digital_music_subscribers"
            ).fetchall()
        ]

    notification = (
        "🎵 ¡NUEVA MÚSICA EN UNARED!\n\n"
        f"🎧 {title}\n"
        + (f"👤 {performer}\n" if performer else "")
        + "\nYa está disponible en Modo Digital. "
          "Entra al bot y selecciona «Modo Digital» → «Escuchar música»."
    )
    sent = 0
    for telegram_id in subscribers:
        try:
            await context.bot.send_message(chat_id=telegram_id, text=notification)
            sent += 1
        except Exception as exc:
            logger.warning("No se pudo notificar al usuario %s: %s", telegram_id, exc)

    logger.info(
        "Canción importada desde @Una1Red: %s. Notificaciones enviadas: %s/%s",
        title, sent, len(subscribers)
    )


# =====================================
# RECIBIR SOLICITUDES
# =====================================

async def receive_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Los mensajes de grupos/canales no son solicitudes de clientes.
    # La música de @Una1Red se procesa únicamente en channel_music_ingest.
    if not update.effective_chat or update.effective_chat.type != "private":
        return

    if context.user_data.get("music_upload_mode"):
        message = update.message
        if not message.audio:
            await message.reply_text(
                "Para que se pueda reproducir dentro de Telegram, envía el MP3 como audio, no como documento. "
                "Pulsa el clip y selecciona «Audio»."
            )
            return
        audio = message.audio
        if audio.mime_type and audio.mime_type not in ("audio/mpeg", "audio/mp3"):
            await message.reply_text("Por ahora solo aceptamos archivos MP3.")
            return
        user = update.effective_user
        title = (audio.title or "Canción enviada").strip()[:120]
        performer = (audio.performer or "").strip()[:120]
        with sqlite3.connect(DATABASE_PATH) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS digital_music (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL,
                title TEXT NOT NULL,
                performer TEXT NOT NULL DEFAULT '',
                submitted_by INTEGER NOT NULL,
                submitter_name TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'PENDING',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            cursor = db.execute(
                """INSERT INTO digital_music
                   (file_id, title, performer, submitted_by, submitter_name, status)
                   VALUES (?, ?, ?, ?, ?, 'PENDING')""",
                (audio.file_id, title, performer, user.id, user.full_name[:120]),
            )
            song_id = cursor.lastrowid
        admin_caption = (
            "🎵 NUEVA CANCIÓN PARA REVISAR | UNARED\n\n"
            f"🎼 Título: {title}\n"
            f"🎤 Artista: {performer or 'No indicado'}\n"
            f"👤 Enviada por: {user.full_name}\n"
            f"🆔 Telegram ID: {user.id}\n"
            "🟡 Estado: pendiente de aprobación.\n"
            "Confirma que tienes autorización para compartir esta grabación."
        )
        try:
            await context.bot.send_audio(
                chat_id=int(ADMIN_CHAT_ID),
                audio=audio.file_id,
                caption=admin_caption,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Aprobar", callback_data=f"music_approve_{song_id}")],
                    [InlineKeyboardButton("❌ Rechazar", callback_data=f"music_reject_{song_id}")],
                ]),
            )
            context.user_data.pop("music_upload_mode", None)
            await message.reply_text(
                "✅ Recibimos tu canción. Quedó pendiente de revisión y solo aparecerá en el catálogo si UnaRed la aprueba."
            )
        except Exception:
            logger.exception("No se pudo enviar la canción %s al administrador.", song_id)
            await message.reply_text(
                "La canción quedó registrada, pero no pudimos enviarla para revisión. Inténtalo más tarde."
            )
        return

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
            "Monto indicado: US$250\n"
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
        await update.message.reply_photo(
            photo="https://i.ibb.co/Ng1nYXJR/Create-promotional-graphic-card-f640c15b.jpg",
            caption=(
                "🔐 Crea la contraseña para tu nueva cuenta SIP.\n\n"
                "Debe tener entre 8 y 64 caracteres. No uses la contraseña de otra cuenta."
            )
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
        await update.message.reply_photo(
            photo="https://i.ibb.co/BhJcTrj/Create-promotional-image-for-tel-a730da20-2-K-jpg-27254ce0-2-K.jpg",
            caption=(
                "💚 UNARED | RESUMEN DE TU ORDEN\n\n"
                "📞 Servicio: Alquiler de línea SIP para MicroSIP.\n\n"
                f"👤 Usuario SIP: {context.user_data.get('dayler_username')}\n"
                f"🔐 Contraseña SIP (confirma que esté correcta): {password}\n\n"
                "💰 Total a pagar: US$150\n\n"
                "🎁 BENEFICIO INCLUIDO:\n"
                "Recibirás US$50 de saldo acreditado en tu panel, disponible para realizar llamadas desde MicroSIP.\n\n"
                "📲 ¿QUÉ RECIBES?\n"
                "• Tu línea SIP.\n"
                "• Acceso y detalles de configuración.\n"
                "• US$50 de saldo para realizar llamadas.\n"
                "• Posibilidad de llamar a los bancos disponibles en el servicio.\n\n"
                "👇 Pulsa el botón para ver el método de pago y continuar con tu solicitud."
            ),
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
            f"👤 Cliente: {user.full_name}\n"
            f"🔗 Usuario Telegram: @{user.username or 'Sin usuario'}\n"
            f"🆔 ID Telegram: {user.id}\n"
            f"📞 Usuario SIP solicitado: {context.user_data.get('dayler_username', 'No indicado')}\n"
            f"🧾 Referencia de pago: {reference}\n"
            "🟡 Estado: pendiente de verificación manual."
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
            "💚 PAGO DE SERVICIO - UNARED\n\n"
            f"👤 Cliente: {user.full_name}\n"
            f"🔗 Usuario Telegram: @{user.username or 'Sin usuario'}\n"
            f"🧾 Categoría: {context.user_data.get('bill_category')}\n"
            f"💵 Monto: USD {context.user_data.get('bill_amount')}\n"
            f"🧾 Referencia: {reference}\n"
            "🟡 Estado: pendiente de verificación."
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
# WOLVPAY WEBHOOK
# =====================================

async def wolvpay_webhook(request):
    if not WOLVPAY_WEBHOOK_SECRET or not WOLVPAY_API_KEY:
        return web.Response(status=503, text="Payment integration is not configured.")

    raw_body = await request.read()
    signature = request.headers.get("X-WolvPay-Signature", "")
    expected = hmac.new(
        WOLVPAY_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not signature or not hmac.compare_digest(expected, signature):
        return web.Response(status=401, text="Invalid signature.")

    try:
        event = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return web.Response(status=400, text="Invalid JSON.")

    invoice_id = str(event.get("invoice_id", "")).strip()
    if not invoice_id:
        return web.Response(status=400, text="Missing invoice_id.")

    if str(event.get("status", "")).upper() != "PAID":
        return web.Response(status=200, text="Event ignored.")

    try:
        with sqlite3.connect(DATABASE_PATH) as db:
            row = db.execute(
                "SELECT telegram_id, amount, username, status FROM dayler_invoices WHERE invoice_id = ?",
                (invoice_id,),
            ).fetchone()
            invoice_type = "dayler"
            if not row:
                row = db.execute(
                    "SELECT telegram_id, amount, quantity, status FROM pages_invoices WHERE invoice_id = ?",
                    (invoice_id,),
                ).fetchone()
                invoice_type = "pages"
            if not row:
                row = db.execute(
                    "SELECT telegram_id, amount, quantity, status FROM icloud_invoices WHERE invoice_id = ?",
                    (invoice_id,),
                ).fetchone()
                invoice_type = "icloud"
            if not row:
                row = db.execute(
                    "SELECT telegram_id, amount, product, username, status FROM demo_bot_invoices WHERE invoice_id = ?",
                    (invoice_id,),
                ).fetchone()
                invoice_type = "demo"
            if not row:
                row = db.execute(
                    "SELECT telegram_id, amount, category, username, status FROM bill_invoices WHERE invoice_id = ?",
                    (invoice_id,),
                ).fetchone()
                invoice_type = "bill"
            if not row:
                row = db.execute(
                    "SELECT telegram_id, amount, status FROM edit_upload_invoices WHERE invoice_id = ?",
                    (invoice_id,),
                ).fetchone()
                invoice_type = "edit_upload"
    except sqlite3.Error:
        logger.exception("Could not read WolvPay invoice record.")
        return web.Response(status=500, text="Database error.")

    if not row:
        logger.warning("Received WolvPay event for unknown invoice %s", invoice_id)
        return web.Response(status=200, text="Unknown invoice ignored.")

    if invoice_type == "dayler":
        telegram_id, expected_amount, username, current_status = row
        customer_description = "Tu pago de US$150 para la solicitud Dayler fue confirmado automáticamente."
        order_detail = f"Usuario SIP solicitado: {username}"
        admin_detail = f"Usuario SIP solicitado: {username}\nImporte confirmado: US$150"
    elif invoice_type == "pages":
        telegram_id, expected_amount, quantity, current_status = row
        customer_description = "Tu pago de US$" + str(expected_amount) + f" por {quantity} página(s) web fue confirmado automáticamente."
        order_detail = f"Cantidad de páginas web: {quantity}"
        admin_detail = f"Cantidad: {quantity}\nImporte confirmado: US$" + str(expected_amount)
    elif invoice_type == "icloud":
        telegram_id, expected_amount, quantity, current_status = row
        customer_description = "Tu pago de US$" + str(expected_amount) + f" por {quantity} servicio(s) de configuración de iCloud fue confirmado automáticamente."
        order_detail = f"Servicio: configuración de iCloud en dispositivo propio (cantidad: {quantity})"
        admin_detail = f"Servicio: iCloud\nCantidad: {quantity}\nImporte confirmado: US$" + str(expected_amount)
    elif invoice_type == "edit_upload":
        telegram_id, expected_amount, current_status = row
        customer_description = "Tu pago de US$250 para el servicio Editar y Subir Papel fue confirmado automáticamente."
        order_detail = "Servicio: edición y preparación legítima de documentos propios"
        admin_detail = "Servicio: Editar y Subir Papel\\nImporte confirmado: US$" + str(expected_amount)
    elif invoice_type == "demo":
        telegram_id, expected_amount, product, username, current_status = row
        product_labels = {"otp": "BOT OTP", "ssn": "BOT SSN", "check": "BOT CHECK"}
        product_label = product_labels.get(product, "DEMO SANDBOX")
        customer_description = "Tu pago de US$35 para la demostración sandbox fue confirmado automáticamente."
        order_detail = f"Producto: {product_label} (datos sintéticos únicamente)"
        admin_detail = f"Producto: {product_label}\\nCliente: @{username or 'sin_username'}\\nImporte confirmado: US$" + str(expected_amount)
    else:
        telegram_id, expected_amount, category, username, current_status = row
        customer_description = "Tu pago de servicios fue confirmado automáticamente."
        order_detail = f"Servicio solicitado: {category}"
        admin_detail = f"Servicio: {category}\\nCliente: @{username or 'sin_username'}\\nImporte confirmado: US$" + str(expected_amount)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{WOLVPAY_API_URL}/invoices/{invoice_id}",
                headers={"Authorization": f"Bearer {WOLVPAY_API_KEY}"},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                invoice_payload = await response.json(content_type=None)
                if response.status != 200:
                    logger.error("WolvPay invoice verification returned HTTP %s", response.status)
                    return web.Response(status=502, text="Could not verify invoice.")
        invoice = invoice_payload.get("data") or invoice_payload
        verified_amount = Decimal(str(invoice.get("amount", "0")))
        if (
            str(invoice.get("invoice_id", invoice_id)) != invoice_id
            or str(invoice.get("status", "")).upper() != "PAID"
            or verified_amount != Decimal(expected_amount)
            or Decimal(str(event.get("amount", "0"))) != Decimal(expected_amount)
        ):
            logger.warning("WolvPay invoice verification mismatch for %s", invoice_id)
            return web.Response(status=400, text="Invoice verification mismatch.")
    except (aiohttp.ClientError, asyncio.TimeoutError, InvalidOperation, ValueError, TypeError):
        logger.exception("Error verifying WolvPay invoice %s", invoice_id)
        return web.Response(status=502, text="Invoice verification failed.")

    try:
        with sqlite3.connect(DATABASE_PATH) as db:
            table_name = {"dayler": "dayler_invoices", "pages": "pages_invoices", "icloud": "icloud_invoices", "demo": "demo_bot_invoices", "bill": "bill_invoices", "edit_upload": "edit_upload_invoices"}[invoice_type]
            db.execute(
                f"UPDATE {table_name} SET status = 'PAID' WHERE invoice_id = ? AND status = 'PENDING'",
                (invoice_id,),
            )
            confirmed = db.execute(
                f"SELECT status FROM {table_name} WHERE invoice_id = ?",
                (invoice_id,),
            ).fetchone()
            if not confirmed or confirmed[0] != "PAID":
                logger.error("Invoice %s could not be marked PAID after provider verification.", invoice_id)
                return web.Response(status=500, text="Could not persist payment status.")

            db.execute(
                """CREATE TABLE IF NOT EXISTS wolvpay_notifications (
                    invoice_id TEXT PRIMARY KEY,
                    customer_sent INTEGER NOT NULL DEFAULT 0,
                    admin_sent INTEGER NOT NULL DEFAULT 0
                )"""
            )
            db.execute(
                "INSERT OR IGNORE INTO wolvpay_notifications (invoice_id) VALUES (?)",
                (invoice_id,),
            )
            notification_state = db.execute(
                "SELECT customer_sent, admin_sent FROM wolvpay_notifications WHERE invoice_id = ?",
                (invoice_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("Could not persist WolvPay payment/notification state for %s.", invoice_id)
        return web.Response(status=500, text="Database error.")

    application = request.app["telegram_application"]
    try:
        customer_chat = await application.bot.get_chat(int(telegram_id))
        customer_username = "@" + customer_chat.username if customer_chat.username else "No tiene username público"
    except Exception:
        logger.exception("Could not retrieve Telegram username for customer %s.", telegram_id)
        customer_username = "No disponible"
    customer_text = (
        "✅ PAGO CONFIRMADO | UNARED\n\n"
        f"{customer_description}\n{order_detail}\n"
        f"Factura: {invoice_id}\n\n"
        "El equipo de UnaRed continuará con la preparación de tu servicio."
    )
    admin_text = (
        "💚 PAGO " + ({"dayler": "DAYLER", "pages": "PÁGINAS WEB", "icloud": "ICLOUD", "demo": "DEMO SANDBOX", "bill": "PAGO DE SERVICIOS", "edit_upload": "EDITAR Y SUBIR PAPEL"}[invoice_type]) + " CONFIRMADO | UNARED\n\n"
        f"Cliente: {customer_username}\n"
        f"Cliente Telegram ID: {telegram_id}\n{admin_detail}\n"
        f"Factura WolvPay: {invoice_id}\n"
        "Estado: PAGADO (verificado con WolvPay)."
    )

    try:
        if not notification_state[0]:
            await application.bot.send_message(chat_id=int(telegram_id), text=customer_text)
            with sqlite3.connect(DATABASE_PATH) as db:
                db.execute(
                    "UPDATE wolvpay_notifications SET customer_sent = 1 WHERE invoice_id = ?",
                    (invoice_id,),
                )

        if not notification_state[1]:
            await application.bot.send_message(chat_id=int(ADMIN_CHAT_ID), text=admin_text)
            with sqlite3.connect(DATABASE_PATH) as db:
                db.execute(
                    "UPDATE wolvpay_notifications SET admin_sent = 1 WHERE invoice_id = ?",
                    (invoice_id,),
                )
    except Exception:
        logger.exception("Payment confirmed; notification retry is pending for %s", invoice_id)
        return web.Response(status=500, text="Payment confirmed; notification retry required.")

    return web.Response(status=200, text="Webhook processed; notifications complete.")


async def start_webhook_server(application):
    if not WOLVPAY_API_KEY or not WOLVPAY_WEBHOOK_SECRET:
        logger.warning("WolvPay credentials missing; webhook server was not started.")
        return

    app = web.Application(client_max_size=1024 * 64)
    app["telegram_application"] = application
    app.router.add_post("/webhooks/wolvpay", wolvpay_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "8080")))
    await site.start()
    application.bot_data["wolvpay_webhook_runner"] = runner
    logger.info("WolvPay webhook listening on port %s", os.getenv("PORT", "8080"))


async def stop_webhook_server(application):
    runner = application.bot_data.get("wolvpay_webhook_runner")
    if runner:
        await runner.cleanup()


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
            filters.UpdateType.CHANNEL_POST & filters.AUDIO,
            channel_music_ingest,
        )
    )

    app.add_handler(
        MessageHandler(
            (filters.TEXT & ~filters.COMMAND) | filters.PHOTO | filters.AUDIO | filters.Document.ALL,
            receive_request,
        )
    )

    app.add_error_handler(error_handler)
    app.post_init = start_webhook_server
    app.post_shutdown = stop_webhook_server

    print("💚 UnaRed Bot está funcionando.")

    app.run_polling()


if __name__ == "__main__":
    main()
