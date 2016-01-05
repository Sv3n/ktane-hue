# ktane-hue
Control hue lights based on ktane (Keep Talking and Nobody Explodes) game state. See [my blog](http://svengoossens.nl/2015/12/25/ktane-hue/) for some more details.

# Features / detected events

 * Dims all non-color lights that were switched on
 * In the menu, sets all color lights to a yellowy-white tone
 * In game, color lights pulse between red-orange and orange when you have 0 or 1 strike
 * In game, color lights pulse between red-pink and orange when you have 2 or more strikes, or there is less than 1 minute left
 * For each strike, the pulse frequency increases
 * When the bomb explodes, lights flash in satisfying pallet of yellow / green and red, and then dim down to a low intensity red
 * In the post-mortem screen (where you can see the reason you exploded), lights get a hard-white color

## Requirements

 * Python 3
 * [Keep Talking and Nobody Explodes](http://www.keeptalkinggame.com/)
 * Some hue lights
 * [phue](https://github.com/studioimaginaire/phue)

## Setup
Copy the script to your ktane folder. The script has one mandatory, and one optional command line argument:

```bash
D:\SteamLibrary\steamapps\common\Keep Talking and Nobody Explodes> python.exe .\ktane_hue.py --help
usage: ktane_hue.py [-h] --bridge BRIDGE_IP [--explode]

ktane_hue

optional arguments:
  -h, --help          show this help message and exit
  --bridge BRIDGE_IP  Set the bridge ip
  --explode           Test the explosion animation
```

Run the script with the `--bridge` parameter pointing to the ip of your hue bridge. (`python.exe ktane_hue.py --bridge 192.168.0.12` or something similar).

You will have to push the button on the bridge once to allow the `b.connect` call to handshake with the bridge.  After the inital run, the script can be run without pushing the button.

Now you can launch ktane, and the lights should be responding to the game.
