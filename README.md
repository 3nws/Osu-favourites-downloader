## osu! favourites downloader

```
$ ./download.py [PLAYER_ID] [DIR] [LIMIT]
```
```
python download.py [PLAYER_ID] [DIR] [LIMIT]
```

PLAYER_ID: The player's id to download favourite beatmaps of.

DIR: Either absolute or relative path of the directory to store the files.

LIMIT (OPTIONAL): The maximum number of favourites to download. Defaults to 100.

It will show download progress in the terminal.

Requires client_id and secret. [See](https://osu.ppy.sh/home/account/edit#new-oauth-application). Place them in `config.py`.
