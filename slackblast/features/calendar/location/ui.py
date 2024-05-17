from utilities.slack import actions, orm

ADD_LOCATION_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Location Name",
            action=actions.CALENDAR_ADD_LOCATION_NAME,
            element=orm.PlainTextInputElement(placeholder="Enter the location name"),
            optional=False,
        ),
        orm.InputBlock(
            label="Description / Address",
            action=actions.CALENDAR_ADD_LOCATION_DESCRIPTION,
            element=orm.PlainTextInputElement(
                placeholder="Enter a description and / or address",
                multiline=True,
            ),
        ),
        orm.InputBlock(
            label="Google Lat/Long",
            action=actions.CALENDAR_ADD_LOCATION_GOOGLE,
            element=orm.PlainTextInputElement(placeholder="ie '34.0522, -118.2437'"),
        ),
        orm.ContextBlock(
            element=orm.ContextElement(
                initial_value="To get Google's Lat/Long, long press to create a pin, then bring up the context menu and select the coordinates to copy them."  # noqa
            ),
        ),
    ]
)
