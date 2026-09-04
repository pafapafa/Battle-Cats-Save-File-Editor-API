from __future__ import annotations
from bcsfe import core
from bcsfe.cli import color
import datetime


class Fixes:
    @staticmethod
    def fix_gamatoto_crash(save_file: core.SaveFile):
        save_file.gamatoto.skin = 2

        color.color_print_key("fix_gamatoto_crash_success")

    @staticmethod
    def fix_ototo_crash(save_file: core.SaveFile):
        save_file.ototo.cannons = core.game.gamoto.ototo.Cannons.init(
            save_file.game_version
        )
        color.color_print_key("fix_ototo_crash_success")

    @staticmethod
    def fix_time_errors(save_file: core.SaveFile):
        save_file.date_3 = datetime.datetime.now()
        save_file.timestamp = datetime.datetime.now().timestamp()
        save_file.energy_penalty_timestamp = datetime.datetime.now().timestamp()

        color.color_print_key("fix_time_errors_success")
