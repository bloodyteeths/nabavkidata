# NabavkiData -- Budget Proposal

## National Endowment for Democracy Grant Application

**Applicant:** Facturino DOOEL Veles
**Project Title:** Strengthening Civic Oversight of Public Procurement in North Macedonia Through AI-Driven Corruption Detection
**Requested Amount:** $150,000 USD
**Project Duration:** 12 months
**Budget Period:** September 2026 -- August 2027

---

## Budget Summary

| Category | Amount (USD) | % of Total |
|----------|-------------|------------|
| A. Personnel | $96,000 | 64.0% |
| B. Technology and Infrastructure | $18,600 | 12.4% |
| C. Outreach, Training, and Events | $19,800 | 13.2% |
| D. Administrative and Operational | $10,200 | 6.8% |
| E. Monitoring and Evaluation | $5,400 | 3.6% |
| **Total** | **$150,000** | **100.0%** |

---

## A. Personnel -- $96,000 (64.0%)

Personnel costs reflect competitive rates for the North Macedonian labor market, where NabavkiData's technical team is based. All personnel are engaged on a contract basis through Facturino DOOEL Veles.

| Position | Level of Effort | Monthly Rate (USD) | Months | Total (USD) |
|----------|----------------|-------------------|--------|-------------|
| **Senior Full-Stack Developer** | Full-time (100%) | $3,000 | 12 | $36,000 |
| **ML/Data Engineer** | Full-time (100%) | $3,000 | 12 | $36,000 |
| **Data Analyst / Researcher** | Full-time (100%) | $1,500 | 12 | $18,000 |
| **Project Manager** | Part-time (50%) | $500 | 12 | $6,000 |
| **Subtotal** | | | | **$96,000** |

### Position Descriptions

**Senior Full-Stack Developer ($3,000/month)**
Responsible for maintaining and expanding the NabavkiData platform, including the Next.js frontend, FastAPI backend, PostgreSQL database, and Scrapy scraping infrastructure. Key deliverables include the Investigation Dashboard, API development, tip submission system, and cross-border entity matching integration. This role requires expertise in Python, TypeScript, React, and database optimization. The developer has been building the platform since inception and possesses deep institutional knowledge of the codebase and data architecture.

**ML/Data Engineer ($3,000/month)**
Responsible for the AI/ML corruption detection pipeline: feature extraction (150+ features across 7 categories), model training (Random Forest, XGBoost, Graph Neural Networks), SHAP/LIME explainability, and real-time scoring. Key deliverables include model retraining on labeled ground truth data, cross-border entity matching with multilingual NLP, collusion network detection via GNN, and automated evidence package generation. This role requires expertise in scikit-learn, PyTorch, PyTorch Geometric, asyncpg, and statistical analysis.

**Data Analyst / Researcher ($1,500/month)**
Responsible for analyzing detection results, validating risk flags against known corruption cases, preparing quarterly Procurement Integrity Reports, producing open datasets, and drafting the policy brief. Also responsible for stakeholder mapping, training curriculum development, and monitoring media coverage of NabavkiData findings. Supports workshop facilitation and coalition building. This role requires expertise in data analysis, procurement regulation, Macedonian language proficiency, and familiarity with North Macedonian governance structures.

**Project Manager ($500/month, part-time)**
Responsible for overall project coordination, reporting to NED, budget management, stakeholder communications, event logistics, and M&E framework implementation. Oversees timeline adherence, manages subcontractor relationships, and ensures deliverable quality. This role is staffed at 50% because project management functions are partially shared with the existing team lead.

---

## B. Technology and Infrastructure -- $18,600 (12.4%)

NabavkiData's current infrastructure costs are minimal due to efficient architecture choices. This budget line covers the scaling required for real-time monitoring, expanded ML processing, and increased user traffic.

| Item | Unit Cost (USD) | Units/Months | Total (USD) |
|------|----------------|-------------|-------------|
| **AWS EC2 (application server, upgraded)** | $120/month | 12 | $1,440 |
| **AWS RDS PostgreSQL (database, upgraded)** | $150/month | 12 | $1,800 |
| **Google Gemini AI API (embeddings, RAG)** | $300/month | 12 | $3,600 |
| **AWS S3 (document storage and backups)** | $50/month | 12 | $600 |
| **Vercel Pro (frontend hosting)** | $20/month | 12 | $240 |
| **Domain and SSL certificates** | $120/year | 1 | $120 |
| **GPU compute for GNN training (AWS/GCP)** | $200/session | 12 sessions | $2,400 |
| **Cross-border data acquisition and APIs** | -- | -- | $3,000 |
| **Security audit (external penetration test)** | $2,500 | 1 | $2,500 |
| **Development tools and licenses** | $75/month | 12 | $900 |
| **Backup and disaster recovery** | $250/quarter | 4 | $1,000 |
| **CDN and DDoS protection** | $1,000/year | 1 | $1,000 |
| **Subtotal** | | | **$18,600** |

### Notes on Technology Costs

- **AWS EC2 upgrade:** The current t3.micro instance ($50/month) is upgraded to a t3.medium ($120/month) to support real-time ML inference, concurrent scraping, and increased API traffic.
- **AWS RDS upgrade:** The database is upgraded from db.t3.micro to db.t3.small to handle expanded indices, materialized views, and concurrent query load from the Investigation Dashboard.
- **Gemini AI API:** Costs cover embedding generation for new tenders and documents, RAG-based natural language search, and AI-powered document analysis. Current usage is $200/month; projected increase reflects expanded document processing and user query volume.
- **GPU compute:** Graph Neural Network training requires GPU acceleration. Rather than maintaining a dedicated GPU server, the project uses on-demand cloud GPU instances (AWS p3.2xlarge or GCP T4) for periodic model retraining sessions.
- **Cross-border data acquisition:** Covers API access fees, web scraping infrastructure, and data licensing for procurement data from Serbia, Kosovo, Albania, Montenegro, Bosnia, and Croatia.
- **Security audit:** An external penetration test by a qualified cybersecurity firm ensures the platform meets security standards appropriate for a system handling sensitive corruption data.

---

## C. Outreach, Training, and Events -- $19,800 (13.2%)

| Item | Unit Cost (USD) | Units | Total (USD) |
|------|----------------|-------|-------------|
| **Regional training workshops (6 cities)** | $1,800/workshop | 6 | $10,800 |
| **Quarterly Procurement Integrity Reports** | $600/report | 4 | $2,400 |
| **Media outreach and press materials** | $500/quarter | 4 | $2,000 |
| **Conference attendance and presentations** | $1,500/conference | 2 | $3,000 |
| **Printed training materials and guides** | $100/workshop | 6 | $600 |
| **Coalition building events** | $500 | 2 | $1,000 |
| **Subtotal** | | | **$19,800** |

### Workshop Budget Breakdown (per workshop, $1,800)

| Item | Cost (USD) |
|------|-----------|
| Venue rental (half-day) | $400 |
| Catering (20 participants) | $300 |
| Travel for trainers (2 people) | $400 |
| Participant travel stipends (regional attendees) | $300 |
| A/V equipment rental | $150 |
| Printed materials and handouts | $100 |
| Miscellaneous (signage, supplies) | $150 |
| **Total per workshop** | **$1,800** |

### Conference Attendance Breakdown (per conference, $1,500)

| Item | Cost (USD) |
|------|-----------|
| Registration fee | $300 |
| Round-trip airfare (regional) | $500 |
| Hotel (3 nights) | $450 |
| Per diem (3 days) | $150 |
| Presentation materials | $100 |
| **Total per conference** | **$1,500** |

### Quarterly Report Production ($600/report)

| Item | Cost (USD) |
|------|-----------|
| Data analysis and writing (analyst time, included in personnel) | $0 |
| Graphic design and layout | $300 |
| Translation (Macedonian/English) | $200 |
| Distribution (digital and limited print) | $100 |
| **Total per report** | **$600** |

---

## D. Administrative and Operational -- $10,200 (6.8%)

| Item | Unit Cost (USD) | Units/Months | Total (USD) |
|------|----------------|-------------|-------------|
| **Legal counsel (corporate compliance)** | $200/month | 12 | $2,400 |
| **Accounting and bookkeeping** | $150/month | 12 | $1,800 |
| **Bank fees and international transfers** | $100/month | 12 | $1,200 |
| **Insurance (professional liability)** | $1,200/year | 1 | $1,200 |
| **Office supplies and communications** | $100/month | 12 | $1,200 |
| **Legal review of publishing guidelines** | $1,200 | 1 | $1,200 |
| **Local legal counsel (North Macedonia)** | $1,200 | 1 | $1,200 |
| **Subtotal** | | | **$10,200** |

### Notes on Administrative Costs

- **Legal counsel:** Facturino DOOEL Veles requires ongoing corporate compliance under North Macedonian law, including annual reporting, tax filing, and NED grant compliance review.
- **Legal review of publishing guidelines:** A one-time engagement with a Macedonian media law attorney to establish responsible disclosure protocols for corruption findings, ensuring that published risk flags comply with defamation laws and do not expose the organization to legal liability.
- **Local legal counsel:** A one-time engagement to review data protection compliance under North Macedonia's Law on Personal Data Protection, which aligns with the EU GDPR framework, and ensure grant fund management complies with North Macedonian corporate law.

---

## E. Monitoring and Evaluation -- $5,400 (3.6%)

| Item | Unit Cost (USD) | Units | Total (USD) |
|------|----------------|-------|-------------|
| **Mid-term external evaluation** | $2,000 | 1 | $2,000 |
| **End-of-project external evaluation** | $2,500 | 1 | $2,500 |
| **User survey design and analysis** | $450 | 2 | $900 |
| **Subtotal** | | | **$5,400** |

### Notes on M&E Costs

- **External evaluations:** Conducted by an independent evaluator (not a team member) to provide objective assessment of project progress, impact, and sustainability. The mid-term evaluation at Month 6 allows for course correction; the end-of-project evaluation at Month 12 provides a summative assessment.
- **User surveys:** Two structured surveys (Month 6 and Month 12) of platform users, workshop participants, and coalition partners to assess satisfaction, utility, and impact.

---

## Cost-Sharing and In-Kind Contributions

Facturino DOOEL Veles will contribute the following resources at no cost to the grant:

| In-Kind Contribution | Estimated Value (USD) |
|----------------------|----------------------|
| Existing NabavkiData platform and codebase (3+ years of development) | $250,000+ |
| Database of 276,037 analyzed tenders with 70,338 risk flags | $50,000+ |
| Existing user base of 4,500 active users | -- |
| Current infrastructure and hosting (pre-grant period) | $6,000/year |
| Founder/CEO time (strategic direction, fundraising, partnerships) | $36,000/year |
| **Total estimated in-kind contribution** | **$342,000+** |

This in-kind contribution demonstrates Facturino DOOEL Veles's substantial commitment to the project and ensures that NED funds are leveraged against a significant existing investment. The requested $150,000 represents approximately 30% of the total project value when in-kind contributions are included.

---

## Budget Flexibility

Facturino DOOEL Veles requests the standard NED flexibility to reallocate up to 10% between budget categories without prior approval, subject to reporting at the next quarterly report. Any reallocation exceeding 10% will require written NED approval in advance.

---

## Payment Schedule

Facturino DOOEL Veles requests disbursement in three tranches:

| Tranche | Timing | Amount (USD) | Condition |
|---------|--------|-------------|-----------|
| First | Upon signing | $60,000 (40%) | Executed grant agreement |
| Second | Month 5 | $50,000 (33%) | Submission of first progress report and financial statement |
| Third | Month 9 | $40,000 (27%) | Submission of mid-term evaluation and second financial statement |

---

*Budget prepared by Facturino DOOEL Veles. All costs are based on current market rates for the North Macedonian market as of May 2026. Costs are presented in US Dollars.*
