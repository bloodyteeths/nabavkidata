# Organization Description

## Facturino DOOEL Veles

**Legal Name:** Facturino DOOEL Veles
**Address:** Veles, North Macedonia
**Entity Type:** DOOEL (Друштво со ограничена одговорност на едно лице / Single-Member Limited Liability Company)
**Year Established:** February 2026
**Website:** nabavkidata.com
**Primary Contact:** Atilla Tkulu, Founder, hello@nabavkidata.com, +389 70 253 467

---

## About Facturino DOOEL Veles

Facturino DOOEL Veles is a North Macedonian technology company dedicated to building civic technology tools that increase transparency and accountability in government operations. The organization's flagship product, NabavkiData (nabavkidata.com), is an AI-powered platform for monitoring and analyzing public procurement in North Macedonia -- a country where procurement corruption has been identified by the European Commission, Transparency International, and the US State Department as a systemic barrier to democratic governance and EU integration.

Facturino DOOEL Veles was founded by a team of technologists and data scientists who identified a critical gap in the anti-corruption ecosystem: while North Macedonia digitized its procurement system through the e-nabavki.gov.mk portal, no organization had the technical capacity to systematically analyze the hundreds of thousands of tenders flowing through that system. NabavkiData was built to fill this gap, applying state-of-the-art machine learning to make procurement data accessible, analyzable, and actionable for citizens, journalists, civil society, and oversight institutions.

---

## Organizational Capacity

### Technical Capabilities

Facturino DOOEL Veles possesses deep expertise in the specific technologies required for this project:

- **Data Engineering:** The team has built and operates a production data pipeline that automatically scrapes, structures, and stores over 276,000 government tenders from North Macedonia's official procurement portal, processing new data every three hours. The pipeline handles bilingual content (Macedonian Cyrillic and Latin scripts), PDF document extraction via OCR, and complex web scraping with JavaScript rendering.

- **Machine Learning for Anti-Corruption:** The team has designed and implemented a corruption detection system that extracts 150+ features per tender across seven analytical categories (competition, price, timing, relationship, procedural, document, and historical patterns) and applies 50 statistical risk indicators based on World Bank, OECD, and Dozorro methodologies. The ML pipeline includes ensemble models (Random Forest, XGBoost), Graph Neural Networks for collusion detection, and SHAP/LIME explainability frameworks. The system has detected 70,338 risk flags across 67,802 tenders.

- **Full-Stack Web Development:** The team maintains a production web platform built on Next.js 14, React, TypeScript, Tailwind CSS, and shadcn/ui (frontend), Python FastAPI with asyncpg (backend), and PostgreSQL on AWS RDS (database). The platform supports bilingual search (Latin-to-Cyrillic transliteration), AI-powered natural language queries via Google Gemini RAG, and responsive design for mobile access.

- **Infrastructure and DevOps:** The platform runs on AWS (EC2, RDS, S3) with frontend hosting on Vercel, automated scraping via cron jobs, and daily ML pipeline refreshes. Operational costs are kept under $500/month through efficient architecture, demonstrating the team's ability to build scalable systems at low cost.

### Domain Expertise

The team brings direct knowledge of North Macedonian governance, procurement regulation, and the anti-corruption landscape:

- **Procurement law:** Familiarity with North Macedonia's Law on Public Procurement (aligned with EU Directives 2014/24/EU and 2014/25/EU), the role of the Public Procurement Bureau, and the administrative review process through the State Appeals Commission on Public Procurement.
- **Anti-corruption ecosystem:** Understanding of the roles and mandates of the State Commission for Prevention of Corruption, the State Audit Office, the Public Revenue Office, and relevant civil society organizations (Transparency International Macedonia, Center for Civil Communications, BIRN Macedonia).
- **Investigative journalism:** The team has cataloged confirmed corruption cases from Macedonian court verdicts, prosecution records, and investigative journalism reports, and has used these as ground truth for ML model training and validation.
- **Regional context:** Knowledge of procurement systems across the Western Balkans (Serbia, Kosovo, Albania, Montenegro, Bosnia, Croatia), enabling the cross-border detection capabilities planned under this project.

---

## Track Record

### NabavkiData Platform Achievements (to date)

NabavkiData was developed entirely with private funding and without government support, demonstrating the team's capacity to deliver results independently:

| Metric | Achievement |
|--------|-------------|
| Tenders analyzed | 276,037 |
| Public institutions monitored | 3,036 |
| Unique winning companies tracked | 18,666 |
| Corruption risk flags detected | 70,338 |
| Flag types implemented | 8 (single_bidder, repeat_winner, price_anomaly, bid_clustering, short_deadline, high_amendments, spec_rigging, related_companies) |
| ML features per tender | 150+ across 7 categories |
| Statistical risk indicators | 50 (Dozorro-style adaptive indicators) |
| Active platform users | 4,500+ |
| Data coverage | 2008 -- present (17+ years of procurement history) |
| Total procurement value analyzed | 1.36 trillion MKD (~$25 billion USD) |
| Platform uptime | 99.5%+ |
| Data refresh frequency | Every 3 hours |

### Key Technical Milestones

- Built a custom web scraper using Scrapy and Playwright that handles the e-nabavki.gov.mk portal's JavaScript-heavy interface, archive year navigation, and pagination -- processing up to 4,000 listing pages per session with automatic filter state recovery.
- Developed a 150+ feature extraction pipeline that computes competition, price, timing, relationship, procedural, document, and historical features for every tender, enabling sophisticated ML analysis.
- Implemented Graph Neural Network architecture (GraphSAGE + Graph Attention Networks) for detecting collusion networks among bidding companies.
- Created a ground truth dataset from confirmed corruption cases (court verdicts from the Macedonian judiciary, prosecution records, investigative journalism) for supervised model training.
- Achieved 81--95% detection accuracy on known corruption indicators through adaptive threshold calibration.
- Built SHAP and LIME explainability layers so that every corruption risk flag includes a human-readable explanation of which factors contributed to the score -- critical for credibility with journalists and oversight agencies.

---

## Governance and Financial Management

Facturino DOOEL Veles is registered under North Macedonian law as a single-member limited liability company (DOOEL) and operates in compliance with the Law on Trade Companies. The organization maintains:

- **Financial controls:** Separate bank accounts for grant funds, standard double-entry bookkeeping, and monthly financial reconciliation.
- **Audit readiness:** Financial records maintained in accordance with International Financial Reporting Standards (IFRS) as adopted in North Macedonia, with the capacity to provide audited financial statements upon request.
- **Compliance:** Adherence to all applicable North Macedonian regulations, including tax filing obligations with the Public Revenue Office, social contribution payments, and annual financial reporting to the Central Registry.
- **Data protection:** The NabavkiData platform processes only publicly available government data from the official e-procurement portal. Personal data handling complies with North Macedonia's Law on Personal Data Protection (aligned with EU GDPR). A formal data protection impact assessment is included in the project plan.
- **Responsible disclosure:** All corruption risk flags are presented as statistical indicators, not as accusations. Prominent disclaimers accompany all outputs, stating in both Macedonian and English that risk analysis does not constitute evidence of corruption and requires further investigation.

---

## Partnerships and Affiliations

Facturino DOOEL Veles maintains working relationships with organizations in the North Macedonian anti-corruption and civic technology ecosystem, including:

- **Startup Macedonia** -- ecosystem organization that maps and connects startups in North Macedonia; Facturino DOOEL Veles is included in their mapping of AI solutions and startups
- Investigative journalists covering procurement irregularities for Macedonian media outlets
- Civic technology practitioners in the Western Balkans working on open data and government transparency
- Academic researchers studying corruption detection methodologies and machine learning applications in governance

During the proposed grant period, Facturino DOOEL Veles will formalize these relationships through the Civic Monitoring Coalition and media partnership agreements, as described in the project proposal.

---

## Why Facturino DOOEL Veles is Qualified for This Grant

1. **Proven product:** NabavkiData is not a concept or proposal -- it is an operational platform with 276,000+ tenders analyzed, 70,000+ risk flags detected, and 4,500+ active users. NED funding will scale an existing, working system rather than fund speculative development.

2. **Technical depth:** The team possesses rare expertise at the intersection of AI/ML, public procurement, anti-corruption methodology, and Western Balkans governance -- a combination that is not available from general-purpose technology firms or traditional CSOs.

3. **Independence:** NabavkiData has been built without any government funding, ensuring complete independence from the institutions it monitors. This independence is essential for credibility.

4. **Local presence:** As a North Macedonian company based in Veles, Facturino DOOEL Veles has direct access to the local ecosystem, government institutions, media, and civil society -- enabling effective outreach, training, and coalition building.

5. **Cost efficiency:** The platform's total infrastructure cost is under $500/month, and the full development investment to date exceeds $250,000 in value. Facturino DOOEL Veles has demonstrated the ability to build sophisticated technology at a fraction of typical costs.

6. **Sustainability pathway:** The freemium SaaS model, institutional subscriptions, and consulting services provide a clear path to financial sustainability beyond the grant period, ensuring that NED's investment creates lasting impact.

7. **Replication potential:** The modular architecture and documented methodology make NabavkiData replicable across the Western Balkans, multiplying the impact of NED's investment across the region.

---

*Facturino DOOEL Veles is committed to transparency, accountability, and the use of technology to strengthen democratic governance. We welcome the opportunity to partner with the National Endowment for Democracy in advancing procurement integrity in North Macedonia and the wider Western Balkans region.*
