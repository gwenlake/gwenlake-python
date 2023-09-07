import logging
from sqlalchemy import text, create_engine


logger = logging.getLogger(__name__)


class SQLStore(object):

    def __init__(self, db, bind=None):
        try:
            if isinstance(db, str):
                self.engine = create_engine(db)
            else:
                self.engine = db.engines[bind]
        except Exception as e:
            logger.warning(str(e))

    def queryone(self, sql):
        if not self.engine:
            logger.warning("No SQLAlchemy engine.")
            return None
        try:
            with self.engine.connect() as connection:
                rows = connection.execute(text(sql)).first()
        except Exception as e:
            logger.warning(str(e))
        if not rows:
            return None
        return rows._asdict()

    def query(self, sql, page=None, per_page=25):
        if not self.engine:
            logger.warning("No SQLAlchemy engine.")
            return []

        if page is not None:
            start_at = (page-1) * per_page
            sql += f" LIMIT {start_at}, {per_page}"

        try:
            with self.engine.connect() as connection:
                rows = connection.execute(text(sql)).all()
        except Exception as e:
            logger.warning(str(e))
            return []

        if not rows:
            return []

        return [row._asdict() for row in rows]
