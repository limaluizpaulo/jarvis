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
from typing import Optional, Dict, Any, Union, Tuple

from openai import OpenAI

# Importações locais
from cache_manager import CacheManager
from log_manager import LogManager

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
        assistant = self.client.beta.assistants.create(
            name="Jarvis",
            instructions=(
                "Você é Jarvis, um assistente pessoal inteligente e conciso. "
                "Pode descrever imagens e responder por voz."
            ),
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
