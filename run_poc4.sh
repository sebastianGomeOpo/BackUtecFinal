#!/bin/bash

echo "🚀 Launching POC 4: Gemini Video Sales Agent with FastRTC"
echo "=========================================================="
echo ""
echo "📋 Prerequisites:"
echo "  ✓ Python 3.13"
echo "  ✓ Virtual environment activated"
echo "  ✓ All dependencies installed"
echo ""
echo "🌐 Server will be available at:"
echo "  👉 http://localhost:7860"
echo ""
echo "💡 Tip: Make sure MongoDB and Pinecone are accessible"
echo ""

cd "$(dirname "$0")"
source venv/bin/activate
python gradio_gemini_app.py

