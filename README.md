# 골때리는공작소 블로그

`https://golgong.github.io`에서 공개되는 정적 블로그입니다.

## 구성

- `data/blog.json`: 공개 글 16편과 소개 페이지의 원문 데이터
- `assets/images/`: WordPress에서 옮긴 대표 이미지와 본문 이미지
- `tools/build_site.py`: 홈·개별 글·RSS·사이트맵 생성
- `tools/validate_site.py`: 본문·표·이미지·링크·검색 메타정보 검증
- `tools/migrate_wordpress.py`: 최초 이전용 WordPress 가져오기 도구

초안은 공개 저장소에 넣지 않습니다.

## 다시 만들기

```powershell
python .\tools\build_site.py
python .\tools\validate_site.py
```

검증이 통과한 파일만 공개합니다. Git 커밋 작성자는 아래 값을 사용합니다.

```text
golgong <54047541+golgong@users.noreply.github.com>
```

검색 등록 절차는 [SEARCH_REGISTRATION.md](SEARCH_REGISTRATION.md)를 따릅니다.
