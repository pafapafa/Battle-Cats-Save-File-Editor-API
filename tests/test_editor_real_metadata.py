"""Opt-in public BCSFE metadata integration, with no metadata/model mocks.

Run: BCSFE_TEST_REAL_METADATA=1 python -m unittest discover -s tests -p test_editor_real_metadata.py
Uses public game tables plus generated save bytes, never account-transfer servers.
"""
import os
import unittest

from bcsfe_runtime import core, scoped_runtime
from editor_engine import apply_operations, serialize_checked
from editor_metadata import prepare_metadata
from bcsfe.core.game.catbase.cat import Talent
from bcsfe.core.game.catbase.user_rank_rewards import Reward
from bcsfe.core.game.gamoto.ototo import Cannon, Cannons, CastleRecipeUnlock
from bcsfe.core.game.map.event import EventChapterGroup, EventSubChapter, EventSubChapterStars
import editor_stages


@unittest.skipUnless(os.environ.get("BCSFE_TEST_REAL_METADATA") == "1", "Set BCSFE_TEST_REAL_METADATA=1 for public metadata integration")
class RealMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with scoped_runtime():
            status = prepare_metadata("kr", 150500)
            if not status["exact_match"]:
                raise AssertionError("The reference integration requires exact kr 15.5.0 tables")
            sf = core.SaveFile(cc=core.CountryCode.from_code("kr"), gv=core.GameVersion(150500), load=False)
            buy = core.UnitBuy(sf)
            sf.cats = core.Cats([core.Cat(i, int(i != 1)) for i in range(len(buy.unit_buy))], 8)
            talent_data = sf.cats.read_talent_data(sf)
            for cat in sf.cats.cats:
                skill = talent_data.get_cat_skill(cat.id)
                if skill is not None:
                    cat.talents = [Talent(s.ability_id, 0) for s in skill.skills if s.ability_id > 0]
            drops = core.core_data.get_chara_drop(sf).drops
            sf.unit_drops = [0] * (max(d.save_id for d in drops) + 1)
            sf.menu_unlocks = [0, 0, 0, 0]
            gifts = core.core_data.get_rank_gifts(sf).rank_gift
            sf.user_rank_rewards.rewards = [Reward(False) for gift in gifts]
            sf.xp, sf.catfood = 123, 456
            sf.officer_pass.play_time = 987654
            items = core.core_data.get_gatya_item_buy(sf)
            categories = {core.GatyaItemCategory.EVOLVE_ITEMS: "catfruit", core.GatyaItemCategory.EVENT_TICKETS: "event_capsules", core.GatyaItemCategory.LUCKY_TICKETS_1: "lucky_tickets", core.GatyaItemCategory.LUCKY_TICKETS_2: "event_capsules_2"}
            for category, field in categories.items():
                rows = items.get_by_category(category)
                setattr(sf, field, [0] * (max((row.index for row in rows), default=-1) + 1))
            mission_ids = set(core.core_data.get_mission_names(sf).names) & set(core.core_data.get_mission_conditions(sf).conditions)
            sf.missions.clear_states = {mid: 0 for mid in mission_ids}
            sf.missions.requirements = {mid: 0 for mid in mission_ids}
            recipe = CastleRecipeUnlock(sf)
            parts = {}
            for row in recipe.level_part_recipe_unlocks:
                parts[row.cannon_id] = max(parts.get(row.cannon_id, -1), row.part_id)
            sf.ototo.cannons = Cannons({cid: Cannon(0, [0] * (last + 1)) for cid, last in parts.items()}, [[0, 0, 0]])
            names = core.MapNames(sf, "N", base_index=0, output=False)
            options = core.MapOption.from_save(sf)
            crowns = options.get_map(0).crown_count
            stages = len(names.stage_names[0])
            sf.event_stages = core.EventChapters([EventChapterGroup([EventSubChapterStars([EventSubChapter.init(stages) for _ in range(crowns)])]) for _ in range(3)])
            cls.raw = sf.to_data().data
            cls.evolve_id = items.get_by_category(core.GatyaItemCategory.EVOLVE_ITEMS)[0].id
            cls.evolve_index = items.get(cls.evolve_id).index
            cls.event_id = items.get_by_category(core.GatyaItemCategory.EVENT_TICKETS)[0].id
            cls.event_index = items.get(cls.event_id).index
            cls.mission_id = min(mission_ids)
            cls.helper_id = core.core_data.get_gamatoto_members_name(sf).members[0].member_id
            cls.reward_id = next(g.index for g in gifts if g.threshold <= sf.calculate_user_rank())
            cls.cannon_id = next(cid for cid in parts if cid != 0)
            cls.talent_cat_id = next(cat.id for cat in sf.cats.cats if cat.talents)
            cls.talent_cat_max_plus = buy.get_unit_buy(cls.talent_cat_id).max_plus_upgrade_level
            cls.mission_progress = core.core_data.get_mission_conditions(sf).conditions[cls.mission_id].progress_count
            cls.orb_id = core.game.catbase.talent_orbs.OrbInfoList.create(sf).orb_info_list[0].raw_orb_info.orb_id
        serialize_checked(core.SaveFile(core.Data(cls.raw)))

    def setUp(self):
        self.sf = core.SaveFile(core.Data(self.raw))

    def apply(self, *operations):
        after, raw, delta = apply_operations(self.sf, list(operations))
        self.assertTrue(after.verify_hash())
        self.assertEqual(after.to_data().data, raw)
        self.assertEqual(self.sf.to_data().data, self.raw, "The input save must remain unchanged")
        self.assertEqual(after.officer_pass.serialize(), self.sf.officer_pass.serialize())
        self.assertEqual(after.catfood, self.sf.catfood)
        return after, delta

    def test_all_metadata_helper_categories_load_actual_tables(self):
        fields = {"get_gatya_item_names": "names", "get_gatya_item_buy": "buy", "get_chara_drop": "drops", "get_gamatoto_levels": "levels", "get_gamatoto_members_name": "members", "get_ability_data": "ability_data", "get_enemy_names": "names", "get_rank_gift_descriptions": "rank_gift_descriptions", "get_rank_gifts": "rank_gift", "get_treasure_text": "treasure_text", "get_cat_shrine_levels": "boundaries", "get_medal_names": "medal_names", "get_mission_names": "names", "get_mission_conditions": "conditions"}
        with scoped_runtime():
            for method, field in fields.items():
                with self.subTest(category=method):
                    self.assertTrue(getattr(getattr(core.core_data, method)(self.sf), field))
            self.assertTrue(self.sf.cats.read_unitbuy(self.sf).unit_buy)
            self.assertTrue(self.sf.cats.read_unitlimit(self.sf).unit_limit)
            self.assertTrue(self.sf.cats.read_nyanko_picture_book(self.sf).cats)
            self.assertTrue(self.sf.cats.read_talent_data(self.sf).cats.skills)
            self.assertTrue(CastleRecipeUnlock(self.sf).level_part_recipe_unlocks)

    def test_all_stage_metadata_families_load_actual_tables(self):
        with scoped_runtime():
            for kind, (_, code, base, _) in editor_stages.MAPS.items():
                with self.subTest(kind=kind):
                    names, options = editor_stages._metadata(self.sf, code, base, kind == "dojo_catclaw")
                    self.assertTrue(names.map_names)
                    self.assertTrue(names.stage_names)
                    self.assertIsNotNone(options)

    def test_cats_unlock_levels_forms_talents_and_orbs_persist_using_actual_tables(self):
        cid = self.talent_cat_id
        select = [{"kind": "ids", "ids": [cid]}]
        operations = [{"action": "cats.unlock", "args": {"select": [{"kind": "ids", "ids": [1]}]}},
                      {"action": "cats.levels", "args": {"select": select, "base": "max", "plus": "max"}},
                      {"action": "cats.forms", "args": {"select": select, "operation": "true", "set_current": True}},
                      {"action": "cats.talents", "args": {"select": select, "operation": "max"}},
                      {"action": "cats.orbs", "args": {"values": {str(self.orb_id): 3}}}]
        after, delta = self.apply(*operations)
        self.assertEqual(after.cats.cats[1].unlocked, 1)
        self.assertEqual(after.cats.cats[cid].upgrade.plus, self.talent_cat_max_plus)
        self.assertEqual(after.cats.cats[cid].current_form, 2)
        self.assertTrue(all(t.level > 0 for t in after.cats.cats[cid].talents))
        self.assertEqual(after.talent_orbs.orbs[self.orb_id].value, 3)
        self.assertEqual(after.lineups.serialize(), self.sf.lineups.serialize())
        self.assertTrue(delta)

    def test_game_item_ids_gamatoto_cannons_rewards_and_missions_persist(self):
        after, delta = self.apply(
            {"action": "items.evolve_by_id", "args": {"items": {str(self.evolve_id): 7}}},
            {"action": "items.event_tickets", "args": {"items": {str(self.event_id): 8}}},
            {"action": "gamatoto.level", "args": {"value": 5}},
            {"action": "gamatoto.helpers", "args": {"ids": [self.helper_id]}},
            {"action": "ototo.cannons", "args": {"ids": [self.cannon_id], "max": True}},
            {"action": "rewards.claim", "args": {"ids": [self.reward_id], "mode": "claim"}},
            {"action": "missions.set", "args": {"ids": [self.mission_id], "state": "complete_reward"}})
        self.assertEqual(after.catfruit[self.evolve_index], 7)
        self.assertEqual(after.event_capsules[self.event_index], 8)
        self.assertGreater(after.gamatoto.xp, 0)
        self.assertEqual(after.gamatoto.helpers.helpers[0].id, self.helper_id)
        self.assertEqual(after.ototo.cannons.cannons[self.cannon_id].development, 3)
        self.assertTrue(after.user_rank_rewards.rewards[self.reward_id].claimed)
        self.assertEqual(after.missions.clear_states[self.mission_id], 2)
        self.assertEqual(after.missions.requirements[self.mission_id], self.mission_progress)
        self.assertTrue(delta)

    def test_story_and_legend_stages_persist_without_changing_treasures(self):
        after, delta = self.apply(
            {"action": "stages.story", "args": {"chapters": [0], "stages": [0], "clear_count": 2}},
            {"action": "stages.sol", "args": {"maps": [0], "crowns": [1], "stages": [0], "clear_count": 3}})
        self.assertEqual(after.story.get_real_chapters()[0].stages[0].clear_times, 2)
        self.assertEqual(after.event_stages.chapters[0].chapters[0].chapters[0].stages[0].clear_amount, 3)
        self.assertEqual([s.treasure for s in after.story.get_real_chapters()[0].stages], [s.treasure for s in self.sf.story.get_real_chapters()[0].stages])
        self.assertTrue(delta)


if __name__ == "__main__":
    unittest.main()
