import re
import time
from datetime import datetime

from flask import jsonify, render_template, request

from server import app, auth, database, reloader
from server.models import FlagStatus


@app.template_filter('timestamp_to_datetime')
def timestamp_to_datetime(s):
    return datetime.fromtimestamp(s)


@app.route('/')
@auth.auth_required
def index():
    distinct_values = {}
    for column in ['sploit', 'status', 'team']:
        rows = database.query('SELECT DISTINCT {} FROM flags ORDER BY {}'.format(column, column))
        distinct_values[column] = [item[column] for item in rows]

    config = reloader.get_config()

    server_tz_name = time.strftime('%Z')
    if server_tz_name.startswith('+'):
        server_tz_name = 'UTC' + server_tz_name

    return render_template('index.html',
                           flag_format=config['FLAG_FORMAT'],
                           distinct_values=distinct_values,
                           server_tz_name=server_tz_name)


FORM_DATETIME_FORMAT = '%Y-%m-%d %H:%M'
FLAGS_PER_PAGE = 30


@app.route('/ui/show_flags', methods=['POST'])
@auth.auth_required
def show_flags():
    conditions = []
    for column in ['sploit', 'status', 'team']:
        value = request.form[column]
        if value:
            conditions.append(('{} = ?'.format(column), value))
    for column in ['flag', 'checksystem_response']:
        value = request.form[column]
        if value:
            conditions.append(('INSTR(LOWER({}), ?)'.format(column), value.lower()))
    for param in ['time-since', 'time-until']:
        value = request.form[param].strip()
        if value:
            timestamp = round(datetime.strptime(value, FORM_DATETIME_FORMAT).timestamp())
            sign = '>=' if param == 'time-since' else '<='
            conditions.append(('time {} ?'.format(sign), timestamp))
    if request.form.get('time-ago'):
        value = int(request.form['time-ago'])
        now = int(time.time())
        conditions.append((f'time >= ?', now - 60 * value))
    page_number = int(request.form['page-number'])
    if page_number < 1:
        raise ValueError('Invalid page-number')

    if conditions:
        chunks, values = list(zip(*conditions))
        conditions_sql = 'WHERE ' + ' AND '.join(chunks)
        conditions_args = list(values)
    else:
        conditions_sql = ''
        conditions_args = []

    sql = 'SELECT * FROM flags ' + conditions_sql + ' ORDER BY time DESC LIMIT ? OFFSET ?'
    args = conditions_args + [FLAGS_PER_PAGE, FLAGS_PER_PAGE * (page_number - 1)]
    flags = database.query(sql, args)

    sql = 'SELECT COUNT(*) FROM flags ' + conditions_sql
    args = conditions_args
    total_count = database.query(sql, args)[0][0]

    return jsonify({
        'rows': [dict(item) for item in flags],

        'rows_per_page': FLAGS_PER_PAGE,
        'total_count': total_count,

        'stats': render_template(
            'progress.html',
            counts=get_flag_counts(conditions=conditions_sql, conditions_args=conditions_args)
        ),
    })


@app.route('/ui/post_flags_manual', methods=['POST'])
@auth.auth_required
def post_flags_manual():
    config = reloader.get_config()
    flags = re.findall(config['FLAG_FORMAT'], request.form['text'])

    cur_time = round(time.time())
    rows = [(item, 'Manual', '*', cur_time, FlagStatus.QUEUED.name)
            for item in flags]

    db = database.get()
    db.executemany("INSERT OR IGNORE INTO flags (flag, sploit, team, time, status) "
                   "VALUES (?, ?, ?, ?, ?)", rows)
    db.commit()

    return ''


@app.route('/ui/get_client')
@auth.auth_required
def get_client():
    from flask import send_file
    import io
    import requests
    with open('../start_sploit.py', 'r') as f:
        client_file = f.read()
    config = reloader.get_config()
    my_ip = requests.get('http://ifconfig.me/').text
    client_file = client_file.replace('farm.kolambda.com', my_ip)
    if config['ENABLE_API_AUTH']:
        token = config['API_TOKEN']
        client_file = client_file.replace("metavar='TOKEN',", f"metavar='TOKEN', default='{token}',")
    return send_file(
        io.BytesIO(client_file.encode()),
        attachment_filename='start_sploit.py',
        as_attachment=True,
    )


def get_flag_counts(conditions='', conditions_args=None):
    sql = f'SELECT sploit, status, COUNT(*) as count FROM flags {conditions} GROUP BY sploit, status'
    q = database.query(sql, conditions_args)
    counts = {'Total': {'TOTAL': 0}}
    for sploit, status, count in q:
        if sploit not in counts:
            counts[sploit] = {'TOTAL': 0}
        counts[sploit]['TOTAL'] += count
        counts[sploit][status] = {'count': count}
        if status not in counts['Total']:
            counts['Total'][status] = {'count': 0}
        counts['Total'][status]['count'] += count
        counts['Total']['TOTAL'] += count
    for sploit in counts:
        for status in counts[sploit]:
            if status == 'TOTAL':
                continue
            counts[sploit][status]['percent'] = counts[sploit][status]['count'] / counts['Total']['TOTAL'] * 100
    if len(counts) <= 2:
        counts.pop('Total')
    return dict(sorted(counts.items(), key=lambda x: x[1]['TOTAL'], reverse=True))
