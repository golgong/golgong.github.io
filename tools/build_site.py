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
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


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


def site_header() -> str:
    return f"""<header class="site-header">
  <div class="site-header__inner">
    <a class="brand" href="/">{SITE_NAME}</a>
    <nav aria-label="주요 메뉴">
      <a href="/">글</a>
      <a href="/about/">소개</a>
      <a href="mailto:{CONTACT}">문의</a>
    </nav>
  </div>
</header>"""


def site_footer() -> str:
    return f"""<footer class="site-footer">
  <p>공공데이터와 공개 API에서 자료를 모아 직접 세어 봅니다.</p>
  <p>문의: <a href="mailto:{CONTACT}">{CONTACT}</a></p>
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
        f'<a href="{esc(other["path"])}"><span>{label}</span>{esc(other["title"])}</a>'
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
<main class="article-shell">
  <article>
    <header class="article-header">
      <p class="eyebrow">데이터로 세어 본 결과</p>
      <h1>{esc(post["title"])}</h1>
      <time datetime="{esc(post["date"])}">{esc(post["date"][:10])}</time>
    </header>
    {hero}
    <div class="article-body">
{post["body_html"]}
    </div>
    <section class="contact-box" aria-label="데이터 수집 문의">
      <h2>자료를 대신 모아 드립니다</h2>
      <p>공공데이터·공개 API·웹에 흩어진 자료를 모아 표와 데이터베이스로 정리합니다.</p>
      <p><a href="mailto:{CONTACT}">{CONTACT}</a></p>
    </section>
  </article>
  <nav class="post-nav" aria-label="다른 글">{neighbor_html}</nav>
</main>
{site_footer()}
</body>
</html>
"""


def render_index(posts: list[dict]) -> str:
    description = "공공데이터와 공개 API에서 자료를 모아 직접 세어 본 결과를 공개합니다. 데이터 수집과 가공을 대신해 드립니다."
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
    cards = []
    for post in posts:
        thumb = ""
        if post.get("featured_image"):
            thumb = f'<img src="{esc(post["featured_image"])}" alt="" width="320" height="240" loading="lazy">'
        cards.append(f"""<article class="post-card">
  <a class="post-card__image" href="{esc(post["path"])}" tabindex="-1" aria-hidden="true">{thumb}</a>
  <div><time datetime="{esc(post["date"])}">{esc(post["date"][:10])}</time>
  <h2><a href="{esc(post["path"])}">{esc(post["title"])}</a></h2>
  <p>{esc(post["description"])}</p></div>
</article>""")
    return f"""{page_head(
        title=f"{SITE_NAME} — 공공데이터를 직접 세어 봅니다",
        description=description, canonical=SITE_URL + "/", og_type="website",
        image=latest_image, schema=schema,
    )}
<body>
{site_header()}
<main class="home-shell">
  <section class="home-intro">
    <p class="eyebrow">흩어진 데이터 수집·가공</p>
    <h1>아무도 세어 보지 않은 것을<br>데이터로 확인합니다</h1>
    <p>공공데이터와 공개 API에서 자료를 모아 직접 세어 보고, 확인된 결과만 씁니다.</p>
  </section>
  <section class="post-list" aria-labelledby="latest-heading">
    <h2 id="latest-heading" class="section-title">최근 글</h2>
    {''.join(cards)}
  </section>
  <section class="service-box">
    <h2>필요한 자료를 대신 모아 드립니다</h2>
    <p>여러 사이트에 흩어진 자료를 모아 엑셀이나 데이터베이스로 정리하고, 반복 수집 프로그램도 만듭니다.</p>
    <a href="mailto:{CONTACT}">{CONTACT}</a>
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
{site_header()}
<main class="article-shell">
  <article>
    <header class="article-header"><p class="eyebrow">소개</p><h1>{SITE_NAME}</h1></header>
    <div class="article-body">{about["body_html"]}</div>
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
        items.append(f"""<item>
  <title>{esc(post["title"])}</title>
  <link>{esc(url)}</link>
  <guid isPermaLink="true">{esc(url)}</guid>
  <pubDate>{published}</pubDate>
  <description>{esc(post["description"])}</description>
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


CSS = r"""*{box-sizing:border-box}html{color-scheme:light}body{margin:0;background:#f7f7f5;color:#18181b;font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",sans-serif;line-height:1.75;word-break:keep-all}a{color:#c2410c;text-decoration-thickness:1px;text-underline-offset:3px}img{max-width:100%;height:auto}.site-header{background:#111827;color:#fff}.site-header__inner{max-width:1100px;margin:auto;padding:18px 24px;display:flex;justify-content:space-between;align-items:center;gap:24px}.brand{font-size:21px;font-weight:800;color:#fb923c;text-decoration:none}.site-header nav{display:flex;gap:18px}.site-header nav a{color:#e5e7eb;text-decoration:none;font-size:14px}.home-shell,.article-shell{max-width:1100px;margin:auto;padding:52px 24px 80px}.home-intro{max-width:820px;padding:36px 0 64px}.eyebrow{margin:0 0 10px;color:#c2410c;font-size:14px;font-weight:800;letter-spacing:.04em}.home-intro h1,.article-header h1{margin:0;line-height:1.28;letter-spacing:-.035em}.home-intro h1{font-size:clamp(34px,7vw,64px)}.home-intro>p:last-child{font-size:18px;color:#52525b}.section-title{font-size:16px;border-bottom:2px solid #18181b;padding-bottom:10px}.post-card{display:grid;grid-template-columns:180px 1fr;gap:24px;padding:26px 0;border-bottom:1px solid #d4d4d8}.post-card__image{display:block;aspect-ratio:4/3;overflow:hidden;background:#e4e4e7}.post-card__image img{width:100%;height:100%;object-fit:cover}.post-card time,.article-header time{font-size:13px;color:#71717a}.post-card h2{font-size:22px;line-height:1.4;margin:5px 0 8px}.post-card h2 a{color:#18181b;text-decoration:none}.post-card p{margin:0;color:#52525b}.service-box,.contact-box{margin-top:56px;padding:28px;border:1px solid #fed7aa;background:#fff7ed}.service-box h2,.contact-box h2{margin-top:0}.article-shell{max-width:960px}.article-header{max-width:800px;margin:0 auto 36px}.article-header h1{font-size:clamp(32px,6vw,54px);margin-bottom:16px}.hero{margin:0 auto 48px;max-width:920px}.hero img{display:block;width:100%;border-radius:4px}.article-body{max-width:800px;margin:auto;font-size:17px}.article-body>p{margin:1.15em 0}.article-body h2{margin:2.4em 0 .7em;font-size:clamp(22px,4vw,30px);line-height:1.4;letter-spacing:-.025em}.article-note{margin:0 0 34px;padding:22px 24px;border-left:4px solid #f97316;background:#fff7ed;color:#3f3f46}.article-note p:first-child{margin-top:0}.article-note p:last-child{margin-bottom:0}.wp-block-table{display:block;max-width:100%;overflow-x:auto;margin:24px 0 34px}.wp-block-table table{width:100%;min-width:680px;border-collapse:collapse;font-size:14px;background:#fff}.wp-block-table th,.wp-block-table td{padding:9px 11px;border:1px solid #d4d4d8;text-align:left;vertical-align:top;white-space:nowrap}.wp-block-table th{background:#27272a;color:#fff;font-weight:700}.wp-block-table.is-style-stripes tbody tr:nth-child(odd){background:#f4f4f5}.has-text-align-right{text-align:right!important}.has-text-align-left{text-align:left!important}.has-text-align-center{text-align:center!important}.wp-element-caption,figcaption{margin-top:8px;color:#71717a;font-size:13px;line-height:1.55}.wp-block-image{margin:28px 0}.wp-block-separator{border:0;border-top:1px solid #d4d4d8;margin:40px 0}.contact-box{max-width:800px;margin:64px auto 0}.post-nav{max-width:800px;margin:42px auto 0;display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.post-nav a{padding:18px;background:#fff;border:1px solid #e4e4e7;text-decoration:none;color:#27272a}.post-nav span{display:block;color:#a1a1aa;font-size:12px}.site-footer{padding:32px 24px 48px;text-align:center;background:#111827;color:#a1a1aa;font-size:14px}.site-footer p{margin:4px}.site-footer a{color:#fb923c}@media(max-width:700px){body{word-break:normal}.site-header__inner{padding:15px 18px}.site-header nav{gap:12px}.home-shell,.article-shell{padding:36px 17px 60px}.post-card{grid-template-columns:112px 1fr;gap:14px}.post-card h2{font-size:18px}.post-card p{display:none}.article-body{font-size:16px}.article-note{padding:18px}.wp-block-table{margin-left:-17px;margin-right:-17px;padding-left:17px;padding-right:17px}.post-nav{grid-template-columns:1fr}}"""


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
    write(ROOT / "assets" / "css" / "site.css", CSS + "\n")
    write(ROOT / "404.html", f"""{page_head(title='페이지를 찾을 수 없습니다 | '+SITE_NAME, description='요청한 페이지를 찾을 수 없습니다.', canonical=SITE_URL+'/404.html', og_type='website', robots='noindex,follow')}<body>{site_header()}<main class="article-shell"><article><header class="article-header"><p class="eyebrow">404</p><h1>페이지를 찾을 수 없습니다</h1></header><p><a href="/">글 목록으로 돌아가기</a></p></article></main>{site_footer()}</body></html>\n""")

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
