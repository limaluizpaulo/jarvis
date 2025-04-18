# filepath: /home/comunikime/code/jarvis/log_manager.py
#!/usr/bin/env python3
"""
Módulo para gerenciamento de logs do Jarvis,
fornecendo registro estruturado das operações.
"""

import os
import sys
import logging
import logging.handlers
from datetime import datetime

class LogManager:
    """Gerencia logs do sistema Jarvis."""
    
    # Níveis de log personalizados
    API_CALL = 15  # Entre DEBUG e INFO
    USER_ACTION = 25  # Entre INFO e WARNING
    
    def __init__(self, log_dir=None, console_level=logging.INFO, file_level=logging.DEBUG):
        """
        Inicializa o gerenciador de logs.
        
        Args:
            log_dir: Diretório para armazenar logs
            console_level: Nível mínimo para exibir no console
            file_level: Nível mínimo para registrar em arquivo
        """
        # Configuração dos níveis personalizados
        logging.addLevelName(self.API_CALL, "API_CALL")
        logging.addLevelName(self.USER_ACTION, "USER_ACTION")
        
        # Cria o logger principal do Jarvis
        self.logger = logging.getLogger("jarvis")
        self.logger.setLevel(logging.DEBUG)  # Captura todos os níveis
        
        # Evita duplicação de handlers se o logger já estiver configurado
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        
        # Configura handler para console
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_format = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', 
                                          datefmt='%H:%M:%S')
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
        
        # Configura handler para arquivo se o diretório for especificado
        if not log_dir:
            log_dir = os.path.expanduser("~/.jarvis/logs")
        
        os.makedirs(log_dir, exist_ok=True)
        
        # Cria um novo arquivo de log para cada dia
        log_filename = os.path.join(log_dir, f"jarvis_{datetime.now().strftime('%Y-%m-%d')}.log")
        
        # Cria um manipulador que rotaciona os logs (mantém no máximo 30 dias de logs)
        file_handler = logging.handlers.TimedRotatingFileHandler(
            log_filename, 
            when='midnight',
            backupCount=30
        )
        file_handler.setLevel(file_level)
        file_format = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(module)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        self.logger.addHandler(file_handler)
    
    def api_call(self, msg, *args, **kwargs):
        """Registra uma chamada de API."""
        self.logger.log(self.API_CALL, msg, *args, **kwargs)
    
    def user_action(self, msg, *args, **kwargs):
        """Registra uma ação do usuário."""
        self.logger.log(self.USER_ACTION, msg, *args, **kwargs)
    
    def debug(self, msg, *args, **kwargs):
        """Registra mensagem de debug."""
        self.logger.debug(msg, *args, **kwargs)
    
    def info(self, msg, *args, **kwargs):
        """Registra mensagem informativa."""
        self.logger.info(msg, *args, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        """Registra mensagem de aviso."""
        self.logger.warning(msg, *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        """Registra mensagem de erro."""
        self.logger.error(msg, *args, **kwargs)
    
    def critical(self, msg, *args, **kwargs):
        """Registra mensagem crítica."""
        self.logger.critical(msg, *args, **kwargs)
    
    def exception(self, msg, *args, **kwargs):
        """Registra exceção incluindo stack trace."""
        self.logger.exception(msg, *args, **kwargs)
