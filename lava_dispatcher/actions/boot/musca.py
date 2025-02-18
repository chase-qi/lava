# Copyright (C) 2019 Arm Limited
#
# Author: Dean Birch <dean.birch@arm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.boot import (
    AutoLoginAction,
    BootHasMixin,
    ExportDeviceEnvironment,
    OverlayUnpack,
)
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.shell import ExpectShellSession
from lava_dispatcher.utils.udev import WaitUSBSerialDeviceAction


class MuscaBoot(BootHasMixin, RetryAction):
    name = "musca-boot"
    description = "power device and trigger software to run"
    summary = "power device and trigger software to run"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(ResetDevice(self.job))
        self.pipeline.add_action(WaitUSBSerialDeviceAction(self.job))
        self.pipeline.add_action(ConnectDevice(self.job))
        if self.has_prompts(parameters):
            self.pipeline.add_action(AutoLoginAction(self.job))
        if self.test_has_shell(parameters):
            self.pipeline.add_action(ExpectShellSession(self.job))
            if "transfer_overlay" in parameters:
                self.pipeline.add_action(OverlayUnpack(self.job))
            self.pipeline.add_action(ExportDeviceEnvironment(self.job))
