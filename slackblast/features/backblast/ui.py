from utilities import constants
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
                filetypes=constants.ALLOWED_BOYBAND_FILETYPES,
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
