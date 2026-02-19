# API Documentation

> Complete REST API reference for nabavkidata.com

## Table of Contents

- [Overview](#overview)
- [Base URL](#base-url)
- [Authentication](#authentication)
- [Rate Limiting](#rate-limiting)
- [Response Format](#response-format)
- [Error Codes](#error-codes)
- [Authentication Endpoints](#authentication-endpoints)
- [Tender Endpoints](#tender-endpoints)
- [Document Endpoints](#document-endpoints)
- [RAG/AI Endpoints](#ragai-endpoints)
- [Billing Endpoints](#billing-endpoints)
- [Admin Endpoints](#admin-endpoints)
- [Webhooks](#webhooks)

## Overview

The nabavkidata.com API is a RESTful API that provides access to Macedonian public procurement data, AI-powered search, and tender intelligence features.

### API Version

Current version: **v1**

All endpoints are prefixed with `/api/v1/` (currently `/api/` is accepted but will be deprecated).

### Content Type

All requests and responses use `application/json` unless otherwise specified.

### Interactive Documentation

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI Spec**: http://localhost:8000/api/openapi.json

## Base URL

| Environment | Base URL |
|-------------|----------|
| Production | `https://api.nabavkidata.com` |
| Staging | `https://api-staging.nabavkidata.com` |
| Development | `http://localhost:8000` |

## Authentication

### JWT Bearer Token

All authenticated endpoints require a JWT token in the `Authorization` header:

```http
Authorization: Bearer <access_token>
```

### Obtaining Tokens

1. **Register** a new account: `POST /api/auth/register`
2. **Login** to get tokens: `POST /api/auth/login`
3. **Refresh** expired token: `POST /api/auth/refresh`

### Token Expiry

- **Access Token**: 30 minutes
- **Refresh Token**: 7 days

### Example: Getting Authenticated

```bash
# 1. Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=yourpassword"

# Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "full_name": "John Doe",
    "subscription_tier": "pro"
  }
}

# 2. Use access token for authenticated requests
curl http://localhost:8000/api/tenders \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## Rate Limiting

### Limits by Tier

| Tier | Requests/Minute | Burst | AI Queries/Month |
|------|----------------|-------|------------------|
| Free | 10 | 20 | 5 |
| Pro | 60 | 100 | 100 |
| Premium | 300 | 500 | Unlimited |

### Rate Limit Headers

Every API response includes rate limit information:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1704564000
```

### Rate Limit Exceeded Response

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please try again later.",
    "retry_after": 60
  }
}
```

## Response Format

### Success Response

**List Response:**

```json
{
  "total": 150,
  "page": 1,
  "page_size": 20,
  "items": [
    { ... },
    { ... }
  ]
}
```

**Single Resource:**

```json
{
  "tender_id": "2024/123",
  "title": "IT Services Procurement",
  "status": "open",
  ...
}
```

### Pagination

Query parameters:
- `page`: Page number (1-indexed, default: 1)
- `page_size`: Items per page (default: 20, max: 100)

Example:
```http
GET /api/tenders?page=2&page_size=50
```

## Error Codes

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Request successful |
| 201 | Created - Resource created |
| 400 | Bad Request - Invalid request data |
| 401 | Unauthorized - Missing or invalid token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 422 | Unprocessable Entity - Validation error |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

### Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request data",
    "details": {
      "field": "email",
      "error": "Invalid email format"
    }
  }
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `AUTHENTICATION_FAILED` | Invalid credentials |
| `TOKEN_EXPIRED` | JWT token expired |
| `INVALID_REQUEST` | Malformed request |
| `VALIDATION_ERROR` | Field validation failed |
| `RESOURCE_NOT_FOUND` | Requested resource not found |
| `PERMISSION_DENIED` | Insufficient permissions |
| `RATE_LIMIT_EXCEEDED` | Too many requests |
| `TIER_LIMIT_EXCEEDED` | Subscription tier limit reached |
| `SERVICE_UNAVAILABLE` | External service unavailable |

## Authentication Endpoints

### Register New User

**Endpoint:** `POST /api/auth/register`

**Description:** Create a new user account.

**Request Body:**

```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "full_name": "John Doe"
}
```

**Validation:**
- Email: Valid email format, unique
- Password: Min 8 characters, recommended: uppercase, lowercase, number, symbol
- Full Name: Optional, max 255 characters

**Response:** `201 Created`

```json
{
  "message": "Registration successful",
  "detail": "Please check your email to verify your account"
}
```

**Rate Limit:** 5 registrations per hour per IP

---

### Login

**Endpoint:** `POST /api/auth/login`

**Description:** Authenticate user and receive JWT tokens.

**Request Body:** (Form-encoded)

```
username=user@example.com
password=SecurePassword123!
```

**Response:** `200 OK`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "full_name": "John Doe",
    "subscription_tier": "pro",
    "email_verified": true,
    "created_at": "2024-01-15T10:00:00Z"
  }
}
```

**Rate Limit:** 5 login attempts per minute per IP

---

### Refresh Token

**Endpoint:** `POST /api/auth/refresh`

**Description:** Get new access token using refresh token.

**Request Body:**

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:** `200 OK`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": { ... }
}
```

---

### Get Current User

**Endpoint:** `GET /api/auth/me`

**Authentication:** Required

**Response:** `200 OK`

```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "full_name": "John Doe",
  "subscription_tier": "pro",
  "email_verified": true,
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-20T14:30:00Z"
}
```

---

### Update Profile

**Endpoint:** `PATCH /api/auth/me`

**Authentication:** Required

**Request Body:**

```json
{
  "full_name": "John Smith"
}
```

**Response:** `200 OK`

```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "full_name": "John Smith",
  "subscription_tier": "pro"
}
```

---

### Change Password

**Endpoint:** `POST /api/auth/change-password`

**Authentication:** Required

**Request Body:**

```json
{
  "current_password": "OldPassword123!",
  "new_password": "NewPassword456!"
}
```

**Response:** `200 OK`

```json
{
  "message": "Password changed successfully",
  "detail": "Please login with your new password"
}
```

---

### Forgot Password

**Endpoint:** `POST /api/auth/forgot-password`

**Request Body:**

```json
{
  "email": "user@example.com"
}
```

**Response:** `200 OK`

```json
{
  "message": "Password reset email sent",
  "detail": "Please check your email for reset instructions"
}
```

**Rate Limit:** 3 requests per hour per email

---

### Logout

**Endpoint:** `POST /api/auth/logout`

**Authentication:** Required

**Response:** `200 OK`

```json
{
  "message": "Logout successful",
  "detail": "Please remove tokens from client storage"
}
```

## Tender Endpoints

### List Tenders

**Endpoint:** `GET /api/tenders`

**Description:** Get paginated list of tenders with filtering.

**Query Parameters:**

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `page` | integer | Page number (1-indexed) | 1 |
| `page_size` | integer | Items per page (max 100) | 20 |
| `category` | string | Filter by category | - |
| `status` | string | Filter by status (open, closed, awarded) | - |
| `procuring_entity` | string | Filter by procuring entity (partial match) | - |
| `cpv_code` | string | Filter by CPV code (prefix match) | - |
| `sort_by` | string | Sort field (created_at, closing_date, estimated_value_mkd) | created_at |
| `sort_order` | string | Sort direction (asc, desc) | desc |

**Example Request:**

```bash
GET /api/tenders?page=1&page_size=20&status=open&category=IT&sort_by=closing_date&sort_order=asc
```

**Response:** `200 OK`

```json
{
  "total": 150,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "tender_id": "2024/123",
      "title": "IT Infrastructure Upgrade",
      "description": "Procurement of servers, networking equipment...",
      "category": "IT",
      "procuring_entity": "Ministry of Finance",
      "opening_date": "2024-02-01",
      "closing_date": "2024-02-15",
      "publication_date": "2024-01-15",
      "estimated_value_mkd": 5000000.00,
      "estimated_value_eur": 81000.00,
      "status": "open",
      "cpv_code": "48000000",
      "source_url": "https://e-nabavki.gov.mk/tender/2024/123",
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-15T10:00:00Z"
    },
    ...
  ]
}
```

---

### Get Tender by ID

**Endpoint:** `GET /api/tenders/{tender_id}`

**Path Parameters:**
- `tender_id`: Tender ID (e.g., "2024/123")

**Response:** `200 OK`

```json
{
  "tender_id": "2024/123",
  "title": "IT Infrastructure Upgrade",
  "description": "Full detailed description...",
  "category": "IT",
  "procuring_entity": "Ministry of Finance",
  "opening_date": "2024-02-01",
  "closing_date": "2024-02-15",
  "publication_date": "2024-01-15",
  "estimated_value_mkd": 5000000.00,
  "estimated_value_eur": 81000.00,
  "actual_value_mkd": null,
  "actual_value_eur": null,
  "cpv_code": "48000000",
  "status": "open",
  "winner": null,
  "source_url": "https://e-nabavki.gov.mk/tender/2024/123",
  "language": "mk",
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:00:00Z",
  "scraped_at": "2024-01-15T09:30:00Z"
}
```

**Error Response:** `404 Not Found`

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Tender not found"
  }
}
```

---

### Advanced Tender Search

**Endpoint:** `POST /api/tenders/search`

**Description:** Advanced search with multiple filter criteria.

**Request Body:**

```json
{
  "query": "IT services",
  "category": "IT",
  "status": "open",
  "procuring_entity": "Ministry",
  "cpv_code": "48",
  "min_value_mkd": 100000,
  "max_value_mkd": 10000000,
  "opening_date_from": "2024-01-01",
  "opening_date_to": "2024-12-31",
  "closing_date_from": "2024-02-01",
  "closing_date_to": "2024-03-31",
  "page": 1,
  "page_size": 20,
  "sort_by": "closing_date",
  "sort_order": "asc"
}
```

**Response:** `200 OK`

```json
{
  "total": 45,
  "page": 1,
  "page_size": 20,
  "items": [ ... ]
}
```

---

### Get Tender Statistics

**Endpoint:** `GET /api/tenders/stats/overview`

**Description:** Get aggregate statistics about tenders.

**Response:** `200 OK`

```json
{
  "total_tenders": 1250,
  "open_tenders": 340,
  "closed_tenders": 910,
  "total_value_mkd": 15000000000.00,
  "avg_value_mkd": 12000000.00,
  "tenders_by_category": {
    "IT": 245,
    "Construction": 180,
    "Healthcare": 120,
    "Services": 305,
    "Goods": 400
  }
}
```

---

### Get Recent Tenders

**Endpoint:** `GET /api/tenders/stats/recent`

**Query Parameters:**
- `limit`: Number of tenders (default: 10, max: 50)

**Response:** `200 OK`

```json
{
  "count": 10,
  "tenders": [ ... ]
}
```

## Document Endpoints

### List Documents for Tender

**Endpoint:** `GET /api/documents`

**Query Parameters:**
- `tender_id`: Filter by tender ID (required)
- `doc_type`: Filter by document type (optional)

**Response:** `200 OK`

```json
{
  "total": 5,
  "items": [
    {
      "doc_id": "doc-uuid-1234",
      "tender_id": "2024/123",
      "doc_type": "Specification",
      "file_name": "technical_specification.pdf",
      "file_url": "https://e-nabavki.gov.mk/docs/...",
      "file_size_bytes": 2500000,
      "mime_type": "application/pdf",
      "page_count": 45,
      "extraction_status": "success",
      "created_at": "2024-01-15T10:00:00Z"
    },
    ...
  ]
}
```

---

### Get Document by ID

**Endpoint:** `GET /api/documents/{doc_id}`

**Response:** `200 OK`

```json
{
  "doc_id": "doc-uuid-1234",
  "tender_id": "2024/123",
  "doc_type": "Specification",
  "file_name": "technical_specification.pdf",
  "file_path": "/storage/docs/2024/123/spec.pdf",
  "file_url": "https://e-nabavki.gov.mk/docs/...",
  "content_text": "Full extracted text content...",
  "file_size_bytes": 2500000,
  "mime_type": "application/pdf",
  "page_count": 45,
  "extraction_status": "success",
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:05:00Z"
}
```

---

### Download Document

**Endpoint:** `GET /api/documents/{doc_id}/download`

**Authentication:** Required (Pro tier+)

**Response:** `200 OK` (Binary PDF file)

**Headers:**
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="technical_specification.pdf"
```

## RAG/AI Endpoints

### Ask Question (RAG Query)

**Endpoint:** `POST /api/rag/query`

**Description:** Ask natural language question and get AI-generated answer with source citations.

**Authentication:** Required

**Tier Limits:**
- Free: 5 queries/month
- Pro: 100 queries/month
- Premium: Unlimited

**Request Body:**

```json
{
  "question": "What are the technical requirements for IT tenders in Q1 2024?",
  "tender_id": null,
  "top_k": 5,
  "conversation_history": [
    {
      "question": "Previous question",
      "answer": "Previous answer"
    }
  ]
}
```

**Fields:**
- `question` (required): User question in Macedonian or English
- `tender_id` (optional): Limit search to specific tender
- `top_k` (optional): Number of chunks to retrieve (1-20, default: 5)
- `conversation_history` (optional): Previous Q&A for context

**Response:** `200 OK`

```json
{
  "question": "What are the technical requirements for IT tenders in Q1 2024?",
  "answer": "Based on the analyzed tenders, the main technical requirements include:\n\n1. Server infrastructure with minimum 64GB RAM [Tender 2024/045]\n2. Network equipment supporting 10Gbps [Tender 2024/067]\n3. Security compliance with ISO 27001 [Tender 2024/089]\n\nThe procuring entities emphasize compatibility with existing infrastructure and 3-year warranty coverage.",
  "sources": [
    {
      "tender_id": "2024/045",
      "doc_id": "doc-uuid-5678",
      "chunk_text": "Technical requirements: Server infrastructure must include minimum 64GB RAM, dual CPU configuration...",
      "similarity": 0.89,
      "metadata": {
        "page": 5,
        "section": "Technical Specifications"
      }
    },
    ...
  ],
  "confidence": "high",
  "query_time_ms": 2340,
  "generated_at": "2024-01-22T10:30:00Z"
}
```

**Confidence Levels:**
- `high`: Similarity > 0.8, multiple relevant sources
- `medium`: Similarity 0.6-0.8, some relevant sources
- `low`: Similarity < 0.6, limited sources

**Error Response:** `403 Forbidden` (Tier limit exceeded)

```json
{
  "error": {
    "code": "TIER_LIMIT_EXCEEDED",
    "message": "Monthly query limit exceeded",
    "detail": "Free tier allows 5 queries/month. Upgrade to Pro for 100 queries/month."
  }
}
```

---

### Semantic Search

**Endpoint:** `POST /api/rag/search`

**Description:** Vector-based semantic search without answer generation.

**Request Body:**

```json
{
  "query": "cloud infrastructure requirements",
  "tender_id": null,
  "top_k": 10
}
```

**Response:** `200 OK`

```json
{
  "query": "cloud infrastructure requirements",
  "total_results": 10,
  "results": [
    {
      "tender_id": "2024/123",
      "doc_id": "doc-uuid-1234",
      "chunk_text": "Cloud infrastructure must support hybrid deployment...",
      "chunk_index": 5,
      "similarity": 0.92,
      "metadata": {
        "page": 12,
        "section": "Infrastructure Requirements"
      }
    },
    ...
  ]
}
```

---

### Embed Document

**Endpoint:** `POST /api/rag/embed/document`

**Description:** Generate embeddings for document text.

**Authentication:** Required (Admin only)

**Request Body:**

```json
{
  "tender_id": "2024/123",
  "doc_id": "doc-uuid-1234",
  "text": "Full document text to embed...",
  "metadata": {
    "doc_type": "Specification",
    "page_count": 45
  }
}
```

**Response:** `200 OK`

```json
{
  "success": true,
  "tender_id": "2024/123",
  "doc_id": "doc-uuid-1234",
  "embed_count": 45,
  "embed_ids": [
    "embed-uuid-1",
    "embed-uuid-2",
    ...
  ]
}
```

---

### RAG Health Check

**Endpoint:** `GET /api/rag/health`

**Response:** `200 OK`

```json
{
  "status": "healthy",
  "rag_enabled": true,
  "openai_configured": true,
  "database_configured": true,
  "service": "rag-api"
}
```

## Billing Endpoints

### List Subscription Plans

**Endpoint:** `GET /api/billing/plans`

**Response:** `200 OK`

```json
{
  "plans": [
    {
      "plan_id": "free",
      "name": "Free",
      "price_mkd": 0,
      "price_eur": 0,
      "features": [
        "Basic tender search",
        "5 RAG queries per month",
        "1 saved alert",
        "Email support"
      ],
      "limits": {
        "rag_queries_per_month": 5,
        "saved_alerts": 1,
        "export_results": false
      }
    },
    {
      "plan_id": "pro",
      "name": "Pro",
      "price_mkd": 999,
      "price_eur": 16.99,
      "features": [
        "Advanced search & filters",
        "100 RAG queries per month",
        "10 saved alerts",
        "Export to CSV/PDF",
        "Priority email support"
      ],
      "limits": {
        "rag_queries_per_month": 100,
        "saved_alerts": 10,
        "export_results": true
      }
    },
    {
      "plan_id": "premium",
      "name": "Premium",
      "price_mkd": 2499,
      "price_eur": 39.99,
      "features": [
        "Unlimited RAG queries",
        "Unlimited saved alerts",
        "API access",
        "Advanced analytics",
        "Dedicated support"
      ],
      "limits": {
        "rag_queries_per_month": -1,
        "saved_alerts": -1,
        "export_results": true,
        "api_access": true
      }
    }
  ]
}
```

---

### Create Checkout Session

**Endpoint:** `POST /api/billing/checkout`

**Authentication:** Required

**Request Body:**

```json
{
  "plan": "pro",
  "success_url": "https://nabavkidata.com/billing/success",
  "cancel_url": "https://nabavkidata.com/billing/cancelled"
}
```

**Response:** `200 OK`

```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_..."
}
```

**Rate Limit:** 5 checkout sessions per hour per user

---

### Get Customer Portal

**Endpoint:** `POST /api/billing/portal`

**Description:** Get Stripe customer portal link for managing subscription.

**Authentication:** Required

**Response:** `200 OK`

```json
{
  "portal_url": "https://billing.stripe.com/p/session/..."
}
```

---

### Stripe Webhook Handler

**Endpoint:** `POST /api/billing/webhook`

**Description:** Stripe webhook handler for subscription events.

**Headers:**
- `Stripe-Signature`: Webhook signature for verification

**Events Handled:**
- `checkout.session.completed`: Subscription created
- `customer.subscription.updated`: Subscription modified
- `customer.subscription.deleted`: Subscription cancelled
- `invoice.payment_succeeded`: Payment successful
- `invoice.payment_failed`: Payment failed

**Response:** `200 OK`

```json
{
  "received": true
}
```

## Admin Endpoints

### Get All Users

**Endpoint:** `GET /api/admin/users`

**Authentication:** Required (Admin role)

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20)
- `tier`: Filter by subscription tier
- `is_active`: Filter by active status

**Response:** `200 OK`

```json
{
  "total": 1250,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "user_id": "uuid-1234",
      "email": "user@example.com",
      "full_name": "John Doe",
      "subscription_tier": "pro",
      "email_verified": true,
      "created_at": "2024-01-15T10:00:00Z",
      "last_login": "2024-01-22T08:30:00Z"
    },
    ...
  ]
}
```

---

### Get System Analytics

**Endpoint:** `GET /api/admin/analytics`

**Authentication:** Required (Admin role)

**Response:** `200 OK`

```json
{
  "users": {
    "total": 1250,
    "active": 890,
    "by_tier": {
      "free": 800,
      "pro": 350,
      "premium": 100
    }
  },
  "tenders": {
    "total": 15000,
    "open": 340,
    "this_month": 125
  },
  "queries": {
    "total": 45000,
    "this_month": 3500,
    "avg_per_user": 36
  },
  "revenue_mkd": 1500000.00
}
```

---

### View Audit Logs

**Endpoint:** `GET /api/admin/logs`

**Authentication:** Required (Admin role)

**Query Parameters:**
- `action`: Filter by action type
- `user_id`: Filter by user
- `start_date`: From date
- `end_date`: To date
- `page`: Page number
- `page_size`: Items per page

**Response:** `200 OK`

```json
{
  "total": 5000,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "log_id": "log-uuid-1234",
      "user_id": "user-uuid-5678",
      "action": "user_login",
      "details": {
        "email": "user@example.com"
      },
      "ip_address": "192.168.1.100",
      "created_at": "2024-01-22T10:00:00Z"
    },
    ...
  ]
}
```

## Webhooks

### Configuring Webhooks

Webhooks allow you to receive real-time notifications about events in your account.

**Supported Events:**
- `tender.created`: New tender added
- `tender.updated`: Tender information updated
- `alert.triggered`: User alert matched a tender
- `subscription.changed`: Subscription tier changed

### Webhook Payload

**Example: tender.created**

```json
{
  "event": "tender.created",
  "timestamp": "2024-01-22T10:00:00Z",
  "data": {
    "tender_id": "2024/123",
    "title": "IT Infrastructure Upgrade",
    "category": "IT",
    "procuring_entity": "Ministry of Finance",
    "closing_date": "2024-02-15"
  }
}
```

### Webhook Security

All webhooks include a signature in the `X-Webhook-Signature` header for verification:

```python
import hmac
import hashlib

def verify_webhook(payload, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)
```

---

**API Documentation Version**: 1.0
**Last Updated**: 2025-01-22
**For Support**: api-support@nabavkidata.com
