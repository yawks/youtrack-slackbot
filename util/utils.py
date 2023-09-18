from typing import List, Tuple
from datetime import datetime


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


def get_now_timestamp() -> str:
    return datetime.now().strftime('%Y-%m-%dT%H:%M')