#!/usr/bin/env python3

#
# Copyright (C) 2023 FloMobility Pvt. Ltd.
# All rights reserved.
#
# Confidential and Proprietary - FloMobility Pvt. Ltd.
# @author: Gagan Malvi <malvi@aospa.co>
# @author: Clay Motupalli <clay@flomobility.com>
#

VERSION="v0.1.0"

import os
import re
import sys
import subprocess
import platform
import time
import urllib.request as request
import shutil

import click
import boto3
import alive_progress as alive
from simple_term_menu import TerminalMenu

import logger


PLATFORM_TOOLS_VERSION = "r34.0.0"
PLATFORM = platform.uname().system.lower()
PLATFORM_TOOLS_URL = f"https://dl.google.com/android/repository/platform-tools_{PLATFORM_TOOLS_VERSION}-{PLATFORM}.zip"
PLATFORM_TOOLS_PATH=f"{os.getcwd()}/platform-tools"

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME")

FLO_OS_RELEASES_BUCKET_NAME = "flo-os-release-bundles"

if AWS_ACCESS_KEY_ID == None or AWS_SECRET_ACCESS_KEY == None or AWS_S3_REGION_NAME == None:
    logger.error("Missing aws configuration. Check your env variables for AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_REGION_NAME")
    sys.exit(1)

s3 = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_S3_REGION_NAME)

BUCKET_NAME = "flo-os-release-builds"

if PLATFORM == "windows":
    FASTBOOT = f"{PLATFORM_TOOLS_PATH}\\fastboot.exe"
    ADB = f"{PLATFORM_TOOLS_PATH}\\adb.exe"
else:
    FASTBOOT = f"{PLATFORM_TOOLS_PATH}/fastboot"
    ADB = f"{PLATFORM_TOOLS_PATH}/adb"

def fastboot(cmd, *args):
    return subprocess.run([FASTBOOT, cmd] + list(args))

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
        logger.info('Platform tools already exists, skipping...')


def populate_and_select_os_versions():
    if not os.path.exists("builds"):
        os.mkdir("builds")

    s3.download_file(
        Bucket=FLO_OS_RELEASES_BUCKET_NAME,
        Key="manifest",
        Filename="builds/manifest")
    with open('builds/manifest') as f:
        versions = f.read()
        versions = versions.rstrip().split("\n")
    terminal_menu = TerminalMenu(
        menu_entries=versions,
        title="Available versions of Flo OS")
    selected_version_index = terminal_menu.show()
    return versions[selected_version_index]


def check_for_local_build(version):
    file_name = f"{version}.zip"
    return os.path.isfile(f"builds/{file_name}")


def download_flo_build(version):
    file_name = f"{version}.zip"
    build_file_data = s3.get_object(
        Bucket=FLO_OS_RELEASES_BUCKET_NAME,
        Key=file_name
    )
    total_size = build_file_data["ContentLength"]
    logger.info(f'Downloading Flo OS : {version} ...')
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
            Bucket=FLO_OS_RELEASES_BUCKET_NAME,
            Key=file_name,
            Filename=f'builds/{file_name}',
            Callback=progress)
    logger.info(f'Done.')

def flash_partition(partition_name, img_file):
    return fastboot("flash", partition_name, img_file)

def flash_flo_build(file_name, wipe):
    """Flashes flo os build via fastboot

    Arguments:
        file_name -- a .zip file
        wipe -- flag to perform factory reset
    """

    # if wipe:
    #     factory_reset()
    dir_name = file_name.split(".zip")[0]
    dir_name = os.path.join(os.getcwd(), os.path.abspath(dir_name))
    file_name = os.path.abspath(file_name)
    # unzip file
    if PLATFORM == "windows":
        ret = subprocess.run(['powershell.exe', '-Command',
                       f'Expand-Archive -Path {file_name} -DestinationPath .\\{dir_name}'], capture_output=True)
    else:
        ret = subprocess.run(['unzip', file_name, f"-d{dir_name}"], capture_output=True)
    
    if ret.returncode != 0:
        logger.error(ret.stderr.decode())
        sys.exit(ret.returncode)

    image_file_pattern = re.compile(r"\w+\.img")
    # flash individual partitions
    for file in os.listdir(dir_name):
        if image_file_pattern.match(file):
            partition_name = file.split(".img")[0]
            logger.debug(f"{partition_name, os.path.join(dir_name, file)}")
            ret = flash_partition(partition_name, os.path.join(dir_name, file))
            if ret.returncode != 0:
                logger.error(f"Failed flashing {partition_name} : {ret.stderr.decode()}")


def adb_reboot_bootloader():
    logger.info('Rebooting into bootloader...')
    ret = subprocess.run([ADB, 'reboot', 'bootloader'])
    if ret.returncode != 0:
        logger.error(ret.stderr.decode())
        return
    logger.info("Done.")

def in_fastboot():
    try:
        ret = subprocess.run([FASTBOOT, "devices"], capture_output=True, timeout=3)
        return "fastboot" in ret.stdout.decode().rstrip().split("\t")
    except subprocess.TimeoutExpired:
        return False

def wait_for_fastboot_device():
    logger.info("Checking if device is in fastboot ...")
    if in_fastboot():
        logger.info("Device found in fastboot mode.")
        return True

    logger.warn("Couldn't find device in fastboot mode. Will try to reboot via adb.")
    # Check if the device is connected via ADB
    logger.info('Checking if the device is connected via ADB...')
    ret = subprocess.run([ADB, "get-state"], capture_output=True, timeout=5)

    if "device" not in ret.stdout.decode():
        logger.error(
            'Device not found in ADB mode.')
        logger.warn("Check if device is switched on.")
        return False
    
    # Reboot into bootloader
    adb_reboot_bootloader()

    # wait for fastboot
    logger.info("Waiting for device to boot into fastboot ...")
    counter = 0
    max_attempts = 10
    while counter < max_attempts:
        if in_fastboot():
            logger.info("Device found in fastboot mode.")
            return True
        time.sleep(1)
        counter += 1
    
    logger.error("Couldn't identify if device in fastboot mode.")
    logger.warn("Some troubleshooting steps :")
    logger.warn("1. Try reconnecting the device.")
    logger.warn("2. Use a USB hub between the device and the host computer.")
    logger.warn("3. Device could be faulty. <|-_-|>. Don't blame the software!!")
    return False

@click.command(name="factory_reset")
def factory_reset():
    """Performs a factory reset."""
    fastboot_ok = wait_for_fastboot_device()
    if not fastboot_ok:
        sys.exit(1)
    logger.info("Proceeding to perform a factory reset.")
    if PLATFORM == "windows":
        subprocess.run(['platform-tools\\fastboot.exe','-w'])
        subprocess.run(['platform-tools\\fastboot.exe','erase','system'])
        subprocess.run(['platform-tools\\fastboot.exe','erase','vendor'])
        subprocess.run(['platform-tools\\fastboot.exe','erase','boot'])
        subprocess.run(['platform-tools\\fastboot.exe','erase','recovery'])
    else:
        subprocess.run(['./platform-tools/fastboot', '-w'])
        subprocess.run(['./platform-tools/fastboot','erase', 'system'])
        subprocess.run(['./platform-tools/fastboot','erase', 'vendor'])
        subprocess.run(['./platform-tools/fastboot','erase', 'boot'])
        subprocess.run(['./platform-tools/fastboot','erase', 'recovery'])
    logger.info("Factory reset done!")

@click.command(name="clean")
def cleanup():
    """Clears builds directory"""
    if os.path.exists("builds"):
        shutil.rmtree("builds")

@click.command(name="local")
@click.argument("os_zip_file")
@click.option('--wipe', is_flag=True, help='Performs a factory reset.')
def flash_local(wipe, os_zip_file):
    """Flash a local version of Flo OS.
    
    Pass the path to the zip file containing all partitions as an argument.

    The zip file must contain all partition image files (.img) with the filename as the partition name.

    """
    fastboot_ok = wait_for_fastboot_device()
    if not fastboot_ok:
        sys.exit(1)
    
    flash_flo_build(os_zip_file, wipe)
    

@click.command(name="remote")
@click.option('--wipe', is_flag=True, help='Performs a factory reset.')
def flash_remote(wipe):
    """Download and flash a version of Flo OS"""

    # Download platform tools
    check_platform_tools()

    # populate versions
    # show available versions
    version = populate_and_select_os_versions()

    # Download Flo build
    if not check_for_local_build(version):
        download_flo_build(version)

    fastboot_ok = wait_for_fastboot_device()
    if not fastboot_ok:
        sys.exit(1)
    
    # Flash Flo build via fastboot
    file_name = f"builds/{version}.zip"
    flash_flo_build(file_name, wipe)

@click.group()
def cli():
    """Flo OS flash utility (v0.1.0)
    
    Important points:

    1. To download and flash flo OS builds, make sure you have :

    - AWS bucket access
    
    - AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_REGION_NAME env variables sourced

    2. For local builds, the zip file must contain all partition image files (.img) with the filename as the partition name.

    3. If you're using a beryllium (Xiaomi Poco F1) device, USB 2.0 port might cause a problem, be sure to use a USB Hub.
    """

cli.add_command(flash_remote)
cli.add_command(flash_local)
cli.add_command(factory_reset)
cli.add_command(cleanup)

if __name__ == '__main__':
    cli()