from datetime import datetime, timezone
import imaplib
import email
from email.header import decode_header
import json
from json import JSONDecodeError
import os
import re

pattern_uid = re.compile(r'\d+ \(UID (?P<uid>\d+)\)')
EMAIL = "tcsimon58@gmail.com"
PASSWORD = "kkiq ypxe ypwp ssbb"
SPAM_KEYWORDS = ["delivered", "win big", "prize", "urgent action required"]

class GmailOrganizer():
    def read_config(self):
        try:
            config = ''
            config_path = os.path.join(os.path.dirname(__file__), 'conf', 'config.json')
            with open(config_path, 'rt') as f:
                config = json.load(f)
            config_str = json.dumps(config, indent=4)
            self. config_data = json.loads(config_str)
        except JSONDecodeError:
            print(f'The config file has malformed JSON data.')
        return

    def standardize_date(self, email_date):
        standard_date = ''
        idx = email_date.find('(')
        if idx > 0:
            stripped_date = email_date[0:idx]
            standard_date = stripped_date.strip()
        else:
            standard_date = email_date
        # from msg: Wed, 05 Nov 2025 09:54:36 +0000 (UTC)

        return standard_date

    def parse_uid(self, data):
        breakpoint()
        match = pattern_uid.match(data)
        return match.group('uid')

    def remove_junk(self, remove_items):
        ret = self.mail.select(mailbox='inbox', readonly = False)
        print(f'Select returned: {ret}')
        if ret[0] != 'OK':
            print(f'Selecting inbox failed, returning {ret}. Exiting.')
            exit(-1)

        now = datetime.now(timezone.utc)
        print(now)
        criteria = ''
        keyword = ''
        deleted_count = 0

        for item in remove_items:
            criteria = item["criteria"]
            keyword = item["keyword"]
            days_to_wait = item["days"]
            print(f'{criteria} - {keyword} - {days_to_wait}')
            result, data = self.mail.search(None, criteria, keyword)
            split_data = data[0].split()
            print(f'Length of data: {len(split_data)}')
            email_date = ''
            loop_count = 0
            for num in split_data:
                loop_count += 1
                try:
                    result, msg_data = self.mail.fetch(num, "(RFC822)")
                    # check for result == 'Ok'
                    msg = email.message_from_bytes(msg_data[0][1])
                    # subject = msg["subject"]
                    # if any(keyword.lower() in subject.lower() for keyword in SPAM_KEYWORDS):
                    #     self.mail.store(num, "+FLAGS", "\\Deleted")

                    date_format = "%a, %d %b %Y %H:%M:%S %z"
                    # from msg: Wed, 05 Nov 2025 09:54:36 +0000 (UTC)
                    header_date = decode_header(msg["Date"])[0][0]
                    standard_date = self.standardize_date(header_date)
                    email_date = datetime.strptime(standard_date, date_format)
                    diff = str(now - email_date)
                    diff_days = int(diff[0:diff.find(' ')])
                    # print(f'diff_days: {diff_days}')
                    if diff_days > int(days_to_wait):
                        self.mail.store(num, '+X-GM-LABELS', '\Trash')
                        self.mail.store(num, '-X-GM-LABELS', '\Inbox')

                except ValueError as e:
                    
                    print(f'ValueError on {criteria} = {keyword} email on {email_date}')
            print(f'Removed {loop_count} emails for {keyword}')
            deleted_count = deleted_count + loop_count
        self.mail.expunge()
        print(f"Spam emails deleted: {deleted_count}")


    def process_email(self):
        remove_items = self.config_data["remove"]
        print('Checking inbox')
        self.remove_junk(remove_items)



    def __init__(self):
        self.mail = imaplib.IMAP4_SSL("imap.gmail.com")
        self.mail.login(EMAIL, PASSWORD)

        self.read_config()
        self.process_email()
        self.mail.logout()



# breakpoint()

# mail.select("inbox")
# result, data = mail.search(None, 'FROM','Chewy.com')
# for num in data[0].split():
#     result, msg_data = mail.fetch(num, "(RFC822)")
#     msg = email.message_from_bytes(msg_data[0][1])
#     subject = msg["subject"]
#     if any(keyword.lower() in subject.lower() for keyword in SPAM_KEYWORDS):
#         mail.store(num, "+FLAGS", "\\Deleted")
# mail.expunge()
# mail.logout()
# print("Spam emails deleted!")

if __name__ == '__main__':
    go = GmailOrganizer()
