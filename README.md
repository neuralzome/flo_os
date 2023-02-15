# Flo OS
> Android based OS forked from Lineage 17
## Supported Devices
1. **beryllium** (a.k.a Xiaomi Poco F1)

## Installation
> This assumes the device is unlocked. Check [here](#unlock-phone) for more info.
### Prerequisites
1. Install [android platform tools](https://developer.android.com/studio/releases/platform-tools#downloads). 
2. Download the latest OS image from the [releases page](https://github.com/flomobility/flo_os/releases/latest)

### Add recovery
1. Ensure the phone is switched off
2. Press and hold **Volume Down + Power button** for 3-5 seconds. This boots the phone into fastboot mode.
3. Open your terminal and type `fastboot devices`. The device would appear in the list
4. Now cd into the device workspace `cd ./xiaomi/devices/<device codename>`
5. Execute the following command `fastboot flash recovery lineage-17.1-recovery-<device codename>.img`
6. Press and hold **Volume Up + Power button** for 3-5 seconds. This boots the phone into recovery mode.

### Flash System partition
1. From the menu, select the `Factory Reset` option
2. Select the `Format data/partition reset` option and then `Format Data`
3. Once the format is complete, proceed back to the main menu
4. Select the `Apply Update` option and then `Apply from ADB`
5. Verify if sideload is active by `adb devices`. Sideload would be listed
6. Now execute `adb sideload flo-os-<latest release name>-<device codename>.zip`
7. After the installation is done, execute `adb sideload Magisk-v24.1.zip`
8. Once this is done. Proceed back to main menu
9. Reboot system now

### Final touches
1. Once you boot into the system partition
2. Skip all setup steps
3. Anx app would start and download the file system.
4. Meanwhile open Magisk app and install it. It would prompt to reboot, but wait.
5. Reboot system after anx app completes installation.
   
## Unlock Phone
> Currently this process is only supported on windows laptops
1. Create and login with an MI account on the phone (You'd need a phone number for this step)
2. Extract the contents of Mi Flash-Unlock and open batch_unlock
3. Enable the Developer Option in your mobile by clicking on the MiUi version in the About Phone 8 times.
   You'd then see a message say "You're already a developer".
4. Go in the Developer Options menu and turn on OEM Unlocking and USB Debugging
5. Now, click on Mi Unlock status and login with the same Mi Account
6. Connect your phone with your laptop and open cmd
7. After connecting type the command `adb reboot fastboot`, the phone will reboot to Fastboot mode.
8. Then in the Mi Flash Unlock tool, after pressing F5 you will see your device listed, then press F6 to start unlocking the bootloader.
9. After the bootloader successfully unlocks, reboot the phone
10. You should see an unlocked lock symbol on the top center of the screen.

