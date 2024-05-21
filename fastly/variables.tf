variable "agent_name" {
  description = "Name of the Kubernetes agent"
  type        = string
  default     = "fastly-test"
}

variable "runners" {
  description = "Runners for the Kubernetes agent"
  type        = string
  default     = "nats"
}

variable "description" {
  description = "Description of the Kubernetes agent"
  type        = string
  default     = <<EOT
Fastly, an intelligent agent specializing in DevOps tasks, facilitates streamlined interactions with Fastly services through the Fastly API. It prompts users to specify the environment (dev, qa, or production) and the service name, intelligently filtering services based on the environment provided. Users then define the type of data they wish to query, such as 5xx errors, 4xx errors, request counts, cache hit ratio, etc, along with the desired duration. Fastly executes the Fastly stats command dynamically, ensuring accurate querying while handling time intervals appropriately. In case of errors or empty output, Fastly provides intelligent error handling, notifying the user and suggesting relevant metrics to assist in specifying valid queries.
EOT
}

variable "instructions" {
  description = "Instructions for the Kubernetes agent"
  type        = string
  default     = <<EOT
Your primary task is to quickly and efficiently query various fastly services stats using different tools which are available on your environment.
Available tools:
- \`query-fastly\`: A simple and efficient program to query Fastly stats from the API. Usage: 'query-fastly ENVIRONMENT SERVICE_NAME FIELD_NAME DURATION'
Replace 'ENVIRONMENT', 'SERVICE_NAME', 'FIELD_NAME', and 'DURATION' with the actual values you want to use for each variable based on the task.
Example: \`query-fastly "production" "yoga" "503" "1 month ago"\`
EOT
}

variable "model" {
  description = "Model to use for the agent"
  type        = string
  default     = "azure/gpt-4"
}

variable "image" {
  description = "Image for the Kubernetes agent"
  type        = string
  default     = "michaelkubiya/fastly-test:shaked"
}

variable "secrets" {
  description = "Secrets for the Kubernetes agent"
  type        = string
  default     = "FASTLY_API_TOKEN"
}

variable "integrations" {
  description = "Integrations for the Kubernetes agent"
  type        = string
  default     = ""
}

variable "users" {
  description = "Users for the Kubernetes agent"
  type        = string
  default     = "kubiyamg@gmail.com"
}

variable "groups" {
  description = "Groups for the Kubernetes agent"
  type        = string
  default     = "Admin"
}

variable "links" {
  description = "Links for the Kubernetes agent"
  type        = string
  default     = ""
}

variable "starters" {
  description = "Starters for the Kubernetes agent"
  type        = list(object({
    display_name = string
    command      = string
  }))
  default = [
    {
      display_name = "503 - yoga prod"
      command      = "Show me the 503 errors on yoga production service in the last 1 hour"
    },
    {
      display_name = "403 - yoga prod"
      command      = "Show me the 403 errors on yoga production service in the last 1 hour"
    }
  ]
}

variable "tasks" {
  description = "Tasks for the Kubernetes agent"
  type        = list(object({
    name        = string
    prompt      = string
    description = string
  }))
  default = [
    {
      name        = "Query Fastly Stats"
      prompt      = <<EOT
Your task involves the following steps:
1. Gather the required variables from the user:
- 'ENVIRONMENT': The environment (e.g., production, dev, qa) where the Fastly service is deployed.
- 'SERVICE_NAME': The name of the Fastly service you want to interact with.
- 'FIELD_NAME': The name of the field for which you want to retrieve historical data.
- 'DURATION': The duration for which you want to query historical data (e.g., '30 days ago', '12 hours ago', '30 minutes ago'). 
    
2. Execute the query-fastly script with the required arguments based on the collected input.
   
**Note:** For the field, you can provide simple arguments such as 503, 5xx, requests, etc.
EOT
      description = "This task can query different Fastly services for different historical and real-time data."
    }
  ]
}

variable "env_vars" {
  description = "Environment variables for the Kubernetes agent"
  type        = map(string)
  default = {
    DEBUG      = "1"
    LOG_LEVEL  = "INFO"
  }
}
