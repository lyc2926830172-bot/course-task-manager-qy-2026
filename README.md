# 课程任务管理系统

Python 程序设计作业 3  
姓名：强蕴祺　学号：2024110901

## 一、系统功能

本系统使用 Flask 和 SQLite 管理课程及学习任务，主要功能如下：

- 添加、修改和删除课程，记录课程名称、任课教师和显示颜色。
- 添加、修改和删除任务，设置所属课程、截止日期、优先级、状态和说明。
- 按关键词、课程、状态和截止时间筛选任务。
- 将任务标记为已完成，或重新改为待开始。
- 首页统计任务数量、进行中数量、逾期数量和完成比例。

系统包含 11 条业务路由、2 张数据表和 9 个 HTML 模板文件。

## 二、运行方法

使用 Python 3.10 或以上版本，推荐 Python 3.12。测试环境为 Windows、Python 3.12.6、Flask 3.1.2。

### Windows

1. 解压压缩包，进入含有 app.py 的文件夹。
2. 双击“启动系统.bat”，等待安装依赖并启动服务。
3. 在浏览器中打开 http://127.0.0.1:5000/ 。

运行时不要关闭命令窗口。停止程序时，在命令窗口按 Ctrl+C。

也可以在项目文件夹中打开 PowerShell，依次执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

上面的前两条命令只需要在第一次运行时执行。以后进入同一个文件夹，执行第三条即可。首次安装依赖需要联网，安装后可以在本机离线运行。

如果默认的 `python` 命令指向旧版 Anaconda Python 3.7，创建环境时请使用 `py -3.12`。未安装新版 Python 时，需先安装 Python 3.10 或以上版本。

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

启动后同样访问 http://127.0.0.1:5000/ 。

## 三、使用说明

首页显示任务统计和未完成任务，最多列出截止日期最早的 5 项任务。点击任务名称可以查看详情。

“我的课程”页面用于管理课程。新建任务前需要先有课程。每个任务只能属于一门课程，一门课程可以有多个任务。仍有关联任务的课程不能直接删除，需要先修改任务所属课程或删除这些任务。

“全部任务”页面可以组合使用关键词、课程、状态和截止时间筛选。关键词搜索任务名称和说明。“已逾期”指截止日期早于今天且未完成；“未来 7 天”包含今天和之后 6 天的未完成任务。日期按北京时间计算。

任务列表优先显示未完成项，再按截止日期和优先级排序。点击“标记为已完成”后，任务状态改为已完成；点击“重新打开任务”后，状态改为待开始。

## 四、数据保存

运行数据库为 `instance/study.sqlite`。首次启动时自动建表并添加 3 门课程、8 个示例任务。再次启动不会重复添加，也不会覆盖已修改的数据。

示例任务用于展示功能，日期根据第一次运行的日期生成，教师信息可自行修改。`data/demo.sqlite` 是附带的示例数据库，可以用 SQLite 工具查看。

备份数据时，先停止程序，再复制 `instance/study.sqlite`。恢复时先备份现有数据库，再将备份文件放回原位置。`instance/secret.key` 是首次启动时生成的会话密钥。

## 五、路由设计

| 路由 | 请求方法 | 功能 |
| --- | --- | --- |
| / | GET | 首页统计 |
| /courses | GET | 课程列表 |
| /courses/new | GET、POST | 新建课程 |
| /courses/&lt;int:course_id&gt;/edit | GET、POST | 修改课程 |
| /courses/&lt;int:course_id&gt;/delete | POST | 删除课程 |
| /tasks | GET | 任务列表和筛选 |
| /tasks/new | GET、POST | 新建任务 |
| /tasks/&lt;int:task_id&gt; | GET | 任务详情 |
| /tasks/&lt;int:task_id&gt;/edit | GET、POST | 修改任务 |
| /tasks/&lt;int:task_id&gt;/toggle | POST | 切换完成状态 |
| /tasks/&lt;int:task_id&gt;/delete | POST | 删除任务 |

表单页面用 GET 请求显示内容，用 POST 请求保存数据，保存成功后重定向到列表或详情页。

## 六、数据表

### courses：课程表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | INTEGER | 主键，自增 |
| name | TEXT | 课程名称，不可重复，1—60 字符 |
| teacher | TEXT | 任课教师，最多 40 字符，可不填 |
| color | TEXT | 课程颜色 |
| created_at | TEXT | 创建时间 |

### tasks：任务表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | INTEGER | 主键，自增 |
| course_id | INTEGER | 外键，引用 courses.id |
| title | TEXT | 任务名称，1—100 字符 |
| description | TEXT | 任务说明，最多 3000 字符 |
| due_date | TEXT | 截止日期，格式为 YYYY-MM-DD |
| priority | TEXT | high、normal、low |
| status | TEXT | todo、doing、done |
| created_at | TEXT | 创建时间 |
| updated_at | TEXT | 修改时间 |

两张表通过 `tasks.course_id = courses.id` 关联。每次连接 SQLite 时启用外键约束，课程表使用删除限制。建表语句见 schema.sql。

## 七、模板和程序结构

```text
app.py                      Flask 应用、路由和数据处理
schema.sql                  建表语句
requirements.txt            依赖列表
requirements-lock.txt       测试环境中的依赖版本
启动系统.bat                Windows 启动脚本
README.md                   程序说明
说明文档.html               程序说明的 HTML 版本
验证结果.txt                测试输出
templates/
    base.html               公共布局和导航
    _macros.html            表单字段及任务表格等公共内容
    dashboard.html          首页
    courses.html            课程列表
    course_form.html        课程表单
    tasks.html              任务列表
    task_form.html          任务表单
    task_detail.html        任务详情
    error.html              错误页面
static/
    style.css               页面样式
    app.js                  删除确认
tests/test_app.py           功能测试
data/demo.sqlite            示例数据库
docs/screenshots/           页面截图
```

页面通过 Jinja2 继承 base.html，复用导航和整体布局。数据库连接在请求结束后关闭。写入操作使用事务，SQL 使用参数传值。

表单会检查必填项、文本长度、课程是否存在和日期是否合法；日期范围为 2000—2100 年。POST 请求检查 CSRF token，用户填写的文本由 Jinja2 自动转义。程序只监听本机地址，未实现多用户登录。

## 八、测试

在项目文件夹中执行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

共 10 项测试，覆盖页面访问、课程和任务操作、筛选、输入校验、关联删除限制、CSRF、HTML 转义、数据持久化及示例数据初始化。测试使用临时数据库，不修改运行数据库。测试输出见“验证结果.txt”。

## 九、常见问题

- 提示找不到 Flask：使用 `.venv` 中的解释器执行安装和启动命令。
- 提示 Python 版本过低：改用 Python 3.10 或以上版本，不要使用 Python 3.7。
- 提示端口被占用：在 PowerShell 中执行下面的命令，改用 5001 端口。

```powershell
$env:PORT = "5001"
.\.venv\Scripts\python.exe app.py
```

然后访问 http://127.0.0.1:5001/ 。

- 提示表单失效：刷新当前页面后重新填写。
- 双击 HTML 文件不能运行系统：templates 中的文件需要由 Flask 渲染，应先运行 app.py。
