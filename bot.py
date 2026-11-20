
import os
import logging
import asyncio
import hmac
import hashlib
import json
import sqlite3
from io import BytesIO
from decimal import Decimal, InvalidOperation
from datetime import datetime
from zoneinfo import ZoneInfo

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
    TypeHandler,
    ContextTypes,
    filters,
)

# =====================================
# CONFIGURACION
# =====================================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "5864523026")
BOT_OWNER_ID = "5864523026"
WOLVPAY_API_KEY = os.getenv("WOLVPAY_API_KEY")
WOLVPAY_WEBHOOK_SECRET = os.getenv("WOLVPAY_WEBHOOK_SECRET")
WOLVPAY_API_URL = "https://wolvpay.com/api/v1"
DATABASE_PATH = os.getenv("DATABASE_PATH", "unared_payments.sqlite3")

GROUP_LINK = "https://t.me/+slI1SJL6HIQ4Nzcx"

# =====================================
# UTILIDADES DE ADMINISTRACIÓN
# =====================================

def copy_id_keyboard(telegram_id):
    """Acciones administrativas permitidas para un cliente."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("👤 Ir al perfil", callback_data=f"view_customer:{int(telegram_id)}"),
        InlineKeyboardButton("🔔 Mandar alerta", callback_data=f"notify_customer:{int(telegram_id)}"),
    ]])


async def reply_with_copyable_id(query, telegram_id):
    """Compatibilidad con callbacks antiguos: no muestra ni copia IDs."""
    await query.answer("Usa los botones Ir al perfil y Mandar alerta.", show_alert=True)


async def notify_new_customer(application, user):
    """Notifica al propietario el registro inicial y ofrece perfil y alerta."""
    admin_bot = application.bot_data.get("admin_bot") or application.bot
    now = datetime.now(ZoneInfo("America/Santo_Domingo")).strftime("%d/%m/%Y %I:%M %p")
    caption = (
        "💚 UNARED | NUEVO CLIENTE\n\n"
        f"👤 Cliente: {user.full_name or 'Sin nombre'}\n"
        f"📛 Usuario: @{user.username if user.username else 'Sin nombre de usuario'}\n"
        f"🆔 ID Telegram: {user.id}\n"
        f"🕒 Registro: {now}"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("👤 Ir al perfil", callback_data=f"view_customer:{int(user.id)}"),
        InlineKeyboardButton("🔔 Mandar alerta", callback_data=f"notify_customer:{int(user.id)}"),
    ]])
    try:
        await admin_bot.send_message(
            chat_id=int(BOT_OWNER_ID),
            text=caption,
            reply_markup=keyboard,
        )
    except Exception:
        logger.exception("No se pudo notificar el registro del nuevo cliente %s.", user.id)

# =====================================
# METODO DE PAGO UNARED
# =====================================


async def notify_invoice_pending(
    application, telegram_id, invoice_id, amount, service, table_name,
    send_customer=True, send_admin=True, reminder_number=None
):
    """Send the pending-payment image to the customer and/or admin."""
    image_url = "https://i.ibb.co/99pb657f/6-D87-B76-C-02-AD-4-AEA-97-EB-DB3409-D6-F803.png"
    cancel_keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Cancelar pago", callback_data=f"cancel_invoice:{table_name}:{invoice_id}")
    ]])
    reminder_line = f"🔔 Recordatorio {reminder_number}/3\n\n" if reminder_number else ""
    customer_caption = (
        "⌛️ PAGO EN ESPERA | UNARED\n\n"
        f"{reminder_line}"
        f"🧾 Tu factura de {service} fue creada correctamente.\n"
        "⏳ Estado: Pendiente de pago\n"
        f"💵 Importe: USD {amount}\n"
        f"🔖 Factura: {invoice_id}\n\n"
        "🔐 Tu pago todavía no se ha confirmado.\n"
        "💳 Abre la factura para completar el pago.\n"
        "❌ Si no deseas continuar, puedes cancelar la factura."
    )
    admin_caption = (
        "💚 UNARED | NUEVA FACTURA PENDIENTE\n\n"
        f"👤 Cliente ID: {telegram_id}\n"
        f"🛠️ Servicio: {service}\n"
        f"💵 Importe: USD {amount}\n"
        f"🧾 Factura: {invoice_id}\n"
        "⌛️ Estado: PENDIENTE DE PAGO"
    )
    if send_customer:
        try:
            await application.bot.send_photo(
                chat_id=int(telegram_id), photo=image_url,
                caption=customer_caption, reply_markup=cancel_keyboard
            )
        except Exception:
            logger.exception("No se pudo enviar la imagen de pago pendiente al cliente %s.", telegram_id)
    if send_admin:
        try:
            admin_bot = application.bot_data.get("admin_bot")
            if not admin_bot:
                raise RuntimeError("El bot administrativo no está inicializado.")
            invoice_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔎 Verificar pago WolvPay", callback_data=f"av:{invoice_id}"),
                ],
                [
                    InlineKeyboardButton("✅ Pagado", callback_data=f"ap:{invoice_id}"),
                ],
                [
                    InlineKeyboardButton("👤 Ir al perfil", callback_data=f"view_customer:{int(telegram_id)}"),
                    InlineKeyboardButton("🔔 Mandar alerta", callback_data=f"notify_customer:{int(telegram_id)}"),
                ],
            ])
            await admin_bot.send_photo(
                chat_id=int(BOT_OWNER_ID), photo=image_url, caption=admin_caption,
                reply_markup=invoice_keyboard,
            )
        except Exception:
            logger.exception("No se pudo enviar la notificación de factura pendiente al administrador %s.", invoice_id)


async def schedule_payment_reminder(application, table_name, invoice_id, telegram_id, amount, service, invoice_url=None):
    """Send up to three reminders every three minutes while the invoice remains pending."""
    allowed_tables = {"dayler_invoices", "pyp_invoices", "demo_bot_invoices", "pages_invoices", "icloud_invoices", "bill_invoices", "edit_upload_invoices", "ssn_assistance_invoices"}
    if table_name not in allowed_tables:
        return
    for attempt in range(1, 4):
        await asyncio.sleep(180)
        try:
            with sqlite3.connect(DATABASE_PATH) as db:
                row = db.execute(
                    f"SELECT status FROM {table_name} WHERE invoice_id = ?",
                    (invoice_id,),
                ).fetchone()
            if not row or str(row[0]).upper() != "PENDING":
                return
            await notify_invoice_pending(
                application, telegram_id, invoice_id, amount, service, table_name,
                send_customer=True, send_admin=False, reminder_number=attempt
            )
        except Exception:
            logger.exception("No se pudo enviar el recordatorio %s para %s.", attempt, invoice_id)



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

def main_menu(user=None):
    keyboard = [
        [
            InlineKeyboardButton(
                "🏦 Bancos",
                callback_data="menu_banks",
            ),
        ],
        [
            InlineKeyboardButton(
                "💸 Remesas",
                callback_data="remesas",
            ),
            InlineKeyboardButton(
                "💡 Pago Bill",
                callback_data="pagos",
            ),
        ],
        [
            InlineKeyboardButton(
                "🛒 Amazon",
                callback_data="amazon",
            ),
            InlineKeyboardButton(
                "🍎 Apple",
                callback_data="apple",
            ),
        ],
        [
            InlineKeyboardButton(
                "✈️ Vuelos",
                callback_data="vuelos",
            ),
            InlineKeyboardButton(
                "📟 Modo Digital",
                callback_data="digital",
            ),
        ],
        [
            InlineKeyboardButton(
                "🧰 Herramientas",
                callback_data="menu_tools",
            ),
        ],
        [
            InlineKeyboardButton(
                "💚 Ser Parte de UnaRed",
                url=GROUP_LINK,
            )
        ],
    ]

    # El acceso al panel solo aparece para las cuentas autorizadas.
    if is_admin(user):
        keyboard.append([
            InlineKeyboardButton(
                "⚙️ Panel de administración",
                url="https://t.me/Unaredadminbot?start=admin_panel",
            )
        ])

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


def pyp_coin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("₿ Bitcoin (BTC)", callback_data="pyp_coin_btc")],
        [InlineKeyboardButton("₮ USDT (TRC20)", callback_data="pyp_coin_trc20_usdt")],
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
        [InlineKeyboardButton("🤖 BOT OTP", callback_data="botproduct_otp")],
        [InlineKeyboardButton("🤖 BOT SSN", callback_data="botproduct_ssn")],
        [InlineKeyboardButton("🤖 BOT CHECK", callback_data="botproduct_check")],
        [InlineKeyboardButton("🤖 LICENCIA", callback_data="botproduct_template")],
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
        # Cuatro servicios principales en filas completas.
        [InlineKeyboardButton("📞 Alquilar Línea Dialer", callback_data="tool_dayler")],
        [InlineKeyboardButton("🗂️ Páginas Buy CC", callback_data="tool_pages")],

        # Servicios secundarios organizados en dos columnas.
        [
            InlineKeyboardButton("🤖 Comprar Bot", callback_data="tool_bots"),
            InlineKeyboardButton("🪪 SSN", callback_data="tool_ssn_info"),
        ],
        [
            InlineKeyboardButton("👤 Perfiles", callback_data="tool_profiles"),
            InlineKeyboardButton("📄 Papeles", callback_data="edit_buy_paper"),
        ],

        [InlineKeyboardButton("💵 Método PyP", callback_data="tool_pyp")],
        [InlineKeyboardButton("📝 Editar y subir papel", callback_data="tool_edit_upload")],
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
# PANEL PRIVADO UNARED
# =====================================
INVOICE_TABLES = ("bill_invoices", "dayler_invoices", "pyp_invoices", "demo_bot_invoices", "pages_invoices", "icloud_invoices", "edit_upload_invoices", "ssn_assistance_invoices")

def save_customer(user):
    """Guarda/actualiza al cliente y devuelve True únicamente en su primer registro."""
    if not user or is_admin(user):
        return False
    with sqlite3.connect(DATABASE_PATH) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS unared_customers (
            telegram_id INTEGER PRIMARY KEY, username TEXT NOT NULL DEFAULT '',
            full_name TEXT NOT NULL DEFAULT '', first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        cursor = db.execute(
            """INSERT OR IGNORE INTO unared_customers (telegram_id, username, full_name)
               VALUES (?, ?, ?)""",
            (user.id, user.username or "", user.full_name or ""),
        )
        is_new = cursor.rowcount == 1
        if not is_new:
            db.execute(
                """UPDATE unared_customers SET username=?, full_name=?,
                   last_seen=CURRENT_TIMESTAMP WHERE telegram_id=?""",
                (user.username or "", user.full_name or "", user.id),
            )
    return is_new

def log_customer_interaction(user, button_key):
    """Guarda qué botón pulsó cada cliente, sin almacenar el contenido de sus mensajes."""
    if not user or not button_key or is_admin(user):
        return
    labels = {
        "menu_banks": "🏦 Bancos",
        "remesas": "💸 Envíos y remesas",        "pagos": "🧾 Pago de servicios",
        "amazon": "🛒 Amazon",
        "apple": "🍎 Apple",        "vuelos": "✈️ Vuelos",        "menu_tools": "🧰 Herramientas",
        "digital": "📟 Modo Digital",
        "menu_home": "🏠 Menú principal",
        "bill_pay": "💡 Pago de bill",
        "dayler_pay": "💳 Servicio Dayler",
        "music_catalog": "🎵 Catálogo de música",
        "music_submit": "🎧 Enviar música",
        "tool_edit_upload": "🛠️ Editar y subir",
    }
    label = labels.get(button_key, "🔘 " + button_key.replace("_", " ").strip().capitalize())
    with sqlite3.connect(DATABASE_PATH) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS unared_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            username TEXT NOT NULL DEFAULT '',
            full_name TEXT NOT NULL DEFAULT '',
            button_key TEXT NOT NULL,
            button_label TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute(
            """INSERT INTO unared_interactions
               (telegram_id, username, full_name, button_key, button_label)
               VALUES (?, ?, ?, ?, ?)""",
            (user.id, user.username or "", user.full_name or "", str(button_key), label),
        )


def is_admin(user):
    # Únicamente la cuenta propietaria puede ver y usar el panel.
    return bool(user and str(user.id) == BOT_OWNER_ID)

def admin_dashboard_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Estadísticas", callback_data="admin_stats"),
            InlineKeyboardButton("👥 Clientes", callback_data="admin_customers"),
        ],
        [
            InlineKeyboardButton("💳 Facturación", callback_data="admin_billing"),
            InlineKeyboardButton("🕘 Actividad", callback_data="admin_activity"),
        ],
        [InlineKeyboardButton("🔎 Buscar cliente", callback_data="admin_search_help")],
    ])


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.effective_message.reply_text("⛔ Panel privado.")
        return
    banner_url = "https://i.ibb.co/PvB4jdJT/E1-ED4248-C0-F3-45-C2-A875-5165-EF2-D4504.png"
    await update.effective_message.reply_photo(
        photo=banner_url,
        caption=(
            "💚 UNARED | ADMIN\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "CENTRO DE CONTROL PRIVADO\n\n"
            "Administra clientes, revisa la actividad y consulta la facturación "
            "desde un solo lugar."
        ),
        reply_markup=admin_dashboard_keyboard(),
    )


async def admin_customers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not is_admin(update.effective_user):
        if update.callback_query:
            await update.callback_query.answer("⛔ Acceso denegado.", show_alert=True)
        return

    try:
        customers = {}
        with sqlite3.connect(DATABASE_PATH, timeout=15) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS unared_customers (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL DEFAULT '',
                full_name TEXT NOT NULL DEFAULT '',
                first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            columns = {column[1] for column in db.execute("PRAGMA table_info(unared_customers)")}
            for column, definition in (
                ("username", "TEXT NOT NULL DEFAULT ''"),
                ("full_name", "TEXT NOT NULL DEFAULT ''"),
                ("first_seen", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
                ("last_seen", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
            ):
                if column not in columns:
                    db.execute(f"ALTER TABLE unared_customers ADD COLUMN {column} {definition}")

            for tid, username, name, last_seen in db.execute(
                "SELECT telegram_id, username, full_name, last_seen FROM unared_customers"
            ).fetchall():
                customers[int(tid)] = {
                    "username": username or "", "name": name or "",
                    "last_seen": last_seen or ""
                }

            interactions_exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='unared_interactions'"
            ).fetchone()
            if interactions_exists:
                interaction_rows = db.execute(
                    """SELECT telegram_id, username, full_name, MAX(created_at)
                       FROM unared_interactions
                       WHERE telegram_id != ?
                       GROUP BY telegram_id""",
                    (int(BOT_OWNER_ID),),
                ).fetchall()
                for tid, username, name, last_seen in interaction_rows:
                    tid = int(tid)
                    current = customers.get(tid, {})
                    customers[tid] = {
                        "username": username or current.get("username", ""),
                        "name": name or current.get("name", ""),
                        "last_seen": max(str(last_seen or ""), str(current.get("last_seen", ""))),
                    }

        ordered = sorted(
            customers.items(),
            key=lambda item: item[1].get("last_seen", ""),
            reverse=True,
        )[:12]
        total = len(customers)
        lines = [
            f"• {data['name'] or 'Cliente'} | @{data['username'] or 'sin_usuario'}"
            for tid, data in ordered
        ]
        buttons = []
        for tid, data in ordered:
            buttons.append([
                InlineKeyboardButton(
                    f"👤 Ir al perfil: {(data['name'] or data['username'] or str(tid))[:20]}",
                    callback_data=f"view_customer:{int(tid)}",
                ),
                InlineKeyboardButton(
                    "🔔 Mandar alerta",
                    callback_data=f"notify_customer:{tid}",
                ),
            ])
        buttons.append([InlineKeyboardButton("⬅️ Volver al panel", callback_data="admin_home")])

        await message.reply_text(
            "👥 UNARED | CLIENTES\n━━━━━━━━━━━━━━━━━━\n\n"
            f"Total de clientes únicos: {total}\nÚltimos 12 clientes:\n"
            + ("\n".join(lines) if lines else "Todavía no hay clientes registrados."),
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    except Exception:
        logger.exception("Error mostrando la lista de clientes en el panel administrativo.")
        if update.callback_query:
            await update.callback_query.answer("No se pudo cargar la lista de clientes.", show_alert=True)
        elif message:
            await message.reply_text("⚠️ No se pudo cargar la lista de clientes. Revisa los registros de Railway.")


async def refresh_wolvpay_statuses():
    """Sincroniza los estados de las facturas locales con el endpoint de WolvPay ya utilizado."""
    if not WOLVPAY_API_KEY:
        return
    invoice_rows = []
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=20) as db:
            for table in INVOICE_TABLES:
                exists = db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                if not exists:
                    continue
                cols = {row[1] for row in db.execute("PRAGMA table_info(" + table + ")")}
                if "invoice_id" in cols and "status" in cols:
                    invoice_rows.extend((table, row[0]) for row in db.execute(
                        "SELECT invoice_id FROM " + table + " WHERE invoice_id IS NOT NULL"
                    ).fetchall())
    except sqlite3.Error:
        logger.exception("No se pudieron preparar las facturas para sincronizar con WolvPay.")
        return

    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        semaphore = asyncio.Semaphore(8)

        async def fetch_status(table, invoice_id):
            async with semaphore:
                try:
                    async with session.get(
                        f"{WOLVPAY_API_URL}/invoices/{invoice_id}",
                        headers={"Authorization": f"Bearer {WOLVPAY_API_KEY}"},
                    ) as response:
                        if response.status != 200:
                            return None
                        payload = await response.json(content_type=None)
                    invoice = payload.get("data") or payload
                    status = str(invoice.get("status") or "").strip().upper()
                    if invoice.get("invoice_id") and str(invoice["invoice_id"]) != str(invoice_id):
                        return None
                    return (table, invoice_id, status) if status else None
                except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError):
                    logger.warning("No se pudo actualizar el estado WolvPay de %s.", invoice_id)
                    return None

        results = await asyncio.gather(
            *(fetch_status(table, invoice_id) for table, invoice_id in invoice_rows)
        )
    updates = [item for item in results if item]
    if updates:
        try:
            with sqlite3.connect(DATABASE_PATH, timeout=20) as db:
                for table, invoice_id, status in updates:
                    db.execute(
                        "UPDATE " + table + " SET status=? WHERE invoice_id=?",
                        (status, invoice_id),
                    )
        except sqlite3.Error:
            logger.exception("No se pudieron guardar los estados sincronizados de WolvPay.")


async def admin_billing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        return

    # Cada vez que se abre Facturación, consulta WolvPay y actualiza los estados locales.
    await refresh_wolvpay_statuses()

    status_counts = {}
    total_invoiced = Decimal("0")
    confirmed_income = Decimal("0")
    invoices = 0
    invalid_amounts = 0

    with sqlite3.connect(DATABASE_PATH, timeout=20) as db:
        for table in INVOICE_TABLES:
            if not db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone():
                continue
            cols = {row[1] for row in db.execute("PRAGMA table_info(" + table + ")")}
            if not {"amount", "status"}.issubset(cols):
                continue

            for amount, status in db.execute(
                "SELECT amount, status FROM " + table
            ).fetchall():
                invoices += 1
                state = str(status or "UNKNOWN").strip().upper()
                # Unifica variantes habituales que puede devolver el proveedor.
                if state in {"CANCELED", "CANCEL", "VOID", "VOIDED"}:
                    state = "CANCELLED"
                elif state in {"UNPAID", "PROCESSING", "AWAITING_SELECTION", "CREATED", "NEW"}:
                    state = "PENDING"

                status_counts[state] = status_counts.get(state, 0) + 1
                try:
                    value = Decimal(str(amount or "0"))
                    if value.is_finite() and value >= 0:
                        total_invoiced += value
                        if state == "PAID":
                            confirmed_income += value
                    else:
                        invalid_amounts += 1
                except (InvalidOperation, ValueError, TypeError):
                    invalid_amounts += 1

    pending = status_counts.get("PENDING", 0)
    paid = status_counts.get("PAID", 0)
    cancelled = status_counts.get("CANCELLED", 0)
    other_states = {
        state: count for state, count in status_counts.items()
        if state not in {"PAID", "PENDING", "CANCELLED"}
    }
    status_detail = "\\n".join(
        f"• {state}: {count}" for state, count in sorted(other_states.items())
    ) or "• Ninguno"

    report = (
        "💳 UNARED | FACTURACIÓN WOLVPAY\\n"
        "━━━━━━━━━━━━━━━━━━\\n\\n"
        f"🧾 Facturas creadas: {invoices}\\n"
        f"⌛ Pendientes: {pending}\\n"
        f"✅ Pagadas: {paid}\\n"
        f"❌ Canceladas: {cancelled}\\n\\n"
        f"💰 Total facturado: USD {total_invoiced:,.2f}\\n"
        f"💵 Ingresos confirmados: USD {confirmed_income:,.2f}\\n\\n"
        f"📌 Otros estados:\\n{status_detail}"
    )
    if invalid_amounts:
        report += f"\\n⚠️ Facturas con importe no válido: {invalid_amounts}"

    await update.effective_message.reply_text(
        report,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Actualizar estadísticas", callback_data="admin_billing"),
            InlineKeyboardButton("⬅️ Volver al panel", callback_data="admin_home")
        ]]),
    )


async def admin_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        return
    with sqlite3.connect(DATABASE_PATH) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS unared_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL,
            username TEXT NOT NULL DEFAULT '', full_name TEXT NOT NULL DEFAULT '',
            button_key TEXT NOT NULL, button_label TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        rows = db.execute(
            """SELECT i.full_name, i.username, i.telegram_id, i.button_label, i.created_at
               FROM unared_interactions AS i
               INNER JOIN (
                   SELECT telegram_id, MAX(id) AS latest_id
                   FROM unared_interactions
                   WHERE telegram_id != ?
                   GROUP BY telegram_id
               ) AS latest ON latest.latest_id = i.id
               ORDER BY i.id DESC LIMIT 15""",
            (int(BOT_OWNER_ID),),
        ).fetchall()
    lines = [
        f"• {name or 'Cliente'} (@{username or 'sin_usuario'})\n  Última acción: {label} | {when}"
        for name, username, tid, label, when in rows
    ]
    buttons = []
    for name, username, tid, label, when in rows:
        buttons.append([
            InlineKeyboardButton("👤 Ir al perfil", callback_data=f"view_customer:{int(tid)}"),
            InlineKeyboardButton("🔔 Mandar alerta", callback_data=f"notify_customer:{int(tid)}"),
        ])
    buttons.append([InlineKeyboardButton("⬅️ Volver al panel", callback_data="admin_home")])
    await update.effective_message.reply_text(
        "🕘 UNARED | ACTIVIDAD RECIENTE\n━━━━━━━━━━━━━━━━━━\n\n"
        + ("\n".join(lines) if lines else "Todavía no hay actividad registrada."),
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def admin_bot_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.effective_message.reply_text("⛔ Acceso denegado. Este bot es privado.")
        return
    await admin_panel(update, context)


async def admin_bot_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user):
        await query.answer("⛔ Acceso denegado.", show_alert=True)
        return
    await query.answer()
    if query.data.startswith("ssn_process:") or query.data.startswith("ssn_complete:"):
        action, invoice_id = query.data.split(":", 1)
        with sqlite3.connect(DATABASE_PATH, timeout=20) as db:
            row = db.execute(
                "SELECT telegram_id, status, request_status FROM ssn_assistance_invoices WHERE invoice_id=?",
                (invoice_id,),
            ).fetchone()
            if not row or str(row[1]).upper() != "PAID":
                await query.message.reply_text("⚠️ La solicitud no existe o WolvPay aún no confirma el pago.")
                return
            telegram_id, _, current_request_status = row
            if action == "ssn_process":
                db.execute(
                    "UPDATE ssn_assistance_invoices SET request_status='PROCESSING' WHERE invoice_id=? AND request_status IN ('PAID','PROCESSING')",
                    (invoice_id,),
                )
                customer_text = (
                    "⌛️ UNARED | SOLICITUD EN PROCESO\n\n"
                    "Tu pago fue confirmado. Estamos preparando la orientación para que recuperes tu propio SSN mediante la SSA. "
                    "No envíes números ni documentos sensibles por Telegram."
                )
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ Marcar como completada", callback_data=f"ssn_complete:{invoice_id}")
                ]])
            else:
                db.execute(
                    "UPDATE ssn_assistance_invoices SET request_status='COMPLETED' WHERE invoice_id=? AND request_status IN ('PAID','PROCESSING')",
                    (invoice_id,),
                )
                customer_text = (
                    "✅ UNARED | SOLICITUD COMPLETADA\n\n"
                    "Tu solicitud de orientación fue completada. Para recuperar tu SSN, utiliza los canales oficiales de la SSA: "
                    "https://www.ssa.gov/number-card/\n\n"
                    "Nunca compartas tu SSN completo ni documentos sensibles por Telegram."
                )
                keyboard = None
        try:
            main_bot = context.application.bot_data.get("main_bot") or context.application.bot
            await main_bot.send_message(chat_id=int(telegram_id), text=customer_text, disable_web_page_preview=True)
            await query.message.reply_text(
                "✅ Estado actualizado: " + ("EN PROCESO" if action == "ssn_process" else "COMPLETADA") + f"\nFactura: {invoice_id}"
            )
            await query.message.edit_reply_markup(reply_markup=keyboard)
        except Exception:
            logger.exception("No se pudo notificar el cambio de estado SSN %s.", invoice_id)
            await query.message.reply_text("⚠️ El estado se guardó, pero no se pudo notificar al cliente.")
        return

    if query.data.startswith("av:") or query.data.startswith("ap:"):
        action, invoice_id = query.data.split(":", 1)
        try:
            table_name = None
            row = None
            with sqlite3.connect(DATABASE_PATH, timeout=20) as db:
                for candidate in INVOICE_TABLES:
                    exists = db.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (candidate,)
                    ).fetchone()
                    if not exists:
                        continue
                    found = db.execute(
                        "SELECT telegram_id, amount, status FROM " + candidate + " WHERE invoice_id=?",
                        (invoice_id,),
                    ).fetchone()
                    if found:
                        table_name, row = candidate, found
                        break
            if not row:
                await query.message.reply_text("⚠️ No encontramos esa factura en el registro de UnaRed.")
                return
            telegram_id, expected_amount, current_status = row
            if str(current_status).upper() in ("CANCELLED", "CANCELED", "REJECTED"):
                await query.message.reply_text("⛔ Esta factura está cancelada o rechazada; no se puede confirmar.")
                return

            verified_by_wolvpay = action == "av"
            if verified_by_wolvpay:
                if not WOLVPAY_API_KEY:
                    await query.message.reply_text("⚠️ La conexión con WolvPay no está configurada.")
                    return
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"{WOLVPAY_API_URL}/invoices/{invoice_id}",
                            headers={"Authorization": f"Bearer {WOLVPAY_API_KEY}"},
                            timeout=aiohttp.ClientTimeout(total=20),
                        ) as response:
                            payload = await response.json(content_type=None)
                            if response.status != 200:
                                logger.error("WolvPay admin verification HTTP %s: %s", response.status, payload)
                                await query.message.reply_text("⚠️ WolvPay no pudo consultar la factura. Sigue pendiente; inténtalo más tarde.")
                                return
                    invoice = payload.get("data") or payload
                    provider_amount = Decimal(str(invoice.get("amount", "0")))
                    expected_decimal = Decimal(str(expected_amount))
                    provider_currency = str(invoice.get("currency") or "USD").upper()
                    if str(invoice.get("invoice_id", invoice_id)) != str(invoice_id):
                        await query.message.reply_text("⚠️ WolvPay devolvió un ID de factura diferente. No se modificó el pago.")
                        return
                    if str(invoice.get("status", "")).upper() != "PAID":
                        await query.message.reply_text("⌛ WolvPay todavía muestra esta factura como no pagada. Sigue pendiente.")
                        return
                    if provider_amount != expected_decimal or provider_currency != "USD":
                        logger.warning("WolvPay amount/currency mismatch for invoice %s", invoice_id)
                        await query.message.reply_text("⛔ El importe o la moneda de WolvPay no coincide con el registro (USD). No se confirmó el pago.")
                        return
                except (aiohttp.ClientError, asyncio.TimeoutError, InvalidOperation, ValueError, TypeError):
                    logger.exception("No se pudo verificar la factura %s con WolvPay.", invoice_id)
                    await query.message.reply_text("⚠️ Error consultando WolvPay. La factura permanece sin cambios.")
                    return

            admin_user = update.effective_user
            admin_label = (admin_user.username and "@" + admin_user.username) or str(admin_user.id)
            confirmed_at = datetime.now(ZoneInfo("America/Santo_Domingo")).isoformat(timespec="seconds")
            with sqlite3.connect(DATABASE_PATH, timeout=20) as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("""CREATE TABLE IF NOT EXISTS wolvpay_notifications (
                    invoice_id TEXT PRIMARY KEY,
                    customer_sent INTEGER NOT NULL DEFAULT 0,
                    admin_sent INTEGER NOT NULL DEFAULT 0,
                    approval_status TEXT NOT NULL DEFAULT 'PENDING',
                    image_status TEXT NOT NULL DEFAULT 'PENDING'
                )""")
                cols = {item[1] for item in db.execute("PRAGMA table_info(wolvpay_notifications)")}
                for col, definition in (
                    ("admin_id", "INTEGER"),
                    ("admin_username", "TEXT"),
                    ("confirmed_at", "TEXT"),
                    ("confirmation_method", "TEXT"),
                ):
                    if col not in cols:
                        db.execute("ALTER TABLE wolvpay_notifications ADD COLUMN " + col + " " + definition)
                db.execute("INSERT OR IGNORE INTO wolvpay_notifications (invoice_id) VALUES (?)", (invoice_id,))
                state = db.execute(
                    "SELECT image_status FROM wolvpay_notifications WHERE invoice_id=?",
                    (invoice_id,),
                ).fetchone()
                if state and str(state[0]).upper() in ("SENT", "SENDING", "FAILED"):
                    db.rollback()
                    message = (
                        "ℹ️ Esta factura ya fue confirmada y la imagen fue enviada."
                        if str(state[0]).upper() == "SENT"
                        else "⚠️ Esta factura ya tiene un envío en curso o un intento fallido. No la reenvío para evitar duplicados."
                    )
                    await query.message.reply_text(message)
                    return
                if verified_by_wolvpay:
                    db.execute(
                        "UPDATE " + table_name + " SET status='PAID' WHERE invoice_id=? AND status IN ('PENDING','PAID')",
                        (invoice_id,),
                    )
                else:
                    db.execute(
                        "UPDATE " + table_name + " SET status='PAID' WHERE invoice_id=? AND status IN ('PENDING','PAID')",
                        (invoice_id,),
                    )
                saved = db.execute(
                    "SELECT status FROM " + table_name + " WHERE invoice_id=?",
                    (invoice_id,),
                ).fetchone()
                if not saved or str(saved[0]).upper() != "PAID":
                    db.rollback()
                    await query.message.reply_text("⛔ La factura no está en un estado que permita confirmarla.")
                    return
                claimed = db.execute(
                    """UPDATE wolvpay_notifications
                       SET approval_status='APPROVED', image_status='SENDING',
                           admin_id=?, admin_username=?, confirmed_at=?, confirmation_method=?
                       WHERE invoice_id=? AND image_status='PENDING'""",
                    (
                        int(admin_user.id), admin_label, confirmed_at,
                        "WOLVPAY_VERIFIED" if verified_by_wolvpay else "MANUAL_ADMIN",
                        invoice_id,
                    ),
                )
                if claimed.rowcount != 1:
                    db.rollback()
                    await query.message.reply_text("ℹ️ Otro proceso ya está confirmando esta factura. No se enviará otra imagen.")
                    return
                db.commit()

            main_bot = context.application.bot_data.get("main_bot")
            if not main_bot:
                raise RuntimeError("No está disponible el bot principal para enviar la confirmación.")
            confirmation_image = "https://i.ibb.co/ccmC4XsG/86-DE6634-72-C2-4544-9-DB5-351541-A91286.png"
            await main_bot.send_photo(
                chat_id=int(telegram_id),
                photo=confirmation_image,
                caption=(
                    "✅ PAGO CONFIRMADO | UNARED\n\n"
                    + ("WolvPay confirmó automáticamente el pago." if verified_by_wolvpay else "El administrador confirmó manualmente tu pago.")
                    + f"\nFactura: {invoice_id}\nImporte: USD {expected_amount}"
                ),
            )
            with sqlite3.connect(DATABASE_PATH, timeout=20) as db:
                db.execute(
                    "UPDATE wolvpay_notifications SET image_status='SENT' WHERE invoice_id=? AND image_status='SENDING'",
                    (invoice_id,),
                )
            await query.message.reply_text(
                f"✅ Factura {invoice_id} confirmada "
                + ("por WolvPay" if verified_by_wolvpay else "manualmente")
                + ". La imagen se envió al cliente."
            )
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        except Exception:
            logger.exception("Error procesando la acción administrativa de la factura %s.", invoice_id)
            try:
                with sqlite3.connect(DATABASE_PATH, timeout=20) as db:
                    db.execute(
                        "UPDATE wolvpay_notifications SET image_status='FAILED' WHERE invoice_id=? AND image_status='SENDING'",
                        (invoice_id,),
                    )
            except sqlite3.Error:
                logger.exception("No se pudo registrar el fallo del envío.")
            await query.message.reply_text(
                f"⚠️ No se pudo completar la confirmación de {invoice_id}. Se bloqueó el reenvío automático para evitar duplicados."
            )
        return
    if query.data.startswith("admin_wolvpay_accept:") or query.data.startswith("admin_wolvpay_reject:"):
        action, invoice_id = query.data.split(":", 1)
        table_name = None
        telegram_id = None
        invoice_status = None
        try:
            with sqlite3.connect(DATABASE_PATH, timeout=20) as db:
                for candidate in INVOICE_TABLES:
                    exists = db.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (candidate,)
                    ).fetchone()
                    if not exists:
                        continue
                    found = db.execute(
                        "SELECT telegram_id, status FROM " + candidate + " WHERE invoice_id=?",
                        (invoice_id,),
                    ).fetchone()
                    if found:
                        table_name = candidate
                        telegram_id, invoice_status = found
                        break
                if not table_name or str(invoice_status).upper() != "PAID":
                    await query.message.reply_text("⚠️ No se encontró una factura pagada válida para aprobar.")
                    return
                db.execute("""CREATE TABLE IF NOT EXISTS wolvpay_notifications (
                    invoice_id TEXT PRIMARY KEY,
                    customer_sent INTEGER NOT NULL DEFAULT 0,
                    admin_sent INTEGER NOT NULL DEFAULT 0,
                    approval_status TEXT NOT NULL DEFAULT 'PENDING',
                    image_status TEXT NOT NULL DEFAULT 'PENDING'
                )""")
                cols = {row[1] for row in db.execute("PRAGMA table_info(wolvpay_notifications)")}
                if "approval_status" not in cols:
                    db.execute("ALTER TABLE wolvpay_notifications ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'PENDING'")
                if "image_status" not in cols:
                    db.execute("ALTER TABLE wolvpay_notifications ADD COLUMN image_status TEXT NOT NULL DEFAULT 'PENDING'")
                if action == "admin_wolvpay_reject":
                    cursor = db.execute(
                        """UPDATE wolvpay_notifications
                           SET approval_status='REJECTED'
                           WHERE invoice_id=? AND approval_status='PENDING' AND image_status='PENDING'""",
                        (invoice_id,),
                    )
                    if cursor.rowcount != 1:
                        current = db.execute(
                            "SELECT approval_status, image_status FROM wolvpay_notifications WHERE invoice_id=?",
                            (invoice_id,),
                        ).fetchone()
                        await query.message.reply_text(
                            "ℹ️ Esta factura ya fue procesada: " + str(current or "sin estado")
                        )
                        return
                else:
                    cursor = db.execute(
                        """UPDATE wolvpay_notifications
                           SET approval_status='APPROVED', image_status='SENDING'
                           WHERE invoice_id=? AND approval_status='PENDING' AND image_status='PENDING'""",
                        (invoice_id,),
                    )
                    if cursor.rowcount != 1:
                        current = db.execute(
                            "SELECT approval_status, image_status FROM wolvpay_notifications WHERE invoice_id=?",
                            (invoice_id,),
                        ).fetchone()
                        await query.message.reply_text(
                            "ℹ️ Esta factura ya fue procesada: " + str(current or "sin estado")
                        )
                        return
            if action == "admin_wolvpay_reject":
                await query.message.reply_text(f"❌ Factura {invoice_id}: imagen rechazada. No se enviará al cliente.")
                try:
                    await query.message.edit_reply_markup(reply_markup=None)
                except Exception:
                    pass
                return
            main_bot = context.application.bot_data.get("main_bot")
            if not main_bot:
                raise RuntimeError("No está disponible el bot principal para enviar la imagen.")
            image_url = "https://i.ibb.co/ccmC4XsG/86-DE6634-72-C2-4544-9-DB5-351541-A91286.png"
            await main_bot.send_photo(
                chat_id=int(telegram_id),
                photo=image_url,
                caption="✅ PAGO CONFIRMADO | UNARED\n\nTu comprobante de pago ha sido aprobado por nuestro equipo.",
            )
            with sqlite3.connect(DATABASE_PATH, timeout=20) as db:
                db.execute(
                    "UPDATE wolvpay_notifications SET image_status='SENT' WHERE invoice_id=? AND image_status='SENDING'",
                    (invoice_id,),
                )
            await query.message.reply_text(f"✅ Imagen de pago enviada al cliente. Factura: {invoice_id}")
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        except Exception:
            logger.exception("Error procesando la aprobación administrativa de la factura %s.", invoice_id)
            try:
                with sqlite3.connect(DATABASE_PATH, timeout=20) as db:
                    db.execute(
                        "UPDATE wolvpay_notifications SET image_status='FAILED' WHERE invoice_id=? AND image_status='SENDING'",
                        (invoice_id,),
                    )
            except sqlite3.Error:
                logger.exception("No se pudo guardar el fallo de envío de imagen.")
            await query.message.reply_text(
                f"⚠️ No se pudo enviar la imagen de la factura {invoice_id}. El sistema la marcó como FALLIDA para evitar duplicados."
            )
        return
    if query.data.startswith("view_customer:"):
        try:
            telegram_id = int(query.data.split(":", 1)[1])
            customer_name = "este cliente"
            username = ""
            with sqlite3.connect(DATABASE_PATH, timeout=15) as db:
                exists = db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='unared_customers'"
                ).fetchone()
                if exists:
                    cols = {c[1] for c in db.execute("PRAGMA table_info(unared_customers)")}
                    if {"telegram_id", "full_name", "username"}.issubset(cols):
                        row = db.execute(
                            "SELECT full_name, username FROM unared_customers WHERE telegram_id=?",
                            (telegram_id,),
                        ).fetchone()
                        if row:
                            customer_name, username = row[0] or customer_name, row[1] or ""
            profile_link = f'<a href="tg://user?id={telegram_id}">Abrir perfil de {customer_name}</a>'
            if username:
                profile_link = f'<a href="https://t.me/{username.lstrip("@")}">Abrir perfil de {customer_name}</a>'
            await query.message.reply_text(profile_link, parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            logger.exception("No se pudo abrir el perfil del cliente.")
            await query.message.reply_text("No se pudo abrir el perfil de ese cliente.")
        return
    if query.data == "contact_admin":
        await query.message.reply_text(
            f'<a href="tg://user?id={int(BOT_OWNER_ID)}">Contactar con el administrador</a>',
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return
    if query.data.startswith("notify_customer:"):
        try:
            telegram_id = int(query.data.split(":", 1)[1])
            main_bot = context.application.bot_data.get("main_bot")
            if not main_bot:
                await query.message.reply_text("⚠️ No está disponible la conexión con el bot principal.")
                return
            customer_keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("📩 Contactar a Flow Montana", url="https://t.me/flowmontana777")
            ]])
            await main_bot.send_photo(
                chat_id=telegram_id,
                photo="https://i.ibb.co/sJqnfCPG/50-FDEC59-BC9-A-40-EC-9-AF8-E19-B16-C4931-C.png",
                caption=("💚 UNARED | NOTIFICACIÓN\n\n"
                         "Tenemos una notificación importante para ti. "
                         "Pulsa el botón de abajo para contactar con nuestro administrador."),
                reply_markup=customer_keyboard,
            )
            await query.message.reply_text(f"✅ Notificación enviada al cliente {telegram_id}.")
        except (ValueError, IndexError):
            await query.message.reply_text("⚠️ ID de cliente no válido.")
        except Exception:
            logger.exception("No se pudo enviar la notificación desde el panel.")
            await query.message.reply_text("⚠️ No se pudo enviar la notificación. Es posible que el cliente no haya iniciado el bot.")
        return
    if query.data.startswith("copy_id:"):
        try:
            telegram_id = int(query.data.split(":", 1)[1])
            await reply_with_copyable_id(query, telegram_id)
        except (ValueError, IndexError):
            await query.message.reply_text("ID no válido.")
        return
    if query.data == "admin_home":
        await admin_panel(update, context)
    elif query.data == "admin_stats":
        await admin_stats(update, context)
    elif query.data == "admin_stats_more":
        await admin_stats_more(update, context)
    elif query.data == "admin_customers":
        await admin_customers(update, context)
    elif query.data == "admin_billing":
        await admin_billing(update, context)
    elif query.data == "admin_activity":
        await admin_activity(update, context)
    elif query.data == "admin_search_help":
        await query.message.reply_text(
            "🔎 UNARED | BUSCAR CLIENTE\n\n"
            "Usa el comando:\n/buscarcliente TELEGRAM_ID\n\n"
            "Ejemplo: /buscarcliente 123456789\n"
            "El cliente debe haber iniciado o interactuado con UnaRed para aparecer en el registro.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Volver al panel", callback_data="admin_home")
            ]]),
        )



def build_admin_application():
    admin_app = Application.builder().token(ADMIN_BOT_TOKEN).build()
    admin_app.add_handler(CommandHandler("start", admin_bot_start))
    admin_app.add_handler(CommandHandler("panel", admin_panel))
    admin_app.add_handler(CommandHandler("stats", admin_stats))
    # Los callbacks del panel se procesan aquí; los callbacks de otros flujos no se interceptan.
    admin_app.add_handler(CommandHandler("buscarcliente", find_customer))
    admin_app.add_handler(CallbackQueryHandler(
        admin_bot_callbacks,
        pattern=r"^(admin_|av:|ap:|ssn_process:|ssn_complete:|copy_id:|notify_customer:|view_customer:|contact_admin$)",
    ))
    return admin_app


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        return
    await refresh_wolvpay_statuses()
    with sqlite3.connect(DATABASE_PATH) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS unared_customers (
            telegram_id INTEGER PRIMARY KEY, username TEXT NOT NULL DEFAULT '',
            full_name TEXT NOT NULL DEFAULT '', first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        customers = db.execute("SELECT COUNT(*) FROM unared_customers").fetchone()[0]
        today = db.execute("SELECT COUNT(*) FROM unared_customers WHERE date(first_seen)=date('now','localtime')").fetchone()[0]
        week = db.execute("SELECT COUNT(*) FROM unared_customers WHERE first_seen >= datetime('now','-7 days')").fetchone()[0]
        invoices = paid = pending = 0
        income = 0.0
        status_counts = {}
        for table in INVOICE_TABLES:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
            if exists:
                cols = {x[1] for x in db.execute("PRAGMA table_info(" + table + ")")}
                if "amount" in cols and "status" in cols:
                    rows = db.execute("SELECT amount,status FROM " + table).fetchall()
                    invoices += len(rows)
                    for amount,status in rows:
                        status_value = str(status or "UNKNOWN").upper()
                        status_counts[status_value] = status_counts.get(status_value, 0) + 1
                        if status_value == "PAID":
                            paid += 1
                            try: income += float(amount)
                            except (ValueError, TypeError): pass
                        elif status_value in {"PENDING", "UNPAID", "PROCESSING", "AWAITING_SELECTION", "CREATED", "NEW"}:
                            pending += 1
        music = db.execute("SELECT COUNT(*) FROM digital_music_subscribers").fetchone()[0] if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='digital_music_subscribers'").fetchone() else 0
        db.execute("""CREATE TABLE IF NOT EXISTS unared_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL,
            username TEXT NOT NULL DEFAULT '', full_name TEXT NOT NULL DEFAULT '',
            button_key TEXT NOT NULL, button_label TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        total_clicks = db.execute(
            "SELECT COUNT(*) FROM unared_interactions WHERE telegram_id != ?",
            (int(BOT_OWNER_ID),)
        ).fetchone()[0]
        top_buttons = db.execute("""SELECT button_label, COUNT(*) AS total
            FROM unared_interactions WHERE telegram_id != ?
            GROUP BY button_key, button_label
            ORDER BY total DESC LIMIT 8""", (int(BOT_OWNER_ID),)).fetchall()
        recent = db.execute("""SELECT full_name, username, telegram_id, button_label, created_at
            FROM unared_interactions WHERE telegram_id != ?
            ORDER BY id DESC LIMIT 10""", (int(BOT_OWNER_ID),)).fetchall()
    top_text = "\n".join(
        f"  • {label}: {count} clics" for label, count in top_buttons
    ) or "  • Todavía no hay clics registrados."
    recent_text = "\n".join(
        f"  • {name or ('@' + username if username else 'Cliente')} → {label} | ID {tid} ({when})"
        for name, username, tid, label, when in recent
    ) or "  • Todavía no hay actividad registrada."
    report = (
        "📊 UNARED | ESTADÍSTICAS\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "👥 CLIENTES\n"
        f"• Registrados: {customers}\n"
        f"• Nuevos hoy: {today}\n"
        f"• Últimos 7 días: {week}\n"
        f"• Modo Digital: {music}\n\n"
        "🖱️ INTERACCIÓN DE CLIENTES\n"
        f"• Botones pulsados: {total_clicks}\n\n"
        "🏆 BOTONES MÁS UTILIZADOS\n"
        f"{top_text}\n\n"
        "🕘 ACTIVIDAD RECIENTE\n"
        f"{recent_text}\n\n"
        "💳 FACTURACIÓN Y PAGOS\n"
        f"• Facturas creadas: {invoices}\n"
        f"• Pendientes: {pending}\n"
        f"• Pagos confirmados: {paid}\n"
        f"• Ingresos: USD {income:,.2f}\n"
        + "• Otros estados: " + (", ".join(f"{k}: {v}" for k, v in sorted(status_counts.items()) if k not in {"PAID", "PENDING", "UNPAID", "PROCESSING"}) or "ninguno") + "\n"
        + "━━━━━━━━━━━━━━━━━━"
    )
    keyboard_rows = [
        [
            InlineKeyboardButton("👤 Ir al perfil", callback_data=f"view_customer:{int(tid)}"),
            InlineKeyboardButton("🔔 Mandar alerta", callback_data=f"notify_customer:{int(tid)}"),
        ]
        for _, _, tid, _, _ in recent
    ]
    keyboard_rows.append([
        InlineKeyboardButton("🔎 Ver más estadísticas", callback_data="admin_stats_more")
    ])
    await update.effective_message.reply_text(report, reply_markup=InlineKeyboardMarkup(keyboard_rows))


async def admin_stats_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        return
    with sqlite3.connect(DATABASE_PATH) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS unared_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL,
            username TEXT NOT NULL DEFAULT '', full_name TEXT NOT NULL DEFAULT '',
            button_key TEXT NOT NULL, button_label TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        unique_clients = db.execute(
            "SELECT COUNT(DISTINCT telegram_id) FROM unared_interactions WHERE telegram_id != ?",
            (int(BOT_OWNER_ID),)
        ).fetchone()[0]
        all_buttons = db.execute("""SELECT button_label, COUNT(*) FROM unared_interactions
            WHERE telegram_id != ?
            GROUP BY button_key, button_label ORDER BY COUNT(*) DESC, button_label ASC""",
            (int(BOT_OWNER_ID),)).fetchall()
        all_activity = db.execute("""SELECT full_name, username, telegram_id, button_label, created_at
            FROM unared_interactions WHERE telegram_id != ?
            ORDER BY id DESC LIMIT 30""", (int(BOT_OWNER_ID),)).fetchall()
    buttons_text = "\n".join(
        f"• {label}: {count} clics" for label, count in all_buttons
    ) or "• Todavía no hay botones registrados."
    activity_text = "\n".join(
        f"• {name or ('@' + username if username else 'Cliente')} | ID {tid}\n  {label} | {when}"
        for name, username, tid, label, when in all_activity
    ) or "• Todavía no hay actividad registrada."
    detail = (
        "🔎 UNARED | DETALLE DE INTERACCIONES\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Clientes que han interactuado: {unique_clients}\n\n"
        "📌 TODOS LOS BOTONES REGISTRADOS\n"
        f"{buttons_text}\n\n"
        "🧾 REGISTRO DE ACTIVIDAD (últimos 30)\n"
        f"{activity_text}\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    keyboard_rows = [
        [
            InlineKeyboardButton("👤 Ir al perfil", callback_data=f"view_customer:{int(tid)}"),
            InlineKeyboardButton("🔔 Mandar alerta", callback_data=f"notify_customer:{int(tid)}"),
        ]
        for _, _, tid, _, _ in all_activity
    ]
    keyboard_rows.append([
        InlineKeyboardButton("⬅️ Volver a estadísticas", callback_data="admin_stats")
    ])
    await update.effective_message.reply_text(
        detail,
        reply_markup=InlineKeyboardMarkup(keyboard_rows)
    )


async def find_customer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not is_admin(update.effective_user):
        if message:
            await message.reply_text("⛔ No autorizado.")
        return
    if not context.args or not context.args[0].isdigit():
        await message.reply_text("Uso: /buscarcliente TELEGRAM_ID")
        return

    tid = int(context.args[0])
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=15) as db:
            row = None
            customer_exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='unared_customers'"
            ).fetchone()
            if customer_exists:
                columns = {column[1] for column in db.execute("PRAGMA table_info(unared_customers)")}
                required = {"telegram_id", "username", "full_name"}
                if required.issubset(columns):
                    select_cols = ["telegram_id", "username", "full_name"]
                    select_cols.append("first_seen" if "first_seen" in columns else "''")
                    select_cols.append("last_seen" if "last_seen" in columns else "''")
                    row = db.execute(
                        f"SELECT {', '.join(select_cols)} FROM unared_customers WHERE telegram_id=?",
                        (tid,),
                    ).fetchone()

            if not row:
                interactions_exists = db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='unared_interactions'"
                ).fetchone()
                if interactions_exists:
                    interaction = db.execute(
                        """SELECT telegram_id, username, full_name, MIN(created_at), MAX(created_at)
                           FROM unared_interactions
                           WHERE telegram_id=? GROUP BY telegram_id""",
                        (tid,),
                    ).fetchone()
                    if interaction:
                        row = interaction

            total = 0
            for table in INVOICE_TABLES:
                exists = db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if not exists:
                    continue
                columns = {column[1] for column in db.execute(f"PRAGMA table_info({table})")}
                if "telegram_id" in columns:
                    total += db.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE telegram_id=?",
                        (tid,),
                    ).fetchone()[0]
                    if not row:
                        invoice_row = db.execute(
                            f"SELECT telegram_id FROM {table} WHERE telegram_id=? LIMIT 1",
                            (tid,),
                        ).fetchone()
                        if invoice_row:
                            row = (tid, "", "Cliente con factura", "", "")

    except sqlite3.Error:
        logger.exception("Error buscando al cliente %s.", tid)
        await message.reply_text("⚠️ No se pudo consultar el cliente por un error en la base de datos. Revisa los registros de Railway.")
        return

    if not row:
        await message.reply_text(
            "No encontramos ese cliente en los registros de clientes, actividad ni facturación."
        )
        return

    tid, username, name, first_seen, last_seen = row
    await message.reply_text(
        "👤 UNARED | FICHA DEL CLIENTE\n\n"
        f"🆔 ID: {tid}\n👤 Nombre: {name or 'Sin nombre'}\n"
        f"📛 Usuario: " + (("@" + username) if username else "Sin username") +
        f"\n📅 Registro: {first_seen or 'No disponible'}\n🕒 Última actividad: {last_seen or 'No disponible'}\n🧾 Facturas: {total}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 Ir al perfil", callback_data=f"view_customer:{int(tid)}")],
            [InlineKeyboardButton("🔔 Mandar alerta", callback_data=f"notify_customer:{tid}")],
        ]),
    )

# =====================================
# INICIO DEL BOT CON PORTADA
# =====================================

async def publish_group_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Publica el botón persistente Menu en el grupo."""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or chat.type not in ("group", "supergroup"):
        if message:
            await message.reply_text("Este comando se configura desde el grupo de UnaRed.")
        return

    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("Menu")]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Pulsa Menu para abrir UnaRed",
    )
    await message.reply_text(
        "💚 UNARED | MENÚ DEL GRUPO\n\n"
        "El botón Menu quedará disponible para todos los miembros. "
        "Al pulsarlo, recibirás el acceso al menú privado de servicios.",
        reply_markup=keyboard,
    )


async def open_private_menu_from_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entrega a cualquier miembro un enlace para abrir su menú privado."""
    message = update.effective_message
    if not message or message.text != "Menu":
        return
    bot_user = await context.bot.get_me()
    if not bot_user.username:
        await message.reply_text("Abre el bot de UnaRed desde su perfil para acceder al menú.")
        return
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "💚 Abrir menú de UnaRed",
            url=f"https://t.me/{bot_user.username}?start=grupo",
        )
    ]])
    await message.reply_text(
        f"{message.from_user.mention_html()}, aquí tienes tu menú privado de UnaRed:",
        parse_mode="HTML",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Da la bienvenida automáticamente a cada nuevo integrante del grupo."""
    message = update.effective_message
    if not message or not message.new_chat_members:
        return

    bot_user = await context.bot.get_me()
    for member in message.new_chat_members:
        if member.id == bot_user.id or member.is_bot:
            continue

        welcome_text = (
            f"💚 ¡Bienvenido/a {member.mention_html()} a UNARED!\n\n"
            "💳 Ya formas parte de nuestra comunidad.\n"
            "Para consultar servicios o realizar una solicitud, "
            "abre nuestro bot privado con el botón de abajo."
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "💚 Abrir UnaRed",
                url=f"https://t.me/{bot_user.username}?start=grupo",
            )
        ]]) if bot_user.username else None

        await message.reply_text(
            welcome_text,
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    user = update.effective_user
    is_new_customer = save_customer(user)
    if is_new_customer:
        await notify_new_customer(context.application, user)

    # Enlace privado: /start admin_panel abre el panel solo al propietario.
    if context.args and context.args[0] == "admin_panel":
        if not is_admin(user):
            await update.effective_message.reply_text("⛔ Este panel es privado y no tienes autorización.")
            return
        await admin_panel(update, context)
        return

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
        reply_markup=main_menu(update.effective_user),
    )



# =====================================
# BOTONES Y NAVEGACION
# =====================================

async def select_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    choice = query.data

    # Acciones vinculadas a la factura exacta del mensaje del cliente.
    if choice.startswith(("iv:", "ip:")):
        action, invoice_id = choice.split(":", 1)
        await query.answer()
        try:
            invoice_record = None
            table_name = None
            with sqlite3.connect(DATABASE_PATH, timeout=20) as db:
                for candidate in INVOICE_TABLES:
                    exists = db.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (candidate,)
                    ).fetchone()
                    if not exists:
                        continue
                    row = db.execute(
                        "SELECT telegram_id, amount, status FROM " + candidate + " WHERE invoice_id=?",
                        (invoice_id,),
                    ).fetchone()
                    if row:
                        table_name, invoice_record = candidate, row
                        break
            if not invoice_record:
                await query.message.reply_text("⚠️ No encontramos esta factura. Genera una nueva o contacta a UnaRed.")
                return
            telegram_id, expected_amount, current_status = invoice_record
            if int(telegram_id) != int(update.effective_user.id):
                await query.message.reply_text("⛔ Esta factura no pertenece a tu cuenta.")
                return
            status_now = str(current_status or "").upper()
            service_names = {
                "bill_invoices": "Pago de servicios",
                "dayler_invoices": "Dayler",
                "pyp_invoices": "Método PyP",
                "demo_bot_invoices": "Bot de demostración",
                "pages_invoices": "Páginas Web / Buy CC",
                "icloud_invoices": "iCloud",
                "edit_upload_invoices": "Editar y subir papel",
            }
            service_name = service_names.get(table_name, "Servicio UnaRed")
            if status_now == "PAID":
                await query.message.reply_text("✅ Esta factura ya figura como PAGADA. El equipo de UnaRed continuará con tu solicitud.")
                return
            if status_now in ("CANCELLED", "CANCELED", "REJECTED"):
                await query.message.reply_text("⛔ Esta factura está cancelada o rechazada. Genera una nueva si deseas continuar.")
                return

            admin_bot = context.application.bot_data.get("admin_bot")
            if action == "ip":
                if not admin_bot:
                    raise RuntimeError("El bot administrativo no está disponible.")
                username = "@" + update.effective_user.username if update.effective_user.username else "Sin username público"
                await admin_bot.send_message(
                    chat_id=int(BOT_OWNER_ID),
                    text=(
                        "🔔 CLIENTE INDICA QUE YA PAGÓ | UNARED\n\n"
                        f"👤 Cliente: {update.effective_user.full_name} ({username})\n"
                        f"🆔 Telegram ID: {update.effective_user.id}\n"
                        f"🛠️ Servicio: {service_name}\n"
                        f"💵 Importe: USD {expected_amount}\n"
                        f"🧾 Factura WolvPay: {invoice_id}\n"
                        "⌛ Estado: pendiente de verificación. Este aviso no confirma el pago."
                    ),
                )
                await query.message.reply_text("📩 Avisamos al equipo de UnaRed. Tu factura sigue pendiente hasta que WolvPay confirme el pago.")
                return

            if not WOLVPAY_API_KEY:
                await query.message.reply_text("⚠️ La verificación con WolvPay no está configurada. Contacta al equipo de UnaRed.")
                return
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{WOLVPAY_API_URL}/invoices/{invoice_id}",
                    headers={"Authorization": f"Bearer {WOLVPAY_API_KEY}"},
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as response:
                    payload = await response.json(content_type=None)
                    if response.status != 200:
                        logger.error("WolvPay customer verification HTTP %s for invoice %s", response.status, invoice_id)
                        await query.message.reply_text("⚠️ No pudimos consultar WolvPay ahora mismo. Inténtalo de nuevo en unos minutos.")
                        return
            invoice = payload.get("data") or payload
            provider_status = str(invoice.get("status", "")).upper()
            provider_id = str(invoice.get("invoice_id", invoice_id))
            provider_amount = Decimal(str(invoice.get("amount", "0")))
            provider_currency = str(invoice.get("currency") or "USD").upper()
            if provider_id != str(invoice_id):
                await query.message.reply_text("⚠️ WolvPay devolvió una factura diferente. No se modificó tu registro.")
                return
            if provider_status != "PAID":
                await query.message.reply_text("⌛ WolvPay todavía no confirma el pago. Espera unos minutos y vuelve a verificar.")
                return
            if provider_amount != Decimal(str(expected_amount)) or provider_currency != "USD":
                logger.warning("WolvPay customer verification mismatch for invoice %s", invoice_id)
                await query.message.reply_text("⛔ El importe o la moneda no coinciden con el registro. No se confirmó el pago; contacta a UnaRed.")
                return
            with sqlite3.connect(DATABASE_PATH, timeout=20) as db:
                db.execute(
                    "UPDATE " + table_name + " SET status='PAID' WHERE invoice_id=? AND telegram_id=? AND status='PENDING'",
                    (invoice_id, update.effective_user.id),
                )
            if admin_bot:
                username = "@" + update.effective_user.username if update.effective_user.username else "Sin username público"
                await admin_bot.send_message(
                    chat_id=int(BOT_OWNER_ID),
                    text=(
                        "💚 PAGO VERIFICADO CON WOLVPAY | UNARED\n\n"
                        f"👤 Cliente: {username}\n"
                        f"🆔 Telegram ID: {update.effective_user.id}\n"
                        f"🛠️ Servicio: {service_name}\n"
                        f"💵 Importe: USD {expected_amount}\n"
                        f"🧾 Factura: {invoice_id}\n"
                        "✅ Estado: PAID, confirmado consultando WolvPay."
                    ),
                )
            await query.message.reply_text("✅ WolvPay confirma el pago. Tu factura quedó marcada como PAGADA y el equipo de UnaRed fue notificado.")
        except (aiohttp.ClientError, asyncio.TimeoutError, sqlite3.Error, InvalidOperation, ValueError, TypeError):
            logger.exception("Error processing customer invoice action %s for %s", choice, update.effective_user.id)
            await query.message.reply_text("⚠️ No pudimos procesar la solicitud ahora mismo. Inténtalo más tarde o contacta a UnaRed.")
        except Exception:
            logger.exception("Unexpected error processing customer invoice action %s", choice)
            await query.message.reply_text("⚠️ No pudimos completar la acción. El equipo de UnaRed puede revisarlo.")
        return

    # Responder de inmediato al botón Pago Bill para quitar el indicador de carga.
    callback_answered = False
    if choice == "pagos":
        await query.answer()
        callback_answered = True

    save_customer(update.effective_user)

    if choice.startswith("copy_id:"):
        if not is_admin(update.effective_user):
            await query.answer("⛔ No autorizado.", show_alert=True)
            return
        try:
            telegram_id = int(choice.split(":", 1)[1])
            await query.answer("Te envié el ID para que puedas copiarlo.")
            await reply_with_copyable_id(query, telegram_id)
        except (ValueError, IndexError):
            await query.answer("ID no válido.", show_alert=True)
        return

    if choice.startswith("cancel_invoice:"):
        try:
            _, table_name, invoice_id = choice.split(":", 2)
            allowed_tables = {"dayler_invoices", "pyp_invoices", "demo_bot_invoices", "pages_invoices", "icloud_invoices", "bill_invoices", "edit_upload_invoices"}
            if table_name not in allowed_tables:
                raise ValueError("Invalid invoice table")
            with sqlite3.connect(DATABASE_PATH) as db:
                cursor = db.execute(
                    f"UPDATE {table_name} SET status = 'CANCELLED' WHERE invoice_id = ? AND telegram_id = ? AND status = 'PENDING'",
                    (invoice_id, update.effective_user.id),
                )
                changed = cursor.rowcount
            if changed:
                await query.answer("Pago cancelado.", show_alert=True)
                await query.edit_message_reply_markup(reply_markup=None)
                await query.message.reply_text(
                    "❌ UNARED | PAGO CANCELADO\n\n"
                    "La factura quedó cancelada. Si cambias de opinión, puedes generar una nueva."
                )
            else:
                await query.answer("Esta factura ya fue pagada, cancelada o no está disponible.", show_alert=True)
        except Exception:
            logger.exception("No se pudo cancelar la factura desde el botón.")
            await query.answer("No se pudo cancelar el pago. Contacta a UnaRed.", show_alert=True)
        return
    if update.effective_chat and update.effective_chat.type == "private":
        log_customer_interaction(update.effective_user, choice)

    # Feedback visual para las acciones principales de UnaRed.
    # Telegram no permite animar el botón; mostramos estado de proceso
    # y retiramos el teclado anterior mientras el bot prepara la respuesta.
    loading_actions = {
        "bill_pay",
        "dayler_pay",
        "pyp_pay",
        "music_catalog",
        "music_submit",
        "tool_edit_upload",
    }
    is_loading_action = (
        choice in loading_actions
        or choice.startswith((
            "bill_coin_",
            "dayler_coin_",
            "pyp_coin_",
            "pages_coin_",
            "icloud_coin_",
            "edit_upload_coin_",
        ))
    )

    if is_loading_action:
        await query.answer("⏳ Procesando tu selección...", show_alert=False)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            logger.debug("No se pudo retirar el teclado anterior para %s.", choice, exc_info=True)
    elif not callback_answered:
        await query.answer()

    # ACCESO AL PANEL ADMINISTRATIVO DESDE EL MENÚ PRINCIPAL
    if choice == "open_admin_panel":
        await admin_panel(update, context)
        return

    # ACCIONES DEL PANEL ADMINISTRATIVO
    if choice == "admin_stats":
        await admin_stats(update, context)
        return

    if choice == "admin_search_help":
        if not is_admin(update.effective_user):
            await query.message.reply_text("⛔ Panel privado.")
            return
        await query.message.reply_text(
            "🔎 UNARED | BUSCAR CLIENTE\n\n"
            "Usa el comando:\n/buscarcliente TELEGRAM_ID\n\n"
            "Ejemplo: /buscarcliente 123456789\n"
            "El cliente debe haber iniciado o interactuado con el bot para aparecer en el registro."
        )
        return

    # VOLVER AL MENU PRINCIPAL

    if choice == "menu_home":
        context.user_data.clear()

        await query.message.reply_text(
            "💚 UNARED | MENÚ PRINCIPAL\n\n"
            "LA RED QUE MUEVE TU DINERO.",
            reply_markup=main_menu(update.effective_user),
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
                await context.application.bot_data["admin_bot"].send_message(
                    chat_id=int(BOT_OWNER_ID),
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
                f"🏦 {bank_name}\n\nIntroduce el límite que aparece en tu cuenta con los botones numéricos y pulsa Confirmar.",
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
            await context.application.bot_data["admin_bot"].send_message(
                chat_id=int(BOT_OWNER_ID),
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
        caption = (
            "🧾 UNARED | PAGO DE SERVICIOS\n\n"
            "Selecciona una opción:"
        )
        banner_url = "https://i.ibb.co/HTHNhsPk/10298-B3B-996-F-4BAF-8-D43-87552-B663-C6A.png"
        try:
            # Descargar el banner desde el servidor del bot y enviarlo como archivo.
            # Así Telegram no tiene que acceder directamente al alojamiento de ImgBB.
            timeout = aiohttp.ClientTimeout(total=25, connect=10, sock_read=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(banner_url) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("Content-Type", "").lower()
                    if not content_type.startswith("image/"):
                        raise ValueError(
                            f"ImgBB devolvió un contenido que no es imagen: {content_type or 'tipo desconocido'}"
                        )
                    image_data = await response.read()

            if not image_data:
                raise ValueError("ImgBB devolvió una imagen vacía.")

            await query.message.reply_photo(
                photo=BytesIO(image_data),
                filename="unared-pago-bill.png",
                caption=caption,
                reply_markup=bills_menu(),
            )
        except Exception:
            logger.exception("No se pudo descargar o enviar el banner de Pago Bill desde ImgBB.")
            await query.message.reply_text(
                caption,
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
                f"🧾 {payment_name}\n\nMonto: USD 0\nUsa los botones numéricos:",
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
            f"🧾 {context.user_data.get('bill_category', 'Pago')}\n\nMonto: USD {amount or '0'}",
            reply_markup=bill_amount_keyboard(),
        )
        return

    if choice == "bill_backspace":
        amount = context.user_data.get("bill_amount", "")[:-1]
        context.user_data["bill_amount"] = amount
        await query.edit_message_text(
            f"🧾 {context.user_data.get('bill_category', 'Pago')}\n\nMonto: USD {amount or '0'}",
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
            "💚 UNARED | MÉTODO DE PAGO\n\n"
            f"Categoría: {context.user_data.get('bill_category')}\n"
            f"Monto: USD {amount}\n\n"
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
            await notify_invoice_pending(context.application, user.id, invoice_id, amount, category, "bill_invoices", send_customer=False, send_admin=True)
            asyncio.create_task(schedule_payment_reminder(
                context.application, "bill_invoices", invoice_id, user.id, amount, category, invoice_url
            ))
            await query.message.reply_text(
                "💚 UNARED | FACTURA DE PAGO DE SERVICIOS\n\n"
                f"🛠️ Servicio: {category}\n"
                f"💵 Importe: USD {amount}\n"
                f"💳 Moneda: {'Bitcoin (BTC)' if coin == 'btc' else 'USDT (TRC20)'}\n"
                f"🧾 Factura: {invoice_id}\n\n"
                "🔐 Pulsa «Abrir factura y pagar» para completar el pago.\n"
                "⚡️ WolvPay confirmará el pago automáticamente.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Abrir factura y pagar", url=invoice_url)],
                    [InlineKeyboardButton("🔎 Verificar pago", callback_data=f"iv:{invoice_id}")],
                    [InlineKeyboardButton("✅ Ya pagué", callback_data=f"ip:{invoice_id}")],
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
        digital_caption = (
            "📟 UNARED | MODO DIGITAL\n\n"
            "🎵 Música para escuchar directamente en Telegram.\n"
            "Explora el catálogo aprobado o envía una canción para revisión."
        )
        with sqlite3.connect(DATABASE_PATH) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS digital_banner (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                file_id TEXT NOT NULL
            )""")
            banner = db.execute("SELECT file_id FROM digital_banner WHERE id = 1").fetchone()

        # Primero intenta usar el file_id guardado por Telegram; si no existe
        # o queda inválido, utiliza la portada fija configurada en el código.
        banner_file_id = banner[0].strip() if banner and banner[0] else ""
        banner_url = "https://i.ibb.co/C5NDDGjZ/743800-F9-4-E12-4093-91-E2-4-F05-EB16161-E.png"
        if banner_file_id and not banner_file_id.startswith(("http://", "https://")):
            try:
                await query.message.reply_photo(
                    photo=banner_file_id,
                    caption=digital_caption,
                    reply_markup=digital_music_menu(),
                )
                logger.info("Banner de Modo Digital enviado usando file_id guardado.")
                return
            except Exception:
                logger.exception("Falló el file_id guardado; se usará la portada fija.")
        try:
            await query.message.reply_photo(
                photo=banner_url,
                caption=digital_caption,
                reply_markup=digital_music_menu(),
            )
            logger.info("Banner de Modo Digital enviado desde la URL fija.")
        except Exception:
            logger.exception("No se pudo enviar la portada fija de Modo Digital.")
            await query.message.reply_text(
                "⚠️ No se pudo cargar la portada de Modo Digital. Inténtalo de nuevo más tarde.",
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
            columns = {item[1] for item in db.execute("PRAGMA table_info(digital_music)")}
            if "media_type" not in columns:
                db.execute("ALTER TABLE digital_music ADD COLUMN media_type TEXT NOT NULL DEFAULT 'audio'")
            if "file_name" not in columns:
                db.execute("ALTER TABLE digital_music ADD COLUMN file_name TEXT NOT NULL DEFAULT ''")
            row = db.execute(
                "SELECT file_id, title, performer, media_type, file_name FROM digital_music WHERE id = ? AND status = 'APPROVED'",
                (song_id,),
            ).fetchone()
        if not row:
            await query.message.reply_text("Esta canción ya no está disponible.")
            return
        file_id, title, performer, media_type, file_name = row
        if media_type == "document":
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=file_id,
                filename=file_name or None,
                caption=f"🎵 UNARED | MODO DIGITAL\n{title}",
            )
        else:
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

    if choice == "pyp_pay":
        await query.message.reply_text(
            "💚 UNARED | FACTURA MÉTODO PyP\n\n"
            "Total: US$100\n"
            "Selecciona la criptomoneda para generar tu factura individual:",
            reply_markup=pyp_coin_menu(),
        )
        return

    if choice.startswith("pyp_coin_"):
        coin = choice.replace("pyp_coin_", "", 1)
        if coin not in ("btc", "trc20_usdt"):
            await query.message.reply_text("Método de pago no disponible.")
            return
        if not WOLVPAY_API_KEY:
            await query.message.reply_text("El pago automático no está configurado. Contacta al equipo de UnaRed.")
            return
        user = update.effective_user
        username = user.username or ""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{WOLVPAY_API_URL}/invoices",
                    headers={
                        "Authorization": f"Bearer {WOLVPAY_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "amount": 100,
                        "currency": "USD",
                        "coin": coin,
                        "description": f"UNARED_PYP|telegram_id={user.id}",
                        "white_label": False,
                    },
                    timeout=aiohttp.ClientTimeout(total=25),
                ) as response:
                    payload = await response.json(content_type=None)
                    if response.status not in (200, 201) or payload.get("success") is False:
                        logger.error("WolvPay PyP invoice error: HTTP %s", response.status)
                        raise RuntimeError("No se pudo crear la factura.")
            invoice_data = payload.get("data") or payload
            invoice_id = invoice_data.get("invoice_id")
            invoice_url = invoice_data.get("url") or invoice_data.get("payment_url")
            if not invoice_id or not invoice_url:
                raise RuntimeError("Respuesta incompleta del proveedor.")
            with sqlite3.connect(DATABASE_PATH) as db:
                db.execute("""CREATE TABLE IF NOT EXISTS pyp_invoices (
                    invoice_id TEXT PRIMARY KEY,
                    telegram_id INTEGER NOT NULL,
                    amount TEXT NOT NULL,
                    username TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'PENDING'
                )""")
                db.execute(
                    """INSERT INTO pyp_invoices
                       (invoice_id, telegram_id, amount, username, status)
                       VALUES (?, ?, '100.00', ?, 'PENDING')""",
                    (invoice_id, user.id, username),
                )
            await notify_invoice_pending(
                context.application, user.id, invoice_id, "100", "Método PyP",
                "pyp_invoices", send_customer=False, send_admin=True
            )
            asyncio.create_task(schedule_payment_reminder(
                context.application, "pyp_invoices", invoice_id, user.id,
                "100", "Método PyP", invoice_url
            ))
            await query.message.reply_text(
                "💚 UNARED | FACTURA MÉTODO PyP\n\n"
                "Importe: US$100\n"
                f"Moneda: {'Bitcoin (BTC)' if coin == 'btc' else 'USDT (TRC20)'}\n"
                f"Factura: {invoice_id}\n\n"
                "Pulsa «Abrir factura y pagar» para completar el pago. "
                "WolvPay confirmará el pago automáticamente.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Abrir factura y pagar", url=invoice_url)],
                    [InlineKeyboardButton("🔎 Verificar pago", callback_data=f"iv:{invoice_id}")],
                    [InlineKeyboardButton("✅ Ya pagué", callback_data=f"ip:{invoice_id}")],
                    [InlineKeyboardButton("⬅️ Volver a Método PyP", callback_data="tool_pyp")],
                ]),
            )
        except Exception:
            logger.exception("No se pudo crear la factura WolvPay para Método PyP.")
            await query.message.reply_text(
                "No pudimos generar la factura. Inténtalo más tarde o contacta al equipo de UnaRed."
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
            await notify_invoice_pending(context.application, update.effective_user.id, invoice_id, "150", "Dayler", "dayler_invoices", send_customer=False, send_admin=True)
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
                    [InlineKeyboardButton("🔎 Verificar pago", callback_data=f"iv:{invoice_id}")],
                    [InlineKeyboardButton("✅ Ya pagué", callback_data=f"ip:{invoice_id}")]
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
                await context.application.bot_data["admin_bot"].send_message(
                    chat_id=int(BOT_OWNER_ID),
                    text=f"💚 PAGO DAYLER CONFIRMADO | UNARED\nCliente: {'@' + update.effective_user.username if update.effective_user.username else 'No tiene username público'}\nFactura: {invoice_id}\nCliente Telegram ID: {update.effective_user.id}\nEstado: PAGADO (consulta manual verificada con WolvPay)."
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
                "🔎 ¿Buscas un bot que esté funcionando?\n\n"
                "🤖En UnaRed Bot tenemos todos los Bot que está funcionando\n\n"
                  "Status: ✅ Online\n\n"
                "Selecciona el tipo de automatización que necesitas:\n\n"
            ),
            reply_markup=bot_catalog_menu(),
        )
        return

    if choice == "botproduct_template":
        await query.answer()
        await query.message.reply_photo(
            photo="https://i.ibb.co/5qz3HNw/115569821-1795196307147570.jpg",
            caption=(
                "🤖 LICENCIA | UNARED\n\n"
                "🧪 Ejemplo demostración.\n"
                "Name: Nombre del cliente\n"
                "DOB: 06/04/1990\n"
                "DI: S78491614 MA\n\n"
                "💵 Precio: US$35\n"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Comprar US$35", callback_data="botdemo_buy_template")],
                [InlineKeyboardButton("❓ Ayuda", callback_data="bothelp_template")],
                [InlineKeyboardButton("📩 Contactar", url="https://t.me/flowmontana777")],
                [InlineKeyboardButton("⬅️ Volver al catálogo", callback_data="tool_bots")],
            ]),
        )
        return

    if choice.startswith("bothelp_"):
        product = choice.rsplit("_", 1)[-1]
        labels = {"otp": "BOT OTP", "ssn": "BOT SSN", "check": "BOT CHECK", "template": "LICENCIA"}
        label = labels.get(product)
        if not label:
            await query.answer("Ayuda no disponible.", show_alert=True)
            return

        await query.answer()
        if product == "otp":
            await query.message.reply_text(
                "❓ PREGUNTAS FRECUENTES | BOT OTP\n\n"
                "❶ ¿Qué es Bot OTP?\n"
                "Plataforma para realizar llamadas IVR automatizadas de verificación de fraude con el nombre dinámico del cliente.\n\n"
                "❷ ¿Cómo funciona?\n"
                "① Ingresas datos del cliente.\n"
                "② Eliges la categoría y empresa.\n"
                "③ Seleccionas qué datos pedir (OTP, PIN, CVV, etc.).\n"
                "④ El IVR llama con el script adecuado.\n"
                "⑤ Apruebas o rechazas desde el bot.\n\n"
                "❸ ¿Qué tipos de datos puedo pedir?\n"
                "🔢 OTP — código de un solo uso\n"
                "🔐 PIN — código personal\n"
                "💳 CVV — código de tarjeta\n"
                "🪪 SSN — seguro social\n"
                "💳Tarjeta — últimos dígitos\n"
                "🚘 Licencia — licencia de conducir\n\n"
                "❹ ¿Qué categorías hay?\n"
                "💳 Pagos · 🏦 Banco · 🛒 E-commerce · 📱 Telecom\n"
                "🍎 Apple · 🔵 Google · 🪟 Microsoft · ⚙️ Genérica\n\n"
                "❺ ¿Cómo pago?\n"
                "Mediante WolvPay con criptomonedas compatibles, como BTC, ETH, USDT y LTC.\n\n"
                "❻ ¿Necesito instalar algo?\n"
                "No. Todo funciona desde Telegram en cualquier dispositivo."
            )
        else:
            await query.message.reply_text(
                f"❓ AYUDA | {label}\n\n"
                "La sección de preguntas frecuentes se está preparando. "
                "Pronto encontrarás aquí las respuestas a tus dudas."
            )
        return

    if choice == "botproduct_otp":
        await query.message.reply_photo(
            photo="https://i.ibb.co/cSK5YPpW/871464408-1795197001675973.jpg",
            caption=(
                "🔐 OTP Verification System v3.2\n\n"
                "📲 Automated Call & SMS Verification Tool\n\n"
                "💵 Precio: US$35\n\n"
                "🧾 Después de realizar el pago, conserva el comprobante "
                "y contacta al equipo para verificarlo.\n\n"
                "✨Supported services:\n"
                "🏦Wells Fargo\n"
                "🏦Bank of America\n"
                "🏦Chase\n"
                "💳Paypal\n"
                "📧Gmail\n"
                "📱Instagram\n"
                "📲3D security\n"
                "🔢Verizon pin\n"
                " Icloud\n"
                "👻And more...\n\n"
                "Features:\n"
                "• 📞 Real-time call panel\n"
                "• 🗣️ Human voice AI\n"
                "• 🛡️ Custom caller ID\n"
                "• 🌍 Multi country routes\n"
                "• 📊 Live status logs\n\n"
                "⚠️ Uso exclusivo para obtener código\n\n"
                "Status: ✅ Online\n\n"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Comprar $35", callback_data="botdemo_buy_otp")],
                [InlineKeyboardButton("❓ Ayuda", callback_data="bothelp_otp")],
                [InlineKeyboardButton("📩 Contactar", url="https://t.me/flowmontana777")],
                [InlineKeyboardButton("⬅️ Volver al catálogo", callback_data="tool_bots")],
            ]),
        )
        return

    if choice == "botproduct_ssn":
        await query.message.reply_photo(
            photo="https://i.ibb.co/jZMvm7Mk/51859006-1795198455885885.jpg",
            caption="💚 UNARED | BOT SSN\n\nConsulta información y disponibilidad con nuestro equipo.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Comprar $35", callback_data="botdemo_buy_ssn")],
                [InlineKeyboardButton("❓ Ayuda", callback_data="bothelp_ssn")],
                [InlineKeyboardButton("📩 Contactar", url="https://t.me/flowmontana777")],
                [InlineKeyboardButton("⬅️ Volver al catálogo", callback_data="tool_bots")],
            ]),
        )
        return

    if choice == "botproduct_check":
        await query.message.reply_photo(
            photo="https://i.ibb.co/RkZRgV38/516870573-1795201394511117.jpg",
            caption="💚 UNARED | BOT CHECK\n\nConsulta información y disponibilidad con nuestro equipo.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Comprar $35", callback_data="botdemo_buy_check")],
                [InlineKeyboardButton("❓ Ayuda", callback_data="bothelp_check")],
                [InlineKeyboardButton("📩 Contactar", url="https://t.me/flowmontana777")],
                [InlineKeyboardButton("⬅️ Volver al catálogo", callback_data="tool_bots")],
            ]),
        )
        return

    # DEMOS AISLADAS: DATOS SINTÉTICOS; NO HAY CONSULTAS A DATOS REALES
    if choice.startswith("botdemo_buy_"):
        product = choice.rsplit("_", 1)[-1]
        labels = {"otp": "BOT OTP", "ssn": "BOT SSN", "check": "BOT CHECK", "template": "LICENCIA"}
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
                    invoice_id TEXT PRIMARY KEY, telegram_id INTEGER NOT NULL, amount TEXT NOT NULL,                    product TEXT NOT NULL, username TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING'
                )""")
                db.execute(
                    "INSERT INTO demo_bot_invoices VALUES (?, ?, ?, ?, ?, 'PENDING')",
                    (invoice_id, user.id, "35.00", product, user.username or ""),
                )
            await notify_invoice_pending(context.application, user.id, invoice_id, "35", labels[product], "demo_bot_invoices", send_customer=False, send_admin=True)
            asyncio.create_task(schedule_payment_reminder(context.application, "demo_bot_invoices", invoice_id, user.id, "35", labels[product], invoice_url))
            await query.message.reply_text(
                f"💚 UNARED | FACTURA\nProducto: {labels[product]}\nImporte: US$35\nFactura: {invoice_id}\n"
                "Uso de demostración con datos ficticios únicamente.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Abrir factura y pagar", url=invoice_url)],
                    [InlineKeyboardButton("🔎 Verificar pago", callback_data=f"iv:{invoice_id}")],
                    [InlineKeyboardButton("✅ Ya pagué", callback_data=f"ip:{invoice_id}")],
                    [InlineKeyboardButton("⬅️ Volver", callback_data="tool_bots")],
                ]),
            )

        except Exception:
            logger.exception("Error creando factura de demo sandbox.")
            await query.message.reply_text("No pudimos generar la factura. Inténtalo más tarde.")
        return

    if choice.startswith("botdemo_paid_"):
        product = choice.rsplit("_", 1)[-1]
        labels = {"otp": "BOT OTP", "ssn": "BOT SSN", "check": "BOT CHECK", "template": "LICENCIA"}
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
        await context.application.bot_data["admin_bot"].send_message(
            chat_id=int(BOT_OWNER_ID),
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
        labels = {"otp": "BOT OTP", "ssn": "BOT SSN", "check": "BOT CHECK", "template": "LICENCIA"}
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
            await context.application.bot_data["admin_bot"].send_message(
                chat_id=int(BOT_OWNER_ID),
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
                [InlineKeyboardButton("💳 Pagar US$100", callback_data="pyp_pay")],
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
                "🌐 Catálogo de páginas web Cc.\n\n"
                "━━━━━━━━━━\n\n"
                "🏷️ Precio especial: US$17\n"
                "💰 Precio regular: <del>US$20</del>\n\n"
                f"📦 Cantidad: {quantity} {'unidad' if quantity == 1 else 'unidades'}\n"
                f"🧾 Total a pagar: US${total}"
            ),
            parse_mode="HTML",
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
                "🌐 Catálogo de páginas web Cc.\n\n"
                "━━━━━━━━━━\n\n"
                "🏷️ Precio especial: US$17\n"
                "💰 Precio regular: <del>US$20</del>\n\n"
                f"📦 Cantidad: {quantity} {'unidad' if quantity == 1 else 'unidades'}\n"
                f"🧾 Total a pagar: US${total}"
            ),
            parse_mode="HTML",
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
            await notify_invoice_pending(context.application, user.id, invoice_id, str(total), "Páginas Web", "pages_invoices", send_customer=False, send_admin=True)
            asyncio.create_task(schedule_payment_reminder(context.application, "pages_invoices", invoice_id, user.id, str(total), "Páginas Web", invoice_url))
            await query.message.reply_text(
                "💚 UNARED | FACTURA DE PÁGINAS WEB\n\n"
                f"📦 Cantidad: {quantity}\n"
                f"💵 Total: US${total}\n"
                f"🧾 Factura: {invoice_id}\n\n"
                "Completa el pago desde WolvPay.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Abrir factura y pagar", url=invoice_url)],
                    [InlineKeyboardButton("🔎 Verificar pago", callback_data=f"iv:{invoice_id}")],
                    [InlineKeyboardButton("✅ Ya pagué", callback_data=f"ip:{invoice_id}")],
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
            await context.application.bot_data["admin_bot"].send_message(
                chat_id=int(BOT_OWNER_ID),
                text=(
                    "🔔 AVISO DE PAGO | PÁGINAS WEB\n"
                    f"Cliente: {username_text}\n"
                    f"Cliente Telegram ID: {update.effective_user.id}\n"
                    f"Cantidad: {quantity}\nImporte: US${amount}\nFactura: {invoice_id}\n"
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
            await context.application.bot_data["admin_bot"].send_message(
                chat_id=int(BOT_OWNER_ID),
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
        await query.message.reply_text(
            "🪪 UNARED | SSN\n\n"
            "Selecciona una opción:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔎 Buscar", callback_data="ssn_search")],
                [InlineKeyboardButton("❓ FAQ", callback_data="ssn_faq")],
                [InlineKeyboardButton("⬅️ Volver al Centro de Herramientas", callback_data="menu_tools")],
            ]),
        )
        return

    if choice == "ssn_faq":
        await query.message.reply_text(
            "❗️❓ UNARED | PREGUNTAS FRECUENTES (FAQ)\n\n"
            "1️⃣ ¿Qué es el SSN?\n"
            "Es el número de Seguro Social que la Administración del Seguro Social de EE. UU. "
            "utiliza para identificar y llevar registros de las personas.\n\n"
            "2️⃣ ¿Qué hago si olvidé mi SSN?\n"
            "Puedes solicitar orientación para recuperarlo mediante los canales oficiales de "
            "la Administración del Seguro Social (SSA).\n\n"
            "3️⃣ ¿Puedo buscar el SSN de otra persona?\n"
            "No. Solo podemos orientar al titular para recuperar su propio número.\n\n"
            "4️⃣ ¿Debo enviar mi SSN por este chat?\n"
            "No. Nunca compartas aquí tu SSN completo, contraseñas ni documentos sensibles.\n\n"
            "5️⃣ ¿Dónde puedo obtener ayuda oficial?\n"
            "Visita https://www.ssa.gov/number-card/ para información y asistencia.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔎 Buscar", callback_data="ssn_search")],
                [InlineKeyboardButton("⬅️ Volver a SSN", callback_data="tool_ssn_info")],
                [InlineKeyboardButton("⬅️ Centro de Herramientas", callback_data="menu_tools")],
            ]),
            disable_web_page_preview=True,
        )
        return

    if choice == "ssn_search":
        await query.message.reply_text(
            "🔎 UNARED | ASISTENCIA SSN\n\n"
            "Orientación para que el titular recupere su propio SSN mediante los canales oficiales de la SSA.\n\n"
            "💵 Precio: US$3.20\n"
            "🔐 No solicitamos SSN completo, fecha de nacimiento, documentos, contraseñas ni datos de terceros.\n\n"
            "No realizamos búsquedas en bases de datos ni entregamos números de Seguro Social. Al continuar confirmas que eres el titular y que solo deseas orientación oficial.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Soy el titular — Continuar", callback_data="ssn_assist_confirm")],
                [InlineKeyboardButton("📋 Ver estado de mi solicitud", callback_data="ssn_status")],
                [InlineKeyboardButton("⬅️ Volver a SSN", callback_data="tool_ssn_info")],
            ]),
        )
        return

    if choice == "ssn_assist_confirm":
        await query.answer()
        user = update.effective_user
        if not WOLVPAY_API_KEY:
            await query.message.reply_text("⚠️ WolvPay no está configurado. Contacta al equipo de UnaRed.")
            return
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{WOLVPAY_API_URL}/invoices",
                    headers={"Authorization": f"Bearer {WOLVPAY_API_KEY}", "Content-Type": "application/json"},
                    json={
                        "amount": 3.20,
                        "currency": "USD",
                        "coin": "trc20_usdt",
                        "description": f"UNARED_SSN_ASSISTANCE|telegram_id={user.id}",
                        "white_label": False,
                    },
                    timeout=aiohttp.ClientTimeout(total=25),
                ) as response:
                    payload = await response.json(content_type=None)
                    if response.status not in (200, 201) or payload.get("success") is False:
                        raise RuntimeError("WolvPay invoice creation failed")
            data = payload.get("data") or payload
            invoice_id = data.get("invoice_id")
            invoice_url = data.get("url") or data.get("payment_url")
            if not invoice_id or not invoice_url:
                raise RuntimeError("Incomplete WolvPay invoice response")
            with sqlite3.connect(DATABASE_PATH, timeout=20) as db:
                db.execute("""CREATE TABLE IF NOT EXISTS ssn_assistance_invoices (
                    invoice_id TEXT PRIMARY KEY,
                    telegram_id INTEGER NOT NULL,
                    amount TEXT NOT NULL DEFAULT '3.20',
                    request_type TEXT NOT NULL DEFAULT 'RECOVERY_GUIDANCE',
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    request_status TEXT NOT NULL DEFAULT 'WAITING_PAYMENT',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )""")
                db.execute(
                    "INSERT INTO ssn_assistance_invoices (invoice_id, telegram_id, amount, request_type, status, request_status) VALUES (?, ?, '3.20', 'RECOVERY_GUIDANCE', 'PENDING', 'WAITING_PAYMENT')",
                    (invoice_id, user.id),
                )
            await notify_invoice_pending(
                context.application, user.id, invoice_id, "3.20",
                "Orientación oficial para recuperar SSN propio",
                "ssn_assistance_invoices", send_customer=False, send_admin=True
            )
            admin_bot = context.application.bot_data.get("admin_bot")
            if admin_bot:
                await admin_bot.send_message(
                    chat_id=int(BOT_OWNER_ID),
                    text=(
                        "🪪 NUEVA SOLICITUD | ASISTENCIA SSN\n\n"
                        f"Cliente: {user.full_name}\nTelegram ID: {user.id}\nFactura: {invoice_id}\n"
                        "Alcance: orientación al titular mediante canales oficiales SSA.\n"
                        "No se recopilaron datos de identidad sensibles.\nEstado: esperando pago."
                    ),
                )
            await query.message.reply_text(
                "💚 UNARED | FACTURA DE ASISTENCIA\n\n"
                "Servicio: orientación oficial para recuperar tu propio SSN\n"
                "Importe: US$3.20\nMétodo: USDT (TRC20) mediante WolvPay\n"
                f"Factura: {invoice_id}\n\n"
                "WolvPay confirmará el pago. Después podrás consultar el estado de tu solicitud.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 Abrir factura y pagar", url=invoice_url)],
                    [InlineKeyboardButton("🔎 Verificar pago", callback_data=f"iv:{invoice_id}")],
                    [InlineKeyboardButton("📋 Ver estado", callback_data="ssn_status")],
                    [InlineKeyboardButton("⬅️ Volver a SSN", callback_data="tool_ssn_info")],
                ]),
            )
        except Exception:
            logger.exception("No se pudo crear la factura de asistencia SSN.")
            await query.message.reply_text("❌ No pudimos generar la factura. Inténtalo más tarde o contacta al equipo.")
        return

    if choice == "ssn_status":
        user = update.effective_user
        with sqlite3.connect(DATABASE_PATH, timeout=20) as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ssn_assistance_invoices'").fetchone()
            row = db.execute(
                "SELECT invoice_id, status, request_status, created_at FROM ssn_assistance_invoices WHERE telegram_id=? ORDER BY created_at DESC LIMIT 1",
                (user.id,),
            ).fetchone() if exists else None
        if not row:
            status_text = "Todavía no tienes solicitudes registradas."
        else:
            invoice_id, payment_status, request_status, created_at = row
            labels = {
                "WAITING_PAYMENT": "💳 Esperando pago",
                "PAID": "⌛️ Cargando... — pago confirmado, en cola de revisión",
                "PROCESSING": "⌛️ Cargando... — solicitud en revisión",
                "COMPLETED": "✅ Completada",
            }
            state = request_status if str(payment_status).upper() == "PAID" else "WAITING_PAYMENT"
            status_text = f"Factura: {invoice_id}\nEstado: {labels.get(state, state)}\nFecha: {created_at}"
        await query.message.reply_text(
            "📋 UNARED | ESTADO DE MI SOLICITUD\n\n" + status_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Actualizar", callback_data="ssn_status")],
                [InlineKeyboardButton("⬅️ Volver a SSN", callback_data="tool_ssn_info")],
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
            await notify_invoice_pending(context.application, user.id, invoice_id, str(total), "iCloud", "icloud_invoices", send_customer=False, send_admin=True)
            asyncio.create_task(schedule_payment_reminder(context.application, "icloud_invoices", invoice_id, user.id, str(total), "iCloud", invoice_url))
            await query.message.reply_text(
                "💚 UNARED | FACTURA ICLOUD\n\n"
                f"📦 Cantidad: {quantity}\n💵 Total: US${total}\n"
                f"Factura: {invoice_id}\n\nCompleta el pago desde WolvPay.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Abrir factura y pagar", url=invoice_url)],
                    [InlineKeyboardButton("🔎 Verificar pago", callback_data=f"iv:{invoice_id}")],
                    [InlineKeyboardButton("✅ Ya pagué", callback_data=f"ip:{invoice_id}")],
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
                await context.application.bot_data["admin_bot"].send_message(
                    chat_id=int(BOT_OWNER_ID),
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
            await context.application.bot_data["admin_bot"].send_message(chat_id=int(BOT_OWNER_ID),
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
            await notify_invoice_pending(context.application, user.id, invoice_id, "250", "Editar y subir papel", "edit_upload_invoices", send_customer=False, send_admin=True)
            asyncio.create_task(schedule_payment_reminder(context.application, "edit_upload_invoices", invoice_id, user.id, "250", "Editar y subir papel", invoice_url))
            await query.message.reply_text(
                "💚 UNARED | FACTURA - QUIERO EDITAR Y SUBIR PAPEL\n\n"
                "💵 Total: US$250\n"
                f"🧾 Factura: {invoice_id}\n\n"
                "Completa el pago desde WolvPay. La confirmación se enviará automáticamente cuando el proveedor verifique el pago.\n",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Abrir factura y pagar", url=invoice_url)],
                    [InlineKeyboardButton("🔎 Verificar pago", callback_data=f"iv:{invoice_id}")],
                    [InlineKeyboardButton("✅ Ya pagué", callback_data=f"ip:{invoice_id}")],
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
        await context.application.bot_data["admin_bot"].send_message(
            chat_id=int(BOT_OWNER_ID),
            text=(
                "💚 UNARED | AVISO: CLIENTE INDICA QUE PAGÓ\n\n"
                f"👤 Cliente: {user.full_name}\n"
                f"🔗 Usuario: {username}\n"
                f"🆔 Telegram ID: {user.id}\n"
                "📄 Servicio: Quiero Editar y Subir Papel\n"
                f"💵 Importe: US${amount}\n"
                f"🧾 Factura: {invoice_id}\n"
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
            await context.application.bot_data["admin_bot"].send_message(
                chat_id=int(BOT_OWNER_ID),
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
    if not message:
        return

    channel_username = (message.chat.username or "").lower() if message.chat else ""
    if channel_username != "una1red":
        return

    audio = message.audio
    document = message.document
    media = audio or document
    if not media:
        return

    file_name = (getattr(media, "file_name", None) or "").strip()
    mime_type = (getattr(media, "mime_type", None) or "").lower()
    extension = os.path.splitext(file_name)[1].lower()
    music_extensions = {
        ".mp3", ".m4a", ".m4b", ".aac", ".ogg", ".oga", ".opus",
        ".wav", ".flac", ".wma", ".aiff", ".aif", ".alac", ".amr",
        ".mid", ".midi", ".mpga", ".weba",
    }
    is_music_document = bool(document) and (
        mime_type.startswith("audio/") or extension in music_extensions
    )
    if document and not is_music_document:
        logger.info(
            "Documento ignorado en @Una1Red: no parece un archivo musical (mime=%s, nombre=%s).",
            mime_type, file_name
        )
        return
    if not audio and not is_music_document:
        return

    media_type = "audio" if audio else "document"
    title = (
        (getattr(media, "title", None) or "").strip()
        or (os.path.splitext(file_name)[0] if file_name else "")
        or (message.caption or "").strip()
        or "Canción de UnaRed"
    )[:120]
    performer = (getattr(media, "performer", None) or "").strip()[:120]
    file_id = media.file_id

    logger.info(
        "Música detectada en @Una1Red: message_id=%s, tipo=%s, mime=%s, archivo=%s",
        message.message_id, media_type, mime_type or "no indicado", file_name or title
    )

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
        columns = {row[1] for row in db.execute("PRAGMA table_info(digital_music)")}
        if "media_type" not in columns:
            db.execute("ALTER TABLE digital_music ADD COLUMN media_type TEXT NOT NULL DEFAULT 'audio'")
        if "file_name" not in columns:
            db.execute("ALTER TABLE digital_music ADD COLUMN file_name TEXT NOT NULL DEFAULT ''")
        db.execute("""CREATE TABLE IF NOT EXISTS digital_music_subscribers (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL DEFAULT '',
            full_name TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        exists = db.execute(
            "SELECT id FROM digital_music WHERE file_id = ? LIMIT 1",
            (file_id,),
        ).fetchone()
        if exists:
            logger.info("La música ya estaba registrada en el catálogo: %s", title)
            return
        db.execute(
            """INSERT INTO digital_music
               (file_id, title, performer, submitted_by, submitter_name, status, media_type, file_name)
               VALUES (?, ?, ?, ?, ?, 'APPROVED', ?, ?)""",
            (file_id, title, performer, 0, "Canal @Una1Red", media_type, file_name),
        )
        subscribers = [
            row[0] for row in db.execute(
                "SELECT telegram_id FROM digital_music_subscribers"
            ).fetchall()
        ]
        banner_row = db.execute(
            "SELECT file_id FROM digital_banner WHERE id = 1"
        ).fetchone() if db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'digital_banner'"
        ).fetchone() else None

    notification = (
        "🎵 ¡NUEVA MÚSICA EN UNARED!\n\n"
        f"🎧 {title}\n"
        + (f"👤 {performer}\n" if performer else "")
        + "\nYa está disponible en Modo Digital. "
          "Entra al bot y selecciona «Modo Digital» → «Escuchar música»."
    )
    # Priorizar la portada incrustada en el audio/documento; si no existe,
    # utilizar la portada general de Modo Digital como respaldo.
    music_thumbnail = getattr(media, "thumbnail", None)
    cover_file_id = music_thumbnail.file_id if music_thumbnail else ""
    banner_file_id = banner_row[0].strip() if banner_row and banner_row[0] else ""
    notification_photo = (
        cover_file_id
        or (banner_file_id if not banner_file_id.startswith(("http://", "https://")) else "")
    )
    sent = 0
    if not subscribers:
        logger.warning(
            "La música %s se agregó al catálogo, pero no hay suscriptores registrados. "
            "Los clientes deben abrir el bot y pulsar /start.",
            title,
        )

    for telegram_id in subscribers:
        try:
            # Si la portada no se puede enviar (por ejemplo, miniatura no válida),
            # enviar igualmente la notificación de texto para no perder el aviso.
            if notification_photo:
                try:
                    await context.bot.send_photo(
                        chat_id=telegram_id,
                        photo=notification_photo,
                        caption=notification,
                    )
                except Exception as photo_exc:
                    logger.warning(
                        "No se pudo enviar la portada al usuario %s; se enviará texto: %s",
                        telegram_id, photo_exc
                    )
                    await context.bot.send_message(
                        chat_id=telegram_id,
                        text=notification,
                    )
            else:
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text=notification,
                )
            sent += 1
        except Exception as exc:
            logger.warning(
                "No se pudo notificar al usuario %s sobre %s: %s",
                telegram_id, title, exc
            )

    logger.info(
        "Música importada desde @Una1Red: %s (tipo=%s, extensión=%s, mime=%s). "
        "Notificaciones enviadas: %s/%s",
        title, media_type, extension or "sin extensión",
        mime_type or "no indicado", sent, len(subscribers)
    )


# =====================================
# RECIBIR SOLICITUDES
# =====================================

async def receive_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_customer(update.effective_user)
    # Los mensajes de grupos/canales no son solicitudes de clientes.
    # La música de @Una1Red se procesa únicamente en channel_music_ingest.
    if not update.effective_chat or update.effective_chat.type != "private":
        return

    # El administrador puede configurar la portada de Modo Digital
    # enviando la imagen al bot con el texto /setdigitalbanner como caption.
    if (
        update.message
        and update.message.photo
        and (update.message.caption or "").strip().lower() == "/setdigitalbanner"
        and str(update.effective_user.id) == str(ADMIN_CHAT_ID)
    ):
        banner_file_id = update.message.photo[-1].file_id
        with sqlite3.connect(DATABASE_PATH) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS digital_banner (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                file_id TEXT NOT NULL
            )""")
            db.execute(
                "INSERT INTO digital_banner (id, file_id) VALUES (1, ?) "
                "ON CONFLICT(id) DO UPDATE SET file_id = excluded.file_id",
                (banner_file_id,),
            )
        await update.message.reply_text("✅ Banner de Modo Digital guardado correctamente.")
        return

    if context.user_data.get("music_upload_mode"):
        message = update.message
        media = message.audio or message.document
        if not media:
            await message.reply_text(
                "🎵 Envía un archivo de audio (MP3, M4A, AAC, OGG, OPUS, WAV, FLAC, WMA, AIFF o AMR). "
                "Puedes enviarlo como «Audio» o como «Archivo»."
            )
            return

        file_name = (getattr(media, "file_name", None) or "").strip()
        mime_type = (getattr(media, "mime_type", None) or "").lower()
        extension = os.path.splitext(file_name)[1].lower()
        allowed_audio_extensions = {
            ".mp3", ".m4a", ".m4b", ".aac", ".ogg", ".oga", ".opus",
            ".wav", ".flac", ".wma", ".aiff", ".aif", ".alac", ".amr",
            ".mid", ".midi", ".mpga", ".weba",
        }
        is_audio_document = bool(message.document) and (
            mime_type.startswith("audio/") or extension in allowed_audio_extensions
        )
        if message.document and not is_audio_document:
            await message.reply_text(
                "⚠️ El archivo no parece ser un audio compatible. Envía MP3, M4A, AAC, OGG, OPUS, WAV o FLAC."
            )
            return
        if message.audio and mime_type and not mime_type.startswith("audio/") and extension not in allowed_audio_extensions:
            await message.reply_text(
                "⚠️ El formato de audio no es compatible. Envía MP3, M4A, AAC, OGG, OPUS, WAV o FLAC."
            )
            return

        media_type = "document" if message.document else "audio"
        user = update.effective_user
        title = (
            (getattr(media, "title", None) or "").strip()
            or (os.path.splitext(file_name)[0] if file_name else "")
            or "Canción enviada"
        )[:120]
        performer = (getattr(media, "performer", None) or "").strip()[:120]
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
            columns = {row[1] for row in db.execute("PRAGMA table_info(digital_music)")}
            if "media_type" not in columns:
                db.execute("ALTER TABLE digital_music ADD COLUMN media_type TEXT NOT NULL DEFAULT 'audio'")
            if "file_name" not in columns:
                db.execute("ALTER TABLE digital_music ADD COLUMN file_name TEXT NOT NULL DEFAULT ''")
            cursor = db.execute(
                """INSERT INTO digital_music
                   (file_id, title, performer, submitted_by, submitter_name, status, media_type, file_name)
                   VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?)""",
                (media.file_id, title, performer, user.id, user.full_name[:120], media_type, file_name),
            )
            song_id = cursor.lastrowid
        admin_caption = (
            "🎵 NUEVA CANCIÓN PARA REVISAR | UNARED\n\n"
            f"🎼 Título: {title}\n"
            f"🎤 Artista: {performer or 'No indicado'}\n"
            f"📁 Archivo: {file_name or extension or 'Audio'}\n"
            f"👤 Enviada por: {user.full_name}\n"
            f"🆔 Telegram ID: {user.id}\n"
            "🟡 Estado: pendiente de aprobación.\n"
            "Confirma que tienes autorización para compartir esta grabación."
        )
        try:
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Aprobar", callback_data=f"music_approve_{song_id}")],
                [InlineKeyboardButton("❌ Rechazar", callback_data=f"music_reject_{song_id}")],
            ])
            if media_type == "document":
                await context.bot.send_document(
                    chat_id=int(ADMIN_CHAT_ID),
                    document=media.file_id,
                    filename=file_name or None,
                    caption=admin_caption,
                    reply_markup=buttons,
                )
            else:
                await context.bot.send_audio(
                    chat_id=int(ADMIN_CHAT_ID),
                    audio=media.file_id,
                    title=title,
                    performer=performer or None,
                    caption=admin_caption,
                    reply_markup=buttons,
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
            await context.application.bot_data["admin_bot"].send_message(chat_id=int(BOT_OWNER_ID), text=admin_message)
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
            await context.application.bot_data["admin_bot"].send_message(chat_id=int(BOT_OWNER_ID), text=admin_message)
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
            reply_markup=main_menu(update.effective_user),
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
        await context.application.bot_data["admin_bot"].send_message(
            chat_id=int(BOT_OWNER_ID),
            text=message,
        )

        context.user_data.clear()

        await update.message.reply_text(
            "✅ ¡Solicitud enviada correctamente!\n\n"
            "Nuestro equipo de UnaRed recibió tu mensaje.\n"
            "Gracias por confiar en nosotros. 💚",
            reply_markup=main_menu(update.effective_user),
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
        reply_markup=main_menu(update.effective_user),
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
                    "SELECT telegram_id, amount, username, status FROM pyp_invoices WHERE invoice_id = ?",
                    (invoice_id,),
                ).fetchone()
                invoice_type = "pyp"
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
            if not row:
                row = db.execute(
                    "SELECT telegram_id, amount, status FROM ssn_assistance_invoices WHERE invoice_id = ?",
                    (invoice_id,),
                ).fetchone()
                invoice_type = "ssn_assistance"
    except sqlite3.Error:
        logger.exception("Could not read WolvPay invoice record.")
        return web.Response(status=500, text="Database error.")

    if not row:
        logger.warning("Received WolvPay event for unknown invoice %s", invoice_id)
        return web.Response(status=200, text="Unknown invoice ignored.")

    if invoice_type == "ssn_assistance":
        telegram_id, expected_amount, current_status = row
        customer_description = "Tu pago de US$3.20 para orientación de recuperación de tu propio SSN fue confirmado automáticamente."
        order_detail = "Servicio: orientación para utilizar los canales oficiales de la SSA."
        admin_detail = "Servicio: asistencia SSN propia\nImporte confirmado: US$3.20"
    elif invoice_type == "dayler":
        telegram_id, expected_amount, username, current_status = row
        customer_description = "Tu pago de US$150 para la solicitud Dayler fue confirmado automáticamente."
        order_detail = f"Usuario SIP solicitado: {username}"
        admin_detail = f"Usuario SIP solicitado: {username}\nImporte confirmado: US$150"
    elif invoice_type == "pyp":
        telegram_id, expected_amount, username, current_status = row
        customer_description = "Tu pago de US$100 mediante Método PyP fue confirmado automáticamente."
        order_detail = "Servicio: Método PyP"
        admin_detail = "Servicio: Método PyP\nImporte confirmado: US$100\nCliente: @" + (username or "sin_username")
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
        admin_detail = "Servicio: Editar y Subir Papel\nImporte confirmado: US$" + str(expected_amount)
    elif invoice_type == "demo":
        telegram_id, expected_amount, product, username, current_status = row
        product_labels = {"otp": "BOT OTP", "ssn": "BOT SSN", "check": "BOT CHECK", "template": "LICENCIA"}
        product_label = product_labels.get(product, "DEMO SANDBOX")
        customer_description = "Tu pago de US$35 para la demostración sandbox fue confirmado automáticamente."
        order_detail = f"Producto: {product_label} (datos sintéticos únicamente)"
        admin_detail = f"Producto: {product_label}\nCliente: @{username or 'sin_username'}\nImporte confirmado: US$" + str(expected_amount)
    else:
        telegram_id, expected_amount, category, username, current_status = row
        customer_description = "Tu pago de servicios fue confirmado automáticamente."
        order_detail = f"Servicio solicitado: {category}"
        admin_detail = f"Servicio: {category}\nCliente: @{username or 'sin_username'}\nImporte confirmado: US$" + str(expected_amount)
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
            table_name = {"dayler": "dayler_invoices", "pyp": "pyp_invoices", "pages": "pages_invoices", "icloud": "icloud_invoices", "demo": "demo_bot_invoices", "bill": "bill_invoices", "edit_upload": "edit_upload_invoices", "ssn_assistance": "ssn_assistance_invoices"}[invoice_type]
            db.execute(
                f"UPDATE {table_name} SET status = 'PAID' WHERE invoice_id = ? AND status = 'PENDING'",
                (invoice_id,),
            )
            if invoice_type == "ssn_assistance":
                db.execute(
                    "UPDATE ssn_assistance_invoices SET request_status='PAID' WHERE invoice_id=? AND request_status='WAITING_PAYMENT'",
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
                    admin_sent INTEGER NOT NULL DEFAULT 0,
                    approval_status TEXT NOT NULL DEFAULT 'PENDING',
                    image_status TEXT NOT NULL DEFAULT 'PENDING'
                )"""
            )
            notification_columns = {row[1] for row in db.execute("PRAGMA table_info(wolvpay_notifications)")}
            if "approval_status" not in notification_columns:
                db.execute("ALTER TABLE wolvpay_notifications ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'PENDING'")
            if "image_status" not in notification_columns:
                db.execute("ALTER TABLE wolvpay_notifications ADD COLUMN image_status TEXT NOT NULL DEFAULT 'PENDING'")
            # Las facturas notificadas por la versión anterior ya recibieron la imagen;
            # se marcan como enviadas para impedir que una actualización las duplique.
            db.execute(
                """UPDATE wolvpay_notifications
                   SET approval_status='APPROVED', image_status='SENT'
                   WHERE customer_sent=1 AND image_status='PENDING'"""
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
    payment_image_url = "https://i.ibb.co/ccmC4XsG/86-DE6634-72-C2-4544-9-DB5-351541-A91286.png"
    customer_text = (
        "✅ PAGO REALIZADO | UNARED\n\n"
        f"{customer_description}\n{order_detail}\n"
        f"Factura: {invoice_id}\n\n"
        ("Tu solicitud está en cola. Puedes consultar el estado desde el botón «Ver estado»." if invoice_type == "ssn_assistance" else "El equipo de UnaRed continuará con la preparación de tu servicio.")
    )
    admin_text = (
        "💚 PAGO " + ({"dayler": "DAYLER", "pyp": "MÉTODO PyP", "pages": "PÁGINAS WEB", "icloud": "ICLOUD", "demo": "DEMO SANDBOX", "bill": "PAGO DE SERVICIOS", "edit_upload": "EDITAR Y SUBIR PAPEL", "ssn_assistance": "ASISTENCIA SSN"}[invoice_type]) + " CONFIRMADO | UNARED\n\n"
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
            admin_bot = application.bot_data["admin_bot"]
            if invoice_type == "ssn_assistance":
                review_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⌛️ Marcar en proceso", callback_data=f"ssn_process:{invoice_id}")],
                    [InlineKeyboardButton("✅ Completar solicitud", callback_data=f"ssn_complete:{invoice_id}")],
                ])
            else:
                review_keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ Aceptar", callback_data=f"admin_wolvpay_accept:{invoice_id}"),
                    InlineKeyboardButton("❌ Rechazar", callback_data=f"admin_wolvpay_reject:{invoice_id}"),
                ]])
            await admin_bot.send_photo(
                chat_id=int(BOT_OWNER_ID),
                photo=payment_image_url,
                caption=admin_text,
                reply_markup=review_keyboard,
            )
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

def build_main_application():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", publish_group_menu))
    app.add_handler(MessageHandler(filters.Regex(r"^Menu$"), open_private_menu_from_group))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("panel", admin_panel))
    app.add_handler(CommandHandler("stats", admin_stats))
    # /buscarcliente está disponible exclusivamente en el bot de administración.
    # Solo los callbacks administrativos pasan por el control de acceso del panel.
    # Los botones de servicios y precios siguen llegando a select_option.
    app.add_handler(CallbackQueryHandler(admin_bot_callbacks, pattern=r"^(admin_|av:|ap:|ssn_process:|ssn_complete:|copy_id:|notify_customer:)"))
    app.add_handler(CallbackQueryHandler(select_option))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members))
    app.add_handler(TypeHandler(Update, channel_music_ingest), group=-1)
    app.add_handler(MessageHandler(
        (filters.TEXT & ~filters.COMMAND) | filters.PHOTO | filters.AUDIO | filters.Document.ALL,
        receive_request,
    ))
    app.add_error_handler(error_handler)
    return app


async def main():
    if not TOKEN:
        raise RuntimeError("Falta configurar TELEGRAM_BOT_TOKEN en Railway.")
    if not ADMIN_CHAT_ID:
        raise RuntimeError("Falta configurar ADMIN_CHAT_ID en Railway.")

    app = build_main_application()
    # Permite que /buscarcliente envíe alertas aunque se ejecute desde el bot principal.
    app.bot_data["main_bot"] = app.bot
    admin_app = None
    applications = [app]
    if ADMIN_BOT_TOKEN:
        admin_app = build_admin_application()
        app.bot_data["admin_bot"] = admin_app.bot
        admin_app.bot_data["main_bot"] = app.bot
        applications.append(admin_app)
    else:
        logger.warning("ADMIN_BOT_TOKEN no configurado; solo se iniciará el bot principal.")

    initialized = []
    started = []
    polling = []
    try:
        for current in applications:
            await current.initialize()
            initialized.append(current)

        await start_webhook_server(app)
        for current in applications:
            await current.start()
            started.append(current)

        # Ambos bots comparten el mismo event loop; no se usan hilos ni señales del sistema.
        for current in applications:
            await current.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            polling.append(current)

        print("💚 UnaRed Bot está funcionando.")
        if admin_app:
            logger.info("💚 UnaRed Admin Bot está funcionando.")
        await asyncio.Event().wait()
    finally:
        for current in reversed(polling):
            await current.updater.stop()
        for current in reversed(started):
            await current.stop()
        await stop_webhook_server(app)
        for current in reversed(initialized):
            await current.shutdown()


if __name__ == "__main__":
    asyncio.run(main())