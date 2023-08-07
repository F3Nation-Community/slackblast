import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from utilities.slack import orm, actions

from utilities import constants

BACKBLAST_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Title",
            action=actions.BACKBLAST_TITLE,
            optional=False,
            element=orm.PlainTextInputElement(placeholder="Enter a workout title..."),
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
            text=":warning: :warning: *WARNING*: duplicate backblast detected in PAXMiner DB for this Q, AO, and date; this backblast will not be saved as-is. Please modify one of these selections",
            action=actions.BACKBLAST_DUPLICATE_WARNING,
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
            text="If left blank, this will be calculated automatically from the fields above."
        ),
        orm.InputBlock(
            label="The Moleskin",
            action=actions.BACKBLAST_MOLESKIN,
            optional=False,
            element=orm.PlainTextInputElement(
                placeholder="Tell us what happened\n\n",
                initial_value="\n*WARMUP:* \n*THE THANG:* \n*MARY:* \n*ANNOUNCEMENTS:* \n*COT:* ",
                multiline=True,
                max_length=3000,
            ),
        ),
        orm.ContextBlock(
            text="If trying to tag PAX in here, substitute _ for spaces and do not include titles in parenthesis (ie, @Moneyball not @Moneyball_(F3_STC)). Spelling is important, capitalization is not!"
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
                options=orm.as_selector_options(
                    names=["Send Email", "Don't Send Email"], values=["yes", "no"]
                ),
                initial_value="yes",
            ),
        ),
        orm.ContextBlock(
            text="*Do not hit Submit more than once!* Even if you get a timeout error, the backblast has likely already been posted. If using email, this can take time and this form may not automatically close."
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
        # orm.InputBlock(
        #   label="The Why",
        #   action=actions.PREBLAST_WHY,
        #   optional=True,
        #   element=orm.PlainTextInputElement(
        #     placeholder="[Optional] Explain the Why...",
        #   )
        # ),
        # orm.InputBlock(
        #   label="Coupons?",
        #   action=actions.PREBLAST_COUPONS,
        #   optional=True,
        #   element=orm.PlainTextInputElement( # TODO: change to radio buttons or checkboxes
        #     placeholder="Coupons or not?",
        #   )
        # ),
        # orm.InputBlock(
        #   label="FNGs",
        #   action=actions.PREBLAST_FNGS,
        #   optional=True,
        #   element=orm.PlainTextInputElement(
        #     placeholder="Any message for FNGs?",
        #   )
        # ),
        orm.InputBlock(
            label="Moleskin",
            action=actions.PREBLAST_MOLESKIN,
            optional=True,
            element=orm.PlainTextInputElement(
                placeholder="A hint of what you're planning...",
                multiline=True,
                max_length=3000,
            ),
        ),
        orm.DividerBlock(),
        orm.InputBlock(
            label="Choose where to post this",
            action=actions.PREBLAST_DESTINATION,
            optional=False,
            element=orm.StaticSelectElement(placeholder="Select a destination..."),
        ),
        orm.ContextBlock(
            text="*Do not hit Submit more than once!* Even if you get a timeout error, the preblast has likely already been posted. This form may not automatically close."
        ),
    ]
)

CONFIG_FORM = orm.BlockView(
    [
        # orm.InputBlock(
        #     label="Paxminer Region Database",
        #     action=actions.CONFIG_PAXMINER_DB,
        #     optional=False,
        #     element=orm.StaticSelectElement(placeholder="Select your database..."),
        # ),
        # orm.InputBlock(
        #     label="Other (if not listed above)",
        #     action=actions.CONFIG_PAXMINER_DB_OTHER,
        #     optional=False,
        #     element=orm.PlainTextInputElement(initial_value="OtherDBName"),
        # ),
        orm.InputBlock(
            label="Slackblast Email",
            action=actions.CONFIG_EMAIL_ENABLE,
            optional=False,
            element=orm.RadioButtonsElement(
                initial_value="disable",
                options=orm.as_selector_options(
                    names=["Enable Email", "Disable Email"], values=["enable", "disable"]
                ),
            ),
            dispatch_action=True,
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
            text="If using gmail, you must use an App Password (https://support.google.com/accounts/answer/185833). Your password will be stored encrypted - however, it is STRONGLY recommended that you use a non-personal email address and password for this purpose, as security cannot be guaranteed.",
            action=actions.CONFIG_PASSWORD_CONTEXT,
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
            text="This will put the AO name as a category for the post, and will put PAX names at the end as tags.",
            action=actions.CONFIG_POSTIE_CONTEXT,
        ),
        orm.InputBlock(
            label="Lock editing of backblasts?",
            action=actions.CONFIG_EDITING_LOCKED,
            optional=False,
            element=orm.RadioButtonsElement(
                initial_value="no",
                options=orm.as_selector_options(names=["Yes", "No"], values=["yes", "no"]),
            ),
        ),
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
    ]
)
