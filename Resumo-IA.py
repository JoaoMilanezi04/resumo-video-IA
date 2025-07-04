import os 
from pytube import YouTube
import whisper

def download_video(video_url):
    try:
        print("Downloading video from URL:", video_url)
        yt = YouTube(video_url)
        video = yt.streams.filter(only_audio=True).first()
        arquivo_baixado = video.download()
        print("Download completed:", arquivo_baixado)
        os.rename(arquivo_baixado, "audio.mp4")
        return "audio.mp4"
    except Exception as e:
        print("Error downloading video:", e)
        return None
    
def transcribe_audio(audio_file):
    try:
        print("Transcrevendo arquivo de audio:", audio_file)
        model = whisper.load_model("base")
        result = model.transcribe(audio_file)
        print("Transcription completed.")
        return result['text']
    except Exception as e:
        print("Error transcribing audio:", e)
        return None
    
if __name__ == "__main__":
    url_do_video = input("=> Insira a URL do vídeo do YouTube: ")
    
    if url_do_video:
        caminho_audio = download_video(url_do_video)
        
        # Se o download funcionou, vamos transcrever
        if caminho_audio:
            texto_do_video = transcribe_audio(caminho_audio)
            
            if texto_do_video:
                print("\n------------------------")
                print(texto_do_video)
                print("------------------------\n")
            
            # Limpar o arquivo de audio após o uso
            try:
                os.remove("audio.mp4")
                print("Arquivo de áudio removido com sucesso.")
            except FileNotFoundError:
                print("Arquivo de áudio já foi removido.")
            except Exception as e:
                print("Erro ao remover arquivo de áudio:", e)