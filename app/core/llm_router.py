import itertools
import os
from enum import Enum
from dataclasses import dataclass
from typing import Iterable, List, Dict
from loguru import logger

class Feature(Enum):
    DREAM = "dream"
    NUMEROLOGY = "numerology"

@dataclass
class LLMConfig:
    model: str
    keys: List[str]

def _split_env(name: str) -> List[str]:
    raw = os.getenv(name, "")
    return [x.strip() for x in raw.split(",") if x.strip()]

def _cycle(lst: List[str]) -> Iterable[str]:
    # безопасный цикл (если список пуст — вернём пустую строку)
    return itertools.cycle(lst if lst else [""])

class KeyRouter:
    """Round-robin маршрутизатор API-ключей по фичам."""
    def __init__(self) -> None:
        self._map: Dict[Feature, LLMConfig] = {
            Feature.DREAM: LLMConfig(
                model=os.getenv("LLM_DREAM_MODEL", "gpt-4o-mini"),
                keys=_split_env("LLM_DREAM_KEYS"),
            ),
            Feature.NUMEROLOGY: LLMConfig(
                model=os.getenv("LLM_NUMEROLOGY_MODEL", "gpt-4o-mini"),
                keys=_split_env("LLM_NUMEROLOGY_KEYS"),
            ),
        }
        logger.info(
            "[llm] init: dream_keys={}, numerology_keys={}, dream_model={}, numerology_model={}",
            len(self._map[Feature.DREAM].keys),
            len(self._map[Feature.NUMEROLOGY].keys),
            self._map[Feature.DREAM].model,
            self._map[Feature.NUMEROLOGY].model,
        )
        self._rr: Dict[Feature, Iterable[str]] = {
            feat: _cycle(cfg.keys) for feat, cfg in self._map.items()
        }

    def next_creds(self, feature: Feature) -> tuple[str, str]:
        cfg = self._map[feature]
        key = next(self._rr[feature])
        return key, cfg.model
