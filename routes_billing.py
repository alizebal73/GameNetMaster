"""
Billing and Session Management Routes for GameNetMaster
"""

import datetime
import uuid
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from app import app, db
from models import Client, Rate, ClientSession, BillingSettings, Payment

# Initialize default billing settings if not exist
@app.before_first_request
def initialize_billing():
    # Check if billing settings exist
    if BillingSettings.query.count() == 0:
        # Create default settings
        settings = BillingSettings(
            currency_symbol='$',
            payment_methods='Cash,Credit Card',
            receipt_header='Game Center Receipt',
            receipt_footer='Thank you for your business!',
            tax_percentage=0.0,
            enable_automatic_billing=True
        )
        db.session.add(settings)
        
        # Create a default rate
        default_rate = Rate(
            name='Standard Rate',
            description='Default hourly rate',
            hourly_rate=5.0,  # $5 per hour
            minimum_minutes=15,
            is_default=True,
            created_by_id=1  # Assume admin user has ID 1
        )
        db.session.add(default_rate)
        db.session.commit()
        
        # Update settings with default rate
        settings.default_rate_id = default_rate.id
        db.session.commit()

# Billing Dashboard
@app.route('/billing')
@login_required
def billing_dashboard():
    # Get recent sessions
    recent_sessions = ClientSession.query.order_by(ClientSession.start_time.desc()).limit(10).all()
    
    # Get quick stats
    today = datetime.datetime.now().date()
    today_start = datetime.datetime.combine(today, datetime.time.min)
    today_end = datetime.datetime.combine(today, datetime.time.max)
    
    sessions_today = ClientSession.query.filter(
        ClientSession.start_time.between(today_start, today_end)
    ).count()
    
    revenue_today = db.session.query(func.sum(Payment.amount)).filter(
        Payment.payment_time.between(today_start, today_end)
    ).scalar() or 0
    
    active_sessions = ClientSession.query.filter_by(is_active=True).count()
    unpaid_sessions = ClientSession.query.filter_by(payment_status='Pending').count()
    
    # Get settings
    settings = BillingSettings.query.first()
    
    return render_template(
        'billing/dashboard.html', 
        recent_sessions=recent_sessions,
        sessions_today=sessions_today,
        revenue_today=revenue_today,
        active_sessions=active_sessions,
        unpaid_sessions=unpaid_sessions,
        settings=settings
    )

# Rates Management
@app.route('/billing/rates')
@login_required
def manage_rates():
    rates = Rate.query.all()
    return render_template('billing/rates.html', rates=rates)

@app.route('/billing/rates/add', methods=['POST'])
@login_required
def add_rate():
    name = request.form.get('name')
    description = request.form.get('description', '')
    hourly_rate = float(request.form.get('hourly_rate', 0))
    minimum_minutes = int(request.form.get('minimum_minutes', 15))
    is_default = 'is_default' in request.form
    
    if not name or hourly_rate <= 0:
        flash('Rate name and a positive hourly rate are required', 'danger')
        return redirect(url_for('manage_rates'))
    
    new_rate = Rate(
        name=name,
        description=description,
        hourly_rate=hourly_rate,
        minimum_minutes=minimum_minutes,
        is_default=is_default,
        created_by_id=current_user.id
    )
    
    db.session.add(new_rate)
    
    # If this is set as default, remove default from others
    if is_default:
        Rate.query.filter(Rate.id != new_rate.id).update({'is_default': False})
        
        # Update billing settings to use this rate as default
        settings = BillingSettings.query.first()
        if settings:
            settings.default_rate_id = new_rate.id
    
    db.session.commit()
    flash(f'Rate "{name}" added successfully', 'success')
    return redirect(url_for('manage_rates'))

@app.route('/billing/rates/edit/<int:rate_id>', methods=['POST'])
@login_required
def edit_rate(rate_id):
    rate = Rate.query.get_or_404(rate_id)
    
    rate.name = request.form.get('name')
    rate.description = request.form.get('description', '')
    rate.hourly_rate = float(request.form.get('hourly_rate', 0))
    rate.minimum_minutes = int(request.form.get('minimum_minutes', 15))
    
    is_default = 'is_default' in request.form
    
    # If this is set as default, remove default from others
    if is_default and not rate.is_default:
        Rate.query.filter(Rate.id != rate.id).update({'is_default': False})
        
        # Update billing settings to use this rate as default
        settings = BillingSettings.query.first()
        if settings:
            settings.default_rate_id = rate.id
    
    rate.is_default = is_default
    db.session.commit()
    
    flash(f'Rate "{rate.name}" updated successfully', 'success')
    return redirect(url_for('manage_rates'))

@app.route('/billing/rates/delete/<int:rate_id>', methods=['POST'])
@login_required
def delete_rate(rate_id):
    rate = Rate.query.get_or_404(rate_id)
    
    # Check if this rate is being used by any sessions
    sessions_using_rate = ClientSession.query.filter_by(rate_id=rate_id).count()
    if sessions_using_rate > 0:
        flash(f'Cannot delete rate "{rate.name}" because it is used by {sessions_using_rate} sessions', 'danger')
        return redirect(url_for('manage_rates'))
    
    # Check if this is the default rate
    if rate.is_default:
        flash(f'Cannot delete rate "{rate.name}" because it is set as the default rate', 'danger')
        return redirect(url_for('manage_rates'))
    
    db.session.delete(rate)
    db.session.commit()
    
    flash(f'Rate "{rate.name}" deleted successfully', 'success')
    return redirect(url_for('manage_rates'))

# Session Management
@app.route('/billing/sessions')
@login_required
def manage_sessions():
    # Get filter parameters
    status = request.args.get('status', 'all')
    client_id = request.args.get('client_id')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Build query
    query = ClientSession.query
    
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'closed':
        query = query.filter_by(is_active=False)
    elif status == 'pending':
        query = query.filter_by(payment_status='Pending')
    elif status == 'paid':
        query = query.filter_by(payment_status='Paid')
    
    if client_id:
        query = query.filter_by(client_id=client_id)
    
    if date_from:
        date_from = datetime.datetime.strptime(date_from, '%Y-%m-%d')
        query = query.filter(ClientSession.start_time >= date_from)
    
    if date_to:
        date_to = datetime.datetime.strptime(date_to, '%Y-%m-%d')
        date_to = datetime.datetime.combine(date_to, datetime.time.max)  # End of day
        query = query.filter(ClientSession.start_time <= date_to)
    
    # Order by newest first
    sessions = query.order_by(ClientSession.start_time.desc()).all()
    
    # Get clients for filter dropdown
    clients = Client.query.all()
    
    # Get rates for new session form
    rates = Rate.query.all()
    
    return render_template(
        'billing/sessions.html',
        sessions=sessions,
        clients=clients,
        rates=rates,
        status=status,
        client_id=client_id,
        date_from=date_from,
        date_to=date_to
    )

@app.route('/billing/sessions/start', methods=['POST'])
@login_required
def start_session():
    client_id = request.form.get('client_id')
    user_name = request.form.get('user_name', '')
    rate_id = request.form.get('rate_id')
    
    if not client_id:
        flash('Client selection is required', 'danger')
        return redirect(url_for('manage_sessions'))
    
    # Check if client already has an active session
    active_session = ClientSession.query.filter_by(client_id=client_id, is_active=True).first()
    if active_session:
        flash(f'Client already has an active session (started at {active_session.start_time})', 'warning')
        return redirect(url_for('manage_sessions'))
    
    # If no rate specified, use default
    if not rate_id:
        settings = BillingSettings.query.first()
        if settings and settings.default_rate_id:
            rate_id = settings.default_rate_id
        else:
            default_rate = Rate.query.filter_by(is_default=True).first()
            if default_rate:
                rate_id = default_rate.id
    
    # Create new session
    new_session = ClientSession(
        client_id=client_id,
        user_name=user_name,
        rate_id=rate_id,
        start_time=datetime.datetime.now(),
        is_active=True,
        payment_status='Pending'
    )
    
    db.session.add(new_session)
    db.session.commit()
    
    flash('Session started successfully', 'success')
    return redirect(url_for('manage_sessions'))

@app.route('/billing/sessions/end/<int:session_id>', methods=['POST'])
@login_required
def end_session(session_id):
    session = ClientSession.query.get_or_404(session_id)
    
    if not session.is_active:
        flash('This session is already closed', 'warning')
        return redirect(url_for('manage_sessions'))
    
    # End session
    end_time = datetime.datetime.now()
    session.end_time = end_time
    session.is_active = False
    
    # Calculate duration
    duration = (end_time - session.start_time).total_seconds() / 60  # in minutes
    session.duration_minutes = int(duration)
    
    # Calculate billing if rate is set
    if session.rate_id:
        rate = Rate.query.get(session.rate_id)
        if rate:
            # Apply minimum billing time
            billable_minutes = max(session.duration_minutes, rate.minimum_minutes)
            
            # Calculate amount
            hourly_rate = rate.hourly_rate
            billed_amount = (billable_minutes / 60) * hourly_rate
            
            # Add tax if applicable
            settings = BillingSettings.query.first()
            if settings and settings.tax_percentage > 0:
                tax_amount = billed_amount * (settings.tax_percentage / 100)
                billed_amount += tax_amount
            
            session.billed_amount = round(billed_amount, 2)
    
    db.session.commit()
    flash('Session ended successfully', 'success')
    return redirect(url_for('view_session', session_id=session_id))

@app.route('/billing/sessions/view/<int:session_id>')
@login_required
def view_session(session_id):
    session = ClientSession.query.get_or_404(session_id)
    settings = BillingSettings.query.first()
    payment_methods = settings.payment_methods.split(',') if settings else ['Cash']
    
    return render_template(
        'billing/view_session.html',
        session=session,
        settings=settings,
        payment_methods=payment_methods
    )

@app.route('/billing/sessions/create_payment/<int:session_id>', methods=['POST'])
@login_required
def create_payment(session_id):
    session = ClientSession.query.get_or_404(session_id)
    
    if session.payment_status == 'Paid':
        flash('This session is already paid', 'warning')
        return redirect(url_for('view_session', session_id=session_id))
    
    amount = float(request.form.get('amount', 0))
    payment_method = request.form.get('payment_method', 'Cash')
    notes = request.form.get('notes', '')
    
    if amount <= 0:
        flash('Payment amount must be greater than zero', 'danger')
        return redirect(url_for('view_session', session_id=session_id))
    
    # Generate receipt number
    receipt_number = f"R-{datetime.datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    # Create payment
    payment = Payment(
        session_id=session_id,
        amount=amount,
        payment_method=payment_method,
        receipt_number=receipt_number,
        notes=notes,
        created_by_id=current_user.id
    )
    
    db.session.add(payment)
    
    # Update session
    session.payment_status = 'Paid'
    
    db.session.commit()
    flash(f'Payment of {amount} recorded successfully. Receipt #: {receipt_number}', 'success')
    return redirect(url_for('view_session', session_id=session_id))

@app.route('/billing/sessions/waive/<int:session_id>', methods=['POST'])
@login_required
def waive_payment(session_id):
    session = ClientSession.query.get_or_404(session_id)
    
    if session.payment_status == 'Paid':
        flash('This session is already paid', 'warning')
        return redirect(url_for('view_session', session_id=session_id))
    
    reason = request.form.get('reason', '')
    
    session.payment_status = 'Waived'
    session.notes = f"Payment waived. Reason: {reason}"
    
    db.session.commit()
    flash('Payment waived successfully', 'success')
    return redirect(url_for('view_session', session_id=session_id))

# Billing Settings
@app.route('/billing/settings')
@login_required
def billing_settings():
    settings = BillingSettings.query.first()
    rates = Rate.query.all()
    
    return render_template('billing/settings.html', settings=settings, rates=rates)

@app.route('/billing/settings/update', methods=['POST'])
@login_required
def update_billing_settings():
    settings = BillingSettings.query.first()
    
    settings.default_rate_id = request.form.get('default_rate_id')
    settings.currency_symbol = request.form.get('currency_symbol', '$')
    settings.payment_methods = request.form.get('payment_methods', 'Cash,Credit Card')
    settings.receipt_header = request.form.get('receipt_header', '')
    settings.receipt_footer = request.form.get('receipt_footer', '')
    settings.tax_percentage = float(request.form.get('tax_percentage', 0))
    settings.enable_automatic_billing = 'enable_automatic_billing' in request.form
    settings.last_updated = datetime.datetime.now()
    settings.updated_by_id = current_user.id
    
    db.session.commit()
    flash('Billing settings updated successfully', 'success')
    return redirect(url_for('billing_settings'))