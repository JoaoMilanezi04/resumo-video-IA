import os
import sys
import time
import argparse
import requests
import json
import subprocess
from pytube import YouTube
import whisper

def download_video(video_url):
    """Baixa o áudio de um vídeo do YouTube."""
    try:
        print("A baixar o vídeo do URL:", video_url)
        
        # Configura a instância do YouTube com tentativas adicionais
        yt = YouTube(
            video_url,
            use_oauth=False,
            allow_oauth_cache=True
        )
        
        # Seleciona preferencialmente uma stream de áudio, ou uma de menor qualidade
        video = yt.streams.filter(only_audio=True).first()
        
        # Se não encontrou stream de áudio, tenta qualquer stream disponível
        if not video:
            video = yt.streams.get_lowest_resolution()
            
        if not video:
            raise Exception("Não foi possível encontrar nenhum stream disponível para este vídeo")
            
        arquivo_baixado = video.download()
        print("Download concluído:", arquivo_baixado)
        
        os.rename(arquivo_baixado, "audio.mp4")
        return "audio.mp4"
    except Exception as e:
        print("Erro ao baixar o vídeo:", e)
        print("\nDicas para resolver:")
        print("1. Verifique se o URL está correto e se o vídeo está disponível")
        print("2. O YouTube pode estar bloqueando o download automático deste vídeo")
        print("3. Tente atualizar a biblioteca pytube: pip install --upgrade pytube")
        print("4. Tente outro vídeo para testar se o problema é específico deste vídeo")
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

def verificar_pytube():
    """Verifica e tenta atualizar a biblioteca pytube se necessário."""
    try:
        # Tenta atualizar o pytube para a versão mais recente
        print("Verificando a versão do pytube...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pytube"])
        print("PyTube atualizado com sucesso!\n")
        return True
    except Exception as e:
        print(f"Erro ao atualizar pytube: {e}")
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
    parser.add_argument("--update", action="store_true", help="Atualizar a biblioteca pytube")
    
    args = parser.parse_args()
    
    # Se solicitada atualização
    if args.update:
        verificar_pytube()
    
    url_do_video = args.url if args.url else input("=> Insira o URL do vídeo do YouTube: ")
    api_key_usuario = args.key if args.key else input("=> Insira a sua chave de API do Google AI Studio (Gemini): ")
    salvar = args.save
    
    if not url_do_video or not api_key_usuario:
        print("[!] URL do vídeo e chave da API são obrigatórios.")
        sys.exit(1)
    
    # Tenta processar o vídeo
    resultado = processar_video(url_do_video, api_key_usuario, salvar)
    
    # Se falhou, oferece opção de atualizar pytube
    if not resultado and "youtube.com" in url_do_video:
        print("\n[!] Encontrou problemas com o download do YouTube.")
        try_fix = input("Deseja tentar atualizar a biblioteca pytube? (s/n): ").lower()
        if try_fix == "s":
            verificar_pytube()
            print("\nTente executar o programa novamente com o mesmo URL.")
