#!/bin/bash

if [ -z "$@" ]
then
  echo "Please specify release version"
  exit 1
fi

echo "legacy-web-app@"$@ > release-info.txt
echo $(git rev-parse HEAD) >> release-info.txt

echo "release-info.txt file re-created"
