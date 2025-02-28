# Use an official Python runtime as a parent image
FROM python:3-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Set environment variables for configuration
ENV MQTT_BROKER='192.168.1.1'
ENV MQTT_PORT=1883
ENV MQTT_TOPIC=battery/reportEquip
ENV MQTT_USERNAME=test
ENV MQTT_PASSWORD=test
ENV HEARTBEAT_INTERVAL=60
ENV RECONNECT_DELAY=60
ENV APP_CODE=Storcube
ENV LOGIN_NAME='test'
ENV PASSWORD='test'
ENV DEVICE_ID='****'

# Copy the current directory contents into the container at /usr/src/app
COPY batteryMqtt.py .

# Set Python to run unbuffered
ENV PYTHONUNBUFFERED=1

# Install the required Python packages with specific versions
RUN pip install --no-cache-dir \
    websockets==12.0 \
    requests==2.32.3 \
    paho-mqtt==2.1.0


# Run the script when the container launches
CMD ["python", "./batteryMqtt.py"]
