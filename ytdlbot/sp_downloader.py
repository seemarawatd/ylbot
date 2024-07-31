#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - sp_downloader.py
# 3/16/24 16:32
#

__author__ = "SanujaNS <sanujas@sanuja.biz>"

import functools
import os
import json
import logging
import pathlib
import re
import traceback
from urllib.parse import urlparse, parse_qs

from pyrogram import types
from tqdm import tqdm
import filetype
import requests
from bs4 import BeautifulSoup
import yt_dlp as ytdl

from config import (
    PREMIUM_USER,
    TG_NORMAL_MAX_SIZE,
    TG_PREMIUM_MAX_SIZE,
    FileTooBig,
    IPv6,
)
from downloader import (
    edit_text,
    remove_bash_color,
    ProgressBar,
    tqdm_progress,
    download_hook,
    upload_hook,
)
from limit import Payment
from utils import sizeof_fmt, parse_cookie_file, extract_code_from_instagram_url


def sp_dl(url: str, tempdir: str, bm, **kwargs) -> list:
    """Specific link downloader"""
    domain = urlparse(url).hostname
    if "youtube.com" in domain or "youtu.be" in domain:
        raise ValueError("ERROR: This is ytdl bot for Youtube links just send the link.")
    elif "www.instagram.com" in domain:
        return instagram(url, tempdir, bm, **kwargs)
    elif "pixeldrain.com" in domain:
        return pixeldrain(url, tempdir, bm, **kwargs)
    elif "krakenfiles.com" in domain:
        return krakenfiles(url, tempdir, bm, **kwargs)
    elif any(
        x in domain
        for x in [
            "terabox.com",
            "nephobox.com",
            "4funbox.com",
            "mirrobox.com",
            "momerybox.com",
            "teraboxapp.com",
            "1024tera.com",
            "terabox.app",
            "gibibox.com",
            "goaibox.com",
            "tibibox.com",
            "freeterabox.com",
            "teraboxlink.com",
        ]
    ):
        return terabox(url, tempdir, bm, **kwargs)
    else:
        raise ValueError(f"Invalid URL: No specific link function found for {url}")

    return []


def sp_ytdl_download(url: str, tempdir: str, bm, filename=None, ARIA2=None, **kwargs) -> list:
    payment = Payment()
    chat_id = bm.chat.id
    if filename:
        output = pathlib.Path(tempdir, filename).as_posix()
    else:
        output = pathlib.Path(tempdir, "%(title).70s.%(ext)s").as_posix()
    ydl_opts = {
        "progress_hooks": [lambda d: download_hook(d, bm)],
        "outtmpl": output,
        "restrictfilenames": False,
        "quiet": True,
        "format": None,
    }
    if ARIA2:
        ydl_opts["external_downloader"] = "aria2c"
        ydl_opts["external_downloader_args"] = [
            "--min-split-size=1M",
            "--max-connection-per-server=1",
            "--max-concurrent-downloads=2",
            "--connect-timeout=120",
            "--max-tries=0",
            "--retry-wait=3",
            "--timeout=120",
            "--split=2",
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        ]

    address = ["::", "0.0.0.0"] if IPv6 else [None]
    error = None
    video_paths = None
    for addr in address:
        ydl_opts["source_address"] = addr
        try:
            logging.info("Downloading %s", url)
            with ytdl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            video_paths = list(pathlib.Path(tempdir).glob("*"))
            break
        except FileTooBig as e:
                raise e
        except Exception:
            error = traceback.format_exc()
            logging.error("Download failed for %s - %s", url)

    if not video_paths:
        raise Exception(error)

    return video_paths


def instagram(url: str, tempdir: str, bm, **kwargs):
    resp = requests.get(f"https://insta1-sanujaput.b4a.run/api/instagram?token=1a1e726b4b40a&url={url}").json()
    code = extract_code_from_instagram_url(url)
    counter = 1
    video_paths = []
    if url_results := resp.get("data"):
        for link in url_results:
            req = requests.get(link, stream=True)
            length = int(req.headers.get("content-length"))
            content = req.content
            ext = filetype.guess_extension(content)
            filename = f"{code}_{counter}.{ext}"
            save_path = pathlib.Path(tempdir, filename)
            chunk_size = 4096
            downloaded = 0
            for chunk in req.iter_content(chunk_size):
                text = tqdm_progress(f"Downloading: {filename}", length, downloaded)
                edit_text(bm, text)
                with open(save_path, "ab") as fp:
                    fp.write(chunk)
                downloaded += len(chunk)
            video_paths.append(save_path)
            counter += 1

    return video_paths


def pixeldrain(url: str, tempdir: str, bm, **kwargs):
    user_page_url_regex = r"https://pixeldrain.com/u/(\w+)"
    match = re.match(user_page_url_regex, url)
    if match:
        url = "https://pixeldrain.com/api/file/{}?download".format(match.group(1))
        return sp_ytdl_download(url, tempdir, bm, **kwargs)
    else:
        return url


def krakenfiles(url: str, tempdir: str, bm, **kwargs):
    resp = requests.get(url)
    html = resp.content
    soup = BeautifulSoup(html, "html.parser")
    link_parts = []
    token_parts = []
    for form_tag in soup.find_all("form"):
        action = form_tag.get("action")
        if action and "krakenfiles.com" in action:
            link_parts.append(action)
        input_tag = form_tag.find("input", {"name": "token"})
        if input_tag:
            value = input_tag.get("value")
            token_parts.append(value)
    for link_part, token_part in zip(link_parts, token_parts):
        link = f"https:{link_part}"
        data = {
            "token": token_part
        }
        response = requests.post(link, data=data)
        json_data = response.json()
        url = json_data["url"]
    return sp_ytdl_download(url, tempdir, bm, **kwargs)


def terabox(url: str, tempdir: str, bm, **kwargs):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.5',
        # 'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Content-Type': 'application/json',
        'Origin': 'https://ytshorts.savetube.me',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Priority': 'u=1',
    }
    json_data = {
        'url': url,
    }
    response = requests.post('https://ytshorts.savetube.me/api/v1/terabox-downloader', headers=headers, json=json_data).json()["response"][0]
    filename = response["title"]
    file_name = f"{filename}.mp4"
    d_link = response["resolutions"]['HD Video']
    resp = requests.get(d_link, stream=True)
    sizebytes = int(resp.headers.get('content-length', 0))
    url = d_link

    return sp_ytdl_download(url, tempdir, bm, filename=file_name, ARIA2=True, **kwargs)
