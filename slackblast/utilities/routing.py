from features import backblast, config, custom_fields, preblast, strava, weaselbot, welcome
from features.calendar import ao, home, location, series
from features.calendar import config as calendar_config
from utilities import announcements, builders
from utilities.slack import actions

# Required arguments for handler functions:
#     body: dict
#     client: WebClient
#     logger: Logger
#     context: dict

# The mappers define the function to be called for each event
# The boolean value indicates whether a loading modal should be triggered before running the function

COMMAND_MAPPER = {
    "/backblast": (backblast.build_backblast_form, True),
    "/slackblast": (backblast.build_backblast_form, True),
    "/preblast": (preblast.build_preblast_form, True),
    "/config-welcome-message": (welcome.build_welcome_message_form, True),
    "/config-slackblast": (config.build_config_form, True),
    "/tag-achievement": (weaselbot.build_achievement_form, True),
    "/send-announcement": (announcements.send, False),
    "/calendar": (home.build_home_form, True),
}

VIEW_MAPPER = {
    actions.BACKBLAST_CALLBACK_ID: (backblast.handle_backblast_post, False),
    actions.BACKBLAST_EDIT_CALLBACK_ID: (backblast.handle_backblast_post, False),
    actions.PREBLAST_CALLBACK_ID: (preblast.handle_preblast_post, False),
    actions.PREBLAST_EDIT_CALLBACK_ID: (preblast.handle_preblast_post, False),
    actions.WELCOME_MESSAGE_CONFIG_CALLBACK_ID: (welcome.handle_welcome_message_config_post, False),
    actions.CONFIG_GENERAL_CALLBACK_ID: (config.handle_config_general_post, False),
    actions.CONFIG_EMAIL_CALLBACK_ID: (config.handle_config_email_post, False),
    actions.STRAVA_MODIFY_CALLBACK_ID: (strava.handle_strava_modify, False),
    actions.CUSTOM_FIELD_ADD_CALLBACK_ID: (custom_fields.handle_custom_field_add, False),
    actions.CUSTOM_FIELD_MENU_CALLBACK_ID: (custom_fields.handle_custom_field_menu, False),
    actions.ACHIEVEMENT_CALLBACK_ID: (weaselbot.handle_achievements_tag, False),
    actions.WEASELBOT_CONFIG_CALLBACK_ID: (weaselbot.handle_config_form, False),
    actions.CONFIG_PAXMINER_CALLBACK_ID: (config.handle_config_paxminer_post, False),
    actions.ADD_LOCATION_CALLBACK_ID: (location.handle_location_add, False),
    actions.ADD_AO_CALLBACK_ID: (ao.handle_ao_add, False),
    actions.ADD_SERIES_CALLBACK_ID: (series.handle_series_add, False),
}

ACTION_MAPPER = {
    actions.BACKBLAST_EDIT_BUTTON: (backblast.handle_backblast_edit_button, True),
    actions.BACKBLAST_NEW_BUTTON: (backblast.build_backblast_form, True),
    actions.BACKBLAST_STRAVA_BUTTON: (strava.build_strava_form, True),
    actions.STRAVA_ACTIVITY_BUTTON: (strava.build_strava_modify_form, False),
    actions.BACKBLAST_AO: (backblast.build_backblast_form, False),
    actions.BACKBLAST_DATE: (backblast.build_backblast_form, False),
    actions.BACKBLAST_Q: (backblast.build_backblast_form, False),
    # actions.CONFIG_EMAIL_ENABLE: (config.build_config_form, False),
    actions.STRAVA_CONNECT_BUTTON: (builders.ignore_event, False),
    actions.CONFIG_CUSTOM_FIELDS: (custom_fields.build_custom_field_menu, False),
    actions.CUSTOM_FIELD_ADD: (custom_fields.build_custom_field_add_edit, False),
    actions.CUSTOM_FIELD_EDIT: (custom_fields.build_custom_field_add_edit, False),
    actions.CUSTOM_FIELD_DELETE: (custom_fields.delete_custom_field, False),
    actions.PREBLAST_NEW_BUTTON: (preblast.build_preblast_form, True),
    actions.PREBLAST_EDIT_BUTTON: (preblast.handle_preblast_edit_button, True),
    actions.CONFIG_WEASELBOT: (weaselbot.build_config_form, False),
    actions.CONFIG_WELCOME_MESSAGE: (welcome.build_welcome_message_form, False),
    actions.CONFIG_EMAIL: (config.build_config_email_form, False),
    actions.CONFIG_GENERAL: (config.build_config_general_form, False),
    actions.CONFIG_WELCOME_MESSAGE: (welcome.build_welcome_config_form, False),
    actions.CONFIG_PAXMINER: (config.build_config_paxminer_form, False),
    actions.CONFIG_CALENDAR: (calendar_config.build_calendar_config_form, False),
    # actions.CALENDAR_ADD_LOCATION: (location.build_location_add_form, False),
    # actions.CALENDAR_ADD_AO: (ao.build_ao_add_form, False),
    # actions.CALENDAR_ADD_SERIES: (series.build_series_add_form, False),
    actions.CALENDAR_ADD_SERIES_AO: (series.build_series_add_form, False),
    # actions.CALENDAR_EDIT_SERIES: (series.build_series_list_form, False),
    actions.SERIES_EDIT_DELETE: (series.handle_series_edit_delete, False),
    # actions.CALENDAR_EDIT_LOCATION: (location.build_location_list_form, False),
    actions.LOCATION_EDIT_DELETE: (location.handle_location_edit_delete, False),
    actions.AO_EDIT_DELETE: (ao.handle_ao_edit_delete, False),
    # actions.CALENDAR_EDIT_AO: (ao.build_ao_list_form, False),
    # actions.CALENDAR_ADD_SINGLE_EVENT: (series.build_series_add_form, False),
    actions.CALENDAR_ADD_EVENT_AO: (series.build_series_add_form, False),
    # actions.CALENDAR_EDIT_SINGLE_EVENT: (series.build_series_list_form, False),
    actions.CALENDAR_MANAGE_LOCATIONS: (location.manage_locations, False),
    actions.CALENDAR_MANAGE_AOS: (ao.manage_aos, False),
    actions.CALENDAR_MANAGE_SERIES: (series.manage_series, False),
    actions.CALENDAR_MANAGE_EVENTS: (series.manage_series, False),
}

VIEW_CLOSED_MAPPER = {
    actions.CUSTOM_FIELD_ADD_FORM: (builders.ignore_event, False),
    actions.STRAVA_MODIFY_CALLBACK_ID: (strava.handle_strava_modify, False),
}

EVENT_MAPPER = {
    "team_join": (welcome.handle_team_join, False),
}

MAIN_MAPPER = {
    "command": COMMAND_MAPPER,
    "block_actions": ACTION_MAPPER,
    "view_submission": VIEW_MAPPER,
    "view_closed": VIEW_CLOSED_MAPPER,
    "event_callback": EVENT_MAPPER,
}
