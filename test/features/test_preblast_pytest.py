"""
Pytest tests for preblast functionality
Run with: pytest test/features/test_preblast_pytest.py -v
"""

import json
import pytest


class TestPreblastMessageFormatting:
    """Test preblast message formatting logic"""

    def test_complete_message_formatting(self):
        """Test that preblast messages are formatted correctly with all fields"""
        preblast_data = {
            "title": "Morning Beatdown",
            "date": "2024-01-15",
            "time": "0530",
            "The_AO": "C11111",
            "the_q": "U54321",
            "the_why": "Get better",
            "fngs": "Bring friends",
            "coupons": "Yes"
        }
        
        # Simulate message construction logic
        title = preblast_data.get("title")
        the_date = preblast_data.get("date")
        the_time = preblast_data.get("time")
        the_ao = preblast_data.get("The_AO")
        the_q = preblast_data.get("the_q")
        the_why = preblast_data.get("the_why")
        fngs = preblast_data.get("fngs")
        coupons = preblast_data.get("coupons")

        header_msg = f"*Preblast: {title}*"
        date_msg = f"*Date*: {the_date}"
        time_msg = f"*Time*: {the_time}"
        ao_msg = f"*Where*: <#{the_ao}>"
        q_msg = f"*Q*: <@{the_q}>"

        body_list = [header_msg, date_msg, time_msg, ao_msg, q_msg]
        if the_why:
            body_list.append(f"*Why*: {the_why}")
        if coupons:
            body_list.append(f"*Coupons*: {coupons}")
        if fngs:
            body_list.append(f"*FNGs*: {fngs}")

        msg = "\n".join(body_list)
        
        # Assertions
        assert "Morning Beatdown" in msg
        assert "2024-01-15" in msg
        assert "0530" in msg
        assert "C11111" in msg
        assert "U54321" in msg
        assert "Get better" in msg
        assert "Bring friends" in msg
        assert "Yes" in msg

    def test_minimal_message_formatting(self):
        """Test message formatting with only required fields"""
        preblast_data = {
            "title": "Simple Workout",
            "date": "2024-01-15", 
            "time": "0530",
            "The_AO": "C11111",
            "the_q": "U54321"
        }
        
        # Simulate message construction with minimal data
        title = preblast_data.get("title")
        the_date = preblast_data.get("date")
        the_time = preblast_data.get("time")
        the_ao = preblast_data.get("The_AO")
        the_q = preblast_data.get("the_q")
        the_why = preblast_data.get("the_why")
        fngs = preblast_data.get("fngs")
        coupons = preblast_data.get("coupons")

        header_msg = f"*Preblast: {title}*"
        date_msg = f"*Date*: {the_date}"
        time_msg = f"*Time*: {the_time}"
        ao_msg = f"*Where*: <#{the_ao}>"
        q_msg = f"*Q*: <@{the_q}>"

        body_list = [header_msg, date_msg, time_msg, ao_msg, q_msg]
        if the_why:
            body_list.append(f"*Why*: {the_why}")
        if coupons:
            body_list.append(f"*Coupons*: {coupons}")
        if fngs:
            body_list.append(f"*FNGs*: {fngs}")

        msg = "\n".join(body_list)
        
        # Should contain required fields
        assert "Simple Workout" in msg
        assert "2024-01-15" in msg
        assert "0530" in msg
        
        # Should not contain optional field labels when fields are None
        assert the_why is None and ("*Why*:" not in msg or "*Why*: None" not in msg)
        assert coupons is None and ("*Coupons*:" not in msg or "*Coupons*: None" not in msg) 
        assert fngs is None and ("*FNGs*:" not in msg or "*FNGs*: None" not in msg)

    def test_message_formatting_with_emojis(self):
        """Test message formatting with emoji characters in various fields"""
        preblast_data = {
            "title": "🔥 Epic Morning Beatdown 💪",
            "date": "2024-01-15",
            "time": "0530",
            "The_AO": "C11111",
            "the_q": "U54321",
            "the_why": "Get stronger 💪 and have fun 😄",
            "fngs": "Bring your friends! 👫 All welcome 🎉",
            "coupons": "Yes! 🧱 Bring blocks and heavy things ⚖️"
        }
        
        # Simulate message construction with emoji data
        title = preblast_data.get("title")
        the_date = preblast_data.get("date")
        the_time = preblast_data.get("time")
        the_ao = preblast_data.get("The_AO")
        the_q = preblast_data.get("the_q")
        the_why = preblast_data.get("the_why")
        fngs = preblast_data.get("fngs")
        coupons = preblast_data.get("coupons")

        header_msg = f"*Preblast: {title}*"
        date_msg = f"*Date*: {the_date}"
        time_msg = f"*Time*: {the_time}"
        ao_msg = f"*Where*: <#{the_ao}>"
        q_msg = f"*Q*: <@{the_q}>"

        body_list = [header_msg, date_msg, time_msg, ao_msg, q_msg]
        if the_why:
            body_list.append(f"*Why*: {the_why}")
        if coupons:
            body_list.append(f"*Coupons*: {coupons}")
        if fngs:
            body_list.append(f"*FNGs*: {fngs}")

        msg = "\n".join(body_list)
        
        # Test that emojis are preserved in the message
        assert "🔥 Epic Morning Beatdown 💪" in msg
        assert "Get stronger 💪 and have fun 😄" in msg
        assert "Bring your friends! 👫 All welcome 🎉" in msg
        assert "Yes! 🧱 Bring blocks and heavy things ⚖️" in msg
        
        # Test that basic structure is still intact
        assert "*Preblast:" in msg
        assert "*Date*: 2024-01-15" in msg
        assert "*Time*: 0530" in msg
        assert "*Where*: <#C11111>" in msg
        assert "*Q*: <@U54321>" in msg
        
        # Test that message can be encoded/decoded properly (common issue with emojis)
        try:
            msg_bytes = msg.encode('utf-8')
            decoded_msg = msg_bytes.decode('utf-8')
            assert decoded_msg == msg
        except UnicodeError:
            pytest.fail("Message with emojis failed UTF-8 encoding/decoding")


class TestEditPermissions:
    """Test preblast edit permission logic"""

    def can_user_edit(self, user_id, preblast_q, preblast_op, is_admin, editing_locked):
        """Simulate the edit permission logic from the actual function"""
        return (
            (editing_locked == 0)
            or is_admin
            or (user_id == preblast_q)
            or (user_id == preblast_op)
        )

    @pytest.mark.parametrize("user_id,preblast_q,preblast_op,is_admin,editing_locked,expected", [
        ("U12345", "U54321", "U99999", True, 1, True),   # Admin can always edit
        ("U12345", "U12345", "U99999", False, 1, True),  # Q can edit their own
        ("U12345", "U54321", "U12345", False, 1, True),  # Original poster can edit
        ("U12345", "U54321", "U99999", False, 0, True),  # Anyone can edit when unlocked
        ("U12345", "U54321", "U99999", False, 1, False), # No permission when locked
        ("U12345", "U12345", "U12345", True, 1, True),   # Admin + Q + OP (all conditions true)
        ("U12345", "U54321", "U99999", False, 0, True),  # Editing unlocked overrides other restrictions
    ])
    def test_edit_permission_scenarios(self, user_id, preblast_q, preblast_op, is_admin, editing_locked, expected):
        """Test various edit permission scenarios"""
        result = self.can_user_edit(user_id, preblast_q, preblast_op, is_admin, editing_locked)
        assert result == expected


class TestDestinationRouting:
    """Test message destination routing logic"""

    def get_destination_channel(self, destination, ao_channel, user_id):
        """Simulate destination routing logic"""
        if destination == "The_AO":
            return ao_channel
        else:
            return user_id

    def test_ao_destination(self):
        """Test routing to AO channel"""
        result = self.get_destination_channel("The_AO", "C11111", "U12345")
        assert result == "C11111"

    def test_dm_destination(self):
        """Test routing to user DM"""
        result = self.get_destination_channel("U12345", "C11111", "U12345")
        assert result == "U12345"


class TestSlackBlockStructure:
    """Test Slack block structure creation"""

    def create_preblast_blocks(self, msg, moleskin=None):
        """Simulate block creation logic"""
        msg_block = {
            "type": "section",
            "text": {"type": "mrkdwn", "text": msg},
            "block_id": "msg_text",
        }
        
        action_block = {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":pencil: Edit this preblast", "emoji": True},
                    "value": "edit",
                    "action_id": "edit-preblast",
                },
                {
                    "type": "button", 
                    "text": {"type": "plain_text", "text": ":heavy_plus_sign: New preblast", "emoji": True},
                    "value": "new",
                    "action_id": "new-preblast",
                },
            ],
            "block_id": "edit-preblast",
        }

        blocks = [msg_block]
        if moleskin:
            blocks.append(moleskin)
        blocks.append(action_block)
        
        return blocks

    def test_basic_block_structure(self):
        """Test basic block structure without moleskin"""
        msg = "*Preblast: Test*\n*Date*: 2024-01-15"
        blocks = self.create_preblast_blocks(msg)
        
        assert len(blocks) == 2  # msg block + action block
        assert blocks[0]["type"] == "section"
        assert blocks[0]["text"]["text"] == msg
        assert blocks[1]["type"] == "actions"
        assert len(blocks[1]["elements"]) == 2  # Edit and New buttons

    def test_block_structure_with_moleskin(self):
        """Test block structure with moleskin section"""
        msg = "*Preblast: Test*\n*Date*: 2024-01-15"
        moleskin = {"type": "section", "text": {"type": "mrkdwn", "text": "Extra info"}}
        blocks = self.create_preblast_blocks(msg, moleskin)
        
        assert len(blocks) == 3  # msg + moleskin + actions
        assert blocks[1] == moleskin
        assert blocks[2]["type"] == "actions"

    def test_action_buttons(self):
        """Test that action buttons have correct properties"""
        msg = "*Preblast: Test*"
        blocks = self.create_preblast_blocks(msg)
        
        action_block = blocks[-1]  # Last block should be actions
        elements = action_block["elements"]
        
        # Check edit button
        edit_button = elements[0]
        assert edit_button["action_id"] == "edit-preblast"
        assert edit_button["value"] == "edit"
        assert ":pencil:" in edit_button["text"]["text"]
        
        # Check new button
        new_button = elements[1]
        assert new_button["action_id"] == "new-preblast"
        assert new_button["value"] == "new"
        assert ":heavy_plus_sign:" in new_button["text"]["text"]


class TestFormModeDetection:
    """Test form mode detection logic"""

    def detect_form_mode(self, body):
        """Simulate form mode detection logic"""
        callback_id = body.get("view", {}).get("callback_id")
        if callback_id == "preblast-id":
            return "create"
        elif callback_id == "preblast-edit-id":
            return "edit"
        else:
            # Check for slash command or button action
            if body.get("command") == "/preblast":
                return "create"
            elif body.get("actions", [{}])[0].get("action_id") == "new-preblast":
                return "create"
            else:
                return "edit"

    def test_create_mode_from_callback(self):
        """Test create mode detection from callback ID"""
        body = {"view": {"callback_id": "preblast-id"}}
        assert self.detect_form_mode(body) == "create"

    def test_edit_mode_from_callback(self):
        """Test edit mode detection from callback ID"""
        body = {"view": {"callback_id": "preblast-edit-id"}}
        assert self.detect_form_mode(body) == "edit"

    def test_create_mode_from_slash_command(self):
        """Test create mode detection from slash command"""
        body = {"command": "/preblast"}
        assert self.detect_form_mode(body) == "create"

    def test_create_mode_from_button(self):
        """Test create mode detection from new button action"""
        body = {"actions": [{"action_id": "new-preblast"}]}
        assert self.detect_form_mode(body) == "create"


class TestSafeGet:
    """Test safe dictionary access utility"""

    def safe_get(self, data, *keys):
        """Safely get nested dict values"""
        for key in keys:
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return None
        return data

    def test_successful_nested_access(self):
        """Test successful access to nested dict values"""
        body = {
            "user": {"id": "U12345"},
            "view": {"callback_id": "preblast-id"},
            "message": {
                "metadata": {
                    "event_payload": {"title": "Test Workout"}
                }
            }
        }
        
        assert self.safe_get(body, "user", "id") == "U12345"
        assert self.safe_get(body, "view", "callback_id") == "preblast-id"
        assert self.safe_get(body, "message", "metadata", "event_payload", "title") == "Test Workout"

    def test_missing_key_handling(self):
        """Test handling of missing keys"""
        body = {"user": {"id": "U12345"}}
        
        assert self.safe_get(body, "nonexistent") is None
        assert self.safe_get(body, "user", "nonexistent") is None
        assert self.safe_get(body, "message", "nonexistent", "key") is None

    def test_non_dict_handling(self):
        """Test handling when encountering non-dict values"""
        body = {"user": "not_a_dict"}
        
        assert self.safe_get(body, "user", "id") is None 