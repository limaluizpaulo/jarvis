#!/usr/bin/env python3
# filepath: /home/comunikime/code/jarvis/openai_client.py
"""
Módulo para interação com a API OpenAI, gerenciando assistentes e threads
de conversação para o assistente Jarvis.
"""

import base64
import json
import os
import time
from typing import Optional, Dict, Any, Union, Tuple, List

from openai import OpenAI

# Importações locais
from cache_manager import CacheManager
from log_manager import LogManager
from github_retriever import GitHubRetriever

# Configura o logger
log = LogManager().logger

# ================= ASSISTANT / THREAD POOL =================
_ASSISTANTS_FILE = os.path.expanduser("~/.jarvis/assistants.json")
os.makedirs(os.path.dirname(_ASSISTANTS_FILE), exist_ok=True)
if not os.path.exists(_ASSISTANTS_FILE):
    with open(_ASSISTANTS_FILE, "w") as fp:
        json.dump({}, fp)

def _load_meta():
    """Carrega metadados de assistentes salvos localmente."""
    try:
        with open(_ASSISTANTS_FILE) as fp:
            return json.load(fp)
    except (json.JSONDecodeError, OSError) as e:
        log.error(f"Erro ao carregar metadados de assistentes: {e}")
        return {}

def _save_meta(meta):
    """Salva metadados de assistentes localmente."""
    try:
        with open(_ASSISTANTS_FILE, "w") as fp:
            json.dump(meta, fp, indent=2)
    except OSError as e:
        log.error(f"Erro ao salvar metadados de assistentes: {e}")

class AssistantManager:
    """Gerencia assistentes e threads da OpenAI, guardando IDs localmente."""

    def __init__(self, client: OpenAI):
        self.client = client
        self.meta = _load_meta()
        self.cache = CacheManager(cache_dir=os.path.expanduser("~/.jarvis/cache/assistants"))
        log.debug("AssistantManager inicializado")

    def get(self, name: str, instructions: str) -> tuple[str, str]:
        """
        Obtém ou cria um assistente e thread para o nome fornecido.
        
        Args:
            name: Nome do assistente
            instructions: Instruções para o assistente
            
        Returns:
            tuple: (assistant_id, thread_id)
        """
        if name in self.meta:
            assistant_id = self.meta[name]["assistant_id"]
            thread_id = self.meta[name]["thread_id"]
            log.debug(f"Usando assistente e thread existentes: {assistant_id}, {thread_id}")
            return assistant_id, thread_id

        # novo assistant + thread
        log.info(f"Criando novo assistente com nome: {name}")
        a = self.client.beta.assistants.create(name=name, instructions=instructions, model="gpt-4o")
        t = self.client.beta.threads.create()
        self.meta[name] = {"assistant_id": a.id, "thread_id": t.id}
        _save_meta(self.meta)
        log.info(f"Assistente criado: {a.id}, Thread criado: {t.id}")
        return a.id, t.id

class OpenAIClient:
    """Gerencia interações com a API OpenAI para o assistente Jarvis."""
    
    def __init__(self):
        """Inicializa o cliente OpenAI e configura o assistente."""
        # Verificar API key do arquivo .env
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            log.critical("OPENAI_API_KEY não encontrada no arquivo .env")
            raise ValueError("OPENAI_API_KEY não encontrada no arquivo .env. Configure o arquivo .env com suas credenciais.")
        
        # Inicializa o cache
        self.cache = CacheManager(cache_dir=os.path.expanduser("~/.jarvis/cache/openai"))
        log.debug("Cache inicializado")
        
        # Inicializa cliente OpenAI
        self.client = OpenAI(api_key=api_key)
        log.debug("Cliente OpenAI inicializado")
        
        # Inicializa integração com GitHub
        self.github_retriever = GitHubRetriever()
        log.debug("GitHub Retriever inicializado")
        
        # Configurações para gerenciamento de assistentes
        self.assistant_manager = AssistantManager(self.client)
        
        # Create or retrieve assistant
        self.assistant = self._get_or_create_assistant()
        
        # Create a new thread or use existing one
        thread_id = os.getenv("JARVIS_THREAD_ID")
        if thread_id:
            try:
                self.thread = self.client.beta.threads.retrieve(thread_id)
                log.info(f"Usando thread existente: {thread_id}")
            except Exception as e:
                log.warning(f"Erro ao recuperar thread existente: {e}")
                self.thread = self.client.beta.threads.create()
                log.info(f"Nova thread criada: {self.thread.id}")
        else:
            self.thread = self.client.beta.threads.create()
            log.info(f"Nova thread criada: {self.thread.id}")
            log.info(f"Configure JARVIS_THREAD_ID={self.thread.id} para manter o histórico de conversa")
    
    def _get_or_create_assistant(self):
        """
        Recupera um assistente existente ou cria um novo.
        
        Returns:
            O assistente configurado
        """
        assistant_id = os.getenv("JARVIS_ASSISTANT_ID")
        
        if assistant_id:
            try:
                log.debug(f"Tentando recuperar assistente com ID {assistant_id}")
                return self.client.beta.assistants.retrieve(assistant_id)
            except Exception as e:
                log.warning(f"Não foi possível recuperar o assistente com ID {assistant_id}. Criando novo assistente. Erro: {e}")
        
        # Create a new assistant
        log.info("Criando novo assistente")
        
        # Base de instruções para o assistente
        instructions = (
            "Você é Jarvis, um assistente pessoal inteligente e conciso. "
            "Pode descrever imagens e responder por voz."
        )
        
        # Adicionar instruções de pair programming se o GitHub estiver configurado
        if self.github_retriever.is_enabled():
            instructions += (
                "\n\nVocê também atua como parceiro de programação (pair programming), "
                "ajudando a analisar, revisar e escrever código. "
                "Você tem acesso ao repositório GitHub do usuário e pode consultar "
                "arquivos específicos quando solicitado. "
                "Quando o usuário pedir para analisar código, pergunte qual arquivo "
                "ou diretório deseja examinar. "
                "Quando o usuário perguntar sobre acesso ao GitHub, sempre confirme "
                f"que você tem acesso ao repositório: {self.github_retriever.repo_owner}/{self.github_retriever.repo_name}."
            )
        
        # Criar o assistente
        assistant = self.client.beta.assistants.create(
            name="Jarvis",
            instructions=instructions,
            model="gpt-4o"  # visão já é nativa do modelo
        )
        
        log.info(f"Novo assistente criado com ID: {assistant.id}")
        log.info(f"Configure JARVIS_ASSISTANT_ID={assistant.id} para reutilizar este assistente")
        
        return assistant
    
    def send_message(self, content, image_path=None):
        """
        Envia uma mensagem para o assistente e obtém uma resposta.
        
        Args:
            content: Texto da mensagem
            image_path: Caminho opcional para uma imagem a ser analisada
            
        Returns:
            str: Resposta do assistente ou mensagem de erro
        """
        # Verifica consultas GitHub em linguagem natural
        if isinstance(content, str):
            # Primeiro verifica se é uma consulta em linguagem natural
            github_response = self.process_github_query(content)
            if github_response:
                return github_response
                
            # Se não for linguagem natural, verifica comandos explícitos
            if content.startswith("!github"):
                parts = content.split(maxsplit=2)
                if len(parts) < 2:
                    return "Comando inválido. Use !github list [caminho] ou !github get [arquivo]"
                
                command = parts[1]
                
                if command == "list":
                    path = parts[2] if len(parts) > 2 else ""
                    return self.list_github_files(path)
                
                if command == "get":
                    if len(parts) < 3:
                        return "Especifique o caminho do arquivo. Ex: !github get src/main.py"
                    return self.get_github_file(parts[2])
                
                return f"Comando GitHub desconhecido: {command}. Comandos disponíveis: list, get."
        
        # Verifica se a resposta está em cache quando não há imagem
        # (não fazemos cache de análise de imagens)
        cache_key = None
        if not image_path:
            cache_key = {"content": content, "thread_id": self.thread.id}
            cached_response = self.cache.get(cache_key)
            if cached_response:
                log.info("Usando resposta em cache")
                return cached_response
        
        try:
            message_content = []
            
            # Add text content if provided
            if isinstance(content, str) and content.strip():
                message_content.append({"type": "text", "text": content})
            
            # Add image if provided
            if image_path:
                if os.path.exists(image_path):
                    log.info(f"Processando imagem: {image_path}")
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
                    log.error(f"Arquivo de imagem não encontrado: {image_path}")
                    return f"Erro: Arquivo de imagem não encontrado: {image_path}"
            
            # If no content was added, return error
            if not message_content:
                log.error("Nenhum conteúdo fornecido")
                return "Erro: Nenhum conteúdo fornecido"
            
            # Send message to thread
            log.debug(f"Enviando mensagem para thread {self.thread.id}")
            self.client.beta.threads.messages.create(
                thread_id=self.thread.id,
                role="user",
                content=message_content
            )
            
            # Run the assistant
            log.debug(f"Executando assistente {self.assistant.id}")
            run = self.client.beta.threads.runs.create(
                thread_id=self.thread.id,
                assistant_id=self.assistant.id
            )
            
            # Wait for completion with status updates
            log.info("Processando...")
            start_time = time.time()
            while True:
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id=self.thread.id,
                    run_id=run.id
                )
                
                if run_status.status == "completed":
                    elapsed_time = time.time() - start_time
                    log.info(f"Processamento concluído em {elapsed_time:.2f} segundos")
                    break
                elif run_status.status in ["failed", "cancelled", "expired"]:
                    log.error(f"Processamento falhou: {run_status.status}")
                    return f"Erro: {run_status.last_error}"
                
                # Log menos frequente para não sobrecarregar
                log.debug(f"Status do processamento: {run_status.status}")
                time.sleep(1)
            
            # Get the latest message
            log.debug(f"Obtendo mensagens da thread {self.thread.id}")
            messages = self.client.beta.threads.messages.list(
                thread_id=self.thread.id
            )
            
            # Return the assistant's response
            for message in messages.data:
                if message.role == "assistant":
                    for content_item in message.content:
                        if content_item.type == "text":
                            response = content_item.text.value
                            
                            # Armazena em cache se não for análise de imagem
                            if cache_key:
                                self.cache.set(cache_key, response)
                                log.debug("Resposta armazenada em cache")
                            
                            return response
            
            log.warning("Nenhuma resposta recebida do assistente")
            return "Nenhuma resposta recebida."
        
        except Exception as e:
            log.exception(f"Erro ao processar mensagem: {str(e)}")
            return f"Erro: {str(e)}"
    
    def get_raw_client(self):
        """
        Retorna o cliente OpenAI para uso direto em outros módulos.
        
        Returns:
            OpenAI: Cliente OpenAI
        """
        return self.client
    
    def get_github_file(self, file_path: str) -> Optional[str]:
        """
        Obtém o conteúdo de um arquivo do GitHub.
        
        Args:
            file_path: Caminho do arquivo no repositório
            
        Returns:
            Conteúdo do arquivo ou None se não encontrado/disponível
        """
        if not self.github_retriever.is_enabled():
            return "Integração com GitHub não está configurada. Configure as variáveis GITHUB_API_TOKEN, GITHUB_REPO_OWNER e GITHUB_REPO_NAME no arquivo .env."
        
        content = self.github_retriever.get_file_content(file_path)
        if content is None:
            return f"Não foi possível obter o arquivo {file_path}."
        
        return content

    def list_github_files(self, path: str = "", extension: str = None) -> str:
        """
        Lista arquivos do repositório GitHub.
        
        Args:
            path: Caminho dentro do repositório
            extension: Extensão para filtrar
            
        Returns:
            String formatada com lista de arquivos
        """
        if not self.github_retriever.is_enabled():
            return "Integração com GitHub não está configurada. Configure as variáveis GITHUB_API_TOKEN, GITHUB_REPO_OWNER e GITHUB_REPO_NAME no arquivo .env."
        
        files = self.github_retriever.list_files(path, extension)
        if not files:
            return f"Nenhum arquivo encontrado no caminho: {path}"
        
        result = "Arquivos encontrados:\n"
        for file in files:
            result += f"- {file['path']} ({file['size']} bytes)\n"
        
        return result
    
    def process_github_query(self, content: str) -> Optional[str]:
        """
        Processa consultas sobre GitHub em linguagem natural e as converte
        em comandos apropriados.
        
        Args:
            content: Texto da mensagem do usuário
            
        Returns:
            Resposta processada ou None se não for uma consulta GitHub
        """
        # Verificar se a integração com GitHub está ativada
        if not self.github_retriever.is_enabled():
            return None
            
        # Palavras-chave que indicam consulta ao GitHub
        github_keywords = [
            "github", "repositório", "repositorio", "repo", "git", 
            "código fonte", "codigo fonte", "arquivos do projeto"
        ]
        
        content_lower = content.lower()
        is_github_query = any(keyword in content_lower for keyword in github_keywords)
        
        if not is_github_query:
            return None
            
        log.info("Processando consulta GitHub")
        
        # Detecção de pedidos de visão geral do repositório
        overview_keywords = [
            "visão geral", "visao geral", "overview", "resumo", "estrutura", 
            "arquivos", "me mostre", "me dê", "me de"
        ]
        
        if any(keyword in content_lower for keyword in overview_keywords):
            return self.get_repo_overview()
            
        # Detecção de pedido de arquivo específico
        file_patterns = [
            r"arquivo\s+(.+?)[\s\.\?]",
            r"conteúdo\s+de\s+(.+?)[\s\.\?]",
            r"conteudo\s+de\s+(.+?)[\s\.\?]",
            r"ver\s+arquivo\s+(.+?)[\s\.\?]",
            r"ver\s+(.+\.(py|js|md|html|css|json))[\s\.\?]",
            r"abrir\s+(.+?)[\s\.\?]"
        ]
        
        import re
        for pattern in file_patterns:
            match = re.search(pattern, content_lower)
            if match:
                file_path = match.group(1).strip()
                return self.get_github_file(file_path)
        
        # Detecção de pedido para listar diretório específico
        dir_patterns = [
            r"listar\s+(.+?)[\s\.\?]",
            r"arquivos\s+em\s+(.+?)[\s\.\?]",
            r"diretório\s+(.+?)[\s\.\?]",
            r"diretorio\s+(.+?)[\s\.\?]",
            r"pasta\s+(.+?)[\s\.\?]"
        ]
        
        for pattern in dir_patterns:
            match = re.search(pattern, content_lower)
            if match:
                dir_path = match.group(1).strip()
                return self.list_github_files(dir_path)
        
        # Se não conseguir determinar um comando específico, 
        # mas for relacionado ao GitHub, mostrar visão geral
        return self.get_repo_overview()
        
    def get_repo_overview(self) -> str:
        """
        Fornece uma visão geral do repositório GitHub configurado.
        
        Returns:
            String formatada com visão geral do repositório
        """
        if not self.github_retriever.is_enabled():
            return "Integração com GitHub não está configurada. Configure as variáveis GITHUB_API_TOKEN, GITHUB_REPO_OWNER e GITHUB_REPO_NAME no arquivo .env."
        
        # Obter lista de arquivos na raiz
        files = self.github_retriever.list_files()
        
        # Obter commits recentes
        commits = self.github_retriever.get_recent_commits(5)
        
        # Formatar resposta
        result = f"# Visão Geral do Repositório: {self.github_retriever.repo_owner}/{self.github_retriever.repo_name}\n\n"
        
        # Adicionar estrutura de arquivos
        result += "## Estrutura de Arquivos (raiz):\n"
        if files:
            for file in files:
                # Adicionar ícone de pasta ou arquivo
                icon = "📁 " if file["type"] == "dir" else "📄 "
                result += f"{icon}{file['path']}\n"
        else:
            result += "Nenhum arquivo encontrado na raiz do repositório.\n"
        
        # Adicionar commits recentes
        result += "\n## Commits Recentes:\n"
        if commits:
            for i, commit in enumerate(commits, 1):
                date = commit["date"]
                message = commit["message"].split("\n")[0]  # Primeira linha da mensagem
                author = commit["author"]
                result += f"{i}. **{message}** (por {author} em {date})\n"
        else:
            result += "Não foi possível obter commits recentes.\n"
            
        # Adicionar instruções para comandos específicos
        result += "\n## Comandos Disponíveis:\n"
        result += "- Para listar arquivos de um diretório específico: `!github list [caminho]`\n"
        result += "- Para ver o conteúdo de um arquivo específico: `!github get [arquivo]`\n"
            
        return result
