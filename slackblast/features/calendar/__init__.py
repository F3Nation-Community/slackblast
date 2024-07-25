from utilities.slack import actions, orm

PREBLAST_MESSAGE_ACTION_ELEMENTS = [
    orm.ButtonElement(label=":hc: HC/Un-HC", action=actions.EVENT_PREBLAST_HC_UN_HC),
    orm.ButtonElement(label=":pencil: Edit Preblast", action=actions.EVENT_PREBLAST_EDIT, value="Edit Preblast"),
]
