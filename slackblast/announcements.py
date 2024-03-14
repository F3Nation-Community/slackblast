# A quick script to make announcements (changelogs, etc) to Slack
from utilities.database.orm import Region, PaxminerRegion
from utilities.database import DbManager
from typing import List
from slack_sdk import WebClient
from logging import Logger

msg = "Hello, {region}! This is Moneyball, lead developer of the Slackblast app. I wanted to make you aware of updates to Slackblast over the last few months:\n\n"
msg += ":left_speech_bubble: *Welcome Messages!* - We've added a new feature that allows you to send a welcome message to new members as they join your Slack space. This is a great way to introduce new members to your region and let them know how to navigate your space. Use `/config-welcome-message` to set it up.\n\n"
msg += ":runner: *Strava Integration!* - Allows Strava PAX to transfer the backblast notes over to Strava, while gathering workout data (calories, distance) from linked devices. Go to `/config-slackblast` to enable.\n\n"
msg += ":bar_chart: *Custom Fields!* - Does your region want to track something specific in your backblasts (burpee count, gloom index, etc.)? You can create your own fields through the Custom Field menu in `/config-slackblast`.\n\n"
msg += ":sports_medal: *Weaselbot Achievements (new today)!* - For those using <https://github.com/F3Nation-Community/weaselbot|Weaselbot>, you can now assign achievements to PAX directly without having to create a whole backblast for it. Use the `/tag-achievement` command to get started.\n\n"
msg += ":mechanic: *Under the Hood!* - Things like rich text input for backblasts, boyband image support, and better error handling.\n\n"
msg += "\nIf you have any questions or issues, the best way to reach out is on the #paxminer-and-slackblast channel in the Nation space.\n"
msg += "\n~ :moneybag: :baseball:"


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
                        print(f"Error sending message to {region.workspace_name}: {e}")