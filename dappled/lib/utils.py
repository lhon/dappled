import contextlib
import subprocess
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
            yield out            yield out

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



