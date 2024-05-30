terraform {
  required_providers {
    kubiya = {
      source = "kubiya-terraform/kubiya"
    }
  }
}

provider "kubiya" {
  // Your Kubiya API Key will be taken from the
  // environment variable KUBIYA_API_KEY
  // To set the key, please use export KUBIYA_API_KEY="YOUR_API_KEY"
}

resource "kubiya_agent" "agent" {
  // Mandatory Fields
  name         = "Fastly Stats Fetcher" // String
  runner       = "dev-eks-sandbox"     // String
  description  = <<EOT
Fastly Stats Fetcher is an intelligent agent that helps you fetch stats for a specific Fastly service efficiently. It can answer queries related to Fastly services and provide real-time data if needed. You can query using it core metrics from Fastly such as requests, 5xx errors, etc.
EOT
  instructions = <<EOT
As an intelligent agent named Fastly Stats Fetcher, you have the capability to interact with Fastly services efficiently using the provided script.

## The main task you can help with is QUICKLY fetching stats for a specific Fastly service ##

If a user wants to query fastly, you need to make sure to ask the user for the following information:

1. Environment (can be one of: production, dev, qa) - default to production if not provided but ask the user for confirmation if you're going to use the default value
2. Service Name on Fastly (partial name is also fine)
3. Stat to look for on Fastly (e.g., 503, 5xx, requests, overview) - `overview` can cover all general stats - go with it if the user doesn't specify a specific stat to look for
4. Duration (e.g., '30 days ago', '12 hours ago', '30 minutes ago') - default to last 24 hours if not provided
5. **Realtime (Optional)**: The user can ask for real-time data by providing the `realtime` keyword. If the user asks for real-time data, you should provide the data as soon as possible. If the user doesn't provide the `realtime` keyword, you should provide historical data based on the duration provided.

**After you got the minimal required information, quickly execute the `query-fastly` command with the provided parameters.**
- Script usage: query-fastly <environment> <service_name> <field_name|overview> <duration> [realtime <timeout> [wait_interval]]
- Example for Historical data: `query-fastly "production" "yoga" "overview" "60 minutes ago"`
- Example for Real-time data: `query-fastly "production" "yoga" "5xx" realtime`

--> Be fast and efficient, don't talk too much, and provide the data as soon as possible.
EOT
  // Optional fields, String
  model = "azure/gpt-3.5-turbo" // If not provided, Defaults to "azure/gpt-4"
  // If not provided, Defaults to "ghcr.io/kubiyabot/kubiya-agent:stable"
  image = "michaelkubiya/fastly-test:update"

  // Optional Fields:
  // Arrays
  secrets      = ["FASTLY_API_TOKEN"]
  integrations = ["slack"]
  users        = ["alen.ismic@aenetworks.com"]
  groups       = ["Admin", "Users"]
  links = []
  tasks = []
  environment_variables = {
    DEBUG            = "1"
    LOG_LEVEL        = "INFO"
  }
  starters = [
    {
      name = "📈 RealTime Overview - Yoga Prod"
      command      = "Show me the real-time overview of the yoga service on production"
    },
    {
      name = "📈 Find 5xx Errors [REALTIME]"
      command      = "Show me the 5xx errors on production in real-time"
    },
        {
      name = "📈 Find 4xx Errors [REALTIME]"
      command      = "Show me the 4xx errors on production in real-time"
    },
    {
      name = "📈 Find requests data [REALTIME]"
      command      = "Show me the requests data on production in real-time"
    }
  ]
}

output "agent" {
  value = kubiya_agent.agent
}