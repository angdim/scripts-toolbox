#!/usr/bin/env python3

import argparse

from audio_metadata_normalizer.discogs_client.provider import DiscogsProvider
from audio_metadata_normalizer.mb_client.provider import MusicBrainzProvider


# ------------------------------------------------------------
# Provider factory
# ------------------------------------------------------------

def get_provider(source: str):
    """
    Връща provider инстанция според избрания източник.
    """
    source = source.lower()

    if source == "discogs":
        return DiscogsProvider()

    if source == "musicbrainz":
        return MusicBrainzProvider()

    raise ValueError(f"Unknown metadata source: {source}")


# ------------------------------------------------------------
# Main workflow
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Normalize album metadata and generate chapters."
    )

    parser.add_argument("--source", required=True,
                        help="discogs | musicbrainz")

    parser.add_argument("--artist", required=True,
                        help="Artist name")

    parser.add_argument("--album", required=True,
                        help="Album title")

    parser.add_argument("--input", required=True,
                        help="Input audio file (single-file album)")

    parser.add_argument("--output", required=True,
                        help="Output audio file with embedded chapters")

    parser.add_argument("--chapters", default="chapters.txt",
                        help="Path to generated chapter file")

    args = parser.parse_args()

    # 1) Provider selection
    provider = get_provider(args.source)

    # 2) Search
    results = provider.search(args.artist, args.album)
    if not results:
        print("No results found.")
        return

    # 3) Pick best release
    best = provider.pick_best(results, args.artist, args.album)
    if not best:
        print("No suitable release found.")
        return

    # 4) Extract metadata (optional, for display)
    meta = provider.extract_metadata(best)
    print("Selected release:")
    for k, v in meta.items():
        print(f"  {k}: {v}")

    # 5) Build trackmap
    trackmap = provider.build_trackmap(best)

    # 6) Generate chapter file
    provider.generate_chapter_file(trackmap, args.chapters)

    # 7) Embed chapters
    provider.embed_chapters(args.input, args.output, args.chapters)

    print("Done.")


if __name__ == "__main__":
    main()
