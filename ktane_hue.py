"""
File: ktane_hue.py
Purpose: Control hue lights from ktane
Author: Sven Goossens
"""
import argparse
import datetime
from enum import Enum, IntEnum
import json
import logging
import os
import re
import sys
import time
from phue import Bridge

logger = None

SETTINGS = 'ktane_hue.json'

def parse_arguments():
    parser = argparse.ArgumentParser(description='ktane_hue')
    parser.add_argument('--bridge', dest='bridge_ip', type=str, required=True, help='Set the bridge ip')
    parser.add_argument('--explode', dest='explode', required=False, default=False, action='store_const', const=True, help='Test the explosion animation')
    return parser.parse_args()


def main():
    setup_logger()
    args = parse_arguments()
    if not os.path.exists(SETTINGS):
        pass
    kt = Ktane(args.bridge_ip)
    if len(kt.color_lamps) == 0:
        logger.error("No color lamps found. Exiting....")

    # We run from the ktane folder
    lp = KtaneLogParse('logs/ktane.log')

    if args.explode:
        kt.action(KtaneAction.round_started)
        kt.action(KtaneAction.explode)
        # Assumes explode animation < 100 ticks
        for _ in range(0, 100):
            kt.tick()
            time.sleep(0.1)
        return

    # Parse the log (but don't update lights).
    # This recovers the state when the script is restarted.
    kt.fast_forward(True)
    lp.parse_wrap(kt)
    kt.fast_forward(False)

    """The main event loop"""
    while True:
        # Parse the log, update state of Ktane class
        lp.parse_wrap(kt)
        # (light) animation tick
        kt.tick()
        # Go to sleep. This value determines the duration of each "frame" of the the light animation
        time.sleep(0.1)


class KtaneState(Enum):
    in_menu = 0
    in_game = 1
    exploding = 2
    post_mortem = 3
    in_game_quick = 4


class KtaneAction(IntEnum):
    menu_opened = 0
    round_started = 1
    round_ended = 2
    explode = 3
    win = 4
    post_mortem = 5
    result_screen_dismissed_to_menu = 6
    strike1 = 7
    strike2 = 8
    strike3 = 9
    strike4 = 10
    strike5 = 11
    result_screen_dismissed_retry = 12
    one_minute_left = 13
    unknown = 14


class Ktane():
    """ Class that tracks the game state and controls the lights """
    def __init__(self, bridge_ip):
        self.b = Bridge(bridge_ip)
        self.mb = MockBridge(bridge_ip)
        self.b.connect()
        self.tmpb = None
        self.fast_forward_on = False
        self.state = KtaneState.in_menu

        self.pulse = 0
        self.strikes = 0
        self.won = False

        self.color_lamps = []
        for l in self.b.lights:
            try:
                dummy = l.hue
            except KeyError:
                # All the non-color lamps get dimmed
                l.brightness = 40
                continue
            self.menu_mode(l)
            self.color_lamps.append(l)

        logger.info("Initialized ktane_hue")

    def game_active(self):
        return (self.state == KtaneState.in_game or self.state == KtaneState.in_game_quick)

    def fast_forward(self, ff):
        if ff and not self.fast_forward_on:
            logger.info("Fast forwarding enabled")
            self.fast_forward_on = True
            self.tmpb = self.b
            self.b = self.mb
        else:
            logger.info("Fast forward disabled")
            self.fast_forward_on = False
            self.b = self.tmpb
            self.tmpb = None

    def tick(self):
        """The function called by our main event loop"""
        if self.state == KtaneState.exploding:
            self.explode()
        elif self.game_active():
            self.do_pulse()

    def explode(self):
        """Explosion animation. Once done, it moves to the post_portem state"""
        if self.pulse == 1:
            self.quarter_transitions()

        for lamp in self.color_lamps:
            if self.pulse == 0:
                lamp.brightness = 251
                self.color_red(lamp)
            elif self.pulse == 2:
                lamp.brightness = 251
                self.color_green(lamp)
            elif self.pulse == 4:
                self.normal_transitions()
                lamp.brightness = 57
                self.color_red(lamp)

        self.pulse += 1
        if self.pulse == 70:
            self.normal_transitions()
            self.state = KtaneState.post_mortem
            self.pulse = 0
            self.post_mortem()

    def do_pulse(self):
        """
        Pulses the lights while the countdown timer is running.
        The pulse counts on which the state changes are chosen to be dividable
        1, 2, 3 and 4. Might glitch slightly when the number of strikes
        increases during the animation, but self corrects once self.pulse resets
        to 0.
        """
        div = 1 + max(self.strikes, 3)

        for lamp in self.color_lamps:
            if self.pulse == 0:
                if self.state == KtaneState.in_game_quick or self.strikes >= 2:
                    self.color_mild_red(lamp)
                else:
                    self.color_mild_pink(lamp)

            elif self.pulse == 24 / div:
                self.color_orange(lamp)

        self.pulse += 1
        if self.pulse >= 48 / div:
            self.pulse = 0

    def menu_mode(self, lamp):
        """Lamp settings during the main menu / bomb selection"""
        lamp.on = True
        lamp.brightness = 251
        self.color_warm_white(lamp)

    def post_mortem(self):
        """Lamp settings during the post mortem debriefing"""
        logger.debug("post-mortem mode")
        for lamp in self.color_lamps:
            lamp.on = True
            lamp.brightness = 251
            self.color_coolest_white(lamp)

    def quick_transitions(self):
        """Set lamps to quickest transition speed (fastest color change)"""
        self.set_transition_time(0)

    def normal_transitions(self):
        """Set lamps to normal transition mode."""
        self.set_transition_time(10)

    def half_transitions(self):
        self.set_transition_time(5)

    def quarter_transitions(self):
        self.set_transition_time(2)

    def set_transition_time(self, t):
        for lamp in self.color_lamps:
            lamp.transitiontime = t

    def action(self, action):
        logger.info("From state {state}".format(state=self.state))
        if action == KtaneAction.round_started:
            if not self.game_active():
                self.start_round()

        if action == KtaneAction.round_ended:
            if self.state != KtaneState.exploding or self.fast_forward_on:
                self.stop_round()

        if action == KtaneAction.explode:
            if self.state != KtaneState.exploding:
                self.state = KtaneState.exploding
                logger.debug("exploded")
                self.quick_transitions()
                self.pulse = 0

        if action == KtaneAction.win:
            self.won = True

        if action == KtaneAction.result_screen_dismissed_to_menu:
            self.stop_round()

        if action == KtaneAction.result_screen_dismissed_retry:
            self.stop_round()
            self.start_round()

        if action >= KtaneAction.strike1 and action <= KtaneAction.strike5:
            new_strikes = action - KtaneAction.strike1 + 1
            if new_strikes != self.strikes:
                logger.debug("Detected strike {strike}".format(strike=new_strikes))
                self.strikes = new_strikes
                if self.strikes == 1:
                    self.half_transitions()
                if self.strikes == 2:
                    self.quarter_transitions()

        if action == KtaneAction.one_minute_left:
            self.state = KtaneState.in_game_quick

        logger.info("To state {state}".format(state=self.state))


    def start_round(self):
        """Reset state, start round"""
        logger.debug("start_round()")
        self.normal_transitions()
        self.state = KtaneState.in_game
        self.won = False
        self.strikes = 0

    def menu_mode_all(self):
        """Set all lamps to menu mode"""
        for lamp in self.color_lamps:
            self.menu_mode(lamp)

    def stop_round(self):
        """Stop round, back to menu mode"""
        logger.debug("Stopped round")
        self.state = KtaneState.in_menu
        self.normal_transitions()
        self.menu_mode_all()

    def color_set(self, hue, sat, l):
        l.hue = hue
        l.sat = sat

    def color_cool_white(self, l):
        self.color_set(35535, 200, l)

    def color_coolest_white(self, l):
        self.color_set(35535, 254, l)

    def color_warm_white(self, l):
        self.color_set(15460, 113, l)

    def color_red(self, l):
        self.color_set(65535, 254, l)

    def color_mild_red(self, l):
        self.color_set(65535, 150, l)

    def color_magenta(self, l):
        self.color_set(55535, 254, l)

    def color_mild_pink(self, l):
        self.color_set(62159, 83, l)

    def color_blue(self, l):
        self.color_set(47125, 200, l)

    def color_orange(self, l):
        self.color_set(13535, 254, l)

    def color_mild_orange(self, l):
        self.color_set(17535, 200, l)

    def color_green(self, l):
        self.color_set(25650, 254, l)

    def color_black(self, l):
        """Not exactly black"""
        self.color_set(47125, 0, l)


class KtaneLogParse:
    def __init__(self, fname):
        self.fname = fname
        # Correct for local timezone (log contains UTC)
        self.local_tz = time.timezone

    def parse_time_str(self, time_str):
        t = datetime.datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S,%f')
        return t - datetime.timedelta(seconds=self.local_tz)

    def parse_wrap(self, kt):
        """Small wrapper around the parse function"""
        with open(self.fname, 'r') as f:
            txt = f.read()
            lines = txt.splitlines()
            self.parse_log(lines, kt)

    def parse_log(self, lines, kt):
        """Parse log (list of lines). Pass useful state updates to kt."""
        for line in lines[-400:-1]:
            if '[State]' in line or \
               '[Bomb]' in line or \
               '[PostGameState]' in line or \
               '[Assets.Scripts.Pacing.PaceMaker]' in line or \
               '[Assets.Scripts.DossierMenu.MenuPage]' in line:
                # logger.info('--------> {line}'.format(line=line))
                # DEBUG 2015-12-24 18:57:49,884 [Assets.Scripts.Pacing.PaceMaker] Round start! Mission: The First Bomb Pacing Enabled: False

                r = r"[ ]*(?P<log_type>[A-Z]+) (?P<start_time>[^\[]*) \[(?P<component>[^\]]*)\] (?P<state_info>.*)"
                m = re.match(r, line)
                res = m.groupdict()

                t = self.parse_time_str(res['start_time'])
                now = datetime.datetime.now()

                action = self.parse_action(res['state_info'], res['component'])

                if abs(t - now) < datetime.timedelta(seconds=0.2) or kt.fast_forward_on:
                    logger.info(action)
                    # A recent change: pass to kt
                    # logger.info("State changed to {state}".format(state=res['state_info']))
                    kt.action(action)

    def parse_action(self, state_info, component):
        """Called by the parser when it picks up a new log entry of interest"""
        if state_info == 'Enter GameplayState':
            return KtaneAction.round_started

        if state_info == 'OnRoundEnd()':
            return KtaneAction.round_ended

        if state_info == 'Boom':
            return KtaneAction.explode

        if state_info == "A winner is you!!":
            return KtaneAction.win

        if state_info == 'Results screen bomb binder dismissed (continue). Restarting...' or state_info == 'ReturnToSetupRoom':
            return KtaneAction.result_screen_dismissed_to_menu

        if state_info == 'Results screen bomb binder dismissed (retry). Retrying same mission...':
            return KtaneAction.result_screen_dismissed_retry

        if state_info == "Executing random action of type OneMinuteLeft":
            return KtaneAction.one_minute_left

        if component == "Bomb" and "strike" in state_info:
            new_strikes = int(state_info[8])

            if new_strikes == 1:
                return KtaneAction.strike1
            if new_strikes == 2:
                return KtaneAction.strike2
            if new_strikes == 3:
                return KtaneAction.strike3
            if new_strikes == 4:
                return KtaneAction.strike4
            if new_strikes == 5:
                return KtaneAction.strike5

        return KtaneAction.unknown


def setup_logger():
    global logger
    logger = logging.getLogger('ktane_hue_logger')
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(message)s')

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.DEBUG)
    logger.addHandler(stream_handler)


class MockBridge:
    def __init__(self, ip):
        self.lights = []
        pass

    def connect(self):
        logger.debug("bridge.connect")


if __name__ == '__main__':
    main()
