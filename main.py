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
        """팟캐스트 스크립트 생성"""
        system_prompt = """
        You are an expert podcast script writer. Create engaging, conversational scripts 
        that naturally incorporate information while maintaining good pacing and flow.
        Follow broadcast standards and use clear language.
        """

        user_prompt = f"""
        주제: '{query}'
        
        다음 검색 결과를 바탕으로 {duration_minutes}분 길이의 팟캐스트 대본을 작성해주세요.

        시간 배분:
        - 도입부: 30초
        - 본문: {duration_minutes - 1}분
        - 마무리: 30초

        필수 요구사항:
        1. 자연스러운 대화체 사용
        2. 검색 결과의 핵심 정보 포함
        3. 문장은 간결하게 구성
        4. 적절한 문장 부호 사용
        5. 청취자의 이해를 돕는 설명 포함
        6. 항상 한글 작성
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

    def generate_audio(self, script: str, voice: str = "nova") -> Optional[bytes]:
        """
        OpenAI TTS API를 사용하여 오디오 생성
        
        Args:
            script (str): 변환할 텍스트
            voice (str): 사용할 음성 (alloy, echo, fable, onyx, nova, shimmer)
        
        Returns:
            bytes: 생성된 오디오 데이터
        """
        try:
            response = self.client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=script,
                speed= 1.0
            )
            return response.content
        except Exception as e:
            console.print(f"[red]Error generating audio: {str(e)}[/red]")
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
        voice = console.input("[green]사용할 음성을 선택하세요 (alloy/echo/fable/onyx/nova/shimmer) [기본값: nova]: [/green]")
        
        duration = int(duration) if duration.strip() else 5
        voice = voice.strip().lower() if voice.strip() else "nova"
        
        if voice not in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]:
            console.print("[yellow]잘못된 음성이 선택되었습니다. 기본값 'nova'를 사용합니다.[/yellow]")
            voice = "nova"

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
            with console.status("[cyan]음성 생성 중...[/cyan]"):
                audio = generator.generate_audio(script, voice)
            
            if audio:
                # 파일 저장
                script_file, audio_file = generator.save_outputs(script, audio, query)
                
                console.print(f"\n[bold green]파일이 생성되었습니다:[/bold green]")
                console.print(f"스크립트: {script_file}")
                console.print(f"오디오: {audio_file}")
                play_audio_with_system(audio_file)
            else:
                console.print("[red]음성 생성에 실패했습니다.[/red]")
        
    except Exception as e:
        console.print(f"[red]오류가 발생했습니다: {str(e)}[/red]")

if __name__ == "__main__":
    asyncio.run(main())