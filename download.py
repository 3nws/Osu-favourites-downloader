#!/usr/bin/env python3

import requests
import sys
import os

from os.path import basename, dirname, abspath
from pathlib import Path
from zipfile import ZipFile

from config import *

class BeatmapSet:
    def __init__(self, **kwargs):
        self.title = kwargs['title']
        self.id = str(kwargs['id'])
        self.artist = kwargs['artist']
        self.status = kwargs['status']
        self.favourite_count = kwargs['favourite_count']


def read_beatmap_list(**kwargs):
    beatmap_list = []
    json_ = kwargs.pop("json", None)
    if json_ is not None:
        for beatmap in json_:
            b = BeatmapSet(**beatmap)
            beatmap_list.append(b)
    return beatmap_list

class CredentialsError(Exception):
    pass

class ArgumentsException(Exception):
    pass

def add_to_zip(paths, name):
    print("Adding to zip....")
    with ZipFile(name, 'w') as z:
        for f in paths:
            z.write(f, basename(f))

def download_beatmapset(beatmapset, absolute_path):
    mirrors = { 
        "beatconnect.io": "https://beatconnect.io/b/{}",
        "chimu.moe": "https://api.chimu.moe/v1/download/{}?n=1",
        "nerinyan.moe": "https://nerinyan.moe/d/{}"
    }
    downloaded = None
    try: id = beatmapset.id
    except AttributeError: id = beatmapset.beatmapset_id
    success = False

    for m in mirrors:
        url = mirrors[m].format(id)
        print("\nTrying to download #{0} from {1}. Press Ctrl + C if download gets stuck for too long.".format(id, m))

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
                response = requests.get(r.url, stream=True)
                total_length = response.headers.get('Content-Length')

                if total_length is None:
                    f.write(response.content)
                else:
                    dl = 0
                    total_length = int(total_length)
                    for data in response.iter_content(chunk_size=4096):
                        dl += len(data)
                        f.write(data)
                        done = int(50 * dl / total_length)
                        sys.stdout.write(f"\r[{'='*done}{' '*(50-done)}] {int(100 * dl / total_length)}%")    
                        sys.stdout.flush()
            downloaded = filename

            if filename.exists():
                print(f"\nDownloaded #{id}")
                success = True
    
    if not success:
        print("Failed to download #{}! It probably does not exist on the mirrors.\n"
        "Please manually download the beatmap from osu.ppy.sh!".format(id))
    
    print("\nFinished downloading!")
    return downloaded

def read_favourites(player, *, limit=100):
    sess = requests.Session()
    res = sess.post("https://osu.ppy.sh/oauth/token", json={
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
        "scope": "public",
    })
    token = None
    try:
        token = res.json()["access_token"]
    except KeyError:
        raise CredentialsError("Please check your credentials!")
    url = f"https://osu.ppy.sh/api/v2/users/{player}/beatmapsets/favourite?limit={limit}"
    sess.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    })
    res = sess.get(url)
    maps = res.json()
    return read_beatmap_list(json=maps)

def download_favourites(player, download_dir, limit=None):
    abs_path = abspath(download_dir)
    if limit is not None: 
        stored_results = read_favourites(player, limit=limit)
    else:
        stored_results = read_favourites(player)
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
    if len(args) < 2:
        raise ArgumentsException("Please check the arguments.")
    if len(args) > 2:
        download_favourites(args[0], args[1], int(args[2]))
    else:
        download_favourites(args[0], args[1])


if __name__ == "__main__":
    main(sys.argv[1:])
