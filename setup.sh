#!/bin/bash

# Update system packages
echo "Updating system packages..."
sudo apt update && sudo apt install -y \
  python3 python3-pip python3-venv \
  portaudio19-dev libespeak-ng1 espeak-ng ffmpeg

# Create and activate virtual environment
echo "Setting up Python virtual environment..."
python3 -m venv jarvis_env
source jarvis_env/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install "openai==1.*" "SpeechRecognition==3.*" requests pygame python-dotenv

# Prompt for OpenAI API key
echo "Please enter your OpenAI API key:"
read api_key

# Export API key to environment
export OPENAI_API_KEY="$api_key"

# Add to .bashrc for persistence
echo "Adding API key to .bashrc for persistence..."
echo "export OPENAI_API_KEY=\"$api_key\"" >> ~/.bashrc

echo "Setup complete! You can now run Jarvis with: python3 jarvis.py"
