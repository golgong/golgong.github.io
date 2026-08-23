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
ANALYTICS_CONFIG_FILE = ROOT / "data" / "analytics.json"
SITE_URL = "https://golgong.github.io"
SITE_NAME = "골때리는공작소"
HOME_HERO = "/assets/images/home/hero-v4.jpg"
HOME_OG = "/assets/images/home/og-v4.jpg"
CONTACT = "golgong@kakao.com"
SERVICE_HEADLINE = "필요한 자료를 대신 분석해 드립니다."
OLD_ARTICLE_SERVICE_HEADLINE = "골때리는공작소는 이런 일을 대신해 드립니다."
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
GA_MEASUREMENT_ID_PATTERN = re.compile(r"G-[A-Z0-9]{6,20}")


def load_ga_measurement_id() -> str:
    config = json.loads(ANALYTICS_CONFIG_FILE.read_text(encoding="utf-8"))
    if set(config) != {"measurement_id"}:
        raise RuntimeError("analytics config keys mismatch")
    measurement_id = str(config["measurement_id"] or "").strip().upper()
    if not GA_MEASUREMENT_ID_PATTERN.fullmatch(measurement_id):
        raise RuntimeError("invalid Google Analytics measurement ID")
    return measurement_id


GA_MEASUREMENT_ID = load_ga_measurement_id()


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


def enhance_article(body_html: str, appendix_html: str = "") -> str:
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
    body_html = body_html.rstrip()
    if appendix_html:
        body_html += f"\n{appendix_html}"
    body_html += f'\n<aside class="article-contact">{contact_note}</aside>'
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
              image: str | None = None, image_alt: str | None = None,
              image_width: int | None = None, image_height: int | None = None,
              image_type: str | None = None, published: str | None = None,
              modified: str | None = None, schema: object | None = None,
              robots: str = "index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1") -> str:
    image_tags = ""
    if image:
        resolved_image_alt = image_alt or title
        image_tags = (
            f'\n<meta property="og:image" content="{esc(image)}">'
            f'\n<meta property="og:image:alt" content="{esc(resolved_image_alt)}">'
            f'\n<meta name="twitter:card" content="summary_large_image">'
            f'\n<meta name="twitter:image" content="{esc(image)}">'
            f'\n<meta name="twitter:image:alt" content="{esc(resolved_image_alt)}">'
        )
        if image_width is not None:
            image_tags += f'\n<meta property="og:image:width" content="{image_width}">'
        if image_height is not None:
            image_tags += f'\n<meta property="og:image:height" content="{image_height}">'
        if image_type:
            image_tags += f'\n<meta property="og:image:type" content="{esc(image_type)}">'
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
<meta name="google-analytics-id" content="{esc(GA_MEASUREMENT_ID)}">
<script>
window.dataLayer = window.dataLayer || [];
window.gtag = window.gtag || function(){{window.dataLayer.push(arguments);}};
window["ga-disable-{GA_MEASUREMENT_ID}"] = true;
window.gtag("consent", "default", {{
  analytics_storage: "denied",
  ad_storage: "denied",
  ad_user_data: "denied",
  ad_personalization: "denied"
}});
window.gtag("js", new Date());
window.gtag("config", "{GA_MEASUREMENT_ID}", {{
  send_page_view: false,
  allow_google_signals: false,
  allow_ad_personalization_signals: false
}});
</script>
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
<script defer src="/assets/js/site.js?v={SITE_JS_VERSION}"></script>
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="robots" content="{esc(robots)}">
<link rel="canonical" href="{esc(canonical)}">
<link rel="alternate" type="application/rss+xml" title="{SITE_NAME}" href="{SITE_URL}/feed.xml">
<link rel="stylesheet" href="/assets/css/site.css?v={CSS_VERSION}">
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
    <div><strong>{SITE_NAME}</strong><p>공공데이터와 공개 API에서 자료를 모아 정확히 분석합니다.</p></div>
    <nav aria-label="사이트 안내">
      <a href="/about/">작업 방식과 문의</a>
      <a href="/privacy/">방문 분석 안내</a>
      <button type="button" data-analytics-settings>분석 설정</button>
    </nav>
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
    if post.get("og_image"):
        schema["image"] = [SITE_URL + post["og_image"]]
    return schema


def render_downloads(post: dict) -> str:
    downloads = post.get("downloads", [])
    if not downloads:
        return ""
    items = "".join(
        f'<li><a href="{esc(item["path"])}" download>{esc(item["label"])}</a></li>'
        for item in downloads
    )
    return (
        '<section class="article-downloads">'
        '<h2>결과 파일</h2>'
        '<p>원천 상품명과 URL은 재배포하지 않고, 방식별 집계와 분할 결과를 함께 공개합니다.</p>'
        f'<ul>{items}</ul>'
        '</section>'
    )


def render_article(post: dict, posts: list[dict]) -> str:
    canonical = SITE_URL + post["path"]
    image = SITE_URL + post["og_image"] if post.get("og_image") else None
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
    neighbor_class = "post-nav post-nav--single" if len(neighbors) == 1 else "post-nav"
    hero = ""
    if post.get("featured_image"):
        hero = (
            f'<figure class="hero"><img src="{esc(post["featured_image"])}" '
            f'alt="{esc(post["title"])} 대표 이미지" width="1448" height="1086" '
            f'fetchpriority="high" decoding="async"></figure>'
        )
    return f"""{page_head(
        title=post["title"], description=post["description"], canonical=canonical,
        og_type="article", image=image, image_alt=post["title"],
        image_width=1200, image_height=630, image_type="image/jpeg",
        published=post["date"], modified=post["modified"],
        schema=article_schema(post),
    )}
<body>
{site_header()}
<main id="main-content" class="article-shell" tabindex="-1">
  <article>
    <header class="article-header">
      <p class="eyebrow">Data note · {esc(post["date"][:10])}</p>
      <h1>{esc(post["title"])}</h1>
      <div class="article-meta"><span>공개 데이터 분석</span><span>자료 수집·가공</span></div>
    </header>
    {hero}
    <div class="article-body">
{enhance_article(post["body_html"], render_downloads(post))}
    </div>
  </article>
  <section class="post-nav-wrap" aria-labelledby="continue-heading">
    <h2 id="continue-heading" class="eyebrow">이어서 읽기</h2>
    <nav class="{neighbor_class}" aria-label="다른 글">{neighbor_html}</nav>
  </section>
</main>
{site_footer()}
</body>
</html>
"""


def render_index(posts: list[dict]) -> str:
    description = f"공공데이터와 공개 API에서 자료를 모아 정확히 분석한 결과를 공개합니다. {SERVICE_HEADLINE}"
    home_og = SITE_URL + HOME_OG
    schema = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": SITE_NAME,
        "url": SITE_URL + "/",
        "description": description,
        "inLanguage": "ko-KR",
        "publisher": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL + "/about/"},
        "image": home_og,
    }
    journal_rows = []
    for number, post in enumerate(posts, start=1):
        thumb = ""
        if post.get("featured_image"):
            thumb = (
                f'<img src="{esc(post["featured_image"])}" alt="{esc(post["title"])} 대표 이미지" '
                f'width="1448" height="1086" '
                f'loading="lazy" decoding="async">'
            )
        if number <= 4:
            layout = " journal-row--feature"
            if number % 2 == 0:
                layout += " journal-row--reverse"
        else:
            layout = " journal-row--compact"
        journal_rows.append(f"""<article class="journal-row{layout}" aria-labelledby="record-{number:02d}-title">
  <a class="journal-row__image" data-post-link href="{esc(post["path"])}" aria-labelledby="record-{number:02d}-title">{thumb}</a>
  <div class="journal-row__body">
    <p class="eyebrow">Data record · {number:02d}</p>
    <h2 id="record-{number:02d}-title" class="visually-hidden">{esc(post["title"])}</h2>
    <p class="journal-row__summary">{esc(display_summary(post["description"]))}</p>
    <div class="journal-row__meta"><time datetime="{esc(post["date"])}">{esc(post["date"][:10])}</time><a class="outline-link" href="{esc(post["path"])}" aria-label="{esc(post["title"])} 내용 보기">내용 보기</a></div>
  </div>
</article>""")

    return f"""{page_head(
        title=f"{SITE_NAME} — 공공데이터를 정확히 분석합니다",
        description=description, canonical=SITE_URL + "/", og_type="website",
        image=home_og, image_alt=f"{SITE_NAME} — 아무도 세어 보지 않은 것을 끝까지 확인합니다",
        image_width=1200, image_height=630, image_type="image/jpeg", schema=schema,
    )}
<body>
{site_header("home")}
<main id="main-content" class="home-shell" tabindex="-1">
  <h1 class="visually-hidden">{SITE_NAME}</h1>

  <section class="home-manifesto" aria-label="골때리는공작소 소개">
    <figure class="home-hero"><img src="{HOME_HERO}" alt="{SITE_NAME} — 아무도 세어 보지 않은 것을 끝까지 확인합니다" width="1448" height="1086" fetchpriority="high" decoding="async"></figure>
    <div class="home-manifesto__copy">
      <p>공공데이터와 공개 API에서 자료를 모아 정확히 분석합니다.</p>
      <a class="outline-link" href="#records">전체 기록 보기</a>
    </div>
  </section>

  <section id="records" class="recent-section" aria-labelledby="recent-heading">
    <div class="section-heading"><p class="eyebrow">Data records · 01—{len(posts):02d}</p><h2 id="recent-heading">전체 기록</h2></div>
    <div class="journal-list">{''.join(journal_rows)}</div>
  </section>

  <section class="service-panel" aria-labelledby="service-heading">
    <p class="eyebrow">Data collection · analysis</p>
    <h2 id="service-heading">{SERVICE_HEADLINE}</h2>
    <p>여러 사이트에 흩어진 자료를 모아 엑셀이나 데이터베이스로 정리하고, 반복 수집 프로그램도 만듭니다.</p>
    <a class="text-link" href="mailto:{CONTACT}">{CONTACT} <span aria-hidden="true">→</span></a>
  </section>

  <section class="visitor-strip" aria-label="방문 분석 통계" data-visitor-stats>
    <p class="visitor-strip__label">Visitor note</p>
    <p class="visitor-strip__summary" data-visitor-summary aria-live="polite">분석을 허용한 방문을 집계하고 있습니다.</p>
    <div class="visitor-strip__trend" data-visitor-trend hidden>
      <span data-visitor-change></span>
      <span class="visitor-bars" data-visitor-bars hidden></span>
    </div>
    <time class="visitor-strip__date" data-visitor-date></time>
  </section>
</main>
{site_footer()}
</body>
</html>
"""


def render_about(about: dict) -> str:
    description = "골때리는공작소는 공공데이터와 공개 API에서 자료를 모아 정확히 분석하고, 확인된 결과를 공개합니다."
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


def render_privacy() -> str:
    description = "골때리는공작소의 Google Analytics 사용 범위와 방문 분석 설정을 안내합니다."
    return f"""{page_head(
        title=f"방문 분석 안내 | {SITE_NAME}", description=description,
        canonical=SITE_URL + "/privacy/", og_type="website", robots="noindex,follow",
    )}
<body>
{site_header()}
<main id="main-content" class="article-shell privacy-shell" tabindex="-1">
  <article>
    <header class="article-header">
      <p class="eyebrow">방문 분석 안내</p>
      <h1>Google Analytics 사용</h1>
      <p class="article-dek">방문 흐름을 확인하고 사이트를 다듬기 위해, 허용한 경우에만 Google Analytics를 사용합니다.</p>
    </header>
    <div class="article-body privacy-copy">
      <h2>수집하는 정보</h2>
      <p>페이지 주소, 방문 시각, 브라우저와 기기 종류, 대략적인 지역 정보가 Google에 전송될 수 있습니다. 이름, 이메일 주소, 전화번호는 분석 정보로 보내지 않습니다.</p>
      <h2>공개하는 통계</h2>
      <p>첫 화면에는 Google Analytics에서 측정된 최근 7일의 분석 허용 활성 사용자 수와 직전 7일 대비 변화만 표시합니다. 한 사람이 여러 기기나 브라우저를 사용하면 서로 다른 사용자로 집계될 수 있습니다. 페이지별 방문, 유입어, 위치, 기기, 방문 시각은 공개하지 않습니다. 분석 허용 활성 사용자가 5명 미만이면 정확한 숫자와 추이를 숨깁니다.</p>
      <h2>허용과 거부</h2>
      <p>Google 태그 파일은 페이지를 열 때 불러오지만, 허용하기 전에는 방문 분석 이벤트를 보내거나 분석 쿠키를 저장하지 않습니다. 허용하면 Google Analytics가 <code>_ga</code>로 시작하는 쿠키를 최대 2년간 사용할 수 있습니다. 허용 여부는 이 브라우저의 로컬 저장소에 보관하며, 설정을 바꾸거나 브라우저 저장 정보를 지울 때까지 유지됩니다. 언제든 아래 버튼에서 설정을 바꿀 수 있습니다.</p>
      <p class="analytics-choice" data-analytics-choice>현재 설정을 확인하고 있습니다.</p>
      <p><button class="settings-button" type="button" data-analytics-settings>방문 분석 설정 열기</button></p>
      <h2>문의</h2>
      <p>방문 분석에 관한 문의는 <a href="mailto:{CONTACT}">{CONTACT}</a>으로 보내 주십시오.</p>
    </div>
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
  <description>공공데이터와 공개 API에서 자료를 모아 정확히 분석한 결과</description>
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
  --paper: #ededed;
  --surface: #ffffff;
  --surface-muted: #dfe2e3;
  --ink: #171b1f;
  --muted: #555c61;
  --line: #041f3e;
  --accent: #314c63;
  --accent-light: #cbd3d8;
  --night: #363b41;
  --content: 760px;
  --wide: 980px;
  --system-font: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif;
}
* { box-sizing: border-box; }
html { overflow-x: clip; color-scheme: light; scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--system-font);
  font-size: 16px;
  font-synthesis: none;
  line-height: 1.75;
  letter-spacing: -.012em;
  word-break: keep-all;
}
strong, b { font-weight: inherit; }
#main-content { scroll-margin-top: 82px; }
a { color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 4px; }
a:hover { color: var(--ink); }
img { max-width: 100%; height: auto; }
time, table { font-variant-numeric: tabular-nums; }
::selection { background: #cbd3d8; color: var(--ink); }
:focus-visible {
  outline: 2px solid #fff;
  outline-offset: 2px;
  box-shadow: 0 0 0 4px var(--accent);
}
[hidden] { display: none !important; }
.skip-link {
  position: fixed;
  top: 12px;
  left: 12px;
  z-index: 100;
  padding: 10px 14px;
  background: #fff;
  color: #000;
  transform: translateY(-160%);
  text-decoration: none;
}
.skip-link:focus { transform: translateY(0); }
.visually-hidden {
  position: absolute !important;
  width: 1px !important;
  height: 1px !important;
  padding: 0 !important;
  margin: -1px !important;
  overflow: hidden !important;
  clip: rect(0, 0, 0, 0) !important;
  white-space: nowrap !important;
  border: 0 !important;
  font-weight: 400 !important;
}
.site-header {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(54, 59, 65, .98);
  color: var(--surface);
  border-bottom: 0;
  backdrop-filter: blur(12px);
}
.site-header__inner {
  width: min(var(--wide), calc(100% - 36px));
  min-height: 69px;
  margin: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}
.brand {
  display: inline-flex;
  flex: 0 1 270px;
  align-items: center;
  gap: 12px;
  color: var(--surface);
  font-size: 18px;
  font-weight: 400;
  letter-spacing: .08em;
  text-decoration: none;
}
.brand:hover { color: #fff; }
.brand__mark {
  width: 8px;
  height: 8px;
  background: #d7dadd;
  transform: rotate(45deg);
}
.site-header nav { display: flex; align-items: center; gap: 0; }
.site-header nav a {
  display: grid;
  min-width: 100px;
  min-height: 50px;
  padding: 0 18px;
  place-items: center;
  color: #e4e6e7;
  font-size: 14px;
  font-weight: 400;
  letter-spacing: 0;
  text-decoration: none;
}
.site-header nav a:hover { background: rgba(255, 255, 255, .09); color: #fff; }
.site-header nav a[aria-current="page"] { background: #fff; color: var(--night); }
.home-shell {
  width: min(var(--wide), calc(100% - 48px));
  margin: auto;
  padding: 29px 0 88px;
}
.home-intro {
  padding: 0 0 29px;
  text-align: center;
}
.eyebrow {
  margin: 0 0 16px;
  color: var(--accent);
  font-size: 11px;
  font-weight: 400;
  letter-spacing: .16em;
  line-height: 1.4;
  text-transform: uppercase;
}
.home-intro h1,
.article-header h1,
.section-heading h2,
.service-panel h2,
.article-body h2,
.article-body h3 {
  font-family: inherit;
  font-weight: 400;
}
.home-intro h1,
.article-header h1 {
  margin: 0;
  color: var(--ink);
  letter-spacing: -.02em;
  line-height: 1.18;
}
.home-intro h1 {
  color: #5b6166;
  font-size: clamp(40px, 4vw, 50px);
  letter-spacing: .01em;
}
.home-intro .eyebrow { display: none; }
.home-manifesto {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, .92fr);
  align-items: center;
  gap: 27px;
  padding: 0 0 28px;
  border-bottom: 1px solid var(--line);
}
.home-hero {
  margin: 0;
  overflow: hidden;
  background: var(--night);
}
.home-hero img {
  display: block;
  width: 100%;
  aspect-ratio: 4 / 3;
  object-fit: cover;
}
.home-manifesto__copy {
  padding: 10px 10px 10px 0;
  color: #20252a;
  font-size: 16px;
  line-height: 1.5;
}
.home-manifesto__copy p { margin: 0 0 24px; }
.home-manifesto__copy .outline-link { margin-top: 6px; }
.outline-link {
  display: inline-flex;
  min-height: 40px;
  padding: 7px 16px;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink);
  font-size: 13px;
  font-weight: 400;
  text-decoration: none;
}
.outline-link:hover { background: var(--night); color: #fff; }
.journal-row__image {
  display: block;
  overflow: hidden;
  background: var(--night);
}
.journal-row__image img {
  display: block;
  width: 100%;
  aspect-ratio: 4 / 3;
  object-fit: cover;
  transition: transform .6s cubic-bezier(.2, .7, .2, 1), filter .6s ease;
}
.journal-row__image:hover img { transform: scale(1.012); filter: saturate(1.03); }
.article-meta { color: var(--muted); font-size: 12px; }
.text-link { font-size: 13px; font-weight: 400; text-decoration: none; }
.visitor-strip {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 10px 20px;
  min-height: 52px;
  margin-top: 20px;
  padding: 12px 2px;
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
}
.visitor-strip p { margin: 0; }
.visitor-strip__label { color: var(--accent); font-size: 10px; letter-spacing: .14em; text-transform: uppercase; }
.visitor-strip__summary { font-size: 13px; }
.visitor-strip__trend { display: flex; align-items: center; gap: 13px; color: var(--muted); font-size: 11px; }
.visitor-strip__date { color: var(--muted); font-size: 11px; }
.visitor-bars { display: inline-flex; align-items: end; gap: 3px; width: 34px; height: 20px; }
.visitor-bars > span { width: 6px; min-height: 3px; background: var(--accent); opacity: .58; }
.recent-section { margin-top: 28px; }
.section-heading {
  margin-bottom: 0;
  padding: 8px 0 26px;
  border-bottom: 1px solid var(--ink);
  text-align: center;
}
.section-heading .eyebrow { margin: 0 0 5px; color: var(--muted); }
.section-heading h2 { margin: 0; font-size: clamp(38px, 4vw, 48px); letter-spacing: -.02em; line-height: 1.2; }
.journal-list { display: block; }
.journal-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, .92fr);
  align-items: center;
  gap: 27px;
  padding: 28px 0;
  border-bottom: 1px solid var(--line);
}
.journal-row--reverse .journal-row__image { grid-column: 2; grid-row: 1; }
.journal-row--reverse .journal-row__body { grid-column: 1; grid-row: 1; }
.journal-row--compact {
  grid-template-columns: minmax(260px, .58fr) minmax(0, 1fr);
  padding: 20px 0;
}
.journal-row--compact .journal-row__body { padding: 8px 10px; }
.journal-row--compact .journal-row__summary { max-width: 560px; font-size: 15px; }
.journal-row--compact .journal-row__meta { margin-top: 20px; }
.journal-row__body { min-width: 0; padding: 12px 10px; }
.journal-row__summary {
  max-width: 430px;
  margin: 0;
  color: #20252a;
  font-size: 16px;
  line-height: 1.5;
}
.journal-row__meta { display: flex; align-items: center; gap: 18px; margin-top: 28px; }
.journal-row__meta time { color: var(--muted); font-size: 12px; }
.service-panel {
  margin-top: 28px;
  padding: 38px 0 42px;
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  text-align: center;
}
.service-panel .eyebrow { color: var(--muted); }
.service-panel h2 { margin: 0 auto; font-size: clamp(34px, 4vw, 46px); letter-spacing: -.02em; line-height: 1.22; white-space: nowrap; }
.service-panel > p:not(.eyebrow) { max-width: 610px; margin: 22px auto 0; color: var(--muted); font-size: 16px; line-height: 1.5; }
.service-panel .text-link { display: inline-block; margin-top: 26px; padding: 8px 16px; border: 1px solid var(--line); color: var(--ink); }
.service-panel .text-link:hover { background: var(--night); color: #fff; }
.article-shell { width: min(var(--wide), calc(100% - 48px)); margin: auto; padding: 62px 0 104px; }
.article-header { max-width: 848px; margin: 0 auto 44px; text-align: center; }
.article-header h1 { font-size: clamp(40px, 5vw, 58px); letter-spacing: -.02em; line-height: 1.18; }
.article-dek { max-width: 730px; margin: 26px 0 0; color: var(--muted); font-size: clamp(18px, 2vw, 21px); line-height: 1.68; }
.article-meta { display: flex; justify-content: center; gap: 18px; margin-top: 24px; letter-spacing: .08em; text-transform: uppercase; }
.article-meta span + span::before { content: "·"; margin-right: 18px; color: var(--line); }
.hero { max-width: var(--wide); margin: 0 auto 74px; background: var(--night); }
.hero img { display: block; width: 100%; aspect-ratio: 4 / 3; object-fit: cover; }
.article-body { max-width: var(--content); margin: auto; color: #292a27; font-size: 17px; line-height: 1.82; }
.article-body > p { margin: 1.18em 0; }
.article-body > p:first-of-type { font-size: 1.08em; line-height: 1.78; }
.article-body h2 { margin: 2.8em 0 .72em; padding-top: .2em; color: var(--ink); font-size: clamp(28px, 3.4vw, 36px); letter-spacing: -.04em; line-height: 1.32; }
.article-body h3 { margin: 2em 0 .65em; font-size: 23px; letter-spacing: -.03em; }
.article-body strong { color: var(--ink); font-weight: inherit; }
.article-body a { overflow-wrap: anywhere; }
.article-body ul, .article-body ol { padding-left: 1.35em; }
.article-body li + li { margin-top: .45em; }
.article-downloads {
  margin: 52px 0 0;
  padding: 28px;
  border: 1px solid var(--line);
  background: #f5f2ea;
}
.article-downloads h2 { margin-top: 0; }
.article-downloads ul {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 20px 0 0;
  padding: 0;
  list-style: none;
}
.article-downloads li + li { margin-top: 0; }
.article-downloads a {
  display: inline-block;
  padding: 10px 14px;
  border: 1px solid var(--ink);
  color: var(--ink);
  text-decoration: none;
}
.article-downloads a:hover { background: var(--ink); color: var(--paper); }
.article-note {
  margin: 0 0 48px !important;
  padding: 26px 28px !important;
  border-left: 2px solid var(--accent);
  background: var(--surface);
  color: #3e3f3a !important;
  font-size: 15px;
  line-height: 1.72;
}
.article-note > p { margin: 0 !important; }
.article-contact {
  margin: 76px 0 0 !important;
  padding: 34px !important;
  background: var(--night);
  color: #f5f1e8 !important;
  font-size: 15px !important;
  line-height: 1.72 !important;
}
.article-contact > p { margin: 0 !important; color: inherit !important; }
.article-contact strong { color: inherit; }
.article-contact a { color: var(--accent-light); font-weight: 400; }
.wp-block-table {
  display: block;
  width: min(1000px, calc(100vw - 48px));
  max-width: none;
  margin: 36px 0 50px;
  margin-left: 50%;
  overflow-x: auto;
  transform: translateX(-50%);
  border-top: 1px solid var(--ink);
  background: var(--surface);
  scrollbar-color: var(--muted) var(--surface-muted);
}
.wp-block-table table { width: 100%; min-width: 680px; border-collapse: collapse; background: transparent !important; font-size: 14px; line-height: 1.55; }
.wp-block-table th, .wp-block-table td { padding: 11px 13px !important; border: 0 !important; border-bottom: 1px solid var(--line) !important; background: transparent !important; color: var(--ink) !important; text-align: left; vertical-align: top; white-space: nowrap; }
.wp-block-table th { background: var(--night) !important; color: #fff !important; font-weight: 400; }
.wp-block-table.is-style-stripes tbody tr:nth-child(odd) { background: #f0ece3; }
.wp-block-table.is-style-stripes tbody tr:nth-child(even) { background: var(--surface); }
.has-text-align-right { text-align: right !important; }
.has-text-align-left { text-align: left !important; }
.has-text-align-center { text-align: center !important; }
.wp-element-caption, figcaption { margin: 10px 0 0; color: var(--muted); font-size: 13px; line-height: 1.55; }
.wp-block-image { width: min(1000px, calc(100vw - 48px)); max-width: none; margin: 40px 0 !important; margin-left: 50% !important; transform: translateX(-50%); }
.wp-block-image img { display: block; margin: auto; }
.wp-block-separator { margin: 52px 0; border: 0; border-top: 1px solid var(--line); }
.post-nav-wrap { max-width: var(--content); margin: 82px auto 0; padding-top: 28px; border-top: 1px solid var(--ink); }
.post-nav-wrap > .eyebrow { margin-bottom: 18px; }
.post-nav { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1px; background: var(--line); }
.post-nav--single { grid-template-columns: 1fr; background: transparent; }
.post-nav a { min-width: 0; padding: 22px; background: var(--surface); color: var(--ink); text-decoration: none; }
.post-nav a:hover { background: #f0ece3; }
.post-nav span { display: block; margin-bottom: 7px; color: var(--muted); font-size: 11px; letter-spacing: .08em; }
.post-nav strong { display: block; font-family: inherit; font-size: 17px; font-weight: inherit; line-height: 1.45; }
.about-shell .article-header { margin-bottom: 62px; }
.about-section-title { color: var(--accent); }
.privacy-copy h2:first-child { margin-top: 0; }
.settings-button, .site-footer button { padding: 0; border: 0; background: transparent; color: inherit; font: inherit; font-size: 12px; font-weight: 400; text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 4px; cursor: pointer; }
.settings-button { padding: 9px 13px; border: 1px solid var(--line); color: var(--accent); text-decoration: none; }
.analytics-choice { color: var(--muted); font-size: 14px; }
.consent-panel { position: fixed; right: 24px; bottom: 24px; z-index: 120; width: min(520px, calc(100% - 48px)); padding: 20px; border: 1px solid var(--line); background: var(--surface); box-shadow: 0 18px 52px rgba(21, 23, 20, .18); }
.consent-panel p { margin: 0; font-size: 14px; line-height: 1.65; }
.consent-actions { display: flex; align-items: center; gap: 9px; margin-top: 16px; }
.consent-actions button { min-height: 40px; padding: 8px 15px; border: 1px solid var(--ink); background: var(--ink); color: #fff; font: inherit; font-size: 13px; font-weight: 400; cursor: pointer; }
.consent-actions button + button { background: transparent; color: var(--ink); }
.consent-actions a { margin-left: auto; font-size: 12px; }
.site-footer { padding: 54px 0 58px; background: var(--night); color: #aeb0a9; }
.site-footer__inner { width: min(var(--wide), calc(100% - 48px)); margin: auto; display: flex; align-items: end; justify-content: space-between; gap: 32px; }
.site-footer strong { color: #fff; font-size: 14px; font-weight: inherit; }
.site-footer p { margin: 5px 0 0; font-size: 12px; }
.site-footer nav { display: flex; align-items: center; gap: 20px; }
.site-footer a, .site-footer button { color: #c6c7c0; font-size: 12px; font-weight: 400; }
@media (max-width: 960px) {
  .home-manifesto, .journal-row { gap: 24px; }
  .home-manifesto__copy, .journal-row__body { padding-right: 4px; padding-left: 4px; }
}
@media (max-width: 720px) {
  body { word-break: normal; }
  .site-header__inner, .home-shell, .article-shell, .site-footer__inner { width: calc(100% - 36px); }
  .site-header__inner { min-height: 62px; }
  .site-header nav a { min-width: 70px; min-height: 44px; padding: 0 10px; font-size: 13px; }
  .brand { flex-basis: auto; white-space: nowrap; font-size: 15px; letter-spacing: .03em; }
  .home-shell { padding: 22px 0 64px; }
  .home-intro { padding-bottom: 22px; }
  .home-intro h1 { font-size: clamp(34px, 10vw, 42px); }
  .home-manifesto, .journal-row, .journal-row--compact { grid-template-columns: 1fr; gap: 0; }
  .home-manifesto { padding-bottom: 24px; }
  .home-manifesto__copy { padding: 28px 2px 4px; }
  .home-manifesto__copy p { margin-bottom: 18px; }
  .journal-row { padding: 24px 0 28px; }
  .journal-row--reverse .journal-row__image, .journal-row--reverse .journal-row__body { grid-column: 1; grid-row: auto; }
  .journal-row--compact .journal-row__body { padding: 24px 2px 2px; }
  .journal-row--compact .journal-row__summary { font-size: 15px; }
  .journal-row__body { padding: 24px 2px 2px; }
  .journal-row__summary { font-size: 15px; }
  .journal-row__meta { margin-top: 22px; }
  .visitor-strip { grid-template-columns: 1fr auto; gap: 5px 12px; }
  .visitor-strip__label { grid-column: 1; }
  .visitor-strip__summary { grid-column: 1 / -1; grid-row: 2; }
  .visitor-strip__trend { grid-column: 1 / -1; grid-row: 3; }
  .visitor-strip__date { grid-column: 2; grid-row: 1; }
  .recent-section { margin-top: 24px; }
  .section-heading { padding: 7px 0 22px; }
  .section-heading h2 { font-size: 36px; }
  .service-panel { margin-top: 24px; padding: 34px 2px 38px; }
  .service-panel h2 { white-space: normal; }
  .service-panel > p:not(.eyebrow) { font-size: 15px; }
  .article-shell { padding: 58px 0 82px; }
  .article-header { margin-bottom: 38px; }
  .article-header h1 { font-size: clamp(36px, 10vw, 46px); }
  .article-dek { font-size: 17px; }
  .article-meta { flex-wrap: wrap; gap: 8px 12px; }
  .article-meta span + span::before { margin-right: 12px; }
  .hero { width: 100vw; margin-right: 50%; margin-bottom: 50px; margin-left: 50%; transform: translateX(-50%); }
  .article-body { font-size: 16px; line-height: 1.78; }
  .article-body h2 { font-size: 29px; }
  .article-note, .article-contact { padding: 24px 20px !important; }
  .wp-block-table, .wp-block-image { width: 100vw; margin-right: 50% !important; margin-left: 50% !important; transform: translateX(-50%); }
  .wp-block-table table { min-width: 640px; font-size: 13px; }
  .wp-block-table th, .wp-block-table td { padding: 10px 11px !important; }
  .post-nav { grid-template-columns: 1fr; }
  .site-footer__inner { align-items: flex-start; flex-direction: column; }
  .site-footer nav { flex-wrap: wrap; }
  .consent-panel { right: 18px; bottom: 18px; width: calc(100% - 36px); }
  .consent-actions { flex-wrap: wrap; }
  .consent-actions a { width: 100%; margin: 4px 0 0; }
}
@media (max-width: 380px) {
  .site-header__inner { gap: 8px; }
  .brand { gap: 6px; font-size: 13px; letter-spacing: 0; }
  .site-header nav a { min-width: 54px; padding: 0 6px; font-size: 12px; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  .journal-row__image img { transition: none; }
}
"""
SITE_JS = r"""
(() => {
  "use strict";

  const consentKey = "golgong-analytics-consent";
  const measurementNode = document.querySelector('meta[name="google-analytics-id"]');
  const measurementId = measurementNode ? measurementNode.content.trim() : "";
  const validMeasurementId = /^G-[A-Z0-9]{6,20}$/.test(measurementId);
  let pageViewSent = false;

  function readChoice() {
    try { return localStorage.getItem(consentKey); } catch (_) { return null; }
  }

  function saveChoice(value) {
    try { localStorage.setItem(consentKey, value); } catch (_) { /* keep this visit only */ }
  }

  function updateChoiceText() {
    const node = document.querySelector("[data-analytics-choice]");
    if (!node) return;
    const choice = readChoice();
    node.textContent = choice === "granted"
      ? "현재 설정: 허용"
      : choice === "denied" ? "현재 설정: 거부" : "현재 설정: 선택 전";
  }

  function setAnalyticsDisabled(disabled) {
    window[`ga-disable-${measurementId}`] = disabled;
  }

  function grantAnalytics() {
    if (!validMeasurementId) return;
    setAnalyticsDisabled(false);
    if (typeof window.gtag !== "function") return;
    window.gtag("consent", "update", { analytics_storage: "granted" });
    if (pageViewSent) return;
    pageViewSent = true;
    window.gtag("event", "page_view", {
      page_location: window.location.href,
      page_title: document.title
    });
  }

  function clearAnalyticsCookies() {
    document.cookie.split(";").forEach((item) => {
      const name = item.split("=")[0].trim();
      if (!name.startsWith("_ga")) return;
      document.cookie = `${name}=; Max-Age=0; path=/; SameSite=Lax`;
      document.cookie = `${name}=; Max-Age=0; path=/; domain=.${location.hostname}; SameSite=Lax`;
    });
  }

  function closeConsentPanel() {
    const panel = document.querySelector(".consent-panel");
    if (panel) panel.remove();
  }

  function chooseAnalytics(value) {
    saveChoice(value);
    if (value === "granted") {
      grantAnalytics();
    } else {
      setAnalyticsDisabled(true);
      if (typeof window.gtag === "function") {
        window.gtag("consent", "update", { analytics_storage: "denied" });
      }
      clearAnalyticsCookies();
    }
    updateChoiceText();
    closeConsentPanel();
  }

  function showConsentPanel(shouldFocus = false) {
    if (!validMeasurementId) return;
    closeConsentPanel();
    const panel = document.createElement("section");
    panel.className = "consent-panel";
    panel.setAttribute("aria-label", "방문 분석 설정");

    const message = document.createElement("p");
    message.textContent = "이 사이트는 Google Analytics를 사용합니다. 허용하기 전에는 방문 분석 이벤트를 보내거나 분석 쿠키를 저장하지 않습니다.";
    panel.appendChild(message);

    const actions = document.createElement("div");
    actions.className = "consent-actions";
    const allow = document.createElement("button");
    allow.type = "button";
    allow.textContent = "허용";
    allow.addEventListener("click", () => chooseAnalytics("granted"));
    const deny = document.createElement("button");
    deny.type = "button";
    deny.textContent = "거부";
    deny.addEventListener("click", () => chooseAnalytics("denied"));
    const policy = document.createElement("a");
    policy.href = "/privacy/";
    policy.textContent = "자세히 보기";
    actions.append(allow, deny, policy);
    panel.appendChild(actions);
    document.body.appendChild(panel);
    if (shouldFocus) allow.focus();
  }

  function initAnalytics() {
    document.querySelectorAll("[data-analytics-settings]").forEach((button) => {
      button.addEventListener("click", () => showConsentPanel(true));
    });
    updateChoiceText();
    const choice = readChoice();
    if (choice === "granted") grantAnalytics();
    if (choice !== "granted" && choice !== "denied") showConsentPanel(false);
  }

  function requireCount(value) {
    return Number.isSafeInteger(value) && value >= 0 ? value : null;
  }

  function formatDate(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || "");
    if (!match) return "";
    return `${Number(match[2])}월 ${Number(match[3])}일까지`;
  }

  function drawWeeklyBars(node, values) {
    node.replaceChildren();
    const visible = values.filter((value) => value !== null);
    if (visible.length < 2) {
      node.hidden = true;
      return;
    }
    const maximum = Math.max(...visible, 1);
    values.forEach((value) => {
      const bar = document.createElement("span");
      bar.style.height = value === null ? "3px" : `${Math.max(3, Math.round(value / maximum * 22))}px`;
      bar.style.opacity = value === null ? ".2" : ".72";
      node.appendChild(bar);
    });
    node.hidden = false;
    node.setAttribute("role", "img");
    node.setAttribute("aria-label", `최근 4주 분석 허용 방문자 ${values.map((value) => value === null ? "5명 미만" : `${value}명`).join(", ")}`);
  }

  async function initVisitorStats() {
    const root = document.querySelector("[data-visitor-stats]");
    if (!root) return;
    try {
      const response = await fetch("/data/visitor-stats.json", { cache: "no-store" });
      if (!response.ok) throw new Error("visitor stats unavailable");
      const stats = await response.json();
      const summary = root.querySelector("[data-visitor-summary]");
      const trend = root.querySelector("[data-visitor-trend]");
      const changeNode = root.querySelector("[data-visitor-change]");
      const bars = root.querySelector("[data-visitor-bars]");
      const dateNode = root.querySelector("[data-visitor-date]");
      dateNode.textContent = formatDate(stats.throughDate);

      if (stats.status === "collecting") return;
      if (stats.status === "low_volume") {
        summary.textContent = "최근 7일 분석 허용 방문자 5명 미만";
        trend.hidden = true;
        return;
      }
      const visitors = requireCount(stats.current7Days && stats.current7Days.visitors);
      const pageViews = requireCount(stats.current7Days && stats.current7Days.pageViews);
      if (stats.status !== "ok" || visitors === null || pageViews === null) throw new Error("invalid visitor stats");
      const number = new Intl.NumberFormat("ko-KR");
      summary.textContent = `최근 7일 분석 허용 방문자 ${number.format(visitors)}명 · 페이지 조회 ${number.format(pageViews)}회`;

      const change = Number.isSafeInteger(stats.changeVisitors) ? stats.changeVisitors : null;
      if (change === null) {
        changeNode.textContent = "비교할 이전 기간이 없습니다.";
      } else if (change > 0) {
        changeNode.textContent = `지난 7일보다 ${number.format(change)}명 늘었습니다.`;
      } else if (change < 0) {
        changeNode.textContent = `지난 7일보다 ${number.format(Math.abs(change))}명 줄었습니다.`;
      } else {
        changeNode.textContent = "지난 7일과 같습니다.";
      }
      const weeklySource = stats.weeklyVisitors;
      if (!Array.isArray(weeklySource) || weeklySource.length !== 4) throw new Error("invalid weekly visitor stats");
      const weekly = weeklySource.map((value) => value === null ? null : requireCount(value));
      if (weekly.some((value, index) => value === null && weeklySource[index] !== null)) {
        throw new Error("invalid weekly visitor count");
      }
      drawWeeklyBars(bars, weekly);
      trend.hidden = false;
    } catch (_) {
      root.hidden = true;
    }
  }

  initAnalytics();
  initVisitorStats();
})();
"""
SITE_JS_VERSION = hashlib.sha256((SITE_JS.strip() + "\n").encode("utf-8")).hexdigest()[:12]

CSS_VERSION = hashlib.sha256((CSS.strip() + "\n").encode("utf-8")).hexdigest()[:12]


def validate(data: dict) -> None:
    posts = data["posts"]
    if len(posts) != 16:
        raise RuntimeError(f"expected 16 posts, got {len(posts)}")
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
    write(ROOT / "privacy" / "index.html", render_privacy())
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
    write(ROOT / "assets" / "js" / "site.js", SITE_JS.strip() + "\n")
    write(ROOT / "404.html", f"""{page_head(title='페이지를 찾을 수 없습니다 | '+SITE_NAME, description='요청한 페이지를 찾을 수 없습니다.', canonical=SITE_URL+'/404.html', og_type='website', robots='noindex,follow')}<body>{site_header()}<main id="main-content" class="article-shell" tabindex="-1"><article><header class="article-header"><p class="eyebrow">404</p><h1>페이지를 찾을 수 없습니다</h1><p class="article-dek">주소를 다시 확인하거나 글 목록에서 원하는 내용을 찾아보십시오.</p></header><p><a class="text-link" href="/">글 목록으로 돌아가기 <span aria-hidden="true">→</span></a></p></article></main>{site_footer()}</body></html>\n""")

    tracked = [ROOT / "index.html", ROOT / "about" / "index.html",
               ROOT / "privacy" / "index.html", ROOT / "feed.xml",
               ROOT / "sitemap.xml", ROOT / "robots.txt", ROOT / "404.html",
               ROOT / "assets" / "css" / "site.css", ROOT / "assets" / "js" / "site.js"]
    tracked.extend(ROOT / p["path"].lstrip("/") / "index.html" for p in posts)
    tracked.extend([
        ROOT / "assets" / "data" / "naver-shopping-api-category-matching-test" / "method-results.csv",
        ROOT / "assets" / "data" / "naver-shopping-api-category-matching-test" / "split-results.csv",
        ROOT / "assets" / "data" / "naver-shopping-api-category-matching-test" / "summary.json",
    ])
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
