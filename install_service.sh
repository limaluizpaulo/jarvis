#!/bin/bash

# Obter o diretório absoluto do script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Verify .env file exists
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    if [ -f "$SCRIPT_DIR/.env.example" ]; then
        echo "Creating .env file from example..."
        cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
        echo "Please edit $SCRIPT_DIR/.env with your API keys and configuration."
    else
        echo "Creating basic .env file..."
        cat > "$SCRIPT_DIR/.env" << EOF
# Configurações do Jarvis
OPENAI_API_KEY=
JARVIS_ASSISTANT_ID=
JARVIS_THREAD_ID=
EOF
        echo "Please edit $SCRIPT_DIR/.env with your API keys and configuration."
    fi
    # Não interromper a execução, só avisar
    echo "AVISO: O arquivo .env foi criado, mas você precisará configurá-lo manualmente antes de usar o Jarvis."
    echo "O serviço será instalado, mas não funcionará até que o arquivo .env seja preenchido."
fi

# Create a systemd service file for Jarvis
cat > jarvis.service << EOL
[Unit]
Description=Jarvis AI Assistant
After=network.target

[Service]
ExecStart=/bin/bash -c 'source $HOME/jarvis_env/bin/activate && python $SCRIPT_DIR/jarvis.py --text'
WorkingDirectory=$SCRIPT_DIR
EnvironmentFile=$SCRIPT_DIR/.env
Restart=on-failure
User=$USER

[Install]
WantedBy=multi-user.target
EOL

# Move service file to systemd directory
sudo mv jarvis.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start the service
sudo systemctl enable jarvis.service
sudo systemctl start jarvis.service

echo "Jarvis service installed and started."
echo "Check status with: sudo systemctl status jarvis.service"
echo "View logs with: journalctl -u jarvis.service -f"
echo ""
echo "Se precisar alterar as chaves de API ou outros parâmetros, edite esse arquivo."
