#!/bin/bash

# Define the allowed brands and platforms
brands=("aenetworks" "aetv" "biography" "crimecentral" "crimeandinvestigation" "fyi" "history" "historyvault" "historyvaultca" "lifetime" "lifetimemovies" "lmc")
platforms=("android" "androidtv" "appletv" "firetv" "ios" "kepler" "roku" "tizen" "tvos" "vizio" "web" "webos" "weblanding" "xclass")

# Define the services and their IDs
declare -A services
services["dev-yoga"]="28NWcDuK7eJuohc8s3bxwr"
services["qa-yoga"]="29I6lUZbicNV0kVv07zN7V"
services["prod-yoga"]="2AAgt7ZaOboH1ftYfE1Fxu"

# Check if enough arguments are provided
if [ $# -lt 2 ]; then
    echo "Usage: $0 <service_name> <brand_or_platform_or_operation>"
    echo "Available services: ${!services[@]}"
    exit 1
fi

# Get the service name and key
SERVICE_NAME=$1
KEY=$2

# Check if the provided service name is valid
if [[ -z "${services[$SERVICE_NAME]}" ]]; then
    echo "Invalid service name. Available services: ${!services[@]}"
    exit 1
fi

# Check if the provided argument is in the allowed brands or platforms
if [[ " ${brands[@]} " =~ " ${KEY} " ]]; then
    echo "Purging brand: $KEY for service: $SERVICE_NAME"
elif [[ " ${platforms[@]} " =~ " ${KEY} " ]]; then
    echo "Purging platform: $KEY for service: $SERVICE_NAME"
else
    echo "Purging operation: $KEY for service: $SERVICE_NAME"
fi

# Run the fastly purge command
SERVICE_ID=${services[$SERVICE_NAME]}
fastly purge --service-id=$SERVICE_ID --key=$KEY --soft

# Check the result of the fastly command
if [ $? -eq 0 ]; then
    echo "Purge request was successful."
else
    echo "Purge request failed."
fi