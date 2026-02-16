"""
Configuration loader for n8n Agentic Workflows Manager.

This module loads and validates configuration from config.json and .env files,
providing a centralized configuration management system.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, Optional


class ConfigLoader:
    """Loads and validates configuration from config.json and environment variables."""

    def __init__(self, config_path: Optional[str] = None, env_path: Optional[str] = None):
        """
        Initialize the config loader.

        Args:
            config_path: Path to config.json (default: ../config.json)
            env_path: Path to .env file (default: ../.env)
        """
        self.project_root = Path(__file__).parent.parent
        self.config_path = Path(config_path) if config_path else self.project_root / "config.json"
        self.env_path = Path(env_path) if env_path else self.project_root / ".env"

        self.config = {}
        self.env_vars = {}

    def load(self) -> Dict[str, Any]:
        """
        Load configuration from both config.json and .env files.

        Returns:
            Dictionary containing merged configuration

        Raises:
            FileNotFoundError: If config.json is missing
            ValueError: If required configuration is missing or invalid
        """
        # Load environment variables
        if self.env_path.exists():
            load_dotenv(self.env_path)
        else:
            print(f"Warning: .env file not found at {self.env_path}. Using environment variables only.")

        self._load_env_vars()

        # Load JSON configuration
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}\n"
                "Please create config.json from the template."
            )

        with open(self.config_path, 'r') as f:
            self.config = json.load(f)

        # Validate configuration
        self._validate_config()

        return self._merge_config()

    def _load_env_vars(self):
        """Load required environment variables."""
        self.env_vars = {
            'n8n_base_url': os.getenv('N8N_BASE_URL'),
            'n8n_api_key': os.getenv('N8N_API_KEY'),
            'openai_api_key': os.getenv('OPENAI_API_KEY'),
            'anthropic_api_key': os.getenv('ANTHROPIC_API_KEY'),
            'openrouter_api_key': os.getenv('OPENROUTER_API_KEY'),
            'google_credentials_path': os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json'),
            'google_token_path': os.getenv('GOOGLE_TOKEN_PATH', 'token.json'),
        }

    def _validate_config(self):
        """
        Validate configuration has required fields.

        Raises:
            ValueError: If required configuration is missing
        """
        # Check for required top-level sections
        required_sections = ['n8n', 'monitoring', 'reporting', 'email']
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required configuration section: {section}")

        # Validate n8n configuration
        n8n_config = self.config['n8n']
        if not n8n_config.get('base_url'):
            print("Warning: n8n base_url not configured in config.json.")
            print("Set it in config.json or use N8N_BASE_URL environment variable.")

        # Validate email configuration
        email_config = self.config['email']
        if not email_config.get('recipient'):
            print("Warning: No email recipient configured. Email delivery will be skipped.")

        # Warn about missing API key
        if not self.env_vars['n8n_api_key']:
            print("Warning: N8N_API_KEY not found in environment variables.")
            print("Please add it to .env file before running workflow management tools.")

    def _merge_config(self) -> Dict[str, Any]:
        """
        Merge configuration from JSON and environment variables.

        Returns:
            Complete configuration dictionary
        """
        # Override config base_url with env var if set
        if self.env_vars['n8n_base_url']:
            self.config['n8n']['base_url'] = self.env_vars['n8n_base_url']

        return {
            **self.config,
            'api_keys': {
                'n8n': self.env_vars['n8n_api_key'],
                'openai': self.env_vars['openai_api_key'],
                'anthropic': self.env_vars['anthropic_api_key'],
                'openrouter': self.env_vars['openrouter_api_key'],
            },
            'google_oauth': {
                'credentials_path': self.env_vars['google_credentials_path'],
                'token_path': self.env_vars['google_token_path']
            },
            'paths': {
                'project_root': str(self.project_root),
                'tmp_dir': str(self.project_root / '.tmp'),
                'charts_dir': str(self.project_root / '.tmp' / 'charts'),
                'cache_dir': str(self.project_root / '.tmp' / 'cache'),
                'tools_dir': str(self.project_root / 'tools'),
                'workflows_dir': str(self.project_root / 'workflows'),
                'templates_dir': str(self.project_root / 'templates')
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by dot notation key.

        Args:
            key: Dot-separated key (e.g., 'n8n.base_url')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to load configuration.

    Args:
        config_path: Optional path to config.json

    Returns:
        Complete configuration dictionary
    """
    loader = ConfigLoader(config_path)
    return loader.load()


if __name__ == "__main__":
    # Test configuration loading
    try:
        config = load_config()
        print("Configuration loaded successfully!")
        print(f"\nn8n Base URL: {config['n8n']['base_url']}")
        print(f"API Version: {config['n8n']['api_version']}")
        print(f"Monitoring Interval: {config['monitoring']['check_interval_minutes']} min")
        print(f"Error Threshold: {config['monitoring']['error_alert_threshold']}")
        print(f"Email Recipient: {config['email']['recipient']}")
        print(f"n8n API Key Present: {'Yes' if config['api_keys']['n8n'] else 'No'}")
        print(f"OpenAI Key Present: {'Yes' if config['api_keys']['openai'] else 'No'}")
        print(f"\nPaths:")
        for path_name, path_value in config['paths'].items():
            print(f"  {path_name}: {path_value}")
    except Exception as e:
        print(f"Configuration error: {e}")
