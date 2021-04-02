from multiprocessing import Process, Queue
import datetime

from db import db

queue = Queue()

def transfer_process(user_id, data, current, destination):
    balance_after = current['balance'] - data['amount']
    old_data = {'user_id': user_id}
    new_data = {'$set': {'balance': balance_after, 'updated_at': datetime.datetime.now()}}

    if destination is None:
            dest = {}
            dest['user_id'] = data['target_user']
            dest['balance'] = 0
            dest['created_at'] = datetime.datetime.now()

            dest_balance = dest['balance']

            db.user_balance.insert(dest)
    else:
        dest_balance = destination['balance']

        try:
            db.user_balance.update_one(old_data, new_data)
            
            key = {'user_id': data['target_user']}
            row = {'user_id': data['target_user'], 'balance': dest_balance+data['amount'], 'updated_at': datetime.datetime.now()}

            db.user_balance.update(key, row, upsert=True)
            status = 'SUCCESS'
        except:
            status = 'FAILED'
    
    return balance_after, status