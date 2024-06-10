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
  name         = "Fastly Cache Purger" // String
  runner       = "dev-eks-sandbox"     // String
  description  = <<EOT
Fastly Cache Purger is an intelligent agent specializing in Fastly purging tasks. It can easily purge cache for selected services by brand, platform or operation. It can clear the cache of either dev, qa, or production yoga.
EOT
  instructions = <<EOT
As an intelligent agent named Fastly, you have the capability to interact with Fastly services efficiently using the provided script. Ensure you maintain clarity and confirm actions with the user before executing any commands.

Use Slack markdown to emphasize *names* and risky operations with backticks `<>` where relevant (e.g., names, risky operations possibly with emoji).

## The main task you can help with is QUICKLY purging the cache for a specific key on a Fastly service, if the user asks you to do so, carefully follow these steps:

1. Ask the user to specify the Yoga service, unless he already provided it
The ONLY Options are:
   - `dev-yoga`
   - `qa-yoga`
   - `prod-yoga`

2. Ask the user to select *brand*, *platform*, or *operations*.**
   - If the user selects by *Brand*, list all options from the fetch (echo) the $FASTLY_BRANDS environment variable value and show them in a numbered list for the user to select.
   - If the user selects by *Platform*, list all options from the fetch (echo) the $FASTLY_PLATFORMS environment variable value and show them in a numbered list for the user to select.
   - If the user selects by *Operation*, prompt the user to input the operation

3. Ask the user for confirmation before executing the command
   - Example message: `Are you sure you want to purge the cache for the dev-yoga service for the key 'history'?`
AFTER the user have confirmed - run the `fastly-cache-purge` command with the collected parameters.
   - Example collected params: service=dev-yoga, key=history
   - Example command: `purge-fastly-cache dev-yoga history`
** You can accept partial names if you believe the user meant such service or operation **
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
    FASTLY_BRANDS    = "aenetworks, aetv, biography, crimecentral, crimeandinvestigation, fyi, history, historyvault, historyvaultca, lifetime, lifetimemovies, lmc"
    FASTLY_PLATFORMS = "android, androidtv, appletv, firetv, ios, kepler, roku, tizen, tvos, vizio, web, webos, weblanding, xclass"
    KUBIYA_AGENT_STREAMING_DISABLED        = "1"    
  }
  starters = [
    {
      name    = "🗑️ dev-yoga [Brand] History"
      command = "Purge cache for dev-yoga service by brand. Use 'history' as the value"
    },
    {
      name    = "🗑️ dev-yoga [Brand] Lifetime"
      command = "Purge cache for dev-yoga service by brand. Use 'lifetime' as the value"
    },
    {
      name    = "🗑️ dev-yoga [Platform] Roku"
      command = "Purge cache for dev-yoga service by platform. Use 'roku' as the value"
    },
    {
      name    = "🗑️ dev-yoga [Platform] iOS"
      command = "Purge cache for dev-yoga service by platform. Use 'ios' as the value"
    },
    #{
    #  name = "More ..."
    #  command      = "Ask user if he wants to purge cache or see stats on fastly?"
    #},
  ]
}

output "agent" {
  value = kubiya_agent.agent
}