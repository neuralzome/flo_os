from termcolor import colored

def debug(msg, tag="-"):
    print(colored(f"[{tag}] {msg}", "white"))

def info(msg, tag="-"):
    print(colored(f"[{tag}] {msg}", "green"))

def warn(msg, tag="-"):
    print(colored(f"[{tag}] {msg}", "yellow"))

def error(msg, tag="-"):
    print(colored(f"[{tag}] {msg}", "red"))

