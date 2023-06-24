-- Create or replace databases
CREATE DATABASE IF NOT EXISTS paxminer;
CREATE DATABASE IF NOT EXISTS slackblast;
CREATE DATABASE IF NOT EXISTS f3devregion;
-- Create or replace paxminer.regions table
DROP TABLE IF EXISTS paxminer.regions;
CREATE TABLE paxminer.`regions` (
  `region` varchar(45) NOT NULL,
  `slack_token` varchar(90) NOT NULL,
  `schema_name` varchar(45) DEFAULT NULL,
  `active` tinyint DEFAULT '1',
  `firstf_channel` varchar(45) DEFAULT NULL,
  `contact` varchar(45) DEFAULT NULL,
  `send_pax_charts` tinyint DEFAULT '0',
  `send_ao_leaderboard` tinyint DEFAULT '0',
  `send_q_charts` tinyint DEFAULT '0',
  `send_region_leaderboard` tinyint DEFAULT '0',
  `send_region_uniquepax_chart` tinyint DEFAULT '0',
  `send_region_stats` varchar(45) DEFAULT '0',
  `send_mid_month_charts` varchar(45) DEFAULT '0',
  `comments` text,
  PRIMARY KEY (`region`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb3;
-- Insert sample rows into paxminer.regions table
INSERT INTO paxminer.regions (region, slack_token, schema_name)
VALUES ('f3devregion', 'xoxb-1234', 'f3devregion'),
  ('f3otherregion', 'xoxb-1234', 'f3otherregion'),
  (
    'f3anotherregion',
    'xoxb-1234',
    'f3anotherregion'
  );
-- Create or replace slackblast.regions table
DROP TABLE IF EXISTS slackblast.regions;
CREATE TABLE slackblast.`regions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `team_id` varchar(100) NOT NULL,
  `workspace_name` varchar(100) DEFAULT NULL,
  `bot_token` varchar(100) DEFAULT NULL,
  `paxminer_schema` varchar(45) CHARACTER SET utf8 COLLATE utf8_general_ci DEFAULT NULL,
  `email_enabled` tinyint(1) DEFAULT 0,
  `email_server` varchar(100) DEFAULT NULL,
  `email_server_port` int DEFAULT NULL,
  `email_user` varchar(100) DEFAULT NULL,
  `email_password` longtext CHARACTER SET utf8 COLLATE utf8_general_ci,
  `email_to` varchar(100) DEFAULT NULL,
  `email_option_show` tinyint(1) DEFAULT 0,
  `postie_format` tinyint(1) DEFAULT 1,
  `created` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE = InnoDB AUTO_INCREMENT = 34 DEFAULT CHARSET = utf8mb3;
-- Create or replace f3devregion tables
DROP TABLE IF EXISTS f3devregion.beatdowns;
CREATE TABLE f3devregion.`beatdowns` (
  `timestamp` varchar(45) DEFAULT NULL,
  `ts_edited` varchar(45) DEFAULT NULL,
  `ao_id` varchar(45) NOT NULL,
  `bd_date` date NOT NULL,
  `q_user_id` varchar(45) NOT NULL,
  `coq_user_id` varchar(45) DEFAULT NULL,
  `pax_count` int DEFAULT NULL,
  `backblast` longtext,
  `fngs` varchar(45) DEFAULT NULL,
  `fng_count` int DEFAULT NULL,
  PRIMARY KEY (`ao_id`, `bd_date`, `q_user_id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb3;
DROP TABLE IF EXISTS f3devregion.bd_attendance;
CREATE TABLE f3devregion.`bd_attendance` (
  `timestamp` varchar(45) DEFAULT NULL,
  `ts_edited` varchar(45) DEFAULT NULL,
  `user_id` varchar(45) NOT NULL,
  `ao_id` varchar(45) NOT NULL,
  `date` varchar(45) NOT NULL,
  `q_user_id` varchar(45) NOT NULL,
  PRIMARY KEY (`q_user_id`, `user_id`, `ao_id`, `date`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb3;
DROP TABLE IF EXISTS f3devregion.aos;
CREATE TABLE f3devregion.`aos` (
  `channel_id` varchar(45) NOT NULL,
  `ao` varchar(45) NOT NULL,
  `channel_created` int NOT NULL,
  `archived` tinyint NOT NULL,
  `backblast` tinyint DEFAULT NULL,
  PRIMARY KEY (`channel_id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb3;
INSERT INTO f3devregion.aos (
    channel_id,
    ao,
    channel_created,
    archived,
    backblast
  )
VALUES ('C04KKHZAUSZ', 'ao-brissy-ridge', 1, 0, 1),
  ('C04KDTR844F', 'ao-bye-pandas', 1, 0, 1);