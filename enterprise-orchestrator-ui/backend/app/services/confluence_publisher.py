"""
Confluence publisher adapter.
Creates or updates a Confluence page with the orchestration report content
using the Atlassian REST API v2.

Auto-reads credentials from ~/.atlassian/credentials.json if env vars are empty.
"""
import json
import logging
from pathlib import Path

from atlassian import Confluence

from app import config

logger = logging.getLogger(__name__)


def _load_credentials_file() -> tuple[str, str]:
    """Read email and token from ~/.atlassian/credentials.json"""
    cred_path = Path(config.CONFLUENCE_CREDENTIALS_FILE)
    if not cred_path.exists():
        raise RuntimeError(f"Confluence credentials file not found: {cred_path}")
    raw = cred_path.read_text(encoding="utf-8-sig")  # BOM-aware
    data = json.loads(raw)
    email = data.get("email") or data.get("username") or ""
    token = data.get("token") or data.get("api_token") or data.get("password") or ""
    if not email or not token:
        raise RuntimeError("credentials.json missing email/token fields")
    return email, token


def _get_client() -> Confluence:
    email = config.CONFLUENCE_USER_EMAIL
    token = config.CONFLUENCE_API_TOKEN

    # Fallback: read from credentials file if env vars not set
    if not email or not token:
        email, token = _load_credentials_file()
        logger.info("Using Confluence credentials from %s", config.CONFLUENCE_CREDENTIALS_FILE)

    return Confluence(
        url=config.CONFLUENCE_BASE_URL,
        username=email,
        password=token,
        cloud=True,
        verify_ssl=False,
    )


def publish_report(job_id: str, title: str, report_html: str) -> str:
    """
    Create or update a Confluence page under the configured parent.
    Returns the page URL.
    """
    client = _get_client()
    space_key = config.CONFLUENCE_SPACE_KEY
    parent_id = config.CONFLUENCE_PARENT_PAGE_ID

    # Check if page already exists
    existing = client.get_page_by_title(space=space_key, title=title)

    if existing:
        page_id = existing["id"]
        client.update_page(
            page_id=page_id,
            title=title,
            body=report_html,
            type="page",
            representation="storage",
        )
        logger.info("Updated Confluence page: %s (id=%s)", title, page_id)
    else:
        result = client.create_page(
            space=space_key,
            title=title,
            body=report_html,
            parent_id=parent_id,
            type="page",
            representation="storage",
        )
        page_id = result["id"]
        logger.info("Created Confluence page: %s (id=%s)", title, page_id)

    page_url = f"{config.CONFLUENCE_BASE_URL}/spaces/{space_key}/pages/{page_id}"
    return page_url
