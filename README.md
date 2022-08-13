# Mediagram

Headless media server, controlled via Telegram, to download torrent files and cast them on smart TVs.
Made to be hosted on Raspberry Pi 4b.

## Requirements

```bash
sudo apt update -y
sudo apt full-upgrade -y
sudo apt install ntfs-3g exfat-fuse exfat-utils minidlna qbittorrent-nox screen -y
```

## Storage / Media server

```bash
sudo mkdir /media
sudo bash -c "echo 'media_dir=/media' > /etc/minidlna.conf"
sudo bash -c "echo 'sudo service minidlna force-reload && echo \"/media: refresh.\"' > /media/refresh.sh"
sudo chmod +x /media/refresh.sh

# [Optional] To add the script as a command:
sudo echo 'alias media-refresh="/media/refresh.sh"' >> ~/.bashrc
source ~/.bashrc
```

Automatically mount USB key / SD card when connected:
https://miqu.me/blog/2015/01/14/tip-exfat-hdd-with-raspberry-pi/

## qbittorrent-nox

Follow:
https://www.linuxcapable.com/how-to-install-latest-qbittorrent-on-ubuntu-20-04-desktop-and-server/#Import_qBittorrent-nox_Stable

Settings:

```
Default url: http://localhost:8080
Default account: admin/adminadmin
[Download] Delete .torrent files afterwards ✔️
[Download] Default Save Path = <your media directory>
[Web UI] Bypass authentication for clients on localhost ✔️
```

## Telegram bot

Follow:
https://core.telegram.org/bots#6-botfather

## Deploy from PC to Raspberry Pi with SSH

Copy deploy_rpi.sh, modify HOST, PORT, SRC, DEST, and then deploy:

```bash
./deploy_rpi_local.sh
```

## Environment variables

Create .env file with:

```bash
sudo nano Mediagram/.env
```

Then paste the modified following lines:

```ini
TELEGRAM_BOT_ID=<your bot id>
TELEGRAM_CHAT_ID=<your chat id>
DIR_PROD=<your media directory for production>
DIR_TEST=<your media directory for test>
QB_ADDR=<http://host:port>
QB_USER=<user_account>
QB_PASS=<password>
```

## Run

```bash
screen # To run in subprocess: https://www.tecmint.com/keep-remote-ssh-sessions-running-after-disconnection/
pip install -U -r requirements.txt
python main.py
```
