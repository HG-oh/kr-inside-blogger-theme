# KR Inside Journal

네 Blogger 사이트의 공통 디자인과 도메인별 메뉴를 관리하는 독립 테마입니다. 기존 `HG-oh/kr-inside-styles`는 수정하지 않습니다.

CSS와 JavaScript는 `assets/theme.css`, `assets/theme.js` 한 벌을 사용합니다. 도메인별 XML에는 각 사이트의 메뉴·소개·인증·분석·광고 설정을 반영합니다.

| 사이트 | 설정 파일 | 보존한 원본 메뉴 URL | 메뉴 그룹 | 관심 태그 |
| --- | --- | ---: | ---: | ---: |
| www.kr-inside.com | `sites/www.json` | 23 | 9 | 12 |
| news.kr-inside.com | `sites/news.json` | 23 | 6 | 8 |
| trip.kr-inside.com | `sites/trip.json` | 31 | 8 | 12 |
| item.kr-inside.com | `sites/item.json` | 29 | 6 | 4 |

`www`는 경제·생활과 언어별 메뉴, `news`는 전국 모음과 지역별 뉴스, `trip`은 한국어·영어·일본어·베트남어·중국어 여행 메뉴를 유지합니다. 여행 원본의 Blogspot 지역 뉴스 URL도 임의 변경하지 않았습니다. 실제 주소가 없는 About/Contact, 숨겨진 데모 메뉴는 추가하지 않습니다. Home은 각 블로그 홈으로 연결합니다.

세 새 프로필은 각각의 Naver 인증값, 원본 GTM·Clarity ID, 선택 태그와 기존 애드센스 단위를 보존합니다. 제목·게시물·페이지·댓글은 Blogger의 실제 데이터를 사용합니다.

## 공통 기능

- 모바일·PC 한 줄에 한 글, 한 페이지 24개 후 다음 페이지
- Blogger 기본 인기글 5개, 같은 도메인의 최근글 4개
- 썸네일 필드가 비어 있으면 본문·요약 이미지 사용
- 메뉴 +/− 기호의 Blogger 문자 변환 오류 수정
- 6·12·18번째 글 뒤, 다음 글이 있을 때만 반응형 광고 배치
- 스크롤 접근 시 각 광고 한 번 요청; 기존 SDK 재사용
- 자동·밝게·어둡게 화면, 키보드 메뉴 이동, 기존 본문 스타일 지원
- www·trip 상단의 한국어·English·日本語·Tiếng Việt·中文 선택
- news 상단의 전체·서울·부산·대전·대구·광주·인천·울산·경기 선택

목록을 24개까지 채우는 과정은 같은 사이트의 실제 다음 페이지를 사용합니다. 오류가 발생하면 이미 표시한 글을 유지하고 재시도와 다음 페이지 링크를 제공합니다. JavaScript 비활성 시 Blogger가 출력하는 기본 목록과 메뉴를 사용합니다. 광고 송출은 AdSense 상태에 따라 달라집니다.

www·trip의 기본 홈은 한국어입니다. 원본 메뉴·관심 태그의 외국어 태그와 해당 언어의 하위 태그를 분류에 사용하며, 한국어 전용 태그를 새로 요구하지 않습니다. 확인된 외국어 태그가 없는 글은 한국어로 분류합니다. 외국어 버튼은 기존 언어 태그 페이지로 연결하고, 뉴스 버튼은 기존 지역 태그 페이지로 연결합니다. 최근 게시물도 선택 언어·지역에 맞춥니다. 인기 게시물은 Blogger의 기존 전체 인기 순위를 유지합니다.

한국어 목록은 Blogger 출력 단계에서 외국어 태그가 있는 글을 제외하고, JavaScript가 실제 다음 페이지를 이어 읽어 한국어 글 24개를 채웁니다. 번역 글만 있는 구간도 건너뛰되 실제 페이지 주소를 유지합니다. 무한 요청을 막기 위해 한 번에 최대 48개 원본 페이지를 읽으며, 실패·제한 도달 시 현재 글과 다음 페이지·재시도 기능을 제공합니다. 최근 한국어 글은 기본 피드를 최대 6페이지 읽어 4개를 찾습니다. 언어 선택은 저장하지 않으므로 홈에 돌아오면 항상 한국어가 기본입니다.

## 구성

| 경로 | 역할 |
| --- | --- |
| `assets/theme.css`, `assets/theme.js` | 네 사이트가 공유하는 디자인·동작 |
| `sites/*.json` | 도메인별 원본 메뉴, 소개, 태그, 인증, 분석, 광고 ID |
| `templates/theme.xml.in` | 공유 Blogger 구조 |
| `templates/ad-content.html` | 기존 광고 위젯 구조; 프로필의 계정·슬롯 적용 |
| `navigation.json` | 최초 item 메뉴 추출 기록; 현재 빌드는 `sites/item.json` 사용 |
| `tools/build.py` | 도메인별 XML 생성과 공개 자산 검증 |
| `tools/preview.py` | 실제 XML을 예시 데이터로 렌더링 |
| `tests/domains.py` | 원본에서 독립 추출한 기대값과 도메인별 출력 검증 |
| `tests/content_selectors.py` | 언어·지역 링크, 한국어 기본 출력, 다국어 페이지·피드 경계 검증 |
| `tests/validate.py`, `tests/listing.py`, `tests/ads.py` | 반응형·목록·썸네일·광고 회귀 검사 |

## XML 생성

Python 3.10 이상이며, 독립형 XML 생성에는 인터넷이 필요하지 않습니다.

```bash
python3 tools/build.py --site all --out dist
python3 tools/build.py --site www --out dist/www
```

`dist/www/kr-inside-www.xml`, `dist/news/kr-inside-news.xml`, `dist/trip/kr-inside-trip.xml`이 생성됩니다. `item`은 이전 명령과 호환되는 `kr-inside-new.xml`을 사용합니다. `--site`를 생략하면 item을 빌드합니다.

독립형 XML에는 동일한 CSS·JS가 포함되어 있어 업로드 즉시 동작합니다. 이 모드에서는 이후 Git 수정이 운영 블로그에 자동 반영되지는 않습니다. 각 manifest에 원본 파일 해시, 보존 링크 수, 자산 해시를 기록합니다.

## 공통 GitHub 자산 게시

공통 저장소: [HG-oh/kr-inside-blogger-theme](https://github.com/HG-oh/kr-inside-blogger-theme). `main`의 공통 CSS·JS를 네 도메인에서 같은 주소로 사용합니다. 변경을 검증한 뒤 이 저장소에 게시합니다.

게시 후 같은 공개 자산 URL을 네 XML에 사용합니다.

```bash
python3 tools/build.py --site all --out dist/shared \
  --asset-base https://cdn.jsdelivr.net/gh/HG-oh/kr-inside-blogger-theme@main/assets
```

생성기는 실제 CSS·JS의 HTTPS 응답, 콘텐츠 유형, SHA-256이 로컬 코드와 일치해야 `*-external.xml`을 생성합니다. 존재하지 않는 주소의 설치용 XML은 제공하지 않습니다.

`@main`은 공통 변경을 각 블로그에 반영하기 위한 주소이며, CDN·브라우저 캐시가 갱신되기까지 시간이 걸릴 수 있습니다. 버전 고정이 필요하면 `main`을 공개된 전체 커밋 해시로 바꿉니다. 고정 모드에서는 다음 버전 배포 시 XML의 주소도 갱신해야 합니다.

현재 item XML도 독립형이므로 네 사이트 전체를 외부 공통 자산으로 전환하려면 item용 외부 XML도 한 번 업로드해야 합니다. 기존 CSS 저장소를 사용하는 예전 테마는 변경하지 않습니다.

## 검증

```bash
python3 -m pip install -r requirements-dev.txt
python3 tools/build.py --site all --out dist
python3 tools/preview.py --xml dist/www/kr-inside-www.xml --out dist/www/previews --inline-assets
```

다른 도메인도 같은 방식으로 미리보기를 생성한 뒤 `python3 tests/domains.py --root dist --report dist/validation-domains.json`을 실행합니다. `tests/validate.py`는 `--inventory`로 도메인별 URL 기대값을 받을 수 있습니다.

`python3 tests/content_selectors.py`는 실제 생성 XML과 시험용 다국어 게시물·피드로 선택 동작을 검증합니다. 실제 사이트가 접근을 차단하면 원본 XML에서 확인한 태그를 기준으로 검사하며, 운영 글의 태그 일관성이나 Blogger 서버에서의 템플릿 컴파일까지 확인했다는 의미는 아닙니다.

검증은 실제 XML 구조와 공유 자산을 사용하되 글·그림·Google 광고·분석 응답은 시험 데이터입니다. 원본 XML의 스크립트는 실행하지 않고 필요한 공개 설정값만 읽었습니다. Blogger 서버의 실제 업로드·광고 송출·댓글 제출까지 검증한 결과는 아닙니다.
