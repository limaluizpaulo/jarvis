#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

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

# Exibir informações do sistema
log_info "Configurando Jarvis no sistema: $(lsb_release -ds || cat /etc/*release | head -n1)"
log_info "Diretório atual: $(pwd)"

# Verificar se é necessário criar o ambiente virtual
if [ -d "jarvis_env" ]; then
    log_info "Ambiente virtual já existe. Deseja recriá-lo? (s/N):"
    read recreate_env
    if [[ "$recreate_env" == "s" || "$recreate_env" == "S" ]]; then
        log_info "Removendo ambiente virtual antigo..."
        rm -rf jarvis_env
        need_to_create_env=true
    else
        log_info "Mantendo ambiente virtual existente."
        need_to_create_env=false
    fi
else
    need_to_create_env=true
fi

# Atualizar pacotes do sistema
log_info "Atualizando pacotes do sistema..."
if ! sudo apt update && sudo apt install -y \
  python3 python3-pip python3-venv \
  portaudio19-dev libespeak-ng1 espeak-ng ffmpeg; then
    log_error "Falha ao instalar dependências do sistema. Verifique permissões e conexão."
    exit 1
fi

# Criar e ativar ambiente virtual
if [ "$need_to_create_env" = true ]; then
    log_info "Configurando ambiente virtual Python..."
    if ! python3 -m venv jarvis_env; then
        log_error "Falha ao criar ambiente virtual. Verifique a instalação do Python."
        exit 1
    fi
fi

# Ativar o ambiente virtual
source jarvis_env/bin/activate || {
    log_error "Falha ao ativar ambiente virtual."
    exit 1
}

# Verificar a ativação do ambiente
if [[ "$VIRTUAL_ENV" != *"jarvis_env"* ]]; then
    log_error "Ambiente virtual não ativado corretamente."
    exit 1
fi

# Instalar dependências Python
log_info "Instalando dependências Python..."
pip install --upgrade pip
pip install -q "openai==1.*" "SpeechRecognition==3.*" "requests" "pygame" "python-dotenv>=1.0.0" "coloredlogs"

# Criar diretórios de cache e logs
mkdir -p ~/.jarvis/cache ~/.jarvis/logs

# Verificar se já existe a API key
if [ -f ".env" ]; then
    if grep -q "OPENAI_API_KEY" .env; then
        log_info "API key encontrada no arquivo .env."
        source_key_from_env=true
    else
        source_key_from_env=false
    fi
else
    source_key_from_env=false
fi

# Prompt para a API key se não existir
if [ "$source_key_from_env" = false ]; then
    log_info "Por favor, insira sua chave de API OpenAI:"
    read -s api_key
    
    # Validar a API key (formato básico)
    if [[ ! $api_key =~ ^sk-[A-Za-z0-9]{32,}$ ]]; then
        log_error "Formato de API key inválido. Deve começar com 'sk-' seguido de pelo menos 32 caracteres alfanuméricos."
        log_info "Continuando, mas você pode precisar corrigir o arquivo .env manualmente."
    fi
    
    # Criar/atualizar arquivo .env
    if [ -f ".env" ]; then
        # Atualizar arquivo existente
        sed -i '/OPENAI_API_KEY/d' .env
        echo "OPENAI_API_KEY=\"$api_key\"" >> .env
    else
        # Criar novo arquivo
        cat > .env << EOF
# Configurações do Jarvis
OPENAI_API_KEY="$api_key"
# Descomente e configure estas linhas para manter o histórico de conversas
#JARVIS_ASSISTANT_ID=
#JARVIS_THREAD_ID=
EOF
    fi
    
    log_success "Arquivo .env criado/atualizado com sua API key."
fi

# Oferecer instalação do serviço
log_info "Deseja instalar o Jarvis como um serviço systemd? (s/N):"
read install_service
if [[ "$install_service" == "s" || "$install_service" == "S" ]]; then
    log_info "Executando script de instalação do serviço..."
    chmod +x ./install_service.sh
    ./install_service.sh
fi

log_success "Configuração concluída! Você pode executar o Jarvis com: python jarvis.py"
log_info "Para modo de texto apenas: python jarvis.py --text"
log_info "Para analisar uma imagem: python jarvis.py --image caminho/para/imagem.jpg"
log_info "Para modo de depuração: python jarvis.py --debug"
