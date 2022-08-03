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
dead = False

# Logs
basicConfig(format="%(asctime)s - %(levelname)s - %(message)s",
            level=INFO if is_rpi else DEBUG)
logger = getLogger(__name__)


class QBittorrent():
    qb = None

    def start(self):
        run('sudo systemctl start qbittorrent-nox', shell=True)
        logger.info("qBittorrent - starting...")
        sleep(2)

    def init(self):
        self.qb = Client(qb_addr)
        self.qb.login(qb_user, qb_pass)
        logger.info("qBittorrent - connected")
        self.clean_torrents()

    def stop(self):
        run('sudo systemctl stop qbittorrent-nox', shell=True)
        logger.info("qBittorrent - stopping...")

    def size_format(self, b, factor=1024, suffix="o"):
        for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
            if b < factor:
                return f"{b:.2f} {unit}{suffix}"
            b /= factor
        return f"{b:.2f} Y{suffix}"

    def download_from_torrent_file(self, torrent):
        self.qb.download_from_file(torrent)

    def download_from_magnet_link(self, magnet):
        self.qb.download_from_link(magnet)

    def get_torrents(self):
        return self.qb.torrents()

    def get_torrent(self, info_hash):
        for t in self.get_torrents():
            if t['hash'] == info_hash:
                return t

    def clean_torrents(self):
        self.qb.delete_all_permanently()

    def delete_torrent(self, info_hash):
        self.qb.delete(info_hash)

    def log_torrent(self, info_hash):
        torrent = self.get_torrent(info_hash)
        size = f"Size: {self.size_format(torrent['total_size'])}"
        speed = f"Speed: {self.size_format(torrent['dlspeed'])}/s"
        progress = f"Progress: {torrent['progress'] * 100:.2f} %"
        return dict(
            name=torrent['name'],
            details=f"{size}\n{speed}\n{progress}",
            done=torrent['progress'] == 1
        )


def mediagram():
    qb = QBittorrent()
    if is_rpi:
        qb.start()
    qb.init()

    bot = TeleBot(token)
    bot.delete_my_commands(scope=None, language_code=None)
    bot.set_my_commands(
        commands=[types.BotCommand("help", "Description"),
                  types.BotCommand("alive", "HealthCheck"),
                  types.BotCommand("list", "File list of files (TODO)"),
                  types.BotCommand("delete", "Delete file(s) (TODO)"),
                  types.BotCommand("stop", "KillSwitch"),
                  types.BotCommand("restart", "Restart")])
    started = dt.fromtimestamp(now()).strftime("%Y-%m-%d %H:%M:%S")
    bot.send_message(chat_id, f"Started.")
    logger.info("Mediagram - initialized")

    @bot.message_handler(commands=['start', 'alive'])
    def alive(message):
        if message.chat.id == chat_id:
            bot.send_message(chat_id, f"Started at {started}\nRunning...")
            logger.info(message.text)

    @bot.message_handler(commands=['stop', 'restart'])
    def kill(message):
        if message.chat.id == chat_id:
            global dead
            if message.text == '/stop':
                bot.send_message(chat_id, f"Stopped.")
                dead = True
            else:
                bot.send_message(chat_id, f"Restarting...")
            logger.info(message.text)
            if is_rpi:
                qb.stop()
            bot.stop_polling()

    @bot.message_handler(commands=['help'])
    def help(message):
        if message.chat.id == chat_id:
            bot.send_message(
                chat_id, f"Send a .torrent file or a magnet link to download it on your Raspberry Pi.")
            logger.info(message.text)

    @bot.message_handler(func=lambda message: message.document.mime_type == 'application/x-bittorrent', content_types=['document'])
    def upload_torrent_file(message):
        if message.chat.id == chat_id:
            file_info = bot.get_file(message.document.file_id)
            torrent = bot.download_file(file_info.file_path)
            if not path.exists(repo):
                logger.error(f"Missing directory: '{repo}'")
            else:
                logger.info(
                    f"/upload_torrent_file: '{message.document.file_name}'")
                qb.download_from_torrent_file(torrent)
                download_manager(message, "Torrent file")

    @bot.message_handler(func=lambda message: message.text.startswith('magnet:?xt='), content_types=['text'])
    def upload_magnet_link(message):
        if message.chat.id == chat_id:
            if not path.exists(repo):
                logger.error(f"Missing directory: '{repo}'")
            else:
                logger.info(f"/upload_magnet_link: '{message.text}'")
                qb.download_from_magnet_link(message.text)
                download_manager(message, "Magnet link")

    def download_manager(src_message, torrent_type):
        info_hash = qb.get_torrents()[0]['hash']
        info = qb.log_torrent(info_hash)
        name = info['name']
        logger.info(f"/download: '{name}'")
        uploaded = f"Torrent: {name}\n{torrent_type} uploaded.\nStart downloading...\n"
        msg = bot.reply_to(src_message, f"{uploaded}{info['details']}")
        while not info['done']:
            sleep(1)
            new_info = qb.log_torrent(info_hash)
            if info != new_info:
                info = new_info
                bot.edit_message_text(
                    f"{uploaded}{info['details']}", chat_id, msg.id)
        qb.delete_torrent(info_hash)
        bot.edit_message_text(
            f"{uploaded}{info['details']} - Done!", chat_id, msg.id)
        logger.info(f"/done: '{name}'")

    bot.infinity_polling(skip_pending=True)


if __name__ == '__main__':
    while not dead:
        mediagram()
