import datetime
import logging

from django.db import DatabaseError, InterfaceError, close_old_connections

from django_celery_beat.schedulers import DatabaseScheduler, SCHEDULE_SYNC_MAX_INTERVAL

logger = logging.getLogger(__name__)


class ResilientDatabaseScheduler(DatabaseScheduler):
    """Keep celery beat alive across PostgreSQL restarts."""

    def all_as_schedule(self):
        close_old_connections()
        try:
            return super().all_as_schedule()
        except (DatabaseError, InterfaceError) as exc:
            close_old_connections()
            logger.warning(
                'DatabaseScheduler failed to refresh schedule after reconnect attempt: %r',
                exc,
            )
            if self._schedule is None:
                return {}
            return self._schedule

    @property
    def schedule(self):
        initial = update = False
        current_time = datetime.datetime.now()

        if self._initial_read:
            initial = update = True
            self._initial_read = False
            self._last_full_sync = current_time
        elif self.schedule_changed():
            update = True
            self._last_full_sync = current_time

        if not update:
            time_since_last_sync = (current_time - self._last_full_sync).total_seconds()
            if time_since_last_sync >= SCHEDULE_SYNC_MAX_INTERVAL:
                update = True
                self._last_full_sync = current_time

        if update:
            self.sync()
            self._schedule = self.all_as_schedule()
            if not initial:
                self._heap = []
                self._heap_invalidated = True
        return self._schedule
