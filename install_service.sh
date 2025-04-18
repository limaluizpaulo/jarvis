#!/bin/bash
set -e  # Encerra o script se qualquer comando falhar

# Função para exibir mensagens formatadas
log_info() {
    echo -e "\e[1;34m[INFO]\e[0m $1"
}

log_error() {
    echo -e "\e[1;31m[ERROR]\e[0m $1" >&2
}

log_success() {
    echo -e "\e[1;32m[SUCCESS]\e[0m $1"
}

# Obter o diretório absoluto do script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

# Verificar se o script está sendo executado como root
if [[ $EUID -eq 0 ]]; then
    log_error "Este script não deve ser executado como root."
    log_info "Use: ./install_service.sh"
    exit 1
fi

# Verificar se o arquivo .env existe
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$SCRIPT_DIR/.env.example" ]; then
        log_info "Criando arquivo .env a partir do exemplo..."
        cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
        log_info "Por favor, edite $ENV_FILE com suas chaves de API e configurações."
    else
        log_info "Criando arquivo .env básico..."
        cat > "$ENV_FILE" << EOF
# Configurações do Jarvis
OPENAI_API_KEY=
JARVIS_ASSISTANT_ID=
JARVIS_THREAD_ID=
EOF
        log_info "Por favor, edite $ENV_FILE com suas chaves de API e configurações."
    fi
    # Não interromper a execução, só avisar
    log_info "AVISO: O arquivo .env foi criado, mas você precisará configurá-lo manualmente antes de usar o Jarvis."
    log_info "O serviço será instalado, mas não funcionará até que o arquivo .env seja preenchido."
fi

# Obter o caminho absoluto para o ambiente virtual
VENV_PATH="$SCRIPT_DIR/jarvis_env"
if [ ! -d "$VENV_PATH" ]; then
    log_error "Ambiente virtual não encontrado em $VENV_PATH."
    log_info "Execute primeiro o script setup.sh: ./setup.sh"
    exit 1
fi

# Verificar permissões de arquivos críticos
log_info "Verificando permissões dos arquivos..."
chmod +x "$SCRIPT_DIR/jarvis.py"

# Perguntar pelo modo de operação (texto ou voz)
log_info "Deseja que o Jarvis execute no modo de texto ou no modo de voz quando iniciar como serviço?"
log_info "1) Modo de texto (sem saída de voz, recomendado para servidores)"
log_info "2) Modo de voz (com saída de voz, recomendado para máquinas locais)"
read -p "Escolha uma opção (1/2, padrão: 1): " voice_mode

# Configurar o comando de execução com base na escolha
if [[ "$voice_mode" == "2" ]]; then
    EXEC_COMMAND="--debug"
    log_info "Configurando serviço para executar com saída de voz e logs detalhados."
else
    EXEC_COMMAND="--text --debug"
    log_info "Configurando serviço para executar em modo texto com logs detalhados."
fi

# Criar diretório de logs
mkdir -p ~/.jarvis/logs

# Criar arquivo de serviço systemd com configurações aprimoradas
log_info "Criando arquivo de serviço systemd..."
SYSTEMD_FILE="$SCRIPT_DIR/jarvis.service"

cat > "$SYSTEMD_FILE" << EOL
[Unit]
Description=Jarvis AI Assistant
Documentation=https://github.com/seu-usuario/jarvis
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/bin/bash -c 'source $VENV_PATH/bin/activate && python $SCRIPT_DIR/jarvis.py $EXEC_COMMAND'
WorkingDirectory=$SCRIPT_DIR
EnvironmentFile=$ENV_FILE
Restart=on-failure
RestartSec=10
StartLimitIntervalSec=60
StartLimitBurst=3
User=$USER
# Limites de recursos para evitar consumo excessivo
CPUQuota=50%
MemoryLimit=500M
# Configurações de segurança
ProtectSystem=full
PrivateTmp=true
NoNewPrivileges=true
# Opções para log
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOL

# Mover arquivo de serviço para o diretório do systemd
log_info "Instalando serviço systemd..."
if ! sudo mv "$SYSTEMD_FILE" /etc/systemd/system/; then
    log_error "Falha ao mover arquivo de serviço. Verifique suas permissões sudo."
    exit 1
fi

# Recarregar systemd
log_info "Recarregando configurações do systemd..."
if ! sudo systemctl daemon-reload; then
    log_error "Falha ao recarregar systemd."
    exit 1
fi

# Habilitar e iniciar o serviço
log_info "Habilitando o serviço para iniciar com o sistema..."
if ! sudo systemctl enable jarvis.service; then
    log_error "Falha ao habilitar o serviço."
    exit 1
fi

log_info "Iniciando o serviço Jarvis..."
if ! sudo systemctl start jarvis.service; then
    log_error "Falha ao iniciar o serviço."
    log_info "Verifique o status com: sudo systemctl status jarvis.service"
    log_info "E os logs com: sudo journalctl -u jarvis.service -f"
    exit 1
fi

# Verificar status do serviço
if sudo systemctl is-active --quiet jarvis.service; then
    log_success "Serviço Jarvis instalado e executando!"
else
    log_error "O serviço Jarvis foi instalado, mas não está executando."
    log_info "Verifique os logs para entender o problema: sudo journalctl -u jarvis.service -f"
    exit 1
fi

log_info "============================================================="
log_info "Status atual do serviço:"
sudo systemctl status jarvis.service --no-pager

log_info "============================================================="
log_success "Serviço Jarvis configurado com sucesso!"
log_info "Comandos úteis:"
log_info "  - Verificar status: sudo systemctl status jarvis.service"
log_info "  - Ver logs: sudo journalctl -u jarvis.service -f"
log_info "  - Reiniciar serviço: sudo systemctl restart jarvis.service"
log_info "  - Parar serviço: sudo systemctl stop jarvis.service"
log_info "  - Desabilitar na inicialização: sudo systemctl disable jarvis.service"
log_info "============================================================="
log_info "Logs detalhados estão disponíveis em: ~/.jarvis/logs/"
log_info "Se precisar ajustar configurações, edite o arquivo $ENV_FILE"
