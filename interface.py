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
    
    def is_github_query(self, user_input):
        """
        Verifica se a pergunta do usuário é relacionada ao GitHub.
        
        Args:
            user_input: A pergunta ou comando do usuário
            
        Returns:
            Boolean indicando se a pergunta é sobre GitHub
        """
        github_keywords = [
            "github", "repositório", "repositorio", "repo", 
            "commit", "branches", "pull request", "pr", 
            "código fonte", "codigo fonte", "fonte", 
            "último commit", "ultimo commit", "alterações",
            "alteracoes", "modificações", "modificacoes",
            "alterou", "modificou", "mudou", "atualizou",
            "lista de arquivos", "arquivos do projeto",
            "mostra o código", "mostra o codigo", "ver código", "ver codigo",
            "listar arquivos", "ver arquivo", "mostrar arquivo"
        ]
        
        # Converte para minúsculas para facilitar a comparação
        user_input_lower = user_input.lower()
        
        # Verifica se alguma das palavras-chave está presente na pergunta
        for keyword in github_keywords:
            if keyword in user_input_lower:
                log.debug(f"Consulta GitHub detectada: '{user_input}'")
                return True
                
        return False
    
    def process_github_query(self, user_input):
        """
        Processa uma consulta relacionada ao GitHub e retorna a resposta.
        
        Args:
            user_input: A pergunta ou comando do usuário relacionado ao GitHub
            
        Returns:
            str: Resposta com informações do GitHub
        """
        # Verifica se o GitHub está habilitado
        if not self.openai_client.github_retriever.is_enabled():
            return "Desculpe, a integração com GitHub não está configurada. Verifique se as variáveis GITHUB_API_TOKEN, GITHUB_REPO_OWNER e GITHUB_REPO_NAME estão definidas no arquivo .env."
        
        # Verifica se é uma pergunta sobre acesso ao GitHub
        if "acesso ao github" in user_input.lower() or "tem acesso" in user_input.lower():
            repo_info = f"{self.openai_client.github_retriever.repo_owner}/{self.openai_client.github_retriever.repo_name}"
            return f"Sim, tenho acesso ao repositório GitHub: {repo_info}. Posso listar arquivos, mostrar código, obter commits recentes e outras informações. Como posso ajudar com o GitHub?"
        
        # Comandos específicos para commits
        if "commits" in user_input.lower() or "últimos commits" in user_input.lower():
            log.info("Obtendo os commits mais recentes do repositório")
            commits = self.openai_client.github_retriever.get_recent_commits()
            if not commits:
                return "Não foi possível obter os commits mais recentes."
            
            response = "Commits mais recentes:\n"
            for commit in commits:
                response += f"- {commit['message']} por {commit['author']} em {commit['date']}\n  Link: {commit['url']}\n"
            return response
        
        # Listar arquivos do repositório
        if "listar arquivos" in user_input.lower() or "ver arquivos" in user_input.lower():
            log.info("Listando arquivos do repositório")
            files = self.openai_client.github_retriever.list_files()
            if not files:
                return "Não foi possível listar os arquivos do repositório."
            
            response = "Arquivos no repositório:\n"
            for file in files[:20]:  # Limita a 20 arquivos para não sobrecarregar a resposta
                response += f"- {file['path']}\n"
            
            if len(files) > 20:
                response += f"\n... e mais {len(files) - 20} arquivos."
            
            return response
        
        # Para outras consultas, passamos para o LLM responder com contexto do GitHub
        return self.openai_client.send_message(f"Esta é uma pergunta sobre o repositório GitHub {self.openai_client.github_retriever.repo_owner}/{self.openai_client.github_retriever.repo_name}: {user_input}")
    
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
                    
                    # Verifica se é uma consulta relacionada ao GitHub
                    if self.is_github_query(user_input):
                        log.info("Processando consulta GitHub")
                        response = self.process_github_query(user_input)
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
        Otimizada para ser mais seletiva e reduzir o uso desnecessário de tokens.
        
        Args:
            question: A pergunta do usuário
            
        Returns:
            Boolean indicando se a pergunta é sobre código
        """
        # Converte para minúsculas para facilitar a comparação
        question_lower = question.lower()
        
        # Sistema de pontuação para determinar a necessidade do analisador de código
        score = 0
        
        # Palavras-chave de alta relevância (forte indicação de perguntas sobre o código)
        high_relevance_keywords = [
            "código fonte", "implementação", "arquitetura do jarvis",
            "como funciona o código", "estrutura do projeto",
            "como está implementado o", "def ", "class "
        ]
        
        # Palavras-chave de média relevância
        medium_relevance_keywords = [
            "módulo", "função", "classe", "método", 
            "openai_client", "audio_handler"
        ]
        
        # Palavras-chave gerais (baixa relevância)
        low_relevance_keywords = [
            "código", "python", "arquivo", "sistema", 
            "desenvolvimento", "programação"
        ]
        
        # Verifica palavras-chave de alta relevância (3 pontos cada)
        for keyword in high_relevance_keywords:
            if keyword in question_lower:
                log.debug(f"Palavra-chave de alta relevância detectada: '{keyword}'")
                score += 3
                
        # Verifica palavras-chave de média relevância (2 pontos cada)
        for keyword in medium_relevance_keywords:
            if keyword in question_lower:
                log.debug(f"Palavra-chave de média relevância detectada: '{keyword}'")
                score += 2
                
        # Verifica palavras-chave de baixa relevância (1 ponto cada)
        for keyword in low_relevance_keywords:
            if keyword in question_lower:
                log.debug(f"Palavra-chave de baixa relevância detectada: '{keyword}'")
                score += 1
                
        # Padrões de expressão regular específicos (3 pontos cada)
        specific_code_patterns = [
            r'como\s+(?:você|o jarvis)\s+(?:está|foi)\s+implementado',
            r'explique\s+(?:o|a)\s+(?:código|implementação|arquitetura)\s+do\s+jarvis',
            r'(?:qual|como\s+é)\s+a\s+estrutura\s+do\s+código',
            r'como\s+funciona\s+(?:o módulo|a classe|o arquivo)\s+(\w+)'
        ]
        
        # Verifica os padrões específicos
        for pattern in specific_code_patterns:
            if re.search(pattern, question_lower):
                log.debug(f"Padrão específico de código detectado: '{pattern}'")
                score += 3
        
        # Define um limiar para utilizar o analisador de código (min. 3 pontos)
        threshold = 3
        should_use_analyzer = score >= threshold
        
        if should_use_analyzer:
            log.info(f"Análise de código necessária (pontuação: {score})")
        else:
            log.info(f"Análise de código não necessária (pontuação: {score})")
            
        return should_use_analyzer
