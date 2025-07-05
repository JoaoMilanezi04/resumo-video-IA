import os
import sys
import time
import argparse
import requests
import json
import subprocess
import yt_dlp
import whisper

def download_video(video_url):
    """Baixa o áudio de um vídeo do YouTube usando yt-dlp."""
    try:
        print("A baixar o vídeo do URL:", video_url)
        
        # Configurações para yt-dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'audio.%(ext)s',
            'noplaylist': True,
            'extractaudio': True,
            'audioformat': 'mp4',
            'audioquality': '192K',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Baixa o áudio
            ydl.download([video_url])
            
        # Procura pelo arquivo baixado
        for arquivo in os.listdir('.'):
            if arquivo.startswith('audio.') and not arquivo.endswith('.mp4'):
                # Renomeia para .mp4 se necessário
                os.rename(arquivo, 'audio.mp4')
                break
        
        if os.path.exists('audio.mp4'):
            print("Download concluído: audio.mp4")
            return "audio.mp4"
        else:
            # Se não encontrou audio.mp4, procura por qualquer arquivo de áudio
            for arquivo in os.listdir('.'):
                if arquivo.startswith('audio.'):
                    print(f"Download concluído: {arquivo}")
                    return arquivo
            
            raise Exception("Arquivo de áudio não foi encontrado após o download")
            
    except Exception as e:
        print("Erro ao baixar o vídeo:", e)
        print("\nDicas para resolver:")
        print("1. Verifique se o URL está correto e se o vídeo está disponível")
        print("2. O vídeo pode ter restrições de idade ou geográficas")
        print("3. Tente outro vídeo para testar se o problema é específico deste vídeo")
        print("4. Verifique sua conexão com a internet")
        return None
    
def transcribe_audio(audio_file):
    """Transcreve o áudio para texto usando Whisper."""
    try:
        print("A transcrever o ficheiro de áudio:", audio_file)
        model = whisper.load_model("base")
        result = model.transcribe(audio_file, fp16=False)
        print("Transcrição concluída.")
        return result['text']
    except Exception as e:
        print("Erro ao transcrever o áudio:", e)
        return None
    
def resume_video_gemini(texto_resumir, api_key):
    """Envia o texto para a API do Gemini e retorna um resumo."""
    print("A resumir o texto com o Gemini...")
    
    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
    
    prompt = (
        "Com base no seguinte texto de uma transcrição de vídeo do YouTube, faça um resumo."
        "O resumo deve ser direto, conciso, conter os pontos principais do vídeo e as ideias centrais."
        "Estruture o resumo usando marcadores (bullet points)."
        "--- TRANSCRIÇÃO DO VÍDEO ---"
        f"{texto_resumir}"
        "--- FIM DA TRANSCRIÇÃO ---"
        "Resumo em marcadores:"
    )
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(gemini_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        response_data = response.json()
        resumo = response_data['candidates'][0]['content']['parts'][0]['text']
        
        print("[+] Resumo gerado com sucesso!")
        return resumo
    except Exception as e:
        print(f"[!] Ocorreu um erro ao contactar a API do Gemini: {e}")
        if 'response' in locals():
            print(f"[!] Resposta da API: {response.text}")
        return None

def salvar_resumo(texto, url):
    """Salva o resumo em um arquivo de texto."""
    try:
        # Cria nome de arquivo baseado na data/hora atual
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        nome_arquivo = f"resumo-{timestamp}.txt"
        
        with open(nome_arquivo, "w", encoding="utf-8") as arquivo:
            arquivo.write(f"Resumo de: {url}\n")
            arquivo.write(f"Data: {time.strftime('%d/%m/%Y %H:%M:%S')}\n")
            arquivo.write("="*50 + "\n\n")
            arquivo.write(texto)
            arquivo.write("\n\n" + "="*50 + "\n")
            
        print(f"[+] Resumo salvo em: {nome_arquivo}")
        return nome_arquivo
    except Exception as e:
        print(f"[!] Erro ao salvar o resumo: {e}")
        return None

def verificar_ytdlp():
    """Verifica e tenta atualizar a biblioteca yt-dlp se necessário."""
    try:
        print("Verificando a versão do yt-dlp...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"])
        print("yt-dlp atualizado com sucesso!\n")
        return True
    except Exception as e:
        print(f"Erro ao atualizar yt-dlp: {e}")
        return False

def mostrar_banner():
    """Exibe um banner de boas-vindas para o programa."""
    banner = """
    ------ RESUMO DE VÍDEO COM INTELIGÊNCIA ARTIFICIAL ------
    
    """
    print(banner)

def processar_video(url, api_key, salvar=False):
    """Função principal que coordena todo o processo."""
    caminho_audio = None
    
    try:
        print("\n[1/3] Iniciando download do vídeo...")
        caminho_audio = download_video(url)
        
        if not caminho_audio:
            print("[!] Não foi possível baixar o vídeo.")
            return
            
        print("\n[2/3] Iniciando transcrição do áudio...")
        texto_do_video = transcribe_audio(caminho_audio)
        
        if not texto_do_video:
            print("[!] Não foi possível transcrever o áudio.")
            return
            
        print("\n[3/3] Gerando resumo com IA...")
        resumo_final = resume_video_gemini(texto_do_video, api_key)
        
        if not resumo_final:
            print("[!] Não foi possível gerar o resumo.")
            return
            
        print("\n\n" + "="*60)
        print("               RESUMO GERADO PELA IA               ")
        print("="*60)
        print(resumo_final)
        print("\n" + "="*60)
        
        if salvar:
            salvar_resumo(resumo_final, url)
            
        return resumo_final
            
    finally:
        if caminho_audio and os.path.exists(caminho_audio):
            print(f"\n[*] Removendo arquivo de áudio temporário: {caminho_audio}")
            os.remove(caminho_audio)
            print("[+] Limpeza concluída.")

if __name__ == "__main__":
    mostrar_banner()
    
    parser = argparse.ArgumentParser(description="Resumo de vídeos do YouTube usando IA")
    parser.add_argument("-u", "--url", help="URL do vídeo do YouTube")
    parser.add_argument("-k", "--key", help="Chave da API do Google AI Studio (Gemini)")
    parser.add_argument("-s", "--save", action="store_true", help="Salvar o resumo em arquivo de texto")
    parser.add_argument("--update", action="store_true", help="Atualizar a biblioteca yt-dlp")
    
    args = parser.parse_args()
    
    # Se solicitada atualização
    if args.update:
        verificar_ytdlp()
    
    url_do_video = args.url if args.url else input("=> Insira o URL do vídeo do YouTube: ")
    api_key_usuario = args.key if args.key else input("=> Insira a sua chave de API do Google AI Studio (Gemini): ")
    salvar = args.save
    
    if not url_do_video or not api_key_usuario:
        print("[!] URL do vídeo e chave da API são obrigatórios.")
        sys.exit(1)
    
    # Tenta processar o vídeo
    resultado = processar_video(url_do_video, api_key_usuario, salvar)
    
    # Se falhou, oferece opção de atualizar yt-dlp
    if not resultado and "youtube.com" in url_do_video:
        print("\n[!] Encontrou problemas com o download do YouTube.")
        try_fix = input("Deseja tentar atualizar a biblioteca yt-dlp? (s/n): ").lower()
        if try_fix == "s":
            verificar_ytdlp()
            print("\nTente executar o programa novamente com o mesmo URL.")
