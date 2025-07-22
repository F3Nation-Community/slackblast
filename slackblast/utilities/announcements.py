# A quick script to make announcements (changelogs, etc) to Slack
import time
from logging import Logger
from typing import List

from slack_sdk import WebClient

from utilities.database import DbManager
from utilities.database.orm import PaxminerRegion, Region

msg = "Hello, {region}! This is Moneyball, lead developer of the Slackblast app. I wanted to make you aware of a couple known issues in Slack right now that probably has affected your slackblast usage:\n\n"
msg += ":warning: *Tagging* - Particularly on Android phones, you've probably noticed that you can only tag other PAX with their full name, not their display / F3 name\n\n"
msg += ":warning: *Errors while using emojis* - Particularly on iOS devices, editing moleskines that have emojis will result in an error when you try to submit\n\n"
msg += "\nBoth of these are known issues that I've bubbled up to Slack support. Unfortunately, there's nothing we can do but wait at this point. To avoid the second issue, I would avoid the use of emojis for now.\n"
msg += "\n~ :moneybag: :baseball:"
msg += "\n\nPS don't forget to tune in to the F3 Nation State of the Nation tonight at 8pm EST! There will be some info on a lot of cool stuff happening in the F3 tech space that you won't want to miss: https://f3nation.com/sotn"


def send(client: WebClient, body: dict, logger: Logger, context: dict, region_record: Region):
    if body.get("text") == "confirm":
        region_records: List[Region] = DbManager.find_records(Region, filters=[True])
        paxminer_regions = DbManager.find_records(PaxminerRegion, filters=[True], schema="paxminer")
        paxminer_dict = {region.schema_name: region.firstf_channel for region in paxminer_regions}

        for region in region_records:
            if region.paxminer_schema:
                send_channel = paxminer_dict.get(region.paxminer_schema)
                if send_channel:
                    print(f"Sending message to {region.workspace_name}")
                    client = WebClient(token=region.bot_token)
                    try:
                        client.chat_postMessage(channel=send_channel, text=msg.format(region=region.workspace_name))
                        print("Message sent!")
                    except Exception as e:
                        if e.response.get("error") == "ratelimited":
                            print("Rate limited, waiting 10 seconds")
                            time.sleep(10)
                            try:
                                client.chat_postMessage(
                                    channel=send_channel, text=msg.format(region=region.workspace_name)
                                )
                                print("Message sent!")
                            except Exception as e:
                                print(f"Error sending message to {region.workspace_name}: {e}")
                        print(f"Error sending message to {region.workspace_name}: {e}")
