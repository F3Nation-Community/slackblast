from utilities.slack import actions, orm

ADD_AO_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="AO Title",
            element=orm.PlainTextInputElement(
                action_id=actions.CALENDAR_ADD_AO_NAME,
                placeholder="Enter the AO name",
            ),
            optional=False,
        ),
        orm.InputBlock(
            label="Description",
            element=orm.PlainTextInputElement(
                action_id=actions.CALENDAR_ADD_AO_DESCRIPTION,
                placeholder="Enter a description",
            ),
        ),
        orm.InputBlock(
            label="Channel associated with this AO:",
            element=orm.ChannelsSelectElement(
                action_id=actions.CALENDAR_ADD_AO_CHANNEL,
                placeholder="Select a channel",
            ),
        ),
        orm.InputBlock(
            label="Default Location",
            element=orm.StaticSelectElement(
                action_id=actions.CALENDAR_ADD_AO_LOCATION,
                placeholder="Select a location",
            ),
        ),
    ]
)
