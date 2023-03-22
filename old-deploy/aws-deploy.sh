#!/bin/bash
#pip install python-lambda -U
lambda deploy \
  --config-file aws-config.yaml \
  --requirements requirements.txt