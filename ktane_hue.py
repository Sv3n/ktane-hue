"""
File: ktane_hue.py
Purpose: Control hue lights from ktane
Author: Sven Goossens
"""
import time
import re
import datetime
from phue import Bridge

# A list with the light ids of the lamps the game should control
COLOR_LAMPS = ["light1", "light2"]

# The ip of the bridge
BRIDGE = '192.168.0.42'


def main():
    kt = Ktane()
    # We run from the ktane folder
    fname = 'logs/ktane.log'

    """The main event loop"""
    while True:
        # Parse the log, update state of Ktane class
        parse_wrap(fname, kt)
        # (light) animation tick
        kt.tick()
        # Go to sleep. This value determines the duration of each "frame" of the the light animation
        time.sleep(0.1)


class Ktane():
    """ Class that tracks the game state and controls the lights """
    def __init__(self):
        self.b = Bridge(BRIDGE)
        self.b.connect()

        self.round_started = False
        self.pulse = 0
        self.exploded = False
        self.strikes = 0
        self.won = False

        self.color_lamps = []
        for l in self.b.lights:
            if l.name in COLOR_LAMPS:
                self.menu_mode(l)
                self.color_lamps.append(l)
            else:
                l.brightness = 40

    def tick(self):
        """The function called by our main event loop"""
        if self.exploded:
            self.explode()
        elif self.round_started:
            self.do_pulse()

    def explode(self):
        """Explosion animation. Once done, it moves to the post_portem state"""
        if self.pulse == 1:
            self.normal_transitions()

        for lamp in self.color_lamps:
            if self.pulse == 0:
                lamp.brightness = 251
                self.color_red(lamp)
            elif self.pulse == 2:
                lamp.brightness = 251
                self.color_green(lamp)
            elif self.pulse == 4:
                lamp.brightness = 10
                self.color_red(lamp)

        self.pulse += 1
        if self.pulse == 50:
            self.round_started = False
            self.exploded = False
            self.pulse = 0
            self.post_mortem()

    def do_pulse(self):
        """
        Pulses the lights while the countdown timer is running.
        The pulse counts on which the state changes are chosen to be dividable
        1, 2, 3 and 4. Might glitch slightly when the number of strikes
        increases during the animation, but self corrects once self.pulse resets to 0.
        """
        div = 1 + max(self.strikes, 3)

        for lamp in self.color_lamps:
            if self.pulse == 0:
                self.color_mild_orange(lamp)
            elif self.pulse == 24 / div:
                self.color_orange(lamp)

        self.pulse += 1
        if self.pulse >= 48 / div:
            self.pulse = 0

    def menu_mode(self, lamp):
        """Lamp settings during the main menu / bomb selection"""
        lamp.on = True
        lamp.brightness = 200
        self.color_warm_white(lamp)

    def post_mortem(self):
        """Lamp settings during the post mortem debriefing"""
        print("post-mortem mode")
        for lamp in self.color_lamps:
            lamp.on = True
            lamp.brightness = 200
            self.color_cool_white(lamp)

    def quick_transitions(self):
        """Set lamps to quickest transition speed (fastest color change)"""
        for lamp in self.color_lamps:
            lamp.transitiontime = 0

    def normal_transitions(self):
        """Set lamps to normal transition mode."""
        for lamp in self.color_lamps:
            lamp.transitiontime = 10

    def half_transitions(self):
        for lamp in self.color_lamps:
            lamp.transitiontime = 5

    def quarter_transitions(self):
        for lamp in self.color_lamps:
            lamp.transitiontime = 2

    def state_update(self, state):
        """Called by the parser when it picks up a new log entry of interest"""
        if state == 'Enter GameplayState':
            if not self.round_started:
                self.start_round()

        if state == 'OnRoundEnd()' or state == 'Enter SetupState':
            if not self.exploded:
                self.stop_round()

        if state == 'Boom' and self.exploded is False:
            self.exploded = True
            print("exploded")
            self.quick_transitions()
            self.pulse = 0

        if state == "A winner is you!!":
            self.won = True

        if state == 'Results screen bomb binder dismissed (continue). Restarting...':
            self.stop_round()

        if "strike" in state:
            new_strikes = int(state[8])
            if new_strikes != self.strikes:
                print("Strike", new_strikes)
                self.strikes = new_strikes
                if self.strikes == 1:
                    self.half_transitions()
                if self.strikes == 2:
                    self.quarter_transitions()

    def start_round(self):
        """Reset state, start round"""
        print("Started round")
        self.normal_transitions()
        self.exploded = False
        self.won = False
        self.strikes = 0
        self.round_started = True

    def menu_mode_all(self):
        """Set all lamps to menu mode"""
        for lamp in self.color_lamps:
            self.menu_mode(lamp)

    def stop_round(self):
        """Stop round, back to menu mode"""
        print("Stopped round")
        self.round_started = False
        self.normal_transitions()
        self.menu_mode_all()

    def color_cool_white(self, l):
        l.hue = 35535
        l.saturation = 200

    def color_warm_white(self, l):
        l.hue = 30535
        l.saturation = 0

    def color_red(self, l):
        l.hue = 65535
        l.saturation = 254

    def color_magenta(self, l):
        l.hue = 55535
        l.saturation = 254

    def color_blue(self, l):
        l.hue = 47125
        l.saturation = 200

    def color_orange(self, l):
        l.hue = 13535
        l.saturation = 254

    def color_mild_orange(self, l):
        l.hue = 13535
        l.saturation = 100

    def color_green(self, l):
        l.hue = 25650
        l.saturation = 254

    def color_black(self, l):
        """Not exactly black"""
        l.hue = 47125
        l.saturation = 0


def parse_log(log, kt):
    """Parse log (list of lines). Pass useful state updates to kt."""
    log = list(log) # do we still need this?
    for line in log:
        if '[State]' in line or '[Bomb]' in line or '[PostGameState]' in line:
            # DEBUG 2015-12-24 18:57:49,884 [Assets.Scripts.Pacing.PaceMaker] Round start! Mission: The First Bomb Pacing Enabled: False

            r = r"[ ]*(?P<log_type>[A-Z]+) (?P<start_time>[^\[]*) \[(State|Bomb|PostGameState)\] (?P<state_info>.*)"
            m = re.match(r, line)
            res = m.groupdict()

            # Correct for local timezone (log contains UTC)
            local_tz = time.timezone
            t = datetime.datetime.strptime(res['start_time'], '%Y-%m-%d %H:%M:%S,%f')

            t = t - datetime.timedelta(seconds=local_tz)
            now = datetime.datetime.now()

            if abs(t - now) < datetime.timedelta(seconds=0.3):
                # A recent change: pass to kt
                print("State changed to {state}".format(state=res['state_info']))
                kt.state_update(res['state_info'])


def parse_wrap(fname, kt):
    """Small wrapper around the parse function"""
    with open(fname, 'r') as f:
        info = f.readlines()
        parse_log(info, kt)

if __name__ == '__main__':
    main()
