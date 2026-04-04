import logging
from notifier.weekly import send_weekly_email

logging.basicConfig(level=logging.INFO)
if __name__ == "__main__":
    send_weekly_email()
