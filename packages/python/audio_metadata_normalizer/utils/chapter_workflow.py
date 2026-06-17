# audio_metadata_normalizer/utils/chapter_workflow.py

"""
Помощни функции за single-file албуми и chapter workflow.

Тук е логиката около:
- пътища до chapter файлове;
- пътища за изходен аудио файл;
- план за in-place или output-file вграждане;
- валидация и преглед на редактирани глави.
"""

import os

from audio_metadata_normalizer.utils.chapters import parse_chapter_file


def _apply_audio_template(path_value: str, audio_file: str) -> str:
    stem = os.path.splitext(os.path.basename(audio_file))[0]
    return path_value.format(stem=stem, name=stem)


def default_sfa_chapter_filename(audio_file: str) -> str:
    stem = os.path.splitext(os.path.basename(audio_file))[0]
    return f"{stem}.chapters.txt"


def resolve_chapter_output_path(album_dir: str, output_path: str | None) -> str:
    if not output_path:
        return os.path.join(album_dir, "chapters.txt")

    if os.path.isabs(output_path):
        return output_path

    return os.path.join(album_dir, output_path)


def resolve_sfa_chapter_output_path(audio_file: str, output_path: str | None) -> str:
    album_dir = os.path.dirname(audio_file)
    name = output_path or default_sfa_chapter_filename(audio_file)
    name = _apply_audio_template(name, audio_file)

    if os.path.isabs(name):
        return name

    return os.path.join(album_dir, name)


def resolve_chapter_input_path(album_dir: str, chapter_file: str | None) -> str:
    if not chapter_file:
        return os.path.join(album_dir, "chapters.txt")

    if os.path.isabs(chapter_file):
        return chapter_file

    return os.path.join(album_dir, chapter_file)


def resolve_sfa_chapter_input_path(audio_file: str, chapter_file: str | None) -> str:
    album_dir = os.path.dirname(audio_file)
    name = chapter_file or default_sfa_chapter_filename(audio_file)
    name = _apply_audio_template(name, audio_file)

    if os.path.isabs(name):
        return name

    return os.path.join(album_dir, name)


def resolve_audio_output_path(album_dir: str, output_path: str | None) -> str | None:
    if not output_path:
        return None

    if os.path.isabs(output_path):
        return output_path

    return os.path.join(album_dir, output_path)


def resolve_sfa_audio_output_path(audio_file: str, output_path: str | None) -> str | None:
    if not output_path:
        return None

    name = _apply_audio_template(output_path, audio_file)
    if os.path.isabs(name):
        return name

    return os.path.join(os.path.dirname(audio_file), name)


def build_temp_chaptered_path(audio_file: str) -> str:
    dir_name = os.path.dirname(audio_file)
    base_name = os.path.basename(audio_file)
    return os.path.join(dir_name, f".tmp_chapters_{base_name}")


def build_embed_chapters_plan(album_dir: str, audio_file: str, output_path: str | None):
    resolved_output = resolve_audio_output_path(album_dir, output_path)
    in_place = (
        resolved_output is None
        or os.path.abspath(resolved_output) == os.path.abspath(audio_file)
    )

    final_path = audio_file if in_place else resolved_output
    tmp_out = build_temp_chaptered_path(audio_file) if in_place else final_path

    return {
        "audio_file": audio_file,
        "final_path": final_path,
        "tmp_out": tmp_out,
        "in_place": in_place,
    }


def embed_chapters_plan_has_conflict(plan) -> bool:
    if plan["in_place"]:
        return False

    if os.path.exists(plan["final_path"]):
        print(f"Пропускане: целевият файл вече съществува: {plan['final_path']}")
        return True

    return False


def print_embed_chapters_plan(plan, chapter_file: str):
    print(f"Входен аудио файл: {plan['audio_file']}")
    print(f"Chapter файл: {chapter_file}")

    if plan["in_place"]:
        print(f"Режим: обновяване на място чрез временен файл {plan['tmp_out']}")
        return

    print(f"Режим: запис в нов файл {plan['final_path']}")


def validate_chapters(chapters) -> bool:
    if not chapters:
        print("Chapter файлът не съдържа валидни глави.")
        return False

    first_start = chapters[0].get("start")
    if first_start != "00:00:00.000":
        print("Първата глава трябва да започва от 00:00:00.000.")
        return False

    for chapter in chapters:
        if not chapter.get("title") or not chapter.get("start"):
            print("Има глава без заглавие или начален момент.")
            return False

    return True


def print_chapters(chapters, header: str = "Глави за вграждане:"):
    print(header)
    for idx, chapter in enumerate(chapters, start=1):
        print(f"{idx:02d}. {chapter['start']} - {chapter['title']}")


def load_chapters_for_embedding(chapter_file: str, header: str = "Глави за вграждане:"):
    try:
        chapters = parse_chapter_file(chapter_file)
    except ValueError as exc:
        print(f"Грешка в chapter файла: {exc}")
        return None

    if not validate_chapters(chapters):
        return None

    print_chapters(chapters, header=header)
    return chapters
