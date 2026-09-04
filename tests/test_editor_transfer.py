import copy
import unittest
from unittest.mock import patch
from jsonschema import Draft202012Validator
from editor_transfer import transfer_to_operations, SUPPORTED_FIELDS, CREDENTIAL_FIELDS, SIMPLE_FLAGS, MAP_FLAGS, _catalog


ORIGINAL_FIELDS = frozenset('''aku_chapters base_materials battle_items battle_items_endless behemoth_culling behemoth_stones castle_development castle_levels cat_evolutions cat_forms cat_levels cat_shrine cat_storage cat_talents catamin_stages catamins catamins_a catamins_b catamins_c catfood catfruit catseyes cc cc_str challenge_score claim_all_rewards claim_rewards clear_all_stages clear_chapters clear_enigma_stages clear_stages collab collab_gauntlets complete_missions confirmation_code confirmation_pin country country_code dojo_catclaw_championships dojo_score enable_safety enemy_guide event event_gatya_seed event_tickets filibuster_reclearing fix_gamatoto_crash fix_officer_pass_crash fix_ototo_crash fix_time_errors gamatoto_helper_ids gamatoto_helper_rarities gamatoto_helpers gamatoto_level gamatoto_xp gauntlets hundred_million_ticket inquiry_code itf_timed_scores labyrinth_medals leadership legend_quest legend_tickets max_all_talents max_castle_development max_cat_evolutions max_cat_levels max_chapter_treasures max_special_skills max_talent_orbs max_talents max_treasures medals missions normal_gatya_seed normal_tickets np orbs ototo_cat_cannon ototo_engineers ototo_materials outbreaks password_refresh_token platinum_shards platinum_tickets playtime rare_gatya_seed rare_tickets remove_cat_ids reset_gambling_events reset_golden_cat_cpus restart_pack scheme_items sol special_skills stage_treasures stones talent_orbs talents tc towers transfer_code treasure_chests true_form_all unban_account uncanny unlock_aku_realm unlock_cat_guide unlock_cat_ids unlock_cats unlock_equip_menu unlocked_slots upload_items xp zero_legends'''.split())


def field_cases():
    cases = {field: True for field in SIMPLE_FLAGS}
    cases.update({field: True for field in MAP_FLAGS})
    cases.update({field: 10 for field in '''catfood xp normal_tickets rare_tickets platinum_tickets legend_tickets platinum_shards np leadership hundred_million_ticket restart_pack gamatoto_level gamatoto_xp ototo_engineers unlocked_slots challenge_score dojo_score rare_gatya_seed normal_gatya_seed event_gatya_seed'''.split()})
    cases.update({field: 3 for field in '''catseyes catfruit catamins battle_items treasure_chests labyrinth_medals'''.split()})
    cases.update({field: 'fixture' for field in CREDENTIAL_FIELDS})
    cases.update({
        'inquiry_code': 'abc123', 'password_refresh_token': 'refresh_fixture',
        'enable_safety': False, 'unban_account': True, 'upload_items': True,
        'unlock_cat_ids': [0], 'remove_cat_ids': [0],
        'aku_chapters': True, 'outbreaks': True, 'medals': True, 'missions': True, 'enemy_guide': True, 'scheme_items': True,
        'base_materials': {'0': 5}, 'ototo_materials': {'0': 5}, 'battle_items_endless': 0,
        'behemoth_stones': {'item_ids': {'160': 5}}, 'stones': {'item_ids': {'160': 5}},
        'castle_development': {'0': 2}, 'castle_levels': {'0': [1, 2, 3]},
        'cat_evolutions': {'0': 3}, 'cat_forms': {'0': 2}, 'cat_levels': {'0': {'level': 30, 'plus': 0}},
        'cat_shrine': {'visible': False}, 'cat_storage': {'operation': 'remove', 'slots': [0]},
        'cat_talents': {'0': {'1': 0}}, 'talents': {'0': {'1': 0}},
        'catamins_a': 0, 'catamins_b': 0, 'catamins_c': 0,
        'claim_rewards': True, 'clear_all_stages': True,
        'clear_chapters': [0, {'chapter': 9, 'clears': 2}], 'clear_stages': [{'chapter': 0, 'stage': 1, 'clear_amount': 0}],
        'event_tickets': {'items': {'160': 5}}, 'gamatoto_helper_ids': [], 'gamatoto_helper_rarities': {'1': 0},
        'gamatoto_helpers': [0, 1], 'itf_timed_scores': 6000, 'max_cat_evolutions': True,
        'max_chapter_treasures': [0, {'chapter': 1, 'treasure': 0}], 'max_talents': True,
        'talent_orbs': {'1': 0}, 'orbs': {'1': 0}, 'ototo_cat_cannon': {'ids': [0], 'development': 2},
        'playtime': 0, 'special_skills': {'0': {'level': 1, 'plus': 0}},
        'stage_treasures': [{'chapter': 0, 'stage': 1, 'treasure': 0}],
    })
    return cases


class TransferContractTests(unittest.TestCase):
    def test_every_old_parser_field_has_a_schema_valid_translation(self):
        cases = field_cases()
        self.assertEqual(len(ORIGINAL_FIELDS), 115)
        self.assertFalse(ORIGINAL_FIELDS - SUPPORTED_FIELDS)
        self.assertFalse(ORIGINAL_FIELDS - cases.keys())
        catalog = _catalog()
        for field in sorted(ORIGINAL_FIELDS):
            with self.subTest(field=field):
                operations = transfer_to_operations({field: cases[field]})
                if field not in CREDENTIAL_FIELDS | {'unban_account', 'upload_items', 'enable_safety'}:
                    self.assertTrue(operations)
                for operation in operations:
                    Draft202012Validator(catalog[operation['action']]['schema']).validate(operation['args'])

    def test_zero_values_are_never_lost(self):
        operations = transfer_to_operations({'catfood': 0, 'xp': 0, 'catamins_b': 0, 'playtime': 0, 'rare_gatya_seed': 0})
        mapped = {operation['action']: operation['args'] for operation in operations}
        self.assertEqual(mapped['items.catfood']['value'], 0)
        self.assertEqual(mapped['items.xp']['value'], 0)
        self.assertEqual(mapped['items.catamins']['values'], {'1': 0})
        self.assertEqual(mapped['playtime.set']['frames'], 0)
        self.assertEqual(mapped['gatya.rare_seed']['value'], 0)

    def test_false_boolean_flags_do_not_invoke_edits(self):
        fields = {*SIMPLE_FLAGS, *MAP_FLAGS, 'unban_account', 'upload_items', 'outbreaks', 'aku_chapters', 'cat_shrine', 'cat_storage', 'ototo_cat_cannon', 'event_tickets', 'clear_all_stages'}
        self.assertEqual(transfer_to_operations({field: False for field in fields}), [])
        operations = transfer_to_operations({'outbreaks': {'chapters': [0], 'cleared': False}, 'cat_shrine': {'visible': False}})
        self.assertIs(operations[0]['args']['cleared'], False)
        self.assertIs(operations[1]['args']['visible'], False)

    def test_scalar_bools_floats_strings_and_overflows_are_rejected(self):
        for field in ('xp', 'catfood', 'inquiry_code', 'password_refresh_token', 'unlocked_slots', 'restart_pack'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                transfer_to_operations({field: True})
        for value in (True, 1.0, '5', -1, 2147483648, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                transfer_to_operations({'xp': value})
        for value in (0, 1, 'false', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                transfer_to_operations({'unlock_cats': value})

    def test_safety_is_off_by_default_and_only_added_where_supported(self):
        payload = {'xp': 500000000, 'catamins_b': 1, 'rare_gatya_seed': 4000000000, 'max_cat_levels': True}
        for safety in (False, True):
            operations = transfer_to_operations({**payload, 'enable_safety': safety})
            catalog = _catalog()
            for operation in operations:
                supported = 'respect_maxima' in catalog[operation['action']]['schema']['properties']
                self.assertEqual('respect_maxima' in operation['args'], supported)
                if supported:
                    self.assertIs(operation['args']['respect_maxima'], safety)
        self.assertIs(transfer_to_operations({'xp': 5})[0]['args']['respect_maxima'], False)
        seed = transfer_to_operations({'rare_gatya_seed': 4000000000})[0]
        self.assertEqual(seed['args']['value'], 4000000000)

    def test_catamin_aliases_and_catseye_names_preserve_unspecified_indexes(self):
        self.assertEqual(transfer_to_operations({'catamins_c': 7})[0]['args']['values'], {'2': 7})
        self.assertEqual(transfer_to_operations({'catseyes': {'rare': 7, 'uber': 0}})[0]['args']['values'], {'1': 7, '3': 0})
        with self.assertRaises(ValueError):
            transfer_to_operations({'catseyes': {'ex': 1, 'special': 2}})
        with self.assertRaises(ValueError):
            transfer_to_operations({'catseyes': {'superrare_typo': 2}})
        self.assertEqual(transfer_to_operations({'catfruit': [0, 9]})[0]['args']['values'], [0, 9])

    def test_aliases_do_not_override_conflicting_values(self):
        with self.assertRaises(ValueError):
            transfer_to_operations({'true_form_all': False, 'max_cat_evolutions': True})
        with self.assertRaises(ValueError):
            transfer_to_operations({'cat_forms': {'0': 1}, 'cat_evolutions': {'0': 3}})
        operations = transfer_to_operations({'claim_rewards': True, 'claim_all_rewards': True})
        self.assertEqual(len(operations), 1)

    def test_ambiguous_old_menu_flags_request_explicit_arguments(self):
        for field in ('cat_storage', 'cat_shrine', 'ototo_cat_cannon', 'event_tickets', 'behemoth_stones', 'gamatoto_helpers'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                transfer_to_operations({field: True})
        self.assertEqual(transfer_to_operations({'behemoth_stones': {'item_ids': {'166': 5}}})[0]['action'], 'items.evolve_by_id')

    def test_unknown_top_level_and_nested_fields_fail(self):
        for payload in ({'typo': 1}, {'xp': 1, 'typo': False}, {'cat_levels': [{'id': 0, 'levle': 30}]}, {'clear_chapters': [{'chapter': 0, 'stage': 5}]}, {'cat_shrine': {'unknown': True}}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                transfer_to_operations(payload)

    def test_levels_do_not_invent_missing_plus_level_or_unlock(self):
        operation = transfer_to_operations({'cat_levels': {'0': {'level': 30}}})[0]
        self.assertEqual(operation['args'], {'select': [{'kind': 'ids', 'ids': [0]}], 'base': 30})
        operation = transfer_to_operations({'cat_levels': [{'id': 0, 'plus_level': 0}]})[0]
        self.assertEqual(operation['args']['plus'], 0)
        self.assertNotIn('base', operation['args'])
        with self.assertRaises(ValueError):
            transfer_to_operations({'cat_levels': {'0': {'id': 1, 'level': 30}}})

    def test_true_form_means_third_form_not_fourth(self):
        operation = transfer_to_operations({'true_form_all': True})[0]
        self.assertEqual(operation['args']['operation'], 'true')
        operation = transfer_to_operations({'cat_forms': {'3': 2}})[0]
        self.assertEqual(operation['args']['operation'], 'current')
        self.assertEqual(operation['args']['form'], 2)

    def test_clear_all_stages_includes_every_stage_family(self):
        operations = transfer_to_operations({'clear_all_stages': True})
        names = {operation['action'] for operation in operations}
        expected = {'stages.story', 'stages.aku', 'stages.tutorial'} | {'stages.' + kind for kind in MAP_FLAGS.values()}
        self.assertEqual(names, expected)
        selected = transfer_to_operations({'clear_all_stages': {'scopes': ['story', 'aku']}})
        self.assertEqual({entry['action'] for entry in selected}, {'stages.story', 'stages.aku'})

    def test_treasure_edits_never_add_score_edits(self):
        operations = transfer_to_operations({'max_treasures': True, 'stage_treasures': [{'chapter': 0, 'stage': 1, 'treasure': 0}]})
        self.assertEqual([entry['action'] for entry in operations], ['stages.treasures', 'stages.treasures'])
        self.assertEqual(operations[-1]['args']['level'], 0)

    def test_aku_single_stage_keeps_map_and_crown(self):
        operation = transfer_to_operations({'clear_stages': [{'chapter': 9, 'stage': 2, 'map': 1, 'star': 0, 'clears': 0}]})[0]
        self.assertEqual(operation, {'action': 'stages.aku', 'args': {'clear_count': 0, 'stages': [2], 'map': 1, 'crown': 1}})

    def test_storage_operations_are_explicit(self):
        operation = transfer_to_operations({'cat_storage': {'operation': 'clear', 'confirm': True}})[0]
        self.assertEqual(operation, {'action': 'cats.storage.clear', 'args': {'confirm': True}})
        with self.assertRaises(ValueError):
            transfer_to_operations({'cat_storage': {'operation': 'clear'}})

    def test_translated_partial_vectors_change_only_requested_entries(self):
        from types import SimpleNamespace
        sf = SimpleNamespace(catamins=[10, 20, 30], catseyes=[1, 2, 3, 4, 5, 6])
        operations = transfer_to_operations({'catamins_b': 0, 'catseyes': {'rare': 0}})
        catalog = _catalog()
        for operation in operations:
            catalog[operation['action']]['apply'](sf, operation['args'])
        self.assertEqual(sf.catamins, [10, 0, 30])
        self.assertEqual(sf.catseyes, [1, 0, 3, 4, 5, 6])

    def test_transfer_treasure_raw_slot_is_preserved(self):
        from types import SimpleNamespace
        from bcsfe import core
        sf = SimpleNamespace(story=core.StoryChapters.init())
        operation = transfer_to_operations({'stage_treasures': [{'chapter': 0, 'stage': 0, 'treasure': 2}]})[0]
        _catalog()[operation['action']]['apply'](sf, operation['args'])
        self.assertEqual(sf.story.chapters[0].stages[0].treasure, 2)
        self.assertEqual(sf.story.chapters[0].stages[45].treasure, 0)

    def test_conversion_does_not_mutate_payload_or_call_transport(self):
        payload = {'cat_levels': {'0': {'level': 30, 'plus': 0}}, 'catseyes': {'rare': 0}, 'cat_storage': {'operation': 'remove', 'slots': [0]}}
        before = copy.deepcopy(payload)
        with patch('requests.sessions.Session.request', side_effect=AssertionError('Network request from converter')):
            transfer_to_operations(payload)
        self.assertEqual(payload, before)


if __name__ == '__main__':
    unittest.main()
