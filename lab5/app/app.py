
import base64
from flask import Flask, render_template, session, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from mysqldb import DBConnector
from mysql.connector.errors import DatabaseError
app = Flask(__name__)
application = app
app.config.from_pyfile('config.py')

db_connector = DBConnector(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth"
login_manager.login_message = "Войдите, чтобы просматривать содержимое данной страницы"
login_manager.login_message_category = "warning"

class User(UserMixin):
    def __init__(self, user_id, login, role_name):
        self.id = user_id
        self.login = login
        self.role_name = role_name

    def is_driver(self):
        return self.role_name == 'водитель'

    def is_client(self):
        return self.role_name == 'клиент'

def get_user_list():
    return [{"user_id": "14", "login": "root", "password": "admin"}, 
            {"user_id": "64", "login": "guest", "password": "c1sc0"}, 
            {"user_id": "98", "login": "user", "password": "example"}]

CREATE_USER_FIELDS = ['login', 'password','date_birth', 'first_name', 'last_name', 'surname', 'email','phone_num','role_id', 'class', 'pass_info', 'user_image']
EDIT_USER_FIELDS = ['last_name', 'first_name', 'surname', 'email','phone_num', 'user_image']
CHANGE_PASS_FIELDS=['password','newpass','newpass2']
CREATE_ORDER_FIELDS = ['source_address', 'destination_address', 'order_weight', 'cargo_id', 'date_order', 'time_order', 'car_type_id','user_descr']
EDIT_ORDER_FIELDS = ['source_address', 'destination_address', 'order_weight', 'cargo_id', 'date_order', 'time_order', 'car_type_id']

@login_manager.user_loader
def load_user(user_id):
    query = "SELECT u.user_id, u.login, r.role_name FROM users u JOIN roles r ON u.role_id = r.role_id WHERE user_id=%s"
    with db_connector.connect().cursor(named_tuple=True) as cursor:
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()
    if user:
        return User(user.user_id, user.login, user.role_name)
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/info')
def info():
    session['counter'] = session.get('counter', 0) + 1

    return render_template('info.html')

@app.route('/auth', methods=["GET", "POST"])
def auth():
    if request.method == "GET":
        return render_template("auth.html")
    
    login = request.form.get("login", "")
    password = request.form.get("password", "") 
    remember = request.form.get("remember") == "on"


    query = 'SELECT user_id, login, role_name FROM users join roles'
    'on users.role_id = roles.role_id WHERE login=%s AND password=SHA2(%s, 256)'
    
    print(query)

    with db_connector.connect().cursor(named_tuple=True) as cursor:

        cursor.execute(query, (login, password))

        print(cursor.statement)

        user = cursor.fetchone()

    if user:
        login_user(User(user.user_id, user.login,user.role_name), remember=remember)
        flash("Успешная авторизация", category="success")
        target_page = request.args.get("next", url_for("index"))
        return redirect(target_page)

    flash("Введены некорректные учётные данные пользователя", category="danger")    

    return render_template("auth.html")
def get_roles():
    query = "SELECT * FROM roles"

    with db_connector.connect().cursor(named_tuple=True) as cursor:
        cursor.execute(query)
        roles = cursor.fetchall()

    return roles

import base64

@app.route('/users')
@login_required
def users():
    query = 'SELECT u.*, d.pass_info, d.classdriver FROM users u LEFT JOIN drivers_pro d ON u.user_id = d.driver_id WHERE u.user_id=%s'
    
    with db_connector.connect().cursor(named_tuple=True) as cursor:
        cursor.execute(query, (current_user.id,))
        data = cursor.fetchall()
    users_data = []
    for user in data:
        if user.user_image:
            user_data = dict(user._asdict())  
            user_data['user_image'] = base64.b64encode(user.user_image).decode('utf-8')
            users_data.append(user_data)
        else:
            users_data.append(dict(user._asdict()))

    return render_template("users.html", users=users_data)


@app.route('/orders')
@login_required
def orders():
    print(f"Текущая роль пользователя: {current_user.role_name}")  # отладочное сообщение
    orders = [] 
    per_page = 5  
    page = request.args.get('page', 1, type=int)
    total_pages=0
    if current_user.is_client():
        query = 'SELECT COUNT(*) AS total_count FROM orders WHERE user_id=%s'
        with db_connector.connect().cursor(named_tuple=True) as cursor:
            cursor.execute(query, (current_user.id,))
            total_orders = cursor.fetchone().total_count

        total_pages = (total_orders + per_page - 1) // per_page
        query = (
            'SELECT * FROM orders WHERE user_id=%s and not(order_status="Отменен")'
            'LIMIT %s OFFSET %s'
        )
        with db_connector.connect().cursor(named_tuple=True) as cursor:
            cursor.execute(query, (current_user.id, per_page, (page - 1) * per_page))
            orders = cursor.fetchall()
            print(orders)
    elif current_user.is_driver():
        query = 'SELECT COUNT(*) AS total_count FROM orders WHERE order_status="В обработке"'
        with db_connector.connect().cursor(named_tuple=True) as cursor:
            cursor.execute(query)
            total_orders = cursor.fetchone().total_count

        total_pages = (total_orders + per_page - 1) // per_page
        query = (
            'SELECT order_id, source_address, destination_address, date_order, time_order '
            'FROM orders WHERE order_status="В обработке" '
            'LIMIT %s OFFSET %s'
        )
        with db_connector.connect().cursor(named_tuple=True) as cursor:
            cursor.execute(query, (per_page, (page - 1) * per_page))
            orders = cursor.fetchall()

    return render_template("orders.html", orders=orders, page=page, total_pages=total_pages)


@app.route('/orders/new', methods=['GET', 'POST'])
@login_required
def create_order():
    if request.method == 'POST':
        order = get_form_data1(CREATE_ORDER_FIELDS + ['order_cost', 'money_status'])
        order['user_id'] = current_user.id
        order['order_status'] = "В обработке"
        import random
        order['order_cost'] = random.randint(7000, 20000)
        query = (
            "INSERT INTO orders (user_id, source_address, destination_address, order_weight, cargo_id, date_order, time_order, car_type_id,"
            "order_cost, money_status, order_status, user_descr) "
            "VALUES (%(user_id)s, %(source_address)s, %(destination_address)s, %(order_weight)s, %(cargo_id)s, %(date_order)s,"
            "%(time_order)s, %(car_type_id)s, %(order_cost)s, %(money_status)s, %(order_status)s,%(user_descr)s )"
        )

        try:
            with db_connector.connect().cursor(named_tuple=True) as cursor:
                cursor.execute(query, order)
                db_connector.connect().commit()
            flash("Заказ успешно создан", category="success")
            return redirect(url_for('orders'))
        except DatabaseError as error:
            flash(f'Ошибка создания заказа! {error}', category="danger")
            db_connector.connect().rollback()

    return render_template("order_form.html", order={})
@app.route('/orders/<int:order_id>/cancel', methods=["POST"])
@login_required
def cancel_order(order_id):
    if current_user.is_driver():
        query_update_order = "UPDATE orders SET order_status='В обработке' WHERE order_id=%s AND driver_id=%s"
        try:
            with db_connector.connect().cursor() as cursor:
                cursor.execute(query_update_order, (order_id, current_user.id))
                db_connector.connect().commit()
            notification_description = "Водитель отказался от выполнения заказа"
            insert_notification_query = "INSERT INTO notifications (user_id, order_id, description, button) VALUES (%s, %s, %s, '0')"
            query_get_client_id = "SELECT user_id FROM orders WHERE order_id = %s"
            
            with db_connector.connect().cursor() as cursor:
                cursor.execute(query_get_client_id, (order_id,))
                client_id = cursor.fetchone()
                if client_id:
                    cursor.execute(insert_notification_query, (client_id[0], order_id, notification_description))
                    db_connector.connect().commit()

            flash("Отказ от заказа успешно отправлен", category="success")
        except DatabaseError as error:
            flash(f'Ошибка при отказе от заказа: {error}', category="danger")
            db_connector.connect().rollback()
    else:
        flash("Только водители могут отказаться от заказа", category="danger")
    return redirect(url_for('orders'))




@app.route('/orders/<int:order_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_order(order_id):
    query = "SELECT * FROM orders WHERE order_id = %s AND user_id = %s"
    
    with db_connector.connect().cursor(named_tuple=True) as cursor:
        cursor.execute(query, (order_id, current_user.id))
        order = cursor.fetchone()
    
    if request.method == "POST":
        updated_order = {
            'date_order': request.form.get('date_order'),
            'time_order': request.form.get('time_order')
        }
        
        if order.order_status == 'Выполнение заказа':
            flash("Вы не можете изменить заказ, так как он взят в работу водителем", category="danger")
            return redirect(url_for('orders'))
        
        if order.order_status == 'Взят в работу':
            notify_driver(order_id, f"Пользователь отправил запрос на изменение заказа номер {order_id}",
                          1, request.form.get('date_order'), request.form.get('time_order'), request.form.get('user_descr'))
            flash("Запрос на изменение заказа отправлен", category="success")
            return redirect(url_for('orders'))
        else:
            query = (
                "UPDATE orders SET date_order=%(date_order)s, time_order=%(time_order)s "
                "WHERE order_id=%(order_id)s"
            )
        
            try:
                with db_connector.connect().cursor(named_tuple=True) as cursor:
                    cursor.execute(query, dict(updated_order, order_id=order_id))
                    db_connector.connect().commit()
            
                flash("Заказ изменен", category="success")
           
            except DatabaseError as error:
                flash(f'Ошибка редактирования заказа! {error}', category="danger")
                db_connector.connect().rollback()
            return redirect(url_for('orders'))
    return render_template("edit_order.html", order=order)

@app.route('/orders/<int:order_id>/accept', methods=["GET","POST"])
@login_required
def accept_order(order_id):
    if request.method == 'POST':
        if current_user.is_driver():
            
            date_order = request.form.get('edit_date')
     
            time_order = request.form.get('edit_time')
     
            user_descr = request.form.get('edit_descr')
     
            query = (
            "UPDATE orders SET date_order=%s, time_order=%s, user_descr=%s "
            "WHERE order_id=%s"
        )
            query2 = (
            "UPDATE notifications SET button='0'"
            "WHERE order_id=%s"
        )
            try:
                with db_connector.connect().cursor() as cursor:
                    cursor.execute(query, (date_order, time_order, user_descr, order_id))
                
                
                    cursor.execute(query2, (order_id, ))
                    db_connector.connect().commit()
               
            
                flash("Вы приняли изменения в заказе", category="success")
            except DatabaseError as error:
                flash(f'Ошибка при принятии изменений заказа: {error}', category="danger")
                db_connector.connect().rollback()
        else:
            flash('Вы не имеете доступа к данной странице')
    return redirect(url_for('notifications'))
@app.route('/orders/<int:order_id>/decline', methods=["POST"])
@login_required
def decline_order(order_id):
    if request.method == 'POST':
        if current_user.is_driver():
            query_get_client_id = "SELECT user_id FROM orders WHERE order_id = %s"
            try:
                connection = db_connector.connect()
                with connection.cursor() as cursor:
                    cursor.execute(query_get_client_id, (order_id,))
                    result = cursor.fetchone()
                
                    if result:
                        client_id = result[0]  
                        notification_description = "Водитель отклонил ваши изменения"
                        query2 = (
            "UPDATE notifications SET button='0'"
            "WHERE order_id=%s"
        )
                        insert_notification_query = (
                        "INSERT INTO notifications (user_id, order_id, description, button) "
                        "VALUES (%s, %s, %s, '0')"
                    )
                        cursor.execute(insert_notification_query, (client_id, order_id, notification_description))
                        connection.commit()
                        cursor.execute(query2, (order_id, ))
                        db_connector.connect().commit()
               
                    
                        flash("Вы отклонили изменения", category="danger")
                    else:
                        flash("Клиент не найден", category="danger")
        
            except DatabaseError as error:
                flash(f'Ошибка при отклонении изменений заказа: {error}', category="danger")
                connection.rollback()
        else:
            flash('Вы не имеете доступа к данной странице')
    return redirect(url_for('notifications'))

@app.route('/orders/<int:order_id>/view')
@login_required
def view_order(order_id):
    query = "SELECT * FROM orders WHERE order_id = %s"
    with db_connector.connect().cursor(named_tuple=True) as cursor:
        cursor.execute(query, (order_id,))
        order = cursor.fetchone()
    if not order:
        flash("Заказ не найден", category="danger")
        return redirect(url_for('orders'))
    return render_template("order_view.html", order=order, 
                           get_cargo_name=get_cargo_name, 
                           get_car_type_name=get_car_type_name, 
                           get_money_status_description=get_money_status_description)


def notify_driver(order_id, message, button, edit_date,edit_time,edit_descr):
    query_get_driver_id = "SELECT driver_id FROM orders WHERE order_id = %s"
    with db_connector.connect().cursor() as cursor:
        cursor.execute(query_get_driver_id, (order_id,))
        driver_id = cursor.fetchone()
    
    if driver_id:
        driver_id = driver_id[0]  
        
        insert_notification_query = "INSERT INTO notifications (user_id, order_id, description, button, edit_date,edit_time,edit_descr) VALUES (%s, %s, %s, %s,%s,%s,%s)"
        with db_connector.connect().cursor() as cursor:
            cursor.execute(insert_notification_query, (driver_id, order_id, message, button,edit_date,edit_time,edit_descr))
            db_connector.connect().commit()

@app.route('/orders/<int:order_id>/delete', methods=["POST"])
@login_required
def delete_order(order_id):
    if current_user.is_client():
        query_update_order_status = "UPDATE orders SET order_status='Отменен' WHERE order_id=%s"
        notify_driver(order_id, 'Клиент отменил заказ', '0', '1970-01-01','00:00','')
        try:
            with db_connector.connect().cursor() as cursor:
                cursor.execute(query_update_order_status, (order_id,))
                db_connector.connect().commit()

            flash("Заказ успешно отменен", category="success")
        except DatabaseError as error:
            flash(f'Ошибка отмены заказа: {error}', category="danger")
            db_connector.connect().rollback()
    else:
        flash("У вас нет прав для отмены этого заказа", category="danger")

    return redirect(url_for('orders'))


def get_form_data(required_fields):
    user = {}

    for field in required_fields:
        user[field] = request.form.get(field) or None

    return user
def get_form_data1(required_fields):
    data = {}
    for field in required_fields:
        data[field] = request.form.get(field) or None
    return data



@app.route('/user/<int:user_id>/delete', methods=["POST"])
@login_required
def delete_user(user_id):
    query1 = "DELETE FROM users WHERE user_id=%s"
    try:
        with db_connector.connect().cursor(named_tuple=True) as cursor:
          
            cursor.execute(query1, (user_id, ))
            db_connector.connect().commit() 
    except DatabaseError as error:
        flash(f'Ошибка удаления пользователя! {error}', category="danger")
        db_connector.connect().rollback()    
    query2 = "DELETE FROM drivers_pro WHERE driver_id=%s"
    try:
        with db_connector.connect().cursor(named_tuple=True) as cursor:
          
            cursor.execute(query2, (user_id, ))
            db_connector.connect().commit() 
        
        flash("Запись пользователя успешно удалена", category="success")
    except DatabaseError as error:
        flash(f'Ошибка удаления пользователя! {error}', category="danger")
        db_connector.connect().rollback()    
    
    return redirect(url_for('users'))



@app.route('/users/new', methods=['GET', 'POST'])
def create_user():
    user = {}
    roles = get_roles()
    errors = {}

    if request.method == 'POST':
        user = get_form_data(CREATE_USER_FIELDS)
        user_image = None
        
        if 'user_image' in request.files:
            file = request.files['user_image']
            if file and file.filename != '':
                user_image = file.read()
        
        try:
            with db_connector.connect().cursor() as cursor:
                query_user = (
                    "INSERT INTO users (login, password, first_name, last_name, surname, date_birth, email, phone_num, role_id, user_image) "
                    "VALUES (%(login)s, SHA2(%(password)s, 256), %(first_name)s, %(last_name)s, %(surname)s,"
                    "%(date_birth)s, %(email)s, %(phone_num)s, %(role_id)s, %(user_image)s)"
                )
                user['user_image'] = user_image  
                cursor.execute(query_user, user)
                user_id = cursor.lastrowid

                if user['role_id'] == '2':
                    driver_data = {
                        'user_id': user_id,
                        'pass_info': request.form.get('pass_info'),
                        'class': request.form.get('class')
                    }
                    query_driver = (
                        "INSERT INTO drivers_pro (user_id, pass_info, classdriver) "
                        "VALUES (%(user_id)s, %(pass_info)s, %(class)s)"
                    )
                    cursor.execute(query_driver, driver_data)

                db_connector.connect().commit()
                flash("Пользователь успешно создан", category="success")
                return redirect(url_for('users'))

        except DatabaseError as error:
            flash(f'Ошибка создания пользователя: {error}', category="danger")
            db_connector.connect().rollback()
            print(f"Ошибка выполнения запроса: {error}")

    return render_template("user_form.html", user=user, roles=roles, errors=errors)

@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    query = ("SELECT * FROM users where user_id = %s")
    with db_connector.connect().cursor(named_tuple=True) as cursor:
        cursor.execute(query, (user_id, ))
        user = cursor.fetchone()

    if request.method == "POST":
        user = get_form_data(EDIT_USER_FIELDS)
        user_image = None
        if 'user_image' in request.files:
            file = request.files['user_image']
            if file and file.filename != '':
                user_image = file.read()
        
        user['user_id'] = user_id
        query = ("UPDATE users "
                 "SET last_name=%(last_name)s, first_name=%(first_name)s, "
                 "surname=%(surname)s, email=%(email)s, phone_num=%(phone_num)s, user_image=%(user_image)s"
                 "WHERE user_id=%(user_id)s ")
        user['user_image'] = user_image  
        try:
            with db_connector.connect().cursor(named_tuple=True) as cursor:
                cursor.execute(query, user)
                response=db_connector.connect().commit()
            flash("Запись пользователя успешно обновлена", category="success")
            return redirect(url_for('users'))
        except DatabaseError as error:
            flash(f'Ошибка редактирования пользователя! {error}', category="danger")
            db_connector.connect().rollback()    

    return render_template("edit_user.html", user=user, )
def get_cargo_name(cargo_id):
    query = "SELECT cargo_name FROM cargo WHERE cargo_id = %s"
    with db_connector.connect().cursor() as cursor:
        cursor.execute(query, (cargo_id,))
        result = cursor.fetchone()
        if result:
            return result[0]
        return None

def get_car_type_name(car_type_id):
    query = "SELECT car_type_name FROM cars_basic WHERE car_type_id = %s"
    with db_connector.connect().cursor() as cursor:
        cursor.execute(query, (car_type_id,))
        result = cursor.fetchone()
        if result:
            return result[0]
        return None

def get_money_status_description(money_status_id):
    query = "SELECT description FROM money_status WHERE status_id = %s"
    with db_connector.connect().cursor() as cursor:
        cursor.execute(query, (money_status_id,))
        result = cursor.fetchone()
        if result:
            return result[0]
        return None


@app.route('/user/<int:user_id>/change', methods=["GET", "POST"])
@login_required
def change_password(user_id):
    if request.method == 'POST':
        user = get_form_data(CHANGE_PASS_FIELDS)
        
        query_check_password = "SELECT user_id FROM users WHERE user_id = %s AND password = SHA2(%s, 256)"
        with db_connector.connect().cursor(named_tuple=True) as cursor:
            cursor.execute(query_check_password, (user_id, user["password"]))
            if not cursor.fetchone():
                flash("Текущий пароль введен неверно", category="danger")
                return redirect(url_for('change_password', user_id=user_id))
        
        if user["newpass"] == user["newpass2"]:

            query_change_password = "UPDATE users SET password = SHA2(%s, 256) WHERE user_id = %s"
            try:
                with db_connector.connect().cursor(named_tuple=True) as cursor:
                    cursor.execute(query_change_password, (user["newpass"], user_id))
                    db_connector.connect().commit()
                    flash("Пароль успешно изменен", category="success")
                    return redirect(url_for('users'))
            except DatabaseError as error:
                flash(f'Ошибка изменения пароля! {error}', category="danger")
                db_connector.connect().rollback()
                return redirect(url_for('users'))
        else:
            flash("Новые пароли не совпадают", category="danger")
            return redirect(url_for('change_password', user_id=user_id))

    return render_template("change.html")

#ВЗЯТЬ ЗАКАЗ

@app.route('/orders/<int:order_id>/take', methods=["POST"])
@login_required
def take_order(order_id):
    if current_user.is_driver():

        query_get_client_id = "SELECT user_id FROM orders WHERE order_id = %s"
        with db_connector.connect().cursor() as cursor:
            cursor.execute(query_get_client_id, (order_id,))
            client_id = cursor.fetchone()
        
        if client_id:
            client_id = client_id[0]  
        
            query = "UPDATE orders SET driver_id=%s, order_status='Взят в работу' WHERE order_id=%s"
            try:
                with db_connector.connect().cursor() as cursor:
                    cursor.execute(query, (current_user.id, order_id))
                    db_connector.connect().commit()

                notification_description = "Ваш заказ был взят в работу водителем"
                insert_notification_query = "INSERT INTO notifications (user_id, order_id, description, button) VALUES (%s, %s, %s, 0)"
                with db_connector.connect().cursor() as cursor:
                    cursor.execute(insert_notification_query, (client_id, order_id, notification_description))
                    db_connector.connect().commit()
                flash("Заказ взят в работу", category="success")
            except DatabaseError as error:
                flash(f'Ошибка при попытке взять заказ в работу: {error}', category="danger")
                db_connector.connect().rollback()
        else:
            flash("Не удалось найти клиента для этого заказа", category="danger")
    else:
        flash("Только водители могут брать заказы", category="danger")
    return redirect(url_for('orders'))

#ВЗЯТЫЕ ЗАКАЗЫ
@app.route('/orders/taken')
@login_required
def taken_orders():
    if current_user.is_driver():
        query = 'SELECT * FROM orders WHERE driver_id=%s AND not(order_status="В обработке" or order_status="Заказ завершен" or order_status="Отменен")'
        with db_connector.connect().cursor(named_tuple=True) as cursor:
            cursor.execute(query, (current_user.id,))
            orders = cursor.fetchall()
            print("Взятые заказы:", orders)  
        return render_template("taken_orders.html", orders=orders)  
    else:
        flash("Only drivers can view taken orders", category="danger")
        return redirect(url_for('index'))



#ОТОБРАЖЕНИЕ УВЕДОМЛЕНИЙ
@app.route('/notify')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    per_page = 5 

    query_count = "SELECT COUNT(*) AS total_count FROM notifications WHERE user_id = %s"
    query_notifications = "SELECT * FROM notifications WHERE user_id = %s ORDER BY note_id DESC LIMIT %s OFFSET %s"

    with db_connector.connect().cursor(named_tuple=True) as cursor:
        cursor.execute(query_count, (current_user.id,))
        total_count = cursor.fetchone().total_count

        total_pages = (total_count + per_page - 1) // per_page
        offset = (page - 1) * per_page

        cursor.execute(query_notifications, (current_user.id, per_page, offset))
        notifications = cursor.fetchall()
       
    return render_template('notify.html', notifications=notifications, page=page, total_pages=total_pages)

@app.route('/notifications/delete/<int:note_id>', methods=['POST'])
@login_required
def delete_notification(note_id):
    query = "DELETE FROM notifications WHERE note_id = %s AND user_id = %s"
    try:
        with db_connector.connect().cursor() as cursor:
            cursor.execute(query, (note_id, current_user.id))
            db_connector.connect().commit()
        flash("Уведомление успешно удалено", category="success")
    except DatabaseError as error:
        flash(f'Ошибка удаления уведомления: {error}', category="danger")
        db_connector.connect().rollback()
    return redirect(url_for('notifications'))

@app.route('/notifications/delete_all_notifications', methods=['POST'])
@login_required
def delete_all_notifications():
    query = "DELETE FROM notifications WHERE user_id = %s"
    try:
        with db_connector.connect().cursor() as cursor:
            cursor.execute(query, (current_user.id,))
            db_connector.connect().commit()
        flash("Все уведомления успешно удалены", category="success")
    except DatabaseError as error:
        flash(f'Ошибка удаления всех уведомлений: {error}', category="danger")
        db_connector.connect().rollback()
    return redirect(url_for('notifications'))



#НАЧАТЬ ВЫПОЛНЕНИЕ ЗАКАЗА И ОТПРАВИТЬ УВЕДОМЛЕНИЕ
@app.route('/orders/<int:order_id>/start', methods=["POST"])
@login_required
def start_order(order_id):
    if current_user.is_driver():

        query_get_client_id = "SELECT user_id FROM orders WHERE order_id = %s"
        with db_connector.connect().cursor(named_tuple=True) as cursor:
            cursor.execute(query_get_client_id, (order_id,))
            client = cursor.fetchone()
        
        if client:
            client_id = client.user_id
            
            query = "UPDATE orders SET order_status='Выполнение заказа' WHERE order_id=%s AND driver_id=%s"
            try:
                with db_connector.connect().cursor(named_tuple=True) as cursor:
                    cursor.execute(query, (order_id, current_user.id))
                    db_connector.connect().commit()

                notification_description = "Ваш заказ был взят в выполнение водителем"
                insert_notification_query = "INSERT INTO notifications (user_id, order_id, description, button) VALUES (%s, %s, %s, 0)"
                with db_connector.connect().cursor() as cursor:
                    cursor.execute(insert_notification_query, (client_id, order_id, notification_description))
                    db_connector.connect().commit()

                flash("Заказ начат", category="success")
            except DatabaseError as error:
                flash(f'Ошибка при начале выполнения заказа: {error}', category="danger")
                db_connector.connect().rollback()
        else:
            flash("Не удалось найти клиента для этого заказа", category="danger")
    else:
        flash("Только водители могут начинать выполнение заказа", category="danger")
    return redirect(url_for('taken_orders'))


#ЗАВЕРШИТЬ ВЫПОЛНЕНИЕ ЗАКАЗА И ОТПРАВИТЬ УВЕДОМЛЕНИЕ
@app.route('/orders/<int:order_id>/complete', methods=["POST"])
@login_required
def complete_order(order_id):
    if current_user.is_driver():

        query_get_client_id = "SELECT user_id FROM orders WHERE order_id = %s"
        with db_connector.connect().cursor() as cursor:
            cursor.execute(query_get_client_id, (order_id,))
            client_id = cursor.fetchone()
        
        if client_id:
            client_id = client_id[0]  

            query = "UPDATE orders SET order_status='Заказ выполнен' WHERE order_id=%s AND driver_id=%s"
            try:
                with db_connector.connect().cursor() as cursor:
                    cursor.execute(query, (order_id, current_user.id))
                    db_connector.connect().commit()

                notification_description = "Ваш заказ был успешно выполнен. Вы можете оценить качество обслуживания"
                insert_notification_query = "INSERT INTO notifications (user_id, order_id, description, button) VALUES (%s, %s, %s, 0)"
                with db_connector.connect().cursor() as cursor:
                    cursor.execute(insert_notification_query, (client_id, order_id,notification_description))
                    db_connector.connect().commit()

                flash("Заказ завершен", category="success")
            except DatabaseError as error:
                flash(f'Ошибка при завершении заказа: {error}', category="danger")
                db_connector.connect().rollback()
        else:
            flash("Не удалось найти клиента для этого заказа", category="danger")
    else:
        flash("Только водители могут завершать заказ", category="danger")
    return redirect(url_for('taken_orders'))

#ОЦЕНИТЬ ЗАКАЗ
@app.route('/orders/<int:order_id>/rate', methods=['GET', 'POST'])
@login_required
def rate_order(order_id):
    if request.method == 'POST':
        rating = request.form.get('rating')
        if rating:
            try:
                rating = int(rating)
                if rating < 1 or rating > 5:
                    flash("Оценка должна быть от 1 до 5", category="danger")
                    return redirect(url_for('view_order', order_id=order_id))
                
                query_update_rating = "UPDATE orders SET rate = %s WHERE order_id = %s"
                with db_connector.connect().cursor() as cursor:
                    cursor.execute(query_update_rating, (rating, order_id))
                    db_connector.connect().commit()
                
                flash("Оценка успешно добавлена", category="success")
                return redirect(url_for('view_order', order_id=order_id))
            except ValueError:
                flash("Оценка должна быть числом", category="danger")
                return redirect(url_for('view_order', order_id=order_id))
        else:
            flash("Необходимо выбрать оценку", category="danger")
            return redirect(url_for('view_order', order_id=order_id))
    
    return render_template("rate_order.html", order_id=order_id)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route('/secret')
@login_required
def secret():
    return render_template('secret.html')
