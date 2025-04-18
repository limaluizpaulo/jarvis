#!/usr/bin/env python3
# filepath: /home/comunikime/code/jarvis/interface.py
"""
Módulo para gerenciar a interface do usuário do Jarvis, incluindo
o ciclo principal de execução e interação com o usuário via texto ou voz.
"""

import os
import sys
import re

# Importar o logger
from log_manager import LogManager

# Importar analisador de código
try:
    from code_analyzer import process_query_with_context
    _has_code_analyzer = True
except ImportError:
    _has_code_analyzer = False

# Configura o logger
log = LogManager().logger

class JarvisInterface:
    """Gerencia a interface do usuário e o ciclo principal de execução do Jarvis."""
    
    def __init__(self, openai_client, audio_handler):
        """
        Inicializa a interface do Jarvis.
        
        Args:
            openai_client: Cliente para interação com a API OpenAI
            audio_handler: Manipulador para operações de áudio
        """
        self.openai_client = openai_client
        self.audio_handler = audio_handler
        log.debug("Interface Jarvis inicializada")
    
    def analyze_image(self, image_path):
        """
        Analisa uma imagem usando a API OpenAI.
        
        Args:
            image_path: Caminho para a imagem a ser analisada
        """
        log.info(f"Analisando imagem: {image_path}")
        response = self.openai_client.send_message("O que você vê nesta imagem?", image_path=image_path)
        self.audio_handler.speak(response)
    
    def run_conversation(self, with_voice=True):
        """
        Executa um loop contínuo de conversação com o usuário.
        
        Args:
            with_voice: Se True, usa entrada e saída por voz; caso contrário, usa texto
        """
        try:
            # Verifica se estamos usando uma thread existente ou nova
            thread_id = os.environ.get("JARVIS_THREAD_ID")
            if thread_id and thread_id == self.openai_client.thread.id:
                # Usando thread existente, saudação para conversa contínua
                log.info("Continuando conversa com thread existente")
                self.audio_handler.speak("Olá novamente. Continuando nossa conversa.")
            else:
                # Nova thread, usar saudação inicial completa
                log.info("Iniciando nova conversa")
                self.audio_handler.speak("Olá, eu sou o Jarvis. Como posso ajudar você hoje?")
            
            while True:
                try:
                    if with_voice:
                        # Listen for user input
                        log.debug("Aguardando entrada de voz")
                        user_input = self.audio_handler.listen()
                        
                        # Handle speech recognition errors
                        if user_input in ["SPEECH_NOT_RECOGNIZED", "SPEECH_SERVICE_DOWN", "SPEECH_ERROR"]:
                            if user_input == "SPEECH_NOT_RECOGNIZED":
                                log.warning("Fala não reconhecida")
                                self.audio_handler.speak("Desculpe, não entendi. Pode repetir?")
                            else:
                                log.error(f"Erro de reconhecimento: {user_input}")
                                self.audio_handler.speak("Desculpe, estou tendo problemas para entender você.")
                            continue
                        
                        # Check for exit command
                        if "sair" in user_input.lower() or "encerrar" in user_input.lower():
                            log.info("Comando de saída detectado")
                            self.audio_handler.speak("Até logo!")
                            break
                    else:
                        # Text input mode
                        log.debug("Aguardando entrada de texto")
                        user_input = input("Você: ")
                        
                        # Check for exit command
                        if user_input.lower() in ["sair", "exit", "quit"]:
                            log.info("Comando de saída detectado")
                            self.audio_handler.speak("Até logo!")
                            break
                    
                    # Log a entrada do usuário
                    log.info(f"Entrada do usuário: {user_input}")
                    
                    # Verifica se a pergunta é sobre código
                    if _has_code_analyzer and self._is_code_question(user_input):
                        log.info("Pergunta sobre código detectada, usando analisador de código")
                        
                        # Obtenha o diretório do projeto Jarvis
                        project_dir = os.path.dirname(os.path.abspath(__file__))
                        
                        # Use o analisador de código para obter uma resposta contextualizada
                        response = process_query_with_context(
                            directory=project_dir,
                            user_question=user_input,
                            openai_client=self.openai_client,
                            use_cache=True
                        )
                    else:
                        # Get response from assistant (método padrão)
                        log.debug("Enviando mensagem para o assistente")
                        response = self.openai_client.send_message(user_input)
                    
                    # Speak the response
                    self.audio_handler.speak(response)
                    
                except KeyboardInterrupt:
                    log.warning("Interrupção de teclado durante a conversa")
                    log.info("Encerrando Jarvis por interrupção do usuário")
                    try:
                        # Mudar para modo texto para a despedida
                        self.audio_handler.text_only = True
                        self.audio_handler.speak("Até logo!")
                    except Exception as e:
                        log.error(f"Erro na despedida: {e}")
                    break
                except Exception as e:
                    log.exception(f"Erro durante a conversa: {e}")
                    self.audio_handler.speak("Encontrei um erro. Vamos tentar novamente.")
        
        except KeyboardInterrupt:
            # Captura Ctrl+C durante a saudação inicial ou outras operações
            log.warning("Interrupção de teclado na inicialização")
            log.info("Encerrando Jarvis por interrupção do usuário")
        
        finally:
            # Limpar recursos ao sair
            self.audio_handler.cleanup()
            print("Jarvis encerrado.")
    
    def _is_code_question(self, question):
        """
        Verifica se a pergunta do usuário é relacionada a código ou ao funcionamento do Jarvis.
        
        Args:
            question: A pergunta do usuário
            
        Returns:
            Boolean indicando se a pergunta é sobre código
        """
        # Converte para minúsculas para facilitar a comparação
        question_lower = question.lower()
        
        # Palavras-chave que indicam perguntas sobre código
        code_keywords = [
            "código", "function", "classe", "método", "implementação", "como funciona",
            "código fonte", "arquivo", "módulo", "implementado", "código do jarvis",
            "como está implementado", "estrutura do código", "arquitetura", "desenvolvimento",
            "programação", "projeto", "sistema", "openai_client", "audio_handler", "interface",
            "log_manager", "script", "python", "def ", "class ", "import ", "pacote", "biblioteca"
        ]
        
        # Verifica se qualquer palavra-chave está na pergunta
        for keyword in code_keywords:
            if keyword in question_lower:
                log.debug(f"Palavra-chave de código detectada: '{keyword}'")
                return True
                
        # Padrões de expressão regular que indicam perguntas sobre código
        code_patterns = [
            r'como\s+(?:você|o sistema|o jarvis)\s+(?:está|é|foi)\s+(?:feito|implementado|programado|desenvolvido|codificado)',
            r'(?:explique|mostre|detalhe)\s+(?:o|a)\s+(?:código|implementação|funcionamento|arquitetura)',
            r'(?:qual|como\s+é)\s+a\s+(?:estrutura|arquitetura|organização)\s+do\s+(?:código|sistema|projeto)',
            r'(?:onde|como)\s+(?:está|é)\s+definido',
            r'(?:qual|como)\s+(?:arquivo|módulo|classe|função)',
        ]
        
        # Verifica se qualquer padrão corresponde à pergunta
        for pattern in code_patterns:
            if re.search(pattern, question_lower):
                log.debug(f"Padrão de código detectado: '{pattern}'")
                return True
                
        return False
