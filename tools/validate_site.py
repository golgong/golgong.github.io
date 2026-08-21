from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
SITE = "https://golgong.github.io"
NEW_EMAIL = "golgong@kakao.com"
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
EXPECTED_ROBOTS = (
    "User-agent: *\nAllow: /\nDisallow: /data/\nDisallow: /tools/\n\n"
    "Sitemap: https://golgong.github.io/sitemap.xml\n"
)
VERIFICATION_FILES = {
    "naver7bbde15a7e92af038251ebca890908dc.html":
        "naver-site-verification: naver7bbde15a7e92af038251ebca890908dc.html\n",
    "googlefacd3b2ba31cd754.html":
        "google-site-verification: googlefacd3b2ba31cd754.html\n",
}


def fail(message: str) -> None:
    raise RuntimeError(message)


def text_hash(node) -> str:
    visible = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
    return hashlib.sha256(visible.encode("utf-8")).hexdigest()


def text_counter(node) -> Counter[str]:
    return Counter(re.sub(r"\s+", " ", text).strip() for text in node.stripped_strings)


def local_file(url: str) -> Path | None:
    if url.startswith(("mailto:", "tel:", "#")):
        return None
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme and parsed.netloc and parsed.netloc != "golgong.github.io":
        return None
    path = urllib.parse.unquote(parsed.path)
    if not path or path == "/":
        return ROOT / "index.html"
    candidate = ROOT / path.lstrip("/")
    if path.endswith("/"):
        candidate /= "index.html"
    return candidate


def main() -> None:
    data = json.loads((ROOT / "data" / "blog.json").read_text(encoding="utf-8"))
    posts = sorted(data["posts"], key=lambda p: (p["date"], p["id"]), reverse=True)
    if len(posts) != 14 or {p["id"] for p in posts} != {21, 24, 43, 45, 78, 97, 122, 124, 128, 134, 138, 141, 144, 150}:
        fail("published post identity mismatch")
    if len({p["description"] for p in posts}) != 14:
        fail("post descriptions are not unique")

    html_files = [ROOT / "index.html", ROOT / "about" / "index.html", ROOT / "404.html"]
    html_files.extend(ROOT / p["path"].lstrip("/") / "index.html" for p in posts)
    missing = [str(path) for path in html_files if not path.is_file()]
    if missing:
        fail(f"missing HTML files: {missing}")
    expected_article_files = {
        (ROOT / post["path"].lstrip("/") / "index.html").resolve() for post in posts
    }
    actual_article_files = {path.resolve() for path in (ROOT / "2026").rglob("index.html")}
    if actual_article_files != expected_article_files:
        fail("stale or missing article HTML files")

    for relative, expected in VERIFICATION_FILES.items():
        path = ROOT / relative
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            fail(f"search verification file changed: {relative}")
    if not (ROOT / ".nojekyll").is_file() or (ROOT / ".nojekyll").read_bytes() != b"":
        fail(".nojekyll missing or changed")
    if (ROOT / "robots.txt").read_text(encoding="utf-8") != EXPECTED_ROBOTS:
        fail("robots.txt content mismatch")

    public_blob = "\n".join(path.read_text(encoding="utf-8") for path in html_files)
    emails = {match.group(0).lower() for match in EMAIL_PATTERN.finditer(public_blob)}
    if emails != {NEW_EMAIL}:
        fail("generated HTML contains an unexpected contact email set")
    if "golgong.wordpress.com/wp-content" in public_blob:
        fail("WordPress media hotlink remains")

    home = BeautifulSoup((ROOT / "index.html").read_text(encoding="utf-8"), "html.parser")
    about_page = BeautifulSoup((ROOT / "about" / "index.html").read_text(encoding="utf-8"), "html.parser")
    if text_hash(about_page.select_one(".article-body")) != data["about"]["text_sha256"]:
        fail("visible about text changed")
    if len(about_page.select("h2.about-section-title")) != 7:
        fail("about section heading structure mismatch")
    for name, page in (("home", home), ("about", about_page)):
        og_image = page.find("meta", attrs={"property": "og:image"})
        if not og_image or local_file(og_image.get("content", "")) is None:
            fail(f"local Open Graph image missing: {name}")
        if not local_file(og_image["content"]).is_file():
            fail(f"Open Graph image file missing: {name}")
    if home.find("link", rel="canonical").get("href") != SITE + "/":
        fail("home canonical mismatch")
    if about_page.find("link", rel="canonical").get("href") != SITE + "/about/":
        fail("about canonical mismatch")
    not_found = BeautifulSoup((ROOT / "404.html").read_text(encoding="utf-8"), "html.parser")
    robots = not_found.find("meta", attrs={"name": "robots"})
    if not robots or robots.get("content") != "noindex,follow":
        fail("404 page must be noindex,follow")
    home_links = home.select("a[data-post-link]")
    home_paths = {a.get("href") for a in home_links}
    expected_paths = {p["path"] for p in posts}
    if len(home_links) != len(posts) or home_paths != expected_paths:
        fail(f"home links differ: {home_paths ^ expected_paths}")
    if len(home.select(".featured-story")) != 1 or len(home.select(".story-card")) != 3 or len(home.select(".archive-row")) != 10:
        fail("home editorial layout mismatch")
    visible_summaries = home.select(".featured-story__body > p:not(.eyebrow), .story-card p")
    if len(visible_summaries) != 4 or any(
        not re.search(r"[.!?]$", summary.get_text(" ", strip=True)) for summary in visible_summaries
    ):
        fail("home contains an incomplete visible summary")

    for path in html_files:
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        if soup.html.get("lang") != "ko":
            fail(f"document language missing: {path}")
        main = soup.select_one("main#main-content")
        skip = soup.select_one('a.skip-link[href="#main-content"]')
        if main is None or skip is None:
            fail(f"skip navigation missing: {path}")

    table_total = 0
    expected_canonicals = {SITE + "/", SITE + "/about/"}
    for post in posts:
        page_path = ROOT / post["path"].lstrip("/") / "index.html"
        soup = BeautifulSoup(page_path.read_text(encoding="utf-8"), "html.parser")
        canonical = SITE + post["path"]
        expected_canonicals.add(canonical)
        if len(soup.find_all("h1")) != 1 or soup.h1.get_text(" ", strip=True) != post["title"]:
            fail(f"h1 mismatch: {post['slug']}")
        if soup.select_one(".article-header .article-dek") is not None:
            fail(f"search excerpt exposed in article header: {post['slug']}")
        canonical_tag = soup.find("link", rel="canonical")
        og_url = soup.find("meta", attrs={"property": "og:url"})
        og_type = soup.find("meta", attrs={"property": "og:type"})
        og_image = soup.find("meta", attrs={"property": "og:image"})
        if not og_image or og_image.get("content") != SITE + post["featured_image"]:
            fail(f"Open Graph image mismatch: {post['slug']}")
        if not canonical_tag or canonical_tag.get("href") != canonical:
            fail(f"canonical mismatch: {post['slug']}")
        if not og_url or og_url.get("content") != canonical or not og_type or og_type.get("content") != "article":
            fail(f"Open Graph mismatch: {post['slug']}")
        schema_node = soup.find("script", attrs={"type": "application/ld+json"})
        schema = json.loads(schema_node.string)
        if schema.get("@type") != "BlogPosting" or schema.get("url") != canonical:
            fail(f"schema mismatch: {post['slug']}")
        if schema.get("datePublished") != post["date"] or schema.get("dateModified") != post["modified"]:
            fail(f"schema date mismatch: {post['slug']}")
        description = soup.find("meta", attrs={"name": "description"}).get("content")
        if description != post["description"] or not 50 <= len(description) <= 170:
            fail(f"description mismatch: {post['slug']}")
        article_body = soup.select_one(".article-body")
        source_body = BeautifulSoup(post["body_html"], "html.parser")
        if text_hash(source_body) != post["text_sha256"]:
            fail(f"source article text hash changed: {post['slug']}")
        if text_counter(article_body) != text_counter(source_body):
            fail(f"visible article text changed: {post['slug']}")
        direct_children = [node for node in article_body.children if getattr(node, "name", None)]
        if (
            not direct_children
            or "article-note" not in direct_children[0].get("class", [])
            or "article-contact" not in direct_children[-1].get("class", [])
        ):
            fail(f"article source/contact order mismatch: {post['slug']}")
        tables = len(article_body.find_all("table"))
        if tables != post["table_count"]:
            fail(f"table count mismatch: {post['slug']}")
        table_regions = article_body.select('figure.wp-block-table[tabindex="0"][role="region"][aria-label]')
        if len(table_regions) != tables:
            fail(f"keyboard-accessible table regions missing: {post['slug']}")
        if any(region.has_attr("style") for region in table_regions):
            fail(f"conflicting inline table layout remains: {post['slug']}")
        table_total += tables

    if table_total != 73:
        fail(f"expected 73 tables, got {table_total}")

    for path in html_files:
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        feed = soup.find("link", rel="alternate", attrs={"type": "application/rss+xml"})
        if not feed or feed.get("href") != SITE + "/feed.xml":
            fail(f"RSS autodiscovery missing: {path}")
        for element, attribute in [(a, "href") for a in soup.find_all("a", href=True)] + [
            (node, "src") for node in soup.find_all(["img", "script"], src=True)
        ] + [(node, "href") for node in soup.find_all("link", href=True)]:
            url = element.get(attribute)
            if url.startswith(("http://", "https://")):
                host = urllib.parse.urlsplit(url).netloc
                if host not in {"golgong.github.io", "schema.org"}:
                    fail(f"unexpected external resource/link in {path}: {url}")
            candidate = local_file(url)
            if candidate is not None and not candidate.is_file():
                fail(f"broken internal link in {path}: {url}")

    if len(data["images"]) != 19:
        fail(f"expected 19 image records, got {len(data['images'])}")
    expected_images = {(ROOT / image["path"].lstrip("/")).resolve() for image in data["images"]}
    actual_images = {path.resolve() for path in (ROOT / "assets" / "images").rglob("*") if path.is_file()}
    if actual_images != expected_images:
        fail("stale or missing image assets")
    for image in data["images"]:
        path = ROOT / image["path"].lstrip("/")
        raw = path.read_bytes()
        if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
            fail(f"not PNG: {path}")
        if hashlib.sha256(raw).hexdigest() != image["sha256"]:
            fail(f"image hash mismatch: {path}")

    sitemap_root = ET.parse(ROOT / "sitemap.xml").getroot()
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    sitemap_nodes = sitemap_root.findall("sm:url/sm:loc", ns)
    sitemap_urls = {node.text for node in sitemap_nodes}
    if len(sitemap_nodes) != len(expected_canonicals):
        fail("sitemap URL count mismatch")
    if sitemap_urls != expected_canonicals:
        fail(f"sitemap mismatch: {sitemap_urls ^ expected_canonicals}")
    if any(not url.startswith(SITE + "/") for url in sitemap_urls):
        fail("cross-host sitemap URL")

    feed_root = ET.parse(ROOT / "feed.xml").getroot()
    feed_items = feed_root.findall("channel/item")
    if len(feed_items) != len(posts):
        fail("feed item count mismatch")
    feed_links = {node.findtext("link") for node in feed_items}
    if feed_links != {SITE + p["path"] for p in posts}:
        fail("feed item links mismatch")
    posts_by_url = {SITE + post["path"]: post for post in posts}
    for item in feed_items:
        url = item.findtext("link")
        body = item.findtext("description") or ""
        if text_hash(BeautifulSoup(body, "html.parser")) != posts_by_url[url]["text_sha256"]:
            fail(f"feed does not contain the full article body: {url}")

    manifest = json.loads((ROOT / "migration-manifest.json").read_text(encoding="utf-8"))
    if manifest["post_count"] != 14 or set(manifest["paths"]) != expected_paths:
        fail("migration manifest mismatch")
    expected_manifest_files = {
        "index.html", "about/index.html", "404.html", "feed.xml", "sitemap.xml",
        "robots.txt", "assets/css/site.css",
        *(post["path"].lstrip("/") + "index.html" for post in posts),
    }
    if set(manifest["files"]) != expected_manifest_files:
        fail("migration manifest file set mismatch")
    for relative, expected_hash in manifest["files"].items():
        path = ROOT / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            fail(f"generated file changed after build: {relative}")

    print("VALIDATED posts=14 tables=73 images=19 sitemap=16 feed=14 links=ok seo=ok")


if __name__ == "__main__":
    main()
