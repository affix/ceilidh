#!/usr/bin/env python3
"""Search and download simfiles from Zenius -I- vanisher.

    uv run python3 tools/ziv.py search "breakfast club"
    uv run python3 tools/ziv.py get 70549
    uv run python3 tools/ziv.py info 1817
    uv run python3 tools/ziv.py get --pack 1817

Stdlib only so it runs anywhere the game does. One connection, one request at a
time, with a delay between them; the site is run on donations, so do not turn
this into a scraper.
"""

from __future__ import annotations

import argparse
import html
import http.cookiejar
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = "https://zenius-i-vanisher.com/v5.2/"
USER_AGENT = "ceilidh-ziv/0.1 (personal simfile downloader; stdlib urllib)"
SIMFILE_EXT = (".ssc", ".sm", ".dwi")
VIDEO_EXT = {".avi", ".mpg", ".mpeg", ".mp4", ".mkv", ".ogv", ".wmv", ".m2v", ".flv"}
JUNK = ("__MACOSX/", ".DS_Store", "Thumbs.db")
# characters Windows will not put in a filename, which song titles are full of
WINDOWS_ILLEGAL = re.compile(r'[<>:"|?*\x00-\x1f]')

_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_LINK = re.compile(r'<a\s[^>]*?href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
_TITLE_ATTR = re.compile(
    r'<a\s[^>]*?href="viewsimfile\.php\?simfileid=(\d+)"[^>]*?title="([^"]*)"', re.I)
_TAGS = re.compile(r"<[^>]+>")

_last_request = 0.0
_opener: urllib.request.OpenerDirector | None = None


def opener(cookie: str | None = None) -> urllib.request.OpenerDirector:
    global _opener
    if _opener is None:
        jar = http.cookiejar.CookieJar()
        _opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        headers = [("User-Agent", USER_AGENT), ("Accept-Encoding", "identity")]
        if cookie:
            headers.append(("Cookie", cookie))
        _opener.addheaders = headers
    return _opener


def _wait(delay: float) -> None:
    global _last_request
    remaining = delay - (time.monotonic() - _last_request)
    if remaining > 0:
        time.sleep(remaining)
    _last_request = time.monotonic()


def request(url: str, delay: float, cookie: str | None = None, retries: int = 3,
            headers: dict[str, str] | None = None):
    """Open a URL, retrying server errors with a widening backoff."""
    for attempt in range(retries):
        _wait(delay)
        req = urllib.request.Request(url, headers=headers or {})
        try:
            return opener(cookie).open(req, timeout=60)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                backoff = 2.0 * (attempt + 1)
                print(f"  {exc.code} from the server, retrying in {backoff:.0f}s", file=sys.stderr)
                time.sleep(backoff)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt < retries - 1:
                time.sleep(2.0 * (attempt + 1))
                continue
            raise SystemExit(f"cannot reach {url}: {exc}")
    raise SystemExit(f"gave up on {url}")


def get_text(path: str, delay: float, cookie: str | None = None) -> str:
    with request(urllib.parse.urljoin(BASE, path), delay, cookie) as response:
        return response.read().decode("utf-8", errors="replace")


def clean(fragment: str) -> str:
    return html.unescape(_TAGS.sub("", fragment)).strip()


def rows_with_links(page: str) -> list[list[tuple[str, str]]]:
    """Every table row, as a list of (href, text) pairs."""
    out = []
    for row in _ROW.findall(page):
        links = [(html.unescape(href), clean(text)) for href, text in _LINK.findall(row)]
        if links:
            out.append(links)
    return out


def _id_from(href: str, key: str) -> int | None:
    match = re.search(rf"{key}=(\d+)", href)
    return int(match.group(1)) if match else None


def parse_simfile_rows(page: str) -> list[dict]:
    artists = {int(sid): html.unescape(title) for sid, title in _TITLE_ATTR.findall(page)}
    results = []
    for links in rows_with_links(page):
        simfile_id = category_id = None
        title = category = ""
        for href, text in links:
            if simfile_id is None and href.startswith("viewsimfile.php?"):
                found = _id_from(href, "simfileid")
                if found is not None:
                    simfile_id, title = found, text
            elif category_id is None and href.startswith("viewsimfilecategory.php?"):
                found = _id_from(href, "categoryid")
                if found is not None:
                    category_id, category = found, text
        if simfile_id is None:
            continue
        artist = ""
        if simfile_id in artists and "/" in artists[simfile_id]:
            artist = artists[simfile_id].split("/", 1)[1].strip()
        results.append({
            "simfileid": simfile_id,
            "title": title,
            "artist": artist,
            "categoryid": category_id,
            "category": category,
        })
    return results


def parse_category_rows(page: str) -> list[dict]:
    seen: set[int] = set()
    results = []
    for links in rows_with_links(page):
        for href, text in links:
            if not href.startswith("viewsimfilecategory.php?"):
                continue
            category_id = _id_from(href, "categoryid")
            if category_id is None or category_id in seen or not text:
                continue
            seen.add(category_id)
            results.append({"categoryid": category_id, "category": text})
    return results


def cmd_search(args) -> int:
    kind = "simfile_categories" if args.packs else "simfiles"
    query = urllib.parse.urlencode({"search": args.query, "type": kind})
    page = get_text(f"search.php?{query}", args.delay, args.cookie)

    if args.packs:
        results = parse_category_rows(page)[: args.limit]
        if not results:
            print("no packs found")
            return 1
        for row in results:
            print(f"{row['categoryid']:>6}  {row['category']}")
        print(f"\n{len(results)} pack(s). Download one with: ziv.py get --pack <id>")
    else:
        results = parse_simfile_rows(page)[: args.limit]
        if not results:
            print("no simfiles found")
            return 1
        for row in results:
            artist = f" / {row['artist']}" if row["artist"] else ""
            print(f"{row['simfileid']:>6}  {row['title']}{artist}")
            if row["category"]:
                print(f"        pack {row['categoryid']}: {row['category']}")
        print(f"\n{len(results)} simfile(s). Download one with: ziv.py get <id>")
    return 0


def cmd_latest(args) -> int:
    category = "latest-official" if args.official else "latest-user"
    page = get_text(f"simfiles.php?category={category}", args.delay, args.cookie)
    results = parse_simfile_rows(page)[: args.limit]
    for row in results:
        artist = f" / {row['artist']}" if row["artist"] else ""
        print(f"{row['simfileid']:>6}  {row['title']}{artist}")
        if row["category"]:
            print(f"        pack {row['categoryid']}: {row['category']}")
    return 0 if results else 1


def cmd_info(args) -> int:
    kind, target = resolve(args.target, args.pack, args.delay, args.cookie, probe=True)
    if kind == "pack":
        page = get_text(f"viewsimfilecategory.php?categoryid={target}", args.delay, args.cookie)
        name = title_of(page) or f"category {target}"
        songs = parse_simfile_rows(page)
        print(f"{name}  (pack {target}, {len(songs)} simfile(s))")
        for row in songs[: args.limit]:
            artist = f" / {row['artist']}" if row["artist"] else ""
            print(f"  {row['simfileid']:>6}  {row['title']}{artist}")
        if len(songs) > args.limit:
            print(f"  ... {len(songs) - args.limit} more")
    else:
        page = get_text(f"viewsimfile.php?simfileid={target}", args.delay, args.cookie)
        print(f"{title_of(page) or target}  (simfile {target})")
        for row in parse_category_rows(page)[:1]:
            print(f"  pack {row['categoryid']}: {row['category']}")
    return 0


def title_of(page: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S | re.I)
    return clean(match.group(1)) if match else ""


def cmd_get(args) -> int:
    out = Path(args.out).expanduser()
    tmp = out / ".ziv-downloads"
    failures = 0

    for raw in args.targets:
        kind, target = resolve(raw, args.pack, args.delay, args.cookie,
                               probe=args.dry_run)
        attempts = [kind, "pack"] if (kind == "simfile" and raw.isdigit() and not args.pack) else [kind]

        archive = None
        for index, attempt in enumerate(attempts):
            if attempt == "pack":
                url = f"{BASE}download.php?type=ddrpack&categoryid={target}"
                label = f"pack {target}"
            else:
                url = f"{BASE}download.php?type=ddrsimfile&simfileid={target}"
                label = f"simfile {target}"

            if args.dry_run:
                print(f"would download {label} from {url}")
                break

            tmp.mkdir(parents=True, exist_ok=True)
            try:
                archive = download(url, tmp, args.delay, args.cookie, args.force,
                                   quiet=index < len(attempts) - 1)
            except urllib.error.HTTPError as exc:
                print(f"{label}: HTTP {exc.code} {exc.reason}", file=sys.stderr)
                archive = None
            if archive is not None:
                break
            if index < len(attempts) - 1:
                print(f"  {target} is not a simfile id, trying it as a pack")

        if args.dry_run:
            continue
        if archive is None:
            failures += 1
            continue

        destination = out / args.group if args.group else out
        added = extract(archive, destination, keep_video=not args.no_video, force=args.force)
        if not args.keep_zip:
            archive.unlink(missing_ok=True)
        report(added)

    if tmp.is_dir() and not any(tmp.iterdir()):
        tmp.rmdir()
    return 1 if failures else 0


def resolve(target: str, force_pack: bool, delay: float = 1.5,
            cookie: str | None = None, probe: bool = False) -> tuple[str, int]:
    """Work out whether an id or URL points at a single simfile or a whole pack."""
    if "categoryid=" in target:
        return "pack", int(re.search(r"categoryid=(\d+)", target).group(1))
    if "simfileid=" in target:
        return "simfile", int(re.search(r"simfileid=(\d+)", target).group(1))
    if not target.isdigit():
        raise SystemExit(f"cannot work out what {target!r} is; pass an id or a ZIv URL")

    number = int(target)
    if force_pack:
        return "pack", number
    if not probe:
        return "simfile", number

    page = get_text(f"viewsimfile.php?simfileid={number}", delay, cookie)
    if re.search(rf"type=ddrsimfile&(?:amp;)?simfileid={number}\b", page):
        return "simfile", number
    page = get_text(f"viewsimfilecategory.php?categoryid={number}", delay, cookie)
    if re.search(rf"type=ddrpack&(?:amp;)?categoryid={number}\b", page):
        return "pack", number
    raise SystemExit(f"id {number} is neither a simfile nor a pack on ZIv")


def filename_from(response, fallback: str) -> str:
    disposition = response.headers.get("Content-Disposition", "")
    match = re.search(r'filename="?([^";]+)"?', disposition)
    name = match.group(1).strip() if match else fallback
    return re.sub(r'[\\/:*?"<>|]', "_", name) or fallback


def download(url: str, into: Path, delay: float, cookie: str | None, force: bool,
             quiet: bool = False) -> Path | None:
    with request(url, delay, cookie) as response:
        kind = response.headers.get("Content-Type", "")
        if "zip" not in kind and "octet-stream" not in kind:
            if not quiet:
                body = response.read(400).decode("utf-8", errors="replace")
                print(f"expected a zip, got {kind or 'nothing'}: {clean(body)[:160]}",
                      file=sys.stderr)
            return None

        name = filename_from(response, "simfile.zip")
        target = into / name
        if target.exists() and not force:
            print(f"{name} already downloaded")
            return target

        total = int(response.headers.get("Content-Length") or 0)
        part = target.with_suffix(target.suffix + ".part")
        done = 0
        print(f"downloading {name}" + (f" ({total / 1048576:.1f} MB)" if total else ""))
        next_tick = 0.0
        with part.open("wb") as handle:
            while chunk := response.read(262144):
                handle.write(chunk)
                done += len(chunk)
                now = time.monotonic()
                if now >= next_tick:
                    next_tick = now + 0.2
                    if total:
                        print(f"\r  {done / 1048576:6.1f} / {total / 1048576:.1f} MB"
                              f"  {done * 100 // total:3d}%", end="", flush=True)
                    else:
                        print(f"\r  {done / 1048576:6.1f} MB", end="", flush=True)
        print(f"\r  {done / 1048576:6.1f} MB downloaded" + " " * 20)

    if total and done != total:
        part.unlink(missing_ok=True)
        print(f"{name}: truncated transfer, {done} of {total} bytes", file=sys.stderr)
        return None
    part.replace(target)
    return target


def decode_name(info: zipfile.ZipInfo) -> str:
    """Zip names are cp437 unless flagged utf-8; packs are full of both."""
    if info.flag_bits & 0x800:
        return info.filename
    raw = info.filename.encode("cp437", errors="replace")
    for encoding in ("utf-8", "shift_jis", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return info.filename


def safe_path(name: str) -> PurePosixPath | None:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or any(part in ("..", "") for part in path.parts):
        return None
    if any(junk in name for junk in JUNK):
        return None
    if os.name == "nt":
        # a pack called "What?" or "3:00 AM" cannot be written out as is
        parts = [WINDOWS_ILLEGAL.sub("_", part).rstrip(" .") or "_" for part in path.parts]
        path = PurePosixPath(*parts)
    return path


def extract(archive: Path, out: Path, keep_video: bool, force: bool) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    touched: set[Path] = set()
    skipped_video = 0

    with zipfile.ZipFile(archive) as zf:
        members = []
        for info in zf.infolist():
            if info.is_dir():
                continue
            path = safe_path(decode_name(info))
            if path is None:
                continue
            if not keep_video and path.suffix.lower() in VIDEO_EXT:
                skipped_video += 1
                continue
            members.append((info, path))

        # skip per song folder rather than per archive, so re-running a pack
        # download picks up the songs that were added since last time
        song_dirs = {path.parent for _, path in members
                     if path.suffix.lower() in SIMFILE_EXT and path.parent.parts}
        existing = {d for d in song_dirs if (out / d).is_dir()} if not force else set()
        if existing:
            print(f"  {len(existing)} song(s) already in the library, skipping")
        members = [(info, path) for info, path in members if path.parent not in existing]

        for info, path in members:
            target = out / path
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as source, target.open("wb") as handle:
                shutil.copyfileobj(source, handle)
            if target.suffix.lower() in SIMFILE_EXT:
                touched.add(target.parent)

    if skipped_video and touched:
        print(f"  skipped {skipped_video} background video(s)")
    return sorted(touched)


def report(folders: list[Path]) -> None:
    if not folders:
        print("  nothing new extracted")
        return
    try:
        from ceilidh import simfile
    except ImportError:
        for folder in folders:
            print(f"  + {folder}")
        return

    for folder in folders:
        candidates = [p for ext in SIMFILE_EXT for p in sorted(folder.glob(f"*{ext}"))]
        if not candidates:
            continue
        try:
            song = simfile.load(candidates[0])
        except Exception as exc:  # noqa: BLE001 - a bad simfile is the site's problem
            print(f"  ! {folder.name}: {exc}")
            continue
        singles = song.charts_for("single")
        doubles = song.charts_for("double")
        levels = ", ".join(f"{c.difficulty} {c.meter}" for c in singles)
        extra = f" (+{len(doubles)} doubles)" if doubles else ""
        audio = "" if song.music else "  [no audio file!]"
        print(f"  + {song.display_title} - {song.artist}  {levels}{extra}{audio}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ziv.py", description="Search and download simfiles from Zenius -I- vanisher")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="minimum seconds between requests (default 1.5)")
    parser.add_argument("--cookie", help="cookie header, if you need to be logged in")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="search for simfiles or packs")
    search.add_argument("query")
    search.add_argument("--packs", action="store_true", help="search packs instead of songs")
    search.add_argument("--limit", type=int, default=40)
    search.set_defaults(func=cmd_search)

    latest = sub.add_parser("latest", help="list recently uploaded simfiles")
    latest.add_argument("--official", action="store_true", help="official rips instead of user ones")
    latest.add_argument("--limit", type=int, default=25)
    latest.set_defaults(func=cmd_latest)

    info = sub.add_parser("info", help="show what a simfile or pack contains")
    info.add_argument("target", help="id or ZIv URL")
    info.add_argument("--pack", action="store_true", help="a bare id is a pack, not a simfile")
    info.add_argument("--limit", type=int, default=60)
    info.set_defaults(func=cmd_info)

    get = sub.add_parser("get", help="download and unpack into the song library")
    get.add_argument("targets", nargs="+", help="ids or ZIv URLs")
    get.add_argument("--pack", action="store_true", help="bare ids are packs, not simfiles")
    get.add_argument("--out", default="songs", help="song library directory (default songs)")
    get.add_argument("--group", help="put everything in this subfolder, shown as the pack name")
    get.add_argument("--no-video", action="store_true",
                     help="skip background videos (they are most of the download size)")
    get.add_argument("--keep-zip", action="store_true", help="keep the downloaded archive")
    get.add_argument("--force", action="store_true", help="overwrite songs already in the library")
    get.add_argument("--dry-run", action="store_true")
    get.set_defaults(func=cmd_get)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\ninterrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
