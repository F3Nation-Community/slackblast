from utilities.slack import actions, orm

EVENT_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Event Name",
            action=actions.CALENDAR_ADD_SERIES_NAME,
            element=orm.PlainTextInputElement(placeholder="Enter the series name"),
        ),
        orm.ContextBlock(
            element=orm.ContextElement(initial_value="If left blank, will default to the AO name + event type.")
        ),
        orm.InputBlock(
            label="Description",
            action=actions.CALENDAR_ADD_SERIES_DESCRIPTION,
            element=orm.PlainTextInputElement(
                placeholder="Enter a description",
                multiline=True,
            ),
            optional=True,
        ),
        orm.InputBlock(
            label="Highlight on Special Events Page?",
            action=actions.CALENDAR_ADD_SERIES_HIGHLIGHT,
            element=orm.CheckboxInputElement(
                options=orm.as_selector_options(names=["Yes"], values=["True"]),
            ),
            optional=False,
        ),
        orm.ContextBlock(
            element=orm.ContextElement(initial_value="Primarily used for 2nd F events, convergences, etc.")
        ),
        orm.InputBlock(
            label="AO",
            action=actions.CALENDAR_ADD_SERIES_AO,
            element=orm.StaticSelectElement(placeholder="Select an AO"),
            dispatch_action=True,
        ),
        orm.InputBlock(
            label="Location",
            action=actions.CALENDAR_ADD_SERIES_LOCATION,
            element=orm.StaticSelectElement(placeholder="Select the location"),
        ),
        orm.InputBlock(
            label="Event Type",
            action=actions.CALENDAR_ADD_SERIES_TYPE,
            element=orm.StaticSelectElement(placeholder="Select the event type"),
            optional=False,
        ),
        orm.InputBlock(
            label="Date",
            action=actions.CALENDAR_ADD_SERIES_START_DATE,
            element=orm.DatepickerElement(placeholder="Enter the start date"),
            optional=False,
        ),
        orm.InputBlock(
            label="Start Time",
            action=actions.CALENDAR_ADD_SERIES_START_TIME,
            element=orm.TimepickerElement(placeholder="Enter the start time"),
            optional=False,
        ),
        orm.InputBlock(
            label="End Time",
            action=actions.CALENDAR_ADD_SERIES_END_TIME,
            element=orm.TimepickerElement(placeholder="Enter the end time"),
        ),
        orm.ContextBlock(
            element=orm.ContextElement(
                initial_value="If no end time is provided, the event will be defaulted to be one hour long."
            )
        ),
    ]
)
