import os
import secrets
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from twilio.rest import Client

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET', 'dev-secret-key')

location_requests = {}
location_responses = {}

def get_twilio_client():
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    
    if not account_sid or not auth_token:
        return None
    
    return Client(account_sid, auth_token)

def get_base_url():
    return os.environ.get('REPL_SLUG', 'https://your-repl-url.repl.co')

@app.route('/')
def index():
    return render_template('index.html', requests=location_requests, responses=location_responses)

@app.route('/send-request', methods=['POST'])
def send_request():
    phone_number = request.form.get('phone_number')
    message_text = request.form.get('message', 'Someone has requested your location.')
    
    if not phone_number:
        return jsonify({'error': 'Phone number is required'}), 400
    
    request_id = secrets.token_urlsafe(16)
    
    location_requests[request_id] = {
        'phone_number': phone_number,
        'message': message_text,
        'created_at': datetime.now().isoformat(),
        'status': 'pending'
    }
    
    base_url = request.url_root.rstrip('/')
    location_url = f"{base_url}/share/{request_id}"
    
    client = get_twilio_client()
    
    if client:
        try:
            twilio_phone = os.environ.get('TWILIO_PHONE_NUMBER')
            if not twilio_phone:
                return jsonify({'error': 'TWILIO_PHONE_NUMBER not configured'}), 500
            
            full_message = f"{message_text}\n\nShare your location here: {location_url}"
            
            message = client.messages.create(
                body=full_message,
                from_=twilio_phone,
                to=phone_number
            )
            
            location_requests[request_id]['status'] = 'sent'
            location_requests[request_id]['sms_sid'] = message.sid
            
            return jsonify({
                'success': True,
                'request_id': request_id,
                'location_url': location_url,
                'message': 'SMS sent successfully'
            })
        except Exception as e:
            location_requests[request_id]['status'] = 'failed'
            location_requests[request_id]['error'] = str(e)
            return jsonify({'error': f'Failed to send SMS: {str(e)}'}), 500
    else:
        return jsonify({
            'success': False,
            'request_id': request_id,
            'location_url': location_url,
            'message': 'Twilio not configured. Please set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER in Secrets. You can manually send this link: ' + location_url
        })

@app.route('/share/<request_id>')
def share_location(request_id):
    if request_id not in location_requests:
        return "Invalid or expired location request", 404
    
    req_data = location_requests[request_id]
    return render_template('share.html', request_id=request_id, message=req_data.get('message'))

@app.route('/submit-location/<request_id>', methods=['POST'])
def submit_location(request_id):
    if request_id not in location_requests:
        return jsonify({'error': 'Invalid request ID'}), 404
    
    data = request.get_json()
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    
    if latitude is None or longitude is None:
        return jsonify({'error': 'Location coordinates required'}), 400
    
    location_responses[request_id] = {
        'latitude': latitude,
        'longitude': longitude,
        'submitted_at': datetime.now().isoformat(),
        'phone_number': location_requests[request_id]['phone_number']
    }
    
    location_requests[request_id]['status'] = 'received'
    
    return jsonify({'success': True, 'message': 'Location received successfully'})

@app.route('/view/<request_id>')
def view_location(request_id):
    if request_id not in location_responses:
        return "No location shared yet for this request", 404
    
    location = location_responses[request_id]
    return render_template('view.html', location=location, request_id=request_id)

@app.route('/api/requests')
def get_requests():
    return jsonify({
        'requests': location_requests,
        'responses': location_responses
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
