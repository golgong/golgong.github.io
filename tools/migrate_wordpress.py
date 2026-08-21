from __future__ import annotations

import argparse
import hashlib
import html
import json
import mimetypes
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_IDS = {21, 24, 43, 45, 78, 97, 122, 124, 128, 134, 138, 141, 144, 150}
NEW_EMAIL = "golgong@kakao.com"
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
API_ROOT = "https://public-api.wordpress.com/rest/v1.1"


def atomic_write_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_bytes(raw)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def get_json(url: str, headers: dict[str, str]) -> dict:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={**headers, "User-Agent": "golgong-migration/1.0"})
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read())
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    raise RuntimeError(f"GET failed: {url}") from last_error


def download(url: str, destination_stem: Path) -> tuple[Path, str]:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "golgong-migration/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read()
                content_type = response.headers.get_content_type().lower()
            if not content_type.startswith("image/"):
                raise RuntimeError(f"not an image: {content_type}")
            extension = mimetypes.guess_extension(content_type) or Path(urllib.parse.urlsplit(url).path).suffix
            if extension == ".jpe":
                extension = ".jpg"
            if extension not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
                raise RuntimeError(f"unsupported image extension: {extension}")
            path = destination_stem.with_suffix(extension)
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(path, raw)
            return path, hashlib.sha256(raw).hexdigest()
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    raise RuntimeError(f"image download failed: {url}") from last_error


def plain_title(value: str) -> str:
    return html.unescape(BeautifulSoup(value, "html.parser").get_text(" ", strip=True))


def visible_hash(soup: BeautifulSoup) -> str:
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def description_from(soup: BeautifulSoup) -> str:
    parts: list[str] = []
    for node in soup.find_all("p"):
        if node.find_parent("aside", class_="article-note"):
            continue
        style = node.get("style", "").replace(" ", "")
        if "font-weight:800" in style:
            continue
        text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
        if len(text) < 20:
            continue
        parts.append(text)
        if len(" ".join(parts)) >= 150:
            break
    description = " ".join(parts)
    if len(description) > 170:
        description = description[:167].rstrip() + "…"
    if not description:
        raise RuntimeError("could not derive a description")
    return description


def normalize_body(content: str, slug: str, link_map: dict[str, str], image_manifest: list[dict]) -> tuple[str, str, int]:
    emails = {match.group(0).lower() for match in EMAIL_PATTERN.finditer(content)}
    if emails != {NEW_EMAIL}:
        raise RuntimeError(f"unexpected contact email set in authenticated content: {slug}")
    soup = BeautifulSoup(content, "html.parser")
    before_hash = visible_hash(soup)

    first = next((node for node in soup.contents if getattr(node, "name", None)), None)
    if first and first.name == "div" and "wp-block-group" in (first.get("class") or []):
        first.name = "aside"
        first.attrs = {"class": ["article-note"]}

    for paragraph in list(soup.find_all("p")):
        style = paragraph.get("style", "").replace(" ", "")
        if "font-weight:800" in style:
            paragraph.name = "h2"
            paragraph.attrs = {}

    for index, image in enumerate(list(soup.find_all("img")), 1):
        src = image.get("src")
        if not src or not src.startswith("http"):
            continue
        path, digest = download(src, ROOT / "assets" / "images" / slug / f"inline-{index}")
        public_path = "/" + str(path.relative_to(ROOT)).replace("\\", "/")
        image_manifest.append({"source": src, "path": public_path, "sha256": digest})
        image["src"] = public_path
        image["loading"] = "lazy"
        image["decoding"] = "async"
        for attribute in list(image.attrs):
            if attribute in {"srcset", "sizes"} or attribute.startswith("data-"):
                del image.attrs[attribute]
        classes = [c for c in image.get("class", []) if not c.startswith("wp-image-")]
        if classes:
            image["class"] = classes
        elif image.has_attr("class"):
            del image["class"]

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].split("#", 1)[0].rstrip("/") + ("/" if anchor["href"].split("#", 1)[0].endswith("/") else "")
        normalized = href.rstrip("/")
        if normalized in link_map:
            suffix = "#" + anchor["href"].split("#", 1)[1] if "#" in anchor["href"] else ""
            anchor["href"] = link_map[normalized] + suffix

    after_hash = visible_hash(soup)
    if before_hash != after_hash:
        raise RuntimeError(f"visible text changed while normalizing {slug}")
    description = description_from(soup)
    return str(soup), description, len(soup.find_all("table"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token-file", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    token_path = args.token_file.expanduser().resolve()
    repository = ROOT.resolve()
    if token_path == repository or repository in token_path.parents:
        raise RuntimeError("token file must be outside the public repository")
    output = ROOT / "data" / "blog.json"
    if output.exists() and not args.force:
        raise RuntimeError("data/blog.json already exists; pass --force only for an intentional fresh import")

    token = json.loads(token_path.read_text(encoding="utf-8"))
    site = str(token["blog_id"])
    if str(token.get("blog_url", "")).rstrip("/") not in {"https://golgong.wordpress.com", "http://golgong.wordpress.com"}:
        raise RuntimeError("token belongs to another site")
    headers = {"Authorization": "Bearer " + token["access_token"]}

    stamp = int(time.time() * 1000)
    listing = get_json(f"{API_ROOT}/sites/{site}/posts/?number=100&status=publish&type=post&cache_bust={stamp}", headers)
    ids = {int(post["ID"]) for post in listing["posts"]}
    if ids != EXPECTED_IDS or int(listing["found"]) != 14:
        raise RuntimeError(f"unexpected published IDs: {sorted(ids)} found={listing['found']}")

    posts = []
    for post_id in sorted(EXPECTED_IDS):
        current = get_json(f"{API_ROOT}/sites/{site}/posts/{post_id}?context=display&cache_bust={stamp}-{post_id}", headers)
        if current["status"] != "publish" or current["type"] != "post":
            raise RuntimeError(f"post {post_id} is not published")
        posts.append(current)
    about = get_json(f"{API_ROOT}/sites/{site}/posts/1?context=display&cache_bust={stamp}-about", headers)
    if about["status"] != "publish" or about["type"] != "page" or about["slug"] != "about":
        raise RuntimeError("about page identity changed")

    link_map: dict[str, str] = {
        "https://golgong.wordpress.com": "/",
        "https://golgong.wordpress.com/about": "/about/",
    }
    for current in posts:
        old_url = current["URL"].rstrip("/")
        path = urllib.parse.urlsplit(current["URL"]).path
        if not re.fullmatch(r"/\d{4}/\d{2}/\d{2}/[a-z0-9-]+/", path):
            raise RuntimeError(f"unexpected WordPress path: {path}")
        link_map[old_url] = path

    image_manifest: list[dict] = []
    exported_posts = []
    total_tables = 0
    for current in posts:
        slug = current["slug"]
        body_html, description, table_count = normalize_body(current["content"], slug, link_map, image_manifest)
        total_tables += table_count
        featured_path, featured_hash = download(
            current["featured_image"], ROOT / "assets" / "images" / slug / "featured"
        )
        featured_public = "/" + str(featured_path.relative_to(ROOT)).replace("\\", "/")
        image_manifest.append({"source": current["featured_image"], "path": featured_public, "sha256": featured_hash})
        exported_posts.append({
            "id": int(current["ID"]),
            "slug": slug,
            "title": plain_title(current["title"]),
            "date": current["date"],
            "modified": current["modified"],
            "old_url": current["URL"],
            "path": urllib.parse.urlsplit(current["URL"]).path,
            "description": description,
            "featured_image": featured_public,
            "body_html": body_html,
            "text_sha256": visible_hash(BeautifulSoup(body_html, "html.parser")),
            "table_count": table_count,
        })

    about_html, _, _ = normalize_body(about["content"], "about", link_map, image_manifest)
    data = {
        "version": 1,
        "source": {
            "site": "https://golgong.wordpress.com",
            "site_id": int(site),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "published_ids": sorted(EXPECTED_IDS),
        },
        "posts": exported_posts,
        "about": {
            "id": int(about["ID"]),
            "slug": about["slug"],
            "modified": about["modified"],
            "body_html": about_html,
            "text_sha256": visible_hash(BeautifulSoup(about_html, "html.parser")),
        },
        "images": image_manifest,
    }
    # 14 featured images, one inline image in POST 21, and four images on About.
    if len(image_manifest) != 19:
        raise RuntimeError(f"expected 19 images, got {len(image_manifest)}")
    if total_tables != 73:
        raise RuntimeError(f"expected 73 tables, got {total_tables}")
    atomic_write_text(output, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"EXPORTED posts={len(exported_posts)} tables={total_tables} images={len(image_manifest)}")


if __name__ == "__main__":
    main()
