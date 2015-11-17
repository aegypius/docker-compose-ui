"""
Docker Compose UI, flask based application
"""

from flask import Flask, jsonify, request
from scripts.bridge import ps_, get_project, get_container_from_id, get_yml_path
from scripts.find_yml import find_yml_files
from scripts.requires_auth import requires_auth, authentication_enabled, \
  disable_authentication, set_authentication
from json import loads
import logging
import requests
import docker
import os
import traceback
import requests

# Flask Application
API_V1 = '/api/v1/'
YML_PATH = os.environ.get('YML_PATH', '/opt/docker-compose-projects')
logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__, static_url_path='')

# load project definitions
projects = find_yml_files(YML_PATH)

logging.debug(projects)


def get_project_with_name(name):
    """
    get docker compose project given a project name
    """
    path = projects[name]
    return get_project(path)

# REST endpoints

@app.route(API_V1 + "projects", methods=['GET'])
def list_projects():
    """
    List docker compose projects
    """
    global projects
    projects = find_yml_files(YML_PATH)
    return jsonify(projects=projects)

@app.route(API_V1 + "projects/<name>", methods=['GET'])
def project_containers(name):
    """
    get project details
    """
    project = get_project_with_name(name)
    containers = ps_(project)
    return jsonify(containers=containers)


@app.route(API_V1 + "projects/yml/<name>", methods=['GET'])
def project_yml(name):
    """
    get yml content
    """
    path = get_yml_path(projects[name])
    with open(path) as data_file:
        return jsonify(yml=data_file.read())

@app.route(API_V1 + "projects/<name>/<container_id>", methods=['GET'])
def project_container(name, container_id):
    """
    get container details
    """
    project = get_project_with_name(name)
    container = get_container_from_id(project.client, container_id)
    return jsonify(
        id=container.id,
        short_id=container.short_id,
        human_readable_command=container.human_readable_command,
        name=container.name,
        name_without_project=container.name_without_project,
        number=container.number,
        ports=container.ports,
        ip=container.get('NetworkSettings.IPAddress'),
        labels=container.labels,
        log_config=container.log_config,
        image=container.image,
        links=container.links(),
        environment=container.environment
        )

@app.route(API_V1 + "projects/<name>", methods=['DELETE'])
@requires_auth
def kill(name):
    """
    docker-compose kill
    """
    get_project_with_name(name).kill()
    return jsonify(command='kill')

@app.route(API_V1 + "projects", methods=['PUT'])
@requires_auth
def pull():
    """
    docker-compose pull
    """
    name = loads(request.data)["id"]
    get_project_with_name(name).pull()
    return jsonify(command='pull')

@app.route(API_V1 + "services", methods=['PUT'])
@requires_auth
def scale():
    """
    docker-compose scale
    """
    req = loads(request.data)
    name = req['project']
    service_name = req['service']
    num = req['num']

    project = get_project_with_name(name)
    project.get_service(service_name).scale(desired_num=int(num))
    return jsonify(command='scale')

@app.route(API_V1 + "projects", methods=['POST'])
@requires_auth
def up_():
    """
    docker-compose up
    """
    name = loads(request.data)["id"]
    containers = get_project_with_name(name).up()
    logging.debug(containers)
    return jsonify(
        {
            'command': 'up',
            'containers': map(lambda container: container.name, containers)
        })

@app.route(API_V1 + "build", methods=['POST'])
@requires_auth
def build():
    """
    docker-compose build
    """
    name = loads(request.data)["id"]
    get_project_with_name(name).build()
    return jsonify(command='build')

@app.route(API_V1 + "create", methods=['POST'])
@requires_auth
def create():
    """
    create new project
    """
    data = loads(request.data)

    directory = YML_PATH + '/' + data["name"]
    os.makedirs(directory)

    file = directory + "/docker-compose.yml"
    out_file = open(file, "w")
    out_file.write(data["yml"])
    out_file.close()

    return jsonify(path=file)


@app.route(API_V1 + "search", methods=['POST'])
def search():
    """
    search for a project on www.composeregistry.com
    """
    query = loads(request.data)['query']
    r = requests.get('http://www.composeregistry.com/api/v1/search',
        params={'query': query}, headers={'x-key': 'default'})
    if r.status_code == 200:
        return jsonify(r.json())
    else:
        response = jsonify(r.json())
        response.status_code = r.status_code
        return response


@app.route(API_V1 + "yml", methods=['POST'])
def yml():
    """
    get yml content from www.composeregistry.com
    """
    id = loads(request.data)['id']
    r = requests.get('http://www.composeregistry.com/api/v1/yml',
        params={'id': id}, headers={'x-key': 'default'})
    return jsonify(r.json())


@app.route(API_V1 + "start", methods=['POST'])
@requires_auth
def start():
    """
    docker-compose start
    """
    name = loads(request.data)["id"]
    get_project_with_name(name).start()
    return jsonify(command='start')

@app.route(API_V1 + "stop", methods=['POST'])
@requires_auth
def stop():
    """
    docker-compose stop
    """
    name = loads(request.data)["id"]
    get_project_with_name(name).stop()
    return jsonify(command='stop')

@app.route(API_V1 + "logs/<name>", defaults={'limit': "all"}, methods=['GET'])
@app.route(API_V1 + "logs/<name>/<int:limit>", methods=['GET'])
def logs(name, limit):
    """
    docker-compose logs
    """
    lines = {}
    for k in get_project_with_name(name).containers(stopped=True):
        lines[k.name] = k.logs(timestamps=True, tail=limit).split('\n')

    return jsonify(logs=lines)

@app.route(API_V1 + "logs/<name>/<container_id>", defaults={'limit': "all"}, methods=['GET'])
@app.route(API_V1 + "logs/<name>/<container_id>/<int:limit>", methods=['GET'])
def container_logs(name, container_id, limit):
    """
    docker-compose logs of a specific container
    """
    project = get_project_with_name(name)
    container = get_container_from_id(project.client, container_id)
    lines = container.logs(timestamps=True, tail=limit).split('\n')
    return jsonify(logs=lines)

@app.route(API_V1 + "host", methods=['GET'])
def host():
    """
    docker host info
    """
    host_value = os.getenv('DOCKER_HOST')

    return jsonify(host=host_value)


@app.route(API_V1 + "host", methods=['POST'])
@requires_auth
def set_host():
    """
    set docker host
    """
    new_host = loads(request.data)["id"]
    if new_host == None:
        if os.environ.has_key('DOCKER_HOST'):
            del os.environ['DOCKER_HOST']
        return jsonify()
    else:
        os.environ['DOCKER_HOST'] = new_host
        return jsonify(host=new_host)

@app.route(API_V1 + "authentication", methods=['GET'])
def authentication():
    """
    check if basic authentication is enabled
    """
    return jsonify(enabled=authentication_enabled())

@app.route(API_V1 + "authentication", methods=['DELETE'])
@requires_auth
def disable_basic_authentication():
    """
    disable basic authentication
    """
    disable_authentication()
    return jsonify(enabled=False)

@app.route(API_V1 + "authentication", methods=['POST'])
@requires_auth
def enable_basic_authentication():
    """
    set up basic authentication
    """
    data = loads(request.data)
    set_authentication(data["username"], data["password"])
    return jsonify(enabled=True)

# static resources
@app.route("/")
def index():
    """
    index.html
    """
    return app.send_static_file('index.html')

## basic exception handling

@app.errorhandler(requests.exceptions.ConnectionError)
def handle_connection_error(err):
    """
    connection exception handler
    """
    return 'docker host not found: ' + str(err), 500

@app.errorhandler(docker.errors.DockerException)
def handle_docker_error(err):
    """
    docker exception handler
    """
    return 'docker exception: ' + str(err), 500

@app.errorhandler(Exception)
def handle_generic_error(err):
    """
    default exception handler
    """
    traceback.print_exc()
    return 'error: ' + str(err), 500

# run app
if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True, threaded=True)
