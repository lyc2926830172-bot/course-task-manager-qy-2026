# -*- coding: utf-8 -*-
'''课程任务管理系统 — Python 程序设计作业 3。
作者：强蕴祺　学号：2024110901
运行：python app.py，然后访问 http://127.0.0.1:5000。
'''
import hmac
import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)

STATUS = {'todo': '待开始', 'doing': '进行中', 'done': '已完成'}
PRIORITY = {'high': '高优先级', 'normal': '普通', 'low': '低优先级'}
COLORS = {'teal': '青绿', 'blue': '湖蓝', 'amber': '琥珀', 'purple': '紫罗兰'}
LOCAL_TZ = timezone(timedelta(hours=8))


def today():
    return datetime.now(LOCAL_TZ).date()


def timestamp():
    return datetime.now(LOCAL_TZ).isoformat(timespec='seconds')


def get_db():
    '''每个请求复用一个连接，并启用 SQLite 外键约束。'''
    if 'db' not in g:
        g.db = sqlite3.connect(g.app_database, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(
        DATABASE=str(Path(app.instance_path) / 'study.sqlite'),
        SEED_DEMO=True, MAX_CONTENT_LENGTH=1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
    )
    if config:
        app.config.update(config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    # 首次运行时生成会话密钥。
    if not app.config.get('SECRET_KEY'):
        secret_file = Path(app.instance_path) / 'secret.key'
        if not secret_file.exists():
            try:
                with secret_file.open('x', encoding='ascii') as stream:
                    stream.write(secrets.token_hex(32))
            except FileExistsError:
                pass
        app.config['SECRET_KEY'] = secret_file.read_text(encoding='ascii').strip()

    @app.before_request
    def prepare_request():
        g.app_database = app.config['DATABASE']
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_urlsafe(32)
        if request.method == 'POST':
            supplied = request.form.get('csrf_token', '')
            if not supplied.isascii() or not hmac.compare_digest(session['csrf_token'], supplied):
                abort(400, description='表单已失效，请刷新页面后重试。')

    @app.teardown_appcontext
    def close_database(error=None):
        connection = g.pop('db', None)
        if connection is not None:
            connection.close()

    @app.context_processor
    def common_context():
        return dict(status_labels=STATUS, priority_labels=PRIORITY, colors=COLORS,
                    today=today().isoformat(), display_date=today().strftime('%Y年%m月%d日'))

    def find_course(course_id):
        row = get_db().execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
        if row is None:
            abort(404)
        return row

    def find_task(task_id):
        row = get_db().execute('''
            SELECT t.*, c.name AS course_name, c.color AS course_color
            FROM tasks t JOIN courses c ON t.course_id=c.id WHERE t.id=?
        ''', (task_id,)).fetchone()
        if row is None:
            abort(404)
        return row

    def task_order():
        return "CASE WHEN t.status='done' THEN 1 ELSE 0 END, t.due_date, CASE t.priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, t.id DESC"

    @app.route('/')
    def dashboard():
        db = get_db()
        counts = db.execute('''SELECT COUNT(*) AS total,
            COALESCE(SUM(status='done'),0) AS done,
            COALESCE(SUM(status='doing'),0) AS doing,
            COALESCE(SUM(status!='done' AND due_date < ?),0) AS overdue
            FROM tasks''', (today().isoformat(),)).fetchone()
        courses = db.execute('''SELECT c.*, COUNT(t.id) AS total,
            COALESCE(SUM(t.status='done'),0) AS done
            FROM courses c LEFT JOIN tasks t ON c.id=t.course_id
            GROUP BY c.id ORDER BY c.id''').fetchall()
        upcoming = db.execute('''SELECT t.*,c.name AS course_name,c.color AS course_color
            FROM tasks t JOIN courses c ON t.course_id=c.id
            WHERE t.status!='done' ORDER BY ''' + task_order() + ' LIMIT 5').fetchall()
        percentage = round(counts['done'] * 100 / counts['total']) if counts['total'] else 0
        return render_template('dashboard.html', counts=counts, courses=courses,
                               upcoming=upcoming, percentage=percentage, active='dashboard')

    @app.route('/courses')
    def course_list():
        courses = get_db().execute('''SELECT c.*,COUNT(t.id) AS total,
            COALESCE(SUM(t.status='done'),0) AS done
            FROM courses c LEFT JOIN tasks t ON c.id=t.course_id
            GROUP BY c.id ORDER BY c.id''').fetchall()
        return render_template('courses.html', courses=courses, active='courses')

    def course_form(existing=None):
        values = dict(existing) if existing else {'name': '', 'teacher': '', 'color': 'teal'}
        errors = []
        if request.method == 'POST':
            values = {key: request.form.get(key, '').strip() for key in ('name', 'teacher', 'color')}
            if not 1 <= len(values['name']) <= 60:
                errors.append('课程名称必须为 1—60 个字符。')
            if len(values['teacher']) > 40:
                errors.append('任课教师不能超过 40 个字符。')
            if values['color'] not in COLORS:
                errors.append('请选择有效的课程颜色。')
            if not errors:
                db = get_db()
                try:
                    with db:
                        if existing:
                            db.execute('UPDATE courses SET name=?,teacher=?,color=? WHERE id=?',
                                       (values['name'], values['teacher'], values['color'], existing['id']))
                        else:
                            db.execute('INSERT INTO courses(name,teacher,color,created_at) VALUES(?,?,?,?)',
                                       (values['name'], values['teacher'], values['color'], timestamp()))
                except sqlite3.IntegrityError:
                    errors.append('课程名称已存在，请使用不同名称。')
                else:
                    flash('课程已更新。' if existing else '课程已添加。', 'success')
                    return redirect(url_for('course_list'))
        return render_template('course_form.html', values=values, errors=errors,
                               editing=existing is not None, active='courses'), 400 if errors else 200

    @app.route('/courses/new', methods=['GET', 'POST'])
    def course_new():
        return course_form()

    @app.route('/courses/<int:course_id>/edit', methods=['GET', 'POST'])
    def course_edit(course_id):
        return course_form(find_course(course_id))

    @app.route('/courses/<int:course_id>/delete', methods=['POST'])
    def course_delete(course_id):
        find_course(course_id)
        db = get_db()
        # 有任务时禁止删除课程，避免误删关联数据。
        if db.execute('SELECT 1 FROM tasks WHERE course_id=? LIMIT 1', (course_id,)).fetchone():
            flash('该课程仍有关联任务，请先转移或删除任务。', 'error')
        else:
            with db:
                db.execute('DELETE FROM courses WHERE id=?', (course_id,))
            flash('课程已删除。', 'success')
        return redirect(url_for('course_list'))

    @app.route('/tasks')
    def task_list():
        q = request.args.get('q', '').strip()
        status = request.args.get('status', '')
        course = request.args.get('course', '')
        due = request.args.get('due', '')
        if len(q) > 100 or (status and status not in STATUS) or due not in ('', 'overdue', 'week'):
            abort(400, description='筛选条件无效。')
        clauses, params = [], []
        if q:
            # 转义搜索词中的 LIKE 通配符。
            literal = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            clauses.append("(t.title LIKE ? ESCAPE '\\' OR t.description LIKE ? ESCAPE '\\')")
            params.extend(['%' + literal + '%'] * 2)
        if status:
            clauses.append('t.status=?')
            params.append(status)
        if course:
            if not course.isascii() or not course.isdigit() or len(course) > 10:
                abort(400, description='课程筛选无效。')
            find_course(int(course))
            clauses.append('t.course_id=?')
            params.append(int(course))
        if due == 'overdue':
            clauses.append("t.status!='done' AND t.due_date < ?")
            params.append(today().isoformat())
        elif due == 'week':
            clauses.append("t.status!='done' AND t.due_date BETWEEN ? AND ?")
            params.extend([today().isoformat(), (today() + timedelta(days=6)).isoformat()])
        sql = 'SELECT t.*, c.name AS course_name,c.color AS course_color FROM tasks t JOIN courses c ON t.course_id=c.id'
        if clauses:
            sql += ' WHERE ' + ' AND '.join(clauses)
        sql += ' ORDER BY ' + task_order()
        tasks = get_db().execute(sql, params).fetchall()
        courses = get_db().execute('SELECT * FROM courses ORDER BY id').fetchall()
        return render_template('tasks.html', tasks=tasks, courses=courses,
                               filters=dict(q=q, status=status, course=course, due=due), active='tasks')

    def task_form(existing=None):
        values = dict(existing) if existing else dict(title='', description='', course_id='',
            due_date=(today() + timedelta(days=7)).isoformat(), priority='normal', status='todo')
        courses = get_db().execute('SELECT * FROM courses ORDER BY id').fetchall()
        errors = []
        if request.method == 'POST':
            values = {key: request.form.get(key, '').strip() for key in
                      ('title', 'description', 'course_id', 'due_date', 'priority', 'status')}
            if not 1 <= len(values['title']) <= 100:
                errors.append('任务名称必须为 1—100 个字符。')
            if len(values['description']) > 3000:
                errors.append('任务说明不能超过 3000 个字符。')
            if values['course_id'] not in {str(course['id']) for course in courses}:
                errors.append('请选择已存在的课程。')
            try:
                parsed = date.fromisoformat(values['due_date'])
                if parsed.isoformat() != values['due_date'] or not 2000 <= parsed.year <= 2100:
                    raise ValueError()
            except ValueError:
                errors.append('截止日期必须为 2000—2100 年间的有效日期。')
            if values['priority'] not in PRIORITY or values['status'] not in STATUS:
                errors.append('请选择有效的优先级和状态。')
            if not errors:
                db = get_db()
                params = [values[key] for key in ('title', 'description', 'course_id', 'due_date', 'priority', 'status')]
                with db:
                    if existing:
                        db.execute('UPDATE tasks SET title=?,description=?,course_id=?,due_date=?,priority=?,status=?,updated_at=? WHERE id=?',
                                   params + [timestamp(), existing['id']])
                        task_id = existing['id']
                    else:
                        cursor = db.execute('INSERT INTO tasks(title,description,course_id,due_date,priority,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                                            params + [timestamp(), timestamp()])
                        task_id = cursor.lastrowid
                flash('任务已更新。' if existing else '任务已添加。', 'success')
                return redirect(url_for('task_detail', task_id=task_id))
        return render_template('task_form.html', values=values, errors=errors, courses=courses,
                               editing=existing is not None, active='tasks'), 400 if errors else 200

    @app.route('/tasks/new', methods=['GET', 'POST'])
    def task_new():
        return task_form()

    @app.route('/tasks/<int:task_id>')
    def task_detail(task_id):
        return render_template('task_detail.html', task=find_task(task_id), active='tasks')

    @app.route('/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
    def task_edit(task_id):
        return task_form(find_task(task_id))

    @app.route('/tasks/<int:task_id>/toggle', methods=['POST'])
    def task_toggle(task_id):
        task = find_task(task_id)
        status = 'todo' if task['status'] == 'done' else 'done'
        with get_db() as db:
            db.execute('UPDATE tasks SET status=?,updated_at=? WHERE id=?', (status, timestamp(), task_id))
        flash('任务已重新打开。' if status == 'todo' else '任务已标记完成。', 'success')
        return redirect(url_for('task_detail', task_id=task_id))

    @app.route('/tasks/<int:task_id>/delete', methods=['POST'])
    def task_delete(task_id):
        find_task(task_id)
        with get_db() as db:
            db.execute('DELETE FROM tasks WHERE id=?', (task_id,))
        flash('任务已删除。', 'success')
        return redirect(url_for('task_list'))

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error_page(error):
        messages = {400: '请求有误', 404: '页面未找到', 413: '提交内容过大'}
        detail = error.description if error.code == 400 else (
            '这条记录可能已删除，请返回任务列表查看。' if error.code == 404 else '请缩短提交内容后重试。')
        return render_template('error.html', code=error.code, title=messages[error.code], detail=detail, active=''), error.code

    with app.app_context():
        g.app_database = app.config['DATABASE']
        database = Path(app.config['DATABASE'])
        database.parent.mkdir(parents=True, exist_ok=True)
        is_new = not database.exists()
        db = get_db()
        db.executescript((Path(app.root_path) / 'schema.sql').read_text(encoding='utf-8'))
        if is_new and app.config['SEED_DEMO']:
            seed_demo(db)
    return app


def seed_demo(db):
    '''仅首次创建数据库时写入演示数据；后续重启不重复、不重置。'''
    with db:
        db.executemany('INSERT INTO courses(name,teacher,color,created_at) VALUES(?,?,?,?)', [
            ('Python 程序设计', '任课教师', 'teal', timestamp()),
            ('数据库原理', '任课教师', 'blue', timestamp()),
            ('高等数学', '任课教师', 'amber', timestamp()),
        ])
        examples = [
            (1, '完成 Flask Web 应用', '实现路由、关联数据表和 HTML 模板，整理源码与运行说明。', 5, 'high', 'doing'),
            (1, '复习 Python 文件与异常处理', '整理文件读写、上下文管理器与异常处理的课堂笔记。', 2, 'normal', 'todo'),
            (2, '绘制课程选课系统 E-R 图', '标明实体、属性、联系与主外键。', 1, 'high', 'doing'),
            (2, '练习 SQL 关联查询', '完成 INNER JOIN、LEFT JOIN 和分组统计练习。', -2, 'normal', 'todo'),
            (3, '完成微分习题', '复习链式法则与隐函数求导。', 3, 'normal', 'todo'),
            (1, '搭建 Python 开发环境', '确认虚拟环境、依赖安装和解释器版本。', -4, 'low', 'done'),
            (2, '阅读关系模型章节', '理解候选键、主键、外键与参照完整性。', -3, 'normal', 'done'),
            (3, '整理极限与连续笔记', '归纳常用极限与连续性的判断方法。', -1, 'low', 'done'),
        ]
        db.executemany('INSERT INTO tasks(course_id,title,description,due_date,priority,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)', [
            (course, title, description, (today()+timedelta(days=offset)).isoformat(), priority, status, timestamp(), timestamp())
            for course, title, description, offset, priority, status in examples
        ])


if __name__ == '__main__':
    application = create_app()
    # 本地运行，关闭调试模式。
    application.run(host='127.0.0.1', port=int(os.environ.get('PORT', '5000')), debug=False)
