# ktane-hue
Control hue lights based on ktane (Keep Talking and Nobody Explodes) game state. See [my blog](http://svengoossens.nl/2015/12/25/ktane-hue/) for some more details.

## Requirements

 * Python 3
 * [Keep Talking and Nobody Explodes](http://www.keeptalkinggame.com/)
 * Some hue lights
 * [phue](https://github.com/studioimaginaire/phue)

## Setup
Copy the script to your ktane folder. Update the following sections to reflect your own setup:

```python
# A list with the light ids of the lamps the game should control
COLOR_LAMPS = ["light1", "light2"]

# The ip of the bridge
BRIDGE = '192.168.0.42'
```

You will have to push the button on the bridge once to allow the `b.connect` call to handshake with the bridge. Now run the script (`python3.exe ktane_hue.py` or something similar). After the inital run, the script can be run without pushing the button.

Now you can launch ktane, and the lights should be responding to the game.