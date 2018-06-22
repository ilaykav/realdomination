
class Map(object):
    def __init__(self, game_name, db_connection):
        self.data = []
        self.game_name= game_name
        db_connection.execute('select longitude, latitude, name from {}'.format(game_name+'_users'))
        points = db_connection.fetchall()
        for point in points:
            self.data.append([point[1], point[0], point[2]])

    def __str__(self):
        centerLat = sum(( x[0] for x in self.data)) / len(self.data)
        centerLon = sum(( x[1] for x in self.data)) / len(self.data)
        markersCode = "\n".join(
            [ """new google.maps.Marker({{
                position: new google.maps.LatLng({lat}, {lon}),
                map: map,
                title: "asd"
                }});""".format(lat=x[0], lon=x[1]) for x in self.data
            ])
        return """
            <script src="https://maps.googleapis.com/maps/api/js?v=3.exp&sensor=false"></script>
            <div id="map-canvas" style="height: 100%; width: 100%"></div>
            <script type="text/javascript">
                var map;
                var image = '/home/ilayk/PycharmProjects/realdomination/first_pin.png'
                function show_map() {{
                    map = new google.maps.Map(document.getElementById("map-canvas"), {{
                        zoom: 16,
                        center: new google.maps.LatLng({centerLat}, {centerLon})
                    }});
                    {markersCode}
                }}
                google.maps.event.addDomListener(window, 'load', show_map);
                
            </script>
        """.format(centerLat=centerLat, centerLon=centerLon,
                   markersCode=markersCode)

