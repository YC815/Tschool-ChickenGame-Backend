#!/bin/bash
# Quick development server start

echo "🚀 Starting Chicken Game Backend..."
echo "📍 API: http://localhost:8000"
echo "📖 Docs: http://localhost:8000/docs"
echo ""

if command -v uv &> /dev/null; then
    uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
else
    source .venv/bin/activate
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
fi
