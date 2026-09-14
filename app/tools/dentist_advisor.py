
from __future__ import annotations
 
import logging
from typing import Any, Final
 
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
 
from app.core.config import settings
 
logger = logging.getLogger(__name__)
 
# Matched by case-insensitive prefix: real titles carry suffixes.
TRUSTED_CHANNELS_BY_LANGUAGE: Final[dict[str, tuple[str, ...]]] = {
    # English and Spanish are the only languages we have videos in.
    "en": ("Dental Digest", "Teeth Talk"),
    "es": ("Dentalk",),
}
DEFAULT_LANGUAGE: Final[str] = "en"
DESCRIPTION_CHARS: Final[int] = 120
 
# Oral health advice videos from trusted, dentist-run YouTube channels.

def _trusted_channels(language: str) -> tuple[str, ...]:
    return TRUSTED_CHANNELS_BY_LANGUAGE.get(language, 
                                            TRUSTED_CHANNELS_BY_LANGUAGE[DEFAULT_LANGUAGE]
                                            )
 
 
def _is_trusted(channel_title: str, 
                channels: tuple[str, ...]
                ) -> bool:
    """Return True if the channel is trusted."""
    title = channel_title.strip().lower()
    
    return any(title.startswith(name.lower()) for name in channels)
 
 
def get_oral_health_advice(query: str,
                           language: str = DEFAULT_LANGUAGE,
                           *,
                           api_key: str | None = None,
                           max_results: int | None = None,
                           search_pool: int | None = None,
                           ) -> list[dict[str, Any]]:
    """Return up to `max_results` videos; empty if none.
    Raises RuntimeError on API/key failure.

    The keyword arguments default to settings.
    """
    api_key = api_key if api_key is not None else settings.youtube_data_api_key
    max_results = max_results if max_results is not None else settings.youtube_max_results
    search_pool = search_pool if search_pool is not None else settings.youtube_search_pool

    if not api_key:
        raise RuntimeError("YOUTUBE_DATA_API_KEY is not set")
 
    channels = _trusted_channels(language)
 
    # Channel names ride inside the query: one request, 100 quota units.
    channels_query = " OR ".join(f'"{channel}"' for channel in channels)
    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        response = (
            youtube.search()
            .list(
                q=f"{query} ({channels_query})",
                part="snippet",
                type="video",
                videoEmbeddable="true",
                relevanceLanguage=language,
                maxResults=search_pool,
            )
            .execute()
        )
    except HttpError as error:
        raise RuntimeError(f"YouTube Data API error: {error}") from error
 
    results: list[dict[str, Any]] = []
 
    for item in response.get("items", []):
 
        snippet = item.get("snippet", {})
        channel = snippet.get("channelTitle", "")
        video_id = item.get("id", {}).get("videoId")
 
        if not video_id or not _is_trusted(channel, channels):
            continue
 
        description = snippet.get("description", "")
 
        if len(description) > DESCRIPTION_CHARS:
 
            description = description[:DESCRIPTION_CHARS] + "..."
 
        results.append(
            {
                "title": snippet.get("title", "Untitled"),
                "channel": channel,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "description_snippet": description,
            }
        )
        if len(results) >= max_results:
            break
 
    return results
 


def format_advice_videos(videos: list[dict[str, Any]], 
                         query: str
                         ) -> tuple[str, int]:
    """
    Render get_oral_health_advice output as the plain text Claude reads back.

    Returns (text, video_count). An empty list is a normal result, not an error: the
    trusted-channel filter is strict, so "nothing from a channel we trust" is the honest
    answer and the agent must say so rather than reach for another YouTube link.
    """
    if not videos:
        return (
            f"No videos from the trusted dentist-run channels matched {query!r}. "
            "Tell the user nothing suitable was found and answer from your own knowledge "
            "instead — never substitute a link from an untrusted channel.",
            0,
        )

    lines = [f"Oral health advice videos from trusted dentist-run channels, for {query!r}:"]

    for rank, video in enumerate(videos, start=1):
        
        lines.append(f"{rank}. {video['title']} — {video['channel']}")
        lines.append(f"   {video['url']}")
        
        if video.get("description_snippet"):
            lines.append(f"   {video['description_snippet']}")

    return "\n".join(lines), len(videos)


## Only for testing ##
if __name__ == "__main__":
    
    import json
    import sys
 
    if len(sys.argv) < 2:
        print("Usage: python -m app.tools.video_advisor <query> [language]")
        raise SystemExit(1)
 
    lang = sys.argv[-1] if sys.argv[-1] in TRUSTED_CHANNELS_BY_LANGUAGE else DEFAULT_LANGUAGE
    words = sys.argv[1:-1] if lang != DEFAULT_LANGUAGE or sys.argv[-1] == DEFAULT_LANGUAGE else sys.argv[1:]
    
    print(json.dumps(get_oral_health_advice(" ".join(words), lang),
                     ensure_ascii=False, 
                     indent=2
                     )
          )