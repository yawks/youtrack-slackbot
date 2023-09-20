from typing import List
import json
import requests

REQUEST_TIMEOUT_SECS = 30


class Youtrack:
    def __init__(self, base_url: str, authorization_header: str, api_endpoint: str, issue_id_field: str, all_issue_fields: str, max_issues: int):
        self.base_url: str = base_url
        self.max_issues = max_issues
        self.all_issue_fields = all_issue_fields
        self.issue_id_field = issue_id_field

        self.headers = {
            'Authorization': authorization_header
        }

        self.api_endpoint: str = api_endpoint

    def get_issues(self, query: str, only_issue_ids: bool = False) -> List[dict]:
        params = {
            "$top": self.max_issues,
            "fields": self.all_issue_fields if not only_issue_ids else self.issue_id_field
        }
        if query != "":
            params["query"] = query
        # https://www.jetbrains.com/help/youtrack/standalone/api-howto-get-issues-with-all-values.html#summary
        response = requests.get(f"{self.api_endpoint}/issues",
                                params=params,
                                headers=self.headers,
                                timeout=REQUEST_TIMEOUT_SECS)
        issues = json.loads(response.content)
        return sorted(issues, key=lambda x: x["created"])
