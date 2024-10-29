import streamlit as st
import csv
import os
import re
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from time import sleep
from typing import List, Optional
import io


class DebugLogger:
    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode

    def debug(self, message: str):
        if self.debug_mode:
            print(f"[DEBUG] {message}")


class EmailValidator:
    @staticmethod
    def is_valid_email(email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))


class EmailAutomation:
    def __init__(self, debug_mode: bool = False):
        self.debug_logger = DebugLogger(debug_mode)
        self.logger = self._setup_logging()
        self.smtp_server = None

    def _setup_logging(self) -> logging.Logger:
        logger = logging.getLogger('ColdEmailAutomation')
        logger.setLevel(logging.INFO)

        # Create logs directory if it doesn't exist
        if not os.path.exists('logs'):
            os.makedirs('logs')

        # Set up file handler with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_handler = logging.FileHandler(f'logs/email_log_{timestamp}.txt')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        return logger

    def read_csv_content(self, csv_content) -> List[str]:
        """Read and validate email addresses from CSV content."""
        self.debug_logger.debug("Reading CSV content")
        valid_emails = []

        try:
            # Convert bytes to string if necessary
            if isinstance(csv_content, bytes):
                csv_content = csv_content.decode('utf-8')

            # Create a CSV reader from the string content
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)

            # Find email column
            email_column = None
            for column in reader.fieldnames:
                if 'email' in column.lower():
                    email_column = column
                    break

            if not email_column:
                raise ValueError("No email column found in CSV")

            # Validate emails
            for row in reader:
                email = row[email_column].strip()
                if EmailValidator.is_valid_email(email):
                    valid_emails.append(email)
                else:
                    self.logger.warning(f"Invalid email found: {email}")

        except Exception as e:
            self.logger.error(f"Error reading CSV: {str(e)}")
            raise

        self.debug_logger.debug(f"Found {len(valid_emails)} valid emails")
        return valid_emails

    def setup_smtp(self, email: str, password: str):
        """Setup SMTP connection with Gmail."""
        self.debug_logger.debug("Setting up SMTP connection")
        try:
            self.smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
            self.smtp_server.starttls()
            self.smtp_server.login(email, password)
            self.logger.info("SMTP connection established successfully")
        except Exception as e:
            self.logger.error(f"SMTP setup failed: {str(e)}")
            raise

    def create_message(self, sender: str, recipient: str, subject: str,
                       content: str, attachments: Optional[List[tuple]] = None) -> MIMEMultipart:
        """Create email message with optional attachments."""
        self.debug_logger.debug(f"Creating email message for: {recipient}")
        message = MIMEMultipart()
        message['From'] = sender
        message['To'] = recipient
        message['Subject'] = subject

        # Add HTML content
        message.attach(MIMEText(content, 'html'))

        # Add attachments if provided
        if attachments:
            for file_name, file_content in attachments:
                try:
                    img = MIMEImage(file_content)
                    img.add_header('Content-Disposition', 'attachment', filename=file_name)
                    message.attach(img)
                except Exception as e:
                    self.logger.error(f"Error attaching file {file_name}: {str(e)}")
                    raise

        return message

    def send_emails(self, sender: str, emails: List[str], subject: str,
                    content: str, attachments: Optional[List[tuple]] = None):
        """Send emails to all recipients with retry mechanism."""
        self.debug_logger.debug("Starting email sending process")
        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx, email in enumerate(emails):
            retries = 3
            while retries > 0:
                try:
                    message = self.create_message(sender, email, subject, content, attachments)
                    self.smtp_server.send_message(message)
                    self.logger.info(f"Email sent successfully to {email}")
                    self.debug_logger.debug(f"Email sent to: {email}")
                    status_text.text(f"Sent email to: {email}")
                    progress_bar.progress((idx + 1) / len(emails))
                    sleep(1)
                    break
                except Exception as e:
                    retries -= 1
                    self.logger.error(f"Failed to send email to {email}: {str(e)}")
                    if retries > 0:
                        self.debug_logger.debug(f"Retrying email to {email}. Attempts remaining: {retries}")
                        status_text.text(f"Retrying email to {email}... ({retries} attempts remaining)")
                        sleep(2)
                    else:
                        self.logger.error(f"Max retries reached for {email}")
                        status_text.text(f"Failed to send email to {email} after maximum retries")

        status_text.text("Email campaign completed!")


def main():
    st.title("Email Automation System")

    # Default credentials
    sender_email = "datanyx.ai@gmail.com"
    sender_password = "nunx tjqo ubpy jhtq"

    # Debug mode checkbox
    debug_mode = st.checkbox("Enable Debug Mode")

    # File uploader for CSV
    csv_file = st.file_uploader("Upload CSV file containing email addresses", type=['csv'])

    # File uploader for attachments
    attachment_files = st.file_uploader("Upload attachments (optional)", type=['jpg', 'jpeg', 'png', 'pdf'],
                                        accept_multiple_files=True)

    # Email content
    subject = st.text_input("Email Subject")
    content = st.text_area("Email Content (HTML supported)")

    if st.button("Send Emails"):
        try:
            if not csv_file:
                st.error("Please upload a CSV file")
                return

            if not subject or not content:
                st.error("Please fill in both subject and content")
                return

            automation = EmailAutomation(debug_mode)

            # Read CSV
            csv_content = csv_file.read()
            emails = automation.read_csv_content(csv_content)

            if not emails:
                st.error("No valid email addresses found in CSV")
                return

            st.info(f"Found {len(emails)} valid email addresses")

            # Process attachments
            attachments = []
            if attachment_files:
                for file in attachment_files:
                    attachments.append((file.name, file.read()))

            # Setup SMTP
            automation.setup_smtp(sender_email, sender_password)

            # Send emails
            automation.send_emails(sender_email, emails, subject, content, attachments)

            st.success("Email campaign completed successfully!")

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            logging.error(f"Critical error: {str(e)}")
        finally:
            if automation.smtp_server:
                automation.smtp_server.quit()


if __name__ == "__main__":
    main()