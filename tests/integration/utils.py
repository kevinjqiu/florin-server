from florin import db
from tests.integration import app


def reset_database():
    session = app.session
    for clazz in (db.AccountBalance, db.Category, db.Transaction, db.Account, db.FileUpload):
        session.query(clazz).delete()
    session.commit()
    session.expunge_all()


def db_fixture(db_class):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            response = fn(*args, **kwargs)
            session = app.session
            if isinstance(response, list):
                for r in response:
                    session.add(db_class(**r))
            else:
                session.add(db_class(**response))
            session.commit()
            return response
        return wrapper
    return decorator
