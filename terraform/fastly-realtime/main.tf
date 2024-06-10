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
  name         = "Fastly Realtime" // String
  runner       = "dev-eks-sandbox"     // String
  description  = <<EOT
Fastly Realtime is an intelligent agent that helps you fetch only realtime stats for a specific Fastly service efficiently. It can answer queries related to Fastly services and provide only real-time data. You can query it using core metrics from Fastly such as requests, 5xx errors, etc.
EOT
  instructions = <<EOT
As an intelligent agent named Fastly Realtime, you have the capability to interact with Fastly services efficiently using the provided script.

## The main task you can help with is QUICKLY fetching realtime stats for a specific Fastly service ##

If a user wants to query fastly, you need to make sure to ask the user for the following information:

1. Environment (can be one of: production, dev, qa) - default to production if not provided but ask the user for confirmation if you're going to use the default value
2. Service Name on Fastly (partial name is also fine)
3. Stat to look for on Fastly (e.g., 503, 5xx, requests, overview) - `overview` can cover all general stats - go with it if the user doesn't specify a specific stat to look for

**After you got the minimal required information, quickly execute the `query-fastly` command with the provided parameters.**
- Example for Real-time data query: `query-fastly-realtime "production" "yoga" "overview" realtime`

--> Be fast and efficient, don't talk too much, and provide the data as soon as possible.
EOT
  // Optional fields, String
  model = "azure/gpt-4o" // If not provided, Defaults to "azure/gpt-4"
  // If not provided, Defaults to "ghcr.io/kubiyabot/kubiya-agent:stable"
  image = "michaelkubiya/fastly:latest"

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
    KUBIYA_AGENT_STREAMING_DISABLED        = "1"
  }
  starters = [
    {
      name = "📈 RT Overview - Yoga Prod"
      command      = "Show me the real-time overview of the yoga service on production"
    },
    {
      name = "📈 RT Overview - Pulse Prod"
      command      = "Show me the real-time overview of the pulse service on production"
    },
        {
      name = "📈 RT Overview - Cplay Prod"
      command      = "Show me the real-time overview of the cplay service on production"
    },
    {
      name = "📈 RT Overview - Roku Prod"
      command      = "Show me the real-time overview of the roku service on production"
    },
    {
      name = "📈 RT Overview - Webcenter Prod"
      command      = "Show me the real-time overview of the webcenter service on production"
    }
  ]
}

output "agent" {
  value = kubiya_agent.agent
}