#!/bin/bash

# Verify .env file exists
if [ ! -f "$HOME/jarvis/.env" ]; then
    if [ -f "$HOME/jarvis/.env.example" ]; then
        echo "Creating .env file from example..."
        cp "$HOME/jarvis/.env.example" "$HOME/jarvis/.env"
        echo "Please edit $HOME/jarvis/.env with your API keys and configuration."
    else
        echo "Creating basic .env file..."
        cat > "$HOME/jarvis/.env" << EOF
# Configurações do Jarvis
OPENAI_API_KEY=
JARVIS_ASSISTANT_ID=
JARVIS_THREAD_ID=
EOF
        echo "Please edit $HOME/jarvis/.env with your API keys and configuration."
    fi
    exit 1
fi

# Create a systemd service file for Jarvis
cat > jarvis.service << EOL
[Unit]
Description=Jarvis AI Assistant
After=network.target

[Service]
ExecStart=/bin/bash -c 'source $HOME/jarvis_env/bin/activate && python $HOME/jarvis/jarvis.py --text'
WorkingDirectory=$HOME/jarvis
EnvironmentFile=$HOME/jarvis/.env
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
echo "Nota: A configuração foi movida para o arquivo .env em $HOME/jarvis/.env"
echo "Se precisar alterar as chaves de API ou outros parâmetros, edite esse arquivo."
