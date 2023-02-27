from datetime import datetime
from enum import Enum
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import *
from sqlalchemy.types import JSON
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import relationship

BaseClass = declarative_base(mapper=sqlalchemy.orm.mapper)


class GetDBClass:
    def get_id(self):
        return self.id

    def get(self, attr):
        if attr in [c.key for c in self.__table__.columns]:
            return getattr(self, attr)
        return None

    def to_json(self):
        return {c.key: self.get(c.key) for c in self.__table__.columns}

    def __repr__(self):
        return str(self.to_json())


class Region(BaseClass, GetDBClass):
    __tablename__ = "regions"
    id = Column("id", Integer, primary_key=True)
    team_id = Column("team_id", String(100))
    workspace_name = Column("workspace_name", String(100))
    bot_token = Column("bot_token", String(100))
    email_enabled = Column("email_enabled", Integer)
    email_server = Column("email_server", String(100))
    email_server_port = Column("email_server_port", Integer)
    email_user = Column("email_user", String(100))
    email_password = Column("email_password", LONGTEXT)
    email_to = Column("email_to", String(100))
    email_option_show = Column("email_option_show", Integer)
    postie_format = Column("postie_format", Integer)
    created = Column("created", DateTime, default=datetime.utcnow)
    updated = Column("updated", DateTime, default=datetime.utcnow)

    def get_id(self):
        return self.team_id

    def get_id():
        return Region.team_id
