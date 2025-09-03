
# GitHub README Docs (Flask)

Authenticate with GitHub, select a repo, generate a professional README.md (with dynamic badges & sections), and commit it back.

## Local Dev

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.sample .env  # fill your GitHub OAuth creds
flask --app app run --debug
```

## Environment Variables

- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` — GitHub OAuth App credentials
- `SESSION_SECRET` — any random string

## License
MIT
