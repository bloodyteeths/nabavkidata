# Development Guide

> Complete guide for setting up and developing nabavkidata.com

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Local Development](#local-development)
- [Code Style Guide](#code-style-guide)
- [Git Workflow](#git-workflow)
- [Testing Guidelines](#testing-guidelines)
- [Debugging Tips](#debugging-tips)
- [Common Issues](#common-issues)
- [Development Tools](#development-tools)

## Prerequisites

### Required Software

| Software | Minimum Version | Recommended | Installation |
|----------|----------------|-------------|--------------|
| **Python** | 3.11 | 3.11+ | https://www.python.org/downloads/ |
| **Node.js** | 18.x | 20.x LTS | https://nodejs.org/ |
| **PostgreSQL** | 16 | 16+ | https://www.postgresql.org/download/ |
| **Redis** | 7.0 | 7.2+ | https://redis.io/download |
| **Docker** | 20.10 | 24.0+ | https://docs.docker.com/get-docker/ |
| **Git** | 2.30 | Latest | https://git-scm.com/downloads |

### Optional but Recommended

- **VS Code** or **PyCharm** (IDE)
- **Postman** or **Insomnia** (API testing)
- **pgAdmin** or **DBeaver** (Database GUI)
- **Redis Commander** (Redis GUI)

### System Requirements

- **RAM**: 8GB minimum, 16GB recommended
- **Disk Space**: 10GB free space
- **OS**: macOS, Linux, or Windows 10/11 with WSL2

## Environment Setup

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/nabavkidata.git
cd nabavkidata
```

### 2. Set Up Environment Variables

Create `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```bash
# Database
DB_NAME=nabavkidata
DB_USER=dev
DB_PASSWORD=devpass
DB_HOST=localhost
DB_PORT=5432
DATABASE_URL=postgresql+asyncpg://dev:devpass@localhost:5432/nabavkidata

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET=your-secret-key-here-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OpenAI (Required for RAG)
OPENAI_API_KEY=sk-your-openai-key

# Gemini (Optional, fallback for RAG)
GEMINI_API_KEY=your-gemini-key

# Stripe (Optional for local dev)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_PRO=price_...
STRIPE_PRICE_PREMIUM=price_...

# Email (Optional for local dev)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=noreply@nabavkidata.com

# Application
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=debug
FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

### 3. Database Setup

**Option A: Using Docker** (Recommended)

```bash
# Start PostgreSQL with pgvector
docker-compose up -d postgres

# Wait for database to be ready
docker-compose logs -f postgres
# Look for: "database system is ready to accept connections"
```

**Option B: Local PostgreSQL Installation**

```bash
# Install pgvector extension
# macOS with Homebrew:
brew install pgvector

# Ubuntu/Debian:
sudo apt install postgresql-16-pgvector

# Create database
createdb nabavkidata

# Install extensions
psql nabavkidata -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql nabavkidata -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
psql nabavkidata -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"

# Load schema
psql nabavkidata < db/schema.sql
```

### 4. Redis Setup

**Option A: Using Docker** (Recommended)

```bash
docker-compose up -d redis
```

**Option B: Local Redis Installation**

```bash
# macOS with Homebrew:
brew install redis
brew services start redis

# Ubuntu/Debian:
sudo apt install redis-server
sudo systemctl start redis-server
```

## Local Development

### Backend Development

#### 1. Set Up Virtual Environment

```bash
cd backend

# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip
```

#### 2. Install Dependencies

```bash
# Install all dependencies
pip install -r requirements.txt

# For development, also install dev dependencies
pip install black flake8 mypy pytest pytest-cov pytest-asyncio
```

#### 3. Run Database Migrations

```bash
# Generate migration (after model changes)
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

#### 4. Run Backend Server

```bash
# Development server with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# With specific log level
uvicorn main:app --reload --log-level debug

# Access API docs
# Swagger UI: http://localhost:8000/api/docs
# ReDoc: http://localhost:8000/api/redoc
```

#### 5. Run Tests

```bash
# Run all tests
pytest

# With coverage report
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_tenders.py

# Run with verbose output
pytest -v

# Run only unit tests (not integration)
pytest -m "not integration"
```

### Frontend Development

#### 1. Install Dependencies

```bash
cd frontend

# Install packages
npm install

# Or with yarn
yarn install
```

#### 2. Run Development Server

```bash
# Start Next.js dev server
npm run dev

# Access frontend
# http://localhost:3000
```

#### 3. Build for Production

```bash
# Create production build
npm run build

# Start production server
npm start
```

#### 4. Lint and Format

```bash
# Run ESLint
npm run lint

# Format with Prettier
npm run format

# Type check
npm run type-check
```

### Scraper Development

#### 1. Set Up Scraper Environment

```bash
cd scraper

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

#### 2. Run Scraper

```bash
# Run spider with limit
scrapy crawl nabavki -a limit=10

# Run with custom settings
scrapy crawl nabavki -s LOG_LEVEL=DEBUG

# Save to JSON
scrapy crawl nabavki -o output.json -t json

# Run scheduler
python scheduler.py
```

#### 3. Test PDF Extraction

```bash
# Test PDF extractor
python pdf_extractor.py path/to/document.pdf

# Test document parser
python document_parser.py --url "https://example.com/doc.pdf"
```

### AI/RAG Development

#### 1. Set Up AI Environment

```bash
cd ai

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 2. Test RAG Pipeline

```bash
# Test embeddings generation
python embeddings.py --text "Sample text to embed"

# Test RAG query
python rag_query.py --question "What are the IT tenders?"

# Test vector search
python vector_store.py --query "cloud infrastructure"
```

## Code Style Guide

### Python Code Style

We follow **PEP 8** with some modifications:

#### Formatting

- **Line Length**: 100 characters (not 79)
- **Indentation**: 4 spaces
- **Quotes**: Double quotes for strings, single for dict keys
- **Imports**: Organized (stdlib, third-party, local)

#### Example:

```python
"""
Module docstring explaining purpose.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Tender
from schemas import TenderResponse


router = APIRouter(prefix="/tenders", tags=["tenders"])


@router.get("/{tender_id}", response_model=TenderResponse)
async def get_tender(
    tender_id: str,
    db: AsyncSession = Depends(get_db)
) -> TenderResponse:
    """
    Get tender by ID.

    Args:
        tender_id: Tender identifier
        db: Database session

    Returns:
        TenderResponse: Tender details

    Raises:
        HTTPException: If tender not found
    """
    tender = await db.get(Tender, tender_id)
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    return TenderResponse.from_orm(tender)
```

#### Tools

```bash
# Format code with Black
black backend/ scraper/ ai/

# Check code style with flake8
flake8 backend/ scraper/ ai/ --max-line-length=100

# Type check with mypy
mypy backend/ --ignore-missing-imports

# Sort imports with isort
isort backend/ scraper/ ai/
```

### TypeScript/JavaScript Code Style

#### Formatting

- **Line Length**: 100 characters
- **Indentation**: 2 spaces
- **Quotes**: Single quotes for strings
- **Semicolons**: Required

#### Example:

```typescript
import { useState, useEffect } from 'react';
import { TenderResponse } from '@/types';

interface TenderCardProps {
  tender: TenderResponse;
  onSelect?: (id: string) => void;
}

export function TenderCard({ tender, onSelect }: TenderCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    // Effect logic
  }, [tender.tender_id]);

  const handleClick = () => {
    setIsExpanded(!isExpanded);
    onSelect?.(tender.tender_id);
  };

  return (
    <div className="tender-card" onClick={handleClick}>
      {/* Card content */}
    </div>
  );
}
```

#### Tools

```bash
# Format code with Prettier
npm run format

# Lint with ESLint
npm run lint

# Fix linting issues
npm run lint:fix
```

### SQL Style

- **Keywords**: UPPERCASE
- **Table/Column Names**: snake_case
- **Indentation**: 2 or 4 spaces consistently

```sql
-- Good
SELECT
  tender_id,
  title,
  estimated_value_mkd
FROM tenders
WHERE status = 'open'
  AND closing_date > CURRENT_DATE
ORDER BY closing_date ASC
LIMIT 10;

-- Bad
select tender_id, title from tenders where status='open';
```

## Git Workflow

### Branch Naming

- `main` - Production-ready code
- `develop` - Development branch
- `feature/feature-name` - New features
- `bugfix/bug-description` - Bug fixes
- `hotfix/critical-fix` - Critical production fixes
- `docs/documentation-update` - Documentation changes

### Commit Messages

Follow **Conventional Commits**:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

**Examples:**

```
feat(tenders): add advanced search filters

Implement multi-criteria search with date ranges, value filters,
and CPV code filtering. Includes pagination and sorting options.

Closes #123
```

```
fix(auth): resolve JWT token expiration issue

Token refresh was failing due to incorrect expiry validation.
Updated token validation logic to handle edge cases.

Fixes #456
```

### Workflow

1. **Create Branch**

```bash
git checkout develop
git pull origin develop
git checkout -b feature/my-feature
```

2. **Make Changes**

```bash
# Make code changes
# Run tests
pytest

# Format code
black .

# Stage changes
git add .

# Commit with message
git commit -m "feat(feature): add new capability"
```

3. **Push and Create PR**

```bash
git push origin feature/my-feature

# Create Pull Request on GitHub
# Request code review
```

4. **After Review and Approval**

```bash
# Squash and merge to develop
# Delete feature branch
git branch -d feature/my-feature
```

### Code Review Checklist

**Before Creating PR:**
- [ ] All tests pass
- [ ] Code is formatted (black, prettier)
- [ ] No linting errors
- [ ] Documentation updated
- [ ] Environment variables documented
- [ ] Migration files created (if DB changes)

**Reviewer Checklist:**
- [ ] Code follows style guide
- [ ] Logic is correct and efficient
- [ ] Tests cover new functionality
- [ ] No security vulnerabilities
- [ ] Error handling is robust
- [ ] Documentation is clear

## Testing Guidelines

### Backend Tests

#### Unit Tests

```python
# tests/test_tenders.py
import pytest
from datetime import date
from models import Tender

@pytest.mark.asyncio
async def test_create_tender(db_session):
    """Test tender creation."""
    tender = Tender(
        tender_id="2024/TEST",
        title="Test Tender",
        category="IT",
        status="open",
        closing_date=date(2024, 12, 31)
    )
    db_session.add(tender)
    await db_session.commit()

    assert tender.tender_id == "2024/TEST"
    assert tender.status == "open"
```

#### Integration Tests

```python
# tests/integration/test_api.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_tenders(client: AsyncClient, auth_headers):
    """Test GET /api/tenders endpoint."""
    response = await client.get(
        "/api/tenders",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
```

#### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=. --cov-report=html

# Specific test file
pytest tests/test_tenders.py

# Specific test function
pytest tests/test_tenders.py::test_create_tender

# Skip slow tests
pytest -m "not slow"
```

### Frontend Tests (Future)

```typescript
// __tests__/TenderCard.test.tsx
import { render, screen } from '@testing-library/react';
import { TenderCard } from '@/components/TenderCard';

describe('TenderCard', () => {
  it('renders tender title', () => {
    const tender = {
      tender_id: '2024/123',
      title: 'Test Tender',
      status: 'open'
    };

    render(<TenderCard tender={tender} />);
    expect(screen.getByText('Test Tender')).toBeInTheDocument();
  });
});
```

## Debugging Tips

### Backend Debugging

#### 1. Enable Debug Logging

```python
# main.py or any module
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

#### 2. Use Python Debugger (pdb)

```python
# Insert breakpoint
import pdb; pdb.set_trace()

# Or use built-in breakpoint (Python 3.7+)
breakpoint()
```

#### 3. VS Code Debugger

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--reload"],
      "jinja": true,
      "justMyCode": false
    }
  ]
}
```

#### 4. SQL Query Debugging

```python
# Enable SQL logging
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

### Frontend Debugging

#### 1. Browser DevTools

- **Console**: `console.log()`, `console.error()`
- **Network**: Inspect API requests/responses
- **React DevTools**: Component hierarchy and state

#### 2. Next.js Debug Mode

```bash
NODE_OPTIONS='--inspect' npm run dev
```

Then attach Chrome DevTools: `chrome://inspect`

### Database Debugging

#### Check Connection

```bash
psql -h localhost -U dev -d nabavkidata -c "SELECT version();"
```

#### View Active Queries

```sql
SELECT pid, age(clock_timestamp(), query_start), usename, query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start DESC;
```

#### Explain Query

```sql
EXPLAIN ANALYZE
SELECT * FROM tenders WHERE status = 'open';
```

## Common Issues

### Issue: Database Connection Failed

**Symptoms**: `connection refused` or `could not connect to server`

**Solutions:**
1. Check PostgreSQL is running: `pg_isready`
2. Verify credentials in `.env`
3. Check port 5432 is not blocked
4. Restart PostgreSQL: `brew services restart postgresql@16`

### Issue: Redis Connection Error

**Symptoms**: `Error connecting to Redis`

**Solutions:**
1. Check Redis is running: `redis-cli ping` (should return PONG)
2. Verify REDIS_URL in `.env`
3. Restart Redis: `brew services restart redis`

### Issue: OpenAI API Rate Limit

**Symptoms**: `Rate limit exceeded` from OpenAI

**Solutions:**
1. Wait for rate limit reset (check headers)
2. Implement request batching
3. Use caching for frequent queries
4. Upgrade OpenAI tier

### Issue: Frontend Can't Connect to Backend

**Symptoms**: CORS errors, network errors

**Solutions:**
1. Check backend is running: `curl http://localhost:8000/health`
2. Verify `NEXT_PUBLIC_API_URL` in frontend `.env`
3. Check CORS settings in `backend/main.py`
4. Clear browser cache

### Issue: Migrations Not Applied

**Symptoms**: Database schema mismatch

**Solutions:**
```bash
# Check current migration
alembic current

# Check pending migrations
alembic history

# Apply all pending
alembic upgrade head

# Force recreate (DANGER: loses data)
alembic downgrade base
alembic upgrade head
```

### Issue: Python Package Installation Fails

**Symptoms**: Compilation errors during `pip install`

**Solutions:**
1. Upgrade pip: `pip install --upgrade pip`
2. Install build dependencies:
   - macOS: `xcode-select --install`
   - Ubuntu: `sudo apt install build-essential python3-dev`
3. Use pre-built wheels: `pip install --only-binary :all:`

## Development Tools

### Recommended VS Code Extensions

- **Python**: ms-python.python
- **Pylance**: ms-python.vscode-pylance
- **Black Formatter**: ms-python.black-formatter
- **ESLint**: dbaeumer.vscode-eslint
- **Prettier**: esbenp.prettier-vscode
- **Docker**: ms-azuretools.vscode-docker
- **PostgreSQL**: ckolkman.vscode-postgres
- **Thunder Client**: rangav.vscode-thunder-client (API testing)

### Useful Commands

```bash
# Backend
make backend-dev      # Start backend dev server
make backend-test     # Run backend tests
make backend-format   # Format backend code

# Frontend
make frontend-dev     # Start frontend dev server
make frontend-build   # Build frontend

# Database
make db-migrate       # Run migrations
make db-reset         # Reset database (DANGER)
make db-seed          # Seed test data

# Docker
make docker-up        # Start all services
make docker-down      # Stop all services
make docker-logs      # View logs
make docker-clean     # Remove containers and volumes
```

---

**Development Guide Version**: 1.0
**Last Updated**: 2025-01-22
**For Questions**: dev@nabavkidata.com
