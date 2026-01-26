from datetime import datetime, timezone
import imaplib
import email
from email.header import decode_header
import json
from json import JSONDecodeError
import os
import re

# pattern_uid = re.compile(r'\d+ \(UID (?P<uid>\d+)\)')

class GmailOrganizer():
    def read_config(self):
        try:
            config = ''
            config_path = os.path.join(os.path.dirname(__file__), 'conf', 'config.json')
            with open(config_path, 'rt') as f:
                config = json.load(f)
            config_str = json.dumps(config, indent=4)
            self.config_data = json.loads(config_str)
        except JSONDecodeError:
            print(f'The config file has malformed JSON data.')
        return

    def read_login_info(self):
        '''
        login_info.json has the format:
        {
          "email": "mygmail.com",
          "passcode": "app password"
        }
        '''
        try:
            config = ''
            config_path = os.path.join(os.path.dirname(__file__), 'conf', 'login_info.json')
            with open(config_path, 'rt') as f:
                config = json.load(f)
            config_str = json.dumps(config, indent=4)
            self.login_data = json.loads(config_str)
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

    def check_email(self, criteria, keyword, days_to_wait):
        now = datetime.now(timezone.utc)
        print(f'Searching for {criteria} = {keyword}')
        if criteria == 'FROM':
            result, data = self.mail.search(None, criteria, keyword)
        else:
            result, data = self.mail.uid('search', None, r'(X-GM-RAW "{criteria}:\"{keyword}\"")')
        split_data = data[0].split()
        print(f'Length of data: {len(split_data)}')
        email_date = ''
        loop_count = 0
        valid_email_nums = []
        for num in split_data:
            loop_count += 1
            try:
                result, msg_data = self.mail.fetch(num, "(RFC822)")
                # check for result == 'Ok'
                if result != "OK":
                    print(f'Result problem: {result}')
                    continue
                if len(msg_data) == 2:
                    msg_body = msg_data[0]
                elif len(msg_data) == 3:
                    msg_body = msg_data[1]
                else:
                    print(f'Not sure where msg body is for num= {num}')
                    continue
                msg = email.message_from_bytes(msg_body[1])
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
                    valid_email_nums.append(num)
            except ValueError as e:
                print(f'ValueError on {criteria} = {keyword} email on {email_date}')
            except AttributeError as e2:
                print(f'AttributeError on {criteria} = {keyword} email on {email_date}: {e2}')
        return valid_email_nums

    def remove_old(self, remove_items):
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
            num_list = self.check_email(criteria, keyword, days_to_wait)
            for num in num_list:
                self.mail.store(num, '+X-GM-LABELS', '\\Trash')
                self.mail.store(num, '-X-GM-LABELS', '\\Inbox')
            print(f'Removed {len(num_list)} emails for {keyword}')
            deleted_count = deleted_count + len(num_list)
        self.mail.expunge()
        print(f"Old emails deleted: {deleted_count}")

    def folder_exists(self, folder_name):
        # '""' means the reference is the top level, '*' means all mailboxes
        result, data = self.mail.list(directory='""', pattern='*')
        if result == 'OK':
            for line in data:
                # line is bytes, e.g., b'(\\HasNoChildren) "/" "INBOX"'
                # We need to parse the folder name from the response
                # A simpler way is to check the raw response for the name
                if folder_name.encode() in line:
                    return True
        return False

    def make_folder(self, folder_name):
        result, message = self.mail.create(folder_name)
        if result == 'OK':
            print(f"Folder '{folder_name}' created successfully.")
        else:
            print(f"Failed to create folder '{folder_name}': {message[0].decode()}")

    def move_to_archive(self, move_items):
        moved_count = 0
        # loop through move items
        for item in move_items:
            criteria = "FROM"
            keyword = item['keyword']
            folder_name = item['folder']
            days_to_wait = item['days']

            # check if folder_name exists
            exists = self.folder_exists(folder_name)
            # if not, create folder
            if not exists:
                self.make_folder(folder_name)
            num_list = self.check_email(criteria, keyword, days_to_wait)
            for num in num_list:
                self.mail.store(num, '+X-GM-LABELS', f'{folder_name}')
                # self.mail.store(num, '-X-GM-LABELS', '\\Inbox')
                self.mail.store(num, '+FLAGS', '\\Deleted')
            print(f'Moved {len(num_list)} emails for {keyword}')
            moved_count = moved_count + len(num_list)
        self.mail.expunge()
        print(f"Emails moved to archive: {moved_count}")

    def delete_spam(self, spam_items):
        ret = self.mail.select(mailbox='inbox', readonly=False)
        print(f'Select returned: {ret}')
        if ret[0] != 'OK':
            print(f'Selecting inbox failed, returning {ret}. Exiting.')
            exit(-1)

        now = datetime.now(timezone.utc)
        print(now)
        deleted_count = 0
        criteria = "subject"
        days_to_wait = "0"
        for item in spam_items:
            keyword = item
            print(f'{criteria} - {keyword} - {days_to_wait}')
            num_list = self.check_email(criteria, keyword, days_to_wait)
            for num in num_list:
                self.mail.store(num, '+X-GM-LABELS', '\\Trash')
                self.mail.store(num, '-X-GM-LABELS', '\\Inbox')
            print(f'Removed {len(num_list)} emails for {keyword}')
            deleted_count = deleted_count + len(num_list)
        self.mail.expunge()
        print(f"Spam emails deleted: {deleted_count}")



    def process_email(self):
        remove_items = self.config_data["remove"]
        print('Checking inbox')
        self.remove_old(remove_items)
        move_items = self.config_data['move']
        self.move_to_archive(move_items)
        spam_items = self.config_data["spamwords"]
        self.delete_spam(spam_items)



    def __init__(self):
        self.mail = imaplib.IMAP4_SSL("imap.gmail.com")
        self.read_login_info()
        self.mail.login(self.login_data["email"], self.login_data["passcode"])

        self.read_config()
        self.process_email()
        self.mail.logout()



if __name__ == '__main__':
    go = GmailOrganizer()
