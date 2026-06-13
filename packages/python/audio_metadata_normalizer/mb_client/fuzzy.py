from rapidfuzz import fuzz
from typing import List, Dict, Optional
from audio_metadata_normalizer.utils.normalize import normalize, normalize_track_filename


# ---------------------------------------------------------
# Fuzzy match for release-group titles
# ---------------------------------------------------------

def pick_best_release_group(album_name: str, groups: List[Dict]) -> Optional[Dict]:
    """
    Given a normalized album name and a list of release-groups,
    return the best fuzzy match.
    """
    album_norm = normalize(album_name)
    best = None
    best_score = 0.0

    for g in groups:
        title = g.get("title", "")
        title_norm = normalize(title)
        score = fuzz.ratio(album_norm, title_norm)

        if score > best_score:
            best_score = score
            best = g

    return best


# ---------------------------------------------------------
# Fuzzy match for release titles (rarely needed)
# ---------------------------------------------------------

def pick_best_release(releases: List[Dict], album_name: str) -> Optional[Dict]:
    """
    Fuzzy match between album name and release titles.
    Useful when release-group contains multiple editions.
    """
    album_norm = normalize(album_name)
    best = None
    best_score = 0.0

    for r in releases:
        title = r.get("title", "")
        title_norm = normalize(title)
        score = fuzz.ratio(album_norm, title_norm)

        if score > best_score:
            best_score = score
            best = r

    return best


# ---------------------------------------------------------
# Fuzzy match for track titles
# ---------------------------------------------------------

def match_track(local_filename: str, mb_tracks: List[Dict]) -> Optional[Dict]:
    """
    Given a local filename and a list of MB track dicts,
    return the best fuzzy match.
    """
    local_norm = normalize_track_filename(local_filename)
    best = None
    best_score = 0.0

    for t in mb_tracks:
        title = t["recording"]["title"]
        title_norm = normalize(title)
        score = fuzz.ratio(local_norm, title_norm)

        if score > best_score:
            best_score = score
            best = t

    return best
