from typing import List
import json
import requests

REQUEST_TIMEOUT_SECS = 30

YOUTRACK_MAX_ISSUES = 100000
YOUTRACK_ALL_ISSUE_FIELDS = "id,idReadable,created,updated,resolved,reporter(email),updater(email),commentsCount,tags(name),customFields($type,id,projectCustomField($type,id,field($type,id,name)),value($type,name,minutes,presentation)),summary,description"
YOUTRACK_ISSUE_ID_FIELD = "id"


class Youtrack:
    def __init__(self, base_url: str, authorization_header: str, api_endpoint: str):
        self.base_url: str = base_url

        self.headers = {
            'Authorization': authorization_header
        }

        self.api_endpoint: str = api_endpoint

    def get_issues(self, query: str, only_issue_ids: bool = False) -> List[dict]:
        params = {
            "$top": YOUTRACK_MAX_ISSUES,
            "fields": YOUTRACK_ALL_ISSUE_FIELDS if not only_issue_ids else YOUTRACK_ISSUE_ID_FIELD
        }
        if query != "":
            params["query"] = query
        # https://www.jetbrains.com/help/youtrack/standalone/api-howto-get-issues-with-all-values.html#summary
        response = requests.get(f"{self.api_endpoint}/issues",
                                params=params,
                                headers=self.headers,
                                timeout=REQUEST_TIMEOUT_SECS)
        return json.loads(response.content)
