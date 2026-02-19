# NabavkiData: AI-Powered Transparency in North Macedonian Public Procurement

## Grant Application to the National Endowment for Democracy

**Applicant:** Facturino DOOEL Veles
**Project Title:** Strengthening Civic Oversight of Public Procurement in North Macedonia Through AI-Driven Corruption Detection
**Requested Amount:** $150,000
**Project Duration:** 12 months
**Project Location:** North Macedonia
**Submission Date:** June 2, 2026

---

## 1. Executive Summary

Public procurement in North Macedonia accounts for approximately 12% of GDP and represents one of the most corruption-vulnerable sectors identified by the European Commission in its annual enlargement reports. Despite a legal framework aligned with EU directives, systemic corruption in procurement persists due to limited institutional capacity for oversight, fragmented data, and the sheer volume of tenders that exceed the monitoring capabilities of watchdog organizations and citizens.

NabavkiData (nabavkidata.com) is an operational, AI-powered civic technology platform that has already scraped, structured, and analyzed over 276,000 government tenders from North Macedonia's official e-procurement portal (e-nabavki.gov.mk), spanning from 2008 to the present. The platform applies 50 statistical risk indicators -- drawing on methodologies from the World Bank, the OECD, and Ukraine's Dozorro system -- to automatically detect patterns consistent with corruption, including single-bidder dominance, bid rigging, price anomalies, and collusion networks. To date, the system has identified 70,338 risk flags across 67,802 tenders and monitors 3,036 public institutions and 18,666 winning companies.

This proposal requests $150,000 over 12 months to scale NabavkiData from a technology prototype into a sustainable civic tool by: (1) expanding the machine learning pipeline and data coverage to achieve comprehensive, real-time monitoring; (2) building investigative tools for journalists, civil society organizations, and anti-corruption agencies; (3) conducting outreach, training, and public awareness campaigns to build a broad user base capable of leveraging the platform for accountability; and (4) publishing open datasets and research to inform policy reform.

NabavkiData is entirely privately funded to date, with no government support, ensuring independence and credibility. With NED support, the platform will transition from a single-team effort into a replicable, institutionally anchored model for technology-enabled anti-corruption work in the Western Balkans.

---

## 2. Problem Statement

### 2.1 Corruption in North Macedonian Public Procurement

North Macedonia consistently ranks among the most corruption-affected countries in Southeastern Europe. Transparency International's Corruption Perceptions Index places the country at 101st globally (2024), and the European Commission's annual progress reports have flagged public procurement as a "sector of concern" every year since 2015. The State Commission for Prevention of Corruption and the State Audit Office lack the technical capacity to systematically analyze the hundreds of thousands of procurement transactions that flow through the e-nabavki.gov.mk portal.

### 2.2 Scale of the Problem

NabavkiData's analysis of 276,037 tenders across 3,036 public institutions has revealed the following patterns:

- **Single-bidder dominance:** A substantial share of awarded tenders received only one bid, eliminating competitive pricing and raising the risk of pre-arranged outcomes.
- **Repeat winner concentration:** A small number of companies win a disproportionate share of contracts at specific institutions, with some maintaining win rates exceeding 80% over multiple years.
- **Price anomalies:** Winning bids that deviate significantly from estimated values, exact matches to official estimates (suggesting information leakage), and abnormally low bid variance among competitors (suggesting coordinated pricing).
- **Short deadlines:** Tenders published with deadlines too short for genuine competition, effectively limiting participation to pre-informed companies.
- **Specification rigging:** Technical specifications tailored to a single supplier's products, detectable through document analysis and natural language processing.
- **Related companies bidding together:** Companies with shared ownership, addresses, or management submitting ostensibly competing bids.

These 70,338 detected risk flags represent corruption vulnerabilities affecting an estimated 1.36 trillion MKD (approximately $25 billion USD) in cumulative procurement spending over the 2008--2026 period.

### 2.3 Why Technology is Essential

Manual oversight cannot address corruption at this scale. North Macedonia has approximately 15 anti-corruption analysts at the State Commission and a handful of investigative journalists covering procurement. They cannot individually review 276,000 tenders and millions of associated documents. Machine learning and statistical analysis can process this volume in hours, prioritize the highest-risk cases, and generate evidence packages that enable targeted human investigation. Ukraine's Dozorro platform demonstrated this model successfully, contributing to the recovery of an estimated $6 billion in public funds through technology-assisted civic monitoring of procurement.

---

## 3. Project Description

### 3.1 What NabavkiData Is

NabavkiData is a fully operational web platform (nabavkidata.com) built on the following technical architecture:

- **Data Collection:** Automated scraping of all tenders from e-nabavki.gov.mk using Scrapy and Playwright, running every three hours to capture new postings. The system processes tender metadata, bidder information, awarded contracts, and tender documents (PDFs extracted via OCR).
- **Database:** A PostgreSQL database containing 276,037 tenders, with structured fields for procuring entities, winners, bid amounts, dates, CPV codes, documents, and bidder details.
- **AI/ML Corruption Detection Pipeline:** A machine learning system that extracts 150+ features per tender across seven categories (competition, price, timing, relationship, procedural, document, and historical patterns), then applies 50 statistical risk indicators to assign corruption risk scores. The pipeline includes:
  - Random Forest and XGBoost ensemble models trained on labeled data
  - Graph Neural Networks (GraphSAGE, GAT) for collusion network detection
  - SHAP explainability for transparent, human-readable risk explanations
  - LIME local interpretability for individual tender analysis
  - Adaptive thresholds that adjust to market conditions
- **Eight Flag Types:** single_bidder, repeat_winner, price_anomaly, bid_clustering, short_deadline, high_amendments, spec_rigging, and related_companies.
- **Public Web Interface:** A bilingual (Macedonian/English) Next.js frontend where users can search tenders, view risk analyses, compare institutions, and track suspicious patterns. The platform currently serves approximately 4,500 active users.
- **AI-Powered Search:** Gemini-based RAG (Retrieval-Augmented Generation) search that allows users to ask natural language questions about procurement data.

### 3.2 What This Project Will Do

With NED funding, NabavkiData will execute four workstreams over 12 months:

**Workstream 1 -- ML Pipeline Enhancement and Real-Time Monitoring (Months 1--6)**
- Expand the ML pipeline to process tenders in real-time as they are published, enabling alerts within hours rather than days
- Implement cross-border entity matching to detect companies operating across multiple Balkan jurisdictions (Serbia, Albania, Kosovo, Montenegro, Bosnia, Croatia)
- Train models on confirmed corruption cases from Macedonian court verdicts and prosecution records (the system already catalogs known cases including the "Tank Case," "Talir Case," and others)
- Achieve detection accuracy targets of 85%+ precision and 90%+ recall on known corruption cases

**Workstream 2 -- Investigative Toolkit Development (Months 3--9)**
- Build an "Investigation Dashboard" for journalists and CSOs that provides case-file-ready evidence packages: risk scores, statistical evidence, network graphs, and document references
- Create API endpoints for programmatic access by research organizations and media outlets
- Develop automated report generation for institutions flagged with high corruption risk
- Implement a tip submission system where citizens can report suspicious procurement and link their reports to data-driven analysis

**Workstream 3 -- Outreach, Training, and Coalition Building (Months 4--12)**
- Conduct six hands-on training workshops for journalists, CSOs, and municipal transparency officers across North Macedonia (Skopje, Bitola, Tetovo, Ohrid, Shtip, Kumanovo)
- Publish a quarterly "Procurement Integrity Report" with top findings, distributed to media and government
- Establish a Civic Monitoring Coalition of at least 10 partner organizations that use NabavkiData as a shared resource
- Present findings at regional anti-corruption conferences (Regional Anti-Corruption Initiative, Western Balkans Civil Society Forum)

**Workstream 4 -- Open Data and Policy Impact (Months 6--12)**
- Release anonymized, structured open datasets of procurement patterns for academic research
- Publish a policy brief with concrete legislative recommendations for procurement reform
- Engage with the State Commission for Prevention of Corruption and the Public Procurement Bureau to advocate for integration of automated risk assessment into official oversight processes
- Document the NabavkiData methodology for replication in other Western Balkan countries

---

## 4. Objectives

**Objective 1: Enhance detection capability to achieve comprehensive, real-time corruption risk monitoring of all North Macedonian public procurement.**
- KPI: Process 100% of new tenders within 24 hours of publication
- KPI: Achieve 85%+ precision on corruption risk flags validated against known cases
- KPI: Expand from 8 to 15 risk indicator types, adding cross-border entity matching

**Objective 2: Equip journalists, civil society organizations, and anti-corruption agencies with actionable investigative tools and evidence packages.**
- KPI: Launch Investigation Dashboard used by at least 20 active investigative users
- KPI: Generate at least 50 investigation-ready case files from high-risk flagged tenders
- KPI: Facilitate at least 10 published investigative articles or reports based on NabavkiData findings

**Objective 3: Build a broad civic coalition and public awareness of procurement integrity, establishing NabavkiData as the reference platform for procurement transparency in North Macedonia.**
- KPI: Grow user base from 4,500 to 15,000 active users
- KPI: Train 120+ participants across six regional workshops
- KPI: Establish a Civic Monitoring Coalition of 10+ partner organizations
- KPI: Publish 4 quarterly Procurement Integrity Reports

**Objective 4: Produce open data, research, and policy recommendations that advance procurement reform and serve as a replicable model for the Western Balkans.**
- KPI: Release 3 open datasets for academic and policy research
- KPI: Publish 1 policy brief with legislative recommendations
- KPI: Present the NabavkiData model at 2+ regional conferences
- KPI: Initiate replication discussions with at least 2 neighboring countries

---

## 5. Activities and Timeline

### Month 1--3: Foundation and ML Enhancement

| Activity | Deliverable |
|----------|-------------|
| Hire data analyst and onboard project manager | Fully staffed team |
| Expand ML training pipeline with labeled corruption cases | Model v2.0 with 85%+ precision |
| Implement real-time tender processing and alerting | Alerts within 24 hours of publication |
| Begin cross-border entity matching (Serbia, Kosovo, Albania) | Entity matcher prototype |
| Conduct stakeholder mapping and outreach planning | Stakeholder map and outreach plan |

### Month 4--6: Investigative Tools and First Outreach

| Activity | Deliverable |
|----------|-------------|
| Build Investigation Dashboard (frontend and API) | Public beta of investigation tools |
| Develop automated evidence package generation | Case file generator for top-risk tenders |
| Conduct first two training workshops (Skopje, Bitola) | 40+ trained participants |
| Publish first quarterly Procurement Integrity Report | Q1 report distributed to 500+ recipients |
| Establish media partnerships for investigation coverage | MOUs with 3+ media outlets |

### Month 7--9: Scale and Coalition Building

| Activity | Deliverable |
|----------|-------------|
| Deploy cross-border detection for 6 Balkan countries | Cross-border risk detection live |
| Launch API access for partner organizations | Documented public API |
| Conduct third and fourth training workshops (Tetovo, Ohrid) | 80+ cumulative trained participants |
| Formalize Civic Monitoring Coalition | Coalition charter signed by 10+ organizations |
| Publish second quarterly report | Q2 report with cross-border findings |
| Begin anonymous tip submission system development | Tip system design and security audit |

### Month 10--12: Policy Impact, Sustainability, and Replication

| Activity | Deliverable |
|----------|-------------|
| Conduct fifth and sixth training workshops (Shtip, Kumanovo) | 120+ cumulative trained participants |
| Release open datasets and research documentation | 3 open datasets published |
| Publish policy brief with legislative recommendations | Policy brief presented to government |
| Present at Regional Anti-Corruption Initiative conference | Conference presentation and proceedings |
| Publish third and fourth quarterly reports | Q3 and Q4 reports |
| Conduct end-of-project evaluation and sustainability review | Final evaluation report |
| Initiate replication discussions with Kosovo and Serbia | Formal replication interest from 2+ countries |

---

## 6. Expected Results and Impact Metrics

### 6.1 Direct Outputs

| Output | Target |
|--------|--------|
| Tenders analyzed with real-time monitoring | 300,000+ (cumulative) |
| Corruption risk flags generated | 90,000+ |
| High-risk case files produced | 50+ |
| Training workshops conducted | 6 |
| Participants trained | 120+ |
| Quarterly Procurement Integrity Reports | 4 |
| Open datasets released | 3 |
| Policy briefs published | 1 |
| Regional conference presentations | 2+ |
| Coalition partner organizations | 10+ |

### 6.2 Outcomes

- **Accountability:** At least 10 investigative articles or CSO reports published using NabavkiData evidence, leading to public scrutiny of identified irregularities.
- **Institutional response:** At least 2 formal inquiries or audits initiated by oversight bodies based on NabavkiData findings.
- **Policy influence:** Procurement reform recommendations formally submitted to the Public Procurement Bureau and the State Commission for Prevention of Corruption.
- **Civic engagement:** 15,000 active platform users constituting a decentralized monitoring network.
- **Regional impact:** Replication discussions initiated with at least 2 neighboring countries.

### 6.3 Long-Term Impact

NabavkiData aims to shift the equilibrium of public procurement oversight in North Macedonia from reactive, manual review to proactive, AI-assisted monitoring. By providing citizens, journalists, and institutions with the same analytical power that was previously available only to well-resourced auditing firms, the project democratizes access to procurement integrity information. The long-term impact includes reduced corruption in public spending, increased value for money in public services, and strengthened public trust in democratic institutions -- all critical for North Macedonia's EU accession process.

---

## 7. Sustainability Plan

### 7.1 Revenue Model

NabavkiData has been designed with a sustainability model that does not depend on continuous grant funding:

- **Freemium SaaS:** Basic risk analysis and search remain free for all users. Premium features (real-time alerts, bulk API access, advanced investigation tools, custom reports) are offered on paid subscription tiers to companies seeking procurement intelligence, law firms conducting due diligence, and consulting firms advising on compliance.
- **Institutional subscriptions:** Anti-corruption agencies, audit offices, and international organizations (e.g., EU Delegation, USAID, World Bank country offices) can subscribe for full API access and custom dashboards.
- **Data licensing:** Anonymized, aggregated procurement integrity datasets licensed to academic institutions and policy research organizations.
- **Consulting services:** Technical advisory for governments and international organizations seeking to implement similar systems in other countries.

### 7.2 Technical Sustainability

- **Infrastructure costs are low:** The platform runs on a single AWS EC2 instance ($50/month) and AWS RDS PostgreSQL ($80/month), with frontend hosted on Vercel's free tier. AI API costs (Google Gemini) are approximately $200/month. Total operational cost is under $500/month.
- **Automated pipeline:** The scraper runs autonomously every three hours, and the ML pipeline refreshes daily. Minimal human intervention is required for ongoing data collection.
- **Open-source components:** The technology stack (Python, PostgreSQL, Next.js, Scrapy) consists entirely of open-source, well-maintained technologies with no licensing costs.

### 7.3 Institutional Anchoring

During the grant period, NabavkiData will formalize partnerships with at least three established Macedonian CSOs to ensure institutional continuity. The platform's methodology, training materials, and documentation will be published openly, ensuring that knowledge is not concentrated in a single organization. The Civic Monitoring Coalition will provide a governance structure for shared stewardship of the platform beyond the grant period.

### 7.4 Replication Potential

The NabavkiData architecture is designed for replication. The scraper, ML pipeline, and web interface are modular and configurable for different e-procurement portals. Serbia (portal.ujn.gov.rs), Kosovo (e-prokurimi.rks-gov.net), and Albania (app.gov.al) all operate similar electronic procurement systems. With configuration changes rather than full rebuilds, NabavkiData's approach can be extended to the Western Balkans region within 18--24 months.

---

## 8. Monitoring and Evaluation

NabavkiData will implement a structured M&E framework:

- **Monthly progress reports** tracking KPIs against targets
- **Quarterly narrative reports** documenting activities, challenges, and adjustments
- **Mid-term evaluation** (Month 6) assessing whether detection accuracy, user growth, and partnership targets are on track, with an opportunity for course correction
- **End-of-project evaluation** (Month 12) including an independent assessment of impact, sustainability, and replication readiness
- **User analytics:** Platform usage data (unique users, searches, report views, API calls) tracked through privacy-respecting analytics
- **Media monitoring:** Tracking of media coverage referencing NabavkiData findings as a measure of public impact

---

## 9. Risk Assessment and Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Government blocks access to e-nabavki.gov.mk data | Low | High | Data is currently publicly accessible; maintain cached copies; advocate for open data policy |
| Low adoption by journalists/CSOs | Medium | Medium | Invest heavily in training and outreach; co-design tools with target users; provide ongoing technical support |
| False positive corruption flags damage reputations | Medium | High | Prominent disclaimers on all outputs; human review workflow before public flagging; SHAP explainability for every flag; legal review of publishing guidelines |
| Technical infrastructure failure | Low | Medium | Automated backups; infrastructure-as-code; cloud hosting with redundancy |
| Team member departure | Low | Medium | Document all processes; knowledge sharing within team; modular codebase with clear documentation |

---

*This proposal is submitted by Facturino DOOEL Veles in support of democratic governance and anti-corruption in North Macedonia. NabavkiData represents a proven technology platform seeking partnership with the National Endowment for Democracy to maximize its civic impact.*
