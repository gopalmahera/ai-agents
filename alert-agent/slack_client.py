import requests

from config import SLACK_WEBHOOK_URL


def send_slack(message: str) -> None:
    if not SLACK_WEBHOOK_URL:
        raise ValueError("SLACK_WEBHOOK_URL is not set")

    response = requests.post(
        SLACK_WEBHOOK_URL,
        json={"text": message},
        timeout=30,
    )
    response.raise_for_status()
