import argparse
import logging
import os
import paho.mqtt.client as mqtt
import sys

# This implicitly init Sentry
from electrobin import celery_app

logger = logging.root

args_parser = argparse.ArgumentParser(description='MQTT Listener for Sensors app')
args_parser.add_argument('host', type=str, nargs=1, help='The host of the MQTT broker to connect to')
args_parser.add_argument(
    'port', type=int, nargs='?', default=1883, help='The port of the MQTT broker to connect to')


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.debug("Connected OK")
        client.subscribe("/sensors/+/data")
    elif rc in [4, 5]:
        logger.warning("Invalid credentials specified")
        client.disconnect()
        sys.exit(1)
    else:
        logger.warning("Connection failed, return code=%s", rc)


def on_message(client, userdata, message):
    try:
        payload = message.payload.decode("ascii")
    except UnicodeDecodeError:
        logger.warning(f"Failed to parse payload ({str(message.payload)}) as ASCII", exc_info=True)
        return
    logger.debug("Message received with payload=%s", payload)
    logger.debug("Message topic=%s, qos=%s, retain flag=%s", message.topic, message.qos, message.retain)

    try:
        celery_app.send_task('apps.sensors.tasks.execute_sensor_data_pipeline', args=[message.topic, payload])
        logger.debug("Successfully sent data for parsing")
    except Exception as e:
        logger.warning("Failed to send data for parsing = %s", e)


def on_disconnect(client, userdata, rc):
    if rc == 0:
        logger.debug("Disconnected gracefully (return code 0)")
    else:
        logger.warning("Disconnected with return code=%s", rc)


if __name__ == '__main__':
    args = args_parser.parse_args()
    username = os.environ.get('MQTT_USERNAME', None)
    password = os.environ.get('MQTT_PASSWORD', None)
    log_level = os.environ.get('LOG_LEVEL', None)

    logging.basicConfig(level=log_level or logging.WARNING, format='%(asctime)s %(levelname)s: %(message)s')

    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.on_disconnect = on_disconnect
    auth_creds_specified = username and password
    if auth_creds_specified:
        mqtt_client.username_pw_set(username, password)
    logger.debug(f"About to connect to {args.host[0]}:{args.port}")
    if auth_creds_specified:
        logger.debug(f"Using credentials {username} / {password}")
    else:
        logger.debug("Connection is anonymous")
    mqtt_client.connect(args.host[0], args.port)
    mqtt_client.loop_forever()
