set -x

git clone https://github.com/netbox-community/netbox-docker.git
cd netbox-docker

tee docker-compose.override.yml <<EOF
services:
  netbox:
    healthcheck:
      retries: 10
    ports:
      - 8000:8080
    environment:
      SKIP_SUPERUSER: "false"
      SUPERUSER_EMAIL: "test@test.com"
      SUPERUSER_NAME: "test"
      SUPERUSER_PASSWORD: "test"
      SUPER_API_TOKEN: "0123456789abcdef0123456789abcdef01234567"

EOF

docker compose pull
docker compose up -d

while [[ "$(curl -s -o /dev/null -L -w ''%{http_code}'' http://$(docker compose port netbox 8080))" != "200" ]]
do
    sleep 5
done

export NETBOX_AGENT__NETBOX__URL="http://$(docker compose port netbox 8080)"
export NETBOX_AGENT__NETBOX__TOKEN='0123456789abcdef0123456789abcdef01234567'

cd -
pytest
pytest_result=$?

cd netbox-docker
docker compose down
cd -
set +x
exit $pytest_result
