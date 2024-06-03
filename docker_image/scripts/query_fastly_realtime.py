#!/usr/bin/env python3
import sys
import requests
import os
import json
from datetime import datetime, timedelta
from fuzzywuzzy import process, fuzz
from pprint import pprint
import time
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

VALID_ENVIRONMENTS = ['production', 'dev', 'qa']
API_TOKEN = os.getenv("FASTLY_API_TOKEN")  # Replace this with your actual API token
SLACK_API_TOKEN = os.getenv("SLACK_API_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")
SLACK_THREAD_TS = os.getenv("SLACK_THREAD_TS")
CACHE_FILE = "services_cache.json"
FIELDS_CACHE_FILE = "fields_cache.json"
CACHE_EXPIRY_HOURS = 24
TIME_UNITS = ['second', 'seconds', 'minute', 'minutes', 'hour', 'hours', 'day', 'days', 'week', 'weeks', 'month', 'months']
FUZZY_MATCH_THRESHOLD = 80  # Adjust this threshold based on how strict you want the matching to be
REAL_TIME_BASE_URL = "https://rt.fastly.com"
HISTORICAL_BASE_URL = "https://api.fastly.com"
DEFAULT_STREAM_DURATION = 60  # Default streaming duration in seconds
DEFAULT_WAIT_INTERVAL = 2  # Default wait interval for real-time streaming
FASTLY_DASHBOARD_HISTORICAL_URL = "https://manage.fastly.com/observability/dashboard/system/overview/historic/{service_id}?range={range}&region=all"
FASTLY_DASHBOARD_REALTIME_URL = "https://manage.fastly.com/observability/dashboard/system/overview/realtime/{service_id}?range={range}"

COMMON_FIELDS = ["status_5xx", "requests", "hits", "miss", "all_pass_requests"]

def debug_print(message):
    if os.getenv("KUBIYA_DEBUG"):
        print(message)

def load_cache(cache_file):
    try:
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
                cache_timestamp = datetime.fromisoformat(cache_data['timestamp'])
                if datetime.utcnow() - cache_timestamp < timedelta(hours=CACHE_EXPIRY_HOURS):
                    return cache_data['data']
    except Exception as e:
        print(f"Error loading cache from {cache_file}: {e}")
    return None

def save_cache(cache_file, data):
    try:
        cache_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'data': data
        }
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)
    except Exception as e:
        print(f"Error saving cache to {cache_file}: {e}")

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
    
    try:
        while True:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            services = response.json()
            if not services:
                break
            for service in services:
                all_services[service['name']] = service['id']
            params["page"] += 1
    except requests.exceptions.RequestException as e:
        print(f"Error fetching services from Fastly API: {e}")
    
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
        print(f"Error retrieving historical data from Fastly API: {e}")
        return None

def get_real_time_data(api_token, service_id, duration_seconds=5):
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
        print(f"Error retrieving real-time data from Fastly API: {e}")
        return None

def get_best_match(prefix, services):
    results = process.extract(prefix, services, scorer=fuzz.WRatio)
    filtered_results = [result for result in results if result[0].startswith(prefix)]
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

    processed_fields = [field.replace('_', ' ').replace('-', ' ') for field in fields]
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
    try:
        value = float(value)  # Ensure the value is a number
        if value >= 1000:
            return f"{value / 1000:.1f}K ({int(value)})"
        return str(int(value))
    except (ValueError, TypeError):
        return str(value)

def send_slack_message(channel, thread_ts, blocks):
    client = WebClient(token=SLACK_API_TOKEN)
    try:
        response = client.chat_postMessage(channel=channel, thread_ts=thread_ts, blocks=blocks)
        return response["channel"], response["ts"]
    except SlackApiError as e:
        print(f"Error sending message to Slack: {e.response['error']}")
        return None

def update_slack_message(channel, ts, blocks, thread_ts=None):
    client = WebClient(token=SLACK_API_TOKEN)
    try:
        if thread_ts:
            client.chat_update(channel=channel, ts=ts, thread_ts=thread_ts, blocks=blocks)
        else:
            client.chat_update(channel=channel, ts=ts, blocks=blocks)
    except SlackApiError as e:
        print(f"Error updating message on Slack: {e.response['error']}")

def delete_slack_message(channel, ts):
    client = WebClient(token=SLACK_API_TOKEN)
    try:
        client.chat_delete(channel=channel, ts=ts)
    except SlackApiError as e:
        print(f"Error deleting message on Slack: {e.response['error']}")

def generate_dashboard_url(service_id, range_str, is_realtime=False):
    if is_realtime:
        return FASTLY_DASHBOARD_REALTIME_URL.format(service_id=service_id, range=range_str)
    else:
        return FASTLY_DASHBOARD_HISTORICAL_URL.format(service_id=service_id, range=range_str)

def generate_slack_blocks(summary, interval_summary, service_name, environment, service_id, is_realtime):
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":bar_chart: Real-Time Data Summary" if is_realtime else ":bar_chart: Historical Data Summary"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Service Name:*\n<{generate_dashboard_url(service_id, '1m', is_realtime)}|{service_name}>"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Environment:*\n{environment.title()}"
                }
            ]
        },
        {"type": "divider"}
    ]

    for field, value in summary.items():
        interval_value = interval_summary.get(field, 0)
        change_emoji = ""
        if interval_value > 0:
            change_emoji = " :arrow_up:"
        elif interval_value < 0:
            change_emoji = " :arrow_down:"

        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*{field.replace('_', ' ').title()}*\n*Total:* `{format_value(value)}`\n*Last Interval:* `{format_value(interval_value)}` {change_emoji}"
                }
            ]
        })

    if is_realtime:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_You can stop the stream by clicking on the 'Stop' button on this thread._"
            }
        })

    return blocks

def stream_real_time_data(api_token, service_name, environment, service_id, duration, wait_interval=DEFAULT_WAIT_INTERVAL, slack_channel=None, thread_ts=None):
    print(f"Streaming real-time data for {duration} seconds with a wait interval of {wait_interval} seconds...")
    end_time = datetime.utcnow() + timedelta(seconds=duration)
    total_stats = {field: 0 for field in COMMON_FIELDS}
    previous_stats = None

    slack_ts = None
    if slack_channel:
        blocks = generate_slack_blocks(total_stats, {}, service_name, environment, service_id, is_realtime=True)
        channel, slack_ts = send_slack_message(slack_channel, thread_ts, blocks)
    
    try:
        while datetime.utcnow() < end_time:
            time.sleep(wait_interval)
            stats_data = get_real_time_data(api_token, service_id, duration_seconds=wait_interval)
            if not stats_data:
                print("Unable to retrieve real-time data.")
                return

            interval_stats = {field: 0 for field in COMMON_FIELDS}
            for data_point in stats_data:
                for common_field in COMMON_FIELDS:
                    if common_field in data_point['aggregated']:
                        interval_stats[common_field] += data_point['aggregated'][common_field]

            for field in COMMON_FIELDS:
                total_stats[field] += interval_stats[field]

            if slack_channel:
                blocks = generate_slack_blocks(total_stats, interval_stats, service_name, environment, service_id, is_realtime=True)
                update_slack_message(channel, slack_ts, blocks, thread_ts)
                previous_stats = total_stats.copy()
            else:
                print(f"\nReal-Time Data Summary (Last {wait_interval} seconds):")
                for field, value in interval_stats.items():
                    print(f"{field}: {format_value(value)}")
                print("\n---\n")

        if not slack_channel:
            print("\nTotal Real-Time Data Summary:")
            for field, value in total_stats.items():
                print(f"{field}: {format_value(value)}")
            print("\n---\n")
    finally:
        if slack_channel and slack_ts:
            delete_slack_message(slack_channel, slack_ts)

def main(environment=None, service_name=None, field_name=None, duration=None, realtime=False, stream_duration=DEFAULT_STREAM_DURATION, wait_interval=DEFAULT_WAIT_INTERVAL, slack_channel=None, thread_ts=None):
    try:
        if not environment:
            print("No environment specified. Please provide one of the following environments:")
            for env in VALID_ENVIRONMENTS:
                print(f"  - {env}")
            return

        environment = get_environment(environment)
        if not environment:
            print(f"No matching environment found for '{environment}'. Available environments: {VALID_ENVIRONMENTS}")
            return

        if not service_name:
            print("No service name specified. Please provide a service name.")
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

        if realtime:
            stream_real_time_data(API_TOKEN, best_match, environment, service_id, stream_duration, wait_interval, slack_channel, thread_ts)
            print(f"View more details in the Fastly dashboard: {generate_dashboard_url(service_id, f'{stream_duration}s', is_realtime=True)}")
            return

        if not duration:
            print("No duration specified. Please provide a duration in the format 'X minutes ago', 'X hours ago', etc.")
            return

        start_time, end_time, by, range_str = get_time_range(duration)
        if start_time is None or end_time is None:
            print("Failed to parse the duration provided.")
            return

        debug_print(f"Calculated start_time: {datetime.fromtimestamp(start_time)}, end_time: {datetime.fromtimestamp(end_time)}, by: {by}")
        debug_print(f"Retrieving historical data for service '{best_match}' from {start_time} to {end_time}...")
        stats_data = get_historical_data(API_TOKEN, service_id, start_time, end_time, by)
        if not stats_data:
            print(f"Unable to retrieve historical data for service '{best_match}', falling back to real-time data.")
            stream_real_time_data(API_TOKEN, best_match, environment, service_id, stream_duration, wait_interval, slack_channel, thread_ts)
            print(f"View more details in the Fastly dashboard: {generate_dashboard_url(service_id, f'{stream_duration}s', is_realtime=True)}")
            return

        summary = {}
        channel = None
        slack_ts = None
        if not field_name or field_name.lower() == "overview":
            for common_field in COMMON_FIELDS:
                values = [data.get(common_field, 0) for data in stats_data]
                total_value = sum(values)
                formatted_total_value = format_value(total_value)
                summary[common_field] = formatted_total_value
            blocks = generate_slack_blocks(summary, {}, best_match, environment, service_id, is_realtime=False)
            if slack_channel:
                channel, slack_ts = send_slack_message(slack_channel, thread_ts, blocks)
            else:
                pprint(summary)
            return

        matching_field, all_fields = get_matching_field(field_name, stats_data)
        if not matching_field:
            print(f"No matching field found for '{field_name}'")
            return
        
        values = [data.get(matching_field, 0) for data in stats_data]
        total_value = sum(values)
        formatted_total_value = format_value(total_value)
        summary[matching_field] = formatted_total_value

        suggestions = [
            suggestion for suggestion in process.extract(field_name, all_fields, limit=3, scorer=fuzz.WRatio) 
            if suggestion[0] != matching_field.replace(' ', '_').replace('-', '_')
        ]

        if suggestions:
            print("Other close fields you might want to query:")
            for suggestion, score in suggestions:
                print(f"  - {suggestion.replace(' ', '_')}")

        blocks = generate_slack_blocks(summary, {}, best_match, environment, service_id, is_realtime=False)
        if slack_channel:
            send_slack_message(slack_channel, thread_ts, blocks)
        else:
            pprint(summary)

    except Exception as e:
        print(f"An error occurred: {e}")

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
        return duration_parts + ['ago']
    else:
        return None, None

def get_time_range(duration):
    now = datetime.utcnow().replace(second=0, microsecond=0)
    duration_parts = parse_duration(duration)
    if not duration_parts or len(duration_parts) < 2:
        print("Invalid duration format. Supported formats: 'X seconds ago', 'X minutes ago', 'X hours ago', 'X days ago', 'X weeks ago', 'X months ago'")
        return None, None, None, None

    try:
        quantity = int(duration_parts[0])
    except ValueError:
        print(f"Invalid quantity '{duration_parts[0]}' in duration. Must be an integer.")
        return None, None, None, None

    unit = process.extractOne(duration_parts[1], TIME_UNITS, scorer=fuzz.ratio)[0]
    start_time = None
    end_time = now.timestamp()
    by = 'minute'
    range_str = f"{quantity}{unit[0]}" if unit not in ['months', 'month'] else f"{quantity}mo"

    if unit in ['second', 'seconds']:
        start_time = (now - timedelta(seconds=quantity)).timestamp()
        by = 'second'
    elif unit in ['minute', 'minutes']:
        start_time = (now - timedelta(minutes=quantity)).timestamp()
    elif unit in ['hour', 'hours']:
        start_time = (now - timedelta(hours=quantity)).timestamp()
        by = 'minute' if quantity == 1 else 'hour'
    elif unit in ['day', 'days']:
        start_time = (now - timedelta(days=quantity)).timestamp()
        by = 'hour' if quantity == 1 else 'day'
    elif unit in ['week', 'weeks']:
        start_time = (now - timedelta(weeks=quantity)).timestamp()
        by = 'day'
    elif unit in ['month', 'months']:
        start_time = (now - timedelta(days=30 * quantity)).timestamp()
        by = 'day'
    else:
        print("Invalid unit format. Supported units are 'second(s)', 'minute(s)', 'hour(s)', 'day(s)', 'week(s)', 'month(s)'.")
        return None, None, None, None

    debug_print(f"Calculated start_time: {datetime.fromtimestamp(start_time)}, end_time: {datetime.fromtimestamp(end_time)}, by: {by}")
    return start_time, end_time, by, range_str

if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 1 and args[0] == "list_services":
        services = list_services()
        pprint(services)
    elif len(args) == 4 and args[3].lower() == "realtime":
        try:
            ENVIRONMENT = args[0]
            SERVICE_NAME = args[1]
            FIELD_NAME = args[2]
            main(ENVIRONMENT, SERVICE_NAME, FIELD_NAME, realtime=True, slack_channel=SLACK_CHANNEL_ID, thread_ts=SLACK_THREAD_TS)
        except ValueError as e:
            print(f"An error occurred while parsing arguments: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
    elif len(args) == 5 and args[4].lower() == "realtime":
        try:
            ENVIRONMENT = args[0]
            SERVICE_NAME = args[1]
            FIELD_NAME = args[2]
            STREAM_DURATION = int(args[3])
            main(ENVIRONMENT, SERVICE_NAME, FIELD_NAME, realtime=True, stream_duration=STREAM_DURATION, slack_channel=SLACK_CHANNEL_ID, thread_ts=SLACK_THREAD_TS)
        except ValueError as e:
            print(f"An error occurred while parsing arguments: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
    elif len(args) == 6 and args[4].lower() == "realtime":
        try:
            ENVIRONMENT = args[0]
            SERVICE_NAME = args[1]
            FIELD_NAME = args[2]
            STREAM_DURATION = int(args[3])
            WAIT_INTERVAL = int(args[5])
            main(ENVIRONMENT, SERVICE_NAME, FIELD_NAME, realtime=True, stream_duration=STREAM_DURATION, wait_interval=WAIT_INTERVAL, slack_channel=SLACK_CHANNEL_ID, thread_ts=SLACK_THREAD_TS)
        except ValueError as e:
            print(f"An error occurred while parsing arguments: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
    elif len(args) == 4:
        try:
            ENVIRONMENT = args[0]
            SERVICE_NAME = args[1]
            FIELD_NAME = args[2]
            DURATION = args[3]
            main(ENVIRONMENT, SERVICE_NAME, FIELD_NAME, duration=DURATION, slack_channel=SLACK_CHANNEL_ID, thread_ts=SLACK_THREAD_TS)
        except ValueError as e:
            print(f"An error occurred while parsing arguments: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
    else:
        print(f"Usage: python {sys.argv[0]} <environment> <service_name> <field_name|overview> <duration> [realtime <timeout> [wait_interval]]")
        sys.exit(1)
