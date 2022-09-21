from os import getenv, uname, path, listdir, remove
from shutil import rmtree, disk_usage
from subprocess import run
from threading import Thread, Event
from time import time as now, sleep
from datetime import datetime as dt
from logging import basicConfig, getLogger, INFO, DEBUG
from rich.logging import RichHandler
from telebot import TeleBot, types
from qbittorrent import Client
from plugins import TorrentSearch, SubtitlesSearch
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
ost_user = getenv("OST_USER")
ost_pass = getenv("OST_PASS")

# Platform
repo = dir_test
LOG_MODE = DEBUG
is_rpi = uname().machine == 'aarch64'
if is_rpi:
    run('/media/refresh.sh', shell=True)
    repo = dir_prod
    LOG_MODE = INFO
started = False
killed = False

# Logs
basicConfig(format="%(message)s",
            datefmt="[%Y-%m-%d %X]",
            level=LOG_MODE,
            handlers=[RichHandler()])
logger = getLogger("rich")


class SafeRequest:
    delay = 0.2
    timestamp = 0

    @staticmethod
    def release():
        SafeRequest.timestamp = now()
        return True

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
        self.qb.download_from_file(torrent, save_path=repo)

    def download_from_magnet_link(self, magnet):
        self.qb.download_from_link(magnet, save_path=repo)

    def only_sequential(self, info_hash):
        self.qb.toggle_sequential_download(info_hash)
        self.qb.toggle_first_last_piece_priority(info_hash)

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
            commands=[types.BotCommand("download", "🎬 Download"),
                      types.BotCommand("subtitles", "💬 Add subtitles"),
                      types.BotCommand("list", "🔍 List files"),
                      types.BotCommand("delete", "❌ Delete file(s)"),
                      types.BotCommand("help", "📝 Description"),
                      types.BotCommand("alive", "⚪ Health check"),
                      types.BotCommand("force", "♻️ Force media refresh"),
                      types.BotCommand("stop", "🔴 Kill the bot"),
                      types.BotCommand("restart", "🔵 Restart the bot")])
    started = dt.fromtimestamp(now()).strftime("%Y-%m-%d  -  %H:%M:%S")
    signal = Event()
    signal.set()
    threads = []
    id_stack, id_magnet, file_buffer = [], {}, ''
    bot.send_message(chat_id, "🟢 Started.")
    logger.info("Mediagram - initialized")

    @bot.message_handler(commands=['start', 'alive'])
    def alive(message):
        if message.chat.id == chat_id:
            bot.send_message(
                chat_id, f"⏰ Started at:\n{started}\n🟢 Running...")
            logger.info(message.text)

    @bot.message_handler(commands=['force'])
    def force(message):
        if message.chat.id == chat_id:
            run('/media/refresh.sh', shell=True)
            bot.send_message(chat_id, "♻️ Force media refresh: Done.")
            logger.info("/force: media-refresh")

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

    @bot.callback_query_handler(func=lambda call: call.data == 'Cancel')
    def cancel(call):
        if call.message.chat.id == chat_id:
            nonlocal id_stack, id_magnet, file_buffer
            for _, id in id_stack:
                bot.delete_message(chat_id, id)
            id_stack, id_magnet, file_buffer = [], {}, ''
            logger.info("/cancel")

    def delete_file(name):
        file = path.join(repo, name)
        srt = file[:-3] + 'srt'
        if path.isfile(file):
            remove(file)
            if path.isfile(srt):
                remove(srt)
            return True
        elif path.isdir(file):
            rmtree(file, ignore_errors=True)
            return True
        return False

    def download_manager(torrent_type, signal):
        info = qb.log_torrent(new=True)
        file, name, info_hash = info['name'], info['name'].capitalize(
        ), info['hash']
        qb.only_sequential(info_hash)
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
                bot.delete_message(chat_id, message.id)
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
                bot.delete_message(chat_id, message.id)
                thread = Thread(target=download_manager,
                                args=("Magnet link", signal))
                thread.start()
                threads.append(thread)

    @bot.callback_query_handler(func=lambda call: call.data in ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣'])
    def callback_select(call):
        if call.message.chat.id == chat_id:
            logger.info(f"/selected: {call.data}")
            if not signal.is_set():
                logger.info("/download-blocked - Magnet link")
            else:
                nonlocal id_stack, id_magnet
                magnet = id_magnet[call.data]
                logger.info(f"/retrieved_magnet_link: '{magnet}'")
                qb.download_from_magnet_link(magnet)
                for _, id in id_stack[1:]:
                    bot.delete_message(chat_id, id)
                id_stack, id_magnet = [], {}
                thread = Thread(target=download_manager,
                                args=("Magnet link", signal))
                thread.start()
                threads.append(thread)

    @bot.message_handler(func=lambda m: not list(filter(lambda x: m.text.startswith(x), ['/', 'magnet:?xt=', '🌐', '💬', '🔈'])), content_types=['text'])
    def torrent_select(message):
        if message.chat.id == chat_id:
            logger.info(f"/request: '{message.text}'")
            searcher = TorrentSearch()
            retry = 0
            while retry < 3:
                retry += 1
                torrents = searcher.query(message.text)
                if torrents:
                    break
            nonlocal id_stack
            id_stack.append(('download_reply', message.id))
            if not torrents:
                bot.send_message(chat_id, f"🚫 No result for: {message.text}")
                for _, id in id_stack[1:]:
                    bot.delete_message(chat_id, id)
                id_stack = []
                logger.info("/no_result")
            else:
                text = f"⛳️ Results for: {message.text}\n"
                markup = types.InlineKeyboardMarkup()
                row = []
                nonlocal id_magnet
                for i, t in zip(['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣'], torrents):
                    text += f"\n{i} {t['name']}\n💾 {t['size']} Go 🔗 {t['seeders']} 👤 {t['leechers']}\n⏰ {t['date']}\n"
                    row.append(types.InlineKeyboardButton(i, callback_data=i))
                    id_magnet[i] = t['magnet']
                markup.row(*row)
                markup.add(types.InlineKeyboardButton(
                    'Cancel', callback_data='Cancel'))
                msg = bot.send_message(chat_id, text, reply_markup=markup)
                id_stack.append(('download_choose', msg.id))
                logger.info("/torrent_select")

    @bot.message_handler(commands=['download'])
    def downloader(message):
        if message.chat.id == chat_id:
            if not path.exists(repo):
                logger.error(f"Missing directory: '{repo}'")
            else:
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton(
                    'Cancel', callback_data='Cancel'))
                msg = bot.send_message(chat_id, f"Enter filename:",
                                       reply_markup=markup)
                id_stack.append(('download_init', message.id))
                id_stack.append(('download_enter', msg.id))
                logger.info("/downloader")

    def get_disk_stats():
        usage = disk_usage(repo)
        total, used, free = [f'{v / 2**30:.1f}' for v in usage]
        return f"📦 {used} / {total} Go 🟰 {free} Go 🚥"

    def list_repo(symbol):
        ignored = ['System Volume Information', '$RECYCLE.BIN']
        return sorted([f"{symbol} {f[:32].capitalize()}" for f in listdir(repo) if f not in ignored and not f.endswith('.srt')])

    @bot.message_handler(commands=['list'])
    def list_files(message):
        if message.chat.id == chat_id:
            files = '\n'.join(list_repo('🌐'))
            bot.send_message(
                chat_id, f"💾 Available files 💾\n{get_disk_stats()}\n\n{files}", disable_web_page_preview=True)
            logger.info(message.text)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('🌐'))
    def callback_delete(call):
        if call.message.chat.id == chat_id:
            file = [f for f in listdir(
                repo) if f.capitalize().startswith(call.data[2:])][0]
            torrent = qb.get_torrent(name=file)
            if torrent:
                qb.delete_torrent(torrent['hash'])
                bot.edit_message_text(
                    f"🌐 {file.capitalize()}\n🚫 Aborted.", chat_id, call.message.id)
            elif delete_file(file):
                bot.edit_message_text(
                    f"🌐 {file.capitalize()}\n🗑 Deleted.", chat_id, call.message.id)
                logger.info(f"/deleted: '{file}'")
            nonlocal id_stack
            id_stack = []

    @bot.message_handler(commands=['delete'])
    def delete(message):
        if message.chat.id == chat_id:
            markup = types.InlineKeyboardMarkup()
            for file in list_repo('🌐'):
                markup.add(types.InlineKeyboardButton(
                    file, callback_data=file))
            markup.add(types.InlineKeyboardButton(
                'Cancel', callback_data='Cancel'))
            msg = bot.send_message(
                chat_id, f"❌ Available files to delete ❌\n{get_disk_stats()}", reply_markup=markup)
            id_stack.append(('delete_init', message.id))
            id_stack.append(('delete_select', msg.id))
            logger.info(message.text)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('🔈'))
    def callback_sub_download(call):
        if call.message.chat.id == chat_id:
            nonlocal id_stack, file_buffer
            subtitles_interface, buffer = id_stack[-1][1], file_buffer
            lang = call.data[1:]
            logger.info(f"/selected_language: {lang}")
            searcher = SubtitlesSearch(ost_user, ost_pass)
            retry = 0
            while retry < 3:
                retry += 1
                subtitles = searcher.query(buffer, lang)
                if subtitles:
                    break
                sleep(1)
            if not subtitles:
                text = f"🚫 No result for: {buffer}"
                sub_info = {lang: buffer}
                logger.info(f"/no_subtitles_found: {sub_info}")
            else:
                file = path.join(repo, buffer)
                if path.isdir(file):
                    filepath, filename, size = file, '', 0
                    for f in listdir(filepath):
                        s = path.getsize(path.join(filepath, f))
                        if s > size:
                            filename, size = f, s
                    if size == 0:
                        text = f"🚫 Empty directory error for: {buffer}"
                        logger.info(
                            f"/subtitles_empty_directory_error: {sub_info}")
                else:
                    filepath, filename = repo, buffer
                sub = subtitles[0]
                sub_info = {lang: filename}
                if searcher.download(sub, filename[:-4], filepath):
                    text = f"✅ Subtitles added for: {filename}"
                    logger.info(f"/subtitles_added: {sub_info}")
                else:
                    text = f"🚫 Download error for: {filename}"
                    logger.info(f"/subtitles_download_error: {sub_info}")
            id_stack, file_buffer = [], ''
            bot.edit_message_text(text, chat_id, subtitles_interface)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('💬'))
    def callback_sub_lang(call):
        if call.message.chat.id == chat_id:
            nonlocal file_buffer
            file_buffer = [f for f in listdir(
                repo) if f.capitalize().startswith(call.data[2:])][0]
            logger.info(f"/selected_for_subtitles: {file_buffer}")
            text = f"🔈 Select language for: {file_buffer}"
            markup = types.InlineKeyboardMarkup()
            row = []
            for lang, data in [('🇺🇸 English', '🔈eng'), ('🇫🇷 French', '🔈fre')]:
                row.append(types.InlineKeyboardButton(
                    lang, callback_data=data))
            markup.row(*row)
            markup.add(types.InlineKeyboardButton(
                'Cancel', callback_data='Cancel'))
            bot.edit_message_text(
                text, chat_id, id_stack[-1][1], reply_markup=markup)
            logger.info('/subtitles_lang')

    @bot.message_handler(commands=['subtitles'])
    def subtitles(message):
        if message.chat.id == chat_id:
            markup = types.InlineKeyboardMarkup()
            for file in list_repo('💬'):
                markup.add(types.InlineKeyboardButton(
                    file, callback_data=file))
            markup.add(types.InlineKeyboardButton(
                'Cancel', callback_data='Cancel'))
            msg = bot.send_message(
                chat_id, f"🪄 Add subtitles for:", reply_markup=markup)
            id_stack.append(('subtitles_init', message.id))
            id_stack.append(('subtitles_interface', msg.id))
            logger.info(message.text)

    try:
        bot.infinity_polling(skip_pending=True, timeout=200,
                             long_polling_timeout=200)
    except KeyboardInterrupt:
        global killed
        killed = True
        logger.info("Mediagram - killed by KeyboardInterrupt")
        signal.clear()
        for thread in threads:
            thread.join()
        qb.close()
        if is_rpi:
            qb.stop()
        return
    except Exception:
        pass


if __name__ == '__main__':
    while not killed:
        try:
            mediagram()
        except KeyboardInterrupt:
            killed = True
            logger.info("Mediagram - killed by KeyboardInterrupt")
