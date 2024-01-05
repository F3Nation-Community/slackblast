import pymysql
from pymysql.constants import CLIENT
import os, sys
import json

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from utilities import constants

def create_database():
    env_dict = json.load(open("env.json", "r"))
    conn_info = {
        "host": env_dict['Parameters']['DATABASE_HOST'],
        "port": 3306,
        "user": env_dict['Parameters']['ADMIN_DATABASE_USER'],
        "password": env_dict['Parameters']['ADMIN_DATABASE_PASSWORD'],
        "database": env_dict['Parameters']['ADMIN_DATABASE_SCHEMA'],
        "client_flag": CLIENT.MULTI_STATEMENTS,
    }
    
    print(conn_info)


    with pymysql.connect(**conn_info) as cnxn:
        crsr = cnxn.cursor()

        with open("slackblast/utilities/database/create_clear_local_db.sql", "r") as f:
            sql = f.read()
            
        print(sql)

        crsr.execute(sql)
        cnxn.commit()
    
    print("Database created successfully")

if __name__ == "__main__":
    create_database()