set -x

git clone https://github.com/netbox-community/netbox-docker.git
cd netbox-docker
docker-compose pull
docker-compose up -d

while [[ "$(curl -s -o /dev/null -w ''%{http_code}'' http://$(docker-compose port nginx 8080))" != "200" ]]
do
    sleep 5
done

export NETBOX_AGENT__NETBOX__URL="http://$(docker-compose port nginx 8080)"
export NETBOX_AGENT__NETBOX__TOKEN=0123456789abcdef0123456789abcdef01234567

cd -
pytest

cd netbox-docker
docker-compose down
cd -
set +x
