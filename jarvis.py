#!/usr/bin/env python3
# filepath: /home/comunikime/code/jarvis/jarvis.py
"""
Módulo principal do Jarvis, integrando os componentes de áudio, OpenAI
e interface do usuário para criar um assistente de voz completo.
"""

import argparse
import os
import sys
import atexit
import traceback
from dotenv import load_dotenv

# Importações de módulos locais
from audio_handler import AudioHandler
from openai_client import OpenAIClient
from interface import JarvisInterface
from log_manager import LogManager

# Inicializa o logger global
log = LogManager().logger

def cleanup_resources():
    """Limpa recursos antes de encerrar o programa."""
    log.info("Realizando limpeza de recursos antes de encerrar")
    # Qualquer limpeza adicional pode ser adicionada aqui

def main():
    """Função principal do programa Jarvis."""
    # Registra função de limpeza para ser executada na saída
    atexit.register(cleanup_resources)
    
    log.info("Iniciando Jarvis - Assistente pessoal inteligente")
    
    parser = argparse.ArgumentParser(description="Jarvis - Assistente pessoal inteligente")
    parser.add_argument("--text", action="store_true", help="Executar em modo somente texto (sem saída de voz)")
    parser.add_argument("--image", type=str, help="Caminho para uma imagem para análise")
    parser.add_argument("--debug", action="store_true", help="Ativar modo de depuração com logs detalhados")
    args = parser.parse_args()
    
    # Configurar nível de log com base nos argumentos
    if args.debug:
        LogManager(console_level=logging.DEBUG)
        log.info("Modo de depuração ativado")
    
    # Carregar variáveis de ambiente
    try:
        # Forçar uso de variáveis apenas do arquivo .env
        dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        if not os.path.exists(dotenv_path):
            log.critical("Arquivo .env não encontrado")
            raise ValueError("Arquivo .env não encontrado. Por favor, crie um arquivo .env com suas configurações.")
        
        log.debug(f"Carregando variáveis de ambiente de: {dotenv_path}")
        load_dotenv(dotenv_path=dotenv_path, override=True)  # override=True garante que as variáveis do .env tenham precedência
        
        # Verificar se as variáveis essenciais foram carregadas
        if not os.getenv("OPENAI_API_KEY"):
            log.critical("OPENAI_API_KEY não definida no arquivo .env")
            raise ValueError("OPENAI_API_KEY não foi definida no arquivo .env. Configure essa variável no arquivo .env.")
    except ImportError as e:
        log.critical(f"Erro ao importar python-dotenv: {e}")
        log.error("Erro: python-dotenv não está instalado. Execute: pip install python-dotenv")
        sys.exit(1)
    
    try:
        # Inicializar cliente OpenAI
        log.debug("Inicializando cliente OpenAI")
        openai_client = OpenAIClient()
        
        # Inicializar manipulador de áudio
        log.debug("Inicializando manipulador de áudio")
        audio_handler = AudioHandler(openai_client.get_raw_client(), text_only=args.text)
        
        # Inicializar interface do usuário
        log.debug("Inicializando interface do usuário")
        interface = JarvisInterface(openai_client, audio_handler)
        
        log.info("Jarvis está pronto.")
        
        # Se uma imagem foi fornecida, analisar a imagem
        if args.image:
            log.info(f"Modo de análise de imagem: {args.image}")
            interface.analyze_image(args.image)
        else:
            # Iniciar conversa
            log.info(f"Iniciando conversa no modo: {'texto' if args.text else 'voz'}")
            interface.run_conversation(with_voice=not args.text)
            
    except ValueError as e:
        log.error(f"Erro de configuração: {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        log.info("Programa interrompido pelo usuário (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        log.critical(f"Erro inesperado: {str(e)}")
        log.debug(f"Detalhes do erro: {traceback.format_exc()}")
        sys.exit(1)
    finally:
        log.info("Programa encerrado")

if __name__ == "__main__":
    # Importa logging aqui para evitar erros circulares de importação
    import logging
    main()
