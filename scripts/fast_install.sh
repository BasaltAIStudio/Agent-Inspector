#!/bin/bash
set -e

echo "🚀 Starting AgentInspector Fast Install..."

# 1. Virtual Env
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv .venv
fi

source .venv/bin/activate

# 2. Dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -e ".[dev,dashboard]"

# 3. Environment Variables
if [ -z "$DATABASE_URL" ]; then
    echo "⚠️  DATABASE_URL not set. Using default local postgres..."
    export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/agentinspector"
fi

if [ -z "$SECRET_KEY" ]; then
    echo "🔑 Generating secret key..."
    export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
fi

# 4. Database
echo "🗄️  Initializing database..."
alembic upgrade head

echo "✅ Setup complete!"
echo "👉 Run 'source .venv/bin/activate' and then 'agentinspector --help' to start."
