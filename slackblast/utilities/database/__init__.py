from dataclasses import dataclass
from typing import TypeVar, List

import os, sys
from sqlalchemy import create_engine, pool, and_
from sqlalchemy.orm import sessionmaker
from contextlib import ContextDecorator

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from utilities.database.orm import BaseClass
from utilities import constants


@dataclass
class DatabaseField:
    name: str
    value: object = None


GLOBAL_ENGINE = None
GLOBAL_SESSION = None


def get_session(echo=False):
    if GLOBAL_SESSION:
        return GLOBAL_SESSION

    global GLOBAL_ENGINE
    if not GLOBAL_ENGINE:
        host = os.environ[constants.DATABASE_HOST]
        user = os.environ[constants.ADMIN_DATABASE_USER]
        passwd = os.environ[constants.ADMIN_DATABASE_PASSWORD]
        database = os.environ[constants.ADMIN_DATABASE_SCHEMA]

        db_url = f"mysql+pymysql://{user}:{passwd}@{host}:3306/{database}?charset=utf8mb4"
        GLOBAL_ENGINE = create_engine(
            db_url, echo=echo, poolclass=pool.NullPool, convert_unicode=True
        )
    return sessionmaker()(bind=GLOBAL_ENGINE)


def close_session(session):
    global GLOBAL_SESSION, GLOBAL_ENGINE
    if GLOBAL_SESSION == session:
        if GLOBAL_ENGINE:
            GLOBAL_ENGINE.close()
            GLOBAL_SESSION = None


T = TypeVar("T")


class DbManager:
    def get_record(cls: T, id) -> T:
        session = get_session()
        try:
            x = session.query(cls).filter(cls.get_id() == id).first()
            if x:
                session.expunge(x)
            return x
        finally:
            session.rollback()
            close_session(session)

    def find_records(cls: T, filters) -> List[T]:
        session = get_session()
        try:
            records = session.query(cls).filter(and_(*filters)).all()
            for r in records:
                session.expunge(r)
            return records
        finally:
            session.rollback()
            close_session(session)

    def update_record(cls: T, id, fields):
        session = get_session()
        try:
            session.query(cls).filter(cls.get_id() == id).update(
                fields, synchronize_session="fetch"
            )
            session.flush()
        finally:
            session.commit()
            close_session(session)

    def update_records(cls: T, filters, fields):
        session = get_session()
        try:
            session.query(cls).filter(and_(*filters)).update(fields, synchronize_session="fetch")
            session.flush()
        finally:
            session.commit()
            close_session(session)

    def create_record(record: BaseClass) -> BaseClass:
        session = get_session()
        try:
            session.add(record)
            session.flush()
            session.expunge(record)
        finally:
            session.commit()
            close_session(session)
            return record

    def create_records(records: List[BaseClass]):
        session = get_session()
        try:
            session.add_all(records)
            session.flush()
        finally:
            session.commit()
            close_session(session)

    def delete_record(cls: T, id):
        session = get_session()
        try:
            session.query(cls).filter(cls.get_id() == id).delete()
            session.flush()
        finally:
            session.commit()
            close_session(session)

    def delete_records(cls: T, filters):
        session = get_session()
        try:
            session.query(cls).filter(and_(*filters)).delete()
            session.flush()
        finally:
            session.commit()
            close_session(session)
