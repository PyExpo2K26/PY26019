# Security Review And Production Checklist

## Current Security Posture

The app has already been improved in these areas:

- hardcoded auto-seeded demo users were removed
- secrets are expected from environment variables instead of source files
- session settings were tightened in the Flask app
- tests exist for core auth and route behavior

## Required Before Production

1. Rotate any previously exposed credentials.

- Gmail app password
- Twilio token
- OpenWeatherMap API key

2. Keep secrets only in `.env` or deployment secret storage.

- never commit `.env`
- never place live credentials in `env.example`

3. Use secure Flask settings.

- `FLASK_DEBUG=0`
- strong `SECRET_KEY`
- secure cookies in production
- `SESSION_COOKIE_HTTPONLY=True`
- `SESSION_COOKIE_SAMESITE=Lax` or stricter if compatible
- `SESSION_COOKIE_SECURE=True` when behind HTTPS

4. Protect operational routes.

- keep dashboards and sensitive APIs behind login where appropriate
- review whether public realtime endpoints expose only low-risk, read-only data

5. Validate outbound integrations.

- weather requests should fail safely
- alert sending should never expose secrets in logs
- rate-limit high-impact endpoints

## Recommended Additional Hardening

### Authentication

- add password reset flow
- add account lockout or backoff after repeated failed logins
- add email verification for new signups

### Sessions

- rotate session secret on environment rebuilds
- set permanent session lifetime explicitly
- clear session on logout and privilege changes

### Data

- back up SQLite databases regularly
- restrict write permissions on `artifacts/data/`
- consider migrations before schema changes

### Logging

- never log passwords, tokens, or full secrets
- log alert failures and external API failures with masked values only

## Model Security

Pickled model artifacts must be treated as trusted internal files only.

- do not load untrusted `.pkl` files
- regenerate artifacts in a controlled local environment using `scripts/retrain_models.py`
- keep `artifacts/models/model_metadata.json` under review to track feature compatibility

## Release Checklist

Before each release:

1. run `python -m unittest discover -s tests -v`
2. run `python scripts/retrain_models.py` if Python or sklearn changed
3. check login, dashboard, hydrology, forecast, and safe-route flows
4. verify live GPS and reverse geocoding behavior
5. confirm same-state shelter preference still works
6. verify no secrets are present in changed files
