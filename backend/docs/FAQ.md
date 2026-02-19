# Frequently Asked Questions (FAQ)

> Common questions about nabavkidata.com

## Table of Contents

- [General Questions](#general-questions)
- [Technical Questions](#technical-questions)
- [Subscription & Billing](#subscription--billing)
- [API Usage](#api-usage)
- [Data & Privacy](#data--privacy)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

## General Questions

### What is nabavkidata.com?

nabavkidata.com is an AI-powered tender intelligence platform for Macedonian public procurement. It scrapes, processes, and analyzes tender data from e-nabavki.gov.mk, providing smart search, alerts, and insights.

### Who is this platform for?

- **Businesses**: Find relevant tender opportunities
- **Procurement professionals**: Monitor procuring entities
- **Consultants**: Analyze procurement trends
- **Researchers**: Study public procurement data
- **Developers**: Access tender data via API

### What data sources does it use?

Primary data source: **e-nabavki.gov.mk** (official Macedonian public procurement portal)

We scrape:
- Tender announcements
- Technical specifications
- Contract awards
- PDF documents

### Is the data real-time?

Data is updated:
- **Daily scrapes**: Every night at 2:00 AM
- **Incremental updates**: Every 6 hours
- **Typical delay**: 0-6 hours from source publication

### How accurate is the data?

Data accuracy depends on:
- Source data quality (e-nabavki.gov.mk)
- PDF extraction success (95%+ accuracy)
- Document structure changes

We continuously monitor extraction success rates and adapt to changes.

### What languages are supported?

- **Interface**: English (Macedonian UI planned for v1.1)
- **Data**: Macedonian (native language of tenders)
- **AI Search**: Both Macedonian and English queries

## Technical Questions

### What technology stack is used?

**Backend:**
- FastAPI (Python 3.11+)
- PostgreSQL 16 with pgvector
- Redis 7
- OpenAI/Gemini for AI

**Frontend:**
- Next.js 14
- React 18
- TypeScript
- Tailwind CSS

**Scraping:**
- Scrapy
- Playwright
- PyMuPDF, pdfminer

See [Architecture](ARCHITECTURE.md) for details.

### How does the AI search work?

Our RAG (Retrieval Augmented Generation) pipeline:

1. **Document Processing**: Extract text from PDFs, chunk into segments
2. **Embedding**: Convert text to vectors using OpenAI embeddings
3. **Storage**: Store vectors in PostgreSQL with pgvector
4. **Query**: Convert user question to vector
5. **Search**: Find similar chunks via cosine similarity
6. **Generate**: Feed context to LLM (Gemini/GPT-4) for answer

### How many tenders are in the database?

Current status (as of January 2025):
- **Total tenders**: 15,000+
- **Open tenders**: 300-400 (varies)
- **Historical data**: Back to 2020
- **Growth rate**: ~125 new tenders/month

### Can I export data?

Yes, for Pro and Premium tiers:
- **Formats**: CSV, JSON, PDF (Premium only)
- **Limits**:
  - Pro: 100 exports/month
  - Premium: Unlimited
- **API Access**: Premium tier includes API access

### Is there a mobile app?

Not yet. Mobile app (React Native) is planned for Q1 2025.

Current web app is mobile-responsive and works on all devices.

### Does it work offline?

No, the platform requires internet connection for:
- Real-time data access
- AI search queries
- Authentication

Offline mode is not planned.

## Subscription & Billing

### What subscription plans are available?

| Feature | Free | Pro (€16.99/mo) | Premium (€39.99/mo) |
|---------|------|-----------------|---------------------|
| Tender search | ✓ | ✓ | ✓ |
| AI queries | 5/month | 100/month | Unlimited |
| Saved alerts | 1 | 10 | Unlimited |
| Export | - | CSV/PDF | All formats |
| API access | - | - | ✓ |
| Support | Email | Priority | Dedicated |

### How do I upgrade my plan?

1. Log in to your account
2. Go to **Settings → Billing**
3. Click **Upgrade Plan**
4. Select desired plan
5. Enter payment details (Stripe)
6. Confirm upgrade

Upgrade takes effect immediately. Prorated charges apply.

### Can I downgrade my plan?

Yes:
1. Go to **Settings → Billing**
2. Click **Manage Subscription**
3. Select **Change Plan**
4. Choose lower tier

Downgrade takes effect at the end of current billing period.

### What payment methods are accepted?

Via Stripe:
- Credit/debit cards (Visa, Mastercard, Amex)
- Google Pay
- Apple Pay

Payments in EUR. Macedonian businesses: Contact us for MKD invoicing.

### Is there a refund policy?

- **Free tier**: No charges, no refunds needed
- **Paid tiers**: 14-day money-back guarantee
- **Annual plans**: Prorated refunds for cancellations

Contact support@nabavkidata.com for refund requests.

### Can I get an invoice?

Yes. Invoices are automatically:
- Sent via email after each payment
- Available in **Settings → Billing → Invoices**
- Include VAT (if applicable)

Need custom invoicing? Contact billing@nabavkidata.com.

## API Usage

### How do I get API access?

API access is included in **Premium tier** only.

After subscribing:
1. Go to **Settings → API Keys**
2. Click **Generate API Key**
3. Save the key securely (shown once)
4. Use in requests: `Authorization: Bearer YOUR_API_KEY`

### What are the API rate limits?

| Tier | Rate Limit | Burst |
|------|-----------|-------|
| Free | 10 req/min | 20 |
| Pro | 60 req/min | 100 |
| Premium | 300 req/min | 500 |

Exceeding limits returns `429 Too Many Requests`.

### Is there API documentation?

Yes, comprehensive API docs:
- **OpenAPI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **Written docs**: [API.md](API.md)

### Can I use the API for commercial purposes?

Yes, with Premium subscription. Commercial use includes:
- Building applications on top of our API
- Reselling data or insights
- Integration with commercial products

Free/Pro tiers: Personal use only.

### Are there SDKs available?

Currently: No official SDKs

Planned: Python and JavaScript SDKs (Q2 2025)

For now, use standard HTTP clients:
```bash
# Python
import requests
response = requests.get(
    "https://api.nabavkidata.com/tenders",
    headers={"Authorization": "Bearer YOUR_TOKEN"}
)

# JavaScript
fetch("https://api.nabavkidata.com/tenders", {
    headers: { "Authorization": "Bearer YOUR_TOKEN" }
})
```

## Data & Privacy

### How is my data protected?

**Security measures:**
- Passwords: bcrypt hashing (cost 12)
- Data in transit: TLS 1.3 (HTTPS)
- Data at rest: PostgreSQL encryption
- API: JWT authentication
- Audit logging: All critical actions logged

See our [Privacy Policy](https://nabavkidata.com/privacy) for details.

### What personal data do you collect?

We collect:
- **Account**: Email, name, password (hashed)
- **Usage**: Query history, search terms, alerts
- **Billing**: Stripe customer ID (not full card details)
- **Analytics**: Page views, feature usage

We do NOT collect:
- Social security numbers
- Full payment details (handled by Stripe)
- Biometric data
- Location tracking

### Is my data shared with third parties?

**We share data with:**
- **Stripe**: For payment processing
- **OpenAI/Google**: For AI queries (anonymized)
- **Email provider**: For transactional emails

**We do NOT:**
- Sell your data
- Share with advertisers
- Provide data to third parties without consent

### Can I delete my account and data?

Yes, GDPR-compliant deletion:
1. Go to **Settings → Account**
2. Click **Delete Account**
3. Confirm deletion
4. Data removed within 30 days

Includes:
- Account information
- Search history
- Saved alerts
- Billing history (anonymized after 7 years for tax compliance)

### Where is data stored?

- **Primary servers**: EU region (GDPR compliant)
- **Database backups**: EU region
- **CDN**: Global (for static assets)

Data does not leave EU without encryption and adequate safeguards.

## Troubleshooting

### Login Issues

**Problem**: Can't log in

**Solutions:**
1. Check email/password are correct
2. Try "Forgot Password" to reset
3. Verify email is confirmed (check spam folder)
4. Clear browser cache and cookies
5. Try different browser

**Still not working?** Contact support@nabavkidata.com

### Search Not Working

**Problem**: Search returns no results

**Possible causes:**
1. Too specific search query
2. Recent tender (not yet scraped)
3. Filters too restrictive

**Try:**
- Broaden search terms
- Remove some filters
- Try Macedonian keywords
- Check "Open" tenders filter is not excluding everything

### AI Search Returns "I don't have enough information"

**Reasons:**
1. Query too specific/niche
2. Relevant documents not yet processed
3. Embeddings not generated for that tender

**Solutions:**
- Rephrase question more broadly
- Try keyword-based search instead
- Check if tender is very recent (<24 hours)

### Export Failing

**Problem**: Export download fails

**Check:**
1. Subscription tier (Pro+ required)
2. Export limit not exceeded
3. Browser allows downloads
4. Stable internet connection

### "Rate Limit Exceeded" Error

**Cause**: Too many requests

**Solutions:**
1. Wait for rate limit window to reset (check `Retry-After` header)
2. Reduce request frequency
3. Implement exponential backoff
4. Upgrade tier for higher limits

### "Tier Limit Exceeded" for AI Queries

**Cause**: Monthly AI query limit reached

**Options:**
1. Wait for next billing cycle reset
2. Upgrade to higher tier:
   - Pro: 100 queries/month
   - Premium: Unlimited

### Email Notifications Not Received

**Check:**
1. Spam/junk folder
2. Email settings in **Settings → Notifications**
3. Email verification completed
4. Email provider not blocking our domain

**Whitelist**: noreply@nabavkidata.com

## Development

### How do I set up local development?

See [DEVELOPMENT.md](DEVELOPMENT.md) for complete guide.

Quick start:
```bash
git clone https://github.com/nabavkidata/nabavkidata.git
cd nabavkidata
cp .env.example .env
# Edit .env with your API keys
docker-compose up -d
```

### Where is the source code?

**Public Repository**: https://github.com/nabavkidata/nabavkidata

Licensed under MIT. See [LICENSE](../LICENSE).

### How can I contribute?

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md).

Quick checklist:
1. Fork repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request
5. Pass code review

### Can I self-host?

Yes, it's open source!

Requirements:
- PostgreSQL 16+ with pgvector
- Redis 7+
- OpenAI API key
- 4GB RAM minimum

See deployment docs for detailed instructions.

### Is there a Docker image?

Yes, Dockerfiles included for:
- Backend (FastAPI)
- Frontend (Next.js)
- Scraper (Scrapy)

Docker Compose setup for local development.

Kubernetes manifests in `/k8s` directory.

### How do I report a bug?

1. Check [existing issues](https://github.com/nabavkidata/nabavkidata/issues)
2. Create new issue with:
   - Clear description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details
3. Add relevant labels

See [CONTRIBUTING.md](CONTRIBUTING.md) for bug report template.

### How do I request a feature?

1. Check [roadmap](../README.md#roadmap)
2. Open GitHub Discussion or Issue
3. Describe:
   - Use case
   - Proposed solution
   - Benefits
4. Engage with community feedback

Popular requests are prioritized in roadmap.

---

## Still Have Questions?

**Documentation:**
- [README](../README.md) - Project overview
- [Architecture](ARCHITECTURE.md) - System design
- [API Docs](API.md) - API reference
- [Development Guide](DEVELOPMENT.md) - Setup and development

**Contact:**
- **General**: support@nabavkidata.com
- **Technical**: dev@nabavkidata.com
- **Billing**: billing@nabavkidata.com
- **Security**: security@nabavkidata.com
- **Discord**: https://discord.gg/nabavkidata

**Response Time:**
- Free tier: 48-72 hours
- Pro tier: 24 hours
- Premium tier: 4-8 hours

---

**FAQ Version**: 1.0
**Last Updated**: 2025-01-22
