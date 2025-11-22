# Global Rules for All Claude Agents
## Tender Intelligence SaaS Platform - nabavkidata.com

---

## ⚠️ CRITICAL: READ THIS FIRST

**All agents MUST obey these global rules without exception.**

These rules ensure:
- **Production-grade code** with zero shortcuts
- **Parallel execution** without conflicts
- **Self-auditing** to catch issues before handoff
- **Security** built-in from the start
- **User safety** (user has minimal coding knowledge)

Violation of these rules will result in agent task rejection and requeue.

---

## 1. CODE QUALITY STANDARDS

### 1.1 Production-Ready Code Only
- ✅ **NO placeholder code** ("TODO: implement later")
- ✅ **NO commented-out logic** expecting someone else to complete it
- ✅ **NO assumptions** about future work
- ✅ Write code as if deploying to production immediately

**Example of FORBIDDEN code**:
```python
# TODO: Add authentication here
def get_tenders():
    # user_id = get_current_user()  # Implement this later
    return Tender.query.all()
```

**Correct approach**:
```python
@requires_auth
def get_tenders(user_id: UUID) -> List[Tender]:
    """Fetch tenders accessible to authenticated user."""
    if not user_id:
        raise UnauthorizedException("Authentication required")
    return Tender.query.filter_by(user_id=user_id).all()
```

### 1.2 Error Handling is Mandatory
- ✅ Every external call (API, DB, file I/O) MUST have try/except
- ✅ Log all errors with context (not just `print(e)`)
- ✅ Return meaningful error messages to users
- ✅ Never let exceptions crash the application

**Example**:
```python
try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
except requests.Timeout:
    logger.error(f"Timeout fetching {url}")
    raise ServiceUnavailableError("External service timeout")
except requests.HTTPError as e:
    logger.error(f"HTTP {e.response.status_code} from {url}")
    raise
```

### 1.3 Input Validation Everywhere
- ✅ Validate ALL user inputs (API parameters, form data, file uploads)
- ✅ Use type hints in Python, TypeScript types in frontend
- ✅ Sanitize inputs to prevent SQL injection, XSS, command injection
- ✅ Return 400 Bad Request with clear validation errors

**Python Example**:
```python
from pydantic import BaseModel, EmailStr, validator

class UserSignup(BaseModel):
    email: EmailStr
    password: str
    name: str

    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        return v
```

### 1.4 Testing is Non-Negotiable
- ✅ Every function/endpoint MUST have at least one unit test
- ✅ Minimum 80% code coverage
- ✅ Write tests BEFORE marking module complete
- ✅ Include edge case tests (empty inputs, max limits, invalid data)

**Test Structure**:
```python
# tests/test_tenders.py
def test_get_tenders_requires_auth():
    """Unauthenticated request should return 401."""
    response = client.get('/api/tenders')
    assert response.status_code == 401

def test_get_tenders_returns_valid_json():
    """Authenticated request returns tender list."""
    token = get_auth_token('user@example.com')
    response = client.get('/api/tenders', headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 200
    data = response.json()
    assert 'results' in data
```

### 1.5 Documentation as You Code
- ✅ Docstrings for all public functions/classes
- ✅ Inline comments for complex logic only (code should be self-explanatory)
- ✅ README.md in each module explaining setup and usage
- ✅ API documentation generated automatically (OpenAPI/Swagger)

**Python Docstring Format**:
```python
def embed_text(text: str, model: str = "text-embedding-ada-002") -> List[float]:
    """
    Generate vector embedding for text using specified model.

    Args:
        text: Input text to embed (max 8000 tokens)
        model: Embedding model name (default: ada-002)

    Returns:
        List of floats representing the embedding vector (1536 dimensions)

    Raises:
        ValueError: If text is empty or exceeds token limit
        APIError: If embedding service is unavailable

    Example:
        >>> vector = embed_text("Public procurement tender")
        >>> len(vector)
        1536
    """
```

---

## 2. NAMING CONVENTIONS

### 2.1 File and Directory Names
- ✅ **Python**: `snake_case.py` (e.g., `tender_service.py`)
- ✅ **JavaScript/TypeScript**: `camelCase.ts` or `PascalCase.tsx` for components
- ✅ **Directories**: `lowercase` (e.g., `scrapers/`, `services/`)
- ✅ **No spaces** in filenames ever

### 2.2 Variable and Function Names
- ✅ **Python**: `snake_case` for functions/variables
- ✅ **TypeScript**: `camelCase` for functions/variables
- ✅ **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES = 3`)
- ✅ **Classes**: `PascalCase` (e.g., `TenderService`, `UserModel`)

### 2.3 Database Names
- ✅ **Tables**: `plural_snake_case` (e.g., `tenders`, `query_history`)
- ✅ **Columns**: `snake_case` (e.g., `tender_id`, `created_at`)
- ✅ **Indexes**: `idx_{table}_{column}` (e.g., `idx_tenders_category`)
- ✅ **Foreign Keys**: `fk_{from_table}_{to_table}` (e.g., `fk_documents_tenders`)

### 2.4 API Endpoints
- ✅ **REST**: `/api/{resource}/{id}` (e.g., `/api/tenders/2023-47`)
- ✅ **Use plural nouns**: `/api/tenders` not `/api/tender`
- ✅ **Lowercase with hyphens**: `/api/query-history` not `/api/queryHistory`

---

## 3. SECURITY RULES (CRITICAL)

### 3.1 Secrets Management
- 🚫 **NEVER** hardcode credentials, API keys, passwords
- ✅ **ALWAYS** use environment variables: `os.getenv('STRIPE_SECRET_KEY')`
- ✅ Use `.env.example` with placeholder values, gitignore `.env`
- ✅ Rotate secrets regularly (implement key rotation in DevOps)

**Example `.env.example`**:
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/nabavkidata

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# OpenAI
OPENAI_API_KEY=sk-...

# Gemini
GEMINI_API_KEY=...
```

### 3.2 Authentication & Authorization
- ✅ **JWT tokens** with expiration (max 24 hours)
- ✅ **Refresh tokens** for long-lived sessions
- ✅ **Password hashing** with Argon2 or bcrypt (work factor ≥12)
- ✅ **Role-based access control** (RBAC) enforced at API level
- ✅ **Rate limiting** on login endpoint (max 5 attempts/minute)

### 3.3 SQL Injection Prevention
- ✅ **ALWAYS** use parameterized queries or ORM
- 🚫 **NEVER** use string concatenation for SQL

**BAD**:
```python
query = f"SELECT * FROM users WHERE email = '{user_email}'"  # VULNERABLE!
```

**GOOD**:
```python
query = "SELECT * FROM users WHERE email = %s"
cursor.execute(query, (user_email,))
```

### 3.4 XSS Protection
- ✅ Sanitize all user inputs before rendering in HTML
- ✅ Use framework's built-in escaping (React automatically escapes)
- ✅ Set CSP headers: `Content-Security-Policy: default-src 'self'`

### 3.5 CSRF Protection
- ✅ Use CSRF tokens for all state-changing requests (POST, PUT, DELETE)
- ✅ SameSite cookies: `Set-Cookie: session=...; SameSite=Strict`

### 3.6 Dependency Security
- ✅ Run `npm audit` / `pip check` before every commit
- ✅ Pin dependency versions in `requirements.txt` / `package-lock.json`
- ✅ Update dependencies monthly, test thoroughly

---

## 4. DATA HANDLING RULES

### 4.1 Database Transactions
- ✅ Use transactions for multi-step operations
- ✅ Rollback on error
- ✅ Never leave database in inconsistent state

**Example**:
```python
with db.transaction():
    user = User.create(email=email)
    subscription = Subscription.create(user_id=user.id, plan='Free')
    # If subscription creation fails, user creation is rolled back
```

### 4.2 Migration Safety
- ✅ All migrations MUST be reversible (have `up` and `down`)
- ✅ Test migrations on staging before production
- ✅ Never drop columns/tables without backup
- ✅ Add columns as nullable first, populate, then make non-nullable

### 4.3 GDPR Compliance
- ✅ Log all access to personal data in `audit_log`
- ✅ Implement "right to deletion" (user can delete account)
- ✅ Anonymize data in analytics (no PII in logs)
- ✅ Data retention policy: delete old audit logs after 2 years

---

## 5. PARALLEL EXECUTION RULES

### 5.1 Respect Dependencies
- ✅ Check `orchestrator.yaml` for your dependencies
- ✅ **NEVER** start work until dependencies are met
- ✅ Notify Orchestrator when you complete a milestone

**Example**: Frontend Agent MUST wait for Backend Agent to publish API spec.

### 5.2 No Overlapping Responsibilities
- ✅ Each agent owns specific files/modules
- ✅ **NEVER** modify another agent's files
- ✅ Use integration contracts (APIs, schemas) to communicate

**Example**: Scraper Agent owns `scraper/`, Backend Agent owns `backend/`. If Scraper needs DB schema, it reads `db/schema.md` (Database Agent's output).

### 5.3 Handoff Protocol
When completing a milestone:
1. ✅ Run self-audit (see Section 6)
2. ✅ Generate handoff artifacts (API spec, sample data, etc.)
3. ✅ Notify downstream agents via Orchestrator
4. ✅ Wait for validation before moving to next milestone

---

## 6. SELF-AUDIT REQUIREMENTS

### 6.1 Mandatory Audit Report
**Every agent MUST produce** `{module}/audit_report.md` before marking complete.

**Template**:
```markdown
# Audit Report: {Agent Name}
**Date**: YYYY-MM-DD
**Agent**: {Agent ID}
**Module**: {Module Path}

## 1. Code Quality Checks
- [ ] All functions have docstrings
- [ ] No hardcoded secrets
- [ ] Input validation on all endpoints
- [ ] Error handling implemented

## 2. Security Scan
- [ ] Dependencies scanned (bandit/eslint-security)
- [ ] No SQL injection vulnerabilities
- [ ] XSS protection verified
- [ ] Authentication enforced

## 3. Testing
- [ ] Unit tests written (coverage: X%)
- [ ] Integration tests pass
- [ ] Edge cases covered

## 4. Issues Found & Fixed
| Issue | Severity | Fix Applied |
|-------|----------|-------------|
| Missing input validation in /api/ask | HIGH | Added Pydantic model |
| Hardcoded API key in config | CRITICAL | Moved to env var |

## 5. Outstanding Risks
- None / {describe any known limitations}

## 6. Sign-Off
**Status**: ✅ READY FOR HANDOFF / ⚠️ ISSUES REMAINING
**Next Agent**: {Agent ID to receive handoff}
```

### 6.2 Automated Checks
Run these tools before submitting:
- **Python**: `bandit -r .`, `pylint`, `black --check`
- **JavaScript**: `eslint`, `prettier --check`
- **Dependencies**: `safety check` (Python), `npm audit` (Node)

### 6.3 Fix Issues Immediately
- ✅ If audit finds critical issues → **FIX BEFORE HANDOFF**
- ✅ Do not escalate to QA Agent unless truly blocked
- ✅ Re-run audit after fixes to verify

---

## 7. COMMUNICATION PROTOCOL

### 7.1 Status Updates
Send structured JSON to Orchestrator at these events:
- ✅ **Task Start**: `{agent_id, status: "in_progress", timestamp}`
- ✅ **Milestone Complete**: `{agent_id, milestone, artifacts: [...]}`
- ✅ **Error**: `{agent_id, error_type, severity, description}`
- ✅ **Handoff**: `{from_agent, to_agent, validation_status}`

### 7.2 Escalation Levels
| Level | When to Use | Action |
|-------|-------------|--------|
| **L1** | Agent can fix internally | Self-resolve, log in audit report |
| **L2** | Need input from another agent | Peer consultation via Orchestrator |
| **L3** | Blocking dependency failure | Orchestrator intervention |
| **L4** | Critical security flaw | **HALT ENTIRE SYSTEM**, notify user |

**Example L4 Escalation**:
```json
{
  "agent_id": "backend",
  "level": 4,
  "severity": "CRITICAL",
  "issue": "SQL injection vulnerability in /api/tenders",
  "action": "HALT_DEPLOYMENT",
  "requires_human_review": true
}
```

### 7.3 Integration Requests
When Agent A needs integration with Agent B:
1. ✅ Agent A creates **Integration Contract** document
2. ✅ Contract specifies: endpoints, data formats, error codes
3. ✅ Both agents sign off on contract
4. ✅ Implementation proceeds independently
5. ✅ QA Agent validates integration

**Example Contract** (`backend_ai_integration.md`):
```markdown
# Backend ↔ AI/RAG Integration Contract

## Endpoint
`POST /internal/ai/query`

## Request
{
  "question": "string (max 500 chars)",
  "user_id": "UUID",
  "context_filters": {"category": "string", "date_range": "..."}
}

## Response
{
  "answer": "string",
  "sources": [{"tender_id": "...", "relevance": 0.95}],
  "model": "gemini-pro",
  "latency_ms": 1200
}

## Error Codes
- 400: Invalid question format
- 429: Rate limit exceeded
- 500: LLM service unavailable
```

---

## 8. GIT & VERSION CONTROL

### 8.1 Branching Strategy
- ✅ `main` branch is production-ready (protected)
- ✅ Each agent works on feature branch: `feature/{agent-name}/{task}`
- ✅ Example: `feature/scraper/pdf-extraction`

### 8.2 Commit Messages
- ✅ Use conventional commits: `type(scope): description`
- ✅ Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`

**Examples**:
```
feat(scraper): add PDF text extraction with PyMuPDF
fix(backend): prevent SQL injection in tender search
test(ai): add RAG pipeline integration tests
docs(db): document embedding table schema
```

### 8.3 Pull Requests
- ✅ All code goes through PR (even for agents)
- ✅ PR must include:
  - Description of changes
  - Link to audit report
  - Test results
  - Screenshots (for UI changes)
- ✅ Auto-merge after CI passes + audit approval

---

## 9. LOGGING & MONITORING

### 9.1 Structured Logging
- ✅ Use JSON format for all logs
- ✅ Include: `timestamp`, `level`, `agent_id`, `message`, `context`

**Python Example**:
```python
import structlog

logger = structlog.get_logger()

logger.info("tender_scraped",
    tender_id="2023/47",
    category="IT Equipment",
    status="success")
```

### 9.2 Log Levels
- **DEBUG**: Development only (verbose)
- **INFO**: Normal operations (tender scraped, user login)
- **WARNING**: Unexpected but recoverable (API timeout, retry)
- **ERROR**: Failure requiring attention (DB connection lost)
- **CRITICAL**: System-wide failure (all LLMs down)

### 9.3 Never Log Sensitive Data
- 🚫 **NEVER** log passwords, tokens, credit card numbers
- 🚫 **NEVER** log full user emails in production (use hashed IDs)

**BAD**:
```python
logger.info(f"User {email} logged in with password {password}")  # FORBIDDEN!
```

**GOOD**:
```python
logger.info("user_login", user_id=user.id, ip=request.ip)
```

---

## 10. PERFORMANCE REQUIREMENTS

### 10.1 Response Time Targets
| Endpoint | Target | Max |
|----------|--------|-----|
| API (GET) | <100ms | 500ms |
| API (POST) | <200ms | 1s |
| AI Query | <3s | 10s |
| Scraper (per tender) | <500ms | 2s |

### 10.2 Database Query Optimization
- ✅ Use `EXPLAIN ANALYZE` for slow queries
- ✅ Add indexes for all WHERE/JOIN columns
- ✅ Limit result sets (pagination)
- ✅ Use connection pooling (PgBouncer)

### 10.3 Caching Strategy
- ✅ Cache static data (categories, config) in Redis (TTL: 1 hour)
- ✅ Cache API responses (tender lists) (TTL: 5 minutes)
- ✅ Cache embeddings lookups (TTL: indefinite, invalidate on update)

---

## 11. DEPLOYMENT RULES

### 11.1 Environment Separation
- ✅ **Development**: Local, no real API keys
- ✅ **Staging**: Replica of production, test Stripe mode
- ✅ **Production**: Real users, real payments

### 11.2 Deployment Checklist
Before deploying to production:
- [ ] All tests pass (unit + integration)
- [ ] Security scan clean (no HIGH/CRITICAL vulnerabilities)
- [ ] Database migrations tested on staging
- [ ] Rollback plan documented
- [ ] Monitoring dashboards configured
- [ ] On-call engineer notified

### 11.3 Zero-Downtime Deployments
- ✅ Use blue-green deployment or rolling updates
- ✅ Health checks before routing traffic
- ✅ Database migrations run BEFORE code deploy

---

## 12. USER INTERACTION RULES

### 12.1 Never Ask User Technical Questions
**User has minimal coding knowledge.** Agents MUST:
- ✅ Make reasonable technical decisions autonomously
- ✅ Document decisions in audit report
- ✅ Only escalate critical business decisions (e.g., pricing tier features)

**FORBIDDEN**:
```
Agent: "Should I use FastAPI or Flask for the backend?"
```

**ALLOWED**:
```
Agent: "I've chosen FastAPI for async support and auto-generated API docs.
        See backend/ARCHITECTURE.md for rationale."
```

### 12.2 User-Facing Error Messages
- ✅ Friendly, non-technical language
- ✅ Actionable (tell user what to do)
- 🚫 Never show stack traces to users

**BAD**:
```
Error: NoneType object has no attribute 'id'
```

**GOOD**:
```
We couldn't find that tender. Please check the ID and try again.
```

---

## 13. FORBIDDEN PRACTICES

### 13.1 NEVER Do These
- 🚫 Commit code with `console.log()` or `print()` debug statements
- 🚫 Use `eval()` or `exec()` on user input
- 🚫 Store passwords in plaintext
- 🚫 Trust client-side validation (always validate server-side)
- 🚫 Return different error messages for "user not found" vs "wrong password" (timing attacks)
- 🚫 Use `SELECT *` in production queries
- 🚫 Deploy on Friday afternoon (no weekend emergency fixes)

### 13.2 Code Smells to Avoid
- 🚫 Functions >50 lines (break into smaller functions)
- 🚫 Nested loops >3 levels deep
- 🚫 Magic numbers (use named constants)
- 🚫 Copy-pasted code (create reusable functions)

---

## 14. AGENT-SPECIFIC OVERRIDES

Some agents have specialized rules in their individual `.md` files.

**Priority**: `agent-specific rules` > `global rules`

**Example**: AI/RAG Agent may have relaxed performance targets (10s response time) due to LLM latency.

---

## 15. QUALITY GATES (AUTOMATED)

Before any handoff, these checks MUST pass:

### ✅ Code Quality
```bash
# Python
black --check .
pylint **/*.py --fail-under=8.0

# JavaScript
prettier --check .
eslint --max-warnings 0
```

### ✅ Security
```bash
# Python
bandit -r . -ll  # Only HIGH/MED severity

# JavaScript
npm audit --audit-level=moderate
```

### ✅ Tests
```bash
pytest --cov=. --cov-fail-under=80
```

### ✅ Type Checking
```bash
mypy .  # Python
tsc --noEmit  # TypeScript
```

**If any check fails → FIX before proceeding.**

---

## 16. SUCCESS CRITERIA

An agent's work is considered **COMPLETE** when:
- ✅ All assigned tasks implemented (no TODOs)
- ✅ Self-audit report submitted with ✅ READY status
- ✅ All quality gates passed
- ✅ Integration tests with dependent agents pass
- ✅ Documentation complete (README, API docs, inline comments)
- ✅ Handoff artifacts delivered to next agent

**Orchestrator will validate before allowing handoff.**

---

## 17. CONFLICT RESOLUTION

### 17.1 File Conflicts
If two agents accidentally modify same file:
1. ✅ Merge carefully, preserving both changes
2. ✅ Run full test suite
3. ✅ Notify Orchestrator of conflict resolution

### 17.2 Design Conflicts
If agents disagree on approach (e.g., REST vs GraphQL):
1. ✅ Document both approaches in `design_decisions.md`
2. ✅ Choose based on project priorities (speed, scalability, team skill)
3. ✅ Get sign-off from Orchestrator

---

## 18. CONTINUOUS IMPROVEMENT

### 18.1 Retrospectives
After each sprint:
- ✅ Document what went well
- ✅ Document what needs improvement
- ✅ Update rules if patterns emerge

### 18.2 Rule Updates
These rules are living documents. Propose changes via:
1. ✅ Create `rules_proposal.md`
2. ✅ Get consensus from affected agents
3. ✅ Orchestrator approves and updates `rules.md`

---

## 19. EMERGENCY PROCEDURES

### 19.1 Critical Bug in Production
1. ✅ **HALT all deployments**
2. ✅ Rollback to last known good version
3. ✅ Create hotfix branch
4. ✅ Fix, test, deploy
5. ✅ Post-mortem document

### 19.2 Data Loss Event
1. ✅ **STOP all write operations**
2. ✅ Restore from latest backup
3. ✅ Verify data integrity
4. ✅ Resume operations
5. ✅ Incident report

---

## 20. FINAL NOTES

### For Agents
These rules exist to ensure nabavkidata.com launches successfully with:
- ✅ **Zero critical bugs** (because you self-audit)
- ✅ **No security incidents** (because you follow security rules)
- ✅ **High performance** (because you optimize from the start)
- ✅ **Happy users** (because you build with them in mind)

**When in doubt, over-communicate. Ask Orchestrator. Document your decisions.**

### For User
You don't need to understand these technical details. Just know that every agent is following strict quality standards to deliver a production-ready SaaS platform.

---

**END OF GLOBAL RULES**

*Version 1.0 - Updated 2024-11-22*
*Next Review: After Sprint 1 completion*
