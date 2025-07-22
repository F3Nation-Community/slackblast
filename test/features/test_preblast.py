import json
import os
import sys
from unittest.mock import MagicMock, patch, call
from datetime import datetime

# Mock the database and utility modules before importing
sys.modules['slackblast.utilities.database'] = MagicMock()
sys.modules['slackblast.utilities.database.orm'] = MagicMock()
sys.modules['slackblast.utilities.helper_functions'] = MagicMock()
sys.modules['slackblast.utilities.slack'] = MagicMock()
sys.modules['slackblast.utilities.slack.actions'] = MagicMock()
sys.modules['slackblast.utilities.slack.forms'] = MagicMock()
sys.modules['slackblast.utilities.slack.orm'] = MagicMock()

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

# Now we can mock the specific modules we need
with patch.dict('sys.modules', {
    'utilities.database': MagicMock(),
    'utilities.database.orm': MagicMock(),
    'utilities.helper_functions': MagicMock(),
    'utilities.slack': MagicMock(),
    'utilities.slack.actions': MagicMock(),  
    'utilities.slack.forms': MagicMock(),
    'utilities.slack.orm': MagicMock(),
}):
    from slackblast.features.preblast import build_preblast_form, handle_preblast_post, handle_preblast_edit_button

# Mock the actions constants we need for testing
class MockActions:
    LOADING_ID = "loading"
    PREBLAST_CALLBACK_ID = "preblast-id"
    PREBLAST_EDIT_CALLBACK_ID = "preblast-edit-id"
    PREBLAST_NEW_BUTTON = "new-preblast"
    PREBLAST_TITLE = "title"
    PREBLAST_DATE = "date"
    PREBLAST_TIME = "time"
    PREBLAST_AO = "The_AO"
    PREBLAST_Q = "the_q"
    PREBLAST_WHY = "the_why"
    PREBLAST_FNGS = "fngs"
    PREBLAST_COUPONS = "coupons"
    PREBLAST_MOLESKIN = "moleskin"
    PREBLAST_DESTINATION = "destination"
    PREBLAST_OP = "preblast_original_poster"
    PREBLAST_EDIT_BUTTON = "edit-preblast"

actions = MockActions()


class TestBuildPreblastForm:
    """Test cases for build_preblast_form function"""

    def setup_method(self):
        """Set up common test fixtures"""
        self.mock_client = MagicMock()
        self.mock_logger = MagicMock()
        self.mock_context = {}
        self.mock_region = MagicMock()
        self.mock_region.preblast_moleskin_template = "Default moleskin template"

    def test_build_preblast_form_new_slash_command(self):
        """Test building a new preblast form from /preblast command"""
        body = {
            "command": "/preblast",
            "user_id": "U12345",
            "channel_id": "C67890",
            actions.LOADING_ID: "view_123"
        }

        with patch('slackblast.features.preblast.copy.deepcopy') as mock_deepcopy, \
             patch('slackblast.features.preblast.forms.PREBLAST_FORM') as mock_form, \
             patch('slackblast.features.preblast.slack_orm.as_selector_options') as mock_options, \
             patch('slackblast.features.preblast.datetime') as mock_datetime:
            
            mock_form_instance = MagicMock()
            mock_deepcopy.return_value = mock_form_instance
            mock_datetime.now.return_value.strftime.return_value = "2024-01-15"
            mock_options.return_value = ["option1", "option2"]

            build_preblast_form(body, self.mock_client, self.mock_logger, self.mock_context, self.mock_region)

            # Verify form was configured for new preblast
            mock_form_instance.set_options.assert_called_once()
            mock_form_instance.set_initial_values.assert_called()
            mock_form_instance.update_modal.assert_called_with(
                client=self.mock_client,
                view_id="view_123",
                callback_id=actions.PREBLAST_CALLBACK_ID,
                title_text="New Preblast",
                parent_metadata={}
            )

    def test_build_preblast_form_new_button_action(self):
        """Test building a new preblast form from button action"""
        body = {
            "actions": [{"action_id": actions.PREBLAST_NEW_BUTTON}],
            "user": {"id": "U12345"},
            "channel": {"id": "C67890"},
            actions.LOADING_ID: "view_456"
        }

        with patch('slackblast.features.preblast.copy.deepcopy') as mock_deepcopy, \
             patch('slackblast.features.preblast.forms.PREBLAST_FORM') as mock_form, \
             patch('slackblast.features.preblast.slack_orm.as_selector_options') as mock_options, \
             patch('slackblast.features.preblast.datetime') as mock_datetime:
            
            mock_form_instance = MagicMock()
            mock_deepcopy.return_value = mock_form_instance
            mock_datetime.now.return_value.strftime.return_value = "2024-01-15"

            build_preblast_form(body, self.mock_client, self.mock_logger, self.mock_context, self.mock_region)

            # Should still create new preblast
            mock_form_instance.update_modal.assert_called_with(
                client=self.mock_client,
                view_id="view_456",
                callback_id=actions.PREBLAST_CALLBACK_ID,
                title_text="New Preblast",
                parent_metadata={}
            )

    def test_build_preblast_form_edit_existing(self):
        """Test building form for editing existing preblast"""
        metadata = {"channel_id": "C67890", "message_ts": "1234567890.123"}
        body = {
            "view": {"private_metadata": json.dumps(metadata)},
            "message": {
                "metadata": {"event_payload": {"title": "Test Workout"}},
                "blocks": [
                    {"type": "section"},
                    {"type": "section", "some_key": "value"},
                    {"type": "actions"}
                ]
            },
            "user": {"id": "U12345"},
            actions.LOADING_ID: "view_789"
        }

        with patch('slackblast.features.preblast.copy.deepcopy') as mock_deepcopy, \
             patch('slackblast.features.preblast.forms.PREBLAST_FORM') as mock_form, \
             patch('slackblast.features.preblast.remove_keys_from_dict') as mock_remove_keys:
            
            mock_form_instance = MagicMock()
            mock_deepcopy.return_value = mock_form_instance
            mock_remove_keys.return_value = {"cleaned": "block"}

            build_preblast_form(body, self.mock_client, self.mock_logger, self.mock_context, self.mock_region)

            # Verify form was configured for editing
            mock_form_instance.delete_block.assert_called_with(actions.PREBLAST_DESTINATION)
            mock_form_instance.set_initial_values.assert_called()
            mock_form_instance.update_modal.assert_called_with(
                client=self.mock_client,
                view_id="view_789",
                callback_id=actions.PREBLAST_EDIT_CALLBACK_ID,
                title_text="Edit Preblast",
                parent_metadata=metadata
            )


class TestHandlePreblastPost:
    """Test cases for handle_preblast_post function"""

    def setup_method(self):
        """Set up common test fixtures"""
        self.mock_client = MagicMock()
        self.mock_logger = MagicMock()
        self.mock_context = {}
        self.mock_region = MagicMock()
        self.mock_region.paxminer_schema = "test_schema"
        self.mock_region.workspace_name = "Test Workspace"

    def test_handle_preblast_post_create_new(self):
        """Test creating a new preblast post"""
        body = {
            "view": {"callback_id": actions.PREBLAST_CALLBACK_ID},
            "user_id": "U12345"
        }

        mock_preblast_data = {
            actions.PREBLAST_TITLE: "Morning Beatdown",
            actions.PREBLAST_DATE: "2024-01-15",
            actions.PREBLAST_TIME: "0530",
            actions.PREBLAST_AO: "C11111",
            actions.PREBLAST_Q: "U54321",
            actions.PREBLAST_WHY: "Get better",
            actions.PREBLAST_FNGS: "Bring friends",
            actions.PREBLAST_COUPONS: "Yes",
            actions.PREBLAST_MOLESKIN: {"type": "section", "text": "Extra info"},
            actions.PREBLAST_DESTINATION: "The_AO"
        }

        with patch('slackblast.features.preblast.forms.PREBLAST_FORM') as mock_form, \
             patch('slackblast.features.preblast.DbManager.find_records') as mock_db, \
             patch('slackblast.features.preblast.get_user_names') as mock_get_names:
            
            mock_form.get_selected_values.return_value = mock_preblast_data.copy()
            mock_get_names.return_value = (["Test User"], ["http://example.com/avatar.jpg"])

            handle_preblast_post(body, self.mock_client, self.mock_logger, self.mock_context, self.mock_region)

            # Verify message was posted
            self.mock_client.chat_postMessage.assert_called_once()
            call_args = self.mock_client.chat_postMessage.call_args
            
            assert "Morning Beatdown" in call_args[1]["text"]
            assert "2024-01-15" in call_args[1]["text"]
            assert "0530" in call_args[1]["text"]
            assert call_args[1]["channel"] == "C11111"  # The_AO maps to the AO channel
            assert call_args[1]["username"] == "Test User (via Slackblast)"

    def test_handle_preblast_post_edit_existing(self):
        """Test editing an existing preblast post"""
        metadata = {"channel_id": "C67890", "message_ts": "1234567890.123"}
        body = {
            "view": {
                "callback_id": actions.PREBLAST_EDIT_CALLBACK_ID,
                "private_metadata": json.dumps(metadata)
            },
            "user": {"id": "U12345"}
        }

        mock_preblast_data = {
            actions.PREBLAST_TITLE: "Updated Beatdown",
            actions.PREBLAST_DATE: "2024-01-16",
            actions.PREBLAST_TIME: "0545",
            actions.PREBLAST_AO: "C22222",
            actions.PREBLAST_Q: "U67890",
            actions.PREBLAST_MOLESKIN: {"type": "section"}
        }

        with patch('slackblast.features.preblast.forms.PREBLAST_FORM') as mock_form, \
             patch('slackblast.features.preblast.get_user_names') as mock_get_names:
            
            mock_form.get_selected_values.return_value = mock_preblast_data.copy()
            mock_get_names.return_value = (["Updated User"], ["http://example.com/updated.jpg"])

            handle_preblast_post(body, self.mock_client, self.mock_logger, self.mock_context, self.mock_region)

            # Verify message was updated
            self.mock_client.chat_update.assert_called_once()
            call_args = self.mock_client.chat_update.call_args
            
            assert call_args[1]["channel"] == "C67890"
            assert call_args[1]["ts"] == "1234567890.123"
            assert "Updated Beatdown" in call_args[1]["text"]

    def test_handle_preblast_post_minimal_data(self):
        """Test posting with minimal required data (no optional fields)"""
        body = {
            "view": {"callback_id": actions.PREBLAST_CALLBACK_ID},
            "user_id": "U12345"
        }

        mock_preblast_data = {
            actions.PREBLAST_TITLE: "Simple Workout",
            actions.PREBLAST_DATE: "2024-01-15",
            actions.PREBLAST_TIME: "0530",
            actions.PREBLAST_AO: "C11111",
            actions.PREBLAST_Q: "U54321",
            actions.PREBLAST_DESTINATION: "U12345"  # DM to user
        }

        with patch('slackblast.features.preblast.forms.PREBLAST_FORM') as mock_form, \
             patch('slackblast.features.preblast.get_user_names') as mock_get_names:
            
            mock_form.get_selected_values.return_value = mock_preblast_data.copy()
            mock_get_names.return_value = (["Test User"], ["http://example.com/avatar.jpg"])

            handle_preblast_post(body, self.mock_client, self.mock_logger, self.mock_context, self.mock_region)

            # Verify message was posted to user's DM
            call_args = self.mock_client.chat_postMessage.call_args
            assert call_args[1]["channel"] == "U12345"
            
            # Should not contain optional fields
            assert "Why" not in call_args[1]["text"]
            assert "Coupons" not in call_args[1]["text"]
            assert "FNGs" not in call_args[1]["text"]


class TestHandlePreblastEditButton:
    """Test cases for handle_preblast_edit_button function"""

    def setup_method(self):
        """Set up common test fixtures"""
        self.mock_client = MagicMock()
        self.mock_logger = MagicMock()
        self.mock_context = {}
        self.mock_region = MagicMock()
        self.mock_region.editing_locked = 0

    def test_handle_preblast_edit_button_allowed_admin(self):
        """Test edit button when user is admin (should be allowed)"""
        body = {
            "user_id": "U12345",
            "channel_id": "C67890",
            "message": {
                "metadata": {
                    "event_payload": {
                        actions.PREBLAST_Q: "U54321",
                        actions.PREBLAST_OP: "U99999"
                    }
                }
            }
        }

        self.mock_client.users_info.return_value = {
            "user": {"is_admin": True}
        }

        with patch('slackblast.features.preblast.build_preblast_form') as mock_build:
            handle_preblast_edit_button(body, self.mock_client, self.mock_logger, self.mock_context, self.mock_region)

            # Should call build_preblast_form for editing
            mock_build.assert_called_once_with(
                body=body,
                client=self.mock_client,
                logger=self.mock_logger,
                context=self.mock_context,
                region_record=self.mock_region
            )

    def test_handle_preblast_edit_button_allowed_original_q(self):
        """Test edit button when user is the original Q (should be allowed)"""
        body = {
            "user": {"id": "U12345"},
            "channel": {"id": "C67890"},
            "message": {
                "metadata": {
                    "event_payload": {
                        actions.PREBLAST_Q: "U12345",  # Same as user_id
                        actions.PREBLAST_OP: "U99999"
                    }
                }
            }
        }

        self.mock_client.users_info.return_value = {
            "user": {"is_admin": False}
        }

        with patch('slackblast.features.preblast.build_preblast_form') as mock_build:
            handle_preblast_edit_button(body, self.mock_client, self.mock_logger, self.mock_context, self.mock_region)

            mock_build.assert_called_once()

    def test_handle_preblast_edit_button_allowed_original_poster(self):
        """Test edit button when user is the original poster (should be allowed)"""
        body = {
            "user_id": "U12345",
            "channel_id": "C67890",
            "message": {
                "metadata": {
                    "event_payload": {
                        actions.PREBLAST_Q: "U54321",
                        actions.PREBLAST_OP: "U12345"  # Same as user_id
                    }
                }
            }
        }

        self.mock_client.users_info.return_value = {
            "user": {"is_admin": False}
        }

        with patch('slackblast.features.preblast.build_preblast_form') as mock_build:
            handle_preblast_edit_button(body, self.mock_client, self.mock_logger, self.mock_context, self.mock_region)

            mock_build.assert_called_once()

    def test_handle_preblast_edit_button_not_allowed(self):
        """Test edit button when user is not allowed to edit"""
        body = {
            "user_id": "U12345",
            "channel_id": "C67890",
            "message": {
                "metadata": {
                    "event_payload": {
                        actions.PREBLAST_Q: "U54321",
                        actions.PREBLAST_OP: "U99999"
                    }
                }
            }
        }

        # User is not admin, not Q, not original poster
        self.mock_client.users_info.return_value = {
            "user": {"is_admin": False}
        }
        
        # Editing is locked
        self.mock_region.editing_locked = 1

        with patch('slackblast.features.preblast.build_preblast_form') as mock_build:
            handle_preblast_edit_button(body, self.mock_client, self.mock_logger, self.mock_context, self.mock_region)

            # Should not call build_preblast_form
            mock_build.assert_not_called()
            
            # Should send ephemeral message
            self.mock_client.chat_postEphemeral.assert_called_once_with(
                text="Editing this preblast is only allowed for the Q, the original poster, or your local Slack admins. "
                     "Please contact one of them to make changes.",
                channel="C67890",
                user="U12345"
            )

    def test_handle_preblast_edit_button_json_fallback(self):
        """Test edit button with JSON fallback for preblast data"""
        body = {
            "user_id": "U12345",
            "channel_id": "C67890",
            "actions": [{"value": json.dumps({actions.PREBLAST_Q: "U12345", actions.PREBLAST_OP: "U12345"})}]
        }

        self.mock_client.users_info.return_value = {
            "user": {"is_admin": False}
        }

        with patch('slackblast.features.preblast.build_preblast_form') as mock_build:
            handle_preblast_edit_button(body, self.mock_client, self.mock_logger, self.mock_context, self.mock_region)

            # Should still work with JSON fallback
            mock_build.assert_called_once()


# Helper functions for running tests
def test_safe_get_in_preblast_context():
    """Test that safe_get works correctly in preblast context"""
    from slackblast.utilities.helper_functions import safe_get
    
    # Test typical preblast body structure
    body = {
        "user": {"id": "U12345"},
        "view": {"callback_id": "preblast-id"},
        "message": {
            "metadata": {
                "event_payload": {
                    "title": "Test Workout"
                }
            }
        }
    }
    
    assert safe_get(body, "user", "id") == "U12345"
    assert safe_get(body, "view", "callback_id") == "preblast-id"
    assert safe_get(body, "message", "metadata", "event_payload", "title") == "Test Workout"
    assert safe_get(body, "nonexistent", "key") is None


if __name__ == "__main__":
    # Simple test runner - in practice you'd use pytest
    import traceback
    
    def run_tests():
        test_classes = [TestBuildPreblastForm, TestHandlePreblastPost, TestHandlePreblastEditButton]
        
        for test_class in test_classes:
            print(f"\nRunning tests for {test_class.__name__}:")
            instance = test_class()
            
            for attr_name in dir(instance):
                if attr_name.startswith('test_'):
                    try:
                        if hasattr(instance, 'setup_method'):
                            instance.setup_method()
                        
                        method = getattr(instance, attr_name)
                        method()
                        print(f"  ✓ {attr_name}")
                    except Exception as e:
                        print(f"  ✗ {attr_name}: {e}")
                        traceback.print_exc()
        
        # Run standalone test
        try:
            test_safe_get_in_preblast_context()
            print("\n  ✓ test_safe_get_in_preblast_context")
        except Exception as e:
            print(f"\n  ✗ test_safe_get_in_preblast_context: {e}")
            traceback.print_exc()
    
    run_tests() 