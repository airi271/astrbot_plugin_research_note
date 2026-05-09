import asyncio
import re
from html import unescape
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def validate_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_url_input(value: str) -> str:
    value = value.strip()
    markdown_match = re.search(r"\[[^\]]*\]\((https?://[^\s)]+)\)", value)
    if markdown_match:
        return markdown_match.group(1)

    slack_match = re.search(r"<((?:https?)://[^>|]+)(?:\|[^>]*)?>", value)
    if slack_match:
        return slack_match.group(1)

    plain_match = re.search(r'https?://[^\s)>"]+', value)
    if plain_match:
        return plain_match.group(0)
    return value


def extract_title(html: str) -> str:
    match = re.search(
        r"<title[^>]*>(.*?)</title>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return "Untitled Web Page"
    return re.sub(r"\s+", " ", unescape(match.group(1))).strip() or "Untitled Web Page"


def html_to_text(html: str) -> str:
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _fetch_url_text_sync(url: str, timeout: int) -> str:
    request = Request(url, headers={"User-Agent": "AstrBot ResearchNote/0.1"})
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type.lower() and "text" not in content_type.lower():
            raise ValueError("URL did not return text/html content")
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


async def fetch_url_text(url: str, timeout: int = 20) -> dict:
    url = normalize_url_input(url)
    if not validate_url(url):
        raise ValueError("Only http/https URLs are supported")

    html = await asyncio.to_thread(_fetch_url_text_sync, url, timeout)
    return {
        "title": extract_title(html),
        "content": html_to_text(html),
        "source_type": "url",
        "source_uri": url,
    }
