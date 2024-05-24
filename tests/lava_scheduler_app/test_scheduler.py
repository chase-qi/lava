#
# Copyright (C) 2017-2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import logging
import time
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from lava_scheduler_app.models import Device, DeviceType, Tag, TestJob, Worker
from lava_scheduler_app.scheduler import (
    schedule,
    schedule_health_checks,
    worker_summary,
)


def _minimal_valid_job(self) -> str:
    return """
job_name: minimal valid job
visibility: public
timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
actions: []
"""


class TestHealthCheckScheduling(TestCase):
    def setUp(self):
        self.worker01 = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE
        )
        self.worker02 = Worker.objects.create(
            hostname="worker-02", state=Worker.STATE_OFFLINE
        )
        self.worker03 = Worker.objects.create(
            hostname="worker-03", state=Worker.STATE_ONLINE
        )

        self.device_type01 = DeviceType.objects.create(name="panda")

        # ignored by other tests, used to check device.is_valid handling
        self.device_type02 = DeviceType.objects.create(name="unknown")
        self.device_type02.display = False
        self.device_type02.save()

        self.device01 = Device.objects.create(
            hostname="panda01",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_UNKNOWN,
        )
        # This device should never be considered (his worker is OFFLINE)
        self.device02 = Device.objects.create(
            hostname="panda02",
            device_type=self.device_type01,
            worker_host=self.worker02,
            health=Device.HEALTH_UNKNOWN,
        )
        self.device03 = Device.objects.create(
            hostname="panda03",
            device_type=self.device_type01,
            worker_host=self.worker03,
            health=Device.HEALTH_UNKNOWN,
        )
        # ignored by other tests, used to check device.is_valid handling
        self.device04 = Device.objects.create(
            hostname="unknown-01",
            device_type=self.device_type02,
            worker_host=self.worker01,
            health=Device.HEALTH_RETIRED,
        )

        self.user = User.objects.create(username="user-01")
        self.last_hc03 = TestJob.objects.create(
            health_check=True,
            actual_device=self.device03,
            submitter=self.user,
            start_time=timezone.now(),
            state=TestJob.STATE_FINISHED,
            health=TestJob.HEALTH_COMPLETE,
        )
        self.device03.last_health_report_job = self.last_hc03
        self.device03.save()

    def _check_hc_scheduled(self, device):
        device.refresh_from_db()
        self.assertEqual(device.state, Device.STATE_RESERVED)
        job = device.current_job()
        self.assertIsNotNone(job)
        self.assertEqual(job.state, TestJob.STATE_SCHEDULED)
        self.assertEqual(job.health, TestJob.HEALTH_UNKNOWN)
        self.assertEqual(job.actual_device, device)

    def _check_hc_not_scheduled(self, device):
        device.refresh_from_db()
        self.assertEqual(device.state, Device.STATE_IDLE)
        self.assertIsNone(device.current_job())

    @patch.object(Device, "get_health_check", lambda _: None)
    def test_without_health_checks(self):
        self.assertIsNone(self.device01.get_health_check())
        self.assertIsNone(self.device02.get_health_check())
        self.assertIsNone(self.device03.get_health_check())
        # Schedule without health check
        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
        )
        available_devices = schedule_health_checks(
            logging.getLogger(), [], workers_limit
        )
        self.assertEqual(available_devices, {"panda": ["panda01", "panda03"]})

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_disabled_hc(self):
        self.assertNotEqual(self.device01.get_health_check(), None)
        self.assertNotEqual(self.device02.get_health_check(), None)
        self.assertNotEqual(self.device03.get_health_check(), None)

        self.device_type01.disable_health_check = True
        self.device_type01.save()
        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
        )
        available_devices = schedule_health_checks(
            logging.getLogger(), [], workers_limit
        )
        self.assertEqual(available_devices, {"panda": ["panda01", "panda03"]})

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_no_devicedict(self):
        self.device_type02.disable_health_check = False
        self.device_type02.display = True
        self.device_type02.save()

        self.device04.state = Device.STATE_IDLE
        self.device04.health = Device.HEALTH_UNKNOWN
        self.device04.save()

        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
        )
        schedule_health_checks(logging.getLogger(), [], workers_limit)

        self.device04.refresh_from_db()
        self.assertFalse(self.device04.is_valid())
        self.assertEqual(self.device04.health, Device.HEALTH_BAD)
        self.assertIsNone(self.device04.current_job())

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_without_previous_hc_device_health_unknown(self):
        self.assertIsNotNone(self.device01.get_health_check())
        self.assertIsNotNone(self.device02.get_health_check())
        self.assertIsNotNone(self.device03.get_health_check())

        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
        )
        available_devices = schedule_health_checks(
            logging.getLogger(), [], workers_limit
        )
        self.assertEqual(available_devices, {"panda": []})
        self._check_hc_scheduled(self.device01)
        self._check_hc_not_scheduled(self.device02)
        self._check_hc_scheduled(self.device03)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_device_health_good(self):
        self.assertIsNotNone(self.device01.get_health_check())
        self.assertIsNotNone(self.device02.get_health_check())
        self.assertIsNotNone(self.device03.get_health_check())

        self.device01.health = Device.HEALTH_GOOD
        self.device01.save()
        self.device02.health = Device.HEALTH_GOOD
        self.device02.save()
        self.device03.health = Device.HEALTH_GOOD
        self.device03.save()
        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
        )
        available_devices = schedule_health_checks(
            logging.getLogger(), [], workers_limit
        )
        self.assertEqual(available_devices, {"panda": ["panda03"]})
        self._check_hc_scheduled(self.device01)
        self._check_hc_not_scheduled(self.device02)
        self._check_hc_not_scheduled(self.device03)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_device_health_good_worker_maintenance(self):
        self.assertIsNotNone(self.device01.get_health_check())
        self.assertIsNotNone(self.device02.get_health_check())
        self.assertIsNotNone(self.device03.get_health_check())

        self.worker01.health = Worker.HEALTH_MAINTENANCE
        self.worker01.save()
        self.device01.health = Device.HEALTH_GOOD
        self.device01.save()
        self.device02.health = Device.HEALTH_GOOD
        self.device02.save()
        self.device03.health = Device.HEALTH_GOOD
        self.device03.save()
        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-03"])
        )
        available_devices = schedule_health_checks(
            logging.getLogger(), [], workers_limit
        )
        self.assertEqual(available_devices, {"panda": ["panda03"]})
        self._check_hc_not_scheduled(self.device01)
        self._check_hc_not_scheduled(self.device02)
        self._check_hc_not_scheduled(self.device03)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_device_health_looping(self):
        self.assertIsNotNone(self.device01.get_health_check())
        self.assertIsNotNone(self.device02.get_health_check())
        self.assertIsNotNone(self.device03.get_health_check())

        self.device01.health = Device.HEALTH_LOOPING
        self.device01.save()
        self.device02.health = Device.HEALTH_LOOPING
        self.device02.save()
        self.device03.health = Device.HEALTH_LOOPING
        self.device03.save()
        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
        )
        available_devices = schedule_health_checks(
            logging.getLogger(), [], workers_limit
        )
        self.assertEqual(available_devices, {"panda": []})
        self._check_hc_scheduled(self.device01)
        self._check_hc_not_scheduled(self.device02)
        self._check_hc_scheduled(self.device03)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_device_health_wrong(self):
        self.assertIsNotNone(self.device01.get_health_check())
        self.assertIsNotNone(self.device02.get_health_check())
        self.assertIsNotNone(self.device03.get_health_check())

        # HEALTH_(BAD|MAINTENANCE|RETIRED)
        for health in [
            Device.HEALTH_BAD,
            Device.HEALTH_MAINTENANCE,
            Device.HEALTH_RETIRED,
        ]:
            self.device01.health = health
            self.device01.save()
            self.device02.health = health
            self.device02.save()
            self.device03.health = health
            self.device03.save()
            workers_limit = worker_summary(
                Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
            )
            available_devices = schedule_health_checks(
                logging.getLogger(), [], workers_limit
            )
            self.assertEqual(available_devices, {"panda": []})
            self._check_hc_not_scheduled(self.device01)
            self._check_hc_not_scheduled(self.device02)
            self._check_hc_not_scheduled(self.device03)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_health_frequency_hours(self):
        self.device_type01.health_denominator = DeviceType.HEALTH_PER_HOUR
        self.device_type01.health_frequency = 24
        self.device_type01.save()

        self.assertIsNotNone(self.device01.get_health_check())
        self.assertIsNotNone(self.device02.get_health_check())
        self.assertIsNotNone(self.device03.get_health_check())
        # Only device03 is available now
        self.device01.health = Device.HEALTH_BAD
        self.device01.save()
        self.assertTrue(self.device01.is_valid())
        self.device03.health = Device.HEALTH_GOOD
        self.device03.save()
        self.assertTrue(self.device03.is_valid())

        # Create a job that should be scheduled now
        j = TestJob.objects.create(
            requested_device_type=self.device_type01,
            submitter=self.user,
            definition=_minimal_valid_job(None),
        )
        schedule(logging.getLogger(), [], ["worker-01", "worker-03"])
        self.device01.refresh_from_db()
        j.refresh_from_db()
        self.assertEqual(j.state, TestJob.STATE_SCHEDULED)
        self.assertEqual(j.actual_device, self.device03)
        j.go_state_finished(TestJob.HEALTH_COMPLETE)
        j.save()

        # Create a job that should be scheduled after the health check
        j = TestJob.objects.create(
            requested_device_type=self.device_type01,
            submitter=self.user,
            definition=_minimal_valid_job(None),
        )
        self.device03.refresh_from_db()
        self.last_hc03.submit_time = timezone.now() - timedelta(hours=25)
        self.last_hc03.save()

        schedule(logging.getLogger(), [], ["worker-01", "worker-03"])
        self.device03.refresh_from_db()
        j.refresh_from_db()
        self.assertEqual(j.state, TestJob.STATE_SUBMITTED)
        current_hc = self.device03.current_job()
        self.assertTrue(current_hc.health_check)
        self.assertEqual(current_hc.state, TestJob.STATE_SCHEDULED)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_health_frequency_jobs(self):
        self.device_type01.health_denominator = DeviceType.HEALTH_PER_JOB
        self.device_type01.health_frequency = 2
        self.device_type01.save()
        self.last_hc03.submit_time = timezone.now() - timedelta(hours=2)
        self.last_hc03.save()

        self.assertIsNotNone(self.device01.get_health_check())
        self.assertIsNotNone(self.device02.get_health_check())
        self.assertIsNotNone(self.device03.get_health_check())
        # Only device03 is available now
        self.device01.health = Device.HEALTH_BAD
        self.device01.save()
        self.device03.health = Device.HEALTH_GOOD
        self.device03.save()

        # Create three jobs that should be scheduled with a healthcheck preceding the
        # last one
        for i in range(0, 3):
            TestJob.objects.create(
                requested_device_type=self.device_type01,
                submitter=self.user,
                definition=_minimal_valid_job(None),
            )

        schedule(logging.getLogger(), [], ["worker-01", "worker-03"])
        self.device03.refresh_from_db()
        jobs = TestJob.objects.filter(state=TestJob.STATE_SCHEDULED)
        self.assertEqual(jobs.count(), 1)
        j = jobs[0]
        self.assertEqual(j.actual_device, self.device03)
        j.go_state_finished(TestJob.HEALTH_COMPLETE)
        j.start_time = timezone.now() - timedelta(hours=1)
        j.save()

        schedule(logging.getLogger(), [], ["worker-01", "worker-03"])
        self.device03.refresh_from_db()
        jobs = TestJob.objects.filter(state=TestJob.STATE_SCHEDULED)
        self.assertEqual(jobs.count(), 1)
        j = jobs[0]
        self.assertEqual(j.actual_device, self.device03)
        j.go_state_finished(TestJob.HEALTH_COMPLETE)
        j.start_time = timezone.now() - timedelta(hours=1)
        j.save()

        schedule(logging.getLogger(), [], ["worker-01", "worker-03"])
        self.device03.refresh_from_db()
        jobs = TestJob.objects.filter(state=TestJob.STATE_SUBMITTED)
        self.assertEqual(jobs.count(), 1)
        current_hc = self.device03.current_job()
        self.assertTrue(current_hc.health_check)
        self.assertEqual(current_hc.state, TestJob.STATE_SCHEDULED)


@patch.object(Device, "get_health_check", _minimal_valid_job)
class TestTagsScheduling(TestCase):
    def setUp(self) -> None:
        self.worker01 = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE
        )
        self.user = User.objects.create(username="user-01")
        self.device_type01 = DeviceType.objects.create(
            name="qemu", disable_health_check=True
        )
        self.device01 = Device.objects.create(
            hostname="qemu01",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.device03 = Device.objects.create(
            hostname="qemu03",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )

    def create_job_with_tags(self, *tags: Tag) -> TestJob:
        job = TestJob.objects.create(
            requested_device_type=self.device_type01,
            submitter=self.user,
            definition=_minimal_valid_job(None),
        )
        job.tags.add(*tags)
        return job

    def test_tags_none(self) -> None:
        test_tag = Tag.objects.create(name="test-01")

        job = self.create_job_with_tags(test_tag)

        schedule(logging.getLogger(), [], ["worker-01"])
        job.refresh_from_db()

        self.assertIsNone(job.actual_device_id)

    def test_tags_equal(self) -> None:
        test_tag = Tag.objects.create(name="test-01")
        self.device03.tags.add(test_tag)

        job = self.create_job_with_tags(test_tag)

        schedule(logging.getLogger(), [], ["worker-01"])
        job.refresh_from_db()

        self.assertEqual(job.actual_device_id, self.device03.pk)

    def test_tags_equal_multiple(self) -> None:
        test_tag_1 = Tag.objects.create(name="test-01")
        test_tag_2 = Tag.objects.create(name="test-02")
        self.device03.tags.add(test_tag_1)
        self.device01.tags.add(test_tag_1)
        self.device01.tags.add(test_tag_2)

        job = self.create_job_with_tags(test_tag_1, test_tag_2)

        schedule(logging.getLogger(), [], ["worker-01"])
        job.refresh_from_db()

        self.assertEqual(job.actual_device_id, self.device01.pk)

    def test_tags_subset(self) -> None:
        test_tag_1 = Tag.objects.create(name="test-01")
        test_tag_2 = Tag.objects.create(name="test-02")
        self.device03.tags.add(test_tag_1)
        self.device03.tags.add(test_tag_2)
        self.device01.tags.add(test_tag_1)

        job = self.create_job_with_tags(test_tag_2)

        schedule(logging.getLogger(), [], ["worker-01"])
        job.refresh_from_db()

        self.assertEqual(job.actual_device_id, self.device03.pk)

    def test_tags_superset(self) -> None:
        test_tag_1 = Tag.objects.create(name="test-01")
        test_tag_2 = Tag.objects.create(name="test-02")
        self.device03.tags.add(test_tag_2)
        self.device01.tags.add(test_tag_1)

        job = self.create_job_with_tags(test_tag_1, test_tag_2)

        schedule(logging.getLogger(), [], ["worker-01"])
        job.refresh_from_db()

        self.assertIsNone(job.actual_device_id)


class TestVisibility(TestCase):
    def setUp(self):
        self.worker01 = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE
        )
        self.worker02 = Worker.objects.create(
            hostname="worker-02", state=Worker.STATE_OFFLINE
        )
        self.worker03 = Worker.objects.create(
            hostname="worker-03", state=Worker.STATE_ONLINE
        )

        self.device_type01 = DeviceType.objects.create(name="panda")

        self.device01 = Device.objects.create(
            hostname="panda01",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_UNKNOWN,
        )
        # This device should never be considered (his worker is OFFLINE)
        self.device02 = Device.objects.create(
            hostname="panda02",
            device_type=self.device_type01,
            worker_host=self.worker02,
            health=Device.HEALTH_UNKNOWN,
        )
        self.device03 = Device.objects.create(
            hostname="panda03",
            device_type=self.device_type01,
            worker_host=self.worker03,
            health=Device.HEALTH_UNKNOWN,
        )
        self.user = User.objects.create(username="user-01")
        self.device03.save()

    def _check_hc_scheduled(self, device):
        device.refresh_from_db()
        self.assertEqual(device.state, Device.STATE_RESERVED)
        job = device.current_job()
        self.assertIsNotNone(job)
        self.assertEqual(job.state, TestJob.STATE_SCHEDULED)
        self.assertEqual(job.health, TestJob.HEALTH_UNKNOWN)
        self.assertEqual(job.actual_device, device)

    def _check_hc_not_scheduled(self, device):
        device.refresh_from_db()
        self.assertEqual(device.state, Device.STATE_IDLE)
        self.assertEqual(device.current_job(), None)

    def _check_initial_state(self):
        self.assertIsNotNone(self.device01.get_health_check())
        self.assertIsNotNone(self.device02.get_health_check())
        self.assertIsNotNone(self.device03.get_health_check())
        self.assertEqual(self.device01.health, Device.HEALTH_UNKNOWN)
        self.assertEqual(self.device02.health, Device.HEALTH_UNKNOWN)
        self.assertEqual(self.device03.health, Device.HEALTH_UNKNOWN)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_health_visibility(self):
        self._check_initial_state()

        self.device_type01.disable_health_check = False
        self.device_type01.save()

        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
        )
        schedule_health_checks(logging.getLogger(), [], workers_limit)

        self._check_hc_scheduled(self.device01)
        self._check_hc_not_scheduled(self.device02)
        self._check_hc_scheduled(self.device03)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_health_visibility_some_restricted(self):
        self._check_initial_state()

        self.device_type01.disable_health_check = False
        self.device_type01.save()

        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
        )
        schedule_health_checks(logging.getLogger(), [], workers_limit)

        self._check_hc_scheduled(self.device01)
        self._check_hc_not_scheduled(self.device02)
        # device03 is restricted in setUp
        self._check_hc_scheduled(self.device03)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_health_visibility_all_restricted(self):
        self._check_initial_state()

        self.device_type01.disable_health_check = False
        self.device_type01.save()

        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
        )
        schedule_health_checks(logging.getLogger(), [], workers_limit)

        self._check_hc_scheduled(self.device01)
        self._check_hc_not_scheduled(self.device02)
        self._check_hc_scheduled(self.device03)


class TestPriorities(TestCase):
    def setUp(self):
        self.worker01 = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE
        )
        self.device_type01 = DeviceType.objects.create(name="panda")
        self.device01 = Device.objects.create(
            hostname="panda01",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.user = User.objects.create(username="user-01")

    def _check_job(
        self, job, priorities, state=TestJob.STATE_SUBMITTED, actual_device=None
    ):
        job.refresh_from_db()
        self.assertIn(job.priority, priorities)
        self.assertEqual(job.state, state)
        self.assertEqual(job.actual_device, actual_device)

    def _check_scheduling(self, logger, device, current_priority, remaining_priorities):
        schedule(logger, [], ["worker-01"])
        device.refresh_from_db()
        self.assertEqual(device.state, Device.STATE_RESERVED)

        scheduled = TestJob.objects.filter(state=TestJob.STATE_SCHEDULED)
        self.assertEqual(scheduled.count(), 1)

        current = TestJob.objects.get(id=scheduled[0].id)
        self._check_job(current, (current_priority,), TestJob.STATE_SCHEDULED, device)

        submitted = TestJob.objects.filter(state=TestJob.STATE_SUBMITTED)
        for j in submitted:
            self._check_job(j, remaining_priorities)

        current.go_state_finished(TestJob.HEALTH_COMPLETE)
        current.save()
        self._check_job(current, (current_priority,), TestJob.STATE_FINISHED, device)

    def test_low_medium_high_without_hc(self):
        for p in [
            TestJob.LOW,
            TestJob.MEDIUM,
            TestJob.HIGH,
            TestJob.MEDIUM,
            TestJob.LOW,
            40,
        ]:
            TestJob.objects.create(
                requested_device_type=self.device_type01,
                submitter=self.user,
                definition=_minimal_valid_job(None),
                priority=p,
            )

        log = logging.getLogger()

        # High priority job
        self._check_scheduling(
            log, self.device01, TestJob.HIGH, (TestJob.MEDIUM, TestJob.LOW, 40)
        )

        # Medium priority jobs
        self._check_scheduling(
            log, self.device01, TestJob.MEDIUM, (TestJob.MEDIUM, TestJob.LOW, 40)
        )
        self._check_scheduling(log, self.device01, TestJob.MEDIUM, (TestJob.LOW, 40))

        # Custom priority job
        self._check_scheduling(log, self.device01, 40, (TestJob.LOW,))

        # Low priority jobs
        self._check_scheduling(log, self.device01, TestJob.LOW, (TestJob.LOW,))
        self._check_scheduling(log, self.device01, TestJob.LOW, ())

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_low_medium_high_with_hc(self):
        # Enable health checks
        self.device_type01.health_denominator = DeviceType.HEALTH_PER_HOUR
        self.device_type01.health_frequency = 24
        self.device_type01.save()

        self.assertIsNotNone(self.device01.get_health_check())

        jobs = []
        for p in [
            TestJob.LOW,
            TestJob.MEDIUM,
            TestJob.HIGH,
            TestJob.MEDIUM,
            TestJob.LOW,
        ]:
            j = TestJob.objects.create(
                requested_device_type=self.device_type01,
                submitter=self.user,
                definition=_minimal_valid_job(None),
                priority=p,
            )
            jobs.append(j)

        # Check that an health check will be scheduled before any jobs
        log = logging.getLogger()
        schedule(log, [], ["worker-01"])
        self.device01.refresh_from_db()
        self.assertEqual(self.device01.state, Device.STATE_RESERVED)
        submitted = TestJob.objects.filter(state=TestJob.STATE_SUBMITTED)
        self.assertEqual(submitted.count(), len(jobs))

        current_hc = self.device01.current_job()
        self.assertEqual(current_hc.state, TestJob.STATE_SCHEDULED)
        current_hc.go_state_finished(TestJob.HEALTH_COMPLETE)
        current_hc.save()

        # Check that the next job is the highest priority
        schedule(log, [], ["worker-01"])
        self.device01.refresh_from_db()
        self.assertEqual(self.device01.state, Device.STATE_RESERVED)
        scheduled = TestJob.objects.filter(state=TestJob.STATE_SCHEDULED)
        self.assertEqual(scheduled.count(), 1)
        self._check_job(
            scheduled[0], (TestJob.HIGH,), TestJob.STATE_SCHEDULED, self.device01
        )


# test joblimit with HealthChecks with a joblimit of 1
class TestJobLimitHc1(TestCase):
    def setUp(self):
        self.worker01 = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE, job_limit=1
        )
        self.device_type01 = DeviceType.objects.create(name="qemu")
        self.devices = []
        self.user = User.objects.create(username="user-01")

        self.device01 = Device.objects.create(
            hostname="qemu01",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.device02 = Device.objects.create(
            hostname="qemu02",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.device03 = Device.objects.create(
            hostname="qemu03",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.device04 = Device.objects.create(
            hostname="qemu04",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.devices.append(self.device01)
        self.devices.append(self.device02)
        self.devices.append(self.device03)
        self.devices.append(self.device04)
        self.device01.save()
        self.device02.save()
        self.device03.save()
        self.device04.save()

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_job_limit_hc(self):
        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01"])
        )
        schedule_health_checks(logging.getLogger(), [], workers_limit)

        devs = 0
        # check that only one device got healthcheck
        for device in self.devices:
            device.refresh_from_db()
            if device.state != Device.STATE_IDLE:
                devs = devs + 1
        self.assertEqual(devs, 1)
        for job in TestJob.objects.filter(
            state__in=[TestJob.STATE_SCHEDULING, TestJob.STATE_SCHEDULED]
        ):
            job.go_state_finished(TestJob.HEALTH_COMPLETE)
            job.actual_device.health = Device.HEALTH_GOOD
            job.actual_device.state = Device.STATE_IDLE
            job.actual_device.save()
            job.save()

        # STEP 2
        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01"])
        )
        schedule_health_checks(logging.getLogger(), [], workers_limit)

        devs = 0
        for device in self.devices:
            device.refresh_from_db()
            if device.state != Device.STATE_IDLE:
                devs = devs + 1
        self.assertEqual(devs, 1)


# test joblimit with HealthChecks with a joblimit of 2
class TestJobLimitHc2(TestCase):
    def setUp(self):
        self.worker01 = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE, job_limit=2
        )
        self.device_type01 = DeviceType.objects.create(name="qemu")
        self.devices = []
        self.user = User.objects.create(username="user-01")

        self.device01 = Device.objects.create(
            hostname="qemu01",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.device02 = Device.objects.create(
            hostname="qemu02",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.device03 = Device.objects.create(
            hostname="qemu03",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.device04 = Device.objects.create(
            hostname="qemu04",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.devices.append(self.device01)
        self.devices.append(self.device02)
        self.devices.append(self.device03)
        self.devices.append(self.device04)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_job_limit_hc2(self):
        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01"])
        )
        schedule_health_checks(logging.getLogger(), [], workers_limit)

        devs = 0
        # check that only 2 devices got healthcheck
        for device in self.devices:
            device.refresh_from_db()
            if device.state != Device.STATE_IDLE:
                devs = devs + 1
        self.assertEqual(devs, 2)

        for job in TestJob.objects.filter(
            state__in=[TestJob.STATE_SCHEDULING, TestJob.STATE_SCHEDULED]
        ):
            job.go_state_finished(TestJob.HEALTH_COMPLETE)
            job.actual_device.health = Device.HEALTH_GOOD
            job.actual_device.state = Device.STATE_IDLE
            job.actual_device.save()
            job.save()

        # STEP 2
        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01"])
        )
        schedule_health_checks(logging.getLogger(), [], workers_limit)

        devs = 0
        # check that only 4 devices got healthcheck
        for device in self.devices:
            device.refresh_from_db()
            if device.state != Device.STATE_IDLE:
                devs = devs + 1
        self.assertEqual(devs, 2)


# test both healthcheck and normal testjobs with joblimit
class TestJobLimit(TestCase):
    def setUp(self):
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)
        self.job_limit = 2

        self.worker01 = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE, job_limit=self.job_limit
        )
        self.user = User.objects.create(username="user-01")
        self.device_type01 = DeviceType.objects.create(
            name="qemu", disable_health_check=True
        )
        self.devices = []
        for i in range(0, 6):
            dev = Device.objects.create(
                hostname=f"qemu0{i}",
                device_type=self.device_type01,
                worker_host=self.worker01,
                health=Device.HEALTH_GOOD,
            )
            self.devices.append(dev)

    def test_job_limit(self):
        for i in range(0, 4):
            TestJob.objects.create(
                requested_device_type=self.device_type01,
                submitter=self.user,
                definition=_minimal_valid_job(None),
            )
        self.assertEqual(TestJob.objects.all().count(), 4)
        # Limit the number of jobs that can run
        schedule(self.logger, [], ["worker-01"])
        self.assertEqual(
            TestJob.objects.filter(state=TestJob.STATE_SCHEDULED).count(), 2
        )
        self.assertEqual(
            TestJob.objects.filter(state=TestJob.STATE_SUBMITTED).count(), 2
        )

    def test_job_limit_unlimited(self):
        for i in range(0, 4):
            TestJob.objects.create(
                requested_device_type=self.device_type01,
                submitter=self.user,
                definition=_minimal_valid_job(None),
            )
        self.assertEqual(TestJob.objects.all().count(), 4)
        # Limit the number of jobs that can run
        self.worker01.job_limit = 0
        self.worker01.save()
        schedule(self.logger, [], ["worker-01"])
        self.assertEqual(
            TestJob.objects.filter(state=TestJob.STATE_SCHEDULED).count(), 4
        )
        self.assertEqual(
            TestJob.objects.filter(state=TestJob.STATE_SUBMITTED).count(), 0
        )


# test both healthcheck and normal testjobs with joblimit
class TestJobQueueTimeout(TestCase):
    def setUp(self):
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)

        self.worker01 = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE
        )
        self.user = User.objects.create(username="user-01")
        self.device_type01 = DeviceType.objects.create(
            name="qemu", disable_health_check=True
        )
        self.devices = []
        dev = Device.objects.create(
            hostname="qemu0",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_BAD,
        )
        self.devices.append(dev)

    def test_job_limit(self):
        TestJob.objects.create(
            requested_device_type=self.device_type01,
            submitter=self.user,
            queue_timeout=int(timedelta(seconds=1).total_seconds()),
        )
        self.assertEqual(TestJob.objects.all().count(), 1)
        # Limit the number of jobs that can run
        schedule(self.logger, [], [])
        self.assertEqual(
            TestJob.objects.filter(state=TestJob.STATE_SUBMITTED).count(), 1
        )
        self.assertEqual(
            TestJob.objects.filter(state=TestJob.STATE_CANCELING).count(), 0
        )
        time.sleep(3)
        schedule(self.logger, [], [])
        self.assertEqual(
            TestJob.objects.filter(state=TestJob.STATE_SUBMITTED).count(), 0
        )
        canceling = TestJob.objects.filter(state=TestJob.STATE_CANCELING).count()
        canceled = TestJob.objects.filter(health=TestJob.HEALTH_CANCELED).count()
        if canceling == 0:
            self.assertEqual(canceled, 1)
        else:
            self.assertEqual(canceling, 1)
            self.assertEqual(canceled, 0)
