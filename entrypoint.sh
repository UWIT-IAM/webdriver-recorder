#!/usr/bin/env bash
cmd="$@"

function get_selenium_status {
    resp=$(curl -sSL "http://selenium:4444/wd/hub/status")
    if [[ "$?" -gt 0 ]]
    then
        return 1
    fi
    ready=$(echo "$resp" | jq -r '.value.ready')
    test "${ready}" == "true"
}


while ! get_selenium_status
do
    echo "Waiting for the grid..."
    sleep 2
done

>&2 echo "Selenium Grid is up - executing tests"
set -e
exec $cmd
