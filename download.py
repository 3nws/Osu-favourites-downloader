#!/usr/bin/env python3

import requests
import sys
import os
import datetime

from time import monotonic
from os.path import basename, dirname, abspath
from pathlib import Path
from zipfile import ZipFile

from config import *

class CredentialsError(Exception):
    pass


class ArgumentsException(Exception):
    pass

sess = requests.Session()
res = sess.post(
    "https://osu.ppy.sh/oauth/token",
    json={
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
        "scope": "public",
    },
)
token = None
try:
    token = res.json()["access_token"]
except KeyError:
    raise CredentialsError("Please check your credentials!")

class BeatmapSet:
    def __init__(self, **kwargs):
        self.title = kwargs["title"]
        self.id = str(kwargs["id"])
        self.artist = kwargs["artist"]
        self.status = kwargs["status"]
        self.favourite_count = kwargs["favourite_count"]


def read_beatmap_list(**kwargs):
    beatmap_list = []
    json_ = kwargs.pop("json", None)
    mode = kwargs.pop("mode", None)
    if json_ is not None and mode is not None:
        for beatmap in json_:
            if mode == "fav":
                b = BeatmapSet(**beatmap)
                beatmap_list.append(b)
            elif mode == "best":
                bsetid = beatmap["beatmap"]["beatmapset_id"]
                url = (
                    f"https://osu.ppy.sh/api/v2/beatmapsets/{bsetid}"
                )
                res = sess.get(url)
                map_ = res.json()
                b = BeatmapSet(**map_)
                beatmap_list.append(b)
    return beatmap_list


def add_to_zip(paths, name):
    print("Adding to zip....")
    with ZipFile(name, "w") as z:
        for f in paths:
            z.write(f, basename(f))


def download_beatmapset(beatmapset, absolute_path):
    mirrors = {
        "beatconnect.io": "https://beatconnect.io/b/{}",
        "chimu.moe": "https://api.chimu.moe/v1/download/{}?n=1",
        "nerinyan.moe": "https://nerinyan.moe/d/{}",
    }
    downloaded = None
    try:
        id = beatmapset.id
    except AttributeError:
        id = beatmapset.beatmapset_id
    success = False

    for m in mirrors:
        url = mirrors[m].format(id)
        print(
            "\nTrying to download #{0} from {1}. Press Ctrl + C if download gets stuck for too long.".format(
                id, m
            )
        )

        timeout = False

        try:
            r = requests.head(url, allow_redirects=True, timeout=10)
        except:
            timeout = True

        path = Path(absolute_path)
        if not timeout and r.status_code == 200:  # type: ignore
            filename = path.joinpath(id + ".osz")

            os.makedirs(dirname(filename), exist_ok=True)
            with open(filename, "wb") as f:
                print(f"Downloading {filename}")
                sess = requests.Session()
                sess.headers.update(
                    {
                        "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36"
                    }
                )
                response = sess.get(
                    r.url,
                    stream=True,
                )
                total_length = response.headers.get("Content-Length")
                start = last_print = monotonic()
                if total_length is None:
                    f.write(response.content)
                else:
                    dl = 0
                    total_length = int(total_length)
                    for data in response.iter_content(chunk_size=4096):
                        now = monotonic()
                        dl += len(data)
                        f.write(data)
                        if now - last_print > 1:
                            done = int(50 * dl / total_length)
                            speed = int(dl / (now - start) / 1024)
                            n = (total_length - dl) / (speed * 1024)
                            n = datetime.timedelta(seconds=n)
                            sys.stdout.write(
                                f"\r[{'='*done}{' '*(50-done)}] {int(100 * dl / total_length)}% - {speed} kb/s - {n}"
                            )
                            sys.stdout.flush()
                            last_print = now
            downloaded = filename

            if filename.exists():
                print(f"\nDownloaded #{id}")
                success = True

    if not success:
        print(
            "Failed to download #{}! It probably does not exist on the mirrors.\n"
            "Please manually download the beatmap from osu.ppy.sh!".format(id)
        )

    print("\nFinished downloading!")
    return downloaded


def read_beatmaps(mode, player, *, limit=100):
    if mode == "fav":
        url = (
            f"https://osu.ppy.sh/api/v2/users/{player}/beatmapsets/favourite?limit={limit}"
        )
    elif mode == "best":
        url = (
            f"https://osu.ppy.sh/api/v2/users/{player}/scores/best?limit={limit}"
        )
    else:
        raise ArgumentsException("Please pick either 'fav' or 'best'!")
    sess.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    )
    res = sess.get(url)
    maps = res.json()
    return read_beatmap_list(json=maps, mode=mode)


def download_beatmaps(mode, player, download_dir, limit=None):
    stored_results = []
    abs_path = abspath(download_dir)
    if limit is not None:
        if mode == "fav":
            stored_results = read_beatmaps(mode, player, limit=limit)
        if mode == "best":
            stored_results = read_beatmaps(mode, player, limit=limit)
    else:
        if mode == "fav":
            stored_results = read_beatmaps(mode, player)
        if mode == "best":
            stored_results = read_beatmaps(mode, player)
    counter = 0
    downloaded = []
    for b in stored_results:
        file = download_beatmapset(b, abs_path)
        if file is not None:
            downloaded.append(file)
            counter += 1
            print(str(counter) + "/" + str(len(stored_results)) + " downloaded")

    add_to_zip(downloaded, "maps.zip")
    print("Files added to zip")


def main(args):
    if len(args) < 3:
        raise ArgumentsException("Please check the arguments.")
    if len(args) > 4:
        if args[0] == "fav":
            download_beatmaps(args[0], args[1], args[2], int(args[3]))
        elif args[0] == "best":
            download_beatmaps(args[0], args[1], args[2], int(args[3]))
    else:
        if args[0] == "fav":
            download_beatmaps(args[0], args[1], args[2])
        elif args[0] == "best":
            download_beatmaps(args[0], args[1], args[2])


if __name__ == "__main__":
    main(sys.argv[1:])
