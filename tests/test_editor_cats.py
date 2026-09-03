"""Offline regression checks using real vendored BCSFE SaveFile round trips.

Only static game metadata is replaced with explicit, small fixtures. Account and
external network operations are forbidden throughout these tests.
"""
import copy
import unittest
from contextlib import ExitStack
from types import SimpleNamespace as NS
from unittest.mock import patch

from bcsfe import core
import editor_cats as editor
from bcsfe.core.game.catbase.cat import Talent, NyankoPictureBook, NyankoPictureBookCatData, UnitBuy, UnitLimit, UnitLimitCatData
from bcsfe.core.game.catbase.drop_chara import CharaDrop, Drop
from bcsfe.core.game.catbase.user_rank_rewards import RankGifts, RankGift, Reward


def selection(*ids):
    return [{"kind": "ids", "ids": list(ids)}]


def make_save():
    original = core.SaveFile(cc=core.CountryCode.from_code("kr"), gv=core.GameVersion(150500), load=False)
    original.cats = core.Cats([core.Cat(i, int(i == 0)) for i in range(4)], 5)
    original.cats.chara_new_flags = {i: 1 for i in range(4)}
    original.cats.cats[0].talents = [Talent(1, 2), Talent(2, 3)]
    original.cats.cats[1].talents = [Talent(1, 1)]
    original.cats.cats[0].upgrade.base = 19
    original.cats.cats[0].upgrade.plus = 7
    original.cats.cats[0].max_upgrade_level.base = 30
    original.cats.cats[0].catseyes_used = 4
    original.cats.storage_items[0] = core.StorageItem.from_cat(2)
    original.cats.cats[0].current_form = 1
    original.unit_drops = [0] * 4
    original.menu_unlocks = [0] * 5
    original.user_rank_rewards.rewards = [Reward(True)]
    original.officer_pass.play_time = 654321
    original.lineups.slots[0].slots[0].cat_id = 2
    original.lineups.slots[0].slots[1].cat_id = 1
    original.xp = 1245
    original.catfood = 987
    original.gamatoto.skin = 1
    original.talent_orbs.orbs = {0: core.TalentOrb(0, 7), 1: core.TalentOrb(1, 8)}
    return core.SaveFile(core.Data(original.to_data().data))


class CatEditorTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch("socket.socket.connect", side_effect=AssertionError("Network forbidden in editor tests")))
        self.stack.enter_context(patch.object(core.core_data, "config", NS(get_bool=lambda key: False), create=True))
        self.sf = make_save()
        self.before = self.sf.to_data().data
        self.book = NyankoPictureBook.__new__(NyankoPictureBook)
        self.book.cats = [NyankoPictureBookCatData(i, i != 2, False, i + 1, 0, 0, 0, 0, 0) for i in range(4)]
        self.buy = UnitBuy.__new__(UnitBuy)
        self.buy.unit_buy = [NS(id=i, rarity=i, unlock_source=2 if i == 0 else 0, game_version=140000+i*100, original_max_levels=(30, 0), max_upgrade_level_catseye=60, max_plus_upgrade_level=20+i, max_upgrade_level_no_catseye=30, unknown_22=10) for i in range(4)]
        self.limit = UnitLimit.__new__(UnitLimit)
        self.limit.unit_limit = [UnitLimitCatData(i, [1000]) for i in range(4)]
        self.gifts = RankGifts.__new__(RankGifts)
        self.gifts.rank_gift = [RankGift(0, 0, [(1000, 30)])]
        self.drops = CharaDrop.__new__(CharaDrop)
        self.drops.save_file = self.sf
        self.drops.drops = [Drop(i, i, i) for i in range(4)]
        self.stack.enter_context(patch.object(core.Cats, "read_nyanko_picture_book", return_value=self.book))
        self.stack.enter_context(patch.object(core.Cats, "read_unitbuy", return_value=self.buy))
        self.stack.enter_context(patch.object(core.Cats, "read_unitlimit", return_value=self.limit))
        self.stack.enter_context(patch.object(type(self.sf.user_rank_rewards), "read_rank_gifts", return_value=self.gifts))
        self.stack.enter_context(patch.object(core.core_data, "get_chara_drop", return_value=self.drops))
        self.stack.enter_context(patch.object(core.core_data, "get_game_data_getter", return_value=NS(does_save_version_match=lambda sf: True)))
        for cat in self.sf.cats.cats:
            cat.names = [f"Test Cat {cat.id}", f"Other Form {cat.id}"]
        self.talent_data = NS(get_cat_skill=lambda cid: NS(skills=[NS(ability_id=1, max_lv=10), NS(ability_id=2, max_lv=1), NS(ability_id=0, max_lv=0)]) if cid == 0 else NS(skills=[NS(ability_id=1, max_lv=5)]) if cid == 1 else None)
        self.stack.enter_context(patch.object(core.Cats, "read_talent_data", return_value=self.talent_data))
        self.orb_info = NS(orb_info_list=[NS(raw_orb_info=NS(orb_id=i)) for i in range(3)])
        self.orb_info.get_orbs_from_component_fuzzy = lambda grade, attribute, effect: [self.orb_info.orb_info_list[2]] if grade == "S" else []
        self.stack.enter_context(patch.object(core.game.catbase.talent_orbs.OrbInfoList, "create", return_value=self.orb_info))
        self.stack.enter_context(patch.object(core.core_data, "max_value_manager", NS(talent_orbs=999), create=True))
        self.stack.enter_context(patch.object(core.core_data, "get_gatya_item_buy", return_value=NS(get_names_by_category=lambda category: [(NS(id=i), str(i)) for i in range(3)])))

    def apply(self, name, args):
        editor.ACTIONS[name]["apply"](self.sf, args)

    def reload(self):
        return core.SaveFile(core.Data(self.sf.to_data().data))

    def assert_unrelated_preserved(self):
        before = core.SaveFile(core.Data(self.before))
        after = self.reload()
        for field in ("xp", "catfood", "inquiry_code", "password_refresh_token"):
            self.assertEqual(getattr(before, field), getattr(after, field), field)
        self.assertEqual(before.officer_pass.serialize(), after.officer_pass.serialize())
        self.assertEqual(before.gamatoto.serialize(), after.gamatoto.serialize())

    def test_unlock_updates_only_selected_cats_and_original_drop_flags(self):
        self.apply("cats.unlock", {"select": selection(1, 3)})
        after = self.reload()
        self.assertEqual([c.unlocked for c in after.cats.cats], [1, 1, 0, 1])
        self.assertEqual(after.unit_drops, [0, 1, 0, 1])
        self.assertEqual(after.menu_unlocks[2], 1)
        self.assertEqual(after.lineups.serialize(), core.SaveFile(core.Data(self.before)).lineups.serialize())
        self.assert_unrelated_preserved()

    def test_missing_drop_metadata_fails_before_unlock(self):
        self.drops.drops = None
        with self.assertRaisesRegex(ValueError, "metadata"):
            self.apply("cats.unlock", {"select": selection(1)})
        self.assertEqual(self.sf.to_data().data, self.before)

    def test_remove_without_reset_preserves_cat_progress(self):
        old = copy.deepcopy(self.sf.cats.cats[0].serialize())
        self.apply("cats.remove", {"select": selection(0)})
        old["unlocked"] = 0
        self.assertEqual(self.reload().cats.cats[0].serialize(), old)
        self.assert_unrelated_preserved()

    def test_remove_reset_matches_core_reset_and_removes_drop(self):
        self.sf.unit_drops[0] = 1
        self.sf.cats.chara_new_flags = {}
        expected = copy.deepcopy(self.sf.cats.cats[0])
        expected.reset()
        self.apply("cats.remove", {"select": selection(0), "reset": True})
        after = self.reload()
        self.assertEqual(after.cats.cats[0].serialize(), expected.serialize())
        self.assertEqual(after.unit_drops[0], 0)
        self.assertEqual(after.cats.chara_new_flags[0], 0)

    def test_all_original_selectors_and_combinations(self):
        scenarios = [("all", {}, [0, 1, 2, 3]), ("current", {}, [0]), ("not_unlocked", {}, [1, 2, 3]), ("name", {"name": "Form 2"}, [2]), ("rarity", {"rarities": [1, 3]}, [1, 3]), ("obtainable", {}, [0, 1, 3]), ("not_obtainable", {}, [2]), ("non_gacha", {}, [1, 2, 3]), ("game_version", {"versions": [140100]}, [1]), ("game_version", {"version_ranges": [{"min": 140100, "max": 140300}]}, [1, 2, 3])]
        for kind, args, expected in scenarios:
            with self.subTest(kind=kind, args=args):
                self.assertEqual([c.id for c in editor.select_cats(self.sf, [{"kind": kind, **args}])], expected)
        steps = [{"kind": "all"}, {"kind": "rarity", "rarities": [1, 3], "mode": "and"}, {"kind": "ids", "ids": [0], "mode": "or"}]
        self.assertEqual([c.id for c in editor.select_cats(self.sf, steps)], [0, 1, 3])

    def test_banner_selectors_resolve_original_gacha_metadata(self):
        banner = NS(gatya_data_set=[[]], get_cat_ids=lambda bid: [1, 3] if bid == 9 else None)
        with patch.object(type(self.sf.gatya), "read_gatya_data_set", return_value=banner), patch.object(core, "GatyaInfos", return_value=NS(get_all_names=lambda: {9: "Test Banner"})):
            for step in ({"kind": "banner", "ids": [9]}, {"kind": "banner_name", "name": "Test"}):
                self.assertEqual([c.id for c in editor.select_cats(self.sf, [step])], [1, 3])

    def test_forms_follow_metadata_instead_of_guessing_all_cats_have_three(self):
        self.apply("cats.forms", {"select": [{"kind": "all"}], "operation": "fourth", "set_current": True})
        after = self.reload()
        self.assertEqual([c.current_form for c in after.cats.cats], [0, 1, 2, 3])
        self.assertEqual([c.unlocked_forms for c in after.cats.cats], [0, 0, 3, 3])
        self.assertEqual([c.fourth_form for c in after.cats.cats], [0, 0, 0, 2])
        self.assertEqual([c.unlocked for c in after.cats.cats], [1, 0, 0, 0])
        self.assert_unrelated_preserved()

    def test_forms_omitted_current_stays_unchanged(self):
        before = [c.current_form for c in self.sf.cats.cats]
        self.apply("cats.forms", {"select": [{"kind": "all"}], "operation": "true"})
        self.assertEqual([c.current_form for c in self.reload().cats.cats], before)

    def test_force_fourth_and_removal_use_distinct_fields(self):
        self.apply("cats.forms", {"select": selection(0), "operation": "fourth", "force": True, "set_current": True})
        self.assertEqual(self.sf.cats.cats[0].fourth_form, 2)
        self.apply("cats.forms", {"select": selection(0), "operation": "remove_fourth"})
        self.assertEqual(self.sf.cats.cats[0].current_form, 2)
        self.assertEqual(self.sf.cats.cats[0].unlocked_forms, 3)
        self.apply("cats.forms", {"select": selection(0), "operation": "remove_true"})
        self.assertEqual(self.reload().cats.cats[0].current_form, 1)
        self.assertEqual(self.sf.cats.cats[0].unlocked_forms, 0)

    def test_current_form_cannot_select_unavailable_or_locked_form(self):
        for cid, form in [(0, 2), (2, 3), (3, 4)]:
            with self.subTest(cid=cid, form=form), self.assertRaises(ValueError):
                self.apply("cats.forms", {"select": selection(cid), "operation": "current", "form": form})
        self.assertEqual(self.sf.to_data().data, self.before)

    def test_levels_plus_only_preserves_base_catseyes_and_max_levels(self):
        expected = copy.deepcopy(self.sf.cats.cats[0].serialize())
        self.apply("cats.levels", {"select": selection(0), "plus": 12})
        expected["upgrade"]["plus"] = 12
        self.assertEqual(self.reload().cats.cats[0].serialize(), expected)
        self.assert_unrelated_preserved()

    def test_levels_use_real_powerup_algorithm(self):
        expected_sf = make_save()
        expected_cat = expected_sf.cats.cats[0]
        with patch.object(core.core_data.config, "get_bool", return_value=False):
            power = core.PowerUpHelper(expected_cat, expected_sf)
            power.reset_upgrade()
            power.upgrade_by(39)
        self.apply("cats.levels", {"select": selection(0), "base": 40})
        self.assertEqual(self.reload().cats.cats[0].serialize(), expected_cat.serialize())
        self.assert_unrelated_preserved()

    def test_levels_max_resolves_each_cats_own_limit(self):
        self.apply("cats.levels", {"select": selection(0, 1), "base": "max", "plus": "max"})
        after = self.reload()
        self.assertEqual([c.upgrade.base for c in after.cats.cats[:2]], [59, 59])
        self.assertEqual([c.upgrade.plus for c in after.cats.cats[:2]], [20, 21])

    def test_levels_reject_missing_metadata_and_overflow(self):
        for args in ({"base": 61}, {"plus": 99}, {"base": True}, {"plus": "12"}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.apply("cats.levels", {"select": selection(0), **args})
        self.buy.unit_buy = None
        with self.assertRaisesRegex(ValueError, "metadata"):
            self.apply("cats.levels", {"select": selection(0), "plus": 10})
        self.assertEqual(self.sf.to_data().data, self.before)

    def test_talent_partial_set_preserves_other_levels(self):
        self.apply("cats.talents", {"select": selection(0), "operation": "set", "levels": {"1": 9}})
        talents = self.reload().cats.cats[0].talents
        self.assertEqual([(t.id, t.level) for t in talents], [(1, 9), (2, 3)])
        self.assert_unrelated_preserved()

    def test_talent_max_and_remove(self):
        self.apply("cats.talents", {"select": [{"kind": "all"}], "operation": "max"})
        self.assertEqual([t.level for t in self.sf.cats.cats[0].talents], [10, 1])
        self.assertEqual(self.sf.cats.cats[1].talents[0].level, 5)
        self.apply("cats.talents", {"select": selection(0), "operation": "remove"})
        self.assertEqual([t.level for t in self.reload().cats.cats[0].talents], [0, 0])
        self.assertEqual(self.sf.cats.cats[1].talents[0].level, 5)

    def test_talent_metadata_version_mismatch_is_explicit(self):
        with patch.object(core.core_data, "get_game_data_getter", return_value=NS(does_save_version_match=lambda sf: False)):
            with self.assertRaisesRegex(ValueError, "version"):
                self.apply("cats.talents", {"select": selection(0), "operation": "max"})
            self.apply("cats.talents", {"select": selection(0), "operation": "max", "allow_metadata_version_mismatch": True})

    def test_guide_does_not_unlock_without_explicit_flag(self):
        self.apply("cats.guide", {"select": selection(1), "collected": True})
        after = self.reload()
        self.assertTrue(after.cats.cats[1].catguide_collected)
        self.assertEqual(after.cats.cats[1].unlocked, 0)
        self.assert_unrelated_preserved()

    def test_storage_add_preserves_items_capacity_and_counts(self):
        self.apply("cats.storage.add", {"items": [{"kind": "cat", "id": 1, "quantity": 2}, {"kind": "special_skill", "id": 2, "quantity": 1}]})
        items = self.reload().cats.storage_items
        self.assertEqual(len(items), 5)
        self.assertEqual([(i.item_type, i.item_id) for i in items], [(1, 2), (1, 1), (1, 1), (2, 2), (0, 0)])
        self.assert_unrelated_preserved()

    def test_storage_full_rejects_without_partial_add(self):
        with self.assertRaisesRegex(ValueError, "empty storage"):
            self.apply("cats.storage.add", {"items": [{"kind": "special_skill", "id": 0, "quantity": 5}]})
        self.assertEqual(self.sf.to_data().data, self.before)

    def test_storage_remove_uses_physical_slot_indices(self):
        self.sf.cats.storage_items[3] = core.StorageItem.from_cat(1)
        self.apply("cats.storage.remove", {"slots": [3]})
        items = self.reload().cats.storage_items
        self.assertEqual(items[0].item_type, 1)
        self.assertEqual(items[3].item_type, 0)
        self.apply("cats.storage.clear", {"confirm": True})
        self.assertEqual([i.item_type for i in self.reload().cats.storage_items], [0] * 5)

    def test_orb_partial_all_and_filters(self):
        self.apply("cats.orbs", {"values": {"1": 50}})
        self.assertEqual(self.sf.talent_orbs.orbs[0].value, 7)
        self.apply("cats.orbs", {"filters": [{"grade": "S"}], "count": 55})
        self.assertEqual(self.sf.talent_orbs.orbs[2].value, 55)
        self.apply("cats.orbs", {"all": True, "count": "max"})
        self.assertEqual([orb.value for orb in self.reload().talent_orbs.orbs.values()], [999] * 3)
        self.assert_unrelated_preserved()

    def test_orb_invalid_ids_and_values_cannot_report_success(self):
        for args in ({"values": {"99": 3}}, {"values": {"1": True}}, {"all": True, "count": 1000}, {"filters": [{"grade": "missing"}], "count": 5}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.apply("cats.orbs", args)
        self.assertEqual(self.sf.to_data().data, self.before)

    def test_lineup_partial_edit_preserves_every_unmentioned_slot(self):
        before = copy.deepcopy(self.sf.lineups.serialize())
        self.apply("cats.lineups", {"lineups": [{"id": 0, "slots": {"1": 3}, "name": "test"}], "selected": 2})
        before["slots"][0]["slots"][1] = 3
        before["slots"][0]["name"] = "test"
        before["selected_slot"] = 2
        self.assertEqual(self.reload().lineups.serialize(), before)
        self.assert_unrelated_preserved()

    def test_random_levels_use_original_upgrade_range_generator(self):
        with patch("bcsfe.core.game.catbase.upgrade.random.randint", side_effect=[34, 12]):
            self.apply("cats.levels", {"select": selection(0), "base": {"min": 30, "max": 40}, "plus": {"min": 10, "max": 15}})
        cat = self.reload().cats.cats[0]
        self.assertEqual((cat.upgrade.base, cat.upgrade.plus), (34, 12))

    def test_storage_add_accepts_the_original_cat_selectors(self):
        self.apply("cats.storage.add", {"select": [{"kind": "rarity", "rarities": [1, 3]}], "quantity": 2})
        self.assertEqual([i.item_id for i in self.reload().cats.storage_items], [2, 1, 1, 3, 3])

    def test_old_version_orbs_do_not_overflow_signed_byte(self):
        self.sf.game_version = core.GameVersion(110300)
        with self.assertRaisesRegex(ValueError, "maximum 127"):
            self.apply("cats.orbs", {"values": {"0": 128}})
        self.apply("cats.orbs", {"values": {"0": "max"}})
        self.assertEqual(self.sf.talent_orbs.orbs[0].value, 127)
        # Test the precise old-version orb write/read path without translating the entire save version.
        stream = core.Data()
        self.sf.talent_orbs.orbs[0].write(stream, self.sf.game_version)
        loaded = core.TalentOrb.read(core.Data(stream.data), self.sf.game_version)
        self.assertEqual(loaded.value, 127)

    def test_every_action_rejects_unknown_top_level_input(self):
        for name, action in editor.ACTIONS.items():
            with self.subTest(action=name), self.assertRaises(ValueError):
                action["apply"](self.sf, {"surprise": 1})
        self.assertEqual(self.sf.to_data().data, self.before)

    def test_bool_strings_unknown_selector_fields_and_cat_ids_fail(self):
        cases = [("cats.guide", {"select": selection(0), "collected": "false"}), ("cats.unlock", {"select": selection(True)}), ("cats.unlock", {"select": selection(999)}), ("cats.unlock", {"select": [{"kind": "all", "ids": [0]}]}), ("cats.forms", {"select": selection(0), "operation": "true", "force": 1}), ("cats.lineups", {"lineups": [{"id": 0, "slots": {"0": True}}]}), ("cats.storage.clear", {"confirm": 1})]
        for name, args in cases:
            with self.subTest(name=name, args=args), self.assertRaises(ValueError):
                self.apply(name, args)
        self.assertEqual(self.sf.to_data().data, self.before)


if __name__ == "__main__":
    unittest.main()
