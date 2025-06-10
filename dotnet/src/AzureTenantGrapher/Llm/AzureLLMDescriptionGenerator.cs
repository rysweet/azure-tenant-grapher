using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Azure;
using Azure.AI.OpenAI;

namespace AzureTenantGrapher.Llm
{
    public class AzureLLMDescriptionGenerator
    {
        private readonly OpenAIClient _client;

        public AzureLLMDescriptionGenerator(AzureTenantGrapher.Config.AzureOpenAIConfig config)
        {
            _client = new OpenAIClient(new Uri(config.Endpoint), new AzureKeyCredential(config.ApiKey));
        }

        private string ExtractDeploymentName(string endpoint)
        {
            // Assume endpoint ends with /deployments/{name}/...
            var parts = endpoint.TrimEnd('/').Split('/');
            var idx = Array.FindIndex(parts, p => p.Equals("deployments", StringComparison.OrdinalIgnoreCase));
            return idx >= 0 && idx + 1 < parts.Length ? parts[idx + 1] : "";
        }

        public async Task<string> GenerateResourceDescriptionAsync(Dictionary<string, object> resourceData)
        {
            var deployment = ExtractDeploymentName(_client.Endpoint.AbsoluteUri);
            var prompt = $"Describe the Azure resource with properties: {Newtonsoft.Json.JsonConvert.SerializeObject(resourceData)}";
            var response = await _client.GetChatCompletionsAsync(deployment, new ChatCompletionsOptions
            {
                Messages = { new ChatMessage(ChatRole.System, "You are an Azure resource assistant."), new ChatMessage(ChatRole.User, prompt) }
            });
            return response.Value.Choices[0].Message.Content;
        }

        public async Task<string> GenerateRelationshipDescriptionAsync(Dictionary<string, object> sourceResource, Dictionary<string, object> targetResource, string relationshipType)
        {
            var deployment = ExtractDeploymentName(_client.Endpoint.AbsoluteUri);
            var prompt = $"Describe the relationship '{relationshipType}' between source: {Newtonsoft.Json.JsonConvert.SerializeObject(sourceResource)} and target: {Newtonsoft.Json.JsonConvert.SerializeObject(targetResource)}";
            var response = await _client.GetChatCompletionsAsync(deployment, new ChatCompletionsOptions
            {
                Messages = { new ChatMessage(ChatRole.System, "You are an Azure resource assistant."), new ChatMessage(ChatRole.User, prompt) }
            });
            return response.Value.Choices[0].Message.Content;
        }
    }

    public static class LlmFactory
    {
        public static AzureLLMDescriptionGenerator? Create(AzureTenantGrapher.Config.AzureOpenAIConfig? config)
        {
            if (config == null) return null;
            return new AzureLLMDescriptionGenerator(config);
        }
    }
}
