from os import getenv, path, uname
from subprocess import run
from time import time as now, sleep
from datetime import datetime as dt
from logging import basicConfig, getLogger, INFO, DEBUG
from telebot import TeleBot, types
from qbittorrent import Client
from dotenv import load_dotenv
load_dotenv()

# .env
token = getenv("TELEGRAM_BOT_ID")
chat_id = int(getenv("TELEGRAM_CHAT_ID"))
dir_prod = getenv("DIR_PROD")
dir_test = getenv("DIR_TEST")
qb_addr = getenv("QB_ADDR")
qb_user = getenv("QB_USER")
qb_pass = getenv("QB_PASS")

# Platform
repo = dir_test
is_rpi = uname().machine == 'aarch64'
if is_rpi:
    run('cd / && ./media/refresh.sh', shell=True)
    repo = dir_prod

# Logs
basicConfig(format="%(asctime)s - %(levelname)s - %(message)s",
            level=INFO if is_rpi else DEBUG)
logger = getLogger(__name__)


class QBittorrent():
    def start(self):
        run('sudo systemctl start qbittorrent-nox', shell=True)
        logger.info("qBittorrent - starting...")
        sleep(2)

    def init(self):
        qb = Client(qb_addr)
        qb.login(qb_user, qb_pass)
        logger.info("qBittorrent - connected")

    def stop(self):
        run('sudo systemctl stop qbittorrent-nox', shell=True)
        logger.info("qBittorrent - stopping...")

    def size_format(self, b, factor=1024, suffix="B"):
        for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
            if b < factor:
                return f"{b:.2f}{unit}{suffix}"
            b /= factor
        return f"{b:.2f}Y{suffix}"

    def add_from_torrent_file(self, torrent):
        self.qb.download_from_file(torrent)

    def add_from_magnet_link(self, magnet):
        self.qb.download_from_link(magnet)

    def get_torrents(self):
        return self.qb.torrents()

    def get_torrent(self, infohash):
        return self.qb.get_torrent(infohash)

    def delete_torrent(self, infohash):
        return self.qb.delete_torrent(infohash)

    def log_torrent(self, infohash):
        torrent = self.get_torrent(infohash)
        return dict(torrent=f"Torrent: {torrent['name']}",
                    size=f"Size: {self.size_format(torrent['total_size'])}",
                    speed=f"Speed: {self.size_format(torrent['dlspeed'])}/s",
                    progress=f"Progress: {torrent['progress'] * 100} %")


def mediagram():
    qb = QBittorrent()
    if is_rpi:
        qb.start()
    qb.init()

    bot = TeleBot(token)
    bot.delete_my_commands(scope=None, language_code=None)
    bot.set_my_commands(
        commands=[types.BotCommand("alive", "Check if running"),
                  types.BotCommand("stop", "Kill switch")]
    )
    started = dt.fromtimestamp(now()).strftime("%Y-%m-%d %H:%M:%S")
    logger.info("Mediagram - initialized")

    @bot.message_handler(commands=['start', 'alive'])
    def alive(message):
        if message.chat.id == chat_id:
            bot.send_message(chat_id, f"Started at {started}\nRunning...")
            logger.info(message.text)

    @bot.message_handler(commands=['stop'])
    def stop(message):
        if message.chat.id == chat_id:
            bot.send_message(chat_id, f"Stopped.")
            logger.info(message.text)
            if is_rpi:
                qb.stop()
            bot.stop_polling()

    @bot.message_handler(func=lambda message: message.document.mime_type == 'application/x-bittorrent', content_types=['document'])
    def upload(message):
        if message.chat.id == chat_id:
            file_info = bot.get_file(message.document.file_id)
            file = bot.download_file(file_info.file_path)
            if not path.exists(repo):
                logger.info(f"Missing directory: '{repo}'")
            else:
                torrent = repo + message.document.file_name
                with open(torrent, 'wb') as f:
                    f.write(file)
                msg = bot.send_message(
                    chat_id, "Torrent uploaded.\nStart downloading...")
                logger.info(f"/upload: '{message.document.file_name}'")
                #bot.edit_message_text('edited', chat_id, msg.id)

    bot.infinity_polling(skip_pending=True)


if __name__ == '__main__':
    mediagram()
