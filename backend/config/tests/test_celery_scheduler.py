import datetime
from unittest.mock import patch

from django.db.utils import OperationalError
from django.test import SimpleTestCase

from config.celery_scheduler import ResilientDatabaseScheduler


class ResilientDatabaseSchedulerTests(SimpleTestCase):
    def build_scheduler(self):
        scheduler = ResilientDatabaseScheduler.__new__(ResilientDatabaseScheduler)
        scheduler._initial_read = False
        scheduler._last_full_sync = datetime.datetime.now()
        scheduler._schedule = {'existing': object()}
        scheduler._heap = ['stale']
        scheduler._heap_invalidated = False
        scheduler._dirty = set()
        return scheduler

    def test_schedule_returns_existing_snapshot_when_refresh_hits_operational_error(self):
        scheduler = self.build_scheduler()

        with patch.object(ResilientDatabaseScheduler, 'schedule_changed', return_value=True), \
             patch.object(ResilientDatabaseScheduler, 'sync'), \
             patch('config.celery_scheduler.DatabaseScheduler.all_as_schedule', side_effect=OperationalError('db restarted')):
            schedule = ResilientDatabaseScheduler.schedule.fget(scheduler)

        self.assertIs(schedule, scheduler._schedule)
        self.assertEqual(scheduler._heap, [])
        self.assertTrue(scheduler._heap_invalidated)

    def test_all_as_schedule_returns_empty_mapping_when_initial_load_hits_operational_error(self):
        scheduler = self.build_scheduler()
        scheduler._schedule = None

        with patch('config.celery_scheduler.DatabaseScheduler.all_as_schedule', side_effect=OperationalError('db restarted')):
            schedule = scheduler.all_as_schedule()

        self.assertEqual(schedule, {})
