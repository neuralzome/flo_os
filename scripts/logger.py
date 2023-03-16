import time

from termcolor import colored

def current_milli_time():
    return round(time.time() * 1000)

def debug(msg, tag="-"):
    print(colored(f"[{current_milli_time()}] [{tag}] {msg}", "white"))

def info(msg, tag="-"):
    print(colored(f"[{current_milli_time()}] [{tag}] {msg}", "green"))

def warn(msg, tag="-"):
    print(colored(f"[{current_milli_time()}] [{tag}] {msg}", "yellow"))

def error(msg, tag="-"):
    print(colored(f"[{current_milli_time()}] [{tag}] {msg}", "red"))

