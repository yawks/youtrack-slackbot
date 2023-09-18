from datetime import datetime
import configparser
from typing import List

CONFIG_FILE_NAME = "config.ini"

MODULE_TRACKING = "tracking"
MODULE_STATS = "stats"
MODULE_DIGEST = "digest"
MODULES = [MODULE_TRACKING, MODULE_STATS, MODULE_DIGEST]

TRACKING_LASTCHECK = "lastcheck"

FREQUENCY_POLLING = "polling"
FREQUENCY_DAILY = "daily"
FREQUENCY_WEEKLY = "weekly"
FREQUENCIES = [FREQUENCY_POLLING, FREQUENCY_DAILY, FREQUENCY_WEEKLY]


class Config:
    def __init__(self) -> None:
        self.configuration = configparser.ConfigParser()
        self.configuration.read(CONFIG_FILE_NAME)

        if "channels" not in self.configuration:
            self.configuration.add_section("channels")

    def get_last_check_for_channel(self, channel_name: str) -> datetime:
        return datetime.strptime(
            self.configuration['channels'][channel_name+"."+TRACKING_LASTCHECK], "%Y-%m-%dT%H:%M")

    def get_channel_names(self) -> List[str]:
        channel_names: List[str] = []
        for entry in self.configuration["channels"]:
            if not entry.endswith("." + TRACKING_LASTCHECK) and entry not in channel_names:
                appendable = True
                for module in MODULES:
                    if entry.endswith("." + module):
                        appendable = False
                        break
                if appendable:
                    channel_names.append(entry)

        return channel_names

    def save_config(self):
        with open(CONFIG_FILE_NAME, "w", encoding="utf-8") as configfile:
            self.configuration.write(configfile)
