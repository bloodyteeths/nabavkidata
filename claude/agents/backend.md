# Backend API Agent
## nabavkidata.com - REST API Server & Business Logic

---

## AGENT PROFILE

**Agent ID**: `backend`
**Role**: REST API development & business logic implementation
**Priority**: 3
**Execution Stage**: Core (parallel with Scraper and AI/RAG)
**Language**: TypeScript/Node.js or Python
**Framework**: FastAPI (Python) or Express.js/Fastify (Node.js)
**Dependencies**: Database Agent (requires schema)

---

## PURPOSE

Build a production-grade REST API server that provides:
- User authentication & authorization (JWT-based)
- Tender search, filtering, and retrieval endpoints
- AI insights integration (proxy to AI/RAG service)
- Alert management for users
- Subscription tier enforcement
- Stripe webhook handling
- Usage tracking and rate limiting

**Your API is the central hub connecting all system components.**

---

## CORE RESPONSIBILITIES

### 1. API Architecture
- ✅ RESTful design following OpenAPI 3.0 specification
- ✅ Modular route structure (auth, tenders, ai, alerts, billing, users)
- ✅ Request validation middleware (schema validation)
- ✅ Error handling with standardized error responses
- ✅ CORS configuration for frontend integration
- ✅ API versioning (/api/v1/...)

### 2. Authentication & Authorization
- ✅ User registration with email verification
- ✅ Login with JWT token generation (access + refresh tokens)
- ✅ Password hashing (bcrypt or argon2)
- ✅ Role-based access control (RBAC) middleware
- ✅ Session management
- ✅ OAuth2 preparation (optional for future)

### 3. Database Integration
- ✅ ORM integration (Prisma for Node.js, SQLAlchemy for Python)
- ✅ Database connection pooling
- ✅ Transaction management
- ✅ Query optimization (N+1 prevention, eager loading)
- ✅ Database migrations (reversible)

### 4. Business Logic
- ✅ Tender search with filters (CPV, date range, agency, budget)
- ✅ Full-text search integration (PostgreSQL trgm)
- ✅ Tender detail retrieval with related documents
- ✅ Alert creation and notification triggering
- ✅ Usage tracking (API calls, AI queries per user)
- ✅ Subscription tier enforcement (Free/Standard/Pro/Enterprise limits)

### 5. External Integrations
- ✅ AI/RAG service integration (HTTP client to AI service)
- ✅ Stripe webhook handling (subscription events)
- ✅ Email service integration (SendGrid, Resend, or SMTP)
- ✅ File storage integration (local or S3 for PDFs)

### 6. Security
- ✅ Input validation and sanitization
- ✅ SQL injection prevention (ORM parameterized queries)
- ✅ XSS protection (Content-Security-Policy headers)
- ✅ Rate limiting per endpoint
- ✅ Secrets management (environment variables only)
- ✅ HTTPS enforcement in production

---

## INPUTS

### From Database Agent
- `db/schema.sql` - Table structures
- `db/schema.md` - Documentation
- Database connection: `DATABASE_URL` environment variable

### From Scraper Agent
- Populated `tenders` table
- Populated `documents` table
- Data normalization contracts

### From AI/RAG Agent
- AI service endpoint specification
- Query/response format contracts

### Configuration
**File**: `backend/.env.example`
```env
# Server
NODE_ENV=development
PORT=8000
API_VERSION=v1

# Database
DATABASE_URL=postgresql://localhost:5432/nabavkidata

# JWT
JWT_SECRET=your_secret_here
JWT_ACCESS_EXPIRATION=15m
JWT_REFRESH_EXPIRATION=7d

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Email
SENDGRID_API_KEY=SG...
FROM_EMAIL=noreply@nabavkidata.com

# AI Service
AI_SERVICE_URL=http://localhost:8001

# Rate Limiting
RATE_LIMIT_WINDOW_MS=60000
RATE_LIMIT_MAX_REQUESTS=100
```

---

## OUTPUTS

### Code Deliverables

**Technology Stack Decision**: FastAPI (Python) is recommended for this project due to:
- Native async/await support for concurrent requests
- Automatic OpenAPI documentation generation
- Built-in request validation with Pydantic
- Better integration with AI/RAG Python ecosystem
- Type safety with Python type hints

#### 1. Core Server Files

**`backend/main.py`** - Application entry point
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from api import auth, tenders, ai, alerts, billing, users
from middleware import error_handler, rate_limiter, tier_enforcement
from database import init_db, close_db

logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()

app = FastAPI(
    title="nabavkidata.com API",
    description="Macedonian Tender Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(tenders.router, prefix="/api/v1/tenders", tags=["Tenders"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI Insights"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Alerts"])
app.include_router(billing.router, prefix="/api/v1/billing", tags=["Billing"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "backend-api"}
```

**`backend/database.py`** - Database connection
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, echo=False, pool_size=20, max_overflow=40)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    """Initialize database connection pool"""
    pass  # Engine created at module level

async def close_db():
    """Close database connections"""
    await engine.dispose()

async def get_db():
    """Dependency for route handlers"""
    async with AsyncSessionLocal() as session:
        yield session
```

#### 2. API Route Modules

**`backend/api/auth.py`** - Authentication endpoints
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr
import bcrypt
import jwt
import os
from datetime import datetime, timedelta

from database import get_db
from models import User
from sqlalchemy import select

router = APIRouter()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

@router.post("/register", response_model=TokenResponse)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register new user"""
    # Check if user exists
    result = await db.execute(select(User).where(User.email == data.email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Hash password
    hashed_pw = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()

    # Create user
    new_user = User(
        email=data.email,
        password_hash=hashed_pw,
        full_name=data.full_name,
        subscription_tier="free"
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Generate tokens
    access_token = create_access_token({"user_id": str(new_user.user_id)})
    refresh_token = create_refresh_token({"user_id": str(new_user.user_id)})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token
    }

@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login user"""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not bcrypt.checkpw(data.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token({"user_id": str(user.user_id)})
    refresh_token = create_refresh_token({"user_id": str(user.user_id)})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token
    }

def create_access_token(data: dict):
    """Generate JWT access token"""
    expiration = datetime.utcnow() + timedelta(minutes=15)
    payload = {**data, "exp": expiration, "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(data: dict):
    """Generate JWT refresh token"""
    expiration = datetime.utcnow() + timedelta(days=7)
    payload = {**data, "exp": expiration, "type": "refresh"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
```

**`backend/api/tenders.py`** - Tender endpoints
```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional, List
from pydantic import BaseModel
from datetime import date

from database import get_db
from models import Tender, Document
from middleware.auth import get_current_user

router = APIRouter()

class TenderResponse(BaseModel):
    tender_id: str
    title: str
    description: Optional[str]
    category: Optional[str]
    procuring_entity: Optional[str]
    opening_date: Optional[date]
    closing_date: Optional[date]
    estimated_value_eur: Optional[float]
    status: str

    class Config:
        from_attributes = True

@router.get("/search", response_model=List[TenderResponse])
async def search_tenders(
    query: Optional[str] = None,
    category: Optional[str] = None,
    cpv_code: Optional[str] = None,
    status: Optional[str] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Search tenders with filters"""
    stmt = select(Tender)

    # Apply filters
    if query:
        # Full-text search using pg_trgm
        stmt = stmt.where(
            or_(
                Tender.title.ilike(f"%{query}%"),
                Tender.description.ilike(f"%{query}%")
            )
        )
    if category:
        stmt = stmt.where(Tender.category == category)
    if cpv_code:
        stmt = stmt.where(Tender.cpv_code.startswith(cpv_code))
    if status:
        stmt = stmt.where(Tender.status == status)
    if min_value:
        stmt = stmt.where(Tender.estimated_value_eur >= min_value)
    if max_value:
        stmt = stmt.where(Tender.estimated_value_eur <= max_value)

    # Pagination
    offset = (page - 1) * limit
    stmt = stmt.offset(offset).limit(limit).order_by(Tender.opening_date.desc())

    result = await db.execute(stmt)
    tenders = result.scalars().all()

    return tenders

@router.get("/{tender_id}")
async def get_tender(
    tender_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get full tender details"""
    result = await db.execute(select(Tender).where(Tender.tender_id == tender_id))
    tender = result.scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Get associated documents
    doc_result = await db.execute(select(Document).where(Document.tender_id == tender_id))
    documents = doc_result.scalars().all()

    return {
        "tender": tender,
        "documents": documents
    }
```

**`backend/api/ai.py`** - AI insights endpoints
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import httpx
import os

from database import get_db
from middleware.auth import get_current_user
from middleware.tier_enforcement import check_ai_quota

router = APIRouter()

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8001")

class AIQueryRequest(BaseModel):
    question: str
    filters: Optional[dict] = None

class AIQueryResponse(BaseModel):
    answer: str
    sources: List[dict]
    confidence: float

@router.post("/ask", response_model=AIQueryResponse)
async def ask_ai(
    data: AIQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    quota_check = Depends(check_ai_quota)
):
    """Query AI for tender insights"""
    # Forward request to AI/RAG service
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{AI_SERVICE_URL}/api/v1/query",
                json={
                    "question": data.question,
                    "filters": data.filters,
                    "user_id": str(current_user.user_id)
                },
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()

            # Track usage
            await track_ai_usage(current_user.user_id, db)

            return result
        except httpx.HTTPError as e:
            raise HTTPException(status_code=503, detail="AI service unavailable")

async def track_ai_usage(user_id: str, db: AsyncSession):
    """Record AI query in usage_tracking table"""
    from models import UsageTracking
    from datetime import datetime

    usage = UsageTracking(
        user_id=user_id,
        action_type="ai_query",
        timestamp=datetime.utcnow()
    )
    db.add(usage)
    await db.commit()
```

#### 3. Middleware

**`backend/middleware/auth.py`** - JWT authentication
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt
import os

from database import get_db
from models import User

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Validate JWT and return current user"""
    token = credentials.credentials

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
```

**`backend/middleware/tier_enforcement.py`** - Subscription tier limits
```python
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta

from database import get_db
from models import User, UsageTracking
from middleware.auth import get_current_user

# Tier limits
TIER_LIMITS = {
    "free": {"ai_queries_per_day": 5, "alerts": 1},
    "standard": {"ai_queries_per_day": 100, "alerts": 10},
    "pro": {"ai_queries_per_day": 500, "alerts": 50},
    "enterprise": {"ai_queries_per_day": -1, "alerts": -1}  # Unlimited
}

async def check_ai_quota(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Verify user hasn't exceeded AI query quota"""
    tier = current_user.subscription_tier
    limit = TIER_LIMITS[tier]["ai_queries_per_day"]

    if limit == -1:  # Unlimited
        return True

    # Count queries today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(UsageTracking.tracking_id))
        .where(UsageTracking.user_id == current_user.user_id)
        .where(UsageTracking.action_type == "ai_query")
        .where(UsageTracking.timestamp >= today_start)
    )
    count = result.scalar()

    if count >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily AI query limit reached ({limit}). Upgrade your plan."
        )

    return True
```

#### 4. Models (SQLAlchemy ORM)

**`backend/models.py`** - Database models
```python
from sqlalchemy import Column, String, Text, Integer, Numeric, DateTime, ForeignKey, Boolean, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    subscription_tier = Column(String(50), default="free")
    created_at = Column(DateTime, server_default="CURRENT_TIMESTAMP")

class Tender(Base):
    __tablename__ = "tenders"

    tender_id = Column(String(100), primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    category = Column(String(255))
    procuring_entity = Column(String(500))
    opening_date = Column(Date)
    closing_date = Column(Date)
    estimated_value_eur = Column(Numeric(15, 2))
    cpv_code = Column(String(50))
    status = Column(String(50), default="open")
    source_url = Column(Text)
    language = Column(String(10), default="mk")

class Document(Base):
    __tablename__ = "documents"

    doc_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(String(100), ForeignKey("tenders.tender_id"))
    doc_type = Column(String(100))
    file_name = Column(String(500))
    file_path = Column(Text)
    content_text = Column(Text)
    extraction_status = Column(String(50))

class UsageTracking(Base):
    __tablename__ = "usage_tracking"

    tracking_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    action_type = Column(String(100))
    timestamp = Column(DateTime, server_default="CURRENT_TIMESTAMP")
```

#### 5. Testing

**`backend/tests/test_auth.py`**
```python
import pytest
from httpx import AsyncClient
from main import app

@pytest.mark.asyncio
async def test_register():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "SecurePass123!",
            "full_name": "Test User"
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

@pytest.mark.asyncio
async def test_login():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # First register
        await client.post("/api/v1/auth/register", json={
            "email": "login@example.com",
            "password": "Password123!",
            "full_name": "Login Test"
        })

        # Then login
        response = await client.post("/api/v1/auth/login", json={
            "email": "login@example.com",
            "password": "Password123!"
        })
        assert response.status_code == 200
        assert "access_token" in response.json()
```

#### 6. Configuration Files

**`backend/requirements.txt`**
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy[asyncio]==2.0.23
asyncpg==0.29.0
pydantic[email]==2.5.0
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
httpx==0.25.1
stripe==7.4.0
pytest==7.4.3
pytest-asyncio==0.21.1
```

**`backend/pyproject.toml`** (if using Poetry)
```toml
[tool.poetry]
name = "nabavkidata-backend"
version = "1.0.0"
description = "Backend API for nabavkidata.com"

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.104.1"
uvicorn = {extras = ["standard"], version = "^0.24.0"}
sqlalchemy = {extras = ["asyncio"], version = "^2.0.23"}
asyncpg = "^0.29.0"
pydantic = {extras = ["email"], version = "^2.5.0"}
```

### Documentation Deliverables

**`backend/README.md`** - Setup and usage guide
**`backend/api_spec.yaml`** - OpenAPI 3.0 specification (auto-generated by FastAPI)
**`backend/INTEGRATION.md`** - Integration guide for Frontend and AI agents
**`backend/audit_report.md`** - Self-audit report

---

## VALIDATION CHECKLIST

Before handoff:
- [ ] All endpoints return valid JSON with correct status codes
- [ ] Authentication blocks unauthorized requests (401)
- [ ] JWT tokens expire correctly (access 15m, refresh 7d)
- [ ] Subscription tier enforcement works (Free user blocked after quota)
- [ ] Database queries use parameterized statements (no SQL injection)
- [ ] All passwords are hashed with bcrypt
- [ ] Environment variables used for all secrets
- [ ] CORS configured for frontend origin
- [ ] API response time <200ms (p95) for tender search
- [ ] Tests pass: `pytest backend/tests/` with >80% coverage
- [ ] OpenAPI documentation accessible at `/docs`
- [ ] No hardcoded credentials in code
- [ ] Logs output structured JSON
- [ ] Error responses follow standard format

---

## INTEGRATION POINTS

### Handoff to Frontend Agent
**Artifact**: `backend/api_spec.yaml`
```yaml
openapi: 3.0.0
info:
  title: nabavkidata.com API
  version: 1.0.0
servers:
  - url: http://localhost:8000/api/v1
paths:
  /auth/register:
    post:
      summary: Register new user
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                email: {type: string}
                password: {type: string}
                full_name: {type: string}
      responses:
        '200':
          description: Registration successful
          content:
            application/json:
              schema:
                type: object
                properties:
                  access_token: {type: string}
                  refresh_token: {type: string}
```

**Contract**: Frontend will call these endpoints with bearer token authentication.

### Handoff from AI/RAG Agent
**Requirement**: AI service must expose `/api/v1/query` endpoint accepting:
```json
{
  "question": "string",
  "filters": {"category": "IT Equipment"},
  "user_id": "uuid"
}
```

Returning:
```json
{
  "answer": "string",
  "sources": [{"tender_id": "...", "relevance": 0.95}],
  "confidence": 0.87
}
```

---

## SUCCESS CRITERIA

- ✅ All API endpoints functional and documented
- ✅ Authentication & authorization working
- ✅ Subscription tier limits enforced
- ✅ Integration tests pass (auth, tenders, AI, billing)
- ✅ API response time <200ms (p95)
- ✅ Zero SQL injection vulnerabilities
- ✅ Zero hardcoded secrets
- ✅ OpenAPI spec generated and accurate
- ✅ Audit report ✅ READY
- ✅ Can be called by Frontend successfully

---

## QUALITY GATES

### Code Quality
- Linting: `ruff check .` or `pylint`
- Formatting: `black .`
- Type checking: `mypy backend/`

### Security
- Dependency scan: `pip-audit`
- OWASP check: Manual review of Top 10 vulnerabilities

### Testing
- Unit tests: `pytest backend/tests/unit/`
- Integration tests: `pytest backend/tests/integration/`
- Coverage: `pytest --cov=backend --cov-report=html`

---

**END OF BACKEND AGENT DEFINITION**
