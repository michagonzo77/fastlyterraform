#!/usr/bin/env python3
import sys
import requests
import os
import json
from datetime import datetime, timedelta
from fuzzywuzzy import process, fuzz
from pprint import pprint

VALID_ENVIRONMENTS = ['production', 'dev', 'qa']
API_TOKEN = os.getenv("FASTLY_API_TOKEN")  # Replace this with your actual API token
CACHE_FILE = "services_cache.json"
FIELDS_CACHE_FILE = "fields_cache.json"
CACHE_EXPIRY_HOURS = 24
TIME_UNITS = ['minute', 'minutes', 'hour', 'hours', 'day', 'days', 'month', 'months']
FUZZY_MATCH_THRESHOLD = 80  # Adjust this threshold based on how strict you want the matching to be
REAL_TIME_BASE_URL = "https://rt.fastly.com"
HISTORICAL_BASE_URL = "https://api.fastly.com"

def debug_print(message):
    if os.getenv("KUBIYA_DEBUG"):
        print(message)

def load_cache(cache_file):
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
            cache_timestamp = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.utcnow() - cache_timestamp < timedelta(hours=CACHE_EXPIRY_HOURS):
                return cache_data['data']
    return None

def save_cache(cache_file, data):
    cache_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'data': data
    }
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f)

def list_services():
    cached_services = load_cache(CACHE_FILE)
    if cached_services:
        debug_print("Loaded services from cache.")
        return cached_services

    url = f"{HISTORICAL_BASE_URL}/service"
    headers = {
        "Fastly-Key": API_TOKEN,
        "Accept": "application/json"
    }
    params = {
        "direction": "ascend",
        "page": 1,
        "per_page": 20,
        "sort": "created"
    }
    
    all_services = {}
    
    while True:
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            services = response.json()
            if not services:
                break
            for service in services:
                all_services[service['name']] = service['id']
            params["page"] += 1
        except requests.exceptions.RequestException as e:
            print(f"Exception when calling Fastly API: {e}\n")
            break
    
    save_cache(CACHE_FILE, all_services)
    return all_services

def construct_service_prefix(service_name, environment):
    if environment == 'production':
        return service_name
    return f"{environment}-{service_name}"

def get_environment(env_name):
    if not env_name:
        return None
    env_name = env_name.lower()
    if env_name in VALID_ENVIRONMENTS:
        return env_name
    return None

def get_historical_data(api_token, service_id, start_time=None, end_time=None, by='minute', field=None):
    base_url = f"{HISTORICAL_BASE_URL}/stats/service/{service_id}"
    if field:
        url = f"{base_url}/field/{field}?from={int(start_time)}&to={int(end_time)}&by={by}&region=global"
    else:
        url = f"{base_url}?from={int(start_time)}&to={int(end_time)}&by={by}&region=global"
    debug_print(f"API URL: {url}")
    headers = {
        "Fastly-Key": api_token,
        "Accept": "application/json"
    }
    
    try:
        debug_print(f"Retrieving data from {start_time} to {end_time}...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        stats_data = response.json()
        return stats_data['data']
    except requests.exceptions.RequestException as e:
        print(f"Exception when calling Fastly API: {e}\n")
        debug_print(f"API Response: {response.text}\n")  # Print API response when an error occurs
        return None

def get_real_time_data(api_token, service_id, field, duration_seconds=5):
    url = f"{REAL_TIME_BASE_URL}/v1/channel/{service_id}/ts/h?limit={duration_seconds}"
    debug_print(f"Real-Time API URL: {url}")
    headers = {
        "Fastly-Key": api_token,
        "Accept": "application/json"
    }
    
    try:
        debug_print("Retrieving real-time data...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        real_time_data = response.json()
        return real_time_data['Data']
    except requests.exceptions.RequestException as e:
        print(f"Exception when calling Fastly Real-Time API: {e}\n")
        debug_print(f"API Response: {response.text}\n")  # Print API response when an error occurs
        return None

def get_best_match(prefix, services):
    # Use fuzzy matching to find the best match for the prefix
    results = process.extract(prefix, services, scorer=fuzz.WRatio)
    
    # Filter results to only include those that have the prefix at the start
    filtered_results = [result for result in results if result[0].startswith(prefix)]
    
    # If no results meet the criteria, fall back to the highest score regardless of prefix
    if not filtered_results:
        best_match = max(results, key=lambda x: x[1])
    else:
        best_match = max(filtered_results, key=lambda x: x[1])
    
    return best_match[0] if best_match else None

def get_matching_field(field_name, stats_data):
    fields_cache = load_cache(FIELDS_CACHE_FILE)
    if fields_cache:
        debug_print("Loaded fields from cache.")
        fields = fields_cache
    else:
        fields = list(stats_data[0].keys()) if stats_data else []
        save_cache(FIELDS_CACHE_FILE, fields)

    # Preprocess field names to improve fuzzy matching
    processed_fields = [field.replace('_', ' ').replace('-', ' ') for field in fields]
    
    # Perform fuzzy matching
    best_match = process.extractOne(field_name, processed_fields, scorer=fuzz.WRatio)
    if best_match[1] < FUZZY_MATCH_THRESHOLD:
        print(f"Ambiguous field name '{field_name}'. Did you mean one of these?")
        suggestions = process.extract(field_name, processed_fields, limit=5, scorer=fuzz.WRatio)
        for suggestion, score in suggestions:
            print(f"  - {suggestion.replace(' ', '_')}")
        sys.exit(1)

    original_fields = {field.replace(' ', '_').replace('-', '_'): field for field in fields}
    return original_fields.get(best_match[0].replace(' ', '_').replace('-', '_')), processed_fields

def format_value(value):
    if value >= 1000:
        return f"{value/1000:.1f}K ({value})"
    return str(value)

def main(environment, service_name, field_name, duration):
    debug_print("Starting the Fastly data retrieval process...")

    environment = get_environment(environment)
    if not environment:
        print(f"No matching environment found for '{environment}'. Available environments: {VALID_ENVIRONMENTS}")
        return

    service_prefix = construct_service_prefix(service_name, environment)
    debug_print(f"Constructed service prefix: {service_prefix}")

    debug_print("Fetching list of services...")
    services = list_services()
    
    if not services:
        print("No services found.")
        return

    best_match = get_best_match(service_prefix, list(services.keys()))
    if not best_match:
        print(f"No matching service found for '{service_prefix}'.")
        return

    service_id = services[best_match]
    debug_print(f"Best matching service: {best_match}")

    # Check if the duration is less than 2 minutes or "now" for real-time data
    if duration.lower() == "now" or (parse_duration(duration)[1] in ['minute', 'minutes'] and int(parse_duration(duration)[0]) < 2):
        print("Waiting for data...")
        debug_print("Retrieving real-time data...")
        stats_data = get_real_time_data(API_TOKEN, service_id, field_name)
        if not stats_data:
            print(f"Unable to retrieve real-time data for service '{best_match}'")
            return
        print("Duration is 5 seconds (waiting for data)")

    else:
        # Calculate start and end times based on the provided duration
        start_time, end_time, by = get_time_range(duration)
        if not start_time:
            return

        if duration.lower() in ["1 hour", "1 hour ago"]:
            debug_print("Including 'by=minute' in the historical data request.")
            stats_data = get_historical_data(API_TOKEN, service_id, start_time, end_time, by='minute')
        elif duration.lower() in ["1 day", "1 day ago"]:
            debug_print("Including 'by=hour' in the historical data request.")
            stats_data = get_historical_data(API_TOKEN, service_id, start_time, end_time, by='hour')
        else:
            debug_print(f"Calculated start_time: {datetime.fromtimestamp(start_time)}, end_time: {datetime.fromtimestamp(end_time)}, by: {by}")
            debug_print(f"Retrieving historical data for service '{best_match}' from {start_time} to {end_time}...")
            stats_data = get_historical_data(API_TOKEN, service_id, start_time, end_time, by)
            if not stats_data:
                print(f"Unable to retrieve historical data for service '{best_match}', switching to real-time data...")
                stats_data = get_real_time_data(API_TOKEN, service_id, field_name)
                if not stats_data:
                    print(f"Unable to retrieve real-time data for service '{best_match}'")
                    return

    debug_print("Performing fuzzy matching for field name...")
    matching_field, all_fields = get_matching_field(field_name, stats_data)
    if not matching_field:
        print(f"No matching field found for '{field_name}'")
        return
    
    debug_print(f"Best matching field: {matching_field}")

    if 'Data' in stats_data:  # Handle real-time data format
        values = [data['aggregated'].get(matching_field, 0) for data in stats_data['Data']]
    else:
        values = [data.get(matching_field, 0) for data in stats_data]

    debug_print(f"Retrieved values for field '{matching_field}':")
    debug_print(f"Gathered {len(values)} data points:\n\n{values}")

    # Sum up all the values
    total_value = sum(values)
    formatted_total_value = format_value(total_value)

    # Display the total value for the specified duration
    print(f"Total value for the last {duration}: {formatted_total_value} (from field: {matching_field})")

    # Get top 3 similar fields, excluding the current field
    suggestions = [
        suggestion for suggestion in process.extract(field_name, all_fields, limit=3, scorer=fuzz.WRatio) 
        if suggestion[0] != matching_field
    ]

    # Print suggestions in a formatted way
    print("Other close fields you might want to query:")
    for suggestion, score in suggestions:
        print(f"  - {suggestion.replace(' ', '_')}")

def parse_duration(duration):
    duration = duration.lower().strip()
    duration_parts = duration.split()
    if len(duration_parts) == 2 and duration_parts[0].isdigit():
        return duration_parts
    elif duration.startswith("last "):
        return duration[5:].split()
    elif duration.endswith(" ago"):
        return duration[:-4].split()
    elif duration_parts[0].isdigit():
        return duration_parts + ['ago']  # Assume ago if no prefix is provided
    else:
        return None, None

def get_time_range(duration):
    now = datetime.utcnow().replace(second=0, microsecond=0)
    duration_parts = parse_duration(duration)
    if not duration_parts:
        print("Invalid duration format. Supported formats: 'X minutes ago', 'X hours ago', 'X days ago', 'X months ago'")
        return None, None, None

    quantity = int(duration_parts[0])
    unit = process.extractOne(duration_parts[1], TIME_UNITS, scorer=fuzz.ratio)[0]
    start_time = None
    end_time = now.timestamp()
    by = 'minute'

    if unit in ['month', 'months']:
        start_time = (now - timedelta(days=30 * quantity)).timestamp()
        by = 'day'
    elif unit in ['day', 'days']:
        start_time = (now - timedelta(days=quantity)).timestamp()
        by = 'day'
    elif unit in ['hour', 'hours']:
        start_time = (now - timedelta(hours=quantity)).timestamp()
        by = 'hour'
    elif unit in ['minute', 'minutes']:
        start_time = (now - timedelta(minutes=quantity)).timestamp()
    else:
        print("Invalid unit format. Supported units are 'minute(s)', 'hour(s)', 'day(s)', 'month(s)'.")
        return None, None, None

    debug_print(f"Calculated start_time: {datetime.fromtimestamp(start_time)}, end_time: {datetime.fromtimestamp(end_time)}, by: {by}")
    return start_time, end_time, by

if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 1 and args[0] == "list_services":
        # Run list_services function
        services = list_services()
        pprint(services)  # Print the services dictionary
    elif len(args) != 4:
        print(f"Usage: python {sys.argv[0]} <environment> <service_name> <field_name> <duration>")
        sys.exit(1)
    else:
        # Parse command-line arguments
        ENVIRONMENT = args[0]  # or 'dev', 'qa'
        SERVICE_NAME = args[1]
        FIELD_NAME = args[2]
        DURATION = args[3]  # e.g., "5 minutes ago", "12 hours ago", "1 day ago", "1 month ago"

        # Call main function
        main(ENVIRONMENT, SERVICE_NAME, FIELD_NAME, DURATION)