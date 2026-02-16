"""
Google OAuth 2.0 authentication handler.

This module manages OAuth authentication for Google services (Slides, Gmail, Drive).
It handles token creation, refresh, and provides authenticated credentials.
"""

import os
import pickle
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from typing import List, Optional


class GoogleAuthenticator:
    """Handles OAuth 2.0 authentication for Google APIs."""

    # Default scopes for n8n Agentic Workflows Manager
    DEFAULT_SCOPES = [
        'https://www.googleapis.com/auth/presentations',  # Google Slides
        'https://www.googleapis.com/auth/drive.file',     # Google Drive (for file creation/export)
        'https://www.googleapis.com/auth/gmail.send'      # Gmail (send emails)
    ]

    def __init__(self, credentials_path: Optional[str] = None,
                 token_path: Optional[str] = None,
                 scopes: Optional[List[str]] = None):
        """
        Initialize the Google authenticator.

        Args:
            credentials_path: Path to credentials.json (OAuth client ID)
            token_path: Path to save/load token.json (or token.pickle)
            scopes: List of Google API scopes to request
        """
        self.project_root = Path(__file__).parent.parent
        self.credentials_path = Path(credentials_path) if credentials_path else self.project_root / "credentials.json"
        self.token_path = Path(token_path) if token_path else self.project_root / "token.json"
        self.scopes = scopes or self.DEFAULT_SCOPES
        self.creds = None

    def authenticate(self) -> Credentials:
        """
        Authenticate and return valid credentials.

        This method:
        1. Loads existing token if available and valid
        2. Refreshes token if expired
        3. Runs OAuth flow if no valid token exists

        Returns:
            Authenticated Google API credentials

        Raises:
            FileNotFoundError: If credentials.json is missing
            Exception: If OAuth flow fails
        """
        # Check if token file exists (support both .json and .pickle formats)
        token_pickle = self.token_path.with_suffix('.pickle')
        token_json = self.token_path

        # Try to load existing credentials
        if token_json.exists():
            try:
                self.creds = Credentials.from_authorized_user_file(str(token_json), self.scopes)
            except Exception as e:
                print(f"Warning: Failed to load token from {token_json}: {e}")
        elif token_pickle.exists():
            try:
                with open(token_pickle, 'rb') as token:
                    self.creds = pickle.load(token)
            except Exception as e:
                print(f"Warning: Failed to load token from {token_pickle}: {e}")

        # If credentials don't exist or are invalid
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                # Refresh expired token
                print("Refreshing expired Google OAuth token...")
                try:
                    self.creds.refresh(Request())
                    print("✓ Token refreshed successfully!")
                except Exception as e:
                    print(f"Failed to refresh token: {e}")
                    print("Running new OAuth flow...")
                    self.creds = None

            if not self.creds:
                # Run OAuth flow for new token
                if not self.credentials_path.exists():
                    raise FileNotFoundError(
                        f"Google OAuth credentials file not found: {self.credentials_path}\n\n"
                        "Please follow these steps:\n"
                        "1. Go to Google Cloud Console (console.cloud.google.com)\n"
                        "2. Create or select a project\n"
                        "3. Enable APIs: Google Slides, Gmail, Google Drive\n"
                        "4. Create OAuth 2.0 Client ID (Desktop app)\n"
                        "5. Download credentials and save as 'credentials.json'\n"
                    )

                print("Starting Google OAuth flow...")
                print("A browser window will open for authentication.")
                print("Please grant the requested permissions.")

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), self.scopes
                )
                self.creds = flow.run_local_server(port=0)
                print("✓ Authentication successful!")

            # Save the credentials for future runs
            self._save_token()

        return self.creds

    def _save_token(self):
        """Save credentials to token file for future use."""
        try:
            # Save as JSON (preferred format)
            with open(self.token_path, 'w') as token:
                token.write(self.creds.to_json())
            print(f"✓ Token saved to {self.token_path}")
        except Exception as e:
            print(f"Warning: Failed to save token: {e}")

    def get_credentials(self) -> Credentials:
        """
        Get authenticated credentials (convenience method).

        Returns:
            Authenticated Google API credentials
        """
        if not self.creds or not self.creds.valid:
            return self.authenticate()
        return self.creds

    def revoke(self):
        """Revoke the current credentials and delete token file."""
        if self.creds:
            try:
                self.creds.revoke(Request())
                print("✓ Credentials revoked successfully")
            except Exception as e:
                print(f"Warning: Failed to revoke credentials: {e}")

        # Delete token file
        if self.token_path.exists():
            self.token_path.unlink()
            print(f"✓ Token file deleted: {self.token_path}")


def get_google_credentials(credentials_path: Optional[str] = None,
                           token_path: Optional[str] = None,
                           scopes: Optional[List[str]] = None) -> Credentials:
    """
    Convenience function to get Google API credentials.

    Args:
        credentials_path: Path to credentials.json
        token_path: Path to token.json
        scopes: List of API scopes to request

    Returns:
        Authenticated Google API credentials
    """
    authenticator = GoogleAuthenticator(credentials_path, token_path, scopes)
    return authenticator.authenticate()


if __name__ == "__main__":
    # Test authentication
    print("Testing Google OAuth authentication...\n")

    try:
        creds = get_google_credentials()
        print("\n✓ Authentication test successful!")
        print(f"Token is valid: {creds.valid}")
        print(f"Scopes: {', '.join(creds.scopes) if hasattr(creds, 'scopes') else 'N/A'}")
        print(f"\nYou can now use Google Slides, Gmail, and Drive APIs.")

    except FileNotFoundError as e:
        print(f"\n✗ Missing credentials file:")
        print(str(e))

    except Exception as e:
        print(f"\n✗ Authentication failed:")
        print(f"Error: {e}")
        print("\nPlease check your credentials.json file and try again.")
