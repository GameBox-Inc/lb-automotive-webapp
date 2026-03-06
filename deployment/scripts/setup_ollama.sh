#!/bin/bash

# Wait for Ollama to start
echo "Waiting for Ollama to fully start..."
sleep 10

# Initialize SmolLM 135M model (Ultra-lightweight, ~270MB)
echo "Pulling SmolLM 135M model..."
docker exec lb-auto-ollama ollama pull smollm2:135m

# Verify installation
echo "Verifying model..."
docker exec lb-auto-ollama ollama list

echo "✅ Ollama setup complete! You can now use it locally via http://localhost:11434"
