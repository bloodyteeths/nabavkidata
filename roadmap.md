MK Tender Intelligence – Technical Architecture and Implementation Plan

1. System Architecture Overview

The MK Tender Intelligence platform is designed as a modular multi-agent system where specialized Claude Code agents handle different responsibilities in parallel. The architecture follows a distributed microservices style, with a centralized database and well-defined APIs for communication between components. Key components include:
	•	Web Scraper Agent (Claude Code): Periodically crawls the North Macedonian public procurement portal (e-nabavki.gov.mk) to collect tender data and documents.
	•	AI Assistant Agent (Claude Code): Handles user queries by retrieving relevant tender information (via a RAG pipeline) and generating answers using an LLM (Gemini or a fallback model).
	•	Backend API Server: A centralized backend (Node.js or Python) that exposes RESTful endpoints and coordinates tasks – handling user authentication, authorizing requests based on subscription tier, serving data from the database, and invoking the AI assistant agent for Q&A. It also integrates with Stripe for billing.
	•	PostgreSQL Database: A unified datastore for all structured information – tenders, organizations, users, subscriptions, embeddings, etc. (with vector search capability for document embeddings).
	•	Frontend UI: A Next.js web application providing a dashboard, search interface, AI chat UI, and user account management. It communicates with the backend via HTTP(S) API calls (and web sockets or Server-Sent Events for real-time alerts if needed).

These components interact as depicted below:

System Architecture:
+-------------+       +-------------------+       +-----------------+
| Scraper     +------>|                   |<------+ AI Assistant   |
| (Claude)    |  data |  PostgreSQL DB    | Vector| (Claude + LLM)  |
+-------------+ files | (Tenders, Embeds) |------>+----------------+
                      |                   |   Q&A 
                      +-------------------+    ^
                           ^    ^             /|\
                           |    |  API calls   |
+-------------+   HTTP     |    +--------------+
| Frontend UI +----------->|      Backend/API   |---> Stripe API (billing)
| (Next.js)   | <----------+   (Auth, Alerts)   |
+-------------+   responses

Data Flow: The scraper agent pulls tender notices and related PDF documents from the source site and stores them in the database. The AI assistant agent then uses the stored data (and pre-computed embeddings) to fulfill user requests by performing retrieval and passing context to an LLM for answer generation. The frontend allows users to interact (search tenders, ask questions, set alerts) and the backend orchestrates these requests (fetching from the DB, triggering AI agent, enforcing auth/billing rules). This separation of concerns makes the system multi-agent friendly – each Claude agent can be developed and run independently, yet their outputs integrate through the database and API.

Scalability & Parallelism: Each module can scale horizontally. For example, the scraper can run on a schedule or multiple instances for different sources (for future international expansion). The AI assistant queries can be handled concurrently by multiple Claude instances if needed. Using Claude Code agents for distinct tasks ensures parallel development and deployment – the scraping agent, AI agent, etc., can run in isolation and be updated without affecting others, as long as the data contract (DB schema/API) remains consistent. This architecture is also cloud-deployable (containers or serverless functions per component) for resilience.

2. End-to-End Technical Roadmap

To build this SaaS product, a phased implementation roadmap is recommended. Below is a breakdown of major milestones by week/sprint, focusing on delivering incremental functionality:
	•	Sprint 0 (Project Setup & Planning):
	•	Set up version control (e.g. Git) and define the tech stack (Next.js for frontend, Node.js or Python for backend, PostgreSQL for DB).
	•	Provision development and staging environments.
	•	Outline the core schema and design high-level API routes.
	•	Deliverable: Project scaffolding with placeholder modules for scraper, backend, and frontend.
	•	Sprint 1 (Database & Basic Scraper):
	•	Implement the PostgreSQL database schema (users, tenders, documents, etc. – see Section 3).
	•	Build a basic web scraper agent for e-nabavki.gov.mk that can fetch recent tenders and store them in the DB. Start with a limited scope (e.g., open tenders in one category) to ensure the pipeline works.
	•	Ensure legal compliance: review site’s robots.txt and terms; introduce delays or scheduling as needed.
	•	Deliverable: A running scraper that populates the database with actual tender data (at least a small sample).
	•	Sprint 2 (Backend API & Core Models):
	•	Develop the backend API with endpoints for core data: e.g., GET /tenders, GET /tenders/{id}, GET /organizations, POST /user/signup, POST /auth/login, etc.
	•	Implement ORMs or query builders for database interaction (SQLAlchemy, Prisma, etc. depending on language).
	•	Basic authentication using JWT or session for the API, and protect endpoints accordingly.
	•	Deliverable: Backend server that the frontend can call to fetch tender data and manage user accounts (with dummy or seeded data if scraper not fully ready).
	•	Sprint 3 (Frontend UI & Dashboard):
	•	Build the Next.js frontend pages: Login/Signup, Dashboard (list of latest tenders or summary stats), Tenders Search/List page, Tender Details view (with attached documents and info).
	•	Implement UI components for table/list of tenders, search filters (by keyword, category, date).
	•	Integrate frontend with backend API (using fetch/axios) to display real data from the database.
	•	Deliverable: A functional web app where a user can log in, view a list of tenders, search/filter them, and click for details.
	•	Sprint 4 (PDF Processing & Search/Embed Pipeline):
	•	Extend the scraper or a separate ingestion module to download tender PDF documents and perform text extraction and chunking (Section 6 details this).
	•	Compute embeddings for document chunks and store them (in PostgreSQL with a vector extension, or an external vector DB).
	•	Implement a basic search API: e.g., GET /tenders/search?q=... that can do a vector similarity lookup or keyword search combining tender metadata and document content.
	•	Deliverable: Users can search tenders by text queries (with relevant results returned using the combined metadata + content search powered by embeddings).
	•	Sprint 5 (AI Assistant Integration – Q&A Chatbot):
	•	Develop the retrieval-augmented generation (RAG) pipeline in the AI assistant agent. When a user asks a question (e.g., via a chat UI), the backend triggers the AI agent: it retrieves relevant chunks from the vector index and calls the LLM (Gemini API or another model) with those chunks as context ￼.
	•	Design prompt templates for the AI assistant (see Section 9) to ensure it understands domain-specific questions and provides grounded answers.
	•	Integrate a chat interface in the frontend where users can converse with the AI assistant about tenders.
	•	Implement a fallback mechanism: if the primary LLM (Gemini) is unavailable or yields no answer, use an alternate model (e.g., Claude or GPT-4) to maintain service continuity.
	•	Deliverable: An AI Q&A feature – users can ask questions like “Give me price trends for IT equipment tenders this year” and receive a coherent answer generated from the data.
	•	Sprint 6 (Billing & Subscription Tiers):
	•	Set up Stripe integration for subscription management. Create products/plans for Free, €99, €395, €1495 tiers (monthly billing). Implement Stripe Checkout or billing portal integration for users to upgrade plans.
	•	Add backend logic to enforce tier limits (e.g., Free tier may limit number of queries per month or accessible features like advanced analytics).
	•	Implement a usage tracking mechanism if needed (e.g., count API calls or track which features are used by which plan).
	•	Frontend: add a Pricing page and account billing management UI. Ensure the UI shows when a feature is locked due to plan and prompts upgrade.
	•	Deliverable: End-to-end billing flow – users can enter payment, subscribe to a plan, and the system recognizes their tier to unlock features accordingly.
	•	Sprint 7 (Notifications & Alerts, Polish):
	•	Implement alerting functionality: allow users to save search criteria or categories for tenders and get notified (via email or in-app notification) of new matching tenders. This involves a scheduled job to check for new tenders and matching user criteria.
	•	Add role-based access control and admin tools if needed (perhaps an admin dashboard to monitor usage or manage content).
	•	Perform comprehensive testing (unit tests for modules, integration tests for API endpoints, and UAT on the whole flow). Focus on security testing (e.g., ensure auth is properly enforced, no data leaks between tenants).
	•	Refine the UI/UX with responsiveness, better error handling, and help tooltips/documentation especially around the AI assistant’s capabilities and limitations.
	•	Prepare for internationalization: although the UI remains English for now, ensure text is easily replaceable for a Macedonian locale pack in future (e.g., using i18n libraries).
	•	Deliverable: A production-ready MVP with all key features, ready for deployment in North Macedonia’s market.
	•	Future Sprints (Post-MVP Scaling):
	•	Add support for additional countries’ tender data (new scraper agents targeting other e-procurement portals).
	•	Introduce multi-language support for non-English UIs and for the AI (e.g., enabling the assistant to answer in Macedonian).
	•	Enhance analytics: e.g., trend graphs in the dashboard, vendor performance analysis, etc.
	•	Explore a mobile-friendly interface or a dedicated mobile app.
	•	Deliverable: International and multi-language expansion with more advanced analytical features.

Each sprint builds on the previous, and thanks to the modular architecture, work on scrapers, AI pipeline, and UI can proceed in parallel by different Claude agents, converging in integrated testing phases.

3. Unified Database Schema (PostgreSQL)

A well-structured relational database underpins the entire system, storing both application data and AI-related artifacts (like embeddings). PostgreSQL is chosen for its reliability and ability to handle JSON and vector extensions. Below is the unified schema design with key tables and their purposes:
	•	users – Stores user accounts and profile info.
	•	Fields: user_id (PK), email, password_hash, name, role (e.g., “user” or “admin”), plan_tier (e.g., Free/Standard/Pro/Enterprise), stripe_customer_id, created_at, etc.
	•	Each user is associated with a subscription tier and possibly an organization (for enterprise accounts with multiple seats).
	•	organizations (optional) – If enterprise tier allows multi-user teams.
	•	Fields: org_id (PK), name, etc. (Plus billing info if needed).
	•	Relationship: one org to many users, with one user as owner/admin. For simplicity, MVP may skip this and tie each user directly to a Stripe subscription.
	•	subscriptions – Tracks Stripe subscription status (one per user or org).
	•	Fields: sub_id (PK), user_id (FK) (or org_id), plan (Free/Standard/Pro/Enterprise), status (active/cancelled), renewal_date, stripe_sub_id, etc.
	•	This table is updated via Stripe webhooks (e.g., when a payment succeeds or a subscription is canceled).
	•	tenders – Core table for tender notices (procurement opportunities).
	•	Fields: tender_id (PK, could be internal or the e-nabavki notice ID), title, description (brief summary), category, procuring_entity (e.g., which government department or agency is issuing it), opening_date, closing_date, estimated_value, status (open/closed/awarded), etc.
	•	Populated by the scraper. Text fields like description might be in Macedonian (initially), which is fine to store as UTF-8 text.
	•	Indexes on important fields (category, dates) to speed up searches/filters.
	•	documents – Stores documents (like PDFs) associated with tenders.
	•	Fields: doc_id (PK), tender_id (FK to tenders), doc_type (e.g., “Specification PDF” or “Contract PDF”), file_path or URL (if stored externally or path on disk/cloud), content_text (TEXT for extracted text content).
	•	The content_text holds the full text extracted from the PDF for search/embedding. (Alternatively, store this in a separate search index to keep DB lean, but using PostgreSQL JSONB or TEXT is convenient for RAG).
	•	Could also store an embedding vector per document or per chunk here if using pgvector extension (see embeddings table below).
	•	embeddings – (If using a separate table for vector search) Stores chunked text embeddings for RAG.
	•	Fields: embed_id (PK), tender_id (FK), doc_id (FK nullable, if some embeddings are from tender metadata vs. from docs), chunk_text, vector (VECTOR type), metadata (JSON with info like source page, section).
	•	Use PostgreSQL with pgvector extension, so that a VECTOR column can store high-dimensional floats and be indexed for similarity search ￼. Alternatively, an external vector DB like Pinecone can be used, but using pgvector keeps the stack unified.
	•	This table is populated after PDF text extraction: e.g., split each document’s text into ~500-token chunks and insert their embedding. Also consider embedding key tender fields (title, description) for semantic search on those.
	•	search_index – (Optional if not using embeddings table) Could be a Materialized View or a full-text index on tender titles/descriptions to support keyword search. PostgreSQL’s GIN indices with to_tsvector can provide full-text search for Macedonian and English text.
	•	queries (or chat_history) – Logs of AI assistant interactions (optional but useful for analytics and debugging).
	•	Fields: query_id, user_id, question_text, answer_text, timestamp, used_tokens, feedback (if user can rate answers).
	•	Storing questions and answers can help improve the system and also enforce usage limits (e.g., count queries per user per month for Free tier).
	•	alerts – Stores user-defined alerts criteria.
	•	Fields: alert_id, user_id, criteria_type (category/keyword/other filters), criteria_value (e.g., “IT Equipment” category or keyword “software”), created_at.
	•	This is used by an alerting job that matches new tenders against saved criteria and then generates notifications.
	•	notifications – (Optional) If implementing in-app notifications or storing email logs.
	•	Fields: note_id, user_id, tender_id (or alert_id), message, sent_at, read_flag, etc.

All relationships use foreign keys for referential integrity (with cascades on deletion where appropriate, e.g., deleting a tender could delete associated documents and embeddings). Below is a simplified ER diagram in text form:
	•	User (1) — (N) Subscription (if per user, or 1-1 if one sub per user)
	•	User (1) — (N) Alert (each user can have multiple alerts)
	•	Tender (1) — (N) Document (a tender can have multiple docs)
	•	Tender (1) — (N) Embedding (multiple chunks per tender)
	•	Document (1) — (N) Embedding (embedding chunks link to their source doc)

Each table’s schema is designed to be Claude-readable (clear naming, comments in the SQL DDL explaining each column) to ease future maintenance by AI agents. The database will primarily be filled by the scraper and used by the AI assistant for retrieval and by the API for serving content to the UI. By centralizing all data here, it ensures consistency – for example, the AI’s knowledge is always based on the latest data the scraper pulled, and any new tenders or updates only need to be updated in one place.

4. Claude Agent Modules – Prompt Instructions per Component

This section provides module-specific design prompts, written as commented outlines, for each Claude Code agent or code module. These prompts (embedded in code comments) are structured so that Claude can easily understand the requirements and generate the code for that module. Each module’s responsibilities and steps are clearly delineated:

4.1 Scraper Module (Claude Code Agent – Web Scraping for e-nabavki.gov.mk)

# AGENT: WebScraper
# Language: Python
# Role: Periodically scrape the North Macedonia public procurement portal (https://e-nabavki.gov.mk) for new tenders and updates.
# Strategy:
#    1. **Startup:** Load last scraped tender ID or timestamp from a state (file/DB) to avoid duplicates.
#    2. **Access Portal:** Navigate to the public tenders listings. Use an HTTP client (requests + BeautifulSoup) or a headless browser (Playwright) if needed for dynamic content.
#    3. **Parse Listings:** Identify HTML patterns for tender entries (title, ID, dates, category). The site likely lists tenders with unique IDs or links like "TenderDetails.aspx?id=XYZ". Extract key fields.
#    4. **Detail Page:** For each new tender found, fetch its detail page for full information (description, procuring entity, budget, etc.). Also gather links to attached documents (PDFs).
#    5. **PDF Download:** Download PDF files for the tender (specifications, forms, etc.). Save files to storage (local or cloud) and send to PDF processing (or do text extraction immediately).
#    6. **Data Storage:** Save tender data into the PostgreSQL DB (via an API call or direct DB connection). Ensure to populate `tenders` table (and `documents` table with file references and extracted text placeholder).
#    7. **Respect Politeness:** Abide by robots.txt and site terms – limit request rate (e.g., sleep 1-2 seconds between requests) and scrape during off-peak hours. Optionally randomize user-agent string or use an API provided by the site (if any) for public data.
#    8. **Error Handling:** Log errors (network issues, parsing issues) but continue with next item. Implement retry with backoff for robust crawling.
#    9. **Schedule:** Run this scraper agent daily (or multiple times a day) via a cron or scheduler. Alternatively, trigger it to run continuously with a delay loop, checking regularly for new tenders.
# Additional Notes:
#    - The e-nabavki portal may require login for some data; if so, use a service account. But public tender announcements should be accessible without login [oai_citation:2‡bjn.gov.mk](https://bjn.gov.mk/wp-content/uploads/2024/10/AnnualReport2009.pdf#:~:text=,Table%2011%20and) [oai_citation:3‡track.unodc.org](https://track.unodc.org/uploads/documents/UNCAC/WorkingGroups/workinggroup4/2025-June-17-20/Presentations/Presentation_North_Macedonia_E.pdf#:~:text=,in%20order%20to%20enable%20greater).
#    - Focus on *open tenders* initially. Later, a separate mode can scrape awarded contract results for completed tenders (to support historical analysis).
#    - Ensure all text is captured in original language (Macedonian) – do not translate content in scraping. Store text as UTF-8.
#    - Use environment variables or config for any credentials (if needed) and base URLs, to avoid hardcoding.

(The above prompt guides the scraper agent to implement efficient and lawful scraping of the procurement portal, retrieving all necessary tender information and documents. It’s written in a commented Python style, which Claude can directly use to generate a Python script.)

4.2 AI Assistant Module (Claude Code Agent – Retrieval-Augmented QA)

# AGENT: AIAssistant
# Language: Python
# Role: Provide an AI Q&A service over the tender data. Uses Retrieval-Augmented Generation (RAG) to answer questions about tenders.
# Steps:
#    1. **Query Intake:** Expose a function or API (e.g., answer_query(user_question)) that the backend can call with a user's question.
#    2. **Retrieve Relevant Data:** Parse the question for keywords or entities (e.g., "IT equipment", "last year"). Use the embeddings index in the database to find top-N relevant chunks (semantic search) [oai_citation:4‡cloud.google.com](https://cloud.google.com/use-cases/retrieval-augmented-generation#:~:text=Search%20with%20vector%20databases%20and,rankers). Also possibly do keyword filtering (e.g., if question mentions "IT equipment", filter tenders by that category).
#    3. **Prepare Context:** From the retrieval results, gather a set of text passages (chunk_text from DB, plus maybe tender titles or stats) that are most relevant. Construct a prompt context that includes these facts. Ensure not to exceed token limits (if necessary, summarize or truncate less relevant parts).
#    4. **LLM Prompting:** Call the LLM (preferably **Google Gemini** via its API) with a carefully formatted prompt that includes system instructions, user question, and the retrieved context as reference. For example:
#         SYSTEM: "You are an expert in public procurement data for Macedonia. Answer questions using the provided tender information. If quantitative analysis is needed, base it on data provided. Respond in English in a clear, professional tone."
#         USER: "<actual user question here>"
#         CONTEXT: "Relevant tender data: ... (e.g., list of contracts in IT equipment category with their prices and dates)..."
#         ASSISTANT: (the model will generate answer)
#    5. **Answer Generation:** The LLM (Gemini) produces an answer. If Gemini API supports tools like File Search (embedding search), leverage that for simplicity [oai_citation:5‡blog.google](https://blog.google/technology/developers/file-search-gemini-api/#:~:text=,data%20for%20accurate%2C%20relevant%20responses). If the response is not confident or empty, fall back to an alternative model (e.g., OpenAI GPT-4 or Anthropic Claude) using our own retrieval pipeline.
#    6. **Post-process:** Optionally, format the answer (Markdown, lists, etc., if the UI needs). Also, extract any sources or tender IDs mentioned to possibly provide links.
#    7. **Return Result:** Send the answer back to the backend, along with any metadata (e.g., which tenders were referenced or confidence score).
# Additional Considerations:
#    - **Gemini Integration:** If using Google’s Gemini API with File Search, you can preload tender documents into Gemini’s index and simply query it [oai_citation:6‡blog.google](https://blog.google/technology/developers/file-search-gemini-api/#:~:text=,data%20for%20accurate%2C%20relevant%20responses). Otherwise, use a local vector DB query and feed results in the prompt.
#    - **Fallback Logic:** Implement a simple check – if Gemini API call fails (exception or no answer), log it and then call an alternate LLM. This ensures high availability of the AI feature.
#    - **Numeric Analysis:** The agent might need to compute trends (e.g., average prices). LLMs can estimate if given data, but for high accuracy consider pre-calculating some stats. (For MVP, rely on the LLM’s reasoning over provided numbers).
#    - **Context Size:** Ensure the retrieved context + question fits the model’s context window. If the question is broad (requiring many documents), consider summarizing parts of data or informing the user to narrow the query.
#    - **Safety:** Include a system instruction to only use provided data (avoid speculation) to minimize hallucinations, and to refuse questions unrelated to tenders.

(The above instructions define how the AI assistant agent should perform retrieval and interface with the LLM. It emphasizes using the Gemini API’s RAG features if available and provides a fallback path. The prompt formatting and steps ensure Claude can implement a robust QA service.)

4.3 Backend/API Module (Server-side Application)

# AGENT: BackendAPI
# Language: Python (FastAPI) or Node.js (Express) - choose one consistent with team skill.
# Role: Provide RESTful API endpoints for the frontend and coordinate other modules (scraper, AI, billing).
# Responsibilities:
#    1. **User Auth:** Implement endpoints for user registration (hash passwords, store user), login (JWT issuance), and token verification middleware for protected routes. Support OAuth in future if needed.
#    2. **Tender Data Endpoints:** e.g., GET /tenders (with query params for filtering by category, date, etc.), GET /tenders/{id} for details (including related documents and possibly an AI-generated summary from the doc text). These handlers will query the PostgreSQL DB via SQL or ORM.
#    3. **AI Query Endpoint:** POST /ask (protected) – accepts a user question, calls the AI Assistant agent (perhaps via an RPC or just a Python function if integrated) to get an answer, then returns that answer to the frontend. Stream the answer if using streaming API (useful for longer responses).
#    4. **Alerts & Notifications:** POST /alerts to create a new alert criterion, GET /alerts to list, etc. Also, an endpoint for notifications if implementing (or push via WebSocket).
#    5. **Stripe Webhooks:** Expose an endpoint (e.g., /webhook/stripe) to receive events from Stripe. Handle events like `checkout.session.completed` or `invoice.paid` to activate a subscription, and `customer.subscription.updated` to handle cancellations or upgrades. Secure this endpoint by verifying Stripe signature.
#    6. **Billing Logic:** Provide endpoints to create Stripe Checkout sessions or Billing Portal links (so frontend can redirect users for payment). Also on login, check if user’s subscription is active (stored in DB from webhook).
#    7. **Admin Tools:** (If needed) Endpoints to list users, usage stats etc., restricted to admin role.
# Design:
#    - Organize code in a modular way: e.g., routes folder with auth.py, tenders.py, ai.py, billing.py for clarity.
#    - Use environment variables for config (DB URL, Stripe API keys, LLM API keys, etc.).
#    - Ensure proper error handling and return appropriate HTTP status codes (400 for bad requests, 401 for unauthenticated, 500 for server errors, etc.).
#    - Apply rate limiting or plan-based restrictions in middleware or in the specific handlers (e.g., if Free tier user -> limit certain endpoints).
# Performance:
#    - Use caching for frequent requests, like an in-memory cache for GET /tenders (or leverage HTTP caching headers on responses).
#    - For the AI answers, possibly cache recent Q&A for a user to avoid re-computation if they ask the same thing again.
# Security:
#    - Validate all inputs (especially for any query parameters to avoid SQL injection, though using parameterized queries/ORM mitigates this).
#    - Log important actions (logins, errors, Stripe webhook events) for audit.
# Integration with Agents:
#    - The backend might invoke the scraper agent (e.g., via a message queue or simply trigger on demand). However, since the scraper runs independently on schedule, the backend mainly reads its output from DB.
#    - The AI assistant can be integrated as a library call if in same codebase (for Python, the Claude agent code could be included). Alternatively, treat the AI assistant as a microservice with its own API.
# Testing:
#    - Include unit tests for each route’s logic (e.g., using FastAPI’s TestClient or Express supertest) to ensure correctness.

(This prompt guides the creation of the backend API, covering all major responsibilities from auth to billing. It ensures Claude will generate a structured server application with appropriate route handlers, middleware for auth, and integration points for Stripe and the AI agent.)

4.4 Frontend/UI Module (Next.js React App)

// AGENT: FrontendUI
// Framework: Next.js (React + TypeScript)
// Role: Provide an interactive web dashboard for users to view tender information, ask AI questions, and manage their account.
// Key Pages/Components:
//    1. **Login & Signup Pages:** Simple forms for authentication (email, password inputs). On success, store auth token (e.g., in HttpOnly cookie or local storage) and redirect to dashboard.
//    2. **Dashboard Page:** Overview after login. Show a summary of latest tenders (maybe a table of recently added tenders with key info). If applicable, show some metrics (e.g., count of open tenders, user’s alerts, etc.). Provide navigation to other sections like Search, Alerts, Account, AI Assistant.
//    3. **Tenders Search/List Page:** A page where users can search and filter tenders. Components:
//          - Filter sidebar or controls (keywords, date range, category dropdown).
//          - Results table or cards listing tenders (with pagination if many results). Each item shows title, agency, close date, value, etc., with a link or button to view details.
//    4. **Tender Details Page/Modal:** Shows full details of a tender: all fields, attached documents (as downloadable links), and possibly a section for "Insights" (where an AI summary or key points could be displayed). If the tender has an AI-generated summary of the PDF or previous Q&A, display it here for quick info.
//    5. **AI Chat Page/Widget:** A dedicated section for interacting with the AI assistant. 
//          - Could be a full page titled "Ask AI" with a chat interface (chat bubbles for Q&A) or a floating chat widget accessible from any page (so users can ask questions contextually).
//          - Implement a chat component with an input box and send button. Display conversation history above. Show a loading indicator while awaiting response.
//          - Support markdown in the assistant's answer (e.g., if lists or tables are returned) by using a React Markdown renderer.
//    6. **Alerts Management Page:** Form for users to create a new alert (choose criteria like category or keywords, maybe via multi-select or text input). List any existing alerts with option to delete. Explain that alerts will notify when new tenders match.
//    7. **Account/Billing Page:** Shows the user’s current plan, usage statistics (e.g., queries used this month), and a button to upgrade/downgrade. The upgrade button leads to Stripe Checkout. If Free, label features that are locked with an upgrade prompt.
//    8. **Admin Page:** (If admin role) – view overall stats, user list, etc. (Optional for MVP).
// Layout & Navigation:
//    - Use a consistent header or sidebar for navigation between pages (Dashboard, Tenders, Ask AI, Alerts, Account).
//    - Show user’s name and plan in header with a dropdown for account settings/logout.
//    - Ensure the design is responsive (mobile-friendly, since some users may check alerts on phone).
// Integration:
//    - Use Next.js API routes or directly call the backend API endpoints for data. For example, fetch tender list in getServerSideProps or via SWR on the client side.
//    - Manage auth token in requests (attach JWT in Authorization header or rely on cookie if using cookie auth).
//    - Use WebSocket or SSE for real-time alerts if implementing push notifications (e.g., new tender alert could pop up a toast).
// Styling:
//    - Use a component library or custom Tailwind/CSS for a clean, enterprise look. Keep it simple and data-focused (tables, modals, forms).
//    - Indicate clearly features that require a higher tier (e.g., a tooltip or lock icon on AI chat if user is free and that’s paid).
// Testing:
//    - Utilize React testing library for component tests, and Cypress or Playwright for end-to-end flows (login -> search -> ask AI).

(This prompt outlines the frontend structure. It ensures the Claude agent will generate a Next.js project with all necessary pages and components, focusing on usability and integration with backend and Stripe. It mentions where dynamic data comes into the UI and emphasizes clarity and responsiveness.)

4.5 Billing Integration Module (Stripe integration logic)

# AGENT: BillingIntegration
# Language: Python (for backend portion) and JavaScript/React (for frontend)
# Role: Implement subscription plans (Free, €99, €395, €1495 tiers) using Stripe's subscription API.
# Backend Responsibilities:
#    1. **Stripe Setup:** Use Stripe SDK (Stripe Python or Node library) with secret keys. Define Product and Price IDs in config for each tier:
#         - Free tier: (Handled as special case – no payment, but consider creating a $0 Stripe plan for tracking [oai_citation:7‡reddit.com](https://www.reddit.com/r/stripe/comments/x6yxc4/optimal_approach_to_implementing_a_freetier_in/#:~:text=Use%20Stripe%20for%20the%20free,minimal%20coding%20on%20your%20part)).
#         - Standard tier (€99/mo), Pro tier (€395/mo), Enterprise tier (€1495/mo) – these have price IDs from Stripe dashboard.
#    2. **Checkout Session:** Provide an endpoint (e.g., POST /billing/checkout) that takes the target plan and creates a Stripe Checkout Session for that plan, tied to the authenticated user’s Stripe customer ID. Return the session URL for the frontend to redirect.
#    3. **Customer Portal:** Optionally provide an endpoint to create a Stripe customer portal session (so users can manage payment methods, cancel subscription, etc., via Stripe-hosted pages).
#    4. **Webhook Handling:** Listen to Stripe webhooks for subscription events:
#         - On `checkout.session.completed`: mark the subscription as active in our DB (update user’s plan_tier and record stripe_subscription_id).
#         - On `invoice.payment_failed` or `customer.subscription.deleted`: mark subscription as inactive or grace period in our DB.
#         - On `customer.subscription.updated`: adjust plan details if the user upgraded/downgraded.
#         (Use Stripe’s event types and the subscription object in the payload to update our database accordingly.)
#    5. **Free Tier Logic:** We treat free users as having a subscription too (possibly via a $0 plan in Stripe for consistency [oai_citation:8‡reddit.com](https://www.reddit.com/r/stripe/comments/x6yxc4/optimal_approach_to_implementing_a_freetier_in/#:~:text=I%20see,be%20additional%20conditional%20logic%20otherwise), so that every user has a Stripe customer and can easily upgrade). Alternatively, manage free tier purely in-app (no Stripe object until upgrade) – but using Stripe for free tier simplifies checking "is user subscribed?" with one code path.
#    6. **Plan Enforcement:** Middleware or logic in endpoints to check the user’s plan before serving:
#         - e.g., If a Free tier user calls the AI endpoint and they’ve exceeded a monthly query limit, return a 402 or an error indicating upgrade needed.
#         - Only Enterprise tier can access certain advanced analytics or have multiple user seats (if implemented).
# Frontend Responsibilities:
#    7. **Pricing UI:** Clearly display the features of each tier (in a pricing page or on the account page). For example:
#         - Free: Limited to e.g. 5 AI queries/day, basic search, 1 alert.
#         - €99/mo (Standard): e.g. 50 queries/day, unlimited search, 5 alerts, email support.
#         - €395/mo (Pro): higher limits, maybe multiple user logins (if org support), priority support.
#         - €1495/mo (Enterprise): custom limits, multiple accounts, dedicated support, perhaps data export features.
#         (These are examples; finalize exact limits/benefits per tier).
#    8. **Checkout Flow:** When user clicks "Upgrade" on account page, call backend to get Checkout Session URL, then use JavaScript (Stripe.js) to redirect to the Stripe checkout page.
#    9. **Post-Checkout:** After payment, Stripe will redirect back (configure a return URL). On that page, frontend can display "Success, you are now subscribed to [Plan]" and prompt a refresh of user data.
#    10. **Account Status:** The account page should call an API (or decode JWT) to get current plan and status. If payment is pending or sub canceled, show that info.
# Security & Testing:
#    - Keep Stripe secret key on backend only. Use the publishable key in frontend for Stripe.js if needed for client-side tokenization (though for subscriptions, mostly handled via checkout).
#    - Test the webhook flow using Stripe CLI or test webhooks to ensure the app updates correctly on subscription events.
#    - Make sure to handle currency and tax as needed (Stripe does pricing, so likely fine).
#    - Ensure idempotency in webhook handler (Stripe might resend events).

(The billing module prompt details how to integrate Stripe for the subscription tiers. It references best practices like using Stripe’s customer portal and even suggests using a $0 free-tier product so that even free users are tracked in Stripe ￼. Claude can use this to implement robust billing logic.)

4.6 Authentication & Authorization Module (User Management & RBAC)

# AGENT: AuthModule
# Language: Python (if part of Backend API) 
# Role: Manage user authentication, account security, and role-based access.
# Features:
#    1. **User Registration:** Endpoint to create a new user (collect email, password, maybe name). Validate email format and password strength. Hash passwords using bcrypt or Argon2 before storing. If using email confirmation, generate a token and email it (optional for MVP).
#    2. **Login:** Endpoint to authenticate (verify password) and return a JWT or session cookie. Include user’s role and plan in the token claims for easy checking on frontend.
#    3. **Password Reset:** (Optional) Endpoint to initiate password reset (email a link with token) – can be implemented later if needed.
#    4. **JWT Middleware:** Middleware to parse JWT from Authorization header (or cookie) on protected endpoints. Verify signature and expiration. Attach user info (ID, role, plan) to request context for handler to use.
#    5. **Role-Based Access Control:** Use the user’s role/plan from token to guard certain endpoints:
#         - e.g., Only admin role can access admin routes.
#         - Only Pro/Enterprise can access certain analytics routes (if any).
#         - Implement as a decorator or middleware that checks required role/tier on the endpoint.
#    6. **Account Management:** Endpoint to fetch the logged-in user’s profile and subscription info (so frontend can display it). Also allow user to update profile info or delete account (GDPR considerations).
#    7. **Security Measures:** 
#         - Protect against brute-force: e.g., rate limit login attempts by IP or use captcha after many failures.
#         - Use HTTPS for all requests (especially login) in production.
#         - HttpOnly cookies for JWT if SPA pattern (to mitigate XSS stealing tokens).
#         - Regularly review dependency vulnerabilities for auth library.
#    8. **Multi-language support prep:** Though UI is English now, design the auth messages (emails, errors) so they can be translated later (e.g., using a message template system).
# Testing:
#    - Write unit tests for auth flows: correct password allows login, wrong password denies, protected route rejects missing token, etc.
#    - Test a variety of roles and plans to ensure the access control logic works (simulate a Free user vs. Pro user on an endpoint).

(This prompt ensures the Auth module is properly implemented, covering everything from user signup to JWT verification and role/tier enforcement. Claude will use these guidelines to implement secure authentication flows.)

Each of the above module prompts is marked with a clear header (# AGENT: or // AGENT:) so that Claude can identify and work on them in isolation. These commented instructions serve as in-line documentation and tasks breakdown for the AI, ensuring each sub-system is built to specification.

5. AI Assistant Pipeline & Retrieval Architecture (Gemini Integration)

The AI assistant uses a Retrieval-Augmented Generation (RAG) architecture ￼ ￼ to leverage the tender data for answering user queries. The pipeline comprises several steps to ensure accurate and context-rich responses:
	•	Document Embedding & Indexing: All tender texts (including PDF content and key metadata) are converted into vector embeddings and stored in a vector index (either pgvector in Postgres or an external service). This allows semantic similarity searches: given a query, we can find relevant documents even if exact keywords aren’t matched ￼. The system may also maintain a keyword index for precise filters (like category or date constraints).
	•	Query Understanding: When a user asks a question (through the chat UI or an API call), the AI assistant first interprets the query. This may involve simple NLP tasks like identifying the time frame (“last year”), category (“IT equipment”), or specific entities (agency names, supplier names). This understanding can be used to narrow down the search scope (e.g., filter by category if mentioned).
	•	Hybrid Retrieval (Semantic + Symbolic): The assistant performs a search for relevant information:
	•	Semantic Vector Search: Use the embeddings to find the top relevant chunks of tender text that might contain the answer. For example, for “price trends for IT equipment”, the search might retrieve all tender records or documents related to IT equipment purchases, especially those containing prices and dates.
	•	Keyword Filtering: Optionally, also apply traditional filtering (e.g., restrict to tenders whose category is IT equipment, if known; or if query mentions 2024, filter tenders by year 2024). This can improve precision by not misleading the semantic search.
	•	Re-Ranking: If many results are found, the system can rank them by relevance (a combination of vector similarity and keyword overlap). Advanced implementations might use a re-ranker model to score relevancy more accurately ￼, but a simple approach is fine for MVP (e.g., take top 5-10 most similar chunks).
	•	Context Construction: The retrieved pieces of information (e.g., a snippet: “Tender X for IT equipment in 2023 had a winning bid of €100k…”) are compiled into a context for the LLM. This context is usually prepended or appended to the prompt given to the LLM. Since LLMs have input size limits, we include only the most relevant information. The context might be formatted as a bullet list of facts or as raw text paragraphs. For example:
	•	Context: “Tender 123 (IT Equipment, 2022): awarded price €95,000; Tender 456 (IT Equipment, 2023): awarded price €110,000; Tender 789 (IT Equipment, 2024): awarded price €120,000…” – if the query is about price trends, these data points can help the LLM see the trend.
	•	LLM (Gemini) Query: We then send a prompt to the LLM. If using Google Gemini, we have two primary modes:
	1.	Using Gemini’s File Search API: Upload or reference documents via Gemini’s retrieval system. Gemini’s File Search acts as a managed RAG – you provide your documents to the API, and at query time you simply ask the question and Gemini will retrieve from those docs internally ￼. This simplifies our pipeline (Google handles embedding, searching, and maybe some reasoning).
	2.	Manual Prompt Construction: If we use Gemini (or another model) directly, we include the context ourselves. The prompt might look like:
	•	System: “You are TenderGPT, an AI assistant specialized in public procurement data. Answer the user’s question based on the provided documents.”
	•	User: “Give me price trends for IT equipment over the last 3 years.”
	•	Assistant: (Gemini will output the answer)
	•	Context (in the prompt): We might include something like “Relevant data: (list of yearly IT equipment tender prices…)” before the assistant part.
	•	Fallback LLM: If Gemini is not available (e.g., cost or access issues), the system can use an alternative like OpenAI GPT-4 or Anthropic Claude. In that case, our pipeline’s manual context construction is used (since those models can accept context as well). The switch can be controlled via config: e.g., a flag USE_GEMINI=True toggles the integration. If False, use local embeddings + OpenAI API (for example).
	•	For open-source fallback (if we need an offline model), we could incorporate a local LLM like Llama 2, but those might have context length or quality limitations. Given this is a cloud SaaS, using a high-quality API model is preferred for best answers.
	•	Answer Generation and Grounding: The LLM generates an answer to the user’s question using the context. RAG ensures that the answer is grounded in real data ￼ – meaning it should reflect the facts provided rather than the model’s imagination. For example, instead of guessing, it will base “price trends” on the actual numbers from the documents. We instruct the model (via system prompt) to only use provided information and if possible, to reference tender IDs or dates when giving figures, to increase transparency.
	•	Result Post-processing: Once the LLM returns the answer, the AI assistant agent can do minor post-processing. For instance:
	•	Ensure the answer is in the desired language (English for now). If in the future we allow the user to specify language (Macedonian), the assistant can translate or directly prompt the model in that language.
	•	Format the answer if needed (the front-end can also style it).
	•	If the model returned any references (like “Tender #123”), the assistant could hyperlink those IDs using known URLs or include them as part of the answer metadata.
	•	Fallback Behavior: If the model cannot find relevant info or the question is outside the domain, the assistant should return a polite message indicating no data (rather than hallucinating). The system prompt will stress that if unsure or data not found, respond with an appropriate statement (“I’m sorry, I couldn’t find information on that.”). Also, if our retrieval yielded nothing (e.g., user asks about a tender that doesn’t exist), we can short-circuit and respond accordingly.

Gemini and Long-Term Strategy: The advantage of using Gemini is its expected multimodal and long-context capabilities ￼ – it could handle large amounts of tender text and perhaps even the PDF content directly. As the product scales to more data or other countries, relying on a managed RAG service could offload a lot of complexity (scaling vector indices, etc.). However, we maintain the fallback pipeline in-house to avoid single dependency risk. This design ensures the AI assistant is robust: using the best available model while keeping control of our data and having a backup method.

Performance and Monitoring: The RAG pipeline will be monitored for:
	•	Latency: The combination of DB retrieval and LLM API call should ideally return answers in a few seconds. We might cache common queries or pre-embed frequent asked concepts to speed up retrieval.
	•	Accuracy: We will continuously refine the prompt templates and retrieval ranking. We might log when the LLM’s answer seems irrelevant or incorrect despite having data, to later adjust the system (e.g., provide more context or refine the instructions).
	•	Cost: Calls to LLM APIs (Gemini/others) will incur costs. We will track usage per user and overall, to ensure it aligns with subscription limits and profitability (this ties into the billing logic – e.g., Free tier might have lower daily limits to control cost).

In summary, the AI assistant pipeline is a closed-loop system where user queries are answered using up-to-date tender knowledge from our database. It uses Claude’s capabilities in orchestrating retrieval and language generation to provide an intelligent layer on top of raw procurement data, making it easier for users to get insights.

6. PDF Document Ingestion and Processing

Many tender notices include attached documents (tender specifications, forms, contracts) typically in PDF format. To enable full-text search and detailed Q&A, the system must ingest these PDFs effectively:

Scraping and Storage of PDFs: The scraper module, upon finding a PDF link for a tender, will download the file. Depending on scale, we might store the PDF files in:
	•	A dedicated file storage (like an AWS S3 bucket or locally on the server in a structured folder).
	•	The documents table will have a reference (file path or URL) to where the PDF is stored for later retrieval or download via the UI.

Text Extraction: Once downloaded, we extract text from the PDF:
	•	Use a Python library like PyMuPDF (fitz), PDFPlumber, or Tika to reliably extract text from PDF files. PyMuPDF is fast and can handle Macedonian characters.
	•	Extracted text is stored in the documents.content_text field (or a separate table if needed). We also record the length of text and possibly split by page or section (some PDFs may contain multiple sections like technical specs vs. legal terms).
	•	If PDFs contain tables or special formatting that doesn’t extract well, consider capturing them as is or noting that some data might need special handling (for MVP, straightforward text extraction is fine).

Text Chunking: Long documents cannot be fed entirely into an LLM context at once, and indexing large texts improves search:
	•	We split the text into chunks, ideally by semantic boundaries. For example, split by paragraph or section headers. If that’s not easily detectable, use a simple strategy like splitting every N sentences or ~300-500 words, ensuring chunks overlap a little to not cut important info. Also ensure chunks do not exceed, say, 500 tokens (to comfortably fit several in LLM context if needed).
	•	Each chunk is stored (in the embeddings table) along with metadata: which document and tender it came from, and maybe which page or section it corresponds to. This is useful if we want to display or cite the source of a snippet in the answer.

Embedding Generation: For each chunk:
	•	Use an embedding model to convert the text into a vector. This could be:
	•	An API like OpenAI’s text-embedding-ada-002 (which is multilingual and can handle Macedonian text).
	•	Or a local model via libraries (like sentence-transformers, e.g., all-MiniLM or multilingual MPNet). If using local, ensure it’s reasonably good with Macedonian (likely a multilingual model).
	•	If using Google’s Gemini File Search, we might skip manual embedding and instead upload the text through their API which handles embedding under the hood ￼. Otherwise, we do it ourselves and store vectors in the DB.
	•	We attach each embedding vector to the corresponding chunk record in the DB (if using pgvector) or push it into an external vector store with an ID reference to our DB record.

Index Maintenance: This ingestion process can be continuous:
	•	When new tenders or new docs appear, extract and embed them.
	•	We might set up a separate Claude agent or a background worker for “Document Processing” that waits for new docs (the scraper can mark new docs needing processing, or simply call the processing functions after download).
	•	In case a document is updated or corrected, we should update the stored text and re-embed if necessary (likely a rare case, but possible).
	•	Over time, if the index grows large (thousands of documents), consider performance: vector search should still be fine with an index on pgvector or with approximate search if needed. We may also archive older tenders if not needed (or move them to cheaper storage but still indexable if queries ask historical questions).

Quality of Extraction: Not all PDFs are text-based (some might be scans). If text extraction yields nothing or gibberish (image scans), we might integrate OCR (e.g., Tesseract). However, OCR for multiple languages adds complexity and might not be needed if most procurement PDFs are digitally generated. For MVP, log any PDFs that failed extraction and handle them manually or mark them as unavailable for search.

Storing Summaries (Optional): As an optimization, we could pre-generate an AI summary of each PDF (like a short summary of tender requirements). This summary can be stored in the DB (e.g., a summary field in documents or tenders). This way, for general questions like “What is this tender about?”, we can serve the summary without hitting the LLM each time. We can use Claude or GPT to generate these offline. This is a nice-to-have if time permits; otherwise, on-demand summarization can be done by the AI assistant.

Data Privacy Consideration: Tender documents are public, so privacy isn’t a big issue, but we should still handle them securely:
	•	Ensure no injection of malicious PDF content – e.g., if a PDF had some script (unlikely in PDF, but just ensure our parser libraries are updated to avoid vulnerabilities).
	•	When users download a PDF via our app, it should be the exact file from the official source (or our stored copy) – ensure the file is not tampered with.

By implementing this PDF ingestion pipeline, the system can answer detailed questions (since many important details might only be in the tender docs, not the short description). It transforms the service from just a listing of tenders into a knowledge base of procurement information that can be queried and analyzed.

7. Stripe Integration Model (Subscription Tiers)

The platform will offer four tiers: Free, Standard (€99/month), Pro (€395/month), and Enterprise (€1495/month). Using Stripe for billing allows us to automate payments and manage subscription state.

Stripe Account Setup: In Stripe’s dashboard, we will create:
	•	Products for each tier, each with a recurring price (monthly). For example, a product “Tender Intelligence Standard” with price €99/month.
	•	A free tier can be represented in Stripe as a product with €0 pricing. While not strictly necessary (we can handle free outside Stripe), it is beneficial to create a $0 subscription plan ￼. This way, every user can have an associated Stripe subscription object (free or paid), which simplifies upgrade logic and record-keeping.
	•	Webhook endpoints must be configured in Stripe to point to our backend (for handling events).

User Signup and Free Tier:
	•	When a user signs up, by default they are on the Free plan. We can either:
	•	Automatically create a Stripe customer for them and subscribe them to the free plan via Stripe’s API.
	•	Or delay creating a Stripe customer until they initiate a checkout for paid plan.
	•	Using the first approach (create customer & free sub on signup) lets us use Stripe’s Customer Portal even for free users (they could self-upgrade) and unify the subscription logic. As one Stripe expert noted, using Stripe for the free tier means all subscription checks go through one system ￼.
	•	The users table has plan_tier = “Free” initially, and may also store stripe_customer_id. If we subscribe them to free plan, we’ll get a stripe_subscription_id as well.

Checkout for Upgrades:
	•	The frontend “Upgrade” button (for Standard/Pro/Enterprise) will call our backend (e.g., POST /billing/checkout with desired plan). The backend uses Stripe API to create a Checkout Session:
	•	It will include the price ID for the chosen plan.
	•	Set the customer to the user’s Stripe customer ID.
	•	Set success_url (e.g., ourdomain.com/account?upgrade=success) and cancel_url.
	•	The user is redirected to Stripe’s hosted Checkout, enters payment info. Stripe handles EU VAT if applicable, etc.
	•	On success, Stripe will redirect back. Our frontend can then inform the backend or rely on webhooks to finalize.

Stripe Webhooks: We configure a webhook (e.g., /webhook/stripe on our backend) to listen for:
	•	checkout.session.completed – indicates user successfully paid and subscription is active. We then:
	•	Mark the user’s plan in DB to the new tier.
	•	Record the Stripe subscription ID and status (active) in subscriptions table.
	•	Possibly grant some immediate access if needed (though they likely already have it after redirect).
	•	invoice.payment_failed – if a renewal fails, we might notify the user via email (Stripe can also do this) and set a flag that their account is grace period or past due.
	•	customer.subscription.deleted (or canceled) – if user cancels or the subscription ends, mark their plan in our DB as Free (or inactive) after the current period. Possibly restrict features if cancellation is immediate.
	•	customer.subscription.updated – handle upgrades/downgrades initiated from Stripe’s portal or admin. E.g., if a user upgrades from Standard to Pro mid-cycle, Stripe might prorate. We update their plan_tier accordingly.

Our webhook handler will verify the event’s signature (using Stripe’s signing secret) to ensure authenticity.

Tier-Based Feature Control:
	•	The backend will check the user’s tier (from JWT or DB) on certain endpoints:
	•	The AI Q&A endpoint: Free tier might be limited to say 5 queries per day. We can enforce this by counting requests per user per day (store counters in Redis or DB).
	•	Alerts: Free might allow 1 alert; paid tiers more (Standard: 5, Pro: 20, Enterprise: unlimited, for example).
	•	Data export (if any feature like CSV export of tenders) might be only for higher tiers.
	•	Multi-user access: Possibly Enterprise tier will allow inviting teammates. If implemented, that ties into the organizations in DB; likely an Enterprise org can have multiple user accounts linked. This can be enforced by checking plan and then allowing creation of new users under an org.
	•	The frontend should visually reflect limitations: e.g., if a Free user opens the AI chat, we might show “(5/5 queries used today)” and disable input if they hit the limit, prompting upgrade. Similarly, if they try to create more alerts than allowed.
	•	These limits and features should be defined in a config or easily adjustable, as we might tweak them based on usage.

Stripe Customer Portal: To reduce our effort in building billing management UI, we can leverage Stripe’s customer portal. This is a hosted page where users can update their card, switch plans, or cancel.
	•	We can provide a “Manage Billing” link in the Account page that hits our backend to create a portal session (Stripe API call) and returns the URL. The user then goes to that URL to manage subscription.
	•	This way, we don’t have to implement card updates or cancellation UI ourselves; Stripe handles it and sends webhooks for changes.

Testing the Billing Flow: We will use Stripe’s test mode and Stripe CLI to simulate events. We’ll create test prices for €99, €395, €1495 and ensure:
	•	Free signup correctly creates a free sub (or not, depending on approach).
	•	Upgrading to Standard goes through, webhook updates user.
	•	Downgrading or canceling works and our system reflects it.
	•	We also account for if a user tries to cheat (like calling the AI beyond limit), our server still prevents it based on DB counters.

Compliance: Since we charge in Euros and likely in Macedonia:
	•	Ensure to comply with tax/VAT rules (Stripe can handle EU VAT if configured).
	•	Terms of service and maybe an agreement should be in place (legal aspect, out of scope for coding but worth noting we should have a terms page and require agreement on signup or purchase).

Plan Summaries:
	•	Free: Ideal for trial and basic use. Possibly allows only recent tenders (e.g., last 30 days of data), and maybe limited AI queries/day, and no advanced analysis.
	•	Standard (€99): For small businesses – access to full local tender database, moderate AI usage (e.g., 100 queries/month), few alerts.
	•	Pro (€395): For larger companies – higher limits (e.g., 500 queries/month), priority email support, more alerts, possibly historical data analysis or integration (maybe an API access for their internal systems? Could be a future idea).
	•	Enterprise (€1495): For enterprise clients – unlimited or very high limits, ability to have team accounts, dedicated support, perhaps custom features (like custom data integration or on-prem deployment if needed).
	•	These specifics can evolve, but our system should be flexible to enforce whatever limits we set.

By integrating Stripe in this manner, we ensure reliable recurring revenue management. The modular design (the BillingIntegration agent prompt above) means Claude can generate the necessary webhook handlers and checkout flows with minimal custom code, as Stripe’s SDK and docs provide a lot of the heavy lifting. This approach also keeps us from storing sensitive payment info (all handled by Stripe securely).

8. Scraping Strategy for e-nabavki.gov.mk

Scraping the official North Macedonian e-Procurement portal (https://e-nabavki.gov.mk) must be done carefully and ethically. The strategy involves understanding the site’s structure, adhering to legal boundaries, and setting up a robust mechanism to fetch new data without overloading the site.

Legal and Ethical Considerations:
	•	Terms of Use: We must check if the portal has an explicit API or data sharing policy. Some government sites provide open data access or require permission for scraping. Since the data is public (as per law all concluded contracts are public ￼), using it should be legal, but we should ensure compliance with any usage policies.
	•	Robots.txt: Respect the directives given by https://e-nabavki.gov.mk/robots.txt. If certain paths are disallowed, avoid scraping them. If the whole site disallows bots, we might need to request data directly or obtain permission.
	•	Rate Limiting: Implement a rate limit on requests. For example, at most 1 page per second, and maybe no more than X pages per minute, to avoid stressing the servers. Since tender data doesn’t update by the second, we can afford to go slow.
	•	Off-Peak Scraping: Schedule the scraper during times when user traffic is low (late night or early morning local time). This reduces the chance of interfering with legitimate user access.
	•	Identification: It’s good practice to identify our scraper via the User-Agent string (e.g., “Mozilla/5.0 (compatible; MK-TenderIntelligence-Bot/1.0; email: contact@ourdomain.mk)”). This transparency helps the site admins know who is accessing. Providing a contact email in User-Agent is sometimes done in academic scrapers.

Understanding Site Structure:
	•	The portal likely has a section listing open tenders. Possibly an “Open Tenders” page or search page. For example, many eProcurement systems have search filters for status (open, closed, awarded).
	•	Tenders might have an ID or code. The URLs might be like /PublicAccess/NoticeDetails.aspx?id=12345 or similar. We saw hints of “Infrastructure.asmx/LoadLanguage” which suggests parts of the site use AJAX or web services.
	•	There might be an API: The presence of services/Infrastructure.asmx hints at SOAP web services. If a web service exists to query tenders (maybe for integration purposes), we should investigate that. Using an official service (if documented) is preferable to HTML scraping. If none is accessible, proceed with HTML parsing.

Scraping Steps (Implementation Details):
	•	Listing Page Scrape: Find how tenders are listed. Possibly on the homepage (PublicAccess) or a dedicated search page. We may need to simulate a search for all open tenders or iterate through pages.
	•	If an HTML table of tenders is present, parse each row to get basic info and a link/ID.
	•	If the site requires a form submission (common with ASP.NET WebForms), our scraper might need to mimic that (e.g., sending a POST with certain viewstate parameters). Using a tool like requests_html or Playwright might simplify this if the listing is behind an interactive search form.
	•	Pagination: If there are multiple pages of results, ensure to handle pagination (find “next page” links or page indices and loop through).
	•	Detail Page: For each tender, navigate to the detail page which has comprehensive info. Extract:
	•	Description text, criteria, any lots or lots info if present.
	•	Key dates (publication, deadline, etc.).
	•	Procuring entity name.
	•	Any results (if the tender is closed and has winner info, if that’s public).
	•	Document links (PDFs usually).
	•	Document Download: Access each document URL. They might be behind an authenticated link or direct download. If the site uses cookies or sessions, the scraper should maintain those (requests will handle cookies by default if same session).
	•	Data cleaning: Normalize fields (e.g., convert dates to ISO format, remove currency symbols from values to store numeric values, etc.). Many fields might be in Macedonian (e.g., “Датум на објава” for publication date) – our scraper can either have a mapping or simply treat those as fixed labels to parse.
	•	Frequency: New tenders are posted regularly (daily). We should run the scraper at least once a day to capture new ones. If near a deadline (maybe many tenders posted at end of year or quarter), could increase to twice daily. Avoid constant scraping since data changes relatively slowly.
	•	Change Detection: We should also handle updates – sometimes tender deadlines get extended or clarifications issued. We might identify tenders by a unique ID and if we see the same ID scraped again with changes (e.g., status changed from open to awarded), update the record in DB. This means scraper should allow updating existing DB entries (not just insert new).
	•	Scraping Historical Data: Initially, we likely want to backfill some history (e.g., last year’s tenders) for the AI to have context for “trends”. This could be done by running the scraper for closed tenders as well. Perhaps add a mode or parameter for scraping “all tenders in 2022”, etc., and populate the DB. This is a one-time heavy load; we must throttle more gently for large historical scrapes.
	•	Scaling for International: When expanding beyond MK, we will create similar scrapers for other countries’ portals. To facilitate that, design the scraper module in a configurable way (maybe separate the parsing logic from the core pipeline, so new sites can be added as plugins). But for now, focus on e-nabavki specifics.

Link Patterns Example (Hypothetical):
	•	PublicAccess/OpenTenders.aspx?page=1 – listing page.
	•	PublicAccess/Dossier.aspx?id=XYZ – maybe the details.
	•	The PDF links might be something like File/DownloadPublicFile.aspx?ID=abc123.
We will confirm by inspecting the HTML structure (one could do a quick manual check or use developer tools). The scraper can search the HTML for <a href="File/DownloadPublicFile?f=..."> links.

Politeness & Monitoring:
	•	Implement logging in the scraper: each run logs how many tenders fetched, how long it took, any errors. This helps monitor if the site layout changes (scraper might then fail to find expected elements).
	•	If the site introduces anti-scraping (like blocking our user-agent or IP after a while), we may need to adjust (e.g., slower, or use rotating proxies if absolutely necessary). But since this is public interest data, hopefully no such blocks if we behave.

By following this strategy, we ensure that our data collection is thorough, up-to-date, and does not violate terms. Keeping a good relationship with the data source (maybe informing the Public Procurement Bureau if needed) could be beneficial, especially as the product grows (maybe they even provide a feed if asked).

9. Prompt Template Structure for AI Assistant (MCP-Style Queries)

To effectively handle user queries in the style of “Give me X based on Y”, we craft a prompt template that guides the LLM to provide helpful answers specifically about tenders. The acronym MCP here can be interpreted in context as our Model/Claude Prompt style that might be inspired by the “model-context-protocol” from multi-agent setups, ensuring consistency and clarity.

User Query Pattern: Users will likely ask in natural language, possibly very domain-specific:
	•	“Give me price trends for IT equipment in the last 3 years.”
	•	“Which companies have won the most public contracts in 2024?”
	•	“Summarize the tender requirements for Tender 123/2023.”
	•	“List open tenders in the healthcare sector with deadlines in next month.”

The AI should handle these by retrieving relevant data and responding succinctly.

Prompt Template Design: We will use a structured prompt that includes the following parts:
	1.	System Instruction: Defines the role and scope of the AI. For example:
	•	“You are a tender procurement analysis assistant. You have access to a database of public tenders and their details. Answer the user’s question using the data provided, and do not speculate beyond the data. If calculations are required, perform them based on the data. Provide answers in English, in a clear and concise manner.”
	•	This ensures the model knows to behave like an analyst focused on tenders.
	2.	Context Insertion: This is where we inject retrieved data. One format (to clearly delineate it) is:
	•	“Context: {Here we list facts…}”
	•	For example:

Context:
- IT equipment tenders 2022: average awarded price €95k (from Tender A, Ministry of Education).
- IT equipment tenders 2023: average awarded price €110k (from Tender B, Ministry of Health).
- IT equipment tenders 2024: average awarded price €120k (from Tender C, Ministry of Defense).


	•	Or if listing top companies:

Context:
- Company ABC won 5 contracts in 2024 (total value €300k).
- Company XYZ won 3 contracts in 2024 (total value €250k).
- …


	•	The context may also include excerpts from documents if the question is detailed (e.g., “The tender requires the supplier to have ISO certification…” taken from a PDF).
	•	We label it clearly so the model can distinguish between context and user query.

	3.	User Question: Then we explicitly present the user’s question, for clarity. E.g.:
	•	“User’s question: Give me price trends for IT equipment in the last 3 years.”
This ensures the model knows exactly what to answer, after reading the context.
	4.	Answer Guidelines (optional): We might add a brief assistant instruction after the context if needed, such as:
	•	“Considering the data above, provide a brief summary of the price trends. Quantify the increase or decrease and mention any notable factors. Do not mention data that is not in the context.”
	•	This helps focus the answer. In multi-agent setups, sometimes such directives are given to ensure the response is grounded and formatted well.

Using MCP or Multi-Agent Protocol: In some multi-agent frameworks, a special triple-hash (###) or similar formatting is used to separate roles/instructions. For our purpose, a simpler approach suffices, but we can incorporate markers if needed:
	•	Possibly format as:

### System:
(system instructions)
### Context:
... facts ...
### Question:
... user question ...
### Answer:
(this is where the model responds)

This structure, reminiscent of certain chain-of-thought prompting or tools like LangChain, can help ensure each part is distinct. Claude and other LLMs handle such structured prompts well.

Example Prompt Assembly:

For the example query “Give me price trends for IT equipment”:
	•	After retrieving data (e.g., found relevant tenders from 2022, 2023, 2024), the assistant might assemble:

System: You are an expert procurement assistant...
Context:
IT Equipment Tenders:
2022 – 10 contracts, average price €95,000.
2023 – 12 contracts, average price €110,000.
2024 – 15 contracts, average price €120,000.
User: "Give me price trends for IT equipment in the last 3 years."
Assistant: The average awarded prices for IT equipment tenders have been rising over the past 3 years. In 2022, the typical contract value was around €95k. This increased to roughly €110k in 2023, and further to about €120k in 2024. This indicates a steady upward trend in prices, approximately a 26% increase from 2022 to 2024. Several factors could contribute, such as increased demand and inflation, but the data clearly shows year-on-year growth in IT procurement costs.

The Assistant’s answer here was generated from the context. It quantifies the trend and provides a concise explanation. The format used clear delineation of context vs question.

Ensuring Claude Agents Recognize Template: The prompt templates (with sections like “Context:” and so forth) should be written in a consistent way each time the AI assistant agent is invoked. Claude Code (or any LLM agent) will then follow this pattern. In our implementation, the formatting of the prompt will be coded in the AI assistant agent. We can include a comment in the code (like we did in section 4.2) that explicitly shows the format expected.

Follow-up Questions: The chat UI allows multi-turn conversations. We must maintain context between turns carefully:
	•	We can keep track of previous Q&A pairs in the conversation state and include the most relevant ones in the prompt (especially if the user asks a follow-up like “What about 2021?” we need to recall they were talking about IT equipment).
	•	Possibly, for each follow-up, re-run retrieval if needed (the user might broaden or narrow scope).
	•	The prompt structure for follow-ups might simply include the last Q&A as context too (or an on-going summary). We should also give the LLM a system instruction to remember prior conversation, but since our domain is factual, re-supplying relevant facts explicitly is safer.

MCP (Model-Context-Protocol) Alignment: If we are integrating with a multi-agent orchestrator (like Claude Flow’s MCP protocol), the prompt template can be aligned to that. For example, certain multi-agent systems expect the assistant to output answers and citations in a certain way. Given our UI likely won’t show raw citations (unless we want to), we might not require the model to output 【source】 style citations. Instead, the assistant could mention tender IDs or names in answers for traceability.

To summarize, the prompt template is designed to be:
	•	Descriptive in instruction (so the model knows its role).
	•	Explicit with data context (to ground answers).
	•	Clear in question (so the model doesn’t get confused with all the data).
	•	Resulting in concise answer (we instruct for brevity and clarity).

This structure, consistently applied, will help the Claude agents produce reliable outputs for a variety of procurement-related questions, mimicking an expert analyst that always references the actual tender data.

10. Sample Data Objects and API Responses

To illustrate how data flows through the system, here are examples of JSON data objects and API responses for key entities and endpoints. These samples can guide the implementation of serialization in the backend and help frontend developers understand what to expect.

Tender Object (API Representation):

{
  "tender_id": "2023/47",
  "title": "Procurement of IT Equipment for Ministry of Education",
  "description": "Purchase of laptops and projectors for public schools.",
  "category": "IT Equipment",
  "procuring_entity": "Ministry of Education",
  "opening_date": "2023-05-10",
  "closing_date": "2023-06-15",
  "status": "Awarded",
  "estimated_value_eur": 120000,
  "awarded_value_eur": 115000,
  "winner": "TechNova LLC",
  "documents": [
    {
      "doc_id": 987,
      "name": "Tender Specification.pdf",
      "url": "https://ourapp.com/api/tenders/2023/47/docs/987",
      "content_text_excerpt": "The Ministry of Education is seeking laptops and projectors ...", 
      "pages": 25
    },
    {
      "doc_id": 988,
      "name": "Award Decision.pdf",
      "url": "https://ourapp.com/api/tenders/2023/47/docs/988",
      "content_text_excerpt": "Awarded bidder: TechNova LLC with bid of EUR 115,000 ...",
      "pages": 3
    }
  ],
  "created_at": "2023-05-10T09:00:00Z",
  "updated_at": "2023-07-01T12:00:00Z"
}

Explanation: This JSON represents a tender that has been awarded. It includes key fields. The documents array lists associated documents, each with an API URL to fetch or download it (our backend could serve the file). We include a short excerpt from the text for quick preview (and maybe for search indexing). The monetary values are normalized to EUR (if the site provided in MKD denars, we might convert or at least store currency info; here for simplicity assume EUR). The ID “2023/47” could be a combination of year and tender number as often used in procurement.

API Response: GET /api/tenders?status=open

{
  "results": [
    {
      "tender_id": "2025/12",
      "title": "Construction of Local Roads in Skopje Region",
      "category": "Construction Works",
      "procuring_entity": "Ministry of Transport",
      "closing_date": "2025-12-01",
      "estimated_value_eur": 500000,
      "status": "Open"
    },
    {
      "tender_id": "2025/13",
      "title": "Supply of Medical Consumables",
      "category": "Medical Supplies",
      "procuring_entity": "Health Insurance Fund",
      "closing_date": "2025-12-05",
      "estimated_value_eur": 200000,
      "status": "Open"
    },
    ...
  ],
  "total": 2,
  "page": 1,
  "page_size": 50
}

Explanation: A listing of open tenders (filtered by status). For listing endpoints, we include summary info for each tender to minimize payload. Pagination fields (total, page, page_size) are present if applicable.

API Response: GET /api/tenders/2023/47 (specific tender)
would return the full object as shown in the first JSON (the Tender Object example).

API Response: POST /api/ask (AI query)
Request payload:

{
  "question": "What were the average awarded prices for IT Equipment tenders each year from 2020 to 2024?"
}

Response payload (successful):

{
  "answer": "From 2020 to 2024, the average awarded contract price for IT Equipment tenders in North Macedonia has steadily increased. In 2020, the average was around €80k. By 2022 it rose to roughly €95k, and in 2024 it reached approximately €120k. This suggests a significant upward trend in prices for IT equipment over the last five years.",
  "references": [
    { "tender_id": "2020/05", "detail": "2020 procurement of PCs for schools – awarded €78k" },
    { "tender_id": "2022/10", "detail": "2022 national IT equipment tender – awarded €95k average per lot" },
    { "tender_id": "2024/07", "detail": "2024 joint IT procurement – multiple awards averaging €120k" }
  ]
}

Explanation: The answer text is given. We also include a references array – this is optional but helpful. It lists some tender IDs or data points that underpin the answer. The front-end could display these references in a tooltip or just for our debugging. If we decide not to expose references to users, we can omit that field or keep it for internal use.

If the question was beyond scope or invalid, the response might be:

{
  "answer": "I'm sorry, I could not find information relevant to that question in the tender database.",
  "references": []
}

And perhaps an HTTP 400 if it’s an invalid request.

API Response: POST /api/alerts (create alert)
Request:

{
  "criteria_type": "category",
  "criteria_value": "IT Equipment"
}

Response:

{
  "alert_id": 45,
  "user_id": 123,
  "criteria_type": "category",
  "criteria_value": "IT Equipment",
  "created_at": "2025-11-22T10:00:00Z"
}

Then when a new tender is scraped that matches this category, our system would generate a notification (could be an email or an entry in notifications table).

API Response: GET /api/account (get current user profile & subscription)

{
  "user_id": 123,
  "name": "John Doe",
  "email": "john@example.com",
  "plan": "Pro",
  "plan_status": "active",
  "usage": {
    "queries_this_month": 42,
    "queries_limit": 500,
    "alerts_count": 3,
    "alerts_limit": 20
  },
  "billing": {
    "stripe_customer_id": "cus_ABC123",
    "current_period_end": "2024-12-01T00:00:00Z",
    "cancel_at_period_end": false
  }
}

Explanation: This would combine user info and subscription info for the account page. The usage is our internal tracking. The billing comes partly from Stripe (if we want to show next renewal date, etc.). This avoids extra calls on frontend to multiple endpoints.

Websocket/SSE for Alerts: If we implement server push:
	•	e.g., SSE stream on /api/alerts/stream could send events like:
event: new_tender\ndata: {"tender_id": "2025/14", "title": "New IT Equipment Tender ..."}
for a user if a tender matches their alert. But implementing SSE/WS is optional; we could also just send email and show on dashboard.

The above sample objects cover the main structures. They should be documented in our API docs for developers. Claude agents generating code will use these as a target format for serialization (e.g., the Django/Express code will format query results into these JSON shapes).

11. UI Structure and UX (Next.js Dashboard & Chat)

The user interface is crucial for presenting the AI-powered insights in a friendly way. We outline the UI structure in terms of pages and components, aligning with a modern single-page application (SPA) feel, using Next.js for server-side rendering and client-side interactivity:
	•	Login Page: A simple page (/login) with a form (email, password). If using Next.js App Router, it could be a React component that handles form submission to our auth API. On success, redirect to the Dashboard. Optionally include a link to Signup page. Use proper error display (e.g., “Invalid credentials”).
	•	Signup Page: (/signup) Form for new users (name, email, password). Possibly also select a plan here or after signup (most likely we default to Free and they upgrade later). After signup, auto-login the user and go to onboarding or dashboard.
	•	Dashboard Page: The main landing after login, e.g., (/dashboard or the root /). This page provides an overview:
	•	Header: At top of all pages, a header bar with our app name/logo, navigation links (Dashboard, Tenders, Ask AI, Alerts, Account) and maybe a quick indicator of plan (e.g., “Pro Plan” badge).
	•	Summary Cards: Could show a few high-level metrics like:
	•	Number of open tenders today.
	•	Total tenders in database.
	•	Perhaps user-specific stat: how many queries they ran this month (out of limit).
	•	Latest Tenders List: A section listing, say, 5 most recent tenders added (with title, category, date). Each links to detail.
	•	Notifications/Alerts Feed: If the user has alerts, show if any new tender matched (e.g., “New tender in IT Equipment: [title]”). This could be a sidebar or a section with dismissible notifications.
	•	Quick Actions: Maybe buttons like “Ask a Question” (takes to chat) or “Upgrade Plan” (if on Free).
	•	This page is about giving a quick snapshot and entry point to deeper features.
	•	Tenders List/Search Page: (/tenders):
	•	Filters UI: Perhaps at top or side: text search box (for keyword in title/description), dropdown for category, date range picker for publication date, etc. Also a toggle for status (open/closed/all).
	•	Results Table: Display tenders in a table with columns: Title, Procuring Entity, Closing Date (or Award Date if closed), Value (estimated or awarded), Status.
	•	We can allow sorting by date or value. Pagination controls at bottom if result > page size.
	•	Each row clickable or with a “View” button to open details.
	•	Consider using a library for tables or custom styling with Tailwind/Bootstrap for quick dev.
	•	If no results, show a friendly “No tenders found for your criteria” message.
	•	This page essentially allows exploring the data in a structured way, which complements the AI free-form Q&A.
	•	Tender Details Page: (/tenders/[id]):
	•	Show all details of the tender as listed in the sample JSON:
	•	Perhaps group info into sections: “Basic Info” (title, category, entity, status, etc.), “Dates”, “Values”, “Winner” if any.
	•	Documents: For each document, provide a link (which will trigger download or open in new tab if PDF can be displayed). If we have a text summary for the doc, we can show a “Summary” toggle or preview.
	•	AI Insight Panel: This is optional but powerful – since we have AI, we could precompute or on-demand compute some insights here. For example, a button “Summarize this tender” which calls the AI to produce a short summary of the tender’s requirements or evaluation. Or “Compare to similar tenders” which might list how its price compares to average. These are advanced features; for MVP maybe just a “Summarize Document” that uses the AI on the PDF text.
	•	Even without that, we ensure the Ask AI feature is easily accessible (maybe a button “Ask about this tender” that opens the chat with context pre-filled).
	•	UI wise, could be a dedicated page or a modal/pop-up overlay to avoid leaving the list page. A modal is nice for quick view, but for simplicity we can do a page.
	•	AI Chat Page: (/ask or perhaps integrated as a widget):
	•	The chat interface should feel like using a messaging app or ChatGPT: a scrollable conversation area and an input box.
	•	Each exchange shows user question (maybe align right) and AI answer (align left, or vice versa, but differentiate style).
	•	Support markdown in AI answer: use a library to render things like bullet points, or code block (though code not likely here, but maybe a table).
	•	Possibly allow the user to provide thumbs-up/down feedback on answers to help future tuning.
	•	If user is on a restricted plan and exceeds usage, we can intercept the send action: e.g., “You have reached your query limit for today on the Free plan. Please upgrade to continue.”
	•	Also, we might show system messages in the chat if needed (like “Your context has been reset” if we clear after some time).
	•	Implementing it in Next.js could involve using API routes for streaming response (Server Sent Events or similar) so that the answer appears progressively. But initially, can do a simple full response (the AI agent likely will produce the full answer at once anyway via backend).
	•	Ensure mobile-friendly: this chat interface should resize well, maybe full screen on mobile with a bigger input field.
	•	Alerts Page: (/alerts):
	•	If user has none, show message “No alerts yet. Create one to get notified of new tenders.”
	•	Create Alert Form: Dropdown or radio to choose type (Category or Keyword; maybe others like “Procuring Entity” or “Above Value X”, but keep minimal for MVP). If category, show a list of categories (we can fetch distinct categories from DB). If keyword, a text input.
	•	Submit button -> calls POST /alerts.
	•	Alerts List: List existing alerts: e.g., “Category: IT Equipment – created Nov 22, 2025”. Each with a delete [X] button.
	•	Possibly a note on how notifications are delivered (for now, maybe just shown on dashboard or email if we implement that).
	•	We might include a toggle to enable/disable an alert without deleting it.
	•	Account Page: (/account):
	•	Show user profile info: email, maybe allow name edit.
	•	Show current plan: e.g., “Pro Plan – €395/month – Next payment on Jan 1, 2026” if we have that info.
	•	If Free plan, highlight what they’re missing out (“Upgrade to unlock unlimited queries, more alerts, etc.”).
	•	Upgrade/Downgrade buttons: Based on plan, show relevant actions:
	•	Free -> show Standard, Pro, Enterprise options with brief benefits of each and a “Upgrade” button for each (or a single Upgrade that takes them to Pricing page).
	•	If on Standard/Pro, maybe show “Upgrade to next tier” or “Downgrade to lower tier” and a “Cancel subscription” link (if they don’t want paid anymore, which would go to free).
	•	Possibly integrate Stripe customer portal: a “Manage Billing” button that opens Stripe portal for them.
	•	Usage stats: If relevant, show a small section with usage as in sample JSON (how many queries used etc.). This is more for transparency so they know where they stand.
	•	Logout button or link to end session.
	•	Pricing Page: (/pricing) – if not using just account page for it:
	•	Public page showing Free vs Paid features, and maybe an “Sign up” or “Upgrade now” call to action. Could be part of marketing site rather than app, but we can include it in app for logged out users exploring.
	•	Not critical if our marketing is separate.
	•	Admin Page (optional): If we allow admin role:
	•	Could be at /admin and require admin. Show lists of users, maybe a way to impersonate user to troubleshoot, usage charts, etc.
	•	Not needed for MVP but the backend allows such queries so we can easily add it later.

Navigation & Layout:
	•	Likely implement a common layout component in Next.js that wraps protected pages (so only logged-in can see them).
	•	Use Next.js routing to guard routes: if no auth, redirect to login.
	•	Possibly implement a loading state between route changes or use skeletons for content loading.
	•	The header nav as described earlier ensures user can go between main sections easily.

Design & Aesthetics:
	•	Aim for a clean, professional look (since target users are businesses responding to tenders).
	•	Colors and branding: maybe use a palette that matches Macedonia flag colors (red/yellow) subtly, or government feel (blue/white). But also we can choose a modern SaaS design.
	•	Use icons where intuitive: e.g., an icon for logout, icons for alert (bell icon), chat (speech bubble).
	•	Make buttons and links clearly labeled.

Internationalization (future):
	•	We would design the UI text (labels, placeholders) with an eye on translation later. Possibly using a library like react-i18next. For now, English only – but for example, our category names might be in Macedonian because the source data is in MK. We might either show them as-is (with maybe an English tooltip if we map categories). Or just keep them since our initial users likely know the categories in Macedonian.
	•	Later, adding a language switch to Macedonian (particularly for the UI chrome text like “Login”, “Dashboard”) will be done. The agent’s answers could also be requested in Macedonian in the future by adjusting the prompt language or translating output.

Responsiveness:
	•	Ensure CSS is flexible (use Flexbox/Grid) so that on smaller screens things stack nicely.
	•	Tables on mobile are tricky; might allow horizontal scroll or use cards view for tenders list on narrow screens.
	•	Chat on mobile: full-screen with messages, input fixed at bottom.

User Experience Flow Example:
	1.	A user logs in, sees the Dashboard with some stats and notices there’s a new tender matching their alert.
	2.	They click that tender, read the details, and then click “Ask AI” and ask “Is the budget for this tender above average for similar tenders?”.
	3.	The AI chat responds with an analysis comparing it to similar past tenders (because our system retrieved category average etc.).
	4.	The user then goes to Alerts page, adds another alert for a new category.
	5.	They reach their daily query limit. The next time they try to ask, the system says “Upgrade to continue”. They go to Account page, choose a plan, and go through Stripe checkout to upgrade.
	6.	Now as a Pro user, they get higher limits, and maybe new sections appear (like more analytics).
	7.	Admin (internally) could log in to see user stats, etc., but that’s background.

The UI ties everything together and needs to be intuitive even if the underlying system is complex. By breaking it down into these pages and components, we make it easy for the FrontendUI Claude agent to generate the code in a modular way (each page as a component, reusing a NavBar component, etc.).

12. Comment Markers for Claude Agents (Module Demarcation)

To ensure that the documentation is Claude-ingestible and multi-agent friendly, we’ve inserted clear comment markers and structured prompts in section 4 for each module. These markers serve as delimiters so that each Claude Code sub-agent can focus on its respective part of the system without confusion.

Key approaches we’ve used:
	•	Section Headings and Agent Labels: Each major module in section 4 starts with a heading naming the module (e.g., “Scraper Module”) and within the code block, a comment like # AGENT: WebScraper. This explicit label helps a Claude agent or orchestrator identify “this is the part relevant to the WebScraper agent”.
	•	Commented Task Lists: Within each code block, all instructions are inside comments (# for Python, // for JavaScript). This means if a Claude Code agent directly uses that as a starting file, it will treat it as pseudocode comments, which is ideal for prompting code generation. The agent will then write actual code beneath or between these comments as needed, effectively following the plan.
	•	Consistent Format: We maintained a consistent format: the first line is always # AGENT: ModuleName (or // AGENT: depending on language) followed by key info like language and role. Then a numbered or bulleted list of steps. This consistency makes it machine-parseable. For instance, an orchestrator could split the documentation by the regex ^# AGENT: to isolate each agent’s instructions.
	•	Avoiding Ambiguity: Each comment prompt is self-contained so that even if extracted alone, it gives enough context to the agent about what to do. For example, the Scraper agent’s prompt includes the site URL and specifics about what to parse. This way, if one were to feed only that segment to Claude, it has all necessary info.
	•	Markers in Narrative Sections: We mainly put markers in code blocks for technical tasks. However, even in the narrative text above, we refer to agent names and modules clearly (capitalized names like Scraper Agent, AI Assistant Agent). This reinforces context if an agent reads the whole document.
	•	No Overlap: We ensured that each module’s responsibilities are distinct to minimize any confusion or overlap between agents. The comment markers thus delineate code responsibilities (one agent won’t inadvertently implement another’s role if following the markers).

Using the Documentation with Claude Agents:
If one were orchestrating this, they would likely instruct each Claude Code instance with the relevant portion. For example:
	•	The orchestrator finds the section labeled AGENT: WebScraper and feeds that (plus perhaps the DB schema section for context on where to save data) to a Claude Code instance. That instance then produces the scraper code.
	•	Similarly for the AGENT: FrontendUI, the orchestrator provides that section to another Claude Code instance, which then generates the Next.js code.

Because we have embedded the design directives as comments, the agents can even include those comments in the code as documentation. This way, the final codebase is well-documented. For instance, the generated Python scraper might still contain some of the # Step: ... comments as it implements them.

Additionally, for modules that interact (like Backend API will call AI Assistant), the documentation has cross-references (the backend prompt says how to call the AI agent). These cross-references align their integration points.

Finally, should a Claude agent ingest the entire documentation, these comment markers act as waypoints that it can use to structure a complex task into sub-tasks. Claude’s ability to follow instructions should allow it to jump to the relevant parts for each sub-task.

In conclusion, the use of comment markers and structured prompts in this document is deliberate. It transforms this technical plan into a blueprint that is not just for human understanding, but also directly readable by AI development agents. The modules can be built in parallel by multiple Claude instances, orchestrated via the markers we’ve placed, ensuring consistency and speeding up development.

⸻

Sources:
	•	Google Cloud Blog – Introducing the File Search Tool in Gemini API ￼ – helped outline using Gemini’s managed RAG for context retrieval.
	•	Google Cloud Documentation – What is Retrieval-Augmented Generation (RAG)? ￼ ￼ – provided details on vector search and RAG benefits for grounding answers.
	•	Reddit – Optimal approach to implementing a free-tier in Stripe? ￼ ￼ – guided the decision to use a $0 Stripe subscription for Free tier to unify billing logic.
	•	North Macedonia Public Procurement Bureau info ￼ – confirmed that all public contract data is available on e-nabavki.gov.mk, implying data is publicly accessible for our scraper.