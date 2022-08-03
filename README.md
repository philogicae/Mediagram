# Mediagram

Headless media server, controlled via Telegram, to download torrent files and cast them on smart TVs.
Made to be hosted on Raspberry Pi 4b.

## Requirements

```bash
sudo apt update -y
sudo apt full-upgrade -y
sudo apt install ntfs-3g exfat-fuse exfat-utils minidlna qbittorrent-nox screen -y

# Setup qbittorrent-nox:
# https://www.linuxcapable.com/how-to-install-latest-qbittorrent-on-ubuntu-20-04-desktop-and-server/#Import_qBittorrent-nox_Stable
```

## Configuration

```bash
sudo mkdir /media/usb
sudo bash -c "echo 'media_dir=/media/usb' > /etc/minidlna.conf"
sudo bash -c "echo 'sudo service minidlna force-reload && echo \"/media/usb: refresh.\"' > /media/refresh.sh"
sudo chmod +x /media/refresh.sh
#[Optionnal] sudo echo 'alias media-refresh="/media/refresh.sh"' >> ~/.bashrc
#[Optionnal] source ~/.bashrc

# Automatically mount USB drive when connected:
# https://miqu.me/blog/2015/01/14/tip-exfat-hdd-with-raspberry-pi/
```

## Environment variables

```bash
cat > .env

# Add:
# TELEGRAM_BOT_ID=<your bot id>
# TELEGRAM_CHAT_ID=<your chat id>
# DIR_PROD=<your media directory for production>
# DIR_TEST=<your media directory for test>
# QB_ADDR=<http://host:port>
# QB_USER=<user_account>
# QB_PASS=<password>
```

## Deploy on Raspberry Pi

```bash
# Modify: HOST, PORT, SRC, DEST
./deploy_rpi.sh
```

## Run

```bash
screen # to run in subprocess
pip install -U -r requirements.txt
python main.py
```
