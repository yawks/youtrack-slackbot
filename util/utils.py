from typing import List
from datetime import datetime, timedelta

STAT_YOUTRACK_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


def get_args(command: str) -> List[str]:
    """
        Split command into arguments.
        Multiple words inside quotes are considered as one argument.
    """
    args: List[str] = []
    quote_open = False
    current_arg = ""
    if command is not None:
        for token in command.strip().split(' '):
            if token == "":
                continue
            if quote_open:
                current_arg += ' ' + token
                if token[-1] == '"':
                    args.append(current_arg[1:-1])  # remove quotes
                    current_arg = ""
                    quote_open = False
            elif token[0] == '"':
                quote_open = True
                current_arg = token
            else:
                args.append(token)

    return args


def get_today_timestamp(seconds_delta:int = 0) -> str:
    now = datetime.now() + timedelta(seconds=seconds_delta)
    return now.strftime(STAT_YOUTRACK_DATE_FORMAT)



def split_string(string, max_characters):
    lines = string.splitlines()

    result = []
    current_chunk = ""
    for line in lines:
        if len(current_chunk) + len(line) < max_characters:
            current_chunk += line + "\n"
        else:
            result.append(current_chunk)
            current_chunk = line + "\n"
    
    result.append(current_chunk)

    return result
