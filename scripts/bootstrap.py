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
from utils import AdbException

VERSION = "v0.1.0"

SCRIPT_DIR=os.path.abspath(os.path.dirname(__file__))
STUB_SCRIPTS_DIR=""
if os.path.islink(__file__):
    STUB_SCRIPTS_DIR=f"{SCRIPT_DIR}/scripts/stub"
else:
    STUB_SCRIPTS_DIR=f"{SCRIPT_DIR}/stub"

PLATFORM_TOOLS_VERSION = "r34.0.0"
PLATFORM = platform.uname().system.lower()
PLATFORM_TOOLS_URL = f"https://dl.google.com/android/repository/platform-tools_{PLATFORM_TOOLS_VERSION}-{PLATFORM}.zip"
PLATFORM_TOOLS_PATH=f"{os.getcwd()}/platform-tools"

if PLATFORM == "windows":
    ADB = f"{PLATFORM_TOOLS_PATH}\\adb.exe"
else:
    ADB = f"{PLATFORM_TOOLS_PATH}/adb"

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME")

FLO_OS_SETUP_BUCKET_NAME = "flo-os-setup"

LOCAL_SETUP_DIR = f"{SCRIPT_DIR}/setup"
SSH_SETUP = "ssh_setup"
ADB_SETUP = "adb_keys"

if AWS_ACCESS_KEY_ID == None or AWS_SECRET_ACCESS_KEY == None or AWS_S3_REGION_NAME == None:
    logger.error("Missing aws configuration. Check your env variables for AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_REGION_NAME")
    sys.exit(1)
s3 = None

MAGISK = "magisk"
ANX = "anx"
APP_NAME = "com.flomobility.anx"
APP_PACKAGE_NAME=f"{APP_NAME}.headless"
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
        ret = subprocess.run([ADB, "shell", cmd] + list(args), stderr=subprocess.PIPE)
        if ret.returncode == 0:
            return True
        else:
            raise AdbException(error_code=ret.returncode, message=ret.stderr.decode().rstrip())
    except Exception as e:
        logger.error(f"Error in executing adb command : {e.message}")
        logger.error(f"Exiting with code - {e.error_code}")
        exit(e.error_code)

def adb(cmd, *args):
    try:
        ret = subprocess.run([ADB, cmd] + list(args), stderr=subprocess.PIPE)
        if ret.returncode == 0:
            return True
        else:
            raise AdbException(error_code=ret.returncode, message=ret.stderr.decode().rstrip())
    except AdbException as e:
        logger.error(f"Error in executing adb command : {e.message}")
        logger.error(f"Exiting with code - {e.error_code}")
        exit(e.error_code)

def check_aws_credentials():
    if AWS_ACCESS_KEY_ID == None or AWS_SECRET_ACCESS_KEY == None or AWS_S3_REGION_NAME == None:
        logger.error(
            "Missing aws configuration. Check your env variables for AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_REGION_NAME")
        sys.exit(1)

def download_magisk_apk():
    file_name = f"{MAGISK}.apk"
    logger.info("Downloading Magisk ...")
    local_magisk = f"{LOCAL_SETUP_DIR}/{file_name}"
    if os.path.isfile(local_magisk):
        logger.info("Using cache.")
        return
    s3.download_file(
        Bucket=FLO_OS_SETUP_BUCKET_NAME,
        Key=file_name,
        Filename=local_magisk)
    logger.info("Done.")

def install_magisk():
    logger.info("Installing Magisk ...")
    file_name = f"{MAGISK}.apk"
    adb("install", f"{LOCAL_SETUP_DIR}/{file_name}")
    logger.info("Done.")

def download_anx_apk():
    file_name = f"{ANX}.apk"
    logger.info("Downloading anx ...")
    local_anx = f"{LOCAL_SETUP_DIR}/{file_name}"
    if os.path.isfile(local_anx):
        logger.info("Using cache.")
        return
    s3.download_file(
        Bucket=FLO_OS_SETUP_BUCKET_NAME,
        Key=file_name,
        Filename=local_anx)
    logger.info("Done.")

def install_anx():
    logger.info("Installing anx app  ...")
    file_name = f"{ANX}.apk"
    adb("install", f"{LOCAL_SETUP_DIR}/{file_name}")
    logger.info("Done.")

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
    logger.info(f"Downloading ssh setup files ...")
    file_name = f"{SSH_SETUP}.zip"
    s3.download_file(
        Bucket=FLO_OS_SETUP_BUCKET_NAME,
        Key=file_name,
        Filename=f"{LOCAL_SETUP_DIR}/{file_name}")
    logger.info("Done.")

def download_adb_setup():
    logger.info(f"Downloading adb setup files ...")
    file_name = f"{ADB_SETUP}.zip"
    s3.download_file(
        Bucket=FLO_OS_SETUP_BUCKET_NAME,
        Key=file_name,
        Filename=f"{LOCAL_SETUP_DIR}/{file_name}")
    logger.info("Done.")

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

def push_config_file(file_name):
    adb_shell(f"mkdir -p {PATH_TO_CONFIG_FILES}")
    logger.info("Uploading config file ...")
    adb("push", file_name, f"{PATH_TO_CONFIG_FILES}/linux.conf")
    adb_shell(f"chown -R {get_owner_group()} {ANX_APP_ROOT_FOLDER_PATH}")
    logger.info("Done.")

def push_file_system(file_name):
    logger.info("Uploading file system ...")
    adb("push", file_name, "/sdcard/flo-linux-rootfs.tar.gz")
    logger.info("Done.")

def setup_chroot_env():
    logger.info("Setting up chroot env ...")
    adb_shell(LINUX_DEPLOY, "umount")
    time.sleep(2)
    adb_shell(LINUX_DEPLOY, "deploy")
    logger.info("Done.")

def do_ssh_setup():
    adb("push", f"{LOCAL_SETUP_DIR}/{SSH_SETUP}.zip", "/")
    adb_shell("unzip", f"{SSH_SETUP}.zip")
    adb_shell("rm", f"{SSH_SETUP}.zip")

    adb_shell("mkdir -p /.ssh")
    adb_shell(f"mv {SSH_SETUP}/sshd_config /data/ssh/")
    adb_shell(f"mv {SSH_SETUP}/ssh_host_rsa_key /data/ssh/")
    adb_shell(f"mv {SSH_SETUP}/authorized_keys /.ssh/")
    adb_shell("chmod 600 /data/ssh/ssh_host_rsa_key")
    adb_shell("chmod 644 /.ssh/authorized_keys")
    adb_shell("chmod 660 /data/ssh/sshd_config")
    adb_shell("chmod 751 /.ssh/")

    adb_shell(f"rm -r {SSH_SETUP}")

def do_adb_setup():
    logger.info("Uploading adb keys to device ...")
    adb("push", f"{LOCAL_SETUP_DIR}/{ADB_SETUP}.zip", "/")
    adb_shell("unzip", f"{ADB_SETUP}.zip")
    adb_shell("rm", f"{ADB_SETUP}.zip")

    adb_shell(f"mv adb_keys /data/misc/adb")
    logger.info("Done.")

def get_owner_group():
    ret = subprocess.run([ADB, "shell", f"ls -dl {ANX_APP_FOLDER_PATH}"+"| awk '{print $3}'"], capture_output=True)
    owner = ret.stdout.decode().rstrip()
    return owner

def create_boot_up_script(ssh_setup):
    # create bootup.sh
    with open(f"{LOCAL_SETUP_DIR}/flo_edge_bootup.rc", "w") as script:
        script.write('service flo_edge_bootup /system/bin/bootup.sh\n')
        script.write('\tdisabled\n')
        script.write('\toneshot\n')
        script.write('\tseclabel u:r:magisk:s0\n')
        script.write("on property:sys.boot_completed=1\n")
        script.write("\tstart flo_edge_bootup")

    with open(f"{LOCAL_SETUP_DIR}/bootup.sh", "w") as script:
        # open .script file and copy the text
        with open(f"{STUB_SCRIPTS_DIR}/bootup.sh.script", "r") as script_stub:
            script_text = script_stub.read()
            script_text = script_text.replace("{LINUX_DEPLOY}", LINUX_DEPLOY)
            script.write(script_text)
    
    with open(f"{LOCAL_SETUP_DIR}/server.sh", "w") as script:
        # open .script file and copy the text
        with open(f"{STUB_SCRIPTS_DIR}/server.sh.script", "r") as script_stub:
            script_text = script_stub.read()
            script.write(script_text)

    adb("push", f"{LOCAL_SETUP_DIR}/flo_edge_bootup.rc", "/etc/init")
    adb("push", f"{LOCAL_SETUP_DIR}/bootup.sh", "/bin/")
    adb("push", f"{LOCAL_SETUP_DIR}/server.sh", "/bin/")
    adb_shell("chmod 644 /etc/init/flo_edge_bootup.rc")
    adb_shell("chown 0.0 /etc/init/flo_edge_bootup.rc")
    adb_shell("chmod 755 /bin/bootup.sh")
    adb_shell("chown 0.0 /bin/bootup.sh")
    adb_shell("chmod 755 /bin/server.sh")
    adb_shell("chown 0.0 /bin/server.sh")
    
def rm_su_if_present():
    ret = subprocess.run([ADB, "shell", "test -f /system/xbin/su"], capture_output=True)
        
    if ret.returncode !=0:
        logger.info("Found /system/xbin/su. Proceeding to delete...")
        adb_shell("rm /system/xbin/su")
        logger.info("Done.")

def cleanup():
    if os.path.exists(LOCAL_SETUP_DIR):
        shutil.rmtree(LOCAL_SETUP_DIR)

def exit(return_code):
    s3.close()
    sys.exit(return_code)

def pre_setup():

    check_aws_credentials()

    global s3
    s3 = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_S3_REGION_NAME)

    # Download platform tools
    check_platform_tools()

    if not os.path.exists(LOCAL_SETUP_DIR):
        os.mkdir(LOCAL_SETUP_DIR)

    # os.chdir(LOCAL_SETUP_DIR)
    # set adb to root
    adb("root")

    # remount : equivalent to mount -o rw,remount /
    adb("remount")

    # Download and install magisk
    download_magisk_apk()
    install_magisk()

    # Download and install anx app
    download_anx_apk()
    install_anx()

    # ensure app has storage permission granted
    adb_shell(f"pm grant {APP_PACKAGE_NAME} android.permission.WRITE_EXTERNAL_STORAGE")

    # disable lock screen
    adb_shell("locksettings set-disabled true")


@click.command(name="local")
@click.argument('filesystem_path')
@click.argument('filesystem_config_path')
def local_setup(filesystem_path, filesystem_config_path):
    """
    Local boostrap setup of file system

    Pass 2 arguments:

    1. Path to the file system - a .tar.gz file

    2. Path to file system config - a .conf file
    """
    pre_setup()

    # 1. Push config File
    push_config_file(filesystem_config_path)
    adb_shell(f"am start -n {APP_PACKAGE_NAME}/{APP_NAME}.activity.MainActivity")

    # 2. push file system
    push_file_system(filesystem_path)

    # 3. Deploy the File system
    # 3.1 set profile to flo-linux
    # 3.2 run `$LINUX_DEPLOY deploy`
    setup_chroot_env()

    logger.info("Flo Edge Setup complete!")
    logger.info("Rebooting in 5s...")
    time.sleep(5)
    adb("reboot")

@click.command(name="clean")
def clean():
    """Clears setup directory"""
    logger.info("Clearing setup folder ...")
    cleanup()
    logger.info("Done.")
    return

@click.command(name="remote")
@click.option('--setup-fs', '-f', is_flag=True, help='Download a file system upload it to your Flo Edge')
@click.option('--setup-ssh', '-s', is_flag=True, help='Sets up openssh-server on your Flo Edge ')
@click.option('--secure-adb', '-a', is_flag=True, help='Sets up adb keys on your Flo Edge and secures it.')
def remote_setup(setup_fs, setup_ssh, secure_adb):
    """
    Download and setup a file system.

    To download and setup file systems, make sure you have :

    - AWS bucket access

    - AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_REGION_NAME env variables sourced
    """

    # flags default to false when not set
    if not setup_fs and not setup_ssh and not secure_adb:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        sys.exit(0)
    
    pre_setup()
    
    if setup_fs:
        file_system_name = populate_and_select_file_systems()

        download_fs_config(file_system_name)
        download_file_system(file_system_name)

        # 1. Push config File
        config_file = f"{LOCAL_SETUP_DIR}/{file_system_name}.conf"
        push_config_file(config_file)
        adb_shell(f"am start -n {APP_PACKAGE_NAME}/{APP_NAME}.activity.MainActivity")

        # 2. push file system
        file_system_file = f"{LOCAL_SETUP_DIR}/{file_system_name}-rootfs.tar.gz"
        push_file_system(file_system_file)

        # 3. Deploy the File system
        # 3.1 set profile to flo-linux
        # 3.2 run `$LINUX_DEPLOY deploy`
        setup_chroot_env()
        # 4. wait for installation to finish

    # 5. run adb ssh setup
    if setup_ssh:
        download_ssh_setup()
        do_ssh_setup()

    # 6. Copy adb keys
    if(secure_adb):
        download_adb_setup()
        do_adb_setup()

    create_boot_up_script(setup_ssh)

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

@click.group()
@click.version_option(version="", message=f"Flo OS bootstrap utility : {VERSION}")
def cli():
    """
    Flo OS bootstrap utility

    Important points:

    This script assumes only a single device is connected to the host PC.

    1. To download and setup file systems, make sure you have :

    - AWS bucket access

    - AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_REGION_NAME env variables sourced

    2. For local based file system setup, the file system must be a .tar.gz file.

    3. To setup ssh and secure_adb, as of now it's only possible with remote
    """
    pass

cli.add_command(remote_setup)
cli.add_command(local_setup)
cli.add_command(clean)

if __name__ == "__main__":
    cli()
