"""One-time raw downloads. Raw files are immutable — never modified after fetch."""
import shutil
import urllib.request
from pathlib import Path

from .config import resolve

USER_AGENT = "Mozilla/5.0 (portfolio-etl)"


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")  # no half-written final files
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as out:
        shutil.copyfileobj(resp, out)
    tmp.replace(dest)


def fetch_file(url: str, dest_str: str) -> Path:
    dest = resolve(dest_str)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[fetch] present: {dest.name} ({dest.stat().st_size:,} bytes)")
        return dest
    print(f"[fetch] downloading {url}")
    _download(url, dest)
    print(f"[fetch] saved: {dest.name} ({dest.stat().st_size:,} bytes)")
    return dest


def fetch(cfg: dict) -> tuple[Path, Path]:
    trips = fetch_file(cfg["source"]["trips"]["url"], cfg["source"]["trips"]["file"])
    zones = fetch_file(cfg["source"]["zones"]["url"], cfg["source"]["zones"]["file"])
    return trips, zones
