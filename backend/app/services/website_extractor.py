"""Extract structured data from organization websites."""

import re
from dataclasses import dataclass, field
from typing import Optional

import httpx
from bs4 import BeautifulSoup


@dataclass
class WebsiteData:
    """Extracted data from a website."""
    about: Optional[str] = None
    mission: Optional[str] = None
    mission_statements: list[str] = field(default_factory=list)
    vision: Optional[str] = None
    founded_year: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    raw_text: Optional[str] = None


def _extract_year(text: str) -> Optional[int]:
    """Extract founded/established year from text."""
    # Look for patterns like "established 2015", "founded in 2010", "since 1995"
    patterns = [
        r"established\s+in\s+(\d{4})",
        r"established\s+(\d{4})",
        r"founded\s+in\s+(\d{4})",
        r"founded\s+(\d{4})",
        r"since\s+(\d{4})",
        r"since\s+(\d{4})",
    ]

    text_lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            year = int(match.group(1))
            if 1800 <= year <= 2100:
                return year
    return None


def _extract_section(html: str, keywords: list[str], min_length: int = 50) -> Optional[str]:
    """Extract a text section containing keywords."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove script and style elements
    for script in soup(["script", "style", "nav", "footer"]):
        script.decompose()

    text = soup.get_text(separator=" ", strip=True)
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # Look for sections with keywords
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(kw in line_lower for kw in keywords):
            # Collect this line and next few lines as context
            section = " ".join(lines[i:min(i+5, len(lines))])
            if len(section) >= min_length:
                return section[:500]  # Limit to 500 chars

    return None


def _extract_mission_statements(html: str) -> list[str]:
    """Extract potential mission statements from the page.

    Looks for sentences that:
    - Start with "We" or "Our"
    - Contain action words (support, help, provide, enable, etc.)
    - Are 15-150 characters (reasonable mission length)
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove script and style elements
    for script in soup(["script", "style", "nav", "footer"]):
        script.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # Split into sentences
    sentences = [s.strip() for s in re.split(r'[.!?]\s+', text) if s.strip()]

    mission_keywords = [
        "support", "help", "provide", "enable", "empower", "transform",
        "develop", "improve", "strengthen", "build", "create", "ensure",
        "promote", "advance", "foster", "facilitate", "deliver", "expand",
        "implement", "achieve", "address", "combat", "reduce", "increase"
    ]

    missions = []
    for sentence in sentences:
        # Look for mission-like sentences
        if (sentence.lower().startswith(("we ", "our ", "to ")) and
            any(kw in sentence.lower() for kw in mission_keywords) and
            15 < len(sentence) < 150):
            cleaned = _clean_text(sentence)
            if cleaned and cleaned not in missions:
                missions.append(cleaned)

    return missions[:5]  # Return top 5 mission statements


def _clean_text(text: str) -> str:
    """Clean extracted text."""
    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Remove common junk
    text = re.sub(r"javascript:|onclick:|href=", "", text)
    return text[:1000]  # Max 1000 chars


async def fetch_website(url: str) -> Optional[WebsiteData]:
    """Fetch and extract data from a website.

    Args:
        url: Full https:// URL to the website

    Returns:
        WebsiteData with extracted fields, or None if fetch fails
    """
    if not url or not url.startswith("https://"):
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            html = response.text
    except Exception:
        # Network error, timeout, etc.
        return None

    try:
        soup = BeautifulSoup(html, "html.parser")

        # Extract title/org name
        title = None
        if soup.title:
            title = soup.title.string
        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)

        # Extract meta description
        meta_desc = None
        meta_tag = soup.find("meta", attrs={"name": "description"})
        if meta_tag and meta_tag.get("content"):
            meta_desc = meta_tag.get("content")

        # Get all text content
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()
        full_text = soup.get_text(separator=" ", strip=True)
        full_text = _clean_text(full_text)

        # Extract founded year
        founded_year = _extract_year(full_text)

        # Extract mission
        mission = _extract_section(
            html,
            ["mission", "core mission", "our mission"],
            min_length=40
        )
        if mission:
            mission = _clean_text(mission)

        # Extract vision
        vision = _extract_section(
            html,
            ["vision", "our vision", "long-term vision"],
            min_length=40
        )
        if vision:
            vision = _clean_text(vision)

        # Extract about
        about = _extract_section(
            html,
            ["about", "about us", "who we are", "we are", "our story"],
            min_length=50
        )
        if about:
            about = _clean_text(about)

        # Fallback: use meta description
        if not about and meta_desc:
            about = _clean_text(meta_desc)

        # Extract multiple mission statements
        mission_statements = _extract_mission_statements(html)

        return WebsiteData(
            about=about,
            mission=mission,
            mission_statements=mission_statements,
            vision=vision,
            founded_year=founded_year,
            title=title,
            description=meta_desc,
            raw_text=full_text[:2000],
        )

    except Exception:
        # Parse error - return None
        return None
