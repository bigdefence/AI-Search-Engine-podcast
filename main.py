import os
from openai import OpenAI
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
from dotenv import load_dotenv
from services.search import fetch_all_search_results, fetch_and_process_content, semantic_search
from utils.text_processing import process_query
import asyncio
from rich.console import Console
from rich.progress import Progress
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
import subprocess
from pydub import AudioSegment
console = Console()

class PodcastGenerator:
    def __init__(self):
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        # 결과물 저장을 위한 디렉토리 생성
        self.output_dir = Path("generated_podcasts")
        self.output_dir.mkdir(exist_ok=True)

    async def get_search_results(self, query: str) -> List[Dict[str, Any]]:
        """검색 결과를 가져오고 처리하는 메서드"""
        optimized_query = process_query(query)
        console.print(f"\n[yellow]최적화된 검색어:[/yellow] {optimized_query}")
            
        text_results = await fetch_all_search_results(optimized_query)
            
        processed_results = await fetch_and_process_content(text_results)
            
        return processed_results

    def display_search_results(self, results: List[Dict[str, Any]], top_k: int = 5):
        """검색 결과를 테이블 형태로 표시"""
        table = Table(title="검색 결과", show_header=True, header_style="bold magenta")
        table.add_column("번호", style="dim", width=4)
        table.add_column("제목", style="cyan", width=30)
        table.add_column("내용 미리보기", style="green", width=50)

        for i, result in enumerate(results[:top_k], 1):
            title = result.get("title", result.get("Title", ""))
            content = result.get("content", result.get("Content", ""))
            
            if not title.strip():
                title = "(제목 정보 없음)"
            if not content.strip():
                content = "(내용 정보 없음)"
            
            content_preview = content[:200] + "..." if len(content) > 200 else content
            title = title[:30] + "..." if len(title) > 30 else title
            
            table.add_row(str(i), title, content_preview)

        console.print(table)
        console.print("\n")

    def prepare_prompt(self, query: str, processed_results: List[Dict[str, Any]], 
                      top_k: int = 5) -> str:
        """검색 결과를 바탕으로 프롬프트 생성"""
        top_indices = semantic_search(query, processed_results, top_k=top_k)
        selected_results = [processed_results[i] for i in top_indices]
        
        console.print("[bold cyan]검색된 참고 자료:[/bold cyan]")
        self.display_search_results(selected_results)
        
        prompt_parts = ["Search results:\n"]
        for i, result in enumerate(selected_results, 1):
            content = result.get("content", result.get("Content", ""))
            title = result.get("title", result.get("Title", ""))
            
            if content:
                content_preview = content[:2000]
                prompt_parts.append(f"Result {i} (Source: {title}):\n{content_preview}\n\n")
        
        return "\n".join(prompt_parts)

    def generate_script(self, query: str, search_results: str, 
                       duration_minutes: int = 5) -> str:
        """팟캐스트 스크립트 생성 - 두 명의 AI 호스트가 진행"""
        system_prompt = """
        You are an expert podcast script writer. Create engaging scripts for two AI hosts:
        - Host A (지식): A knowledgeable and analytical character who focuses on facts and explanations
        - Host B (호기심): A curious and enthusiastic character who asks insightful questions and shares interesting perspectives
        
        Format the script with clear speaker labels and natural conversational flow. 
        Include appropriate reactions, interjections, and chemistry between the hosts.
        """

        user_prompt = f"""
        주제: '{query}'
        
        다음 검색 결과를 바탕으로 {duration_minutes}분 길이의 2인 진행 팟캐스트 대본을 작성해주세요.

        구성:
        1. 도입부 (30초):
           - 인사 및 주제 소개
           - 두 진행자의 자연스러운 호흡
        
        2. 본문 ({duration_minutes - 1}분):
           - 지식: 검색 결과의 핵심 내용 설명
           - 호기심: 적절한 질문과 청취자 관점 제시
           - 서로의 의견에 대한 자연스러운 리액션
        
        3. 마무리 (30초):
           - 핵심 내용 정리
           - 청취자 대상 마무리 멘트

        형식:
        지식: (대사)
        호기심: (대사)

        필수 요구사항:
        1. 모든 대화는 한글로 작성
        2. 자연스러운 대화체 사용
        3. 진행자별 특성이 잘 드러나도록 작성
        4. 서로 호흡이 맞는 대화 전개
        5. 청취자가 이해하기 쉽게 설명
        6. 적절한 예시와 비유 활용

        검색 결과:
        {search_results}
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            console.print(f"[red]Error generating podcast script: {str(e)}[/red]")
            return None

    def generate_audio(self, script: str) -> Optional[bytes]:
        """두 진행자의 목소리로 오디오 생성"""
        try:
            # Split the script into segments by speaker
            segments = []
            current_speaker = ""
            current_text = []
            
            for line in script.split('\n'):
                if line.startswith('지식:'):
                    if current_speaker and current_text:
                        segments.append((current_speaker, ' '.join(current_text)))
                    current_speaker = "onyx"  # More authoritative voice for 지식
                    current_text = [line.replace('지식:', '').strip()]
                elif line.startswith('호기심:'):
                    if current_speaker and current_text:
                        segments.append((current_speaker, ' '.join(current_text)))
                    current_speaker = "nova"  # More energetic voice for 호기심
                    current_text = [line.replace('호기심:', '').strip()]
                elif line.strip():
                    if current_speaker:
                        current_text.append(line.strip())
            
            if current_speaker and current_text:
                segments.append((current_speaker, ' '.join(current_text)))

            # Generate audio for each segment and combine
            all_audio = []
            for voice, text in segments:
                if text.strip():
                    response = self.client.audio.speech.create(
                        model="tts-1",
                        voice=voice,
                        input=text,
                        speed=1.0
                    )
                    all_audio.append(response.content)

            # Combine all audio segments
            return b''.join(all_audio)

        except Exception as e:
            console.print(f"[red]Error generating audio: {str(e)}[/red]")
            return None

    def add_background_music(self, audio_file: str, music_file: str, output_file: str, volume_reduction: int = -30):
        """배경음악을 추가하고 최종 오디오를 저장하는 메서드"""
        try:
            # 생성된 음성 로드
            voice = AudioSegment.from_file(audio_file)
            
            # 배경음악 로드
            music = AudioSegment.from_file(music_file)
            
            # 배경음악 볼륨 조절
            music = music - abs(volume_reduction)
            
            # 배경음악을 음성 길이에 맞게 반복
            if len(music) < len(voice):
                music = music * (len(voice) // len(music) + 1)
            music = music[:len(voice)]
            
            # 음성과 배경음악 병합
            combined = voice.overlay(music)
            
            # 병합된 오디오 저장
            combined.export(output_file, format="mp3")
            return output_file
        except Exception as e:
            console.print(f"[red]배경음악 추가 중 오류 발생: {str(e)}[/red]")
            return None

    def save_outputs(self, script: str, audio: bytes, query: str) -> tuple:
        """스크립트와 오디오 파일 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"podcast_{timestamp}"
        
        # 스크립트 저장
        script_filename = self.output_dir / f"{base_filename}.txt"
        with open(script_filename, "w", encoding="utf-8") as f:
            f.write(f"주제: {query}\n\n")
            f.write(script)
        
        # 오디오 저장
        audio_filename = self.output_dir / f"{base_filename}.mp3"
        with open(audio_filename, "wb") as f:
            f.write(audio)
        
        return script_filename, audio_filename
def play_audio_with_system(audio_file_path: str):
    subprocess.run(["start", audio_file_path], shell=True)  # Windows


async def main():
    try:
        generator = PodcastGenerator()
        
        # 사용자 입력
        query = console.input("[green]팟캐스트 주제를 입력하세요: [/green]")
        duration = console.input("[green]팟캐스트 길이(분)를 입력하세요 [기본값: 5]: [/green]")
        
        duration = int(duration) if duration.strip() else 5

        # 검색 및 스크립트 생성
        with console.status("[cyan]검색 결과를 가져오는 중...[/cyan]"):
            processed_results = await generator.get_search_results(query)
        
        with console.status("[cyan]프롬프트 준비 중...[/cyan]"):
            prompt = generator.prepare_prompt(query, processed_results)
        
        with console.status("[cyan]스크립트 생성 중...[/cyan]"):
            script = generator.generate_script(query, prompt, duration_minutes=duration)
        
        if script:
            # 스크립트 표시
            console.print(Panel(
                Markdown(script),
                title="생성된 팟캐스트 스크립트",
                border_style="green"
            ))
            
            # 오디오 생성
            with console.status("[cyan]팟캐스트 생성 중...[/cyan]"):
                audio = generator.generate_audio(script)
            
            if audio:
                # 파일 저장
                script_file, audio_file = generator.save_outputs(script, audio, query)
                
                # 배경음악 파일 경로
                music_file = "background.mp3"  # 배경음악 파일 이름 또는 경로
                
                # 배경음악 추가
                output_with_music = str(generator.output_dir / f"podcast_with_bgm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3")
                result_file = generator.add_background_music(audio_file, music_file, output_with_music)
                
                if result_file:
                    console.print(f"\n[bold green]파일이 생성되었습니다:[/bold green]")
                    console.print(f"스크립트: {script_file}")
                    console.print(f"오디오: {result_file}")
                    play_audio_with_system(result_file)
                else:
                    console.print("[red]배경음악 추가에 실패했습니다.[/red]")
            else:
                console.print("[red]음성 생성에 실패했습니다.[/red]")
        
    except Exception as e:
        console.print(f"[red]오류가 발생했습니다: {str(e)}[/red]")

if __name__ == "__main__":
    asyncio.run(main())
