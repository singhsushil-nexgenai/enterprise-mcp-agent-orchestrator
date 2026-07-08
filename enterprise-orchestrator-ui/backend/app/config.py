"""
Application settings loaded from environment variables.
Auto-detects credentials from known locations when env vars are empty.
"""
import configparser
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/orchestrator")
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# SharePoint
SHAREPOINT_TENANT_URL: str = os.getenv("SHAREPOINT_TENANT_URL", "")
SHAREPOINT_SITE_PATH: str = os.getenv("SHAREPOINT_SITE_PATH", "")
SHAREPOINT_LIBRARY: str = os.getenv("SHAREPOINT_LIBRARY", "Shared Documents")
SHAREPOINT_TARGET_FOLDER: str = os.getenv("SHAREPOINT_TARGET_FOLDER", "OrchestratorReports")
SHAREPOINT_CLIENT_ID: str = os.getenv("SHAREPOINT_CLIENT_ID", "")
SHAREPOINT_CLIENT_SECRET: str = os.getenv("SHAREPOINT_CLIENT_SECRET", "")
SHAREPOINT_TENANT_ID: str = os.getenv("SHAREPOINT_TENANT_ID", "")

# Confluence — defaults use your existing ~/.atlassian/credentials.json
CONFLUENCE_BASE_URL: str = os.getenv("CONFLUENCE_BASE_URL", "https://[Company]-it.atlassian.net/wiki")
CONFLUENCE_SPACE_KEY: str = os.getenv("CONFLUENCE_SPACE_KEY", "")
CONFLUENCE_PARENT_PAGE_ID: str = os.getenv("CONFLUENCE_PARENT_PAGE_ID", "")
CONFLUENCE_USER_EMAIL: str = os.getenv("CONFLUENCE_USER_EMAIL", "")
CONFLUENCE_API_TOKEN: str = os.getenv("CONFLUENCE_API_TOKEN", "")
CONFLUENCE_CREDENTIALS_FILE: str = os.getenv("CONFLUENCE_CREDENTIALS_FILE", os.path.join(os.path.expanduser("~"), ".atlassian", "credentials.json"))

# GitHub — read job configs/SQL from YOUR-ORG repos
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
GITHUB_API_URL: str = os.getenv("GITHUB_API_URL", "https://api.github.com")

# Auto-detect GitHub token from gh CLI if not set
if not GITHUB_TOKEN:
    try:
        result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            GITHUB_TOKEN = result.stdout.strip()
    except Exception:
        pass

# Dagster Cloud — GraphQL API for ops intelligence
DAGSTER_URL: str = os.getenv("DAGSTER_URL", "https://[Company].dagster.cloud/prod/graphql")
DAGSTER_TOKEN: str = os.getenv("DAGSTER_TOKEN", "")
DAGSTER_TOKEN_FILE: str = os.getenv("DAGSTER_TOKEN_FILE", os.path.join(os.path.expanduser("~"), ".dagster", "token"))
DTV_CA_CERT: str = os.getenv("DTV_CA_CERT", os.path.join(os.path.expanduser("~"), "corporate_root_ca.pem"))

# Auto-detect Dagster token from file if not set
if not DAGSTER_TOKEN and os.path.isfile(DAGSTER_TOKEN_FILE):
    try:
        DAGSTER_TOKEN = Path(DAGSTER_TOKEN_FILE).read_text(encoding="utf-8").strip()
    except Exception:
        pass

# Monte Carlo — GraphQL API for data quality
MC_API_KEY: str = os.getenv("MCD_API_KEY", "")
MC_API_SECRET: str = os.getenv("MCD_API_SECRET", "")
MC_API_URL: str = os.getenv("MCD_BASE_URL", "https://api.getmontecarlo.com/graphql")

# Auto-detect Monte Carlo credentials from profiles.ini if not set
if not MC_API_KEY or not MC_API_SECRET:
    _mc_profiles = os.path.join(os.path.expanduser("~"), ".mcd", "profiles.ini")
    if os.path.isfile(_mc_profiles):
        try:
            _cp = configparser.ConfigParser()
            _cp.read(_mc_profiles)
            _section = "default" if "default" in _cp else (_cp.sections()[0] if _cp.sections() else "")
            if _section:
                MC_API_KEY = MC_API_KEY or _cp.get(_section, "mcd_id", fallback="")
                MC_API_SECRET = MC_API_SECRET or _cp.get(_section, "mcd_token", fallback="")
        except Exception:
            pass

# Snowflake — direct connector for table metadata
SNOWFLAKE_ACCOUNT: str = os.getenv("SNOWFLAKE_ACCOUNT", "<YOUR-SNOWFLAKE-ACCOUNT>")
SNOWFLAKE_USER: str = os.getenv("SNOWFLAKE_USER", "ADMIN")
SNOWFLAKE_PASSWORD: str = os.getenv("SNOWFLAKE_PASSWORD", "")
SNOWFLAKE_ROLE: str = os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN")
SNOWFLAKE_WAREHOUSE: str = os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")
SNOWFLAKE_DATABASE: str = os.getenv("SNOWFLAKE_DATABASE", "UMA")
SNOWFLAKE_SCHEMA: str = os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC")
