import copy

from utilities.database.orm import Region
from utilities.helper_functions import safe_get
from utilities.slack import actions, forms
from utilities.slack import orm as slack_orm


def add_custom_field_blocks(form: slack_orm.BlockView, region_record: Region) -> slack_orm.BlockView:
    output_form = copy.deepcopy(form)
    for custom_field in (region_record.custom_fields or {}).values():
        if safe_get(custom_field, "enabled"):
            output_form.add_block(
                slack_orm.InputBlock(
                    element=forms.CUSTOM_FIELD_TYPE_MAP[custom_field["type"]],
                    action=actions.CUSTOM_FIELD_PREFIX + custom_field["name"],
                    label=custom_field["name"],
                    optional=True,
                )
            )
            if safe_get(custom_field, "type") == "Dropdown":
                output_form.set_options(
                    {
                        actions.CUSTOM_FIELD_PREFIX + custom_field["name"]: slack_orm.as_selector_options(
                            names=custom_field["options"],
                            values=custom_field["options"],
                        )
                    }
                )
    return output_form
