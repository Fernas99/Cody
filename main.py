import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import TOKEN, ADMIN_IDS, OWNER_ID
from license_manager import LicenseManager
import asyncio
from aiogram.utils import exceptions as aiogram_exceptions
from telethon import TelegramClient, events
import sqlite3
from aiogram.dispatcher.filters import Command
import os
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram import Bot, Dispatcher, types
from aiogram.utils import exceptions
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from generate import SessionGenerator
from telethon import events, Button
import json
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

conn = sqlite3.connect('channels.db')
cursor = conn.cursor()

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
logging.basicConfig(level=logging.DEBUG)
license_manager = LicenseManager()
forwarding_active = True
# Telethon client setup (replace with your own API ID and hash)
api_id = 26987711
api_hash = '45bdd610a83032342bc504afb183fcd9'
client = TelegramClient('session', api_id, api_hash)
API_ID = "26987711"
API_HASH = "45bdd610a83032342bc504afb183fcd9"



LANGUAGES = {
    "en": "🇬🇧 English",
    "it": "🇮🇹 Italian",
    "es": "🇪🇸 Spanish",
    "fr": "🇫🇷 French",
    "de": "🇩🇪 German"
}
TRANSLATION_ENABLED = True  # Default to enabled

client = None

async def initialize_client():
    global client
    logging.info("Inizializzazione del client Telethon...")
    conn = sqlite3.connect('voip_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT string_session FROM voip_sessions LIMIT 1')
    session_data = cursor.fetchone()
    conn.close()

    if session_data:
        string_session = session_data[0]
        logging.info("Sessione Telethon trovata, avvio del client...")
        try:
            client = TelegramClient(StringSession(string_session), API_ID, API_HASH)
            await client.start()
            logging.info("Client Telethon avviato con successo")
            return True
        except Exception as e:
            logging.error(f"Errore nell'avvio del client Telethon: {e}")
    else:
        logging.warning("Nessuna sessione Telethon trovata nel database")
    return False





def get_translation_state():
    return get_setting('translation_enabled', 'True') == 'True'

def set_translation_state(state):
    save_setting('translation_enabled', str(state))

def get_current_language():
    return get_setting('current_language', 'en')

def set_current_language(lang_code):
    save_setting('current_language', lang_code)

async def on_shutdown(dp):
    # Close the bot session
    await dp.storage.close()
    await dp.storage.wait_closed()

class AddSessionState(StatesGroup):
    phone_number = State()
    code = State()
    password = State()
    two_factor = State()

def init_db():
    conn = sqlite3.connect('voip_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voip_sessions
        (phone_number TEXT PRIMARY KEY, string_session TEXT)
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings
        (key TEXT PRIMARY KEY, value TEXT)
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels
        (id INTEGER PRIMARY KEY, name TEXT, chat_id INTEGER, type TEXT)
    ''')
    conn.commit()
    conn.close()

def init_channels_db():
    conn = sqlite3.connect('channels.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels
        (id INTEGER PRIMARY KEY, name TEXT, chat_id INTEGER, type TEXT)
    ''')
    conn.commit()
    conn.close()


def get_input_channel_count():
    conn = sqlite3.connect('channels.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM channels WHERE type='input'")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def save_setting(key, value):
    conn = sqlite3.connect('voip_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = sqlite3.connect('voip_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else default

def save_voip_session(phone_number, string_session):
    conn = sqlite3.connect('voip_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO voip_sessions (phone_number, string_session)
        VALUES (?, ?)
    ''', (phone_number, string_session))
    conn.commit()
    conn.close()

data_stasher = {}

async def display_voip_sessions(message: types.Message):
    conn = sqlite3.connect('voip_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT phone_number FROM voip_sessions')
    sessions = cursor.fetchall()
    conn.close()

    keyboard = InlineKeyboardMarkup(row_width=1)
    for session in sessions:
        keyboard.add(InlineKeyboardButton(f"Remove {session[0]}", callback_data=f"remove_voip_{session[0]}"))
    keyboard.add(InlineKeyboardButton("🔙 Back", callback_data="voip_panel"))

    await message.answer("Select a VoIP session to remove:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "remove_session")
async def remove_session_handler(callback_query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(row_width=1)
    conn = sqlite3.connect('voip_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT phone_number FROM voip_sessions')
    sessions = cursor.fetchall()
    conn.close()

    for session in sessions:
        keyboard.add(InlineKeyboardButton(f"Remove {session[0]}", callback_data=f"remove_voip_{session[0]}"))
    keyboard.add(InlineKeyboardButton("🔙 Back", callback_data="voip_panel"))

    image_path = 'admin_panel.png'
    if os.path.exists(image_path):
        with open(image_path, 'rb') as photo:
            await callback_query.message.edit_media(
                media=types.InputMediaPhoto(photo, caption="Select a VoIP session to remove:"),
                reply_markup=keyboard
            )
    else:
        await callback_query.message.edit_text("Select a VoIP session to remove:", reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith("remove_voip_"))
async def remove_voip_session(callback_query: types.CallbackQuery):
    phone_number = callback_query.data.split("_")[2]
    conn = sqlite3.connect('voip_database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM voip_sessions WHERE phone_number = ?', (phone_number,))
    conn.commit()

    # Fetch remaining sessions
    cursor.execute('SELECT phone_number FROM voip_sessions')
    sessions = cursor.fetchall()
    conn.close()

    keyboard = InlineKeyboardMarkup(row_width=1)
    for session in sessions:
        keyboard.add(InlineKeyboardButton(f"Remove {session[0]}", callback_data=f"remove_voip_{session[0]}"))
    keyboard.add(InlineKeyboardButton("🔙 Back", callback_data="voip_panel"))

    # Update the existing message
    await callback_query.message.edit_caption(
        caption=f"VoIP session {phone_number} removed successfully!\nSelect another VoIP session to remove:",
        reply_markup=keyboard
    )

    await callback_query.answer()


@dp.message_handler(state=AddSessionState.phone_number)
async def process_phone_number(message: types.Message, state: FSMContext):
    phone_number = message.text
    await state.update_data(phone_number=phone_number)

    session_generator = SessionGenerator(int(API_ID), API_HASH, phone_number)
    await session_generator.begin()

    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_add_session"))

    image_path = 'admin_panel.png'
    with open(image_path, 'rb') as photo:
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=photo,
            caption="A code has been sent to your phone. Please enter it:",
            reply_markup=keyboard
        )

    data_stasher[message.chat.id] = {"class": session_generator, "num": phone_number}

    await AddSessionState.code.set()


MAX_RETRIES = 3


@dp.message_handler(state=AddSessionState.code)
async def process_code(message: types.Message, state: FSMContext):
    code = message.text

    if message.chat.id not in data_stasher:
        return await message.reply("Unknown error")

    phone_number = data_stasher[message.chat.id]["num"]
    session_generator = data_stasher[message.chat.id]["class"]

    logging.debug(f"Phone number: {phone_number}")
    logging.debug(f"Code provided by user: {code}")

    result = await session_generator.auth(code)
    logging.debug(f"Authentication result: {result}")

    if result != True:
        if "Two-steps verification is enabled" in str(result):
            await message.reply("Two-factor authentication is required. Please enter your 2FA password:")
            await AddSessionState.two_factor.set()
            data_stasher[message.chat.id]["code"] = code
        else:
            await message.reply(f"Authentication failed: {result}")
            await message.reply("Please try again.")
            await state.finish()
        return

    string_session = await session_generator.string_session()
    await session_generator.disconnect()

    save_voip_session(phone_number, string_session)

    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back to VOIP Panel", callback_data="voip_panel"))

    image_path = 'admin_panel.png'
    with open(image_path, 'rb') as photo:
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=photo,
            caption="Session added successfully!",
            reply_markup=keyboard
        )

    await state.finish()


async def authenticate_with_2fa(self, phone, code, password):
    try:
        # First, try to sign in with the phone number and code
        await self.client.sign_in(phone, code)
        return True, None
    except PhoneCodeInvalidError:
        return False, "Invalid code. Please try again."
    except PhoneCodeExpiredError:
        return False, "Code expired. Please request a new code."
    except SessionPasswordNeededError:
        try:
            # If 2FA is required, attempt to sign in with the password
            await self.client.sign_in(password=password)
            return True, None
        except PasswordHashInvalidError:
            return False, "Invalid 2FA password. Please check and try again."
    except FloodWaitError as e:
        return False, f"Too many attempts. Please wait for {e.seconds} seconds before trying again."
    except Exception as e:
        return False, f"An unexpected error occurred: {str(e)}"


@dp.message_handler(state=AddSessionState.two_factor)
async def process_two_factor(message: types.Message, state: FSMContext):
    two_factor_code = message.text

    if message.chat.id not in data_stasher:
        return await message.reply("Unknown error")

    session_generator = data_stasher[message.chat.id]["class"]
    phone_number = data_stasher[message.chat.id]["num"]
    code = data_stasher[message.chat.id]["code"]

    print(session_generator, phone_number, code, two_factor_code)

    try:
        result = await session_generator.auth(code=data_stasher[message.chat.id]["code"], password=two_factor_code)

        if result:
            string_session = await session_generator.string_session()
            await session_generator.disconnect()

            save_voip_session(data_stasher[message.chat.id]["num"], string_session)

            keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back to VOIP Panel", callback_data="voip_panel"))

            image_path = 'admin_panel.png'
            with open(image_path, 'rb') as photo:
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=photo,
                    caption="Session added successfully!",
                    reply_markup=keyboard
                )
            await state.finish()
        else:
            await message.reply("Authentication failed. Please check your 2FA password and try again.")
            # Optionally, you can implement a retry mechanism here
    except Exception as e:
        await message.reply(f"An error occurred during 2FA authentication: {str(e)}")
        await state.finish()

@dp.callback_query_handler(lambda c: c.data == "add_session")
async def add_session(callback_query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_add_session"))

    image_path = 'admin_panel.png'
    with open(image_path, 'rb') as photo:
        await bot.edit_message_media(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            media=types.InputMediaPhoto(photo,
                                        caption="Please enter your phone number in international format (e.g., +1234567890):"),
            reply_markup=keyboard
        )

    await AddSessionState.phone_number.set()



@dp.callback_query_handler(lambda c: c.data == "cancel_add_session", state="*")
async def cancel_add_session(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)
    await voip_panel(callback_query.message)

@dp.message_handler(Command("license"), lambda message: message.chat.type == 'private' and message.from_user.id in ADMIN_IDS)
async def show_license_admin(message: types.Message):
    logging.debug(f"License command received from admin {message.from_user.id}")
    remaining_time = license_manager.get_remaining_time()
    await message.reply(f"🔑 License status: {remaining_time}")

@dp.message_handler(Command("licenza"), lambda message: message.chat.type == 'private')
async def show_license_owner(message: types.Message):
    logging.info(f"Licenza command received from user {message.from_user.id}")

    if message.from_user.id != OWNER_ID:
        logging.warning(f"Unauthorized access attempt by user {message.from_user.id}")
        await message.reply("Only the owner can use this command.")
        return

    logging.info("User is the owner, proceeding with license check")
    remaining_time = license_manager.get_remaining_time()
    logging.info(f"Remaining time: {remaining_time}")

    if remaining_time == "⚠️ No license set":
        response_text = "⚠️ No license set. Select an option to activate the license:"
    else:
        response_text = f"🔑 License status: {remaining_time}\nSelect an option to renew:"

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("1 Week 📅", callback_data="renew_1w"))
    keyboard.add(InlineKeyboardButton("1 Month 📅", callback_data="renew_1m"))
    keyboard.add(InlineKeyboardButton("3 Months 📅", callback_data="renew_3m"))
    keyboard.add(InlineKeyboardButton("6 Months 📅", callback_data="renew_6m"))
    keyboard.add(InlineKeyboardButton("1 Year 📅", callback_data="renew_1y"))
    keyboard.add(InlineKeyboardButton("Revoke License 🚫", callback_data="reset_license"))

    await message.reply(response_text, reply_markup=keyboard)


@dp.errors_handler()
async def error_handler(update: types.Update, exception: Exception):
    logging.error(f"Unhandled exception: {exception}")
    return True

@dp.callback_query_handler(lambda c: c.data.startswith('renew_') or c.data == 'revoke_license')
async def process_license_action(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != OWNER_ID:
        await callback_query.answer("Only the owner can perform this action.", show_alert=True)
        return

    if callback_query.data == 'revoke_license':
        success = license_manager.revoke_license(OWNER_ID)
        if success:
            license_manager.load_license()
            confirmation_message = "✅ License has been successfully revoked."
        else:
            confirmation_message = "❌ Failed to revoke the license. Please try again later."
    else:
        duration = callback_query.data.split('_')[1]
        success = license_manager.renew_license(duration)
        if success:
            duration_text = {
                "1w": "one week",
                "1m": "one month",
                "3m": "three months",
                "6m": "six months",
                "1y": "one year"
            }.get(duration, duration)
            new_expiration = license_manager.get_expiration_date()
            confirmation_message = (
                f"✅ License successfully renewed for {duration_text}.\n"
                f"New expiration date: {new_expiration.strftime('%d/%m/%Y %H:%M:%S')}"
            )
        else:
            confirmation_message = "❌ An error occurred while renewing the license. Please try again later."

    await bot.send_message(callback_query.message.chat.id, confirmation_message)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == 'revoke_license')
async def revoke_license(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != OWNER_ID:
        await callback_query.answer("Only the owner can perform this action.", show_alert=True)
        return

    print(f"Attempting to revoke license for user {OWNER_ID}")
    success = license_manager.revoke_license(1)  # Use 1 as the default ID for the single license
    print(f"Revoke license result: {success}")

    if success:
        license_manager.load_license()
        confirmation_message = "✅ License has been successfully revoked."
    else:
        confirmation_message = "❌ Failed to revoke the license. Please try again later."

    await bot.send_message(callback_query.message.chat.id, confirmation_message)
    await callback_query.answer()

@dp.message_handler(commands=['reset_license'])
async def reset_license(message: types.Message):
    if message.from_user.id != OWNER_ID:
        await message.reply("Only the owner can perform this action.")
        return

    license_manager.force_reset_license()
    await message.reply("✅ License Revoked.")

@dp.callback_query_handler(lambda c: c.data == 'reset_license')
async def reset_license_callback(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != OWNER_ID:
        await callback_query.answer("Only the owner can perform this action.", show_alert=True)
        return

    license_manager.force_reset_license()
    await bot.send_message(callback_query.message.chat.id, "✅ License Revoked.")
    await callback_query.answer()


async def check_expiring_licenses():
    while True:
        expiring_soon = license_manager.get_expiring_licenses(days=1)
        for user_id in expiring_soon:
            try:
                await bot.send_message(user_id, "⚠️ Your license will expire in 1 day. Contact @fernas1999 to renew.")
            except aiogram_exceptions.ChatNotFound:
                print(f"Chat not found for user {user_id}. Removing from database.")
                license_manager.revoke_license(user_id)
            except Exception as e:
                print(f"Error sending message to user {user_id}: {e}")


@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    if user_id in ADMIN_IDS or user_id == OWNER_ID:
        await admin_panel(message)
    else:
        welcome_message = ("🤖 Bot developed by @Fernas1999\n"
                           "📞 Contact me for more information or bot development!")
        await message.reply(welcome_message)


@dp.callback_query_handler(lambda c: c.data == "voip_panel")
async def show_voip_panel(callback_query: types.CallbackQuery):
    # Delete the previous message
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)

    # Call the voip_panel function to show the new panel
    await voip_panel(callback_query.message)

@dp.callback_query_handler(lambda c: c.data == "settings_menu")
async def show_settings_menu(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await settings_menu(callback_query.message)


async def settings_menu(message: types.Message):
    translation_enabled = get_translation_state()
    toggle_text = "✅ Toggle Translation" if translation_enabled else "❌ Toggle Translation"

    current_language = get_current_language()
    language_text = LANGUAGES.get(current_language, "🌐 Select Language")

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(toggle_text, callback_data="toggle_translation"),
        InlineKeyboardButton(language_text, callback_data="select_language")
    )
    keyboard.add(InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel"))

    image_path = 'admin_panel.png'
    with open(image_path, 'rb') as photo:
        await bot.edit_message_media(
            chat_id=message.chat.id,
            message_id=message.message_id,
            media=types.InputMediaPhoto(photo, caption="Settings Menu:"),
            reply_markup=keyboard
        )


@dp.callback_query_handler(lambda c: c.data == "toggle_translation")
async def toggle_translation(callback_query: types.CallbackQuery):
    current_state = get_translation_state()
    new_state = not current_state
    set_translation_state(new_state)

    await bot.answer_callback_query(callback_query.id, text="Translation setting toggled")
    await settings_menu(callback_query.message)


@dp.callback_query_handler(lambda c: c.data == "select_language")
async def select_language(callback_query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(row_width=2)
    for lang_code, lang_name in LANGUAGES.items():
        keyboard.add(InlineKeyboardButton(lang_name, callback_data=f"set_lang_{lang_code}"))
    keyboard.add(InlineKeyboardButton("🔙 Back", callback_data="settings_menu"))

    image_path = 'admin_panel.png'
    with open(image_path, 'rb') as photo:
        await bot.edit_message_media(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            media=types.InputMediaPhoto(photo, caption="Select translation language:"),
            reply_markup=keyboard
        )


@dp.callback_query_handler(lambda c: c.data.startswith("set_lang_"))
async def set_language(callback_query: types.CallbackQuery):
    lang_code = callback_query.data.split("_")[2]
    set_current_language(lang_code)
    await bot.answer_callback_query(callback_query.id, text=f"Language set to {LANGUAGES[lang_code]}")
    await settings_menu(callback_query.message)


@dp.callback_query_handler(lambda c: c.data == "admin_panel")
async def back_to_admin_panel(callback_query: types.CallbackQuery):
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)
    await admin_panel(callback_query.message)


async def voip_panel(message: types.Message):
    global forwarding_active
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Add Voip", callback_data="add_session"),
        InlineKeyboardButton("❌ Remove Voip", callback_data="remove_session"),
        InlineKeyboardButton("🔙 Back To Admin Panel", callback_data="admin_panel"),
    )

    image_path = 'admin_panel.png'
    if os.path.exists(image_path):
        with open(image_path, 'rb') as photo:
            await message.answer_photo(
                photo=photo,
                caption="Welcome to the admin panel. Choose an option:",
                reply_markup=keyboard
            )
    else:
        await message.answer("Welcome to the admin panel. Choose an option:", reply_markup=keyboard)

async def admin_panel(message: types.Message):
    global forwarding_active
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("➕ Add Channel", callback_data="add_channel"),
        InlineKeyboardButton("➖ Remove Channel", callback_data="remove_channel"),
        InlineKeyboardButton("📋 Channel List", callback_data="channel_list"),
        InlineKeyboardButton("🔑 License Info", callback_data="license_info"),
    )

    # Add the button for pausing/resuming forwarding
    forwarding_status = "✅" if forwarding_active and license_manager.is_license_active() else "❌"
    keyboard.add(InlineKeyboardButton(f"Forwarding: {forwarding_status}", callback_data="toggle_forwarding"))
    keyboard.add(
        InlineKeyboardButton("☎️ Manage Voip", callback_data="voip_panel"),
        InlineKeyboardButton("❓ FAQ", callback_data="show_faq"),
        InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu"),
        InlineKeyboardButton("🤖 Bot Info", callback_data="bot_info")
    )
    image_path = 'admin_panel.png'
    if os.path.exists(image_path):
        with open(image_path, 'rb') as photo:
            await message.answer_photo(
                photo=photo,
                caption="Welcome to the admin panel. Choose an option:",
                reply_markup=keyboard
            )
    else:
        await message.answer("Welcome to the admin panel. Choose an option:", reply_markup=keyboard)
@dp.message_handler(Command("admin"))
async def admin_command(message: types.Message):
    logging.info(f"Admin command received from user {message.from_user.id}")
    if message.from_user.id in ADMIN_IDS or message.from_user.id == OWNER_ID:
        logging.info("User is authorized. Opening admin panel.")
        await admin_panel(message)
    else:
        logging.warning(f"Unauthorized access attempt by user {message.from_user.id}")
        await message.reply("You are not authorized to use this command.")


@dp.callback_query_handler(lambda c: c.data == "add_channel")
async def add_channel_step1(callback_query: types.CallbackQuery):
    logging.info("Add channel callback received")
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("Input Channel", callback_data="add_input"),
        InlineKeyboardButton("Output Channel", callback_data="add_output"),
        InlineKeyboardButton("Back", callback_data="back_to_admin")
    )

    if callback_query.message.photo:
        await bot.edit_message_caption(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            caption="Select channel type:",
            reply_markup=keyboard
        )
    else:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text="Select channel type:",
            reply_markup=keyboard
        )


@dp.callback_query_handler(lambda c: c.data in ["add_input", "add_output"])
async def add_channel_step2(callback_query: types.CallbackQuery, state: FSMContext):
    channel_type = "input" if callback_query.data == "add_input" else "output"
    await state.update_data(channel_type=channel_type)
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("Cancel", callback_data="cancel_add_channel"))
    await bot.answer_callback_query(callback_query.id)

    new_text = f"Please forward a message from the {channel_type} channel you want to add."

    if callback_query.message.photo:
        await bot.edit_message_caption(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            caption=new_text,
            reply_markup=keyboard
        )
    else:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=new_text,
            reply_markup=keyboard
        )

    # Store the channel type in user data
    state = dp.current_state(user=callback_query.from_user.id)
    await state.set_data({"channel_type": channel_type})


@dp.callback_query_handler(lambda c: c.data == "cancel_add_channel")
async def cancel_add_channel(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)

    # Delete the current message
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)

    # Call the admin_panel function to show the main menu
    await admin_panel(callback_query.message)

    await dp.current_state(user=callback_query.from_user.id).reset_state()

def add_channel_to_database(channel_id, channel_title):
    # Implement your database logic here
    logging.debug(f"Adding channel to database: {channel_id} - {channel_title}")
    # Your database code here

async def check_bot_permissions(chat_id):
    try:
        chat_member = await bot.get_chat_member(chat_id, bot.id)
        return chat_member.is_chat_admin()
    except Exception as e:
        logging.error(f"Error checking bot permissions: {e}")
        return False


@dp.message_handler(content_types=types.ContentType.ANY, state="*")
async def handle_all_message(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    if user_id in ADMIN_IDS or user_id == OWNER_ID:
        if message.forward_from_chat and message.forward_from_chat.type == 'channel':
            channel_id = message.forward_from_chat.id
            channel_name = message.forward_from_chat.title

            user_data = await state.get_data()
            channel_type = user_data.get('channel_type', 'unknown')

            if channel_type == 'input' and get_input_channel_count() >= 3:
                await message.reply("Error: Maximum limit of 3 input channels reached.")
                await state.finish()
                await admin_panel(message)
                return

            if channel_type == 'output' and get_output_channel_count() >= 10:
                await message.reply("Error: Maximum limit of 10 output channels reached.")
                await state.finish()
                await admin_panel(message)
                return

            if channel_type == 'output':
                try:
                    bot_member = await bot.get_chat_member(channel_id, bot.id)
                    if bot_member.status != 'administrator':
                        raise Exception("Bot is not an admin")
                except Exception:
                    keyboard = InlineKeyboardMarkup().add(
                        InlineKeyboardButton("🔙Back To Main Menu", callback_data="back_to_admin")
                    )
                    await message.reply(
                        "Error: The bot is not an admin in this channel. "
                        "Please add the bot as an admin and try again.",
                        reply_markup=keyboard
                    )
                    return

            cursor.execute("INSERT INTO channels (name, chat_id, type) VALUES (?, ?, ?)",
                           (channel_name, channel_id, channel_type))

            conn.commit()

            await message.reply(f"Channel '{channel_name}' has been added as an {channel_type} channel.")
            await state.finish()
            await admin_panel(message)
        else:
            # Handle other admin messages if needed
            pass
    else:
        # Send the standard message only to normal users
        await message.reply("🤖 Bot developed by @Fernas1999\n"
                            "📞 Contact me for more information or bot development!")

    if forwarding_active and client:
        input_channels = get_input_channels()
        if message.chat.id in input_channels:
            for output_channel in get_output_channels():
                try:
                    await client.forward_messages(output_channel, message.chat.id, message.message_id)
                except Exception as e:
                    logging.error(f"Error forwarding message: {e}")


def get_voip_session():
    conn = sqlite3.connect('voip_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT string_session FROM voip_sessions LIMIT 1')
    session_data = cursor.fetchone()
    conn.close()
    return session_data[0] if session_data else None

@dp.message_handler(content_types=types.ContentTypes.ANY, state="*")
async def add_channel_step3(message: types.Message, state: FSMContext):
    if message.forward_from_chat and message.forward_from_chat.type == 'channel':
        channel_id = message.forward_from_chat.id
        channel_name = message.forward_from_chat.title

        user_data = await state.get_data()
        channel_type = user_data.get('channel_type', 'unknown')

        if channel_type == 'input' and get_input_channel_count() >= 3:
            await message.reply("Error: Maximum limit of 3 input channels reached.")
            await state.finish()
            await admin_panel(message)
            return

        if channel_type == 'output' and get_output_channel_count() >= 10:
            await message.reply("Error: Maximum limit of 10 output channels reached.")
            await state.finish()
            await admin_panel(message)
            return

        if channel_type == 'output':
            try:
                bot_member = await bot.get_chat_member(channel_id, bot.id)
                if bot_member.status != 'administrator':
                    raise Exception("Bot is not an admin")
            except Exception:
                keyboard = InlineKeyboardMarkup().add(
                    InlineKeyboardButton("🔙Back To Main Menu", callback_data="back_to_admin")
                )
                await message.reply(
                    "Error: The bot is not an admin in this channel. "
                    "Please add the bot as an admin and try again.",
                    reply_markup=keyboard
                )
                return

        cursor.execute("INSERT INTO channels (name, channel_id, type) VALUES (?, ?, ?)",
                       (channel_name, channel_id, channel_type))
        conn.commit()

        await message.reply(f"Channel '{channel_name}' has been added as an {channel_type} channel.")
        await state.finish()
        await admin_panel(message)
    else:
        await message.reply("🤖 Bot developed by @Fernas1999\n"
                           "📞 Contact me for more information or bot development!")

async def add_channel_step4(message: types.Message, channel_id):
    channel_name = message.text
    channel_type = "input" if message.text.startswith("add_input") else "output"
    cursor.execute("INSERT INTO channels (name, channel_id, type) VALUES (?, ?, ?)",
                   (channel_name, channel_id, channel_type))
    conn.commit()
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("Back to Admin Panel", callback_data="back_to_admin"))
    await update_message(message, f"Channel '{channel_name}' has been added as an {channel_type} channel.", keyboard)
    dp.message_handlers.unregister(add_channel_step4)


@dp.callback_query_handler(lambda c: c.data == "channel_list")
async def channel_list(callback_query: types.CallbackQuery):
    # Delete the previous menu
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)

    cursor.execute("SELECT name, type FROM channels")
    channels = cursor.fetchall()

    if channels:
        channel_list = "\n".join([f"{channel[0]} ({channel[1]})" for channel in channels])
        message_text = f"Channel List:\n{channel_list}"
    else:
        message_text = "No channels added yet."

    # Create a keyboard with the "Back to Main Menu" button
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_admin"))

    # Send the new message with the channel list and the back button
    await bot.send_message(callback_query.from_user.id, message_text, reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "license_info")
async def show_license_info(callback_query: types.CallbackQuery):
    # Delete the previous menu
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)

    remaining_time = license_manager.get_remaining_time()
    message_text = f"License Info: {remaining_time}"

    # Create a keyboard with the "Back to Main Menu" button
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_admin"))

    # Send the new message with the license info and the back button
    await bot.send_message(callback_query.from_user.id, message_text, reply_markup=keyboard)


async def forward_messages():
    global client, forwarding_active
    logging.info("Funzione di inoltro messaggi avviata")
    while True:
        if forwarding_active and client:
            logging.info("Inoltro messaggi attivo, controllo nuovi messaggi...")
            input_channels = get_input_channels()
            for channel in input_channels:
                try:
                    async for message in client.iter_messages(channel, limit=5):
                        for output_channel in get_output_channels():
                            try:
                                await client.forward_messages(output_channel, message)
                                logging.info(f"Messaggio inoltrato da {channel} a {output_channel}")
                            except Exception as e:
                                logging.error(f"Errore nell'inoltro del messaggio: {e}")
                except Exception as e:
                    logging.error(f"Errore nel recupero dei messaggi dal canale {channel}: {e}")
        else:
            logging.info("Inoltro messaggi non attivo o client non inizializzato")
        await asyncio.sleep(10)  # Controlla ogni 10 secondi


def get_input_channels():
    cursor.execute("SELECT chat_id FROM channels WHERE type='input'")
    return [row[0] for row in cursor.fetchall()]

def get_output_channels():
    cursor.execute("SELECT chat_id FROM channels WHERE type='output'")
    return [row[0] for row in cursor.fetchall()]

@dp.callback_query_handler(lambda c: c.data == "remove_channel" or c.data.startswith("remove_channel_page_"))
async def remove_channel_step1(callback_query: types.CallbackQuery):
    page = int(callback_query.data.split("_")[-1]) if callback_query.data.startswith("remove_channel_page_") else 1
    channels = get_all_channels()
    channels_per_page = 10
    start_index = (page - 1) * channels_per_page
    end_index = start_index + channels_per_page
    current_page_channels = channels[start_index:end_index]

    keyboard = InlineKeyboardMarkup(row_width=1)
    for channel in current_page_channels:
        keyboard.add(InlineKeyboardButton(f"{channel[1]} ({channel[3]})", callback_data=f"remove_{channel[0]}"))

    # Add navigation buttons
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"remove_channel_page_{page-1}"))
    if end_index < len(channels):
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"remove_channel_page_{page+1}"))
    if nav_buttons:
        keyboard.row(*nav_buttons)

    # Add back button
    keyboard.add(InlineKeyboardButton("🔙 Back", callback_data="back_to_admin"))

    message_text = f"Select a channel to remove (Page {page}/{(len(channels)-1)//channels_per_page + 1}):"

    if callback_query.message.photo:
        await bot.edit_message_caption(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            caption=message_text,
            reply_markup=keyboard
        )
    else:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=message_text,
            reply_markup=keyboard
        )

@dp.callback_query_handler(lambda c: c.data.startswith("remove_"))
async def remove_channel_step2(callback_query: types.CallbackQuery):
    try:
        channel_id = int(callback_query.data.split("_")[1])
        cursor.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
        conn.commit()

        # Delete the previous message
        await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)

        # Show the main menu
        await admin_panel(callback_query.message)

        await bot.answer_callback_query(callback_query.id, "Channel removed successfully!")
    except (ValueError, IndexError):
        await bot.answer_callback_query(callback_query.id, "Invalid channel selection. Please try again.")
    except Exception as e:
        await bot.answer_callback_query(callback_query.id, "An error occurred. Please try again.")
        logging.error(f"Error in remove_channel_step2: {str(e)}")

@dp.message_handler(Command("pause"), lambda message: message.chat.type == 'private' and message.from_user.id in ADMIN_IDS)
async def pause_forwarding(message: types.Message):
    global forwarding_active
    forwarding_active = False
    await message.reply("Message forwarding has been paused.")

@dp.message_handler(Command("resume"), lambda message: message.chat.type == 'private' and message.from_user.id in ADMIN_IDS)
async def resume_forwarding(message: types.Message):
    global forwarding_active
    forwarding_active = True
    await message.reply("Message forwarding has been resumed.")


async def update_channel_list():
    while True:
        cursor.execute("SELECT name, chat_id, type FROM channels")
        channels = cursor.fetchall()
        input_channels = [channel[0] for channel in channels if channel[1] == 'input']
        output_channels = [channel[0] for channel in channels if channel[1] == 'output']
        await asyncio.sleep(300)  # Update every 5 minutes

def get_all_channels():
    cursor.execute("SELECT id, name, chat_id, type FROM channels")
    return cursor.fetchall()

async def update_message(message: types.Message, new_text: str, new_reply_markup: InlineKeyboardMarkup = None):
    try:
        if message.photo:
            await bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=message.message_id,
                caption=new_text,
                reply_markup=new_reply_markup
            )
        else:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id,
                text=new_text,
                reply_markup=new_reply_markup
            )
    except aiogram_exceptions.MessageNotModified:
        pass
    except aiogram_exceptions.MessageToEditNotFound:
        await message.delete()
        await bot.send_message(message.chat.id, new_text, reply_markup=new_reply_markup)


@dp.callback_query_handler(lambda c: c.data.startswith("back_to_"))
async def handle_back_button(callback_query: types.CallbackQuery):
    if callback_query.data == "back_to_admin":
        # Delete the current message
        await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)
        # Create a new admin panel message
        await admin_panel(callback_query.message)
    elif callback_query.data == "back_to_add_channel":
        # Delete the current message
        await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)
        # Create a new add channel menu
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("Input Channel", callback_data="add_input"),
            InlineKeyboardButton("Output Channel", callback_data="add_output"),
            InlineKeyboardButton("Back", callback_data="back_to_admin")
        )
        await bot.send_message(callback_query.message.chat.id, "Select channel type:", reply_markup=keyboard)

@dp.errors_handler()
async def error_handler(update: types.Update, exception: Exception):
    logging.error(f"Unhandled exception: {exception}", exc_info=True)
    return True

from aiogram.utils import exceptions

@dp.callback_query_handler(lambda c: c.data == "toggle_forwarding")
async def toggle_forwarding(callback_query: types.CallbackQuery):
    global forwarding_active
    if not license_manager.is_license_active():
        await bot.answer_callback_query(callback_query.id, "Error: Cannot activate forwarding. License is not active.", show_alert=True)
    else:
        forwarding_active = not forwarding_active
        status = "resumed" if forwarding_active else "paused"
        await bot.answer_callback_query(callback_query.id, f"Message forwarding has been {status}.")

    # Update the existing menu
    keyboard = callback_query.message.reply_markup
    for row in keyboard.inline_keyboard:
        for button in row:
            if button.callback_data == "toggle_forwarding":
                forwarding_status = "✅" if forwarding_active and license_manager.is_license_active() else "❌"
                button.text = f"📡 Forwarding: {forwarding_status}"
                break

    try:
        if callback_query.message.caption:
            await bot.edit_message_caption(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                caption=callback_query.message.caption,
                reply_markup=keyboard
            )
        else:
            await bot.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                text=callback_query.message.text,
                reply_markup=keyboard
            )
    except exceptions.MessageNotModified:
        pass  # Message is not modified, no need to take action
    except exceptions.TelegramAPIError as e:
        logging.error(f"Telegram API Error in toggle_forwarding: {e}")


@dp.callback_query_handler(lambda c: c.data == "bot_info")
async def show_bot_info(callback_query: types.CallbackQuery):
    # Delete the previous menu
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)

    bot_info_text = (
        "🤖 Forwarding Bot (Only Telegram Version)\n"
        "📊 Version: 1.0\n"
        "👨‍💻 Dev: @Fernas1999"
    )

    # Create a keyboard with the "Back to Main Menu" button
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_admin"))

    # Send the new message with the bot info and the back button
    await bot.send_message(callback_query.from_user.id, bot_info_text, reply_markup=keyboard)

def get_input_channel_count():
    cursor.execute("SELECT COUNT(*) FROM channels WHERE type='input'")
    return cursor.fetchone()[0]


def get_output_channel_count():
    cursor.execute("SELECT COUNT(*) FROM channels WHERE type='output'")
    return cursor.fetchone()[0]


@dp.callback_query_handler(lambda c: c.data == "show_faq")
async def show_faq(callback_query: types.CallbackQuery):
    faq_text = (
        "📚 Frequently Asked Questions\n\n"
        "1. How do I add a channel?\n"
        "   Use the 'Add Channel' button and follow the prompts.\n\n"
        "2. What's the difference between input and output channels?\n"
        "   Input channels are sources, output channels receive forwarded messages.\n\n"
        "3. How many channels can I add?\n"
        "   You can add up to 3 input channels and 10 output channels.\n\n"
        "4. How do I pause message forwarding?\n"
        "   Use the 'Forwarding' toggle in the admin panel.\n\n"
        "5. What should I do if the bot isn't working?\n"
        "   Ensure the bot is an admin in all output channels.\n\n"
        "6. How do I check my license status?\n"
        "   Use the 'License Info' button in the admin panel.\n\n"
        "7. Can I customize the forwarding behavior?\n"
        "   Currently, all messages are forwarded as-is.\n\n"
        "8. How do I get support?\n"
        "   Contact @Fernas1999 for assistance.\n\n"
        "9. Is there a way to filter messages?\n"
        "   Not at the moment, but it's a planned feature.\n\n"
        "10. How secure is my data?\n"
        "    We prioritize security and don't store message content."
    )

    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_admin")
    )

    if callback_query.message.photo:
        # If the message has a photo, edit the caption
        await bot.edit_message_caption(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            caption=faq_text,
            reply_markup=keyboard
        )
    else:
        # If it's a text message, edit the text
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=faq_text,
            reply_markup=keyboard
        )

def is_license_active(self):
    if not self.expiration_date:
        return False
    return datetime.now() < self.expiration_date

async def check_license_status():
    while True:
        if not license_manager.is_license_active():
            global forwarding_active
            forwarding_active = False
            logging.warning("License inactive. Forwarding has been paused.")
        await asyncio.sleep(3600)  # Check every hour

async def check_telethon_status():
    global client
    while True:
        if client and not client.is_connected():
            logging.warning("Client Telethon disconnesso, tentativo di riconnessione...")
            try:
                await client.connect()
                logging.info("Client Telethon riconnesso con successo")
            except Exception as e:
                logging.error(f"Errore nella riconnessione del client Telethon: {e}")
        await asyncio.sleep(60)  # Controlla ogni minuto


async def main():
    logging.info("Avvio del bot...")
    client_initialized = await initialize_client()
    if client_initialized:
        logging.info("Client Telethon inizializzato, avvio dell'inoltro messaggi...")
        asyncio.create_task(forward_messages())
        asyncio.create_task(check_telethon_status())
    else:
        logging.warning("Client Telethon non inizializzato, l'inoltro dei messaggi non sarà attivo")

    await on_startup(dp)
    await set_commands(bot)
    await dp.start_polling()
    await dp.idle()


if __name__ == '__main__':
    logging.info("Bot starting...")
    init_db()
    init_channels_db()
    executor.start_polling(dp, skip_updates=True)
    loop = asyncio.get_event_loop()
    try:
        client.start()
        client.loop.create_task(forward_messages())
        client.loop.create_task(update_channel_list())
        client.loop.create_task(check_license_status())
        logging.info("Starting polling...")
        loop.run_until_complete(init_db())
        executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown, skip_updates=True, loop=loop)
    except Exception as e:
        logging.error(f"Error starting the bot: {e}")
    finally:
        loop.run_until_complete(dp.storage.close())
        loop.run_until_complete(dp.storage.wait_closed())
        loop.close()
        conn.close()



