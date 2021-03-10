from logging import getLogger
import smtplib, time, ssl
from email.mime.text import MIMEText
from datetime import datetime


MAIL_SUBARU = 'mail.subaru.nao.ac.jp'
MAIL_UCSB = 'mta.connect.ucsb.edu'

UCSB_MAIL_PASSWORD = ''
EMAIL_BLOB = ''
SMS_BLOB = ''
EMAIL_BLOB = ('\t\x18\x06\x01;$:\x02.\x0b1\x0f*\x1e*\x11\x0077F\x12\x01\r#\x146=\t5\x08W\x1c;;&\x02-!1\x0f'
              '\x11\x1e:\r\x007\'F9\x16\x0e\x05:SF\x1f66\x1a\x18\x04&1]8Q>\x08?\x1e:\n\x06#\x02\x00:/\x05'
              '\x0b*6G\x1d#\x08#\x1e8\x1eB\x04\x04\x0f\x1c\x14";:\x0b\x01B(\x06);3S:RCN')

SMS_BLOB = ('\t\x18\x06\x01;$:\x02.\x0b1\x0f=\t!Q/\n\x06F=8$R=Q1A\x08&4D\x050F\x06\x03P@\x0f?0-\x0f;\x1d7'
            '\x069\x16\x0e\x05:\x1b*\n"\x0b\x05\n,\t*],\x182 \x17\x1d>\r\x0780\x06*^X\x16:RCN')


MAIL_URL = MAIL_SUBARU

MAIL_USER = '' if 'subaru' in MAIL_URL else 'physics-mazinlab-instruments@ucsb.edu'
MAIL_PASSWORD = '' if 'subaru' in MAIL_URL else UCSB_MAIL_PASSWORD
MAIL_PORT = 25
MAIL_USE_TLS = False

_NOTIFY_TIMES = {}


CELL_GATEWAY = {'tmobile': 'tmomail.net', 'att': 'txt.att.net', 'verizon': 'vtext.com', 'virgin': 'vmobl.com',
                'boost': 'sms.myboostmobile.com', 'xfinity': 'vtext.com', 'sprint': 'messaging.sprintpcs.com'}


def make_blob(email_dict, key='labpass'):
    """To make the blob pass a dictionary of name:email pairs. """
    import base64
    from itertools import cycle
    b1 = base64.b64encode(repr(email_dict).encode('utf-8'))
    encrypted = ''.join([chr(ord(a) ^ ord(b)) for (a, b) in zip(b1, cycle(key))])
    return encrypted


def restore_blob(blob, key='labpass'):
    import base64
    from itertools import cycle
    decrypted = ''.join([chr(ord(a) ^ ord(b)) for (a, b) in zip(blob, cycle(key))])
    return eval(base64.b64decode(decrypted))


EMAIL_ADDR = restore_blob(EMAIL_BLOB)
SMS_ADDR = restore_blob(SMS_BLOB)


def sms_email(recip):
    for k in CELL_GATEWAY.values():
        if k in recip:
            return True
    return False


def notify(recipients, message, sender='mkidcore', subject=None, holdoff_min=5, email=True, sms=True, holdoff_key=None):
    """ If Subject is none will use the first 20 characters to the left of the of the first colon after stripping it of
    whitespace.

    if holdoff_key is None hash((tuple(recipients), message, email, sms)) will be used which will means a one character
    difference in the message is all it takes for a new message to be sent.

    sender should be a word on an email address. whitespace, commas and anything not allowed in email addresses is bad
    """
    if isinstance(recipients, str):
        recipients = (recipients,)

    sender=sender.replace(' ', '_').replace(',','_')

    global _NOTIFY_TIMES
    if holdoff_key is None:
        holdoff_key = hash((tuple(recipients), message, email, sms))
    if time.time() - _NOTIFY_TIMES.get(holdoff_key, 0) < holdoff_min*60:
        getLogger(__name__).debug('Notification hold-off in effect.')
        return
    _NOTIFY_TIMES[holdoff_key] = time.time()

    to = []
    tosms = []

    for r in recipients:
        if '@' in r:
            if sms_email(r):
                tosms.append(r)
            else:
                to.append(r)
            continue

        if email:
            try:
                to.append(EMAIL_ADDR[r])
            except KeyError:
                getLogger(__name__).warning('No email known for {}'.format(r))
        if sms:
            try:
                tosms.append(SMS_ADDR[r])
            except KeyError:
                getLogger(__name__).warning('No SMS known for {}'.format(r))

    if subject is None:
        subject = message.partition(':')[0].strip()
        subject = subject[:20] + ('...' if len(subject)>20 else '')

    emailmsg = MIMEText(message, )
    emailmsg['Subject'] = subject
    emailmsg['From'] = sender
    emailmsg['To'] = ', '.join(to)

    smsmsg = MIMEText(message[:160-len(subject)-5], )
    smsmsg['Subject'] = subject
    smsmsg['From'] = sender
    smsmsg['To'] = ', '.join(tosms)

    user, password = MAIL_USER, MAIL_PASSWORD
    try:
        with open('~/.mkidcore_email') as f:
            user, _, password = f.readline().partition(':')
    except IOError:
        getLogger(__name__).info('~/.mkidcore_email file with "login:password" not found, using defaults')

    if not tosms+to:
        return

    try:
        if MAIL_USE_TLS:
            smtp = smtplib.SMTP_SSL(MAIL_URL, MAIL_PORT, ssl.create_default_context())
        else:
            smtp = smtplib.SMTP(MAIL_URL, port=MAIL_PORT)

        if user+password:
            smtp.login(user, password)

        if to:
            getLogger(__name__).debug("Sending email:\n{}\nto {}\n".format(emailmsg, to))
            smtp.sendmail(emailmsg['From'], to, emailmsg.as_string())

        if tosms:
            smtp.sendmail(smsmsg['From'], tosms, smsmsg.as_string())
            getLogger(__name__).debug("Sending SMS:\n{}\nto {}\n".format(smsmsg, tosms))
        smtp.close()
    except Exception as e:
        fstr = 'The following email was not sent because {}\n{}'
        getLogger(__name__).error(fstr.format(e, body))

