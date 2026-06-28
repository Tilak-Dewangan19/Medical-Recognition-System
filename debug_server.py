import subprocess
import os
import sys

print('Killing Python processes...')
subprocess.run(['taskkill', '/F', '/IM', 'python.exe', '/T'], shell=True, check=False)
print('Running processes:')
print(subprocess.check_output(['tasklist'], shell=True, text=True))
