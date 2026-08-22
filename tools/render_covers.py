from __future__ import annotations

import hashlib
import html
import json
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "blog.json"
SOURCE_DIR = ROOT / "tools" / "cover_sources"
SYSTEM_FONT = Path(r"C:\Windows\Fonts\NotoSansKR-VF.ttf")
BRAND = "골때리는공작소"
SITE = "golgong.github.io"

TITLE_LINES = {
    "one-person-households-top-districts": [
        "1인 가구가 가장 많은",
        "동네는 어디인가",
        "— 전국 196개 시군구 집계",
    ],
    "ad-depth-ctr": ["같은 클릭률인데", "광고비가 35배 차이납니다"],
    "clinic-open-by-specialty": ["개원 수는 그대로인데", "진료과목이 달라졌습니다"],
    "clinic-location-by-specialty": ["동네별 병원", "진료과목 분포"],
    "internal-medicine-review-count": ["내과 5,786곳,", "리뷰 많은 곳"],
    "hospital-keyword-ad-cost": ["병원 검색어 광고비,", "클릭 한 번에", "980원에서 9만원"],
    "orthopedics-review-count": ["정형외과 2,841곳,", "리뷰 많은 곳"],
    "dermatology-review-count": ["피부과 1,556곳,", "리뷰 많은 곳"],
    "dental-clinic-review-count": ["치과 19,396곳,", "리뷰 많은 곳"],
    "cosmetic-medical-keyword-ad-cost": ["임플란트 클릭 한 번에", "71,150원"],
    "manual-therapy-price-gap": ["같은 30분 도수치료,", "1만원과 30만원"],
    "what-119-actually-does": ["119는 불 끄러", "가지 않는다"],
    "most-used-medicines-korea": ["한국인이 제일 많이", "먹는 약"],
    "baby-names-seoul": ["민준이는 어디 갔을까"],
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def title_size(lines: list[str], wide: bool) -> int:
    longest = max(len(line) for line in lines)
    if wide:
        return 50 if longest >= 20 else 56 if longest >= 15 else 64
    return 60 if longest >= 20 else 68 if longest >= 15 else 78


def cover_html(
    *,
    source: Path,
    lines: list[str],
    label: str,
    width: int,
    height: int,
    wide: bool,
) -> str:
    safe_x = 58 if wide else 72
    safe_top = 48 if wide else 62
    safe_bottom = 48 if wide else 72
    brand_size = 20 if wide else 24
    url_size = 16 if wide else 18
    label_size = 15 if wide else 17
    main_size = title_size(lines, wide)
    title_width = 82 if wide else 78
    line_markup = "".join(f"<span>{html.escape(line)}</span>" for line in lines)
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<style>
@font-face {{ font-family: CoverSystem; src: url('{SYSTEM_FONT.as_uri()}') format('truetype'); font-style: normal; font-weight: 400; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; width: {width}px; height: {height}px; overflow: hidden; background: #111719; }}
.cover {{ position: relative; width: 100%; height: 100%; overflow: hidden; color: #f7f3ea; background: #111719; }}
.art {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: center; }}
.cover::before {{
  content: ""; position: absolute; inset: 0; z-index: 1;
  background:
    linear-gradient(180deg, rgba(9,12,11,.58) 0%, rgba(9,12,11,.08) 30%, rgba(9,12,11,.20) 48%, rgba(8,10,9,.92) 100%),
    linear-gradient(90deg, rgba(8,10,9,.52) 0%, rgba(8,10,9,.12) 58%, rgba(8,10,9,.04) 100%);
}}
.cover::after {{ content: ""; position: absolute; inset: 18px; z-index: 2; border: 1px solid rgba(247,243,234,.18); pointer-events: none; }}
.mast {{ position: absolute; z-index: 3; top: {safe_top}px; left: {safe_x}px; right: {safe_x}px; display: flex; align-items: center; justify-content: space-between; font-family: CoverSystem, sans-serif; font-weight: 400; }}
.brand {{ display: flex; align-items: center; gap: 13px; font-size: {brand_size}px; letter-spacing: -.02em; white-space: nowrap; }}
.brand::before {{ content: ""; width: 10px; height: 10px; background: #c77555; transform: rotate(45deg); flex: 0 0 auto; }}
.url {{ font-size: {url_size}px; letter-spacing: .07em; white-space: nowrap; }}
.rule {{ position: absolute; z-index: 3; top: {safe_top + 52}px; left: {safe_x}px; right: {safe_x}px; height: 1px; background: rgba(247,243,234,.42); }}
.copy {{ position: absolute; z-index: 3; left: {safe_x}px; right: {safe_x}px; bottom: {safe_bottom}px; }}
.label {{ margin: 0 0 {18 if wide else 24}px; font-family: CoverSystem, sans-serif; font-weight: 400; font-size: {label_size}px; letter-spacing: .2em; color: #d59a78; }}
.title {{ margin: 0; width: {title_width}%; font-family: CoverSystem, sans-serif; font-weight: 400; font-size: {main_size}px; line-height: 1.16; letter-spacing: -.045em; text-wrap: balance; text-shadow: 0 2px 18px rgba(0,0,0,.28); }}
.title span {{ display: block; white-space: nowrap; }}
</style>
</head>
<body>
  <main class="cover">
    <img class="art" src="{source.as_uri()}" alt="">
    <header class="mast"><div class="brand">{BRAND}</div><div class="url">{SITE}</div></header>
    <div class="rule"></div>
    <section class="copy"><p class="label">{html.escape(label)}</p><h1 class="title">{line_markup}</h1></section>
  </main>
</body>
</html>"""


def render(page, *, source: Path, lines: list[str], label: str, output: Path, width: int, height: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".html", encoding="utf-8", delete=False) as temp:
        temp_path = Path(temp.name)
        temp.write(
            cover_html(
                source=source,
                lines=lines,
                label=label,
                width=width,
                height=height,
                wide=width / height > 1.5,
            )
        )
    try:
        page.set_viewport_size({"width": width, "height": height})
        page.goto(temp_path.as_uri(), wait_until="load")
        page.evaluate("document.fonts.ready")
        page.wait_for_function("document.querySelector('.art').complete && document.querySelector('.art').naturalWidth > 0")
        page.screenshot(path=str(output), type="jpeg", quality=92, full_page=False)
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    posts = sorted(data["posts"], key=lambda post: post["date"])
    missing = {post["slug"] for post in posts} - set(TITLE_LINES)
    if missing:
        raise SystemExit(f"missing title line rules: {sorted(missing)}")
    for post in posts:
        if "".join(TITLE_LINES[post["slug"]]).replace(" ", "") != post["title"].replace(" ", ""):
            raise SystemExit(f"title line rule differs from source: {post['slug']}")
    if not SYSTEM_FONT.is_file():
        raise SystemExit("Noto Sans KR font is missing")

    outputs: list[Path] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(device_scale_factor=1)
        for post in posts:
            source = SOURCE_DIR / f"{post['slug']}.webp"
            if not source.is_file():
                raise SystemExit(f"missing source image: {source}")
            target_dir = ROOT / "assets" / "images" / post["slug"]
            version = "v3" if post["slug"] == "baby-names-seoul" else "v2"
            featured = target_dir / f"featured-{version}.jpg"
            og = target_dir / f"og-{version}.jpg"
            render(page, source=source, lines=TITLE_LINES[post["slug"]], label="DATA RECORD", output=featured, width=1448, height=1086)
            render(page, source=source, lines=TITLE_LINES[post["slug"]], label="DATA RECORD", output=og, width=1200, height=630)
            outputs.extend((featured, og))

        home_source = SOURCE_DIR / "home.png"
        home_dir = ROOT / "assets" / "images" / "home"
        home_featured = home_dir / "hero-v2.jpg"
        home_og = home_dir / "og-v2.jpg"
        home_lines = ["아무도 세어 보지 않은 것을", "끝까지 확인합니다"]
        render(page, source=home_source, lines=home_lines, label="INDEPENDENT DATA JOURNAL", output=home_featured, width=1448, height=1086)
        render(page, source=home_source, lines=home_lines, label="INDEPENDENT DATA JOURNAL", output=home_og, width=1200, height=630)
        outputs.extend((home_featured, home_og))
        browser.close()

    rendered_hashes = {
        "/" + path.relative_to(ROOT).as_posix(): file_sha256(path)
        for path in outputs
    }
    updated_paths: set[str] = set()
    for image in data["images"]:
        if image["path"] in rendered_hashes:
            image["sha256"] = rendered_hashes[image["path"]]
            updated_paths.add(image["path"])
    if updated_paths != set(rendered_hashes):
        missing_paths = sorted(set(rendered_hashes) - updated_paths)
        raise SystemExit(f"rendered images missing from blog manifest: {missing_paths}")
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for path in outputs:
        rel = "/" + path.relative_to(ROOT).as_posix()
        print(f"{rel}\t{path.stat().st_size}\t{rendered_hashes[rel]}")
    print(f"RENDERED={len(outputs)}")


if __name__ == "__main__":
    main()
