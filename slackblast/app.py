# import json
import json
from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from utilities.helper_functions import (
    get_oauth_flow,
    safe_get,
    get_region_record,
    get_request_type,
)
from utilities.constants import LOCAL_DEVELOPMENT
from utilities.routing import MAIN_MAPPER
import logging
from utilities.database.orm import Region
from utilities import strava
import re

logger = logging.getLogger()
logger.setLevel(logging.INFO)

app = App(
    process_before_response=not LOCAL_DEVELOPMENT,
    oauth_flow=get_oauth_flow(),
)


def handler(event, context):
    exchange_prefix = "" if LOCAL_DEVELOPMENT else "/Prod"
    print(event.get("path"))
    if event.get("path") == f"{exchange_prefix}/exchange_token":
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
    run_function = safe_get(safe_get(MAIN_MAPPER, request_type), request_id)
    if run_function:
        run_function(body=body, client=client, logger=logger, context=context, region_record=region_record)
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

if __name__ == "__main__":
    app.start(3000)
