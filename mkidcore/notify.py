from logging import getLogger
import smtplib, time, ssl
from email.mime.text import MIMEText


MAIL_SUBARU = 'mail.subaru.nao.ac.jp'
MAIL_UCSB = 'mta.connect.ucsb.edu'

UCSB_MAIL_PASSWORD = ''
EMAIL_BLOB = ''
SMS_BLOB = ''
MAIL_URL = MAIL_UCSB

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


def notify(recipients, message, sender='mkidcore', subject=None, holdoff_min=5, email=True, sms=True):
    """ If Subject is none will use the first 20 characters to the left of the of the first colon after stripping it of
    whitespace.

    Holdoff is unique per recipient+message+email+sms combo. One character difference in the message is all it takes!

    """
    if isinstance(recipients, str):
        recipients = (recipients,)

    global _NOTIFY_TIMES
    holdoffkey = hash((tuple(recipients), message, email, sms))
    if time.time() - _NOTIFY_TIMES.get(holdoffkey, 0) < holdoff_min*60:
        getLogger(__name__).debug('Notification hold-off in effect.')
        return
    _NOTIFY_TIMES[holdoffkey] = time.time()

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
        subject = message.partition(':')[0].strip()[:20]
    body = message

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
            getLogger(__name__).debug("Sending email {} to {}".format(emailmsg, to))
            smtp.sendmail(emailmsg['From'], to, emailmsg.as_string())
        if tosms:
            smtp.sendmail(emailmsg['From'], tosms, smsmsg.as_string())
            getLogger(__name__).debug("Sending SMS {} to {}".format(smsmsg, tosms))
    except Exception as e:
        fstr = 'The following email was not sent because {}\n{}'
        getLogger(__name__).error(fstr.format(e, body))

