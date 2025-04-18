#!/bin/bash

# Create a systemd service file for Jarvis
cat > jarvis.service << EOL
[Unit]
Description=Jarvis AI Assistant
After=network.target

[Service]
ExecStart=/bin/bash -c 'source $HOME/jarvis_env/bin/activate && python $HOME/jarvis/jarvis_with_functions.py'
WorkingDirectory=$HOME/jarvis
Environment=OPENAI_API_KEY=${OPENAI_API_KEY}
Environment=JARVIS_ASSISTANT_ID=${JARVIS_ASSISTANT_ID}
Environment=JARVIS_THREAD_ID=${JARVIS_THREAD_ID}
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
