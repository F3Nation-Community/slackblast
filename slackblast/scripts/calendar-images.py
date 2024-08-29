import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import random
from datetime import date, timedelta

import boto3
import dataframe_image as dfi
import pandas as pd
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import aliased
from sqlalchemy.sql.functions import coalesce

from utilities.constants import EVENT_TAG_COLORS

# import dataframe_image as dfi
from utilities.database import get_session
from utilities.database.orm import (
    Attendance,
    Event,
    EventTag,
    EventTag_x_Org,
    EventType,
    Org,
    User,
)

tomorrow_day_of_week = (date.today() + timedelta(days=1)).weekday()
current_week_start = date.today() + timedelta(days=-tomorrow_day_of_week + 1)
current_week_end = date.today() + timedelta(days=7 - tomorrow_day_of_week)
next_week_start = current_week_start + timedelta(weeks=1)
next_week_end = current_week_end + timedelta(weeks=1)

session = get_session()


def time_int_to_str(time: int) -> str:
    return f"{time // 100:02d}{time % 100:02d}"


def highlight_cells(s, color_dict):
    highlight_cells_list = []
    for cell in s:
        cell_str = str(cell)
        tags = cell_str.split("\n")
        found = False
        if tags:
            for tag in tags:
                if tag in color_dict.keys():
                    highlight_cells_list.append(f"background-color: {EVENT_TAG_COLORS[color_dict[tag]]}")
                    found = True
                    break
        if not found:
            highlight_cells_list.append("background-color: #000000")
    return pd.Series(highlight_cells_list)


firstq_subquery = (
    select(
        Attendance.event_id,
        User.f3_name.label("q_name"),
        func.row_number().over(partition_by=Attendance.event_id, order_by=Attendance.created).label("rn"),
    )
    .select_from(Attendance)
    .join(User, Attendance.user_id == User.id)
    .filter(Attendance.attendance_type_id == 2)
    .alias()
)

attendance_subquery = (
    select(
        Attendance.event_id,
        func.max(
            case(
                (Attendance.attendance_type_id == 2, Attendance.updated),
            )
        ).label("q_last_updated"),
    )
    .select_from(Attendance)
    .group_by(Attendance.event_id)
    .alias()
)

RegionOrg = aliased(Org)

query = (
    session.query(
        Event.start_date,
        Event.start_time,
        Event.updated.label("event_updated"),
        EventTag.name.label("event_tag"),
        EventTag.color.label("event_tag_color"),
        EventType.name.label("event_type"),
        EventType.acronym.label("event_acronym"),
        Org.name.label("ao_name"),
        Org.description.label("ao_description"),
        Org.parent_id.label("ao_parent_id"),
        firstq_subquery.c.q_name,
        attendance_subquery.c.q_last_updated,
        RegionOrg.name.label("region_name"),
        RegionOrg.id.label("region_id"),
    )
    .select_from(Event)
    .outerjoin(EventTag, Event.event_tag_id == EventTag.id)
    .join(EventType, Event.event_type_id == EventType.id)
    .join(Org, Event.org_id == Org.id)
    .join(RegionOrg, RegionOrg.id == Org.parent_id)
    .outerjoin(
        firstq_subquery,
        and_(Event.id == firstq_subquery.c.event_id, firstq_subquery.c.rn == 1),
    )
    .outerjoin(attendance_subquery, Event.id == attendance_subquery.c.event_id)
    .filter(
        (Event.start_date >= current_week_start),
        (Event.start_date < next_week_end),
        (Event.is_active),
        (~Event.is_series),
    )
)

results = query.all()
df_all = pd.DataFrame(results)

color_query = (
    session.query(
        EventTag_x_Org.org_id.label("region_id"),
        EventTag.name,
        coalesce(EventTag_x_Org.color_override, EventTag.color).label("color"),
    )
    .select_from(EventTag_x_Org)
    .join(EventTag, EventTag_x_Org.event_tag_id == EventTag.id)
)

color_results = color_query.all()

region_org_records = session.query(Org).filter(Org.org_type_id == 2).all()

for region_id in df_all["region_id"].unique():
    df_full = df_all[df_all["region_id"] == region_id].copy()
    region_name = df_full["region_name"].iloc[0]
    print(f"Running for {region_name}")

    color_dict = {c.name: c.color for c in color_results if c.region_id == region_id}
    if "Open" in color_dict:
        color_dict["OPEN!"] = color_dict.pop("Open")

    for week in ["current", "next"]:
        if week == "current":
            df = df_full[
                (df_full["start_date"] >= current_week_start) & (df_full["start_date"] < current_week_end)
            ].copy()
        else:
            df = df_full[(df_full["start_date"] >= next_week_start) & (df_full["start_date"] < next_week_end)].copy()

        # convert start_date from date to string
        df.loc[:, "event_date"] = pd.to_datetime(df["start_date"])
        df.loc[:, "event_date_fmt"] = df["event_date"].dt.strftime("%m/%d")
        df.loc[:, "event_time"] = df["start_time"].apply(time_int_to_str)
        df.loc[df["q_name"].isna(), "q_name"] = "OPEN!"
        df.loc[:, "q_name"] = df["q_name"].str.replace(r"\(.*\)", "")

        df.loc[:, "label"] = df["q_name"] + "\n" + df["event_acronym"] + " " + df["event_time"]
        df.loc[(df["event_tag"].notnull()), ("label")] = df["q_name"] + "\n" + df["event_tag"] + "\n" + df["event_time"]
        df.loc[:, "AO\nLocation"] = df["ao_name"]  # + "\n" + df["ao_description"]
        df.loc[df["ao_description"].notnull(), "AO\nLocation"] = df["ao_name"] + "\n" + df["ao_description"]
        df.loc[:, "AO\nLocation2"] = df["AO\nLocation"].str.replace("The ", "")
        df.loc[:, "event_day_of_week"] = df["event_date"].dt.day_name()

        # Combine cells for days / AOs with more than one event
        df.sort_values(["ao_name", "event_date", "event_time"], ignore_index=True, inplace=True)
        prior_date = ""
        prior_label = ""
        prior_ao = ""
        include_list = []
        for i in range(len(df)):
            row2 = df.loc[i]
            if (row2["event_date_fmt"] == prior_date) & (row2["ao_name"] == prior_ao):
                df.loc[i, "label"] = prior_label + "\n" + df.loc[i, "label"]
                prior_label = df.loc[i, "label"]
                include_list.append(False)
            else:
                if prior_label != "":
                    include_list.append(True)
                prior_date = row2["event_date_fmt"]
                prior_ao = row2["ao_name"]
                prior_label = row2["label"]

        include_list.append(True)

        # filter out duplicate dates
        print(include_list)
        print(df.head())
        df = df[include_list]

        # Reshape to wide format by date
        df2 = df.pivot(
            index="AO\nLocation",
            columns=["event_day_of_week", "event_date_fmt"],
            values="label",
        ).fillna("")

        # Sort and enforce word wrap on labels
        df2.sort_index(axis=1, level=["event_date_fmt"], inplace=True)
        df2.columns = df2.columns.map("\n".join).str.strip("\n")
        df2.reset_index(inplace=True)

        # Take out "The " for sorting
        df2["AO\nLocation2"] = df2["AO\nLocation"].str.replace("The ", "")
        df2.sort_values(by=["AO\nLocation2"], axis=0, inplace=True)
        df2.drop(["AO\nLocation2"], axis=1, inplace=True)
        df2.reset_index(inplace=True, drop=True)

        # Set CSS properties for th elements in dataframe
        th_props = [
            ("font-size", "15px"),
            ("text-align", "center"),
            ("font-weight", "bold"),
            ("color", "#F0FFFF"),
            ("background-color", "#000000"),
            ("white-space", "pre-wrap"),
            ("border", "1px solid #F0FFFF"),
        ]

        # Set CSS properties for td elements in dataframe
        td_props = [
            ("font-size", "15px"),
            ("text-align", "center"),
            ("white-space", "pre-wrap"),
            # ('background-color', '#000000'),
            ("color", "#F0FFFF"),
            ("border", "1px solid #F0FFFF"),
        ]

        # Set table styles
        styles = [
            {"selector": "th", "props": th_props},
            {"selector": "td", "props": td_props},
        ]

        # set style and export png
        # df_styled = df2.style.set_table_styles(styles).apply(highlight_cells).hide_index()
        # apply styles, hide the index
        df_styled = df2.style.set_table_styles(styles).apply(highlight_cells, color_dict=color_dict).hide(axis="index")

        # create calendar image
        random_chars = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=10))
        filename = f"{region_id}-{week}-{random_chars}.png"
        dfi.export(df_styled, filename, table_conversion="playwright")

        # upload to s3 and remove local file
        region_org_record = [r for r in region_org_records if r.id == region_id][0]
        slack_app_settings = region_org_record.slack_app_settings or {}
        existing_file = slack_app_settings.get(f"calendar_image_{week}")

        s3_client = boto3.client("s3")
        with open(filename, "rb") as f:
            s3_client.upload_fileobj(f, "slackblast-images", filename, ExtraArgs={"ContentType": "image/png"})

        if existing_file:
            s3_client.delete_object(Bucket="slackblast-images", Key=existing_file)
        os.remove(filename)

        # update org record with new filename
        slack_app_settings[f"calendar_image_{week}"] = filename
        session.query(Org).filter(Org.id == region_id).update({"slack_app_settings": slack_app_settings})
        session.commit()

session.close()
