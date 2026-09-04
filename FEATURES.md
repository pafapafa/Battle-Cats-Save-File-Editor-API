# Original BCSFE feature mapping

This inventory maps all **99 unique source menu features** to the API. It follows [reference_features.json](reference_features.json) and the supplied [feature registry](vendor/bcsfe/src/bcsfe/cli/feature_handler.py), including the expanded cat submenus. The source has 101 menu entries because `special_skills` and `unlock_equip_menu` each appear in two places; both paths are retained below.

The 79 gameplay menu features map to 89 typed save-edit actions. A menu can expose multiple actions or several argument variants of one action, so these counts describe different things. File management, account transport, metadata, device operations, and terminal behavior are recorded separately.

Use [ACTIONS.md](ACTIONS.md) for the full arguments and examples for each edit, [ENDPOINTS.md](ENDPOINTS.md) for HTTP request/response contracts, and [TEMPLATES.md](TEMPLATES.md) for the additional backup/template APIs. Those backup APIs extend this project and are not counted as original BCSFE menu entries.

The deployed [feature endpoint](https://battle-cats-save-file-editor-api.vercel.app/v2/features) checks registered bindings and exposes the machine-readable inventory. The [API documentation](https://battle-cats-save-file-editor-api.vercel.app/docs) groups endpoints and actions by purpose.

## Status definitions

| Status | Count | Meaning |
| --- | --- | --- |
| Implemented (`implemented`) | 86 | The recorded action or endpoint is implemented; input/save compatibility and remote acceptance remain separate checks. |
| Adapted to HTTP (`adapted`) | 7 | The original interactive, filesystem, or configuration behavior is represented by explicit HTTP arguments, downloads, or service operations. |
| Unavailable on Vercel (`unavailable_in_vercel`) | 4 | Requires access to the user's device through ADB/root or a device-side companion. |
| Not applicable to HTTP (`not_applicable_to_http`) | 2 | A terminal session, theme/locale package, or desktop self-update action has no equivalent shared HTTP editing operation. |

These are implementation classifications, not a claim that every input has been tested or every remote operation succeeds. The separate Light, Dark, and System appearance choices on `/docs` are documentation preferences; they do not represent the source terminal's external-content update operation.

## Menu categories

- [Cats, storage, and special skills](#cats_special_skills) (10 features)
- [Save management and device operations](#save_management) (12 features)
- [Resources and items](#items) (22 features)
- [Stages, scores, and treasures](#levels) (24 features)
- [Gamatoto and Ototo](#gamototo) (6 features)
- [Account fields](#account) (4 features)
- [Gacha seeds](#gatya) (3 features)
- [Explicit repairs](#fixes) (5 features)
- [Rewards, collections, and other edits](#other) (9 features)
- [Editor configuration and game data](#editor) (3 features)
- [Terminal session](#exit) (1 feature)

## How to read the entries

Original menu paths retain their source identifiers. Each feature is listed once under its first menu category; additional alias paths remain visible in the entry. Action links open the matching API reference entry. Endpoint bindings list the HTTP method and path; route placeholders use the names in the inventory.

An offline binary sample means the registered action has an example using a real SaveFile model and the serialization boundary. It does not mean exhaustive input coverage. An entry that includes remote account transport remains explicitly unverified against live game accounts.

<a id="cats_special_skills"></a>

## Cats, storage, and special skills

### `special_skills`

Set special-skill base and plus levels using fixed values, random ranges, or metadata maxima.

| Field | Mapping |
| --- | --- |
| Original menu | `cats_special_skills > special_skills`; `other > special_skills` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [skills.set](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=skills.set) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:395](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L395) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_special_skills`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `cat_storage`

Fill existing empty storage slots with requested cats or special-skill items. Empty selected physical storage slots while preserving every other slot. Empty every existing cat-storage slot.

| Field | Mapping |
| --- | --- |
| Original menu | `cats_special_skills > cat_storage` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [cats.storage.add](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=cats.storage.add), [cats.storage.remove](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=cats.storage.remove), [cats.storage.clear](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=cats.storage.clear) |
| HTTP endpoints | `POST /v2/save/edit`; `POST /v2/save/inspect` |
| Source | [src/bcsfe/cli/edits/storage.py:93](vendor/bcsfe/src/bcsfe/cli/edits/storage.py#L93) |

Original function: `bcsfe.cli.edits.storage.edit_storage`.

- Storage display is available through save inspection; add/remove/clear preserve physical capacity and unselected slots.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `unlock_remove_cats`

Unlock selected cats and set their gacha-seen, stage-drop, and equip-menu flags. Remove selected cats from the unlocked collection, optionally resetting their progress and original drop flags.

| Field | Mapping |
| --- | --- |
| Original menu | `cats_special_skills > unlock_remove_cats` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [cats.unlock](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=cats.unlock), [cats.remove](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=cats.remove) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/cat_editor.py:599](vendor/bcsfe/src/bcsfe/cli/edits/cat_editor.py#L599) |

Original function: `bcsfe.cli.edits.cat_editor.CatEditor.unlock_remove_cats_run`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `upgrade_cats`

Set displayed base and plus levels independently, using exact values, metadata maxima, or inclusive random ranges.

| Field | Mapping |
| --- | --- |
| Original menu | `cats_special_skills > upgrade_cats` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [cats.levels](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=cats.levels) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/cat_editor.py:686](vendor/bcsfe/src/bcsfe/cli/edits/cat_editor.py#L686) |

Original function: `bcsfe.cli.edits.cat_editor.CatEditor.upgrade_cats_run`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `true_form_remove_form_cats`

Grant or remove true/fourth-form state, or choose the current displayed form of selected cats.

| Field | Mapping |
| --- | --- |
| Original menu | `cats_special_skills > true_form_remove_form_cats` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [cats.forms](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=cats.forms) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/cat_editor.py:622](vendor/bcsfe/src/bcsfe/cli/edits/cat_editor.py#L622) |

Original function: `bcsfe.cli.edits.cat_editor.CatEditor.true_form_remove_form_cats_run`.

Argument variant: `{"action": "cats.forms", "args": {"operation": "true"}}`.

Argument variant: `{"action": "cats.forms", "args": {"operation": "remove_true"}}`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `force_true_form_cats`

Grant or remove true/fourth-form state, or choose the current displayed form of selected cats.

| Field | Mapping |
| --- | --- |
| Original menu | `cats_special_skills > force_true_form_cats` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [cats.forms](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=cats.forms) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/cat_editor.py:670](vendor/bcsfe/src/bcsfe/cli/edits/cat_editor.py#L670) |

Original function: `bcsfe.cli.edits.cat_editor.CatEditor.force_true_form_cats_run`.

Argument variant: `{"action": "cats.forms", "args": {"force": true, "operation": "true"}}`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `fourth_form_remove_form_cats`

Grant or remove true/fourth-form state, or choose the current displayed form of selected cats.

| Field | Mapping |
| --- | --- |
| Original menu | `cats_special_skills > fourth_form_remove_form_cats` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [cats.forms](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=cats.forms) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/cat_editor.py:646](vendor/bcsfe/src/bcsfe/cli/edits/cat_editor.py#L646) |

Original function: `bcsfe.cli.edits.cat_editor.CatEditor.fourth_form_remove_form_cats_run`.

Argument variant: `{"action": "cats.forms", "args": {"operation": "fourth"}}`.

Argument variant: `{"action": "cats.forms", "args": {"operation": "remove_fourth"}}`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `force_fourth_form_cats`

Grant or remove true/fourth-form state, or choose the current displayed form of selected cats.

| Field | Mapping |
| --- | --- |
| Original menu | `cats_special_skills > force_fourth_form_cats` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [cats.forms](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=cats.forms) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/cat_editor.py:678](vendor/bcsfe/src/bcsfe/cli/edits/cat_editor.py#L678) |

Original function: `bcsfe.cli.edits.cat_editor.CatEditor.force_fourth_form_cats_run`.

Argument variant: `{"action": "cats.forms", "args": {"force": true, "operation": "fourth"}}`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `upgrade_talents_remove_talents_cats`

Set selected talent ability IDs, maximize existing supported talents, or reset talent levels on selected cats.

| Field | Mapping |
| --- | --- |
| Original menu | `cats_special_skills > upgrade_talents_remove_talents_cats` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [cats.talents](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=cats.talents) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/cat_editor.py:694](vendor/bcsfe/src/bcsfe/cli/edits/cat_editor.py#L694) |

Original function: `bcsfe.cli.edits.cat_editor.CatEditor.upgrade_talents_remove_talents_cats_run`.

Argument variant: `{"action": "cats.talents", "args": {"operation": "set"}}`.

Argument variant: `{"action": "cats.talents", "args": {"operation": "max"}}`.

Argument variant: `{"action": "cats.talents", "args": {"operation": "remove"}}`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `unlock_remove_cat_guide`

Set the collected flag for selected cat-guide entries.

| Field | Mapping |
| --- | --- |
| Original menu | `cats_special_skills > unlock_remove_cat_guide` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [cats.guide](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=cats.guide) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/cat_editor.py:719](vendor/bcsfe/src/bcsfe/cli/edits/cat_editor.py#L719) |

Original function: `bcsfe.cli.edits.cat_editor.CatEditor.unlock_cat_guide_remove_guide_run`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

<a id="save_management"></a>

## Save management and device operations

### `save_save`

| Field | Mapping |
| --- | --- |
| Original menu | `save_management > save_save` |
| Classification | `file_account` |
| Implementation | Adapted to HTTP (`adapted`) |
| Edit actions | None |
| HTTP endpoints | `POST /v2/save/download` |
| Source | [src/bcsfe/cli/save_management.py:15](vendor/bcsfe/src/bcsfe/cli/save_management.py#L15) |

Original function: `bcsfe.cli.save_management.SaveManagement.save_save`.

- The raw save is returned as a download. The browser/client chooses the destination; the server does not overwrite a path on the user device. Item synchronization and new-account creation are explicit separate requests.
- Offline action sample: not applicable to this entry's HTTP, device, or terminal behavior; see its implementation notes.

### `save_upload`

| Field | Mapping |
| --- | --- |
| Original menu | `save_management > save_upload` |
| Classification | `file_account` |
| Implementation | Implemented (`implemented`) |
| Edit actions | None |
| HTTP endpoints | `POST /v2/save/upload` |
| Source | [src/bcsfe/cli/save_management.py:66](vendor/bcsfe/src/bcsfe/cli/save_management.py#L66) |

Original function: `bcsfe.cli.save_management.SaveManagement.save_upload`.

- Uses the original transfer upload protocol. New-account creation is explicit rather than an implicit strict-ban-prevention side effect. Actual PONOS acceptance has not been tested.
- Live game-account verification: not completed for the remote operation.

### `save_save_file`

| Field | Mapping |
| --- | --- |
| Original menu | `save_management > save_save_file` |
| Classification | `file_account` |
| Implementation | Adapted to HTTP (`adapted`) |
| Edit actions | None |
| HTTP endpoints | `POST /v2/save/download` |
| Source | [src/bcsfe/cli/save_management.py:38](vendor/bcsfe/src/bcsfe/cli/save_management.py#L38) |

Original function: `bcsfe.cli.save_management.SaveManagement.save_save_dialog`.

- A download replaces the native save-file chooser. The client controls its local filename and destination.
- Offline action sample: not applicable to this entry's HTTP, device, or terminal behavior; see its implementation notes.

### `save_save_documents`

| Field | Mapping |
| --- | --- |
| Original menu | `save_management > save_save_documents` |
| Classification | `file_account` |
| Implementation | Adapted to HTTP (`adapted`) |
| Edit actions | None |
| HTTP endpoints | `POST /v2/save/download` |
| Source | [src/bcsfe/cli/save_management.py:54](vendor/bcsfe/src/bcsfe/cli/save_management.py#L54) |

Original function: `bcsfe.cli.save_management.SaveManagement.save_save_data_dir`.

- A download replaces writing directly to the desktop editor data directory.
- Offline action sample: not applicable to this entry's HTTP, device, or terminal behavior; see its implementation notes.

### `adb_push`

| Field | Mapping |
| --- | --- |
| Original menu | `save_management > adb_push` |
| Classification | `device_cli` |
| Implementation | Unavailable on Vercel (`unavailable_in_vercel`) |
| Edit actions | None |
| HTTP endpoints | None |
| Source | [src/bcsfe/cli/save_management.py:118](vendor/bcsfe/src/bcsfe/cli/save_management.py#L118) |

Original function: `bcsfe.cli.save_management.SaveManagement.adb_push`.

- ADB/root device access and restarting the game require a companion on the device host; Vercel cannot perform these physical-device operations.
- Offline action sample: not applicable to this entry's HTTP, device, or terminal behavior; see its implementation notes.

### `adb_push_rerun`

| Field | Mapping |
| --- | --- |
| Original menu | `save_management > adb_push_rerun` |
| Classification | `device_cli` |
| Implementation | Unavailable on Vercel (`unavailable_in_vercel`) |
| Edit actions | None |
| HTTP endpoints | None |
| Source | [src/bcsfe/cli/save_management.py:199](vendor/bcsfe/src/bcsfe/cli/save_management.py#L199) |

Original function: `bcsfe.cli.save_management.SaveManagement.adb_push_rerun`.

- ADB/root device access and restarting the game require a companion on the device host; Vercel cannot perform these physical-device operations.
- Offline action sample: not applicable to this entry's HTTP, device, or terminal behavior; see its implementation notes.

### `root_push`

| Field | Mapping |
| --- | --- |
| Original menu | `save_management > root_push` |
| Classification | `device_cli` |
| Implementation | Unavailable on Vercel (`unavailable_in_vercel`) |
| Edit actions | None |
| HTTP endpoints | None |
| Source | [src/bcsfe/cli/save_management.py:162](vendor/bcsfe/src/bcsfe/cli/save_management.py#L162) |

Original function: `bcsfe.cli.save_management.SaveManagement.root_push`.

- ADB/root device access and restarting the game require a companion on the device host; Vercel cannot perform these physical-device operations.
- Offline action sample: not applicable to this entry's HTTP, device, or terminal behavior; see its implementation notes.

### `root_push_rerun`

| Field | Mapping |
| --- | --- |
| Original menu | `save_management > root_push_rerun` |
| Classification | `device_cli` |
| Implementation | Unavailable on Vercel (`unavailable_in_vercel`) |
| Edit actions | None |
| HTTP endpoints | None |
| Source | [src/bcsfe/cli/save_management.py:217](vendor/bcsfe/src/bcsfe/cli/save_management.py#L217) |

Original function: `bcsfe.cli.save_management.SaveManagement.root_push_rerun`.

- ADB/root device access and restarting the game require a companion on the device host; Vercel cannot perform these physical-device operations.
- Offline action sample: not applicable to this entry's HTTP, device, or terminal behavior; see its implementation notes.

### `export_save`

| Field | Mapping |
| --- | --- |
| Original menu | `save_management > export_save` |
| Classification | `file_account` |
| Implementation | Implemented (`implemented`) |
| Edit actions | None |
| HTTP endpoints | `POST /v2/save/export` |
| Source | [src/bcsfe/cli/save_management.py:235](vendor/bcsfe/src/bcsfe/cli/save_management.py#L235) |

Original function: `bcsfe.cli.save_management.SaveManagement.export_save`.

- Offline action sample: not applicable to this entry's HTTP, device, or terminal behavior; see its implementation notes.

### `load_save`

| Field | Mapping |
| --- | --- |
| Original menu | `save_management > load_save` |
| Classification | `file_account` |
| Implementation | Adapted to HTTP (`adapted`) |
| Edit actions | None |
| HTTP endpoints | `POST /v2/save/inspect`; `POST /v2/save/import`; `POST /v2/save/from-transfer` |
| Source | [src/bcsfe/cli/save_management.py:488](vendor/bcsfe/src/bcsfe/cli/save_management.py#L488) |

Original function: `bcsfe.cli.save_management.SaveManagement.load_save`.

- File/base64, exported JSON and transfer-code reception have HTTP equivalents. Direct ADB/root loading still requires software beside the device. Receiving a transfer consumes its code.
- Live game-account verification: not completed for the remote operation.

### `convert_region`

Change the save's country code through BCSFE set_cc.

| Field | Mapping |
| --- | --- |
| Original menu | `save_management > convert_region` |
| Classification | `file_account` |
| Implementation | Adapted to HTTP (`adapted`) |
| Edit actions | [save.region](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=save.region) |
| HTTP endpoints | `POST /v2/save/edit`; `POST /v2/account/convert-region` |
| Source | [src/bcsfe/cli/save_management.py:504](vendor/bcsfe/src/bcsfe/cli/save_management.py#L504) |

Original function: `bcsfe.cli.save_management.SaveManagement.convert_save_cc`.

- save.region changes the local format/region. /v2/account/convert-region also requests fresh account credentials, as the source region conversion does. Remote creation is unverified.
- Verification: mapped typed actions have recorded offline binary examples.
- Live game-account verification: not completed for the remote operation.

### `convert_version`

Change the version used to serialize the save.

| Field | Mapping |
| --- | --- |
| Original menu | `save_management > convert_version` |
| Classification | `file_account` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [save.version](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=save.version) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/save_management.py:516](vendor/bcsfe/src/bcsfe/cli/save_management.py#L516) |

Original function: `bcsfe.cli.save_management.SaveManagement.convert_save_gv`.

- Uses the original version setter, then rejects any conversion that cannot retain a stable, complete binary round trip. Not every cross-version downgrade preserves all fields.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

<a id="items"></a>

## Resources and items

### `catfood`

Set the cat food balance.

| Field | Mapping |
| --- | --- |
| Original menu | `items > catfood` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.catfood](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.catfood) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:23](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L23) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_catfood`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `xp`

Set the XP balance.

| Field | Mapping |
| --- | --- |
| Original menu | `items > xp` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.xp](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.xp) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:41](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L41) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_xp`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `normal_tickets`

Set the normal ticket balance.

| Field | Mapping |
| --- | --- |
| Original menu | `items > normal_tickets` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.normal_tickets](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.normal_tickets) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:50](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L50) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_normal_tickets`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `rare_tickets`

Set the rare ticket balance.

| Field | Mapping |
| --- | --- |
| Original menu | `items > rare_tickets` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.rare_tickets](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.rare_tickets) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:94](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L94) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_rare_tickets`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `rare_ticket_trade_feature_name`

Prepare the original five-to-one rare-ticket trade in cat storage.

| Field | Mapping |
| --- | --- |
| Original menu | `items > rare_ticket_trade_feature_name` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.rare_ticket_trade](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.rare_ticket_trade) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/rare_ticket_trade.py:9](vendor/bcsfe/src/bcsfe/cli/edits/rare_ticket_trade.py#L9) |

Original function: `bcsfe.cli.edits.rare_ticket_trade.RareTicketTrade.rare_ticket_trade`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `platinum_tickets`

Set the platinum ticket balance.

| Field | Mapping |
| --- | --- |
| Original menu | `items > platinum_tickets` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.platinum_tickets](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.platinum_tickets) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:117](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L117) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_platinum_tickets`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `legend_tickets`

Set the legend ticket balance.

| Field | Mapping |
| --- | --- |
| Original menu | `items > legend_tickets` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.legend_tickets](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.legend_tickets) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:142](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L142) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_legend_tickets`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `platinum_shards`

Set the platinum shard count.

| Field | Mapping |
| --- | --- |
| Original menu | `items > platinum_shards` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.platinum_shards](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.platinum_shards) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:161](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L161) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_platinum_shards`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `np`

Set the NP balance.

| Field | Mapping |
| --- | --- |
| Original menu | `items > np` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.np](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.np) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:176](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L176) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_np`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `leadership`

Set the Leadership count.

| Field | Mapping |
| --- | --- |
| Original menu | `items > leadership` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.leadership](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.leadership) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:185](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L185) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_leadership`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `battle_items`

Set selected battle-item quantities.

| Field | Mapping |
| --- | --- |
| Original menu | `items > battle_items` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.battle_items](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.battle_items) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:194](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L194) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_battle_items`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `battle_items_endless`

Start or replace endless battle-item durations in minutes.

| Field | Mapping |
| --- | --- |
| Original menu | `items > battle_items_endless` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.endless](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.endless) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:198](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L198) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_battle_items_endless`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `catseyes`

Set selected Catseye quantities.

| Field | Mapping |
| --- | --- |
| Original menu | `items > catseyes` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.catseyes](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.catseyes) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:224](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L224) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_catseyes`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `catfruit`

Set selected evolution-material quantities in the catfruit array. Set evolution-material quantities, including stones, by original game item ID.

| Field | Mapping |
| --- | --- |
| Original menu | `items > catfruit` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.catfruit](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.catfruit), [items.evolve_by_id](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.evolve_by_id) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:274](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L274) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_catfruit`.

- Includes the original indexed evolution-material vector and game-item-ID access for fruits/seeds/stones; item IDs are resolved from game metadata.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `talent_orbs`

Set talent-orb inventory counts by exact orb ID or by metadata component filters.

| Field | Mapping |
| --- | --- |
| Original menu | `items > talent_orbs` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [cats.orbs](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=cats.orbs) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/catbase/talent_orbs.py:703](vendor/bcsfe/src/bcsfe/core/game/catbase/talent_orbs.py#L703) |

Original function: `bcsfe.core.game.catbase.talent_orbs.SaveOrbs.edit_talent_orbs`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `catamins`

Set selected Catamin quantities.

| Field | Mapping |
| --- | --- |
| Original menu | `items > catamins` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.catamins](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.catamins) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:202](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L202) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_catamins`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `scheme_items`

Add or remove selected scheme rewards from the pending reward list.

| Field | Mapping |
| --- | --- |
| Original menu | `items > scheme_items` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.scheme](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.scheme) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:342](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L342) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_scheme_items`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `labyrinth_medals`

Set selected labyrinth medal quantities.

| Field | Mapping |
| --- | --- |
| Original menu | `items > labyrinth_medals` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.labyrinth_medals](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.labyrinth_medals) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:370](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L370) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_labyrinth_medals`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `100_million_tickets`

Set the 100 Million Ticket count.

| Field | Mapping |
| --- | --- |
| Original menu | `items > 100_million_tickets` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.hundred_million_ticket](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.hundred_million_ticket) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:61](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L61) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_100_million_ticket`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `event_tickets`

Set event and lucky-ticket quantities by original game item ID.

| Field | Mapping |
| --- | --- |
| Original menu | `items > event_tickets` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.event_tickets](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.event_tickets) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/event_tickets.py:35](vendor/bcsfe/src/bcsfe/cli/edits/event_tickets.py#L35) |

Original function: `bcsfe.cli.edits.event_tickets.EventTickets.edit`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `treasure_chests`

Set selected treasure chest quantities.

| Field | Mapping |
| --- | --- |
| Original menu | `items > treasure_chests` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.treasure_chests](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.treasure_chests) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:247](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L247) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_treasure_chests`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `reset_golden_cat_cpus`

Set the Gold CPU count.

| Field | Mapping |
| --- | --- |
| Original menu | `items > reset_golden_cat_cpus` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.golden_cpu_count](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.golden_cpu_count) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:17](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L17) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.reset_golden_cat_cpus`.

Argument variant: `{"action": "items.golden_cpu_count", "args": {"value": 0}}`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

<a id="levels"></a>

## Stages, scores, and treasures

### `clear_tutorial`

Apply BCSFE's tutorial-completion routine explicitly.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > clear_tutorial` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.tutorial](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.tutorial) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/clear_tutorial.py:6](vendor/bcsfe/src/bcsfe/cli/edits/clear_tutorial.py#L6) |

Original function: `bcsfe.cli.edits.clear_tutorial.clear_tutorial`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `clear_story`

Set story chapter clear counts or exact chapter progress.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > clear_story` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.story](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.story) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/story.py:556](vendor/bcsfe/src/bcsfe/core/game/map/story.py#L556) |

Original function: `bcsfe.core.game.map.story.StoryChapters.clear_story`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `challenge_score`

Set the first challenge score and its completion state.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > challenge_score` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.challenge_score](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.challenge_score) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/challenge.py:74](vendor/bcsfe/src/bcsfe/core/game/map/challenge.py#L74) |

Original function: `bcsfe.core.game.map.challenge.edit_challenge_score`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `dojo_score`

Set the regular dojo's stored score.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > dojo_score` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.dojo_score](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.dojo_score) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/dojo.py:358](vendor/bcsfe/src/bcsfe/core/game/map/dojo.py#L358) |

Original function: `bcsfe.core.game.map.dojo.edit_dojo_score`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `add_enigma_stages`

Add decoded Enigma maps or replace the decoded map list.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > add_enigma_stages` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.enigma](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.enigma) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/enigma.py:220](vendor/bcsfe/src/bcsfe/core/game/map/enigma.py#L220) |

Original function: `bcsfe.core.game.map.enigma.edit_enigma`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `clear_enigma_stages`

Edit Enigma map clear counts or progress.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > clear_enigma_stages` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.enigma_clears](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.enigma_clears) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/gauntlets.py:344](vendor/bcsfe/src/bcsfe/core/game/map/gauntlets.py#L344) |

Original function: `bcsfe.core.game.map.gauntlets.GauntletChapters.edit_enigma_stages`.

- Both the source CLI and API select maps already represented in the save. API progress acts on explicitly selected crowns; source cross-crown progress/reset effects can require multiple explicit operations. Metadata placeholder stages are excluded from normal API stage selection.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `unlock_aku_realm`

Clear the original seven quests used to unlock the Aku Realm.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > unlock_aku_realm` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.unlock_aku](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.unlock_aku) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/aku_realm.py:6](vendor/bcsfe/src/bcsfe/cli/edits/aku_realm.py#L6) |

Original function: `bcsfe.cli.edits.aku_realm.unlock_aku_realm`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `story_treasures`

Set treasure levels on selected story stages or treasure groups.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > story_treasures` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.treasures](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.treasures) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/story.py:908](vendor/bcsfe/src/bcsfe/core/game/map/story.py#L908) |

Original function: `bcsfe.core.game.map.story.StoryChapters.edit_treasures`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `outbreaks`

Mark existing zombie outbreak stages cleared or uncleared.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > outbreaks` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.outbreaks](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.outbreaks) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/outbreaks.py:212](vendor/bcsfe/src/bcsfe/core/game/map/outbreaks.py#L212) |

Original function: `bcsfe.core.game.map.outbreaks.Outbreaks.edit_outbreaks`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `aku_chapters`

Set Aku Realm clear counts for selected stages or an exact prefix.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > aku_chapters` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.aku](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.aku) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/aku.py:187](vendor/bcsfe/src/bcsfe/core/game/map/aku.py#L187) |

Original function: `bcsfe.core.game.map.aku.AkuChapters.edit_aku_chapters`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `itf_timed_scores`

Set Into the Future timed scores on selected stages.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > itf_timed_scores` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.itf_scores](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.itf_scores) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/story.py:939](vendor/bcsfe/src/bcsfe/core/game/map/story.py#L939) |

Original function: `bcsfe.core.game.map.story.StoryChapters.edit_itf_timed_scores`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `filibuster_reclearing`

Enable a replay of the Filibuster stage.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > filibuster_reclearing` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.filibuster](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.filibuster) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:404](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L404) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.allow_filibuster_stage_reclearing`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `sol`

Edit Stories of Legend map clear counts or progress.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > sol` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.sol](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.sol) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/event.py:828](vendor/bcsfe/src/bcsfe/core/game/map/event.py#L828) |

Original function: `bcsfe.core.game.map.event.EventChapters.edit_sol_chapters`.

- Both the source CLI and API select maps already represented in the save. API progress acts on explicitly selected crowns; source cross-crown progress/reset effects can require multiple explicit operations. Metadata placeholder stages are excluded from normal API stage selection.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `event`

Edit event map clear counts or progress.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > event` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.event](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.event) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/event.py:832](vendor/bcsfe/src/bcsfe/core/game/map/event.py#L832) |

Original function: `bcsfe.core.game.map.event.EventChapters.edit_event_chapters`.

- Both the source CLI and API select maps already represented in the save. API progress acts on explicitly selected crowns; source cross-crown progress/reset effects can require multiple explicit operations. Metadata placeholder stages are excluded from normal API stage selection.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `collab`

Edit collaboration map clear counts or progress.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > collab` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.collab](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.collab) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/event.py:836](vendor/bcsfe/src/bcsfe/core/game/map/event.py#L836) |

Original function: `bcsfe.core.game.map.event.EventChapters.edit_collab_chapters`.

- Both the source CLI and API select maps already represented in the save. API progress acts on explicitly selected crowns; source cross-crown progress/reset effects can require multiple explicit operations. Metadata placeholder stages are excluded from normal API stage selection.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `gauntlets`

Edit Gauntlet map clear counts or progress.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > gauntlets` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.gauntlets](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.gauntlets) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/gauntlets.py:329](vendor/bcsfe/src/bcsfe/core/game/map/gauntlets.py#L329) |

Original function: `bcsfe.core.game.map.gauntlets.GauntletChapters.edit_gauntlets`.

- Both the source CLI and API select maps already represented in the save. API progress acts on explicitly selected crowns; source cross-crown progress/reset effects can require multiple explicit operations. Metadata placeholder stages are excluded from normal API stage selection.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `collab_gauntlets`

Edit collaboration Gauntlet map clear counts or progress.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > collab_gauntlets` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.collab_gauntlets](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.collab_gauntlets) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/gauntlets.py:334](vendor/bcsfe/src/bcsfe/core/game/map/gauntlets.py#L334) |

Original function: `bcsfe.core.game.map.gauntlets.GauntletChapters.edit_collab_gauntlets`.

- Both the source CLI and API select maps already represented in the save. API progress acts on explicitly selected crowns; source cross-crown progress/reset effects can require multiple explicit operations. Metadata placeholder stages are excluded from normal API stage selection.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `uncanny`

Edit Uncanny Legends map clear counts or progress.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > uncanny` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.uncanny](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.uncanny) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/uncanny.py:46](vendor/bcsfe/src/bcsfe/core/game/map/uncanny.py#L46) |

Original function: `bcsfe.core.game.map.uncanny.UncannyChapters.edit_uncanny`.

- Both the source CLI and API select maps already represented in the save. API progress acts on explicitly selected crowns; source cross-crown progress/reset effects can require multiple explicit operations. Metadata placeholder stages are excluded from normal API stage selection.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `catamin_stages`

Edit Catamin map clear counts or progress.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > catamin_stages` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.catamin](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.catamin) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/uncanny.py:117](vendor/bcsfe/src/bcsfe/core/game/map/uncanny.py#L117) |

Original function: `bcsfe.core.game.map.uncanny.UncannyChapters.edit_catamin_stages`.

- Both the source CLI and API select maps already represented in the save. API progress acts on explicitly selected crowns; source cross-crown progress/reset effects can require multiple explicit operations. Metadata placeholder stages are excluded from normal API stage selection.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `behemoth_culling`

Edit Behemoth Culling map clear counts or progress.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > behemoth_culling` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.behemoth](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.behemoth) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/gauntlets.py:339](vendor/bcsfe/src/bcsfe/core/game/map/gauntlets.py#L339) |

Original function: `bcsfe.core.game.map.gauntlets.GauntletChapters.edit_behemoth_culling`.

- Both the source CLI and API select maps already represented in the save. API progress acts on explicitly selected crowns; source cross-crown progress/reset effects can require multiple explicit operations. Metadata placeholder stages are excluded from normal API stage selection.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `legend_quest`

Edit Legend Quest map clear counts or progress.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > legend_quest` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.legend_quest](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.legend_quest) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/legend_quest.py:370](vendor/bcsfe/src/bcsfe/core/game/map/legend_quest.py#L370) |

Original function: `bcsfe.core.game.map.legend_quest.LegendQuestChapters.edit_legend_quest`.

- Both the source CLI and API select maps already represented in the save. API progress acts on explicitly selected crowns; source cross-crown progress/reset effects can require multiple explicit operations. Metadata placeholder stages are excluded from normal API stage selection.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `towers`

Edit tower map clear counts or progress.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > towers` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.towers](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.towers) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/tower.py:66](vendor/bcsfe/src/bcsfe/core/game/map/tower.py#L66) |

Original function: `bcsfe.core.game.map.tower.TowerChapters.edit_towers`.

- Both the source CLI and API select maps already represented in the save. API progress acts on explicitly selected crowns; source cross-crown progress/reset effects can require multiple explicit operations. Metadata placeholder stages are excluded from normal API stage selection.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `zero_legends`

Edit Zero Legends map clear counts or progress.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > zero_legends` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.zero_legends](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.zero_legends) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/zero_legends.py:283](vendor/bcsfe/src/bcsfe/core/game/map/zero_legends.py#L283) |

Original function: `bcsfe.core.game.map.zero_legends.ZeroLegendsChapters.edit_zero_legends`.

- Both the source CLI and API select maps already represented in the save. API progress acts on explicitly selected crowns; source cross-crown progress/reset effects can require multiple explicit operations. Metadata placeholder stages are excluded from normal API stage selection.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `dojo_catclaw_championships`

Edit Catclaw Championship map clear counts or progress.

| Field | Mapping |
| --- | --- |
| Original menu | `levels > dojo_catclaw_championships` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [stages.dojo_catclaw](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=stages.dojo_catclaw) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/map/zero_legends.py:289](vendor/bcsfe/src/bcsfe/core/game/map/zero_legends.py#L289) |

Original function: `bcsfe.core.game.map.zero_legends.ZeroLegendsChapters.edit_catclaw_championships`.

- Both the source CLI and API select maps already represented in the save. API progress acts on explicitly selected crowns; source cross-crown progress/reset effects can require multiple explicit operations. Metadata placeholder stages are excluded from normal API stage selection.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

<a id="gamototo"></a>

## Gamatoto and Ototo

### `engineers`

Set the number of Ototo construction engineers.

| Field | Mapping |
| --- | --- |
| Original menu | `gamototo > engineers` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [ototo.engineers](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=ototo.engineers) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:346](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L346) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_engineers`.

- respect_maxima=false follows the source DISABLE_MAXES option for recommended limits; metadata identities and representable storage/prompt bounds remain validated.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `base_materials`

Set construction-material quantities at selected save indexes.

| Field | Mapping |
| --- | --- |
| Original menu | `gamototo > base_materials` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [ototo.materials](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=ototo.materials) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:350](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L350) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_base_materials`.

- respect_maxima=false follows the source DISABLE_MAXES option for recommended limits; metadata identities and representable storage/prompt bounds remain validated.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `gamatoto_xp_level`

Set the raw Gamatoto expedition XP total. Convert a displayed Gamatoto level to its XP threshold using the save's game metadata.

| Field | Mapping |
| --- | --- |
| Original menu | `gamototo > gamatoto_xp_level` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [gamatoto.xp](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=gamatoto.xp), [gamatoto.level](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=gamatoto.level) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/gamoto/gamatoto.py:502](vendor/bcsfe/src/bcsfe/core/game/gamoto/gamatoto.py#L502) |

Original function: `bcsfe.core.game.gamoto.gamatoto.edit_xp`.

- respect_maxima=false follows the source DISABLE_MAXES option for recommended limits; metadata identities and representable storage/prompt bounds remain validated.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `gamatoto_helpers`

Replace the helper list or set helper counts for selected rarities.

| Field | Mapping |
| --- | --- |
| Original menu | `gamototo > gamatoto_helpers` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [gamatoto.helpers](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=gamatoto.helpers) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/gamoto/gamatoto.py:506](vendor/bcsfe/src/bcsfe/core/game/gamoto/gamatoto.py#L506) |

Original function: `bcsfe.core.game.gamoto.gamatoto.edit_helpers`.

- respect_maxima=false follows the source DISABLE_MAXES option for recommended limits; metadata identities and representable storage/prompt bounds remain validated.
- Empty helper slots (-1) are excluded from occupancy and are removed when rebuilding selected rarity groups; other occupied groups are preserved.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `ototo_cat_cannon`

Edit development state and displayed part levels for existing cannons.

| Field | Mapping |
| --- | --- |
| Original menu | `gamototo > ototo_cat_cannon` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [ototo.cannons](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=ototo.cannons) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/gamoto/ototo.py:641](vendor/bcsfe/src/bcsfe/core/game/gamoto/ototo.py#L641) |

Original function: `bcsfe.core.game.gamoto.ototo.edit_cannon`.

- respect_maxima=false follows the source DISABLE_MAXES option for recommended limits; metadata identities and representable storage/prompt bounds remain validated.
- Effect part display level 0 stores -1, matching the original editor. Development still selects only 0..3.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `cat_shrine`

Set Cat Shrine offering XP or its derived level, and optionally change shrine visibility.

| Field | Mapping |
| --- | --- |
| Original menu | `gamototo > cat_shrine` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [shrine.set](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=shrine.set) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/gamoto/cat_shrine.py:135](vendor/bcsfe/src/bcsfe/core/game/gamoto/cat_shrine.py#L135) |

Original function: `bcsfe.core.game.gamoto.cat_shrine.CatShrine.edit_catshrine`.

- Level 1 is corrected to XP 0; the source get_xp_from_level(1) incorrectly reads the final boundary. This deliberate bug fix is not byte-for-byte emulation of that defect.
- respect_maxima=false follows the source DISABLE_MAXES option for recommended limits; metadata identities and representable storage/prompt bounds remain validated.
- The original disabled-maxima XP prompt caps at signed int32, while an enabled metadata maximum can exceed int32 because the save stores signed int64 offering XP.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

<a id="account"></a>

## Account fields

### `unban_account`

| Field | Mapping |
| --- | --- |
| Original menu | `account > unban_account` |
| Classification | `account` |
| Implementation | Implemented (`implemented`) |
| Edit actions | None |
| HTTP endpoints | `POST /v2/account/new` |
| Source | [src/bcsfe/cli/save_management.py:90](vendor/bcsfe/src/bcsfe/cli/save_management.py#L90) |

Original function: `bcsfe.cli.save_management.SaveManagement.unban_account`.

- The source menu actually creates a new account; it does not reverse a server ban on the old account. New-account creation and synchronization are implemented but not live verified.
- Live game-account verification: not completed for the remote operation.

### `upload_items`

| Field | Mapping |
| --- | --- |
| Original menu | `account > upload_items` |
| Classification | `account` |
| Implementation | Implemented (`implemented`) |
| Edit actions | None |
| HTTP endpoints | `POST /v2/account/upload-items` |
| Source | [src/bcsfe/cli/save_management.py:250](vendor/bcsfe/src/bcsfe/cli/save_management.py#L250) |

Original function: `bcsfe.cli.save_management.SaveManagement.upload_items`.

- Uploads the original managed-item metadata. A false or unconfirmed upstream result is reported as failure; live account synchronization is unverified.
- Live game-account verification: not completed for the remote operation.

### `inquiry_code`

Replace the account's stored inquiry code.

| Field | Mapping |
| --- | --- |
| Original menu | `account > inquiry_code` |
| Classification | `account` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [account.inquiry_code](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=account.inquiry_code) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:321](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L321) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_inquiry_code`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `password_refresh_token`

Replace the account's stored password refresh token.

| Field | Mapping |
| --- | --- |
| Original menu | `account > password_refresh_token` |
| Classification | `account` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [account.password_refresh_token](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=account.password_refresh_token) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:332](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L332) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_password_refresh_token`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

<a id="gatya"></a>

## Gacha seeds

### `rare_gatya_seed`

Set the rare gacha seed.

| Field | Mapping |
| --- | --- |
| Original menu | `gatya > rare_gatya_seed` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [gatya.rare_seed](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=gatya.rare_seed) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:354](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L354) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_rare_gatya_seed`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `normal_gatya_seed`

Set the normal gacha seed.

| Field | Mapping |
| --- | --- |
| Original menu | `gatya > normal_gatya_seed` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [gatya.normal_seed](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=gatya.normal_seed) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:358](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L358) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_normal_gatya_seed`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `event_gatya_seed`

Set the event gacha seed.

| Field | Mapping |
| --- | --- |
| Original menu | `gatya > event_gatya_seed` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [gatya.event_seed](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=gatya.event_seed) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:362](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L362) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_event_gatya_seed`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

<a id="fixes"></a>

## Explicit repairs

### `fix_gamatoto_crash`

Apply the original Gamatoto crash repair by setting expedition skin to 2.

| Field | Mapping |
| --- | --- |
| Original menu | `fixes > fix_gamatoto_crash` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [fixes.gamatoto](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=fixes.gamatoto) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/fixes.py:9](vendor/bcsfe/src/bcsfe/cli/edits/fixes.py#L9) |

Original function: `bcsfe.cli.edits.fixes.Fixes.fix_gamatoto_crash`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `fix_ototo_crash`

Reset the cannon collection and selected parts to the original version-specific initial state.

| Field | Mapping |
| --- | --- |
| Original menu | `fixes > fix_ototo_crash` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [fixes.ototo](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=fixes.ototo) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/fixes.py:15](vendor/bcsfe/src/bcsfe/cli/edits/fixes.py#L15) |

Original function: `bcsfe.cli.edits.fixes.Fixes.fix_ototo_crash`.

- Explicitly resets the cannon collection and selected parts, matching the original repair routine.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `fix_time_errors`

Set the save's time-error fields to an explicit Unix timestamp or the current API server time.

| Field | Mapping |
| --- | --- |
| Original menu | `fixes > fix_time_errors` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [fixes.time](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=fixes.time) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/fixes.py:22](vendor/bcsfe/src/bcsfe/cli/edits/fixes.py#L22) |

Original function: `bcsfe.cli.edits.fixes.Fixes.fix_time_errors`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `unlock_equip_menu`

Unlock the equipment menu with the original save-file method.

| Field | Mapping |
| --- | --- |
| Original menu | `fixes > unlock_equip_menu`; `other > unlock_equip_menu` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [fixes.equip_menu](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=fixes.equip_menu) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:399](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L399) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.unlock_equip_menu`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `fix_officer_pass_crash`

Reset officer-cat identity, play time, and Gold Pass state using the original repair routine.

| Field | Mapping |
| --- | --- |
| Original menu | `fixes > fix_officer_pass_crash` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [fixes.officer_pass](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=fixes.officer_pass) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/catbase/officer_pass.py:75](vendor/bcsfe/src/bcsfe/core/game/catbase/officer_pass.py#L75) |

Original function: `bcsfe.core.game.catbase.officer_pass.OfficerPass.fix_crash`.

- Explicitly resets playtime, officer cat, gold-pass state and related login state, matching the repair routine. It never runs merely because another field is edited.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

<a id="other"></a>

## Rewards, collections, and other edits

### `unlocked_slots`

Set the number of unlocked lineups without changing equipped units.

| Field | Mapping |
| --- | --- |
| Original menu | `other > unlocked_slots` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [lineups.unlocked_slots](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=lineups.unlocked_slots) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:366](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L366) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.edit_unlocked_slots`.

- respect_maxima=false follows the source DISABLE_MAXES option for recommended limits; metadata identities and representable storage/prompt bounds remain validated.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `reset_gambling_events`

Reset the completion flags, values, and start dates of selected gambling events.

| Field | Mapping |
| --- | --- |
| Original menu | `other > reset_gambling_events` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [gambling.reset](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=gambling.reset) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/catbase/gambling.py:107](vendor/bcsfe/src/bcsfe/core/game/catbase/gambling.py#L107) |

Original function: `bcsfe.core.game.catbase.gambling.GamblingEvent.reset_events`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `restart_pack`

Set the restart pack count.

| Field | Mapping |
| --- | --- |
| Original menu | `other > restart_pack` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [items.restart_pack](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.restart_pack) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/basic_items.py:315](vendor/bcsfe/src/bcsfe/cli/edits/basic_items.py#L315) |

Original function: `bcsfe.cli.edits.basic_items.BasicItems.set_restart_pack`.

Argument variant: `{"action": "items.restart_pack", "args": {"value": 1}}`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `playtime`

Set the total stored play duration using frames or time components.

| Field | Mapping |
| --- | --- |
| Original menu | `other > playtime` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [playtime.set](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=playtime.set) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/catbase/playtime.py:64](vendor/bcsfe/src/bcsfe/core/game/catbase/playtime.py#L64) |

Original function: `bcsfe.core.game.catbase.playtime.edit`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `enemy_guide`

Unlock or reset enemy-guide entries selected by ID, name, or metadata validity.

| Field | Mapping |
| --- | --- |
| Original menu | `other > enemy_guide` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [enemy_guide.set](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=enemy_guide.set) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/cli/edits/enemy_editor.py:169](vendor/bcsfe/src/bcsfe/cli/edits/enemy_editor.py#L169) |

Original function: `bcsfe.cli.edits.enemy_editor.EnemyEditor.edit_enemy_guide`.

- Select internal save IDs, explicit game IDs, validity, or a name substring. Internal IDs are zero-based; game IDs subtract 2 explicitly.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `user_rank_rewards`

Set user-rank reward claim flags, or repair claims above the current calculated user rank.

| Field | Mapping |
| --- | --- |
| Original menu | `other > user_rank_rewards` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [rewards.claim](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=rewards.claim) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/catbase/user_rank_rewards.py:267](vendor/bcsfe/src/bcsfe/core/game/catbase/user_rank_rewards.py#L267) |

Original function: `bcsfe.core.game.catbase.user_rank_rewards.edit_user_rank_rewards`.

- Changes claimed flags on eligible rewards, including unclaim and fix-claimed; it does not directly grant the reward items.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `gold_pass`

Apply or remove the original Gold Pass state in the save file.

| Field | Mapping |
| --- | --- |
| Original menu | `other > gold_pass` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [account.gold_pass](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=account.gold_pass) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/catbase/nyanko_club.py:230](vendor/bcsfe/src/bcsfe/core/game/catbase/nyanko_club.py#L230) |

Original function: `bcsfe.core.game.catbase.nyanko_club.NyankoClub.edit_gold_pass`.

- Edits the local gold-pass save model using the source routine. It does not purchase, activate, or verify a server-side subscription.
- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `medals`

Add or remove medals identified by the game's medal metadata.

| Field | Mapping |
| --- | --- |
| Original menu | `other > medals` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [medals.set](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=medals.set) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/catbase/medals.py:91](vendor/bcsfe/src/bcsfe/core/game/catbase/medals.py#L91) |

Original function: `bcsfe.core.game.catbase.medals.Medals.edit_medals`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

### `missions`

Set existing missions to reward-ready, already claimed, or incomplete.

| Field | Mapping |
| --- | --- |
| Original menu | `other > missions` |
| Classification | `gameplay` |
| Implementation | Implemented (`implemented`) |
| Edit actions | [missions.set](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=missions.set) |
| HTTP endpoints | `POST /v2/save/edit` |
| Source | [src/bcsfe/core/game/catbase/mission.py:202](vendor/bcsfe/src/bcsfe/core/game/catbase/mission.py#L202) |

Original function: `bcsfe.core.game.catbase.mission.Missions.edit_missions`.

- Verification: mapped typed actions have recorded offline binary examples.
- Remote account calls are not required for this local file edit.

<a id="editor"></a>

## Editor configuration and game data

### `config`

| Field | Mapping |
| --- | --- |
| Original menu | `editor > config` |
| Classification | `editor_metadata` |
| Implementation | Adapted to HTTP (`adapted`) |
| Edit actions | None |
| HTTP endpoints | `GET /v2/editor/config` |
| Source | [src/bcsfe/core/io/config.py:469](vendor/bcsfe/src/bcsfe/core/io/config.py#L469) |

Original function: `bcsfe.core.io.config.Config.edit_config`.

- The API exposes defaults/maxima and uses explicit per-request action options. It does not offer persistent mutation of every terminal/editor preference.
- Offline action sample: not applicable to this entry's HTTP, device, or terminal behavior; see its implementation notes.

### `update_external`

| Field | Mapping |
| --- | --- |
| Original menu | `editor > update_external` |
| Classification | `editor_metadata` |
| Implementation | Not applicable to HTTP (`not_applicable_to_http`) |
| Edit actions | None |
| HTTP endpoints | None |
| Source | [src/bcsfe/core/__init__.py:359](vendor/bcsfe/src/bcsfe/core/__init__.py#L359) |

Original function: `bcsfe.core.update_external_content`.

- Terminal themes/locales and self-updating the desktop package are not exposed as HTTP save editing. The vendored source is updated through deployment.
- Offline action sample: not applicable to this entry's HTTP, device, or terminal behavior; see its implementation notes.

### `manage_game_data`

| Field | Mapping |
| --- | --- |
| Original menu | `editor > manage_game_data` |
| Classification | `editor_metadata` |
| Implementation | Adapted to HTTP (`adapted`) |
| Edit actions | None |
| HTTP endpoints | `GET /v2/metadata/versions`; `POST /v2/metadata/prepare`; `DELETE /v2/metadata/cache` |
| Source | [src/bcsfe/core/__init__.py:376](vendor/bcsfe/src/bcsfe/core/__init__.py#L376) |

Original function: `bcsfe.core.manage_game_data`.

- Available metadata versions, download preparation, and deletion of one or all verified cache versions have HTTP operations. Unknown/unverified directories are preserved; the cache is server-local and may be temporary on Vercel.
- Offline action sample: not applicable to this entry's HTTP, device, or terminal behavior; see its implementation notes.

<a id="exit"></a>

## Terminal session

### `exit`

| Field | Mapping |
| --- | --- |
| Original menu | `exit > exit` |
| Classification | `editor_cli` |
| Implementation | Not applicable to HTTP (`not_applicable_to_http`) |
| Edit actions | None |
| HTTP endpoints | None |
| Source | [src/bcsfe/cli/main.py:266](vendor/bcsfe/src/bcsfe/cli/main.py#L266) |

Original function: `bcsfe.cli.main.Main.exit_editor`.

- An HTTP request finishes on return; there is no shared interactive editor process to exit.
- Offline action sample: not applicable to this entry's HTTP, device, or terminal behavior; see its implementation notes.

## Verification limits

Every registered typed action has at least one offline real-SaveFile binary integration case. Static game tables are explicit fixtures; this is not exhaustive input coverage or live PONOS account verification.

- Actual game account reception, creation, upload and in-game acceptance remain unverified.
- Vercel cannot access a user device through ADB/root without a separate local companion.
- Terminal UI choices and host filesystem destinations are adapted to HTTP request arguments and downloads.
- Malformed or non-stable save round trips and edits that lose fields during serialization are rejected.
- The original parser/serializer and game-version branches are vendored from the provided source; supported fields still depend on the input game version.

Source: the user-supplied BCSFE source, version label `3.6.0`. The feature registry SHA-256 recorded in the inventory is `bddcc9232dbbe8ccb4cea4998df410e57588d5dea817f368ad535fdadfff063c`. [SOURCE_MANIFEST.json](vendor/bcsfe/SOURCE_MANIFEST.json) records the vendored source hashes. BCSFE is credited to fieryhenry and retains its GNU GPL-3.0-or-later license.
