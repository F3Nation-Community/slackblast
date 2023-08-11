from typing import Any, List, Union, Dict
from dataclasses import dataclass, field
from slack_sdk.web import WebClient
import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from utilities.helper_functions import safe_get


@dataclass
class BaseElement:
    placeholder: str = None
    initial_value: str = None

    def make_placeholder_field(self):
        return {"placeholder": {"type": "plain_text", "text": self.placeholder, "emoji": True}}

    def get_selected_value():
        return "Not yet implemented"


@dataclass
class BaseBlock:
    label: str = None
    action: str = None
    element: BaseElement = None

    def make_label_field(self, text=None):
        return {"type": "plain_text", "text": text or self.label, "emoji": True}

    def as_form_field(self, initial_value=None):
        raise Exception("Not Implemented")

    def get_selected_value(self, input_data, action):
        return "Not yet implemented"


@dataclass
class BaseAction:
    label: str
    action: str

    def make_label_field(self, text=None):
        return {"type": "plain_text", "text": text or self.label, "emoji": True}

    def as_form_field(self, initial_value=None):
        raise Exception("Not Implemented")


@dataclass
class InputBlock(BaseBlock):
    optional: bool = True
    element: BaseElement = None
    dispatch_action: bool = False

    def get_selected_value(self, input_data):
        return self.element.get_selected_value(input_data, self.action)

    def as_form_field(self):
        block = {
            "type": "input",
            "block_id": self.action,
            "optional": self.optional,
            "label": self.make_label_field(),
        }
        block.update({"element": self.element.as_form_field(action=self.action)})
        if self.dispatch_action:
            block.update({"dispatch_action": True})
        return block


@dataclass
class SectionBlock(BaseBlock):
    element: BaseElement = None

    def get_selected_value(self, input_data, **kwargs):
        return self.element.get_selected_value(input_data, self.action, **kwargs)

    def as_form_field(self):
        block = {"type": "section", "block_id": self.action, "text": self.make_label_field()}
        block.update({"accessory": self.element.as_form_field(action=self.action)})
        return block


@dataclass
class ButtonElement(BaseAction):
    style: str = None
    value: str = None
    confirm: object = None
    url: str = None

    def as_form_field(self):
        j = {
            "type": "button",
            "text": self.make_label_field(),
            "action_id": self.action,
            "value": self.value or self.label,
        }
        if self.style:
            j["style"] = self.style
        if self.confirm:
            j["confirm"] = self.confirm
        if self.url:
            j["url"] = self.url
        return j


@dataclass
class SelectorOption:
    name: str
    value: str


def as_selector_options(names: List[str], values: List[str] = []) -> List[SelectorOption]:
    if values == []:
        selectors = [SelectorOption(name=x, value=x) for x in names]
    else:
        selectors = [SelectorOption(name=x, value=y) for x, y in zip(names, values)]
    return selectors


@dataclass
class StaticSelectElement(BaseElement):
    initial_value: str = None
    options: List[SelectorOption] = None

    # def with_options(self, options: List[SelectorOption]):
    #   return SelectorElement(self.label, self.action, options)

    def as_form_field(self, action: str):
        if not self.options:
            self.options = as_selector_options(["Default"])

        option_elements = [self.__make_option(o) for o in self.options]
        j = {"type": "static_select", "options": option_elements, "action_id": action}
        if self.placeholder:
            j.update(self.make_placeholder_field())

        initial_option = None
        if self.initial_value:
            initial_option = next(
                (x for x in option_elements if x["value"] == self.initial_value), None
            )
            if initial_option:
                j["initial_option"] = initial_option
        return j

    # def get_selected_value(self, input_data, action, text_too: bool = False):
    #   if text_too:
    #     return safe_get(input_data['actions'][0], 'selected_option', 'value'), safe_get(input_data['actions'][0], 'selected_option', 'text', 'text')
    #   else:
    #     return safe_get(input_data['actions'][0], 'selected_option', 'value')
    def get_selected_value(self, input_data, action):
        return safe_get(input_data, action, action, "selected_option", "value")

    def __make_option(self, option: SelectorOption):
        return {
            "text": {"type": "plain_text", "text": option.name, "emoji": True},
            "value": option.value,
        }


@dataclass
class RadioButtonsElement(BaseElement):
    initial_value: str = None
    options: List[SelectorOption] = None

    def get_selected_value(self, input_data, action):
        return safe_get(input_data, action, action, "selected_option", "value")

    def as_form_field(self, action: str):
        if not self.options:
            self.options = as_selector_options(["Default"])

        option_elements = [self.__make_option(o) for o in self.options]
        j = {
            "type": "radio_buttons",
            "options": option_elements,
            "action_id": action,
        }

        initial_option = None
        if self.initial_value:
            initial_option = next(
                (x for x in option_elements if x["value"] == self.initial_value), None
            )
            if initial_option:
                j["initial_option"] = initial_option
        return j

    def __make_option(self, option: SelectorOption):
        return {
            "text": {"type": "plain_text", "text": option.name, "emoji": True},
            "value": option.value,
        }


@dataclass
class PlainTextInputElement(BaseElement):
    initial_value: str = None
    multiline: bool = False
    max_length: int = None

    def get_selected_value(self, input_data, action):
        return safe_get(input_data, action, action, "value")

    def as_form_field(self, action: str):
        j = {
            "type": "plain_text_input",
            "action_id": action,
            "initial_value": self.initial_value or "",
        }
        if self.placeholder:
            j.update(self.make_placeholder_field())
        if self.multiline:
            j["multiline"] = True
        if self.max_length:
            j["max_length"] = self.max_length
        return j


@dataclass
class ChannelsSelectElement(BaseElement):
    initial_value: str = None

    def get_selected_value(self, input_data, action):
        return safe_get(input_data, action, action, "selected_channel")

    def as_form_field(self, action: str):
        j = {
            "type": "channels_select",
            "action_id": action,
        }
        if self.placeholder:
            j.update(self.make_placeholder_field())
        if self.initial_value:
            j["initial_channel"] = self.initial_value
        return j


@dataclass
class DatepickerElement(BaseElement):
    initial_value: str = None

    def get_selected_value(self, input_data, action):
        return safe_get(input_data, action, action, "selected_date")

    def as_form_field(self, action: str):
        j = {
            "type": "datepicker",
            "action_id": action,
        }
        if self.placeholder:
            j.update(self.make_placeholder_field())
        if self.initial_value:
            j["initial_date"] = self.initial_value
        return j


@dataclass
class TimepickerElement(BaseElement):
    initial_value: str = None

    def get_selected_value(self, input_data, action):
        return safe_get(input_data, action, action, "selected_time")

    def as_form_field(self, action: str):
        j = {
            "type": "timepicker",
            "action_id": action,
        }
        if self.placeholder:
            j.update(self.make_placeholder_field())
        if self.initial_value:
            j["initial_time"] = self.initial_value
        return j


@dataclass
class UsersSelectElement(BaseElement):
    initial_value: str = None

    def get_selected_value(self, input_data, action):
        return safe_get(input_data, action, action, "selected_user")

    def as_form_field(self, action: str):
        j = {
            "type": "users_select",
            "action_id": action,
        }
        if self.placeholder:
            j.update(self.make_placeholder_field())
        if self.initial_value:
            j["initial_user"] = self.initial_value
        return j


@dataclass
class MultiUsersSelectElement(BaseElement):
    initial_value: List[str] = None

    def get_selected_value(self, input_data, action):
        return safe_get(input_data, action, action, "selected_users")

    def as_form_field(self, action: str):
        j = {
            "type": "multi_users_select",
            "action_id": action,
        }
        if self.placeholder:
            j.update(self.make_placeholder_field())
        if self.initial_value:
            j["initial_users"] = self.initial_value
        return j


@dataclass
class ContextBlock(BaseBlock):
    text: str = ""

    def as_form_field(self):
        j = {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": self.text}],
        }
        if self.action:
            j["block_id"] = self.action
        return j


@dataclass
class DividerBlock(BaseBlock):
    def as_form_field(self):
        return {"type": "divider"}


@dataclass
class ActionsBlock(BaseBlock):
    elements: List[BaseAction] = field(default_factory=list)

    def as_form_field(self):
        j = {
            "type": "actions",
            "elements": [e.as_form_field() for e in self.elements],
        }
        if self.action:
            j["block_id"] = self.action
        return j


@dataclass
class BlockView:
    blocks: List[BaseBlock]

    def delete_block(self, action: str):
        self.blocks = [b for b in self.blocks if b.action != action]

    def add_block(self, block: BaseBlock):
        self.blocks.append(block)

    def set_initial_values(self, values: dict):
        for block in self.blocks:
            if block.action in values:
                block.element.initial_value = values[block.action]

    def set_options(self, options: Dict[str, List[SelectorOption]]):
        for block in self.blocks:
            if block.action in options:
                block.element.options = options[block.action]

    def as_form_field(self) -> List[dict]:
        return [b.as_form_field() for b in self.blocks]

    def get_selected_values(self, body) -> dict:
        values = body["view"]["state"]["values"]

        selected_values = {}
        for block in self.blocks:
            if isinstance(block, InputBlock):
                selected_values[block.action] = block.get_selected_value(values)

        return selected_values

    def post_modal(
        self,
        client: Any,
        trigger_id: str,
        title_text: str,
        callback_id: str,
        submit_button_text: str = "Submit",
        parent_metadata: str = None,
    ):
        blocks = self.as_form_field()
        if parent_metadata:
            blocks.append(ContextBlock(text=parent_metadata).as_form_field())

        view = {
            "type": "modal",
            "callback_id": callback_id,
            "title": {"type": "plain_text", "text": title_text},
            "blocks": blocks,
        }

        if submit_button_text != "None":  # TODO: would prefer this to use None instead of "None"
            view["submit"] = {"type": "plain_text", "text": submit_button_text}

        res = client.views_open(trigger_id=trigger_id, view=view)

    def update_modal(
        self,
        client: Any,
        view_id: str,
        title_text: str,
        callback_id: str,
        submit_button_text: str = "Submit",
        parent_metadata: str = None,
    ):
        blocks = self.as_form_field()
        if parent_metadata:
            blocks.append(ContextBlock(text=parent_metadata).as_form_field())

        view = {
            "type": "modal",
            "callback_id": callback_id,
            "title": {"type": "plain_text", "text": title_text},
            "submit": {"type": "plain_text", "text": submit_button_text},
            "blocks": blocks,
        }

        res = client.views_update(view_id=view_id, view=view)


class DividerBlock(BaseBlock):
    def as_form_field(self):
        return {"type": "divider"}
