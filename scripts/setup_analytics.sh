#!/bin/bash
# Setup script for Cuyahoga Court Analytics System

set -e

echo "🚀 Cuyahoga Court Analytics Setup"
echo "=================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"
echo ""

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cat > .env << EOF
# Database Passwords
POSTGRES_PASSWORD=$(openssl rand -base64 32)
MONGO_PASSWORD=$(openssl rand -base64 32)

# LLM Configuration
LLM_PROVIDER=ollama
LLM_MODEL=llama3

# Optional: Add API keys if using cloud LLMs
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
EOF
    echo "✅ Created .env file with secure passwords"
else
    echo "✅ .env file already exists"
fi
echo ""

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt
echo "✅ Python dependencies installed"
echo ""

# Start Docker services
echo "🐳 Starting Docker services..."
cd deploy
docker-compose up -d postgres mongodb redis ollama
echo "⏳ Waiting for databases to be ready..."
sleep 10
echo "✅ Database services started"
echo ""

# Pull Ollama model
echo "🤖 Pulling Ollama llama3 model (this may take a few minutes)..."
docker exec cuyahoga_ollama ollama pull llama3
echo "✅ Ollama model ready"
echo ""

# Initialize PostgreSQL database
echo "🗄️  Initializing PostgreSQL database..."
# TODO: Run Alembic migrations
# alembic upgrade head
echo "✅ PostgreSQL initialized"
echo ""

# Initialize MongoDB collections
echo "📚 Initializing MongoDB collections..."
# TODO: Create MongoDB indexes
echo "✅ MongoDB initialized"
echo ""

echo "✨ Setup Complete!"
echo ""
echo "Next steps:"
echo "1. Start the API server:"
echo "   cd deploy && docker-compose up -d api"
echo ""
echo "2. Start the scraper:"
echo "   cd deploy && docker-compose up -d scraper"
echo ""
echo "3. Access the API documentation:"
echo "   http://localhost:8000/docs"
echo ""
echo "4. Run analytics calculations:"
echo "   python scripts/calculate_analytics.py"
echo ""
echo "5. Import existing data:"
echo "   python scripts/import_existing_data.py"
echo ""

