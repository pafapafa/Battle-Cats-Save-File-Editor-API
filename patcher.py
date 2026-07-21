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

    # 1. Modify currency & basic item fields safely
    if catfood is not None:
        try:
            sf.catfood = max(0, min(int(catfood), INT32_MAX))
            result["new_catfood"] = sf.catfood
        except Exception as e:
            print(f"catfood patch error: {e}")

    if xp is not None:
        try:
            sf.xp = max(0, min(int(xp), INT32_MAX))
            result["new_xp"] = sf.xp
        except Exception as e:
            print(f"xp patch error: {e}")

    if normal_tickets is not None and hasattr(sf, "normal_tickets"):
        try:
            sf.normal_tickets = max(0, min(int(normal_tickets), INT32_MAX))
            result["new_normal_tickets"] = sf.normal_tickets
        except Exception as e:
            print(f"normal_tickets patch error: {e}")

    if rare_tickets is not None:
        try:
            sf.rare_tickets = max(0, min(int(rare_tickets), INT32_MAX))
            result["new_rare_tickets"] = sf.rare_tickets
        except Exception as e:
            print(f"rare_tickets patch error: {e}")

    if platinum_tickets is not None:
        try:
            sf.platinum_tickets = max(0, min(int(platinum_tickets), INT32_MAX))
            result["new_platinum_tickets"] = sf.platinum_tickets
        except Exception as e:
            print(f"platinum_tickets patch error: {e}")

    if legend_tickets is not None:
        try:
            sf.legend_tickets = max(0, min(int(legend_tickets), INT32_MAX))
            result["new_legend_tickets"] = sf.legend_tickets
        except Exception as e:
            print(f"legend_tickets patch error: {e}")

    if platinum_shards is not None and hasattr(sf, "platinum_shards"):
        try:
            sf.platinum_shards = max(0, min(int(platinum_shards), INT32_MAX))
            result["new_platinum_shards"] = sf.platinum_shards
        except Exception as e:
            print(f"platinum_shards patch error: {e}")

    if np is not None and hasattr(sf, "np"):
        try:
            sf.np = max(0, min(int(np), INT32_MAX))
            result["new_np"] = sf.np
        except Exception as e:
            print(f"np patch error: {e}")

    if leadership is not None and hasattr(sf, "leadership"):
        try:
            sf.leadership = max(0, min(int(leadership), 32767))
            result["new_leadership"] = sf.leadership
        except Exception as e:
            print(f"leadership patch error: {e}")

    # 2. Cats Fine-Grained Editing safely
    if unlock_cats:
        try:
            sf.unlock_equip_menu()
            sf.unlock_popups()
            if hasattr(sf, "cats") and hasattr(sf.cats, "get_cats_obtainable"):
                obtainable = sf.cats.get_cats_obtainable(sf) if hasattr(sf.cats.get_cats_obtainable, "__code__") and sf.cats.get_cats_obtainable.__code__.co_argcount > 1 else sf.cats.get_cats_obtainable()
                if obtainable:
                    for cat in obtainable:
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
                try:
                    cid = int(cid)
                    cat = None
                    if hasattr(sf.cats, "get_cat_by_id"):
                        cat = sf.cats.get_cat_by_id(cid)
                    elif hasattr(sf.cats, "cats") and 0 <= cid < len(sf.cats.cats):
                        cat = sf.cats.cats[cid]
                    if cat:
                        cat.unlock(sf)
                        unlocked_count += 1
                except Exception:
                    pass
            result["unlocked_cat_ids_count"] = unlocked_count
        except Exception as e:
            print(f"unlock_cat_ids exception: {e}")

    if remove_cat_ids and hasattr(sf, "cats"):
        removed_count = 0
        try:
            for cid in remove_cat_ids:
                try:
                    cid = int(cid)
                    cat = None
                    if hasattr(sf.cats, "get_cat_by_id"):
                        cat = sf.cats.get_cat_by_id(cid)
                    elif hasattr(sf.cats, "cats") and 0 <= cid < len(sf.cats.cats):
                        cat = sf.cats.cats[cid]
                    if cat:
                        cat.remove(reset=True, save_file=sf)
                        removed_count += 1
                except Exception:
                    pass
            result["removed_cat_ids_count"] = removed_count
        except Exception as e:
            print(f"remove_cat_ids exception: {e}")

    # 3. Stage Clearing Granular Editing safely
    if clear_all_stages and hasattr(sf, "story") and hasattr(sf.story, "chapters"):
        try:
            for ch in sf.story.chapters:
                ch.clear_chapter()
            if hasattr(sf, "aku") and hasattr(sf.aku, "clear_chapters"):
                sf.aku.clear_chapters()
            result["clear_all_stages"] = True
        except Exception as e:
            print(f"clear_all_stages exception: {e}")

    if clear_chapters and hasattr(sf, "story") and hasattr(sf.story, "chapters"):
        cleared_count = 0
        for ch_id in clear_chapters:
            try:
                ch_id = int(ch_id)
                if 0 <= ch_id < len(sf.story.chapters):
                    sf.story.chapters[ch_id].clear_chapter()
                    cleared_count += 1
            except Exception:
                pass
        result["cleared_chapters_count"] = cleared_count

    if clear_stages and hasattr(sf, "story") and hasattr(sf.story, "chapters"):
        cleared_stages_count = 0
        for item in clear_stages:
            try:
                if isinstance(item, dict):
                    ch_id = int(item.get("chapter"))
                    st_id = int(item.get("stage"))
                    amt = int(item.get("clear_amount", 1))
                    if 0 <= ch_id < len(sf.story.chapters) and 0 <= st_id < 51:
                        sf.story.chapters[ch_id].clear_stage(st_id, amt, overwrite_clear_progress=True)
                        cleared_stages_count += 1
            except Exception:
                pass
        result["cleared_stages_count"] = cleared_stages_count

    # 4. Treasures Granular Editing safely
    if max_treasures and hasattr(sf, "story") and hasattr(sf.story, "chapters"):
        try:
            for ch in sf.story.chapters:
                for st_id in range(48):
                    ch.set_treasure(st_id, 3)
            result["max_treasures"] = True
        except Exception as e:
            print(f"max_treasures exception: {e}")

    if max_chapter_treasures and hasattr(sf, "story") and hasattr(sf.story, "chapters"):
        maxed_ch_count = 0
        for ch_id in max_chapter_treasures:
            try:
                ch_id = int(ch_id)
                if 0 <= ch_id < len(sf.story.chapters):
                    for st_id in range(48):
                        sf.story.chapters[ch_id].set_treasure(st_id, 3)
                    maxed_ch_count += 1
            except Exception:
                pass
        result["max_chapter_treasures_count"] = maxed_ch_count

    if stage_treasures and hasattr(sf, "story") and hasattr(sf.story, "chapters"):
        set_tr_count = 0
        for item in stage_treasures:
            try:
                if isinstance(item, dict):
                    ch_id = int(item.get("chapter"))
                    st_id = int(item.get("stage"))
                    tr_val = int(item.get("treasure", 3))
                    if 0 <= ch_id < len(sf.story.chapters) and 0 <= st_id < 48:
                        sf.story.chapters[ch_id].set_treasure(st_id, min(3, max(0, tr_val)))
                        set_tr_count += 1
            except Exception:
                pass
        result["set_stage_treasures_count"] = set_tr_count

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
