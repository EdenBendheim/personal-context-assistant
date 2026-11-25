from email.message import EmailMessage
from pathlib import Path
import mailbox
import tempfile
import unittest

from personal_context.messages import scan_mbox


def email_message(identifier, *, author="owner@example.invalid", recipient="alex@example.invalid"):
    mail = EmailMessage()
    mail["From"] = author
    mail["To"] = recipient
    mail["Date"] = "Tue, 01 Sep 2026 10:00:00 +0000"
    mail["Message-ID"] = f"<{identifier}@example.invalid>"
    return mail


class MboxTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(self.enterContext(tempfile.TemporaryDirectory())) / "synthetic.mbox"

    def write_mail(self, *messages):
        box = mailbox.mbox(self.path)
        try:
            for mail in messages:
                box.add(mail)
        finally:
            box.close()

    def test_plain_body_excludes_nested_attachments_and_encapsulated_mail(self):
        mail = email_message("outer")
        mail.set_content("Synthetic top-level body")
        mail.add_alternative("<p>HTML alternative</p>", subtype="html")
        document = EmailMessage()
        document.set_content("Synthetic attached text")
        document.add_alternative("<p>Attached HTML</p>", subtype="html")
        document["Content-Disposition"] = "attachment"
        mail.make_mixed()
        mail.attach(document)
        forwarded = email_message("forwarded")
        forwarded.set_content("Separate synthetic conversation")
        wrapper = EmailMessage()
        wrapper.set_type("message/rfc822")
        wrapper.set_payload([forwarded])
        mail.attach(wrapper)
        self.write_mail(mail)

        [record] = scan_mbox(self.path)
        self.assertEqual(record.message.body, "Synthetic top-level body")

    def test_html_body_with_text_attachment_is_still_skipped(self):
        mail = email_message("html-only")
        mail.set_content("<p>HTML only</p>", subtype="html")
        mail.add_attachment("Synthetic plain attachment", filename="notes.txt")
        self.write_mail(mail)

        [record] = scan_mbox(self.path)
        self.assertEqual(record.skipped, "No supported plain-text body")
        self.assertIsNone(record.message)
