"""
Помощни функции за split/fade/concat project workflow.
"""

import subprocess
import json
import platform
from jsonschema import validate

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "videos": {
            "type": "object",
            "patternProperties": {
                ".*": {
                    "type": "object",
                    "properties": {
                        "segments": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 2,
                                "maxItems": 2
                            }
                        },
                        "fade": {"type": "number", "minimum": 0}
                    },
                    "required": ["segments", "fade"]
                }
            }
        },
        "encoding": {
            "type": "object",
            "properties": {
                "video": {
                    "type": "object",
                    "properties": {
                        "codec": {"type": "string"},
                        "crf": {"type": "integer", "minimum": 0, "maximum": 51},
                        "preset": {"type": "string"},
                        "profile": {"type": "string"},
                        "tune": {"type": "string"}
                    },
                    "required": ["codec", "crf", "preset"]
                },
                "audio": {
                    "type": "object",
                    "properties": {
                        "codec": {"type": "string"},
                        "bitrate": {"type": "string"},
                        "channels": {"type": "integer", "minimum": 1, "maximum": 8},
                        "sample_rate": {"type": "string"}
                    },
                    "required": ["codec", "bitrate"]
                }
            },
            "required": ["video", "audio"]
        }
    },
    "required": ["videos", "encoding"]
}


def validate_config(config):
    validate(instance=config, schema=CONFIG_SCHEMA)


def time_to_seconds(time_str):
    h, m, s = map(float, time_str.split(':'))
    return h * 3600 + m * 60 + s


def get_font_path():
    system = platform.system()
    if system == "Windows":
        return "C:/Windows/Fonts/arial.ttf"
    elif system == "Darwin":
        return "/System/Library/Fonts/Helvetica.ttc"
    else:
        return "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def get_video_metadata(video_path):
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", video_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return json.loads(result.stdout)
