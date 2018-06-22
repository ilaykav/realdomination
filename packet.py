import time
import math
import random
import location
import json
import datetime
import geopy.distance

EATRH_RADIUS = 6371000
POINTS_TO_WIN = 300
CAPTURE_TIME = 10  # in seconds
CALL_UPDATE_POINTS_SEQUENCE = 1

# game state - 0 ok 1 1wins 2 2wins 3 tie 4 game aborted 5 name invalid


def add_distance(mLocation, distance, angle):
    y = distance * math.sin(angle)
    x = distance * math.cos(angle)
    new_latitude = mLocation.latitude + (y / EATRH_RADIUS) * (180 / math.pi);
    new_longitude = mLocation.longitude + (x / EATRH_RADIUS) * (180 / math.pi) / math.cos(mLocation.latitude * math.pi / 180);
    # print("Location: %f, %f" % (new_latitude, new_longitude))
    return location.Location(float(new_longitude), float(new_latitude))

def calculate_distance(location1, location2):

    lat2 = location2.latitude
    lat1 = location1.latitude
    lon1 = location1.longitude
    lon2 = location2.longitude

    coords_1 = (lat1, lon1)
    coords_2 = (lat2, lon2)

    d = geopy.distance.vincenty(coords_1, coords_2).m

    print(d)
    return d # result in meters

# will be called every CALL_UPDATE_POINTS_SEQUENCE
def update_points(gamename, db_connection):

    # statsions = ((2/1/0 - team, 1.4.16-14:54:12 - time)...)
    db_connection.execute('select team, from_unixtime(UNIX_TIMESTAMP(initial_time)) from {}'.format(gamename+'_stations'))
    stations = db_connection.fetchall()
    for station_index, station in enumerate(stations):
        if station[0] != 0 and (datetime.datetime.now()-station[1]).total_seconds() > CAPTURE_TIME:
            team_points = 'first_team_points' if station[0] == 1 else 'second_team_points'
            db_connection.execute('select {} from sessions where name = %s'.format(team_points), (gamename, ))
            points = db_connection.fetchall()[0][0]
            print(points)

            db_connection.execute('update sessions set {} = %s where name = %s'.format(team_points), (points+1, gamename))

    db_connection.execute('select first_team_points, second_team_points from sessions where name = %s', (gamename,))
    points = db_connection.fetchall()[0]
    print(points)
    wins = list(map(lambda point: point >= POINTS_TO_WIN, points))
    print(wins)
    # first check for tie, then for any winner, then if not found return 0
    result = -1
    if all(wins):
        result = 0
    if any(wins):
        result = wins.index(True)+1

    print(result)
    db_connection.execute('update sessions set game_result= %s where name = %s', (result, gamename))

class Packet(object):
    def __init__(self, request, db_connection):
        self.data = request.headers
        self.type = self.data.get('type')
        self.username = self.data.get('username')
        self.db_connection = db_connection

    # returns message to client if needed
    def process(self):
        """

        """
        callbacks = {
            'create_game': self.process_create_game,
            'join_game': self.process_join_game,
            'update_game': self.process_update_game,
            'quit_game': self.process_quit_game,
            'close_game': self.process_close_game
        }

        print('Processing packet: type - ' + str(self.type))
        return callbacks[self.type]()

    def process_create_game(self):

        game_name = self.data.get('game_name')
        user_name = self.data.get('user_name')
        origin_location = location.Location(json.loads(self.data.get('origin_longitude')), json.loads(self.data.get('origin_latitude')))
        origin_radius = json.loads(self.data.get('origin_radius'))
        number_of_stations = self.data.get('number_of_stations')
        stations_radius = self.data.get('stations_radius')

        # if game ended -
        try:
            self.db_connection.execute("CREATE TABLE {} (longitude double, latitude double, radius double, team int, initial_time timestamp, num_players int, id INT NOT NULL AUTO_INCREMENT, PRIMARY KEY (id))".format(game_name + '_stations'))
        except Exception as e:

            print(e)

            # talbe with this name already exists!
            return json.dumps({'game_name': game_name, 'game_state': 5})

        self.db_connection.execute("INSERT INTO sessions VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (game_name, origin_radius, origin_location.longitude, origin_location.latitude, game_name + '_stations', game_name + '_users', 0, 0, user_name, -1))

        current_time = time.time()

        for number_of_station in range(int(number_of_stations)):
            new_location = add_distance(origin_location, random.uniform(0, origin_radius), random.uniform(0, math.pi * 2))
            self.db_connection.execute("INSERT INTO {} (longitude, latitude, radius, team, initial_time, num_players) values (%s, %s, %s, %s, %s, %s)".format(game_name+'_stations'), (float(new_location.longitude), float(new_location.latitude), float(stations_radius), 0, datetime.datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S'), 0))


        self.db_connection.execute("CREATE TABLE {} (name text, longitude double, latitude double, team int)".format(game_name+'_users'))

        return json.dumps({'game_name': game_name, 'game_state': 0})

    def process_join_game(self):
        game_name = self.data.get('game_name')
        user_name = self.data.get('user_name')
        loc = location.Location(self.data.get('longitude'), self.data.get('latitude'))

        # init number_of_teams = 2 for demo server
        number_of_teams = 2
        num_of_users = [0, 0]

        self.db_connection.execute('SELECT COUNT(*) FROM sessions WHERE name = %s', (game_name,))
        if self.db_connection.fetchall()[0][0] != 1:
            # game name not exists
            return json.dumps({'game_name': game_name, 'game_state': 5})

        # self.db_connection.execute('SELECT COUNT(*) FROM {} WHERE name = %s'.format(game_name+'_users'), (user_name,))
        # if self.db_connection.fetchall()[0][0] > 0:
        #     # game name not exists
        #     return json.dumps({'game_name': game_name, 'game_state': 5})

        print(num_of_users)
        for team_number in range(number_of_teams):
            self.db_connection.execute("SELECT COUNT(name) from {} where team = %s".format(game_name+'_users'), (team_number + 1,))
            num_of_users_response = self.db_connection.fetchall()[0]
            print(num_of_users_response)

            if num_of_users_response is not None:
                num_of_users[team_number] = num_of_users_response[0]

        smallest_team = num_of_users.index(min(num_of_users))+1

        self.db_connection.execute("INSERT INTO {} VALUES(%s, %s, %s, %s)".format(game_name+'_users'), (user_name,
                                                                                                        loc.longitude,
                                                                                                        loc.latitude,
                                                                                                        smallest_team))

        self.db_connection.execute("select origin_longitude, origin_latitude from sessions where name = %s", (game_name,))
        origins = self.db_connection.fetchall()[0]

        # return: game_name, game_status (created - 0)
        d = {'game_name': game_name, 'origin_long': origins[0], 'origin_lat': origins[1], 'game_state': 0,
             'team': smallest_team, 'stations': self.stations_to_json(game_name)}
        return json.dumps(d)

    def process_update_game(self):
        user_name = self.data.get('user_name')
        loc = location.Location(self.data.get('longitude'), self.data.get('latitude'))
        game_name = self.data.get('game_name')

        self.db_connection.execute('select team from {} where name = %s'.format(game_name+'_users'), (user_name,))
        player_team = self.db_connection.fetchall()[0][0]

        self.db_connection.execute('SELECT game_result FROM sessions WHERE name = %s', (game_name,))
        game_result = self.db_connection.fetchall()[0][0]

        if game_result != -1:


            self.db_connection.execute('delete from {} where name = %s'.format(game_name + '_users'), (user_name,))
            self.db_connection.execute('SELECT COUNT(*) FROM {}'.format(game_name + '_users'))

            if self.db_connection.fetchall()[0][0] == 0:
                #  all users deleted, delete session and users db

                self.db_connection.execute('DROP TABLE {}'.format(game_name + '_users'))
                # self.db_connection.execute('delete from sessions where name = %s', (game_name,))

            return json.dumps({'game_name': game_name, 'game_status': game_result})

        self.db_connection.execute('update {} set longitude = %s, latitude = %s where name = %s'.format(game_name +'_users',),
                                   (loc.longitude,
                                   loc.latitude,
                                   user_name))

        # check if user is in station radius
        # for station in stations_in_game:
        #   if user.location.distance(station.location) < station.radius:
        #       if station.team changed:
        #           station.team = user.name
        #           station.time = time.now()
        #       station.num_users = new_num_users


        self.db_connection.execute('select longitude, latitude, radius, id from {}'.format(game_name+'_stations'))
        # stations_info = ((long, lat, rad), ...)
        stations_info = self.db_connection.fetchall()

        self.db_connection.execute('SELECT COUNT(*) FROM {}'.format(game_name+'_stations'))
        stations_num = self.db_connection.fetchall()[0][0]
        print(stations_num)

        for station_index in range(stations_num):


            station_location = location.Location(stations_info[station_index][0], stations_info[station_index][1])
            station_id = stations_info[station_index][3]

            # if we got here it means that the change in the location is causing a change in the users of this station
            num_users = [self.num_users_near_location(1, station_location, stations_info[station_index][2], game_name), \
                         self.num_users_near_location(2, station_location, stations_info[station_index][2], game_name)]

            # update time if team of station changes
            self.db_connection.execute('select team from {} where id = %s'.format(game_name+'_stations'), (station_id,))
            last_team = self.db_connection.fetchall()[0][0]  # 1 / 2

            print(num_users)
            current_team = last_team
            if num_users[0] != num_users[1]:
                current_team = num_users.index(max(num_users))+1  # 1 /2


            print("current team")
            # update users
            self.db_connection.execute('update {} set num_players = %s where id = %s'.format(game_name + '_stations'), \
                                       (max(num_users),
                                        station_id))

            print(str(current_team) + " , " + str(last_team))

            # if team has been changed update  initial_time of station and update team
            if int(current_team) != int(last_team) and any(map(lambda x: x > 0, num_users)):
                print("current team: " + str(current_team) + ", last team: " + str(last_team))
                print("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

                # update team
                self.db_connection.execute('update {} set team = %s where id = %s'.format(game_name + '_stations'),
                                           (current_team, station_id))
                # update initial_time
                current_time = time.time()
                self.db_connection.execute('update {} set  initial_time = %s where id = %s'.format(game_name + '_stations'),
                                           (datetime.datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S'),
                                            station_id))


        st = self.stations_to_json(game_name)
        pl = self.players_to_json(game_name, player_team, user_name)

        self.db_connection.execute('select first_team_points, second_team_points from sessions where name = %s', (game_name,))
        points = self.db_connection.fetchall()[0]

        return json.dumps({'game_name': game_name, 'game_state': 0, 'stations': st,
                          'players': pl, 'points': points})

    def players_to_json(self, game_name, player_team, player_name):
        players_list = []
        dic_keys = ['name', 'longitude', 'latitude']
        self.db_connection.execute('select name, longitude, latitude from {} where team= %s and name != %s'.format(game_name + '_users'), (player_team, player_name))

        players = self.db_connection.fetchall()


        for player_data in players:
            dic = {}
            for index, value in enumerate(player_data):
                dic[dic_keys[index]] = value
            players_list.append(dic)
        return players_list

    def process_quit_game(self):
        user_name = self.data.get('user_name')
        game_name = self.data.get('game_name')

        self.db_connection.execute('select admin_name from sessions where name = %s', (game_name,))
        user_admin = self.db_connection.fetchall()[0][0]

        if user_admin == user_name:
            self.db_connection.execute('select name from {} where name != %s'.format(game_name+'_users'), (user_admin,))
            new_admin = self.db_connection.fetchall()[0][0]

            # set second user to be an admin
            self.db_connection.execute('update sessions set admin_name = %s where name = %s', (new_admin, game_name))

        self.db_connection.execute('delete from {} where name = %s'.format(game_name+'_users'), (user_name, ))

        return json.dumps({'game_name': game_name})

    def process_close_game(self):

        user_name = self.data.get('user_name')
        game_name = self.data.get('game_name')

        self.db_connection.execute('select admin_name from sessions where name = %s', (game_name,))
        admin = self.db_connection.fetchall()[0][0]

        # not admin has no permission to close the game
        if not admin == user_name:
            return json.dumps({'game_name': game_name})

        self.db_connection.execute('update sessions set game_result = 4 where name = %s', (game_name, ))
        self.db_connection.execute('DROP TABLE {}'.format(game_name + '_stations'))
        return json.dumps({'game_name': game_name, 'game_state': 4})

    def num_users_near_location(self, team, m_location, radius, game_name):
        users_num = 0

        self.db_connection.execute('select longitude, latitude from {} where team = %s'.format(game_name+'_users'), (team,))

        # ((lon, lat), ..)
        users = self.db_connection.fetchall()

        # iterate over every user
        for user in users:

            # get player location and check if it's in given location radius
            player_location = location.Location(user[0], user[1])
            if calculate_distance(player_location, m_location) <= radius:
                print("is near")
                users_num += 1

        return users_num

    def stations_to_json(self, game_name):
        stations_list = []
        dic_keys = ['longitude', 'latitude', 'radius', 'status', 'initial_time', 'num_of_players', ]
        self.db_connection.execute('select longitude, latitude, radius, team, from_unixtime(UNIX_TIMESTAMP(initial_time)), num_players from {}'.format(game_name+'_stations'))
        stations = self.db_connection.fetchall()
        for station in stations:
            dic = {}
            for index, value in enumerate(station):

                # if values precent
                if index == 4:
                    dic[dic_keys[index]] = value.strftime('%s')

                # if values status
                elif index == 3:

                    if value != 0 and (datetime.datetime.now() - station[4]).total_seconds() < CAPTURE_TIME:
                        dic[dic_keys[index]] = value+2
                    else:
                        dic[dic_keys[index]] = value

                else:
                    dic[dic_keys[index]] = value

            stations_list.append(dic)
        return stations_list

