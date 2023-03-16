#!/usr/bin/env python3

#
# Copyright (C) 2023 FloMobility Pvt. Ltd.
# All rights reserved.
#
# Confidential and Proprietary - FloMobility Pvt. Ltd.
# @author: Clay Motupalli <clay@flomobility.com>
#

import os
import sys
import subprocess
import platform
import urllib.request as request
import shutil
import time

import click
import boto3
import alive_progress as alive
from simple_term_menu import TerminalMenu

import logger

VERSION = "r34.0.0"
PLATFORM = platform.uname().system.lower()
PLATFORM_TOOLS_URL = f"https://dl.google.com/android/repository/platform-tools_{VERSION}-{PLATFORM}.zip"
PLATFORM_TOOLS_PATH=f"{os.getcwd()}/platform-tools"

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME")

FLO_OS_SETUP_BUCKET_NAME = "flo-os-setup"

LOCAL_SETUP_DIR = "setup"
SSH_SETUP = "ssh_setup"
ADB_SETUP = "adb_setup"

if AWS_ACCESS_KEY_ID == None or AWS_SECRET_ACCESS_KEY == None or AWS_S3_REGION_NAME == None:
    logger.error("Missing aws configuration. Check your env variables for AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_REGION_NAME")
    sys.exit(1)

s3 = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_S3_REGION_NAME)

APP_PACKAGE_NAME="ru.meefik.linuxdeploy"
ANX_APP_FOLDER_PATH=f"/data/data/{APP_PACKAGE_NAME}"
ANX_APP_ROOT_FOLDER_PATH=f"{ANX_APP_FOLDER_PATH}/files"
# variables for cli
LINUX_DEPLOY=f"{ANX_APP_ROOT_FOLDER_PATH}/bin/linuxdeploy"

# variables for file system
PATH_TO_CONFIG_FILES=f"{ANX_APP_ROOT_FOLDER_PATH}/config/"

def download_file(url, filename):
    with alive.alive_bar() as bar:
        def progress(count, block_size, total_size):
            bar()
        request.urlretrieve(url, filename, progress)


def unzip_platform_tools():
    logger.info('Unzipping platform tools...')
    if PLATFORM == "windows":
        subprocess.run(['powershell.exe', '-Command',
                       'Expand-Archive -Path platform-tools.zip -DestinationPath .'])
    else:
        subprocess.run(['unzip', 'platform-tools.zip'])
    os.remove('platform-tools.zip')


def check_platform_tools():
    logger.info('Downloading platform tools...')
    if not os.path.exists('platform-tools'):
        download_file(PLATFORM_TOOLS_URL, 'platform-tools.zip')
        unzip_platform_tools()
    else:
        logger.info('Platform tools already exists, skipping.')

def adb_shell(cmd, *args):
    try:
        if PLATFORM == "windows":
            subprocess.run([f'{PLATFORM_TOOLS_PATH}\\adb.exe', "shell", cmd] + list(args))
        else:
            subprocess.run([f'{PLATFORM_TOOLS_PATH}/adb', "shell", cmd] + list(args))
        return True
    except Exception as e:
        logger.error(f"Error in executing adb command : {e}")
        return False

def adb(cmd, *args):
    try:
        if PLATFORM == "windows":
            subprocess.run([f'{PLATFORM_TOOLS_PATH}\\adb.exe', cmd] + list(args))
        else:
            subprocess.run([f'{PLATFORM_TOOLS_PATH}/adb', cmd] + list(args))
        return True
    except Exception as e:
        logger.error(f"Error in executing adb command : {e}")
        return False

def populate_and_select_file_systems():
    s3.download_file(
        Bucket=FLO_OS_SETUP_BUCKET_NAME,
        Key="manifest",
        Filename=f"{LOCAL_SETUP_DIR}/manifest")
    
    with open(f'{LOCAL_SETUP_DIR}/manifest') as f:
        versions = f.read()
        versions = versions.rstrip().split("\n")
    terminal_menu = TerminalMenu(
        menu_entries=versions,
        title="--- Available file systems ---", 
        skip_empty_entries=True)
    selected_version_index = terminal_menu.show()
    return versions[selected_version_index]

def download_ssh_setup():
    pass

def download_adb_setup():
    pass

def download_fs_config(file_system_name):
    logger.info(f"Downloading {file_system_name} config ...")
    file_name = f"{file_system_name}.conf"
    s3.download_file(
        Bucket=FLO_OS_SETUP_BUCKET_NAME,
        Key=file_name,
        Filename=f"{LOCAL_SETUP_DIR}/{file_name}")
    logger.info("Done.")

def download_file_system(file_system_name):
    file_system_name = f"{file_system_name}-rootfs.tar.gz"
    file_name = f"{LOCAL_SETUP_DIR}/{file_system_name}"
    setup_file = s3.get_object(
        Bucket=FLO_OS_SETUP_BUCKET_NAME,
        Key=file_system_name
    )
    total_size = setup_file["ContentLength"]
    logger.info(f'Downloading {file_system_name} ...')
    if os.path.isfile(file_name):
        logger.info('FS already downloaded, using cache.')
        return
    
    with alive.alive_bar(manual=True) as bar:
        global bytes_seen
        bytes_seen = 0

        def progress(bytes):
            # logger.info(f"Downloaded {bytes} bytes so far")
            global bytes_seen
            bytes_seen = bytes_seen + bytes
            percent = (bytes_seen / total_size)
            bar(percent)

        s3.download_file(
            Bucket=FLO_OS_SETUP_BUCKET_NAME,
            Key=file_system_name,
            Filename=file_name,
            Callback=progress)
    logger.info('Done.')

def push_config_file(file_system_name):
    file_name = f"{LOCAL_SETUP_DIR}/{file_system_name}.conf"
    adb_shell(f"mkdir {PATH_TO_CONFIG_FILES}")
    logger.info("Uploading config file ...")
    adb("push", file_name, f"{PATH_TO_CONFIG_FILES}/linux.conf")
    adb_shell(f"chown -R {get_owner_group()} {ANX_APP_ROOT_FOLDER_PATH}")
    logger.info("Done.")

def push_file_system(file_system_name):
    file_name = f"{LOCAL_SETUP_DIR}/{file_system_name}-rootfs.tar.gz"
    logger.info("Uploading file system ...")
    adb("push", file_name, "/sdcard")
    logger.info("Done.")

def setup_chroot_env():
    logger.info("Setting up chroot env ...")
    adb_shell(LINUX_DEPLOY, "deploy")
    logger.info("Done.")

def do_ssh_setup():
    adb("push", f"{LOCAL_SETUP_DIR}/{SSH_SETUP}.zip", "/")
    adb_shell("cd", "/")
    adb_shell("unzip", f"{SSH_SETUP}.zip")
    adb_shell("rm", f"{SSH_SETUP}.zip")
    adb_shell("cd", f"{SSH_SETUP}")

    adb_shell("mkdir /.ssh")
    adb_shell("mkdir -p /data/adb/service.d/")
    adb_shell("mv sshd_config /data/ssh/")
    adb_shell("mv ssh_host_rsa_key /data/ssh/")
    adb_shell("mv authorized_keys /.ssh/")
    adb_shell("chmod 600 /data/ssh/ssh_host_rsa_key")
    adb_shell("chmod 644 /.ssh/authorized_keys")
    adb_shell("chmod 660 /data/ssh/sshd_config")
    adb_shell("chmod 751 /.ssh/")
    adb_shell("chmod 755 /data/adb/service.d/")

def get_owner_group():
    if PLATFORM == "windows":
        ret = subprocess.run([f'{PLATFORM_TOOLS_PATH}\\adb.exe', "shell", f"ls -dl {ANX_APP_FOLDER_PATH}"+"| awk '{print $3}'"], capture_output=True)
    else:
        ret = subprocess.run([f'{PLATFORM_TOOLS_PATH}/adb', "shell", f"ls -dl {ANX_APP_FOLDER_PATH}"+"| awk '{print $3}'"], capture_output=True)
    owner = ret.stdout.decode().rstrip()
    return owner

def create_boot_up_script(ssh_setup, secure_adb):
    # create bootup.sh
    # push to /data/adb/service.d/
    # chmod 771 /data/adb/service.d/bootup.sh
    pass

def cleanup():
    if os.path.exists(LOCAL_SETUP_DIR):
        shutil.rmtree(LOCAL_SETUP_DIR)

@click.command()
@click.option('--network', '-n', default="", help="Use adb over wifi. Format is HOST:[PORT]")
@click.option('--file-system', '-f', is_flag=True, help='Updates file system to your Flo Edge')
@click.option('--ssh-setup', '-s', is_flag=True, help='sets up openssh-server on your Flo Edge ')
@click.option('--secure-adb', '-a', is_flag=True, help='sets up adb keys on your Flo Edge and secures it.')
@click.option('--clear-cache', '-c', is_flag=True, help='Clears setup directory')
@click.pass_context
def main(ctx, network, file_system, ssh_setup, secure_adb, clear_cache):
    """
    Prerequisities are :

    1. AWS User credentials.

    2. Access to flo os setup bundle

    3. Make sure AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_REGION_NAME env variables are added before running this script
    """
    if (not secure_adb and not ssh_setup and not file_system and not clear_cache):
        print(ctx.get_help())
        return

    if(clear_cache):
        logger.info("Clearing setup folder ...")
        cleanup()
        logger.info("Done.")
        return
    
    # Download platform tools
    check_platform_tools()

    if not os.path.exists(LOCAL_SETUP_DIR):
        os.mkdir(LOCAL_SETUP_DIR)
    
    # os.chdir(LOCAL_SETUP_DIR)
    # set adb to root
    adb("root")

    # remount : equivalent to mount -o rw,remount /
    adb("remount")

    # ensure app has storage permission granted
    adb_shell(f"pm grant {APP_PACKAGE_NAME} android.permission.WRITE_EXTERNAL_STORAGE")
    
    if(file_system):
        file_system = populate_and_select_file_systems()

        download_fs_config(file_system)
        # download_file_system(file_system)

        # 1. Push config File
        push_config_file(file_system)
        adb_shell(f"am start -n {APP_PACKAGE_NAME}/.activity.MainActivity")

        # 2. push file system
        push_file_system(file_system)

        # 3. Deploy the File system
        # 3.1 set profile to flo-linux
        # 3.2 run `$LINUX_DEPLOY deploy`
        setup_chroot_env()
        # 4. wait for installation to finish

    # 5. run adb ssh setup
    if(ssh_setup):
        do_ssh_setup()

    # 6. Copy adb keys
    if(secure_adb):
        logger.info("Uploading adb keys to device ...")
        adb_shell("cp adb_keys /data/misc/adb")
        logger.info("Done.")

    create_boot_up_script(ssh_setup, secure_adb)
    
    # Done with setup
    adb_shell("cd ..")
    
    # cleanup
    # ssh setup
    if(ssh_setup):
        adb_shell(f"rm -r {SSH_SETUP}")
    
    # adb setup
    if(secure_adb):
        adb_shell(f"rm -r {ADB_SETUP}")

    # set it back to read-only fs
    adb_shell("mount -o ro,remount /")

    # locks the system
    if(secure_adb):
        logger.info("Securing adb ...")
        adb_shell("setprop", "persist.adb.secure", "1")
        logger.info("Done.")

    logger.info("Flo Edge Setup complete!")
    logger.info("Rebooting in 5s...")
    time.sleep(5)
    adb("reboot")


if __name__ == "__main__":
    main()