"""
Gmail OAuth2 helper — one-time setup to create google_token.json.

Run ONCE on your local machine:
  pip install google-auth-oauthlib
  python finwatch_auth.py

It opens a browser, asks you to log in with Google, grants Gmail send permission,
and saves the token to backend/google_token.json.
This token file is then mounted into the Docker container (never commit it).

Credentials are loaded from environment variables:
  GOOGLE_CLIENT_ID     — your Google OAuth2 client ID
  GOOGLE_CLIENT_SECRET — your Google OAuth2 client secret
"""
import json
import os
import tempfile

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "backend", "google_token.json")


def main():
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        raise EnvironmentError(
            "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables before running."
        )

    from google_auth_oauthlib.flow import InstalledAppFlow

    client_secrets = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(client_secrets, f)
        creds_file = f.name

    flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
    creds = flow.run_local_server(port=0)

    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    print(f"\n✅ Token saved to: {TOKEN_FILE}")
    print("Mount this file in Docker — email will work automatically.")
    os.unlink(creds_file)


if __name__ == "__main__":
    main()
