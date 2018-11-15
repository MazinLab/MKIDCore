from datetime import datetime
import threading
from .corelog import getLogger
import time
import re
import traceback


def print2socket(the_message, the_socket=None, timestamp=True, warning=False, error=False, queue=None):
    """
    Sends information in order to be displayed in the GUI

    Arguments:
        the_message: message to display
    Optional keywords:
        the_socket: the socket used by the server to send
                    data back to the client. if not provided (default), this
                    function is used by the client to display data.
        timestamp (boolean): if True (default), a timestamp is added before
            the message
        error (boolean): if True (not default), the word 'ERROR: ' is added
            before the message
        warning (boolean): if True (not default), the word 'WARNING: ' is added
            before the message unless error is True
    """
    if error:
        the_message = 'ERROR: '+the_message
    elif warning:
        the_message = 'WARNING: '+the_message
    if timestamp:
        datestr = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        the_message = datestr+' > '+the_message
    if the_socket:
        try:
            the_socket.sendall(the_message)
        except:
            getLogger(__name__).error(the_message)
        time.sleep(0.1)
    elif queue:
        for line in the_message.splitlines():
            line = re.sub('(\n|\r)','<br>', line).rstrip().rstrip('<br>')
            if line:
                queue.put(line)


class Thread(object):
    """
    Class to start and stop each of the threads
    """
    def __init__(self, func, name, log, daemon=False):
        """
        Initialization
        """
        self._func = func
        self._name = name
        self._stop_event = threading.Event()
        self._stop_event.set()
        self._log = log
        self._daemon = daemon
        self._thread = None

    @property
    def is_running(self):
        """
        Is the thread running?
        """
        return not self._stop_event.is_set()

    def start(self, args, kwargs={}, main=False):
        """
        Starting the thread
        """
        if not self.is_running:
            self._log.info('Starting thread: ' + self._name)
            self._stop_event.clear()
            kwargs['stop_event'] = self._stop_event
            if main:
                self._func(*args, **kwargs)
            else:
                self._thread = start_new_thread(self._func, args, kwargs=kwargs,
                                                log=self._log, name=self._name,
                                                daemon=self._daemon)
        else:
            self._log.info('Thread already running: ' + self._name)

    def stop(self):
        """
        Starting the thread
        """
        if self.is_running:
            self._log.info('Ending thread: ' + self._name)
            self._stop_event.set()
        else:
            self._log.info('Cannot stop non-running thread: ' + self._name)


def start_new_thread(target, args, kwargs={}, log=None, name='', timestamp=True, socket=None, daemon=False):
    """
    Starts a new thread with target function. If not successful, error is
    logged.
    Args:
        target (function): Function to execute in the new thread.
        args (tuple): Tuple with arguments of the function.
        kwargs (dictionary, optional): dictionary of keyword arguments for the
            function. Defaults to {}.
        queue (Queue object, optional): Queue to send error messages.
            Defaults to None.
        name (str, optional): Thread name. Defaults to ''.

    Returns:

    Raises:
    """
    try:
        thread = threading.Thread(target=target, args=args, name=name,
                                  kwargs=kwargs)
        if daemon:
            thread.daemon = True
        thread.start()
        return thread
    except Exception:
        errmsg = traceback.format_exc()
        if log:
            log.error(errmsg)
        else:
            print2socket(errmsg, timestamp=timestamp, the_socket=socket)
