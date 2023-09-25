from datetime import datetime, timedelta
import time
import threading
from typing import Dict, List, Tuple
import urllib.parse
from util import config
from util.config import Config
from util.utils import STAT_YOUTRACK_DATE_FORMAT, get_today_timestamp
from youtrack.youtrack import Youtrack

POLLING_INTERVAL = 60  # in secs
STAT_DATE_FORMAT = "%a %d %b %Y"


class YoutrackChecker(threading.Thread):
    def __init__(self, configuration: Config, send_message_to_channel_cb) -> None:
        super().__init__()
        self.send_message_to_channel_cb = send_message_to_channel_cb
        self.config: Config = configuration
        self.youtrack: Youtrack = Youtrack(
            base_url=configuration.configuration["youtrack"]["base_url"],
            authorization_header=configuration.configuration["youtrack"]["authorization_header"],
            api_endpoint=configuration.configuration["youtrack"]["api_endpoint"],
            max_issues=int(
                configuration.configuration["youtrack"]["max_issues"]),
            all_issue_fields=configuration.configuration["youtrack"]["all_issue_fields"],
            issue_id_field=configuration.configuration["youtrack"]["issue_id_field"]
        )

    def run(self):
        while True:
            for entry, channel_name in self.config.get_channel_entries():
                for module in config.MODULES:
                    if self.config.get_module_value_for_channel(channel_name, module) != "":
                        frequency_config = self.config.get_module_value_for_channel(channel_name, module)
                        frequency = frequency_config.split(" ")[0]
                        match frequency:
                            case config.FREQUENCY_POLLING:
                                self._polling(module, frequency, channel_name)
                            case config.FREQUENCY_DAILY:
                                self._daily(module, frequency,
                                            channel_name, " ".join(frequency_config.split(" ")[1:]))
                            case config.FREQUENCY_WEEKLY:
                                self._weekly(module, frequency,
                                             channel_name, " ".join(frequency_config.split(" ")[1:]))
                            case _:
                                print(
                                    f"Unkown frequency {frequency} for module {module} in {channel_name}")
            self.config.save_config()
            time.sleep(POLLING_INTERVAL)

    def _execute_module(self, module: str, frequency: str, channel_name: str):
        match module:
            case config.MODULE_TRACKING:
                self._tracking(channel_name)
            case config.MODULE_DIGEST:
                self._digest(channel_name)
            case config.MODULE_STATS:
                self._stats(channel_name, frequency)

    def _polling(self, module: str, frequency: str, channel_name: str):
        self._execute_module(module, frequency, channel_name)

    def _daily(self, module: str, frequency: str, channel_name: str, timestamp: str):
        if datetime.now().strftime("%H:%M") in [timestamp, f"0{timestamp}"]:
            self._execute_module(module, frequency, channel_name)

    def _weekly(self, module: str, frequency: str, channel_name: str, day_time: str):
        try:
            day = day_time.split(" ")[0]
            day_number = datetime.strptime(day, "%A")
            hour_minutes = day_time.split(" ")[1].split(":")
            now = datetime.now()
            if now.weekday() == day_number.weekday() and now.hour == int(hour_minutes[0]) and now.minute == int(hour_minutes[1]):
                self._execute_module(module, frequency, channel_name)

        except Exception as exception:
            msg = (f"Unable to parse weekly configuration: _{day_time}_."
                   "Expected format: weekly <day> <hour:minute> (in 24h format)"
                   "eg: weekly friday 14:30"
                   f"Exception: {str(exception)}")

            self.send_message_to_channel_cb(
                channel_name=channel_name, message=msg)

    def _digest(self, channel_name: str):
        msg = self.get_digest(channel_name)
        self.send_message_to_channel_cb(
            channel_name=channel_name, message=msg)

    def _tracking(self, channel_name: str):
        last_check: str = self.config.get_module_value_for_channel(channel_name, config.POLLING_LASTCHECK)
        now: str = get_today_timestamp()
        query: str = f"""{self.config.get_module_value_for_channel(channel_name, config.QUERY_ENTRY)} created: {last_check} .. {now}"""
        for issue in self.youtrack.get_issues(query):
            new_issue_msg = self._get_issue_markdown(issue)
            self.send_message_to_channel_cb(
                channel_name=channel_name, message=new_issue_msg)
        self.config.set_module_value_for_channel(channel_name, config.POLLING_LASTCHECK, now)

    def _get_issue_markdown(self, issue: dict, from_visible=True, creation_date_visible=False):
        new_issue_msg: str = ""
        if creation_date_visible:
            new_issue_msg = f"""`{datetime.fromtimestamp(issue["created"]/1000).strftime(STAT_DATE_FORMAT)}` - """

        new_issue_msg += f"""<{self.youtrack.base_url}/issue/{issue["idReadable"]}|{issue["idReadable"]}> - {issue["summary"]}"""
        for tag in issue.get("tags", []):
            new_issue_msg += f""" `{tag.get("name", "")}`"""
        if from_visible:
            new_issue_msg += f"""\nFrom : {issue["reporter"]["email"]}"""
        new_issue_msg = new_issue_msg.replace("**", "³³").replace("*", "_").replace(
            "³³", "*").replace("##", "*").replace("\[", "[").replace("\]", "]")

        return new_issue_msg

    def _get_markdown_query_link(self, query: str, url_label: str) -> str:
        return f"<{self.youtrack.base_url}/issues?u=1&q={urllib.parse.quote(query)}|{url_label}>"

    def _stats(self, channel_name: str, frequency: str):
        period = self.get_beginning_end_from_frequency(frequency)

        msg = self.get_stats(channel_name, period)
        self.send_message_to_channel_cb(
            channel_name=channel_name, message=msg)

    def get_beginning_end_from_frequency(self, frequency) -> str:
        period: str = ""
        match frequency:
            case config.FREQUENCY_POLLING:
                beginning = (
                    datetime.now() - timedelta(seconds=POLLING_INTERVAL)).strftime(STAT_YOUTRACK_DATE_FORMAT)
                end = datetime.now().strftime(STAT_YOUTRACK_DATE_FORMAT)
                period = f"{beginning} {end}"
            case config.FREQUENCY_DAILY:
                period = "{Yesterday}"
            case config.FREQUENCY_WEEKLY:
                period = "{last week}"

        return period

    def get_digest(self, channel_name: str) -> str:
        msg: str = "No ticket!"
        try:
            issues = self.youtrack.get_issues(
                f"""#Unresolved {self.config.get_module_value_for_channel(channel_name, config.QUERY_ENTRY)}""")
            if len(issues) > 0:
                msg = "Digest:\n"
                for issue in issues:
                    msg += f"\n - {self._get_issue_markdown(issue, creation_date_visible=True, from_visible=False)}"
        except Exception as exception:
            msg = str(exception)

        return msg

    def get_stats(self, channel_name: str, period: str) -> str:
        try:
            all_time_unresolved_query: str = f"""#Unresolved {self.config.get_module_value_for_channel(channel_name, config.QUERY_ENTRY)}"""
            all_time_unresolved_issues: List[dict] = self.youtrack.get_issues(
                all_time_unresolved_query, only_issue_ids=True)

            base_query: str = f"""{self.config.get_module_value_for_channel(channel_name, config.QUERY_ENTRY)} created: {period}"""
            unresolved_query: str = f"#Unresolved {base_query}"
            unresolved_issues: List[dict] = self.youtrack.get_issues(
                unresolved_query)

            ticket_count_by_tag_msg = self._get_ticket_count_by_tag(
                unresolved_issues)

            resolved_query: str = f"#Resolved {base_query}"
            resolved_issues: List[dict] = self.youtrack.get_issues(resolved_query)

            resolved_other_issues_query: str = f"""#Resolved {self.config.get_module_value_for_channel(channel_name, config.QUERY_ENTRY)} resolved date: {period}"""
            resolved_other_issues: List[dict] = self.youtrack.get_issues(
                (resolved_other_issues_query))

            msg: str = (f"Stats for period _{period}_:\n"
                        f""" 🛎️ {self._get_markdown_query_link(base_query, f"{len(unresolved_issues)+len(resolved_issues)} tickets")} have been created.\n"""
                        f""" 🏗️ {self._get_markdown_query_link(unresolved_query, f"{len(unresolved_issues)} tickets")} are still opened.{ticket_count_by_tag_msg}\n"""
                        f""" ✅ {self._get_markdown_query_link(resolved_query, f"{len(resolved_issues)} tickets")} among created have been closed + {self._get_markdown_query_link(resolved_other_issues_query, f"{len(resolved_other_issues)} tickets")} from previous creation period."""
                        f"""\n 🧮 {self._get_markdown_query_link(all_time_unresolved_query, f"{len(all_time_unresolved_issues)}")} all time unresolved tickets."""
                        )
        except Exception as exception:
            msg = str(exception)
        
        return msg

    def _get_ticket_count_by_tag(self, issues: List[dict]) -> str:
        ticket_count_by_tag_msg: str = ""
        ticket_count_by_tag: Dict[str, int] = {}
        for issue in issues:
            for tag in issue["tags"]:
                if tag["name"] not in ticket_count_by_tag:
                    ticket_count_by_tag[tag["name"]] = 0
                ticket_count_by_tag[tag["name"]] += 1
        for tag, count in ticket_count_by_tag.items():
            ticket_count_by_tag_msg += f"""\n  - {count} tickets `{tag}` """
        return ticket_count_by_tag_msg
