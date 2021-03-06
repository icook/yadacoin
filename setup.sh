sudo mkdir /data/db -p
sudo chmod 777 /data/db
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 2930ADAE8CAF5059EE73BB4B58712A2291FA4AD5
sudo echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu xenial/mongodb-org/3.6 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-3.6.list
sudo apt update
sudo apt install -y mongodb-org
sudo systemctl enable mongod.service
sudo systemctl start mongod.service
sudo apt install -y libxml2-dev libxmlsec1-dev python-dev build-essential
cd ~
git clone https://github.com/pdxwebdev/yadacoin.git
cd yadacoin
sudo apt install -y python-pip
sudo pip install virtualenv
virtualenv venv
venv/bin/pip install -r requirements.txt
venv/bin/python utils/generate_config.py auto > config/config.json
venv/bin/python utils/generate_services.py
sudo cp services/* /lib/systemd/system/.
sudo systemctl daemon-reload
sudo systemctl enable yadacoin-serve
sudo systemctl enable yadacoin-mine
sudo systemctl enable yadacoin-consensus
sudo service yadacoin-mine start
sudo service yadacoin-consensus start
sudo service yadacoin-serve start