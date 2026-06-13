"""
Главен CLI за project workflow, който разделя видео, добавя fade преходи и сглобява резултат.
"""

import json
from jsonschema import ValidationError
from utils import validate_config
from preview import preview_all_videos
from processor import process_all_videos

def load_config(config_path="config.json"):
    with open(config_path) as f:
        config = json.load(f)
    validate_config(config)
    return config

def main():
    try:
        config = load_config()
        
        if input("Преглед преди обработка? (y/n): ").lower() == "y":
            preview_all_videos(config["videos"])
            
        if input("Продължи с обработката? (y/n): ").lower() == "y":
            process_all_videos(config["videos"], config["encoding"])
            
    except ValidationError as e:
        print(f"Грешка в конфигурацията: {e.message}")
    except FileNotFoundError:
        print("Грешка: Конфигурационният файл не е намерен")
    except json.JSONDecodeError:
        print("Грешка: Невалиден JSON формат")
    except Exception as e:
        print(f"Неочаквана грешка: {str(e)}")

if __name__ == "__main__":
    main()
