import copy
import datetime
import socket
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import bcsfe_runtime
from bcsfe import core
from bcsfe.core.game.gamoto.gamatoto import GamatotoLevel, GamatotoLimit, MemberName, Helper, Helpers
from bcsfe.core.game.gamoto.ototo import Cannon, Cannons, CastleRecipeUnlock, LevelPartRecipeUnlock
from bcsfe.core.game.catbase.user_rank_rewards import RankGift, Reward
import editor_misc as misc


class MiscEditorTests(unittest.TestCase):
    def setUp(self):
        self.net = patch.object(socket, "create_connection", side_effect=AssertionError("No network in editor tests"))
        self.net.start()
        self.addCleanup(self.net.stop)
        self.sf = core.SaveFile(cc=core.CountryCode.from_code("en"), gv=core.GameVersion(150000))
        for key, value in vars(self.sf).items():
            if isinstance(value, datetime.datetime):
                setattr(self.sf, key, datetime.datetime(2020, 1, 2))
        self.sf.menu_unlocks = [0, 0, 0]
        self.sf.xp = 117
        self.sf.gamatoto.skin = 7
        self.sf.officer_pass.play_time = 4321
        self.sf.officer_pass.gold_pass.officer_id = 55
        self.sf.enemy_guide = [0, 1, 0, 0, 0]
        self.sf.ototo.base_materials = core.BaseMaterials.deserialize([11, 22, 33, 44])

    def apply(self, action, **args):
        return misc.ACTIONS[action]["apply"](self.sf, args)

    def meta(self, name, value):
        context = patch.object(core.core_data, name, return_value=value)
        context.start()
        self.addCleanup(context.stop)
        return context

    def gamatoto_levels(self):
        data = object.__new__(core.GamatotoLevels)
        data.levels = [GamatotoLevel(1, 100, 0, 0), GamatotoLevel(2, 300, 0, 0), GamatotoLevel(3, 600, 0, 0)]
        data.limit = GamatotoLimit(3, 99, 8)
        self.meta("get_gamatoto_levels", data)
        return data

    def test_helper_empty_sentinel_does_not_consume_capacity(self):
        levels = self.gamatoto_levels()
        levels.limit.total_helpers = 2
        names = object.__new__(core.GamatotoMembersName)
        names.members = [MemberName(10, 0, 0, "A", "R", []), MemberName(23, 1, 0, "B", "S", [])]
        self.meta("get_gamatoto_members_name", names)
        self.sf.gamatoto.helpers = Helpers([Helper(-1), Helper(23)])
        self.apply("gamatoto.helpers", rarities={"0": 1})
        restored = core.SaveFile(core.Data(self.sf.to_data().data))
        self.assertEqual(restored.gamatoto.helpers.serialize(), [23, 10])
        self.assertEqual(restored.officer_pass.play_time, 4321)

    def test_disabled_helper_maximum_keeps_id_and_save_size_validation(self):
        self.gamatoto_levels()
        names = object.__new__(core.GamatotoMembersName)
        names.members = [MemberName(10, 0, 0, "A", "R", [])]
        self.meta("get_gamatoto_members_name", names)
        self.apply("gamatoto.helpers", rarities={"0": 10}, respect_maxima=False)
        self.assertEqual(self.sf.gamatoto.helpers.serialize(), [10] * 10)
        with self.assertRaises(ValueError):
            self.apply("gamatoto.helpers", ids=[99], respect_maxima=False)
        with self.assertRaises(ValueError):
            self.apply("gamatoto.helpers", rarities={"0": 2147483647}, respect_maxima=False)
        self.assertEqual(self.sf.gamatoto.helpers.serialize(), [10] * 10)

    def test_disabled_gamatoto_level_cap_requires_an_actual_xp_row(self):
        levels = self.gamatoto_levels()
        levels.limit.max_level = 2
        with self.assertRaises(ValueError):
            self.apply("gamatoto.level", value=3)
        self.apply("gamatoto.level", value=3, respect_maxima=False)
        self.assertEqual(self.sf.gamatoto.xp, 300)
        with self.assertRaises(ValueError):
            self.apply("gamatoto.level", value=4, respect_maxima=False)

    def test_disabled_engineer_material_and_cannon_maxima_roundtrip(self):
        self.meta("get_game_data_getter", SimpleNamespace(download=lambda *args: core.Data(b"9\n")))
        self.cannon_fixture()
        with self.assertRaises(ValueError):
            self.apply("ototo.engineers", value=10)
        self.apply("ototo.engineers", value=2147483647, respect_maxima=False)
        self.apply("ototo.materials", values={"2": 2147483647}, respect_maxima=False)
        self.apply("ototo.cannons", ids=[13], levels={"0": 100, "1": 100}, respect_maxima=False)
        restored = core.SaveFile(core.Data(self.sf.to_data().data))
        self.assertEqual(restored.ototo.engineers, 2147483647)
        self.assertEqual(restored.ototo.base_materials.serialize(), [11, 22, 2147483647, 44])
        self.assertEqual(restored.ototo.cannons.cannons[13].serialize(), [3, 99, 100, 4])
        for action, args in [
            ("ototo.engineers", {"value": 2147483648}),
            ("ototo.materials", {"values": {"2": 2147483648}}),
            ("ototo.cannons", {"ids": [13], "levels": {"0": 2147483648}}),
            ("ototo.cannons", {"ids": [13], "development": 4}),
        ]:
            with self.subTest(action=action), self.assertRaises(ValueError):
                self.apply(action, **args, respect_maxima=False)

    def test_shrine_long_storage_and_original_disabled_prompt_ceiling(self):
        levels = self.shrine_fixture()
        with self.assertRaises(ValueError):
            self.apply("shrine.set", xp=601)
        self.apply("shrine.set", xp=2147483647, respect_maxima=False)
        restored = core.SaveFile(core.Data(self.sf.to_data().data))
        self.assertEqual(restored.cat_shrine.xp_offering, 2147483647)
        self.assertEqual(restored.cat_shrine.dialogs, 2)
        with self.assertRaises(ValueError):
            self.apply("shrine.set", xp=2147483648, respect_maxima=False)
        self.apply("shrine.set", level=99, respect_maxima=False)
        self.assertEqual(self.sf.cat_shrine.xp_offering, 600)


        levels.boundaries = [100, 300, 6000000000]
        self.apply("shrine.set", xp=5000000000)
        restored = core.SaveFile(core.Data(self.sf.to_data().data))
        self.assertEqual(restored.cat_shrine.xp_offering, 5000000000)

    def test_cannon_display_level_zero_stores_original_minus_one(self):
        self.cannon_fixture()
        self.apply("ototo.cannons", ids=[13], levels={"0": 0})
        restored = core.SaveFile(core.Data(self.sf.to_data().data))
        self.assertEqual(restored.ototo.cannons.cannons[13].serialize(), [3, -1, 3, 4])

    def test_disabled_slot_limit_still_uses_signed_byte_or_old_ten_flags(self):
        with self.assertRaises(ValueError):
            self.apply("lineups.unlocked_slots", value=16)
        self.apply("lineups.unlocked_slots", value=127, respect_maxima=False)
        restored = core.SaveFile(core.Data(self.sf.to_data().data))
        self.assertEqual(restored.lineups.unlocked_slots, 127)
        with self.assertRaises(ValueError):
            self.apply("lineups.unlocked_slots", value=128, respect_maxima=False)
        self.sf.game_version = core.GameVersion(90600)
        with self.assertRaises(ValueError):
            self.apply("lineups.unlocked_slots", value=11, respect_maxima=False)

    def test_registry_contract(self):
        self.assertEqual(len(misc.ACTIONS), 20)
        for action in misc.ACTIONS.values():
            self.assertTrue(action["description"])
            self.assertTrue(action["source"])
            self.assertEqual(action["schema"]["type"], "object")
            self.assertTrue(callable(action["apply"]))

    def test_xp_does_not_reset_skin_pass_or_other_expedition_fields(self):
        before = self.sf.to_dict()
        self.apply("gamatoto.xp", value=8765)
        after = self.sf.to_dict()
        before["gamatoto"]["xp"] = 8765
        self.assertEqual(before, after)
        self.assertEqual(self.sf.officer_pass.play_time, 4321)

    def test_level_uses_metadata_and_rejects_out_of_range(self):
        self.gamatoto_levels()
        self.apply("gamatoto.level", value=3)
        self.assertEqual(self.sf.gamatoto.xp, 300)
        self.assertEqual(self.sf.gamatoto.skin, 7)
        with self.assertRaises(ValueError):
            self.apply("gamatoto.level", value=4)

    def test_helper_partial_rarity_edit_and_metadata_limit(self):
        levels = self.gamatoto_levels()
        names = object.__new__(core.GamatotoMembersName)
        names.members = [MemberName(10, 0, 0, "A", "R", []), MemberName(23, 1, 0, "B", "S", [])]
        self.meta("get_gamatoto_members_name", names)
        self.sf.gamatoto.helpers = Helpers([Helper(10), Helper(23)])
        self.apply("gamatoto.helpers", rarities={"0": 5})
        self.assertEqual(self.sf.gamatoto.helpers.serialize(), [23, 10, 10, 10, 10, 10])
        before = self.sf.gamatoto.helpers.serialize()
        with self.assertRaises(ValueError):
            self.apply("gamatoto.helpers", rarities={"0": 8})
        self.assertEqual(self.sf.gamatoto.helpers.serialize(), before)
        self.apply("gamatoto.helpers", ids=[])
        self.assertEqual(self.sf.gamatoto.helpers.serialize(), [])
        levels.limit.total_helpers = 1
        with self.assertRaises(ValueError):
            self.apply("gamatoto.helpers", ids=[10, 23])

    def test_engineers_uses_metadata_instead_of_hardcoded_five(self):
        self.meta("get_game_data_getter", SimpleNamespace(download=lambda *args: core.Data(b"9\n")))
        self.apply("ototo.engineers", value=8)
        self.assertEqual(self.sf.ototo.engineers, 8)
        with self.assertRaises(ValueError):
            self.apply("ototo.engineers", value=10)

    def test_material_index_preservation_and_no_silent_expansion(self):
        self.apply("ototo.materials", values={"2": 78})
        self.assertEqual(self.sf.ototo.base_materials.serialize(), [11, 22, 78, 44])
        with self.assertRaises(ValueError):
            self.apply("ototo.materials", values={"9": 9})
        self.assertEqual(self.sf.ototo.base_materials.serialize(), [11, 22, 78, 44])

    def cannon_fixture(self):
        self.sf.ototo.cannons = Cannons({0: Cannon(0, [9]), 13: Cannon(1, [2, 3, 4]), 99: Cannon(2, [8, 8, 8])}, [[13, 0, 0]])
        recipe = object.__new__(CastleRecipeUnlock)
        recipe.level_part_recipe_unlocks = [LevelPartRecipeUnlock(i, cannon, part, 0, 0, maximum) for i, (cannon, part, maximum) in enumerate([(0, 0, 30), (13, 0, 25), (13, 1, 12), (13, 2, 7)])]
        context = patch.object(misc, "CastleRecipeUnlock", return_value=recipe)
        context.start()
        self.addCleanup(context.stop)

    def test_cannons_use_real_ids_and_display_level_preserve_unselected(self):
        self.cannon_fixture()
        self.apply("ototo.cannons", ids=[13], levels={"0": 20})
        self.assertEqual(self.sf.ototo.cannons.cannons[13].serialize(), [3, 19, 3, 4])
        self.assertEqual(self.sf.ototo.cannons.cannons[99].serialize(), [2, 8, 8, 8])
        self.assertEqual(self.sf.ototo.cannons.selected_parts, [[13, 0, 0]])
        self.apply("ototo.cannons", ids=[13], max=True)
        self.assertEqual(self.sf.ototo.cannons.cannons[13].serialize(), [3, 24, 12, 7])
        self.apply("ototo.cannons", ids=[13], development=0)
        self.assertEqual(self.sf.ototo.cannons.cannons[13].development, 0)

    def test_cannon_invalid_second_entry_cannot_partly_apply(self):
        self.cannon_fixture()
        before = copy.deepcopy(self.sf.ototo.cannons.serialize())
        with self.assertRaises(ValueError):
            self.apply("ototo.cannons", entries=[{"id": 13, "development": 3}, {"id": 99, "levels": {"0": 20}}])
        self.assertEqual(self.sf.ototo.cannons.serialize(), before)

    def shrine_fixture(self):
        levels = object.__new__(core.CatShrineLevels)
        levels.boundaries = [100, 300, 600]
        self.meta("get_cat_shrine_levels", levels)
        return levels

    def test_shrine_level_one_is_zero_not_negative_index_maximum(self):
        levels = self.shrine_fixture()
        self.assertEqual(levels.get_xp_from_level(1), 600)
        self.apply("shrine.set", level=1)
        self.assertEqual(self.sf.cat_shrine.xp_offering, 0)
        self.assertEqual(self.sf.cat_shrine.dialogs, 0)
        self.apply("shrine.set", level=3)
        self.assertEqual(self.sf.cat_shrine.xp_offering, 300)
        self.assertEqual(self.sf.cat_shrine.dialogs, 2)

    def test_shrine_visibility_keeps_flags_and_updates_timestamps_as_source(self):
        self.shrine_fixture()
        self.sf.cat_shrine.flags = [9, 1]
        self.sf.cat_shrine.stamp_1 = 87
        self.apply("shrine.set", visible=True)
        self.assertFalse(self.sf.cat_shrine.shrine_gone)
        self.assertEqual(self.sf.cat_shrine.stamp_1, 0)
        self.assertEqual(self.sf.cat_shrine.flags, [9, 1])
        self.apply("shrine.set", visible=False)
        self.assertTrue(self.sf.cat_shrine.shrine_gone)

    def test_rewards_respect_current_rank_and_fix_claimed(self):
        self.sf.user_rank_rewards.rewards = [Reward(False), Reward(False), Reward(True)]
        rank = self.sf.calculate_user_rank()
        self.meta("get_rank_gifts", SimpleNamespace(rank_gift=[RankGift(0, 0, []), RankGift(1, rank, []), RankGift(2, rank + 100, [])]))
        self.apply("rewards.claim", ids="all", mode="claim")
        self.assertEqual(self.sf.user_rank_rewards.serialize(), [True, True, True])
        with self.assertRaises(ValueError):
            self.apply("rewards.claim", ids=[2], mode="claim")
        self.apply("rewards.claim", mode="fix_claimed")
        self.assertEqual(self.sf.user_rank_rewards.serialize(), [True, True, False])
        self.apply("rewards.claim", mode="unclaim", ids=[1])
        self.assertEqual(self.sf.user_rank_rewards.serialize(), [True, False, False])

    def test_medals_support_metadata_beyond_200_and_preserve_unknown(self):
        names = [[] for _ in range(213)]
        names[211] = ["Medal 211", "Requirement"]
        self.meta("get_medal_names", SimpleNamespace(medal_names=names))
        self.sf.medals.add_medal(999)
        self.apply("medals.set", ids="all", owned=True)
        self.assertEqual(self.sf.medals.medal_data_1, [999, 211])
        self.apply("medals.set", ids=[211], owned=False)
        self.assertEqual(self.sf.medals.medal_data_1, [999])
        self.assertEqual(self.sf.medals.medal_data_2, {999: 0})

    def test_mission_all_states_and_unselected_progress_preserved(self):
        self.sf.missions.clear_states = {7: 0, 8: 0, 999: 4}
        self.sf.missions.requirements = {7: 1, 999: 42}
        self.sf.missions.gamatoto_values = {7: 83}
        self.meta("get_mission_conditions", SimpleNamespace(conditions={7: SimpleNamespace(progress_count=25), 8: SimpleNamespace(progress_count=50)}))
        self.meta("get_mission_names", SimpleNamespace(names={7: "A", 8: "B"}))
        self.apply("missions.set", ids=[7], state="complete_reward")
        self.assertEqual(self.sf.missions.clear_states, {7: 2, 8: 0, 999: 4})
        self.assertEqual(self.sf.missions.requirements, {7: 25, 999: 42})
        self.apply("missions.set", ids=[8], state="complete_claim")
        self.assertEqual(self.sf.missions.clear_states[8], 4)
        self.assertEqual(self.sf.missions.requirements[8], 50)
        self.apply("missions.set", ids=[7], state="uncomplete")
        self.assertEqual(self.sf.missions.requirements[7], 0)
        self.assertEqual(self.sf.missions.gamatoto_values, {7: 83})

    def test_gold_pass_uses_original_model_and_preserves_playtime(self):
        expected = copy.deepcopy(self.sf)
        with patch("bcsfe.core.game.catbase.nyanko_club.time.time", return_value=1700000000):
            expected.officer_pass.gold_pass.get_gold_pass(123, 30, expected)
            self.apply("account.gold_pass", enabled=True, officer_id=123)
        self.assertEqual(self.sf.to_dict(), expected.to_dict())
        self.assertEqual(self.sf.officer_pass.play_time, 4321)
        self.apply("account.gold_pass", enabled=False)
        self.assertEqual(self.sf.officer_pass.gold_pass.officer_id, -1)
        self.assertEqual(self.sf.officer_pass.play_time, 4321)

    def test_enemy_ids_are_explicit_and_do_not_off_by_two(self):
        self.apply("enemy_guide.set", ids=[2], unlocked=True)
        self.assertEqual(self.sf.enemy_guide, [0, 1, 1, 0, 0])
        self.apply("enemy_guide.set", ids=[2], id_space="game", unlocked=True)
        self.assertEqual(self.sf.enemy_guide, [1, 1, 1, 0, 0])
        self.apply("enemy_guide.set", ids=[2], unlocked=False)
        self.assertEqual(self.sf.enemy_guide, [1, 1, 0, 0, 0])

    def test_enemy_valid_invalid_and_name_selectors(self):
        with patch.object(core, "EnemyDictionary", return_value=SimpleNamespace(get_valid_enemies=lambda: [0, 3])):
            self.apply("enemy_guide.set", group="valid", unlocked=True)
            self.assertEqual(self.sf.enemy_guide, [1, 1, 0, 1, 0])
            self.apply("enemy_guide.set", group="invalid", unlocked=False)
            self.assertEqual(self.sf.enemy_guide, [1, 0, 0, 1, 0])
        names = ["A", "Dog", "DOGE", "D", "E"]
        self.meta("get_enemy_names", SimpleNamespace(names=names, get_name=lambda index: names[index]))
        self.apply("enemy_guide.set", name="dog", unlocked=True)
        self.assertEqual(self.sf.enemy_guide, [1, 1, 1, 1, 0])

    def test_playtime_30fps_and_integer_serialization_limit(self):
        before = self.sf.officer_pass.gold_pass.serialize()
        self.apply("playtime.set", hours=1, minutes=1, seconds=1)
        self.assertEqual(self.sf.officer_pass.play_time, 3661 * 30)
        self.assertEqual(self.sf.officer_pass.gold_pass.serialize(), before)
        with self.assertRaises(ValueError):
            self.apply("playtime.set", hours=100000000)

    def test_gambling_can_reset_one_event_and_keep_other(self):
        self.sf.wildcat_slots.completed = {4: True}
        self.sf.wildcat_slots.values = {4: {9: 2}}
        self.sf.wildcat_slots.start_times = {4: 99}
        self.sf.cat_scratcher.completed = {8: True}
        self.apply("gambling.reset", events=["wildcat_slots"])
        self.assertEqual(self.sf.wildcat_slots.serialize(), {"completed": {}, "values": {}, "start_times": {}})
        self.assertEqual(self.sf.cat_scratcher.completed, {8: True})
        self.apply("gambling.reset")
        self.assertEqual(self.sf.cat_scratcher.completed, {})

    def test_slots_use_save_capacity_preserving_lineup(self):
        before = self.sf.lineups.serialize()
        self.sf.lineups.slot_names_length = 19
        self.apply("lineups.unlocked_slots", value=18)
        self.assertEqual(self.sf.lineups.unlocked_slots, 18)
        after = self.sf.lineups.serialize()
        before["unlocked_slots"] = 18
        before["slot_names_length"] = 19
        self.assertEqual(before, after)
        with self.assertRaises(ValueError):
            self.apply("lineups.unlocked_slots", value=20)

    def test_repairs_are_explicit_and_match_original_fields(self):
        self.apply("fixes.gamatoto")
        self.assertEqual(self.sf.gamatoto.skin, 2)
        self.assertEqual(self.sf.officer_pass.play_time, 4321)
        self.apply("fixes.time", timestamp=1700000000)
        self.assertEqual(self.sf.timestamp, 1700000000)
        self.assertEqual(self.sf.energy_penalty_timestamp, 1700000000)
        self.assertEqual(self.sf.date_3.timestamp(), 1700000000)
        self.apply("fixes.officer_pass")
        self.assertEqual(self.sf.officer_pass.play_time, 0)
        self.assertEqual(self.sf.officer_pass.gold_pass.officer_id, -1)
        self.apply("fixes.ototo")
        self.assertEqual(self.sf.ototo.cannons.cannons, {})
        expected = copy.deepcopy(self.sf)
        expected.unlock_equip_menu()
        self.apply("fixes.equip_menu")
        self.assertEqual(self.sf.to_dict(), expected.to_dict())

    def test_missing_metadata_is_error_not_success(self):
        self.meta("get_game_data_getter", SimpleNamespace(download=lambda *args: None))
        with self.assertRaisesRegex(ValueError, "metadata"):
            self.apply("ototo.engineers", value=3)
        self.meta("get_medal_names", SimpleNamespace(medal_names=None))
        with self.assertRaisesRegex(ValueError, "metadata"):
            self.apply("medals.set", ids="all", owned=True)
        self.meta("get_cat_shrine_levels", SimpleNamespace(boundaries=None))
        with self.assertRaisesRegex(ValueError, "metadata"):
            self.apply("shrine.set", level=1)

    def test_reject_bool_as_integer_and_unknown_fields(self):
        for args in ({"value": True}, {"value": -1}, {"value": "100"}, {"value": 1, "reset": True}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.apply("gamatoto.xp", **args)
        self.assertEqual(self.sf.gamatoto.xp, 0)

    def test_edited_save_roundtrip_preserves_intended_fields(self):
        self.apply("gamatoto.xp", value=12345)
        self.apply("playtime.set", frames=77777)
        self.apply("ototo.materials", values={"3": 345})
        raw = self.sf.to_data()
        restored = core.SaveFile(core.Data(raw.data), core.CountryCode.from_code("en"))
        self.assertEqual(restored.gamatoto.xp, 12345)
        self.assertEqual(restored.officer_pass.play_time, 77777)
        self.assertEqual(restored.officer_pass.gold_pass.officer_id, 55)
        self.assertEqual(restored.ototo.base_materials.serialize(), [11, 22, 33, 345])
        self.assertTrue(restored.verify_hash())


if __name__ == "__main__":
    unittest.main()
