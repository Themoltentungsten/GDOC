
import os
import base64
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, session, request, flash
from authlib.integrations.flask_client import OAuth
import requests
from markdown import markdown

# ------------ App & OAuth setup ------------
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me"))

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET")

if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
    print("⚠️  Missing GITHUB_CLIENT_ID or GITHUB_CLIENT_SECRET. Set them as environment variables.")

oauth = OAuth(app)
github = oauth.register(
    name="github",
    client_id=GITHUB_CLIENT_ID,
    client_secret=GITHUB_CLIENT_SECRET,
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "repo read:user user:email"}
)

# ------------ Helpers ------------
def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "token" not in session:
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapper

def gh_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

def gh_get(path, token):
    resp = requests.get(f"https://api.github.com/{path}", headers=gh_headers(token))
    return resp

def gh_put(path, token, json_body):
    resp = requests.put(f"https://api.github.com/{path}", headers=gh_headers(token), json=json_body)
    return resp

def month_name(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z","+00:00"))
        return dt.strftime("%B")
    except Exception:
        return ""

def shields_badge(label, message=None, logo=None, color=None, url=None):
    base = "https://img.shields.io/badge/"
    if message is None:
        # label is actually a full shields URL (e.g., github/last-commit/...)
        img = f"https://img.shields.io/{label}"
    else:
        # custom static badge
        from urllib.parse import quote
        lbl = quote(label.replace('-', '--').replace('_', '__'))
        msg = quote(message.replace('-', '--').replace('_', '__'))
        color = color or "0A0A0A"
        img = f"{base}{lbl}-{msg}-{color}"
        if logo:
            img += f"?logo={logo}&logoColor=white"
    if url:
        return f"[![{label}]({img})]({url})"
    return f"![{label}]({img})"

LANG_BADGES = {
    "Python": "https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white",
    "JavaScript": "https://img.shields.io/badge/JavaScript-F7DF1E?logo=javascript&logoColor=black",
    "TypeScript": "https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white",
    "Go": "https://img.shields.io/badge/Go-00ADD8?logo=go&logoColor=white",
    "Java": "https://img.shields.io/badge/Java-007396?logo=openjdk&logoColor=white",
    "Ruby": "https://img.shields.io/badge/Ruby-CC342D?logo=ruby&logoColor=white",
    "Rust": "https://img.shields.io/badge/Rust-000000?logo=rust&logoColor=white",
    "C++": "https://img.shields.io/badge/C%2B%2B-00599C?logo=cplusplus&logoColor=white",
    "C": "https://img.shields.io/badge/C-A8B9CC?logo=c&logoColor=black",
    "PHP": "https://img.shields.io/badge/PHP-777BB4?logo=php&logoColor=white",
    "Kotlin": "https://img.shields.io/badge/Kotlin-7F52FF?logo=kotlin&logoColor=white",
    "Swift": "https://img.shields.io/badge/Swift-F05138?logo=swift&logoColor=white",
    "Shell": "https://img.shields.io/badge/Shell-4EAA25?logo=gnu-bash&logoColor=white",
    "HTML": "https://img.shields.io/badge/HTML5-E34F26?logo=html5&logoColor=white",
    "CSS": "https://img.shields.io/badge/CSS3-1572B6?logo=css3&logoColor=white",
    "Dockerfile": "https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white",
    "Makefile": "https://img.shields.io/badge/Makefile-000000?logo=gnu&logoColor=white",
    "Jupyter Notebook": "https://img.shields.io/badge/Jupyter-F37626?logo=jupyter&logoColor=white",
    "Markdown": "https://img.shields.io/badge/Markdown-000000?logo=markdown&logoColor=white",
    "YAML": "https://img.shields.io/badge/YAML-CC2927?logo=yaml&logoColor=white"
}

def build_built_with(langs):
    # top 6 languages
    items = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)[:6]
    badges = []
    for name, _bytes in items:
        url = LANG_BADGES.get(name)
        if url:
            badges.append(f"![{name}]({url})")
        else:
            # fallback generic badge
            badges.append(shields_badge(name, "tech"))
    return " ".join(badges) if badges else shields_badge("Built with", "Love", "heart")

def generate_readme(owner, repo, repo_json, langs, token):
    name = repo_json.get("name","Repository")
    full_name = repo_json.get("full_name", f"{owner}/{repo}")
    description = repo_json.get("description") or "A professionally documented repository."
    pushed_at = repo_json.get("pushed_at") or repo_json.get("updated_at") or ""
    last_month = month_name(pushed_at)
    default_branch = repo_json.get("default_branch","main")
    open_issues = repo_json.get("open_issues_count",0)
    license_info = (repo_json.get("license") or {}).get("spdx_id", "UNLICENSED")

    # topic list
    topics = repo_json.get("topics") or []
    topics_md = ", ".join([f"`{t}`" for t in topics]) if topics else "—"

    # Language percentages
    total = sum(langs.values()) or 1
    top_langs = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)
    lang_lines = []
    for lang, b in top_langs[:6]:
        pct = round((b/total)*100, 1)
        lang_lines.append(f"- **{lang}** — {pct}%")

    built_with = build_built_with(langs)

    # Dynamic GitHub badges
    badges = [
        f"[![last commit](https://img.shields.io/github/last-commit/{owner}/{name}?label=last%20commit)](https://github.com/{owner}/{name}/commits)",
        f"![languages](https://img.shields.io/github/languages/count/{owner}/{name})",
        f"![top language](https://img.shields.io/github/languages/top/{owner}/{name})",
        f"![license](https://img.shields.io/github/license/{owner}/{name})",
        f"![stars](https://img.shields.io/github/stars/{owner}/{name})",
        f"![issues](https://img.shields.io/github/issues/{owner}/{name})",
    ]

    title = f"# {name.upper()}\n"
    tagline = f"\n{description}\n\n> Default branch: **{default_branch}** · Topics: {topics_md}\n\n"
    badge_line = " ".join(badges) + "\n\n"
    built_with_line = f"**Built with the tools and technologies:**\n\n{built_with}\n\n"
    toc = """## Table of Contents
- [Overview](#overview)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Usage](#usage)
  - [Testing](#testing)
- [Contributing](#contributing)
- [Roadmap](#roadmap)
- [License](#license)
- [Contact](#contact)
"""

    overview = f"""## Overview
{description}

**Why this repo?**  
This README was generated to provide a clean, professional documentation template similar to premium open‑source projects. It includes dynamic badges, a clear structure, and ready‑to‑use sections.

**Key highlights**
{os.linesep.join([f"- {x}" for x in (
    "Webhook-friendly sections and clean anchors",
    "Dynamic GitHub badges for activity and quality stats",
    "Auto-detected languages and tech badges",
    "Copy‑pastable install, run and test commands",
)])}

**Languages (auto‑detected)**
{os.linesep.join(lang_lines) if lang_lines else "- —"}
"""

    # Install/Usage suggestions based on languages
    is_python = any(l for l in langs.keys() if l.lower()=="python")
    is_node = any(l for l in langs.keys() if l.lower() in ("javascript","typescript"))
    install = ["git clone https://github.com/{owner}/{repo}.git".format(owner=owner, repo=name),
               "cd {repo}".format(repo=name)]
    if is_python:
        install += ["python -m venv .venv", "source .venv/bin/activate  # on Windows: .venv\\Scripts\\activate", "pip install -r requirements.txt  # if present"]
    if is_node:
        install += ["npm install  # or: pnpm i / yarn"]

    usage = []
    if is_python:
        usage += ["python main.py  # or the entry point for your app"]
    if is_node:
        usage += ["npm start  # or: node index.js"]

    testing = []
    if is_python:
        testing += ["pytest -q  # if you use pytest"]
    if is_node:
        testing += ["npm test"]

    getting_started = f"""## Getting Started

### Prerequisites
- Git
- {('Python 3.9+ and pip' if is_python else '')}
- {('Node.js 18+ and npm/pnpm/yarn' if is_node else '')}

### Installation
```bash
{os.linesep.join(install)}
```

### Usage
```bash
{os.linesep.join(usage) if usage else 'python app.py  # or your command'}
```

### Testing
```bash
{os.linesep.join(testing) if testing else '# add your tests here'}
```

"""

    contributing = """## Contributing
Contributions are welcome! Fork the repo and open a pull request with a clear description of your changes. Please keep commits focused and small.
"""

    roadmap = """## Roadmap
- [ ] Improve docs
- [ ] Add CI
- [ ] Expand examples
"""

    license_md = f"""## License
{license_info}
"""

    contact = f"""## Contact
Maintainer: @{owner}  
Project Link: https://github.com/{owner}/{name}
"""

    md = (
        title + "\n" +
        tagline +
        badge_line +
        built_with_line +
        toc + "\n" +
        overview + "\n" +
        getting_started + "\n" +
        contributing + "\n" +
        roadmap + "\n" +
        license_md + "\n" +
        contact + "\n"
    )
    return md

# ------------ Routes ------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/heartbeat")
def heartbeat():
    return "OK", 200

@app.route("/login")
def login():
    redirect_uri = url_for("auth_callback", _external=True)
    return github.authorize_redirect(redirect_uri)

@app.route("/callback")
def auth_callback():
    token = github.authorize_access_token()
    session["token"] = token
    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    token = session["token"]["access_token"]
    u = gh_get("user", token).json()
    # fetch repos
    repos = requests.get(
        "https://api.github.com/user/repos?per_page=100&affiliation=owner,collaborator,organization_member",
        headers=gh_headers(token)
    ).json()
    # Coerce private/public flag and sort by pushed_at
    repos = sorted(repos, key=lambda r: r.get("pushed_at",""), reverse=True)
    return render_template("dashboard.html", user=u, repos=repos)

@app.route("/generate/<owner>/<repo>")
@login_required
def generate(owner, repo):
    token = session["token"]["access_token"]
    repo_json = gh_get(f"repos/{owner}/{repo}", token).json()
    langs = gh_get(f"repos/{owner}/{repo}/languages", token).json()
    md = generate_readme(owner, repo, repo_json, langs, token)
    html_preview = markdown(md, extensions=["fenced_code", "tables", "toc"])
    return render_template("generate.html", owner=owner, repo=repo, md=md, html_preview=html_preview)

@app.route("/commit", methods=["POST"])
@login_required
def commit():
    token = session["token"]["access_token"]
    owner = request.form["owner"]
    repo = request.form["repo"]
    content = request.form["content"]
    message = request.form.get("message", "docs: add professional README via gh-readme-docs app")

    # default branch
    repo_json = gh_get(f"repos/{owner}/{repo}", token).json()
    branch = repo_json.get("default_branch", "main")

    # Check if README exists
    readme_resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/contents/README.md?ref={branch}",
        headers=gh_headers(token)
    )
    sha = None
    if readme_resp.status_code == 200:
        sha = readme_resp.json().get("sha")

    b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    body = {"message": message, "content": b64, "branch": branch}
    if sha:
        body["sha"] = sha

    put_resp = gh_put(f"repos/{owner}/{repo}/contents/README.md", token, body)
    if put_resp.status_code in (200,201):
        flash("README committed successfully ✅", "success")
        return redirect(f"https://github.com/{owner}/{repo}")
    else:
        try:
            err = put_resp.json()
        except Exception:
            err = {"message": "Unknown error"}
        flash(f"GitHub API error: {err}", "danger")
        return redirect(url_for("generate", owner=owner, repo=repo))

# ------------- Main -------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
