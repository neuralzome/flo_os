# Flo OS
> Android based OS forked from Lineage 17
## Supported Devices
1. **beryllium** (a.k.a Xiaomi Poco F1)

## Setting up a new device
> This assumes the device is unlocked. Check [here](#unlock-phone) for more info.
### Pre-requisities
- Install Python 3.7+ on your PC
- Be sure to run
   ```bash
   pip install -r scripts/requirements.txt
   ```
### Tools
1. Flash utility
   ```bash
   ./flash remote -wr 
   ```
2. Bootstrap

   ```bash
   ./bootstrap remote -fsa 
   ```

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
   (If incase it doesn't appear, follow [installation of drivers](#install-adb-drivers-for-beryllium-on-windows))
9. After the bootloader successfully unlocks, reboot the phone
10. You should see an unlocked lock symbol on the top center of the screen.

## Install ADB Drivers for Beryllium on Windows
> When in fastboot mode, sometimes the device is not recognized by the system.
> In this case you need to add the respective usb_drivers for the same.
> This assumes your device is in fastboot mode and connected to your PC
1. Open device manager
2. You'll see an unknown android device
3. Right click on it and click update driver
4. Browse for drivers and select install from a location on PC
5. Click then on have driver and then browse to the path of `usb_drivers` in this repo.
6. Select `android_winusb` and click okay then yes
7. You don't have to restart PC after this.
8. Verify via `fastboot devices` if your device is recognized.
