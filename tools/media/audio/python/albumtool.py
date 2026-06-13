#!/usr/bin/env python3
# scripts-toolbox: entrypoint
# ruff: noqa: E402
"""
Инструмент за разпознаване, преименуване, тагване и chapter обработка на аудио албуми.
"""

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
PACKAGE_ROOT = REPO_ROOT / "packages" / "python"
if PACKAGE_ROOT.is_dir():
    sys.path.insert(0, str(PACKAGE_ROOT))

from audio_metadata_normalizer.utils.album import (
    ensure_multi_file_album,
    make_filename,
    resolve_album_dirs,
)
from audio_metadata_normalizer.utils.chapter_workflow import (
    build_embed_chapters_plan,
    embed_chapters_plan_has_conflict,
    load_chapters_for_embedding,
    print_embed_chapters_plan,
    resolve_chapter_input_path,
    resolve_chapter_output_path,
)
from audio_metadata_normalizer.utils.cli import (
    add_album_selection_arguments,
    add_auto_cover_argument,
    add_backup_arguments,
    add_cover_arguments,
    add_match_arguments,
    confirm_action,
    ensure_command_backup,
    parse_match_threshold,
)
from audio_metadata_normalizer.utils.files import (
    get_single_audio_file,
    is_single_file_album,
)
from audio_metadata_normalizer.utils.dir_rename import (
    DIR_TEMPLATE_CHOICES,
    album_dir_release_is_safe_match,
    apply_dir_rename_plan,
    build_album_dir_rename_plan,
    dir_rename_plan_has_conflicts,
)
from audio_metadata_normalizer.utils.cover import (
    ensure_cover_download,
    resolve_cover_path,
)
from audio_metadata_normalizer.utils.provider_workflow import (
    get_provider,
    load_album_release_data,
    match_album_tracks_for_command,
    print_album_header,
    resolve_album_context,
)
from audio_metadata_normalizer.utils.rename import (
    apply_rename_plan,
    build_rename_plan,
    rename_plan_has_conflicts,
)
from audio_metadata_normalizer.utils.tagging import (
    build_album_tags,
    tag_audio_file,
    tag_matched_files,
)


def cmd_scan(args):
    provider = get_provider(args.source)

    for album_dir in resolve_album_dirs(args.dir, args.album_only):
        context = resolve_album_context(album_dir, args)
        if not context:
            continue

        artist, album = context
        print_album_header(None, artist, album)

        release_data = load_album_release_data(provider, artist, album)
        if not release_data:
            continue

        meta, trackmap = release_data

        print("Избран релийз:")
        for key, value in meta.items():
            print(f"  {key}: {value}")

        print("\nТракове:")
        for idx, track in enumerate(trackmap, start=1):
            print(f"{idx:02d}. {track['title']} ({track.get('duration', '')})")

        print("\nПредложени имена на файлове:")
        for idx, track in enumerate(trackmap, start=1):
            filename = make_filename(idx, track["title"], ".EXT", len(trackmap))
            print(filename)


def cmd_rename(args):
    provider = get_provider(args.source)

    for album_dir in resolve_album_dirs(args.dir, args.album_only):
        if not ensure_multi_file_album(album_dir, "преименуване"):
            continue

        context = resolve_album_context(album_dir, args)
        if not context:
            continue

        artist, album = context
        print_album_header("Преименуване", artist, album)

        release_data = load_album_release_data(provider, artist, album)
        if not release_data:
            continue

        _, trackmap = release_data
        matched = match_album_tracks_for_command(
            album_dir,
            trackmap,
            args.match_threshold,
            "Преименуването",
        )
        if not matched:
            continue

        rename_plan = build_rename_plan(matched, len(trackmap))
        if rename_plan_has_conflicts(rename_plan):
            print("Преименуването е прекъснато заради конфликт при целевите имена.")
            continue

        ensure_command_backup(album_dir, args)
        apply_rename_plan(rename_plan, args.dry_run)


def cmd_tag(args):
    provider = get_provider(args.source)

    for album_dir in resolve_album_dirs(args.dir, args.album_only):
        if not ensure_multi_file_album(album_dir, "тагване"):
            continue

        context = resolve_album_context(album_dir, args)
        if not context:
            continue

        artist, album = context
        print_album_header("Тагване", artist, album)

        release_data = load_album_release_data(provider, artist, album)
        if not release_data:
            continue

        meta, trackmap = release_data
        matched = match_album_tracks_for_command(
            album_dir,
            trackmap,
            args.match_threshold,
            "Тагването",
        )
        if not matched:
            continue

        ensure_command_backup(album_dir, args)
        cover_path = resolve_cover_path(album_dir, args.cover_from, args.auto_cover)
        tag_matched_files(meta, matched, artist, cover_path, args.dry_run)


def cmd_run_all(args):
    provider = get_provider(args.source)

    for album_dir in resolve_album_dirs(args.dir, args.album_only):
        if not ensure_multi_file_album(album_dir, "обща обработка"):
            continue

        context = resolve_album_context(album_dir, args)
        if not context:
            continue

        artist, album = context
        print_album_header("Обща обработка", artist, album)

        release_data = load_album_release_data(provider, artist, album)
        if not release_data:
            continue

        meta, trackmap = release_data
        matched = match_album_tracks_for_command(
            album_dir,
            trackmap,
            args.match_threshold,
            "Общата обработка",
        )
        if not matched:
            continue

        rename_plan = build_rename_plan(matched, len(trackmap))
        if rename_plan_has_conflicts(rename_plan):
            print("Общата обработка е прекъсната заради конфликт при преименуване.")
            continue

        ensure_command_backup(album_dir, args)

        print("=== Етап 1: преименуване ===")
        renamed_matched = apply_rename_plan(rename_plan, args.dry_run)
        if len(renamed_matched) != len(matched):
            print("Общата обработка е прекъсната заради непълно преименуване.")
            continue

        print("\n=== Етап 2: тагване ===")
        cover_path = resolve_cover_path(album_dir, args.cover_from, args.auto_cover)
        tag_matched_files(meta, renamed_matched, artist, cover_path, args.dry_run)


def cmd_rename_dirs(args):
    provider = get_provider(args.source)
    dir_plan = []

    for album_dir in resolve_album_dirs(args.dir, args.album_only):
        context = resolve_album_context(album_dir, args)
        if not context:
            continue

        artist, album = context
        print_album_header("Преименуване на директория", artist, album)

        release_data = load_album_release_data(provider, artist, album)
        if not release_data:
            continue

        meta, _ = release_data
        if not album_dir_release_is_safe_match(
            album_dir,
            album,
            meta,
            args.release_threshold,
        ):
            continue

        item = build_album_dir_rename_plan(
            album_dir,
            meta,
            artist,
            args.dir_template,
        )
        if item:
            dir_plan.append(item)

    if not dir_plan:
        print("Няма директории за преименуване.")
        return

    if dir_rename_plan_has_conflicts(dir_plan):
        print("Преименуването на директории е прекъснато заради конфликт.")
        return

    apply_dir_rename_plan(dir_plan, args.dry_run)


def cmd_cover(args):
    provider = get_provider(args.source)

    for album_dir in resolve_album_dirs(args.dir, args.album_only):
        context = resolve_album_context(album_dir, args)
        if not context:
            continue

        artist, album = context
        print_album_header("Обложка", artist, album)

        release_data = load_album_release_data(provider, artist, album)
        if not release_data:
            continue

        meta, _ = release_data
        ensure_cover_download(
            album_dir,
            meta,
            force=args.force,
            dry_run=args.dry_run,
        )


def cmd_chapters(args):
    provider = get_provider(args.source)

    for album_dir in resolve_album_dirs(args.dir, args.album_only):
        if not is_single_file_album(album_dir):
            print(f"Пропускане: директорията не е single-file албум: {album_dir}")
            continue

        context = resolve_album_context(album_dir, args)
        if not context:
            continue

        artist, album = context
        print_album_header("Глави", artist, album)

        release_data = load_album_release_data(provider, artist, album)
        if not release_data:
            continue

        _, trackmap = release_data
        output_path = resolve_chapter_output_path(album_dir, args.output)

        provider.generate_chapter_file(trackmap, output_path)
        print(f"Записан chapter файл: {output_path}")


def cmd_embed_chapters(args):
    provider = get_provider(args.source)

    for album_dir in resolve_album_dirs(args.dir, args.album_only):
        audio_file = get_single_audio_file(album_dir)
        if not audio_file:
            continue

        context = resolve_album_context(album_dir, args)
        if not context:
            continue

        artist, album = context
        chapter_file = resolve_chapter_input_path(album_dir, args.chapters_file)
        if not os.path.exists(chapter_file):
            print(f"Липсва chapter файл: {chapter_file}")
            continue

        chapters = load_chapters_for_embedding(chapter_file)
        if not chapters:
            continue

        album_tags = None
        if args.tag_album:
            print_album_header("Тагване на single-file албум", artist, album)

            release_data = load_album_release_data(provider, artist, album)
            if not release_data:
                continue

            meta, _ = release_data
            album_tags = build_album_tags(meta, artist)

        plan = build_embed_chapters_plan(album_dir, audio_file, args.output)
        if embed_chapters_plan_has_conflict(plan):
            continue

        print(f"Вграждане на глави: {os.path.basename(audio_file)}")
        print_embed_chapters_plan(plan, chapter_file)

        ensure_command_backup(album_dir, args)

        if album_tags and args.dry_run:
            cover_path = resolve_cover_path(album_dir, args.cover_from, args.auto_cover)
            tag_audio_file(
                plan["final_path"],
                album_tags,
                cover_path,
                dry_run=True,
            )

        if args.dry_run:
            continue

        if not confirm_action("Да се вградят ли тези глави?", args.yes):
            print("Пропуснато по избор на потребителя.")
            continue

        provider.embed_chapters(
            plan["audio_file"],
            plan["tmp_out"],
            chapter_file,
        )

        if plan["in_place"]:
            os.replace(plan["tmp_out"], plan["final_path"])

        if not album_tags:
            continue

        cover_path = resolve_cover_path(album_dir, args.cover_from, args.auto_cover)
        tag_audio_file(
            plan["final_path"],
            album_tags,
            cover_path,
            dry_run=False,
        )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="albumtool",
        description="Инструмент за разпознаване, преименуване и тагване на албуми.",
    )
    parser.add_argument(
        "-S",
        "--source",
        choices=["itunes", "discogs", "musicbrainz"],
        required=True,
        help="Източник на метаданни: itunes, discogs или musicbrainz.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    scan_parser = sub.add_parser(
        "scan",
        help="Сканира директория и показва намерения албум и тракове.",
    )
    add_album_selection_arguments(
        scan_parser,
        "Директория с аудио файлове или директория на изпълнител.",
    )
    scan_parser.set_defaults(func=cmd_scan)

    rename_parser = sub.add_parser(
        "rename",
        help="Преименува файловете според траклиста.",
    )
    add_album_selection_arguments(
        rename_parser,
        "Директория с аудио файлове или директория на изпълнител.",
    )
    add_backup_arguments(rename_parser)
    add_match_arguments(rename_parser)
    rename_parser.set_defaults(func=cmd_rename)

    tag_parser = sub.add_parser(
        "tag",
        help="Записва метаданни във всеки трак чрез ffmpeg.",
    )
    add_album_selection_arguments(
        tag_parser,
        "Директория с аудио файлове или директория на изпълнител.",
    )
    add_backup_arguments(tag_parser)
    add_match_arguments(tag_parser)
    add_cover_arguments(tag_parser)
    add_auto_cover_argument(tag_parser)
    tag_parser.set_defaults(func=cmd_tag)

    all_parser = sub.add_parser(
        "run-all",
        aliases=["all"],
        help="Преименува и тагва multi-file албумите в една операция.",
    )
    add_album_selection_arguments(
        all_parser,
        "Директория с аудио файлове или директория на изпълнител.",
    )
    add_backup_arguments(all_parser)
    add_match_arguments(all_parser)
    add_cover_arguments(all_parser)
    add_auto_cover_argument(all_parser)
    all_parser.set_defaults(func=cmd_run_all)

    dirs_parser = sub.add_parser(
        "rename-dirs",
        aliases=["dirs"],
        help="Преименува album директории според metadata от избрания източник.",
    )
    add_album_selection_arguments(
        dirs_parser,
        "Директория с албуми или конкретна album директория.",
    )
    dirs_parser.add_argument(
        "-D",
        "--dir-template",
        choices=DIR_TEMPLATE_CHOICES,
        default="year-title",
        help=(
            "Шаблон за album директории: "
            "year-title, year-spaced-title, artist-year-title, "
            "artist-year-spaced-title."
        ),
    )
    dirs_parser.add_argument(
        "-R",
        "--release-threshold",
        type=parse_match_threshold,
        default=0.75,
        help="Минимален праг за съвпадение между текущото име на албума и намерения релийз.",
    )
    dirs_parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Само показва какво ще се промени.",
    )
    dirs_parser.set_defaults(func=cmd_rename_dirs)

    cover_parser = sub.add_parser(
        "cover",
        aliases=["cov"],
        help="Изтегля обложка от metadata източника, ако липсва локална обложка.",
    )
    add_album_selection_arguments(
        cover_parser,
        "Директория с аудио файлове или директория на изпълнител.",
    )
    cover_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Презаписва/изтегля обложка дори ако вече има локална обложка.",
    )
    cover_parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Само показва какво ще се изтегли.",
    )
    cover_parser.set_defaults(func=cmd_cover)

    chapters_parser = sub.add_parser(
        "chapters",
        aliases=["ch"],
        help="Генерира chapter файл за single-file албум.",
    )
    add_album_selection_arguments(
        chapters_parser,
        "Директория със single-file албум или директория на изпълнител.",
    )
    chapters_parser.add_argument(
        "-o",
        "--output",
        help="Път за генерирания chapter файл. По подразбиране: <album>/chapters.txt.",
    )
    chapters_parser.set_defaults(func=cmd_chapters)

    embed_parser = sub.add_parser(
        "embed-chapters",
        aliases=["embed", "ech"],
        help="Вгражда редактиран chapter файл в single-file албум.",
    )
    add_album_selection_arguments(
        embed_parser,
        "Директория със single-file албум или директория на изпълнител.",
    )
    add_backup_arguments(embed_parser)
    add_cover_arguments(embed_parser)
    add_auto_cover_argument(embed_parser)
    embed_parser.add_argument(
        "-T",
        "--tag-album",
        action="store_true",
        help="Записва album-level метаданни в single-file аудио файла след главите.",
    )
    embed_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Потвърждава автоматично вграждането на глави.",
    )
    embed_parser.add_argument(
        "-c",
        "--chapters-file",
        default="chapters.txt",
        help="Път до chapter файл. По подразбиране: <album>/chapters.txt.",
    )
    embed_parser.add_argument(
        "-o",
        "--output",
        help="Изходен аудио файл. Ако липсва, оригиналният файл се обновява на място.",
    )
    embed_parser.set_defaults(func=cmd_embed_chapters)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
