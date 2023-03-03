#
# Copyright (C) 2023 FloMobility Pvt. Ltd.
# All rights reserved.
#
# Confidential and Proprietary - FloMobility Pvt. Ltd.
# @author: Gagan Malvi <malvi@aospa.co>
#

import os
import subprocess
import urllib.request as request
import alive_progress as alive

PLATFORM_TOOLS_WINDOWS_URL = 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip'
PLATFORM_TOOLS_LINUX_URL = 'https://dl.google.com/android/repository/platform-tools-latest-linux.zip'

# Always make sure that the build name, version and release URL are correct
# This script supports flashing of only update packages

IS_RECOVERY = True

FLO_BUILD_NAME = 'flo-os-inception-beryllium.zip' if IS_RECOVERY else 'flo-os-inception-beryllium-img.zip'
FLO_CURRENT_VERSION = '1.1.15'
# FLO_RELEASE_BUILD_URL = 'https://github.com/flomobility/flo_os/releases/download/v{}/{}'.format(FLO_CURRENT_VERSION, FLO_BUILD_NAME)
FLO_RELEASE_BUILD_URL = 'https://objects.githubusercontent.com/github-production-release-asset-2e65be/577643700/ecf576bd-d121-408f-92c9-99261c76b036?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAIWNJYAX4CSVEH53A%2F20230217%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20230217T154114Z&X-Amz-Expires=300&X-Amz-Signature=1d5c8c893eb37aeb6d46ffee7fcc642a5ed4bcbd870b1b62f864ef9c9aa817f0&X-Amz-SignedHeaders=host&actor_id=26477157&key_id=0&repo_id=577643700&response-content-disposition=attachment%3B%20filename%3Dflo-os-inception-beryllium.zip&response-content-type=application%2Foctet-stream'

def download_file(url, filename):
    with alive.alive_bar(spinner = 'dots_waves2') as bar:
        def progress(count, block_size, total_size):
            bar()
        request.urlretrieve(url, filename, progress)

def unzip_platform_tools():
    print('[-] Unzipping platform tools...')
    if os.name == 'nt':
        subprocess.run(['powershell.exe', '-Command', 'Expand-Archive -Path platform-tools.zip -DestinationPath .'])
    else:
        subprocess.run(['unzip', 'platform-tools.zip'])
    os.remove('platform-tools.zip')

def download_platform_tools():
    print('[-] Downloading platform tools...')
    if not os.path.exists('platform-tools'):
        if os.name == 'nt':
            download_file(PLATFORM_TOOLS_WINDOWS_URL, 'platform-tools.zip')
        else:
            download_file(PLATFORM_TOOLS_LINUX_URL, 'platform-tools.zip')
        unzip_platform_tools()
    else:
        print('[-] Platform tools already exists, skipping...')

def download_flo_build():
    print('[-] Downloading Flo build...')
    download_file(FLO_RELEASE_BUILD_URL, FLO_BUILD_NAME)

def flash_flo_build():
    print('[-] Flashing Flo build via fastboot...')
    if os.name == 'nt':
        subprocess.run(['platform-tools\\fastboot.exe', 'update', FLO_BUILD_NAME])
    else:
        subprocess.run(['./platform-tools/fastboot', 'update', FLO_BUILD_NAME])

def adb_reboot_bootloader():
    print('[-] Rebooting into bootloader...')
    if os.name == 'nt':
        subprocess.run(['platform-tools\\adb.exe', 'reboot', 'bootloader'])
    else:
        subprocess.run(['./platform-tools/adb', 'reboot', 'bootloader'])

def flash_flo_build_via_adb_sideload():
    print('[-] Flashing FloOS over ADB sideload...')
    if os.name == 'nt':
        subprocess.run(['platform-tools\\adb.exe', 'sideload', FLO_BUILD_NAME])
    else:
        subprocess.run(['./platform-tools/adb', 'sideload', FLO_BUILD_NAME])

def push_device_to_sideload():
    print('[-] Pushing device to sideload...')
    if os.name == 'nt':
        subprocess.run(['platform-tools\\adb.exe', 'reboot', 'sideload-auto-reboot'])
    else:
        subprocess.run(['./platform-tools/adb', 'reboot', 'sideload-auto-reboot'])

#
# Please connect your device either in Fastboot mode,
# or in ADB mode with the bootloader unlocked.
#

if __name__ == '__main__':
    # Download platform tools
    download_platform_tools()

    # Download Flo build
    download_flo_build()

    if IS_RECOVERY:
        # Flash Flo build via sideload
        push_device_to_sideload()
        flash_flo_build_via_adb_sideload()
    else:
        # Check if the device is connected via ADB
        print('[-] Checking if the device is connected via ADB...')
        if os.name == 'nt':
            ret = subprocess.run(['platform-tools\\adb.exe', 'devices'], capture_output = True)
        else:
            ret = subprocess.run(['./platform-tools/adb', 'devices'], capture_output = True)
        if 'device' not in ret.stdout.decode('utf-8'):
            print('[-] Device not found in ADB mode, please connect the device in ADB mode with the bootloader unlocked.')
            exit(1)
        
        # Reboot into bootloader
        adb_reboot_bootloader()

        # Flash Flo build via fastboot
        flash_flo_build()
