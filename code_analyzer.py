#!/usr/bin/env python3
"""
Módulo para análise de código que identifica estruturas como funções e classes em arquivos Python.
Utiliza a biblioteca ast (Abstract Syntax Trees) para analisar a estrutura do código.
"""

import os
import ast
import hashlib
import json
import traceback
from functools import lru_cache
from typing import Dict, List, Tuple, Generator, Optional
from log_manager import LogManager

# Tenta importar o cache_manager se disponível no projeto
try:
    from cache_manager import CacheManager
    _has_cache_manager = True
except ImportError:
    _has_cache_manager = False

# Inicializa o logger
log = LogManager().logger

class CodeAnalyzer(ast.NodeVisitor):
    """
    Visitor de AST (Abstract Syntax Tree) que identifica funções e classes em código Python.
    Estende ast.NodeVisitor para percorrer a árvore de sintaxe.
    """
    def __init__(self):
        self.functions = []
        self.classes = []
        self.imports = []
        self.file_path = ""

    def visit_FunctionDef(self, node):
        """Registra definições de funções encontradas no código."""
        function_info = {
            "name": node.name,
            "lineno": node.lineno,
            "args": [arg.arg for arg in node.args.args],
            "docstring": ast.get_docstring(node)
        }
        self.functions.append(function_info)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        """Registra definições de classes encontradas no código."""
        class_info = {
            "name": node.name,
            "lineno": node.lineno,
            "bases": [self._get_base_name(base) for base in node.bases],
            "methods": [],
            "docstring": ast.get_docstring(node)
        }
        
        # Coletar métodos da classe
        original_functions = self.functions.copy()
        self.functions = []
        
        # Visitar os nós filhos para encontrar métodos
        for child in node.body:
            if isinstance(child, ast.FunctionDef):
                self.visit(child)
        
        # Adicionar métodos encontrados à classe
        class_info["methods"] = self.functions
        self.functions = original_functions
        
        self.classes.append(class_info)
        
    def visit_Import(self, node):
        """Registra importações simples."""
        for name in node.names:
            self.imports.append({"type": "import", "name": name.name, "asname": name.asname})
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node):
        """Registra importações do tipo 'from ... import ...'."""
        module = node.module
        for name in node.names:
            self.imports.append({
                "type": "importfrom", 
                "module": module, 
                "name": name.name, 
                "asname": name.asname
            })
        self.generic_visit(node)
        
    def _get_base_name(self, node):
        """Extrai o nome da classe base de um nó AST."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            # Para lidar com herança do tipo module.Class
            return f"{self._get_base_name(node.value)}.{node.attr}"
        return "unknown"

def analyze_file(file_path: str) -> Optional[CodeAnalyzer]:
    """
    Analisa um único arquivo Python e retorna os resultados.
    
    Args:
        file_path: Caminho para o arquivo Python a ser analisado
        
    Returns:
        Um objeto CodeAnalyzer contendo as estruturas encontradas, ou None se ocorrer erro
    """
    try:
        if not os.path.isfile(file_path) or not file_path.endswith('.py'):
            log.warning(f"Arquivo inválido ou não é um arquivo Python: {file_path}")
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        tree = ast.parse(content, filename=file_path)
        analyzer = CodeAnalyzer()
        analyzer.file_path = file_path
        analyzer.visit(tree)
        
        log.debug(f"Analisado arquivo: {file_path} - " 
                 f"Encontradas {len(analyzer.functions)} funções e {len(analyzer.classes)} classes")
        
        return analyzer
        
    except SyntaxError as e:
        log.error(f"Erro de sintaxe ao analisar {file_path}: {str(e)}")
    except Exception as e:
        log.error(f"Erro ao analisar {file_path}: {str(e)}")
    
    return None

def analyze_code(directory: str) -> Generator[Tuple[List, List], None, None]:
    """
    Analisa todos os arquivos Python em um diretório e gera tuplas com as funções e classes encontradas.
    
    Args:
        directory: Caminho para o diretório contendo os arquivos Python
        
    Yields:
        Tuplas (functions, classes) para cada arquivo analisado
    """
    if not os.path.isdir(directory):
        log.error(f"Diretório não encontrado: {directory}")
        return

    log.info(f"Analisando arquivos Python em: {directory}")
    
    for file in os.listdir(directory):
        if file.endswith(".py"):
            file_path = os.path.join(directory, file)
            analyzer = analyze_file(file_path)
            
            if analyzer:
                yield analyzer.functions, analyzer.classes

def analyze_project(project_dir: str) -> Dict:
    """
    Analisa todos os arquivos Python de um projeto e retorna um dicionário
    com as informações estruturadas sobre funções, classes e importações.
    
    Args:
        project_dir: Diretório raiz do projeto
        
    Returns:
        Dicionário com os resultados da análise
    """
    result = {
        "files": {},
        "summary": {
            "total_files": 0,
            "total_functions": 0,
            "total_classes": 0,
            "total_imports": 0
        }
    }
    
    if not os.path.isdir(project_dir):
        log.error(f"Diretório do projeto não encontrado: {project_dir}")
        return result
    
    # Encontra todos os arquivos Python recursivamente
    python_files = []
    for root, _, files in os.walk(project_dir):
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    # Analisa cada arquivo
    for file_path in python_files:
        analyzer = analyze_file(file_path)
        if analyzer:
            rel_path = os.path.relpath(file_path, project_dir)
            result["files"][rel_path] = {
                "functions": analyzer.functions,
                "classes": analyzer.classes,
                "imports": analyzer.imports
            }
            
            # Atualiza o resumo
            result["summary"]["total_files"] += 1
            result["summary"]["total_functions"] += len(analyzer.functions)
            result["summary"]["total_classes"] += len(analyzer.classes)
            result["summary"]["total_imports"] += len(analyzer.imports)
    
    log.info(f"Análise de projeto concluída: {result['summary']['total_files']} arquivos analisados")
    return result

# ----- Funções de cache para análise de código -----

@lru_cache(maxsize=32)
def cached_analyze_code(directory: str) -> List[Tuple[List, List]]:
    """
    Função em cache para analisar todos os arquivos Python em um diretório.
    Utiliza lru_cache para armazenar os resultados de análises anteriores.
    
    Args:
        directory: Caminho para o diretório contendo os arquivos Python
        
    Returns:
        Lista com as tuplas (functions, classes) para cada arquivo analisado
    """
    log.debug(f"Realizando análise com cache para: {directory}")
    analysis_results = list(analyze_code(directory))
    return analysis_results

def _generate_cache_key(directory: str) -> str:
    """
    Gera uma chave de cache única baseada no diretório e na data de modificação
    dos arquivos Python dentro dele.
    
    Args:
        directory: Caminho para o diretório contendo os arquivos Python
        
    Returns:
        String hash que representa o estado atual dos arquivos Python no diretório
    """
    if not os.path.isdir(directory):
        return hashlib.md5(directory.encode()).hexdigest()
    
    # Coleta informações sobre todos os arquivos Python no diretório
    files_info = []
    for root, _, files in os.walk(directory):
        for file in sorted(files):
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    mtime = os.path.getmtime(file_path)
                    size = os.path.getsize(file_path)
                    files_info.append(f"{file_path}:{mtime}:{size}")
                except OSError:
                    # Se não conseguir ler o arquivo, apenas use o caminho
                    files_info.append(file_path)
    
    # Gera um hash a partir das informações coletadas
    hash_input = directory + "|" + "|".join(files_info)
    return hashlib.md5(hash_input.encode()).hexdigest()

def persistent_cached_analyze_code(directory: str) -> Dict:
    """
    Função que utiliza o CacheManager do projeto para armazenar persistentemente
    os resultados de análise de código entre execuções.
    
    Args:
        directory: Caminho para o diretório contendo os arquivos Python
        
    Returns:
        Dicionário com os resultados completos da análise de projeto
    """
    # Se não temos o CacheManager, executa a análise diretamente
    if not _has_cache_manager:
        log.debug("CacheManager não disponível, executando análise sem cache persistente")
        return analyze_project(directory)
    
    # Gera chave de cache baseada no estado atual dos arquivos
    cache_key = _generate_cache_key(directory)
    
    # Criar um subdiretório específico para análise de código
    cache_dir = os.path.expanduser("~/.jarvis/cache/code_analysis")
    cache = CacheManager(cache_dir=cache_dir)
    
    # Tenta obter resultado do cache
    cached_result = cache.get(cache_key)
    if cached_result:
        log.info(f"Usando resultados em cache para análise de: {directory}")
        return cached_result
    
    # Executa a análise e armazena no cache
    log.info(f"Cache não encontrado, realizando nova análise para: {directory}")
    result = analyze_project(directory)
    
    # Salva no cache
    cache.set(cache_key, result)
    
    return result

def get_project_analysis(directory: str, use_persistent_cache: bool = True) -> Dict:
    """
    Função unificada para obter análise de um projeto, com suporte a diferentes
    mecanismos de cache.
    
    Args:
        directory: Caminho para o diretório do projeto
        use_persistent_cache: Se True, usa cache persistente; caso contrário, usa lru_cache
        
    Returns:
        Dicionário com os resultados da análise
    """
    if use_persistent_cache:
        return persistent_cached_analyze_code(directory)
    else:
        # Converte os resultados de cached_analyze_code para o mesmo formato de analyze_project
        results = cached_analyze_code(directory)
        
        # Estrutura o resultado no formato esperado
        formatted_result = {
            "files": {},
            "summary": {
                "total_files": len(results),
                "total_functions": sum(len(functions) for functions, _ in results),
                "total_classes": sum(len(classes) for _, classes in results),
                "total_imports": 0  # Não temos essa informação no formato simples
            }
        }
        
        return formatted_result

if __name__ == "__main__":
    # Exemplo de uso como script independente
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Uso: python code_analyzer.py <caminho_do_projeto> [--use-cache] [--export-json]")
        sys.exit(1)
    
    project_path = sys.argv[1]
    use_cache = "--use-cache" in sys.argv
    
    # Verifica se já temos o sistema de cache completamente definido
    if use_cache and 'get_project_analysis' in globals():
        print("Usando cache para análise")
        results = get_project_analysis(project_path)
    else:
        if use_cache:
            print("Sistema de cache solicitado mas não disponível, executando análise normal")
        else:
            print("Executando análise sem cache")
        results = analyze_project(project_path)
    
    # Imprimir resumo
    print(f"\nResumo da análise:")
    print(f"Arquivos analisados: {results['summary']['total_files']}")
    print(f"Total de funções: {results['summary']['total_functions']}")
    print(f"Total de classes: {results['summary']['total_classes']}")
    print(f"Total de importações: {results['summary']['total_imports']}")
    
    # Opcional: exportar resultados completos para JSON
    if "--export-json" in sys.argv:
        output_file = "code_analysis.json"
        print(f"Exportando resultados para {output_file}")
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)

# ----- Funções para formatação e geração de prompts -----

def format_function_info(function_info: Dict, max_docstring_length: int = None) -> str:
    """
    Formata as informações de uma função para apresentação em prompts.
    
    Args:
        function_info: Dicionário com informações da função
        max_docstring_length: Comprimento máximo permitido para a docstring
        
    Returns:
        String formatada com informações da função
    """
    args_str = ", ".join(function_info["args"]) if function_info["args"] else "sem argumentos"
    
    # Tratar a docstring, possivelmente truncando-a
    docstring = function_info.get("docstring", "")
    if docstring and max_docstring_length and len(docstring) > max_docstring_length:
        docstring = docstring[:max_docstring_length] + "..."
    
    docstring_str = f" - {docstring}" if docstring else ""
    
    # Incluir caminho do arquivo apenas se estiver disponível e for relevante
    file_info = ""
    if function_info.get("_file"):
        file_path = function_info["_file"]
        # Extrair apenas o nome do arquivo para economizar tokens
        file_name = os.path.basename(file_path)
        file_info = f" [arquivo: {file_name}]"
    
    return f"função {function_info['name']}({args_str}){file_info}{docstring_str}"

def format_class_info(class_info: Dict) -> str:
    """
    Formata as informações de uma classe para apresentação em prompts.
    
    Args:
        class_info: Dicionário com informações da classe
        
    Returns:
        String formatada com informações da classe
    """
    bases = ", ".join(class_info["bases"]) if class_info["bases"] else "sem herança"
    methods = [f"{m['name']}({', '.join(m['args'])})" for m in class_info.get("methods", [])]
    methods_str = f" com métodos: {', '.join(methods)}" if methods else ""
    docstring = f" - {class_info['docstring']}" if class_info.get("docstring") else ""
    
    return f"classe {class_info['name']}({bases}){methods_str}{docstring}"

def format_imports_info(imports: List[Dict]) -> str:
    """
    Formata as informações de importações para apresentação em prompts.
    
    Args:
        imports: Lista de dicionários com informações de importações
        
    Returns:
        String formatada com informações das importações
    """
    import_lines = []
    for imp in imports:
        if imp["type"] == "import":
            if imp["asname"]:
                import_lines.append(f"import {imp['name']} as {imp['asname']}")
            else:
                import_lines.append(f"import {imp['name']}")
        else:  # importfrom
            if imp["asname"]:
                import_lines.append(f"from {imp['module']} import {imp['name']} as {imp['asname']}")
            else:
                import_lines.append(f"from {imp['module']} import {imp['name']}")
    
    return "\n".join(import_lines)

def generate_file_context(analyzer: CodeAnalyzer, detailed: bool = False) -> str:
    """
    Gera um contexto textual a partir da análise de um arquivo.
    
    Args:
        analyzer: Instância de CodeAnalyzer com os resultados da análise
        detailed: Se True, inclui informações detalhadas
        
    Returns:
        String formatada com o contexto do arquivo
    """
    file_name = os.path.basename(analyzer.file_path)
    
    if not detailed:
        func_names = [f["name"] for f in analyzer.functions]
        class_names = [c["name"] for c in analyzer.classes]
        return f"Arquivo {file_name}: Funções: {', '.join(func_names) if func_names else 'nenhuma'}. " \
               f"Classes: {', '.join(class_names) if class_names else 'nenhuma'}."
    
    # Versão detalhada
    parts = [f"Arquivo: {file_name}"]
    
    # Adiciona imports
    if analyzer.imports:
        parts.append("Importações:")
        parts.append(format_imports_info(analyzer.imports))
    
    # Adiciona classes
    if analyzer.classes:
        parts.append("Classes:")
        for class_info in analyzer.classes:
            parts.append(f"- {format_class_info(class_info)}")
    
    # Adiciona funções (apenas as de nível superior)
    top_level_functions = [f for f in analyzer.functions if not any(
        f["name"] in [m["name"] for m in c.get("methods", [])] for c in analyzer.classes
    )]
    
    if top_level_functions:
        parts.append("Funções:")
        for func_info in top_level_functions:
            parts.append(f"- {format_function_info(func_info)}")
    
    return "\n".join(parts)

def generate_project_context(analysis_results: Dict, max_files: int = None) -> str:
    """
    Gera um contexto textual a partir da análise completa do projeto.
    
    Args:
        analysis_results: Resultados da análise de projeto
        max_files: Número máximo de arquivos a incluir (None = todos)
        
    Returns:
        String formatada com o contexto do projeto
    """
    summary = analysis_results["summary"]
    parts = [
        f"Projeto com {summary['total_files']} arquivos Python, " 
        f"contendo {summary['total_classes']} classes, "
        f"{summary['total_functions']} funções e {summary['total_imports']} importações."
    ]
    
    files = list(analysis_results["files"].items())
    if max_files and len(files) > max_files:
        files = sorted(files, key=lambda x: len(x[1]["classes"]) + len(x[1]["functions"]), reverse=True)[:max_files]
        parts.append(f"Mostrando os {max_files} arquivos mais relevantes:")
    
    for file_path, file_data in files:
        class_names = [c["name"] for c in file_data["classes"]]
        func_names = [f["name"] for f in file_data["functions"]]
        parts.append(
            f"- {file_path}: "
            f"{len(class_names)} classes ({', '.join(class_names) if len(class_names) <= 5 else f'{", ".join(class_names[:5])}...'}) e "
            f"{len(func_names)} funções ({', '.join(func_names) if len(func_names) <= 5 else f'{", ".join(func_names[:5])}...'})"
        )
    
    return "\n".join(parts)

def generate_prompt_for_openai(functions, classes, user_question):
    """
    Gera um prompt formatado para ser enviado à API OpenAI baseado nos resultados da análise.
    Otimizado para reduzir o consumo de tokens.
    
    Args:
        functions: Lista de funções encontradas na análise
        classes: Lista de classes encontradas na análise
        user_question: Pergunta do usuário
        
    Returns:
        String formatada como prompt para a API OpenAI
    """
    # Limitar número máximo de funções e classes para economizar tokens
    max_functions = 5  # Reduzido de 10 para 5
    max_classes = 3    # Reduzido de 5 para 3
    
    # Cálculo aproximado de tokens (4 caracteres ~ 1 token)
    token_budget = 4000  # Budget máximo de tokens para o contexto
    token_estimate = len(user_question) // 4  # Estimativa para a pergunta
    
    # Truncar para os limites estabelecidos
    functions = functions[:max_functions]
    classes = classes[:max_classes]
    
    # Formatar funções com limite de caracteres
    func_info = []
    for func in functions:
        if isinstance(func, dict):
            # Limitar descrição de funções
            func_formatted = format_function_info(func, max_docstring_length=150)
            func_info.append(func_formatted)
            token_estimate += len(func_formatted) // 4
        else:
            func_info.append(str(func)[:200])  # Limitar tamanho da string
            token_estimate += 50  # Estimativa conservadora
    
    # Formatar classes com limite de caracteres
    class_info = []
    for cls in classes:
        if isinstance(cls, dict):
            # Limitar descrição de classes
            cls_formatted = format_class_info(cls, max_docstring_length=150)
            class_info.append(cls_formatted)
            token_estimate += len(cls_formatted) // 4
        else:
            class_info.append(str(cls)[:200])  # Limitar tamanho da string
            token_estimate += 50  # Estimativa conservadora
    
    # Verificar se estamos dentro do orçamento de tokens
    log.info(f"Estimativa de tokens para o contexto: {token_estimate}")
    
    # Gerar contexto com base no orçamento de tokens
    if token_estimate > token_budget:
        log.warning(f"Estimativa de tokens ({token_estimate}) excede o orçamento ({token_budget})")
        # Reduzir ainda mais para caber no orçamento
        func_info = func_info[:3]  # Apenas 3 funções mais relevantes
        class_info = class_info[:2]  # Apenas 2 classes mais relevantes
        log.info(f"Contexto reduzido para {len(func_info)} funções e {len(class_info)} classes")
    
    # Gerar contexto
    code_context = "Contexto do código:\n"
    
    if func_info:
        code_context += f"Funções encontradas:\n- " + "\n- ".join(func_info) + "\n\n"
    else:
        code_context += "Nenhuma função encontrada.\n\n"
        
    if class_info:
        code_context += f"Classes encontradas:\n- " + "\n- ".join(class_info) + "\n\n"
    else:
        code_context += "Nenhuma classe encontrada.\n\n"
    
    # Montar prompt completo
    prompt = f"{code_context}Pergunta do usuário: {user_question}\n\n"
    prompt += "Por favor, responda à pergunta do usuário com base no contexto do código fornecido."
    
    # Estimativa final de tokens
    final_token_estimate = len(prompt) // 4
    log.info(f"Estimativa final de tokens para o prompt: {final_token_estimate}")
    
    return prompt

def generate_code_summary(analyzer: CodeAnalyzer) -> str:
    """
    Gera um resumo conciso do código analisado, ideal para inclusão em prompts.
    
    Args:
        analyzer: Instância de CodeAnalyzer com os resultados da análise
        
    Returns:
        String com um resumo do código
    """
    file_name = os.path.basename(analyzer.file_path)
    
    # Identificar propósito do arquivo a partir de imports e classes
    purpose = ""
    if any("flask" in imp["name"].lower() for imp in analyzer.imports):
        purpose = "API web Flask"
    elif any("django" in imp["name"].lower() for imp in analyzer.imports):
        purpose = "aplicação Django"
    elif any("unittest" in imp["name"].lower() for imp in analyzer.imports):
        purpose = "testes unitários"
    elif any("pandas" in imp["name"].lower() for imp in analyzer.imports):
        purpose = "análise de dados"
    elif any("tensorflow" in imp["name"].lower() or "torch" in imp["name"].lower() for imp in analyzer.imports):
        purpose = "machine learning"
    
    # Resumir principais funcionalidades
    class_count = len(analyzer.classes)
    function_count = len(analyzer.functions)
    top_level_functions = [f for f in analyzer.functions if not any(
        f["name"] in [m["name"] for m in c.get("methods", [])] for c in analyzer.classes
    )]
    
    summary = f"Arquivo {file_name}"
    if purpose:
        summary += f" parece ser parte de {purpose}"
    
    summary += f", contém {class_count} classes e {function_count} funções"
    
    if class_count > 0:
        main_classes = sorted(analyzer.classes, key=lambda c: len(c.get("methods", [])), reverse=True)[:2]
        class_names = [c["name"] for c in main_classes]
        summary += f". Classes principais: {', '.join(class_names)}"
    
    if top_level_functions:
        func_names = [f["name"] for f in top_level_functions[:3]]
        summary += f". Funções principais: {', '.join(func_names)}"
        
        if len(top_level_functions) > 3:
            summary += f" e mais {len(top_level_functions) - 3} outras"
    
    return summary

# ----- Funções de integração com OpenAI -----

def process_query_with_context(directory: str, user_question: str, openai_client=None, use_cache: bool = True) -> str:
    """
    Processa uma consulta do usuário com contexto de código extraído do diretório especificado,
    aproveitando o sistema de cache para análises repetidas.
    
    Args:
        directory: Caminho para o diretório contendo o código a ser analisado
        user_question: Pergunta ou consulta do usuário sobre o código
        openai_client: Instância do cliente OpenAI. Se None, apenas retorna o prompt
        use_cache: Se True, usa o sistema de cache para análises repetidas
        
    Returns:
        Resposta do OpenAI ou o prompt formatado se openai_client for None
    """
    log.info(f"Processando consulta com contexto de código de: {directory}")
    
    try:
        # Determinar o método de análise com base na flag use_cache
        if use_cache:
            log.debug("Usando análise em cache")
            analysis = get_project_analysis(directory)
            
            # Extrair funções e classes do resultado da análise
            all_functions = []
            all_classes = []
            
            # Pega as 5 funções e 5 classes mais relevantes para o prompt
            # Ordenamos por comprimento de docstring como heurística de relevância
            sorted_files = []
            for file_path, file_data in analysis["files"].items():
                # Calculamos um score baseado em docstrings e número de argumentos
                for func in file_data["functions"]:
                    docstring = func.get("docstring") or ""
                    args = func.get("args") or []
                    func["_relevance"] = len(docstring) + len(args)
                    func["_file"] = file_path
                
                for cls in file_data["classes"]:
                    docstring = cls.get("docstring") or ""
                    methods = cls.get("methods") or []
                    func["_relevance"] = len(docstring) + len(methods)
                    cls["_file"] = file_path
                
                sorted_files.append((file_path, file_data))
            
            # Ordenar por relevância
            sorted_functions = []
            sorted_classes = []
            
            for _, file_data in sorted_files:
                sorted_functions.extend(file_data["functions"])
                sorted_classes.extend(file_data["classes"])
            
            # Ordenar e selecionar as mais relevantes
            sorted_functions.sort(key=lambda x: x.get("_relevance", 0), reverse=True)
            sorted_classes.sort(key=lambda x: x.get("_relevance", 0), reverse=True)
            
            # Limitar o número de funções e classes para não sobrecarregar o contexto
            all_functions = sorted_functions[:10]  # Pegamos as 10 mais relevantes
            all_classes = sorted_classes[:5]       # Pegamos as 5 mais relevantes
        else:
            # Usar a análise básica sem cache persistente
            log.debug("Realizando análise direta sem cache persistente")
            analysis_results = list(analyze_code(directory))
            all_functions = []
            all_classes = []
            
            # Combinamos os resultados de todos os arquivos
            for functions, classes in analysis_results:
                all_functions.extend(functions)
                all_classes.extend(classes)
        
        # Gera o prompt para o OpenAI usando as funções e classes encontradas
        log.debug(f"Gerando prompt com {len(all_functions)} funções e {len(all_classes)} classes")
        prompt = generate_prompt_for_openai(all_functions, all_classes, user_question)
        
        # Registra informações detalhadas sobre o que está sendo enviado
        log.info("=== DETALHES DO CONTEXTO ENVIADO PARA OPENAI ===")
        log.info(f"Pergunta do usuário: {user_question}")
        log.info(f"Total de arquivos analisados: {len(analysis['files']) if use_cache else 'N/A'}")
        log.info(f"Total de funções incluídas no contexto: {len(all_functions)}")
        log.info(f"Total de classes incluídas no contexto: {len(all_classes)}")
        
        # Detalhes sobre as funções mais relevantes no contexto
        if all_functions:
            log.info("Funções mais relevantes incluídas:")
            for i, func in enumerate(all_functions[:5], 1):  # Mostrar apenas as 5 primeiras
                fname = func.get("name", "Sem nome")
                ffile = func.get("_file", "Arquivo desconhecido")
                fdoc = func.get("docstring", "")
                fdoc_preview = fdoc[:50] + "..." if fdoc and len(fdoc) > 50 else fdoc
                log.info(f"  {i}. {fname} - Arquivo: {os.path.basename(ffile)} - Doc: {fdoc_preview}")
        
        # Detalhes sobre as classes mais relevantes no contexto
        if all_classes:
            log.info("Classes mais relevantes incluídas:")
            for i, cls in enumerate(all_classes[:3], 1):  # Mostrar apenas as 3 primeiras
                cname = cls.get("name", "Sem nome")
                cfile = cls.get("_file", "Arquivo desconhecido")
                cdoc = cls.get("docstring", "")
                cdoc_preview = cdoc[:50] + "..." if cdoc and len(cdoc) > 50 else cdoc
                cmethods = len(cls.get("methods", []))
                log.info(f"  {i}. {cname} - Arquivo: {os.path.basename(cfile)} - Métodos: {cmethods} - Doc: {cdoc_preview}")
                
        # Registra o tamanho do prompt
        prompt_size = len(prompt)
        log.info(f"Tamanho total do prompt (caracteres): {prompt_size}")
        
        # Registra uma prévia do prompt
        preview_length = min(500, len(prompt))
        prompt_preview = prompt[:preview_length] + ("..." if len(prompt) > preview_length else "")
        log.info(f"Prévia do prompt:\n{prompt_preview}")
        log.info("=== FIM DOS DETALHES DE CONTEXTO ===")
        
        # Se o cliente OpenAI não foi fornecido, apenas retorna o prompt
        if openai_client is None:
            return prompt
            
        # Envia a consulta para o OpenAI
        log.info("Enviando prompt para o OpenAI")
        response = openai_client.send_message(prompt)
        return response
    
    except Exception as e:
        log.error(f"Erro ao processar consulta com contexto: {str(e)}")
        log.debug(f"Detalhes do erro: {traceback.format_exc()}")
        
        # Em caso de erro, tentamos enviar a pergunta sem contexto
        if openai_client is not None:
            log.info("Tentando enviar consulta sem contexto após erro")
            fallback_prompt = f"Pergunta do usuário (sem contexto de código): {user_question}"
            return openai_client.send_message(fallback_prompt)
        else:
            return f"Erro ao processar consulta: {str(e)}"

def analyze_and_respond_to_error(error_message: str, file_path: str, openai_client=None) -> str:
    """
    Analisa um arquivo de código e utiliza o contexto para gerar uma resposta
    específica para uma mensagem de erro.
    
    Args:
        error_message: Mensagem de erro a ser explicada
        file_path: Caminho para o arquivo com erro
        openai_client: Instância do cliente OpenAI. Se None, apenas retorna o prompt
        
    Returns:
        Explicação do erro baseada no contexto do código
    """
    log.info(f"Analisando erro no arquivo: {file_path}")
    
    try:
        # Analisar o arquivo com erro
        analyzer = analyze_file(file_path)
        if not analyzer:
            raise ValueError(f"Não foi possível analisar o arquivo: {file_path}")
        
        # Gerar contexto detalhado do arquivo
        file_context = generate_file_context(analyzer, detailed=True)
        
        # Criar prompt específico para análise de erro
        prompt = f"""
Contexto do código:
{file_context}

Erro encontrado:
{error_message}

Por favor, explique o que pode estar causando este erro no contexto do código mostrado acima,
e sugira possíveis soluções.
"""
        
        # Se o cliente OpenAI não foi fornecido, apenas retorna o prompt
        if openai_client is None:
            return prompt
            
        # Envia a consulta para o OpenAI
        log.info("Enviando análise de erro para o OpenAI")
        response = openai_client.send_message(prompt)
        return response
    
    except Exception as e:
        log.error(f"Erro ao analisar erro: {str(e)}")
        
        # Em caso de erro, tentamos enviar a pergunta sem contexto detalhado
        if openai_client is not None:
            fallback_prompt = f"Por favor, explique o seguinte erro:\n{error_message}"
            return openai_client.send_message(fallback_prompt)
        else:
            return f"Erro ao analisar o código para o erro: {str(e)}"

def extract_relevant_code_context(query: str, directory: str) -> str:
    """
    Extrai contexto de código relevante para uma consulta específica.
    Útil para criar prompts mais focados em partes específicas do código.
    
    Args:
        query: Consulta ou termo de pesquisa
        directory: Diretório de código para pesquisar
        
    Returns:
        Contexto de código relevante para a consulta
    """
    log.info(f"Extraindo contexto relevante para: '{query}'")
    
    # Usando o sistema de cache para a análise
    analysis = get_project_analysis(directory)
    
    # Palavras-chave da consulta (simplificado)
    keywords = set(query.lower().split())
    
    # Pontuação para cada arquivo baseada em correspondência de palavras-chave
    file_scores = {}
    
    # Analisar cada arquivo
    for file_path, file_data in analysis["files"].items():
        score = 0
        
        # Verificar funções
        for func in file_data["functions"]:
            func_text = func["name"].lower()
            if func.get("docstring"):
                func_text += " " + func["docstring"].lower()
            
            # Aumentar pontuação por palavra-chave encontrada
            for keyword in keywords:
                if keyword in func_text:
                    score += 3  # Peso maior para funções
        
        # Verificar classes
        for cls in file_data["classes"]:
            class_text = cls["name"].lower()
            if cls.get("docstring"):
                class_text += " " + cls["docstring"].lower()
            
            # Aumentar pontuação por palavra-chave encontrada
            for keyword in keywords:
                if keyword in class_text:
                    score += 5  # Peso maior para classes
        
        # Armazenar pontuação se for relevante
        if score > 0:
            file_scores[file_path] = score
    
    # Selecionar os arquivos mais relevantes (até 3)
    relevant_files = sorted(file_scores.items(), key=lambda x: x[1], reverse=True)[:3]
    
    # Gerar contexto para os arquivos relevantes
    context = []
    for file_path, _ in relevant_files:
        file_data = analysis["files"][file_path]
        context.append(f"\nArquivo: {file_path}")
        
        # Adicionar classes relevantes
        for cls in file_data["classes"]:
            class_text = cls["name"].lower()
            if any(keyword in class_text for keyword in keywords):
                context.append(format_class_info(cls))
        
        # Adicionar funções relevantes
        for func in file_data["functions"]:
            func_text = func["name"].lower()
            if any(keyword in func_text for keyword in keywords):
                context.append(format_function_info(func))
    
    if not context:
        return "Não foi encontrado contexto relevante para esta consulta."
    
    return "\n".join(context)
