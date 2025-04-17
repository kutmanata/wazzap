from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from app import app, db
from app.models import User, Group, Message

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Колдонуучу аты жана email текшерүү
        if User.query.filter_by(username=username).first():
            flash('Мындай колдонуучу аты бар', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Мындай email бар', 'danger')
            return render_template('register.html')
        
        # Жаңы колдонуучуну түзүү
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Сиз ийгиликтүү катталдыңыз!', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            flash('Колдонуучу аты же пароль туура эмес', 'danger')
            return render_template('login.html')
        
        login_user(user)
        return redirect(url_for('chat'))
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/chat')
@login_required
def chat():
    contacts = current_user.contacts_list.all()
    groups = current_user.groups
    for contact in contacts:
        contact.last_message = contact.get_last_message_with(current_user.id)
    for group in groups:
        group.last_message = group.get_last_message()
    return render_template('chat.html', contacts=contacts, groups=groups)

@app.route('/new_contact', methods=['GET', 'POST'])
@login_required
def new_contact():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('Мындай колдонуучу табылган жок', 'danger')
            return redirect(url_for('new_contact'))
        
        if current_user.is_contact(user):
            flash('Бул колдонуучу сиздин контакттарыңызда бар', 'warning')
            return redirect(url_for('chat'))
        
        current_user.add_contact(user)
        db.session.commit()
        
        flash('Контакт ийгиликтүү кошулду!', 'success')
        return redirect(url_for('chat'))
    
    return render_template('new_contact.html') 

@app.route('/new_group', methods=['GET', 'POST'])
@login_required
def new_group():
    if request.method == 'POST':
        name = request.form.get('name')
        
        if not name:
            flash('Группанын аты бош боло албайт', 'danger')
            return redirect(url_for('new_group'))
        
        group = Group(name=name, creator_id=current_user.id)
        group.members.append(current_user)
        db.session.add(group)
        db.session.commit()
        
        flash('Жаңы группа түзүлдү!', 'success')
        return redirect(url_for('group_info', group_id=group.id))
    
    return render_template('new_group.html')

@app.route('/new_subgroup', methods=['GET', 'POST'])
@login_required
def new_subgroup():
    if request.method == 'POST':
        name = request.form.get('name')
        parent_group_id = request.form.get('parent_group')
        
        if not name:
            flash('Подгруппанын аты бош боло албайт', 'danger')
            return redirect(url_for('new_subgroup'))
        
        # Жөнөкөйлөтүү үчүн биз подгруппаны жөнөкөй группа катары түзөбүз
        group = Group(name=name, creator_id=current_user.id)
        group.members.append(current_user)
        db.session.add(group)
        db.session.commit()
        
        flash('Жаңы подгруппа түзүлдү!', 'success')
        return redirect(url_for('group_info', group_id=group.id))
    
    groups = current_user.groups
    return render_template('new_subgroup.html', groups=groups)

@app.route('/group/<int:group_id>')
@login_required
def group_info(group_id):
    group = Group.query.get_or_404(group_id)
    members = group.members.all()
    return render_template('group_info.html', group=group, members=members)

# API для билдирүүлөрдү жөнөтүү жана алуу
@app.route('/api/send_message', methods=['POST'])
@login_required
def send_message():
    data = request.json
    content = data.get('content')
    recipient_id = data.get('recipient_id')
    group_id = data.get('group_id')
    
    if not content:
        return jsonify({'error': 'Билдирүү бош боло албайт'}), 400
    
    message = Message(content=content, sender_id=current_user.id)
    
    if recipient_id:
        message.recipient_id = recipient_id
    elif group_id:
        message.group_id = group_id
    else:
        return jsonify({'error': 'Алуучу же группа көрсөтүлүшү керек'}), 400
    
    db.session.add(message)
    db.session.commit()
    
    return jsonify({'message': 'Билдирүү жөнөтүлдү', 'message_id': message.id}), 200

@app.route('/api/get_messages', methods=['GET'])
@login_required
def get_messages():
    contact_id = request.args.get('contact_id')
    group_id = request.args.get('group_id')
    
    if contact_id:
        # Жеке билдирүүлөр
        sent_messages = Message.query.filter_by(sender_id=current_user.id, recipient_id=contact_id).all()
        received_messages = Message.query.filter_by(sender_id=contact_id, recipient_id=current_user.id).all()
        messages = sent_messages + received_messages
        messages.sort(key=lambda x: x.created_at)
    elif group_id:
        # Группадагы билдирүүлөр
        messages = Message.query.filter_by(group_id=group_id).order_by(Message.created_at).all()
    else:
        return jsonify({'error': 'Контакт же группа ID көрсөтүлүшү керек'}), 400
    
    messages_json = []
    for msg in messages:
        messages_json.append({
            'id': msg.id,
            'content': msg.content,
            'sender_id': msg.sender_id,
            'sender_name': User.query.get(msg.sender_id).username,
            'is_mine': msg.sender_id == current_user.id,
            'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'is_read': msg.is_read
        })
    
    return jsonify({'messages': messages_json}), 200