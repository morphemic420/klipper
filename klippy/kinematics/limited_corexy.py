# Code for handling the kinematics of corexy robots
# with per-axis limits for acceleration
#
# Copyright (C) 2020-2021  Mael Kerbiriou <piezo.wdimd@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#
# Usage:
# Copying this file under `klipper/klippy/kinematics/` should be enough
# (click the `raw` button on github, then save as)
# Then your config's [printer] should look like:
# [printer]
# kinematics: limited_corexy
# max_velocity: [141% original value]
# max_z_velocity: [untouched]
# max_accel: [max_x_accel, or less if you want to clip the per-axis limiting]
# max_x_accel: [empirically determined, max_accel taken if omitted]
# max_y_accel: [empirically determined, less than max_x_accel because of gantry mass]
# max_z_accel: [untouched]
# scale_xy_accel: [True/False, default False]
#
# If scale_xy_accel is False, `max_accel` defined by M204 / SET_VELOCITY_LIMIT acts as a third limit,
# which means when you move with less acceleration than max_x_accel and max_y_accel, the toolhead
# accelerates regardless of the move direction. When True, max_x_accel and max_y_accel are scaled
# by the ratio of the dynamically set acceleration and the max_accel value from the config.
# This means that the actual acceleration will always depend on the direction.
#
# Derivation of the formulae described here: http://bl.ocks.org/Piezoid/raw/368e4ca48c65724e419cfb8198cfee0e/
# (notebook source: /docs/PerAxisLimits.ipynb)

from . import corexy
from math import sqrt, atan2, pi

class LimitedCoreXYKinematics(corexy.CoreXYKinematics):
    def __init__(self, toolhead, config):
        corexy.CoreXYKinematics.__init__(self, toolhead, config)
        # Setup x/y axis limits
        max_velocity, max_accel = toolhead.get_max_velocity()
        self.config_max_accel = max_accel
        self.max_x_accel = config.getfloat('max_x_accel', max_accel, above=0)
        self.max_y_accel = config.getfloat('max_y_accel', max_accel, above=0)
        self.scale_per_axis = config.getboolean('scale_xy_accel', False)
        config.get_printer().lookup_object('gcode').register_command(
            'SET_KINEMATICS_LIMIT', self.cmd_SET_KINEMATICS_LIMIT)
    def cmd_SET_KINEMATICS_LIMIT(self,gcmd):
        config_max_accel = self.config_max_accel
        self.max_x_accel = gcmd.get_float('X_ACCEL', self.max_x_accel, above=0., maxval=config_max_accel)
        self.max_y_accel = gcmd.get_float('Y_ACCEL', self.max_y_accel, above=0., maxval=config_max_accel)
        self.max_z_accel = gcmd.get_float('Z_ACCEL', self.max_z_accel, above=0., maxval=config_max_accel)
        self.scale_per_axis = bool(gcmd.get_int('SCALE', self.scale_per_axis, minval=0, maxval=1))
        msg = "x,y max_accels: %r\n" % [self.max_x_accel, self.max_y_accel, self.max_z_accel]
        if self.scale_per_axis:
            msg += "Per axis accelerations limits scale with current acceleration.\n"
        else:
            msg += "Per axis accelerations limits are independant of current acceleration.\n"
        msg += "Minimum XY acceleration of %.0f mm/s² reached on %.0f° diagonals." % (
            1/sqrt(self.max_x_accel**(-2) + self.max_y_accel**(-2)),
            180*atan2(self.max_x_accel, self.max_y_accel) / pi
        )
        gcmd.respond_info(msg)
    def check_move(self, move):
        if not move.is_kinematic_move:
            return
        self._check_endstops(move)
        toolhead = move.toolhead
        max_v = toolhead.max_velocity
        max_a = toolhead.max_accel
        max_pa = max_a
        move_d = move.move_d
        x,y,z = move.axes_d[:3]
        ab_linf = max(abs(x+y), abs(x-y))
        if ab_linf > 0:
            max_v *= move_d / ab_linf
            max_x_accel = self.max_x_accel
            max_y_accel = self.max_y_accel
            x_o_a = x / max_x_accel
            y_o_a = y / max_y_accel
            x_o_pa = x / max_y_accel
            y_o_pa = y / max_x_accel
            if self.scale_per_axis:
                max_a *= move_d / self.config_max_accel
            else:
                max_a = move_d
            max_pa = max_a / max(abs(x_o_pa + y_o_pa), abs(x_o_pa - y_o_pa))
            max_a /= max(abs(x_o_a + y_o_a), abs(x_o_a - y_o_a))
        if z:
            z_ratio = move_d / abs(z)
            max_v = min(max_v, self.max_z_velocity * z_ratio)
            max_a = min(max_a, self.max_z_accel * z_ratio)
        move.limit_speed(max_v, max_a, max_pa)

def load_kinematics(toolhead, config):
    return LimitedCoreXYKinematics(toolhead, config)
