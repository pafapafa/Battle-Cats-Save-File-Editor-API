# Legacy `/edit` migration reference

Legacy field names are converted by `editor_legacy.legacy_to_operations(payload)` into validated editing actions. Each of the 115 keys read by the old parser, including credentials and aliases, has either a conversion path or an explicit validation error. Accepted-but-ignored fields are not reported as successful edits.

Use Bearer authentication with the compatibility routes. `/edit` and `/info` include transfer reception, which uses the supplied transfer code. Preserve returned save and recovery data. This reference describes input conversion; it does not guarantee live game-server transfer acceptance or every in-game display/reward outcome.

## Common rules

- Integer fields require JSON integers. `100` and `0` are accepted; `"100"`, `1.0`, and `true` are not coerced to integers.
- Out-of-range quantities are rejected rather than reduced automatically. Gacha seeds support the unsigned 32-bit range `0..4294967295`.
- `enable_safety` defaults to `false`. When `true`, supported actions enforce BCSFE's recommended quantity limits. Metadata availability, valid IDs, and storage-type checks always apply.
- A `false` execution flag performs no action. To set a stored boolean to `false`, use the corresponding argument object.
- Omitted values are preserved. Zero is an explicit value, not a missing value.
- Unknown fields, conflicting aliases, and menu flags without required values are rejected. For example, `inquiry_code: true` does not supply an inquiry code.
- Transfer credentials are separate from edits: `transfer_code`/`tc`, `confirmation_code`/`confirmation_pin`/`cc`, and `country_code`/`country`/`cc_str`. Edited `inquiry_code` and `password_refresh_token` values must be strings.
- `unban_account` and `upload_items` require booleans. The converter validates these flags without contacting the game server; the HTTP layer handles the remote operations separately.

Numeric IDs in the examples illustrate request structure. Choose IDs that exist in the save and its corresponding game metadata.

## Quantities and partial edits

This request sets XP to zero, changes Rare Catseyes, and sets Catamin B to zero. Other quantities remain unchanged.

```json
{
  "xp": 0,
  "catseyes": {"rare": 7},
  "catamins_b": 0,
  "enable_safety": false
}
```

`catfood`, `xp`, ticket quantities, `platinum_shards`, `np`, `leadership`, `hundred_million_ticket`, and gacha seeds use integers.

`catamins`, `catseyes`, `catfruit`, `battle_items`, `treasure_chests`, and `labyrinth_medals` accept:

| Input | Meaning |
| --- | --- |
| Integer | Set every stored entry in that collection to the quantity |
| Array | Update the supplied indexes from the start; preserve trailing entries |
| Numeric-index object | Update only the specified indexes |

```json
{
  "catfruit": [1, 0, 7],
  "battle_items": {"0": 0, "2": 50},
  "catamins": {"a": 3, "c": 0}
}
```

Catseye aliases map to these indexes:

| Alias | Index |
| --- | ---: |
| `ex`, `special` | 0 |
| `rare` | 1 |
| `super_rare`, `super` | 2 |
| `uber_rare`, `uber` | 3 |
| `legend` | 4 |
| `dark` | 5 |

Specifying the same index through multiple aliases is an error, including `{"ex": 1, "special": 2}`.

`battle_items_endless` uses minutes. A number or `"infinity"` applies to all entries; a numeric-index object updates selected entries.

```json
{"battle_items_endless": {"0": 0, "2": "infinity"}}
```

`behemoth_stones`/`stones` and `event_tickets` use **game item IDs**, not assumed array slices:

```json
{
  "behemoth_stones": {"item_ids": {"160": 5}},
  "event_tickets": {"items": {"161": 3}}
}
```

An ID must belong to the relevant evolution-material or event-ticket category for that version. Ambiguous inputs such as `behemoth_stones: 999` or `event_tickets: true` are rejected.

## Cats and storage

```json
{
  "unlock_cat_ids": [0, 1],
  "cat_levels": {"0": {"level": 30}, "1": {"plus_level": 0}},
  "cat_forms": {"0": 3}
}
```

Base and plus levels in `cat_levels` are independent. An omitted plus level is preserved. Level editing does not automatically unlock a cat: use `unlock_cat_ids` or `"unlock": true` on the level entry when required.

| Legacy field | Contract |
| --- | --- |
| `unlock_cats: true` | Unlock cats identified as obtainable by the version's metadata |
| `max_cat_levels: true` | Maximize metadata-defined base and plus levels for unlocked, obtainable cats |
| `true_form_all`, `max_cat_evolutions` | Apply true forms to currently unlocked cats; these do not request fourth forms |
| `cat_forms`, `cat_evolutions` | `1`/`2` select a current form; `3`/`4` unlock that available evolution and select it |
| `remove_cat_ids` | Remove only the selected cats' unlocked status; use v2 `cats.remove` with `reset` for a full reset |
| `cat_talents`, `talents` | `{catID: {talentID: level}}`; preserve unspecified talents |
| `talent_orbs`, `orbs` | `{orbID: quantity}`, or the explicit argument object for v2 `cats.orbs` |

```json
{
  "cat_talents": {"0": {"1": 0}},
  "talent_orbs": {"1": 2},
  "special_skills": {"0": {"level": 20, "plus": 0}}
}
```

`cat_storage: true` no longer clears storage and fills it with 64 basic cats. Supply an explicit operation:

```json
{"cat_storage": {"operation": "add", "items": [{"kind": "cat", "id": 0, "quantity": 2}]}}
```

```json
{"cat_storage": {"operation": "remove", "slots": [0, 3]}}
```

```json
{"cat_storage": {"operation": "clear", "confirm": true}}
```

## Stages and treasures

Story chapter IDs `0..2` are Empire of Cats, `3..5` are Into the Future, and `6..8` are Cats of the Cosmos. Chapter `9` in legacy `clear_chapters`/`clear_stages` refers to the Aku Realm.

Map and stage IDs are zero-based. The new `crowns`/`crown` arguments are one-based. Only the legacy Aku `clear_stages[].star` retains its zero-based convention.

```json
{
  "clear_chapters": [0, {"chapter": 1, "clear_amount": 3}],
  "clear_stages": [{"chapter": 3, "stage": 0, "clears": 0}],
  "stage_treasures": [{"chapter": 0, "stage": 0, "treasure": 3}]
}
```

**Legacy `stage_treasures[].stage` remains a storage-slot index.** The v2 `stages.treasures` action uses BCSFE's geographical menu order. The compatibility converter maps the old storage slot to the new order so the same treasure is edited.

`max_treasures` and `max_chapter_treasures` edit treasures only. Use `itf_timed_scores` to change Into the Future scores:

```json
{"max_treasures": true, "itf_timed_scores": {"chapters": [3], "stages": [0], "score": 6000}}
```

For the following legacy map fields, `true` clears every valid map and crown in the category. An argument object selects a smaller scope.

| Legacy field | v2 action |
| --- | --- |
| `sol`, `event`, `collab` | `stages.sol`, `stages.event`, `stages.collab` |
| `gauntlets`, `collab_gauntlets` | The corresponding `stages.*` action |
| `uncanny` | `stages.uncanny` |
| `catamin_stages` | `stages.catamin` |
| `behemoth_culling` | `stages.behemoth` |
| `legend_quest`, `towers`, `zero_legends` | The corresponding `stages.*` action |
| `dojo_catclaw_championships` | `stages.dojo_catclaw` |
| `clear_enigma_stages` | `stages.enigma_clears` |

```json
{"sol": {"maps": [0], "crowns": [1], "stages": [0], "clear_count": 0}}
```

`progress` clears a prefix of stages in the selected map/crown and resets the remaining valid stages. Other crowns are preserved unless `reset_following_crowns: true` is supplied.

```json
{"gauntlets": {"maps": [0], "crowns": [1], "progress": 2, "reset_following_crowns": true}}
```

For individual `clear_count` edits, use `reset_after: true` to reset stages after the last selected stage. `ensure_cleared: true` preserves existing nonzero counts and applies the supplied count only to uncleared stages.

```json
{"event": {"maps": [0], "crowns": [1], "stages": [1], "clear_count": 1, "reset_after": true}}
```

`aku_chapters: true` clears all stored Aku maps/crowns. An object can specify the selection within the existing model:

```json
{"aku_chapters": {"map": "all", "crown": "all", "progress": "all", "clear_count": 1}}
```

`clear_all_stages: true` requests story, Aku, the 13 map categories above, and the tutorial. A partial category edit is not reported as completion of the whole request. To select categories explicitly:

```json
{"clear_all_stages": {"scopes": ["story", "aku", "sol"]}}
```

Allowed scopes: `story`, `aku`, `sol`, `event`, `collab`, `gauntlets`, `collab_gauntlets`, `uncanny`, `catamin`, `behemoth`, `legend_quest`, `towers`, `zero_legends`, `dojo_catclaw`, `enigma_clears`, `tutorial`.

Map IDs, crown counts, and stage availability are checked against the BCSFE model and game metadata. Missing maps are not fabricated inside empty save structures. Missing metadata or required save structures produces an error.

## Other edits

```json
{
  "cat_shrine": {"visible": false},
  "unlocked_slots": 3,
  "restart_pack": 0,
  "gamatoto_helper_rarities": {"1": 0},
  "base_materials": {"0": 5},
  "castle_development": {"0": 2},
  "castle_levels": {"0": [1, 2, 3]},
  "playtime": 0
}
```

- `cat_shrine` accepts `level`, `xp`, and `visible` in an object. A standalone `true` does not select a level.
- `unlocked_slots` and `restart_pack` require integers; `true` is not treated as `1`.
- `gamatoto_helper_ids` accepts an ID array; `[]` removes all helpers. `gamatoto_helper_rarities` replaces only the specified rarities.
- `base_materials`/`ototo_materials` accept partial numeric-index objects. Arrays must match the full stored collection length.
- `max_castle_development` maximizes cannons according to metadata. It does not change engineers/materials or delete existing cannons.
- `ototo_cat_cannon` takes the v2 `ototo.cannons` argument object, not a standalone `true`.
- An integer `playtime` is the stored frame count. `{hours, minutes, seconds}` and `{frames}` objects are also supported.
- `outbreaks`, `medals`, `missions`, `enemy_guide`, and `scheme_items` accept execution flags or the corresponding action arguments. For example: `{"outbreaks": {"chapters": [0], "cleared": false}}`.

## Corrected behavior

| Previous behavior | Current contract |
| --- | --- |
| Coerced numeric strings/booleans and reduced out-of-range inputs | Validate exact types and ranges; return an error |
| XP edits also changed pass, lineup, tutorial, and time fields | Perform only the requested editing actions |
| Partial Catseye edits reset unspecified entries | Preserve unspecified indexes |
| True-form requests called fourth-form code | Convert to the true-form action |
| Treasure maximization also changed timed scores | Edit treasures only |
| Storage requests replaced existing items with 64 basic cats | Require `add`, `remove`, or `clear` with explicit targets |
| `clear_all_stages` handled only some categories | Request all categories or an explicit scope selection |
| Unsupported menu booleans appeared successful | Require concrete values/objects or return an error |
| Gacha seeds lost the highest unsigned bit | Preserve the full unsigned 32-bit range |
| Stage resets used incorrect boundaries or nonserialized fields | Update the correct boundary and serialized fields |

Verification covers the fixed legacy-key inventory, generated-action schema validity, invalid-input rejection, partial-resource and treasure-slot preservation, and real BCSFE stage-model serialization. Live account issuance and game-server uploads are separate verification steps.
