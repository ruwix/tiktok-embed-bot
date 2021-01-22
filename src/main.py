#!/usr/bin/env python
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
import os
import youtube_dl
import shutil
from urlextract import URLExtract
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import ChatAction
from functools import wraps
import re
import urllib

os.chdir(os.path.dirname(__file__))
logging.getLogger("filelock").disabled = True

download_dir = "videos"
max_file_size = 100

cur_file_counter = 0
downloaded_files = []


# custom url regexs
tiktok_regex = re.compile("https?://(?:www\.)?(?:vm\.)?tiktok\.com/[^/]+/?")
youtube_regex = re.compile("https?://(?:www\.)?youtube\.com/[^/]+/?")
youtube_mobile_regex = re.compile("https?://(?:www\.)?youtu\.be\/[^/]+/?")

# links that youtube dl wont catch
problem_regex = [tiktok_regex]
# links that should download without a command
auto_download_regex = [tiktok_regex, youtube_regex, youtube_mobile_regex]


def is_video(url: str) -> bool:
    """Check if a url is one which can be downloaded"""
    for extractor in youtube_dl.extractor.gen_extractors():
        if extractor.suitable(url) and extractor.IE_NAME != "generic":
            return True
    return any(regex.match(url) is not None for regex in problem_regex)


def is_auto_download(url: str) -> bool:
    """Check if a url is one which should automatically download"""
    return any(regex.match(url) is not None for regex in auto_download_regex)


def download_video(url: str, ydl_opts: dict) -> int:
    """Download a url to the computer"""
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        try:
            err = ydl.download([url])
        except Exception:
            err = -1
    return err


def extract_url(message):
    """Get the first url in a string"""
    urls = URLExtract().find_urls(message)
    if len(urls) == 0:
        return None
    url = urls[0]
    return url


def parse_message(update, context, is_command=False, force_audio=False):
    """Parse a any message and check whether or not it contains a link,
    whether or not it is a command, and whether or not it can actually download something"""
    global cur_file_counter

    # ensure it's a real message
    if not hasattr(update.message, "text"):
        return

    url = extract_url(update.message.text)

    # if it's a check up one reply for url
    if url is None:
        if is_command:
            if update.message.reply_to_message is not None:
                url = extract_url(update.message.reply_to_message.text)
                if url is None:
                    return
        else:
            return

    # check if the file has already been downloaded
    for downloaded in downloaded_files:
        if downloaded["url"] == url:
            user = update.message.from_user["username"]
            # check if the sent file was in another chat
            if update.message.chat_id != downloaded["message"].chat_id:
                already_sent_message = downloaded["message"].forward(
                    update.message.chat_id
                )
            else:
                already_sent_message = downloaded["message"]
            already_sent_message.reply_text(f"@{user}")
            return

    # make sure we can actually download the url
    if not is_command and not is_auto_download(url):
        return

    if not is_video(url):
        return

    logging.debug(f"Downloading from {url}...")

    ydl_opts = {
        "max_filesize": max_file_size * 1000000,
        "ignoreerrors": False,
    }
    if force_audio:
        # download the url as audio
        context.bot.send_chat_action(
            chat_id=update.effective_message.chat_id, action=ChatAction.UPLOAD_AUDIO
        )

        filename = f"{cur_file_counter}.mp3"
        ydl_opts.update(
            {
                "outtmpl": filename,
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
        )
    else:
        # download the url as a video
        context.bot.send_chat_action(
            chat_id=update.effective_message.chat_id, action=ChatAction.UPLOAD_VIDEO
        )
        filename = f"{cur_file_counter}.mp4"
        ydl_opts.update(
            {
                "format": "mp4",
                "outtmpl": filename,
            }
        )

    # download and check for errors
    err = download_video(url, ydl_opts)

    if not os.path.exists(filename):
        update.message.reply_text("Error downloading")
        return

    cur_file_counter += 1

    if force_audio:
        # send the file as audio
        reply_message = update.message.reply_audio(open(filename, "rb"), timeout=100)
    else:
        # send the file as a videos
        reply_message = update.message.reply_video(open(filename, "rb"), timeout=100)
    downloaded_files.append({"url": url, "message": reply_message})


def download_command(update, context):
    parse_message(update, context, True, False)


def audio_command(update, context):
    parse_message(update, context, True, True)


def on_message(update, context):
    parse_message(update, context, False, False)


def main():
    # get telegram bot token
    with open("token.txt", "r") as token_file:
        token = token_file.read().rstrip("\n")
        updater = Updater(token, use_context=True)

    # remove old download directory
    if os.path.exists(download_dir):
        shutil.rmtree(download_dir)

    # make download directory
    os.mkdir(download_dir)
    os.chdir(download_dir)

    # add message handler
    updater.dispatcher.add_handler(CommandHandler("download", download_command))
    updater.dispatcher.add_handler(CommandHandler("daudio", audio_command))
    updater.dispatcher.add_handler(
        MessageHandler(callback=on_message, filters=Filters.text)
    )

    # wait for messages
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
