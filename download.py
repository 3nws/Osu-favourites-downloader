#!/usr/bin/env python3

import requests
import sys
import os
import datetime

from time import monotonic
from os.path import basename, dirname, abspath
from pathlib import Path
from zipfile import ZipFile
from typing import Optional, Any

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
    def __init__(self, **kwargs: Any):
        self.title = kwargs.pop("title", None)
        self.id = str(kwargs.pop("id", None))
        self.beatmapset_id = str(kwargs.pop("beatmapset_id", None))
        self.artist = kwargs.pop("artist", None)
        self.status = kwargs.pop("status", None)
        self.favourite_count = kwargs.pop("favourite_count", None)

    # def __init__(self, **kwargs: Any):
    #     for k, v in kwargs.items():
    #         setattr(self, k, str(v))


def read_beatmap_list(**kwargs: Any) -> list[BeatmapSet]:
    beatmap_list: list[BeatmapSet] = []
    json_ = kwargs.pop("json", None)
    mode = kwargs.pop("mode", None)
    if json_ is not None and mode is not None:
        for beatmap in json_:
            if mode == "fav":
                b = BeatmapSet(**beatmap)
                beatmap_list.append(b)
            elif mode == "best":
                bsetid = beatmap["beatmap"]["beatmapset_id"]
                url = f"https://osu.ppy.sh/api/v2/beatmapsets/{bsetid}"
                res = sess.get(url)
                map_ = res.json()
                b = BeatmapSet(**map_)
                beatmap_list.append(b)
    return beatmap_list


def add_to_zip(paths: list[Path], name: str):
    print("Zipping files....")
    with ZipFile(name, "w") as z:
        for f in paths:
            z.write(f, basename(f))


def download_beatmapset(beatmapset: BeatmapSet, absolute_path: str) -> Optional[Path]:
    mirrors = {
        "beatconnect.io": "https://beatconnect.io/b/{}",
        "chimu.moe": "https://api.chimu.moe/v1/download/{}?n=1",
        "nerinyan.moe": "https://nerinyan.moe/d/{}",
    }
    downloaded = None
    try:
        id_: str = beatmapset.id
    except AttributeError:
        id_: str = beatmapset.beatmapset_id
    success = False

    for m in mirrors:
        url = mirrors[m].format(id_)
        print(
            f"\nTrying to download #{id_} from {m}. Press Ctrl + C if download gets stuck for too long."
        )

        timeout = False

        try:
            r = requests.head(url, allow_redirects=True, timeout=10)
        except:
            r = None
            timeout = True

        path = Path(absolute_path)

        if not timeout and r is not None and r.status_code == 200:
            filename = path.joinpath(id_ + ".osz")
            os.makedirs(dirname(filename), exist_ok=True)
            if not os.path.isfile(filename):
                with open(filename, "wb") as f:
                    print(f"Downloading {beatmapset.title or ''} #{id_}")
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
                print(f"\nDownloaded {beatmapset.title or ''} #{id_}")
                success = True

    if not success:
        print(
            "Failed to download #{}! It probably does not exist on the mirrors.\n"
            "Please manually download the beatmap from osu.ppy.sh!".format(id)
        )

    print(f"\nFinished downloading {beatmapset.title or ''} #{id_}!")
    return downloaded


def read_beatmaps(mode: str, player: str, *, limit: Optional[int] = 100):
    if mode == "fav":
        url = f"https://osu.ppy.sh/api/v2/users/{player}/beatmapsets/favourite?limit={limit}"
    elif mode == "best":
        url = f"https://osu.ppy.sh/api/v2/users/{player}/scores/best?limit={limit}"
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


def download_beatmaps(
    mode: str, player: str, download_dir: str, limit: Optional[int] = None
):
    stored_results: list[BeatmapSet] = []
    abs_path = abspath(download_dir)
    stored_results = read_beatmaps(mode, player, limit=limit)
    counter = 0
    downloaded: list[Path] = []
    for b in stored_results:
        file = download_beatmapset(b, abs_path)
        if file is not None:
            downloaded.append(file)
            counter += 1
            print(str(counter) + "/" + str(len(stored_results)) + " downloaded")

    add_to_zip(downloaded, f"{abs_path}/maps.zip")
    print("Files zipped")


def main(args: list[str]):
    if len(args) < 3:
        raise ArgumentsException("Please check the arguments.")
    download_beatmaps(
        args[0], args[1], args[2], int(args[3]) if len(args) >= 4 else None
    )


if __name__ == "__main__":
    main(sys.argv[1:])
