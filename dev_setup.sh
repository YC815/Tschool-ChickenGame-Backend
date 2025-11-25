#!/bin/bash
# Development setup script for Chicken Game Backend

set -e

echo "🚀 Setting up Chicken Game Backend..."

# Check if uv is available
if command -v uv &> /dev/null; then
    echo "📦 Using uv for dependency management..."
    uv sync
else
    echo "📦 Using pip for dependency management..."

    # Check Python version
    echo "📦 Checking Python version..."
    python3 --version

    # Create virtual environment if not exists
    if [ ! -d ".venv" ]; then
        echo "📦 Creating virtual environment..."
        python3 -m venv .venv
    fi

    # Activate virtual environment
    echo "📦 Activating virtual environment..."
    source .venv/bin/activate

    # Install dependencies
    echo "📦 Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
fi

# Copy .env if not exists
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env and configure your DATABASE_URL"
fi

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your database configuration"
echo "2. Start PostgreSQL"
echo "3. Run: python main.py"
echo ""
echo "API docs will be available at: http://localhost:8000/docs"
