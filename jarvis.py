#!/usr/bin/env python3
# filepath: /home/comunikime/code/jarvis/jarvis.py
from openai import OpenAI
import os
import time
import speech_recognition as sr
import argparse
import sys
import io
import base64
from PIL import Image
import requests
import wave
# --- streaming / multimodal ---
import asyncio, json, websockets, numpy as np, sounddevice as sd
import threading

# Suprimir mensagens de erro do ALSA
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

# Redirecionar stderr temporariamente para suprimir erros ALSA/JACK
import contextlib
import io

@contextlib.contextmanager
def suppress_stderr():
    """Temporariamente suprime saída para stderr de forma mais robusta."""
    import os
    try:
        # Salvar o stderr original
        _stderr = sys.stderr
        # Redirecionar stderr para /dev/null
        null = open(os.devnull, 'w')
        sys.stderr = null
        yield
    finally:
        # Restaurar stderr
        sys.stderr = _stderr
        null.close()

@contextlib.contextmanager
def suppress_stdout_stderr():
    """Suprime tanto stdout quanto stderr."""
    with open(os.devnull, 'w') as devnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = devnull
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

# Importar pygame para reprodução de áudio com supressão total de saída
try:
    with suppress_stdout_stderr():
        import pygame
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
except ImportError:
    print("Instale pygame: pip install pygame")
    sys.exit(1)

# Mantenha simpleaudio como fallback
try:
    import simpleaudio as sa
    USE_SIMPLEAUDIO = True
except ImportError:
    USE_SIMPLEAUDIO = False

# Verifique se dotenv está instalado e carregue variáveis de ambiente
try:
    from dotenv import load_dotenv
    load_dotenv()  # carrega variáveis de .env se existir
except ImportError:
    print("Recomendado instalar python-dotenv:  pip install python-dotenv")

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ================= ASSISTANT / THREAD POOL =================
_ASSISTANTS_FILE = os.path.expanduser("~/.jarvis/assistants.json")
os.makedirs(os.path.dirname(_ASSISTANTS_FILE), exist_ok=True)
if not os.path.exists(_ASSISTANTS_FILE):
    with open(_ASSISTANTS_FILE, "w") as fp:
        json.dump({}, fp)

def _load_meta():
    with open(_ASSISTANTS_FILE) as fp:
        return json.load(fp)

def _save_meta(meta):
    with open(_ASSISTANTS_FILE, "w") as fp:
        json.dump(meta, fp, indent=2)

class AssistantManager:
    """carrega ou cria assistentes/threads e guarda IDs em ~/.jarvis"""

    def __init__(self, client: OpenAI):
        self.client = client
        self.meta   = _load_meta()

    def get(self, name: str, instructions: str) -> tuple[str, str]:
        if name in self.meta:
            return self.meta[name]["assistant_id"], self.meta[name]["thread_id"]

        # novo assistant + thread
        a = self.client.beta.assistants.create(name=name, instructions=instructions, model="gpt-4o")
        t = self.client.beta.threads.create()
        self.meta[name] = {"assistant_id": a.id, "thread_id": t.id}
        _save_meta(self.meta)
        return a.id, t.id
# ===========================================================

# ================= MULTIMODAL BUILDER ======================
class MMBuilder:
    def __init__(self): self.parts=[]
    def text(self,t):   self.parts.append({"type":"text","text":t});       return self
    def image(self,path,detail="auto"):
        with open(path,"rb") as f:
            b64=base64.b64encode(f.read()).decode()
        self.parts.append({"type":"image_url",
                           "image_url":{"url":f"data:image/jpeg;base64,{b64}",
                                        "detail":detail}})
        return self
    def audio(self,wav_bytes,mime="audio/wav"):
        b64=base64.b64encode(wav_bytes).decode()
        self.parts.append({"type":"audio",
                           "audio":{"mime_type":mime,"data":b64}})
        return self
    def build(self):    return self.parts
# ===========================================================

# ================= STREAMING TTS ===========================
class StreamTTS:
    URL   = "wss://api.openai.com/v1/audio/speech.stream"
    TOKEN = os.environ["OPENAI_API_KEY"]

    async def _recv_audio(self, text, voice):
        async with websockets.connect(self.URL,
               extra_headers={"Authorization": f"Bearer {self.TOKEN}"}) as ws:
            await ws.send(json.dumps({
                "model":"tts-1","voice":voice,"input":text,"format":"pcm",
                "sample_rate":24000}))
            pcm_tot = bytearray()
            async for msg in ws:
                pcm_tot.extend(msg)
            return bytes(pcm_tot)

    def speak(self, text, voice="alloy"):
        loop = asyncio.new_event_loop()
        pcm  = loop.run_until_complete(self._recv_audio(text, voice))
        data = np.frombuffer(pcm, dtype=np.int16)
        threading.Thread(target=sd.play, args=(data,24_000)).start()
# ===========================================================

class Jarvis:
    def __init__(self, text_only=False):
        print("Inicializando Jarvis...")
        self.client = client
        self.text_only = text_only
        
        # Create or retrieve assistant
        self.assistant = self._get_or_create_assistant()
        
        # Create a new thread or use existing one
        thread_id = os.environ.get("JARVIS_THREAD_ID")
        if thread_id:
            self.thread = self.client.beta.threads.retrieve(thread_id)
            print(f"Usando thread existente: {thread_id}")
        else:
            self.thread = self.client.beta.threads.create()
            print(f"Nova thread criada: {self.thread.id}")
            print(f"Configure JARVIS_THREAD_ID={self.thread.id} para manter o histórico de conversa")
        
        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        
        print("Jarvis está pronto.")
    
    def _get_or_create_assistant(self):
        """Get existing assistant or create a new one"""
        assistant_id = os.environ.get("JARVIS_ASSISTANT_ID")
        
        if assistant_id:
            try:
                return self.client.beta.assistants.retrieve(assistant_id)
            except:
                print(f"Não foi possível recuperar o assistente com ID {assistant_id}. Criando novo assistente.")
        
        # Create a new assistant (sem tools de visão)
        assistant = self.client.beta.assistants.create(
            name="Jarvis",
            instructions=(
                "Você é Jarvis, um assistente pessoal inteligente e conciso. "
                "Pode descrever imagens e responder por voz."
            ),
            model="gpt-4o"  # visão já é nativa do modelo
        )
        
        print(f"Novo assistente criado com ID: {assistant.id}")
        print(f"Configure JARVIS_ASSISTANT_ID={assistant.id} para reutilizar este assistente")
        
        return assistant
    
    def ask(self, content, image_path=None):
        """Send a message to the assistant and get a response"""
        try:
            message_content = []
            
            # Add text content if provided
            if isinstance(content, str) and content.strip():
                message_content.append({"type": "text", "text": content})
            
            # Add image if provided
            if image_path:
                if os.path.exists(image_path):
                    with open(image_path, "rb") as image_file:
                        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                    
                    message_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                            "detail": "high"
                        }
                    })
                else:
                    return f"Erro: Arquivo de imagem não encontrado: {image_path}"
            
            # If no content was added, return error
            if not message_content:
                return "Erro: Nenhum conteúdo fornecido"
            
            # Send message to thread
            self.client.beta.threads.messages.create(
                thread_id=self.thread.id,
                role="user",
                content=message_content
            )
            
            # Run the assistant
            run = self.client.beta.threads.runs.create(
                thread_id=self.thread.id,
                assistant_id=self.assistant.id
            )
            
            # Wait for completion with status updates
            print("Processando...", end="", flush=True)
            while True:
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id=self.thread.id,
                    run_id=run.id
                )
                
                if run_status.status == "completed":
                    print(" Concluído!")
                    break
                elif run_status.status in ["failed", "cancelled", "expired"]:
                    print(f" Falhou: {run_status.status}")
                    return f"Erro: {run_status.last_error}"
                
                print(".", end="", flush=True)
                time.sleep(1)
            
            # Get the latest message
            messages = self.client.beta.threads.messages.list(
                thread_id=self.thread.id
            )
            
            # Return the assistant's response
            for message in messages.data:
                if message.role == "assistant":
                    for content_item in message.content:
                        if content_item.type == "text":
                            return content_item.text.value
            
            return "Nenhuma resposta recebida."
        
        except Exception as e:
            return f"Erro: {str(e)}"
    
    def listen(self):
        """Listen for voice input and convert to text"""
        max_attempts = 3  # Número máximo de tentativas contínuas
        attempt = 0
        
        # Configurar o reconhecimento para ser mais paciente
        # Aumentar o tempo que o reconhecedor aguarda após o silêncio para determinar o fim da fala
        self.recognizer.pause_threshold = 1.5  # Espera 1.5 segundos de silêncio antes de considerar que a fala terminou
        # Aumentar a sensibilidade para ouvir vozes mais suaves
        self.recognizer.energy_threshold = 300
        # Ajustar o nível de silêncio que marca o fim da fala
        self.recognizer.non_speaking_duration = 1.0
        
        # Desativado log de ajustes para reduzir verbosidade
        # print("Ajustes para melhor reconhecimento: pause_threshold=1.5s, energy_threshold=300")
        
        while attempt < max_attempts:
            try:
                # Usar o context manager para suprimir erros ALSA durante a inicialização do microfone
                with suppress_stderr(), sr.Microphone() as source:
                    if attempt == 0:
                        print("Ouvindo... (fale o quanto quiser, farei uma pausa antes de processar)")
                    else:
                        print("Ainda ouvindo... (aguardando sua voz)")
                    
                    # Ajustar para o ruído ambiente
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    
                    # Configuração para esperar até que a pessoa fale
                    # Removido o timeout para esperar indefinidamente
                    # phrase_time_limit aumentado para permitir frases muito longas
                    # Configuramos pause_threshold para aguardar mais depois do silêncio
                    audio = self.recognizer.listen(source, phrase_time_limit=30)
                
                print("Processando fala...")
                text = self.recognizer.recognize_google(audio, language="pt-BR")
                print(f"Você disse: {text}")
                return text
            
            except sr.UnknownValueError:
                # Quando não reconhece a fala, tenta novamente sem avisar o usuário
                attempt += 1
                print(f"Nada detectado, continuando a ouvir... (tentativa {attempt}/{max_attempts})")
                # Pequena pausa antes da próxima tentativa
                time.sleep(1)
                continue
                
            except sr.RequestError:
                return "SPEECH_SERVICE_DOWN"
                
            except Exception as e:
                print(f"Erro ao escutar: {str(e)}")
                return "SPEECH_ERROR"
        
        # Se após várias tentativas ainda não conseguiu reconhecer a fala
        return "SPEECH_NOT_RECOGNIZED"
    
    def speak(self, text):
        """Convert text to speech using OpenAI TTS"""
        if self.text_only or not text.strip():
            print(f"Jarvis (texto): {text}")
            return

        print(f"Jarvis (falando): {text}")
        try:
            # Suprimir mensagens sobre solicitação de áudio
            resp = self.client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text,
                response_format="wav"
            )
            wav_bytes = resp.content

            # --- Método usando pygame para reproduzir o áudio ---
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
                temp_file.write(wav_bytes)
            
            try:
                # Reproduzir usando pygame com supressão total de saída
                with suppress_stdout_stderr():
                    pygame.mixer.music.load(temp_path)
                    pygame.mixer.music.play()
                
                # Aguardar até que a reprodução termine, com tratamento de interrupção
                try:
                    # Suprimir toda saída durante a reprodução
                    with suppress_stdout_stderr():
                        while pygame.mixer.music.get_busy():
                            # Usar sleep mais curto para responder mais rapidamente a interrupções
                            time.sleep(0.05)
                except KeyboardInterrupt:
                    # Se Ctrl+C for pressionado, parar reprodução e notificar
                    pygame.mixer.music.stop()
                    print("\nReprodução interrompida pelo usuário")
                    # Re-lançar a exceção para ser capturada pelo nível superior
                    raise
            finally:
                # Remover o arquivo temporário silenciosamente
                try:
                    os.remove(temp_path)
                except Exception:
                    pass  # Ignorar erros ao remover arquivo temporário

        except KeyboardInterrupt:
            # Re-lançar KeyboardInterrupt para ser capturado no método chamador
            raise
        except Exception as e:
            print(f"Erro de áudio: {e}")
    
    def run_conversation(self, with_voice=True):
        """Run a continuous conversation loop"""
        try:
            # Verifica se estamos usando uma thread existente ou nova
            thread_id = os.environ.get("JARVIS_THREAD_ID")
            if thread_id and thread_id == self.thread.id:
                # Usando thread existente, saudação para conversa contínua
                self.speak("Olá novamente. Continuando nossa conversa.")
            else:
                # Nova thread, usar saudação inicial completa
                self.speak("Olá, eu sou o Jarvis. Como posso ajudar você hoje?")
            
            while True:
                try:
                    if with_voice:
                        # Listen for user input
                        user_input = self.listen()
                        
                        # Handle speech recognition errors
                        if user_input in ["SPEECH_NOT_RECOGNIZED", "SPEECH_SERVICE_DOWN", "SPEECH_ERROR"]:
                            if user_input == "SPEECH_NOT_RECOGNIZED":
                                self.speak("Desculpe, não entendi. Pode repetir?")
                            else:
                                self.speak("Desculpe, estou tendo problemas para entender você.")
                            continue
                        
                        # Check for exit command
                        if "sair" in user_input.lower() or "encerrar" in user_input.lower():
                            self.speak("Até logo!")
                            break
                    else:
                        # Text input mode
                        user_input = input("Você: ")
                        
                        # Check for exit command
                        if user_input.lower() in ["sair", "exit", "quit"]:
                            self.speak("Até logo!")
                            break
                    
                    # Get response from assistant
                    response = self.ask(user_input)
                    
                    # Speak the response
                    self.speak(response)
                    
                except KeyboardInterrupt:
                    print("\nEncerrando Jarvis por interrupção do usuário...")
                    try:
                        # Tentar uma despedida rápida
                        if pygame.mixer.get_init():
                            pygame.mixer.quit()  # Encerrar o mixer antes para evitar bloqueios
                        self.text_only = True  # Mudar para modo texto para a despedida
                        self.speak("Até logo!")
                    except:
                        pass
                    break
                except Exception as e:
                    print(f"Erro: {str(e)}")
                    self.speak("Encontrei um erro. Vamos tentar novamente.")
        
        except KeyboardInterrupt:
            # Captura Ctrl+C durante a saudação inicial ou outras operações
            print("\nEncerrando Jarvis por interrupção do usuário...")
        
        finally:
            # Limpar recursos ao sair
            if pygame.mixer.get_init():
                pygame.mixer.quit()
            print("Jarvis encerrado.")

def main():
    parser = argparse.ArgumentParser(description="Jarvis - Assistente pessoal inteligente")
    parser.add_argument("--text", action="store_true", help="Executar em modo somente texto (sem saída de voz)")
    parser.add_argument("--image", type=str, help="Caminho para uma imagem para análise")
    args = parser.parse_args()
    
    # Verificar API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("Erro: OPENAI_API_KEY não encontrada no ambiente.")
        print("Por favor, configure a variável de ambiente OPENAI_API_KEY.")
        sys.exit(1)
    
    # Iniciar Jarvis
    jarvis = Jarvis(text_only=args.text)
    
    # Se uma imagem foi fornecida, analisar a imagem
    if args.image:
        print(f"Analisando imagem: {args.image}")
        response = jarvis.ask("O que você vê nesta imagem?", image_path=args.image)
        jarvis.speak(response)
    else:
        # Iniciar conversa
        jarvis.run_conversation(with_voice=not args.text)

if __name__ == "__main__":
    main()
