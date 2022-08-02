# Mediagram

Headless media server, controlled via Telegram, to download torrent files and cast them on smart TVs.
Made to be hosted on Raspberry Pi 4b.

## Requirements

```bash
sudo apt update -y
sudo apt full-upgrade -y
sudo apt install ntfs-3g exfat-fuse exfat-utils minidlna screen -y
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
```

## Deploy on Raspberry Pi

```bash
# Modify: HOST, PORT, SRC, DEST
./deploy_rpi.sh
```

## Run

```bash
screen # to run in subprocess
cd Mediagram
pip install -U -r requirements.txt
python main.py
```
