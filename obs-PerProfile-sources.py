# Copyright(c) Susko3 <susko3@protonmail.com>. Licensed under the MIT Licence.
# See the LICENCE file in the repository root for full licence text.

import re
from contextlib import contextmanager

import obspython as S


def script_description():
    return "Automatically hides and shows Sources based on the currently selected Profile"


def debug(*args):
    # print(*args)
    ...


PROPERTIES_REGEX_PATTERN = "regex_pattern"
properties_regex_pattern = "[profile:{}]"

REGEX_PATTERN_HELP_TEXT = """
Put {} where you want to have the profile name be

ℹ For example
- [profile:{}]
- [p:{}]
""".strip()


def get_regex_for_profile_name(profile_name: str) -> re.Pattern:
    global properties_regex_pattern

    if '{}' not in properties_regex_pattern:
        raise ValueError(f"Invalid regex pattern: {properties_regex_pattern}")

    gx = re.escape(properties_regex_pattern.format(profile_name))
    debug(f" {gx}")
    return re.compile(gx)


PROFILES_RES: list[re.Pattern] = []
CURRENT_PROFILE_RE: re.Pattern = re.compile(r'^\b$')  # regex that will never match


def update_profiles():
    global PROFILES_RES
    global CURRENT_PROFILE_RE
    try:
        current = S.obs_frontend_get_current_profile()
        debug("current:")
        CURRENT_PROFILE_RE = get_regex_for_profile_name(current)

        debug("list:")
        profile_list = S.obs_frontend_get_profiles()
        PROFILES_RES = list(map(get_regex_for_profile_name, profile_list))
    except ValueError as e:
        debug('💣 Failed to set regex:', e)


def hide_show(name: str) -> bool | None:
    """Determines whether a given ``name`` should be hidden or shown with regard to the current profile."""
    global PROFILES_RES
    global CURRENT_PROFILE_RE

    if any(r.search(name) for r in PROFILES_RES):
        b = bool(CURRENT_PROFILE_RE.search(name))
        debug(f"found some profile string in {name}, current profile: {b}")
        return b

    return None


@contextmanager
def scene_ar(scene):
    scene = S.obs_scene_from_source(scene)
    try:
        yield scene
    finally:
        S.obs_scene_release(scene)


@contextmanager
def scene_enum(scene):
    scene_items = S.obs_scene_enum_items(scene)
    try:
        yield scene_items
    finally:
        S.sceneitem_list_release(scene_items)


@contextmanager
def group_enum(group):
    group_items = S.obs_sceneitem_group_enum_items(group)
    try:
        yield group_items
    finally:
        S.sceneitem_list_release(group_items)


def update_visibility_for_scene_item(scene_item) -> bool | None:
    """
    Maybe works for both sources, groups, and nested scenes?
    """
    source = S.obs_sceneitem_get_source(scene_item)
    name = S.obs_source_get_name(source)
    debug("name:", name)

    match hide_show(name):
        case True:
            S.obs_sceneitem_set_visible(scene_item, True)
            debug("  showing", name)
            return True

        case False:
            S.obs_sceneitem_set_visible(scene_item, False)
            debug("  hiding", name)
            return False

        case None:
            return S.obs_sceneitem_visible(scene_item)


def update_visibility_for_group(scene_item):
    update_visibility_for_scene_item(scene_item)
    with group_enum(scene_item) as group_items:
        for group_item in group_items:
            # while nested groups are not possible, this would need to consider nested Scenes
            update_visibility_for_scene_item(group_item)


def update_visibility_in_scene(_scene):
    with scene_ar(_scene) as scene:
        with scene_enum(scene) as scene_items:
            for scene_item in scene_items:
                if S.obs_sceneitem_is_group(scene_item):
                    update_visibility_for_group(scene_item)
                else:
                    update_visibility_for_scene_item(scene_item)
                # not handled: the 'Scene' source -- would need to recurse into that


def update_visibility_in_current_scene():
    current_scene = S.obs_frontend_get_current_scene()
    update_visibility_in_scene(current_scene)


def callback(event):
    match event:
        case S.OBS_FRONTEND_EVENT_PREVIEW_SCENE_CHANGED:
            debug("the scene has changed!", "updating all sources")
            update_visibility_in_current_scene()
        case S.OBS_FRONTEND_EVENT_PROFILE_LIST_CHANGED \
             | S.OBS_FRONTEND_EVENT_PROFILE_CHANGED \
             | S.OBS_FRONTEND_EVENT_PROFILE_RENAMED:
            update_profiles()
            update_visibility_in_current_scene()


def script_defaults(settings):
    S.obs_data_set_default_string(settings, PROPERTIES_REGEX_PATTERN, "[profile:{}]")


def script_update(settings):
    global properties_regex_pattern
    debug("script_update")
    properties_regex_pattern = S.obs_data_get_string(settings, PROPERTIES_REGEX_PATTERN)
    update_profiles()
    update_visibility_in_current_scene()


def script_properties():
    debug("script_properties")
    props = S.obs_properties_create()
    pattern = S.obs_properties_add_text(props, PROPERTIES_REGEX_PATTERN, "Regex Pattern", S.OBS_TEXT_DEFAULT)
    S.obs_property_set_long_description(pattern, REGEX_PATTERN_HELP_TEXT)
    return props


def script_load(_):
    debug("script_load")
    # update_profiles()
    # update_visibility_in_current_scene()
    S.obs_frontend_add_event_callback(callback)
