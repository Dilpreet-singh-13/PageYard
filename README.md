# PageYard

A personal, markdown-based note taking web app. Create notes with rich formatting, upload images, organize everything with tags and keep things clean with a soft-delete trash and background cleanup jobs.

Built with Django, HTMX, Alpine.js, Tailwind CSS, Redis, Celery, and S3/R2-compatible storage.

## Tech Stack

- **Backend**: Python (Django 5.2)
- **Frontend**: HTMX, Alpine.js, Tailwind CSS v4, DaisyUI 5
- **Database**: PostgreSQL (production / full-text search) or SQLite (local development) via `dj-database-url`
- **Cache**: Redis (Upstash or local) via `django-redis` for rate limiting and app caching (falls back to in-memory `LocMemCache` in local dev)
- **Task Queue & Scheduler**: Celery & Celery Beat (RabbitMQ broker, Redis result backend) for automated cleanup
- **Object Storage**: Cloudflare R2 / AWS S3 via `django-storages` and `boto3` (client-side presigned direct uploads)
- **Markdown & Sanitization**: Python-Markdown + `pymdown-extensions` (Pygments syntax highlighting, Mermaid diagrams, MathJax/LaTeX, task lists, admonitions) sanitized with Rust-based `nh3`
- **Auth**: `django-allauth` (email authentication + Google OAuth2)
- **Typography**: Self-hosted webfonts (Manrope, Fraunces, JetBrains Mono)

## Features

- **Rich Markdown Editing & Rendering**:
  - Live markdown preview with syntax highlighting (Pygments), Mermaid diagrams, LaTeX/math formulas, task lists with checkboxes, admonitions/callouts, and tables.
  - Safe HTML rendering with `nh3` sanitization (blocks XSS while preserving formatting and code blocks).
  - Plain-text preview generation stripped of markdown markers for clean dashboard card previews.
  - Efficient rendering: skips re-rendering when only note metadata (starred, trashed) changes.
- **Image Support & Direct Object Storage**:
  - Direct presigned uploads to Cloudflare R2 (or any S3-compatible store) — images upload straight from the browser to the bucket without choking the Django server.
  - Automatic attachment reconciliation on note save: detects images added or removed from markdown text.
  - Cascade cleanup: deleting a note deletes its DB attachments and removes the files from R2.
- **Organization & Tags**:
  - Multi-tag support with instant search and inline tag chips on notes.
  - Dedicated tags management page (create, rename, delete).
  - Star / pin notes for quick access from the dashboard.
- **Trash & Auto-Purge**:
  - Soft delete with a 30-day retention window.
  - Restore notes or empty trash manually at any time.
  - Celery background job automatically purges expired notes and deletes their associated image files.
- **Background Jobs (Celery & Celery Beat)**:
  - `sweep_trashed_notes`: Purges notes in trash older than 30 days.
  - `sweep_orphaned_attachments`: Removes image attachments unreferenced in markdown older than 30 days.
  - `sweep_stale_pending_attachments`: Checks uploads stuck at pending against R2 with `head_object` after 24 hours to heal or delete them.
- **Search & Filtering**:
  - Search by query, filter by tags, starred status, and date ranges.
  - Supports PostgreSQL full-text search (GIN-indexed search vector) with fallback search for SQLite.
- **UI & Experience**:
  - Custom DaisyUI themes: `pageyard` (light) and `pageyard-dusk` (dark).
  - Mobile bottom navigation dock and keyboard shortcuts modal (`?`).
  - HTMX toast notifications for async feedback.

## Local Development Setup

#### Prerequisites

1. **Python**: Python 3.13 or higher.
2. **Node.js**: Node.js 18+ (for compiling Tailwind CSS).
3. **Database**: PostgreSQL (recommended) or SQLite for quick local setup.
4. **Redis & RabbitMQ** *(Optional for basic dev)*:
   - Celery requires RabbitMQ as a broker and Redis as a result backend.
   - For local development with `DEBUG=True`, Django automatically falls back to in-memory cache if `REDIS_URL` is omitted.

### 1. Clone the Repository

```bash
git clone https://github.com/Dilpreet-singh-13/PageYard
cd PageYard
```

### 2. Set Up Virtual Environment & Dependencies

Using [`uv`](https://docs.astral.sh/uv/) (recommended):

```bash
uv sync
```

Or using standard Python `venv`:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install .
```

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Open `.env` and fill in your values. For quick local testing:
- `DEBUG=True`
- `DJANGO_SECRET_KEY`: Set any random string for development.
- `DATABASE_URL`: `postgres://user:password@localhost:5432/pageyard_db` or `sqlite:///db.sqlite3`
- `REDIS_URL`: `redis://127.0.0.1:6379/0` (or an Upstash Redis URL)
- `RABBITMQ_URL`: `amqp://guest:guest@localhost:5672//` (or CloudAMQP URL)
- `R2_*` / `AWS_*`: Your Cloudflare R2 bucket credentials and public domain.
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`: From Google Cloud Console (if using Google login).

#### Cloudflare R2 CORS Configuration

Because image uploads are sent via direct `PUT` requests straight from your browser to your R2 bucket endpoint, you must enable CORS in your Cloudflare R2 bucket settings (R2 Bucket -> Settings -> CORS Policy):

```json
[
  {
    "AllowedOrigins": [
      "http://localhost:8000",
      "http://127.0.0.1:8000"
    ],
    "AllowedMethods": [
      "PUT"
    ],
    "AllowedHeaders": [
      "Content-Type"
    ],
    "MaxAgeSeconds": 3600
  }
]
```
*(Add your production domain to `AllowedOrigins` when deploying).*

### 4. Database Migrations

```bash
uv run manage.py migrate    # or `python manage.py migrate`
```

Create a superuser to access the Django admin:

```bash
uv run manage.py createsuperuser
```

### 5. Compile Tailwind CSS

Install frontend dependencies:

```bash
npm install
```

Start the Tailwind CLI watcher:

```bash
npm run watch-css
```

For production minified build:

```bash
npm run build-css
```

### 6. Run the Development Server

```bash
uv run manage.py runserver    # or `python manage.py runserver`
```

The app will be available at [http://127.0.0.1:8000](http://127.0.0.1:8000).

### 7. Run Celery & Background Jobs (Optional for Local Dev)

If you are testing background sweeps, run Celery worker and beat in separate terminal windows:

```bash
# Start Celery worker
uv run celery -A core worker -l info

# Start Celery Beat scheduler
uv run celery -A core beat -l info
```

#### Setting Up Periodic Tasks via Django Admin

The project uses `django-celery-beat` with `DatabaseScheduler`, meaning schedules are stored in your database rather than hardcoded in Python. You can manage them directly through the Django Admin without restarting services:

1. Log in to [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/).
2. Under **Periodic Tasks**, click **Periodic tasks** -> **Add Periodic Task**.
3. Name your schedule (e.g., `Daily Trash Sweep`).
4. Select the task from the **Task (registered)** dropdown:
   - `notes.tasks.sweep_trashed_notes` (auto-purges notes in trash older than 30 days)
   - `notes.tasks.sweep_orphaned_attachments` (deletes unused images from R2 older than 30 days)
   - `notes.tasks.sweep_stale_pending_attachments` (reconciles stuck uploads against R2 older than 24 hours)
5. Set the schedule under **Interval Schedule** (e.g., every 1 day) or **Crontab Schedule** (e.g., `0 0 * * *`).
6. Save. Celery Beat automatically detects schedule changes from the database on its next tick.

## Project Structure

```
PageYard/
├── accounts/               # User management and profiles
│   ├── models/             # Custom user model
│   ├── templates/          # Profile and auth templates
│   └── views.py
├── core/                   # Project configuration
│   ├── celery.py           # Celery app initialization
│   ├── settings.py         # Django settings (Redis, R2, Celery, Allauth)
│   ├── urls.py             # Root URL routing
│   └── wsgi.py
├── notes/                  # Main notes application
│   ├── constants.py        # Retention periods and pagination constants
│   ├── forms.py            # Forms for Note and Tag models
│   ├── models.py           # Note, Tag, and NoteAttachment models
│   ├── render.py           # Markdown rendering pipeline & nh3 sanitization
│   ├── signals.py          # Post-delete signal for R2 file cleanup
│   ├── storage.py          # Boto3 client helper for Cloudflare R2
│   ├── tasks.py            # Celery tasks (trash, orphaned attachment sweeps)
│   ├── templates/notes/    # Note views and HTMX partials
│   ├── urls.py             # URLs for notes, tags, trash, and upload presigning
│   ├── utils.py            # Presigned keys, R2 checks, toast triggers
│   └── views.py            # Main application logic
├── static/
│   ├── css/                # Custom styles (admonitions, editor, pygments, fonts)
│   │   └── main.css        # Compiled Tailwind CSS output
│   └── fonts/              # Self-hosted fonts (Fraunces, JetBrains Mono, Manrope)
├── input.css               # Tailwind CSS v4 config & DaisyUI custom themes
├── package.json            # Node.js dependencies (@tailwindcss/cli, daisyui)
├── pyproject.toml          # Python dependencies & metadata
├── uv.lock                 # UV lockfile
└── manage.py               # Django management script
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.