from datetime import datetime, timedelta
import time
import threading
from typing import Dict, List, Tuple
import urllib.parse
from slack_sdk.web import WebClient
from util import config
from util.config import Config
from util.utils import get_now_timestamp
from youtrack.youtrack import Youtrack

POLLING_INTERVAL = 120  # in secs
STAT_DATE_FORMAT = "%a %d %b %Y"


class YoutrackChecker(threading.Thread):
    def __init__(self, client: WebClient, configuration: Config) -> None:
        super().__init__()
        self.client: WebClient = client
        self.config: Config = configuration
        self.youtrack: Youtrack = Youtrack(
            base_url=configuration.configuration["youtrack"]["base_url"],
            authorization_header=configuration.configuration["youtrack"]["authorization_header"],
            api_endpoint=configuration.configuration["youtrack"]["api_endpoint"])

    def run(self):
        while True:
            for channel_name in self.config.get_channel_names():
                for module in config.MODULES:
                    if f"{channel_name}.{module}" in self.config.configuration["channels"]:
                        frequency_config = self.config.configuration[
                            "channels"][f"{channel_name}.{module}"]
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

            self.client.chat_postMessage(
                channel=channel_name, text=msg)

    def _digest(self, channel_name: str):
        msg = self.get_digest(channel_name)
        self.client.chat_postMessage(
            channel=channel_name, text=msg)

    def _tracking(self, channel_name: str):
        last_check: str = self.config.configuration["channels"][channel_name+".lastcheck"]
        now: str = get_now_timestamp()
        query: str = f"""{self.config.configuration["channels"][channel_name]} created: {last_check} .. {now}"""
        for issue in self.youtrack.get_issues(query):
            new_issue_msg = self._get_issue_markdown(issue)
            self.client.chat_postMessage(
                channel=channel_name, text=new_issue_msg)
        self.config.configuration["channels"][channel_name +
                                              ".lastcheck"] = now

    def _get_issue_markdown(self, issue: dict, from_visible=True, creation_date_visible=False):
        new_issue_msg: str = ""
        if creation_date_visible:
            new_issue_msg = f"""[{datetime.fromtimestamp(issue["created"]/1000).strftime(STAT_DATE_FORMAT)}] - """

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
        beginning: str = ""
        end: str = ""
        beginning, end = self.get_beginning_end_from_frequency(frequency)

        msg = self.get_stats(channel_name, f"{beginning} .. {end}")
        self.client.chat_postMessage(
            channel=channel_name, text=msg)

    def get_beginning_end_from_frequency(self, frequency) -> Tuple[str, str]:
        beginning: str = ""
        end: str = ""
        match frequency:
            case config.FREQUENCY_POLLING:
                beginning = (
                    datetime.now() - timedelta(seconds=POLLING_INTERVAL)).strftime(STAT_DATE_FORMAT)
                end = datetime.now().strftime(STAT_DATE_FORMAT)
            case config.FREQUENCY_DAILY:
                beginning_dt = (datetime.now() - timedelta(days=1))
                beginning = datetime(
                    beginning_dt.year, beginning_dt.month, beginning_dt.day).strftime(STAT_DATE_FORMAT)
                end = datetime(
                    beginning_dt.year, beginning_dt.month, beginning_dt.day, 23, 59, 59, 999999).strftime(STAT_DATE_FORMAT)
            case config.FREQUENCY_WEEKLY:
                beginning_dt = (datetime.now() - timedelta(days=7))
                beginning = datetime(
                    beginning_dt.year, beginning_dt.month, beginning_dt.day).strftime(STAT_DATE_FORMAT)
                end_dt = (datetime.now() - timedelta(days=1))
                end = datetime(
                    end_dt.year, end_dt.month, end_dt.day, 23, 59, 59, 999999).strftime(STAT_DATE_FORMAT)

        return beginning, end

    def get_digest(self, channel_name: str) -> str:
        msg: str = "No ticket!"
        issues = self.youtrack.get_issues(
            f"""{self.config.configuration["channels"][channel_name]}""")
        if len(issues) > 0:
            msg = "Digest:\n"
            for issue in issues:
                msg += f"\n - {self._get_issue_markdown(issue, creation_date_visible=True, from_visible=False)}"

        return msg

    def get_stats(self, channel_name: str, period: str) -> str:
        all_time_unresolved_query: str = f"""#Unresolved {self.config.configuration["channels"][channel_name]}"""
        all_time_unresolved_issues: List[dict] = self.youtrack.get_issues(
            all_time_unresolved_query, only_issue_ids=True)

        base_query: str = f"""{self.config.configuration["channels"][channel_name]} created: {period}"""
        unresolved_query: str = f"#Unresolved {base_query}"
        unresolved_issues: List[dict] = self.youtrack.get_issues(
            unresolved_query)

        ticket_count_by_tag_msg = self._get_ticket_count_by_tag(
            unresolved_issues)

        resolved_query: str = f"#Resolved {base_query}"
        resolved_issues: List[dict] = self.youtrack.get_issues(resolved_query)

        resolved_other_issues_query: str = f"""#Resolved {self.config.configuration["channels"][channel_name]} resolved date: {period}"""
        resolved_other_issues: List[dict] = self.youtrack.get_issues(
            (resolved_other_issues_query))

        msg: str = (f"Stats for period _{period}_:\n"
                    f""" 🛎️ {self._get_markdown_query_link(base_query, f"{len(unresolved_issues)+len(resolved_issues)} tickets")} have been created.\n"""
                    f""" 🏗️ {self._get_markdown_query_link(unresolved_query, f"{len(unresolved_issues)} tickets")} are still opened.{ticket_count_by_tag_msg}\n"""
                    f""" ✅ {self._get_markdown_query_link(resolved_query, f"{len(resolved_issues)} tickets")} among created have been closed + {self._get_markdown_query_link(resolved_other_issues_query, f"{len(resolved_other_issues)} tickets")} from previous creation period."""
                    f"""\n 🧮 {self._get_markdown_query_link(all_time_unresolved_query, f"{len(all_time_unresolved_issues)}")} all time unresolved tickets."""
                    )
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