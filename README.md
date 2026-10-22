# KR Inside Journal

네 Blogger 사이트를 위한 새 독립 테마입니다. 기존 `HG-oh/kr-inside-styles`와 별도 디렉터리·Git 이력·CSS·JavaScript를 사용합니다.

- 모바일·PC 모두 한 줄에 한 글씩 표시하고 한 페이지에 24개까지 이어 읽는 목록
- Blogger가 직접 출력하는 게시물, 이미지, 최근 한 달 인기글 5개
- 같은 블로그의 피드에서 가져오는 최근글 4개; 썸네일 필드가 없으면 본문·요약 이미지 사용, 이미지 오류 시 다음 후보 재시도
- 원본 메뉴의 실제 목적지 29개 보존; 중복을 정리한 6개 메뉴 그룹
- 네 도메인별 소개·현재 메뉴 표시, 검색·페이지 이동, 자동/밝게/어둡게 모드
- 기존 글의 FAQ·상품 카드·목차·표 스타일 지원
- 원본 광고 위젯과 사이트 인증값 유지; 댓글·분석은 Blogger 기본 기능 사용

적용 도메인: `www.kr-inside.com`, `news.kr-inside.com`, `trip.kr-inside.com`, `item.kr-inside.com`.

## 구성

| 파일 | 수정할 내용 |
| --- | --- |
| `assets/theme.css` | 레이아웃·색상·본문·반응형 스타일 |
| `assets/theme.js` | 메뉴 보조 동작·화면 모드·최근글·도메인별 소개 |
| `navigation.json` | 원본 링크를 유지한 메뉴 그룹 |
| `templates/theme.xml.in` | Blogger 위젯과 화면 구조 |
| `templates/ad-content.html` | 원본 광고 코드 |
| `tools/build.py` | XML 생성 및 공개 자산 확인 |
| `tools/preview.py` | 실제 XML 구조와 예시 데이터로 검증용 HTML 생성 |
| `tests/validate.py` | 구조·메뉴·반응형·기능 검증 |
| `tests/listing.py` | 24개 목록·다음 페이지·최근글 본문 이미지 회귀 검사 |

`Home`의 이전 `{homeIcon}` 값은 Blogger의 현재 홈 주소로 대체했습니다. 네이버·일본어 경제적자유 중복 링크는 한 번씩 유지하며, 주소가 비어 있던 About/Contact와 숨겨진 이전 Blogspot 홈은 새 메뉴에 넣지 않았습니다.

## XML 생성

Python 3.10 이상이 필요합니다. 기본 XML 생성은 표준 라이브러리만 사용하고 인터넷이 필요하지 않습니다.

```bash
python3 tools/build.py --out dist
```

`dist/kr-inside-new.xml`은 새 CSS·JS를 포함한 독립형 XML입니다. 공개되지 않은 파일을 참조하지 않으므로 자산 게시 전에도 사용할 수 있습니다. `manifest.json`에 실제 크기와 해시가 기록됩니다. Blogger의 테마에서 이 XML을 업로드합니다. Blogger 레이아웃에서 인기글 위젯 설정과 추가 사이드바·광고 위젯을 관리할 수 있습니다.

## 새 저장소 게시 후 외부 자산 사용

예정 저장소는 `HG-oh/kr-inside-blogger-theme`입니다. 먼저 새 저장소에 코드를 게시하고, 해당 커밋의 자산이 실제로 제공되는지 확인합니다.

```bash
python3 tools/build.py --out dist \
  --asset-base https://cdn.jsdelivr.net/gh/HG-oh/kr-inside-blogger-theme@COMMIT/assets
```

`COMMIT`은 실제 게시된 커밋 전체 해시로 바꿉니다. 생성기는 두 자산의 HTTPS 응답·콘텐츠 유형·SHA-256이 로컬 파일과 일치할 때만 `kr-inside-new-external.xml`을 만듭니다. 이 XML은 공통 CSS·JS를 네 블로그에서 같은 주소로 사용합니다. 검증한 커밋을 고정하므로 공통 자산의 새 버전을 배포할 때 XML 주소도 갱신합니다. 존재하지 않는 URL의 XML은 배포하지 않습니다.

GitHub API 연결은 가능하지만, 현재 GitHub 앱에는 새 저장소 생성 권한이 없어 생성 요청이 403 `Resource not accessible by integration`으로 거절되었습니다. 새 공개 저장소를 만들고 앱 접근 권한을 부여한 뒤 게시할 수 있습니다. 기존 저장소는 수정하지 않았습니다. 이번 XML은 게시되지 않은 URL을 참조하지 않습니다.

## 브라우저 검증

검증용 의존성과 Linux Chromium(`/usr/bin/chromium`)이 필요합니다. 현재 클라우드 환경에는 설치되어 있습니다.

```bash
python3 -m pip install -r requirements-dev.txt
python3 tools/build.py --out dist
python3 tools/preview.py --xml dist/kr-inside-new.xml --out dist/previews --inline-assets
python3 tests/validate.py --xml dist/kr-inside-new.xml --previews dist/previews --report dist/validation-results.json
python3 tests/listing.py --preview dist/previews/home.html --report dist/listing-results.json
```

검증 화면의 글과 그림은 예시입니다. 실제 XML에 들어 있는 CSS·JS와 메뉴·위젯 마크업을 검사하지만, 미리보기 렌더러는 Blogger 서버의 템플릿 컴파일러가 아닙니다. 댓글·광고·분석의 실제 서버 동작 및 Blogger 업로드 성공은 이 검사만으로 보증하지 않습니다. 운영 사이트 업로드와 댓글·광고 동작은 실제 Blogger에서 확인해야 합니다.

새 테마는 원본의 게시물·페이지 URL과 본문을 수정하지 않습니다. 숨겨진 원본 테마 전용 위젯·난독화 스크립트·jQuery·유효하지 않은 shortcode는 새 테마에서 사용하지 않습니다.

## 게시물 목록과 최근글 수정

Blogger가 홈페이지 글을 5개만 반환하는 경우에도 실제 다음 페이지를 같은 사이트에서 차례로 읽어 24개를 채웁니다. 마지막으로 읽은 페이지의 원래 다음 주소를 유지하므로 목록을 채운 뒤 다음 글로 이동합니다. 마지막 페이지는 남은 글만 표시합니다. 통신 오류가 발생하면 표시된 글을 유지하고 다시 불러오기 버튼과 다음 페이지 링크를 제공합니다. JavaScript를 끈 경우에는 Blogger가 출력한 기본 글 수와 페이지 이동을 사용합니다.

최근글 썸네일은 미디어 필드, 본문, 요약 순으로 찾습니다. 본문은 비활성 템플릿에서 읽고 이미지 주소만 가져옵니다. 본문 스크립트·외부 위젯은 실행하지 않습니다.
