# Knowledge Base FAQ Auto Builder

> Turns resolved support tickets into a reviewable FAQ knowledge base: ML clustering finds the recurring issues, an LLM writes one grounded FAQ per issue, and a human approves it.

**Live demo:** <https://faq-eight-pearl.vercel.app> · **API:** <https://faq-backend-3prh.onrender.com> ([interactive docs](https://faq-backend-3prh.onrender.com/docs))

> The backend runs on Render's free plan. It sleeps after about 15 minutes idle, so the first request after that can take 30–60 seconds. Open the [health check](https://faq-backend-3prh.onrender.com/health) once before a demo to wake it up.

---

## Contents

1. [Problem Statement](#1-problem-statement)
2. [Project Goals](#2-project-goals)
3. [Key Features](#3-key-features)
4. [Architecture / System Design](#4-architecture--system-design)
5. [Tech Stack](#5-tech-stack)
6. [Project Workflow](#6-project-workflow)
7. [Dataset Details](#7-dataset-details)
8. [Clustering Methodology](#8-clustering-methodology)
9. [Cluster Evaluation / Results](#9-cluster-evaluation--results)
10. [FAQ Generation Methodology](#10-faq-generation-methodology)
11. [LLM Grounding & Hallucination Prevention](#11-llm-grounding--hallucination-prevention)
12. [Representative Ticket Selection](#12-representative-ticket-selection)
13. [API Endpoints](#13-api-endpoints)
14. [Database Schema / Data Model](#14-database-schema--data-model)
15. [Project Structure](#15-project-structure)
16. [Setup & Installation](#16-setup--installation)
17. [Environment Variables](#17-environment-variables)
18. [How to Run](#18-how-to-run)
19. [Docker Setup](#19-docker-setup)
20. [Testing](#20-testing)
21. [Sample Input / Output](#21-sample-input--output)
22. [Current Results / Metrics](#22-current-results--metrics)
23. [Error & Quota Handling](#23-error--quota-handling)
24. [Security Considerations](#24-security-considerations)
25. [Limitations](#25-limitations)
26. [Future Improvements](#26-future-improvements)
27. [License](#27-license)

---

## 1. Problem Statement

Support teams solve the same problems again and again, but the answers stay buried in individual ticket resolutions. Writing FAQs by hand means reading hundreds of tickets to spot patterns.

Pasting a CSV into an LLM and asking for "5 FAQs" is not a reliable alternative:

- the model picks arbitrary groupings and cannot tell you why;
- it cannot see a large dataset at once;
- it may invent plausible-sounding causes and fixes that no agent ever used;
- there is no link from an answer back to the tickets it came from, and no review step.

## 2. Project Goals

- **Find recurring issues automatically and reproducibly**, using deterministic ML rather than an LLM.
- **Choose the number of themes from the data** (silhouette score), not a hard-coded guess.
- **Use the LLM only for writing**, with one call per theme, never per ticket, to keep cost and quota use low.
- **Ground every FAQ in real resolutions** and make every answer traceable to its source tickets.
- **Keep a human in the loop.** Nothing counts as knowledge-base content until a reviewer approves it.
- **Fail safely.** Quota, network and model errors must never lose clustering work or crash the app.

## 3. Key Features

- **CSV upload with validation:** checks required columns, rejects bad rows individually with row numbers, skips duplicate ticket IDs, and blocks re-uploading the identical file.
- **Local embeddings:** `all-MiniLM-L6-v2` runs on the server, so no ticket text is sent anywhere for clustering. Embeddings are cached on disk.
- **Automatic K selection:** K-Means for K = 3, 4, 5; the best silhouette score wins. All scores are shown in the UI.
- **Representative tickets:** the 5 tickets closest to each cluster centre are what the LLM sees.
- **On-demand FAQ generation:** clustering spends no LLM quota. FAQs are generated per cluster with a **Generate FAQ** button.
- **Grounded output:** a strict prompt, JSON schema validation and a source-ID check, plus an `insufficient_information` flag.
- **Review workflow:** approve, reject, edit or **Regenerate** each FAQ. The statuses are `GENERATED`, `REVIEW`, `APPROVED` and `REJECTED`.
- **Traceability:** every FAQ lists the ticket IDs it was built from, and every cluster page shows all of its tickets.
- **Dashboard:** ticket, cluster and FAQ counts, cluster-size chart, and review-status breakdown.
- **Robust error handling:** quota exhaustion is detected and stops further API calls, transient errors are retried with backoff, and an optional offline fallback is available.
- **Pluggable providers:** the LLM, embedder and clusterer each sit behind a small interface. A mock LLM makes the whole app work offline.
- **Deployable:** Docker Compose for local use; Vercel (frontend) plus Render (backend and Postgres) for hosting.

## 4. Architecture / System Design

```mermaid
flowchart LR
    CSV[CSV upload] --> V[Validation<br/>+ ingestion]
    V --> DB[(PostgreSQL)]
    DB --> P[Preprocessing<br/>title + description + resolution]
    P --> E[Local embeddings<br/>all-MiniLM-L6-v2]
    E --> C[K-Means<br/>K = 3, 4, 5]
    C --> S[Silhouette score<br/>select best K]
    S --> R[Representative tickets<br/>5 nearest to centroid]
    R --> DB
    DB -- on demand, per cluster --> L[LLMProvider<br/>Gemini / mock]
    L --> F[Theme + FAQ<br/>validated + grounded]
    F --> DB
    DB --> API[FastAPI]
    API --> UI[Next.js dashboard<br/>approve / reject / edit / regenerate]
```

**Design principles**

- **Discovery and writing are separate steps.** Clustering is free and deterministic, while FAQ generation spends API quota. They are two explicit actions, so a Gemini outage never blocks clustering.
- **Thin API layer.** FastAPI routers only wire dependencies. The business logic lives in `services/`, and domain errors are mapped to HTTP status codes in one place (`main.py`).
- **Interfaces over vendors.** `LLMProvider`, `EmbeddingProvider` and `Clusterer` are small protocols. Only `llm/gemini.py` imports the Gemini SDK.
- **Caching everywhere it is safe.** Embeddings are cached per text, and LLM responses are cached per exact prompt content, so re-running on the same data makes no new API calls.

**Deployment topology**

```
Browser ──► Vercel (Next.js frontend) ──HTTPS/JSON──► Render (FastAPI, Docker) ──► Render PostgreSQL
                                                              │
                                                              └──► Google Gemini API (FAQ writing only)
```

## 5. Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.11, FastAPI, Uvicorn, SQLAlchemy 2, Pydantic 2, pydantic-settings |
| ML | sentence-transformers (`all-MiniLM-L6-v2`), scikit-learn (K-Means, silhouette), NumPy, PyTorch (CPU) |
| LLM | Google Gemini (`google-genai` SDK) behind an `LLMProvider` interface, plus an offline mock provider |
| Database | PostgreSQL 16 (SQLite fallback for local development) |
| Frontend | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Recharts |
| Testing | pytest, httpx (FastAPI TestClient) |
| Infra | Docker, Docker Compose, Vercel (frontend), Render (backend + Postgres, via `render.yaml`) |

## 6. Project Workflow

1. **Upload.** On the **Upload** page, choose a CSV. `POST /api/tickets/upload` validates it and stores new tickets. Bad rows are reported, not fatal.
2. **Cluster.** The Upload page then calls `POST /api/clusters/generate`, which:
   - loads all tickets and builds one text per ticket;
   - embeds the texts (cached);
   - runs K-Means for K = 3, 4, 5 and scores each K;
   - keeps the best K and picks 5 representative tickets per cluster;
   - replaces the previous run in a single transaction.

   **No LLM call is made in this step.**
3. **Generate FAQs.** On the **Clusters** page, click **Generate FAQ** on a cluster. That sends one LLM call with the cluster's representative tickets. The result is validated, checked against the source IDs, stored with status `GENERATED`, and the cluster is renamed after the FAQ's theme.
4. **Review.** On **FAQ Review**, filter by status, then:
   - **Approve** or **Reject** each FAQ;
   - **Edit** it, which moves it to `REVIEW`;
   - **Regenerate** it, which writes a fresh version and resets it to `GENERATED`.
5. **Monitor.** The **Dashboard** shows totals, cluster sizes and the review-status breakdown.

```
GENERATED ──edit──► REVIEW ──approve──► APPROVED
    │                  │
    └──approve/reject──┴──reject──► REJECTED
(edit on an APPROVED FAQ ► REVIEW;  Regenerate ► GENERATED)
```

## 7. Dataset Details

**Required CSV columns** (UTF-8, header row, extra columns ignored):

| Column | Meaning |
| --- | --- |
| `ticket_id` | Unique ID, e.g. `T001` |
| `title` | Short summary of the issue |
| `description` | What the customer reported |
| `resolution` | How support fixed it (the key input for FAQ answers) |
| `status` | e.g. `resolved` |

Blank values, extra fields, and duplicate `ticket_id`s within a file are rejected per row.

**Bundled sample: `data/sample_tickets.csv`**

- **20** synthetic, fully invented tickets (`T001`–`T020`), all `resolved`.
- They cover 5 real-world support areas:
  - API and integration errors (rate limits, timeouts, webhooks, 401s);
  - account security (lockout, OTP, 2FA);
  - login, password reset and sessions;
  - email and notification delivery;
  - refunds.
- Each description and resolution ends with a random context phrase (e.g. "Reported via email.", "Verified fix in production."), so tickets on the same issue are not word-for-word identical.

**Larger synthetic dataset (optional):** `backend/scripts/generate_sample_data.py` creates a seeded dataset of **153 tickets** (9 themes × 17), covering:

- payment failed, payment pending, authentication, refund;
- notification failure, data sync, API failure;
- duplicate transaction, configuration.

It writes to `data/sample_tickets.csv` by default, so pass a different path to keep the bundled file:

```bash
python backend/scripts/generate_sample_data.py data/tickets_153.csv
```

No real customer data is used anywhere in this project.

## 8. Clustering Methodology

| Step | Choice | Why |
| --- | --- | --- |
| Text | `title. description. resolution` (whitespace-normalised) | The **resolution is included on purpose**: tickets fixed the same way belong in one FAQ even when customers describe them differently. |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2`, L2-normalised, 384 dimensions | Small, fast, runs on CPU, good general-purpose sentence similarity. Runs locally, so no data leaves the server. |
| Cache | One `.npy` file per text, key = `sha256(model + text)` | Re-clustering is almost instant. Changing the model or text invalidates the entry automatically. |
| Algorithm | K-Means, `n_init=10`, `random_state=42` | Simple, well understood, and reproducible with a fixed seed. |
| K range | 3, 4, 5 | A small, reviewable number of FAQ themes per run. |
| Selection | Highest **silhouette score (cosine distance)**; ties go to the smaller K | Chooses K from the data. All scores are stored and shown in the UI. |
| Minimum data | More than 5 tickets (the largest K) | Otherwise a `422 InsufficientTicketsError`. |

Clustering sits behind a `Clusterer` protocol (`fit(embeddings, n_clusters) -> labels, centroids`), so another algorithm can be added without touching the pipeline.

## 9. Cluster Evaluation / Results

- **Metric:** the silhouette score, from −1 to 1. For each ticket it compares how close it is to its own cluster with how close it is to the nearest other cluster. Higher means better-separated clusters. It is computed with cosine distance to match the embedding space.
- **Visibility:** the per-K scores and the chosen K are saved on each run (`cluster_runs.k_results`). The UI shows them on every cluster page (**Silhouette by K**) and in the Clusters page subtitle.

Results on the bundled 20-ticket dataset (`python backend/scripts/run_pipeline.py data/sample_tickets.csv`):

| K | Silhouette (cosine) |
| --: | --: |
| 3 | 0.2119 |
| 4 | 0.2291 |
| **5** | **0.2315 ← selected** |

| Cluster | Size | Tickets (closest to centre first) | Interpretation |
| --: | --: | --- | --- |
| 1 | 5 | T004, T007, T001, T016, T010 | Email / notification delivery (plus T001, an API ticket; see below) |
| 2 | 4 | T002, T006, T011, T019 | API & integration errors |
| 3 | 3 | T003, T014, T009 | Account lockout, OTP and 2FA |
| 4 | 3 | T017, T020, T015 | Password reset & sessions |
| 5 | 5 | T018, T005, T013, T012, T008 | Refunds |

19 of 20 tickets land in the cluster matching their issue area. The exception is T001 ("API response missing fields"), which joins the notification cluster. Silhouette scores around 0.2 are typical for short, loosely separated support text. They show the clusters are real but overlap, which is exactly why a human reviews every FAQ.

## 10. FAQ Generation Methodology

- **One LLM call per cluster, never per ticket.** 5 clusters means about 5 calls, and only when a user clicks **Generate FAQ**.
- **Input:** the cluster's 5 representative tickets (ID, title, description, resolution) and the total cluster size. Full clusters are never sent.
- **Prompt** (`backend/app/prompts/faq_prompt.py`, versioned as `PROMPT_VERSION = "v1"`): strict grounding rules, then the exact JSON keys, then the tickets.
- **Output:** JSON, requested with Gemini's `response_mime_type="application/json"`:

  ```json
  {
    "theme": "short name (3-6 words)",
    "description": "1-2 sentences",
    "question": "the FAQ question a user would ask",
    "answer": "concise answer grounded in the resolutions",
    "resolution_steps": ["ordered steps, each supported by the tickets"],
    "source_ticket_ids": ["T018", "T013"],
    "insufficient_information": false
  }
  ```
- **Validation:** parsed into the `FaqDraft` Pydantic model (non-blank fields, at least one source ID). Markdown code fences are stripped first.
- **Retry:** one retry if the output is invalid or cites unknown tickets. A per-cluster ceiling of 3 API requests stops retries from multiplying.
- **Cache:** a valid result is stored under `CACHE_DIR/llm/<sha256>.json`. The key covers the model, prompt version and exact ticket content, so the same cluster never costs a second call.
- **Regenerate:** skips the cache and shows the model the previous version, asking it to "write a fresh version". The grounding rules still apply. The existing FAQ is only replaced once the new one is valid.
- **Model:** `GEMINI_MODEL` (default `gemini-3.8-flash`). Gemini 3.x rejects the older sampling parameters, so the request sets only the response type.

## 11. LLM Grounding & Hallucination Prevention

Several layers work together:

1. **The LLM never decides the clusters.** Grouping is done by embeddings and K-Means; the LLM only writes text for a group it is given.
2. **Prompt rules.**
   - Use *only* the tickets provided.
   - Add no causes, steps, tools, settings or timings they don't mention.
   - Every step must be supported by at least one resolution.
   - List only the ticket IDs actually used.
3. **An honest "I don't know".** When the tickets aren't enough, the model must set `insufficient_information: true` and say what is missing. The flag is stored and shown to reviewers.
4. **Schema validation.** Output that doesn't match `FaqDraft` is rejected.
5. **Citation check in code.** Every `source_ticket_id` must be one of the tickets actually sent. A single unknown ID invalidates the output, which triggers the retry.
6. **Traceability.** Each FAQ shows its source tickets, and each cluster page lists all of its tickets, so a reviewer can check claims against the originals.
7. **Human approval.** FAQs start as `GENERATED`. Editing an approved FAQ sends it back to `REVIEW`.

**Honest limit:** steps 4 and 5 check *structure and citations*, not the *meaning* of each sentence. Semantic accuracy relies on the prompt rules and the human reviewer (see [Future Improvements](#26-future-improvements)).

## 12. Representative Ticket Selection

For each cluster (`backend/app/clustering/representatives.py`):

1. Take the cluster's centroid from K-Means and L2-normalise it.
2. Compute the cosine similarity of every member ticket's embedding to the centroid.
3. Keep the **top 5** (stable sort), ranked by similarity. The rank is stored in `cluster_tickets.rank`.

**Why this approach:**

- **Typical, not extreme.** Tickets nearest the centre best represent the shared issue. Outliers stay out of the prompt.
- **Bounded cost.** The prompt size is fixed no matter how large the cluster is.
- **Deterministic.** The same data always produces the same representatives, which also makes the LLM cache effective.

The UI shows representatives separately from the full ticket list on each cluster page.

## 13. API Endpoints

Interactive docs: `/docs` (Swagger) on any running backend, e.g. [the hosted API](https://faq-backend-3prh.onrender.com/docs).

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/tickets/upload` | Upload a CSV (multipart field `file`). Returns added / skipped / rejected rows. 400 malformed, 409 duplicate file, 422 empty |
| POST | `/api/clusters/generate` | Run clustering (no LLM). Returns the run (chosen K, silhouette per K), cluster count and steps. 422 if too few tickets, 502 on embedding failure |
| GET | `/api/clusters` | Latest run and its clusters (name, size, representatives, FAQ, FAQ status / error) |
| GET | `/api/clusters/{id}` | One cluster plus run info (chosen K, silhouette per K) |
| GET | `/api/clusters/{id}/tickets` | All tickets in the cluster |
| GET | `/api/clusters/{id}/faq` | The cluster's FAQ (404 with the reason if none) |
| POST | `/api/clusters/{id}/faq/generate` | Generate the FAQ for one cluster. 409 if it already has one. Failure is stored on the cluster, not raised |
| POST | `/api/clusters/{id}/faq/regenerate` | Replace the FAQ with a fresh one (skips cache). The FAQ keeps its id and returns to `GENERATED`. 502 with the reason on failure, keeping the old FAQ |
| POST | `/api/clusters/faqs/generate` | Generate FAQs for every cluster that has none, one at a time; stops calling the API on quota exhaustion |
| POST | `/api/clusters/faqs/retry-failed` | Same as above, named for retrying failures |
| PATCH | `/api/faqs/{id}` | Edit theme / description / question / answer / steps. Status becomes `REVIEW` |
| POST | `/api/faqs/{id}/approve` | Status becomes `APPROVED` |
| POST | `/api/faqs/{id}/reject` | Status becomes `REJECTED` |
| GET | `/api/stats` | Dashboard numbers: tickets, clusters, FAQs by status (incl. failed / quota), cluster distribution |
| GET | `/health` | Liveness check → `{"status": "ok"}` |

Errors are always JSON: `{"detail": "..."}`. Database errors return `503` with a generic message.

## 14. Database Schema / Data Model

```mermaid
erDiagram
    uploads {
        int id PK
        string file_hash UK "sha256 of file"
        string filename
        int tickets_added
        datetime created_at
    }
    tickets {
        string ticket_id PK
        text title
        text description
        text resolution
        string status
    }
    cluster_runs {
        int id PK
        int chosen_k
        float silhouette
        json k_results "[{k, silhouette}]"
        int total_tickets
        datetime created_at
    }
    clusters {
        int id PK
        int run_id FK
        int cluster_index
        string name "FAQ theme once generated"
        text description
        int ticket_count
        text faq_error "why generation failed, if it did"
    }
    cluster_tickets {
        int cluster_id PK,FK
        string ticket_id PK,FK
        bool is_representative
        int rank
    }
    faqs {
        int id PK
        int cluster_id FK,UK
        string theme
        text description
        text question
        text answer
        json resolution_steps
        json source_ticket_ids
        bool insufficient_information
        string status "GENERATED|REVIEW|APPROVED|REJECTED"
        datetime created_at
        datetime updated_at
    }
    cluster_runs ||--o{ clusters : contains
    clusters ||--o{ cluster_tickets : has
    tickets ||--o{ cluster_tickets : "member of"
    clusters ||--o| faqs : "has one"
```

**Notes**

- **Only the latest run is kept.** Re-clustering deletes the old run, clusters, memberships and FAQs, and writes the new ones in a single transaction.
- **Tables are created at startup** with `create_all`; there are no migrations yet.
- **A derived FAQ status is shown per cluster.** It is the FAQ's own status, or `GENERATION_FAILED` / `QUOTA_EXHAUSTED` when `faq_error` is set, or none when nothing has been attempted.

## 15. Project Structure

```
FAQ/
├── backend/
│   ├── app/
│   │   ├── api/          thin FastAPI routers + dependency wiring (no business logic)
│   │   ├── clustering/   Clusterer protocol, K-Means, silhouette evaluation, K selection, representatives
│   │   ├── core/         settings (pydantic-settings) + typed domain errors
│   │   ├── database/     engine, session, table creation
│   │   ├── embeddings/   EmbeddingProvider protocol, sentence-transformers impl, on-disk cache
│   │   ├── llm/          LLMProvider protocol, GeminiProvider, MockLLMProvider, FallbackLLMProvider
│   │   ├── models/       SQLAlchemy tables
│   │   ├── prompts/      versioned FAQ prompt
│   │   ├── schemas/      Pydantic models (API, tickets, clustering, FAQ)
│   │   ├── services/     ingestion, preprocessing, clustering, FAQ generation, persistence queries
│   │   └── main.py       app, CORS, error → HTTP status mapping, /health
│   ├── scripts/          run_pipeline.py (CLI demo), generate_sample_data.py, check_gemini.py
│   ├── tests/            pytest suite
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/app/          pages: / (dashboard), /upload, /clusters, /clusters/[id], /faqs
│   ├── src/components/   Nav, charts, FAQ review card, UI primitives
│   ├── src/lib/          typed API client, types, data-loading hook
│   └── Dockerfile
├── data/sample_tickets.csv
├── docker-compose.yml
├── render.yaml           Render blueprint (backend + Postgres)
└── .env.example
```

## 16. Setup & Installation

**Prerequisites**

- Python 3.9+ (3.11 recommended; the Docker image uses 3.11)
- Node.js 18+
- PostgreSQL 16, *or* nothing: without `DATABASE_URL` the backend falls back to a local SQLite file
- Optional: Docker Desktop (Compose v2), or a Gemini API key from <https://aistudio.google.com/apikey>

**Backend**

```bash
git clone https://github.com/abhilasham214/FAQ.git
cd FAQ
python -m venv .venv
.venv/Scripts/activate                  # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r backend/requirements.txt # on Python 3.9/Windows: pip install --only-binary=:all: greenlet first
cp .env.example .env                    # then edit values (see below)
```

The first clustering run downloads the embedding model (~90 MB).

**Frontend**

```bash
cd frontend
npm install
echo NEXT_PUBLIC_API_URL=http://localhost:8000 > .env.local
```

## 17. Environment Variables

**Backend** (`.env` in the directory you start the backend from, or the host's environment settings):

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_URL` | *(unset → SQLite `faq_dev.db`)* | e.g. `postgresql+psycopg2://faq:faq@localhost:5432/faq`. `postgres://` URLs are accepted too |
| `LLM_PROVIDER` | `mock` | `gemini` for real FAQs; `mock` works offline |
| `GEMINI_API_KEY` | – | Required when `LLM_PROVIDER=gemini` |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Gemini model name |
| `GEMINI_MAX_RETRIES` | `1` | Retries after the first attempt, for transient errors only |
| `GEMINI_TIMEOUT_SECONDS` | `60` | Per-request timeout (minimum 10) |
| `GEMINI_RETRY_BASE_DELAY` | `1.0` | Backoff base in seconds (1 s, 2 s, 4 s … + jitter, capped at 30 s) |
| `LLM_FALLBACK_TO_MOCK` | `false` | If Gemini fails (e.g. quota), write that FAQ with the offline mock instead of failing |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Any sentence-transformers model |
| `CACHE_DIR` | `.cache` | Embedding and LLM response caches |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated list of allowed frontend URLs (no trailing `/`) |
| `PORT` | `8000` | Port for the Docker image; set automatically by Render |

**Frontend** (`frontend/.env.local`, or Vercel project settings):

| Variable | Description |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | Backend base URL, e.g. `http://localhost:8000`. Baked in at **build** time, so redeploy after changing it |

**docker-compose only:** `BACKEND_PORT` (default 8000) and `FRONTEND_PORT` (default 3000) are the host ports.

## 18. How to Run

### Local (without Docker)

```bash
# terminal 1: backend
cd backend
uvicorn app.main:app --reload --port 8000

# terminal 2: frontend
cd frontend
npm run dev
```

Open <http://localhost:3000>, then:

1. Go to **Upload**, choose `data/sample_tickets.csv`, and wait for clustering to finish.
2. Go to **Clusters** and click **Generate FAQ** on each cluster.
3. Go to **FAQ Review** to approve, reject, edit or regenerate.

API docs: <http://localhost:8000/docs>.

### CLI demo (no server, no database)

```bash
python backend/scripts/run_pipeline.py data/sample_tickets.csv              # clustering only
python backend/scripts/run_pipeline.py data/sample_tickets.csv --llm mock   # + offline FAQs
python backend/scripts/run_pipeline.py data/sample_tickets.csv --llm gemini # + Gemini FAQs (uses quota)
```

### Hosted deployment (Vercel + Render)

The live demo runs this way.

1. **Backend and database on Render.** In the dashboard, choose **New → Blueprint** and select this repo.
   - `render.yaml` creates `faq-backend` (Docker, free plan) and `faq-db` (Postgres), and links `DATABASE_URL` automatically.
   - Enter `GEMINI_API_KEY` and `CORS_ORIGINS` when Render prompts for them.
2. **Frontend on Vercel.** Import the repo and set **Root Directory** to `frontend`.
   - Add `NEXT_PUBLIC_API_URL` = the Render service URL (no trailing `/`), then deploy.
   - Only this variable belongs in Vercel. Delete any backend variables Vercel pre-fills from `.env.example`.
3. **Connect the two.** Set `CORS_ORIGINS` on Render to the Vercel production URL. Use the short `*.vercel.app` domain, not a per-deployment URL.
4. **Recommended for demos:** set `LLM_FALLBACK_TO_MOCK=true` on Render, so an exhausted free-tier quota doesn't leave clusters without FAQs.

Vercel can't host the backend itself: PyTorch and sentence-transformers exceed Vercel's 250 MB serverless function limit.

### Resetting the database

This permanently deletes all tickets, clusters and FAQs, including approved ones. Stop the backend first, then either:

```powershell
$env:PGPASSWORD = "faq"
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -h 127.0.0.1 -U faq -d faq -c "TRUNCATE faqs, cluster_tickets, clusters, cluster_runs, tickets, uploads RESTART IDENTITY CASCADE;"
```

or, without `psql`:

```powershell
.venv\Scripts\python.exe -c "import psycopg2; c=psycopg2.connect('dbname=faq user=faq password=faq host=127.0.0.1'); c.cursor().execute('TRUNCATE faqs, cluster_tickets, clusters, cluster_runs, tickets, uploads RESTART IDENTITY CASCADE'); c.commit(); print('cleared')"
```

**Notes**

- Use `127.0.0.1` rather than `localhost`: over IPv6 the password check can fail even when the password is correct.
- **SQLite:** instead of the commands above, delete `backend/faq_dev.db`; it is recreated on the next start.
- **Fresh FAQs:** Gemini responses are cached separately, so after a reset a cluster with the same tickets reuses its old FAQ. To force new ones, also delete `backend/.cache/llm`. Leave `.cache/embeddings` alone; it only speeds up clustering.

## 19. Docker Setup

```bash
cp .env.example .env        # optional: add GEMINI_API_KEY and set LLM_PROVIDER=gemini
docker compose up --build
```

| Service | Image / build | Port | Notes |
| --- | --- | --- | --- |
| `db` | `postgres:16-alpine` | internal | Health-checked; data in the `pgdata` volume |
| `backend` | `./backend` (Python 3.11-slim, CPU-only PyTorch) | `${BACKEND_PORT:-8000}` | `cache` volume (embeddings, LLM responses), `models` volume (model weights) |
| `frontend` | `./frontend` (Next.js standalone build) | `${FRONTEND_PORT:-3000}` | `NEXT_PUBLIC_API_URL` passed as a build argument |

- **URLs:** frontend <http://localhost:3000>, API docs <http://localhost:8000/docs>.
- **Ports taken?** Set `BACKEND_PORT` / `FRONTEND_PORT` in `.env`.
- **Why CPU-only PyTorch:** the default wheel bundles CUDA and would add about 2 GB to the image.
- **Port on hosting platforms:** the backend listens on `$PORT` when a host sets it (Render does); otherwise it uses 8000.

## 20. Testing

```bash
cd backend
python -m pytest            # fast suite: no model download, no network
python -m pytest -m slow    # also runs the real embedding model on the sample data
```

**Current status: 110 passed, 1 deselected** (the `slow` test).

| File | Covers |
| --- | --- |
| `test_ingestion.py` | Required columns, bad rows, duplicates, encoding, empty files |
| `test_embeddings.py` | Text building, embedding shape / normalisation, cache hits and misses |
| `test_clustering.py` | Silhouette evaluation, K selection and tie-breaking, too-few-tickets error, representatives |
| `test_faq_generation.py` | Prompt, JSON parsing, citation check, retry, caching, quota short-circuit, regenerate |
| `test_gemini_provider.py` | Error classification (quota vs rate limit vs client error), backoff, key redaction; uses a fake client, **no real API calls** |
| `test_api.py` | All endpoints end to end with FastAPI TestClient and an SQLite database |
| `test_error_handling.py` | Embedding failures → 502 (existing data kept), database errors → 503, bad uploads → 400 / 422 |
| `test_sample_data_slow.py` | Full clustering on `data/sample_tickets.csv` with the real model |

`backend/scripts/check_gemini.py` sends one minimal request to verify a key and model manually.

## 21. Sample Input / Output

**Input** (`data/sample_tickets.csv`, excerpt):

```csv
ticket_id,title,description,resolution,status
T008,Refund stuck in initiated status,Refund has been in initiated status for several days. Occurred on mobile app.,Re-triggered the stuck refund through the gateway dashboard and confirmed the status changed to processed. Documented in the runbook.,resolved
T013,Refund shows processed but no money,The order shows refund processed but the amount is not in the customer's account. Seen by multiple customers this week.,Shared the bank reference number with the customer; the bank credited the amount after its settlement cycle. Monitored for 48 hours with no recurrence.,resolved
T018,Refund not received,Customer cancelled the order two weeks ago and still has not received the refund. Affects a single customer.,"Refund had been submitted to the bank; provided the ARN so the customer could track it, funds arrived in 5-7 business days. Customer confirmed the issue is resolved.",resolved
```

**Upload response** (`POST /api/tickets/upload`):

```json
{ "tickets_added": 20, "tickets_skipped_existing": 0, "rejected_rows": [] }
```

**Clustering output** (real run, CLI):

```
Loaded 20 tickets (0 rows rejected)

Silhouette scores:
  K=3: 0.2119
  K=4: 0.2291
  K=5: 0.2315  <-- selected

Cluster 4  (5 tickets)
  T018: Refund not received
  T005: Refund failed at gateway
  T013: Refund shows processed but no money
  T012: Refund to wrong payment method
  T008: Refund stuck in initiated status
```

**Generated FAQ for the refund cluster.** This example is **illustrative**: it shows the expected shape and grounding, but the actual wording depends on the Gemini model. The mock provider only echoes ticket text.

```json
{
  "theme": "Delayed or failed refunds",
  "description": "Customers report refunds that are stuck, failed, sent to the wrong method, or marked processed but not yet received.",
  "question": "Why haven't I received my refund?",
  "answer": "Most refunds are with the bank and arrive after its settlement cycle (5-7 business days in the tickets); support can share a reference number (ARN) to track it. Refunds stuck or rejected at the gateway are re-triggered or paid by manual bank transfer.",
  "resolution_steps": [
    "Check whether the refund has been submitted to the bank and share the ARN / bank reference with the customer.",
    "If the refund is stuck in 'initiated', re-trigger it from the gateway dashboard and confirm it moves to 'processed'.",
    "If the gateway rejected it because the refund window passed, issue a manual bank transfer.",
    "If it went to the wrong payment method, reverse that credit and route the refund to the original source."
  ],
  "source_ticket_ids": ["T018", "T013", "T008", "T005", "T012"],
  "insufficient_information": false
}
```

## 22. Current Results / Metrics

| Metric | Value |
| --- | --- |
| Tickets in bundled dataset | 20 (0 rejected) |
| K evaluated | 3, 4, 5 |
| Selected K | **5** |
| Best silhouette (cosine) | **0.2315** |
| Cluster sizes | 5 / 4 / 3 / 3 / 5 |
| Tickets in the cluster matching their issue area | 19 / 20 (95%) |
| LLM calls to build all FAQs | **5** (1 per cluster; 0 on a cache hit) |
| Tickets sent to the LLM per call | ≤ 5 representatives |
| Max API requests per cluster (incl. retries) | 3 |
| Backend test suite | 110 passed |

**Earlier run on the 153-ticket generated dataset** (9 themes). Scores were K=3 → 0.169, K=4 → 0.145, K=5 → 0.174, so K=5 was chosen. With 9 underlying themes and K capped at 5, some clusters mix several topics. That is expected, and it is where the `insufficient_information` flag and human review matter most.

## 23. Error & Quota Handling

| Situation | What happens | User sees |
| --- | --- | --- |
| Malformed CSV / missing columns | `400`, nothing stored | Error message naming the problem |
| Individual bad rows | Row skipped, others stored | List of rejected rows with row numbers |
| Same file uploaded twice | `409` (content hash) | "This exact file has already been uploaded" |
| Too few tickets to cluster | `422` | Needs more than 5 tickets |
| Embedding model fails to load | `502` | Error message |
| **Gemini quota exhausted** (429 with a quota/billing message) | Treated as **terminal**, not retried. In a batch, remaining clusters are marked without calling the API | *"FAQ generation stopped: the AI provider's quota for this project is exhausted. The cluster was created successfully; retry once the quota resets."* and a **Retry FAQ generation** button |
| Rate limited (429, short-term) / 408 / 5xx / network timeout | Retried with exponential backoff + jitter (`GEMINI_MAX_RETRIES`) | Only shown if the retries also fail ("temporarily unavailable") |
| Bad key / bad model / bad request (400, 401, 403, 404) | Not retried (retrying can't fix it) | "configuration or request problem; check the server logs" |
| Invalid or ungrounded JSON | One retry, capped at 3 requests per cluster | "The model did not return a usable FAQ" |
| Regenerate fails | `502`, **existing FAQ kept** | Reason + "The existing FAQ was kept" |
| Database error | `503` | Generic "Database error; please try again" |

**Key guarantees**

- **Clustering is never lost to an LLM failure.** The two steps are separate, and the failure reason is stored on the cluster (`faq_error`) and shown in the UI and dashboard stats.
- **No burst of API calls.** Clusters are processed one at a time, and batch generation stops calling Gemini as soon as it reports quota exhaustion.
- **Cached FAQs cost nothing.** A retry after a partial failure only calls the API for clusters that still have no FAQ.

**When the free-tier quota runs out:**

- **Wait for the reset.** Daily limits reset at midnight Pacific time. Then click **Retry FAQ generation**.
- **Use another key.** Create one in a *different* Google Cloud project; keys in the same project share a quota.
- **Enable the fallback.** Set `LLM_FALLBACK_TO_MOCK=true`, and failed clusters get a simple offline FAQ instead of an error. These are never written to the Gemini cache.

## 24. Security Considerations

- **Secrets:** `GEMINI_API_KEY` lives only in the backend environment (`.env`, git-ignored, or Render's environment settings). It is never sent to the frontend. It is **redacted (`***`) from all logged error messages**, and logged errors are truncated to 300 characters.
- **Data privacy:**
  - Embeddings are computed locally, so ticket text is not sent to a third party for clustering.
  - Only the ≤ 5 representative tickets per cluster are sent to Gemini, and only when a user asks for an FAQ.
  - The bundled data is entirely synthetic.
- **CORS:** only origins listed in `CORS_ORIGINS` can call the API from a browser.
- **Input validation:**
  - CSVs must be valid UTF-8 and are parsed with the standard `csv` module.
  - Rows are validated with Pydantic.
  - Uploaded content is never executed or used as a file path.
- **SQL injection:** every query goes through the SQLAlchemy ORM with bound parameters.
- **Error hygiene:** users see sanitized messages; provider details and stack traces stay in server logs. Database errors return a generic 503.
- **No authentication yet.** Anyone with the URL can upload data, approve FAQs or spend LLM quota. Don't put real customer data on a public deployment until auth is added (see Future Improvements).
- **Prompt injection:** ticket text goes into the prompt, so a malicious ticket could try to steer the model. The schema and citation checks, plus human review, limit the impact. They cannot fully prevent it.

## 25. Limitations

- **Fixed K range (3–5).** Datasets with more distinct issue types get mixed clusters (seen with the 9-theme generated dataset).
- **Every ticket must belong to a cluster.** K-Means has no "noise" option, so outliers such as T001 are forced into the nearest cluster.
- **Grounding checks are structural.** Code verifies schema and citations, not whether each sentence is supported. That part relies on the prompt and the reviewer.
- **Only the latest run is kept.** Re-clustering replaces all clusters and FAQs, including approved ones.
- **Synchronous processing.** Clustering runs inside the HTTP request, with no background jobs or progress streaming. Fine for thousands of tickets, not for very large datasets.
- **No authentication, roles or audit log.**
- **No migrations.** Tables are created with `create_all`, so schema changes require a manual reset.
- **Free-tier hosting constraints:**
  - The Render backend sleeps after 15 minutes idle (30–60 s cold start).
  - It has 512 MB RAM, which is tight for PyTorch.
  - The disk is ephemeral, so the embedding/LLM caches and the model download are lost on each restart or redeploy.
  - Render deletes free Postgres databases after 30 days.
  - The Gemini free tier has a small daily quota.
- **English only.** Both the embedding model and the prompt assume English text.

## 26. Future Improvements

- **HDBSCAN** (or other density-based clustering), so the number of themes emerges from the data and outliers stay unassigned.
- **A wider K search** plus more quality metrics: Davies–Bouldin, Calinski–Harabasz, and stability across seeds.
- **Background jobs** (Celery / RQ) with real progress streaming, for large uploads.
- **FAQ versioning and history across runs:** match new clusters to approved FAQs instead of replacing them.
- **Automatic semantic grounding checks**, e.g. an embedding or NLI check that every resolution step is supported by a source resolution.
- **Authentication and reviewer roles**, with an audit log of approvals and edits.
- **Alembic migrations** instead of `create_all` at startup.
- **Publishing and export:** Markdown / JSON export, or push approved FAQs to a help-centre tool.
- **Multilingual support** via a multilingual embedding model and language-aware prompts.
- **Persistent caches on hosted deployments** (disk or object storage), plus a paid instance to avoid cold starts.

## 27. License

No license has been chosen yet, so by default all rights are reserved by the author. To allow reuse, add a `LICENSE` file (for example MIT or Apache-2.0) and update this section.
