from utilities import constants
from utilities.database.orm import PaxminerRegion
from utilities.slack import actions, orm

BACKBLAST_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Title",
            action=actions.BACKBLAST_TITLE,
            optional=False,
            element=orm.PlainTextInputElement(placeholder="Enter a workout title..."),
        ),
        orm.InputBlock(
            label="Upload a boyband",
            element=orm.FileInputElement(
                max_files=1,
                filetypes=[
                    "png",
                    "jpg",
                    "heic",
                    "bmp",
                ],
            ),
            action=actions.BACKBLAST_FILE,
            optional=True,
        ),
        orm.InputBlock(
            label="The AO",
            action=actions.BACKBLAST_AO,
            optional=False,
            element=orm.ChannelsSelectElement(placeholder="Select the AO..."),
            dispatch_action=True,
        ),
        orm.InputBlock(
            label="Workout Date",
            action=actions.BACKBLAST_DATE,
            optional=False,
            element=orm.DatepickerElement(placeholder="Select the date..."),
            dispatch_action=True,
        ),
        orm.InputBlock(
            label="The Q",
            action=actions.BACKBLAST_Q,
            optional=False,
            element=orm.UsersSelectElement(placeholder="Select the Q..."),
            dispatch_action=True,
        ),
        orm.ContextBlock(
            action=actions.BACKBLAST_DUPLICATE_WARNING,
            element=orm.ContextElement(
                initial_value=":warning: :warning: *WARNING*: duplicate backblast detected in PAXMiner DB for this Q, "
                "AO, and date; this backblast will not be saved as-is. Please modify one of these selections",
            ),
        ),
        orm.InputBlock(
            label="The CoQ(s), if any",
            action=actions.BACKBLAST_COQ,
            optional=True,
            element=orm.MultiUsersSelectElement(placeholder="Select the CoQ(s)..."),
        ),
        orm.InputBlock(
            label="The PAX",
            action=actions.BACKBLAST_PAX,
            optional=False,
            element=orm.MultiUsersSelectElement(placeholder="Select the PAX..."),
        ),
        orm.InputBlock(
            label="List untaggable PAX, separated by commas (not FNGs)",
            action=actions.BACKBLAST_NONSLACK_PAX,
            optional=True,
            element=orm.PlainTextInputElement(
                placeholder="Enter untaggable PAX...",
            ),
        ),
        orm.InputBlock(
            label="List FNGs, separated by commas",
            action=actions.BACKBLAST_FNGS,
            optional=True,
            element=orm.PlainTextInputElement(placeholder="Enter FNGs..."),
        ),
        orm.InputBlock(
            label="Total PAX Count",
            action=actions.BACKBLAST_COUNT,
            optional=True,
            element=orm.PlainTextInputElement(placeholder="Total PAX count including FNGs"),
        ),
        orm.ContextBlock(
            element=orm.ContextElement(
                initial_value="If left blank, this will be calculated automatically from the fields above.",
            ),
        ),
        orm.InputBlock(
            label="The Moleskine",
            action=actions.BACKBLAST_MOLESKIN,
            optional=False,
            element=orm.RichTextInputElement(),
        ),
        orm.DividerBlock(),
        orm.InputBlock(
            label="Choose where to post this",
            action=actions.BACKBLAST_DESTINATION,
            optional=False,
            element=orm.StaticSelectElement(placeholder="Select a destination..."),
        ),
        orm.InputBlock(
            label="Email Backblast (to Wordpress, etc)",
            action=actions.BACKBLAST_EMAIL_SEND,
            optional=False,
            element=orm.RadioButtonsElement(
                options=orm.as_selector_options(names=["Send Email", "Don't Send Email"], values=["yes", "no"]),
                initial_value="yes",
            ),
        ),
        orm.ContextBlock(
            element=orm.ContextElement(
                initial_value="*Do not hit Submit more than once!* Even if you get a timeout error, the backblast has "
                "likely already been posted. If using email, this can take time and this form may not automatically "
                "close.",
            ),
        ),
    ]
)

PREBLAST_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Title",
            action=actions.PREBLAST_TITLE,
            optional=False,
            element=orm.PlainTextInputElement(placeholder="Enter a workout title..."),
        ),
        orm.InputBlock(
            label="The AO",
            action=actions.PREBLAST_AO,
            optional=False,
            element=orm.ChannelsSelectElement(placeholder="Select the AO..."),
        ),
        orm.InputBlock(
            label="Workout Date",
            action=actions.PREBLAST_DATE,
            optional=False,
            element=orm.DatepickerElement(
                placeholder="Select the date...",
            ),
        ),
        orm.InputBlock(
            label="Workout Time",
            action=actions.PREBLAST_TIME,
            optional=False,
            element=orm.TimepickerElement(),
        ),
        orm.InputBlock(
            label="The Q",
            action=actions.PREBLAST_Q,
            optional=False,
            element=orm.UsersSelectElement(placeholder="Select the Q..."),
        ),
        orm.InputBlock(
            label="Coupons?",
            action=actions.PREBLAST_COUPONS,
            optional=True,
            element=orm.PlainTextInputElement(  # TODO: change to radio buttons or checkboxes
                placeholder="Coupons or not?",
            ),
        ),
        orm.InputBlock(
            label="Moleskine",
            action=actions.PREBLAST_MOLESKIN,
            optional=True,
            element=orm.RichTextInputElement(),
        ),
        orm.DividerBlock(),
        orm.InputBlock(
            label="Choose where to post this",
            action=actions.PREBLAST_DESTINATION,
            optional=False,
            element=orm.StaticSelectElement(placeholder="Select a destination..."),
        ),
        orm.ContextBlock(
            element=orm.ContextElement(
                initial_value="*Do not hit Submit more than once!* Even if you get a timeout error, the preblast has "
                "likely already been posted. This form may not automatically close.",
            ),
        ),
    ]
)

CONFIG_FORM = orm.BlockView(
    [
        orm.ActionsBlock(
            elements=[
                orm.ButtonElement(
                    label=":gear: General Settings",
                    action=actions.CONFIG_GENERAL,
                ),
                orm.ButtonElement(
                    label=":email: Email Settings",
                    action=actions.CONFIG_EMAIL,
                ),
                orm.ButtonElement(
                    label=":bar_chart: Custom Field Settings",
                    action=actions.CONFIG_CUSTOM_FIELDS,
                ),
                orm.ButtonElement(
                    label=":speech_balloon: Welcomebot Settings",
                    action=actions.CONFIG_WELCOME_MESSAGE,
                ),
                # orm.ButtonElement(
                #     label=":robot_face: Weaselbot Settings",
                #     action=actions.CONFIG_WEASELBOT,
                # ),
                orm.ButtonElement(
                    label=":pick: Paxminer Settings",
                    action=actions.CONFIG_PAXMINER,
                ),
            ],
        ),
    ]
)

CONFIG_EMAIL_FORM = orm.BlockView(
    [
        orm.InputBlock(
            label="Slackblast Email",
            action=actions.CONFIG_EMAIL_ENABLE,
            optional=False,
            element=orm.RadioButtonsElement(
                initial_value="disable",
                options=orm.as_selector_options(names=["Enable Email", "Disable Email"], values=["enable", "disable"]),
            ),
        ),
        orm.InputBlock(
            label="Show email option in form?",
            action=actions.CONFIG_EMAIL_SHOW_OPTION,
            optional=False,
            element=orm.RadioButtonsElement(
                initial_value="no",
                options=orm.as_selector_options(names=["Show", "Don't Show"], values=["yes", "no"]),
            ),
        ),
        orm.InputBlock(
            label="Email Server",
            action=actions.CONFIG_EMAIL_SERVER,
            optional=False,
            element=orm.PlainTextInputElement(initial_value="smtp.gmail.com"),
        ),
        orm.InputBlock(
            label="Email Port",
            action=actions.CONFIG_EMAIL_PORT,
            optional=False,
            element=orm.PlainTextInputElement(initial_value="587"),
        ),
        orm.InputBlock(
            label="Email From Address",
            action=actions.CONFIG_EMAIL_FROM,
            optional=False,
            element=orm.PlainTextInputElement(initial_value="example_sender@gmail.com"),
        ),
        orm.InputBlock(
            label="Email Password",
            action=actions.CONFIG_EMAIL_PASSWORD,
            optional=False,
            element=orm.PlainTextInputElement(initial_value="example_pwd_123"),
        ),
        orm.ContextBlock(
            action=actions.CONFIG_PASSWORD_CONTEXT,
            element=orm.ContextElement(
                initial_value="If using gmail, you must use an App Password (https://support.google.com/accounts/answer"
                "/185833). Your password will be stored encrypted - however, it is STRONGLY recommended that you use "
                "a non-personal email address and password for this purpose, as security cannot be guaranteed.",
            ),
        ),
        orm.InputBlock(
            label="Email To Address",
            action=actions.CONFIG_EMAIL_TO,
            optional=False,
            element=orm.PlainTextInputElement(initial_value="example_destination@gmail.com"),
        ),
        orm.InputBlock(
            label="Use Postie formatting for categories?",
            action=actions.CONFIG_POSTIE_ENABLE,
            optional=False,
            element=orm.RadioButtonsElement(
                initial_value="no",
                options=orm.as_selector_options(names=["Yes", "No"], values=["yes", "no"]),
            ),
        ),
        orm.ContextBlock(
            action=actions.CONFIG_POSTIE_CONTEXT,
            element=orm.ContextElement(
                initial_value="This will put the AO name as a category for the post, and will put PAX names at the end"
                "as tags.",
            ),
        ),
    ]
)

CONFIG_GENERAL_FORM = orm.BlockView(
    [
        orm.InputBlock(
            label="Enable Strava Integration?",
            action=actions.CONFIG_ENABLE_STRAVA,
            optional=False,
            element=orm.RadioButtonsElement(
                initial_value="no",
                options=orm.as_selector_options(names=["Enable", "Disable"], values=["enable", "disable"]),
            ),
        ),
        orm.DividerBlock(),
        orm.InputBlock(
            label="Lock editing of backblasts?",
            action=actions.CONFIG_EDITING_LOCKED,
            optional=False,
            element=orm.RadioButtonsElement(
                initial_value="no",
                options=orm.as_selector_options(names=["Yes", "No"], values=["yes", "no"]),
            ),
        ),
        orm.DividerBlock(),
        orm.InputBlock(
            label="Default Slack channel desination for backblasts",
            action=actions.CONFIG_DEFAULT_DESTINATION,
            optional=False,
            element=orm.RadioButtonsElement(
                initial_value=constants.CONFIG_DESTINATION_AO["value"],
                options=orm.as_selector_options(
                    names=[
                        constants.CONFIG_DESTINATION_AO["name"],
                        constants.CONFIG_DESTINATION_CURRENT["name"],
                    ],
                    values=[
                        constants.CONFIG_DESTINATION_AO["value"],
                        constants.CONFIG_DESTINATION_CURRENT["value"],
                    ],
                ),
            ),
        ),
        orm.DividerBlock(),
        orm.InputBlock(
            label="Backblast Moleskine Template / Starter",
            action=actions.CONFIG_BACKBLAST_MOLESKINE_TEMPLATE,
            optional=True,
            element=orm.RichTextInputElement(),
        ),
        orm.InputBlock(
            label="Preblast Moleskine Template / Starter",
            action=actions.CONFIG_PREBLAST_MOLESKINE_TEMPLATE,
            optional=True,
            element=orm.RichTextInputElement(),
        ),
    ]
)

WELCOME_MESSAGE_CONFIG_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Enable Welcomebot welcome DMs?",
            action=actions.WELCOME_DM_ENABLE,
            optional=False,
            element=orm.RadioButtonsElement(
                initial_value="no",
                options=orm.as_selector_options(names=["Enable", "Disable"], values=["enable", "disable"]),
            ),
        ),
        orm.InputBlock(
            label="Welcome Message Template",
            action=actions.WELCOME_DM_TEMPLATE,
            optional=True,
            element=orm.RichTextInputElement(),
        ),
        orm.ContextBlock(
            element=orm.ContextElement(
                initial_value="*This content will be sent to any new user who joins this Slack workspace.*\n\n"
                + "This is a good time to tell an FNG or long-time Slack hold out what they need to know about your region and how you use Slack.\n"  # noqa: E501
                + "Who should they reach out to if they have a question? What channels should they join? What does HC mean and "  # noqa: E501
                + "how do they do that? Should their Slack handle be their F3 name?",
            ),
        ),
        orm.InputBlock(
            label="Enable Welcomebot welcome channel posts?",
            action=actions.WELCOME_CHANNEL_ENABLE,
            optional=False,
            element=orm.RadioButtonsElement(
                initial_value="disable",
                options=orm.as_selector_options(names=["Enable", "Disable"], values=["enable", "disable"]),
            ),
        ),
        orm.InputBlock(
            label="Welcomebot Channel",
            action=actions.WELCOME_CHANNEL,
            optional=False,
            element=orm.ChannelsSelectElement(placeholder="Select the channel..."),
        ),
        orm.ContextBlock(
            element=orm.ContextElement(
                initial_value="If enabled, this is the channel where welcome messages will be posted.",
            ),
        ),
    ]
)

STRAVA_ACTIVITY_MODIFY_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Activity Title",
            action=actions.STRAVA_ACTIVITY_TITLE,
            optional=False,
            element=orm.PlainTextInputElement(
                initial_value="",
                placeholder="Enter a workout title...",
                max_length=100,
            ),
        ),
        orm.InputBlock(
            label="Activity Description",
            action=actions.STRAVA_ACTIVITY_DESCRIPTION,
            optional=False,
            element=orm.PlainTextInputElement(
                initial_value="",
                placeholder="Enter a workout description...",
                max_length=3000,
                multiline=True,
            ),
        ),
    ]
)

CUSTOM_FIELD_TYPE_MAP = {
    "Dropdown": orm.StaticSelectElement(),
    "Text": orm.PlainTextInputElement(),
    "Number": orm.NumberInputElement(),
}

CUSTOM_FIELD_ADD_EDIT_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            element=orm.PlainTextInputElement(
                initial_value="",
                multiline=False,
                placeholder="Enter the name of the new field or metric",
                max_length=40,
            ),
            action=actions.CUSTOM_FIELD_ADD_NAME,
            label="Field name / metric name",
            optional=False,
        ),
        orm.InputBlock(
            element=orm.StaticSelectElement(
                options=orm.as_selector_options(
                    names=CUSTOM_FIELD_TYPE_MAP.keys(),
                ),
                initial_value="Dropdown",
            ),
            action=actions.CUSTOM_FIELD_ADD_TYPE,
            label="Type of entry",
            optional=False,
            # dispatch_action=True, TODO: hide dropdown options if not "Dropdown"
        ),
        orm.InputBlock(
            element=orm.PlainTextInputElement(
                initial_value=" ",
                multiline=False,
                placeholder="Enter the options for the dropdown, separated by commas",
                max_length=100,
            ),
            action=actions.CUSTOM_FIELD_ADD_OPTIONS,
            label="Dropdown options (only required if 'Dropdown' is selected above)",
            optional=False,
        ),
    ]
)

LOADING_FORM = orm.BlockView(
    blocks=[
        orm.SectionBlock(label=":hourglass: Loading, do not close...", action=actions.LOADING),
        orm.ContextBlock(
            action="loading_context",
            element=orm.ContextElement(
                initial_value="If this form does not update after a few seconds, an error may have occured. Please try again.",  # noqa: E501
            ),
        ),
    ]
)

ERROR_FORM = orm.BlockView(
    blocks=[
        orm.SectionBlock(label=":warning: the following error occurred:", action=actions.ERROR_FORM_MESSAGE),
    ]
)

ACHIEVEMENT_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Achievement",
            action=actions.ACHIEVEMENT_SELECT,
            optional=False,
            element=orm.StaticSelectElement(placeholder="Select the achievement..."),
        ),
        orm.ContextBlock(
            element=orm.ContextElement(
                initial_value="Don't see the achievement you're looking for? Talk to your Weasel Shaker / Tech Q about getting it added!",  # noqa: E501
            ),
        ),
        orm.InputBlock(
            label="Select the PAX",
            action=actions.ACHIEVEMENT_PAX,
            optional=False,
            element=orm.MultiUsersSelectElement(placeholder="Select the PAX..."),
        ),
        orm.InputBlock(
            label="Achievement Date",
            action=actions.ACHIEVEMENT_DATE,
            optional=False,
            element=orm.DatepickerElement(placeholder="Select the date..."),
        ),
        orm.ContextBlock(
            element=orm.ContextElement(
                initial_value="Please use a date in the period the achievement was earned, as some achievements can be earned for several periods.",  # noqa: E501
            ),
        ),
    ]
)

WEASELBOT_CONFIG_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Which Weaselbot features should be enabled?",
            action=actions.WEASELBOT_ENABLE_FEATURES,
            element=orm.CheckboxInputElement(
                options=orm.as_selector_options(
                    names=["Achievements", "Kotter Reports"],
                    values=["achievements", "kotter_reports"],
                )
            ),
        ),
        orm.InputBlock(
            label="Which channel should achievements be posted to?",
            action=actions.WEASELBOT_ACHIEVEMENT_CHANNEL,
            optional=True,
            element=orm.ChannelsSelectElement(placeholder="Select the channel..."),
        ),
        orm.InputBlock(
            label="Which user or channel should Kotter Reports be posted to?",
            action=actions.WEASELBOT_KOTTER_CHANNEL,
            optional=True,
            element=orm.ConversationsSelectElement(placeholder="Select the user or channel..."),
        ),
        orm.ContextBlock(
            element=orm.ContextElement(
                initial_value="Please note that Weaselbot will need to be manually added to private channels if selected.",  # noqa: E501
            ),
        ),
        orm.InputBlock(
            label="How many weeks of no posting should put a PAX on the Kotter Report?",
            action=actions.WEASELBOT_KOTTER_WEEKS,
            optional=True,
            element=orm.NumberInputElement(placeholder="Enter the number of weeks...", is_decimal_allowed=False),
        ),
        orm.InputBlock(
            label="After how many weeks of no posting should a PAX be removed from the Kotter Report?",
            action=actions.WEASELBOT_KOTTER_REMOVE_WEEKS,
            optional=True,
            element=orm.NumberInputElement(placeholder="Enter the number of weeks...", is_decimal_allowed=False),
        ),
        orm.InputBlock(
            label="How many weeks of activity should be used to base a PAX's home AO?",
            action=actions.WEASELBOT_HOME_AO_WEEKS,
            optional=True,
            element=orm.NumberInputElement(placeholder="Enter the number of weeks...", is_decimal_allowed=False),
        ),
        orm.InputBlock(
            label="After how many weeks of no Qing should a PAX be put on the Q list?",
            action=actions.WEASELBOT_Q_WEEKS,
            optional=True,
            element=orm.NumberInputElement(placeholder="Enter the number of weeks...", is_decimal_allowed=False),
        ),
        orm.InputBlock(
            label="What should be the minimum number of posts over that time to be eligible for the Q list?",
            action=actions.WEASELBOT_Q_POSTS,
            optional=True,
            element=orm.NumberInputElement(placeholder="Enter the number of posts...", is_decimal_allowed=False),
        ),
    ]
)

PAXMINER_REPORT_DICT = {
    "names": [
        "PAX Charts",
        "Q Charts",
        "AO Leaderboards",
        "Region Leaderboard",
    ],
    "values": [
        "pax_charts",
        "q_charts",
        "ao_leaderboards",
        "region_leaderboard",
    ],
    "fields": [
        "send_pax_charts",
        "send_q_charts",
        "send_ao_leaderboard",
        "send_region_leaderboard",
    ],
    "schema": [
        PaxminerRegion.send_pax_charts,
        PaxminerRegion.send_q_charts,
        PaxminerRegion.send_ao_leaderboard,
        PaxminerRegion.send_region_leaderboard,
    ],
}

CONFIG_PAXMINER_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Enable PAXMiner scraping?",
            action=actions.CONFIG_PAXMINER_SCRAPE_ENABLE,
            optional=False,
            element=orm.RadioButtonsElement(
                options=orm.as_selector_options(
                    names=["Scraping Enabled", "Disable Scraping"], values=["enable", "disable"]
                ),  # noqa: E501
            ),
        ),
        orm.ContextBlock(
            element=orm.ContextElement(
                initial_value="In preparation for PAXMiner's retirement, we are asking regions to disable scraping and utilize Slackblast for all backblast creation. Disabling scraping will not impact your monthly reporting.",  # noqa: E501
            ),
        ),
        orm.InputBlock(
            label="Which channels should be scraped by PAXMiner?",
            action=actions.CONFIG_PAXMINER_SCRAPE_CHANNELS,
            element=orm.MultiChannelsSelectElement(placeholder="Select some channels..."),
        ),
        orm.InputBlock(
            label="Which monthly reports should be enabled?",
            action=actions.CONFIG_PAXMINER_ENABLE_REPORTS,
            element=orm.CheckboxInputElement(
                options=orm.as_selector_options(
                    names=PAXMINER_REPORT_DICT["names"],
                    values=PAXMINER_REPORT_DICT["values"],
                )
            ),
            optional=False,
        ),
        orm.InputBlock(
            label="Which channel should region reports be posted to?",
            action=actions.CONFIG_PAXMINER_1STF_CHANNEL,
            optional=False,
            element=orm.ChannelsSelectElement(placeholder="Select the channel..."),
        ),
        orm.InputBlock(
            label="Which channels should AO reports be posted to?",
            action=actions.CONFIG_PAXMINER_REPORT_CHANNELS,
            element=orm.MultiChannelsSelectElement(placeholder="Select some channels..."),
        ),
        orm.SectionBlock(
            label="""
*Report Descriptions*

*PAX Charts:*
- One graph sent to each PAX. YTD posting summary, broken down by month and bisected by AO. Contains a total YTD in the upper right
*Q Charts:*
- Graph sent to each AO channel of who has Q'd in the last month.
- Graph sent to the firstf channel, who has Q'd in the last month across the region bisected by AO.
*AO Leaderboards:*
- Two Graphs Sent to each AO channel
- PAX posts in last month
- PAX posts YTD
*Region:*
- Graph sent to the firstf channel of PAX Posts in the last month
- Graph sent to the firstf channel of PAX Posts YTD.
"""  # noqa: E501
        ),
    ]
)

CONFIG_NO_PAXMINER_FORM = orm.BlockView(
    blocks=[
        orm.SectionBlock(
            label="PAXMiner doesn't appear to be configured for this Slack workspace. Please follow <https://f3stlouis.com/paxminer-setup/|these instructions> to get started!",  # noqa: E501
        )
    ]
)

NO_WEASELBOT_CONFIG_FORM = orm.BlockView(
    blocks=[
        orm.SectionBlock(
            label="Weaselbot and / or PAXMiner doesn't appear to be configured for this Slack workspace. Please follow <https://github.com/F3Nation-Community/weaselbot|these instructions> to get started!",  # noqa: E501
        )
    ]
)

CONFIG_NO_PERMISSIONS_FORM = orm.BlockView(
    blocks=[
        orm.SectionBlock(
            label="You must be a Slack admin to access your Slackblast region settings. Your local Slack admin can follow <https://slack.com/help/articles/218124397-Change-a-members-role|these instructions> to grant you admin access.",  # noqa: E501
        )
    ]
)
