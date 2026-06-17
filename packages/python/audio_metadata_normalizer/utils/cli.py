# audio_metadata_normalizer/utils/cli.py

"""
Общи helper-и за CLI parser-и.

Всички help текстове са на български и са независими от конкретната команда.
"""

import argparse
import os
from audio_metadata_normalizer.utils.cover_profile import COVER_PROFILE_CHOICES
from audio_metadata_normalizer.utils.files import (
    ensure_backup,
    ensure_file_backup,
    resolve_backup_dir,
    should_create_backup,
)


def parse_match_threshold(value: str) -> float:
    try:
        threshold = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Прагът трябва да е число между 0.0 и 1.0."
        ) from exc

    if not 0.0 <= threshold <= 1.0:
        raise argparse.ArgumentTypeError("Прагът трябва да е число между 0.0 и 1.0.")

    return threshold


def add_album_selection_arguments(parser, dir_help: str, required: bool = True):
    parser.add_argument("-d", "--dir", required=required, help=dir_help)
    parser.add_argument("-a", "--artist", help="Име на изпълнител (по желание).")
    parser.add_argument("-A", "--album", help="Име на албум (по желание).")
    parser.add_argument(
        "-O", "--album-only",
        action="append",
        default=[],
        help="Обработва само посочения албум. Може да се подаде повече от веднъж."
    )


def add_sfa_file_arguments(parser):
    parser.add_argument(
        "-F",
        "--sfa-file",
        action="append",
        default=[],
        help=(
            "Директен single-file album аудио файл. Може да се подаде повече от веднъж. "
            "Artist/album се извличат от името на файла или се задават с --artist/--album."
        ),
    )
    parser.add_argument(
        "--sfa-glob",
        action="append",
        default=[],
        help=(
            "Glob шаблон за групов избор на SFA файлове, например "
            "'/music/sfa/*.m4a'. Може да се подаде повече от веднъж."
        ),
    )


def add_backup_arguments(parser):
    parser.add_argument(
        "--backup-dir",
        help="Директория за бекъп. Ако липсва, се ползва <dir>/_backup."
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Без бекъп (НЕ се препоръчва)."
    )
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Само показва какво ще се промени."
    )


def add_match_arguments(parser):
    parser.add_argument(
        "-M", "--match-threshold",
        type=parse_match_threshold,
        default=0.55,
        help="Минимален праг за съвпадение между файл и трак. Стойност между 0.0 и 1.0."
    )


def add_cover_arguments(parser):
    parser.add_argument(
        "-C", "--cover-from",
        help="Път до локален файл с обложка (по желание)."
    )


def add_auto_cover_argument(parser):
    parser.add_argument(
        "--auto-cover",
        action="store_true",
        help="Автоматично използва локална cover/folder/front/album обложка, ако има такава."
    )


def add_cover_profile_argument(parser):
    parser.add_argument(
        "-P",
        "--cover-profile",
        choices=COVER_PROFILE_CHOICES,
        default="source",
        help=(
            "Профил за вграждане на обложка: source запазва входния файл; "
            "lexus-jpeg-300 и lexus-jpeg-500 създават JPEG обложка за Lexus/Android Auto "
            "съвместимост."
        ),
    )


def ensure_command_backup(album_dir: str, args):
    backup_dir = resolve_backup_dir(album_dir, args.backup_dir)
    if should_create_backup(args.no_backup, args.dry_run):
        print(f"Създаване на бекъп в: {backup_dir}")
        ensure_backup(album_dir, backup_dir)


def ensure_file_command_backup(file_path: str, args):
    backup_dir = resolve_backup_dir(os.path.dirname(file_path), args.backup_dir)
    if should_create_backup(args.no_backup, args.dry_run):
        print(f"Създаване на бекъп в: {backup_dir}")
        ensure_file_backup(file_path, backup_dir)


def confirm_action(prompt: str, assume_yes: bool = False) -> bool:
    if assume_yes:
        return True

    answer = input(f"{prompt} [y/N]: ").strip().lower()
    return answer in {"y", "yes", "д", "да"}
