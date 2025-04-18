#!/usr/bin/env python3
# filepath: /home/comunikime/code/jarvis/audio_handler.py
"""
Módulo para lidar com operações de áudio, incluindo reconhecimento de voz e conversão
de texto para fala. Contém funções para captura de áudio do microfone e reprodução
de áudio usando TTS da OpenAI.
"""

import contextlib
import os
import sys
import tempfile
import time

import pygame
import speech_recognition as sr
from openai import OpenAI

# Importar o logger
from log_manager import LogManager

# Configura o logger
log = LogManager().logger

# Suprimir mensagens de erro do ALSA
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

@contextlib.contextmanager
def suppress_stderr():
    """Temporariamente suprime saída para stderr de forma mais robusta."""
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

def initialize_audio():
    """Inicializa o pygame para reprodução de áudio."""
    try:
        with suppress_stdout_stderr():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
        log.debug("Sistema de áudio inicializado com sucesso")
        return True
    except Exception as e:
        log.error(f"Erro ao inicializar áudio: {e}")
        return False

class AudioHandler:
    """Gerencia operações de áudio para reconhecimento de voz e síntese de fala."""
    
    def __init__(self, openai_client, text_only=False):
        """
        Inicializa o manipulador de áudio.
        
        Args:
            openai_client: Cliente OpenAI para síntese de fala
            text_only: Se True, não reproduz áudio, apenas exibe texto
        """
        self.client = openai_client
        self.text_only = text_only
        log.info(f"Modo somente texto: {text_only}")
        
        self.recognizer = sr.Recognizer()
        
        # Inicializa pygame para reprodução de áudio
        initialize_audio()
        
        # Configurações para melhor reconhecimento de voz
        self.recognizer.pause_threshold = 1.5  # Espera 1.5 segundos de silêncio antes de considerar que a fala terminou
        self.recognizer.energy_threshold = 300  # Aumentar a sensibilidade para ouvir vozes mais suaves
        self.recognizer.non_speaking_duration = 1.0  # Ajustar o nível de silêncio que marca o fim da fala
        log.debug("Reconhecedor de fala configurado")
    
    def listen(self):
        """
        Escuta entrada de voz e converte para texto.
        
        Returns:
            str: Texto reconhecido ou código de erro específico
        """
        max_attempts = 3  # Número máximo de tentativas contínuas
        attempt = 0
        
        while attempt < max_attempts:
            try:
                # Usar o context manager para suprimir erros ALSA durante a inicialização do microfone
                with suppress_stderr(), sr.Microphone() as source:
                    if attempt == 0:
                        log.info("Ouvindo... (fale o quanto quiser, farei uma pausa antes de processar)")
                    else:
                        log.info(f"Ainda ouvindo... (aguardando sua voz) - tentativa {attempt+1}/{max_attempts}")
                    
                    # Ajustar para o ruído ambiente
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    
                    # Configuração para esperar até que a pessoa fale
                    audio = self.recognizer.listen(source, phrase_time_limit=30)
                
                log.debug("Processando fala...")
                text = self.recognizer.recognize_google(audio, language="pt-BR")
                log.info(f"Texto reconhecido: {text}")
                return text
            
            except sr.UnknownValueError:
                # Quando não reconhece a fala, tenta novamente sem avisar o usuário
                attempt += 1
                log.debug(f"Nada detectado, continuando a ouvir... (tentativa {attempt}/{max_attempts})")
                # Pequena pausa antes da próxima tentativa
                time.sleep(1)
                continue
                
            except sr.RequestError as e:
                log.error(f"Erro de conexão com serviço de reconhecimento: {e}")
                return "SPEECH_SERVICE_DOWN"
                
            except Exception as e:
                log.exception(f"Erro ao escutar: {str(e)}")
                return "SPEECH_ERROR"
        
        # Se após várias tentativas ainda não conseguiu reconhecer a fala
        log.warning("Fala não reconhecida após várias tentativas")
        return "SPEECH_NOT_RECOGNIZED"
    
    def speak(self, text):
        """
        Converte texto para fala usando OpenAI TTS.
        
        Args:
            text (str): Texto a ser convertido em fala
        """
        if self.text_only or not text.strip():
            log.info(f"Jarvis (texto): {text}")
            return

        log.info(f"Jarvis (falando): {text}")
        try:
            # Obter áudio da API OpenAI
            log.debug("Solicitando síntese de voz à API OpenAI")
            resp = self.client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text,
                response_format="wav"
            )
            wav_bytes = resp.content
            log.debug(f"Áudio recebido, tamanho: {len(wav_bytes)} bytes")

            # Método usando pygame para reproduzir o áudio
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
                temp_file.write(wav_bytes)
            
            try:
                # Reproduzir usando pygame com supressão total de saída
                log.debug(f"Reproduzindo áudio de: {temp_path}")
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
                    log.debug("Reprodução concluída")
                except KeyboardInterrupt:
                    # Se Ctrl+C for pressionado, parar reprodução e notificar
                    pygame.mixer.music.stop()
                    log.warning("Reprodução interrompida pelo usuário")
                    # Re-lançar a exceção para ser capturada pelo nível superior
                    raise
            finally:
                # Remover o arquivo temporário silenciosamente
                try:
                    os.remove(temp_path)
                    log.debug("Arquivo temporário removido")
                except Exception as e:
                    log.error(f"Erro ao remover arquivo temporário: {e}")
                    pass  # Ignorar erros ao remover arquivo temporário

        except KeyboardInterrupt:
            # Re-lançar KeyboardInterrupt para ser capturado no método chamador
            log.info("Interrupção de teclado detectada durante síntese de fala")
            raise
        except Exception as e:
            log.exception(f"Erro de áudio: {e}")
    
    def cleanup(self):
        """Limpa recursos de áudio."""
        log.debug("Limpando recursos de áudio")
        if pygame.mixer.get_init():
            pygame.mixer.quit()
            log.debug("Sistema de áudio encerrado")
