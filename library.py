import sqlite3
from datetime import datetime, timedelta
from flask import Flask, g, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = 'library_secret_key_2026'
DATABASE = 'library.db'

FINE_PER_DAY = 2.0
GRACE_PERIOD_DAYS = 7


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    return cur.lastrowid


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def require_role(role):
    user = session.get('user')
    return user and user.get('role') == role


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '').strip()
        if not username or not password:
            flash('Please enter both username and password.', 'danger')
            return render_template('login.html')
        user = query_db('SELECT * FROM users WHERE lower(username) = ? AND password = ?', (username, password), one=True)
        if user:
            session['user'] = {'id': user['id'], 'username': user['username'], 'role': user['role'], 'full_name': user['full_name']}
            flash('Welcome back, ' + user['full_name'] + '!', 'success')
            return redirect(url_for('admin_dashboard' if user['role'] == 'admin' else 'student_dashboard'))
        flash('Invalid credentials. Please try again.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/admin')
def admin_dashboard():
    if not require_role('admin'):
        return redirect(url_for('login'))
    total_books = query_db('SELECT COUNT(*) AS count FROM books', one=True)['count']
    total_students = query_db('SELECT COUNT(*) AS count FROM users WHERE role = ?', ('student',), one=True)['count']
    borrowed_books = query_db("SELECT COUNT(*) AS count FROM borrows WHERE status = 'Borrowed'", one=True)['count']
    overdue_books = query_db("SELECT COUNT(*) AS count FROM borrows WHERE status = 'Borrowed' AND due_date < date('now')", one=True)['count']
    outstanding_fines = query_db('SELECT SUM(fine) AS total FROM borrows WHERE fine > 0 AND fine_paid = 0', one=True)['total'] or 0
    return render_template('admin_dashboard.html', total_books=total_books, total_students=total_students,
                           borrowed_books=borrowed_books, overdue_books=overdue_books, outstanding_fines=outstanding_fines)


@app.route('/admin/books')
def admin_books():
    if not require_role('admin'):
        return redirect(url_for('login'))
    books = query_db('SELECT * FROM books ORDER BY category, title')
    return render_template('manage_books.html', books=books)


@app.route('/admin/books/add', methods=['POST'])
def admin_add_book():
    if not require_role('admin'):
        return redirect(url_for('login'))
    title = request.form['title'].strip()
    author = request.form['author'].strip()
    category = request.form['category'].strip()
    total = int(request.form['total_copies'])
    description = request.form['description'].strip()
    if title and author and category and total > 0:
        execute_db('INSERT INTO books (title, author, category, total_copies, available_copies, description) VALUES (?, ?, ?, ?, ?, ?)',
                   (title, author, category, total, total, description))
        flash('Book added successfully.', 'success')
    else:
        flash('Fill all book details correctly.', 'danger')
    return redirect(url_for('admin_books'))


@app.route('/admin/books/edit/<int:book_id>', methods=['POST'])
def admin_edit_book(book_id):
    if not require_role('admin'):
        return redirect(url_for('login'))
    title = request.form['title'].strip()
    author = request.form['author'].strip()
    category = request.form['category'].strip()
    total = int(request.form['total_copies'])
    description = request.form['description'].strip()
    book = query_db('SELECT * FROM books WHERE id = ?', (book_id,), one=True)
    if book and total >= 0:
        available = book['available_copies'] + (total - book['total_copies'])
        if available < 0:
            available = 0
        execute_db('UPDATE books SET title = ?, author = ?, category = ?, total_copies = ?, available_copies = ?, description = ? WHERE id = ?',
                   (title, author, category, total, available, description, book_id))
        flash('Book updated successfully.', 'success')
    else:
        flash('Unable to update book.', 'danger')
    return redirect(url_for('admin_books'))


@app.route('/admin/books/delete/<int:book_id>', methods=['POST'])
def admin_delete_book(book_id):
    if not require_role('admin'):
        return redirect(url_for('login'))
    execute_db('DELETE FROM books WHERE id = ?', (book_id,))
    flash('Book removed from the collection.', 'warning')
    return redirect(url_for('admin_books'))


@app.route('/admin/students', methods=['GET', 'POST'])
def admin_students():
    if not require_role('admin'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        full_name = request.form['full_name'].strip()
        email = request.form['email'].strip()
        if username and password and full_name:
            try:
                execute_db('INSERT INTO users (username, password, role, full_name, email) VALUES (?, ?, ?, ?, ?)',
                           (username, password, 'student', full_name, email))
                flash('Student account created.', 'success')
            except sqlite3.IntegrityError:
                flash('Username already exists.', 'danger')
        else:
            flash('Complete all fields.', 'danger')
    students = query_db('SELECT * FROM users WHERE role = ? ORDER BY full_name', ('student',))
    return render_template('manage_students.html', students=students)


@app.route('/admin/students/delete/<int:student_id>', methods=['POST'])
def admin_delete_student(student_id):
    if not require_role('admin'):
        return redirect(url_for('login'))
    execute_db('DELETE FROM users WHERE id = ? AND role = ?', (student_id, 'student'))
    flash('Student profile removed.', 'warning')
    return redirect(url_for('admin_students'))


@app.route('/student')
def student_dashboard():
    if not require_role('student'):
        return redirect(url_for('login'))
    user = session['user']
    active = query_db("SELECT COUNT(*) AS count FROM borrows WHERE user_id = ? AND status = 'Borrowed'", (user['id'],), one=True)['count']
    overdue = query_db("SELECT COUNT(*) AS count FROM borrows WHERE user_id = ? AND status = 'Borrowed' AND due_date < date('now')", (user['id'],), one=True)['count']
    total = query_db("SELECT COUNT(*) AS count FROM borrows WHERE user_id = ?", (user['id'],), one=True)['count']
    unpaid_fines = query_db("SELECT SUM(fine) AS total FROM borrows WHERE user_id = ? AND fine > 0 AND fine_paid = 0", (user['id'],), one=True)['total'] or 0
    return render_template('student_dashboard.html', active=active, overdue=overdue, total=total, unpaid_fines=unpaid_fines)


@app.route('/student/books')
def student_books():
    if not require_role('student'):
        return redirect(url_for('login'))
    search_query = request.args.get('q', '').strip()
    if search_query:
        term = f'%{search_query}%'
        books = query_db('''
            SELECT * FROM books
            WHERE title LIKE ? OR author LIKE ? OR category LIKE ?
            ORDER BY category, title
        ''', (term, term, term))
    else:
        books = query_db('SELECT * FROM books ORDER BY category, title')
    borrowed = query_db('''
        SELECT bo.*, b.title AS book_title
        FROM borrows bo
        JOIN books b ON bo.book_id = b.id
        WHERE bo.user_id = ? AND bo.status = ?
        ORDER BY bo.borrow_date DESC
    ''', (session['user']['id'], 'Borrowed'))
    return render_template('student_books.html', books=books, borrowed=borrowed, search_query=search_query)


@app.route('/student/borrow/<int:book_id>', methods=['POST'])
def student_borrow(book_id):
    if not require_role('student'):
        return redirect(url_for('login'))
    book = query_db('SELECT * FROM books WHERE id = ?', (book_id,), one=True)
    if book and book['available_copies'] > 0:
        borrow_date = datetime.now().date()
        due_date = borrow_date + timedelta(days=GRACE_PERIOD_DAYS)
        borrow_id = execute_db('INSERT INTO borrows (user_id, book_id, borrow_date, due_date, status, fine_paid) VALUES (?, ?, ?, ?, ?, ?)',
                   (session['user']['id'], book_id, borrow_date.isoformat(), due_date.isoformat(), 'Borrowed', 0))
        execute_db('UPDATE books SET available_copies = available_copies - 1 WHERE id = ?', (book_id,))
        session['last_borrow_id'] = borrow_id
        return redirect(url_for('student_receipt', borrow_id=borrow_id))
    flash('No available copies to borrow.', 'danger')
    return redirect(url_for('student_books'))


@app.route('/student/return/<int:borrow_id>', methods=['POST'])
def student_return(borrow_id):
    if not require_role('student'):
        return redirect(url_for('login'))
    borrow = query_db('SELECT * FROM borrows WHERE id = ? AND user_id = ?', (borrow_id, session['user']['id']), one=True)
    if borrow and borrow['status'] == 'Borrowed':
        return_date = datetime.now().date()
        due_date = datetime.fromisoformat(borrow['due_date']).date()
        days_late = (return_date - due_date).days
        fine = 0
        if days_late > 0:
            fine = days_late * FINE_PER_DAY
        execute_db('UPDATE borrows SET return_date = ?, fine = ?, status = ?, fine_paid = ? WHERE id = ?',
                   (return_date.isoformat(), fine, 'Returned', 0 if fine > 0 else 1, borrow_id))
        execute_db('UPDATE books SET available_copies = available_copies + 1 WHERE id = ?', (borrow['book_id'],))
        if fine > 0:
            flash(f'Book returned with fine ${fine:.2f} for {days_late} late days.', 'warning')
        else:
            flash('Book returned successfully. Thank you!', 'success')
    return redirect(url_for('student_books'))


@app.route('/student/receipt/<int:borrow_id>')
def student_receipt(borrow_id):
    if not require_role('student'):
        return redirect(url_for('login'))
    receipt = query_db('''
        SELECT bo.*, b.title AS book_title, b.author
        FROM borrows bo
        JOIN books b ON bo.book_id = b.id
        WHERE bo.id = ? AND bo.user_id = ?
    ''', (borrow_id, session['user']['id']), one=True)
    if not receipt:
        flash('Receipt not found.', 'danger')
        return redirect(url_for('student_books'))
    return render_template('student_receipt.html', receipt=receipt)


@app.route('/student/pay-fine/<int:borrow_id>', methods=['POST'])
def student_pay_fine(borrow_id):
    if not require_role('student'):
        return redirect(url_for('login'))
    borrow = query_db('SELECT * FROM borrows WHERE id = ? AND user_id = ?', (borrow_id, session['user']['id']), one=True)
    if borrow and borrow['fine'] > 0 and borrow['fine_paid'] == 0:
        execute_db('UPDATE borrows SET fine_paid = 1 WHERE id = ?', (borrow_id,))
        flash('Fine payment recorded. Thank you!', 'success')
    return redirect(url_for('student_history'))


@app.route('/student/history')
def student_history():
    if not require_role('student'):
        return redirect(url_for('login'))
    records = query_db('''
        SELECT b.*, bo.borrow_date, bo.due_date, bo.return_date, bo.fine, bo.status, bo.fine_paid, bo.id
        FROM borrows bo
        JOIN books b ON bo.book_id = b.id
        WHERE bo.user_id = ?
        ORDER BY bo.borrow_date DESC
    ''', (session['user']['id'],))
    return render_template('student_history.html', records=records)


@app.route('/admin/overdue')
def admin_overdue():
    if not require_role('admin'):
        return redirect(url_for('login'))
    rows = query_db('''
        SELECT bo.*, u.full_name AS student_name, u.username, b.title AS book_title, b.author
        FROM borrows bo
        JOIN users u ON bo.user_id = u.id
        JOIN books b ON bo.book_id = b.id
        WHERE bo.status = 'Borrowed' AND bo.due_date < date('now')
        ORDER BY bo.due_date ASC
    ''')
    records = []
    for row in rows:
        due_date = datetime.fromisoformat(row['due_date']).date()
        days_late = max(0, (datetime.now().date() - due_date).days)
        fine_due = days_late * FINE_PER_DAY
        record = dict(row)
        record['days_late'] = days_late
        record['fine_due'] = fine_due
        records.append(record)
    return render_template('admin_overdue.html', records=records)


@app.route('/admin/fines')
def admin_fines():
    if not require_role('admin'):
        return redirect(url_for('login'))
    records = query_db('''
        SELECT bo.*, u.full_name AS student_name, u.username, b.title AS book_title
        FROM borrows bo
        JOIN users u ON bo.user_id = u.id
        JOIN books b ON bo.book_id = b.id
        WHERE bo.fine > 0 AND bo.fine_paid = 0
        ORDER BY bo.return_date DESC
    ''')
    total = query_db('SELECT SUM(fine) AS total FROM borrows WHERE fine > 0 AND fine_paid = 0', one=True)['total'] or 0
    return render_template('admin_fines.html', records=records, total=total)


@app.route('/admin/fines/pay/<int:borrow_id>', methods=['POST'])
def admin_pay_fine(borrow_id):
    if not require_role('admin'):
        return redirect(url_for('login'))
    execute_db('UPDATE borrows SET fine_paid = 1 WHERE id = ?', (borrow_id,))
    flash('Fine marked as paid.', 'success')
    return redirect(url_for('admin_fines'))


if __name__ == '__main__':
    app.run(debug=True)
