#!/usr/bin/env python
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
import os
import youtube_dl
import shutil
from urlextract import URLExtract
logging.getLogger("filelock").disabled = True
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import ChatAction
from functools import wraps
import re
import urllib

os.chdir(os.path.dirname(__file__))

DOWNLOADS_DIR = "video_downloads"

cur_file_counter = 0

tiktok_regex = re.compile("https?://(?:www\.)?(?:vm\.)?tiktok\.com/[^/]+/?")


def is_tiktok(url: str) -> bool:
    return tiktok_regex.match(url) is not None


def is_video(url: str) -> bool:
    for extractor in youtube_dl.extractor.gen_extractors():
        if extractor.suitable(url) and extractor.IE_NAME != "generic":
            return True
    return is_tiktok(url)

def is_general_download(url: str) -> bool:
    return is_video(url)

def is_auto_download(url: str) -> bool:
    return is_tiktok(url)

def get_length(url: str):
    ydl_opts = {
        "quiet": False,
    }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        video_info = ydl.extract_info(url, download=False)
        if video_info["duration"] is None:
            return 1e99
        return video_info["duration"]


def download_video(url: str, filename: str, max_length: int = 480) -> int:
    # if get_length(url) > 480:
    #     return 999991
    ydl_opts = {
        "format": "mp4",
        "outtmpl": filename,
        "max_filesize": 50000000,
        "ignoreerrors": False,
    }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        try:
            err = ydl.download([url])
        except Exception:
            err = -1
    return err

def extract_url(text):
    urls = URLExtract().find_urls(text)
    if len(urls) == 0:
        return None
        
    url = urls[0]
    return url

def download_command(update, context):
    global cur_file_counter
    filename = f"{cur_file_counter}.mp4"
    logging.info("HEY")

    if not hasattr(update.message, "text"):
        return

    url = extract_url(update.message.text)

    if url is None:
        if update.message.reply_to_message is not None:
            url = extract_url(update.message.reply_to_message.text)
            if url is None:
                return


    if not is_general_download(url):
        return

    context.bot.send_chat_action(
        chat_id=update.effective_message.chat_id, action=ChatAction.UPLOAD_VIDEO
    )


    logging.debug(f"Downloading from {url}...")
    err = download_video(url, filename)

    if not os.path.exists(filename):
        update.message.reply_text("Error downloading video")
        return

    cur_file_counter += 1

    update.message.reply_video(open(filename, "rb"), supports_streaming=True, timeout=100)


def on_message(update, context):
    global cur_file_counter
    filename = f"{cur_file_counter}.mp4"

    if not hasattr(update.message, "text"):
        return

    url = extract_url(update.message.text)

    if url is None:
        return

    if not is_auto_download(url):
        return

    context.bot.send_chat_action(
        chat_id=update.effective_message.chat_id, action=ChatAction.UPLOAD_VIDEO
    )


    logging.debug(f"Downloading from {url}...")
    err = download_video(url, filename)

    if not os.path.exists(filename):
        update.message.reply_text("Error downloading video")
        return

    cur_file_counter += 1

    update.message.reply_video(open(filename, "rb"), supports_streaming=True)

    # elif err == 99999:
    #     update.message.reply_text(
    #         f"Video is too long, must be shorter than {MAX_VID_LENGTH} seconds"
    #     )
    # else:
    #     update.message.reply_text(
    #         f"Could not download, error {err} . Video has to be shorter than {MAX_VID_LENGTH} seconds. Tell @creikey or @ruwix"
    #     )


def main():
    # get telegram bot token
    with open("token.txt", "r") as token_file:
        token = token_file.read()
        updater = Updater(token, use_context=True)

    # remove old download directory
    if os.path.exists(DOWNLOADS_DIR):
        shutil.rmtree(DOWNLOADS_DIR)

    # make download directory
    os.mkdir(DOWNLOADS_DIR)
    os.chdir(DOWNLOADS_DIR)

    # add message handler
    updater.dispatcher.add_handler(CommandHandler("download",download_command))
    updater.dispatcher.add_handler(
        MessageHandler(callback=on_message, filters=Filters.text)
    )

    # wait for messages
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
