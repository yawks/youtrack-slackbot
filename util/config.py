from datetime import datetime
import configparser
from typing import List, Tuple

from util.utils import STAT_YOUTRACK_DATE_FORMAT

CONFIG_FILE_NAME = "config/config.ini"

CHANNEL_NAME_ENTRY = "name"
QUERY_ENTRY = "query"

MODULE_TRACKING = "tracking"
MODULE_STATS = "stats"
MODULE_DIGEST = "digest"
MODULES = [MODULE_TRACKING, MODULE_STATS, MODULE_DIGEST]

POLLING_LASTCHECK = "lastcheck"

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
            self.configuration['channels'][channel_name+"."+POLLING_LASTCHECK], STAT_YOUTRACK_DATE_FORMAT)

    def get_channel_entries(self) -> List[Tuple[str, str]]:
        channel_names: List[Tuple[str,str]] = []
        for entry in self.configuration["channels"]:
            if entry.endswith("." + CHANNEL_NAME_ENTRY):
                channel_names.append((entry[:-len(CHANNEL_NAME_ENTRY)-1], self.configuration["channels"][entry]))

        return channel_names

    def save_config(self):
        with open(CONFIG_FILE_NAME, "w", encoding="utf-8") as configfile:
            self.configuration.write(configfile)
    
    def has_channel(self, channel_name:str) -> bool:
        return channel_name.lower() + "." + CHANNEL_NAME_ENTRY in self.configuration["channels"]
    
    def get_module_value_for_channel(self, channel_name:str, module:str) -> str:
        value: str = ""
        entry: str = channel_name.lower()
        if self.has_channel(channel_name) and module in entry + "." + module in self.configuration["channels"]:
            value = self.configuration["channels"][entry + "." + module]

        return value
    
    def set_module_value_for_channel(self, channel_name:str, module:str, value:str):
        entry: str = channel_name.lower()
        self.configuration["channels"][entry + "." + module] = value

    def delete_channel(self, channel_name: str) -> bool:
        deleted = False
        entry: str = channel_name.lower() + "." + CHANNEL_NAME_ENTRY
        if entry in self.configuration["channels"]:
            deleted = True
            def del_entry(suffix:str):
                full_entry = channel_name.lower() + "." + suffix
                if full_entry in self.configuration["channels"]:
                    del self.configuration["channels"][full_entry]
            
            for module in MODULES:
                del_entry(module)
            del_entry(POLLING_LASTCHECK)
            del_entry(CHANNEL_NAME_ENTRY)
            del_entry(QUERY_ENTRY)
            
        
        return deleted

    def delete_module_for_channel(self, channel_name: str, module: str):
        entry: str = channel_name.lower() + "." + module
        if entry in self.configuration["channels"]:
            del self.configuration["channels"][entry]
