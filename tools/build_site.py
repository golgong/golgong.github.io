from __future__ import annotations

import hashlib
import html
import os
import json
import re
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urljoin


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "blog.json"
SITE_URL = "https://golgong.github.io"
SITE_NAME = "골때리는공작소"
CONTACT = "golgong@kakao.com"
SERVICE_HEADLINE = "필요한 자료를 대신 분석해 드립니다."
OLD_ARTICLE_SERVICE_HEADLINE = "골때리는공작소는 이런 일을 대신해 드립니다."
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def display_summary(value: str) -> str:
    """Keep only complete sentences when metadata is visibly excerpted."""
    value = compact_text(value)
    sentences = [match.group(0).strip() for match in re.finditer(r".*?[.!?](?=\s|$)", value)]
    if not sentences:
        return value
    selected = sentences[:2]
    if len(" ".join(selected)) < 60 and len(sentences) > 2:
        selected.append(sentences[2])
    return " ".join(selected)


def enhance_tables(body_html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        attributes = re.sub(r'\s+style="[^"]*"', "", match.group(2))
        return (
            f'<figure class="{match.group(1)}"{attributes} tabindex="0" role="region" '
            'aria-label="데이터 표. 좌우로 이동해 볼 수 있습니다.">'
        )

    return re.sub(
        r'<figure class="([^"]*\bwp-block-table\b[^"]*)"([^>]*)>',
        replace,
        body_html,
    )


def enhance_article(body_html: str) -> str:
    body_html = body_html.replace(OLD_ARTICLE_SERVICE_HEADLINE, SERVICE_HEADLINE)
    pattern = re.compile(
        r'<aside class="article-note">\s*(<p\b.*?</p>)\s*(<p\b.*?</p>)\s*</aside>',
        re.DOTALL,
    )
    match = pattern.search(body_html)
    if match is None:
        raise RuntimeError("article note structure mismatch")
    source_note, contact_note = match.groups()
    body_html = pattern.sub(
        f'<aside class="article-note">{source_note}</aside>',
        body_html,
        count=1,
    )
    body_html = body_html.rstrip() + f'\n<aside class="article-contact">{contact_note}</aside>'
    return enhance_tables(body_html)


def enhance_about(body_html: str) -> str:
    body_html = enhance_tables(body_html)
    return re.sub(
        r'<p\b[^>]*>\s*<strong>([^<]+)</strong>\s*</p>',
        r'<h2 class="about-section-title">\1</h2>',
        body_html,
    )


def json_script(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def page_head(*, title: str, description: str, canonical: str, og_type: str,
              image: str | None = None, published: str | None = None,
              modified: str | None = None, schema: object | None = None,
              robots: str = "index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1") -> str:
    image_tags = ""
    if image:
        image_tags = (
            f'\n<meta property="og:image" content="{esc(image)}">'
            f'\n<meta name="twitter:card" content="summary_large_image">'
            f'\n<meta name="twitter:image" content="{esc(image)}">'
        )
    article_tags = ""
    if published:
        article_tags += f'\n<meta property="article:published_time" content="{esc(published)}">'
    if modified:
        article_tags += f'\n<meta property="article:modified_time" content="{esc(modified)}">'
    schema_tag = f'\n<script type="application/ld+json">{json_script(schema)}</script>' if schema else ""
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#f3f0e9">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="robots" content="{esc(robots)}">
<link rel="canonical" href="{esc(canonical)}">
<link rel="alternate" type="application/rss+xml" title="{SITE_NAME}" href="{SITE_URL}/feed.xml">
<link rel="stylesheet" href="/assets/css/site.css">
<meta property="og:locale" content="ko_KR">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:type" content="{esc(og_type)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">{image_tags}{article_tags}
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">{schema_tag}
</head>"""


def site_header(active: str = "") -> str:
    home_current = ' aria-current="page"' if active == "home" else ""
    about_current = ' aria-current="page"' if active == "about" else ""
    return f"""<a class="skip-link" href="#main-content">본문으로 바로가기</a>
<header class="site-header">
  <div class="site-header__inner">
    <a class="brand" href="/" aria-label="{SITE_NAME} 홈"><span class="brand__mark" aria-hidden="true"></span>{SITE_NAME}</a>
    <nav aria-label="주요 메뉴">
      <a href="/"{home_current}>전체 글</a>
      <a href="/about/"{about_current}>소개</a>
    </nav>
  </div>
</header>"""


def site_footer() -> str:
    return f"""<footer class="site-footer">
  <div class="site-footer__inner">
    <div><strong>{SITE_NAME}</strong><p>공공데이터와 공개 API에서 자료를 모아 직접 세어 봅니다.</p></div>
    <a href="/about/">작업 방식과 문의</a>
  </div>
</footer>"""


def article_schema(post: dict) -> dict:
    canonical = SITE_URL + post["path"]
    schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
        "headline": post["title"],
        "description": post["description"],
        "datePublished": post["date"],
        "dateModified": post["modified"],
        "inLanguage": "ko-KR",
        "author": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL + "/about/"},
        "publisher": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL + "/"},
        "url": canonical,
    }
    if post.get("featured_image"):
        schema["image"] = [SITE_URL + post["featured_image"]]
    return schema


def render_article(post: dict, posts: list[dict]) -> str:
    canonical = SITE_URL + post["path"]
    image = SITE_URL + post["featured_image"] if post.get("featured_image") else None
    current = posts.index(post)
    neighbors = []
    if current > 0:
        neighbors.append(("다음 글", posts[current - 1]))
    if current + 1 < len(posts):
        neighbors.append(("이전 글", posts[current + 1]))
    neighbor_html = "".join(
        f'<a href="{esc(other["path"])}"><span>{label}</span><strong>{esc(other["title"])}</strong></a>'
        for label, other in neighbors
    )
    hero = ""
    if post.get("featured_image"):
        hero = (
            f'<figure class="hero"><img src="{esc(post["featured_image"])}" '
            f'alt="{esc(post["title"])} 분석 포스터" width="2048" height="1536"></figure>'
        )
    return f"""{page_head(
        title=post["title"], description=post["description"], canonical=canonical,
        og_type="article", image=image, published=post["date"], modified=post["modified"],
        schema=article_schema(post),
    )}
<body>
{site_header()}
<main id="main-content" class="article-shell" tabindex="-1">
  <article>
    <header class="article-header">
      <p class="eyebrow">공개 데이터 분석</p>
      <h1>{esc(post["title"])}</h1>
      <div class="article-meta"><time datetime="{esc(post["date"])}">{esc(post["date"][:10])}</time><span>자료 수집·가공</span></div>
    </header>
    {hero}
    <div class="article-body">
{enhance_article(post["body_html"])}
    </div>
  </article>
  <section class="post-nav-wrap" aria-labelledby="continue-heading">
    <h2 id="continue-heading" class="eyebrow">이어서 읽기</h2>
    <nav class="post-nav" aria-label="다른 글">{neighbor_html}</nav>
  </section>
</main>
{site_footer()}
</body>
</html>
"""


def render_index(posts: list[dict]) -> str:
    description = f"공공데이터와 공개 API에서 자료를 모아 직접 세어 본 결과를 공개합니다. {SERVICE_HEADLINE}"
    latest_image = SITE_URL + posts[0]["featured_image"] if posts and posts[0].get("featured_image") else None
    schema = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": SITE_NAME,
        "url": SITE_URL + "/",
        "description": description,
        "inLanguage": "ko-KR",
        "publisher": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL + "/about/"},
    }
    featured = posts[0]
    featured_thumb = ""
    if featured.get("featured_image"):
        featured_thumb = f'<img src="{esc(featured["featured_image"])}" alt="" width="1024" height="768">'

    recent_cards = []
    for post in posts[1:4]:
        thumb = ""
        if post.get("featured_image"):
            thumb = f'<img src="{esc(post["featured_image"])}" alt="" width="640" height="480" loading="lazy">'
        recent_cards.append(f"""<article class="story-card">
  <a class="story-card__image" href="{esc(post["path"])}" tabindex="-1" aria-hidden="true">{thumb}</a>
  <div class="story-card__body"><time datetime="{esc(post["date"])}">{esc(post["date"][:10])}</time>
  <h3><a data-post-link href="{esc(post["path"])}">{esc(post["title"])}</a></h3>
  <p>{esc(display_summary(post["description"]))}</p></div>
</article>""")

    archive_rows = []
    for post in posts[4:]:
        archive_rows.append(f"""<article class="archive-row">
  <time datetime="{esc(post["date"])}">{esc(post["date"][:10])}</time>
  <h3><a data-post-link href="{esc(post["path"])}">{esc(post["title"])}</a></h3>
  <span aria-hidden="true">→</span>
</article>""")
    return f"""{page_head(
        title=f"{SITE_NAME} — 공공데이터를 직접 세어 봅니다",
        description=description, canonical=SITE_URL + "/", og_type="website",
        image=latest_image, schema=schema,
    )}
<body>
{site_header("home")}
<main id="main-content" class="home-shell" tabindex="-1">
  <section class="home-intro">
    <div>
      <p class="eyebrow">공개 데이터 기록 · {len(posts)}편</p>
      <h1>아무도 세어 보지 않은 것을<br>끝까지 확인합니다</h1>
    </div>
    <p>공공데이터와 공개 API에서 자료를 모아 직접 세어 보고, 확인된 결과만 씁니다.</p>
  </section>

  <section class="featured-story" aria-labelledby="featured-heading">
    <a class="featured-story__image" href="{esc(featured["path"])}" tabindex="-1" aria-hidden="true">{featured_thumb}</a>
    <div class="featured-story__body">
      <p class="eyebrow">가장 최근 기록</p>
      <h2 id="featured-heading"><a data-post-link href="{esc(featured["path"])}">{esc(featured["title"])}</a></h2>
      <p>{esc(display_summary(featured["description"]))}</p>
      <div class="story-meta"><time datetime="{esc(featured["date"])}">{esc(featured["date"][:10])}</time><a href="{esc(featured["path"])}">글 읽기 <span aria-hidden="true">→</span></a></div>
    </div>
  </section>

  <section class="recent-section" aria-labelledby="recent-heading">
    <div class="section-heading"><p class="eyebrow">새 글</p><h2 id="recent-heading">최근에 확인한 결과</h2></div>
    <div class="story-grid">{''.join(recent_cards)}</div>
  </section>

  <section class="archive-section" aria-labelledby="archive-heading">
    <div class="section-heading"><p class="eyebrow">기록 보관함</p><h2 id="archive-heading">지난 글</h2></div>
    <div class="archive-list">{''.join(archive_rows)}</div>
  </section>

  <section class="service-panel" aria-labelledby="service-heading">
    <p class="eyebrow">데이터 수집·가공</p>
    <h2 id="service-heading">{SERVICE_HEADLINE}</h2>
    <p>여러 사이트에 흩어진 자료를 모아 엑셀이나 데이터베이스로 정리하고, 반복 수집 프로그램도 만듭니다.</p>
    <a class="text-link" href="mailto:{CONTACT}">{CONTACT} <span aria-hidden="true">→</span></a>
  </section>
</main>
{site_footer()}
</body>
</html>
"""


def render_about(about: dict) -> str:
    description = "골때리는공작소는 공공데이터와 공개 API에서 자료를 모아 세어 보고, 확인된 결과를 공개합니다."
    image_match = re.search(r'<img\b[^>]*\bsrc="([^"]+)"', about["body_html"])
    image = SITE_URL + image_match.group(1) if image_match else None
    schema = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": SITE_NAME,
        "url": SITE_URL + "/about/",
        "email": CONTACT,
        "description": description,
    }
    return f"""{page_head(
        title=f"소개 | {SITE_NAME}", description=description,
        canonical=SITE_URL + "/about/", og_type="website", image=image, schema=schema,
    )}
<body>
{site_header("about")}
<main id="main-content" class="article-shell about-shell" tabindex="-1">
  <article>
    <header class="article-header"><p class="eyebrow">소개</p><h1>{SITE_NAME}</h1><p class="article-dek">공개된 자료를 모으고, 확인하고, 다시 쓸 수 있는 형태로 정리합니다.</p></header>
    <div class="article-body">{enhance_about(about["body_html"])}</div>
  </article>
</main>
{site_footer()}
</body>
</html>
"""


def render_feed(posts: list[dict]) -> str:
    items = []
    for post in posts:
        url = SITE_URL + post["path"]
        published = format_datetime(datetime.fromisoformat(post["date"]))
        body = post["body_html"].replace(
            OLD_ARTICLE_SERVICE_HEADLINE, SERVICE_HEADLINE
        ).replace("]]>", "]]]]><![CDATA[>")
        items.append(f"""<item>
  <title>{esc(post["title"])}</title>
  <link>{esc(url)}</link>
  <guid isPermaLink="true">{esc(url)}</guid>
  <pubDate>{published}</pubDate>
  <description><![CDATA[{body}]]></description>
</item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>{SITE_NAME}</title>
  <link>{SITE_URL}/</link>
  <description>공공데이터와 공개 API에서 자료를 모아 직접 세어 본 결과</description>
  <language>ko-KR</language>
  <atom:link href="{SITE_URL}/feed.xml" rel="self" type="application/rss+xml" />
  {''.join(items)}
</channel>
</rss>
"""


def render_sitemap(posts: list[dict], about: dict) -> str:
    urls = [(SITE_URL + "/", max(p["modified"] for p in posts)[:10]),
            (SITE_URL + "/about/", about["modified"][:10])]
    urls.extend((SITE_URL + post["path"], post["modified"][:10]) for post in posts)
    rows = "".join(
        f"  <url><loc>{esc(url)}</loc><lastmod>{esc(lastmod)}</lastmod></url>\n"
        for url, lastmod in urls
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{rows}</urlset>
"""


CSS = r"""
:root {
  --paper: #f3f0e9;
  --surface: #fffdfa;
  --surface-muted: #eae5dc;
  --ink: #1b1c1a;
  --muted: #686861;
  --line: #d3cec3;
  --accent: #d8531d;
  --accent-dark: #a83a10;
  --dark: #20221f;
  --content: 760px;
  --wide: 1160px;
}
* { box-sizing: border-box; }
html { overflow-x: clip; color-scheme: light; scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif;
  font-size: 16px;
  line-height: 1.75;
  letter-spacing: -.012em;
  word-break: keep-all;
}
#main-content { scroll-margin-top: 88px; }
a {
  color: var(--accent-dark);
  text-decoration-thickness: 1px;
  text-underline-offset: 4px;
}
a:hover { color: var(--accent-dark); text-decoration-thickness: 2px; }
img { max-width: 100%; height: auto; }
time, table { font-variant-numeric: tabular-nums; }
::selection { background: #f2c5ae; color: var(--ink); }
:focus-visible { outline: 3px solid var(--accent); outline-offset: 4px; }
.skip-link {
  position: fixed;
  top: 12px;
  left: 12px;
  z-index: 100;
  padding: 10px 14px;
  background: var(--ink);
  color: #fff;
  transform: translateY(-160%);
  text-decoration: none;
}
.skip-link:focus { transform: translateY(0); }
.site-header {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(243, 240, 233, .94);
  border-bottom: 1px solid rgba(27, 28, 26, .12);
  backdrop-filter: blur(18px);
}
.site-header__inner {
  width: min(var(--wide), calc(100% - 48px));
  min-height: 72px;
  margin: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: 11px;
  color: var(--ink);
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -.035em;
  text-decoration: none;
}
.brand:hover { color: var(--ink); }
.brand__mark {
  width: 11px;
  height: 11px;
  background: var(--accent);
  border-radius: 50%;
  box-shadow: 0 0 0 5px rgba(216, 83, 29, .12);
}
.site-header nav { display: flex; align-items: center; gap: 28px; }
.site-header nav a {
  position: relative;
  padding: 22px 0;
  color: var(--muted);
  font-size: 14px;
  font-weight: 700;
  text-decoration: none;
}
.site-header nav a:hover,
.site-header nav a[aria-current="page"] { color: var(--ink); }
.site-header nav a[aria-current="page"]::after {
  content: "";
  position: absolute;
  right: 0;
  bottom: -1px;
  left: 0;
  height: 2px;
  background: var(--accent);
}
.home-shell {
  width: min(var(--wide), calc(100% - 48px));
  margin: auto;
  padding: 76px 0 112px;
}
.home-intro {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(260px, .7fr);
  align-items: end;
  gap: 72px;
  padding: 14px 0 68px;
  border-bottom: 1px solid var(--line);
}
.eyebrow {
  margin: 0 0 13px;
  color: var(--accent-dark);
  font-size: 12px;
  font-weight: 850;
  letter-spacing: .12em;
  line-height: 1.4;
  text-transform: uppercase;
}
.home-intro h1,
.article-header h1 {
  margin: 0;
  color: var(--ink);
  font-weight: 820;
  letter-spacing: -.055em;
  line-height: 1.15;
}
.home-intro h1 { font-size: clamp(38px, 5.4vw, 62px); }
.home-intro > p {
  margin: 0 0 6px;
  color: var(--muted);
  font-size: 18px;
  line-height: 1.72;
}
.featured-story {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, .65fr);
  margin-top: 60px;
  border: 1px solid var(--line);
  background: var(--surface);
}
.featured-story__image,
.story-card__image {
  display: block;
  overflow: hidden;
  background: #242724;
}
.featured-story__image { aspect-ratio: 4 / 3; }
.featured-story__image img,
.story-card__image img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.featured-story__body {
  display: flex;
  min-width: 0;
  padding: clamp(30px, 5vw, 58px);
  flex-direction: column;
  justify-content: center;
}
.featured-story h2 {
  margin: 0 0 20px;
  font-size: clamp(30px, 3.5vw, 46px);
  font-weight: 820;
  letter-spacing: -.05em;
  line-height: 1.2;
}
.featured-story h2 a,
.story-card h3 a,
.archive-row h3 a { color: var(--ink); text-decoration: none; }
.featured-story h2 a:hover,
.story-card h3 a:hover,
.archive-row h3 a:hover { color: var(--accent-dark); }
.featured-story__body > p:not(.eyebrow) {
  margin: 0;
  color: var(--muted);
  font-size: 17px;
  line-height: 1.72;
}
.story-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-top: 34px;
  padding-top: 20px;
  border-top: 1px solid var(--line);
}
.story-meta time,
.story-card time,
.archive-row time,
.article-meta { color: var(--muted); font-size: 13px; }
.story-meta a,
.text-link { font-size: 14px; font-weight: 800; text-decoration: none; }
.recent-section,
.archive-section { margin-top: 104px; }
.section-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 28px;
  margin-bottom: 26px;
}
.section-heading .eyebrow { margin: 0 0 5px; }
.section-heading h2 {
  margin: 0;
  font-size: clamp(26px, 3vw, 36px);
  letter-spacing: -.045em;
  line-height: 1.25;
}
.story-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 28px;
}
.story-card {
  min-width: 0;
  border-top: 2px solid var(--ink);
  background: transparent;
}
.story-card__image { aspect-ratio: 4 / 3; margin-top: 14px; }
.story-card__body { padding: 20px 2px 0; }
.story-card h3 {
  margin: 7px 0 11px;
  font-size: 21px;
  font-weight: 780;
  letter-spacing: -.035em;
  line-height: 1.42;
}
.story-card p {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.65;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}
.archive-list { border-top: 2px solid var(--ink); }
.archive-row {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr) 28px;
  align-items: center;
  gap: 20px;
  padding: 22px 4px;
  border-bottom: 1px solid var(--line);
}
.archive-row h3 {
  margin: 0;
  font-size: clamp(17px, 2vw, 21px);
  font-weight: 720;
  letter-spacing: -.025em;
  line-height: 1.45;
}
.archive-row > span { color: var(--accent); font-size: 18px; text-align: right; }
.service-panel {
  display: grid;
  grid-template-columns: minmax(180px, .45fr) minmax(0, 1fr);
  gap: 16px 52px;
  margin-top: 104px;
  padding: 52px;
  background: var(--dark);
  color: #f5f1e8;
  border-top: 5px solid var(--accent);
}
.service-panel .eyebrow { grid-column: 1; color: #f59b70; }
.service-panel h2 {
  grid-column: 1;
  margin: 0;
  font-size: clamp(27px, 3.4vw, 40px);
  letter-spacing: -.045em;
  line-height: 1.2;
}
.service-panel > p:not(.eyebrow) {
  grid-column: 2;
  grid-row: 1 / span 2;
  align-self: center;
  margin: 0;
  color: #c9c7c0;
  font-size: 17px;
}
.service-panel .text-link {
  grid-column: 2;
  color: #fff;
  justify-self: start;
}
.article-shell {
  width: min(1120px, calc(100% - 48px));
  margin: auto;
  padding: 76px 0 104px;
}
.article-header {
  max-width: 860px;
  margin: 0 auto 42px;
}
.article-header h1 { font-size: clamp(36px, 5.8vw, 62px); }
.article-dek {
  max-width: 730px;
  margin: 24px 0 0;
  color: var(--muted);
  font-size: clamp(18px, 2vw, 21px);
  line-height: 1.68;
}
.article-meta {
  display: flex;
  gap: 18px;
  margin-top: 24px;
}
.article-meta span::before { content: "·"; margin-right: 18px; color: var(--line); }
.hero {
  max-width: 1040px;
  margin: 0 auto 58px;
  border: 1px solid var(--line);
  background: #242724;
}
.hero img { display: block; width: 100%; }
.article-body {
  max-width: var(--content);
  margin: auto;
  color: #282926;
  font-size: 17px;
  line-height: 1.82;
}
.article-body > p { margin: 1.18em 0; }
.article-body > p:first-of-type { font-size: 1.08em; line-height: 1.78; }
.article-body h2 {
  margin: 2.7em 0 .72em;
  padding-top: .2em;
  color: var(--ink);
  font-size: clamp(25px, 3.4vw, 32px);
  font-weight: 800;
  letter-spacing: -.04em;
  line-height: 1.38;
}
.article-body h3 {
  margin: 2em 0 .65em;
  font-size: 21px;
  letter-spacing: -.03em;
}
.article-body strong { color: var(--ink); font-weight: 800; }
.article-body a { overflow-wrap: anywhere; }
.article-body ul,
.article-body ol { padding-left: 1.35em; }
.article-body li + li { margin-top: .45em; }
.article-note {
  margin: 0 0 46px !important;
  padding: 26px 28px !important;
  border: 1px solid var(--line);
  border-top: 4px solid var(--accent);
  background: var(--surface);
  color: #3e3f3a !important;
  font-size: 15px;
  line-height: 1.72;
}
.article-note > p { margin: 0 !important; }
.article-contact {
  margin: 72px 0 0 !important;
  padding: 30px 32px !important;
  border-top: 4px solid var(--accent);
  background: var(--dark);
  color: #f5f1e8 !important;
  font-size: 15px !important;
  line-height: 1.72 !important;
}
.article-contact > p { margin: 0 !important; color: inherit !important; }
.article-contact strong { color: inherit; }
.article-contact a { color: #ffb38e; font-weight: 800; }
.wp-block-table {
  display: block;
  width: min(960px, calc(100vw - 48px));
  max-width: none;
  margin: 32px 0 46px;
  margin-left: 50%;
  overflow-x: auto;
  transform: translateX(-50%);
  border-top: 2px solid var(--ink);
  background: var(--surface);
  scrollbar-color: var(--muted) var(--surface-muted);
}
.wp-block-table table {
  width: 100%;
  min-width: 680px;
  border-collapse: collapse;
  background: transparent !important;
  font-size: 14px;
  line-height: 1.55;
}
.wp-block-table th,
.wp-block-table td {
  padding: 11px 13px !important;
  border: 0 !important;
  border-bottom: 1px solid var(--line) !important;
  background: transparent !important;
  color: var(--ink) !important;
  text-align: left;
  vertical-align: top;
  white-space: nowrap;
}
.wp-block-table th {
  background: var(--dark) !important;
  color: #fff !important;
  font-weight: 750;
}
.wp-block-table.is-style-stripes tbody tr:nth-child(odd) { background: #f2eee6; }
.wp-block-table.is-style-stripes tbody tr:nth-child(even) { background: var(--surface); }
.has-text-align-right { text-align: right !important; }
.has-text-align-left { text-align: left !important; }
.has-text-align-center { text-align: center !important; }
.wp-element-caption,
figcaption {
  margin: 10px 0 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.55;
}
.wp-block-image {
  width: min(960px, calc(100vw - 48px));
  max-width: none;
  margin: 36px 0 !important;
  margin-left: 50% !important;
  transform: translateX(-50%);
}
.wp-block-image img { display: block; margin: auto; }
.wp-block-separator {
  margin: 48px 0;
  border: 0;
  border-top: 1px solid var(--line);
}
.post-nav-wrap {
  max-width: var(--content);
  margin: 76px auto 0;
  padding-top: 26px;
  border-top: 2px solid var(--ink);
}
.post-nav-wrap > .eyebrow { margin-bottom: 16px; }
.post-nav {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.post-nav a {
  min-width: 0;
  padding: 20px;
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink);
  text-decoration: none;
}
.post-nav a:hover { border-color: var(--accent); }
.post-nav span {
  display: block;
  margin-bottom: 6px;
  color: var(--muted);
  font-size: 12px;
}
.post-nav strong {
  display: block;
  font-size: 15px;
  line-height: 1.5;
}
.about-shell .article-header { margin-bottom: 56px; }
.about-section-title { color: var(--accent-dark); }
.site-footer {
  padding: 42px 0 48px;
  border-top: 1px solid var(--line);
  color: var(--muted);
}
.site-footer__inner {
  width: min(var(--wide), calc(100% - 48px));
  margin: auto;
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 32px;
}
.site-footer strong { color: var(--ink); font-size: 15px; }
.site-footer p { margin: 4px 0 0; font-size: 13px; }
.site-footer a { font-size: 13px; font-weight: 750; }
@media (max-width: 900px) {
  .home-intro { grid-template-columns: 1fr; gap: 24px; }
  .home-intro > p { max-width: 620px; }
  .featured-story { grid-template-columns: 1fr; }
  .featured-story__body { padding: 36px; }
  .story-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .story-card:last-child { grid-column: 1 / -1; max-width: calc(50% - 14px); }
  .service-panel { grid-template-columns: 1fr; }
  .service-panel .eyebrow,
  .service-panel h2,
  .service-panel > p:not(.eyebrow),
  .service-panel .text-link { grid-column: 1; grid-row: auto; }
}
@media (max-width: 680px) {
  body { word-break: normal; }
  .site-header__inner,
  .home-shell,
  .article-shell,
  .site-footer__inner { width: calc(100% - 36px); }
  .site-header__inner { min-height: 62px; }
  .site-header nav { gap: 18px; }
  .site-header nav a { padding: 17px 0; }
  .brand { font-size: 16px; }
  .home-shell { padding: 46px 0 76px; }
  .home-intro { padding-bottom: 42px; }
  .home-intro h1 { font-size: clamp(36px, 11vw, 46px); }
  .home-intro > p { font-size: 16px; }
  .featured-story { margin-top: 38px; }
  .featured-story__body { padding: 26px 22px 28px; }
  .featured-story h2 { font-size: 31px; }
  .story-meta { align-items: flex-end; }
  .recent-section,
  .archive-section { margin-top: 76px; }
  .story-grid { grid-template-columns: 1fr; gap: 42px; }
  .story-card:last-child { grid-column: auto; max-width: none; }
  .archive-row {
    grid-template-columns: minmax(0, 1fr) 24px;
    gap: 5px 12px;
    padding: 18px 2px;
  }
  .archive-row time { grid-column: 1 / -1; }
  .archive-row h3 { grid-column: 1; }
  .archive-row > span { grid-column: 2; }
  .service-panel { margin-top: 76px; padding: 34px 24px; }
  .service-panel > p:not(.eyebrow) { font-size: 15px; }
  .article-shell { padding: 48px 0 76px; }
  .article-header { margin-bottom: 32px; }
  .article-header h1 { font-size: clamp(34px, 11vw, 46px); }
  .article-dek { font-size: 17px; }
  .article-meta { flex-wrap: wrap; gap: 8px 12px; }
  .article-meta span::before { margin-right: 12px; }
  .hero {
    width: 100vw;
    margin-right: 50%;
    margin-bottom: 42px;
    margin-left: 50%;
    transform: translateX(-50%);
    border-right: 0;
    border-left: 0;
  }
  .article-body { font-size: 16px; }
  .article-note { padding: 22px 20px !important; }
  .article-contact { padding: 26px 22px !important; }
  .wp-block-table {
    width: 100vw;
    margin-top: 28px;
    margin-bottom: 40px;
    padding-right: 18px;
    padding-left: 18px;
  }
  .wp-block-table::before {
    content: "표는 좌우로 밀어 볼 수 있습니다";
    display: block;
    padding: 8px 0;
    color: var(--muted);
    font-size: 12px;
  }
  .wp-block-table table { min-width: 640px; }
  .wp-block-image { width: 100vw; }
  .post-nav-wrap { margin-top: 58px; }
  .post-nav { grid-template-columns: 1fr; }
  .site-footer__inner { align-items: flex-start; flex-direction: column; gap: 18px; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
}
"""


def validate(data: dict) -> None:
    posts = data["posts"]
    if len(posts) != 14:
        raise RuntimeError(f"expected 14 posts, got {len(posts)}")
    paths = [p["path"] for p in posts]
    if len(paths) != len(set(paths)):
        raise RuntimeError("duplicate post paths")
    for post in posts:
        if not re.fullmatch(r"/\d{4}/\d{2}/\d{2}/[a-z0-9-]+/", post["path"]):
            raise RuntimeError(f"invalid path: {post['path']}")
        if "golgong.wordpress.com/wp-content" in post["body_html"]:
            raise RuntimeError(f"WordPress media remains in {post['slug']}")
        emails = {match.group(0).lower() for match in EMAIL_PATTERN.finditer(post["body_html"])}
        if emails != {CONTACT}:
            raise RuntimeError(f"unexpected contact email set in {post['slug']}")


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    validate(data)
    posts = sorted(data["posts"], key=lambda p: (p["date"], p["id"]), reverse=True)
    about = data["about"]

    write(ROOT / "index.html", render_index(posts))
    write(ROOT / "about" / "index.html", render_about(about))
    for post in posts:
        output = ROOT / post["path"].lstrip("/") / "index.html"
        write(output, render_article(post, posts))
    write(ROOT / "feed.xml", render_feed(posts))
    write(ROOT / "sitemap.xml", render_sitemap(posts, about))
    write(
        ROOT / "robots.txt",
        f"User-agent: *\nAllow: /\nDisallow: /data/\nDisallow: /tools/\n\nSitemap: {SITE_URL}/sitemap.xml\n",
    )
    write(ROOT / ".nojekyll", "")
    write(ROOT / "assets" / "css" / "site.css", CSS.strip() + "\n")
    write(ROOT / "404.html", f"""{page_head(title='페이지를 찾을 수 없습니다 | '+SITE_NAME, description='요청한 페이지를 찾을 수 없습니다.', canonical=SITE_URL+'/404.html', og_type='website', robots='noindex,follow')}<body>{site_header()}<main id="main-content" class="article-shell" tabindex="-1"><article><header class="article-header"><p class="eyebrow">404</p><h1>페이지를 찾을 수 없습니다</h1><p class="article-dek">주소를 다시 확인하거나 글 목록에서 원하는 내용을 찾아보십시오.</p></header><p><a class="text-link" href="/">글 목록으로 돌아가기 <span aria-hidden="true">→</span></a></p></article></main>{site_footer()}</body></html>\n""")

    tracked = [ROOT / "index.html", ROOT / "about" / "index.html", ROOT / "feed.xml",
               ROOT / "sitemap.xml", ROOT / "robots.txt", ROOT / "404.html",
               ROOT / "assets" / "css" / "site.css"]
    tracked.extend(ROOT / p["path"].lstrip("/") / "index.html" for p in posts)
    manifest = {
        "version": 1,
        "source": data["source"],
        "post_count": len(posts),
        "paths": [p["path"] for p in posts],
        "files": {
            str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in tracked
        },
    }
    write(ROOT / "migration-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"BUILT posts={len(posts)} sitemap_urls={len(posts)+2} feed_items={len(posts)}")


if __name__ == "__main__":
    main()
