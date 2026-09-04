from collections import Counter
from copy import deepcopy
import json
from pathlib import Path


def coverage():
    from editor_engine import ACTIONS
    from flask import current_app, has_app_context

    document = json.loads(Path(__file__).with_name('reference_features.json').read_text(encoding='utf-8'))
    items = deepcopy(document['features'])
    if len(items) != document['reference']['unique_features'] or len({item['id'] for item in items}) != len(items):
        raise RuntimeError('Source feature inventory is inconsistent.')
    tested = set(document['offline_binary_tested_actions'])
    routes = None
    if has_app_context():
        routes = {(method, rule.rule) for rule in current_app.url_map.iter_rules() for method in rule.methods}
    for item in items:
        missing_actions = [name for name in item['actions'] if name not in ACTIONS]
        missing_endpoints = ([endpoint for endpoint in item['endpoints']
                              if (endpoint['method'], endpoint['path']) not in routes]
                             if routes is not None else None)
        item['binding_check'] = {'missing_actions': missing_actions, 'missing_endpoints': missing_endpoints}
        item['verification']['offline_binary_action_samples'] = bool(item['actions']) and all(name in tested and name in ACTIONS for name in item['actions'])
        if missing_actions or missing_endpoints:
            item['implementation'] = 'binding_missing'
    categories = Counter(item['category'] for item in items)
    implementations = Counter(item['implementation'] for item in items)
    gameplay = [item for item in items if item['category'] == 'gameplay']
    return {
        'reference': document['reference'],
        'counts': {
            'source_features': len(items),
            'source_menu_entries': document['reference']['menu_entries_with_expanded_cat_submenus'],
            'registered_typed_actions': len(ACTIONS),
            'typed_actions_with_offline_binary_examples': len(set(ACTIONS) & tested),
            'gameplay_features': len(gameplay),
            'gameplay_features_with_registered_actions': sum(bool(item['actions']) and not item['binding_check']['missing_actions'] for item in gameplay),
            'features_with_offline_binary_action_examples': sum(item['verification']['offline_binary_action_samples'] for item in items),
            'features_requiring_live_game_verification': sum(item['verification']['live_game_server'] == 'not_verified' for item in items),
            'by_category': dict(categories),
            'by_implementation': dict(implementations),
        },
        'items': items,
        'verification_scope': document['verification_scope'],
        'limitations': document['global_limits'],
        'full_cli_behavioral_equivalence': False,
        'live_game_accounts_verified': False,
    }
