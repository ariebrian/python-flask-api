from flask import Flask, request
import pymongo
import json
import uuid
import datetime

from flask_jwt_extended import create_access_token
from flask_jwt_extended import create_access_token
from flask_jwt_extended import create_refresh_token
from flask_jwt_extended import get_jwt_identity, get_jwt
from flask_jwt_extended import jwt_required
from flask_jwt_extended import JWTManager
from datetime import timedelta

app = Flask(__name__)

app.config["JWT_SECRET_KEY"] = "secret"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=30)
jwt = JWTManager(app)


client = pymongo.MongoClient('mongodb+srv://brian:jGKGtNwW9DjN6Jw@cluster0.qep55.mongodb.net/')
db = client.spin

@app.route('/register', methods=['POST'])
def register():
    response = {}
    data = json.loads(request.data)
    phone_number = data['phone_number']
    check_number = db.user.find_one({'phone_number': phone_number})
    if check_number is None:
        data['user_id'] = str(uuid.uuid4())
        data['created_date'] = datetime.datetime.now()
        db.user.insert(data)
        data.pop('_id', None)
        data.pop('pin', None)
        response['status'] = 'SUCCESS'
        response['result'] = data
        return response
    else:
        response['message'] = 'Phone Number already registered'
        return response

@app.route('/login', methods=['POST'])
def login():
    response = {}
    result = {}
    data = json.loads(request.data)
    phone_number = data['phone_number']
    pin = data['pin']
    check_user = db.user.find_one({'phone_number': phone_number, 'pin':pin})
    if check_user is None:
        response['message'] = "Phone number and pin doesn't match."
        return response
    else:
        user_id = check_user['user_id']
        additional_claims = {
            "phone_number": check_user['phone_number'], 
            "first_name": check_user['first_name'],
            'last_name': check_user['last_name'],
            'address': check_user['address']}
        result['access_token'] = create_access_token(identity=user_id, additional_claims=additional_claims)
        result['refresh_token'] = create_refresh_token(identity=user_id, additional_claims=additional_claims)
        
        key = {'user_id': user_id}
        row = {'user_id': user_id, 'access_token': result['access_token'], 'refresh_token': result['refresh_token']}

        db.token.update(key, row, upsert=True)
        
        result['user_id'] = user_id
        response['status'] = 'SUCCESS'
        response['result'] = result
        return response

@app.route('/topup', methods=['POST'])
@jwt_required()
def topup():
    response = {}
    result = {}
    data_topup = {}
    data = json.loads(request.data)
    user_id = get_jwt_identity()

    current_data = db.user_balance.find_one({'user_id': user_id})
    
    if current_data is not None:
        balance_after = current_data['balance'] + data['amount']
        old_data = {'user_id': user_id}
        new_data = {'$set': {'balance': balance_after, 'updated_at': datetime.datetime.now()}}

        try:
            db.user_balance.update_one(old_data, new_data)
            data_topup['status'] = 'SUCCESS'
        except:
            data_topup['status'] = 'FAILED'

        result['balance_before'] = current_data['balance']
        
    else:
        balance_after = data['amount']
        
        result['balance_before'] = 0

        data_balance = {}
        data_balance['user_id'] = user_id
        data_balance['balance'] = balance_after
        data_balance['created_at'] = datetime.datetime.now() 
        
        try:
            db.user_balance.insert(data_balance)
            data_topup['status'] = 'SUCCESS'
        except:
            data_topup['status'] = 'FAILED'
        
    

    data_topup['top_up_id'] = str(uuid.uuid4())
    data_topup['user_id'] = get_jwt_identity()
    data_topup['transaction_type'] = 'CREDIT'
    data_topup['amount'] = data['amount']
    data_topup['remarks'] = ''
    data_topup['balance_before'] = result['balance_before']
    data_topup['balance_after'] = balance_after
    data_topup['created_date'] = datetime.datetime.now()
    
    db.transaction.insert(data_topup)

    result['top_up_id'] = data_topup['top_up_id']
    result['amount_top_up'] = data['amount']
    result['balance_after'] = balance_after
    result['created_date'] = data_topup['created_date']

    response['status'] = 'SUCCESS'
    response['result'] = result
    
    return response

@app.route('/pay', methods=['POST'])
@jwt_required()
def payment():
    response = {}
    data = json.loads(request.data)
    user_id = get_jwt_identity()
    result = {}
    data_payment = {}

    current_balance = db.user_balance.find_one({'user_id': user_id})
    
    if current_balance is None or current_balance['balance'] < data['amount']:
        response['message'] = 'balance not enough'
        return response
    else:
        balance_after = current_balance['balance'] - data['amount']
        old_data = {'user_id': user_id}
        new_data = {'$set': {'balance': balance_after, 'updated_at': datetime.datetime.now()}}

        try:
            db.user_balance.update_one(old_data, new_data)
            data_payment['status'] = 'SUCCESS'
        except:
            data_payment['status'] = 'FAILED'

        result['balance_before'] = current_balance['balance']  
    

    data_payment['payment_id'] = str(uuid.uuid4())
    data_payment['user_id'] = get_jwt_identity()
    data_payment['transaction_type'] = 'DEBIT'
    data_payment['amount'] = data['amount']
    data_payment['remarks'] = data['remarks']
    data_payment['balance_before'] = result['balance_before']
    data_payment['balance_after'] = balance_after
    data_payment['created_date'] = datetime.datetime.now()
    
    db.transaction.insert(data_payment)

    result['payment_id'] = data_payment['payment_id']
    result['amount'] = data['amount']
    result['remarks'] = data['remarks']
    result['balance_after'] = balance_after
    result['created_date'] = data_payment['created_date']

    response['status'] = 'SUCCESS'
    response['result'] = result
    
    return response

@app.route('/transfer', methods=['POST'])
@jwt_required()
def transfer():
    response = {}
    data = json.loads(request.data)
    user_id = get_jwt_identity()
    result = {}
    data_transfer = {}

    current_balance = db.user_balance.find_one({'user_id': user_id})
    destination_balance = db.user_balance.find_one({'user_id': data['target_user']})
    
    if current_balance is None or current_balance['balance'] < data['amount']:
        response['message'] = 'balance not enough'
        return response
    else:
        balance_after = current_balance['balance'] - data['amount']
        old_data = {'user_id': user_id}
        new_data = {'$set': {'balance': balance_after, 'updated_at': datetime.datetime.now()}}

        if destination_balance is None:
            dest = {}
            dest['user_id'] = data['target_user']
            dest['balance'] = 0
            dest['created_at'] = datetime.datetime.now()

            dest_balance = dest['balance']

            db.user_balance.insert(dest)
        else:
            dest_balance = destination_balance['balance']

        try:
            db.user_balance.update_one(old_data, new_data)
            
            key = {'user_id': data['target_user']}
            row = {'user_id': data['target_user'], 'balance': dest_balance+data['amount'], 'updated_at': datetime.datetime.now()}

            db.user_balance.update(key, row, upsert=True)
            data_transfer['status'] = 'SUCCESS'
        except:
            data_transfer['status'] = 'FAILED'

        result['balance_before'] = current_balance['balance']  
    

    data_transfer['transfer_id'] = str(uuid.uuid4())
    data_transfer['user_id'] = get_jwt_identity()
    data_transfer['transaction_type'] = 'DEBIT'
    data_transfer['amount'] = data['amount']
    data_transfer['remarks'] = data['remarks']
    data_transfer['balance_before'] = result['balance_before']
    data_transfer['balance_after'] = balance_after
    data_transfer['created_date'] = datetime.datetime.now()
    
    db.transaction.insert(data_transfer)

    result['transfer_id'] = data_transfer['transfer_id']
    result['amount'] = data['amount']
    result['remarks'] = data['remarks']
    result['balance_after'] = balance_after
    result['created_date'] = data_transfer['created_date']

    response['status'] = 'SUCCESS'
    response['result'] = result
    
    return response


@app.route('/transactions', methods=['GET'])
@jwt_required()
def transaction():
    response = {}
    user_id = get_jwt_identity()
    data = []

    query = db.transaction.find({'user_id': user_id}, {"_id": 0}).sort('created_date', -1)
    for i in query:
        data.append(i)
    
    response['message'] = 'SUCCESS'
    response['result'] = data
    return response


@app.route('/profile', methods=['PUT'])
@jwt_required()
def profile():
    response = {}
    user_id = get_jwt_identity()
    data = json.loads(request.data)

    address = data['address']

    check_user = db.user.find_one({'user_id': user_id})

    update = datetime.datetime.now()
    
    db.user.update({'user_id': user_id},{'$set': {'address': address, 'updated_at': update}})
    
    response['status'] = 'SUCCESS'
    response['result'] = {
        'user_id': user_id,
        'first_name': check_user['first_name'],
        'last_name': check_user['last_name'],
        'phone_number': check_user['phone_number'],
        'address': address,
        'updated_date': update
    }
    return response