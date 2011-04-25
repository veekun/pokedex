import sys

from sqlalchemy.interfaces import ConnectionProxy
from datetime import datetime, timedelta
import traceback
from collections import defaultdict

class SQLATimerProxy(ConnectionProxy):
    """Simple connection proxy that keeps track of total time spent querying.
    """
    # props: http://techspot.zzzeek.org/?p=31
    def __init__(self, timer=None, timer_object=None):
        self.timer_object = timer_object
        self._timer = None
        if not self.timer:
            self.timer = timer or ResponseTimer()

    @property
    def timer(self):
        if self.timer_object:
            return self.timer_object.timer
        else:
            return self._timer

    @timer.setter
    def timer(self, new_timer):
        if self.timer_object:
            self.timer_object.timer = new_timer
        else:
            self._timer = new_timer

    def cursor_execute(self, execute, cursor, statement, parameters, context, executemany):
        try:
            return execute(cursor, statement, parameters, context)
        finally:
            try:
                self.timer.sql_queries += 1
            except (TypeError, AttributeError):
                # Might happen if SQL is run before Pylons is done starting
                pass

    def execute(self, conn, execute, clauseelement, *args, **kwargs):
        now = datetime.now()
        try:
            return execute(clauseelement, *args, **kwargs)
        finally:
            try:
                delta = datetime.now() - now
                self.timer.sql_time += delta
            except (TypeError, AttributeError):
                pass

class SQLAQueryLogProxy(SQLATimerProxy):
    """Extends the above to also log a summary of exactly what queries were
    executed, what userland code triggered them, and how long each one took.
    """
    def cursor_execute(self, execute, cursor, statement, parameters, context, executemany):
        now = datetime.now()
        try:
            super(SQLAQueryLogProxy, self).cursor_execute(
                execute, cursor, statement, parameters, context, executemany)
        finally:
            try:
                # Find who spawned this query.  Rewind up the stack until we
                # escape from sqlalchemy code -- including this file, which
                # contains proxy stuff
                caller = '(unknown)'
                for frame_file, frame_line, frame_func, frame_code in \
                    reversed(traceback.extract_stack()):

                    if (__file__.startswith(frame_file)
                        or '/sqlalchemy/' in frame_file
                        or 'db/multilang.py' in frame_file
                        or 'db/util.py' in frame_file
                        ):

                        continue

                    # OK, this is it
                    caller = "{0}:{1} in {2}".format(
                        frame_file, frame_line, frame_func)
                    break

                self.timer.sql_query_log[statement].append(dict(
                    parameters=parameters,
                    time=datetime.now() - now,
                    caller=caller,
                ))
            except (TypeError, AttributeError):
                pass

class ResponseTimer(object):
    """Nearly trivial class, used for tracking time and SQL queries.

    Properties are `total_time`, `sql_time`, and `sql_queries`.

    In SQL debug mode, `sql_query_log` is also populated.  Its keys are
    queries; values are dicts of parameters, time, and caller.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset the timer to its initial state
        """
        self._start_time = datetime.now()
        self._total_time = None

        self.from_cache = None

        # SQLAlchemy will add to these using the above proxy classes
        self.sql_time = timedelta()
        self.sql_queries = 0
        self.sql_query_log = defaultdict(list)

    @property
    def total_time(self):
        """Calculate and save the render time as soon as this is accessed
        """
        if self._total_time is None:
            self._total_time = self.time_so_far
        return self._total_time

    @property
    def time_so_far(self):
        return datetime.now() - self._start_time

    def text_log_report(self):
        """Return a textual report
        """
        def format_timedelta(delta):
            return "{0:.03f}".format(delta.seconds + delta.microseconds / 1000000.0)
        report = []
        items = []
        for query, data in self.sql_query_log.iteritems():
            delta = sum((d['time'] for d in data), timedelta())
            report += [u'x%s %ss' % (len(data), format_timedelta(delta))]
            try:
                import sqlparse
                query = sqlparse.format(query, reindent=True)
            except ImportError:
                query = '(Install sqlparse for a nicer printout)\n' + query
            report += ['      %s' % l for l in query.splitlines()]
            for instance in data:
                report += ['    %s: %s' % (format_timedelta(instance['time']), instance['caller'])]
                report += ['      %s' % (instance['parameters'])]
        report += ['Total time: %ss' % format_timedelta(self.total_time)]
        report += ['%s quer%s: %ss' % (
                self.sql_queries,
                'y' if self.sql_queries == 1 else 'ies',
                format_timedelta(self.sql_time),
            )]
        return '\n'.join(report)

