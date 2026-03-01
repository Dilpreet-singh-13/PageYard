# PageYard

A simple, free knowledge base. Create formatted pages, write down lecture notes, draft project proposals, or simply
journal your day seamlessly. Group similar pages together, like bundling all your "Chemistry" notes or "Work Projects"
into dedicated, easy-to-find groups.

## Tech Stack

- **Django**: Python Web Framework
- **HTML & HTMX**: Dynamic interactions without full page reloads. Provide the "SPA" feel.
- **Tailwind CSS & DaisyUI**: Modern, customizable UI.
- **AlpineJS**: lightweight, JavaScript framework.

## Features

- **Create and Manage Pages**: Write formatted notes using Markdown.
- **Group Pages**: Organize related pages into groups for easy access.
- **Search and Filter**: Quickly find notes with a powerful search feature.
- **Responsive Design**: Works seamlessly on mobile and desktop.
- **Google OAuth**: Secure login with Google.

## Local Development Setup

#### Prerequisites to run

1. **Python**: Install Python 3.10 or higher.
2. **Node.js**: Install Node.js (for Tailwind CSS).
3. **PostgreSQL**: Ensure PostgreSQL is installed and running, or you have a cloud DB like Supabase.

### 1. Clone the Repository

```bash
git clone https://github.com/Dilpreet-singh-13/PageYard
cd PageYard
```

### 2. Create a Virtual Environment

We recommend using [`uv` (a modern Python package manager)](https://docs.astral.sh/uv/).

```bash
uv sync     # makes a .venv and installs all dependencies
# Or use a python venv:
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root (or rename `.env.example`).

Using `.env.example` as an baseline, replace the placeholders with your actual credentials.

### 3. Set Up the Database

```bash
uv run manage.py makemigrations   # or `python manage.py makemigrations` if using a python venv
uv run manage.py migrate          # or python manage.py migrate
```

### 4. Run the Development Server

```bash
uv run manage.py runserver    # or python manage.py runserver
```

The app will be available at [http://127.0.0.1:8000](http://127.0.0.1:8000).

### Tailwind CSS Setup

#### 1. Install Node.js Dependencies

```bash
npm i
```

#### 2. Build Tailwind CSS

For development (watch mode):

```bash
npm run watch-css
```

For production (minified):

```bash
npm run build-css
```

## Project Structure

The below tree highlights the main files of this codebase.
> The codebase refers to "pages" as "notes" internally.

```
PageYard/
├── accounts/               # User management
│   ├── templates/          # Templates for profile, account deletion, etc.
│   ├── models/             # Custom user and user manager
│   └── ...
├── core/                   # Project settings and configurations
│   ├── settings.py         # Django settings
│   ├── urls.py             # Core URL routing
│   └── ...
├── notes/                  # Main app for managing notes and groups
│   ├── templates/notes/    # Templates for notes, groups, dashboard
│   ├── urls.py             # URLs for the main functionality 
│   ├── models.py           # Models for Note and Group
│   ├── forms.py            # Custom forms for Note and Group models
│   ├── views.py            # All the main logic is here
│   └── ...
├── static/                 # Static files
│   └── css/main.css        # Compiled Tailwind CSS
├── manage.py               # Django management script
├── package.json            # Node.js dependencies (Tailwind CSS, DaisyUI)
├── input.css               # Tailwind CSS entry point
├── pyproject.toml          # Python dependencies
└── ...
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.