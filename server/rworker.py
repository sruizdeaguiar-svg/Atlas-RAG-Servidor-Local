"""One-use launcher: resource limits survive exec into Apple's Seatbelt sandbox."""
import os, resource, sys
from pathlib import Path
resource.setrlimit(resource.RLIMIT_CPU,(25,25))
resource.setrlimit(resource.RLIMIT_FSIZE,(4*1024*1024,4*1024*1024))
resource.setrlimit(resource.RLIMIT_NOFILE,(1024,1024))
work=Path(sys.argv[2]); os.chdir(work)
fd=os.open(work/'output.txt',os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600)
os.dup2(fd,1); os.dup2(fd,2)
os.execv('/usr/bin/sandbox-exec',['sandbox-exec','-f',str(work/'sandbox.sb'),sys.argv[1],'--vanilla','--no-echo','--file='+str(work/'analysis.R')])
