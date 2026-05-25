import pathlib
from .models import Config

config = Config.model_validate_json(
    pathlib.Path(__file__).resolve().parents[2].with_name("config.json").read_text()
)
