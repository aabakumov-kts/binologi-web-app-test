def validate_route_points(route_points):
    for point in route_points:
        if any(attr not in point for attr in ['id', 'city', 'fullness', 'address', 'serial_number', 'location']):
            return False
        if any(attr not in point[container] for (container, attr) in [('city', 'title'), ('fullness', 'value')]):
            return False
        if any(attr not in point['location'] for attr in ['x', 'y']):
            return False
    return True


def convert_web_app_route_points(route_points, default_container_volume):
    points = []
    for point in route_points:
        route_point = {}
        route_point['id'] = point['id']
        route_point['city'] = point['city']['title']
        route_point['fullness'] = point['fullness']['value']
        route_point['address'] = point['address']
        route_point['title'] = point['serial_number']
        route_point['latitude'] = point['location']['y']
        route_point['longitude'] = point['location']['x']
        if 'current_fullness_volume' in point:
            route_point['volume'] = point['current_fullness_volume']
        else:
            route_point['volume'] = default_container_volume
        points.append(route_point)
    return points
