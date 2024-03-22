# import json
import json
from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from utilities.helper_functions import (
    get_oauth_flow,
    safe_get,
    get_region_record,
    get_request_type,
    update_local_region_records,
)
from utilities.constants import LOCAL_DEVELOPMENT
from utilities.routing import MAIN_MAPPER
from utilities.slack.actions import LOADING_ID
import logging
from utilities.database.orm import Region
from utilities import strava
from utilities.builders import send_error_response, add_loading_form
import re
from typing import Callable, Tuple
import traceback

SlackRequestHandler.clear_all_log_handlers()
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
logger.addHandler(handler)

app = App(
    process_before_response=not LOCAL_DEVELOPMENT,
    oauth_flow=get_oauth_flow(),
)


def handler(event, context):
    if event.get("path") == "/exchange_token":
        return strava.strava_exchange_token(event, context)
    else:
        slack_handler = SlackRequestHandler(app=app)
        return slack_handler.handle(event, context)


def main_response(body, logger, client, ack, context):
    ack()
    logger.info(json.dumps(body, indent=4))
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")
    region_record: Region = get_region_record(team_id, body, context, client, logger)

    request_type, request_id = get_request_type(body)
    lookup: Tuple[Callable, bool] = safe_get(safe_get(MAIN_MAPPER, request_type), request_id)
    if lookup:
        run_function, add_loading = lookup
        if add_loading:
            body[LOADING_ID] = add_loading_form(body=body, client=client)
        try:
            run_function(
                body=body,
                client=client,
                logger=logger,
                context=context,
                region_record=region_record,
            )
        except Exception as exc:
            logger.info("sending error response")
            tb_str = "".join(traceback.format_exception(None, exc, exc.__traceback__))
            send_error_response(body=body, client=client, error=tb_str)
            logger.error(tb_str)
    else:
        logger.error(
            f"no handler for path: {safe_get(safe_get(MAIN_MAPPER, request_type), request_id) or request_type+', '+request_id}"
        )


if LOCAL_DEVELOPMENT:
    ARGS = [main_response]
    LAZY_KWARGS = {}
else:
    ARGS = []
    LAZY_KWARGS = {
        "ack": lambda ack: ack(),
        "lazy": [main_response],
    }


MATCH_ALL_PATTERN = re.compile(".*")
app.action(MATCH_ALL_PATTERN)(*ARGS, **LAZY_KWARGS)
app.view(MATCH_ALL_PATTERN)(*ARGS, **LAZY_KWARGS)
app.command(MATCH_ALL_PATTERN)(*ARGS, **LAZY_KWARGS)
app.view_closed(MATCH_ALL_PATTERN)(*ARGS, **LAZY_KWARGS)
app.event(MATCH_ALL_PATTERN)(*ARGS, **LAZY_KWARGS)

if __name__ == "__main__":
    app.start(3000)
    update_local_region_records()
