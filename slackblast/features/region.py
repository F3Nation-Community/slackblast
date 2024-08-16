import copy
import re
from logging import Logger

import requests
from slack_sdk.web import WebClient

from utilities.database import DbManager
from utilities.database.orm import Org, SlackSettings
from utilities.helper_functions import safe_get
from utilities.slack import actions, orm


def build_region_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    form = copy.deepcopy(REGION_FORM)
    org_record: Org = DbManager.get_record(Org, region_record.org_id)

    form.set_initial_values(
        {
            actions.REGION_NAME: org_record.name,
            actions.REGION_DESCRIPTION: org_record.description,
            actions.REGION_LOGO: org_record.logo,
            actions.REGION_WEBSITE: org_record.website,
            actions.REGION_EMAIL: org_record.email,
            actions.REGION_TWITTER: org_record.twitter,
            actions.REGION_FACEBOOK: org_record.facebook,
            actions.REGION_INSTAGRAM: org_record.instagram,
        }
    )

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Edit Region",
        callback_id=actions.REGION_CALLBACK_ID,
        new_or_add="add",
    )


def handle_region_edit(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form_data = REGION_FORM.get_selected_values(body)

    file = safe_get(form_data, actions.CALENDAR_ADD_AO_LOGO, 0)
    if file:
        try:
            r = requests.get(file["url_private_download"], headers={"Authorization": f"Bearer {client.token}"})
            r.raise_for_status()
            logo = r.content
        except Exception as exc:
            logger.error(f"Error downloading file: {exc}")
            logo = None
    else:
        logo = None

    email = safe_get(form_data, actions.REGION_EMAIL)
    if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        email = None

    website = safe_get(form_data, actions.REGION_WEBSITE)
    if not re.match(
        r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)", website
    ):
        website = None

    fields = {
        Org.name: safe_get(form_data, actions.REGION_NAME),
        Org.description: safe_get(form_data, actions.REGION_DESCRIPTION),
        Org.logo: logo,
        Org.website: website,
        Org.email: email,
        Org.twitter: safe_get(form_data, actions.REGION_TWITTER),
        Org.facebook: safe_get(form_data, actions.REGION_FACEBOOK),
        Org.instagram: safe_get(form_data, actions.REGION_INSTAGRAM),
    }

    DbManager.update_record(Org, region_record.org_id, fields)


REGION_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Region Title",
            action=actions.REGION_NAME,
            element=orm.PlainTextInputElement(placeholder="Enter the Region name"),
            optional=False,
        ),
        orm.InputBlock(
            label="Region Description",
            action=actions.REGION_DESCRIPTION,
            element=orm.PlainTextInputElement(placeholder="Enter a description for the Region", multiline=True),
            optional=True,
        ),
        orm.InputBlock(
            label="Region Logo",
            action=actions.REGION_LOGO,
            optional=True,
            element=orm.FileInputElement(
                max_files=1,
                filetypes=[
                    "png",
                    "jpg",
                    "heic",
                    "bmp",
                ],
            ),
        ),
        orm.InputBlock(
            label="Region Website",
            action=actions.REGION_WEBSITE,
            element=orm.URLInputElement(placeholder="Enter the Region website"),
            optional=True,
        ),
        orm.InputBlock(
            label="Region email",
            action=actions.REGION_EMAIL,
            element=orm.EmailInputElement(placeholder="Enter the Region email"),
            optional=True,
        ),
        orm.InputBlock(
            label="Region Twitter",
            action=actions.REGION_TWITTER,
            element=orm.PlainTextInputElement(placeholder="Enter the Region Twitter"),
            optional=True,
        ),
        orm.InputBlock(
            label="Region Facebook",
            action=actions.REGION_FACEBOOK,
            element=orm.PlainTextInputElement(placeholder="Enter the Region Facebook"),
            optional=True,
        ),
        orm.InputBlock(
            label="Region Instagram",
            action=actions.REGION_INSTAGRAM,
            element=orm.PlainTextInputElement(placeholder="Enter the Region Instagram"),
            optional=True,
        ),
    ]
)
