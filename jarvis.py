#!/usr/bin/env python3
# filepath: /home/comunikime/code/jarvis/jarvis.py
"""
Módulo principal do Jarvis, integrando os componentes de áudio, OpenAI
e interface do usuário para criar um assistente de voz completo.
"""

import argparse
import os
import sys
from dotenv import load_dotenv

# Importações de módulos locais
from audio_handler import AudioHandler
from openai_client import OpenAIClient
from interface import JarvisInterface

def main():
    """Função principal do programa Jarvis."""
    parser = argparse.ArgumentParser(description="Jarvis - Assistente pessoal inteligente")
    parser.add_argument("--text", action="store_true", help="Executar em modo somente texto (sem saída de voz)")
    parser.add_argument("--image", type=str, help="Caminho para uma imagem para análise")
    args = parser.parse_args()
    
    # Carregar variáveis de ambiente
    try:
        # Forçar uso de variáveis apenas do arquivo .env
        dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        if not os.path.exists(dotenv_path):
            raise ValueError("Arquivo .env não encontrado. Por favor, crie um arquivo .env com suas configurações.")
        
        load_dotenv(dotenv_path=dotenv_path, override=True)  # override=True garante que as variáveis do .env tenham precedência
        
        # Verificar se as variáveis essenciais foram carregadas
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY não foi definida no arquivo .env. Configure essa variável no arquivo .env.")
    except ImportError:
        print("Erro: python-dotenv não está instalado. Execute: pip install python-dotenv")
        sys.exit(1)
    
    try:
        # Inicializar cliente OpenAI
        openai_client = OpenAIClient()
        
        # Inicializar manipulador de áudio
        audio_handler = AudioHandler(openai_client.get_raw_client(), text_only=args.text)
        
        # Inicializar interface do usuário
        interface = JarvisInterface(openai_client, audio_handler)
        
        print("Jarvis está pronto.")
        
        # Se uma imagem foi fornecida, analisar a imagem
        if args.image:
            interface.analyze_image(args.image)
        else:
            # Iniciar conversa
            interface.run_conversation(with_voice=not args.text)
            
    except ValueError as e:
        print(f"Erro: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"Erro inesperado: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
