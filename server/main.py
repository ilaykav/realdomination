from flask import Flask
from flask import request
from flask import render_template
# import pygmaps

import time
import mapo
import pygmaps
import MySQLdb
import packet

DOMINATION_PORT = 1337
CALL_UPDATE_POINTS_SEQUENCE = 1

HOST = "localhost"
app = Flask(__name__)
db_connection = None

def init_database(db_connection):
    try:
        db_connection.execute('create table sessions (name text, origin_radius double, origin_longitude double, '
                              'origin_latitude float, station_table_name text, users_table_name text, '
                              'first_team_points int, second_team_points int, admin_name text, game_result int);')
    except Exception as e:
        pass

def init_connection():
    db = MySQLdb.connect(HOST, 'root', 'Koko9090')
    db.autocommit(True)
    db_connection = db.cursor()
    db_connection.execute('use realdominationdb')
    return db_connection

@app.route('/', methods=['GET', 'POST'])
def index():
    m_packet = packet.Packet(request, init_connection())
    return m_packet.process()


@app.route('/clear', methods=['GET', 'POST'])
def clear():
    db_connection = init_connection()
    game_name = request.headers.get('game_name')
    db_connection.execute('DROP TABLE {}'.format(game_name+'_stations'))
    db_connection.execute('DROP TABLE {}'.format(game_name+'_users'))
    db_connection.execute('delete from sessions where name = %s', (game_name,))
    return '0'

@app.route('/hello')
def hello():
    return 'Hello, World'

@app.route('/mapp', methods=['GET', 'POST'])
def mapp():

    db_connection = init_connection()
    game_name = request.args.get('game_name')

    db_connection.execute('select longitude, latitude, team from {}'.format(game_name + '_users'))
    points = db_connection.fetchall()

    mymap = pygmaps.pygmaps(points[0][1], points[0][0], 18)

    for point in points:
        mymap.addpoint(point[1], point[0], ('#0000FF' if bool(point[2]-1) else '#FF0000'))

    mymap.draw('./templates/map.html')
    return render_template('map.html')

if __name__ == "__main__":

    db_connection = init_connection()
    init_database(db_connection)

    last_game_names = ()

    while True:
        time.sleep(CALL_UPDATE_POINTS_SEQUENCE)
        db_connection.execute('select name from sessions')
        game_names = db_connection.fetchall()

        # debug games - show all games only when changed
        if last_game_names != game_names:
            last_game_names = game_names
            print('GAMES = ' + str(list(map(lambda x: x[0], game_names))))

        for game_name in game_names:
            packet.update_points(game_name[0], db_connection)





