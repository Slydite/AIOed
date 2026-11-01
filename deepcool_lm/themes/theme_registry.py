"""
Theme Registry for DeepCool LM360 LCD.
Provides discovery, configuration options, and unified rendering for themes.
"""

from deepcool_lm.themes.cyber_stats import CyberStatsTheme
from deepcool_lm.themes.cyber_dual import CyberDualTheme
from deepcool_lm.themes.white_edition import WhiteEditionTheme
from deepcool_lm.themes.single_gauge import SingleGaugeTheme
from deepcool_lm.themes.retro_matrix import RetroMatrixTheme
from deepcool_lm.themes.theme_base import METRIC_DEFINITIONS

THEMES = {
    CyberStatsTheme.id: CyberStatsTheme(),
    CyberDualTheme.id: CyberDualTheme(),
    WhiteEditionTheme.id: WhiteEditionTheme(),
    SingleGaugeTheme.id: SingleGaugeTheme(),
    RetroMatrixTheme.id: RetroMatrixTheme(),
}

DEFAULT_THEME_ID = CyberStatsTheme.id


def get_theme(theme_id: str):
    return THEMES.get(theme_id, THEMES[DEFAULT_THEME_ID])


def list_themes() -> list[dict]:
    result = []
    for t_id, instance in THEMES.items():
        result.append({
            "id": t_id,
            "name": instance.name,
            "description": instance.description,
            "slots": instance.get_supported_slots(),
        })
    return result


def get_available_metrics() -> dict:
    return {
        k: {
            "name": v["name"],
            "short": v["short"],
            "unit": v["default_unit"]
        }
        for k, v in METRIC_DEFINITIONS.items()
    }

