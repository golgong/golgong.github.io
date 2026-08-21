# 네이버·구글 검색 등록

등록할 사이트 주소는 항상 `https://golgong.github.io`입니다.

## 네이버 서치어드바이저

1. [네이버 서치어드바이저](https://searchadvisor.naver.com/)의 **웹마스터 도구 → 사이트 관리**에서 `https://golgong.github.io`를 추가합니다.
2. 소유확인 방식은 **HTML 파일 업로드**를 선택합니다.
3. 네이버가 내려 준 파일을 이름과 내용 변경 없이 저장소 루트에 둡니다.
4. `main` 배포 후 `https://golgong.github.io/네이버확인파일.html`이 HTTP 200인지 확인합니다.
5. 네이버에서 소유확인을 마칩니다.
6. **요청 → 사이트맵 제출**에 `https://golgong.github.io/sitemap.xml`을 입력합니다.
7. **요청 → RSS 제출**에 `https://golgong.github.io/feed.xml`을 입력합니다.
8. 홈과 주요 글 URL을 **웹 페이지 수집요청**에 제출합니다.
9. **검증 → URL 검사**와 **현황 → 수집 현황**에서 오류를 확인합니다.

확인 파일은 대표님이 네이버에 로그인해 받아야 합니다. 임의의 파일이나 메타태그를 만들면 소유확인이 되지 않습니다.

## Google Search Console

1. [Google Search Console](https://search.google.com/search-console/)에서 속성을 추가합니다.
2. **도메인**이 아니라 **URL 접두어**를 선택하고 `https://golgong.github.io/`를 입력합니다.
3. **HTML 파일** 확인 방식을 선택합니다.
4. Google이 내려 준 파일을 이름과 내용 변경 없이 저장소 루트에 둡니다.
5. 배포 후 해당 파일이 HTTP 200인지 확인하고 소유확인을 마칩니다.
6. **색인 생성 → Sitemaps**에서 `sitemap.xml`을 제출합니다.
7. **URL 검사**에서 홈과 14개 글을 확인하고 필요한 글은 색인 생성을 요청합니다.

## WordPress 이전 주소

새 글 경로는 기존 WordPress 경로와 날짜·슬러그를 같게 만들었습니다. 예:

```text
https://golgong.wordpress.com/2026/08/20/baby-names-seoul/
https://golgong.github.io/2026/08/20/baby-names-seoul/
```

검색 신호를 가장 잘 옮기려면 WordPress.com의 Site Redirect를 최소 1년 유지해 기존 주소를 같은 경로의 GitHub 주소로 301 리디렉션합니다. Site Redirect를 사용하지 않는 동안에는 기존 글에 새 글의 절대 주소를 담은 이전 안내를 유지합니다.
