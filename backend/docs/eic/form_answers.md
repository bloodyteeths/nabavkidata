# NabavkiData - EIC Accelerator Step 1 Form Answers
## Complete Short Proposal Application

---

**Company Name:** NabavkiData d.o.o.e.l.
**Country:** North Macedonia
**Sector:** GovTech / Anti-Corruption / AI/ML
**TRL:** 7 (System prototype demonstrated in operational environment)
**Funding Requested:** EUR 2,500,000 (Blended Finance Preferred)

---

# SECTION 1: EXCELLENCE

## 1.1 Innovation - What is the innovation?

NabavkiData is an AI-powered public procurement intelligence platform that transforms unstructured government data into actionable insights for businesses, anti-corruption organizations, and citizens across the Western Balkans.

### Core Innovation - Three Interconnected Breakthroughs:

**1. Cyrillic Deep OCR Pipeline** *(Our Primary Technical Moat)*

The Western Balkans region uses Cyrillic scripts (Macedonian, Serbian) for government documents. Off-the-shelf OCR solutions (Google Vision, AWS Textract, Tesseract) achieve only 40-60% accuracy on degraded government scans - making extracted text unusable.

We developed a custom-trained pipeline achieving **94% accuracy** on documents where alternatives fail:
- Pre-processing optimized for low-quality government scans
- Custom models trained on 2+ years of real procurement documents
- Post-processing with domain-specific entity recognition (company names, prices, dates)
- Automatic extraction of structured fields from unstructured text

**This capability required 2+ years of training data accumulation and cannot be quickly replicated.**

**2. RAG-Powered Semantic Search**

Traditional keyword search fails when users don't know exact Macedonian/Serbian terminology. Our system understands meaning, not just words:

- 450,000+ document embeddings for semantic similarity
- Bilingual query processing (automatic Latin ↔ Cyrillic transliteration)
- Retrieval-Augmented Generation for natural language Q&A
- Context-aware responses with source citations

*Example:* A user asks "road construction contracts over €100K where only one company bid" - our system finds relevant tenders even if documents use terms like "патен инфраструктурен проект" (road infrastructure project) or contain prices in local currency.

**3. ML-Based Corruption Detection** *(Novel Application)*

We are implementing detection algorithms adapted from successful initiatives (Ukraine's Prozorro/Dozorro system, OECD red flag indicators) for Western Balkans context:

- **Anomaly Detection:** Statistical flagging of unusual pricing, timing, or participation patterns
- **Graph Neural Networks (GNNs):** Network analysis to identify collusion rings and shell company clusters
- **Temporal Analysis:** Pattern recognition for suspicious seasonal tender publication
- **Red Flag Scoring:** Automated risk assessment per tender and entity

### What Makes It Innovative:

| Dimension | Innovation |
|-----------|------------|
| **Technical** | First OCR pipeline achieving >90% accuracy on Cyrillic government scans |
| **Application** | First AI-powered procurement intelligence for Western Balkans |
| **Integration** | Combines document processing + semantic search + fraud detection |
| **Access** | Converts inaccessible government data into searchable intelligence |

---

## 1.2 Beyond State of the Art - How does this exceed existing solutions?

### Current State of the Art:

| Existing Solution | What It Does | Why It Fails for Western Balkans |
|-------------------|--------------|----------------------------------|
| **e-nabavki.gov.mk** | Official Macedonian portal | Scanned PDFs only; no search; no analytics |
| **OpenTender.eu** | EU open data aggregation | No document content; basic search; limited coverage |
| **TED (EU)** | EU tender database | Does not cover non-EU candidate countries |
| **Govini (US)** | AI procurement intelligence | US market only; English language only |
| **Spend Network (UK)** | UK procurement analytics | UK focus; no Cyrillic support |
| **Generic OCR** | Document digitization | <60% accuracy on Cyrillic government scans |

### Our Advancement Beyond SOTA:

| Dimension | Current SOTA | NabavkiData Advancement |
|-----------|--------------|-------------------------|
| **OCR Accuracy** | 40-60% on Cyrillic | 94% accuracy (2x improvement) |
| **Search** | Keyword matching | Semantic understanding |
| **Language** | Single language | Bilingual (Latin/Cyrillic) |
| **Coverage** | Single country or EU only | Multi-country Western Balkans |
| **History** | Current year | 16 years (2008-2024) |
| **Freshness** | Weekly/monthly | 3-hour sync cycle |
| **Corruption Detection** | Manual investigation | Automated ML flagging |

### Scientific Foundation:

Our approach builds on peer-reviewed research:
- Fazekas & Kocsis (2020): "Uncovering High-Level Corruption" - network analysis methodology
- Ferwerda et al. (2017): "Corruption in Public Procurement" - red flag indicators
- Kenny & Musatova (2021): "Using AI to detect public procurement corruption" - ML approaches
- Ukraine Dozorro system (2016-present): Practical implementation reference

---

## 1.3 Technology Readiness Level (TRL)

### Current TRL: 7 (System prototype demonstrated in operational environment)

| TRL Level | Description | Status | Evidence |
|-----------|-------------|--------|----------|
| TRL 1-3 | Basic research to proof of concept | ✅ Complete | 2023 development |
| TRL 4 | Validated in lab | ✅ Complete | OCR accuracy validated |
| TRL 5 | Validated in relevant environment | ✅ Complete | Real government data processing |
| TRL 6 | Demonstrated in relevant environment | ✅ Complete | 7,800+ tenders analyzed |
| **TRL 7** | **System prototype operational** | **✅ Current** | **Production system live** |
| TRL 8 | System complete and qualified | 🎯 Target | Multi-country deployment |
| TRL 9 | System proven in operation | 🎯 Post-EIC | Regional scale proven |

### Component-Level TRL:

| Component | TRL | Evidence |
|-----------|-----|----------|
| Web scraping infrastructure | 8 | Production, 3-hour sync cycle |
| Cyrillic OCR pipeline | 7 | 94% accuracy, 32K+ documents processed |
| Embedding generation | 7 | 450,000+ embeddings in production |
| RAG search system | 7 | Live with bilingual support |
| Corruption detection ML | 5-6 | Algorithms designed, initial validation |
| User interface | 6-7 | Functional, processing real queries |

### Target: TRL 8-9 within 24 months with EIC funding

---

## 1.4 Intellectual Property Strategy

### IP Assets:

| Asset | Type | Status | Protection Strategy |
|-------|------|--------|---------------------|
| **Cyrillic OCR Models** | Software/ML models | Developed | Trade secret (architecture + training data) |
| **Corruption Detection Algorithms** | Software/ML | In development | Patent application planned Q2 2025 |
| **Bilingual NLP Pipeline** | Software | Developed | Trade secret |
| **Data Scrapers** | Software | Developed | Copyright + trade secret |
| **NabavkiData Brand** | Trademark | Registered | EU trademark application filed |
| **Training Data** | Database | 2+ years accumulated | Trade secret (key competitive moat) |

### Freedom to Operate:

- **Patent Landscape:** No blocking patents identified in Cyrillic OCR or procurement analytics
- **Open Source:** Built on open-source foundations (Scrapy, PostgreSQL, pgvector) - no licensing constraints
- **Regulatory:** Public procurement data is public by law; no data access restrictions
- **FTO Analysis:** Preliminary FTO review completed; full analysis available upon request

### Why IP Is Defensible:

1. **Training Data Moat:** 2+ years to replicate our Cyrillic document training corpus
2. **Domain Knowledge:** Entity resolution requires native language expertise
3. **First Mover:** Already operational while competitors would need years to catch up
4. **Network Effects:** More data improves ML models; early lead compounds over time

---

# SECTION 2: IMPACT

## 2.1 Market Opportunity - TAM/SAM/SOM

### Total Addressable Market (TAM): €850M/year
*GovTech + procurement analytics for EU + candidate countries*

**Calculation:**
- 27 EU members + 6 Western Balkans + 3 Eastern Partnership = 36 countries
- Procurement transparency software market: €850M annually (Gartner 2024)
- Growing at 15% CAGR as governments digitize

### Serviceable Addressable Market (SAM): €120M/year
*Western Balkans + Eastern Europe with Cyrillic/complex scripts*

**Calculation:**
- 12 countries requiring specialized Cyrillic/multilingual capabilities
- 500,000+ companies bidding on government contracts
- Enterprise + government contract opportunities: €120M addressable

### Serviceable Obtainable Market (SOM): €15M ARR by 2028
*Realistic 3-year capture*

**Calculation:**
- 5 countries fully deployed
- 8,000 paying business subscribers × €1,500 avg annual revenue = €12M
- 20 government/NGO enterprise contracts × €150K = €3M
- Total: €15M ARR target

### Market Timing - Why Now:

| Driver | Trend | Impact |
|--------|-------|--------|
| **EU Enlargement Push** | Western Balkans priority post-Ukraine | Chapter 23 compliance mandatory |
| **AI Breakthrough** | LLMs, embeddings now viable | Semantic search finally possible |
| **Digital Transformation** | Post-COVID government digitization | More data available online |
| **Anti-Corruption Funding** | €2B+ EU investment in rule-of-law | Willing buyers for our tools |

---

## 2.2 Scalability

### Geographic Scalability:

| Phase | Countries | Timeline | Effort | Cumulative Users |
|-------|-----------|----------|--------|------------------|
| Complete | North Macedonia | Done | Baseline | 5,000 |
| Phase 2 | Kosovo, Albania | 2025 | 3 months each | 20,000 |
| Phase 3 | Serbia, Montenegro | 2026 | 4 months each | 60,000 |
| Phase 4 | Bosnia, Croatia, Bulgaria | 2027+ | 6 months each | 120,000 |

**For each new country we need:**
- New scraper adapters (reusable architecture)
- Language model fine-tuning (if different language)
- Local entity extraction rules
- Minimal additional infrastructure

### Technical Scalability:

- **Database:** PostgreSQL with pgvector scales to billions of embeddings
- **Infrastructure:** AWS cloud enables elastic scaling
- **Architecture:** Microservices support independent component scaling
- **Cost:** Marginal cost per user decreases with scale

### Business Model Scalability:

- **Self-service SaaS:** Reduces customer acquisition costs over time
- **API Access:** Enables partner integrations and ecosystem
- **White-label:** Option for government deployments

---

## 2.3 Societal Impact and European Added Value

### EU Strategic Alignment:

| EU Priority | NabavkiData Contribution |
|-------------|--------------------------|
| **EU Enlargement Strategy** | Direct support for Chapter 23 (Judiciary/Fundamental Rights) compliance |
| **European Green Deal** | Enable monitoring of green public purchasing compliance |
| **Digital Decade 2030** | AI-powered government transparency tool |
| **EU Anti-Corruption Strategy** | Technology infrastructure for anti-corruption efforts |
| **Recovery & Resilience** | Oversight of EU-funded contracts in candidate countries |

### UN Sustainable Development Goals:

| SDG | Contribution |
|-----|--------------|
| **SDG 16: Peace, Justice, Strong Institutions** | Core mission: transparency, anti-corruption, accountability |
| **SDG 8: Decent Work & Economic Growth** | Level playing field for SMEs in procurement |
| **SDG 9: Industry, Innovation, Infrastructure** | AI innovation for public sector efficiency |
| **SDG 10: Reduced Inequalities** | Equal access to government opportunities |

### Quantified Societal Impact (by 2028):

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Corruption cases identified | 50+ | Referrals to authorities |
| SME bid success improvement | +25% | Before/after analysis of users |
| Procurement savings identified | €50M+ | Price anomaly detection |
| Documents made searchable | 2M+ | Platform metrics |
| Citizens with access | 100K+ | Free tier users |

### Anti-Corruption Economics:

- Corruption costs Western Balkans: €2.5-12.5 billion/year (5-25% of procurement)
- If NabavkiData prevents even 0.1% of corruption: €2.5-12.5M annual savings
- ROI on €2.5M investment: 1-5x annually in societal benefit

---

## 2.4 Competitive Advantage and Barriers to Entry

### Competitive Moat:

| Barrier | Our Position | Time for Competitor to Replicate |
|---------|--------------|----------------------------------|
| **Training Data** | 2+ years of Cyrillic document corpus | 2-3 years minimum |
| **OCR Accuracy** | 94% on degraded scans | 1-2 years R&D |
| **Historical Coverage** | 16 years (2008-2024) | Cannot be accelerated |
| **Local Knowledge** | Native team understanding quirks | Hiring challenge |
| **Trust Network** | Relationships with NGOs, journalists | Years to build |
| **First Mover** | Operational platform | 18-24 months to catch up |

### Why Global Players Won't Easily Enter:

- **Market Size:** Western Balkans is "small" for Google/Microsoft strategic interest
- **Language Complexity:** Cyrillic languages are underserved by Big Tech
- **Local Customization:** Government portals require specialized adaptation
- **Trust Requirements:** Anti-corruption community skeptical of foreign tech giants

---

# SECTION 3: IMPLEMENTATION

## 3.1 Team

### Founding Team:

**[CEO Name] - Chief Executive Officer**
*[To be completed with actual details]*
- [X] years experience in [relevant field]
- Previous: [Company/Role]
- Education: [University, Degree]
- Role: Strategy, fundraising, partnerships

**[CTO Name] - Chief Technology Officer**
*[To be completed with actual details]*
- [X] years in software engineering/ML
- Previous: [Company/Role]
- Education: [University, Degree]
- Role: Technology architecture, AI/ML development

### Key Team Competencies:
- ✅ Machine learning and NLP
- ✅ Data engineering and web scraping
- ✅ Full-stack development (Python, React, PostgreSQL)
- ✅ Regional market knowledge
- ✅ Public procurement domain expertise

### Advisory Board:
- **[Advisor 1]:** [Anti-corruption/governance expertise]
- **[Advisor 2]:** [Technical/ML expertise]
- **[Advisor 3]:** [Business/investment expertise]

### Hiring Plan (with EIC Funding):

| Role | Timing | Priority | Key Skills |
|------|--------|----------|------------|
| ML Engineer (Corruption Detection) | Q1 2025 | Critical | GNNs, anomaly detection |
| ML Engineer (NLP/OCR) | Q2 2025 | Critical | Transformers, multilingual NLP |
| Full-Stack Developer | Q2 2025 | High | React, Python, PostgreSQL |
| Data Engineer | Q3 2025 | High | Scrapy, ETL pipelines |
| Business Development Manager | Q3 2025 | High | B2B SaaS, regional experience |
| Customer Success Manager | Q4 2025 | Medium | Technical support, Macedonian |

### Team Diversity Commitment:
- Target: 40% women in technical roles by 2027
- Geographic diversity across Balkan countries
- Inclusive hiring practices, flexible work arrangements

---

## 3.2 Work Plan and Milestones

### Phase 1: Foundation (Months 1-6)
**Budget Allocation: €500,000**

| Milestone | Deliverable | Success Criteria |
|-----------|-------------|------------------|
| M1.1 | Launch paid subscription tiers | Payment system live, first 50 paid users |
| M1.2 | Corruption detection MVP | 3 detection algorithms operational |
| M1.3 | Customer onboarding | 100 paying customers |
| M1.4 | Kosovo deployment | Full data coverage, 1,000+ tenders indexed |

### Phase 2: Regional Expansion (Months 7-12)
**Budget Allocation: €700,000**

| Milestone | Deliverable | Success Criteria |
|-----------|-------------|------------------|
| M2.1 | Albania platform launch | 2,000+ tenders indexed |
| M2.2 | Developer API launch | 10 API customers |
| M2.3 | Public transparency dashboard | Open access launched |
| M2.4 | NGO partnership | MOU signed with TI chapter |

### Phase 3: Scale (Months 13-18)
**Budget Allocation: €700,000**

| Milestone | Deliverable | Success Criteria |
|-----------|-------------|------------------|
| M3.1 | Serbia platform launch | Largest regional market covered |
| M3.2 | Montenegro coverage | 5 countries total |
| M3.3 | Enterprise sales | 20 enterprise customers |
| M3.4 | Advanced ML models | GNN collusion detection live |

### Phase 4: Growth (Months 19-24)
**Budget Allocation: €600,000**

| Milestone | Deliverable | Success Criteria |
|-----------|-------------|------------------|
| M4.1 | 6th country launch | Bosnia and Herzegovina |
| M4.2 | Revenue milestone | €2M ARR achieved |
| M4.3 | User milestone | 3,000+ paying customers |
| M4.4 | Series A readiness | Investment materials, pipeline |

---

## 3.3 Risk Assessment and Mitigation

### Technical Risks:

| Risk | Probability | Impact | Mitigation Strategy |
|------|-------------|--------|---------------------|
| OCR accuracy plateau | Medium | High | Continuous model training; human-in-the-loop for edge cases |
| Corruption detection false positives | Medium | High | Confidence scoring; human verification workflow |
| Government portal changes | High | Medium | Automated monitoring; modular scraper architecture |
| Scalability challenges | Low | Medium | Cloud-native design; horizontal scaling |

### Commercial Risks:

| Risk | Probability | Impact | Mitigation Strategy |
|------|-------------|--------|---------------------|
| Slow customer adoption | Medium | High | Freemium model; partnership distribution |
| Competition from larger players | Low | High | First-mover advantage; data moat |
| Pricing pressure | Medium | Medium | Value-based pricing; enterprise focus |
| Country expansion delays | Medium | Medium | Prioritized rollout; local partnerships |

### External Risks:

| Risk | Probability | Impact | Mitigation Strategy |
|------|-------------|--------|---------------------|
| Political instability | Medium | Medium | Multi-country diversification |
| Regulatory changes | Low | Medium | Legal monitoring; adaptable architecture |
| EU enlargement delays | Low | Low | Business model independent of accession |
| Currency fluctuations | Medium | Low | Euro-denominated contracts |

---

## 3.4 Financial Plan

### Use of EIC Funds (€2,500,000):

| Category | Amount | % | Key Activities |
|----------|--------|---|----------------|
| **R&D - AI/ML** | €1,000,000 | 40% | Corruption detection algorithms, GNN development, OCR improvements |
| **Engineering** | €600,000 | 24% | Platform scaling, multi-country architecture, API |
| **Go-to-Market** | €500,000 | 20% | Sales team, marketing, partnerships |
| **Operations** | €250,000 | 10% | Legal, compliance, infrastructure |
| **Contingency** | €150,000 | 6% | Unforeseen challenges |

### Revenue Projections:

| Year | Free Users | Paid Users | ARR | Gross Margin |
|------|------------|------------|-----|--------------|
| 2025 | 5,000 | 200 | €150K | 80% |
| 2026 | 25,000 | 1,500 | €900K | 80% |
| 2027 | 60,000 | 4,000 | €2.5M | 82% |
| 2028 | 120,000 | 8,000 | €5.5M | 85% |

### Unit Economics:
- **Customer Acquisition Cost (CAC):** €150 target
- **Lifetime Value (LTV):** €1,200 (24-month retention × €50/month avg)
- **LTV:CAC Ratio:** 8:1 (healthy SaaS benchmark: >3:1)

### Path to Sustainability:
- Break-even: ~1,500 paying customers (Month 18-20)
- Cash flow positive: End of EIC funding period
- Series A readiness: Month 24

---

## 3.5 Why EIC Funding (Not Private Investment)

### The Funding Gap:

Private investors are insufficient for NabavkiData because:

1. **Deep Tech Risk:** Corruption detection AI at scale is unproven. VCs require demonstrated unit economics; we need capital to build the algorithms first.

2. **Long Time Horizon:** EU enlargement is a 3-5 year process. Standard VC exit timelines (5-7 years) don't align with our impact trajectory.

3. **Public Good Component:** Free transparency features for journalists and citizens reduce commercial margins but maximize societal impact.

4. **Regional Focus:** Western Balkans is considered "frontier" by European VCs. We've been declined by [X] investors citing geographic risk.

5. **Strategic EU Alignment:** EIC specifically funds technologies enabling EU policy objectives. Our Chapter 23 contribution directly serves enlargement strategy.

### Grant vs. Equity Preference:

We prefer **blended finance** (grant + equity):
- **Grant:** R&D and deep tech development (TRL advancement)
- **Equity:** Go-to-market and scaling activities

### Evidence of Funding Gap:
- [Investor 1]: Declined citing geographic risk
- [Investor 2]: Insufficient ticket size for region
- Regional VCs: Limited capacity for deep tech

---

## 3.6 Long-Term Vision

### 3-Year Vision (2028):
NabavkiData becomes the definitive procurement intelligence platform for the Western Balkans:
- 5+ countries covered
- 3,000+ paying customers
- €2M+ ARR
- Established anti-corruption reputation

### 5-Year Vision (2030):
Expand to EU accession and new member states:
- Coverage: 10+ countries
- Users: 15,000+ paid
- Revenue: €10M+ ARR
- Positioned for strategic acquisition or Series B

### 10-Year Vision (2035):
"Bloomberg Terminal for European Public Procurement":
- Pan-European coverage
- €50M+ revenue
- Essential infrastructure for government transparency

---

# SECTION 4: ADDITIONAL INFORMATION

## 4.1 Keywords (EIC Taxonomy)

1. **Artificial Intelligence** - AI for document processing, semantic search, fraud detection
2. **Digital Governance** - Government transparency, open data, public sector digitization
3. **RegTech** - Regulatory technology for compliance and oversight

## 4.2 Ethics & Responsible AI

### Data Protection:
- GDPR-compliant processing of public procurement data
- No personal data collection beyond business contacts
- Data minimization principles applied

### AI Ethics:
- Transparency in algorithmic decision-making
- Human oversight for corruption allegations
- Regular bias audits of ML models
- Clear documentation of model limitations

### Dual-Use Considerations:
- Technology processes only public government data
- No law enforcement integration without legal framework
- Methodology openly documented for scrutiny

## 4.3 Contact Information

**NabavkiData d.o.o.e.l.**
[Street Address]
1000 Skopje, North Macedonia

**Primary Contact:** [CEO Name]
- Email: [email]
- Phone: [phone]
- LinkedIn: [profile]

**Company Registration:** [Number]
**Website:** [URL]

---

## Summary Statement

NabavkiData represents a unique opportunity to apply cutting-edge AI technology to a critical European challenge: public procurement transparency in EU candidate countries.

**The Problem:** €50+ billion in annual procurement across the Western Balkans is largely opaque - locked in scanned Cyrillic documents no technology can read. Corruption thrives in this darkness.

**Our Solution:** AI that reads what humans can't. We've built the first platform achieving 94% OCR accuracy on government scans, combined with semantic search and corruption detection algorithms.

**The Evidence:** 7,800+ tenders indexed, 450,000+ embeddings generated, operational platform processing data every 3 hours. TRL 7 - this is working technology, not a concept.

**The Ask:** €2.5M to scale from one country to six, advance corruption detection from TRL 6 to TRL 8, and build a sustainable business delivering lasting European impact.

**The Impact:** Every euro saved from corruption is a euro for schools, hospitals, roads. Every company winning on merit strengthens the economy. Every transparency tool brings the Western Balkans closer to Europe.

**We are not just building a company. We are building infrastructure for accountability.**

---

*Application prepared for EIC Accelerator Step 1*
*Last updated: [Date]*

