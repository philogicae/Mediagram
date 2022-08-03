from os import getenv, path, uname
from subprocess import run
from threading import Thread, Event
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

    def close(self):
        self.clean_torrents()
        self.qb.logout()
        logger.info("qBittorrent - disconnected")

    def stop(self):
        run('sudo systemctl stop qbittorrent-nox', shell=True)
        logger.info("qBittorrent - stopping...")

    def size_format(self, b, factor=1024, suffix="o"):
        for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
            if b < factor:
                return f"{b:.2f} {unit}{suffix}"
            b /= factor
        return f"{b:.2f} Y{suffix}"

    def eta_format(self, eta):
        if eta > 24 * 60 * 60:
            return f"23:59:59"
        h = eta // 3600
        m = (eta % 3600) // 60
        s = eta % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def download_from_torrent_file(self, torrent):
        self.qb.download_from_file(torrent)

    def download_from_magnet_link(self, magnet):
        self.qb.download_from_link(magnet)

    def get_torrent(self, info_hash=None):
        if info_hash is None:
            return sorted(self.qb.torrents(), key=lambda x: x['added_on'], reverse=True)[0]
        return self.qb.torrents(info_hash=info_hash)[0]

    def clean_torrents(self):
        self.qb.delete_all_permanently()

    def delete_torrent(self, info_hash):
        self.qb.delete(info_hash)

    def log_torrent(self, info_hash=None):
        torrent = self.get_torrent(info_hash)
        status = f"🌊 {torrent['state'].capitalize()}"
        size = f"💾 {self.size_format(torrent['total_size']):11.11s}"
        speed = f"⚡ {self.size_format(torrent['dlspeed'])}/s"
        eta = f"⏱️ {self.eta_format(torrent['eta']):11.11s}"
        progress = f"⏳ {torrent['progress'] * 100:.2f} %"
        return dict(
            name=torrent['name'],
            hash=torrent['hash'],
            details=f"{status}\n{size} {speed}\n{eta} {progress}",
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
        commands=[types.BotCommand("help", "📝 Description"),
                  types.BotCommand("alive", "⚪ HealthCheck"),
                  types.BotCommand("list", "🔍 List media files [TODO]"),
                  types.BotCommand("delete", "❌ Delete file(s) [TODO]"),
                  types.BotCommand("stop", "🔴 Kill the bot"),
                  types.BotCommand("restart", "🔵 Restart the bot")])
    started = dt.fromtimestamp(now()).strftime("%Y-%m-%d %H:%M:%S")
    signal = Event()
    signal.set()
    threads = []
    bot.send_message(chat_id, f"🟢 Started.")
    logger.info("Mediagram - initialized")

    @bot.message_handler(commands=['start', 'alive'])
    def alive(message):
        if message.chat.id == chat_id:
            bot.send_message(chat_id, f"⏰ Started at {started}\n🟢 Running...")
            logger.info(message.text)

    @bot.message_handler(commands=['stop', 'restart'])
    def kill(message):
        if message.chat.id == chat_id:
            if message.text == '/stop':
                global dead
                dead = True
                bot.send_message(chat_id, "🟠 Stopping... ")
            else:
                bot.send_message(chat_id, "🔵 Restarting... ")
            logger.info(message.text)
            signal.clear()
            for thread in threads:
                thread.join()
            bot.stop_polling()
            qb.close()
            if is_rpi:
                qb.stop()
            logger.info("Mediagram - shutdown")
            bot.send_message(chat_id, "🔴 Shutdown.")

    @bot.message_handler(commands=['help'])
    def help(message):
        if message.chat.id == chat_id:
            bot.send_message(
                chat_id, f"📝 Send a .torrent file or a magnet link to download it on your Raspberry Pi.")
            logger.info(message.text)

    def download_manager(torrent_type, signal):
        info = qb.log_torrent()
        name, info_hash = info['name'], info['hash']
        logger.info(f"/download: '{name}'")
        base = f"🌍 {name}\n🔥 {torrent_type} processed\n"
        msg = bot.send_message(chat_id, f"{base}{info['details']}")
        while signal.is_set() and not info['done']:
            sleep(1)
            new_info = qb.log_torrent(info_hash)
            if info != new_info:
                info = new_info
                bot.edit_message_text(
                    f"{base}{info['details']}", chat_id, msg.id)
        qb.delete_torrent(info_hash)
        if info['done']:
            bot.edit_message_text(
                f"{base}{info['details']} - Done!", chat_id, msg.id)
            logger.info(f"/done: '{name}'")
        else:
            run(f'sudo rm -r {repo}{name}', shell=True)
            logger.info(f"/aborted: '{name}'")

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
                thread = Thread(target=download_manager,
                                args=("Torrent file", signal))
                thread.start()
                threads.append(thread)

    @bot.message_handler(func=lambda message: message.text.startswith('magnet:?xt='), content_types=['text'])
    def upload_magnet_link(message):
        if message.chat.id == chat_id:
            if not path.exists(repo):
                logger.error(f"Missing directory: '{repo}'")
            else:
                logger.info(f"/upload_magnet_link: '{message.text}'")
                qb.download_from_magnet_link(message.text)
                thread = Thread(target=download_manager,
                                args=("Magnet link", signal))
                thread.start()
                threads.append(thread)

    bot.polling(skip_pending=True)


if __name__ == '__main__':
    while not dead:
        mediagram()
