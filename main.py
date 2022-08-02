from sys import platform
from os import getenv, path
from subprocess import run
from logging import basicConfig, getLogger, INFO
from telebot import TeleBot, types
from dotenv import load_dotenv
load_dotenv()
token = getenv("TELEGRAM_BOT_ID")
chat_id = int(getenv("TELEGRAM_CHAT_ID"))

# Logs
basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=INFO)
logger = getLogger(__name__)

# Platform
repo = None
if platform == 'linux':
    run('cd / && ./media/refresh.sh', shell=True)
    repo = '/media/usb/'
else:
    repo = './test/'

# Bot
bot = TeleBot(token)
bot.delete_my_commands(scope=None, language_code=None)
bot.set_my_commands(
    commands=[types.BotCommand("alive", "Check if the bot is running")],
)
logger.info("Telegram bot initialized")


@bot.message_handler(commands=['alive'])
def alive(message):
    if message.chat.id == chat_id:
        bot.send_message(chat_id, "Bot running...")
        logger.info("/alive")


@bot.message_handler(func=lambda message: message.document.mime_type == 'application/x-bittorrent', content_types=['document'])
def upload(message):
    if message.chat.id == chat_id:
        file_info = bot.get_file(message.document.file_id)
        file = bot.download_file(file_info.file_path)
        if not path.exists(repo):
            logger.info(f"Missing directory: '{repo}'")
        else:
            with open(repo + message.document.file_name, 'wb') as f:
                f.write(file)
            bot.send_message(
                chat_id, "Torrent uploaded.\nStart downloading...")
            logger.info(f"Uploaded: '{message.document.file_name}'")


bot.infinity_polling(skip_pending=True)
