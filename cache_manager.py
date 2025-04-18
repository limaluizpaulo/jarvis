# filepath: /home/comunikime/code/jarvis/cache_manager.py
#!/usr/bin/env python3
"""
Módulo para gerenciamento de cache local para o Jarvis,
reduzindo chamadas desnecessárias à API.
"""

import os
import json
import hashlib
import time
from typing import Dict, Any, Optional

class CacheManager:
    """Gerencia o cache local para reduzir chamadas repetitivas à API."""
    
    def __init__(self, cache_dir: str = None, max_age_seconds: int = 86400):
        """
        Inicializa o gerenciador de cache.
        
        Args:
            cache_dir: Diretório para armazenar arquivos de cache
            max_age_seconds: Tempo máximo em segundos para um item de cache ser considerado válido
        """
        self.max_age_seconds = max_age_seconds
        
        # Definir diretório de cache padrão se não especificado
        if not cache_dir:
            cache_dir = os.path.expanduser("~/.jarvis/cache")
        
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Cache em memória para acesso mais rápido
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
    
    def _generate_key(self, data: Any) -> str:
        """
        Gera uma chave única baseada nos dados.
        
        Args:
            data: Dados a serem usados para gerar a chave
            
        Returns:
            str: Chave hash gerada
        """
        # Converte dados para string
        data_str = json.dumps(data, sort_keys=True)
        # Gera hash SHA-256
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def _get_cache_path(self, key: str) -> str:
        """
        Obtém o caminho do arquivo de cache para uma chave.
        
        Args:
            key: Chave do cache
            
        Returns:
            str: Caminho completo do arquivo
        """
        return os.path.join(self.cache_dir, f"{key}.json")
    
    def get(self, key_data: Any) -> Optional[Dict[str, Any]]:
        """
        Obtém um valor do cache se existir e for válido.
        
        Args:
            key_data: Dados usados para gerar a chave
            
        Returns:
            Optional[Dict[str, Any]]: Valor do cache ou None se não existir ou estiver expirado
        """
        key = self._generate_key(key_data)
        
        # Primeiro tenta o cache em memória
        if key in self.memory_cache:
            cached = self.memory_cache[key]
            if time.time() - cached["timestamp"] < self.max_age_seconds:
                return cached["data"]
            # Se expirou, remove do cache de memória
            del self.memory_cache[key]
        
        # Se não existir em memória, tenta do arquivo
        cache_path = self._get_cache_path(key)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r") as f:
                    cached = json.load(f)
                
                # Verifica se o cache ainda é válido
                if time.time() - cached["timestamp"] < self.max_age_seconds:
                    # Armazena em memória para acesso mais rápido da próxima vez
                    self.memory_cache[key] = cached
                    return cached["data"]
                else:
                    # Remove arquivo de cache expirado
                    os.remove(cache_path)
            except (json.JSONDecodeError, KeyError, OSError):
                # Em caso de erro, ignora o cache
                if os.path.exists(cache_path):
                    os.remove(cache_path)
        
        return None
    
    def set(self, key_data: Any, value: Any) -> None:
        """
        Armazena um valor no cache.
        
        Args:
            key_data: Dados usados para gerar a chave
            value: Valor a ser armazenado
        """
        key = self._generate_key(key_data)
        cache_data = {
            "timestamp": time.time(),
            "data": value
        }
        
        # Armazena em memória
        self.memory_cache[key] = cache_data
        
        # Armazena em arquivo
        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, "w") as f:
                json.dump(cache_data, f)
        except OSError:
            # Ignora erros de escrita no arquivo
            pass
    
    def clear(self, max_age_seconds: Optional[int] = None) -> int:
        """
        Limpa entradas de cache expiradas.
        
        Args:
            max_age_seconds: Tempo máximo em segundos ou None para usar o tempo padrão
            
        Returns:
            int: Número de entradas removidas
        """
        if max_age_seconds is None:
            max_age_seconds = self.max_age_seconds
        
        # Limpa cache em memória
        current_time = time.time()
        keys_to_remove = [
            k for k, v in self.memory_cache.items() 
            if current_time - v["timestamp"] > max_age_seconds
        ]
        
        for k in keys_to_remove:
            del self.memory_cache[k]
        
        # Limpa arquivos de cache
        removed_count = len(keys_to_remove)
        for filename in os.listdir(self.cache_dir):
            if not filename.endswith(".json"):
                continue
                
            file_path = os.path.join(self.cache_dir, filename)
            try:
                with open(file_path, "r") as f:
                    cached = json.load(f)
                
                if current_time - cached["timestamp"] > max_age_seconds:
                    os.remove(file_path)
                    removed_count += 1
            except (json.JSONDecodeError, KeyError, OSError):
                # Remove arquivos inválidos
                try:
                    os.remove(file_path)
                    removed_count += 1
                except OSError:
                    pass
        
        return removed_count
