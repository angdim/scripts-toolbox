#!/usr/bin/env python3
# scripts-toolbox: entrypoint
# ruff: noqa: E402
"""
Инструмент за разпознаване, преименуване, тагване и chapter обработка на аудио албуми.

Поддържа multi-file албуми, single-file албуми с chapters, директен SFA вход чрез
аудио файлове и Lexus-safe JPEG cover профили за автомобилни infotainment системи.
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
    resolve_sfa_audio_output_path,
    resolve_sfa_chapter_input_path,
    resolve_sfa_chapter_output_path,
)
from audio_metadata_normalizer.utils.chapters import CHAPTER_FORMAT_CHOICES
from audio_metadata_normalizer.utils.cli import (
    add_album_selection_arguments,
    add_auto_cover_argument,
    add_backup_arguments,
    add_cover_arguments,
    add_cover_profile_argument,
    add_match_arguments,
    add_sfa_file_arguments,
    confirm_action,
    ensure_command_backup,
    ensure_file_command_backup,
    parse_match_threshold,
)
from audio_metadata_normalizer.utils.files import (
    get_single_audio_file,
    is_single_file_album,
    resolve_sfa_audio_files,
)
from audio_metadata_normalizer.utils.local_metadata import (
    build_local_album_metadata,
    build_local_matched_tracks,
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
    resolve_sfa_file_context,
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
from audio_metadata_normalizer.utils.sfa_split import SPLIT_PROFILES, split_sfa_file


def get_required_provider(args, command_label: str):
    if not args.source:
        print(f"Командата {command_label} изисква -S/--source: itunes, discogs или musicbrainz.")
        return None

    return get_provider(args.source)


def cmd_scan(args):
    provider = get_required_provider(args, "scan")
    if not provider:
        return

    for input_label, context in iter_metadata_lookup_targets(args):
        if not context:
            continue

        artist, album = context
        print_album_header(None, artist, album)
        if input_label:
            print(f"Локален вход: {input_label}")

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
    provider = get_provider(args.source) if args.source else None

    for album_dir in resolve_album_dirs(args.dir, args.album_only):
        if not ensure_multi_file_album(album_dir, "преименуване"):
            continue

        context = resolve_album_context(album_dir, args)
        if not context:
            continue

        artist, album = context
        print_album_header("Преименуване", artist, album)

        if provider:
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
        else:
            print("Локален режим: имената на траковете се извличат от текущите имена на файловете.")
            matched = build_local_matched_tracks(album_dir)
            if not matched:
                print("Няма аудио файлове за локално преименуване.")
                continue
            trackmap = [track for _, track, _ in matched]

        rename_plan = build_rename_plan(matched, len(trackmap))
        if rename_plan_has_conflicts(rename_plan):
            print("Преименуването е прекъснато заради конфликт при целевите имена.")
            continue

        ensure_command_backup(album_dir, args)
        apply_rename_plan(rename_plan, args.dry_run)


def cmd_tag(args):
    provider = get_provider(args.source) if args.source else None

    for album_dir in resolve_album_dirs(args.dir, args.album_only):
        if not ensure_multi_file_album(album_dir, "тагване"):
            continue

        context = resolve_album_context(album_dir, args)
        if not context:
            continue

        artist, album = context
        print_album_header("Тагване", artist, album)

        if provider:
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
        else:
            print("Локален режим: metadata за траковете се извлича от текущите имена на файловете.")
            meta = build_local_album_metadata(album)
            matched = build_local_matched_tracks(album_dir)
            if not matched:
                print("Няма аудио файлове за локално тагване.")
                continue

        ensure_command_backup(album_dir, args)
        cover_path = resolve_cover_path(album_dir, args.cover_from, args.auto_cover)
        tag_matched_files(meta, matched, artist, cover_path, args.dry_run, args.cover_profile)


def cmd_run_all(args):
    provider = get_provider(args.source) if args.source else None

    for album_dir in resolve_album_dirs(args.dir, args.album_only):
        if not ensure_multi_file_album(album_dir, "обща обработка"):
            continue

        context = resolve_album_context(album_dir, args)
        if not context:
            continue

        artist, album = context
        print_album_header("Обща обработка", artist, album)

        if provider:
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
        else:
            print("Локален режим: преименуване и metadata от текущите имена на файловете.")
            meta = build_local_album_metadata(album)
            matched = build_local_matched_tracks(album_dir)
            if not matched:
                print("Няма аудио файлове за локална обща обработка.")
                continue
            trackmap = [track for _, track, _ in matched]

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
        tag_matched_files(
            meta,
            renamed_matched,
            artist,
            cover_path,
            args.dry_run,
            args.cover_profile,
        )


def cmd_rename_dirs(args):
    provider = get_required_provider(args, "rename-dirs")
    if not provider:
        return
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
    provider = get_required_provider(args, "cover")
    if not provider:
        return

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
            cover_index=args.cover_index,
        )


def uses_direct_sfa_inputs(args) -> bool:
    return bool(args.sfa_file or args.sfa_glob)


def iter_metadata_lookup_targets(args):
    """Връща metadata lookup targets за directory mode или explicit SFA files."""

    if uses_direct_sfa_inputs(args):
        for audio_file in resolve_sfa_audio_files(args.sfa_file, args.sfa_glob):
            yield audio_file, resolve_sfa_file_context(audio_file, args)
        return

    if not args.dir:
        print("Подай -d/--dir или explicit SFA вход чрез -F/--sfa-file или --sfa-glob.")
        return

    for album_dir in resolve_album_dirs(args.dir, args.album_only):
        yield album_dir, resolve_album_context(album_dir, args)


def iter_sfa_targets(args):
    """Връща SFA targets като (audio_file, album_dir, direct_file_mode)."""

    if uses_direct_sfa_inputs(args):
        for audio_file in resolve_sfa_audio_files(args.sfa_file, args.sfa_glob):
            yield audio_file, os.path.dirname(audio_file), True
        return

    if not args.dir:
        print("Подай -d/--dir или explicit SFA вход чрез -F/--sfa-file или --sfa-glob.")
        return

    for album_dir in resolve_album_dirs(args.dir, args.album_only):
        if not is_single_file_album(album_dir):
            print(f"Пропускане: директорията не е single-file албум: {album_dir}")
            continue

        audio_file = get_single_audio_file(album_dir)
        if audio_file:
            yield audio_file, album_dir, False


def resolve_sfa_context(audio_file: str, album_dir: str, direct_file_mode: bool, args):
    if direct_file_mode:
        return resolve_sfa_file_context(audio_file, args)

    return resolve_album_context(album_dir, args)


def cmd_chapters(args):
    provider = get_required_provider(args, "chapters")
    if not provider:
        return

    for audio_file, album_dir, direct_file_mode in iter_sfa_targets(args):
        context = resolve_sfa_context(audio_file, album_dir, direct_file_mode, args)
        if not context:
            continue

        artist, album = context
        print_album_header("Глави", artist, album)

        release_data = load_album_release_data(provider, artist, album)
        if not release_data:
            continue

        _, trackmap = release_data
        output_path = (
            resolve_sfa_chapter_output_path(audio_file, args.output)
            if direct_file_mode
            else resolve_chapter_output_path(album_dir, args.output)
        )

        provider.generate_chapter_file(trackmap, output_path, args.chapters_format)
        print(f"Записан chapter файл: {output_path}")


def cmd_embed_chapters(args):
    targets = list(iter_sfa_targets(args))
    has_output_template = args.output and ("{stem}" in args.output or "{name}" in args.output)
    if uses_direct_sfa_inputs(args) and args.output and len(targets) > 1 and not has_output_template:
        print(
            "При няколко SFA файла --output трябва да съдържа {stem}/{name} "
            "или да липсва за in-place режим."
        )
        return

    for audio_file, album_dir, direct_file_mode in targets:
        context = resolve_sfa_context(audio_file, album_dir, direct_file_mode, args)
        if not context:
            continue

        artist, album = context
        chapter_file = (
            resolve_sfa_chapter_input_path(audio_file, args.chapters_file)
            if direct_file_mode
            else resolve_chapter_input_path(album_dir, args.chapters_file)
        )
        if not os.path.exists(chapter_file):
            print(f"Липсва chapter файл: {chapter_file}")
            continue

        chapters = load_chapters_for_embedding(chapter_file)
        if not chapters:
            continue

        album_tags = None
        if args.tag_album:
            provider = get_required_provider(args, "embed-chapters -T/--tag-album")
            if not provider:
                return

            print_album_header("Тагване на single-file албум", artist, album)

            release_data = load_album_release_data(provider, artist, album)
            if not release_data:
                continue

            meta, _ = release_data
            album_tags = build_album_tags(meta, artist)

        output_path = (
            resolve_sfa_audio_output_path(audio_file, args.output)
            if direct_file_mode
            else args.output
        )
        plan = build_embed_chapters_plan(album_dir, audio_file, output_path)
        if embed_chapters_plan_has_conflict(plan):
            continue

        print(f"Вграждане на глави: {os.path.basename(audio_file)}")
        print_embed_chapters_plan(plan, chapter_file)

        if direct_file_mode:
            ensure_file_command_backup(audio_file, args)
        else:
            ensure_command_backup(album_dir, args)

        if album_tags and args.dry_run:
            cover_path = resolve_cover_path(album_dir, args.cover_from, args.auto_cover)
            tag_audio_file(
                plan["final_path"],
                album_tags,
                cover_path,
                dry_run=True,
                cover_profile=args.cover_profile,
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
            cover_profile=args.cover_profile,
        )


def resolve_split_output_dir(audio_file: str, profile_name: str, output_dir: str | None) -> str:
    stem = os.path.splitext(os.path.basename(audio_file))[0]
    source_dir = os.path.dirname(audio_file)

    if output_dir:
        resolved = output_dir.format(stem=stem, name=stem, profile=profile_name)
        if os.path.isabs(resolved):
            return os.path.abspath(resolved)
        return os.path.abspath(os.path.join(source_dir, resolved))

    return os.path.abspath(os.path.join(source_dir, f"{stem}_tracks_{profile_name}"))


def cmd_split_sfa(args):
    targets = list(iter_sfa_targets(args))
    if not targets:
        return

    has_output_template = args.output_dir and (
        "{stem}" in args.output_dir or "{name}" in args.output_dir or "{profile}" in args.output_dir
    )
    if uses_direct_sfa_inputs(args) and args.output_dir and len(targets) > 1 and not has_output_template:
        print(
            "При няколко SFA файла --output-dir трябва да съдържа {stem}/{name}/{profile} "
            "или да липсва, за да се създаде отделна директория за всеки файл."
        )
        return

    for audio_file, album_dir, direct_file_mode in targets:
        context = resolve_sfa_context(audio_file, album_dir, direct_file_mode, args)
        if not context:
            continue
        artist, album = context

        chapter_file = (
            resolve_sfa_chapter_input_path(audio_file, args.chapters_file)
            if direct_file_mode
            else resolve_chapter_input_path(album_dir, args.chapters_file)
        )
        if not os.path.exists(chapter_file):
            print(f"Липсва chapter файл: {chapter_file}")
            continue

        chapters = load_chapters_for_embedding(chapter_file, header="Глави за разделяне:")
        if not chapters:
            continue

        cover_path = resolve_cover_path(album_dir, args.cover_from, args.auto_cover)
        output_dir = resolve_split_output_dir(audio_file, args.split_profile, args.output_dir)

        print_album_header("Разделяне на SFA", artist, album)
        print(f"Входен аудио файл: {audio_file}")
        print(f"Chapter файл: {chapter_file}")
        try:
            split_sfa_file(
                input_file=audio_file,
                chapters=chapters,
                output_dir=output_dir,
                profile_name=args.split_profile,
                artist=artist,
                album=album,
                cover_path=cover_path,
                bitrate=args.bitrate,
                sample_rate_hz=args.sample_rate,
                dry_run=args.dry_run,
                force=args.force,
            )
        except FileExistsError as exc:
            print(f"Пропускане: {exc}")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="albumtool",
        description="Инструмент за разпознаване, преименуване и тагване на албуми.",
    )
    parser.add_argument(
        "-S",
        "--source",
        choices=["itunes", "discogs", "musicbrainz"],
        help=(
            "Източник на метаданни: itunes, discogs или musicbrainz. "
            "Задължителен само за команди, които търсят/изтеглят metadata."
        ),
    )

    sub = parser.add_subparsers(dest="command", required=True)

    scan_parser = sub.add_parser(
        "scan",
        aliases=["sc"],
        help="Сканира директория и показва намерения албум и тракове.",
    )
    add_album_selection_arguments(
        scan_parser,
        "Директория с аудио файлове или директория на изпълнител. "
        "Алтернатива за single-file албуми: -F/--sfa-file или --sfa-glob.",
        required=False,
    )
    add_sfa_file_arguments(scan_parser)
    scan_parser.set_defaults(func=cmd_scan)

    rename_parser = sub.add_parser(
        "rename",
        aliases=["ren", "rn"],
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
        aliases=["tg"],
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
    add_cover_profile_argument(tag_parser)
    tag_parser.set_defaults(func=cmd_tag)

    all_parser = sub.add_parser(
        "run-all",
        aliases=["all", "ra"],
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
    add_cover_profile_argument(all_parser)
    all_parser.set_defaults(func=cmd_run_all)

    dirs_parser = sub.add_parser(
        "rename-dirs",
        aliases=["dirs", "rd"],
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
        help="Показва локални и remote cover кандидати с формат, пиксели и файлов размер.",
    )
    cover_parser.add_argument(
        "-I",
        "--cover-index",
        type=int,
        default=1,
        help="1-базиран индекс на remote обложката за реално изтегляне. По подразбиране: 1.",
    )
    cover_parser.set_defaults(func=cmd_cover)

    chapters_parser = sub.add_parser(
        "chapters",
        aliases=["ch"],
        help="Генерира chapter файл за single-file албум.",
    )
    add_album_selection_arguments(
        chapters_parser,
        "Директория със single-file албум или директория на изпълнител. "
        "Алтернатива: -F/--sfa-file или --sfa-glob.",
        required=False,
    )
    add_sfa_file_arguments(chapters_parser)
    chapters_parser.add_argument(
        "-o",
        "--output",
        help=(
            "Път за генерирания chapter файл. Directory mode: <album>/chapters.txt. "
            "Direct SFA mode: <audio-stem>.chapters.txt. Поддържа {stem}."
        ),
    )
    chapters_parser.add_argument(
        "--chapters-format",
        choices=CHAPTER_FORMAT_CHOICES,
        default="human",
        help=(
            "Формат на генерирания chapter файл. human е лесен за ръчна редакция; "
            "ogm е старият FFmpeg/CHAPTERXX формат."
        ),
    )
    chapters_parser.set_defaults(func=cmd_chapters)

    embed_parser = sub.add_parser(
        "embed-chapters",
        aliases=["embed", "ech"],
        help="Вгражда редактиран chapter файл в single-file албум.",
    )
    add_album_selection_arguments(
        embed_parser,
        "Директория със single-file албум или директория на изпълнител. "
        "Алтернатива: -F/--sfa-file или --sfa-glob.",
        required=False,
    )
    add_sfa_file_arguments(embed_parser)
    add_backup_arguments(embed_parser)
    add_cover_arguments(embed_parser)
    add_auto_cover_argument(embed_parser)
    add_cover_profile_argument(embed_parser)
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
        help=(
            "Път до chapter файл. Directory mode: <album>/chapters.txt. "
            "Direct SFA mode: <audio-stem>.chapters.txt. Поддържа {stem}."
        ),
    )
    embed_parser.add_argument(
        "-o",
        "--output",
        help=(
            "Изходен аудио файл. Ако липсва, оригиналният файл се обновява на място. "
            "При групов direct SFA режим използвай {stem}, например '{stem}.tagged.m4a'."
        ),
    )
    embed_parser.set_defaults(func=cmd_embed_chapters)

    split_parser = sub.add_parser(
        "split-sfa",
        aliases=["split", "sfs"],
        help="Разделя single-file албум на отделни тракове според chapter файл.",
    )
    add_album_selection_arguments(
        split_parser,
        "Директория със single-file албум или директория на изпълнител. "
        "Алтернатива: -F/--sfa-file или --sfa-glob.",
        required=False,
    )
    add_sfa_file_arguments(split_parser)
    add_cover_arguments(split_parser)
    add_auto_cover_argument(split_parser)
    split_parser.add_argument(
        "-c",
        "--chapters-file",
        help=(
            "Път до chapter файл. Directory mode: <album>/chapters.txt. "
            "Direct SFA mode: <audio-stem>.chapters.txt. Поддържа {stem}."
        ),
    )
    split_parser.add_argument(
        "-o",
        "--output-dir",
        help=(
            "Изходна директория за траковете. По подразбиране: "
            "<audio-stem>_tracks_<profile>. Поддържа {stem}, {name}, {profile}."
        ),
    )
    split_parser.add_argument(
        "-P",
        "--split-profile",
        choices=sorted(SPLIT_PROFILES.keys()),
        default="lexus-mp3",
        help="Encoding профил за изходните тракове. По подразбиране: lexus-mp3.",
    )
    split_parser.add_argument(
        "-b",
        "--bitrate",
        default="auto",
        help=(
            "Изходен bitrate. auto избира най-близкия стандартен bitrate >= входния. "
            "Може да се зададе и явно, например 128k, 144k, 160k."
        ),
    )
    split_parser.add_argument(
        "--sample-rate",
        type=int,
        default=48000,
        help="Изходна sample rate честота в Hz. По подразбиране: 48000.",
    )
    split_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Позволява презапис на вече съществуващи изходни тракове.",
    )
    split_parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Само показва командите и плана, без да създава файлове.",
    )
    split_parser.set_defaults(func=cmd_split_sfa)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
