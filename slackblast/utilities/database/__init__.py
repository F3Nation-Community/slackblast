import os
from dataclasses import dataclass
from typing import List, Tuple, TypeVar

from sqlalchemy import and_, create_engine, pool
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from utilities import constants
from utilities.database.orm import BaseClass


@dataclass
class DatabaseField:
    name: str
    value: object = None


GLOBAL_ENGINE = None
GLOBAL_SESSION = None
GLOBAL_SCHEMA = None


def get_engine(echo=False, schema=None) -> Engine:
    host = os.environ[constants.DATABASE_HOST]
    user = os.environ[constants.ADMIN_DATABASE_USER]
    passwd = os.environ[constants.ADMIN_DATABASE_PASSWORD]
    database = schema or os.environ[constants.ADMIN_DATABASE_SCHEMA]
    db_url = f"mysql+pymysql://{user}:{passwd}@{host}:3306/{database}?charset=utf8mb4"
    return create_engine(db_url, echo=echo, poolclass=pool.NullPool)


def get_session(echo=True, schema=None):
    if GLOBAL_SESSION:
        return GLOBAL_SESSION

    global GLOBAL_ENGINE, GLOBAL_SCHEMA
    if schema != GLOBAL_SCHEMA or not GLOBAL_ENGINE:
        GLOBAL_ENGINE = get_engine(echo=echo, schema=schema)
        GLOBAL_SCHEMA = schema or os.environ[constants.ADMIN_DATABASE_SCHEMA]
    return sessionmaker()(bind=GLOBAL_ENGINE)


def close_session(session):
    global GLOBAL_SESSION, GLOBAL_ENGINE
    if GLOBAL_SESSION == session:
        if GLOBAL_ENGINE:
            GLOBAL_ENGINE.close()
            GLOBAL_SESSION = None


T = TypeVar("T")


class DbManager:
    def get_record(cls: T, id, schema=None) -> T:
        session = get_session(schema=schema)
        try:
            x = session.query(cls).filter(cls.get_id() == id).first()
            if x:
                session.expunge(x)
            return x
        finally:
            session.rollback()
            close_session(session)

    def find_records(cls: T, filters, schema=None) -> List[T]:
        session = get_session(schema=schema)
        try:
            records = session.query(cls).filter(and_(*filters)).all()
            for r in records:
                session.expunge(r)
            return records
        finally:
            session.rollback()
            close_session(session)

    def find_join_records2(left_cls: T, right_cls: T, filters, schema=None) -> List[Tuple[T]]:
        session = get_session(schema=schema)
        try:
            records = session.query(left_cls, right_cls).join(right_cls).filter(and_(*filters)).all()
            session.expunge_all()
            return records
        finally:
            session.rollback()
            close_session(session)

    def find_join_records3(
        left_cls: T, right_cls1: T, right_cls2: T, filters, schema=None, left_join=False
    ) -> List[Tuple[T]]:
        session = get_session(schema=schema)
        try:
            records = (
                session.query(left_cls, right_cls1, right_cls2)
                .select_from(left_cls)
                .join(right_cls1, isouter=left_join)
                .join(right_cls2, isouter=left_join)
                .filter(and_(*filters))
                .all()
            )
            session.expunge_all()
            return records
        finally:
            session.rollback()
            close_session(session)

    def update_record(cls: T, id, fields, schema=None):
        session = get_session(schema=schema)
        try:
            session.query(cls).filter(cls.get_id() == id).update(fields, synchronize_session="fetch")
            session.flush()
        finally:
            session.commit()
            close_session(session)

    def update_records(cls: T, filters, fields, schema=None):
        session = get_session(schema=schema)
        try:
            session.query(cls).filter(and_(*filters)).update(fields, synchronize_session="fetch")
            session.flush()
        finally:
            session.commit()
            close_session(session)

    def create_record(record: BaseClass, schema=None) -> BaseClass:
        session = get_session(schema=schema)
        try:
            session.add(record)
            session.flush()
            session.expunge(record)
        finally:
            session.commit()
            close_session(session)
            return record  # noqa

    def create_records(records: List[BaseClass], schema=None):
        session = get_session(schema=schema)
        try:
            session.add_all(records)
            session.flush()
            session.expunge_all()
        finally:
            session.commit()
            close_session(session)
            return records  # noqa

    def delete_record(cls: T, id, schema=None):
        session = get_session(schema=schema)
        try:
            session.query(cls).filter(cls.get_id() == id).delete()
            session.flush()
        finally:
            session.commit()
            close_session(session)

    def delete_records(cls: T, filters, schema=None):
        session = get_session(schema=schema)
        try:
            session.query(cls).filter(and_(*filters)).delete()
            session.flush()
        finally:
            session.commit()
            close_session(session)

    def execute_sql_query(sql_query, schema=None):
        session = get_session(schema=schema)
        try:
            records = session.execute(sql_query)
            return records
        finally:
            close_session(session)
