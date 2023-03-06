#!/usr/bin/env python3

#
# Copyright (C) 2023 FloMobility Pvt. Ltd.
# All rights reserved.
#
# Confidential and Proprietary - FloMobility Pvt. Ltd.
# @author: Gagan Malvi <malvi@aospa.co>
# @author: Clay Motupalli <clay@flomobility.com>
#

import os
import sys
import subprocess
import platform
import urllib.request as request

import click
import boto3
import alive_progress as alive
from simple_term_menu import TerminalMenu

import logger

VERSION = "r34.0.0"
PLATFORM = platform.uname().system.lower()
PLATFORM_TOOLS_URL = f"https://dl.google.com/android/repository/platform-tools_{VERSION}-{PLATFORM}.zip"

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME")

FLO_OS_RELEASES_BUCKET_NAME = "flo-os-release-bundles"

if AWS_ACCESS_KEY_ID == None or AWS_SECRET_ACCESS_KEY == None or AWS_S3_REGION_NAME == None:
    print("Missing aws configuration. Check your env variables for AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_REGION_NAME")
    sys.exit(1)

s3 = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_S3_REGION_NAME)

BUCKET_NAME = "flo-os-release-builds"


def download_file(url, filename):
    with alive.alive_bar() as bar:
        def progress(count, block_size, total_size):
            bar()
        request.urlretrieve(url, filename, progress)


def unzip_platform_tools():
    print('Unzipping platform tools...')
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
        versions = versions.split("\n")
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
            # print(f"Downloaded {bytes} bytes so far")
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


def flash_flo_build(version, wipe):
    if wipe:
        logger.info("Proceeding to perform a factory reset.")
        if PLATFORM == "windows":
            subprocess.run(['platform-tools\\fastboot.exe',
                            '-w'])
        else:
            subprocess.run(['./platform-tools/fastboot', '-w'])
        logger.info("Factory reset done!")

    file_name = f"builds/{version}.zip"
    logger.info('Flashing Flo build via fastboot...')
    if PLATFORM == "windows":
        subprocess.run(['platform-tools\\fastboot.exe',
                       'update', file_name])
    else:
        subprocess.run(['./platform-tools/fastboot', 'update', file_name])
    logger.info("Done flashing!")


def adb_reboot_bootloader():
    print('Rebooting into bootloader...')
    if PLATFORM == "windows":
        subprocess.run(['platform-tools\\adb.exe', 'reboot', 'bootloader'])
    else:
        subprocess.run(['./platform-tools/adb', 'reboot', 'bootloader'])


@click.command()
@click.option('--wipe', is_flag=True, help='Performs a factory reset.')
def main(wipe):
    """
    Prerequisities are :

    1. AWS User credentials.

    2. Access to flo release bundles s3 bucket

    3. Make sure AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_REGION_NAME env variables are added before running this script
    """

    # Download platform tools
    check_platform_tools()

    # populate versions
    # show available versions
    version = populate_and_select_os_versions()

    # Download Flo build
    if not check_for_local_build(version):
        download_flo_build(version)

    if PLATFORM == "windows":
        ret = subprocess.run(
            ['platform-tools\\fastboot.exe', 'devices'], capture_output=True)
    else:
        ret = subprocess.run(
            ['./platform-tools/fastboot', "devices"], capture_output=True)

    in_fastboot = False
    if "fastboot" in ret.stdout.decode().rstrip().split("\t"):
        in_fastboot = True

    # Check if the device is connected via ADB
    logger.info('Checking if the device is connected via ADB...')
    if PLATFORM == "windows":
        ret = subprocess.run(
            ['platform-tools\\adb.exe', 'devices'], capture_output=True)
    else:
        ret = subprocess.run(
            ['./platform-tools/adb', "get-state"], capture_output=True)

    if not in_fastboot:
        if "device" not in ret.stdout.decode():
            logger.error(
                'Device not found in ADB mode, please connect the device in ADB mode with the bootloader unlocked.')
            exit(1)
        else:
            # Reboot into bootloader
            adb_reboot_bootloader()

    # Flash Flo build via fastboot
    flash_flo_build(version, wipe)


if __name__ == '__main__':
    main()
