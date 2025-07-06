import os
import sys
import time
import argparse
import requests
import json
import subprocess
import yt_dlp
import whisper
import configparser
import threading
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ResultadoProcessamento:
    """Classe para armazenar resultado do processamento."""
    success: bool
    data: Optional[str] = None
    error: Optional[str] = None
    file_path: Optional[str] = None

class ErroProcessadorVideo(Exception):
    """Exceção customizada para erros do processador de vídeo."""
    pass

class ErroAPI(Exception):
    """Exceção customizada para erros de API."""
    pass

class GerenciadorConfiguracao:
    """Gerencia configurações do aplicativo."""
    
    def __init__(self, config_file: str = 'config.ini'):
        self.config_file = Path(config_file)
        self.config = configparser.ConfigParser()
    
    def load_api_key(self) -> Optional[str]:
        """Carrega a chave da API do arquivo de configuração."""
        try:
            if not self.config_file.exists():
                logger.warning(f"Arquivo de configuração '{self.config_file}' não encontrado.")
                return None
            
            self.config.read(self.config_file)
            if 'DEFAULT' in self.config and 'api_key' in self.config['DEFAULT']:
                return self.config['DEFAULT']['api_key']
            else:
                logger.warning("Chave da API não encontrada nas configurações.")
                return None
        except Exception as e:
            logger.error(f"Erro ao carregar o arquivo de configuração: {e}")
            return None
    
    def save_api_key(self, api_key: str) -> bool:
        """Salva a chave da API no arquivo de configuração."""
        try:
            self.config['DEFAULT'] = {'api_key': api_key}
            with open(self.config_file, 'w') as configfile:
                self.config.write(configfile)
            logger.info("Configurações salvas com sucesso.")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar as configurações: {e}")
            return False

class Carregador:
    """Classe melhorada para exibir um spinner de carregamento."""
    
    def __init__(self, message: str = "Processando"):
        self.message = message
        self.running = False
        self.thread = None
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
    
    def start(self):
        """Inicia o spinner."""
        self.running = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.start()
    
    def stop(self):
        """Para o spinner."""
        self.running = False
        if self.thread:
            self.thread.join()
        print("\r" + " " * (len(self.message) + 10) + "\r", end="")
    
    def _spin(self):
        """Animação do spinner."""
        chars = "|/-\\"
        i = 0
        while self.running:
            print(f"\r{self.message}... {chars[i % len(chars)]}", end="", flush=True)
            time.sleep(0.1)
            i += 1

class GerenciadorProgresso:
    """Gerencia o progresso de downloads."""
    
    @staticmethod
    def progress_hook(d: Dict[str, Any]):
        """Hook para mostrar progresso do download com yt-dlp."""
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded_bytes = d.get('downloaded_bytes', 0)
            
            if total_bytes > 0:
                percent = (downloaded_bytes / total_bytes) * 100
                speed = d.get('speed', 0)
                speed_str = f"{speed/1024/1024:.1f} MB/s" if speed else "N/A"
                
                total_mb = total_bytes / 1024 / 1024
                downloaded_mb = downloaded_bytes / 1024 / 1024
                
                bar_length = 30
                filled_length = int(bar_length * downloaded_bytes // total_bytes)
                bar = '█' * filled_length + '-' * (bar_length - filled_length)
                
                print(f"\r[{bar}] {percent:.1f}% ({downloaded_mb:.1f}/{total_mb:.1f} MB) - {speed_str}", 
                      end="", flush=True)
        
        elif d['status'] == 'finished':
            print(f"\n[+] Download concluído: {d['filename']}")

class BaixadorVideo:
    """Responsável pelo download de vídeos do YouTube."""
    
    def __init__(self):
        self.progress_handler = GerenciadorProgresso()
    
    @contextmanager
    def temporary_audio_file(self, video_url: str):
        """Context manager para gerenciar arquivos de áudio temporários."""
        audio_file = None
        try:
            audio_file = self._download_audio(video_url)
            if audio_file and Path(audio_file).exists():
                yield audio_file
            else:
                raise ErroProcessadorVideo("Falha no download do áudio")
        finally:
            if audio_file and Path(audio_file).exists():
                logger.info(f"Removendo arquivo temporário: {audio_file}")
                Path(audio_file).unlink()
    
    def _download_audio(self, video_url: str) -> Optional[str]:
        """Baixa o áudio de um vídeo do YouTube usando yt-dlp."""
        try:
            logger.info(f"Iniciando download do vídeo: {video_url}")
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'audio.%(ext)s',
                'noplaylist': True,
                'extractaudio': True,
                'audioformat': 'mp4',
                'audioquality': '192K',
                'progress_hooks': [self.progress_handler.progress_hook],
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            
            audio_files = list(Path('.').glob('audio.*'))
            if audio_files:
                audio_file = audio_files[0]
                if audio_file.suffix != '.mp4':
                    new_name = audio_file.with_suffix('.mp4')
                    audio_file.rename(new_name)
                    audio_file = new_name
                
                logger.info(f"Download concluído: {audio_file}")
                return str(audio_file)
            
            raise ErroProcessadorVideo("Arquivo de áudio não foi encontrado após o download")
            
        except Exception as e:
            logger.error(f"Erro ao baixar o vídeo: {e}")
            self._show_troubleshooting_tips()
            return None
    
    def _show_troubleshooting_tips(self):
        """Exibe dicas para resolver problemas de download."""
        tips = [
            "1. Verifique se o URL está correto e se o vídeo está disponível",
            "2. O vídeo pode ter restrições de idade ou geográficas",
            "3. Tente outro vídeo para testar se o problema é específico deste vídeo",
            "4. Verifique sua conexão com a internet"
        ]
        logger.info("Dicas para resolver:")
        for tip in tips:
            logger.info(tip)

class TranscritorAudio:
    """Responsável pela transcrição de áudio usando Whisper."""
    
    def __init__(self, model_name: str = "base"):
        self.model_name = model_name
        self._model = None
    
    @property
    def model(self):
        """Carrega o modelo Whisper de forma lazy."""
        if self._model is None:
            with Carregador("Carregando modelo Whisper"):
                self._model = whisper.load_model(self.model_name)
        return self._model
    
    def transcribe(self, audio_file: str) -> ResultadoProcessamento:
        """Transcreve o áudio para texto usando Whisper."""
        try:
            logger.info(f"Iniciando transcrição do arquivo: {audio_file}")
            
            with Carregador("Transcrevendo áudio (isso pode demorar alguns minutos)"):
                result = self.model.transcribe(audio_file, fp16=False)
            
            logger.info("Transcrição concluída com sucesso.")
            return ResultadoProcessamento(success=True, data=result['text'])
            
        except Exception as e:
            error_msg = f"Erro ao transcrever o áudio: {e}"
            logger.error(error_msg)
            return ResultadoProcessamento(success=False, error=error_msg)

class APIGemini:
    """Cliente para a API do Google Gemini."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"
    
    def generate_summary(self, text: str) -> ResultadoProcessamento:
        """Envia o texto para a API do Gemini e retorna um resumo."""
        try:
            with Carregador("Gerando resumo com IA (Gemini)"):
                response = self._make_request(text)
            
            if response:
                logger.info("Resumo gerado com sucesso!")
                return ResultadoProcessamento(success=True, data=response)
            else:
                return ResultadoProcessamento(success=False, error="Resposta vazia da API")
                
        except Exception as e:
            error_msg = f"Erro ao contactar a API do Gemini: {e}"
            logger.error(error_msg)
            return ResultadoProcessamento(success=False, error=error_msg)
    
    def _make_request(self, text: str) -> Optional[str]:
        """Faz a requisição para a API do Gemini."""
        prompt = self._create_prompt(text)
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        
        headers = {"Content-Type": "application/json"}
        url = f"{self.base_url}?key={self.api_key}"
        
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        response.raise_for_status()
        
        response_data = response.json()
        return response_data['candidates'][0]['content']['parts'][0]['text']
    
    def _create_prompt(self, text: str) -> str:
        """Cria o prompt para a API do Gemini."""
        return (
            "Com base no seguinte texto de uma transcrição de vídeo do YouTube, faça um resumo. "
            "O resumo deve ser direto, conciso, conter os pontos principais do vídeo e as ideias centrais. "
            "Estruture o resumo usando marcadores.\n\n"
            "--- TRANSCRIÇÃO DO VÍDEO ---\n"
            f"{text}\n"
            "--- FIM DA TRANSCRIÇÃO ---\n\n"
            "Resumo em marcadores:"
        )

class GerenciadorArquivos:
    """Gerencia operações de arquivo."""
    
    @staticmethod
    def save_summary(text: str, url: str, output_dir: str = ".") -> ResultadoProcessamento:
        """Salva o resumo em um arquivo de texto."""
        try:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = f"resumo-{timestamp}.txt"
            filepath = Path(output_dir) / filename
            
            content = GerenciadorArquivos._create_file_content(text, url)
            
            with open(filepath, "w", encoding="utf-8") as file:
                file.write(content)
            
            logger.info(f"Resumo salvo em: {filepath}")
            return ResultadoProcessamento(success=True, file_path=str(filepath))
            
        except Exception as e:
            error_msg = f"Erro ao salvar o resumo: {e}"
            logger.error(error_msg)
            return ResultadoProcessamento(success=False, error=error_msg)
    
    @staticmethod
    def _create_file_content(text: str, url: str) -> str:
        """Cria o conteúdo do arquivo de resumo."""
        return (
            f"Resumo de: {url}\n"
            f"Data: {time.strftime('%d/%m/%Y %H:%M:%S')}\n"
            "="*50 + "\n\n"
            f"{text}\n\n"
            "="*50 + "\n"
        )

class GerenciadorSistema:
    """Gerencia operações do sistema."""
    
    @staticmethod
    def update_ytdlp() -> bool:
        """Verifica e tenta atualizar a biblioteca yt-dlp se necessário."""
        try:
            logger.info("Verificando a versão do yt-dlp...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"])
            logger.info("yt-dlp atualizado com sucesso!")
            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar yt-dlp: {e}")
            return False
    
    @staticmethod
    def show_banner():
        banner = """
        ╔══════════════════════════════════════════════════════════════╗
        ║                                                              ║
        ║            Resumo de Vídeos do YouTube com IA                ║
        ║                                                              ║
        ║                                                              ║               
        ║                                                              ║
        ╚══════════════════════════════════════════════════════════════╝"""
        
        print(banner)

class ProcessadorVideo:

    
    def __init__(self, api_key: str, whisper_model: str = "base"):
        self.config_manager = GerenciadorConfiguracao()
        self.downloader = BaixadorVideo()
        self.transcriber = TranscritorAudio(whisper_model)
        self.gemini_api = APIGemini(api_key)
        self.file_manager = GerenciadorArquivos()
        
    def process_video(self, url: str, save_to_file: bool = False, output_dir: str = ".") -> ResultadoProcessamento:
        """Função principal que coordena todo o processo."""
        try:
            logger.info("Iniciando processamento do vídeo...")
            
            logger.info("[1/3] Iniciando download do vídeo...")
            with self.downloader.temporary_audio_file(url) as audio_file:
                
                logger.info("[2/3] Iniciando transcrição do áudio...")
                transcription_result = self.transcriber.transcribe(audio_file)
                
                if not transcription_result.success:
                    return transcription_result
                
                logger.info("[3/3] Gerando resumo com IA...")
                summary_result = self.gemini_api.generate_summary(transcription_result.data)
                
                if not summary_result.success:
                    return summary_result
                
                self._display_summary(summary_result.data)
                
                if save_to_file:
                    file_result = self.file_manager.save_summary(summary_result.data, url, output_dir)
                    if file_result.success:
                        summary_result.file_path = file_result.file_path
                
                return summary_result
                
        except Exception as e:
            error_msg = f"Erro durante o processamento: {e}"
            logger.error(error_msg)
            return ResultadoProcessamento(success=False, error=error_msg)
    
    def _display_summary(self, summary: str):
        """Exibe o resumo de forma formatada."""
        print("\n" + "="*60)
        print("               RESUMO GERADO PELA IA               ")
        print("="*60)
        print(summary)
        print("="*60)

def main():
    """Função principal do programa."""
    GerenciadorSistema.show_banner()
    
    parser = argparse.ArgumentParser(description="Resumo de vídeos do YouTube usando IA")
    parser.add_argument("-u", "--url", help="URL do vídeo do YouTube")
    parser.add_argument("-k", "--key", help="Chave da API do Google AI Studio (Gemini)")
    parser.add_argument("-s", "--save", action="store_true", help="Salvar o resumo em arquivo de texto")
    parser.add_argument("-m", "--model", default="base", 
                       choices=["tiny", "base", "small", "medium", "large"],
                       help="Modelo Whisper a ser usado (padrão: base)")
    parser.add_argument("-o", "--output", default=".", help="Diretório de saída para arquivos salvos")
    parser.add_argument("--update", action="store_true", help="Atualizar a biblioteca yt-dlp")
    
    args = parser.parse_args()
    
    if args.update:
        GerenciadorSistema.update_ytdlp()
        return
    
    config_manager = GerenciadorConfiguracao()
    
    video_url = args.url if args.url else input("=> Insira o URL do vídeo do YouTube: ")
    
    api_key = args.key
    if not api_key:
        api_key = config_manager.load_api_key()
        if not api_key:
            api_key = input("=> Insira a sua chave de API do Google AI Studio (Gemini): ")
            config_manager.save_api_key(api_key)
    
    if not video_url or not api_key:
        logger.error("URL do vídeo e chave da API são obrigatórios.")
        sys.exit(1)
    
    try:
        processor = ProcessadorVideo(api_key, args.model)
        result = processor.process_video(video_url, args.save, args.output)
        
        if result.success:
            logger.info("Processamento concluído com sucesso!")
            if result.file_path:
                logger.info(f"Resumo salvo em: {result.file_path}")
        else:
            logger.error(f"Falha no processamento: {result.error}")
            
            if "youtube.com" in video_url:
                logger.info("Encontrou problemas com o download do YouTube.")
                try_fix = input("Deseja tentar atualizar a biblioteca yt-dlp? (s/n): ").lower()
                if try_fix == "s":
                    GerenciadorSistema.update_ytdlp()
                    logger.info("Tente executar o programa novamente com o mesmo URL.")
    
    except KeyboardInterrupt:
        logger.info("Operação cancelada pelo usuário.")
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")

if __name__ == "__main__":
    main()
