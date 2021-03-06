import math
from florin.db import Transaction, db_transaction
from asbool import asbool
from .params import get_date_range_params
from .categories import TBD_CATEGORY_ID, INTERNAL_TRANSFER_CATEGORY_ID
from . import accounts, exceptions
from sqlalchemy import and_, not_


class Paginator(object):
    def __init__(self, args):
        self.per_page = int(args.get('perPage', '10'))
        self.page = int(args.get('page', '1'))
        self.total = None

    def __call__(self, query):
        total = query.count()
        self.total_pages = int(math.ceil(1.0 * total / self.per_page))
        return query.limit(self.per_page).offset((self.page - 1) * self.per_page)


class TransactionFilter(object):
    def __init__(self, account, args):
        self.start_date, self.end_date = get_date_range_params(args)
        self.include_internal_transfer = asbool(args.get('includeInternalTransfer', 'false'))
        self.only_uncategorized = asbool(args.get('onlyUncategorized', 'false'))
        self.account = account

    def __call__(self, query):
        query = query.filter(and_(Transaction.date >= self.start_date, Transaction.date <= self.end_date))

        if not self.include_internal_transfer:
            query = query.filter(Transaction.category_id != INTERNAL_TRANSFER_CATEGORY_ID)

        if self.only_uncategorized:
            query = query.filter(Transaction.category_id == TBD_CATEGORY_ID)

        if self.account is not accounts.ALL_ACCOUNTS:
            query = query.filter(Transaction.account_id == self.account.id)

        return query


class Sorter(object):
    def __init__(self, clazz, args, default_order):
        self.clazz = clazz
        self.order_by = args.get('orderBy', default_order)

    def get_order(self, field_name, direction):
        order = None
        if direction == 'asc':
            order = getattr(self.clazz, field_name, None)
        elif direction == 'desc':
            field = getattr(self.clazz, field_name, None)
            if field:
                order = field.desc()

        return order

    def __call__(self, query):
        field_name, direction = self.order_by.split(':')
        order = self.get_order(field_name, direction)

        if order is None:
            raise exceptions.InvalidRequest('Invalid orderBy param: "{}"'.format(self.order_by))
        return query.order_by(order)


def get(app, account_id, args):
    session = app.session
    account = accounts.get_by_id(app, account_id)
    filter = TransactionFilter(account, args)
    paginator = Paginator(args)
    sorter = Sorter(Transaction, args, 'date:desc')

    query = reduce(lambda query, fn: fn(query),
                   [filter, sorter, paginator],
                   session.query(Transaction).filter(not_(Transaction.deleted)))
    transactions = query.all()

    return {
        'total_pages': paginator.total_pages,
        'current_page': paginator.page,
        'transactions': [txn.to_dict() for txn in transactions]
    }


def delete(app, transaction_id):
    query = app.session.query(Transaction).filter_by(id=transaction_id)
    if query.count() != 1:
        raise exceptions.ResourceNotFound()

    transaction = query.one()
    with db_transaction(app.session) as session:
        transaction.deleted = True
        session.add(transaction)
    return {'transactionId': transaction_id}


def update(app, transaction_id, request_json):
    query = app.session.query(Transaction).filter_by(id=transaction_id)
    if query.count() != 1:
        raise exceptions.ResourceNotFound()

    transaction = query.one()
    for key, value in request_json.items():
        setattr(transaction, key, value)

    with db_transaction(app.session) as session:
        session.add(transaction)
    transaction = app.session.query(Transaction).filter_by(id=transaction_id).one()
    return {'transactions': [transaction.to_dict()]}
