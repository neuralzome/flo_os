# Flo OS
> Android based OS forked from Lineage 17 for beryllium devices (a.k.a Poco F1)

## Installation
> This assumes the device is unlocked. Check [here](#unlock-phone) for more info.
### Prerequisites
1. Install [android platform tools](https://developer.android.com/studio/releases/platform-tools#downloads). 
2. Download the latest OS image from the [releases page](https://github.com/flomobility/flo_os/releases)
   
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

