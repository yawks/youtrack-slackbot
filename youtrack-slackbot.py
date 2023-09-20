from typing import List, cast
from flask import Flask
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt.adapter.flask import SlackRequestHandler
from util import config
from util.config import Config
from util.utils import split_string, get_args, get_now_timestamp
from youtrack.youtrack_checker import YoutrackChecker

MSG_NO_QUERY_SET = "No query defined for this channel, first set one with `!set_query` command"

SLACK_MAX_MESSAGE_SIZE = 10000
SLACK_MAX_BLOCK_SIZE = 3000

configuration = Config()

app = Flask(__name__)
app = App(
    token=configuration.configuration["slack"]["bot_token"],
    signing_secret=configuration.configuration["slack"]["signing_secret"]
)


@app.event("message")
def on_message(payload):
    msg = ""
    channel_id = payload.get("channel", "xxx")
    text = payload.get("text", "")
    args = get_args(text)
    if len(args) > 0 and args[0][0] == "!":
        channel_name = cast(dict, app.client.conversations_info(
            channel=channel_id).data).get("channel", {}).get("name", channel_id)
        msg = MSG_NO_QUERY_SET
        match args[0]:
            case "!set_query":
                query = " ".join(args[1:])
                msg = "A query already exists for this channel, delete it first."
                if channel_name not in configuration.configuration["channels"]:
                    configuration.configuration["channels"][channel_name] = query
                    configuration.configuration["channels"][channel_name +
                                                            "."+config.TRACKING_LASTCHECK] = get_now_timestamp()
                    msg = "Query set"
            case "!del_query":
                if channel_name in configuration.configuration["channels"]:
                    del configuration.configuration["channels"][channel_name]
                    del configuration.configuration["channels"][channel_name +
                                                                "."+config.TRACKING_LASTCHECK]
                    msg = "Query deleted"
            case "!show_query":
                if channel_name in configuration.configuration["channels"]:
                    msg = configuration.configuration["channels"][channel_name]
            case "!enable":
                msg = _enable_module(args, channel_name)
            case "!disable":
                msg = _disable_module(args, channel_name)
            case "!config":
                msg = _config(channel_name)
            case "!stats":
                msg = _stats(args, channel_name)
            case "!digest":
                msg = _digest(channel_name)
            case _:
                msg = _help()
        configuration.save_config()
        send_message_to_channel(channel_name, msg)


def _enable_module(args: List[str], channel_name: str) -> str:
    msg = MSG_NO_QUERY_SET
    if channel_name in configuration.configuration["channels"]:
        msg = ("You must specify which module you want to enable: tracking, stats"
               "and in which frequence: polling, daily + time, weekly + day + time\n"
               "eg:\n"
               "`!enable tracking polling`\n"
               "`!enable tracking daily 7:30`  (24h format)\n"
               "`!enable stats weekly friday 16:00` (24h format)\n"
               )
        if len(args) > 2:
            module = args[1]
            frequency = args[2]
            if module in config.MODULES and frequency in config.FREQUENCIES:
                if frequency == config.FREQUENCY_DAILY and len(args) != 4:
                    msg = ("For _daily_ frequency you should set the time\n"
                           "eg: `!enable stats daily 13:50` (24 format)")
                elif frequency == config.FREQUENCY_WEEKLY and len(args) != 5:
                    msg = ("For _weekly_ frequency you should set the day and the time\n"
                           "eg: `!enable stats weekly monday 13:50` (24 format)")
                else:
                    configuration.configuration["channels"][f"{channel_name}.{module}"] = " ".join(
                        args[2:])
                    configuration.save_config()
                    msg = f"""Module "{module}" enabled"""

    return msg


def _disable_module(args: List[str], channel_name: str) -> str:
    msg = MSG_NO_QUERY_SET
    if channel_name in configuration.configuration["channels"]:
        msg = "You must specify which module you want to disable: tracking, digest, stats"
        if len(args) > 1:
            module = args[1]
            if module in config.MODULES:
                msg = f"""Module "{module}" not enabled for "{channel_name}" """
                if f"{channel_name}.{module}" in configuration.configuration["channels"]:
                    del configuration.configuration["channels"][f"{channel_name}.{module}"]
                    configuration.save_config()
                    msg = f"""Module "{module}" disabled"""

    return msg


def _config(channel_name: str) -> str:
    msg = "No configuration set for this channel"
    if channel_name in configuration.configuration["channels"]:
        channels_config = configuration.configuration["channels"]
        msg = f"""Youtrack config for _{channel_name}_:
- youtrack query: `{channels_config[channel_name]}`"""

        def get_optional_value(suffix: str) -> str:
            value: str = ""
            if channels_config.get(channel_name + "." + suffix, "") != "":
                value = f"""
- {suffix} {channels_config[channel_name+ "." +suffix]}"""
            return value

        msg += get_optional_value(config.MODULE_TRACKING) \
            + get_optional_value(config.TRACKING_LASTCHECK) \
            + get_optional_value(config.MODULE_STATS)

    return msg


def _stats(args: List[str], channel_name: str) -> str:
    msg: str = "Syntax: `!stats <period>` (see youtrack documentation: https://www.jetbrains.com/help/youtrack/server/Search-and-Command-Attributes.html#Date-and-Period-Values )"
    if len(args) > 1:
        msg = youtrack.get_stats(channel_name, " ".join(args[1:]))

    return msg


def _digest(channel_name: str) -> str:
    return youtrack.get_digest(channel_name)


def _help():
    return """Youtrack bot commands:
 - set_query [youtrack query]: define a youtrack query for this channel. This query will be polled to check new incoming tickets.
 - show_query: display the previously defined query
 - del_query: delete the query
 - stats [youtrack period]: display number of created tickets for given youtrack period (eg: Today, 2023-09-12 .. 2023-09-14, ...)
 - digest: display the list of issues for the query
 - enable [module: tracking|stats] [frequency: polling|daily|weekly] (optional: time)
   eg:
       `!enable tracking polling`
       `!enable stats weekly friday 16:00` (24h format)
"""


def send_message_to_channel(channel_name: str, message: str):
    for chunk in split_string(message, SLACK_MAX_MESSAGE_SIZE):
        blocks = []
        for sub_chunk in split_string(chunk, SLACK_MAX_BLOCK_SIZE):
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": sub_chunk
                    }
                })
        app.client.chat_postMessage(channel=channel_name,
                                    text="digest",
                                    blocks=blocks)


if __name__ == "__main__":
    handler = SlackRequestHandler(app)
    youtrack = YoutrackChecker(configuration, send_message_to_channel)
    youtrack.start()
    SocketModeHandler(
        app, configuration.configuration["slack"]["app_token"]).start()
