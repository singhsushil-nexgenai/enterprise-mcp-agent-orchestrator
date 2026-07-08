"""
SharePoint publisher adapter.
Uploads report HTML to a SharePoint document library using Microsoft Graph API
with app-only (client credentials) authentication via MSAL.
"""
import logging
from pathlib import Path

import httpx
import msal

from app import config

logger = logging.getLogger(__name__)


def _get_access_token() -> str:
    """Acquire an app-only access token for Microsoft Graph."""
    authority = f"https://login.microsoftonline.com/{config.SHAREPOINT_TENANT_ID}"
    app = msal.ConfidentialClientApplication(
        config.SHAREPOINT_CLIENT_ID,
        authority=authority,
        client_credential=config.SHAREPOINT_CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise RuntimeError(f"SharePoint auth failed: {result.get('error_description', result)}")
    return result["access_token"]


def _graph_site_url() -> str:
    """Build the Graph API site URL from config."""
    hostname = config.SHAREPOINT_TENANT_URL.replace("https://", "").rstrip("/")
    site_path = config.SHAREPOINT_SITE_PATH.strip("/")
    return f"https://graph.microsoft.com/v1.0/sites/{hostname}:/{site_path}"


def upload_report(job_id: str, report_html: str, filename: str | None = None) -> str:
    """
    Upload an HTML report to SharePoint.
    Returns the web URL of the uploaded file.
    """
    token = _get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "text/html"}

    # Resolve site ID
    site_url = _graph_site_url()
    with httpx.Client(timeout=60) as client:
        site_resp = client.get(site_url, headers={"Authorization": f"Bearer {token}"})
        site_resp.raise_for_status()
        site_id = site_resp.json()["id"]

        # Resolve drive (document library)
        drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
        drives_resp = client.get(drives_url, headers={"Authorization": f"Bearer {token}"})
        drives_resp.raise_for_status()
        drive_id = None
        for d in drives_resp.json().get("value", []):
            if d["name"] == config.SHAREPOINT_LIBRARY:
                drive_id = d["id"]
                break
        if not drive_id:
            raise RuntimeError(f"Document library '{config.SHAREPOINT_LIBRARY}' not found")

        # Upload file
        fname = filename or f"{job_id}_report.html"
        folder = config.SHAREPOINT_TARGET_FOLDER.strip("/")
        upload_path = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{folder}/{fname}:/content"

        upload_resp = client.put(upload_path, headers=headers, content=report_html.encode("utf-8"))
        upload_resp.raise_for_status()
        web_url = upload_resp.json().get("webUrl", "")
        logger.info("Uploaded report to SharePoint: %s", web_url)
        return web_url
