# AI-Search-Engine-podcast

![Podcast Generator 배너](https://example.com/banner_image.jpg)  
Python 기반 팟캐스트 생성기로, 흥미로운 팟캐스트 스크립트를 자동으로 생성하고, 이를 음성으로 변환하며 배경음악을 추가하여 완성된 팟캐스트 에피소드를 만들어 줍니다. 이 팟캐스트는 두 명의 AI 진행자가 사용자 정의 주제를 토론하며 각기 다른 관점을 제공하는 형식으로 진행됩니다.

## 주요 기능

- **AI 스크립트 생성**: OpenAI를 사용하여 자동으로 대화형 팟캐스트 스크립트를 생성합니다.
- **텍스트 음성 변환**: 생성된 스크립트를 각기 다른 AI 목소리로 오디오로 변환합니다.
- **검색 통합**: 주제와 관련된 정보를 검색하고 그 결과를 팟캐스트 콘텐츠에 활용합니다.
- **배경음악 추가**: 청취 경험을 향상시키기 위해 배경음악을 추가합니다.
- **오디오 파일 저장**: 팟캐스트 에피소드를 MP3 형식으로 저장합니다.

## 사전 요구 사항

이 프로젝트를 실행하기 위해 다음이 필요합니다:

- Python 3.7+
- pip (Python 패키지 설치 관리자)
- ffmpeg (오디오 처리용)

### ffmpeg 설치

#### macOS:
```sh
brew install ffmpeg
```

#### Ubuntu:
```sh
sudo apt-get install ffmpeg
```

#### Windows:
[ffmpeg.org](https://ffmpeg.org/download.html)에서 다운로드하고 시스템 PATH에 추가하세요.

## 설치 방법

1. **저장소 클론**

   ```sh
   git clone https://github.com/yourusername/podcast-generator.git
   cd podcast-generator
   ```

2. **가상 환경 생성 (선택 사항이지만 권장됨)**

   ```sh
   python -m venv venv
   source venv/bin/activate   # macOS/Linux
   .\venv\Scripts\activate  # Windows
   ```

3. **필요한 패키지 설치**

   ```sh
   pip install -r requirements.txt
   ```

4. **환경 변수 설정**

   프로젝트 루트에 `.env` 파일을 생성하고 OpenAI API 키를 추가하세요:

   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

5. **배경음악 파일 추가**

   `background.mp3`라는 이름의 배경음악 파일을 프로젝트 디렉토리에 추가하거나 스크립트 실행 시 경로를 지정하세요.

## 프로젝트 실행

팟캐스트를 생성하려면 다음 명령을 실행하세요:

```sh
python main.py
```

## 작동 방식

1. **팟캐스트 주제 입력**: 스크립트가 팟캐스트 주제를 묻습니다.
2. **정보 검색**: OpenAI와 검색 서비스를 사용해 주제와 관련된 정보를 수집합니다.
3. **스크립트 생성**: 수집된 정보를 바탕으로 두 AI 진행자가 참여하는 팟캐스트 스크립트를 생성합니다.
4. **스크립트를 음성으로 변환**: 생성된 스크립트를 각 진행자 목소리로 변환합니다.
5. **배경음악 추가**: 배경음악을 팟캐스트에 추가합니다.
6. **저장 및 재생**: 최종 팟캐스트 에피소드를 저장하고 재생합니다.

## 코드 개요

### 주요 구성 요소

- **PodcastGenerator 클래스**: 팟캐스트 생성의 모든 과정을 담당하는 주요 클래스입니다.
  - `get_search_results(query: str)`: 주어진 쿼리에 대한 검색 결과를 가져옵니다.
  - `generate_script(query: str, search_results: str, duration_minutes: int)`: 검색 결과를 바탕으로 스크립트를 생성합니다.
  - `generate_audio(script: str)`: OpenAI의 음성 합성을 사용하여 스크립트를 오디오로 변환합니다.
  - `add_background_music(audio_file: str, music_file: str, output_file: str)`: 생성된 오디오에 배경음악을 추가합니다.
  - `save_outputs(script: str, audio: bytes, query: str)`: 생성된 스크립트와 오디오를 저장합니다.

### 사용 기술

- **Python 3.7+**: 메인 프로그래밍 언어.
- **OpenAI API**: 팟캐스트 스크립트와 텍스트 음성 변환에 사용됩니다.
- **pydub**: 오디오 조작 (배경음악 추가)용.
- **Rich**: 콘솔 기반 UI 요소 생성을 위한 라이브러리.
- **Asyncio**: 검색 결과를 비동기적으로 가져오는 데 사용됩니다.

## 예시 출력

프로젝트 실행 시 다음 파일들이 생성됩니다:

- **팟캐스트 스크립트**: 생성된 팟캐스트 스크립트가 포함된 텍스트 파일(`.txt`).
- **팟캐스트 오디오**: 배경음악이 포함된 오디오 파일(`.mp3`).

## 문제 해결

- **API 키를 찾을 수 없음**: `.env` 파일이 올바르게 설정되었는지 확인하세요.
- **오디오 변환 문제**: `ffmpeg`이 설치되어 있고 시스템 PATH에 추가되어 있는지 확인하세요.
- **배경음악을 찾을 수 없음**: `background.mp3` 파일이 올바른 디렉토리에 있는지 확인하세요.

## 기여 방법

기여를 환영합니다! 이 프로젝트를 개선하고 싶다면 다음 단계를 따르세요:

1. 저장소를 포크합니다.
2. 새 브랜치 생성 (`feature/your-feature`).
3. 변경 사항 커밋.
4. 브랜치에 푸시.
5. 풀 리퀘스트 생성.

## 라이선스

이 프로젝트는 MIT 라이선스 하에 제공됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 감사의 말씀

- **OpenAI**의 놀라운 API 덕분에 이 프로젝트가 가능했습니다.
- **pydub**과 **ffmpeg**는 오디오 처리에 도움을 주었습니다.
- **Rich** 덕분에 아름다운 콘솔 애플리케이션을 만들 수 있었습니다.

---

🎙️ **즐거운 팟캐스트 제작 되세요!** 🎶

