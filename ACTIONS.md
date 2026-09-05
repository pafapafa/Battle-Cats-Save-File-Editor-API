# Save-edit action reference

This reference covers all 89 registered actions accepted by `POST /v2/save/edit`. Each entry explains its behavior, argument shapes, runtime conditions, and an example operation.

API base URL: `https://battle-cats-save-file-editor-api.vercel.app`. Use the [HTTP API reference](https://battle-cats-save-file-editor-api.vercel.app/docs) for endpoint authentication and response formats, and the [feature catalog](https://battle-cats-save-file-editor-api.vercel.app/v2/features) for current machine-readable schemas.

## Submit an operation

Put one or more operation objects from this reference in the `operations` array. No API key is required. Supply the original file as Base64:

```json
{
  "country_code": "kr",
  "save_base64": "BASE64_OF_THE_ORIGINAL_SAVE",
  "operations": [
    {
      "action": "items.xp",
      "args": {
        "value": 1000
      }
    }
  ]
}
```

The API applies a batch of 1..100 operations to a copy, serializes and reparses it, and returns the edited `save_base64`, original `backup_base64`, and persisted changes. Preserve the original. The edit response does not upload the result or activate it in the game.

Every example below has been checked against the registered StrictValidator schema. Examples illustrate the request contract; IDs, capacities, metadata versions, and the existing save state still determine whether a particular edit can run. They are not evidence of live account-server or in-game acceptance.

## Shared argument rules

- Unknown fields are rejected. Integer fields require JSON integers: strings, booleans, and floating-point values are not coerced.
- Required in an argument table means schema-required. Conditional requirements and incompatible combinations are stated in the notes; runtime validation enforces them too.
- Numeric object keys are strings in JSON, such as `{"0": 10}`. IDs and array positions are zero-based unless an entry specifies displayed levels, crowns, or another ID space.
- Where offered, `respect_maxima` defaults to `true`. Recommended limits may be lower than the schema's storage range. `false` does not remove binary bounds, valid-ID checks, or save-version restrictions.
- Omitted edit fields are generally preserved, with the stated exceptions for complete-duration inputs, resets, progression updates, and explicit bulk options. An omitted selector may mean `all` when documented.
- Metadata-dependent actions use tables selected for the save's region/version. Missing or incompatible metadata is an error. Use the metadata endpoints in [DOCS.md](DOCS.md) to inspect available versions and the resolved version before a bulk edit.
- The API's binary validation rejects output that cannot preserve the requested changes. A valid JSON shape alone does not guarantee that a save format supports an action.

## Category index

- [Resources and inventory](#resources) (26 actions)
- [Gacha seeds](#gacha) (3 actions)
- [Cats, forms, talents, and orbs](#cats) (7 actions)
- [Cat storage](#storage) (3 actions)
- [Battle lineups](#lineups) (2 actions)
- [Base special skills](#skills) (1 action)
- [Story, treasures, and outbreaks](#story) (6 actions)
- [Event and challenge maps](#maps) (18 actions)
- [Gamatoto expeditions](#gamatoto) (3 actions)
- [Ototo construction](#ototo) (3 actions)
- [Rewards and collection progress](#progression) (6 actions)
- [Account fields and save format](#account) (6 actions)
- [Explicit save repairs](#fixes) (5 actions)

## Cat selection

The `select` array is evaluated in order. Each step requires `kind`; `mode` is optional and defaults to `replace`. The first step must use `replace`. Later steps may replace the current result, intersect it with `and`, or add matches with `or`. An empty final selection is rejected.

| kind | Additional fields | Meaning and metadata |
| --- | --- | --- |
| `all` | None | Every cat record present in the save |
| `current` | None | Currently unlocked cats |
| `not_unlocked` | None | Currently locked cats |
| `ids` | `ids`: nonempty integer array | Exact zero-based cat IDs present in the save |
| `name` | `name`: string | Case-insensitive substring of any form name; requires cat-name tables |
| `rarity` | `rarities`: nonempty integer array | UnitBuy rarity values |
| `obtainable` / `not_obtainable` | None | Picture-book obtainability metadata |
| `non_gacha` | None | UnitBuy unlock_source is not 2 |
| `banner` | `ids`: nonempty integer array | Banner IDs, resolved through the gacha dataset |
| `banner_name` | `name`: string | Case-insensitive banner-name substring, then dataset cat IDs |
| `game_version` | `versions` and/or `version_ranges` | UnitBuy introduction-version values; ranges are inclusive `{min,max}` objects |

Each step accepts only the fields applicable to its kind, plus `mode`. IDs and rarity values are integers in 0..2147483647; version values are 1..2147483647. Selector arrays and nested ID/range arrays contain 1..10000 entries. Names contain 1..256 characters. Every range requires min <= max. Version selectors match the table's introduction-version encoding; they do not change the save version.

```json
{
  "action": "cats.levels",
  "args": {
    "select": [
      {
        "kind": "current"
      },
      {
        "kind": "rarity",
        "rarities": [
          0
        ],
        "mode": "and"
      }
    ],
    "base": 20
  }
}
```

<a id="resources"></a>

## Resources and inventory

Set resource balances, item quantities, timed items, and scheme rewards.

### `items.catfood`

Set the cat food balance.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 0..2147483647 | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.catfood",
  "args": {
    "value": 10
  }
}
```

- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.
- Changing the value records the delta in the save's managed-item metadata. This action does not contact account servers.
- value replaces the existing count; it is not an amount to add.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.xp`

Set the XP balance.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 0..2147483647 | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.xp",
  "args": {
    "value": 1000
  }
}
```

- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.
- value replaces the existing count; it is not an amount to add.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.normal_tickets`

Set the normal ticket balance.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 0..2147483647 | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.normal_tickets",
  "args": {
    "value": 10
  }
}
```

- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.
- value replaces the existing count; it is not an amount to add.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.rare_tickets`

Set the rare ticket balance.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 0..2147483647 | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.rare_tickets",
  "args": {
    "value": 10
  }
}
```

- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.
- Changing the value records the delta in the save's managed-item metadata. This action does not contact account servers.
- value replaces the existing count; it is not an amount to add.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.platinum_tickets`

Set the platinum ticket balance.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 0..2147483647 | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.platinum_tickets",
  "args": {
    "value": 10
  }
}
```

- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.
- Changing the value records the delta in the save's managed-item metadata. This action does not contact account servers.
- value replaces the existing count; it is not an amount to add.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.legend_tickets`

Set the legend ticket balance.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 0..2147483647 | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.legend_tickets",
  "args": {
    "value": 10
  }
}
```

- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.
- Changing the value records the delta in the save's managed-item metadata. This action does not contact account servers.
- value replaces the existing count; it is not an amount to add.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.platinum_shards`

Set the platinum shard count.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 0..2147483647 | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.platinum_shards",
  "args": {
    "value": 0
  }
}
```

- With respect_maxima=true, the limit is max(0, (configured platinum-ticket maximum - current platinum tickets) * 10 + 9). It checks remaining ticket capacity but does not convert shards into tickets. false bypasses this capacity check.
- value replaces the existing count; it is not an amount to add.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.np`

Set the NP balance.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 0..2147483647 | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.np",
  "args": {
    "value": 10
  }
}
```

- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.
- value replaces the existing count; it is not an amount to add.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.leadership`

Set the Leadership count.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 0..32767 | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.leadership",
  "args": {
    "value": 10
  }
}
```

- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.
- The stored value is limited to 0..32767.
- value replaces the existing count; it is not an amount to add.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.hundred_million_ticket`

Set the 100 Million Ticket count.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 0..2147483647 | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.hundred_million_ticket",
  "args": {
    "value": 10
  }
}
```

- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.
- value replaces the existing count; it is not an amount to add.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.restart_pack`

Set the restart pack count.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 0..127 | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.restart_pack",
  "args": {
    "value": 10
  }
}
```

- The stored value is limited to 0..127. respect_maxima is accepted but does not change this action's limit.
- value replaces the existing count; it is not an amount to add.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.golden_cpu_count`

Set the Gold CPU count.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 0..127 | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.golden_cpu_count",
  "args": {
    "value": 10
  }
}
```

- The stored value is limited to 0..127. respect_maxima is accepted but does not change this action's limit.
- value replaces the existing count; it is not an amount to add.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.catamins`

Set selected Catamin quantities.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `values` | Yes | integer 0..2147483647 OR array of (integer 0..2147483647); 1..unbounded entries OR object with numeric-string keys and values (integer 0..2147483647); at least 1 field(s) | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.catamins",
  "args": {
    "values": {
      "0": 10
    }
  }
}
```

- values may be a single quantity for every stored entry, an array replacing entries from index 0, or an object such as {"0": 10} selecting individual zero-based storage indexes. Unspecified entries are preserved.
- Array length and indexes must fit the existing save; this action does not extend the array. Object keys must be canonical decimal indexes, with no leading zeros.
- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.catseyes`

Set selected Catseye quantities.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `values` | Yes | integer 0..2147483647 OR array of (integer 0..2147483647); 1..unbounded entries OR object with numeric-string keys and values (integer 0..2147483647); at least 1 field(s) | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.catseyes",
  "args": {
    "values": {
      "0": 10
    }
  }
}
```

- values may be a single quantity for every stored entry, an array replacing entries from index 0, or an object such as {"0": 10} selecting individual zero-based storage indexes. Unspecified entries are preserved.
- Array length and indexes must fit the existing save; this action does not extend the array. Object keys must be canonical decimal indexes, with no leading zeros.
- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.catfruit`

Set selected evolution-material quantities in the catfruit array.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `values` | Yes | integer 0..2147483647 OR array of (integer 0..2147483647); 1..unbounded entries OR object with numeric-string keys and values (integer 0..2147483647); at least 1 field(s) | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.catfruit",
  "args": {
    "values": {
      "0": 10
    }
  }
}
```

- values may be a single quantity for every stored entry, an array replacing entries from index 0, or an object such as {"0": 10} selecting individual zero-based storage indexes. Unspecified entries are preserved.
- Array length and indexes must fit the existing save; this action does not extend the array. Object keys must be canonical decimal indexes, with no leading zeros.
- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.
- Before game version 11.4.0, the configured old catfruit limit applies to each requested quantity and to the total after the edit. Version 11.4.0 and later uses the newer per-entry cap.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.labyrinth_medals`

Set selected labyrinth medal quantities.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `values` | Yes | integer 0..2147483647 OR array of (integer 0..2147483647); 1..unbounded entries OR object with numeric-string keys and values (integer 0..2147483647); at least 1 field(s) | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.labyrinth_medals",
  "args": {
    "values": {
      "0": 10
    }
  }
}
```

- values may be a single quantity for every stored entry, an array replacing entries from index 0, or an object such as {"0": 10} selecting individual zero-based storage indexes. Unspecified entries are preserved.
- Array length and indexes must fit the existing save; this action does not extend the array. Object keys must be canonical decimal indexes, with no leading zeros.
- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.treasure_chests`

Set selected treasure chest quantities.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `values` | Yes | integer 0..2147483647 OR array of (integer 0..2147483647); 1..unbounded entries OR object with numeric-string keys and values (integer 0..2147483647); at least 1 field(s) | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.treasure_chests",
  "args": {
    "values": {
      "0": 10
    }
  }
}
```

- values may be a single quantity for every stored entry, an array replacing entries from index 0, or an object such as {"0": 10} selecting individual zero-based storage indexes. Unspecified entries are preserved.
- Array length and indexes must fit the existing save; this action does not extend the array. Object keys must be canonical decimal indexes, with no leading zeros.
- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.event_capsules`

Set selected event-capsule ticket quantities.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `values` | Yes | integer 0..2147483647 OR array of (integer 0..2147483647); 1..unbounded entries OR object with numeric-string keys and values (integer 0..2147483647); at least 1 field(s) | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.event_capsules",
  "args": {
    "values": {
      "0": 10
    }
  }
}
```

- values may be a single quantity for every stored entry, an array replacing entries from index 0, or an object such as {"0": 10} selecting individual zero-based storage indexes. Unspecified entries are preserved.
- Array length and indexes must fit the existing save; this action does not extend the array. Object keys must be canonical decimal indexes, with no leading zeros.
- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.
- Uses the shared event_tickets quantity cap. These are storage indexes; items.event_tickets instead accepts original game item IDs.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.lucky_tickets`

Set selected first-category lucky-ticket quantities.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `values` | Yes | integer 0..2147483647 OR array of (integer 0..2147483647); 1..unbounded entries OR object with numeric-string keys and values (integer 0..2147483647); at least 1 field(s) | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.lucky_tickets",
  "args": {
    "values": {
      "0": 10
    }
  }
}
```

- values may be a single quantity for every stored entry, an array replacing entries from index 0, or an object such as {"0": 10} selecting individual zero-based storage indexes. Unspecified entries are preserved.
- Array length and indexes must fit the existing save; this action does not extend the array. Object keys must be canonical decimal indexes, with no leading zeros.
- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.
- Uses the shared event_tickets quantity cap. These are storage indexes; items.event_tickets instead accepts original game item IDs.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.event_capsules_2`

Set selected second-category lucky-ticket quantities.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `values` | Yes | integer 0..2147483647 OR array of (integer 0..2147483647); 1..unbounded entries OR object with numeric-string keys and values (integer 0..2147483647); at least 1 field(s) | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.event_capsules_2",
  "args": {
    "values": {
      "0": 10
    }
  }
}
```

- values may be a single quantity for every stored entry, an array replacing entries from index 0, or an object such as {"0": 10} selecting individual zero-based storage indexes. Unspecified entries are preserved.
- Array length and indexes must fit the existing save; this action does not extend the array. Object keys must be canonical decimal indexes, with no leading zeros.
- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.
- Uses the shared event_tickets quantity cap. These are storage indexes; items.event_tickets instead accepts original game item IDs.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems`

### `items.battle_items`

Set selected battle-item quantities.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `values` | Yes | integer 0..2147483647 OR array of (integer 0..2147483647); 1..unbounded entries OR object with numeric-string keys and values (integer 0..2147483647); at least 1 field(s) | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.battle_items",
  "args": {
    "values": {
      "0": 10,
      "2": 5
    }
  }
}
```

- values may be a single quantity for every stored entry, an array replacing entries from index 0, or an object such as {"0": 10} selecting individual zero-based storage indexes. Unspecified entries are preserved.
- Array length and indexes must fit the existing save; this action does not extend the array. Object keys must be canonical decimal indexes, with no leading zeros.
- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.
- Only quantity fields change; item locks and existing endless-item durations are preserved.

Source: [core/game/battle/battle_items.py](vendor/bcsfe/src/bcsfe/core/game/battle/battle_items.py) — `BattleItems.edit`

### `items.endless`

Start or replace endless battle-item durations in minutes.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `minutes` | Yes | number 0..unbounded OR `"infinity"` OR array of (number 0..unbounded OR `"infinity"`); 1..unbounded entries OR object with numeric-string keys and values (number 0..unbounded OR `"infinity"`); at least 1 field(s) | Required |

```json
{
  "action": "items.endless",
  "args": {
    "minutes": {
      "0": 60
    }
  }
}
```

- minutes accepts a scalar for every stored battle item, a prefix array, or an object keyed by zero-based item indexes; unspecified items are preserved.
- Each selected timer is activated with its start time set to the current UTC time and its internal endless amount set to 0. Ordinary battle-item quantities are preserved.
- Use the string "infinity" for an unlimited end time. Numeric durations must remain finite after conversion to seconds. A duration of 0 produces equal start and end times; it does not clear the active flag.

Source: [core/game/battle/battle_items.py](vendor/bcsfe/src/bcsfe/core/game/battle/battle_items.py) — `BattleItems.edit_endless_items`

### `items.rare_ticket_trade`

Prepare the original five-to-one rare-ticket trade in cat storage.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `amount` | Yes | integer 0..429496729 | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.rare_ticket_trade",
  "args": {
    "amount": 2
  }
}
```

- Sets trade_progress to amount * 5 and places the original trade item (item_id=1, item_type=2) in the first empty or matching storage slot. Existing rare_tickets are not increased by this action.
- The save must contain an empty slot or an existing matching trade item.
- The resulting rare-ticket balance (current tickets + amount) is checked against the configured maximum by default. respect_maxima=false bypasses that configured cap; integer storage limits still apply.

Source: [cli/edits/rare_ticket_trade.py](vendor/bcsfe/src/bcsfe/cli/edits/rare_ticket_trade.py) — `RareTicketTrade.rare_ticket_trade`

### `items.event_tickets`

Set event and lucky-ticket quantities by original game item ID.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `items` | Yes | object with numeric-string keys and values (integer 0..2147483647); at least 1 field(s) | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.event_tickets",
  "args": {
    "items": {
      "501": 10
    }
  }
}
```

- Requires item-buy metadata for the save's region/version. IDs must belong to event tickets, first lucky tickets, or second lucky tickets and map to an existing storage slot.
- Use game item IDs as decimal object keys, not storage indexes. Multiple supplied IDs that resolve to one slot are rejected; unselected slots are preserved.
- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.
- The example ID is illustrative; select an event-ticket ID present in the applicable metadata.

Source: [cli/edits/event_tickets.py](vendor/bcsfe/src/bcsfe/cli/edits/event_tickets.py) — `EventTickets.edit_ticket`

### `items.evolve_by_id`

Set evolution-material quantities, including stones, by original game item ID.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `items` | Yes | object with numeric-string keys and values (integer 0..2147483647); at least 1 field(s) | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "items.evolve_by_id",
  "args": {
    "items": {
      "601": 10
    }
  }
}
```

- Requires item-buy metadata. Each ID must be an evolution item whose mapped catfruit-array index exists in the save. Multiple IDs resolving to the same slot are rejected.
- Uses game item IDs as decimal object keys; unselected materials are preserved.
- respect_maxima defaults to true and rejects quantities above the configured BCSFE maximum; false bypasses that configured cap, while the storage integer limit still applies.
- Before version 11.4.0, the old catfruit cap also limits the total after the edit. Later versions use the newer per-entry cap.
- The example ID is illustrative; select an evolution-item ID present in the applicable metadata.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems.edit_catfruit`

### `items.scheme`

Add or remove selected scheme rewards from the pending reward list.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `ids` | Yes | `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Required |
| `mode` | Yes | one of `"add"`, `"remove"` | Required |

```json
{
  "action": "items.scheme",
  "args": {
    "ids": "all",
    "mode": "add"
  }
}
```

- Requires schemeItemData.tsv metadata. ids="all" selects every valid ID from that table; explicit IDs must exist there.
- mode="add" adds missing IDs to to_obtain; mode="remove" removes selected IDs from to_obtain. Both modes also remove those IDs from received, matching the original editor.
- This changes the save's reward bookkeeping; it does not call a remote claim endpoint.

Source: [core/game/catbase/scheme_items.py](vendor/bcsfe/src/bcsfe/core/game/catbase/scheme_items.py) — `SchemeItems`

<a id="gacha"></a>

## Gacha seeds

Set the independent normal, rare, and event random-number seeds stored in a save.

### `gatya.rare_seed`

Set the rare gacha seed.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 0..4294967295 | Required |

```json
{
  "action": "gatya.rare_seed",
  "args": {
    "value": 4294967295
  }
}
```

- Accepts the complete unsigned 32-bit range 0..4294967295. It replaces the stored seed without drawing a capsule or changing the other seed fields.

Source: [core/game/catbase/gatya.py](vendor/bcsfe/src/bcsfe/core/game/catbase/gatya.py) — `Gatya.edit_rare_gatya_seed`

### `gatya.normal_seed`

Set the normal gacha seed.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 0..4294967295 | Required |

```json
{
  "action": "gatya.normal_seed",
  "args": {
    "value": 4294967295
  }
}
```

- Accepts the complete unsigned 32-bit range 0..4294967295. It replaces the stored seed without drawing a capsule or changing the other seed fields.

Source: [core/game/catbase/gatya.py](vendor/bcsfe/src/bcsfe/core/game/catbase/gatya.py) — `Gatya.edit_normal_gatya_seed`

### `gatya.event_seed`

Set the event gacha seed.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 0..4294967295 | Required |

```json
{
  "action": "gatya.event_seed",
  "args": {
    "value": 4294967295
  }
}
```

- Accepts the complete unsigned 32-bit range 0..4294967295. It replaces the stored seed without drawing a capsule or changing the other seed fields.

Source: [core/game/catbase/gatya.py](vendor/bcsfe/src/bcsfe/core/game/catbase/gatya.py) — `Gatya.edit_event_gatya_seed`

<a id="cats"></a>

## Cats, forms, talents, and orbs

Select cats by identity or game metadata, then edit ownership, progression, guide status, or orb inventory.

### `cats.unlock`

Unlock selected cats and set their gacha-seen, stage-drop, and equip-menu flags.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `select` | Yes | [Cat selection](#cat-selection): array of 1..10000 selector objects | Required |

```json
{
  "action": "cats.unlock",
  "args": {
    "select": [
      {
        "kind": "ids",
        "ids": [
          0
        ]
      }
    ]
  }
}
```

- Cat IDs are zero-based and must exist in the input save. Selection by names, rarity, obtainability, banner, or introduction version also requires game metadata; see the shared cat-selection reference.
- Requires drop_chara.csv and a compatible unit_drops array, even for an explicit ID selection. Existing levels and forms are preserved.

Source: [cli/edits/cat_editor.py](vendor/bcsfe/src/bcsfe/cli/edits/cat_editor.py) — `CatEditor.unlock_cats`

### `cats.remove`

Remove selected cats from the unlocked collection, optionally resetting their progress and original drop flags.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `select` | Yes | [Cat selection](#cat-selection): array of 1..10000 selector objects | Required |
| `reset` | No | boolean | false |

```json
{
  "action": "cats.remove",
  "args": {
    "select": [
      {
        "kind": "ids",
        "ids": [
          0
        ]
      }
    ],
    "reset": false
  }
}
```

- Cat IDs are zero-based and must exist in the input save. Selection by names, rarity, obtainability, banner, or introduction version also requires game metadata; see the shared cat-selection reference.
- reset defaults to false: only ownership is removed. reset=true invokes the original cat reset, clears new-cat flags and mapped stage-drop flags, and requires drop metadata.

Source: [cli/edits/cat_editor.py](vendor/bcsfe/src/bcsfe/cli/edits/cat_editor.py) — `CatEditor.remove_cats`

### `cats.forms`

Grant or remove true/fourth-form state, or choose the current displayed form of selected cats.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `select` | Yes | [Cat selection](#cat-selection): array of 1..10000 selector objects | Required |
| `operation` | Yes | one of `"true"`, `"fourth"`, `"remove_true"`, `"remove_fourth"`, `"current"` | Required |
| `force` | No | boolean | false |
| `unlock` | No | boolean | false |
| `set_current` | No | boolean | false |
| `form` | No | integer 1..4 | Required only for operation=current |

```json
{
  "action": "cats.forms",
  "args": {
    "select": [
      {
        "kind": "ids",
        "ids": [
          9
        ]
      }
    ],
    "operation": "true",
    "set_current": true
  }
}
```

- Cat IDs are zero-based and must exist in the input save. Selection by names, rarity, obtainability, banner, or introduction version also requires game metadata; see the shared cat-selection reference.
- operation=current requires form (1..4); form is rejected for other operations. Current form 3 or 4 must already be unlocked and exist in the picture-book metadata.
- Grant operations true/fourth use picture-book form counts unless force=true. A fourth-form request on a cat with only three forms grants its true form; cats with fewer forms follow the original available-form behavior.
- force, unlock, and set_current default to false. unlock also applies the normal cat-unlock/drop/menu changes. Current-form requests do not accept force or set_current; remove operations do not accept grant flags.

Source: [cli/edits/cat_editor.py](vendor/bcsfe/src/bcsfe/cli/edits/cat_editor.py) — `CatEditor.true_form_cats/fourth_form_cats/remove_true_form_cats/remove_fourth_form_cats`

### `cats.levels`

Set displayed base and plus levels independently, using exact values, metadata maxima, or inclusive random ranges.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `select` | Yes | [Cat selection](#cat-selection): array of 1..10000 selector objects | Required |
| `base` | No | integer 1..2147483647 OR `"max"` OR object { `min` (required): integer 0..2147483647; `max` (required): integer 0..2147483647 }; no other fields | Preserved |
| `plus` | No | integer 0..2147483647 OR `"max"` OR object { `min` (required): integer 0..2147483647; `max` (required): integer 0..2147483647 }; no other fields | Preserved |
| `unlock` | No | boolean | false |
| `strict` | No | boolean | false |
| `rank_up_sale` | No | boolean | false |

```json
{
  "action": "cats.levels",
  "args": {
    "select": [
      {
        "kind": "ids",
        "ids": [
          0
        ]
      }
    ],
    "base": 20,
    "plus": 0
  }
}
```

- Cat IDs are zero-based and must exist in the input save. Selection by names, rarity, obtainability, banner, or introduction version also requires game metadata; see the shared cat-selection reference.
- At least one of base or plus is required. Omitted components stay unchanged. Base levels start at 1; plus levels start at 0. A range is {min,max}, with min <= max.
- Requires UnitBuy metadata; base-level edits also require UnitLimit and rank-gift metadata. Values and range endpoints must fit each selected cat's metadata maxima.
- strict defaults to false; true applies the original progression restrictions and fails if the requested level is unreachable. Base-level changes recalculate the original upgrade/catseye progression fields.
- unlock defaults to false. rank_up_sale defaults to false; true explicitly sets rank_up_sale_value to 2147483647.

Source: [cli/edits/cat_editor.py](vendor/bcsfe/src/bcsfe/cli/edits/cat_editor.py) — `CatEditor.upgrade_individual/upgrade_many`; [core/game/catbase/powerup.py](vendor/bcsfe/src/bcsfe/core/game/catbase/powerup.py) — `PowerUpHelper`

### `cats.talents`

Set selected talent ability IDs, maximize existing supported talents, or reset talent levels on selected cats.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `select` | Yes | [Cat selection](#cat-selection): array of 1..10000 selector objects | Required |
| `operation` | Yes | one of `"set"`, `"max"`, `"remove"` | Required |
| `levels` | No | object with numeric-string keys and values (integer 0..2147483647 OR `"max"`) | Required only for operation=set |
| `unlock` | No | boolean | false |
| `allow_metadata_version_mismatch` | No | boolean | false |

```json
{
  "action": "cats.talents",
  "args": {
    "select": [
      {
        "kind": "ids",
        "ids": [
          9
        ]
      }
    ],
    "operation": "max"
  }
}
```

- Cat IDs are zero-based and must exist in the input save. Selection by names, rarity, obtainability, banner, or introduction version also requires game metadata; see the shared cat-selection reference.
- operation=set requires a nonempty levels object keyed by numeric talent ability IDs, with levels or "max" as values. Array positions are not talent IDs. levels is rejected for max/remove.
- Set/max require talent metadata and existing save talent entries. max skips cats without talent metadata; set rejects them. Omitted talent IDs stay unchanged; remove sets every existing selected-cat talent level to zero.
- allow_metadata_version_mismatch defaults to false. A mismatched metadata version fails unless this flag is explicitly true. unlock defaults to false and independently applies the normal cat-unlock changes.

Source: [cli/edits/cat_editor.py](vendor/bcsfe/src/bcsfe/cli/edits/cat_editor.py) — `CatEditor.edit_talent_individual/edit_talent_many/remove_talents_cats`

### `cats.guide`

Set the collected flag for selected cat-guide entries.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `select` | Yes | [Cat selection](#cat-selection): array of 1..10000 selector objects | Required |
| `collected` | Yes | boolean | Required |
| `unlock` | No | boolean | false |

```json
{
  "action": "cats.guide",
  "args": {
    "select": [
      {
        "kind": "ids",
        "ids": [
          0
        ]
      }
    ],
    "collected": true
  }
}
```

- Cat IDs are zero-based and must exist in the input save. Selection by names, rarity, obtainability, banner, or introduction version also requires game metadata; see the shared cat-selection reference.
- Only guide collection changes by default. unlock defaults to false; true also unlocks the cats, stage-drop flags, and equip menu. This action does not grant a separate guide reward item.

Source: [cli/edits/cat_editor.py](vendor/bcsfe/src/bcsfe/cli/edits/cat_editor.py) — `CatEditor.unlock_cat_guide/remove_cat_guide`

### `cats.orbs`

Set talent-orb inventory counts by exact orb ID or by metadata component filters.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `values` | No | object with numeric-string keys and values (integer 0..2147483647 OR `"max"`) | Choose one mode; see notes |
| `all` | No | boolean | false |
| `filters` | No | array of (object { `grade` (optional): string; 1..256 characters; `attribute` (optional): string; 1..256 characters; `effect` (optional): string; 1..256 characters }; no other fields); 1..10000 entries | Choose one mode; see notes |
| `count` | No | integer 0..2147483647 OR `"max"` | Required with all/filters |

```json
{
  "action": "cats.orbs",
  "args": {
    "all": true,
    "count": 1
  }
}
```

- Choose exactly one mode: a nonempty values object keyed by numeric orb IDs; all=true with count; or filters with count. count is rejected with values.
- Each filter contains at least one grade, attribute, or effect. Values use the original fuzzy component matching; omitted components and "*" are wildcards. Multiple filters are combined as a union.
- All modes require orb metadata. "max" uses the smaller of the configured talent-orb maximum and the storage maximum (127 before version 110400; 32767 from 110400). Unknown IDs or an empty selection fail; unselected counts are preserved.

Source: [core/game/catbase/talent_orbs.py](vendor/bcsfe/src/bcsfe/core/game/catbase/talent_orbs.py) — `SaveOrbs.edit_ind/edit_many/save`

<a id="storage"></a>

## Cat storage

Add cats or special-skill items to existing storage slots, or remove stored entries.

### `cats.storage.add`

Fill existing empty storage slots with requested cats or special-skill items.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `items` | No | array of (object { `kind` (required): one of `"cat"`, `"special_skill"`; `id` (required): integer 0..2147483647; `quantity` (required): integer 1..2147483647 }; no other fields); 1..10000 entries | Use items OR select + quantity |
| `select` | No | [Cat selection](#cat-selection): array of 1..10000 selector objects | Use select + quantity OR items |
| `quantity` | No | integer 1..2147483647 | Required only with select |

```json
{
  "action": "cats.storage.add",
  "args": {
    "items": [
      {
        "kind": "cat",
        "id": 0,
        "quantity": 1
      }
    ]
  }
}
```

- Use either items, or select plus quantity. The latter adds that quantity for every selected cat; quantity is not accepted with items.
- Each item requires kind, id, and quantity >= 1. Cat IDs must exist in the save. special_skill uses a zero-based special-skill storage index from game metadata.
- The total quantity must fit the currently empty physical slots. Existing entries and storage capacity are preserved; no automatic storage expansion or cat unlock occurs.

Source: [cli/edits/storage.py](vendor/bcsfe/src/bcsfe/cli/edits/storage.py) — `add_cats/add_special_skills`

### `cats.storage.remove`

Empty selected physical storage slots while preserving every other slot.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `slots` | Yes | array of (integer 0..2147483647); 1..10000 entries | Required |

```json
{
  "action": "cats.storage.remove",
  "args": {
    "slots": [
      0
    ]
  }
}
```

- slots contains zero-based physical storage positions, not cat IDs. Each position must exist; both its item ID and item type are reset to zero.

Source: [cli/edits/storage.py](vendor/bcsfe/src/bcsfe/cli/edits/storage.py) — `remove_items`

### `cats.storage.clear`

Empty every existing cat-storage slot.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `confirm` | Yes | `true` | Required |

```json
{
  "action": "cats.storage.clear",
  "args": {
    "confirm": true
  }
}
```

- confirm must be the JSON boolean true. This clears stored cats and special-skill items, preserving the number of storage slots.

Source: [cli/edits/storage.py](vendor/bcsfe/src/bcsfe/cli/edits/storage.py) — `clear_storage`

<a id="lineups"></a>

## Battle lineups

Edit lineup names, equipped cats, the active lineup, and the unlocked lineup count.

### `cats.lineups`

Edit existing lineup names and physical cat slots, and optionally select the active lineup.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `lineups` | No | array of (object { `id` (required): integer 0..2147483647; `name` (optional): string; 0..64 characters; `slots` (optional): object with numeric-string keys and values (integer -1..2147483647) }; no other fields); 1..10000 entries | Preserved |
| `selected` | No | integer 0..2147483647 | Preserved |

```json
{
  "action": "cats.lineups",
  "args": {
    "lineups": [
      {
        "id": 0,
        "name": "Main",
        "slots": {
          "0": 0
        }
      }
    ],
    "selected": 0
  }
}
```

- Provide lineups and/or selected. Each lineup entry requires a unique existing id and at least one name or slots change. IDs and slot keys are zero-based; slot values are cat IDs, with -1 clearing a slot.
- Unspecified lineups and positions are preserved. This action does not increase the unlocked lineup count or automatically unlock equipped cats; use the separate actions for those changes.

Source: [core/game/battle/slots.py](vendor/bcsfe/src/bcsfe/core/game/battle/slots.py) — `LineUps/EquipSlots`

### `lineups.unlocked_slots`

Set the number of unlocked lineups without changing equipped units.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 0..2147483647 | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "lineups.unlocked_slots",
  "args": {
    "value": 3
  }
}
```

- The recommended maximum is the save's lineup-name capacity. The hard limit is 10 before version 90700 and 127 from 90700, including when respect_maxima=false. This action does not purchase slots remotely.
- respect_maxima defaults to true. Setting it to false disables recommended game maxima, but valid IDs, available save fields, and binary storage bounds still apply.

Source: [core/game/battle/slots.py](vendor/bcsfe/src/bcsfe/core/game/battle/slots.py) — `LineUps.edit_unlocked_slots`

<a id="skills"></a>

## Base special skills

Edit the displayed base and plus levels of the base's special skills.

### `skills.set`

Set special-skill base and plus levels using fixed values, random ranges, or metadata maxima.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `skills` | Yes | `"all"` OR object with numeric-string keys and values (object { `level` (optional): integer 1..65536 OR `"max"` OR object { `min` (required): integer 1..65536; `max` (required): integer 1..65536 }; no other fields; `plus` (optional): integer 0..65535 OR `"max"` OR object { `min` (required): integer 0..65535; `max` (required): integer 0..65535 }; no other fields; `max` (optional): boolean }; at least 1 field(s); no other fields); at least 1 field(s) | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "skills.set",
  "args": {
    "skills": {
      "0": {
        "level": 10,
        "plus": 0
      }
    }
  }
}
```

- Skill keys are zero-based indexes in the visible skill list. Displayed level starts at 1; plus starts at 0. Metadata must exist for every selected skill.
- Provide level and/or plus, or max=true alone. Omitted components are preserved. max=false alone is rejected.
- Each component accepts an integer, "max", or an inclusive {"min": ..., "max": ...} range. Random draws are made separately per requested component; the hidden cannon skill receives the same chosen value as its visible counterpart.
- skills="all" maximizes both components of every visible skill using that skill's own metadata. "max" still uses metadata when respect_maxima=false.
- respect_maxima defaults to true. false allows explicit values above metadata caps, up to displayed level 65536 and plus 65535.
- Also sets the original rank-up sale field to 2147483647.

Source: [core/game/catbase/special_skill.py](vendor/bcsfe/src/bcsfe/core/game/catbase/special_skill.py) — `SpecialSkills.set_upgrade`; [core/game/catbase/upgrade.py](vendor/bcsfe/src/bcsfe/core/game/catbase/upgrade.py) — `Upgrade.get_user_upgrade`

<a id="story"></a>

## Story, treasures, and outbreaks

Edit story chapter progress, treasures, timed scores, zombie outbreaks, and replay flags.

### `stages.story`

Set story chapter clear counts or exact chapter progress.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `chapters` | Yes | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Required |
| `stages` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all in clear_count mode |
| `clear_count` | No | integer 0..32767 | Required unless progress supplied |
| `progress` | No | integer 0..2147483647 | Alternative to clear_count |
| `reset_after` | No | boolean | false |
| `clear_prerequisites` | No | boolean | false |

```json
{
  "action": "stages.story",
  "args": {
    "chapters": [
      0
    ],
    "stages": [
      0
    ],
    "clear_count": 1
  }
}
```

- Chapter IDs 0..2 select Empire of Cats, 3..5 Into the Future, and 6..8 Cats of the Cosmos. Stage IDs follow in-game progress order and are limited to the real stages in each chapter.
- Provide exactly one of clear_count or progress. With clear_count, stages defaults to "all"; unspecified stages are preserved and the chapter progress marker is adjusted.
- progress sets each stage before that position to one clear and resets all remaining valid stages to zero. It cannot be combined with stages or reset_after.
- reset_after defaults to false; when true with clear_count, stages after the highest selected stage are reset.
- clear_prerequisites defaults to false. When enabled, BCSFE also clears the prerequisite story chapters. Treasure levels and timed scores are otherwise preserved.

Source: [src/bcsfe/core/game/map/story.py](vendor/bcsfe/src/bcsfe/core/game/map/story.py) — `StoryChapters.clear_story`

### `stages.treasures`

Set treasure levels on selected story stages or treasure groups.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `chapters` | Yes | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Required |
| `stages` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all unless groups supplied |
| `groups` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Alternative to stages |
| `level` | Yes | integer 0..2147483647 | Required |

```json
{
  "action": "stages.treasures",
  "args": {
    "chapters": [
      0
    ],
    "stages": [
      0
    ],
    "level": 3
  }
}
```

- Chapter IDs use the story 0..8 mapping. Provide stages or groups, never both; omitting both selects every valid treasure stage.
- Stage IDs follow in-game order. The adapter translates them into the original reverse geographic storage order.
- groups uses zero-based treasure-group indexes and requires the chapter type's treasure-group metadata. Group members are resolved from that table.
- Only treasure values change; clear counts, chapter progress, and timed scores are preserved.

Source: [src/bcsfe/core/game/map/story.py](vendor/bcsfe/src/bcsfe/core/game/map/story.py) — `StoryChapters.edit_treasures`

### `stages.itf_scores`

Set Into the Future timed scores on selected stages.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `chapters` | Yes | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Required |
| `stages` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all |
| `score` | No | integer 0..2147483647 | Provide score OR score_range |
| `score_range` | No | array of (integer 0..2147483647); 2..2 entries | Provide score_range OR score |

```json
{
  "action": "stages.itf_scores",
  "args": {
    "chapters": [
      3
    ],
    "stages": [
      0
    ],
    "score_range": [
      6000,
      6010
    ]
  }
}
```

- chapters may select only story IDs 3..5; "all" means all available Into the Future chapters. stages defaults to "all" valid stages.
- Provide exactly one of score or score_range. score_range is [minimum, maximum], inclusive, and cannot be reversed.
- Each selected stage receives its own random draw when a range is used. Clear counts and treasures are preserved.

Source: [src/bcsfe/core/game/map/story.py](vendor/bcsfe/src/bcsfe/core/game/map/story.py) — `StoryChapters.edit_itf_timed_scores`

### `stages.outbreaks`

Mark existing zombie outbreak stages cleared or uncleared.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `chapters` | Yes | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Required |
| `stages` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all |
| `cleared` | Yes | boolean | Required |

```json
{
  "action": "stages.outbreaks",
  "args": {
    "chapters": [
      3
    ],
    "stages": [
      0
    ],
    "cleared": true
  }
}
```

- Uses true story chapter IDs 0..8, not the internal outbreak chapter keys. Chapters and stages must already exist in the save; stages defaults to "all" existing outbreaks.
- cleared=true also dismisses the corresponding current outbreak by clearing its current-outbreak flag, matching the original routine.
- cleared=false resets the stored clear flag without creating or activating a current outbreak.

Source: [src/bcsfe/core/game/map/outbreaks.py](vendor/bcsfe/src/bcsfe/core/game/map/outbreaks.py) — `Outbreaks.edit_outbreaks`

### `stages.tutorial`

Apply BCSFE's tutorial-completion routine explicitly.

Arguments: `{}`. No arguments are accepted.

```json
{
  "action": "stages.tutorial",
  "args": {}
}
```

- Accepts an empty args object. Raises the tutorial and introductory UI/treasure flags to the original minimum completed values.
- Ensures the required dialog flags exist and marks the first story stage cleared if it was uncleared.
- This routine is an explicit action; ordinary file loading and unrelated actions do not run it.

Source: [src/bcsfe/cli/edits/clear_tutorial.py](vendor/bcsfe/src/bcsfe/cli/edits/clear_tutorial.py) — `clear_tutorial`

### `stages.filibuster`

Enable a replay of the Filibuster stage.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `stage_id` | No | integer 0..2147483647 | Random valid stage in the final story chapter |

```json
{
  "action": "stages.filibuster",
  "args": {
    "stage_id": 47
  }
}
```

- Sets filibuster_stage_enabled=true. stage_id is a zero-based valid stage index from the last real story chapter.
- If stage_id is omitted, a valid stage is chosen randomly, matching the original editor.
- Requires a real story chapter structure; it changes the replay flag and selected stage without clearing the stage.

Source: [src/bcsfe/cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems.allow_filibuster_stage_reclearing`

<a id="maps"></a>

## Event and challenge maps

Edit legend, event, collab, gauntlet, tower, Aku, Enigma, and challenge progression.

### `stages.sol`

Edit Stories of Legend map clear counts or progress.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `maps` | Yes | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Required |
| `crowns` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all |
| `stages` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all in clear_count mode |
| `clear_count` | No | integer 0..32767 | Required unless progress supplied |
| `progress` | No | integer 0..2147483647 | Alternative to clear_count |
| `ensure_cleared` | No | boolean | false |
| `reset_after` | No | boolean | false |
| `reset_following_crowns` | No | boolean | false |

```json
{
  "action": "stages.sol",
  "args": {
    "maps": [
      0
    ],
    "crowns": [
      1
    ],
    "stages": [
      0
    ],
    "clear_count": 1
  }
}
```

- Provide exactly one of clear_count or progress. crowns defaults to "all" valid crowns; stages defaults to "all" valid stages when using clear_count. All selectors must exist in the save and applicable metadata.
- Map and stage IDs are zero-based; crowns are one-based. Available crowns are limited by the stored structure and Map_option.csv. Placeholder or unnamed stage slots are not selected.
- Map IDs are local to this category; the metadata base is 0. Do not pass the absolute base-plus-map ID.
- clear_count replaces counts in selected stages. ensure_cleared=true instead preserves existing nonzero counts and fills zero counts with the supplied positive value.
- progress counts the prefix of valid stages: it ensures that prefix is cleared, retaining existing nonzero counts, and resets the remaining valid stages in each selected crown. It cannot be combined with stages, ensure_cleared, or reset_after.
- reset_after=true clears valid stages after the highest selected stage. reset_following_crowns=true resets valid crowns after the highest selected crown in each map. Both default to false.
- Positive clears update progress and unlock state. Completing a selected map/crown can unlock the next crown and the next map; other counts are preserved unless a reset is requested.

Source: [src/bcsfe/core/game/map/event.py](vendor/bcsfe/src/bcsfe/core/game/map/event.py) — `EventChapters.edit_sol_chapters`

### `stages.event`

Edit event map clear counts or progress.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `maps` | Yes | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Required |
| `crowns` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all |
| `stages` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all in clear_count mode |
| `clear_count` | No | integer 0..32767 | Required unless progress supplied |
| `progress` | No | integer 0..2147483647 | Alternative to clear_count |
| `ensure_cleared` | No | boolean | false |
| `reset_after` | No | boolean | false |
| `reset_following_crowns` | No | boolean | false |

```json
{
  "action": "stages.event",
  "args": {
    "maps": [
      0
    ],
    "crowns": [
      1
    ],
    "stages": [
      0
    ],
    "clear_count": 1
  }
}
```

- Provide exactly one of clear_count or progress. crowns defaults to "all" valid crowns; stages defaults to "all" valid stages when using clear_count. All selectors must exist in the save and applicable metadata.
- Map and stage IDs are zero-based; crowns are one-based. Available crowns are limited by the stored structure and Map_option.csv. Placeholder or unnamed stage slots are not selected.
- Map IDs are local to this category; the metadata base is 1000. Do not pass the absolute base-plus-map ID.
- clear_count replaces counts in selected stages. ensure_cleared=true instead preserves existing nonzero counts and fills zero counts with the supplied positive value.
- progress counts the prefix of valid stages: it ensures that prefix is cleared, retaining existing nonzero counts, and resets the remaining valid stages in each selected crown. It cannot be combined with stages, ensure_cleared, or reset_after.
- reset_after=true clears valid stages after the highest selected stage. reset_following_crowns=true resets valid crowns after the highest selected crown in each map. Both default to false.
- Positive clears update progress and unlock state. Completing a selected map/crown can unlock the next crown and the next map; other counts are preserved unless a reset is requested.

Source: [src/bcsfe/core/game/map/event.py](vendor/bcsfe/src/bcsfe/core/game/map/event.py) — `EventChapters.edit_event_chapters`

### `stages.collab`

Edit collaboration map clear counts or progress.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `maps` | Yes | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Required |
| `crowns` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all |
| `stages` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all in clear_count mode |
| `clear_count` | No | integer 0..32767 | Required unless progress supplied |
| `progress` | No | integer 0..2147483647 | Alternative to clear_count |
| `ensure_cleared` | No | boolean | false |
| `reset_after` | No | boolean | false |
| `reset_following_crowns` | No | boolean | false |

```json
{
  "action": "stages.collab",
  "args": {
    "maps": [
      0
    ],
    "crowns": [
      1
    ],
    "stages": [
      0
    ],
    "clear_count": 1
  }
}
```

- Provide exactly one of clear_count or progress. crowns defaults to "all" valid crowns; stages defaults to "all" valid stages when using clear_count. All selectors must exist in the save and applicable metadata.
- Map and stage IDs are zero-based; crowns are one-based. Available crowns are limited by the stored structure and Map_option.csv. Placeholder or unnamed stage slots are not selected.
- Map IDs are local to this category; the metadata base is 2000. Do not pass the absolute base-plus-map ID.
- clear_count replaces counts in selected stages. ensure_cleared=true instead preserves existing nonzero counts and fills zero counts with the supplied positive value.
- progress counts the prefix of valid stages: it ensures that prefix is cleared, retaining existing nonzero counts, and resets the remaining valid stages in each selected crown. It cannot be combined with stages, ensure_cleared, or reset_after.
- reset_after=true clears valid stages after the highest selected stage. reset_following_crowns=true resets valid crowns after the highest selected crown in each map. Both default to false.
- Positive clears update progress and unlock state. Completing a selected map/crown can unlock the next crown and the next map; other counts are preserved unless a reset is requested.

Source: [src/bcsfe/core/game/map/event.py](vendor/bcsfe/src/bcsfe/core/game/map/event.py) — `EventChapters.edit_collab_chapters`

### `stages.gauntlets`

Edit Gauntlet map clear counts or progress.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `maps` | Yes | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Required |
| `crowns` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all |
| `stages` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all in clear_count mode |
| `clear_count` | No | integer 0..32767 | Required unless progress supplied |
| `progress` | No | integer 0..2147483647 | Alternative to clear_count |
| `ensure_cleared` | No | boolean | false |
| `reset_after` | No | boolean | false |
| `reset_following_crowns` | No | boolean | false |

```json
{
  "action": "stages.gauntlets",
  "args": {
    "maps": [
      0
    ],
    "crowns": [
      1
    ],
    "stages": [
      0
    ],
    "clear_count": 1
  }
}
```

- Provide exactly one of clear_count or progress. crowns defaults to "all" valid crowns; stages defaults to "all" valid stages when using clear_count. All selectors must exist in the save and applicable metadata.
- Map and stage IDs are zero-based; crowns are one-based. Available crowns are limited by the stored structure and Map_option.csv. Placeholder or unnamed stage slots are not selected.
- Map IDs are local to this category; the metadata base is 24000. Do not pass the absolute base-plus-map ID.
- clear_count replaces counts in selected stages. ensure_cleared=true instead preserves existing nonzero counts and fills zero counts with the supplied positive value.
- progress counts the prefix of valid stages: it ensures that prefix is cleared, retaining existing nonzero counts, and resets the remaining valid stages in each selected crown. It cannot be combined with stages, ensure_cleared, or reset_after.
- reset_after=true clears valid stages after the highest selected stage. reset_following_crowns=true resets valid crowns after the highest selected crown in each map. Both default to false.
- Positive clears update progress and unlock state. Completing a selected map/crown can unlock the next crown and the next map; other counts are preserved unless a reset is requested.

Source: [src/bcsfe/core/game/map/gauntlets.py](vendor/bcsfe/src/bcsfe/core/game/map/gauntlets.py) — `GauntletChapters.edit_gauntlets`

### `stages.collab_gauntlets`

Edit collaboration Gauntlet map clear counts or progress.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `maps` | Yes | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Required |
| `crowns` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all |
| `stages` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all in clear_count mode |
| `clear_count` | No | integer 0..32767 | Required unless progress supplied |
| `progress` | No | integer 0..2147483647 | Alternative to clear_count |
| `ensure_cleared` | No | boolean | false |
| `reset_after` | No | boolean | false |
| `reset_following_crowns` | No | boolean | false |

```json
{
  "action": "stages.collab_gauntlets",
  "args": {
    "maps": [
      0
    ],
    "crowns": [
      1
    ],
    "stages": [
      0
    ],
    "clear_count": 1
  }
}
```

- Provide exactly one of clear_count or progress. crowns defaults to "all" valid crowns; stages defaults to "all" valid stages when using clear_count. All selectors must exist in the save and applicable metadata.
- Map and stage IDs are zero-based; crowns are one-based. Available crowns are limited by the stored structure and Map_option.csv. Placeholder or unnamed stage slots are not selected.
- Map IDs are local to this category; the metadata base is 27000. Do not pass the absolute base-plus-map ID.
- clear_count replaces counts in selected stages. ensure_cleared=true instead preserves existing nonzero counts and fills zero counts with the supplied positive value.
- progress counts the prefix of valid stages: it ensures that prefix is cleared, retaining existing nonzero counts, and resets the remaining valid stages in each selected crown. It cannot be combined with stages, ensure_cleared, or reset_after.
- reset_after=true clears valid stages after the highest selected stage. reset_following_crowns=true resets valid crowns after the highest selected crown in each map. Both default to false.
- Positive clears update progress and unlock state. Completing a selected map/crown can unlock the next crown and the next map; other counts are preserved unless a reset is requested.

Source: [src/bcsfe/core/game/map/gauntlets.py](vendor/bcsfe/src/bcsfe/core/game/map/gauntlets.py) — `GauntletChapters.edit_collab_gauntlets`

### `stages.uncanny`

Edit Uncanny Legends map clear counts or progress.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `maps` | Yes | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Required |
| `crowns` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all |
| `stages` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all in clear_count mode |
| `clear_count` | No | integer 0..32767 | Required unless progress supplied |
| `progress` | No | integer 0..2147483647 | Alternative to clear_count |
| `ensure_cleared` | No | boolean | false |
| `reset_after` | No | boolean | false |
| `reset_following_crowns` | No | boolean | false |

```json
{
  "action": "stages.uncanny",
  "args": {
    "maps": [
      0
    ],
    "crowns": [
      1
    ],
    "stages": [
      0
    ],
    "clear_count": 1
  }
}
```

- Provide exactly one of clear_count or progress. crowns defaults to "all" valid crowns; stages defaults to "all" valid stages when using clear_count. All selectors must exist in the save and applicable metadata.
- Map and stage IDs are zero-based; crowns are one-based. Available crowns are limited by the stored structure and Map_option.csv. Placeholder or unnamed stage slots are not selected.
- Map IDs are local to this category; the metadata base is 13000. Do not pass the absolute base-plus-map ID.
- clear_count replaces counts in selected stages. ensure_cleared=true instead preserves existing nonzero counts and fills zero counts with the supplied positive value.
- progress counts the prefix of valid stages: it ensures that prefix is cleared, retaining existing nonzero counts, and resets the remaining valid stages in each selected crown. It cannot be combined with stages, ensure_cleared, or reset_after.
- reset_after=true clears valid stages after the highest selected stage. reset_following_crowns=true resets valid crowns after the highest selected crown in each map. Both default to false.
- Positive clears update progress and unlock state. Completing a selected map/crown can unlock the next crown and the next map; other counts are preserved unless a reset is requested.

Source: [src/bcsfe/core/game/map/uncanny.py](vendor/bcsfe/src/bcsfe/core/game/map/uncanny.py) — `UncannyChapters.edit_uncanny`

### `stages.catamin`

Edit Catamin map clear counts or progress.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `maps` | Yes | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Required |
| `crowns` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all |
| `stages` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all in clear_count mode |
| `clear_count` | No | integer 0..32767 | Required unless progress supplied |
| `progress` | No | integer 0..2147483647 | Alternative to clear_count |
| `ensure_cleared` | No | boolean | false |
| `reset_after` | No | boolean | false |
| `reset_following_crowns` | No | boolean | false |
| `completion_count` | No | integer 0..2147483647 | Separate map-level edit; see notes |

```json
{
  "action": "stages.catamin",
  "args": {
    "maps": [
      0
    ],
    "crowns": [
      1
    ],
    "stages": [
      0
    ],
    "clear_count": 1
  }
}
```

- Provide exactly one of clear_count or progress. crowns defaults to "all" valid crowns; stages defaults to "all" valid stages when using clear_count. All selectors must exist in the save and applicable metadata.
- Map and stage IDs are zero-based; crowns are one-based. Available crowns are limited by the stored structure and Map_option.csv. Placeholder or unnamed stage slots are not selected.
- Map IDs are local to this category; the metadata base is 14000. Do not pass the absolute base-plus-map ID.
- clear_count replaces counts in selected stages. ensure_cleared=true instead preserves existing nonzero counts and fills zero counts with the supplied positive value.
- progress counts the prefix of valid stages: it ensures that prefix is cleared, retaining existing nonzero counts, and resets the remaining valid stages in each selected crown. It cannot be combined with stages, ensure_cleared, or reset_after.
- reset_after=true clears valid stages after the highest selected stage. reset_following_crowns=true resets valid crowns after the highest selected crown in each map. Both default to false.
- Positive clears update progress and unlock state. Completing a selected map/crown can unlock the next crown and the next map; other counts are preserved unless a reset is requested.
- Alternatively, provide only maps and completion_count to set the map-level completion counter at 14000 + map_id. This separate mode does not change stage clears and cannot be combined with other arguments.

Source: [src/bcsfe/core/game/map/uncanny.py](vendor/bcsfe/src/bcsfe/core/game/map/uncanny.py) — `UncannyChapters.edit_catamin_stages`

### `stages.behemoth`

Edit Behemoth Culling map clear counts or progress.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `maps` | Yes | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Required |
| `crowns` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all |
| `stages` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all in clear_count mode |
| `clear_count` | No | integer 0..32767 | Required unless progress supplied |
| `progress` | No | integer 0..2147483647 | Alternative to clear_count |
| `ensure_cleared` | No | boolean | false |
| `reset_after` | No | boolean | false |
| `reset_following_crowns` | No | boolean | false |

```json
{
  "action": "stages.behemoth",
  "args": {
    "maps": [
      0
    ],
    "crowns": [
      1
    ],
    "stages": [
      0
    ],
    "clear_count": 1
  }
}
```

- Provide exactly one of clear_count or progress. crowns defaults to "all" valid crowns; stages defaults to "all" valid stages when using clear_count. All selectors must exist in the save and applicable metadata.
- Map and stage IDs are zero-based; crowns are one-based. Available crowns are limited by the stored structure and Map_option.csv. Placeholder or unnamed stage slots are not selected.
- Map IDs are local to this category; the metadata base is 31000. Do not pass the absolute base-plus-map ID.
- clear_count replaces counts in selected stages. ensure_cleared=true instead preserves existing nonzero counts and fills zero counts with the supplied positive value.
- progress counts the prefix of valid stages: it ensures that prefix is cleared, retaining existing nonzero counts, and resets the remaining valid stages in each selected crown. It cannot be combined with stages, ensure_cleared, or reset_after.
- reset_after=true clears valid stages after the highest selected stage. reset_following_crowns=true resets valid crowns after the highest selected crown in each map. Both default to false.
- Positive clears update progress and unlock state. Completing a selected map/crown can unlock the next crown and the next map; other counts are preserved unless a reset is requested.

Source: [src/bcsfe/core/game/map/gauntlets.py](vendor/bcsfe/src/bcsfe/core/game/map/gauntlets.py) — `GauntletChapters.edit_behemoth_culling`

### `stages.legend_quest`

Edit Legend Quest map clear counts or progress.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `maps` | Yes | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Required |
| `crowns` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all |
| `stages` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all in clear_count mode |
| `clear_count` | No | integer 0..32767 | Required unless progress supplied |
| `progress` | No | integer 0..2147483647 | Alternative to clear_count |
| `ensure_cleared` | No | boolean | false |
| `reset_after` | No | boolean | false |
| `reset_following_crowns` | No | boolean | false |

```json
{
  "action": "stages.legend_quest",
  "args": {
    "maps": [
      0
    ],
    "crowns": [
      1
    ],
    "stages": [
      0
    ],
    "clear_count": 1
  }
}
```

- Provide exactly one of clear_count or progress. crowns defaults to "all" valid crowns; stages defaults to "all" valid stages when using clear_count. All selectors must exist in the save and applicable metadata.
- Map and stage IDs are zero-based; crowns are one-based. Available crowns are limited by the stored structure and Map_option.csv. Placeholder or unnamed stage slots are not selected.
- Map IDs are local to this category; the metadata base is 16000. Do not pass the absolute base-plus-map ID.
- clear_count replaces counts in selected stages. ensure_cleared=true instead preserves existing nonzero counts and fills zero counts with the supplied positive value.
- progress counts the prefix of valid stages: it ensures that prefix is cleared, retaining existing nonzero counts, and resets the remaining valid stages in each selected crown. It cannot be combined with stages, ensure_cleared, or reset_after.
- reset_after=true clears valid stages after the highest selected stage. reset_following_crowns=true resets valid crowns after the highest selected crown in each map. Both default to false.
- Positive clears update progress and unlock state. Completing a selected map/crown can unlock the next crown and the next map; other counts are preserved unless a reset is requested.
- The original Legend Quest stage routine also updates tries alongside clears. ensure_cleared preserves existing nonzero values of each.

Source: [src/bcsfe/core/game/map/legend_quest.py](vendor/bcsfe/src/bcsfe/core/game/map/legend_quest.py) — `LegendQuestChapters.edit_legend_quest`

### `stages.towers`

Edit tower map clear counts or progress.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `maps` | Yes | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Required |
| `crowns` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all |
| `stages` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all in clear_count mode |
| `clear_count` | No | integer 0..32767 | Required unless progress supplied |
| `progress` | No | integer 0..2147483647 | Alternative to clear_count |
| `ensure_cleared` | No | boolean | false |
| `reset_after` | No | boolean | false |
| `reset_following_crowns` | No | boolean | false |

```json
{
  "action": "stages.towers",
  "args": {
    "maps": [
      0
    ],
    "crowns": [
      1
    ],
    "stages": [
      0
    ],
    "clear_count": 1
  }
}
```

- Provide exactly one of clear_count or progress. crowns defaults to "all" valid crowns; stages defaults to "all" valid stages when using clear_count. All selectors must exist in the save and applicable metadata.
- Map and stage IDs are zero-based; crowns are one-based. Available crowns are limited by the stored structure and Map_option.csv. Placeholder or unnamed stage slots are not selected.
- Map IDs are local to this category; the metadata base is 7000. Do not pass the absolute base-plus-map ID.
- clear_count replaces counts in selected stages. ensure_cleared=true instead preserves existing nonzero counts and fills zero counts with the supplied positive value.
- progress counts the prefix of valid stages: it ensures that prefix is cleared, retaining existing nonzero counts, and resets the remaining valid stages in each selected crown. It cannot be combined with stages, ensure_cleared, or reset_after.
- reset_after=true clears valid stages after the highest selected stage. reset_following_crowns=true resets valid crowns after the highest selected crown in each map. Both default to false.
- Positive clears update progress and unlock state. Completing a selected map/crown can unlock the next crown and the next map; other counts are preserved unless a reset is requested.

Source: [src/bcsfe/core/game/map/tower.py](vendor/bcsfe/src/bcsfe/core/game/map/tower.py) — `TowerChapters.edit_towers`

### `stages.zero_legends`

Edit Zero Legends map clear counts or progress.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `maps` | Yes | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Required |
| `crowns` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all |
| `stages` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all in clear_count mode |
| `clear_count` | No | integer 0..32767 | Required unless progress supplied |
| `progress` | No | integer 0..2147483647 | Alternative to clear_count |
| `ensure_cleared` | No | boolean | false |
| `reset_after` | No | boolean | false |
| `reset_following_crowns` | No | boolean | false |

```json
{
  "action": "stages.zero_legends",
  "args": {
    "maps": [
      0
    ],
    "crowns": [
      1
    ],
    "stages": [
      0
    ],
    "clear_count": 1
  }
}
```

- Provide exactly one of clear_count or progress. crowns defaults to "all" valid crowns; stages defaults to "all" valid stages when using clear_count. All selectors must exist in the save and applicable metadata.
- Map and stage IDs are zero-based; crowns are one-based. Available crowns are limited by the stored structure and Map_option.csv. Placeholder or unnamed stage slots are not selected.
- Map IDs are local to this category; the metadata base is 34000. Do not pass the absolute base-plus-map ID.
- clear_count replaces counts in selected stages. ensure_cleared=true instead preserves existing nonzero counts and fills zero counts with the supplied positive value.
- progress counts the prefix of valid stages: it ensures that prefix is cleared, retaining existing nonzero counts, and resets the remaining valid stages in each selected crown. It cannot be combined with stages, ensure_cleared, or reset_after.
- reset_after=true clears valid stages after the highest selected stage. reset_following_crowns=true resets valid crowns after the highest selected crown in each map. Both default to false.
- Positive clears update progress and unlock state. Completing a selected map/crown can unlock the next crown and the next map; other counts are preserved unless a reset is requested.

Source: [src/bcsfe/core/game/map/zero_legends.py](vendor/bcsfe/src/bcsfe/core/game/map/zero_legends.py) — `ZeroLegendsChapters.edit_zero_legends`

### `stages.dojo_catclaw`

Edit Catclaw Championship map clear counts or progress.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `maps` | Yes | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Required |
| `crowns` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all |
| `stages` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all in clear_count mode |
| `clear_count` | No | integer 0..32767 | Required unless progress supplied |
| `progress` | No | integer 0..2147483647 | Alternative to clear_count |
| `ensure_cleared` | No | boolean | false |
| `reset_after` | No | boolean | false |
| `reset_following_crowns` | No | boolean | false |

```json
{
  "action": "stages.dojo_catclaw",
  "args": {
    "maps": [
      0
    ],
    "crowns": [
      1
    ],
    "stages": [
      0
    ],
    "clear_count": 1
  }
}
```

- Provide exactly one of clear_count or progress. crowns defaults to "all" valid crowns; stages defaults to "all" valid stages when using clear_count. All selectors must exist in the save and applicable metadata.
- Map and stage IDs are zero-based; crowns are one-based. Available crowns are limited by the stored structure and Map_option.csv. Placeholder or unnamed stage slots are not selected.
- Map IDs are local to this category; the metadata base is 37000. Do not pass the absolute base-plus-map ID.
- clear_count replaces counts in selected stages. ensure_cleared=true instead preserves existing nonzero counts and fills zero counts with the supplied positive value.
- progress counts the prefix of valid stages: it ensures that prefix is cleared, retaining existing nonzero counts, and resets the remaining valid stages in each selected crown. It cannot be combined with stages, ensure_cleared, or reset_after.
- reset_after=true clears valid stages after the highest selected stage. reset_following_crowns=true resets valid crowns after the highest selected crown in each map. Both default to false.
- Positive clears update progress and unlock state. Completing a selected map/crown can unlock the next crown and the next map; other counts are preserved unless a reset is requested.
- This edits Catclaw Championship stage clears, separate from the regular dojo score.

Source: [src/bcsfe/core/game/map/zero_legends.py](vendor/bcsfe/src/bcsfe/core/game/map/zero_legends.py) — `ZeroLegendsChapters.edit_catclaw_championships`

### `stages.enigma_clears`

Edit Enigma map clear counts or progress.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `maps` | Yes | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Required |
| `crowns` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all |
| `stages` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | all in clear_count mode |
| `clear_count` | No | integer 0..32767 | Required unless progress supplied |
| `progress` | No | integer 0..2147483647 | Alternative to clear_count |
| `ensure_cleared` | No | boolean | false |
| `reset_after` | No | boolean | false |
| `reset_following_crowns` | No | boolean | false |

```json
{
  "action": "stages.enigma_clears",
  "args": {
    "maps": [
      0
    ],
    "crowns": [
      1
    ],
    "stages": [
      0
    ],
    "clear_count": 1
  }
}
```

- Provide exactly one of clear_count or progress. crowns defaults to "all" valid crowns; stages defaults to "all" valid stages when using clear_count. All selectors must exist in the save and applicable metadata.
- Map and stage IDs are zero-based; crowns are one-based. Available crowns are limited by the stored structure and Map_option.csv. Placeholder or unnamed stage slots are not selected.
- Map IDs are local to this category; the metadata base is 25000. Do not pass the absolute base-plus-map ID.
- clear_count replaces counts in selected stages. ensure_cleared=true instead preserves existing nonzero counts and fills zero counts with the supplied positive value.
- progress counts the prefix of valid stages: it ensures that prefix is cleared, retaining existing nonzero counts, and resets the remaining valid stages in each selected crown. It cannot be combined with stages, ensure_cleared, or reset_after.
- reset_after=true clears valid stages after the highest selected stage. reset_following_crowns=true resets valid crowns after the highest selected crown in each map. Both default to false.
- Positive clears update progress and unlock state. Completing a selected map/crown can unlock the next crown and the next map; other counts are preserved unless a reset is requested.
- This edits stored Enigma clear records. Use stages.enigma to add or replace decoded Enigma maps.

Source: [src/bcsfe/core/game/map/gauntlets.py](vendor/bcsfe/src/bcsfe/core/game/map/gauntlets.py) — `GauntletChapters.edit_enigma_stages`

### `stages.aku`

Set Aku Realm clear counts for selected stages or an exact prefix.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `progress` | No | integer 0..2147483647 OR `"all"` | Required unless stages supplied |
| `stages` | No | one of `"all"` OR array of (integer 0..2147483647); 1..unbounded entries; unique entries | Alternative to progress |
| `map` | No | integer 0..2147483647 OR `"all"` | 0 |
| `crown` | No | integer 1..2147483647 OR `"all"` | 1 |
| `clear_count` | No | integer 0..32767 | 1 in progress mode; required with stages |
| `clear_counts` | No | array of (integer 0..32767); 0..unbounded entries | Alternative to clear_count in progress mode only |

```json
{
  "action": "stages.aku",
  "args": {
    "progress": 2,
    "clear_counts": [
      1,
      1
    ]
  }
}
```

- Provide exactly one of stages or progress. map defaults to 0 and crown defaults to 1; either accepts "all". Maps are zero-based and crowns one-based, within the save's structure.
- The stages mode requires clear_count and preserves all unselected stages; clear_counts cannot be used in that mode.
- The progress mode accepts a nonnegative prefix length or "all". It sets counts in the prefix and resets later stages to zero.
- For progress, use one clear_count (default 1) or clear_counts with exactly one entry per prefix stage; the two cannot be combined.
- Only clear_times are changed. Unrelated Aku state, including current_stage, is preserved.

Source: [src/bcsfe/core/game/map/aku.py](vendor/bcsfe/src/bcsfe/core/game/map/aku.py) — `AkuChapters.edit_aku_chapters`

### `stages.unlock_aku`

Clear the original seven quests used to unlock the Aku Realm.

Arguments: `{}`. No arguments are accepted.

```json
{
  "action": "stages.unlock_aku",
  "args": {}
}
```

- Accepts an empty args object. Requires matching event-map metadata and save structures for maps 255, 256, 257, 258, 265, 266, and 268.
- Ensures valid stages in crown 1 of those quests have at least one clear, preserving existing nonzero counts.
- Uses the shared event-map editor, including its progress and next-map/crown unlock updates. Other quest clear counts are preserved.

Source: [src/bcsfe/cli/edits/aku_realm.py](vendor/bcsfe/src/bcsfe/cli/edits/aku_realm.py) — `unlock_aku_realm`

### `stages.enigma`

Add decoded Enigma maps or replace the decoded map list.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `maps` | Yes | one of `"all"` OR array of (integer 0..2147483647); 0..unbounded entries; unique entries | Required |
| `replace` | No | boolean | false |

```json
{
  "action": "stages.enigma",
  "args": {
    "maps": [
      8
    ],
    "replace": false
  }
}
```

- Requires Enigma map metadata. maps contains actual sparse map IDs in category H, before adding the 25000 base; IDs are not menu positions.
- replace defaults to false and appends the selected maps. replace=true discards the current list; maps=[] with replace=true removes all entries.
- At most 127 entries may exist after the edit. New entries use decoded state, the current timestamp, and absolute ID 25000 + map_id.
- Resets the completion counters for added maps. Replacement also resets counters for removed entries. Existing entries are not deduplicated automatically.

Source: [src/bcsfe/core/game/map/enigma.py](vendor/bcsfe/src/bcsfe/core/game/map/enigma.py) — `edit_enigma`

### `stages.dojo_score`

Set the regular dojo's stored score.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `score` | Yes | integer 0..2147483647 | Required |

```json
{
  "action": "stages.dojo_score",
  "args": {
    "score": 4000
  }
}
```

- Updates only the first regular dojo stage's score. It does not submit an online ranking or edit Catclaw Championship clears.

Source: [src/bcsfe/core/game/map/dojo.py](vendor/bcsfe/src/bcsfe/core/game/map/dojo.py) — `edit_dojo_score`

### `stages.challenge_score`

Set the first challenge score and its completion state.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `score` | Yes | integer 0..2147483647 | Required |

```json
{
  "action": "stages.challenge_score",
  "args": {
    "score": 5000
  }
}
```

- Requires the first challenge map, crown, and stage to exist. Creates the first score entry if absent, or replaces it while preserving later score entries.
- Sets shown_popup=true, ensures the first challenge stage has a clear, advances its progress to at least 1, and marks its crown unlocked.
- An existing nonzero clear count is preserved.

Source: [src/bcsfe/core/game/map/challenge.py](vendor/bcsfe/src/bcsfe/core/game/map/challenge.py) — `edit_challenge_score`

<a id="gamatoto"></a>

## Gamatoto expeditions

Edit expedition XP, its derived level, and helpers.

### `gamatoto.xp`

Set the raw Gamatoto expedition XP total.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 0..2147483647 | Required |

```json
{
  "action": "gamatoto.xp",
  "args": {
    "value": 1000
  }
}
```

- No game metadata is needed for the raw XP value. The skin and helper collection are preserved; use gamatoto.level for an XP-table conversion.

Source: [core/game/gamoto/gamatoto.py](vendor/bcsfe/src/bcsfe/core/game/gamoto/gamatoto.py) — `Gamatoto.edit_raw_xp`

### `gamatoto.level`

Convert a displayed Gamatoto level to its XP threshold using the save's game metadata.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 1..2147483647 | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "gamatoto.level",
  "args": {
    "value": 2
  }
}
```

- Requires Gamatoto expedition and limit tables. A level must have an actual XP-table row even when recommended maxima are disabled. Skin and helpers stay unchanged.
- respect_maxima defaults to true. Setting it to false disables recommended game maxima, but valid IDs, available save fields, and binary storage bounds still apply.

Source: [core/game/gamoto/gamatoto.py](vendor/bcsfe/src/bcsfe/core/game/gamoto/gamatoto.py) — `Gamatoto.edit_level`

### `gamatoto.helpers`

Replace the helper list or set helper counts for selected rarities.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `ids` | No | array of (integer 0..2147483647); 0..unbounded entries | Use ids OR rarities |
| `rarities` | No | object with numeric-string keys and values (integer 0..2147483647) | Use rarities OR ids |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "gamatoto.helpers",
  "args": {
    "rarities": {
      "0": 1
    }
  }
}
```

- Provide exactly one of ids or rarities. ids replaces the entire list; [] removes all helpers. Each ID must be present in helper metadata; repeated IDs are allowed.
- rarities must be a nonempty mapping from numeric rarity keys to counts. Other rarity groups and occupied helpers missing from metadata are preserved. Requested helpers cycle through the known IDs in each rarity.
- Requires helper-name and expedition-limit metadata. The final list must fit the allowed helper count and the 262144-entry save-size guard.
- respect_maxima defaults to true. Setting it to false disables recommended game maxima, but valid IDs, available save fields, and binary storage bounds still apply.

Source: [core/game/gamoto/gamatoto.py](vendor/bcsfe/src/bcsfe/core/game/gamoto/gamatoto.py) — `Gamatoto.edit_helpers`

<a id="ototo"></a>

## Ototo construction

Edit engineers, construction materials, and existing cannon development or part levels.

### `ototo.engineers`

Set the number of Ototo construction engineers.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | integer 0..2147483647 | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "ototo.engineers",
  "args": {
    "value": 1
  }
}
```

- Requires CastleCustomLimit.csv; its first value supplies the recommended limit. The engineer count is independent of cannon progress and materials.
- respect_maxima defaults to true. Setting it to false disables recommended game maxima, but valid IDs, available save fields, and binary storage bounds still apply.

Source: [core/game/gamoto/ototo.py](vendor/bcsfe/src/bcsfe/core/game/gamoto/ototo.py) — `Ototo.edit_engineers`

### `ototo.materials`

Set construction-material quantities at selected save indexes.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `values` | Yes | array of (integer 0..2147483647); 0..unbounded entries OR object with numeric-string keys and values (integer 0..2147483647); at least 1 field(s) | Required |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "ototo.materials",
  "args": {
    "values": {
      "0": 10
    }
  }
}
```

- Use a numeric-keyed object to edit selected zero-based indexes, preserving the rest. An array must contain exactly the save's full material count. The configured base_materials limit applies by default.
- respect_maxima defaults to true. Setting it to false disables recommended game maxima, but valid IDs, available save fields, and binary storage bounds still apply.

Source: [core/game/gamoto/base_materials.py](vendor/bcsfe/src/bcsfe/core/game/gamoto/base_materials.py) — `BaseMaterials.edit_base_materials`

### `ototo.cannons`

Edit development state and displayed part levels for existing cannons.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `ids` | No | array of (integer 0..2147483647); 1..unbounded entries; unique entries OR `"all"` | Required unless using entries |
| `entries` | No | array of (object { `id` (required): integer 0..2147483647; `development` (optional): integer 0..3; `levels` (optional): array of (integer 0..2147483647); 0..unbounded entries OR object with numeric-string keys and values (integer 0..2147483647); at least 1 field(s); `max` (optional): `true` }; no other fields); 1..unbounded entries | Alternative to shared ids/edit fields |
| `development` | No | integer 0..3 | Preserved unless level/max edit promotes to 3 |
| `levels` | No | array of (integer 0..2147483647); 0..unbounded entries OR object with numeric-string keys and values (integer 0..2147483647); at least 1 field(s) | Preserved unless max=true |
| `max` | No | `true` | Absent; when supplied must be true |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "ototo.cannons",
  "args": {
    "ids": [
      0
    ],
    "levels": {
      "0": 10
    }
  }
}
```

- Use ids plus development, levels, or max=true; alternatively use entries for per-cannon changes. entries cannot be combined with other edit fields except respect_maxima. Cannon IDs must already exist in the save and may not repeat.
- development is 0..3 and cannot be edited for base cannon ID 0. Level edits promote development to at least 3; an explicitly supplied development below 3 conflicts with a level edit.
- levels may be a complete part array or a partial numeric-keyed object. Part 0 uses displayed levels and stores one less; other parts use their values directly. max=true uses CastleRecipeUnlock.csv per-part limits and cannot be combined with levels.
- Level/max edits require matching recipe rows, even with recommended maxima disabled. Unspecified part levels and the selected cannon/parts remain unchanged.
- respect_maxima defaults to true. Setting it to false disables recommended game maxima, but valid IDs, available save fields, and binary storage bounds still apply.

Source: [core/game/gamoto/ototo.py](vendor/bcsfe/src/bcsfe/core/game/gamoto/ototo.py) — `Ototo.edit_cannon`

<a id="progression"></a>

## Rewards and collection progress

Edit shrine progress, reward flags, medals, missions, the enemy guide, and gambling-event state.

### `shrine.set`

Set Cat Shrine offering XP or its derived level, and optionally change shrine visibility.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `level` | No | integer 1..2147483647 | Derived from XP |
| `xp` | No | integer 0..unbounded | Preserved unless level is provided |
| `visible` | No | boolean | Preserved |
| `respect_maxima` | No | boolean | true |

```json
{
  "action": "shrine.set",
  "args": {
    "level": 1,
    "visible": true
  }
}
```

- Provide level or xp, optionally visible; visible alone is also accepted. level and xp are mutually exclusive. jinja_level.csv is required for all modes, including visibility-only changes.
- Level 1 maps to zero offering XP. The shrine dialog count is recomputed from the resulting XP. With respect_maxima=false, above-table levels map to the table's maximum XP rather than inventing new levels; explicit XP is still limited to 2147483647.
- Omitted visibility is preserved. respect_maxima defaults to true; its normal XP ceiling follows the shrine table and signed 64-bit storage.

Source: [core/game/gamoto/cat_shrine.py](vendor/bcsfe/src/bcsfe/core/game/gamoto/cat_shrine.py) — `CatShrine.edit_catshrine`

### `rewards.claim`

Set user-rank reward claim flags, or repair claims above the current calculated user rank.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `ids` | No | array of (integer 0..2147483647); 1..unbounded entries; unique entries OR `"all"` | Required for claim/unclaim; rejected for fix_claimed |
| `mode` | Yes | one of `"claim"`, `"unclaim"`, `"fix_claimed"` | Required |

```json
{
  "action": "rewards.claim",
  "args": {
    "mode": "fix_claimed"
  }
}
```

- claim/unclaim require ids (a list of reward metadata indexes or "all"). Only rewards available at the save's current calculated user rank and present in its reward array may be selected.
- fix_claimed rejects ids and clears claimed flags only above the current user rank. Requires rankGift.csv. This action changes claim flags; it does not grant the reward's items.

Source: [core/game/catbase/user_rank_rewards.py](vendor/bcsfe/src/bcsfe/core/game/catbase/user_rank_rewards.py) — `UserRankRewards.edit`

### `medals.set`

Add or remove medals identified by the game's medal metadata.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `ids` | Yes | array of (integer 0..2147483647); 1..unbounded entries; unique entries OR `"all"` | Required |
| `owned` | Yes | boolean | Required |

```json
{
  "action": "medals.set",
  "args": {
    "ids": "all",
    "owned": true
  }
}
```

- Requires medalname.tsv. IDs are nonempty metadata row indexes; "all" selects all valid rows. Existing medal IDs absent from metadata are preserved.

Source: [core/game/catbase/medals.py](vendor/bcsfe/src/bcsfe/core/game/catbase/medals.py) — `Medals.edit_medals`

### `missions.set`

Set existing missions to reward-ready, already claimed, or incomplete.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `ids` | Yes | array of (integer 0..2147483647); 1..unbounded entries; unique entries OR `"all"` | Required |
| `state` | Yes | one of `"complete_reward"`, `"complete_claim"`, `"uncomplete"` | Required |

```json
{
  "action": "missions.set",
  "args": {
    "ids": "all",
    "state": "complete_reward"
  }
}
```

- Available IDs are the intersection of the save's mission states, mission conditions, and mission-name metadata. This action does not create unknown missions.
- complete_reward writes state 2; complete_claim writes state 4. Both set the progress requirement to the metadata target. uncomplete writes state 0 and clears an existing progress requirement. No reward inventory is granted separately.

Source: [core/game/catbase/mission.py](vendor/bcsfe/src/bcsfe/core/game/catbase/mission.py) — `Missions.edit_missions`

### `enemy_guide.set`

Unlock or reset enemy-guide entries selected by ID, name, or metadata validity.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `ids` | No | array of (integer 0..2147483647); 1..unbounded entries; unique entries OR `"all"` | Choose one selector |
| `group` | No | one of `"all"`, `"valid"`, `"invalid"` | Choose one selector |
| `name` | No | string; 1..unbounded characters | Choose one selector |
| `id_space` | No | one of `"save"`, `"game"` | save |
| `unlocked` | Yes | boolean | Required |

```json
{
  "action": "enemy_guide.set",
  "args": {
    "ids": [
      0
    ],
    "unlocked": true
  }
}
```

- Provide exactly one of ids, group, or name. With ids, id_space defaults to "save" (zero-based array positions); "game" requires game IDs >= 2 and subtracts 2 before editing. id_space is rejected for other selectors.
- group=all selects the save array; valid/invalid uses enemy_dictionary_list.csv. name performs a case-insensitive substring match on enemy names and fails when nothing matches. Unselected entries are preserved.

Source: [cli/edits/enemy_editor.py](vendor/bcsfe/src/bcsfe/cli/edits/enemy_editor.py) — `EnemyEditor.edit_enemy_guide`

### `gambling.reset`

Reset the completion flags, values, and start dates of selected gambling events.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `events` | No | array of (one of `"wildcat_slots"`, `"cat_scratcher"`); 1..unbounded entries | ["wildcat_slots", "cat_scratcher"] |

```json
{
  "action": "gambling.reset",
  "args": {
    "events": [
      "wildcat_slots",
      "cat_scratcher"
    ]
  }
}
```

- events defaults to both wildcat_slots and cat_scratcher. Supplying a nonempty subset resets only those event models; no new draw is performed.

Source: [core/game/catbase/gambling.py](vendor/bcsfe/src/bcsfe/core/game/catbase/gambling.py) — `GamblingEvent.reset_events`

<a id="account"></a>

## Account fields and save format

Edit local identity fields, pass state, play time, region, or format version. These actions do not perform remote account operations.

### `account.inquiry_code`

Replace the account's stored inquiry code.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | string; 0..512 characters | Required |

```json
{
  "action": "account.inquiry_code",
  "args": {
    "value": "ACCOUNT_INQUIRY_CODE"
  }
}
```

- Accepts a string of at most 512 characters without NUL; an empty string clears the field.
- Only the local save field is changed. This action does not obtain, validate, or refresh server credentials.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems.edit_inquiry_code`

### `account.password_refresh_token`

Replace the account's stored password refresh token.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `value` | Yes | string; 0..512 characters | Required |

```json
{
  "action": "account.password_refresh_token",
  "args": {
    "value": "ACCOUNT_REFRESH_TOKEN"
  }
}
```

- Accepts a string of at most 512 characters without NUL; an empty string clears the field.
- Only the local save field is changed. This action does not obtain, validate, or refresh server credentials.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems.edit_password_refresh_token`

### `save.region`

Change the save's country code through BCSFE set_cc.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `country_code` | Yes | one of `"kr"`, `"en"`, `"jp"`, `"tw"` | Required |

```json
{
  "action": "save.region",
  "args": {
    "country_code": "en"
  }
}
```

- Accepts kr, en, jp, or tw and clears the package-name override as the original method does.
- This is a save conversion, not a server-side account transfer. The edited file must pass the API's serialization and reparse checks.

Source: [cli/save_management.py](vendor/bcsfe/src/bcsfe/cli/save_management.py) — `SaveManagement.convert_save_cc`

### `save.version`

Change the version used to serialize the save.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `game_version` | Yes | integer 1..2147483647 | Required |

```json
{
  "action": "save.version",
  "args": {
    "game_version": 150500
  }
}
```

- Use BCSFE's integer version encoding, for example 150500 for 15.5.0.
- Calls set_gv on the save; it does not download or upgrade the game client. Version-dependent serialization must still pass the API's reparse and preservation checks.
- Schema acceptance of a version number does not establish that the target game accepts the converted save.

Source: [cli/save_management.py](vendor/bcsfe/src/bcsfe/cli/save_management.py) — `SaveManagement.convert_save_gv`

### `account.gold_pass`

Apply or remove the original Gold Pass state in the save file.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `enabled` | Yes | boolean | Required |
| `officer_id` | No | integer 0..2147483647 | Random 1..65535 when enabled |

```json
{
  "action": "account.gold_pass",
  "args": {
    "enabled": true
  }
}
```

- enabled=true uses the server's current time, two successive 30-day periods, and the original pass popup/login-reward fields. officer_id is optional; omission chooses a random ID from 1..65535.
- enabled=false rejects officer_id and clears the pass dates, flags, claimed rewards, and matching login count. Existing play time is preserved.
- This is a local save edit. It does not purchase, activate, or verify a server subscription, and does not establish in-game acceptance.

Source: [core/game/catbase/nyanko_club.py](vendor/bcsfe/src/bcsfe/core/game/catbase/nyanko_club.py) — `NyankoClub.edit_gold_pass`

### `playtime.set`

Set the total stored play duration using frames or time components.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `frames` | No | integer 0..2147483647 | Alternative to time components |
| `hours` | No | integer 0..2147483647 | 0 |
| `minutes` | No | integer 0..2147483647 | 0 |
| `seconds` | No | integer 0..2147483647 | 0 |

```json
{
  "action": "playtime.set",
  "args": {
    "hours": 10,
    "minutes": 30
  }
}
```

- Provide frames alone, or at least one of hours/minutes/seconds. Omitted time components mean zero, not the current value. The conversion uses 30 frames per second, and the resulting total must be <= 2147483647 frames.
- Gold Pass and officer-cat fields are preserved. Minutes and seconds are duration components; they are not restricted to a clock's 0..59 range.

Source: [core/game/catbase/playtime.py](vendor/bcsfe/src/bcsfe/core/game/catbase/playtime.py) — `edit`

<a id="fixes"></a>

## Explicit save repairs

Apply the original targeted repairs only when requested; several reset existing progress or pass state.

### `fixes.gamatoto`

Apply the original Gamatoto crash repair by setting expedition skin to 2.

Arguments: `{}`. No arguments are accepted.

```json
{
  "action": "fixes.gamatoto",
  "args": {}
}
```

- This explicitly changes the stored skin; it does not reset expedition XP or helpers and is not automatically applied by other edits.

Source: [cli/edits/fixes.py](vendor/bcsfe/src/bcsfe/cli/edits/fixes.py) — `Fixes.fix_gamatoto_crash`

### `fixes.ototo`

Reset the cannon collection and selected parts to the original version-specific initial state.

Arguments: `{}`. No arguments are accepted.

```json
{
  "action": "fixes.ototo",
  "args": {}
}
```

- This replaces existing cannon development and level data. Engineer and material quantities remain separate; apply only when this reset is intended.

Source: [cli/edits/fixes.py](vendor/bcsfe/src/bcsfe/cli/edits/fixes.py) — `Fixes.fix_ototo_crash`

### `fixes.time`

Set the save's time-error fields to an explicit Unix timestamp or the current API server time.

| Argument | Required | Format and schema bounds | Default / omission |
| --- | --- | --- | --- |
| `timestamp` | No | number 0..253402300799 | Current API server time |

```json
{
  "action": "fixes.time",
  "args": {
    "timestamp": 1735689600
  }
}
```

- timestamp is optional and must be finite and representable by the runtime's date implementation. Omission uses the API server's clock; supply the device's intended timestamp when required.
- Changes date_3, timestamp, and energy_penalty_timestamp. The schema's numeric ceiling does not guarantee that every platform supports every date within it.

Source: [cli/edits/fixes.py](vendor/bcsfe/src/bcsfe/cli/edits/fixes.py) — `Fixes.fix_time_errors`

### `fixes.officer_pass`

Reset officer-cat identity, play time, and Gold Pass state using the original repair routine.

Arguments: `{}`. No arguments are accepted.

```json
{
  "action": "fixes.officer_pass",
  "args": {}
}
```

- Resets officer cat/form and play time to zero, removes Gold Pass dates and flags, and clears its claimed/login rewards. This is an explicit reset of those fields.

Source: [core/game/catbase/officer_pass.py](vendor/bcsfe/src/bcsfe/core/game/catbase/officer_pass.py) — `OfficerPass.fix_crash`

### `fixes.equip_menu`

Unlock the equipment menu with the original save-file method.

Arguments: `{}`. No arguments are accepted.

```json
{
  "action": "fixes.equip_menu",
  "args": {}
}
```

- Changes the equipment-menu unlock flag only. It does not unlock cats, change lineups, or clear the tutorial.

Source: [cli/edits/basic_items.py](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py) — `BasicItems.unlock_equip_menu`

## Source and verification scope

Behavior is documented from the adapters and the supplied BCSFE source in `vendor/bcsfe`. [SOURCE_MANIFEST.json](vendor/bcsfe/SOURCE_MANIFEST.json) identifies that source. BCSFE is credited to fieryhenry; the original GNU GPL-3.0-or-later license is retained.

The examples are schema-checked operation templates. The project's separate binary, fixture, and opt-in public-metadata tests are described in [README.md](README.md); they do not establish universal game-version compatibility or live account acceptance.
