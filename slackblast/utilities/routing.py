from utilities import handlers, strava, builders
from utilities.slack import actions

# Required arguments for handler functions:
#     body: dict
#     client: WebClient
#     logger: Logger
#     context: dict

# The mappers define the function to be called for each event
# The boolean value indicates whether a loading modal should be triggered before running the function

COMMAND_MAPPER = {
    "/backblast": (builders.build_backblast_form, True),
    "/slackblast": (builders.build_backblast_form, True),
    "/preblast": (builders.build_preblast_form, True),
    "/config-welcome-message": (builders.build_welcome_message_form, True),
    "/config-slackblast": (builders.build_config_form, True),
    "/tag-achievement": (builders.build_achievement_form, True),
}

VIEW_MAPPER = {
    actions.BACKBLAST_CALLBACK_ID: (handlers.handle_backblast_post, False),
    actions.BACKBLAST_EDIT_CALLBACK_ID: (handlers.handle_backblast_post, False),
    actions.PREBLAST_CALLBACK_ID: (handlers.handle_preblast_post, False),
    actions.PREBLAST_EDIT_CALLBACK_ID: (handlers.handle_preblast_post, False),
    actions.WELCOME_MESSAGE_CONFIG_CALLBACK_ID: (handlers.handle_welcome_message_config_post, False),
    actions.CONFIG_CALLBACK_ID: (handlers.handle_config_post, False),
    actions.STRAVA_MODIFY_CALLBACK_ID: (strava.handle_strava_modify, False),
    actions.CUSTOM_FIELD_ADD_CALLBACK_ID: (handlers.handle_custom_field_add, False),
    actions.CUSTOM_FIELD_MENU_CALLBACK_ID: (handlers.handle_custom_field_menu, False),
    actions.ACHIEVEMENT_CALLBACK_ID: (handlers.handle_achievements_tag, False),
}

ACTION_MAPPER = {
    actions.BACKBLAST_EDIT_BUTTON: (builders.handle_backblast_edit_button, True),
    actions.BACKBLAST_NEW_BUTTON: (builders.build_backblast_form, True),
    actions.BACKBLAST_STRAVA_BUTTON: (builders.build_strava_form, True),
    actions.STRAVA_ACTIVITY_BUTTON: (builders.build_strava_modify_form, False),
    actions.BACKBLAST_AO: (builders.build_backblast_form, False),
    actions.BACKBLAST_DATE: (builders.build_backblast_form, False),
    actions.BACKBLAST_Q: (builders.build_backblast_form, False),
    actions.CONFIG_EMAIL_ENABLE: (builders.build_config_form, False),
    actions.STRAVA_CONNECT_BUTTON: (builders.ignore_event, False),
    actions.CONFIG_CUSTOM_FIELDS: (builders.build_custom_field_menu, False),
    actions.CUSTOM_FIELD_ADD: (builders.build_custom_field_add_edit, False),
    actions.CUSTOM_FIELD_EDIT: (builders.build_custom_field_add_edit, False),
    actions.CUSTOM_FIELD_DELETE: (builders.delete_custom_field, False),
    actions.PREBLAST_NEW_BUTTON: (builders.build_preblast_form, True),
    actions.PREBLAST_EDIT_BUTTON: (builders.handle_preblast_edit_button, True),
}

VIEW_CLOSED_MAPPER = {
    actions.CUSTOM_FIELD_ADD_FORM: (builders.ignore_event, False),
    actions.STRAVA_MODIFY_CALLBACK_ID: (strava.handle_strava_modify, False),
}

EVENT_MAPPER = {
    "team_join": (handlers.handle_team_join, False),
}

MAIN_MAPPER = {
    "command": COMMAND_MAPPER,
    "block_actions": ACTION_MAPPER,
    "view_submission": VIEW_MAPPER,
    "view_closed": VIEW_CLOSED_MAPPER,
    "event_callback": EVENT_MAPPER,
}
