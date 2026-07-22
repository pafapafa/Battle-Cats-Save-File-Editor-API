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


def _get_country_code(country_code_str: str):
    if core is None:
        return country_code_str
    try:
        return core.CountryCode.from_code(country_code_str.lower())
    except Exception:
        return core.CountryCode.from_code("kr")


def download_ponos_save(transfer_code: str, confirmation_code: str, country_code_str: str = "kr"):
    if core is None:
        return None, None

    try:
        country_code = _get_country_code(country_code_str)
        game_version = core.GameVersion(140300)

        # Call official bcsfe ServerHandler.from_codes
        server_handler, request_result = core.ServerHandler.from_codes(
            transfer_code,
            confirmation_code,
            cc=country_code,
            gv=game_version,
            print=False,
            save_backup=False,
        )

        if server_handler is None or server_handler.save_file is None:
            return None, None

        return server_handler.save_file, server_handler
    except Exception as exception_error:
        print(f"Download Exception: {exception_error}")
        return None, None


def patch_and_upload_save(
    save_file_or_bytes: Any = None,
    server_handler: Any = None,
    country_code_str: str = "kr",
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
    save_file: Any = None,
    cc_str: Optional[str] = None,
) -> Tuple[Dict[str, Any], Optional[Tuple[str, str]]]:
    if enable_safety:
        if catfood is not None:
            catfood = min(catfood, SAFE_CATFOOD_MAX)
        if xp is not None:
            xp = min(xp, SAFE_XP_MAX)

    target_save_file = getattr(server_handler, "save_file", None) or save_file or save_file_or_bytes

    if server_handler is None or target_save_file is None:
        return {}, None

    modification_results = {
        "original_catfood": getattr(target_save_file, "catfood", 0),
        "original_xp": getattr(target_save_file, "xp", 0),
    }

    # 1. Modify currency & basic item fields safely
    if catfood is not None:
        try:
            target_save_file.catfood = max(0, min(int(catfood), INT32_MAX))
            modification_results["new_catfood"] = target_save_file.catfood
        except Exception as exception_error:
            print(f"catfood patch error: {exception_error}")

    if xp is not None:
        try:
            target_save_file.xp = max(0, min(int(xp), INT32_MAX))
            modification_results["new_xp"] = target_save_file.xp
        except Exception as exception_error:
            print(f"xp patch error: {exception_error}")

    if normal_tickets is not None and hasattr(target_save_file, "normal_tickets"):
        try:
            target_save_file.normal_tickets = max(0, min(int(normal_tickets), INT32_MAX))
            modification_results["new_normal_tickets"] = target_save_file.normal_tickets
        except Exception as exception_error:
            print(f"normal_tickets patch error: {exception_error}")

    if rare_tickets is not None:
        try:
            target_save_file.rare_tickets = max(0, min(int(rare_tickets), INT32_MAX))
            modification_results["new_rare_tickets"] = target_save_file.rare_tickets
        except Exception as exception_error:
            print(f"rare_tickets patch error: {exception_error}")

    if platinum_tickets is not None:
        try:
            target_save_file.platinum_tickets = max(0, min(int(platinum_tickets), INT32_MAX))
            modification_results["new_platinum_tickets"] = target_save_file.platinum_tickets
        except Exception as exception_error:
            print(f"platinum_tickets patch error: {exception_error}")

    if legend_tickets is not None:
        try:
            target_save_file.legend_tickets = max(0, min(int(legend_tickets), INT32_MAX))
            modification_results["new_legend_tickets"] = target_save_file.legend_tickets
        except Exception as exception_error:
            print(f"legend_tickets patch error: {exception_error}")

    if platinum_shards is not None and hasattr(target_save_file, "platinum_shards"):
        try:
            target_save_file.platinum_shards = max(0, min(int(platinum_shards), INT32_MAX))
            modification_results["new_platinum_shards"] = target_save_file.platinum_shards
        except Exception as exception_error:
            print(f"platinum_shards patch error: {exception_error}")

    if np is not None and hasattr(target_save_file, "np"):
        try:
            target_save_file.np = max(0, min(int(np), INT32_MAX))
            modification_results["new_np"] = target_save_file.np
        except Exception as exception_error:
            print(f"np patch error: {exception_error}")

    if leadership is not None and hasattr(target_save_file, "leadership"):
        try:
            target_save_file.leadership = max(0, min(int(leadership), 32767))
            modification_results["new_leadership"] = target_save_file.leadership
        except Exception as exception_error:
            print(f"leadership patch error: {exception_error}")

    # 2. Cats Fine-Grained Editing safely
    if unlock_cats:
        try:
            target_save_file.unlock_equip_menu()
            target_save_file.unlock_popups()
            if hasattr(target_save_file, "cats") and hasattr(target_save_file.cats, "get_cats_obtainable"):
                obtainable_cats = target_save_file.cats.get_cats_obtainable(target_save_file) if hasattr(target_save_file.cats.get_cats_obtainable, "__code__") and target_save_file.cats.get_cats_obtainable.__code__.co_argcount > 1 else target_save_file.cats.get_cats_obtainable()
                if obtainable_cats:
                    for cat in obtainable_cats:
                        cat.unlock(target_save_file)
            modification_results["unlock_cats"] = True
        except Exception as exception_error:
            print(f"unlock_cats exception: {exception_error}")

    if unlock_cat_ids and hasattr(target_save_file, "cats"):
        unlocked_cat_count = 0
        try:
            target_save_file.unlock_equip_menu()
            target_save_file.unlock_popups()
            for cat_id in unlock_cat_ids:
                try:
                    cat_id = int(cat_id)
                    target_cat = None
                    if hasattr(target_save_file.cats, "get_cat_by_id"):
                        target_cat = target_save_file.cats.get_cat_by_id(cat_id)
                    elif hasattr(target_save_file.cats, "cats") and 0 <= cat_id < len(target_save_file.cats.cats):
                        target_cat = target_save_file.cats.cats[cat_id]
                    if target_cat:
                        target_cat.unlock(target_save_file)
                        unlocked_cat_count += 1
                except Exception:
                    pass
            modification_results["unlocked_cat_ids_count"] = unlocked_cat_count
        except Exception as exception_error:
            print(f"unlock_cat_ids exception: {exception_error}")

    if remove_cat_ids and hasattr(target_save_file, "cats"):
        removed_cat_count = 0
        try:
            for cat_id in remove_cat_ids:
                try:
                    cat_id = int(cat_id)
                    target_cat = None
                    if hasattr(target_save_file.cats, "get_cat_by_id"):
                        target_cat = target_save_file.cats.get_cat_by_id(cat_id)
                    elif hasattr(target_save_file.cats, "cats") and 0 <= cat_id < len(target_save_file.cats.cats):
                        target_cat = target_save_file.cats.cats[cat_id]
                    if target_cat:
                        target_cat.remove(reset=True, save_file=target_save_file)
                        removed_cat_count += 1
                except Exception:
                    pass
            modification_results["removed_cat_ids_count"] = removed_cat_count
        except Exception as exception_error:
            print(f"remove_cat_ids exception: {exception_error}")

    # 3. Stage Clearing Granular Editing safely
    if clear_all_stages and hasattr(target_save_file, "story") and hasattr(target_save_file.story, "chapters"):
        try:
            for chapter in target_save_file.story.chapters:
                chapter.clear_chapter()
            if hasattr(target_save_file, "aku") and hasattr(target_save_file.aku, "clear_chapters"):
                target_save_file.aku.clear_chapters()
            modification_results["clear_all_stages"] = True
        except Exception as exception_error:
            print(f"clear_all_stages exception: {exception_error}")

    if clear_chapters and hasattr(target_save_file, "story") and hasattr(target_save_file.story, "chapters"):
        cleared_chapter_count = 0
        for chapter_id in clear_chapters:
            try:
                chapter_id = int(chapter_id)
                if 0 <= chapter_id < len(target_save_file.story.chapters):
                    target_save_file.story.chapters[chapter_id].clear_chapter()
                    cleared_chapter_count += 1
            except Exception:
                pass
        modification_results["cleared_chapters_count"] = cleared_chapter_count

    if clear_stages and hasattr(target_save_file, "story") and hasattr(target_save_file.story, "chapters"):
        cleared_stages_count = 0
        for stage_item in clear_stages:
            try:
                if isinstance(stage_item, dict):
                    chapter_id = int(stage_item.get("chapter"))
                    stage_id = int(stage_item.get("stage"))
                    clear_amount = int(stage_item.get("clear_amount", 1))
                    if 0 <= chapter_id < len(target_save_file.story.chapters) and 0 <= stage_id < 51:
                        target_save_file.story.chapters[chapter_id].clear_stage(stage_id, clear_amount, overwrite_clear_progress=True)
                        cleared_stages_count += 1
            except Exception:
                pass
        modification_results["cleared_stages_count"] = cleared_stages_count

    # 4. Treasures Granular Editing safely
    if max_treasures and hasattr(target_save_file, "story") and hasattr(target_save_file.story, "chapters"):
        try:
            for chapter in target_save_file.story.chapters:
                for stage_id in range(48):
                    chapter.set_treasure(stage_id, 3)
            modification_results["max_treasures"] = True
        except Exception as exception_error:
            print(f"max_treasures exception: {exception_error}")

    if max_chapter_treasures and hasattr(target_save_file, "story") and hasattr(target_save_file.story, "chapters"):
        maxed_chapters_count = 0
        for chapter_id in max_chapter_treasures:
            try:
                chapter_id = int(chapter_id)
                if 0 <= chapter_id < len(target_save_file.story.chapters):
                    for stage_id in range(48):
                        target_save_file.story.chapters[chapter_id].set_treasure(stage_id, 3)
                    maxed_chapters_count += 1
            except Exception:
                pass
        modification_results["max_chapter_treasures_count"] = maxed_chapters_count

    if stage_treasures and hasattr(target_save_file, "story") and hasattr(target_save_file.story, "chapters"):
        set_stage_treasures_count = 0
        for treasure_item in stage_treasures:
            try:
                if isinstance(treasure_item, dict):
                    chapter_id = int(treasure_item.get("chapter"))
                    stage_id = int(treasure_item.get("stage"))
                    treasure_value = int(treasure_item.get("treasure", 3))
                    if 0 <= chapter_id < len(target_save_file.story.chapters) and 0 <= stage_id < 48:
                        target_save_file.story.chapters[chapter_id].set_treasure(stage_id, min(3, max(0, treasure_value)))
                        set_stage_treasures_count += 1
            except Exception:
                pass
        modification_results["set_stage_treasures_count"] = set_stage_treasures_count

    # 5. Sync managed items with PONOS server to prevent TE01 error
    try:
        server_handler.update_managed_items()
    except Exception as exception_error:
        print(f"update_managed_items exception: {exception_error}")

    # 6. Upload modified save file and issue new transfer credentials
    try:
        transfer_credentials = server_handler.get_codes()
        if transfer_credentials and len(transfer_credentials) == 2:
            return modification_results, transfer_credentials
    except Exception as exception_error:
        print(f"get_codes exception: {exception_error}")

    return modification_results, None
