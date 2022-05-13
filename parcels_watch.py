import sqlite3
import pickle
from parcels import Parcels, time_on_the_road
import base64
import io
from server import print_exception
from send import send
from time import sleep
from datetime import datetime
import settings
import importlib
import os
import sys
import threading
import signal
import httplib2
from selenium.common.exceptions import TimeoutException


def events_list_html(event_list):
    s = io.StringIO()
    for i in event_list:
        s.write('<i>{}</i>\n{}\n'.format(*i))
    s.seek(0)
    return s.read()


def timestamp():
    return datetime.now().strftime('%Y-%m-%d %T')


def watch():
    while True:
        prev = os.stat('/opt/telegram/settings.py').st_mtime
        sleep(1)
        new = os.stat('/opt/telegram/settings.py').st_mtime
        if prev != new:
            importlib.reload(settings)
            print(f'{timestamp()} [INFO] reload settings', flush=True)


def get_second_number(attributes):
    for i in attributes:
        if 'Дополнительные номера отслеживания' in i[0]:
            return i[1]


def signal_hendler(signal_number, frame):
    print(f'{timestamp()} [INFO] get signal {signal_number}', flush=True)
    if signal_number == signal.SIGTERM:
        exit()


def shutdown(e=True):
    URL=f'http://10.8.0.2:4444/wd/hub/session/{parcel.session_id}'
    h, c = httplib2.Http().request(URL, method='DELETE')
    print(f'{timestamp()} [INFO] {c.decode()}', flush=True)
    print(f'{timestamp()} [INFO] delete session {parcel.session_id}', flush=True)
    if e:
        print(f'{timestamp()} [INFO] exit', flush=True)
        exit()


def run():
    global parcel
    print(f'{timestamp()} [INFO] parcels_watch start PID:{os.getpid()}', flush=True)
    while True:
        conn = sqlite3.connect('parcels.db')
        cursor = conn.cursor()
        cursor.execute(f'select * from parcels;')
        result = cursor.fetchall()
        if result:
            for i in result:
                try:
                    parcel_id, parcel_name, user_id, events_64decode, date, second_number = i
                    if events_64decode:
                        events_prev = pickle.loads(base64.b64decode(events_64decode))
                    else:
                        events_prev = []
                    parcel = Parcels(parcel_id, settings.SELENIUM_RUN_TYPE)
                    print(f'{timestamp()} [INFO] start session {parcel.session_id}', flush=True)
                    parcel.get_page_source()
                    events_new = parcel.event_list
                    diff_list = [i for i in events_new if i not in events_prev]
                    if diff_list:
                        events_html = events_list_html(diff_list)
                        time = time_on_the_road(date)
                        send('sendMessage', chat_id=user_id, parse_mode='HTML',
                             text=f'<b>{parcel_name}</b>{time}\n{events_html}')
                        events_64decode = base64.b64encode(pickle.dumps(parcel.event_list)).decode('utf-8')
                        cursor.execute(f'update parcels set events = "{events_64decode}" where id="{parcel_id}";')
                        conn.commit()
                    else:
                        print(f'{timestamp()} [INFO] {parcel_id} no changes', flush=True)

                    new_second_number = get_second_number(parcel.parcel_attributes)
                    if new_second_number and second_number != new_second_number:
                        print(f'{timestamp()} [INFO] {parcel_name} has a second number {new_second_number}', flush=True)
                        sql = f"update parcels set second_track_number='{new_second_number}' where id='{parcel_id}';"
                        cursor.execute(sql)
                        conn.commit()
                except TimeoutException:
                    shutdown(e=False)
                except SystemExit:
                    shutdown()
                except:
                    print(print_exception(), flush=True)
        else:
            print(f'{timestamp()} [INFO] No parcels', flush=True)
        conn.close()
        sleep(3600)


if __name__ == '__main__':
    threading.Thread(target=watch, args=(), daemon=True).start()
    signal.signal(signal.SIGTERM, signal_hendler)
    run()

