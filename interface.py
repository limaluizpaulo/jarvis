#!/usr/bin/env python3
# filepath: /home/comunikime/code/jarvis/interface.py
"""
Módulo para gerenciar a interface do usuário do Jarvis, incluindo
o ciclo principal de execução e interação com o usuário via texto ou voz.
"""

import os
import sys

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
    
    def analyze_image(self, image_path):
        """
        Analisa uma imagem usando a API OpenAI.
        
        Args:
            image_path: Caminho para a imagem a ser analisada
        """
        print(f"Analisando imagem: {image_path}")
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
                self.audio_handler.speak("Olá novamente. Continuando nossa conversa.")
            else:
                # Nova thread, usar saudação inicial completa
                self.audio_handler.speak("Olá, eu sou o Jarvis. Como posso ajudar você hoje?")
            
            while True:
                try:
                    if with_voice:
                        # Listen for user input
                        user_input = self.audio_handler.listen()
                        
                        # Handle speech recognition errors
                        if user_input in ["SPEECH_NOT_RECOGNIZED", "SPEECH_SERVICE_DOWN", "SPEECH_ERROR"]:
                            if user_input == "SPEECH_NOT_RECOGNIZED":
                                self.audio_handler.speak("Desculpe, não entendi. Pode repetir?")
                            else:
                                self.audio_handler.speak("Desculpe, estou tendo problemas para entender você.")
                            continue
                        
                        # Check for exit command
                        if "sair" in user_input.lower() or "encerrar" in user_input.lower():
                            self.audio_handler.speak("Até logo!")
                            break
                    else:
                        # Text input mode
                        user_input = input("Você: ")
                        
                        # Check for exit command
                        if user_input.lower() in ["sair", "exit", "quit"]:
                            self.audio_handler.speak("Até logo!")
                            break
                    
                    # Get response from assistant
                    response = self.openai_client.send_message(user_input)
                    
                    # Speak the response
                    self.audio_handler.speak(response)
                    
                except KeyboardInterrupt:
                    print("\nEncerrando Jarvis por interrupção do usuário...")
                    try:
                        # Mudar para modo texto para a despedida
                        self.audio_handler.text_only = True
                        self.audio_handler.speak("Até logo!")
                    except:
                        pass
                    break
                except Exception as e:
                    print(f"Erro: {str(e)}")
                    self.audio_handler.speak("Encontrei um erro. Vamos tentar novamente.")
        
        except KeyboardInterrupt:
            # Captura Ctrl+C durante a saudação inicial ou outras operações
            print("\nEncerrando Jarvis por interrupção do usuário...")
        
        finally:
            # Limpar recursos ao sair
            self.audio_handler.cleanup()
            print("Jarvis encerrado.")
