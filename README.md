# Homeassistant Edenic

Send data from Bluelab Edenic to Home Assistant

## Install

Clone the respository: `git clone git@github.com:farm-urban/fufarm_ha_edenic.git`
Create the python virtual environment:

```cd fufarm_ha_edenic/mqtt_bridge
python -m venv ./venv
source ./venv/bin/activate
pip install paho-mqtt requests pyyaml
```

Edit `edenic.yml` to set the variables required.

Edit `edenic.service` to set the correct paths and install with:

```
sudo cp edenic.service /etc/systemd/system/edenic.service
sudo systemctl daemon-reload
sudo systemctl start edenic.service
```

## Debugging

Getting devices:

```
ORG_ID=9e9efe10-6e9f-11ef-9338-8dff4b34f2dc
API_KEY=XXX
curl -v -X POST "https://api.edenic.io/api/v1/device/${ORG_ID}" \
  -H "Authorization: ${API_KEY}"
```
