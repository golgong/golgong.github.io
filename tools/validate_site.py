from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

from update_visitor_stats import validate_summary


ROOT = Path(__file__).resolve().parents[1]
SITE = "https://golgong.github.io"
SITE_NAME = "골때리는공작소"
HOME_HERO = "/assets/images/home/hero-v2.jpg"
HOME_OG = "/assets/images/home/og-v2.jpg"
HOME_OG_ALT = f"{SITE_NAME} — 아무도 세어 보지 않은 것을 끝까지 확인합니다"
NEW_EMAIL = "golgong@kakao.com"
GA_MEASUREMENT_ID_PATTERN = re.compile(r"G-[A-Z0-9]{6,20}")
SERVICE_HEADLINE = "필요한 자료를 대신 분석해 드립니다."
OLD_ARTICLE_SERVICE_HEADLINE = "골때리는공작소는 이런 일을 대신해 드립니다."
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


def validate_social_image(page: BeautifulSoup, expected_url: str, expected_alt: str) -> None:
    expected_properties = {
        "og:image": expected_url,
        "og:image:width": "1200",
        "og:image:height": "630",
        "og:image:type": "image/jpeg",
        "og:image:alt": expected_alt,
    }
    for property_name, expected in expected_properties.items():
        node = page.find("meta", attrs={"property": property_name})
        if node is None or node.get("content") != expected:
            fail(f"social image metadata mismatch: {property_name}")
    expected_names = {
        "twitter:image": expected_url,
        "twitter:image:alt": expected_alt,
    }
    for name, expected in expected_names.items():
        node = page.find("meta", attrs={"name": name})
        if node is None or node.get("content") != expected:
            fail(f"social image metadata mismatch: {name}")


def main() -> None:
    data = json.loads((ROOT / "data" / "blog.json").read_text(encoding="utf-8"))
    posts = sorted(data["posts"], key=lambda p: (p["date"], p["id"]), reverse=True)
    if len(posts) != 14 or {p["id"] for p in posts} != {21, 24, 43, 45, 78, 97, 122, 124, 128, 134, 138, 141, 144, 150}:
        fail("published post identity mismatch")
    if len({p["description"] for p in posts}) != 14:
        fail("post descriptions are not unique")

    html_files = [
        ROOT / "index.html", ROOT / "about" / "index.html",
        ROOT / "privacy" / "index.html", ROOT / "404.html",
    ]
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

    analytics_config = json.loads((ROOT / "data" / "analytics.json").read_text(encoding="utf-8"))
    if set(analytics_config) != {"measurement_id"}:
        fail("analytics config keys mismatch")
    measurement_id = str(analytics_config["measurement_id"] or "").strip().upper()
    if not GA_MEASUREMENT_ID_PATTERN.fullmatch(measurement_id):
        fail("invalid Google Analytics measurement ID")
    validate_summary(json.loads((ROOT / "data" / "visitor-stats.json").read_text(encoding="utf-8")))

    public_blob = "\n".join(path.read_text(encoding="utf-8") for path in html_files)
    emails = {match.group(0).lower() for match in EMAIL_PATTERN.finditer(public_blob)}
    if emails != {NEW_EMAIL}:
        fail("generated HTML contains an unexpected contact email set")
    if "golgong.wordpress.com/wp-content" in public_blob:
        fail("WordPress media hotlink remains")
    if OLD_ARTICLE_SERVICE_HEADLINE in public_blob:
        fail("old service headline remains in generated HTML")
    if public_blob.count(SERVICE_HEADLINE) < len(posts) + 1:
        fail("new service headline is missing from generated HTML")

    home = BeautifulSoup((ROOT / "index.html").read_text(encoding="utf-8"), "html.parser")
    about_page = BeautifulSoup((ROOT / "about" / "index.html").read_text(encoding="utf-8"), "html.parser")
    privacy_page = BeautifulSoup((ROOT / "privacy" / "index.html").read_text(encoding="utf-8"), "html.parser")
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
    validate_social_image(home, SITE + HOME_OG, HOME_OG_ALT)
    home_hero = home.select_one(".home-hero img")
    if (
        home_hero is None
        or home_hero.get("src") != HOME_HERO
        or home_hero.get("width") != "1448"
        or home_hero.get("height") != "1086"
    ):
        fail("home hero image mismatch")
    home_schema_node = home.find("script", attrs={"type": "application/ld+json"})
    home_schema = json.loads(home_schema_node.string)
    if home_schema.get("@type") != "WebSite" or home_schema.get("image") != SITE + HOME_OG:
        fail("home WebSite schema image mismatch")
    if home.find("link", rel="canonical").get("href") != SITE + "/":
        fail("home canonical mismatch")
    if about_page.find("link", rel="canonical").get("href") != SITE + "/about/":
        fail("about canonical mismatch")
    if privacy_page.find("link", rel="canonical").get("href") != SITE + "/privacy/":
        fail("privacy canonical mismatch")
    privacy_robots = privacy_page.find("meta", attrs={"name": "robots"})
    if not privacy_robots or privacy_robots.get("content") != "noindex,follow":
        fail("privacy page must be noindex,follow")
    if privacy_page.select_one("[data-analytics-settings]") is None:
        fail("privacy analytics settings control missing")
    not_found = BeautifulSoup((ROOT / "404.html").read_text(encoding="utf-8"), "html.parser")
    robots = not_found.find("meta", attrs={"name": "robots"})
    if not robots or robots.get("content") != "noindex,follow":
        fail("404 page must be noindex,follow")
    home_links = home.select("a[data-post-link]")
    home_paths = {a.get("href") for a in home_links}
    expected_paths = {p["path"] for p in posts}
    if len(home_links) != len(posts) or home_paths != expected_paths:
        fail(f"home links differ: {home_paths ^ expected_paths}")
    if home.select_one(".home-intro h1").get_text(" ", strip=True) != "질문. 자료. 확인.":
        fail("home declaration mismatch")
    if home.select_one(".home-manifesto .home-hero") is None:
        fail("home manifesto layout missing")
    journal_rows = home.select(".journal-row")
    if (
        len(journal_rows) != len(posts)
        or len(home.select(".journal-row--feature")) != 4
        or len(home.select(".journal-row--reverse")) != 2
        or len(home.select(".journal-row--compact")) != len(posts) - 4
    ):
        fail("home alternating journal layout mismatch")
    home_images = home.select(".journal-row__image img")
    expected_home_images = {post["featured_image"] for post in posts}
    if len(home_images) != 14 or {image.get("src") for image in home_images} != expected_home_images:
        fail("home editorial image set mismatch")
    if any(image.get("loading") != "lazy" for image in home_images):
        fail("journal images below the home hero must load lazily")
    for row in journal_rows:
        if (
            row.select_one("h2.visually-hidden") is None
            or row.select_one(".journal-row__summary") is None
            or row.select_one(".journal-row__meta time") is None
            or row.select_one(".journal-row__meta .outline-link") is None
        ):
            fail("home journal row content mismatch")
    visitor_strip = home.select_one("[data-visitor-stats]")
    if visitor_strip is None or visitor_strip.select_one("[data-visitor-summary]") is None:
        fail("home visitor statistics strip missing")
    if home.select_one("#service-heading").get_text(" ", strip=True) != SERVICE_HEADLINE:
        fail("home service headline mismatch")
    visible_summaries = home.select(".journal-row__summary")
    if len(visible_summaries) != 14 or any(
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
        analytics_meta = soup.find_all("meta", attrs={"name": "google-analytics-id"})
        analytics_scripts = soup.find_all(
            "script",
            src=f"https://www.googletagmanager.com/gtag/js?id={measurement_id}",
        )
        site_scripts = soup.find_all("script", src=re.compile(r"^/assets/js/site\.js\?v="))
        if len(analytics_meta) != 1 or analytics_meta[0].get("content") != measurement_id:
            fail(f"Google Analytics measurement ID mismatch: {path}")
        if len(analytics_scripts) != 1 or not analytics_scripts[0].has_attr("async"):
            fail(f"Google Analytics tag is not statically detectable: {path}")
        head_text = path.read_text(encoding="utf-8")
        if (
            f'window["ga-disable-{measurement_id}"] = true;' not in head_text
            or 'window.gtag("consent", "default"' not in head_text
            or 'analytics_storage: "denied"' not in head_text
            or 'send_page_view: false' not in head_text
        ):
            fail(f"Google Analytics consent bootstrap mismatch: {path}")
        if len(site_scripts) != 1:
            fail(f"site JavaScript loader mismatch: {path}")
        if soup.select_one("[data-analytics-settings]") is None:
            fail(f"analytics settings control missing: {path}")

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
        validate_social_image(soup, SITE + post["og_image"], post["title"])
        if not canonical_tag or canonical_tag.get("href") != canonical:
            fail(f"canonical mismatch: {post['slug']}")
        if not og_url or og_url.get("content") != canonical or not og_type or og_type.get("content") != "article":
            fail(f"Open Graph mismatch: {post['slug']}")
        schema_node = soup.find("script", attrs={"type": "application/ld+json"})
        schema = json.loads(schema_node.string)
        if schema.get("@type") != "BlogPosting" or schema.get("url") != canonical:
            fail(f"schema mismatch: {post['slug']}")
        if schema.get("image") != [SITE + post["og_image"]]:
            fail(f"schema image mismatch: {post['slug']}")
        if schema.get("datePublished") != post["date"] or schema.get("dateModified") != post["modified"]:
            fail(f"schema date mismatch: {post['slug']}")
        description = soup.find("meta", attrs={"name": "description"}).get("content")
        if description != post["description"] or not 50 <= len(description) <= 170:
            fail(f"description mismatch: {post['slug']}")
        hero_image = soup.select_one(".hero img")
        if hero_image is None or hero_image.get("src") != post["featured_image"]:
            fail(f"article hero image mismatch: {post['slug']}")
        article_body = soup.select_one(".article-body")
        source_body = BeautifulSoup(post["body_html"], "html.parser")
        if text_hash(source_body) != post["text_sha256"]:
            fail(f"source article text hash changed: {post['slug']}")
        public_source_body = BeautifulSoup(
            post["body_html"].replace(OLD_ARTICLE_SERVICE_HEADLINE, SERVICE_HEADLINE),
            "html.parser",
        )
        if text_counter(article_body) != text_counter(public_source_body):
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
                if host not in {"golgong.github.io", "schema.org", "www.googletagmanager.com"}:
                    fail(f"unexpected external resource/link in {path}: {url}")
            candidate = local_file(url)
            if candidate is not None and not candidate.is_file():
                fail(f"broken internal link in {path}: {url}")

    if len(data["images"]) != 35:
        fail(f"expected 35 image records, got {len(data['images'])}")
    expected_images = {(ROOT / image["path"].lstrip("/")).resolve() for image in data["images"]}
    actual_images = {path.resolve() for path in (ROOT / "assets" / "images").rglob("*") if path.is_file()}
    if actual_images != expected_images:
        fail("stale or missing image assets")
    for image in data["images"]:
        path = ROOT / image["path"].lstrip("/")
        raw = path.read_bytes()
        if path.suffix.lower() == ".png":
            if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                fail(f"not PNG: {path}")
        elif path.suffix.lower() == ".webp":
            if not (raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"):
                fail(f"not WebP: {path}")
        elif path.suffix.lower() in {".jpg", ".jpeg"}:
            if not raw.startswith(b"\xff\xd8\xff"):
                fail(f"not JPEG: {path}")
        else:
            fail(f"unsupported image type: {path}")
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
        post = posts_by_url[url]
        expected_body = BeautifulSoup(
            post["body_html"].replace(OLD_ARTICLE_SERVICE_HEADLINE, SERVICE_HEADLINE),
            "html.parser",
        )
        if text_counter(BeautifulSoup(body, "html.parser")) != text_counter(expected_body):
            fail(f"feed does not contain the full article body: {url}")

    site_css = (ROOT / "assets" / "css" / "site.css").read_text(encoding="utf-8")
    site_js = (ROOT / "assets" / "js" / "site.js").read_text(encoding="utf-8")
    numeric_weights = [int(weight) for weight in re.findall(r"font-weight:\s*(\d+)", site_css)]
    if numeric_weights and max(numeric_weights) > 500:
        fail("site typography exceeds the approved maximum font weight")
    if "font-synthesis: none" not in site_css:
        fail("synthetic bold protection is missing")
    if "https://www.googletagmanager.com/gtag/js" in site_js:
        fail("Google Analytics must not be injected dynamically")
    if "innerHTML" in site_js:
        fail("site JavaScript must not render visitor data with innerHTML")
    if (
        "ga-disable-${measurementId}" not in site_js
        or 'analytics_storage: "granted"' not in site_js
        or 'window.gtag("event", "page_view"' not in site_js
    ):
        fail("Google Analytics consent revocation or restoration is missing")
    expected_css_href = f"/assets/css/site.css?v={hashlib.sha256(site_css.encode('utf-8')).hexdigest()[:12]}"
    expected_js_src = f"/assets/js/site.js?v={hashlib.sha256(site_js.encode('utf-8')).hexdigest()[:12]}"
    for path in html_files:
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        stylesheet = soup.find("link", rel="stylesheet")
        if stylesheet is None or stylesheet.get("href") != expected_css_href:
            fail(f"stylesheet cache key mismatch: {path}")
        script = soup.find("script", src=re.compile(r"^/assets/js/site\.js\?v="))
        if script is None or script.get("src") != expected_js_src:
            fail(f"JavaScript cache key mismatch: {path}")

    manifest = json.loads((ROOT / "migration-manifest.json").read_text(encoding="utf-8"))
    if manifest["post_count"] != 14 or set(manifest["paths"]) != expected_paths:
        fail("migration manifest mismatch")
    expected_manifest_files = {
        "index.html", "about/index.html", "privacy/index.html", "404.html",
        "feed.xml", "sitemap.xml", "robots.txt", "assets/css/site.css",
        "assets/js/site.js",
        *(post["path"].lstrip("/") + "index.html" for post in posts),
    }
    if set(manifest["files"]) != expected_manifest_files:
        fail("migration manifest file set mismatch")
    for relative, expected_hash in manifest["files"].items():
        path = ROOT / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            fail(f"generated file changed after build: {relative}")

    print("VALIDATED posts=14 tables=73 images=35 sitemap=16 feed=14 links=ok seo=ok")


if __name__ == "__main__":
    main()
