### Basic usage

1) Upload 'main.py' to the root of your micropython-flashed ESP32
2) Reset the ESP32 to generate the config file
3) Modify the 'config.json' file on the ESP32 to provide the name and password of your local WIFI network.
4) Reset the ESP32 again and view the serial console for IP information.
5) Visit the IP address of the ESP32 on a local web browser:
    IE: http://123.123.123.45

You should see the auto-generated home page (index.html) which now resides under your /files directory on the ESP32. You may then navigate to the file management portion of the program via the "Edit Files" link where you may manage your files.
