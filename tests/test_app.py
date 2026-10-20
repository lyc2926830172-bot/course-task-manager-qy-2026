# -*- coding: utf-8 -*-
"""使用隔离的临时 SQLite 数据库验证真实 HTTP 请求与持久化行为。"""
import sqlite3
from contextlib import closing
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from app import create_app, today


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temporary.name) / 'test.sqlite')
        self.config = dict(TESTING=True, DATABASE=self.database,
                           SECRET_KEY='isolated-test-key', SEED_DEMO=False)
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        self.client.get('/')

    def tearDown(self):
        self.temporary.cleanup()

    def post(self, path, **fields):
        with self.client.session_transaction() as session:
            fields['csrf_token'] = session['csrf_token']
        return self.client.post(path, data=fields, follow_redirects=True)

    def course(self, name='Python 课程'):
        response = self.post('/courses/new', name=name, teacher='教师', color='teal')
        self.assertEqual(response.status_code, 200)
        with closing(sqlite3.connect(self.database)) as db:
            return db.execute('SELECT id FROM courses WHERE name=?', (name,)).fetchone()[0]

    def task(self, course_id=None, **changes):
        fields = dict(title='测试任务', description='详细说明', course_id=str(course_id or self.course()),
                      due_date=today().isoformat(), priority='high', status='todo')
        fields.update(changes)
        response = self.post('/tasks/new', **fields)
        self.assertEqual(response.status_code, 200)
        with closing(sqlite3.connect(self.database)) as db:
            return db.execute('SELECT MAX(id) FROM tasks').fetchone()[0]

    def test_all_read_pages_and_empty_states(self):
        for path in ['/', '/courses', '/courses/new', '/tasks', '/tasks/new']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertIn('还没有课程', self.client.get('/courses').get_data(as_text=True))
        self.assertIn('没有找到任务', self.client.get('/tasks').get_data(as_text=True))

    def test_course_create_update_duplicate_and_delete(self):
        course_id = self.course()
        duplicate = self.post('/courses/new', name='Python 课程', teacher='', color='blue')
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn('课程名称已存在', duplicate.get_data(as_text=True))
        self.assertEqual(self.client.get(f'/courses/{course_id}/edit').status_code, 200)
        self.assertEqual(self.post(f'/courses/{course_id}/edit', name='更新课程', teacher='张老师', color='purple').status_code, 200)
        self.assertIn('更新课程', self.client.get('/courses').get_data(as_text=True))
        self.post(f'/courses/{course_id}/delete')
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM courses').fetchone()[0], 0)

    def test_task_complete_crud_and_toggle(self):
        task_id = self.task()
        detail = self.client.get(f'/tasks/{task_id}')
        self.assertIn('详细说明', detail.get_data(as_text=True))
        self.assertEqual(self.client.get(f'/tasks/{task_id}/edit').status_code, 200)
        response = self.post(f'/tasks/{task_id}/edit', title='修订任务', description='第二版',
                             course_id='1', due_date='2026-11-09', priority='normal', status='doing')
        self.assertIn('修订任务', response.get_data(as_text=True))
        self.post(f'/tasks/{task_id}/toggle')
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT status FROM tasks').fetchone()[0], 'done')
        self.post(f'/tasks/{task_id}/toggle')
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT status FROM tasks').fetchone()[0], 'todo')
        self.post(f'/tasks/{task_id}/delete')
        self.assertEqual(self.client.get(f'/tasks/{task_id}').status_code, 404)

    def test_parent_deletion_protects_tasks(self):
        course_id = self.course()
        self.task(course_id)
        response = self.post(f'/courses/{course_id}/delete')
        self.assertIn('仍有关联任务', response.get_data(as_text=True))
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM courses').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0], 1)

    def test_invalid_forms_do_not_write_rows(self):
        invalid_course = self.post('/courses/new', name='  ', teacher='', color='invalid')
        self.assertEqual(invalid_course.status_code, 400)
        course_id = self.course()
        baseline = dict(title='任务', description='', course_id=str(course_id), due_date='2026-11-01', priority='normal', status='todo')
        for changes in [dict(title=' '), dict(due_date='2026-02-30'), dict(course_id='9999'),
                        dict(priority='invalid'), dict(status='invalid'), dict(description='字'*3001)]:
            with self.subTest(changes=list(changes)):
                response = self.post('/tasks/new', **dict(baseline, **changes))
                self.assertEqual(response.status_code, 400)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0], 0)

    def test_filters_literal_search_and_sql_injection_text(self):
        course_id = self.course()
        other_id = self.course('另一门课程')
        self.task(course_id, title='literal 100%_任务', status='doing', due_date=(today()-timedelta(days=1)).isoformat())
        self.task(other_id, title='普通事项', status='done')
        body = self.client.get('/tasks', query_string={'q': '%_'}).get_data(as_text=True)
        self.assertIn('literal 100%_任务', body)
        self.assertNotIn('普通事项</a>', body)
        for params in [dict(status='doing'), dict(course=str(course_id)), dict(due='overdue')]:
            body = self.client.get('/tasks', query_string=params).get_data(as_text=True)
            self.assertIn('literal 100%_任务', body)
            self.assertNotIn('普通事项</a>', body)
        self.assertEqual(self.client.get('/tasks', query_string={'q': "' OR 1=1--"}).status_code, 200)
        for params in [dict(status='hacked'), dict(course='x'), dict(course='999'), dict(due='oops')]:
            self.assertIn(self.client.get('/tasks', query_string=params).status_code, (400, 404))

    def test_csrf_required_and_get_cannot_mutate(self):
        self.assertEqual(self.client.post('/courses/new', data={'name': '伪造'}).status_code, 400)
        self.assertEqual(self.client.post('/courses/new', data={'csrf_token': '非ASCII'}).status_code, 400)
        task_id = self.task()
        self.assertEqual(self.client.post(f'/tasks/{task_id}/delete').status_code, 400)
        for path in [f'/tasks/{task_id}/delete', f'/tasks/{task_id}/toggle', '/courses/1/delete']:
            self.assertEqual(self.client.get(path).status_code, 405)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0], 1)

    def test_user_text_is_escaped(self):
        task_id = self.task(title='<script>alert(1)</script>', description='<img src=x onerror=alert(1)>')
        body = self.client.get(f'/tasks/{task_id}').get_data(as_text=True)
        self.assertNotIn('<script>alert(1)</script>', body)
        self.assertNotIn('<img src=x onerror=alert(1)>', body)
        self.assertIn('&lt;script&gt;', body)

    def test_restart_preserves_data(self):
        task_id = self.task(title='持久化记录')
        second_app = create_app(self.config)
        self.assertIn('持久化记录', second_app.test_client().get(f'/tasks/{task_id}').get_data(as_text=True))

    def test_demo_initialization_is_not_repeated(self):
        demo_path = str(Path(self.temporary.name) / 'demo.sqlite')
        demo_config = dict(self.config, DATABASE=demo_path, SEED_DEMO=True)
        demo = create_app(demo_config)
        self.assertEqual(demo.test_client().get('/').status_code, 200)
        create_app(demo_config)
        with closing(sqlite3.connect(demo_path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM courses').fetchone()[0], 3)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0], 8)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')


if __name__ == '__main__':
    unittest.main(verbosity=2)
