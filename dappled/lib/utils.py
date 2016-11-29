import contextlib
import subprocess
import netifaces
import socket
import signal

# http://blog.thelinuxkid.com/2013/06/get-python-subprocess-output-without.html
# Unix, Windows and old Macintosh end-of-line
newlines = ['\n', '\r\n', '\r']
def unbuffered(proc, stream='stdout'):
    stream = getattr(proc, stream)
    with contextlib.closing(stream):
        while True:
            out = []
            last = stream.read(1)
            # Don't loop forever
            if last == '' and proc.poll() is not None:
                break
            while last not in newlines:
                # Don't loop forever
                if last == '' and proc.poll() is not None:
                    break
                out.append(last)
                last = stream.read(1)
            out = ''.join(out)
            yield out

def get_ip_addresses():
    results = []
    for if_name in netifaces.interfaces():
        if if_name == 'lo': continue
        for info in netifaces.ifaddresses(if_name).setdefault(netifaces.AF_INET, []):
            if 'addr' in info:
                results.append(info['addr'])
    if not results:
        return ['127.0.0.1']
    return results

# from notebook/notebookapp.py
def random_ports(port, n):
    """Generate a list of n random ports near the given port.

    The first 5 ports will be sequential, and the remaining n-5 will be
    randomly selected in the range [port-2*n, port+2*n].
    """
    for i in range(min(5, n)):
        yield port + i
    for i in range(n-5):
        yield max(1, port + random.randint(-2*n, 2*n))

# based on the following:
# notebook/notebookapp.py
# http://stackoverflow.com/questions/8599984/how-to-pick-a-free-port-number-in-python
# https://gist.github.com/dbrgn/3979133
def get_free_port(port, port_retries):
    for port in random_ports(port, port_retries+1):
        try:
            s = socket.socket()
            s.bind(('', port))
            port = s.getsockname()[1]
            s.close()
            return port
        except socket.error as e:
            if e.errno == errno.EADDRINUSE:
                self.log.info('The port %i is already in use, trying another port.' % port)
                continue
            elif e.errno in (errno.EACCES, getattr(errno, 'WSAEACCES', errno.EACCES)):
                self.log.warn("Permission to listen on port %i denied" % port)
                continue
            else:
                raise
    return None

# http://stackoverflow.com/questions/13593223/making-sure-a-python-script-with-subprocesses-dies-on-sigint
class SignalCatcher:
    def __init__(self):
        self.current_subprocs = set()
        self.shutdown = False

        def handle_signal(signum, frame):
            # send signal received to subprocesses
            self.shutdown = True
            for proc in self.current_subprocs:
                if proc.poll() is None:
                    proc.send_signal(signum)

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

    def add_proc(self, proc):
        self.current_subprocs.add(proc)

    def remove_proc(self, proc):
        self.current_subprocs.remove(proc)



