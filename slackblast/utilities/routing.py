from utilities import handlers, strava
from utilities.slack import actions

# Required arguments for view handler functions:
#     body: dict
#     client: WebClient
#     logger: Logger
#     context: dict
# Testing another update
VIEW_MAPPER = {
    actions.BACKBLAST_CALLBACK_ID: handlers.handle_backblast_post,
    actions.BACKBLAST_EDIT_CALLBACK_ID: handlers.handle_backblast_post,
    actions.PREBLAST_CALLBACK_ID: handlers.handle_preblast_post,
    actions.CONFIG_CALLBACK_ID: handlers.handle_config_post,
    actions.STRAVA_MODIFY_CALLBACK_ID: strava.handle_strava_modify,
    actions.CUSTOM_FIELD_ADD_CALLBACK_ID: handlers.handle_custom_field_add,
    actions.CUSTOM_FIELD_MENU_CALLBACK_ID: handlers.handle_custom_field_menu,
}
