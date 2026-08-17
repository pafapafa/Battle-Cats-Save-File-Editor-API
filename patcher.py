import sys
import os
import tempfile
import datetime
from typing import Optional, Dict, Any, Tuple, List

os.environ["HOME"] = tempfile.gettempdir()
os.environ["USERPROFILE"] = tempfile.gettempdir()

try:
    from bcsfe import core
    if hasattr(core, "Path"):
        def _safe_get_documents_folder(app_name: str = "bcsfe"):
            p = core.Path(os.path.join(tempfile.gettempdir(), app_name))
            p.generate_dirs()
            return p
        core.Path.get_documents_folder = _safe_get_documents_folder

    if hasattr(core, "core_data") and hasattr(core.core_data, "init_data"):
        try:
            core.core_data.init_data()
        except Exception:
            pass
except ImportError:
    core = None

INT32_MAX = 2_147_483_647
SAFE_CATFOOD_MAX = 45_000
SAFE_XP_MAX = 99_999_999

_CC_CACHE = {}
_CAT_DB_CACHE = None


def get_cat_max_forms(cat_id: int, sf=None) -> int:
    global _CAT_DB_CACHE
    try:
        cats = getattr(sf, "cats", None) if sf is not None else None
        if cats is not None and hasattr(cats, "read_nyanko_picture_book"):
            picture_book = cats.read_nyanko_picture_book(sf)
            picture_book_cat = picture_book.get_cat(cat_id) if picture_book is not None else None
            total_forms = int(getattr(picture_book_cat, "total_forms", 0))
            if total_forms > 0:
                return total_forms
    except Exception:
        pass
    try:
        if sf is not None and core is not None and hasattr(core, "Cat") and hasattr(core.Cat, "get_names"):
            names = core.Cat.get_names(cat_id, sf)
            if names:
                return len(names)
    except Exception:
        pass
    try:
        if _CAT_DB_CACHE is None:
            import json
            database_paths = [
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.json"),
                r'C:\Users\USER\Desktop\database.json',
            ]
            _CAT_DB_CACHE = {}
            for cat_db_path in database_paths:
                if os.path.exists(cat_db_path):
                    with open(cat_db_path, 'r', encoding='utf-8') as f:
                        _CAT_DB_CACHE = json.load(f)
                    break
        forms = _CAT_DB_CACHE.get(str(cat_id), [])
        valid = [x for x in forms if isinstance(x, str) and x.strip()]
        if valid:
            return len(valid)
    except Exception:
        pass
    return 3


def _get_cat_by_id(sf: Any, cat_id: int):
    cats = getattr(sf, "cats", None)
    if cats is None:
        return None
    if hasattr(cats, "get_cat_by_id"):
        return cats.get_cat_by_id(cat_id)
    cats_list = getattr(cats, "cats", [])
    if 0 <= cat_id < len(cats_list):
        return cats_list[cat_id]
    return None


def _unlock_cat(cat: Any, sf: Any) -> None:
    cat.unlocked = 1
    cat.gatya_seen = 1
    cat.catguide_collected = True
    try:
        cat.unlock(sf)
    except Exception:
        pass
    try:
        if core is not None and hasattr(core.core_data, "get_chara_drop"):
            chara_drop = core.core_data.get_chara_drop(sf)
            if chara_drop is not None:
                chara_drop.unlock_drops_from_cat_id(cat.id)
    except Exception:
        pass


def _set_cat_form(cat: Any, sf: Any, target_form: int) -> None:
    _unlock_cat(cat, sf)
    max_forms = get_cat_max_forms(cat.id, sf)

    if hasattr(cat, "set_form_true"):
        try:
            fourth = (target_form >= 3)
            cat.set_form_true(sf, max_forms, set_current_form=True, fourth_form=fourth)
            return
        except Exception:
            pass

    if max_forms == 4 and target_form >= 3:
        try:
            cat.unlock_fourth_form(sf, set_current_form=True)
        except Exception:
            cat.current_form = 3
            cat.unlocked_forms = 3
            if hasattr(cat, "fourth_form"):
                cat.fourth_form = 2
        return

    if max_forms >= 3 and target_form >= 2:
        try:
            cat.true_form(sf, set_current_form=True)
        except Exception:
            cat.current_form = 2
            cat.unlocked_forms = 3
        return

    if max_forms == 2 and target_form >= 1:
        cat.unlocked_forms = 0
        cat.current_form = 1
        return

    cat.unlocked_forms = 0
    cat.current_form = 0


def get_country_code(cc_str: str = "kr"):
    if core is None:
        return cc_str
    cc_key = (cc_str or "kr").lower()
    if cc_key in _CC_CACHE:
        return _CC_CACHE[cc_key]
    try:
        res = core.CountryCode.from_code(cc_key)
        _CC_CACHE[cc_key] = res
        return res
    except Exception:
        res = core.CountryCode.from_code("kr")
        _CC_CACHE[cc_key] = res
        return res


_DEFAULT_GV = None

def get_default_gv():
    global _DEFAULT_GV
    if _DEFAULT_GV is None and core is not None:
        try:
            _DEFAULT_GV = core.GameVersion(150500)
        except Exception:
            _DEFAULT_GV = None
    return _DEFAULT_GV


def download_ponos_save(tc: str, cc: str, country: str = "kr"):
    if core is None:
        return None, None
    try:
        country_code = get_country_code(country)
        gv = get_default_gv()
        sh, req_res = core.ServerHandler.from_codes(
            tc,
            cc,
            cc=country_code,
            gv=gv,
            print=False,
            save_backup=False,
        )
        if sh is None or getattr(sh, "save_file", None) is None:
            return None, None
        return sh.save_file, sh
    except Exception:
        return None, None


def patch_and_upload_save(
    save_file_or_bytes: Any = None,
    server_handler: Any = None,
    cc_str: str = "kr",
    catfood: Optional[int] = None,
    xp: Optional[int] = None,
    normal_tickets: Optional[int] = None,
    rare_tickets: Optional[int] = None,
    platinum_tickets: Optional[int] = None,
    legend_tickets: Optional[int] = None,
    platinum_shards: Optional[int] = None,
    np: Optional[int] = None,
    leadership: Optional[int] = None,
    catseyes: Any = None,
    catfruit: Any = None,
    behemoth_stones: Any = None,
    catamins: Any = None,
    battle_items: Any = None,
    gamatoto_level: Optional[int] = None,
    gamatoto_xp: Optional[int] = None,
    gamatoto_helpers: Any = None,
    gamatoto_helper_ids: Optional[List[int]] = None,
    gamatoto_helper_rarities: Optional[Dict[str, int]] = None,
    cat_shrine_max: bool = False,
    ototo_engineers: Optional[int] = None,
    ototo_materials: Any = None,
    base_materials: Any = None,
    unlock_cats: bool = False,
    unlock_cat_ids: Optional[List[int]] = None,
    remove_cat_ids: Optional[List[int]] = None,
    cat_levels: Any = None,
    cat_evolutions: Any = None,
    cat_forms: Any = None,
    max_cat_levels: bool = False,
    true_form_all: bool = False,
    max_cat_evolutions: bool = False,
    max_special_skills: bool = False,
    special_skills: Any = None,
    claim_all_rewards: bool = False,
    complete_missions: bool = False,
    max_all_talents: bool = False,
    max_talents: bool = False,
    cat_talents: Any = None,
    max_talent_orbs: bool = False,
    talent_orbs: Any = None,
    max_castle_development: bool = False,
    castle_development: Any = None,
    castle_levels: Any = None,
    clear_all_stages: bool = False,
    clear_chapters: Optional[List[int]] = None,
    clear_stages: Optional[List[Dict[str, int]]] = None,
    max_treasures: bool = False,
    max_chapter_treasures: Optional[List[int]] = None,
    stage_treasures: Optional[List[Dict[str, int]]] = None,
    enable_safety: bool = False,
    save_file: Any = None,
    **kwargs: Any,
) -> Tuple[Dict[str, Any], Optional[Tuple[str, str]]]:
    if enable_safety:
        if catfood is not None:
            catfood = min(catfood, SAFE_CATFOOD_MAX)
        if xp is not None:
            xp = min(xp, SAFE_XP_MAX)

    sh = server_handler or kwargs.get("sh")
    sf = save_file or save_file_or_bytes or getattr(sh, "save_file", None) or kwargs.get("sf")

    if sh is None or sf is None:
        return {}, None

    res = {
        "original_catfood": getattr(sf, "catfood", 0),
        "original_xp": getattr(sf, "xp", 0),
    }

    # BackupMetaData helper for managed items in BCSFE
    backup_meta = None
    if core is not None and hasattr(core, "BackupMetaData"):
        try:
            backup_meta = core.BackupMetaData(sf)
        except Exception:
            backup_meta = None

    # Catfood
    if catfood is not None:
        try:
            orig_cf = sf.catfood
            sf.catfood = max(0, min(int(catfood), INT32_MAX))
            res["new_catfood"] = sf.catfood
            if backup_meta and hasattr(core, "ManagedItem") and hasattr(core, "ManagedItemType"):
                try:
                    backup_meta.add_managed_item(
                        core.ManagedItem.from_change(sf.catfood - orig_cf, core.ManagedItemType.CATFOOD)
                    )
                except Exception:
                    pass
        except Exception:
            pass

    # XP
    if xp is not None:
        try:
            sf.xp = max(0, min(int(xp), INT32_MAX))
            res["new_xp"] = sf.xp
        except Exception:
            pass

    # Normal Tickets
    if normal_tickets is not None and hasattr(sf, "normal_tickets"):
        try:
            sf.normal_tickets = max(0, min(int(normal_tickets), INT32_MAX))
            res["new_normal_tickets"] = sf.normal_tickets
        except Exception:
            pass

    # Rare Tickets
    if rare_tickets is not None:
        try:
            orig_rt = sf.rare_tickets
            sf.rare_tickets = max(0, min(int(rare_tickets), INT32_MAX))
            res["new_rare_tickets"] = sf.rare_tickets
            if backup_meta and hasattr(core, "ManagedItem") and hasattr(core, "ManagedItemType"):
                try:
                    backup_meta.add_managed_item(
                        core.ManagedItem.from_change(sf.rare_tickets - orig_rt, core.ManagedItemType.RARE_TICKET)
                    )
                except Exception:
                    pass
        except Exception:
            pass

    # Platinum Tickets
    if platinum_tickets is not None:
        try:
            orig_pt = sf.platinum_tickets
            sf.platinum_tickets = max(0, min(int(platinum_tickets), INT32_MAX))
            res["new_platinum_tickets"] = sf.platinum_tickets
            if backup_meta and hasattr(core, "ManagedItem") and hasattr(core, "ManagedItemType"):
                try:
                    backup_meta.add_managed_item(
                        core.ManagedItem.from_change(sf.platinum_tickets - orig_pt, core.ManagedItemType.PLATINUM_TICKET)
                    )
                except Exception:
                    pass
        except Exception:
            pass

    # Legend Tickets
    if legend_tickets is not None:
        try:
            orig_lt = sf.legend_tickets
            sf.legend_tickets = max(0, min(int(legend_tickets), INT32_MAX))
            res["new_legend_tickets"] = sf.legend_tickets
            if backup_meta and hasattr(core, "ManagedItem") and hasattr(core, "ManagedItemType"):
                try:
                    backup_meta.add_managed_item(
                        core.ManagedItem.from_change(sf.legend_tickets - orig_lt, core.ManagedItemType.LEGEND_TICKET)
                    )
                except Exception:
                    pass
        except Exception:
            pass

    # Platinum Shards
    if platinum_shards is not None and hasattr(sf, "platinum_shards"):
        try:
            sf.platinum_shards = max(0, min(int(platinum_shards), INT32_MAX))
            res["new_platinum_shards"] = sf.platinum_shards
        except Exception:
            pass

    # NP
    if np is not None and hasattr(sf, "np"):
        try:
            sf.np = max(0, min(int(np), INT32_MAX))
            res["new_np"] = sf.np
        except Exception:
            pass

    # Leadership
    if leadership is not None and hasattr(sf, "leadership"):
        try:
            sf.leadership = max(0, min(int(leadership), 32767))
            res["new_leadership"] = sf.leadership
        except Exception:
            pass

    # Catseyes
    if catseyes is not None and hasattr(sf, "catseyes"):
        try:
            if isinstance(catseyes, dict):
                ex_val = int(catseyes.get("ex", catseyes.get("special", 0)))
                rare_val = int(catseyes.get("rare", 0))
                sr_val = int(catseyes.get("super_rare", catseyes.get("super", 0)))
                ur_val = int(catseyes.get("uber_rare", catseyes.get("uber", 0)))
                leg_val = int(catseyes.get("legend", 0))
                dark_val = int(catseyes.get("dark", 0))
                catseyes_list = [ex_val, rare_val, sr_val, ur_val, leg_val, dark_val]
                sf.catseyes = [max(0, min(x, INT32_MAX)) for x in catseyes_list]
            elif isinstance(catseyes, list):
                sf.catseyes = [max(0, min(int(x), INT32_MAX)) for x in catseyes]
            else:
                val = max(0, min(int(catseyes), INT32_MAX))
                sf.catseyes = [val] * 6
            res["new_catseyes"] = sf.catseyes
        except Exception:
            pass

    # Catfruit & Seeds (개다래 열매 및 씨앗: 인덱스 0~17)
    if catfruit is not None and hasattr(sf, "catfruit"):
        try:
            while len(sf.catfruit) < 30:
                sf.catfruit.append(0)
            if isinstance(catfruit, list):
                for idx, val in enumerate(catfruit):
                    if idx < 18:
                        sf.catfruit[idx] = max(0, min(int(val), INT32_MAX))
            else:
                val = max(0, min(int(catfruit), INT32_MAX))
                for i in range(18):
                    sf.catfruit[i] = val
            res["new_catfruit"] = sf.catfruit[:18]
        except Exception:
            pass

    # Behemoth Stones & Gems (수석 및 수석 결정: 인덱스 18~29)
    if behemoth_stones is not None and hasattr(sf, "catfruit"):
        try:
            while len(sf.catfruit) < 30:
                sf.catfruit.append(0)
            if isinstance(behemoth_stones, list):
                for idx, val in enumerate(behemoth_stones):
                    if 18 + idx < len(sf.catfruit):
                        sf.catfruit[18 + idx] = max(0, min(int(val), INT32_MAX))
            else:
                val = max(0, min(int(behemoth_stones), INT32_MAX))
                for i in range(18, min(30, len(sf.catfruit))):
                    sf.catfruit[i] = val
            res["new_behemoth_stones"] = sf.catfruit[18:]
        except Exception:
            pass

    # Catamins (비타민 A, B, C)
    if catamins is not None and hasattr(sf, "catamins"):
        try:
            if isinstance(catamins, dict):
                a_val = int(catamins.get("a", catamins.get("catamins_a", 0)))
                b_val = int(catamins.get("b", catamins.get("catamins_b", 0)))
                c_val = int(catamins.get("c", catamins.get("catamins_c", 0)))
                sf.catamins = [max(0, min(x, INT32_MAX)) for x in [a_val, b_val, c_val]]
            elif isinstance(catamins, list):
                sf.catamins = [max(0, min(int(x), INT32_MAX)) for x in catamins]
            else:
                val = max(0, min(int(catamins), INT32_MAX))
                sf.catamins = [val] * 3
            res["new_catamins"] = sf.catamins
        except Exception:
            pass

    # Battle Items (6종 배틀 아이템)
    if battle_items is not None and hasattr(sf, "battle_items") and hasattr(sf.battle_items, "items"):
        try:
            val = max(0, min(int(battle_items), INT32_MAX))
            for item in sf.battle_items.items:
                if hasattr(item, "amount"):
                    item.amount = val
                elif hasattr(item, "set_amount"):
                    item.set_amount(val)
            res["new_battle_items"] = val
        except Exception:
            pass

    # Gamatoto Level & XP (Level 130 만렙 = 100,104,200 XP)
    if (gamatoto_level is not None or gamatoto_xp is not None) and hasattr(sf, "gamatoto") and sf.gamatoto:
        try:
            if hasattr(sf.gamatoto, "skin"):
                sf.gamatoto.skin = 2
            if gamatoto_xp is not None:
                sf.gamatoto.xp = max(0, min(int(gamatoto_xp), INT32_MAX))
                res["new_gamatoto_xp"] = sf.gamatoto.xp
            elif gamatoto_level is not None:
                lvl = max(1, min(int(gamatoto_level), 130))
                try:
                    gl = core.core_data.get_gamatoto_levels(sf)
                    xp = gl.get_xp_from_level(lvl)
                    if xp is not None:
                        sf.gamatoto.xp = xp
                    else:
                        sf.gamatoto.xp = 100104200 if lvl >= 130 else lvl * 100000
                except Exception:
                    sf.gamatoto.xp = 100104200 if lvl >= 130 else lvl * 100000
                res["new_gamatoto_level"] = lvl
        except Exception:
            pass

    # Gamatoto Helpers / Members
    if (gamatoto_helpers or gamatoto_helper_ids or gamatoto_helper_rarities) and hasattr(sf, "gamatoto") and sf.gamatoto:
        try:
            from bcsfe.core.game.gamoto.gamatoto import Helper, Helpers
            members_name = core.core_data.get_gamatoto_members_name(sf)
            r2_members = members_name.get_all_rarity(2) or []
            r1_members = members_name.get_all_rarity(1) or []
            r0_members = members_name.get_all_rarity(0) or []

            new_helpers = []

            if isinstance(gamatoto_helpers, list):
                r2_idx, r1_idx, r0_idx = 0, 0, 0
                for item in gamatoto_helpers[:10]:
                    val = str(item).lower()
                    if any(k in val for k in ["gold", "legend", "master", "grandmaster", "senior", "superior", "top", "2"]):
                        if r2_members:
                            new_helpers.append(Helper(r2_members[r2_idx % len(r2_members)].member_id))
                            r2_idx += 1
                    elif any(k in val for k in ["silver", "rare", "apprentice", "middle", "medium", "1"]):
                        if r1_members:
                            new_helpers.append(Helper(r1_members[r1_idx % len(r1_members)].member_id))
                            r1_idx += 1
                    else:
                        if r0_members:
                            new_helpers.append(Helper(r0_members[r0_idx % len(r0_members)].member_id))
                            r0_idx += 1
            elif gamatoto_helper_ids and isinstance(gamatoto_helper_ids, list):
                for hid in gamatoto_helper_ids[:10]:
                    new_helpers.append(Helper(int(hid)))
            elif gamatoto_helper_rarities and isinstance(gamatoto_helper_rarities, dict) or isinstance(gamatoto_helpers, dict):
                h_dict = gamatoto_helper_rarities if isinstance(gamatoto_helper_rarities, dict) else gamatoto_helpers
                count_r2 = int(h_dict.get("gold", h_dict.get("legend", h_dict.get("rarity_2", 0))))
                count_r1 = int(h_dict.get("silver", h_dict.get("rare", h_dict.get("rarity_1", 0))))
                count_r0 = int(h_dict.get("bronze", h_dict.get("white", h_dict.get("common", h_dict.get("rarity_0", 0)))))

                for i in range(min(count_r2, len(r2_members))):
                    if len(new_helpers) < 10:
                        new_helpers.append(Helper(r2_members[i].member_id))
                for i in range(min(count_r1, len(r1_members))):
                    if len(new_helpers) < 10:
                        new_helpers.append(Helper(r1_members[i].member_id))
                for i in range(min(count_r0, len(r0_members))):
                    if len(new_helpers) < 10:
                        new_helpers.append(Helper(r0_members[i].member_id))
            else:
                rarity_idx = 2
                if isinstance(gamatoto_helpers, str):
                    h_str = gamatoto_helpers.lower()
                    if "silver" in h_str or "rare" in h_str:
                        rarity_idx = 1
                    elif "white" in h_str or "bronze" in h_str or "common" in h_str:
                        rarity_idx = 0

                members = members_name.get_all_rarity(rarity_idx) or r2_members
                if members:
                    for i in range(min(10, len(members))):
                        new_helpers.append(Helper(members[i].member_id))

            if new_helpers:
                sf.gamatoto.helpers = Helpers(new_helpers)
                res["gamatoto_helpers_updated"] = len(new_helpers)
        except Exception:
            pass

    # Cat Shrine (냥코 신사)
    if (cat_shrine_max or claim_all_rewards or kwargs.get("cat_shrine")) and hasattr(sf, "cat_shrine") and sf.cat_shrine:
        try:
            sf.cat_shrine.xp_offering = 300000000
            sf.cat_shrine.dialogs = 9
            res["cat_shrine_maxed"] = True
        except Exception:
            pass

    # Ototo Engineers & Base Materials
    m_val = ototo_materials if ototo_materials is not None else base_materials
    if (ototo_engineers is not None or m_val is not None) and hasattr(sf, "ototo") and sf.ototo:
        try:
            if ototo_engineers is not None:
                sf.ototo.engineers = max(0, min(int(ototo_engineers), 10))
                res["new_ototo_engineers"] = sf.ototo.engineers
            if m_val is not None and hasattr(sf.ototo, "base_materials") and sf.ototo.base_materials:
                existing_mats = getattr(sf.ototo.base_materials, "materials", [])
                if isinstance(m_val, list):
                    int_vals = [max(0, min(int(x), INT32_MAX)) for x in m_val]
                elif isinstance(m_val, dict):
                    int_vals = [getattr(m, "amount", m) if not isinstance(m, int) else m for m in existing_mats]
                    if len(int_vals) < 24:
                        int_vals.extend([0] * (24 - len(int_vals)))
                    for i, (k, v) in enumerate(m_val.items()):
                        if i < len(int_vals):
                            int_vals[i] = max(0, min(int(v), INT32_MAX))
                else:
                    val = max(0, min(int(m_val), INT32_MAX))
                    curr_len = max(len(existing_mats), 24)
                    int_vals = [val] * curr_len

                try:
                    from bcsfe.core.game.gamoto.base_materials import Material as BMaterial
                except Exception:
                    BMaterial = None

                new_mat_objs = []
                for idx, v in enumerate(int_vals):
                    if idx < len(existing_mats) and hasattr(existing_mats[idx], "amount"):
                        existing_mats[idx].amount = v
                        new_mat_objs.append(existing_mats[idx])
                    elif BMaterial is not None:
                        new_mat_objs.append(BMaterial(v))
                    else:
                        new_mat_objs.append(v)
                sf.ototo.base_materials.materials = new_mat_objs
                res["new_base_materials"] = int_vals
        except Exception:
            pass

    # Special Skills / Base Upgrades (파란 구슬 / 대포 공격력, 지갑 등 10종)
    if (max_special_skills or special_skills is not None) and hasattr(sf, "special_skills") and sf.special_skills:
        try:
            ability_data = core.core_data.get_ability_data(sf) if hasattr(core.core_data, "get_ability_data") else None
            if max_special_skills:
                for skill_id in range(10):
                    max_base = ability_data.ability_data[skill_id].max_base_level - 1 if ability_data and ability_data.ability_data and skill_id < len(ability_data.ability_data) else 19
                    max_plus = ability_data.ability_data[skill_id].max_plus_level if ability_data and ability_data.ability_data and skill_id < len(ability_data.ability_data) else 10
                    sf.special_skills.set_upgrade(skill_id, core.Upgrade(max_plus, max_base), max_base=max_base, max_plus=max_plus)
                res["max_special_skills"] = True
            if special_skills is not None:
                if isinstance(special_skills, dict):
                    for k, v in special_skills.items():
                        try:
                            sid = int(k)
                            max_base = ability_data.ability_data[sid].max_base_level - 1 if ability_data and ability_data.ability_data and sid < len(ability_data.ability_data) else 19
                            max_plus = ability_data.ability_data[sid].max_plus_level if ability_data and ability_data.ability_data and sid < len(ability_data.ability_data) else 10
                            if isinstance(v, dict):
                                base_lvl = int(v.get("base", v.get("level", 20))) - 1
                                plus_lvl = int(v.get("plus", 10))
                            elif isinstance(v, (list, tuple)) and len(v) >= 2:
                                base_lvl = int(v[0]) - 1
                                plus_lvl = int(v[1])
                            else:
                                base_lvl = int(v) - 1
                                plus_lvl = 10
                            sf.special_skills.set_upgrade(sid, core.Upgrade(max(0, min(plus_lvl, max_plus)), max(0, min(base_lvl, max_base))), max_base=max_base, max_plus=max_plus)
                        except Exception:
                            pass
                elif isinstance(special_skills, (int, float)):
                    lvl = int(special_skills)
                    for skill_id in range(10):
                        max_base = ability_data.ability_data[skill_id].max_base_level - 1 if ability_data and ability_data.ability_data and skill_id < len(ability_data.ability_data) else 19
                        max_plus = ability_data.ability_data[skill_id].max_plus_level if ability_data and ability_data.ability_data and skill_id < len(ability_data.ability_data) else 10
                        sf.special_skills.set_upgrade(skill_id, core.Upgrade(max_plus, max(0, min(lvl - 1, max_base))), max_base=max_base, max_plus=max_plus)
                res["special_skills_updated"] = True
        except Exception:
            pass

    # Claim All Rewards / Complete Missions / User Rank / Medals (Crash-safe)
    if (claim_all_rewards or complete_missions) and hasattr(sf, "missions") and sf.missions:
        try:
            conditions = core.core_data.get_mission_conditions(sf) if hasattr(core.core_data, "get_mission_conditions") else None
            for mid in list(getattr(sf.missions, "clear_states", {}).keys()):
                # Only modify existing missions in the save file to prevent client crash
                sf.missions.clear_states[mid] = 2  # 2 = 달성 완료 상태 (안전하게 인게임에서 수령 가능)
                if conditions and hasattr(conditions, "get_condition"):
                    cond = conditions.get_condition(mid)
                    if cond:
                        sf.missions.requirements[mid] = cond.progress_count
            res["missions_completed"] = True
        except Exception:
            pass

    if (claim_all_rewards or kwargs.get("user_rank_rewards")) and hasattr(sf, "user_rank_rewards") and sf.user_rank_rewards:
        try:
            user_rank = sf.calculate_user_rank()
            rank_gifts = core.core_data.get_rank_gifts(sf) if hasattr(core.core_data, "get_rank_gifts") else None
            if rank_gifts and rank_gifts.rank_gift:
                for rank_gift in rank_gifts.rank_gift:
                    if rank_gift.index < len(sf.user_rank_rewards.rewards):
                        sf.user_rank_rewards.rewards[rank_gift.index].claimed = (rank_gift.threshold <= user_rank)
            res["user_rank_rewards_claimed"] = True
        except Exception:
            pass

    if hasattr(sf, "officer_pass") and sf.officer_pass:
        try:
            # Reset officer pass / gold pass to clean state to fix crash
            sf.officer_pass.reset(sf)
        except Exception:
            pass

    # Talents & Ultra Talents (본능 / 초본능)
    if (max_all_talents or max_talents or cat_talents) and hasattr(sf, "cats") and sf.cats:
        try:
            talent_data = sf.cats.read_talent_data(sf) if hasattr(sf.cats, "read_talent_data") else None
            from bcsfe.core.game.catbase.cat import Talent
            if max_all_talents or max_talents:
                t_count = 0
                for cat in getattr(sf.cats, "cats", []):
                    if getattr(cat, "unlocked", False):
                        cat_skill = talent_data.get_cat_skill(cat.id) if talent_data else None
                        if cat_skill and hasattr(cat_skill, "skills"):
                            if getattr(cat, "talents", None) is None:
                                cat.talents = []
                            for skill in cat_skill.skills:
                                talent = cat.get_talent_from_id(skill.ability_id) if hasattr(cat, "get_talent_from_id") else None
                                max_lv = skill.max_lv if skill.max_lv > 0 else 1
                                if talent is None:
                                    cat.talents.append(Talent(skill.ability_id, max_lv))
                                else:
                                    talent.level = max_lv
                            t_count += 1
                res["max_talents_cats_count"] = t_count

            if cat_talents:
                items = cat_talents if isinstance(cat_talents, list) else [cat_talents]
                if isinstance(cat_talents, dict) and "cat_id" not in cat_talents and "id" not in cat_talents:
                    items = [{"id": k, "talents": v} for k, v in cat_talents.items()]
                for item in items:
                    if isinstance(item, dict):
                        cid = int(item.get("id", item.get("cat_id", 0)))
                        cat = _get_cat_by_id(sf, cid)
                        if cat:
                            _unlock_cat(cat, sf)
                            if getattr(cat, "talents", None) is None:
                                cat.talents = []
                            t_levels = item.get("talents", item.get("levels", []))
                            cat_skill = talent_data.get_cat_skill(cat.id) if talent_data else None
                            if isinstance(t_levels, list):
                                for tidx, tlvl in enumerate(t_levels):
                                    if cat_skill and tidx < len(cat_skill.skills):
                                        ab_id = cat_skill.skills[tidx].ability_id
                                        talent = cat.get_talent_from_id(ab_id)
                                        if talent is None:
                                            cat.talents.append(Talent(ab_id, int(tlvl)))
                                        else:
                                            talent.level = int(tlvl)
                                    elif tidx < len(cat.talents):
                                        cat.talents[tidx].level = int(tlvl)
                            elif isinstance(t_levels, dict):
                                for tid, tlvl in t_levels.items():
                                    talent = cat.get_talent_from_id(int(tid))
                                    if talent is None:
                                        cat.talents.append(Talent(int(tid), int(tlvl)))
                                    else:
                                        talent.level = int(tlvl)
                            elif isinstance(t_levels, (int, float)):
                                if cat_skill:
                                    for skill in cat_skill.skills:
                                        talent = cat.get_talent_from_id(skill.ability_id)
                                        if talent is None:
                                            cat.talents.append(Talent(skill.ability_id, int(t_levels)))
                                        else:
                                            talent.level = int(t_levels)
                res["cat_talents_updated"] = True
        except Exception:
            pass

    # Talent Orbs (본능 구슬)
    if (max_talent_orbs or talent_orbs) and hasattr(sf, "talent_orbs") and sf.talent_orbs:
        try:
            if max_talent_orbs:
                orb_info_list = core.game.catbase.talent_orbs.OrbInfoList.create(sf) if hasattr(core.game.catbase.talent_orbs, "OrbInfoList") else None
                if orb_info_list and orb_info_list.orb_info_list:
                    for orb in orb_info_list.orb_info_list:
                        sf.talent_orbs.set_orb(orb.raw_orb_info.orb_id, 99)
                res["max_talent_orbs"] = True

            if talent_orbs:
                if isinstance(talent_orbs, dict):
                    for oid, val in talent_orbs.items():
                        sf.talent_orbs.set_orb(int(oid), max(0, min(int(val), 999)))
                elif isinstance(talent_orbs, list):
                    for item in talent_orbs:
                        if isinstance(item, dict):
                            oid = int(item.get("id", item.get("orb_id", 0)))
                            val = int(item.get("amount", item.get("value", 99)))
                            sf.talent_orbs.set_orb(oid, max(0, min(val, 999)))
                        elif isinstance(item, (list, tuple)) and len(item) >= 2:
                            sf.talent_orbs.set_orb(int(item[0]), max(0, min(int(item[1]), 999)))
                elif isinstance(talent_orbs, (int, float)):
                    val = max(0, min(int(talent_orbs), 999))
                    for orb_id in range(250):
                        sf.talent_orbs.set_orb(orb_id, val)
                res["talent_orbs_updated"] = True
        except Exception:
            pass

    # Castle Development & Castle Skins & Cannons (오토토 개발대 성 개발 및 성 스킨)
    if (max_castle_development or castle_development or castle_levels) and hasattr(sf, "ototo") and sf.ototo:
        try:
            if getattr(sf.ototo, "cannons", None) is None:
                gv = getattr(sf, "game_version", None) or core.GameVersion(150400)
                from bcsfe.core.game.gamoto.ototo import Cannons
                sf.ototo.cannons = Cannons.init(gv)

            from bcsfe.core.game.gamoto.ototo import Cannon

            if max_castle_development:
                sf.ototo.engineers = 10
                if hasattr(sf.ototo, "base_materials") and sf.ototo.base_materials:
                    existing_mats = getattr(sf.ototo.base_materials, "materials", [])
                    try:
                        from bcsfe.core.game.gamoto.base_materials import Material as BMaterial
                    except Exception:
                        BMaterial = None
                    new_mat_objs = []
                    for idx in range(max(len(existing_mats), 24)):
                        if idx < len(existing_mats) and hasattr(existing_mats[idx], "amount"):
                            existing_mats[idx].amount = 9999
                            new_mat_objs.append(existing_mats[idx])
                        elif BMaterial is not None:
                            new_mat_objs.append(BMaterial(9999))
                        else:
                            new_mat_objs.append(9999)
                    sf.ototo.base_materials.materials = new_mat_objs
                for cid in list(sf.ototo.cannons.cannons.keys()):
                    if cid < 1 or cid > 7:
                        del sf.ototo.cannons.cannons[cid]
                for cid in range(1, 8):
                    cannon = sf.ototo.cannons.cannons.get(cid)
                    if cannon is None:
                        sf.ototo.cannons.cannons[cid] = Cannon(3, [20, 20, 20])
                    else:
                        cannon.development = 3
                        cannon.levels = [20, 20, 20]
                res["max_castle_development"] = True

            if castle_development is not None and getattr(sf.ototo, "cannons", None) and sf.ototo.cannons.cannons:
                if isinstance(castle_development, dict):
                    for cid, dev in castle_development.items():
                        c = sf.ototo.cannons.cannons.get(int(cid))
                        if c:
                            c.development = max(0, min(int(dev), 3))
                elif isinstance(castle_development, (int, float)):
                    dev_val = max(0, min(int(castle_development), 3))
                    for cid in range(10):
                        c = sf.ototo.cannons.cannons.get(cid)
                        if c:
                            c.development = dev_val
                res["castle_development_updated"] = True

            if castle_levels is not None and getattr(sf.ototo, "cannons", None) and sf.ototo.cannons.cannons:
                if isinstance(castle_levels, dict):
                    for cid, lvls in castle_levels.items():
                        c = sf.ototo.cannons.cannons.get(int(cid))
                        if c and isinstance(lvls, list):
                            c.levels = [max(0, int(x)) for x in lvls]
                res["castle_levels_updated"] = True
        except Exception:
            pass

    # Unlock All Cats (Only Obtainable Cats in this game version to prevent crashes)
    if unlock_cats and hasattr(sf, "cats"):
        try:
            try:
                sf.unlock_equip_menu()
            except Exception:
                pass
            try:
                if core is not None and hasattr(core, "StoryChapters"):
                    core.StoryChapters.clear_tutorial(sf)
            except Exception:
                pass
            obtainable_cats = sf.cats.get_cats_obtainable(sf) if hasattr(sf.cats, "get_cats_obtainable") else None
            if obtainable_cats is not None:
                for cat in obtainable_cats:
                    _unlock_cat(cat, sf)
            else:
                for cat in getattr(sf.cats, "cats", []):
                    _unlock_cat(cat, sf)
            unobtainable = sf.cats.get_cats_non_obtainable(sf) if hasattr(sf.cats, "get_cats_non_obtainable") else None
            if unobtainable:
                for cat in unobtainable:
                    cat.unlocked = 0
                    cat.gatya_seen = 0
            res["unlock_cats"] = True
        except Exception:
            pass

    # Apply official BCSFE Gamatoto crash fix
    if hasattr(sf, "gamatoto") and sf.gamatoto:
        sf.gamatoto.skin = 2

    # Unlock Specific Cat IDs
    if unlock_cat_ids and hasattr(sf, "cats"):
        count = 0
        try:
            for cid in unlock_cat_ids:
                try:
                    cid = int(cid)
                    cat = _get_cat_by_id(sf, cid)
                    if cat:
                        _unlock_cat(cat, sf)
                        count += 1
                except Exception:
                    pass
            res["unlocked_cat_ids_count"] = count
        except Exception:
            pass

    # Remove Specific Cat IDs
    if remove_cat_ids and hasattr(sf, "cats"):
        count = 0
        try:
            for cid in remove_cat_ids:
                try:
                    cid = int(cid)
                    cat = _get_cat_by_id(sf, cid)
                    if cat:
                        cat.unlocked = 0
                        cat.gatya_seen = 0
                        try:
                            cat.remove(reset=True, save_file=sf)
                        except Exception:
                            pass
                        count += 1
                except Exception:
                    pass
            res["removed_cat_ids_count"] = count
        except Exception:
            pass

    # Cat Levels & Upgrades
    if (cat_levels or max_cat_levels) and hasattr(sf, "cats"):
        count = 0
        try:
            if max_cat_levels:
                for cat in getattr(sf.cats, "cats", []):
                    if getattr(cat, "unlocked", False):
                        try:
                            power_up = core.PowerUpHelper(cat, sf)
                            max_base = power_up.get_max_max_base_upgrade_level() - 1
                            max_plus = power_up.get_max_max_plus_upgrade_level()
                            cat.set_upgrade(sf, core.Upgrade(max_plus, max_base), True)
                        except Exception:
                            if hasattr(cat, "upgrade") and cat.upgrade:
                                cat.upgrade = core.Upgrade(0, 49)
                        count += 1
                res["max_cat_levels_count"] = count

            if cat_levels:
                items = cat_levels if isinstance(cat_levels, list) else [cat_levels]
                if isinstance(cat_levels, dict):
                    items = [{"id": k, **(v if isinstance(v, dict) else {"level": v})} for k, v in cat_levels.items()]
                for item in items:
                    if isinstance(item, dict):
                        cid = int(item.get("id", item.get("cat_id", 0)))
                        lvl = int(item.get("level", item.get("upgrade", 50)))
                        plus = int(item.get("plus_level", item.get("plus", 0)))
                        cat = _get_cat_by_id(sf, cid)
                        if cat:
                            _unlock_cat(cat, sf)
                            if hasattr(cat, "upgrade") and cat.upgrade:
                                cat.upgrade = core.Upgrade(max(0, min(plus, 100)), max(0, min(lvl - 1, 99)))
                            count += 1
                res["updated_cat_levels_count"] = count
        except Exception:
            pass

    # Cat Evolutions & Forms
    evo_data = cat_evolutions if cat_evolutions is not None else cat_forms
    if (evo_data or true_form_all or max_cat_evolutions) and hasattr(sf, "cats"):
        count = 0
        try:
            if true_form_all or max_cat_evolutions:
                unlocked_cats = sf.cats.get_unlocked_cats() if hasattr(sf.cats, "get_unlocked_cats") else getattr(sf.cats, "cats", [])
                if hasattr(sf.cats, "fourth_form_cats"):
                    sf.cats.fourth_form_cats(sf, unlocked_cats, force=False, set_current_forms=True)
                elif hasattr(sf.cats, "true_form_cats"):
                    sf.cats.true_form_cats(sf, unlocked_cats, force=False, set_current_forms=True)
                else:
                    for cat in unlocked_cats:
                        max_forms = get_cat_max_forms(cat.id, sf)
                        _set_cat_form(cat, sf, max(0, max_forms - 1))
                count = len(unlocked_cats)
                res["max_cat_evolutions_count"] = count

            if evo_data:
                items = evo_data if isinstance(evo_data, list) else [evo_data]
                if isinstance(evo_data, dict):
                    items = [{"id": k, "form": v} for k, v in evo_data.items()]
                for item in items:
                    if isinstance(item, dict):
                        cid = int(item.get("id", item.get("cat_id", 0)))
                        form_val = int(item.get("form", item.get("evolution", 3)))
                        cat = _get_cat_by_id(sf, cid)
                        if cat:
                            max_forms = get_cat_max_forms(cid, sf)
                            target_form = max(0, min(form_val - 1, max_forms - 1))
                            _set_cat_form(cat, sf, target_form)
                            count += 1
                res["updated_cat_evolutions_count"] = count
        except Exception:
            pass

    def _get_story_chapters(save_f):
        if not hasattr(save_f, "story") or not save_f.story:
            return []
        if hasattr(save_f.story, "get_real_chapters"):
            return save_f.story.get_real_chapters()
        if hasattr(save_f.story, "chapters"):
            return save_f.story.chapters
        return []

    def _get_story_stage_count(chapter):
        try:
            if hasattr(chapter, "get_valid_treasure_stages"):
                return len(chapter.get_valid_treasure_stages())
        except Exception:
            pass
        return min(len(getattr(chapter, "stages", [])), 48)

    def _clear_story_stage(chapter, stage_id, clear_amount=1):
        stage_count = _get_story_stage_count(chapter)
        if not 0 <= stage_id < stage_count:
            return False
        try:
            chapter.clear_stage(stage_id, clear_amount)
            return True
        except Exception:
            pass
        try:
            chapter.stages[stage_id].clear_stage(clear_amount)
            if hasattr(chapter, "progress"):
                chapter.progress = max(int(chapter.progress), stage_id + 1)
            return True
        except Exception:
            return False

    def _clear_story_chapter(chapter, clear_amount=1):
        stage_count = _get_story_stage_count(chapter)
        cleared = 0
        for stage_id in range(stage_count):
            if _clear_story_stage(chapter, stage_id, clear_amount):
                cleared += 1
        return cleared == stage_count and stage_count > 0

    def _get_aku_chapters(save_f):
        result = []
        aku = getattr(save_f, "aku", None)
        for chapter_stars in getattr(aku, "chapters", []) if aku is not None else []:
            result.extend(getattr(chapter_stars, "chapters", []))
        return result

    def _clear_aku_chapter(chapter, clear_amount=1):
        stages = getattr(chapter, "stages", [])
        cleared = 0
        for stage in stages:
            try:
                stage.clear_stage(clear_amount)
                cleared += 1
            except Exception:
                pass
        return cleared == len(stages) and len(stages) > 0

    # Clear Stages
    if clear_all_stages:
        try:
            if core is not None and hasattr(core, "StoryChapters"):
                core.StoryChapters.clear_tutorial(sf)
            if hasattr(sf, "story") and sf.story:
                chapters = sf.story.get_real_chapters() if hasattr(sf.story, "get_real_chapters") else getattr(sf.story, "chapters", [])
                for ch_id, ch in enumerate(chapters):
                    for stage_id in range(48):
                        sf.story.clear_stage(ch_id, stage_id, overwrite_clear_progress=True, clear_amount=1, chapters=chapters)
            for aku_chapter in _get_aku_chapters(sf):
                _clear_aku_chapter(aku_chapter, 1)
            res["clear_all_stages"] = True
        except Exception:
            pass

    if clear_chapters:
        count = 0
        chapters = _get_story_chapters(sf)
        for item in clear_chapters:
            try:
                if isinstance(item, dict):
                    ch_id = int(item.get("chapter", 0))
                    amt = int(item.get("clear_amount", item.get("clears", 1)))
                else:
                    ch_id = int(item)
                    amt = 1

                if 0 <= ch_id < len(chapters):
                    if _clear_story_chapter(chapters[ch_id], amt):
                        count += 1
                elif ch_id == 9:
                    aku_chapters = _get_aku_chapters(sf)
                    if aku_chapters:
                        for aku_chapter in aku_chapters:
                            _clear_aku_chapter(aku_chapter, amt)
                        count += 1
            except Exception:
                pass
        res["cleared_chapters_count"] = count

    if clear_stages:
        count = 0
        chapters = _get_story_chapters(sf)
        for item in clear_stages:
            try:
                if isinstance(item, dict):
                    ch_id = int(item.get("chapter", 0))
                    st_id = int(item.get("stage", 0))
                    amt = int(item.get("clear_amount", item.get("clears", 1)))
                    if 0 <= ch_id < len(chapters):
                        if _clear_story_stage(chapters[ch_id], st_id, amt):
                            count += 1
                    elif ch_id == 9:
                        aku_maps = getattr(getattr(sf, "aku", None), "chapters", [])
                        map_id = int(item.get("map", item.get("aku_map", 0)))
                        star_id = int(item.get("star", 0))
                        if 0 <= map_id < len(aku_maps):
                            stars = getattr(aku_maps[map_id], "chapters", [])
                            if 0 <= star_id < len(stars):
                                aku_stages = getattr(stars[star_id], "stages", [])
                                if 0 <= st_id < len(aku_stages):
                                    aku_stages[st_id].clear_stage(amt)
                                    count += 1
            except Exception:
                pass
        res["cleared_stages_count"] = count

    # Treasures & Timed Scores
    if max_treasures:
        try:
            chapters = _get_story_chapters(sf)
            for ch in chapters:
                t_stages = ch.get_valid_treasure_stages() if hasattr(ch, "get_valid_treasure_stages") else getattr(ch, "stages", [])[:48]
                for st in t_stages:
                    if hasattr(st, "set_treasure"):
                        st.set_treasure(3)
                    if hasattr(st, "itf_timed_score"):
                        st.itf_timed_score = 9999
            res["max_treasures"] = True
        except Exception:
            pass

    if max_chapter_treasures:
        count = 0
        chapters = _get_story_chapters(sf)
        for item in max_chapter_treasures:
            try:
                if isinstance(item, dict):
                    ch_id = int(item.get("chapter", 0))
                    tr_val = int(item.get("treasure", 3))
                else:
                    ch_id = int(item)
                    tr_val = 3

                if 0 <= ch_id < len(chapters):
                    ch = chapters[ch_id]
                    t_stages = ch.get_treasure_stages() if hasattr(ch, "get_treasure_stages") else getattr(ch, "stages", [])
                    for st in t_stages:
                        if hasattr(st, "set_treasure"):
                            st.set_treasure(min(3, max(0, tr_val)))
                        if hasattr(st, "itf_timed_score"):
                            st.itf_timed_score = 9999
                    count += 1
            except Exception:
                pass
        res["max_chapter_treasures_count"] = count

    if stage_treasures:
        count = 0
        chapters = _get_story_chapters(sf)
        for item in stage_treasures:
            try:
                if isinstance(item, dict):
                    ch_id = int(item.get("chapter", 0))
                    st_id = int(item.get("stage", 0))
                    tr_val = int(item.get("treasure", 3))
                    if 0 <= ch_id < len(chapters):
                        ch = chapters[ch_id]
                        if hasattr(ch, "stages") and 0 <= st_id < len(ch.stages):
                            st = ch.stages[st_id]
                            if hasattr(st, "set_treasure"):
                                st.set_treasure(min(3, max(0, tr_val)))
                                count += 1
            except Exception:
                pass
        res["set_stage_treasures_count"] = count

    # Fix Timestamps & Energy penalty (BCSFE Fixes.fix_time_errors)
    try:
        now_dt = datetime.datetime.now()
        now_ts = now_dt.timestamp()
        if hasattr(sf, "date_3"):
            sf.date_3 = now_dt
        if hasattr(sf, "timestamp"):
            sf.timestamp = now_ts
        if hasattr(sf, "energy_penalty_timestamp"):
            sf.energy_penalty_timestamp = now_ts
    except Exception:
        pass

    # Menu Unlocks & Lineup Sanity
    try:
        if hasattr(sf, "unlock_equip_menu"):
            sf.unlock_equip_menu()
        if hasattr(sf, "menu_unlocks") and sf.menu_unlocks:
            for i in range(len(sf.menu_unlocks)):
                sf.menu_unlocks[i] = max(sf.menu_unlocks[i], 1)
        if hasattr(sf, "lineups") and sf.lineups and hasattr(sf.lineups, "slots") and sf.lineups.slots:
            if hasattr(core, "game") and hasattr(core.game, "battle") and hasattr(core.game.battle, "slots"):
                sf.lineups.slots[0].slots[0] = core.game.battle.slots.EquipSlot(0)
    except Exception:
        pass

    try:
        sh.save_file = sf
        has_managed = False
        if backup_meta and hasattr(backup_meta, "managed_items") and backup_meta.managed_items:
            has_managed = len(backup_meta.managed_items) > 0
        codes = sh.get_codes(upload_managed_items=has_managed)
        if codes and len(codes) == 2:
            return res, codes
    except Exception:
        pass

    return res, None
