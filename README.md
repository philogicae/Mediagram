# Mediagram

Headless media server, controlled via Telegram, to download torrent files and stream them on local network.
Made to be hosted on Raspberry Pi 4b.

## 1) Requirements

```bash
sudo apt update -y
sudo apt full-upgrade -y
sudo apt install ntfs-3g exfat-fuse minidlna qbittorrent-nox tmux -y
```

## 2) Media server (MiniDLNA)

```bash
sudo mkdir /media
sudo bash -c "echo 'friendly_name=Mediagram
media_dir=/media
port=8200
root_container=B
notify_interval=60
#network_interface=eth0' > /etc/minidlna.conf"
sudo bash -c "echo 'sudo service minidlna force-reload && echo \"/media: refresh.\"' > /media/refresh.sh"
sudo chmod +x /media/refresh.sh

# [Optional] To add the script as a command:
sudo echo 'alias media-refresh="/media/refresh.sh"' >> ~/.bashrc
source ~/.bashrc
```

## 3) Storage (USB/SD/SSD/HDD)

Prefer NTFS file system: faster to read/write and supports larger files.
(Source: https://miqu.me/blog/2015/01/14/tip-exfat-hdd-with-raspberry-pi/)

```ini
# Automatically (To append in /etc/fstab):
/dev/sda1 /media/mnt/ auto defaults,auto,relatime,umask=000,user,rw,nofail,x-systemd.device-timeout=10 0
```

```bash
# [Optional] Manually:
sudo bash -c "echo 'sudo mount -o umask=0 /dev/sda1 /media/mnt && echo \"/media/mnt: mounted.\"' > /media/mount.sh"
sudo bash -c "echo 'sudo umount /media/mnt && echo \"/media/mnt: unmounted.\"' > /media/umount.sh"
sudo chmod +x /media/mount.sh
sudo chmod +x /media/umount.sh
sudo echo 'alias media-mount="/media/mount.sh"
alias media-umount="/media/umount.sh"' >> ~/.bashrc
source ~/.bashrc
```

## 4) qbittorrent-nox

We need to register qbittorrent-nox as a service.
(Source: https://www.linuxcapable.com/how-to-install-latest-qbittorrent-on-ubuntu-20-04-desktop-and-server/#Import_qBittorrent-nox_Stable)

```bash
sudo adduser --system --group qbittorrent-nox
sudo adduser <your-username> qbittorrent-nox
sudo bash -c "echo '[Unit]
Description=qBittorrent Command Line Client
After=network.target
[Service]
Type=forking
User=qbittorrent-nox
Group=qbittorrent-nox
UMask=007
ExecStart=/usr/bin/qbittorrent-nox -d --webui-port=8080
Restart=on-failure
[Install]
WantedBy=multi-user.target' > /etc/systemd/system/qbittorrent-nox.service"
sudo systemctl daemon-reload
```

Settings:

```
Default url: http://localhost:8080
Default account: admin/adminadmin
[Download] Delete .torrent files afterwards ✔️
[Download] Default Save Path = <your-storage-directory>
[Download] Keep incomplete torrents in = <your-storage-directory> (Allows streaming of incomplete torrents)
[Web UI] Bypass authentication for clients on localhost ✔️
```

## 5) Telegram bot

Follow:
https://core.telegram.org/bots#6-botfather

## 6) Deploy from PC to Raspberry Pi with SSH

Duplicate deploy_rpi.sh, modify HOST, PORT, SRC, DEST, and then deploy:

```bash
./deploy_rpi_local.sh
```

## 7) Environment variables

Create .env file.

```bash
sudo nano Mediagram/.env
```

Create accounts: opensubtitles.org (V1) and opensubtitles.com (V2).
Then paste the modified following lines:

```ini
TELEGRAM_BOT_ID=<your-bot-id>
TELEGRAM_CHAT_ID=<your-chat-id>
DIR_PROD=<your-storage-directory-for-production>
DIR_PROD_ALT=<alt-storage-directory-for-production>
DIR_TEST=<your-storage-directory-for-test>
QB_ADDR=<http://host:port>
QB_USER=<qbittorrent-account>
QB_PASS=<password>
OST_USER=<opensubtitles-account>
OST_PASS=<password>
OST_API_KEY=<api-key> (if V2)
```

## Run

```bash
tmux # https://www.howtogeek.com/671422/how-to-use-tmux-on-linux-and-why-its-better-than-screen/
pip install -U -r requirements.txt
python main.py
```
