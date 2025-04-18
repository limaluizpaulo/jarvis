#!/usr/bin/env python3
# filepath: /home/comunikime/code/jarvis/github_retriever.py
"""
Módulo para integração com o GitHub, permitindo ao assistente Jarvis
acessar arquivos de um repositório para pair programming.
"""

import os
import base64
from typing import List, Dict, Any, Optional
from github import Github, GithubException

from log_manager import LogManager

# Configurar logger
log = LogManager().logger

class GitHubRetriever:
    """Gerencia acesso a repositórios do GitHub."""
    
    def __init__(self):
        """Inicializa o cliente GitHub."""
        # Verificar token do GitHub do arquivo .env
        github_token = os.getenv("GITHUB_API_TOKEN")
        if not github_token:
            log.warning("GITHUB_API_TOKEN não encontrado. A integração com GitHub não estará disponível.")
            self.github = None
            self.enabled = False
            return
            
        self.repo_owner = os.getenv("GITHUB_REPO_OWNER")
        self.repo_name = os.getenv("GITHUB_REPO_NAME")
        
        if not self.repo_owner or not self.repo_name:
            log.warning("GITHUB_REPO_OWNER ou GITHUB_REPO_NAME não definidos. Configure essas variáveis no arquivo .env.")
            self.github = None
            self.enabled = False
            return
            
        try:
            self.github = Github(github_token)
            # Testa a conexão tentando acessar o repositório
            self.repo = self.github.get_repo(f"{self.repo_owner}/{self.repo_name}")
            self.enabled = True
            log.info(f"Integração com GitHub ativada para repositório: {self.repo_owner}/{self.repo_name}")
        except GithubException as e:
            log.error(f"Erro ao conectar ao GitHub: {e}")
            self.github = None
            self.enabled = False
    
    def is_enabled(self) -> bool:
        """Verifica se a integração com GitHub está habilitada."""
        return self.enabled
    
    def list_files(self, path: str = "", extension: str = None) -> List[Dict[str, str]]:
        """
        Lista arquivos no repositório com base no caminho e extensão.
        
        Args:
            path: Caminho dentro do repositório para listar arquivos
            extension: Extensão de arquivo para filtrar (.py, .js, etc)
            
        Returns:
            Lista de dicionários com informações dos arquivos
        """
        if not self.enabled:
            log.warning("Tentativa de listar arquivos com integração GitHub desabilitada")
            return []
            
        try:
            contents = self.repo.get_contents(path)
            files = []
            
            while contents:
                file_content = contents.pop(0)
                if file_content.type == "dir":
                    contents.extend(self.repo.get_contents(file_content.path))
                else:
                    if extension and not file_content.path.endswith(extension):
                        continue
                        
                    files.append({
                        "name": file_content.name,
                        "path": file_content.path,
                        "type": file_content.type,
                        "size": file_content.size
                    })
            
            return files
        except GithubException as e:
            log.error(f"Erro ao listar arquivos do GitHub: {e}")
            return []
    
    def get_file_content(self, file_path: str) -> Optional[str]:
        """
        Obtém o conteúdo de um arquivo do repositório.
        
        Args:
            file_path: Caminho do arquivo no repositório
            
        Returns:
            Conteúdo do arquivo ou None se não encontrado
        """
        if not self.enabled:
            log.warning("Tentativa de obter conteúdo de arquivo com integração GitHub desabilitada")
            return None
            
        try:
            file_content = self.repo.get_contents(file_path)
            decoded_content = base64.b64decode(file_content.content).decode('utf-8')
            return decoded_content
        except GithubException as e:
            log.error(f"Erro ao obter conteúdo do arquivo {file_path}: {e}")
            return None
    
    def get_recent_commits(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        Obtém os commits mais recentes do repositório.
        
        Args:
            count: Número de commits para retornar
            
        Returns:
            Lista de dicionários com informações dos commits
        """
        if not self.enabled:
            log.warning("Tentativa de obter commits com integração GitHub desabilitada")
            return []
            
        try:
            commits = self.repo.get_commits()[:count]
            result = []
            
            for commit in commits:
                result.append({
                    "sha": commit.sha,
                    "message": commit.commit.message,
                    "author": commit.commit.author.name,
                    "date": commit.commit.author.date.strftime("%Y-%m-%d %H:%M:%S"),
                    "url": commit.html_url
                })
                
            return result
        except GithubException as e:
            log.error(f"Erro ao obter commits do GitHub: {e}")
            return []
    
    def get_pull_requests(self, state: str = "open", count: int = 5) -> List[Dict[str, Any]]:
        """
        Obtém os pull requests do repositório.
        
        Args:
            state: Estado dos PRs ('open', 'closed', 'all')
            count: Número de PRs para retornar
            
        Returns:
            Lista de dicionários com informações dos PRs
        """
        if not self.enabled:
            log.warning("Tentativa de obter PRs com integração GitHub desabilitada")
            return []
            
        try:
            pulls = self.repo.get_pulls(state=state)[:count]
            result = []
            
            for pr in pulls:
                result.append({
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state,
                    "author": pr.user.login,
                    "created_at": pr.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "url": pr.html_url
                })
                
            return result
        except GithubException as e:
            log.error(f"Erro ao obter pull requests do GitHub: {e}")
            return []
    
    def get_issues(self, state: str = "open", count: int = 5) -> List[Dict[str, Any]]:
        """
        Obtém as issues do repositório.
        
        Args:
            state: Estado das issues ('open', 'closed', 'all')
            count: Número de issues para retornar
            
        Returns:
            Lista de dicionários com informações das issues
        """
        if not self.enabled:
            log.warning("Tentativa de obter issues com integração GitHub desabilitada")
            return []
            
        try:
            issues = self.repo.get_issues(state=state)[:count]
            result = []
            
            for issue in issues:
                # Pular pull requests que são tratados como issues na API
                if issue.pull_request:
                    continue
                    
                result.append({
                    "number": issue.number,
                    "title": issue.title,
                    "state": issue.state,
                    "author": issue.user.login,
                    "created_at": issue.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "url": issue.html_url
                })
                
            return result
        except GithubException as e:
            log.error(f"Erro ao obter issues do GitHub: {e}")
            return []
    
    def get_collaborators(self) -> List[Dict[str, Any]]:
        """
        Obtém os colaboradores do repositório.
        
        Returns:
            Lista de dicionários com informações dos colaboradores
        """
        if not self.enabled:
            log.warning("Tentativa de obter colaboradores com integração GitHub desabilitada")
            return []
            
        try:
            collaborators = self.repo.get_collaborators()
            result = []
            
            for collab in collaborators:
                result.append({
                    "login": collab.login,
                    "name": collab.name,
                    "email": collab.email,
                    "url": collab.html_url
                })
                
            return result
        except GithubException as e:
            log.error(f"Erro ao obter colaboradores do GitHub: {e}")
            return []
    
    def get_branch_info(self, branch_name: str = None) -> Optional[Dict[str, Any]]:
        """
        Obtém informações sobre uma branch específica ou a branch padrão.
        
        Args:
            branch_name: Nome da branch (se None, usa a branch padrão)
            
        Returns:
            Dicionário com informações da branch ou None se não encontrada
        """
        if not self.enabled:
            log.warning("Tentativa de obter informações de branch com integração GitHub desabilitada")
            return None
            
        try:
            if branch_name is None:
                branch_name = self.repo.default_branch
                
            branch = self.repo.get_branch(branch_name)
            return {
                "name": branch.name,
                "commit_sha": branch.commit.sha,
                "commit_message": branch.commit.commit.message,
                "protected": branch.protected
            }
        except GithubException as e:
            log.error(f"Erro ao obter informações da branch {branch_name}: {e}")
            return None
