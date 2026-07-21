import sys
import os
import tempfile
from typing import Optional, Dict, Any, Tuple, List

# Use standard OS temp directory for bcsfe configuration and cache
os.environ["HOME"] = tempfile.gettempdir()

try:
    from bcsfe import core
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


def _get_country_code(cc_str: str):
    if core is None:
        return cc_str
    try:
        return core.CountryCode.from_code(cc_str.lower())
    except Exception:
        return core.CountryCode.from_code("kr")


def download_ponos_save(transfer_code: str, confirmation_code: str, cc_str: str = "kr"):
    if core is None:
        return None, None

    try:
        cc = _get_country_code(cc_str)
        gv = core.GameVersion(140300)

        # Call official bcsfe ServerHandler.from_codes
        sh, request_res = core.ServerHandler.from_codes(
            transfer_code,
            confirmation_code,
            cc=cc,
            gv=gv,
            print=False,
            save_backup=False,
        )

        if sh is None or sh.save_file is None:
            return None, None

        return sh.save_file, sh
    except Exception as e:
        print(f"Download Exception: {e}")
        return None, None


def patch_and_upload_save(
    save_file_or_bytes: Any,
    server_handler: Any,
    cc_str: str,
    # Currencies & Items
    catfood: Optional[int] = None,
    xp: Optional[int] = None,
    normal_tickets: Optional[int] = None,
    rare_tickets: Optional[int] = None,
    platinum_tickets: Optional[int] = None,
    legend_tickets: Optional[int] = None,
    platinum_shards: Optional[int] = None,
    np: Optional[int] = None,
    leadership: Optional[int] = None,
    # Cats
    unlock_cats: bool = False,
    unlock_cat_ids: Optional[List[int]] = None,
    remove_cat_ids: Optional[List[int]] = None,
    # Stages
    clear_all_stages: bool = False,
    clear_chapters: Optional[List[int]] = None,
    clear_stages: Optional[List[Dict[str, int]]] = None,
    # Treasures
    max_treasures: bool = False,
    max_chapter_treasures: Optional[List[int]] = None,
    stage_treasures: Optional[List[Dict[str, int]]] = None,
    # Safety
    enable_safety: bool = False,
) -> Tuple[Dict[str, Any], Optional[Tuple[str, str]]]:
    if enable_safety:
        if catfood is not None:
            catfood = min(catfood, SAFE_CATFOOD_MAX)
        if xp is not None:
            xp = min(xp, SAFE_XP_MAX)

    if server_handler is None or not hasattr(server_handler, "save_file"):
        return {}, None

    sh = server_handler
    sf = sh.save_file

    result = {
        "original_catfood": getattr(sf, "catfood", 0),
        "original_xp": getattr(sf, "xp", 0),
    }

    # 1. Modify currency & basic item fields
    if catfood is not None:
        sf.catfood = max(0, min(catfood, INT32_MAX))
        result["new_catfood"] = sf.catfood
    if xp is not None:
        sf.xp = max(0, min(xp, INT32_MAX))
        result["new_xp"] = sf.xp
    if normal_tickets is not None and hasattr(sf, "normal_tickets"):
        sf.normal_tickets = max(0, min(normal_tickets, INT32_MAX))
        result["new_normal_tickets"] = sf.normal_tickets
    if rare_tickets is not None:
        sf.rare_tickets = max(0, min(rare_tickets, INT32_MAX))
        result["new_rare_tickets"] = sf.rare_tickets
    if platinum_tickets is not None:
        sf.platinum_tickets = max(0, min(platinum_tickets, INT32_MAX))
        result["new_platinum_tickets"] = sf.platinum_tickets
    if legend_tickets is not None:
        sf.legend_tickets = max(0, min(legend_tickets, INT32_MAX))
        result["new_legend_tickets"] = sf.legend_tickets
    if platinum_shards is not None and hasattr(sf, "platinum_shards"):
        sf.platinum_shards = max(0, min(platinum_shards, INT32_MAX))
        result["new_platinum_shards"] = sf.platinum_shards
    if np is not None and hasattr(sf, "np"):
        sf.np = max(0, min(np, INT32_MAX))
        result["new_np"] = sf.np
    if leadership is not None and hasattr(sf, "leadership"):
        sf.leadership = max(0, min(leadership, 32767))
        result["new_leadership"] = sf.leadership

    # 2. Cats Fine-Grained Editing
    if unlock_cats:
        try:
            sf.unlock_equip_menu()
            sf.unlock_popups()
            if hasattr(sf, "cats") and hasattr(sf.cats, "get_cats_obtainable"):
                for cat in sf.cats.get_cats_obtainable():
                    cat.unlock(sf)
            result["unlock_cats"] = True
        except Exception as e:
            print(f"unlock_cats exception: {e}")

    if unlock_cat_ids and hasattr(sf, "cats"):
        unlocked_count = 0
        try:
            sf.unlock_equip_menu()
            sf.unlock_popups()
            for cid in unlock_cat_ids:
                cat = sf.cats.get_cat(cid)
                if cat:
                    cat.unlock(sf)
                    unlocked_count += 1
            result["unlocked_cat_ids_count"] = unlocked_count
        except Exception as e:
            print(f"unlock_cat_ids exception: {e}")

    if remove_cat_ids and hasattr(sf, "cats"):
        removed_count = 0
        try:
            for cid in remove_cat_ids:
                cat = sf.cats.get_cat(cid)
                if cat:
                    cat.remove(reset=True, save_file=sf)
                    removed_count += 1
            result["removed_cat_ids_count"] = removed_count
        except Exception as e:
            print(f"remove_cat_ids exception: {e}")

    # 3. Stage Clearing Granular Editing
    if clear_all_stages and hasattr(sf, "story"):
        try:
            for ch in sf.story.chapters:
                ch.clear_chapter()
            if hasattr(sf, "aku"):
                sf.aku.clear_chapters()
            result["clear_all_stages"] = True
        except Exception as e:
            print(f"clear_all_stages exception: {e}")

    if clear_chapters and hasattr(sf, "story"):
        cleared_count = 0
        try:
            for ch_id in clear_chapters:
                if 0 <= ch_id < len(sf.story.chapters):
                    sf.story.chapters[ch_id].clear_chapter()
                    cleared_count += 1
            result["cleared_chapters_count"] = cleared_count
        except Exception as e:
            print(f"clear_chapters exception: {e}")

    if clear_stages and hasattr(sf, "story"):
        cleared_stages_count = 0
        try:
            for item in clear_stages:
                ch_id = item.get("chapter")
                st_id = item.get("stage")
                amt = item.get("clear_amount", 1)
                if ch_id is not None and st_id is not None and 0 <= ch_id < len(sf.story.chapters):
                    sf.story.chapters[ch_id].clear_stage(st_id, amt, overwrite_clear_progress=True)
                    cleared_stages_count += 1
            result["cleared_stages_count"] = cleared_stages_count
        except Exception as e:
            print(f"clear_stages exception: {e}")

    # 4. Treasures Granular Editing
    if max_treasures and hasattr(sf, "story"):
        try:
            for ch in sf.story.chapters:
                for st_id in range(48):
                    ch.set_treasure(st_id, 3)  # Gold/Superior treasure
            result["max_treasures"] = True
        except Exception as e:
            print(f"max_treasures exception: {e}")

    if max_chapter_treasures and hasattr(sf, "story"):
        maxed_ch_count = 0
        try:
            for ch_id in max_chapter_treasures:
                if 0 <= ch_id < len(sf.story.chapters):
                    for st_id in range(48):
                        sf.story.chapters[ch_id].set_treasure(st_id, 3)
                    maxed_ch_count += 1
            result["max_chapter_treasures_count"] = maxed_ch_count
        except Exception as e:
            print(f"max_chapter_treasures exception: {e}")

    if stage_treasures and hasattr(sf, "story"):
        set_tr_count = 0
        try:
            for item in stage_treasures:
                ch_id = item.get("chapter")
                st_id = item.get("stage")
                tr_val = item.get("treasure", 3)
                if ch_id is not None and st_id is not None and 0 <= ch_id < len(sf.story.chapters):
                    sf.story.chapters[ch_id].set_treasure(st_id, min(3, max(0, tr_val)))
                    set_tr_count += 1
            result["set_stage_treasures_count"] = set_tr_count
        except Exception as e:
            print(f"stage_treasures exception: {e}")

    # 5. Sync managed items with PONOS server to prevent TE01 error
    try:
        sh.update_managed_items()
    except Exception as e:
        print(f"update_managed_items exception: {e}")

    # 6. Upload modified save file and issue new transfer codes
    try:
        codes = sh.get_codes()
        if codes and len(codes) == 2:
            return result, codes
    except Exception as e:
        print(f"get_codes exception: {e}")

    return result, None
