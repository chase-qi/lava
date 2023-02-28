# Copyright (C) 2023 Linaro
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import os
import subprocess
import time

import requests

from lava_common.exceptions import JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import AutoLoginAction, BootHasMixin
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.utils.docker import DockerRun

LAVA_NODEBOOTER_PATH = "/home/lava/downloads"
LAVA_DOWNLOADS_PATH = "/var/lib/lava/dispatcher/tmp"


class BootNodebooter(Boot):
    compatibility = 4

    @classmethod
    def action(cls):
        return BootNodebooterAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "nodebooter" not in device["actions"]["boot"]["methods"]:
            return (
                False,
                '"nodebooter" was not in the device configuration boot methods',
            )
        if parameters["method"] != "nodebooter":
            return False, '"method" was not "nodebooter"'
        return True, "accepted"


class BootNodebooterAction(BootHasMixin, RetryAction):
    name = "boot-nodebooter"
    description = "boot nodebooter"
    summary = "boot nodebooter"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # TODO: auth with GAR and get image:
        # self.pipeline.add_action(GetNodebooterImage())
        self.pipeline.add_action(RunNodebooterContainer())
        self.pipeline.add_action(ConfigureNodebooter())

        self.pipeline.add_action(ResetDevice())
        if self.has_prompts(parameters):
            self.pipeline.add_action(AutoLoginAction())


class RunNodebooterContainer(Action):
    name = "run-nodebooter-container"
    description = "run nodebooter container based on image"
    summary = "run nodebooter container"

    def __init__(self):
        super().__init__()
        self.cleanup_required = False
        self.container = ""

    def validate(self):
        super().validate()
        self.container = "nodebooter"

        if "docker" not in self.parameters:
            self.errors = "Specify docker parameter"
            raise JobError("Not specified 'docker' in parameters")
        if "network_interface" not in self.parameters["docker"]:
            self.errors = "Missing network interface for the DUT in docker parameter"
        self.docker_image = self.parameters["docker"]

    def run(self, connection, max_end_time):
        NODEBOOTER_HOME = "/data/nodebooter/"
        VOLUMES = {
            f"{NODEBOOTER_HOME}docker_mount": "/home/shared",
            f"{NODEBOOTER_HOME}tftpboot": "/var/lib/tftpboot",
            f"{NODEBOOTER_HOME}dhcpd/etc/dhcp": "/etc/dhcp",
            f"{NODEBOOTER_HOME}dhcpd/var/lib/dhcp": "/var/lib/dhcp",
            f"{NODEBOOTER_HOME}dhcpd/var/db": "/var/db",
            f"{NODEBOOTER_HOME}logs": "/var/log",
            f"{NODEBOOTER_HOME}docker_shm": "/dev/shm",
            f"{NODEBOOTER_HOME}ovss": "/opt/ovss",
            LAVA_DOWNLOADS_PATH: LAVA_NODEBOOTER_PATH,
        }
        INIT_EXEC = "/usr/sbin/init"

        docker = DockerRun.from_parameters(self.parameters["docker"], self.job)
        docker.network = "host"

        for vol, mnt in VOLUMES.items():
            os.makedirs(vol, exist_ok=True)
            option = "--volume=%s:%s" % (vol, mnt)
            docker.add_docker_run_options(option)

        docker.add_docker_run_options("--privileged")
        docker.add_docker_run_options("-it")
        docker.add_docker_run_options("-d")
        docker.add_docker_run_options(
            "-e DUT_IFACE='%s'" % self.parameters["docker"]["network_interface"]
        )
        docker.add_docker_run_options("--network=host")
        self.logger.info(docker.cmdline())
        docker.local(True)
        docker.name(self.container)
        docker.init(False)

        try:
            docker.run(INIT_EXEC)
        except subprocess.CalledProcessError as exc:
            raise JobError(f"docker run command exited: {exc}")

        self.set_namespace_data(
            action="shared",
            label="shared",
            key="nodebooter_container",
            value=self.container,
        )


class ConfigureNodebooter(Action):
    name = "configure-nodebooter"
    description = "update nodebooter settings and add dut via API"
    summary = "configure nodebooter"

    def __init__(self):
        super().__init__()
        self.container = ""

    def validate(self):
        # We assume the nodebooter container is running, otherwise previous
        # action in the pipeline would have failed.
        super().validate()
        if "mac_address" not in self.parameters["docker"]:
            self.errors = "Missing mac address of the DUT in docker parameter"

    def run(self, connection, max_end_time):
        # Make sure nodebooter container is stopped at the end.
        self.cleanup_required = True

        # Manual intervention for nodebooter container.
        # TODO: Remove this once we have higher level of integration.
        machine_interface = self.parameters["docker"]["network_interface"]
        radvd_replace_cmd = [
            "docker",
            "exec",
            "-d",
            "nodebooter",
            "sed",
            "-i",
            "-e",
            "'s/enp102s0f0/%s/g'" % machine_interface,
            "/etc/radvd.conf",
        ]
        try:
            subprocess.check_output(  # nosec - internal.
                radvd_replace_cmd,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as exc:
            self.errors = str(exc)

        # Certain daemons require restart after the container is up.
        services_restart_required = ["radvd", "naas", "nodebooter"]
        for service in services_restart_required:
            try:
                subprocess.check_output(  # nosec - internal.
                    [
                        "docker",
                        "exec",
                        "-d",
                        "nodebooter",
                        "systemctl",
                        "restart",
                        service,
                    ],
                    stderr=subprocess.STDOUT,
                )
            except subprocess.CalledProcessError as exc:
                self.errors = str(exc)

        # Add DUT to Nodebooter via API (on localhost)
        url = "http://localhost:12901/nodebooter/api/v2/machines/"

        # Check that the nodebooter is online and receiving API calls
        self.logger.debug("Probing nodebooter API availability via %s", url)
        while True:
            try:
                res = requests.get(url)
                if res.status_code in (200, 302):
                    break
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(1)
        self.logger.debug("Nodebooter API available at: %s", url)

        # Use API to add the machine to nodebooter with preconfigured data.
        try:
            res = None
            headers = {"Content-Type": "application/json"}
            boot_image = self.get_namespace_data(
                "download-action", label="boot", key="file"
            ).replace(LAVA_DOWNLOADS_PATH, LAVA_NODEBOOTER_PATH)
            json = {
                "machine_name": "dut",
                "machine_model_data": {
                    "node_entities": {
                        "entities": {
                            "host-compute-node": {
                                "network_interfaces": {
                                    "network_interface": [
                                        {
                                            "device_name": machine_interface,
                                            "hostname": "",
                                            "ipv6_subnet_key": "",
                                            "mac_address": self.parameters["docker"][
                                                "mac_address"
                                            ],
                                            "use_for_netboot": True,
                                        }
                                    ]
                                }
                            }
                        }
                    }
                },
                "boot_info": [
                    {
                        "node_entity_name": "host-compute-node",
                        "boot_file": boot_image,
                        "loader_file": "",
                    }
                ],
            }
            res = requests.post(url, json=json, headers=headers)

        except requests.RequestException as exc:
            self.logger.error("Resource not available")
            raise JobError(f"Could not update nodebooter API: {exc}")
        finally:
            if res is not None:
                self.logger.info(
                    f"Nodebooter API call response code: {res.status_code}"
                )
                res.close()

    def cleanup(self, connection):
        super().cleanup(connection)
        container = self.get_namespace_data(
            action="shared", label="shared", key="nodebooter_container"
        )
        self.logger.debug("Stopping container %s", container)
        self.run_cmd("docker stop %s" % (container), allow_fail=True)
