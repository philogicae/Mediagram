from os import getenv, uname, path, listdir, remove
from shutil import rmtree
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
log_mode = DEBUG
is_rpi = uname().machine == 'aarch64'
if is_rpi:
    run('cd / && ./media/refresh.sh', shell=True)
    repo = dir_prod
    log_mode = INFO
started = False
killed = False

# Logs
basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=log_mode)
logger = getLogger(__name__)


def singleton(class_):
    instances = {}

    def getinstance(*args, **kwargs):
        if class_ not in instances:
            instances[class_] = class_(*args, **kwargs)
        return instances[class_]
    return getinstance


@singleton
class SafeRequest:
    delay = 0.2
    timestamp = 0

    @staticmethod
    def release():
        SafeRequest.timestamp = now()

    @staticmethod
    def is_releasable():
        return SafeRequest.timestamp + SafeRequest.delay < now()


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
        # self.qb.logout()
        logger.info("qBittorrent - disconnected")

    def stop(self):
        self.qb.shutdown()
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

    def get_torrent(self, info_hash=None, name=None, new=False):
        if info_hash:
            for t in self.qb.torrents():
                if t['hash'] == info_hash:
                    return t
        elif name:
            for t in self.qb.torrents():
                if t['name'] == name:
                    return t
        elif new:
            return self.qb.torrents(sort='added_on')[-1]

    def clean_torrents(self):
        self.qb.delete_all_permanently()

    def delete_torrent(self, info_hash):
        self.qb.delete(info_hash)

    def log_torrent(self, info_hash=None, name=None, new=False):
        torrent = self.get_torrent(info_hash=info_hash, name=name, new=new)
        if torrent:
            status = f"🌊 {torrent['state'].capitalize()}"
            seeders = f"🔗 {torrent['num_seeds']} ({torrent['num_complete']})"
            leechers = f"👤 {torrent['num_leechs']} ({torrent['num_incomplete']})"
            size = f"💾 {self.size_format(torrent['total_size'])}"
            speed = f"⚡ {self.size_format(torrent['dlspeed'])}/s"
            eta = f"⏱️ {self.eta_format(torrent['eta'])}"
            progress = f"⏳ {torrent['progress'] * 100:.2f} %"
            return dict(
                name=torrent['name'],
                hash=torrent['hash'],
                details=f"{status}\n{seeders:15.15s}{leechers}\n{size:15.15s}{speed}\n{eta:15.15s}{progress}",
                done=torrent['progress'] == 1
            )


def mediagram():
    qb = QBittorrent()
    if is_rpi:
        qb.start()
    qb.init()

    bot = TeleBot(token)
    global started
    if not started:
        bot.set_my_commands(
            commands=[types.BotCommand("help", "📝 Description"),
                      types.BotCommand("alive", "⚪ Health check"),
                      types.BotCommand("list", "🔍 List files"),
                      types.BotCommand("delete", "❌ Delete file(s)"),
                      types.BotCommand("stop", "🔴 Kill the bot"),
                      types.BotCommand("restart", "🔵 Restart the bot")])
    started = dt.fromtimestamp(now()).strftime("%Y-%m-%d  -  %H:%M:%S")
    signal = Event()
    signal.set()
    threads = []
    bot.send_message(chat_id, "🟢 Started.")
    logger.info("Mediagram - initialized")

    @bot.message_handler(commands=['start', 'alive'])
    def alive(message):
        if message.chat.id == chat_id:
            bot.send_message(
                chat_id, f"⏰ Started at:\n{started}\n🟢 Running...")
            logger.info(message.text)

    @bot.message_handler(commands=['stop', 'restart'])
    def kill(message):
        if message.chat.id == chat_id:
            if message.text == '/stop':
                global killed
                killed = True
                bot.send_message(chat_id, "🟠 Stopping...")
            else:
                bot.send_message(chat_id, "🔵 Restarting...")
            logger.info(message.text)
            signal.clear()
            for thread in threads:
                thread.join()
            bot.stop_polling()
            qb.close()
            if is_rpi:
                qb.stop()
            bot.send_message(chat_id, "🔴 Shutdown.")
            logger.info("Mediagram - shutdown")

    @bot.message_handler(commands=['help'])
    def help(message):
        if message.chat.id == chat_id:
            bot.send_message(
                chat_id, "📝 Send a .torrent file or a magnet link to download it on your Raspberry Pi.")
            logger.info(message.text)

    def delete_file(name):
        file = path.join(repo, name)
        if path.isfile(file):
            remove(file)
            return True
        elif path.isdir(file):
            rmtree(file, ignore_errors=True)
            return True
        return False

    def download_manager(torrent_type, signal):
        info = qb.log_torrent(new=True)
        file, name, info_hash = info['name'], info['name'].capitalize(
        ), info['hash']
        logger.info(f"/download: '{file}'")
        base = f"🌐 {name}\n🔥 {torrent_type} processed\n"
        msg = bot.send_message(chat_id, f"{base}{info['details']}")
        while signal.is_set() and not info['done']:
            sleep(2)
            released = False
            while not released:
                new_info = qb.log_torrent(info_hash=info_hash)
                if SafeRequest.is_releasable():
                    if not new_info:
                        delete_file(file)
                        bot.edit_message_text(
                            f"{base}🚫 Aborted.", chat_id, msg.id)
                        logger.info(f"/aborted: '{file}'")
                        return
                    if info != new_info:
                        info = new_info
                        bot.edit_message_text(
                            f"{base}{info['details']}", chat_id, msg.id)
                    released = SafeRequest.release()
        qb.delete_torrent(info_hash)
        if info['done']:
            bot.delete_message(chat_id, msg.id)
            bot.send_message(chat_id, f"{base}✅ Completed. Ready to play!")
            logger.info(f"/done: '{file}'")
        else:
            delete_file(file)
            bot.edit_message_text(f"{base}🚫 Aborted.", chat_id, msg.id)
            logger.info(f"/aborted: '{file}'")

    @bot.message_handler(func=lambda message: message.document.mime_type == 'application/x-bittorrent', content_types=['document'])
    def upload_torrent_file(message):
        if message.chat.id == chat_id:
            file_info = bot.get_file(message.document.file_id)
            torrent = bot.download_file(file_info.file_path)
            if not path.exists(repo):
                logger.error(f"Missing directory: '{repo}'")
            elif not signal.is_set():
                logger.info("/download-blocked - Torrent file")
            else:
                logger.info(
                    f"/upload_torrent_file: '{message.document.file_name}'")
                qb.download_from_torrent_file(torrent)
                bot.delete_message(chat_id, message.message_id)
                thread = Thread(target=download_manager,
                                args=("Torrent file", signal))
                thread.start()
                threads.append(thread)

    @bot.message_handler(func=lambda message: message.text.startswith('magnet:?xt='), content_types=['text'])
    def upload_magnet_link(message):
        if message.chat.id == chat_id:
            if not path.exists(repo):
                logger.error(f"Missing directory: '{repo}'")
            elif not signal.is_set():
                logger.info("/download-blocked - Magnet link")
            else:
                logger.info(f"/upload_magnet_link: '{message.text}'")
                qb.download_from_magnet_link(message.text)
                bot.delete_message(chat_id, message.message_id)
                thread = Thread(target=download_manager,
                                args=("Magnet link", signal))
                thread.start()
                threads.append(thread)

    def list_repo():
        ignored = ['System Volume Information', '$RECYCLE.BIN']
        return sorted([f"🌐 {f[:22].capitalize()}" for f in listdir(repo) if f not in ignored])

    @bot.message_handler(commands=['list'])
    def list_files(message):
        if message.chat.id == chat_id:
            files = '\n'.join(list_repo())
            bot.send_message(
                chat_id, f"💾 Available files 💾\n\n{files}", disable_web_page_preview=True)
            logger.info(message.text)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('🌐') or call.data == 'Cancel')
    def callback_delete(call):
        if call.message.chat.id == chat_id:
            if call.data == 'Cancel':
                bot.delete_message(chat_id, call.message.message_id)
                logger.info(f"/cancel_delete")
                return
            file = [f for f in listdir(
                repo) if f.capitalize().startswith(call.data[2:])][0]
            torrent = qb.get_torrent(name=file)
            if torrent:
                qb.delete_torrent(torrent['hash'])
                bot.edit_message_text(
                    f"🌐 {file.capitalize()}\n🚫 Aborted.", chat_id, call.message.message_id)
            elif delete_file(file):
                bot.edit_message_text(
                    f"🌐 {file.capitalize()}\n🗑 Deleted.", chat_id, call.message.message_id)
                logger.info(f"/deleted: '{file}'")

    @bot.message_handler(commands=['delete'])
    def delete(message):
        if message.chat.id == chat_id:
            markup = types.InlineKeyboardMarkup()
            for file in list_repo():
                markup.add(types.InlineKeyboardButton(
                    file, callback_data=file))
            markup.add(types.InlineKeyboardButton(
                'Cancel', callback_data='Cancel'))
            bot.send_message(
                chat_id, "❌ Available files to delete ❌", reply_markup=markup)
            logger.info(message.text)

    bot.infinity_polling(skip_pending=True)


if __name__ == '__main__':
    while not killed:
        try:
            mediagram()
        except KeyboardInterrupt:
            killed = True
            logger.info("Mediagram - killed by KeyboardInterrupt")
